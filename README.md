# MinuteFlow Alpha

Generate alpha factor expressions from **minute-level market data** using
PandaData. Extracts 44 intraday microstructure features across 7 signal
families and produces validated alpha expressions for daily-frequency
backtesting.

## Quick Start

```bash
# 1. Set credentials in .env

# 2. Fetch minute data + extract features (uses config.json defaults)
python scripts/fetch_minute_data.py --run-name myrun
python scripts/extract_minute_features.py --run-name myrun

# 3. Generate alphas — pick your input mode:
python scripts/generate_minute_alphas.py --run-name myrun \
  --doc paper.pdf --n 5          # Document
python scripts/generate_minute_alphas.py --run-name myrun \
  --query "opening gap reversal" --n 5   # Natural language

# 4. Fill in alphas in output/<run>/alphas.json (LLM agent)

# 5. Validate (auto-generates backtest_factors/ + README.md)
python scripts/validate_minute_alphas.py --run-name myrun
```

## Run Output

Each validated run produces:

```
output/<run>/
├── README.md                # Auto-generated documentation
├── minute_data.csv          # Raw minute OHLCV bars
├── features.csv             # 44 daily-aggregated features
├── feature_definitions.json # Feature catalog with formulas
├── alphas.json              # Alpha expressions
├── validated_alphas.json    # Validated with expanded formulas
└── backtest_factors/        # Daily CSVs ready for backtesting
    ├── <alpha1>.csv         # date,ticker,value
    └── <alpha2>.csv
```

## Backtest Integration

Backtest factors are **auto-generated** during validation. Run backtest directly:

```bash
python ../skill-factor-backtest/scripts/run_factor_backtest.py \
  --input-file output/<run>/backtest_factors/<alpha>.csv \
  --factor-column <alpha_name> \
  --data-root <market_data_dir> --timespan YYYYMMDD YYYYMMDD
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
