# AI use

This file is kept up to date during the work. Each entry is backed by the exported logs in `ai_log/`.

## Tools

- **Claude Code (CLI, Windows), model `claude-opus-5-5`.** Used for: reading the brief, glossary, worked examples and
  the planning documents; revising the project's Claude setup (`CLAUDE.md`, `.claude/` phases, rules, skills, hooks,
  progress tracking); writing the workflow guard and its tests; writing the session-log exporter. Every assistant turn in
  both exported sessions so far used this model.
- **ChatGPT (planning and prompt drafting).** I used it mostly to structure my instructions for Claude Code: the
  planning document `docs/NOVA-SOLUTION-PLAN.md`, the initial Claude setup, and the scaffold-cleanup prompt that removed
  deadline and hour tracking (kept locally as the gitignored `prompt.txt`). Its log is not exported yet; see
  "Prompt log".

## How you worked with them

- **Split of work.** I direct the work and own every API-backed, ML/AI and publishing step. The rules are in
  `.claude/rules/human-execution.md`. Claude Code reads, edits code and docs, installs pinned dependencies into `.venv`
  and runs offline checks. I run API/service setup, the `make grade/sheet/run/eval` runs, real-mailbox ML preprocessing,
  model preparation and any training. A hook (`.claude/hooks/handoff_guard.py`) blocks the known commands for those steps.
- **What I checked.** I reviewed each scaffold change. I applied the guard and settings changes myself from a copy
  Claude Code had tested in a scratch folder, because its auto mode refused to edit its own guardrails. After every
  change, the setup check (`.claude/scripts/check_setup.py`) and the guard tests (`.claude/hooks/test_guard.py`) were
  re-run with the `.venv` interpreter.
- **Where it got things wrong, and how each was caught:**
  - A Python rewrite converted two LF files to CRLF, which made every line show as changed. A diff far larger than
    the edits gave it away; the line endings were restored.
  - In one batch of tool calls, a `sed` on phase files ran alongside a write that the auto-mode classifier had refused.
    It was disclosed rather than repeated.
  - The log redactor first missed API-key values behind JSON-escaped quotes. This was found by listing every match on
    the real transcript; the pattern was fixed and a regression test added.
  - A test file contained a fake key that the submission key scan (`tools/check_submission.py`) would have flagged.
    The fake key is now assembled from pieces.
  - The workflow guard blocked two harmless commands because their text contained gated words (a made-up test
    string; a progress note). The check went into `tests/offline/` and the note was written with the Edit tool.
    Nothing gated was run.
- **No live API use during development.** I chose to stay offline: no personal Anthropic key. The harness calls Claude
  only with the evaluator's key at grading time. Nothing in this repo was produced by a live model call from the
  harness.

## Written without AI

- The short conversational instructions in the Claude Code log are mine. The longer structured ones, such as
  `prompt.txt`, were drafted with ChatGPT.
- So far, nothing in the harness or the eval cases has been written by hand. This section is updated if that changes.

## Prompt log

Real logs, trimmed only for secrets:

- `ai_log/claude-code/<session>.md`: readable version, with prompts and replies verbatim, tool calls on one line each
  and tool output left out.
- `ai_log/claude-code/<session>.jsonl`: the complete Claude Code transcript, with secrets redacted.
- Sessions exported so far:
  - `9c243027…`: first attempt, interrupted.
  - `39a68825…`: reading the brief, reassessing the plan, removing scheduling from the setup, changing the execution
    policy and guard, setting up the log exporter.
- To regenerate after each session: `.venv/Scripts/python.exe ai_log/export_claude_sessions.py`. The exporter's
  redaction is tested in `tests/offline/test_ai_log_export.py`.
- **Deferred:** the ChatGPT conversation (planning document, setup and prompt drafting) will go into
  `ai_log/chatgpt/` when I export it.
