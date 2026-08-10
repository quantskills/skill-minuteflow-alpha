# Portable Loader Prompt — MinuteFlow Alpha

Use this prompt in Claude Code, Hermes, OpenClaw, or any agent runtime that does
not natively discover `SKILL.md` folders.

```text
You have access to a local skill named minuteflow-alpha at:
<<SKILL_ROOT>>

When the user asks to generate alpha factors from minute-level data,
intraday microstructure signals, VWAP-based strategies, order flow
proxies, or any document discussing intraday trading patterns:

1. Read <<SKILL_ROOT>>/SKILL.md.
2. Read <<SKILL_ROOT>>/references/minute_alpha_ops.md for the formula
   contract — all allowed fields and functions.
3. Read <<SKILL_ROOT>>/config.json for current hyperparameters.
4. Ensure PandaData credentials are set in <<SKILL_ROOT>>/.env.
5. Fetch minute data:
   python <<SKILL_ROOT>>/scripts/fetch_minute_data.py \
     --start-date YYYYMMDD --end-date YYYYMMDD \
     --universe 000300 --frequency 5m \
     --output output/run_<ts>/minute_data.csv
6. Extract features:
   python <<SKILL_ROOT>>/scripts/extract_minute_features.py \
     --input output/run_<ts>/minute_data.csv \
     --output output/run_<ts>/features.csv
7. Generate alphas from the user's document or query:
   python <<SKILL_ROOT>>/scripts/generate_minute_alphas.py \
     --query "<user's query or paste doc text>" \
     --features output/run_<ts>/features.csv \
     --n 5 --output output/run_<ts>/alphas.json
   OR for a file:
   python <<SKILL_ROOT>>/scripts/generate_minute_alphas.py \
     --doc "<path/to/document>" \
     --features output/run_<ts>/features.csv \
     --n 5 --output output/run_<ts>/alphas.json
8. Validate:
   python <<SKILL_ROOT>>/scripts/validate_minute_alphas.py \
     --alphas output/run_<ts>/alphas.json \
     --features output/run_<ts>/features.csv \
     --output output/run_<ts>/validated_alphas.json
9. Read validated_alphas.json. Present to the user:
   - Each alpha expression with its name, description, rationale
   - The signal family used (VWAP, order flow, etc.)
   - Validation status (passed / corrected / failed)
   - Academic source attribution
```

Runtime placement notes:
- Codex: keep under a Codex skill path, invoke `$minuteflow-alpha`.
- Claude Code: keep under a Claude skill path, invoke `$minuteflow-alpha`.
- Cursor: copy to `.cursor/skills/minuteflow-alpha`, enable `agents/cursor-rule.mdc`.
- Hermes/OpenClaw: mount as local skill root or paste loader prompt with real path.
