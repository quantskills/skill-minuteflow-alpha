#!/usr/bin/env python3
"""Feature extractor: symbol-level with suppressed warnings for performance."""

import argparse, shutil, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def _safe_autocorr(x):
    """Lag-1 autocorrelation, returns 0 on degenerate input."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 3: return 0.0
    std = float(np.std(x))
    if std < 1e-15: return 0.0
    c = np.corrcoef(x[:-1], x[1:])
    return float(c[0, 1]) if not np.isnan(c[0, 1]) else 0.0


def _process_one_symbol(grp: pd.DataFrame) -> pd.DataFrame:
    """Extract all features for one symbol. All derived columns added first."""

    grp["minute_int"] = grp["minute"].astype(int)
    grp["cum_vp"] = grp.groupby("date")["amount"].cumsum()
    grp["cum_vol"] = grp.groupby("date")["volume"].cumsum()
    grp["vwap_cum"] = (grp["cum_vp"] / grp["cum_vol"].replace(0, np.nan)).fillna(grp["close"])
    bar_range = grp["high"] - grp["low"]
    grp["close_pos"] = ((grp["close"] - grp["low"]) / bar_range.replace(0, np.nan)).fillna(0.5)
    grp["signed_volume"] = (grp["close_pos"] - 0.5) * 2 * grp["volume"]
    grp["is_up_bar"] = grp["close"] > grp["open"]
    grp["bar_return"] = grp["close"].pct_change().where(grp["date"] == grp["date"].shift())
    grp["trade_size"] = grp["amount"] / grp["num_trades"].replace(0, np.nan)
    grp["price_impact"] = grp["close"].diff().abs() / grp["num_trades"].replace(0, np.nan)
    grp["spread_proxy_col"] = (grp["high"] - grp["low"]) / grp["close"].replace(0, np.nan)
    grp["amihud_col"] = grp["close"].pct_change().abs() / grp["amount"].replace(0, np.nan)

    gb = grp.groupby("date", sort=False)

    is_30m = grp["minute_int"] <= 100000
    is_60m = grp["minute_int"] <= 103000
    is_last = (grp["minute_int"] >= 140000) & (grp["minute_int"] <= 150000)
    is_first = (grp["minute_int"] >= 93000) & (grp["minute_int"] <= 103000)
    is_morning = grp["minute_int"] <= 113000
    is_afternoon = grp["minute_int"] >= 130000

    close_last = gb["close"].last()
    open_price = gb["open"].first()
    high_max = gb["high"].max()
    low_min = gb["low"].min()
    total_vol = gb["volume"].sum()

    results = pd.DataFrame(index=close_last.index)

    # ── VWAP ───────────────────────
    vwap_last = gb["vwap_cum"].last()
    vwap_safe = vwap_last.where(vwap_last > 0, close_last)
    vwap_div = (grp["close"] - grp["vwap_cum"]) / grp["vwap_cum"].replace(0, np.nan)
    vwap_div_max = vwap_div.abs().groupby(grp["date"]).max()

    vwap_30m = grp[is_30m].groupby("date")["vwap_cum"].last().reindex(close_last.index)
    vwap_30m = vwap_30m.where(vwap_30m > 0, close_last)

    last_vol = grp[is_last].groupby("date")["volume"].sum().reindex(close_last.index, fill_value=0)
    first_vol = grp[is_first].groupby("date")["volume"].sum().reindex(close_last.index, fill_value=0)

    results["vwap_divergence_close"] = ((close_last - vwap_safe) / vwap_safe.replace(0, np.nan)).fillna(0).values
    results["vwap_divergence_max"] = vwap_div_max.fillna(0).values
    results["vwap_divergence_30m"] = ((close_last - vwap_30m) / vwap_30m.replace(0, np.nan)).fillna(0).values
    results["vwap_volume_share_last_hour"] = (last_vol / total_vol.replace(0, np.nan)).fillna(0).values
    results["vwap_volume_share_first_hour"] = (first_vol / total_vol.replace(0, np.nan)).fillna(0).values

    def _vslope(g):
        y = g["vwap_cum"].values; m = ~np.isnan(y) & (y > 0)
        if m.sum() < 2: return 0.0
        return float(np.polyfit(np.arange(len(g))[m], y[m], 1)[0] / y[m].mean())
    results["vwap_slope"] = gb.apply(_vslope).reindex(close_last.index, fill_value=0).values

    # ── Order Flow ──────────────────
    signed_sum = gb["signed_volume"].sum()
    buy_vol = grp[grp["is_up_bar"]].groupby("date")["volume"].sum().reindex(close_last.index, fill_value=0)
    slast = grp[is_last].groupby("date")["signed_volume"].sum().reindex(close_last.index, fill_value=0)
    sfirst = grp[is_first].groupby("date")["signed_volume"].sum().reindex(close_last.index, fill_value=0)

    results["flow_imbalance"] = (signed_sum / total_vol.replace(0, np.nan)).fillna(0).values
    results["flow_imbalance_last_hour"] = (slast / last_vol.replace(0, np.nan)).fillna(0).values
    results["flow_imbalance_first_hour"] = (sfirst / first_vol.replace(0, np.nan)).fillna(0).values
    results["buy_volume_ratio"] = (buy_vol / total_vol.replace(0, np.nan)).fillna(0.5).values
    results["flow_reversal"] = results["flow_imbalance_first_hour"] - results["flow_imbalance_last_hour"]

    def _fpers(g):
        return _safe_autocorr(g["signed_volume"].values)
    results["flow_persistence"] = gb.apply(_fpers).reindex(close_last.index, fill_value=0).values

    # ── Momentum Decay ──────────────
    close_30m_c = grp[is_30m].groupby("date")["close"].last().reindex(close_last.index)
    close_60m_c = grp[is_60m].groupby("date")["close"].last().reindex(close_last.index)
    aft_open = grp[is_afternoon].groupby("date")["open"].first().reindex(close_last.index)
    aft_close = grp[is_afternoon].groupby("date")["close"].last().reindex(close_last.index)

    o30 = ((close_30m_c - open_price) / open_price.replace(0, np.nan)).fillna(0)
    o60 = ((close_60m_c - open_price) / open_price.replace(0, np.nan)).fillna(0)
    day_ret = ((close_last - open_price) / open_price.replace(0, np.nan)).fillna(0)
    afternoon_ret = ((aft_close - aft_open) / aft_open.replace(0, np.nan)).fillna(0)
    close_prev = gb["close"].nth(-2).reindex(close_last.index)
    close_auc = ((close_last - close_prev) / close_prev.replace(0, np.nan)).fillna(0)

    results["open_30m_return"] = o30.values
    results["open_60m_return"] = o60.values
    results["decay_ratio"] = (o30 / day_ret.replace(0, np.nan)).fillna(0).values
    results["gap_fill_ratio"] = o30.values
    results["afternoon_momentum"] = afternoon_ret.values
    results["close_auction_return"] = close_auc.values

    def _rspeed(g):
        op = float(g["open"].iloc[0])
        e30 = g[g["minute_int"] <= 100000]
        if e30.empty or op <= 0: return 0.0
        o30v = float(e30["close"].iloc[-1] - op) / op
        if abs(o30v) < 1e-6: return 0.0
        half = op + 0.5 * (e30["close"].iloc[-1] - op)
        after = g[g["minute_int"] > 100000]
        if after.empty: return 0.0
        cross = after[after["close"] <= half] if o30v > 0 else after[after["close"] >= half]
        return 0.0 if cross.empty else float(g.index.get_loc(cross.index[0]) + 1)
    results["reversal_speed"] = gb.apply(_rspeed).reindex(close_last.index, fill_value=0).values

    # ── Volatility Curve ────────────
    morning_vol = grp[is_morning].groupby("date")["bar_return"].std().reindex(close_last.index, fill_value=0)
    aft_vol = grp[is_afternoon].groupby("date")["bar_return"].std().reindex(close_last.index, fill_value=0)

    results["morning_volatility"] = morning_vol.values
    results["afternoon_volatility"] = aft_vol.values
    results["vol_curve_skew"] = (morning_vol / aft_vol.replace(0, np.nan)).fillna(1.0).values
    results["range_ratio"] = ((high_max - low_min) / open_price.replace(0, np.nan)).fillna(0).values

    def _jcnt(g):
        r = g["bar_return"].dropna(); sd = float(r.std()) if len(r) > 0 else 0.0
        return int((r.abs() > 3*sd).sum()) if sd > 0 else 0
    results["jump_count"] = gb.apply(_jcnt).reindex(close_last.index, fill_value=0).values

    def _vclust(g):
        return _safe_autocorr(np.abs(g["bar_return"].dropna().values))
    results["vol_clustering"] = gb.apply(_vclust).reindex(close_last.index, fill_value=0).values

    # ── Liquidity ──────────────────
    results["price_impact_per_trade"] = gb["price_impact"].mean().reindex(close_last.index, fill_value=0).values
    results["price_impact_tail"] = gb["price_impact"].quantile(0.95).reindex(close_last.index, fill_value=0).values
    results["liquidity_gap_count"] = gb.apply(
        lambda g: int((g["volume"]==0).sum() + (g["num_trades"]==0).sum())
    ).reindex(close_last.index, fill_value=0).values
    results["spread_proxy"] = gb["spread_proxy_col"].mean().reindex(close_last.index, fill_value=0).values
    results["amihud_illiq"] = gb["amihud_col"].mean().reindex(close_last.index, fill_value=0).values
    results["volume_stability"] = (gb["volume"].std() / gb["volume"].mean().replace(0, np.nan)).fillna(1.0).values

    def _gini_ts(g):
        x = np.sort(g["trade_size"].dropna().values.astype(float))
        if len(x) < 2 or x.sum() == 0: return 0.0
        n = len(x)
        return (2 * np.sum(np.arange(1, n+1) * x)) / (n * x.sum()) - (n+1)/n
    results["trade_size_gini"] = gb.apply(_gini_ts).reindex(close_last.index, fill_value=0).values

    # ── Trade Concentration ────────
    def _conc(g):
        tv = g["volume"].sum()
        p95 = g["amount"].quantile(0.95) if len(g) >= 20 else g["amount"].max()
        ma = g["amount"].median(); mt = g["num_trades"].median()
        vs = g["volume"] / tv if tv > 0 else g["volume"] * 0
        ret = g.loc[g["num_trades"] > mt, "volume"].sum() / tv if tv > 0 else 0.5
        return pd.Series({
            "large_trade_ratio": g.loc[g["amount"] > p95, "volume"].sum() / tv if tv > 0 else 0.0,
            "trade_concentration_hhi": float((vs**2).sum()),
            "block_trade_count": int((g["amount"] > 10*ma).sum()) if ma > 0 else 0,
            "retail_flow_ratio": ret,
            "institutional_participation": 1.0 - ret,
        })
    conc_feats = gb.apply(_conc)
    for c in conc_feats.columns:
        results[c] = conc_feats[c].reindex(close_last.index, fill_value=0).values

    # ── Lead-Lag ────────────────────
    def _ll(g):
        ar = g["close"].pct_change().abs().dropna(); sp = 0.5
        if len(ar) > 0 and ar.sum() > 0:
            cs = ar.cumsum(); half = ar.sum() * 0.5
            if (cs >= half).any():
                idx = (cs >= half).idxmax()
                pos = np.where(g.index == idx)[0]
                sp = float(pos[0]) / max(len(g), 1) if len(pos) > 0 else 0.5
        return pd.Series({"information_arrival_speed": sp, "sector_lead_rank": 0.5,
            "peer_correlation_lag1": 0.0, "lead_lag_strength": 0.0})
    ll_feats = gb.apply(_ll)
    for c in ll_feats.columns:
        results[c] = ll_feats[c].reindex(close_last.index, fill_value=0).values

    return results


def extract_all_features(minute_df: pd.DataFrame) -> pd.DataFrame:
    df = minute_df.copy()
    df["date"] = df["date"].astype(str)

    print(f"[INFO] {df['symbol'].nunique()} symbols × {df['date'].nunique()} dates", file=sys.stderr)
    print("[INFO] Processing symbols...", file=sys.stderr)

    all_feats = []
    for i, (sym, grp) in enumerate(df.groupby("symbol", sort=False)):
        if (i + 1) % 50 == 0:
            print(f"[INFO]   {i+1}/{df['symbol'].nunique()}...", file=sys.stderr)
        feats = _process_one_symbol(grp)
        feats["symbol"] = sym
        all_feats.append(feats.reset_index())

    merged = pd.concat(all_feats, ignore_index=True)

    merged["flow_vol_interaction"] = merged["flow_imbalance"] * merged["vol_clustering"].fillna(0)
    merged["vwap_momentum_combo"] = merged["vwap_divergence_close"] * merged["afternoon_momentum"].fillna(0)
    merged["liquidity_volatility_ratio"] = (
        merged["amihud_illiq"] / merged["morning_volatility"].replace(0, np.nan)
    ).fillna(0.0)

    nr = merged.isnull().sum(axis=1) / merged.shape[1]
    merged = merged[nr < 0.5]

    print(f"[INFO] {merged.shape[1]} features, {merged['symbol'].nunique()} sym × {merged['date'].nunique()} dates",
          file=sys.stderr)
    return merged


def main():
    p = argparse.ArgumentParser(description="Extract daily features from minute OHLCV.")
    p.add_argument("--input", default=None)
    p.add_argument("--output", default=None)
    p.add_argument("--run-name", default=None)
    a = p.parse_args()
    if a.run_name:
        r = sorted((Path(__file__).resolve().parent.parent / "output").glob(f"run_*_{a.run_name}"), reverse=True)
        if not r:
            print("[FATAL] No run dir", file=sys.stderr); sys.exit(1)
        a.input = str(r[0] / "minute_data.csv")
        a.output = str(r[0] / "features.csv")
        print(f"[INFO] {r[0].name}", file=sys.stderr)
    if not a.input or not a.output:
        print("[FATAL] --input --output or --run-name", file=sys.stderr); sys.exit(1)
    df = pd.read_csv(a.input)
    print(f"[INFO] {df.shape[0]:,} rows", file=sys.stderr)
    feats = extract_all_features(df)
    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    feats.to_csv(out, index=False)
    print(f"[INFO] Saved → {out}", file=sys.stderr)
    src = Path(__file__).resolve().parent.parent / "references" / "feature_definitions.json"
    dst = out.parent / "feature_definitions.json"
    if src.is_file():
        shutil.copy(src, dst)
        print(f"[INFO] Definitions → {dst}", file=sys.stderr)


if __name__ == "__main__":
    main()
