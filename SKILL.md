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
  summary_en: Generate alpha factor expressions from minute-level market data (PandaData). Input can be a research document (PDF/txt), URL, natural language query, or the model can invent novel trading paradigms from scratch.
---
---

# MinuteFlow Alpha

Use this skill to generate **alpha factor expressions from minute-level data**.
Unlike daily-bar factor generation, this skill exploits intraday microstructure
signals — VWAP divergence, order flow imbalance, volatility curve shape, trade
concentration — that are invisible at daily resolution.

## Input Modes

The skill accepts **four types of input**. You can mix them freely:

| Mode | Example | How it works |
|:---|:---|:---|
| **📄 Document** | `--doc paper.pdf` | Extracts text from a research paper, then maps its concepts (e.g. "VR factor", "smart money Q") to minute-derived features. |
| **🔗 URL / Link** | `--doc https://arxiv.org/...` | Fetches the page content, then generates alphas from the text. Works with any accessible URL containing research text. |
| **💬 Natural Language** | `--query "stocks where opening gap closes fast reverse next day"` | Maps free-text concepts to the feature catalog. Keywords like "reversal", "VWAP", "liquidity", "smart money" are auto-mapped. |
| **💡 Model Invention** | `--query "invent 5 mean-reversion alphas using intraday volatility patterns"` | No external document needed. The model generates novel alphas from a trading paradigm description. Useful for brainstorming or exploring new signal families. |

**All four modes** produce the same output: validated alpha expressions (with expanded formulas), feature-level derivations, and backtest-ready factor CSVs.

This skill requires **PandaData** (`panda_data`) for minute data retrieval. Set credentials in `.env`.

It provides:

- **Minute data fetcher** — pulls 1m/5m/15m bars from PandaData via
  `get_market_min_data`, with automatic date-range estimation and rate limiting.
- **Rich feature extractor** — computes 44 minute-derived daily features
  across 8 families: VWAP, order flow, momentum decay, volatility curve,
  liquidity, trade concentration, lead-lag, interaction. Agents may also
  define **custom features** (`new_features`) as expressions over existing
  features and operators when the document/query demands a new signal.
- **Alpha expression generator** — takes a research document or NL query,
  maps it to the minute-feature catalog, and produces valid alpha expressions
  following the formula contract.
- **Formula contract** — `references/minute_alpha_ops.md` defines all 44
  allowed minute-derived fields and 26 functions for composable expressions.
  Operators are loaded from `references/operators.json` at runtime, and both
  new operators (`new_operator`) and new features (`new_features`) can be
  proposed by the agent.
- **Validator** — evaluates each expression against real minute data to catch
  errors, NaN ratios, and look-ahead violations.
- **Auto-correction loop** — failed alphas get categorized diagnostics and
  correction hints; the agent retries up to 5 times.
- **Backtest export** — `scripts/materialize_alphas.py` evaluates every alpha
  expression against the feature data and writes `date,ticker,factor_value` CSVs
  compatible with `skill-factor-backtest`. Works on any run regardless of what
  timeframe the minute data was fetched at — output is always daily-frequency.
  **The validate step now runs materialize automatically** — every validated run
  gets a `backtest_factors/` directory with ready-to-use daily factor CSVs.
- **Run README** — each run directory gets a `README.md` auto-generated after
  validation, documenting all alphas, features used, expanded formulas, and
  backtest integration instructions.
- **Formula expansion** — every validated alpha includes `expanded_formula`
  showing the full derivation from raw minute data to final expression.

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
│  44 features across 8 families   │
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

Create a `.env` file with your PandaData credentials:

```bash
# .env
```

```
PANDA_AI_USERNAME="super_data_user"
PANDA_AI_PASSWORD="panda@2026^_^"
PANDA_AI_BASE_URL="http://pandadata.pandaaiquant.com"
```

### 2. Run the pipeline (pick your input mode)

```bash
# Shared: fetch data + extract features (uses config.json defaults)
python scripts/fetch_minute_data.py --run-name myrun
python scripts/extract_minute_features.py --run-name myrun

# 📄 Mode A: From a research document (PDF, txt)
python scripts/generate_minute_alphas.py --run-name myrun \
  --doc path/to/paper.pdf --n 5

# 🔗 Mode B: From a URL
python scripts/generate_minute_alphas.py --run-name myrun \
  --doc "https://arxiv.org/abs/..." --n 5

# 💬 Mode C: From a natural language query
python scripts/generate_minute_alphas.py --run-name myrun \
  --query "stocks where opening gap closes fast reverse next day" --n 5

# 💡 Mode D: Let the model invent from a paradigm
python scripts/generate_minute_alphas.py --run-name myrun \
  --query "invent 5 momentum alphas using intraday trend persistence" --n 5

# Fill in the alphas in output/<run>/alphas.json (LLM agent step)

# Validate (auto-generates backtest_factors/ + README.md)
python scripts/validate_minute_alphas.py --run-name myrun
```

### 3. Run output structure

After successful validation, each run directory contains:

```
output/<run>/
├── README.md                # Auto-generated run documentation
├── minute_data.csv          # Raw minute bars
├── features.csv             # Daily-aggregated features
├── feature_definitions.json # Feature catalog
├── alphas.json              # Alpha expressions (prompt + filled)
├── validated_alphas.json    # Validated alphas with expanded formulas
└── backtest_factors/        # Daily factor CSVs for backtesting
    ├── <alpha1>.csv         # date,ticker,value
    ├── <alpha2>.csv
    └── ...

# Backtest any factor:
python ../skill-factor-backtest/scripts/run_factor_backtest.py \
  --input-file output/<run>/backtest_factors/<alpha>.csv \
  --factor-column <alpha_name> \
  --data-root <market_data_dir> --timespan YYYYMMDD YYYYMMDD
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
| **Lead-Lag** | 4 | `sector_lead_rank`, `peer_correlation_lag1`, `information_arrival_speed`, `lead_lag_strength` |
| **Interaction** | 3 | `flow_vol_interaction`, `vwap_momentum_combo`, `liquidity_volatility_ratio` |

## Backtest Export

Use `scripts/materialize_alphas.py` to convert any run's validated alphas
into daily-frequency factor CSVs for `skill-factor-backtest`.

```bash
# Export all alphas from a run
python scripts/materialize_alphas.py --run-name smartmoney
# → output/<run>/backtest_factors/<alpha>.csv (date,ticker,value)

# Then backtest:
python ../skill-factor-backtest/scripts/run_factor_backtest.py \
  --input-file output/<run>/backtest_factors/<alpha>.csv \
  --factor-column <alpha_name> \
  --data-root <market_data_dir> --timespan YYYYMMDD YYYYMMDD
```

Alphas are computed from minute-level features but output is daily-frequency
(one row per stock per day) — fully compatible with daily backtesting.

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

Scripts read `config.json` for defaults; CLI arguments override. Change values
in config.json to set your preferred defaults.

| Parameter | Default | CLI Flag | Description |
|:---|:---|:---|:---|
| `start_date` | `"20250102"` | `--start-date` | Start date (YYYYMMDD). |
| `end_date` | `"20250624"` | `--end-date` | End date (YYYYMMDD). 5m allows ~6 months. |
| `frequency` | `"5m"` | `--frequency` | Bar frequency: `1m`, `5m`, `15m`, `60m`. |
| `time_zone` | `["09:30","15:00"]` | `--time-zone` | Trading hours filter. |
| `universe` | `"000300"` | `--universe` | CSI 300, CSI 500, CSI 1000, SSE 50. |
| `max_alphas` | `5` | `--n` | Default number of alphas per run. |
| `nan_threshold` | `0.1` | `--nan-threshold` | Max NaN ratio before flagging. |
| `extreme_threshold` | `5.0` | `--extreme-threshold` | Max z-score before flagging instability. |

## Agent Platform Instructions

When an agent uses this skill, follow the workflow in `agents/portable-loader.md`
or the per-platform configs in `agents/`.

General pattern:
```
Read SKILL.md → Read references/minute_alpha_ops.md → Fetch minute data →
Extract features → Read input document → Generate alpha JSON →
Validate → (correct) → Output
```
