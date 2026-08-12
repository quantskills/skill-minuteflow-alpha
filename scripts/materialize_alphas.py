#!/usr/bin/env python3
"""Export validated alpha expressions as daily-frequency factor CSVs compatible
with skill-factor-backtest.

Evaluates each alpha expression against features.csv, produces a
date,ticker,factor_value CSV per alpha, with symbol→ticker conversion.

This is an official skill function — use it to bridge minute-derived alphas
to the daily backtest engine regardless of what timeframe the minute data
was originally fetched at.

Usage:
    # Export all alphas from a run
    python materialize_alphas.py --run-name smartmoney

    # Export specific alphas
    python materialize_alphas.py \
        --alphas output/run_001/validated_alphas.json \
        --features output/run_001/features.csv \
        --output-dir output/run_001/backtest_factors/

Output format (per alpha):
    date,ticker,<alpha_name>
    20250102,1,0.0234
    20250102,2,-0.0156
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ═══════════════════════════════════════════════════════════════════════════════
# Paths
# ═══════════════════════════════════════════════════════════════════════════════

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_ROOT = _SCRIPT_DIR.parent
_OPERATORS_PATH = _SKILL_ROOT / "references" / "operators.json"


# ═══════════════════════════════════════════════════════════════════════════════
# Symbol → Ticker
# ═══════════════════════════════════════════════════════════════════════════════

def symbol_to_ticker(symbols: pd.Series) -> pd.Series:
    """Convert '000001.SZ' → 1, '600000.SH' → 600000."""
    return symbols.str.replace(r"\.(SZ|SH)$", "", regex=True).astype(int)


# ═══════════════════════════════════════════════════════════════════════════════
# Operator engine (shared with validate_minute_alphas.py)
# ═══════════════════════════════════════════════════════════════════════════════

def _load_operators() -> list[dict]:
    if not _OPERATORS_PATH.is_file():
        return []
    with open(_OPERATORS_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("operators", [])


def _build_eval_namespace(features_df: pd.DataFrame) -> dict:
    operators = _load_operators()
    ns = {"np": np, "pd": pd}
    for col in features_df.columns:
        ns[col] = features_df[col].values
    for op in operators:
        name = op["name"]
        impl = op.get("numpy_impl", "")
        if not impl:
            continue
        try:
            eg = {"np": np, "pd": pd}
            if impl.strip().startswith("def "):
                ln = {}
                exec(impl, eg, ln)
                ns[name] = ln[name]
            elif impl.strip().startswith("lambda"):
                ns[name] = eval(impl, eg)
            else:
                ns[name] = eval(impl, eg)
        except Exception as e:
            print(f"[WARN] Operator '{name}' compile failed: {e}", file=sys.stderr)
    return ns


def evaluate_expression(expression: str, features_df: pd.DataFrame) -> pd.Series:
    """Evaluate alpha expression → pandas Series aligned to features_df."""
    ns = _build_eval_namespace(features_df)
    values = eval(expression, {"__builtins__": {}}, ns)
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if len(finite) > 0:
        values = np.clip(values, -5 * np.nanstd(finite), 5 * np.nanstd(finite))
    return pd.Series(values, index=features_df.index)


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def materialize_run(alphas_path: str, features_path: str, output_dir: str) -> list[str]:
    with open(alphas_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    alphas = data.get("alphas", data) if isinstance(data, dict) else data
    if isinstance(alphas, dict):
        alphas = alphas.get("alphas", [])

    if not alphas:
        print("[WARN] No alphas found.", file=sys.stderr)
        return []

    features_df = pd.read_csv(features_path)
    print(f"[INFO] {features_df.shape[0]} rows, {len(alphas)} alphas", file=sys.stderr)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []

    for alpha in alphas:
        name = alpha.get("name", "unnamed")
        expr = alpha.get("expression", "")
        if not expr:
            continue

        print(f"[EVAL] {name}: {expr[:70]}...", file=sys.stderr)
        try:
            series = evaluate_expression(expr, features_df)
        except Exception as e:
            print(f"[FAIL] {name}: {e}", file=sys.stderr)
            continue

        out_df = pd.DataFrame({
            "date": features_df["date"].values,
            "ticker": symbol_to_ticker(features_df["symbol"]).values,
            name: series.values,
        }).dropna(subset=[name]).sort_values(["date", "ticker"]).reset_index(drop=True)

        path = out_dir / f"{name}.csv"
        out_df.to_csv(path, index=False)
        files.append(str(path))
        print(f"  ✓ {out_df.shape[0]:,} rows, {out_df['date'].nunique()} dates → {path.name}", file=sys.stderr)

    return files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export minute-derived alphas as daily backtest-ready factor CSVs."
    )
    parser.add_argument("--alphas", default=None, help="Path to validated_alphas.json.")
    parser.add_argument("--features", default=None, help="Path to features.csv.")
    parser.add_argument("--output-dir", default=None, help="Output directory.")
    parser.add_argument(
        "--run-name", default=None,
        help="Run name. Auto-resolves alphas.json, features.csv, and output dir."
    )
    args = parser.parse_args()

    if args.run_name:
        candidates = sorted(
            (_SKILL_ROOT / "output").glob(f"run_*_{args.run_name}"), reverse=True
        )
        if not candidates:
            print(f"[FATAL] No run dir matching '*_{args.run_name}'", file=sys.stderr)
            sys.exit(1)
        rd = candidates[0]
        # Prefer validated
        args.alphas = str(rd / "validated_alphas.json")
        if not Path(args.alphas).is_file():
            args.alphas = str(rd / "alphas.json")
        args.features = str(rd / "features.csv")
        args.output_dir = str(rd / "backtest_factors")
        print(f"[INFO] Run: {rd.name}", file=sys.stderr)

    if not args.alphas or not args.features:
        print("[FATAL] Requires --alphas + --features, or --run-name.", file=sys.stderr)
        sys.exit(1)
    if not args.output_dir:
        args.output_dir = str(Path(args.alphas).parent / "backtest_factors")

    files = materialize_run(args.alphas, args.features, args.output_dir)
    print(f"\n[INFO] {len(files)} factor CSVs → {args.output_dir}", file=sys.stderr)

    if files:
        print(
            f"\nBacktest with skill-factor-backtest:\n"
            f"  python ../skill-factor-backtest/scripts/run_factor_backtest.py \\\n"
            f"    --input-file {files[0]} \\\n"
            f"    --factor-column {Path(files[0]).stem} \\\n"
            f"    --data-root <market_data_dir> \\\n"
            f"    --timespan YYYYMMDD YYYYMMDD",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
