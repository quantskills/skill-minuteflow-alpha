#!/usr/bin/env python3
"""Expand alpha expressions by substituting each feature with its formula from
feature_definitions.json, showing the full derivation from raw minute data.

Usage:
    python expand_formula.py \
        --alphas output/run_001/alphas.json \
        --definitions references/feature_definitions.json \
        --output output/run_001/expanded_alphas.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_definitions(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def expand_expression(
    expression: str, definitions: dict, depth: int = 0, max_depth: int = 3
) -> str:
    """Recursively substitute each feature name with its formula.

    Args:
        expression: Alpha expression string.
        definitions: Feature definitions dict (features key → {formula, derivation, ...}).
        depth: Current recursion depth.
        max_depth: Maximum substitution depth (features are leaves, stop at 1).

    Returns:
        Expression string with features annotated inline.
    """
    features = definitions.get("features", {})
    if not features or depth >= max_depth:
        return expression

    result = expression
    for name, info in sorted(features.items(), key=lambda x: -len(x[0])):
        formula = info.get("formula", "")
        if not formula:
            continue
        # Only substitute if the feature name appears as a standalone token
        # (not as part of another feature name)
        import re
        pattern = rf'\b{re.escape(name)}\b'
        if re.search(pattern, result):
            replacement = f"/*{name}*/[{formula}]"
            result = re.sub(pattern, replacement, result)

    return result


def expand_alphas(alphas: list[dict], definitions: dict) -> list[dict]:
    """Add expanded_formula field to each alpha."""
    for alpha in alphas:
        expr = alpha.get("expression", "")
        expanded = expand_expression(expr, definitions)
        alpha["expanded_formula"] = expanded

        # Also add feature derivations used
        used_features = []
        features = definitions.get("features", {})
        for name in features:
            import re
            if re.search(rf'\b{re.escape(name)}\b', expr):
                info = features[name]
                used_features.append({
                    "feature": name,
                    "formula": info.get("formula", ""),
                    "description": info.get("description", ""),
                    "family": info.get("family", ""),
                })
        alpha["features_used"] = used_features

    return alphas


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Expand alpha expressions with feature-level formulas."
    )
    parser.add_argument("--alphas", required=True, help="Path to alphas JSON.")
    parser.add_argument(
        "--definitions",
        default=None,
        help="Path to feature_definitions.json. Auto-detected from run directory.",
    )
    parser.add_argument("--output", required=True, help="Output JSON path.")
    args = parser.parse_args()

    # Load alphas
    with open(args.alphas, "r", encoding="utf-8") as f:
        data = json.load(f)
    alphas = data.get("alphas", data) if isinstance(data, dict) else data
    if isinstance(alphas, dict):
        alphas = alphas.get("alphas", [])

    # Auto-detect definitions
    if not args.definitions:
        alphas_dir = Path(args.alphas).parent
        candidate = alphas_dir / "feature_definitions.json"
        if candidate.is_file():
            args.definitions = str(candidate)
        else:
            # Try skill references
            candidate = (
                Path(__file__).resolve().parent.parent
                / "references"
                / "feature_definitions.json"
            )
            if candidate.is_file():
                args.definitions = str(candidate)

    if not args.definitions:
        print("[FATAL] feature_definitions.json not found.", file=sys.stderr)
        sys.exit(1)

    definitions = load_definitions(args.definitions)
    print(
        f"[INFO] Loaded {len(definitions.get('features', {}))} features from definitions.",
        file=sys.stderr,
    )

    alphas = expand_alphas(alphas, definitions)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(alphas, f, indent=2, ensure_ascii=False)

    print(f"[INFO] Expanded {len(alphas)} alphas → {output_path}", file=sys.stderr)

    # Print a preview
    for alpha in alphas[:3]:
        print(f"\n  {alpha['name']}:")
        print(f"    raw:       {alpha['expression'][:80]}")
        print(f"    expanded:  {alpha['expanded_formula'][:120]}...")


if __name__ == "__main__":
    main()
