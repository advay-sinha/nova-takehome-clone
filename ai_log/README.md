# Real AI usage logs

Actual Claude Code and ChatGPT prompt/session exports, trimmed only for secrets. Linked from `AI_USE.md`. Do not
fabricate a clean log after implementation. Include planning/setup assistance and say which checks were done by hand.

Do not store API keys, OAuth tokens or .env dumps.

## Layout

- `claude-code/<session>.jsonl`: the complete Claude Code transcript for this project, secrets redacted.
- `claude-code/<session>.md`: readable version of the same session.
- `chatgpt/`: exported ChatGPT planning conversation (to be added by the user).
- `export_claude_sessions.py`: regenerates `claude-code/` from `~/.claude/projects/<this repo>/*.jsonl`.

## Upkeep

After each working session run `.venv/Scripts/python.exe ai_log/export_claude_sessions.py`. Check the printed
redaction counts, then update `AI_USE.md` with what changed. Redaction patterns are tested in
`tests/offline/test_ai_log_export.py`. The submission check (`tools/check_submission.py`) separately scans the repo for
anything key-shaped.
