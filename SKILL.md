---
name: minuteflow-alpha
description: >-
  Generate alpha factor expressions from minute-level market data using PandaData
  (panda_data). Takes a research document or natural language query as input,
  fetches intraday OHLCV bars via get_market_min_data, extracts rich minute-level
  features (VWAP divergence, intraday momentum decay, order flow proxy, volatility
  curve shape, trade concentration, lead-lag signatures), and produces validated
  alpha expressions backed by a formula contract. Use when an agent needs to
  generate alpha ideas from academic papers, market commentary, or research notes
  that leverage intraday microstructure signals invisible in daily data.
license: GPL-3.0-only
metadata:
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: skill-minuteflow-alpha
  repository_url: https://github.com/quantskills/skill-minuteflow-alpha
  project_type: skill
  collection: factor-generation
  creator: davideliu
  creator_url: https://github.com/davideliu
  maintainer: davideliu
  maintainer_url: https://github.com/davideliu
quantSkills:
  organization: QuantSkills
  organization_url: https://github.com/quantskills
  repository: skill-minuteflow-alpha
  repository_url: https://github.com/quantskills/skill-minuteflow-alpha
  project_type: skill
  collection: factor-generation
  category: factor
  tags:
    - minute-data
    - intraday
    - alpha-generation
    - factor-discovery
    - microstructure
    - vwap
    - order-flow
    - liquidity
    - causal-discovery
    - ohlcv
    - stock-selection
  platforms:
    - claude-code
    - codex
    - cursor
    - openclaw
  language: zh-en
  status: draft
  validation_level: listed
  maintainer_type: community
  requires:
    - panda_data>=0.1.0
  summary_zh: 基于分钟级行情数据（PandaData）生成Alpha因子表达式，支持从研报/自然语言输入中提取日内微观结构信号（VWAP偏离、订单流代理、日内动量衰减、波动率曲线等），并通过公式合约验证。
  summary_en: Generate alpha factor expressions from minute-level market data (PandaData). Takes research docs or natural language queries as input, extracts intraday microstructure signals (VWAP divergence, order flow proxy, momentum decay, volatility curve, trade concentration, lead-lag), and validates against a formula contract.
---
---

# MinuteFlow Alpha

Use this skill to generate **alpha factor expressions from minute-level data**.
Unlike daily-bar factor generation, this skill exploits intraday microstructure
signals — VWAP divergence, order flow imbalance, volatility curve shape, trade
concentration — that are invisible at daily resolution.

This skill requires **PandaData** (`panda_data`) for minute data retrieval.
Set credentials in `.env` and you're ready to go.

It provides:

- **Minute data fetcher** — pulls 1m/5m/15m bars from PandaData via
  `get_market_min_data`, with automatic date-range estimation and rate limiting.
- **Rich feature extractor** — computes 40+ minute-derived daily features
  across 7 families: VWAP, order flow, momentum decay, volatility curve,
  liquidity, trade concentration, lead-lag.
- **Alpha expression generator** — takes a research document or NL query,
  maps it to the minute-feature catalog, and produces valid alpha expressions
  following the formula contract.
- **Formula contract** — `references/minute_alpha_ops.md` defines all 44
  allowed minute-derived fields and 26 functions for composable expressions.
  Operators are loaded from `references/operators.json` at runtime.
- **Validator** — evaluates each expression against real minute data to catch
  errors, NaN ratios, and look-ahead violations.
- **Auto-correction loop** — failed alphas get categorized diagnostics and
  correction hints; the agent retries up to 5 times.

## Creator, Maintainer, And Scope

- Creator: `davideliu` (`https://github.com/davideliu`).
- Maintainer: `davideliu` for the QuantSkills community.
- Repository: `https://github.com/quantskills/skill-minuteflow-alpha`.
- License: GNU General Public License v3.0 only (`GPL-3.0-only`).
- Scope: alpha factor ideation from minute-level market microstructure data.
  The skill is not official investment advice, a certified data product, or
  a guarantee of trading performance.

## Core Workflow

```
┌─────────────────────────────────┐
│  Input: Document or NL query     │
│  e.g. "Intraday momentum decay   │
│        predicts next-day reversal"│
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Step 1: Fetch minute data       │
│  get_market_min_data() for the   │
│  target universe over N days     │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Step 2: Extract minute features │
│  40+ features across 7 families  │
│  → per-day per-stock flat table  │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Step 3: Generate alpha from     │
│  document/query using LLM        │
│  following minute_alpha_ops.md   │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Step 4: Validate expression     │
│  against real minute data        │
│  → NaN, look-ahead, stability    │
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Step 5: Auto-correct failures   │
│  Up to 5 retries with diagnostics│
└──────────────┬──────────────────┘
               ▼
┌─────────────────────────────────┐
│  Output: validated alpha JSON    │
│  + factor CSV for backtesting    │
└─────────────────────────────────┘
```

## Quick Start

### 1. Set up credentials

Copy `.env.example` to `.env` and fill in your PandaData credentials:

```bash
cp .env.example .env
```

```
PANDA_AI_USERNAME="super_data_user"
PANDA_AI_PASSWORD="panda@2026^_^"
PANDA_AI_BASE_URL="http://pandadata.pandaaiquant.com"
```

### 2. Run the pipeline

```bash
# Fetch minute data + extract features
python scripts/fetch_minute_data.py \
  --start-date 20250102 \
  --end-date 20250131 \
  --universe 000300 \
  --frequency 5m \
  --output output/run_001/minute_data.csv

python scripts/extract_minute_features.py \
  --input output/run_001/minute_data.csv \
  --output output/run_001/features.csv

# Generate alphas from a document
python scripts/generate_minute_alphas.py \
  --doc "path/to/research_paper.txt" \
  --features output/run_001/features.csv \
  --n 5 \
  --output output/run_001/alphas.json

# Or from a natural language query
python scripts/generate_minute_alphas.py \
  --query "stocks where opening gap closes fast tend to reverse next day" \
  --features output/run_001/features.csv \
  --n 3 \
  --output output/run_001/alphas.json

# Validate
python scripts/validate_minute_alphas.py \
  --alphas output/run_001/alphas.json \
  --features output/run_001/features.csv \
  --output output/run_001/validated_alphas.json
```

## Minute Feature Families

The feature extractor produces daily-aggregated features from minute bars:

| Family | # Feats | Examples |
|:---|:---:|:---|
| **VWAP** | 6 | `vwap_divergence_close`, `vwap_divergence_max`, `vwap_slope`, `vwap_volume_share_last_hour` |
| **Order Flow** | 6 | `flow_imbalance`, `flow_imbalance_last_hour`, `flow_persistence`, `buy_volume_ratio` |
| **Momentum Decay** | 7 | `open_30m_return`, `decay_ratio`, `reversal_speed`, `gap_fill_ratio`, `afternoon_momentum` |
| **Volatility Curve** | 6 | `morning_volatility`, `afternoon_volatility`, `vol_curve_skew`, `jump_count`, `vol_clustering` |
| **Liquidity** | 7 | `trade_size_gini`, `price_impact_per_trade`, `liquidity_gap_count`, `spread_proxy`, `amihud_illiq` |
| **Trade Concentration** | 5 | `large_trade_ratio`, `trade_concentration_hhi`, `block_trade_count`, `retail_flow_ratio` |
| **Lead-Lag** | 4 | `sector_lead_rank`, `peer_correlation_lag1`, `lead_lag_strength`, `information_arrival_speed` |
| **Lead-Lag** | 4 | `sector_lead_rank`, `peer_correlation_lag1`, `information_arrival_speed`, `lead_lag_strength` |
| **Interaction** | 3 | `flow_vol_interaction`, `vwap_momentum_combo`, `liquidity_volatility_ratio` |

## Document → Alpha Mapping

When processing a document or NL query, the LLM:

1. **Reads the contract** in `references/minute_alpha_ops.md` — all allowed fields and functions.
2. **Maps document concepts** to the minute feature catalog:
   - "intraday reversal" → `decay_ratio`, `reversal_speed`, `gap_fill_ratio`
   - "smart money positioning" → `flow_imbalance_last_hour`, `large_trade_ratio`
   - "liquidity shock" → `liquidity_gap_count`, `price_impact_per_trade`, `amihud_illiq`
   - "institutional execution" → `vwap_divergence_close`, `trade_concentration_hhi`
   - "information diffusion" → `sector_lead_rank`, `information_arrival_speed`
3. **Generates expressions** using only the allowed fields/functions.
4. **Attributes sources** — each alpha cites the academic paper or document passage that inspired it.

## Parameters (config.json)

| Parameter | Default | Description |
|:---|:---|:---|
| `frequency` | `"5m"` | Minute bar frequency (`1m`, `5m`, `15m`, `60m`). CLI: `--frequency`. |
| `time_zone` | `["09:30", "15:00"]` | Trading hours filter. CLI: `--time-zone`. |
| `universe` | `"000300"` | Stock universe code. Approximated as top 300 by market cap. |
| `lookback_days` | `20` | Trading days of minute data to fetch. CLI: `--start-date`/`--end-date`. |
| `max_alphas` | `5` | Default number of alphas to generate. CLI: `--n`. |
| `nan_threshold` | `0.1` | Max allowed NaN ratio. CLI: `--nan-threshold`. |
| `extreme_threshold` | `5.0` | Max allowed z-score. CLI: `--extreme-threshold`. |

## Agent Platform Instructions

When an agent uses this skill, follow the workflow in `agents/portable-loader.md`
or the per-platform configs in `agents/`.

General pattern:
```
Read SKILL.md → Read references/minute_alpha_ops.md → Fetch minute data →
Extract features → Read input document → Generate alpha JSON →
Validate → (correct) → Output
```
