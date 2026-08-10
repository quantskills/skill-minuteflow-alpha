#!/usr/bin/env python3
"""Extract daily-aggregated features from minute-level OHLCV data.

Produces a flat date×symbol table with 40+ minute-derived features across
7 families: VWAP, order flow, momentum decay, volatility curve, liquidity,
trade concentration, lead-lag, and interaction terms.

Also copies the feature definitions JSON to the output directory so every
run has a self-contained record of how each feature was computed.

Usage:
    python extract_minute_features.py \
        --input output/run_001/minute_data.csv \
        --output output/run_001/features.csv
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# Feature Extraction Functions
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_div(a: pd.Series, b: pd.Series, fill: float = 0.0) -> pd.Series:
    """Safe division: a / b, with b=0 replaced by fill."""
    b_safe = b.replace(0, np.nan)
    result = a / b_safe
    return result.fillna(fill)


def extract_vwap_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute VWAP-family features per symbol per date."""
    df = df.copy()
    # Cumulative VWAP per symbol per date
    df["cum_vp"] = df.groupby(["symbol", "date"])["amount"].cumsum()
    df["cum_vol"] = df.groupby(["symbol", "date"])["volume"].cumsum()
    df["vwap_cum"] = _safe_div(df["cum_vp"], df["cum_vol"])

    # Identify bar index per symbol-date
    df["bar_idx"] = df.groupby(["symbol", "date"]).cumcount()

    # Time-based indexing: identify first hour and last hour
    df["minute_int"] = df["minute"].astype(int)
    df["is_first_hour"] = (df["minute_int"] >= 93000) & (df["minute_int"] <= 103000)
    df["is_last_hour"] = (df["minute_int"] >= 140000) & (df["minute_int"] <= 150000)

    results = []

    for (sym, dt), grp in df.groupby(["symbol", "date"]):
        rec = {"symbol": sym, "date": dt}

        close = grp["close"].iloc[-1]
        vwap = grp["vwap_cum"].iloc[-1] if grp["vwap_cum"].iloc[-1] > 0 else close
        rec["vwap_divergence_close"] = (close - vwap) / vwap if vwap > 0 else 0.0

        # Max intraday VWAP divergence
        divs = (grp["close"] - grp["vwap_cum"]) / grp["vwap_cum"].replace(0, np.nan)
        rec["vwap_divergence_max"] = divs.abs().max() if not divs.dropna().empty else 0.0

        # VWAP at 30min
        early = grp[grp["minute_int"] <= 100000]
        if not early.empty and early["vwap_cum"].iloc[-1] > 0:
            vwap_30m = early["vwap_cum"].iloc[-1]
            rec["vwap_divergence_30m"] = (close - vwap_30m) / vwap_30m
        else:
            rec["vwap_divergence_30m"] = 0.0

        # VWAP slope (linear regression of VWAP over bar index)
        x = np.arange(len(grp))
        y = grp["vwap_cum"].values
        mask = ~np.isnan(y) & (y > 0)
        if mask.sum() >= 2:
            slope = np.polyfit(x[mask], y[mask], 1)[0]
            rec["vwap_slope"] = slope / y[mask].mean()  # normalized
        else:
            rec["vwap_slope"] = 0.0

        # Volume share: last hour / total
        total_vol = grp["volume"].sum()
        last_hour_vol = grp.loc[grp["is_last_hour"], "volume"].sum()
        first_hour_vol = grp.loc[grp["is_first_hour"], "volume"].sum()
        rec["vwap_volume_share_last_hour"] = last_hour_vol / total_vol if total_vol > 0 else 0.0
        rec["vwap_volume_share_first_hour"] = first_hour_vol / total_vol if total_vol > 0 else 0.0

        results.append(rec)

    return pd.DataFrame(results)


def extract_order_flow_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute order flow proxy features (no tick data needed)."""
    df = df.copy()

    # Signed volume proxy: bar position within range
    df["bar_range"] = df["high"] - df["low"]
    df["bar_range"] = df["bar_range"].replace(0, np.nan)
    df["close_pos"] = (df["close"] - df["low"]) / df["bar_range"]
    df["close_pos"] = df["close_pos"].fillna(0.5)
    # signed_volume ∈ [-1, 1] scaled to volume
    df["signed_volume"] = (df["close_pos"] - 0.5) * 2 * df["volume"]

    df["minute_int"] = df["minute"].astype(int)
    df["is_last_hour"] = (df["minute_int"] >= 140000) & (df["minute_int"] <= 150000)
    df["is_first_hour"] = (df["minute_int"] >= 93000) & (df["minute_int"] <= 103000)
    df["is_up_bar"] = df["close"] > df["open"]

    results = []
    for (sym, dt), grp in df.groupby(["symbol", "date"]):
        rec = {"symbol": sym, "date": dt}
        total_vol = grp["volume"].sum()

        rec["flow_imbalance"] = (
            grp["signed_volume"].sum() / total_vol if total_vol > 0 else 0.0
        )
        last = grp[grp["is_last_hour"]]
        first = grp[grp["is_first_hour"]]
        last_vol = last["volume"].sum()
        first_vol = first["volume"].sum()

        rec["flow_imbalance_last_hour"] = (
            last["signed_volume"].sum() / last_vol if last_vol > 0 else 0.0
        )
        rec["flow_imbalance_first_hour"] = (
            first["signed_volume"].sum() / first_vol if first_vol > 0 else 0.0
        )

        # Flow persistence: autocorrelation of signed_volume at lag 1
        sv = grp["signed_volume"].values
        if len(sv) >= 3:
            rec["flow_persistence"] = np.corrcoef(sv[:-1], sv[1:])[0, 1] if np.std(sv) > 0 else 0.0
        else:
            rec["flow_persistence"] = 0.0

        rec["buy_volume_ratio"] = (
            grp.loc[grp["is_up_bar"], "volume"].sum() / total_vol if total_vol > 0 else 0.5
        )

        rec["flow_reversal"] = rec["flow_imbalance_first_hour"] - rec["flow_imbalance_last_hour"]

        results.append(rec)

    return pd.DataFrame(results)


def extract_momentum_decay_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute intraday momentum/decay features."""
    df = df.copy()
    df["minute_int"] = df["minute"].astype(int)

    results = []
    for (sym, dt), grp in df.groupby(["symbol", "date"]):
        rec = {"symbol": sym, "date": dt}
        open_price = grp["open"].iloc[0]
        close_price = grp["close"].iloc[-1]
        day_return = (close_price - open_price) / open_price if open_price > 0 else 0.0

        # Open-30m return
        early = grp[grp["minute_int"] <= 100000]
        if not early.empty:
            open_30m_close = early["close"].iloc[-1]
            rec["open_30m_return"] = (open_30m_close - open_price) / open_price if open_price > 0 else 0.0
        else:
            rec["open_30m_return"] = 0.0

        # Open-60m return
        early60 = grp[grp["minute_int"] <= 103000]
        if not early60.empty:
            open_60m_close = early60["close"].iloc[-1]
            rec["open_60m_return"] = (open_60m_close - open_price) / open_price if open_price > 0 else 0.0
        else:
            rec["open_60m_return"] = 0.0

        # Decay ratio
        if abs(day_return) > 1e-8:
            rec["decay_ratio"] = rec["open_30m_return"] / day_return
        else:
            rec["decay_ratio"] = 0.0

        # Reversal speed: minutes until opening return is halved
        rec["reversal_speed"] = 0.0
        if abs(rec["open_30m_return"]) > 1e-6:
            half_target = open_price + 0.5 * (open_30m_close - open_price)
            for i, row in grp.iterrows():
                if (rec["open_30m_return"] > 0 and row["close"] <= half_target) or \
                   (rec["open_30m_return"] < 0 and row["close"] >= half_target):
                    rec["reversal_speed"] = grp.loc[i, "bar_idx"] if "bar_idx" in grp.columns else 0
                    break

        # Gap fill ratio: overnight gap
        # This would need prev_close — approximate with open/previous day's close
        rec["gap_fill_ratio"] = rec.get("open_30m_return", 0.0)

        # Afternoon momentum
        afternoon = grp[grp["minute_int"] >= 130000]
        if not afternoon.empty and afternoon["open"].iloc[0] > 0:
            rec["afternoon_momentum"] = (
                (afternoon["close"].iloc[-1] - afternoon["open"].iloc[0])
                / afternoon["open"].iloc[0]
            )
        else:
            rec["afternoon_momentum"] = 0.0

        # Close auction return (last 5 min)
        if len(grp) >= 2:
            close_5m_before = grp["close"].iloc[-2]
            rec["close_auction_return"] = (
                (close_price - close_5m_before) / close_5m_before
                if close_5m_before > 0 else 0.0
            )
        else:
            rec["close_auction_return"] = 0.0

        results.append(rec)

    return pd.DataFrame(results)


def extract_volatility_curve_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute intraday volatility curve features."""
    df = df.copy()
    df["minute_int"] = df["minute"].astype(int)
    df["bar_return"] = df.groupby("symbol")["close"].pct_change()

    results = []
    for (sym, dt), grp in df.groupby(["symbol", "date"]):
        rec = {"symbol": sym, "date": dt}

        morning = grp[grp["minute_int"] <= 113000]
        afternoon = grp[grp["minute_int"] >= 130000]

        rec["morning_volatility"] = morning["bar_return"].std() if not morning.empty else 0.0
        rec["afternoon_volatility"] = afternoon["bar_return"].std() if not afternoon.empty else 0.0
        rec["vol_curve_skew"] = (
            rec["morning_volatility"] / rec["afternoon_volatility"]
            if rec["afternoon_volatility"] > 1e-10 else 1.0
        )

        # Jump count
        intra_std = grp["bar_return"].std()
        if intra_std and intra_std > 0:
            rec["jump_count"] = (grp["bar_return"].abs() > 3 * intra_std).sum()
        else:
            rec["jump_count"] = 0

        # Vol clustering: autocorrelation of abs returns
        abs_ret = grp["bar_return"].abs().dropna().values
        if len(abs_ret) >= 3:
            rec["vol_clustering"] = np.corrcoef(abs_ret[:-1], abs_ret[1:])[0, 1] if np.std(abs_ret) > 0 else 0.0
        else:
            rec["vol_clustering"] = 0.0

        # Range ratio
        rec["range_ratio"] = (
            (grp["high"].max() - grp["low"].min()) / grp["open"].iloc[0]
            if grp["open"].iloc[0] > 0 else 0.0
        )

        results.append(rec)

    return pd.DataFrame(results)


def extract_liquidity_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute liquidity/microstructure features."""
    df = df.copy()
    results = []

    for (sym, dt), grp in df.groupby(["symbol", "date"]):
        rec = {"symbol": sym, "date": dt}

        # Trade size per bar
        grp = grp.copy()
        grp["trade_size"] = grp["amount"] / grp["num_trades"].replace(0, np.nan)
        sizes = grp["trade_size"].dropna()

        # Gini coefficient
        if len(sizes) >= 2:
            sorted_sizes = np.sort(sizes.values)
            n = len(sorted_sizes)
            index = np.arange(1, n + 1)
            rec["trade_size_gini"] = (
                (2 * np.sum(index * sorted_sizes)) / (n * np.sum(sorted_sizes)) - (n + 1) / n
            ) if np.sum(sorted_sizes) > 0 else 0.0
        else:
            rec["trade_size_gini"] = 0.0

        # Price impact per trade
        grp["price_impact"] = (
            grp["close"].diff().abs() / grp["num_trades"].replace(0, np.nan)
        )
        impacts = grp["price_impact"].dropna()
        rec["price_impact_per_trade"] = impacts.mean() if not impacts.empty else 0.0
        rec["price_impact_tail"] = impacts.quantile(0.95) if not impacts.empty else 0.0

        # Liquidity gaps
        rec["liquidity_gap_count"] = (grp["volume"] == 0).sum() + (grp["num_trades"] == 0).sum()

        # Spread proxy
        grp["spread_proxy"] = (grp["high"] - grp["low"]) / grp["close"].replace(0, np.nan)
        rec["spread_proxy"] = grp["spread_proxy"].mean() if not grp["spread_proxy"].dropna().empty else 0.0

        # Amihud illiquidity
        grp["amihud"] = (
            grp["close"].pct_change().abs() / grp["amount"].replace(0, np.nan)
        )
        rec["amihud_illiq"] = grp["amihud"].dropna().mean() if not grp["amihud"].dropna().empty else 0.0

        # Volume stability
        rec["volume_stability"] = (
            grp["volume"].std() / grp["volume"].mean() if grp["volume"].mean() > 0 else 1.0
        )

        results.append(rec)

    return pd.DataFrame(results)


def extract_trade_concentration_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute trade concentration features."""
    df = df.copy()
    results = []

    for (sym, dt), grp in df.groupby(["symbol", "date"]):
        rec = {"symbol": sym, "date": dt}
        total_vol = grp["volume"].sum()

        # Large trade ratio: bars with amount > 95th percentile
        p95 = grp["amount"].quantile(0.95) if len(grp) >= 20 else grp["amount"].max()
        rec["large_trade_ratio"] = (
            grp.loc[grp["amount"] > p95, "volume"].sum() / total_vol if total_vol > 0 else 0.0
        )

        # HHI of volume share
        vol_shares = grp["volume"] / total_vol if total_vol > 0 else grp["volume"] * 0
        rec["trade_concentration_hhi"] = (vol_shares ** 2).sum()

        # Block trade count: bars > 10× median amount
        median_amt = grp["amount"].median()
        rec["block_trade_count"] = (grp["amount"] > 10 * median_amt).sum() if median_amt > 0 else 0

        # Retail flow ratio: volume in bars with num_trades > median
        median_trades = grp["num_trades"].median()
        rec["retail_flow_ratio"] = (
            grp.loc[grp["num_trades"] > median_trades, "volume"].sum() / total_vol
            if total_vol > 0 else 0.5
        )
        rec["institutional_participation"] = 1.0 - rec["retail_flow_ratio"]

        results.append(rec)

    return pd.DataFrame(results)


def extract_lead_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute lead-lag features (sector-level simplified)."""
    # This is a simplified version — full sector-level requires cross-stock computation.
    # Here we compute per-stock proxies based on intraday dynamics.
    df = df.copy()
    results = []

    for (sym, dt), grp in df.groupby(["symbol", "date"]):
        rec = {"symbol": sym, "date": dt}

        # Information arrival speed: time to reach 50% of total abs return
        abs_ret = grp["close"].pct_change().abs().dropna()
        if len(abs_ret) > 0 and abs_ret.sum() > 0:
            cumsum = abs_ret.cumsum()
            half_point = abs_ret.sum() * 0.5
            idx = (cumsum >= half_point).idxmax() if (cumsum >= half_point).any() else cumsum.index[-1]
            rec["information_arrival_speed"] = grp.index.get_loc(idx) / len(grp) if isinstance(idx, (int, np.integer)) else (
                list(grp.index).index(idx) / len(grp)
            )
        else:
            rec["information_arrival_speed"] = 0.5

        # Simplified lead-lag: just store placeholders for sector-level computation
        rec["sector_lead_rank"] = 0.5  # Placeholder — needs sector peer computation
        rec["peer_correlation_lag1"] = 0.0
        rec["lead_lag_strength"] = 0.0

        results.append(rec)

    return pd.DataFrame(results)


def extract_interaction_features(features: pd.DataFrame) -> pd.DataFrame:
    """Compute interaction features from existing feature columns."""
    df = features.copy()

    if "flow_imbalance" in df.columns and "vol_clustering" in df.columns:
        df["flow_vol_interaction"] = df["flow_imbalance"] * df["vol_clustering"]
    else:
        df["flow_vol_interaction"] = 0.0

    if "vwap_divergence_close" in df.columns and "afternoon_momentum" in df.columns:
        df["vwap_momentum_combo"] = df["vwap_divergence_close"] * df["afternoon_momentum"]
    else:
        df["vwap_momentum_combo"] = 0.0

    if "amihud_illiq" in df.columns and "morning_volatility" in df.columns:
        df["liquidity_volatility_ratio"] = (
            df["amihud_illiq"] / df["morning_volatility"].replace(0, np.nan)
        ).fillna(0.0)
    else:
        df["liquidity_volatility_ratio"] = 0.0

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def extract_all_features(minute_df: pd.DataFrame) -> pd.DataFrame:
    """Run all feature extractors and merge into a single daily table."""
    print("[INFO] Extracting VWAP features...", file=sys.stderr)
    vwap = extract_vwap_features(minute_df)

    print("[INFO] Extracting order flow features...", file=sys.stderr)
    flow = extract_order_flow_features(minute_df)

    print("[INFO] Extracting momentum decay features...", file=sys.stderr)
    momentum = extract_momentum_decay_features(minute_df)

    print("[INFO] Extracting volatility curve features...", file=sys.stderr)
    vol = extract_volatility_curve_features(minute_df)

    print("[INFO] Extracting liquidity features...", file=sys.stderr)
    liq = extract_liquidity_features(minute_df)

    print("[INFO] Extracting trade concentration features...", file=sys.stderr)
    conc = extract_trade_concentration_features(minute_df)

    print("[INFO] Extracting lead-lag features...", file=sys.stderr)
    ll = extract_lead_lag_features(minute_df)

    # Merge all on symbol + date
    dfs = [vwap, flow, momentum, vol, liq, conc, ll]
    merged = dfs[0]
    for d in dfs[1:]:
        merged = merged.merge(d, on=["symbol", "date"], how="outer")

    # Add interaction features
    merged = extract_interaction_features(merged)

    # Drop rows with too many NaNs (stocks with insufficient minute data)
    nan_ratio = merged.isnull().sum(axis=1) / merged.shape[1]
    merged = merged[nan_ratio < 0.5]

    print(
        f"[INFO] Extracted {merged.shape[1]} features for "
        f"{merged['symbol'].nunique()} symbols × {merged['date'].nunique()} dates.",
        file=sys.stderr,
    )

    return merged


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract daily features from minute-level OHLCV data."
    )
    parser.add_argument(
        "--input", default=None,
        help="Input CSV from fetch_minute_data.py."
    )
    parser.add_argument(
        "--output", default=None,
        help="Output features CSV path."
    )
    parser.add_argument(
        "--run-name", default=None,
        help="Run name. Looks in output/run_<ts>_<name>/ for minute_data.csv."
    )
    args = parser.parse_args()

    if args.run_name:
        out_root = Path(__file__).resolve().parent.parent / "output"
        candidates = sorted(out_root.glob(f"run_*_{args.run_name}"), reverse=True)
        if not candidates:
            print(f"[FATAL] No run dir matching '*_{args.run_name}'", file=sys.stderr)
            sys.exit(1)
        run_dir = candidates[0]
        args.input = str(run_dir / "minute_data.csv")
        args.output = str(run_dir / "features.csv")
        print(f"[INFO] Matched: {run_dir.name}", file=sys.stderr)
    elif not args.input or not args.output:
        print("[FATAL] Requires --input and --output, or --run-name.", file=sys.stderr)
        sys.exit(1)

    minute_df = pd.read_csv(args.input)
    print(
        f"[INFO] Loaded {minute_df.shape[0]:,} minute rows from {args.input}.",
        file=sys.stderr,
    )

    features = extract_all_features(minute_df)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_path, index=False)
    print(
        f"[INFO] Saved {features.shape[0]} rows × {features.shape[1]} cols → {output_path}",
        file=sys.stderr,
    )

    # Also copy feature_definitions.json to the output directory
    defs_src = Path(__file__).resolve().parent.parent / "references" / "feature_definitions.json"
    defs_dst = output_path.parent / "feature_definitions.json"
    if defs_src.is_file():
        shutil.copy(defs_src, defs_dst)
        print(f"[INFO] Copied feature definitions → {defs_dst}", file=sys.stderr)


if __name__ == "__main__":
    main()
