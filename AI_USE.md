# AI use

This file is kept up to date during the work. Each entry is backed by the exported logs in `ai_log/`.

## Tools

- **Claude Code (CLI, Windows), model `claude-opus-5-5`.** Used for: reading the brief, glossary, worked examples and
  the planning documents; revising the project's Claude setup (`CLAUDE.md`, `.claude/` phases, rules, skills, hooks,
  progress tracking); writing the workflow guard and its tests; writing the session-log exporter; writing the
  requirements checklist (`docs/REQUIREMENTS.md`) and the harness code from phase 01 on, with its offline tests. Every
  assistant turn in the exported sessions so far used this model.
- **ChatGPT (planning and prompt drafting).** I used it mostly to structure my instructions for Claude Code: the
  planning document `docs/NOVA-SOLUTION-PLAN.md`, the initial Claude setup, and the scaffold-cleanup prompt that removed
  deadline and hour tracking (kept locally as the gitignored `prompt.txt`). Its log is not exported yet; see
  "Prompt log".

## How you worked with them

- **Split of work.** I direct the work and own every API-backed, ML/AI and publishing step. The rules are in
  `.claude/rules/human-execution.md`. Claude Code reads, edits code and docs, installs pinned dependencies into `.venv`
  and runs offline checks. I run API/service setup, the `make grade/sheet/run/eval` runs, real-mailbox ML preprocessing,
  model preparation and any training. A hook (`.claude/hooks/handoff_guard.py`) blocks the known commands for those steps.
  Near the end I changed this on purpose: to save my time and usage, I let Claude Code run the eval runs, the practice
  grade and the exam answer sheet itself. The exception and its exact scope are written in the rules file, and I
  applied the matching guard change myself. Secrets, model downloads, training and publishing stayed with me.
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
  - The planning document proposed forced `tool_choice` for structured extraction and a Sonnet model. Claude Code's
    API reference skill showed forced tool choice now returns a 400 on current models. The harness uses
    `output_config` structured output instead, with `claude-opus-5-5` as the default model (configurable).
  - My live check (H-002) showed that its CLI back end had not accounted for the grader stripping `SystemRoot`, which
    the Bun-based CLI needs on Windows. The code now restores it from the Windows API, with a regression test. The
    handoff's step 3 chained `notepad` with the check, and `notepad` returns immediately in PowerShell, so the check ran
    on an unedited file. That step is now a single command.
  - Its first validator accepted a wrong date when the other day/month order happened to appear on the page, and did
    not check a contract's late-fee percentage. Its own new tests caught both before any real use. Two expectations in
    its extraction-run tests were themselves wrong (a document count and when a failed unit is retried) and were
    corrected after checking the code's intended behaviour.
  - My first live extraction (H-003) produced 6 "unverified" facts. Checking them against the pages showed all 6 were
    bugs in its validator (a date ending a sentence; a total on page 2), not model errors. It fixed the validator,
    re-checked the cached answers (640/640 ok) and added regression tests. It had also written results only at the end
    of a step; at my request each answer is now saved as it arrives, with progress lines.
  - Its first invoice arithmetic check reused the grader's 0.01 tolerance, which let a one-cent printed difference pass;
    its tests caught it and the document check is now exact. Before wiring the check in, it ran it on the live facts
    and found an INR invoice whose lines included the GST line. That was a correct extraction, so the check was
    adjusted rather than the facts.
  - Its first contract view lost every rate band of the agreement: the cover email also produced a contract fact,
    which shadowed the agreement's own. It caught this by inspecting the live facts before writing any rule, and the
    canonical fact now comes from the agreement document. In one test it got a hand calculation wrong
    (0.40 x 118 = 47.20, not 46.20); the rule's answer was right and the test was corrected.
  - It first planned to map spreadsheet columns by cell index. It switched to header labels read from the real
    workbook after noticing that the grader's text layer drops empty cells, which would shift columns.
  - Its first CLI tests left SQLite connections open (`with sqlite3.connect()` commits but does not close), so the
    Windows test teardown failed. The test run showed it; the tests now close connections explicitly.
  - Its detector tests found three report bugs before any live use: a late-fee line was skipped when the model left
    `refers_to_invoice` empty, an item without evidence failed schema validation and took the whole report down, and
    a resent invoice produced two items for one key. Each is fixed; one bad item is now dropped and logged instead.
  - While writing the margin step-down rule it noticed that qualifying spend counted a resent copy of the same
    invoice twice. The fix has a test, and the batch_01 practice comparison was re-run afterwards (unchanged).
  - Building my eval mailboxes, it read every generated document back through the grader's text layer and found
    three generator bugs: indented email bodies, a ledger amount shown as `1991` instead of `1990.80` (float cell
    format), and a waybill printed as `None`. A rebuild-and-hash check then showed the generator was not
    deterministic (random MIME boundaries, PDF ids, spreadsheet timestamps, and a test using Python's randomised
    `hash()`); all are pinned and a test now requires a byte-identical rebuild.
  - Designing those cases showed its date validator did not accept forms such as `09-Mar-2041` or `Mar 04, 2041`,
    which hidden layouts could use. Added, with a test.
  - Its handoff for my first eval run passed `--harness harness\harness.py`; the runner splits that the POSIX way
    and dropped the backslash, so all 20 cases failed in 4 seconds before any model call. It found the cause from my
    output, confirmed it offline and corrected the handoff.
  - After my batch_02 run, its recomputed reports missed one practice waiver. It traced this to its own rule: the
    model had put a billing note ("you can short-pay that line") in the waiver's `condition` field, and the rule
    treated any condition text as unmet. It fixed the rule and the schema description in general terms, with tests.
    The practice answers showed the miss; no practice id or wording is in the code.
  - My first full eval run passed 9 of 20. The cases it had built caught its own over-fitting to the practice
    contract: the rules only knew that contract's charge-code letters (FUEL, SEC) and Schedule 1 spellings
    (billing_disputes), so an agreement coding fuel as FSC lost every fuel line, and "billing disputes" written with
    a space left autonomous actions without a recipient. It classified each failure by layer and fixed the general
    cause (codes mapped to roles by name, categories normalised), with tests that fail without the fix.
  - The grader crashed while printing its card on my Windows console (a ✓ in cp1252) after a 20-minute run, before
    writing the card file. The fix is an environment setting for the next run, not a change to the grader.
  - Its tool calls are checked by the project guard, which matches command text: it blocked an edit to a JSON
    progress file and a test snippet because they mentioned gated commands. It switched to the Edit tool and test
    files, and did not try to get around the guard. When I authorised it to run the evals and grading itself, auto
    mode refused to let it edit the guard; it staged a patched, tested copy for me to apply.
  - When I let it run the evals and grading itself, it did not account for the harness's model calls sharing my
    Claude Pro allowance with its own session. A practice grade costs about 80 Opus calls; together with the day's
    other runs this used up my usage limit mid-run. It then measured the token use per call, found that two
    limit replies would have marked units permanently failed (silently dropping facts), and changed the harness to
    stop calling and leave work pending on a limit reply.
  - Its own earlier change (reading long agreements in 4-page chunks, to fit the step time) introduced a bug its
    offline checks could not see, because they reused my older single-call extraction. The official practice grade
    caught it (86.0): the rate periods came from a different chunk than the one the code kept. It rebuilt the
    grader's state from cached answers at no model cost, found the cause and merged the chunks; the card is now 99.8.
  - Its new tests passed on the first run, so it broke the rule on purpose (window reset, strict threshold, sender
    authority) to confirm the tests fail when the logic is wrong. They did.
- **Model calls from the harness.** I have no personal Anthropic API key. With the grader's key the harness uses the
  Anthropic SDK. On my machine it uses my Claude Code login through headless `claude -p` (decision D-002 in
  `.claude/decisions/`). Outputs from the local CLI path are labelled as such and are not presented as the grader's
  SDK results. I ran the first live runs: the CLI check (H-002), the practice extraction (H-003, H-004), the first
  eval run (9/20) and the first practice grade. Under the exception above, Claude Code ran the final eval run
  (20/20), the final practice grade (99.8) and the exam answer sheet. These reused answers from a local response
  cache, which never exists on the grader's machine.

## Written without AI

- The short conversational instructions in the Claude Code log are mine. The longer structured ones, such as
  `prompt.txt`, were drafted with ChatGPT.
- No harness code, test or eval case was written by hand. By hand I made the setup-level changes: installing the
  guard and settings changes Claude Code had prepared and tested, editing my local `.env`, and choosing what to
  run and when.

## Prompt log

Real logs, trimmed only for secrets:

- `ai_log/claude-code/<session>.md`: readable version, with prompts and replies verbatim, tool calls on one line each
  and tool output left out.
- `ai_log/claude-code/<session>.jsonl`: the complete Claude Code transcript, with secrets redacted.
- Sessions exported so far:
  - `9c243027…`: first attempt, interrupted.
  - `39a68825…`: reading the brief, reassessing the plan, removing scheduling from the setup, changing the execution
    policy and guard, setting up the log exporter, phase 00 requirements, phase 01 reader/store, phase 02 LLM back end
    and extraction, phase 05 rules and report, phase 06 feedback and trace replay, the margin step-down, and the
    phase 07 eval mailboxes, cases and counterfactual tests, the eval and grading runs, the usage-limit investigation,
    the exam answer sheet and the final documents.
  - `1c7d5468…`: a separate short session I ran to check which tool calls the project guard blocks.
  - `4f8a7a0b…`: a separate session I ran while the first live ingest (H-003) seemed stuck (no progress output then),
    and to ask for a progress percentage against the README's requirements.
- To regenerate after each session: `.venv/Scripts/python.exe ai_log/export_claude_sessions.py`. The exporter's
  redaction is tested in `tests/offline/test_ai_log_export.py`.
- **Deferred:** the ChatGPT conversation (planning document, setup and prompt drafting) will go into
  `ai_log/chatgpt/` when I export it.
