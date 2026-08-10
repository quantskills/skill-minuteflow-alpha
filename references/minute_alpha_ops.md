# Minute Alpha Expression — Field & Function Contract

This document defines the exact contract for minute-derived alpha expressions.
All generated expressions **must** use only the fields and functions listed below.

> **Complete computation formulas and derivations are in [`feature_definitions.json`](feature_definitions.json).**
> Every run copies this file to the output directory as `feature_definitions.json`.

## Available Field Variables

These are daily-aggregated features extracted from minute bars.
Each field is a `date × symbol` DataFrame. Fields are grouped by signal family.

### VWAP Family

| Field | Formula | Description |
|:---|:---|:---|
| `vwap_divergence_close` | `(close_eod − VWAP_eod) / VWAP_eod` | Close relative to cumulative VWAP. >0 = close above fair value. |
| `vwap_divergence_max` | `max(|close_i − VWAP_cum_i| / VWAP_cum_i)` | Max intraday deviation from VWAP. |
| `vwap_divergence_30m` | `(close_eod − VWAP_30m) / VWAP_30m` | Close vs VWAP after first 30 min. |
| `vwap_slope` | `slope(VWAP_cum) / mean(VWAP_cum)` | Normalized VWAP trend. >0 = rising (buying pressure). |
| `vwap_volume_share_last_hour` | `Σvol(14:00–15:00) / Σvol(day)` | Fraction of volume in last hour. |
| `vwap_volume_share_first_hour` | `Σvol(09:30–10:30) / Σvol(day)` | Fraction of volume in first hour. |

### Order Flow Family (Proxy — no tick data needed)

| Field | Formula | Description |
|:---|:---|:---|
| `flow_imbalance` | `Σ signed_vol / Σ vol` | Net buy/sell pressure. signed_vol = `((close−low)/(high−low)−0.5)×2×vol`. |
| `flow_imbalance_last_hour` | Same, 14:00–15:00 only | Last-hour flow. >0 = late buying (positioning). |
| `flow_imbalance_first_hour` | Same, 09:30–10:30 only | First-hour flow. >0 = opening follow-through. |
| `flow_persistence` | `corr(signed_vol[0:−1], signed_vol[1:])` | Lag-1 autocorr of signed volume. >0 = trending flow. |
| `buy_volume_ratio` | `Σvol(close>open) / Σvol(day)` | Fraction of volume in up-bars. |
| `flow_reversal` | `flow_imb_first_hour − flow_imb_last_hour` | AM→PM flow sign change. |

### Momentum Decay Family

| Field | Formula | Description |
|:---|:---|:---|
| `open_30m_return` | `(close_30m − open) / open` | Return in first 30 minutes. |
| `open_60m_return` | `(close_60m − open) / open` | Return in first 60 minutes. |
| `decay_ratio` | `open_30m_return / day_return` | How much of day's return is from first 30m. >1 = faded. |
| `reversal_speed` | `bars until 50% retrace of open_30m` | Bars to halve the opening move. Lower = faster reversal. |
| `gap_fill_ratio` | `open_30m_return` (proxy) | Proxy for overnight gap closure. |
| `afternoon_momentum` | `(close_eod − open_13:00) / open_13:00` | Return from 13:00 to close. |
| `close_auction_return` | `(close_last − close_prev) / close_prev` | Return in final bar (closing auction). |

### Volatility Curve Family

| Field | Formula | Description |
|:---|:---|:---|
| `morning_volatility` | `std(bar_returns, 09:30–11:30)` | Std of 5-min returns in morning session. |
| `afternoon_volatility` | `std(bar_returns, 13:00–15:00)` | Std of 5-min returns in afternoon session. |
| `vol_curve_skew` | `morning_vol / afternoon_vol` | >1 = U-shape, <1 = L-shape volatility curve. |
| `jump_count` | `count(|bar_ret| > 3×intraday_std)` | Number of jump bars (>3σ). |
| `vol_clustering` | `corr(|ret[0:−1]|, |ret[1:]|)` | Volatility autocorrelation. >0 = vol clusters. |
| `range_ratio` | `(max_high − min_low) / open` | Full-day range as fraction of open. |

### Liquidity Family

| Field | Formula | Description |
|:---|:---|:---|
| `trade_size_gini` | `Gini(amount_i / num_trades_i)` | Inequality of trade sizes. >0.5 = concentrated. |
| `price_impact_per_trade` | `mean(|Δclose_i| / num_trades_i)` | Avg price move per trade. Higher = less liquid. |
| `price_impact_tail` | `P95(|Δclose_i| / num_trades_i)` | Worst-case price impact (95th pct). |
| `liquidity_gap_count` | `count(vol=0) + count(trades=0)` | Number of bars with no activity. |
| `spread_proxy` | `mean((high_i−low_i) / close_i)` | Bar-level bid-ask spread proxy. |
| `amihud_illiq` | `mean(|ret_i| / amount_i)` | Amihud (2002) illiquidity. Higher = more price impact per CNY. |
| `volume_stability` | `std(vol_i) / mean(vol_i)` | CV of volume. Lower = more stable pattern. |

### Trade Concentration Family

| Field | Formula | Description |
|:---|:---|:---|
| `large_trade_ratio` | `Σvol(amount > P95) / Σvol(day)` | Volume share of largest bars (top 5%). |
| `trade_concentration_hhi` | `Σ (vol_i / Σvol)²` | HHI of volume across bars. >0.1 = concentrated. |
| `block_trade_count` | `count(amount > 10×median)` | Bars with block-trade-level amount. |
| `retail_flow_ratio` | `Σvol(num_trades > median) / Σvol` | Volume share in high-trade-count bars (retail). |
| `institutional_participation` | `1 − retail_flow_ratio` | Inverse: volume in low-trade-count bars (institutional). |

### Lead-Lag Family

| Field | Formula | Description |
|:---|:---|:---|
| `sector_lead_rank` | 0.5 (placeholder) | Sector leadership rank. Needs cross-stock computation. |
| `peer_correlation_lag1` | 0.0 (placeholder) | Peer correlation at lag 1. Placeholder. |
| `information_arrival_speed` | `argmin(cum_abs_ret ≥ 0.5×total) / N` | Normalized time to 50% of total absolute return. |
| `lead_lag_strength` | 0.0 (placeholder) | Max cross-corr with sector ETF. Placeholder. |

### Interaction Family

| Field | Formula | Description |
|:---|:---|:---|
| `flow_vol_interaction` | `flow_imbalance × vol_clustering` | Flow direction × vol persistence. |
| `vwap_momentum_combo` | `vwap_divergence_close × afternoon_momentum` | VWAP position × afternoon trend. |
| `liquidity_volatility_ratio` | `amihud_illiq / morning_volatility` | Illiquidity per unit of volatility. |

## Available Functions

> **Operators are defined in [`operators.json`](operators.json).**
> To add a new operator, append an entry to that file with `name`, `signature`,
> `description`, `category`, and `numpy_impl`. The validator and generator
> auto-load from this file — no code changes needed.

### Cross-Sectional (per date)

| Function | Signature | Description |
|:---|:---|:---|
| `rank(x)` | `rank(x)` | Cross-sectional percentile rank [0,1] |
| `zscore(x)` | `zscore(x)` | Cross-sectional z-score |
| `scale(x, a=1)` | `scale(x, a=1)` | Rescale so |Σx| = a |
| `demean(x)` | `demean(x)` | x − mean(x) per date |

### Time-Series Rolling

| Function | Signature | Description |
|:---|:---|:---|
| `ts_rank(x, n)` | `ts_rank(x, n)` | Time-series percentile rank over n days |
| `ts_zscore(x, n)` | `ts_zscore(x, n)` | Rolling z-score over n days |
| `ts_mean(x, n)` | `ts_mean(x, n)` | Rolling mean over n days |
| `ts_std(x, n)` | `ts_std(x, n)` | Rolling std over n days |
| `ts_max(x, n)` | `ts_max(x, n)` | Rolling max over n days |
| `ts_min(x, n)` | `ts_min(x, n)` | Rolling min over n days |
| `ts_sum(x, n)` | `ts_sum(x, n)` | Rolling sum over n days |
| `ts_argmax(x, n)` | `ts_argmax(x, n)` | Days since rolling max |
| `ts_argmin(x, n)` | `ts_argmin(x, n)` | Days since rolling min |
| `correlation(x, y, n)` | `correlation(x, y, n)` | Rolling Pearson correlation |
| `decay_linear(x, n)` | `decay_linear(x, n)` | Linear-decay weighted moving average |

### Lag / Difference

| Function | Signature | Description |
|:---|:---|:---|
| `delay(x, n)` | `delay(x, n)` | Lag by n days (n ≥ 1) |
| `delta(x, n)` | `delta(x, n)` | x − delay(x, n) (n ≥ 1) |
| `returns(x, n=1)` | `returns(x, n=1)` | pct_change over n days (n ≥ 1) |

### Volume / Amount

| Function | Signature | Description |
|:---|:---|:---|
| *(none — daily volume/amount columns not available in minute feature namespace)* | | |

### Element-Wise Math

| Function | Signature | Description |
|:---|:---|:---|
| `sign(x)` | `sign(x)` | Sign of x |
| `abs(x)` | `abs(x)` | Absolute value |
| `log(x)` | `log(x)` | Natural log (clamped to ≥ 1e-8) |
| `power(x, n)` | `power(x, n)` | x^n |
| `signed_power(x, n)` | `signed_power(x, n)` | sign(x) × |x|^n |
| `min(x, y)` | `min(x, y)` | Element-wise min |
| `max(x, y)` | `max(x, y)` | Element-wise max |
| `clip(x, lower, upper)` | `clip(x, lower, upper)` | Clip to [lower, upper] |

### Arithmetic

Standard `+`, `-`, `*`, `/` work between DataFrames and scalars.

### Extending Operators

To add a new operator, edit [`operators.json`](operators.json):

```json
{
  "name": "my_new_func",
  "category": "elementwise",
  "signature": "my_new_func(x, n)",
  "description": "What it does.",
  "arg_count": 2,
  "has_window": false,
  "lookahead_risk": false,
  "elementwise": true,
  "numpy_impl": "lambda x,n: np.where(x>0, x**n, -((-x)**n))"
}
```

The LLM may also propose new operators in its alpha output via the
`new_operator` field. These should be reviewed and added to the catalog.

## Example Expressions

```python
# VWAP mean-reversion: stocks far above VWAP tend to revert
-1 * rank(vwap_divergence_close)

# Smart money accumulation: persistent buying in last hour
rank(flow_imbalance_last_hour) * rank(flow_persistence)

# Opening gap fade: fast gap closure predicts next-day reversal
-1 * rank(decay_ratio) * rank(reversal_speed)

# Liquidity premium: illiquid stocks with high impact
rank(amihud_illiq) * rank(price_impact_tail)

# Volatility regime reversal: jumpy days mean-revert
-1 * rank(jump_count)

# Information leader: stocks that lead their sector
rank(sector_lead_rank)

# Composite: VWAP + flow interaction
rank(vwap_divergence_close) + rank(flow_imbalance_last_hour)

# Multi-day stability: persistent low trade concentration
-1 * ts_mean(rank(trade_concentration_hhi), 5)
```

## Validation Rules

1. Every field name must match exactly one of the fields defined above.
2. Every function name must match exactly (case-sensitive).
3. Argument counts and types must match the signatures above.
4. Only the fields defined in this contract may appear as leaf variables.
5. `delay(x, n)`, `delta(x, n)`, and `returns(x, n)` MUST use n ≥ 1 (look-ahead prevention).
6. Never divide by something that could be zero — use `max(denom, 1e-8)`.
7. Never take `log(x)` without ensuring `x > 0` — use `log(max(x, 1e-8))`.
8. Prefer `rank()` and `zscore()` based expressions — they are naturally stable.
9. Each alpha must include a `source` field citing the academic paper or
   document passage that inspired it (APA/MLA format).
10. Provide a `source_link` with DOI or arXiv URL where possible, or null.
