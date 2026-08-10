#!/usr/bin/env python3
"""Validate minute alpha expressions against real feature data.

Checks for:
  - Parse errors (invalid syntax)
  - Undefined fields (not in the contract)
  - Look-ahead bias (delay/delta/returns with n < 1)
  - NaN/Inf ratios exceeding threshold
  - Numerical instability (extreme z-scores)
  - Zero-division and log-of-negative violations

Usage:
    python validate_minute_alphas.py \
        --alphas output/run_001/alphas.json \
        --features output/run_001/features.csv \
        --output output/run_001/validated_alphas.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# Contract
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_FIELDS: set[str] = {
    # VWAP
    "vwap_divergence_close", "vwap_divergence_max", "vwap_divergence_30m",
    "vwap_slope", "vwap_volume_share_last_hour", "vwap_volume_share_first_hour",
    # Order Flow
    "flow_imbalance", "flow_imbalance_last_hour", "flow_imbalance_first_hour",
    "flow_persistence", "buy_volume_ratio", "flow_reversal",
    # Momentum Decay
    "open_30m_return", "open_60m_return", "decay_ratio", "reversal_speed",
    "gap_fill_ratio", "afternoon_momentum", "close_auction_return",
    # Volatility Curve
    "morning_volatility", "afternoon_volatility", "vol_curve_skew",
    "jump_count", "vol_clustering", "range_ratio",
    # Liquidity
    "trade_size_gini", "price_impact_per_trade", "price_impact_tail",
    "liquidity_gap_count", "spread_proxy", "amihud_illiq", "volume_stability",
    # Trade Concentration
    "large_trade_ratio", "trade_concentration_hhi", "block_trade_count",
    "retail_flow_ratio", "institutional_participation",
    # Lead-Lag
    "sector_lead_rank", "peer_correlation_lag1", "information_arrival_speed",
    "lead_lag_strength",
    # Interaction
    "flow_vol_interaction", "vwap_momentum_combo", "liquidity_volatility_ratio",
}

# ═══════════════════════════════════════════════════════════════════════════════
# Load Operators from Catalog
# ═══════════════════════════════════════════════════════════════════════════════

_OPERATORS_PATH = Path(__file__).resolve().parent.parent / "references" / "operators.json"

def _load_operators() -> list[dict]:
    """Load operator definitions from operators.json."""
    if not _OPERATORS_PATH.is_file():
        print(f"[WARN] operators.json not found at {_OPERATORS_PATH}", file=sys.stderr)
        return []
    with open(_OPERATORS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("operators", [])

_OPERATORS = _load_operators()

# Build lookup sets from operator catalog
ALLOWED_FUNCTIONS: set[str] = {op["name"] for op in _OPERATORS}
LOOKAHEAD_FUNCTIONS: set[str] = {
    op["name"] for op in _OPERATORS if op.get("lookahead_risk", False)
}
# Map: name → operator dict
_OPERATOR_MAP: dict[str, dict] = {op["name"]: op for op in _OPERATORS}


def _build_eval_namespace(features_df: pd.DataFrame) -> dict:
    """Build the evaluation namespace from operators.json + feature columns.

    Each operator's numpy_impl is compiled into a callable. Feature columns
    are injected as numpy arrays.
    """
    namespace = {"np": np, "pd": pd}

    # Inject feature columns as numpy arrays
    for col in features_df.columns:
        namespace[col] = features_df[col].values

    # Compile each operator from its numpy_impl
    for op in _OPERATORS:
        name = op["name"]
        impl = op.get("numpy_impl", "")
        if not impl:
            continue
        try:
            # Compile the operator expression. For defs, exec into local_ns
            # first, then extract the function. For lambdas, eval directly.
            local_ns = {}
            exec_globals = {"np": np, "pd": pd}
            if impl.strip().startswith("def "):
                exec(impl, exec_globals, local_ns)
                namespace[name] = local_ns[name]
            elif impl.strip().startswith("lambda"):
                namespace[name] = eval(impl, exec_globals)
            else:
                # Assume it's a function name (like np.sign, np.abs)
                namespace[name] = eval(impl, exec_globals)
        except Exception as e:
            print(f"[WARN] Failed to compile operator '{name}': {e}", file=sys.stderr)

    return namespace

# ═══════════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════════

def extract_field_refs(expression: str) -> set[str]:
    """Extract field variable references from an expression string."""
    # Find words that match allowed field names
    tokens = set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', expression))
    return tokens & ALLOWED_FIELDS


def extract_function_calls(expression: str) -> set[str]:
    """Extract ALL function names used in an expression.

    Returns all function calls found, not just allowed ones.
    Unknown functions are caught later in evaluate_expression.
    """
    return set(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', expression))


def extract_unknown_functions(expression: str) -> set[str]:
    """Extract function names NOT in the operators catalog."""
    all_funcs = extract_function_calls(expression)
    # Filter out: fields (ALLOWED_FIELDS) and standard Python builtins
    known = ALLOWED_FUNCTIONS | ALLOWED_FIELDS | {
        "int", "float", "str", "bool", "list", "dict", "tuple",
        "len", "range", "print", "True", "False", "None",
    }
    return all_funcs - known


def check_lookahead(expression: str) -> list[str]:
    """Check for look-ahead bias in delay/delta/returns calls."""
    issues = []
    for func in LOOKAHEAD_FUNCTIONS:
        # Find calls like delay(x, 0) or delta(x, -1)
        pattern = rf'{func}\s*\([^,)]*,\s*(-?\d+)'
        for match in re.finditer(pattern, expression):
            n = int(match.group(1))
            if n < 1:
                issues.append(
                    f"{func}(..., {n}): n must be ≥ 1 (look-ahead bias)"
                )
    return issues


def check_zero_division(expression: str) -> list[str]:
    """Check for potential division by zero without guard."""
    issues = []
    # Simple check: division by a field directly
    divisions = re.findall(r'/\s*([a-zA-Z_][a-zA-Z0-9_]*)', expression)
    for field in divisions:
        if field in ALLOWED_FIELDS:
            issues.append(
                f"Division by '{field}' without zero-guard. "
                f"Use max({field}, 1e-8) as denominator."
            )
    return issues


def check_log_safety(expression: str) -> list[str]:
    """Check log() calls for negative/zero input."""
    issues = []
    # Find log(x) calls where x is a bare field
    log_calls = re.findall(r'log\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)', expression)
    for field in log_calls:
        if field in ALLOWED_FIELDS:
            issues.append(
                f"log({field}) without clamping. "
                f"Use log(max({field}, 1e-8))."
            )
    return issues


def evaluate_expression(
    expression: str,
    features_df: pd.DataFrame,
    nan_threshold: float = 0.1,
    extreme_threshold: float = 5.0,
) -> dict[str, Any]:
    """Evaluate an alpha expression against the feature DataFrame."""
    result = {"expression": expression, "valid": True, "issues": [], "stats": {}}

    # 1. Check fields
    used_fields = extract_field_refs(expression)
    unknown_fields = used_fields - ALLOWED_FIELDS
    if unknown_fields:
        result["issues"].append(f"Unknown fields: {unknown_fields}")
        result["valid"] = False

    missing_fields = used_fields - set(features_df.columns)
    if missing_fields:
        result["issues"].append(f"Fields not in data: {missing_fields}")
        result["valid"] = False

    # 2. Check functions — flag any operator NOT in operators.json
    unknown_funcs = extract_unknown_functions(expression)
    if unknown_funcs:
        result["issues"].append(f"Unknown operators (not in operators.json): {unknown_funcs}")
        result["valid"] = False

    # 3. Check look-ahead
    la_issues = check_lookahead(expression)
    if la_issues:
        result["issues"].extend(la_issues)
        result["valid"] = False

    # 4. Check zero division
    zd_issues = check_zero_division(expression)
    if zd_issues:
        result["issues"].extend(zd_issues)
        result["valid"] = False

    # 5. Check log safety
    log_issues = check_log_safety(expression)
    if log_issues:
        result["issues"].extend(log_issues)
        result["valid"] = False

    # 6. Try to evaluate
    if result["valid"]:
        try:
            namespace = _build_eval_namespace(features_df)

            # Evaluate
            values = eval(expression, {"__builtins__": {}}, namespace)
            values = np.asarray(values, dtype=float)

            nan_ratio = np.isnan(values).mean()
            inf_ratio = np.isinf(values).mean()
            result["stats"]["nan_ratio"] = float(nan_ratio)
            result["stats"]["inf_ratio"] = float(inf_ratio)

            if nan_ratio > nan_threshold:
                result["issues"].append(f"NaN ratio {nan_ratio:.2%} > {nan_threshold:.0%}")
                result["valid"] = False
            if inf_ratio > 0.0:
                result["issues"].append(f"Inf ratio {inf_ratio:.2%} > 0%")
                result["valid"] = False

            # Z-score check
            finite = values[np.isfinite(values)]
            if len(finite) > 0:
                max_z = np.max(np.abs((finite - np.mean(finite)) / np.std(finite)))
                result["stats"]["max_zscore"] = float(max_z)
                if max_z > extreme_threshold:
                    result["issues"].append(
                        f"Max |z-score| = {max_z:.1f} > {extreme_threshold} (numerically unstable)"
                    )
                    result["valid"] = False

            result["stats"]["mean"] = float(np.nanmean(finite)) if len(finite) > 0 else 0.0
            result["stats"]["std"] = float(np.nanstd(finite)) if len(finite) > 0 else 0.0

        except Exception as e:
            result["issues"].append(f"Evaluation error: {e}")
            result["valid"] = False

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate minute alpha expressions."
    )
    parser.add_argument("--alphas", default=None, help="Input JSON with alphas.")
    parser.add_argument("--features", default=None, help="Features CSV.")
    parser.add_argument("--output", default=None, help="Output JSON path.")
    parser.add_argument(
        "--run-name", default=None,
        help="Run name. Looks in output/run_<ts>_<name>/ for alphas.json and features.csv."
    )
    parser.add_argument(
        "--nan-threshold", type=float, default=0.1,
        help="Max allowed NaN ratio (default: 0.1)."
    )
    parser.add_argument(
        "--extreme-threshold", type=float, default=5.0,
        help="Max allowed z-score (default: 5.0)."
    )
    args = parser.parse_args()

    from datetime import datetime
    if args.run_name:
        out_root = Path(__file__).resolve().parent.parent / "output"
        candidates = sorted(out_root.glob(f"run_*_{args.run_name}"), reverse=True)
        if not candidates:
            print(f"[FATAL] No run dir matching '*_{args.run_name}'", file=sys.stderr)
            sys.exit(1)
        run_dir = candidates[0]
        args.alphas = str(run_dir / "alphas.json")
        args.features = str(run_dir / "features.csv")
        args.output = str(run_dir / "validated_alphas.json")
        print(f"[INFO] Matched: {run_dir.name}", file=sys.stderr)
    elif not args.alphas or not args.features or not args.output:
        print("[FATAL] Requires --alphas, --features, --output, or --run-name.", file=sys.stderr)
        sys.exit(1)

    # Load alphas
    with open(args.alphas, "r", encoding="utf-8") as f:
        alphas_data = json.load(f)

    # Handle both formats: direct array or {"alphas": [...]} object
    if isinstance(alphas_data, list):
        alphas = alphas_data
    elif isinstance(alphas_data, dict) and "alphas" in alphas_data:
        alphas = alphas_data["alphas"]
    else:
        print("[FATAL] Unexpected alphas JSON format.", file=sys.stderr)
        sys.exit(1)

    if not alphas:
        print(
            "[WARN] No alphas to validate. Has the agent filled in the "
            "'alphas' array yet?",
            file=sys.stderr,
        )

    # Load features
    features_df = pd.read_csv(args.features)
    print(
        f"[INFO] Loaded {features_df.shape[0]} rows × {features_df.shape[1]} cols.",
        file=sys.stderr,
    )

    # Validate each alpha
    results = []
    passed = 0
    failed = 0

    for i, alpha in enumerate(alphas):
        expr = alpha.get("expression", "")
        name = alpha.get("name", f"alpha_{i}")
        print(f"\n[VALIDATE] {name}: {expr[:80]}...", file=sys.stderr)

        if not expr:
            results.append({
                **alpha,
                "validation": {"valid": False, "issues": ["Empty expression"]},
            })
            failed += 1
            continue

        validation = evaluate_expression(
            expr, features_df,
            nan_threshold=args.nan_threshold,
            extreme_threshold=args.extreme_threshold,
        )

        if validation["valid"]:
            print(f"  ✓ PASSED", file=sys.stderr)
            passed += 1
        else:
            print(f"  ✗ FAILED: {'; '.join(validation['issues'])}", file=sys.stderr)
            failed += 1

        results.append({**alpha, "validation": validation})

    # Summary
    output = {
        "alphas": results,
        "summary": {
            "total": len(alphas),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(alphas) if alphas else 0.0,
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(
        f"\n[INFO] Validation complete: {passed}/{len(alphas)} passed → {output_path}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
