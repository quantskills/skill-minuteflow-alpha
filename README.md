# MinuteFlow Alpha

基于 **分钟级行情数据**（PandaData）生成 Alpha 因子表达式。从分钟K线中提取
44 个日内微观结构特征（8 大信号族），并输出经过验证、可直接用于日频回测的
Alpha 表达式。智能体可通过自定义特征（`new_features`）和自定义算子
（`new_operator`）扩展特征目录。

## 快速开始

```bash
# 1. 在 .env 中配置凭证

# 2. 拉取分钟数据 + 提取特征（使用 config.json 默认参数）
python scripts/fetch_minute_data.py --run-name myrun
python scripts/extract_minute_features.py --run-name myrun

# 3. 生成 Alpha —— 选择输入模式：
python scripts/generate_minute_alphas.py --run-name myrun \
  --doc paper.pdf --n 5          # 文档
python scripts/generate_minute_alphas.py --run-name myrun \
  --query "opening gap reversal" --n 5   # 自然语言

# 4. 在 output/<run>/alphas.json 中填写 Alpha（由 LLM 智能体完成）

# 5. 验证（自动生成 backtest_factors/ + README.md）
python scripts/validate_minute_alphas.py --run-name myrun
```

## 运行输出

每次验证后的运行都会生成：

```
output/<run>/
├── README.md                # 自动生成的文档
├── minute_data.csv          # 原始分钟 OHLCV K线
├── features.csv             # 44 个日聚合特征
├── feature_definitions.json # 特征目录及公式
├── alphas.json              # Alpha 表达式
├── validated_alphas.json    # 已验证 Alpha + 展开公式
└── backtest_factors/        # 日频因子 CSV（可直接回测）
    ├── <alpha1>.csv         # date,ticker,value
    └── <alpha2>.csv
```

## 回测集成

回测因子在验证阶段**自动生成**，可直接回测：

```bash
python ../skill-factor-backtest/scripts/run_factor_backtest.py \
  --input-file output/<run>/backtest_factors/<alpha>.csv \
  --factor-column <alpha_name> \
  --data-root <market_data_dir> --timespan YYYYMMDD YYYYMMDD
```

## 环境要求

- Python 3.10+
- `panda_data==1.0.6`
- 在 `.env` 中配置有效的 PandaData 凭证

## 参数（config.json）

| 参数 | 默认值 | 说明 |
|---|---|---|
| `start_date` | `20250102` | 开始日期（YYYYMMDD） |
| `end_date` | `20250624` | 结束日期（YYYYMMDD） |
| `frequency` | `5m` | K线频率：1m, 5m, 15m, 60m |
| `universe` | `000300` | 沪深300、中证500、中证1000、上证50 |
| `max_alphas` | `5` | 每次运行的默认 Alpha 数量 |

## 许可证

GPL-3.0-only


Pandadata 兼容维护：[abgyjaguo](https://github.com/abgyjaguo)，保留原项目作者署名。
