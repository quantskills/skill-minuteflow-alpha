#!/usr/bin/env python3
"""Generate alpha factor expressions from a document or natural language query.

Maps document/query concepts to the minute feature catalog and produces
validated alpha expressions following the formula contract in
references/minute_alpha_ops.md.

This script provides the mapping logic and prompt builder. Operators are
loaded from references/operators.json — the LLM may propose new operators
which can be added to that file.

Usage:
    # From a document file
    python generate_minute_alphas.py \
        --doc path/to/paper.txt \
        --features output/run_001/features.csv \
        --n 5 \
        --output output/run_001/alphas.json

    # From a natural language query
    python generate_minute_alphas.py \
        --query "intraday momentum decay predicts next-day reversal" \
        --features output/run_001/features.csv \
        --n 3 \
        --output output/run_001/alphas.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# Load operators catalog
# ═══════════════════════════════════════════════════════════════════════════════

_OPERATORS_PATH = Path(__file__).resolve().parent.parent / "references" / "operators.json"


def _load_operators() -> list[dict]:
    if _OPERATORS_PATH.is_file():
        with open(_OPERATORS_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get("operators", [])
    return []


def _read_document(doc_path: Path) -> str:
    """Read text from a PDF, TXT, or other document file."""
    suffix = doc_path.suffix.lower()
    if suffix == ".pdf":
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(doc_path))
            pages = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
            return "\n\n".join(pages)
        except ImportError:
            print("[WARN] PyPDF2 not installed, trying raw read.", file=sys.stderr)
            return doc_path.read_text(encoding="utf-8", errors="replace")
    elif suffix in (".txt", ".md"):
        return doc_path.read_text(encoding="utf-8", errors="replace")
    else:
        return doc_path.read_text(encoding="utf-8", errors="replace")


def _format_operator_catalog(operators: list[dict]) -> str:
    """Format operator catalog as a readable string for the LLM prompt."""
    by_cat: dict[str, list[dict]] = {}
    for op in operators:
        cat = op.get("category", "other")
        by_cat.setdefault(cat, []).append(op)

    cat_names = {
        "cross_sectional": "Cross-Sectional (per date)",
        "time_series": "Time-Series Rolling",
        "lag": "Lag / Difference",
        "volume": "Volume / Amount Specific",
        "elementwise": "Element-Wise Math",
    }

    lines = []
    for cat_key in ["cross_sectional", "time_series", "lag", "volume", "elementwise"]:
        ops = by_cat.get(cat_key, [])
        if not ops:
            continue
        lines.append(f"\n### {cat_names.get(cat_key, cat_key)}")
        for op in ops:
            lookahead = " ⚠️ LOOKAHEAD-RISK (n≥1 required)" if op.get("lookahead_risk") else ""
            lines.append(f"  {op['signature']:40s} — {op['description']}{lookahead}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Concept → Feature Mapping
# ═══════════════════════════════════════════════════════════════════════════════

CONCEPT_MAP = {
    # VWAP / fair value
    "vwap": ["vwap_divergence_close", "vwap_divergence_max", "vwap_divergence_30m",
             "vwap_slope", "vwap_volume_share_last_hour", "vwap_volume_share_first_hour"],
    "fair value": ["vwap_divergence_close", "vwap_divergence_max"],
    "execution": ["vwap_divergence_close", "vwap_volume_share_last_hour",
                  "large_trade_ratio", "trade_concentration_hhi"],
    "algorithmic trading": ["vwap_divergence_close", "vwap_slope",
                            "trade_concentration_hhi"],

    # Order flow / smart money
    "order flow": ["flow_imbalance", "flow_imbalance_last_hour",
                   "flow_imbalance_first_hour", "flow_persistence",
                   "buy_volume_ratio", "flow_reversal"],
    "smart money": ["flow_imbalance_last_hour", "large_trade_ratio",
                    "institutional_participation"],
    "institutional": ["flow_imbalance_last_hour", "large_trade_ratio",
                      "institutional_participation", "block_trade_count"],
    "buying pressure": ["flow_imbalance", "buy_volume_ratio",
                        "flow_imbalance_last_hour"],
    "selling pressure": ["flow_imbalance", "buy_volume_ratio",
                         "flow_imbalance_last_hour"],

    # Momentum / reversal
    "momentum": ["open_30m_return", "open_60m_return", "afternoon_momentum",
                 "decay_ratio"],
    "reversal": ["decay_ratio", "reversal_speed", "gap_fill_ratio",
                 "flow_reversal", "close_auction_return"],
    "opening gap": ["open_30m_return", "open_60m_return", "decay_ratio",
                    "gap_fill_ratio"],
    "gap close": ["gap_fill_ratio", "decay_ratio", "reversal_speed"],
    "gap fade": ["decay_ratio", "reversal_speed", "gap_fill_ratio"],
    "intraday trend": ["decay_ratio", "afternoon_momentum",
                       "open_30m_return"],

    # Volatility
    "volatility": ["morning_volatility", "afternoon_volatility",
                   "vol_curve_skew", "jump_count", "vol_clustering",
                   "range_ratio"],
    "volatility regime": ["morning_volatility", "afternoon_volatility",
                          "vol_curve_skew", "vol_clustering"],
    "jump": ["jump_count", "range_ratio"],
    "volatility clustering": ["vol_clustering"],
    "u-shape": ["vol_curve_skew", "morning_volatility",
                "afternoon_volatility"],

    # Liquidity / microstructure
    "liquidity": ["trade_size_gini", "price_impact_per_trade",
                  "price_impact_tail", "liquidity_gap_count",
                  "spread_proxy", "amihud_illiq", "volume_stability"],
    "illiquidity": ["amihud_illiq", "price_impact_per_trade",
                    "liquidity_gap_count"],
    "spread": ["spread_proxy", "price_impact_per_trade"],
    "market impact": ["price_impact_per_trade", "price_impact_tail",
                      "amihud_illiq"],
    "volume stability": ["volume_stability"],

    # Trade concentration
    "trade concentration": ["large_trade_ratio", "trade_concentration_hhi",
                            "block_trade_count", "retail_flow_ratio",
                            "institutional_participation"],
    "block trade": ["block_trade_count", "large_trade_ratio"],
    "retail": ["retail_flow_ratio", "trade_size_gini"],
    "herfindahl": ["trade_concentration_hhi"],

    # Lead-lag / information
    "lead-lag": ["sector_lead_rank", "peer_correlation_lag1",
                 "information_arrival_speed", "lead_lag_strength"],
    "information diffusion": ["information_arrival_speed",
                              "sector_lead_rank"],
    "sector leader": ["sector_lead_rank", "peer_correlation_lag1"],
    "information arrival": ["information_arrival_speed"],

    # Interaction
    "interaction": ["flow_vol_interaction", "vwap_momentum_combo",
                    "liquidity_volatility_ratio"],
}


def map_query_to_features(query: str) -> list[str]:
    """Map a natural language query to relevant minute feature columns."""
    query_lower = query.lower()
    matched_features = set()

    for concept, features in CONCEPT_MAP.items():
        if concept in query_lower:
            matched_features.update(features)

    # If nothing matched, return a broad default set
    if not matched_features:
        matched_features = {
            "vwap_divergence_close", "flow_imbalance",
            "decay_ratio", "morning_volatility",
            "amihud_illiq", "large_trade_ratio",
        }

    return sorted(matched_features)


def build_agent_prompt(
    text: str,
    feature_columns: list[str],
    n_alphas: int,
    features_df: Optional[pd.DataFrame] = None,
    operators: Optional[list[dict]] = None,
) -> str:
    """Build the prompt for the LLM agent to generate alpha expressions."""
    if operators is None:
        operators = _load_operators()

    operator_catalog = _format_operator_catalog(operators)
    # Feature statistics for context
    feature_stats = ""
    if features_df is not None:
        stats_lines = []
        for col in feature_columns:
            if col in features_df.columns:
                s = features_df[col]
                stats_lines.append(
                    f"  {col}: mean={s.mean():.4f}, std={s.std():.4f}, "
                    f"min={s.min():.4f}, max={s.max():.4f}"
                )
        if stats_lines:
            feature_stats = (
                "\nFEATURE STATISTICS (for context):\n"
                + "\n".join(stats_lines[:20])
                + "\n"
            )

    prompt = f"""You are a quantitative researcher specializing in intraday
market microstructure. Based on the following document or query, generate
exactly {n_alphas} novel alpha factor expressions for stock selection using
MINUTE-DERIVED daily features.

DOCUMENT / QUERY:
{text}

AVAILABLE MINUTE-DERIVED FEATURES (date × symbol DataFrames):
{chr(10).join(f'  - {f}' for f in feature_columns)}

{feature_stats}
AVAILABLE OPERATORS (from operators.json):
{operator_catalog}

OPERATOR EXTENSION RULE:
You MAY propose NEW operators not listed above if the document/query requires
a custom computation. For each new operator, provide:
  - "new_operator": {{"name": "...", "signature": "...", "description": "...", "category": "..", "numpy_impl": "lambda ..."}}
  - The operator will be added to operators.json and validated.
Standard arithmetic (+, -, *, /) and parentheses are always available.

FEATURE EXTENSION RULE:
You MAY define NEW minute-derived features if the document/query requires a
signal not present in the catalog. Each new feature must be computable as an
expression over EXISTING features and operators, provided in a "new_features"
list (top-level or on each alpha):
  "new_features": [{{"name": "my_feature", "expression": "ts_mean(flow_imbalance, 5) / max(amihud_illiq, 1e-8)", "description": "...", "formula": "...", "family": "custom"}}]
- New features are computed in declaration order; later features may reference earlier ones.
- Do NOT reuse an existing catalog field name.

CRITICAL — LOOK-AHEAD BIAS PREVENTION:
- delay(x, n), delta(x, n), and returns(x, n) MUST use n ≥ 1
- All rolling functions inherently use only past data — this is correct

CRITICAL — NUMERICAL STABILITY:
- Never divide by something that could be zero. Use max(denom, 1e-8).
- Never take log(x) without ensuring x > 0: use log(max(x, 1e-8)).
- Prefer rank() and zscore() based expressions — they are naturally stable.

REQUIRED — ACADEMIC ATTRIBUTION:
- For each alpha, cite the specific academic paper, research article, or
  document passage that inspired it in a "source" field (full APA citation).
- Provide a "source_link" with a DOI or arXiv URL. Use null if unavailable.

OUTPUT FORMAT:
Return a JSON array of objects with keys:
  name, expression, description, rationale, signal_family, source, source_link,
  new_operator (optional, only if proposing a new operator),
  new_features (optional, list of custom feature definitions)

Where signal_family is one of:
  vwap, order_flow, momentum_decay, volatility_curve, liquidity,
  trade_concentration, lead_lag, interaction
"""
    return prompt


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate alpha expressions from document or NL query."
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--doc", help="Path to document file.")
    input_group.add_argument("--query", help="Natural language query.")
    parser.add_argument("--features", default=None, help="Features CSV path.")
    parser.add_argument("--n", type=int, default=5, help="Number of alphas to generate.")
    parser.add_argument("--output", default=None, help="Output JSON path.")
    parser.add_argument(
        "--run-name", default=None,
        help="Run name. Looks in output/run_<ts>_<name>/ for features.csv."
    )
    args = parser.parse_args()

    if args.run_name:
        out_root = Path(__file__).resolve().parent.parent / "output"
        candidates = sorted(out_root.glob(f"run_*_{args.run_name}"), reverse=True)
        if not candidates:
            print(f"[FATAL] No run dir matching '*_{args.run_name}'", file=sys.stderr)
            sys.exit(1)
        run_dir = candidates[0]
        args.features = str(run_dir / "features.csv")
        args.output = str(run_dir / "alphas.json")
        print(f"[INFO] Matched: {run_dir.name}", file=sys.stderr)
    elif not args.features or not args.output:
        print("[FATAL] Requires --features and --output, or --run-name.", file=sys.stderr)
        sys.exit(1)

    # Load features for statistics
    features_df = pd.read_csv(args.features)
    feature_columns = sorted(
        [c for c in features_df.columns if c not in ("symbol", "date")]
    )
    print(
        f"[INFO] Loaded {len(feature_columns)} feature columns from {args.features}.",
        file=sys.stderr,
    )

    # Read input text
    if args.doc:
        doc_path = Path(args.doc)
        if not doc_path.is_file():
            print(f"[FATAL] Document not found: {args.doc}", file=sys.stderr)
            sys.exit(1)
        text = _read_document(doc_path)
        print(f"[INFO] Read document: {len(text)} chars.", file=sys.stderr)
    else:
        text = args.query
        print(f"[INFO] Using query: {args.query[:80]}...", file=sys.stderr)

    # Map query to relevant features
    if args.query:
        relevant = map_query_to_features(args.query)
        # Filter to columns actually in the features
        relevant = [f for f in relevant if f in feature_columns]
        print(
            f"[INFO] Query mapped to {len(relevant)} relevant features: "
            f"{relevant[:8]}...",
            file=sys.stderr,
        )
    else:
        relevant = feature_columns

    # Build the agent prompt
    operators = _load_operators()
    prompt = build_agent_prompt(
        text=text,
        feature_columns=relevant,
        n_alphas=args.n,
        features_df=features_df,
        operators=operators,
    )

    # Output: save prompt + template JSON for the agent
    output = {
        "prompt": prompt,
        "n_alphas": args.n,
        "relevant_features": relevant,
        "all_features": feature_columns,
        "input_type": "document" if args.doc else "query",
        "operators_catalog": str(_OPERATORS_PATH),
        "operator_count": len(operators),
        "instructions": (
            "Pass the 'prompt' field to an LLM agent (Claude, GPT-4, etc.). "
            "The agent should return a JSON array of alpha objects with keys: "
            "name, expression, description, rationale, signal_family, source, source_link. "
            "Optionally include 'new_operator' to propose a new function, or "
            "'new_features' to define custom minute features. "
            "Then run validate_minute_alphas.py to check correctness."
        ),
        "alphas": [],  # To be filled by the agent
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(
        f"[INFO] Prompt saved → {output_path}\n"
        f"[INFO] Feed this prompt to an LLM agent. The agent should return "
        f"{args.n} alpha objects as a JSON array.",
        file=sys.stderr,
    )
    print(f"\n{'='*60}\nPROMPT PREVIEW:\n{'='*60}\n{prompt[:1500]}...", file=sys.stderr)


if __name__ == "__main__":
    main()
