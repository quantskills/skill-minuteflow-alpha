# MinuteFlow Alpha

Generate alpha factor expressions from **minute-level market data** using
PandaData. Extracts 44 intraday microstructure features across 7 signal
families and produces validated alpha expressions for daily-frequency
backtesting.

## Quick Start

```bash
# 1. Set credentials in .env
#    PANDA_AI_USERNAME=...
#    PANDA_AI_PASSWORD=...
#    PANDA_AI_BASE_URL=http://pandadata.pandaaiquant.com

# 2. Fetch minute data + extract features (uses config.json defaults)
python scripts/fetch_minute_data.py --run-name myrun
python scripts/extract_minute_features.py --run-name myrun

# 3. Generate alphas — pick your input mode:
python scripts/generate_minute_alphas.py --run-name myrun \
  --doc paper.pdf --n 5          # Document
python scripts/generate_minute_alphas.py --run-name myrun \
  --query "opening gap reversal" --n 5   # Natural language

# 4. Validate
python scripts/validate_minute_alphas.py --run-name myrun

# 5. Export for backtest
python scripts/materialize_alphas.py --run-name myrun
```

## Input Modes

| Mode | Flag | Description |
|---|---|---|
| Document | `--doc paper.pdf` | Research paper or text file |
| URL | `--doc https://...` | Any accessible webpage |
| Natural Language | `--query "..."` | Free-text concept description |
| Model Invention | `--query "invent..."` | Model creates alphas from a paradigm |

## Feature Families (44 features from 5-min bars)

| Family | Features |
|---|---|
| VWAP | divergence (close, max, 30m), slope, volume share by hour |
| Order Flow | imbalance (full day, first/last hour), persistence, buy ratio |
| Momentum Decay | open-30m/60m return, decay ratio, reversal speed, afternoon momentum |
| Volatility Curve | morning/afternoon vol, skew, jump count, clustering, range ratio |
| Liquidity | trade size Gini, price impact, spread proxy, Amihud, volume stability |
| Trade Concentration | large trade ratio, HHI, block trades, retail/institutional flow |
| Lead-Lag | information arrival speed, sector lead, peer correlation |
| Interaction | flow × vol, VWAP × momentum, liquidity / volatility |

## Backtest Integration

Export alphas as daily CSVs for `skill-factor-backtest` or `skill-factor-loop-evolve`:

```bash
python scripts/materialize_alphas.py --run-name myrun
# → output/<run>/backtest_factors/<alpha>.csv (date, ticker, value)
```

## Requirements

- Python 3.10+
- `panda_data>=0.1.0`
- Valid PandaData credentials in `.env`

## Parameters (config.json)

| Parameter | Default | Description |
|---|---|---|
| `start_date` | `20250102` | Start date (YYYYMMDD) |
| `end_date` | `20250624` | End date (YYYYMMDD) |
| `frequency` | `5m` | Bar frequency: 1m, 5m, 15m, 60m |
| `universe` | `000300` | CSI 300, CSI 500, CSI 1000, SSE 50 |
| `max_alphas` | `5` | Default number of alphas per run |

## License

GPL-3.0-only
