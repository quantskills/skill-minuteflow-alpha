# MinuteFlow Alpha

Generate alpha factor expressions from **minute-level market data** using
PandaData. Takes a research document or natural language query as input and
produces validated alpha expressions exploiting intraday microstructure signals.

[中文说明](#chinese) | [English](#english)

---

<a name="english"></a>
## English

### What It Does

Unlike daily-bar factor generation, this skill exploits **intraday
microstructure** signals invisible at daily resolution:

- **VWAP Divergence** — mean-reversion from intraday fair value
- **Order Flow Proxy** — buy/sell pressure from bar-level close position
- **Momentum Decay** — opening gap persistence vs. fade
- **Volatility Curve** — U-shape vs. L-shape intraday vol patterns
- **Liquidity Fingerprint** — trade size Gini, price impact, Amihud
- **Trade Concentration** — institutional vs. retail flow detection
- **Lead-Lag** — sector leadership from minute-level cross-correlation

### Quick Start

```bash
# 1. Set credentials
cp .env.example .env  # edit with your PandaData credentials

# 2. Fetch minute data
python scripts/fetch_minute_data.py \
  --start-date 20250102 --end-date 20250131 \
  --universe 000300 --frequency 5m \
  --output output/run_001/minute_data.csv

# 3. Extract features
python scripts/extract_minute_features.py \
  --input output/run_001/minute_data.csv \
  --output output/run_001/features.csv

# 4. Generate alphas from a query
python scripts/generate_minute_alphas.py \
  --query "stocks where opening gap closes fast tend to reverse next day" \
  --features output/run_001/features.csv --n 5 \
  --output output/run_001/alphas.json

# 5. Validate
python scripts/validate_minute_alphas.py \
  --alphas output/run_001/alphas.json \
  --features output/run_001/features.csv \
  --output output/run_001/validated_alphas.json
```

### Requirements

- Python 3.10+
- `panda_data>=0.1.0`
- Valid PandaData credentials

### License

GPL-3.0-only

---

<a name="chinese"></a>
## 中文

### 功能概述

基于**分钟级行情数据** (PandaData) 生成 Alpha 因子表达式。支持从研报文档或自然语言查询中提取日内微观结构信号。

涵盖 7 大信号家族共 44 个分钟衍生特征：VWAP偏离、订单流代理、日内动量衰减、波动率曲线、流动性指纹、交易集中度、领先滞后。

### 快速开始

```bash
cp .env.example .env  # 填入 PandaData 凭证
python scripts/fetch_minute_data.py --start-date 20250102 --end-date 20250131 --universe 000300 --frequency 5m --output output/run_001/minute_data.csv
python scripts/extract_minute_features.py --input output/run_001/minute_data.csv --output output/run_001/features.csv
python scripts/generate_minute_alphas.py --query "开盘缺口快速回补的股票次日倾向于反转" --features output/run_001/features.csv --n 5 --output output/run_001/alphas.json
python scripts/validate_minute_alphas.py --alphas output/run_001/alphas.json --features output/run_001/features.csv --output output/run_001/validated_alphas.json
```

### 依赖

- Python 3.10+
- `panda_data>=0.1.0`
- 有效的 PandaData 凭证

### 许可证

GPL-3.0-only
