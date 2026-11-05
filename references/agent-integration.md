# Agent Integration Guide — MinuteFlow Alpha

## Supported Platforms

| Platform | Config | Instructions |
|:---|:---|:---|
| Claude Code | `agents/openai.yaml` | Register as skill, invoke `$minuteflow-alpha` |
| Codex | `agents/openai.yaml` | Register as skill, invoke `$minuteflow-alpha` |
| Cursor | `agents/cursor-rule.mdc` | Copy to `.cursor/skills/minuteflow-alpha/`, enable rule |
| OpenClaw / Hermes | `agents/portable-loader.md` | Paste loader prompt with real `<<SKILL_ROOT>>` |

## Prerequisites

1. **Python 3.10+** with `panda_data==1.0.6`, `pandas`, `numpy`.
2. **PandaData credentials** in `.env` (see `.env.example`).
3. **Network access** to `http://pandadata.pandaaiquant.com`.

## Cross-Agent Smoke Test

After installing the skill:

```bash
# 1. Verify minute data fetch works
python scripts/fetch_minute_data.py \
  --start-date 20250102 \
  --end-date 20250108 \
  --universe 000300 \
  --frequency 5m \
  --output /tmp/test_minute.csv

# 2. Verify feature extraction
python scripts/extract_minute_features.py \
  --input /tmp/test_minute.csv \
  --output /tmp/test_features.csv

# 3. Verify alpha generation (NL query)
python scripts/generate_minute_alphas.py \
  --query "stocks with large opening gaps that close quickly tend to reverse" \
  --features /tmp/test_features.csv \
  --n 2 \
  --output /tmp/test_alphas.json

# 4. Verify validation
python scripts/validate_minute_alphas.py \
  --alphas /tmp/test_alphas.json \
  --features /tmp/test_features.csv \
  --output /tmp/test_validated.json
```

All four commands should exit 0 and produce non-empty output files.
