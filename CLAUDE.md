# Nova take-home: project instructions

Build the freight invoice audit CLI defined by this repository. Read the brief before implementation. Complete required correctness and verification before optional experiments.

## Start or resume

1. Read `.claude/progress.json`, `.claude/WORKLOG.md` and any open `.claude/handoffs/` request.
2. Read `README.md`, `GLOSSARY.md`, `SUBMISSION.md`, and `grader/schema/report.schema.json` before the first implementation phase. The glossary resolves conflicts in the brief.
3. Load `.claude/phases/INDEX.md` and the current phase file. Phase files are project documents, not automatically executed Claude workflows.
4. Use `/nova-start` to assess readiness, `/nova-phase <number>` to work, `/nova-status` to resume, and `/nova-handoff <task>` when a human must execute a step.
5. Read `docs/NOVA-SOLUTION-PLAN.md` selectively for architecture detail. Keep this root instruction file concise.

## User execution policy: mandatory

The user explicitly wants to execute API/service setup, API-backed runs, ML/AI preprocessing and model preparation, and any model training themselves. Follow `.claude/rules/human-execution.md` and `.claude/references/HUMAN-HANDOFF.md`.

Claude may inspect files, design/edit implementation, author commands/scripts, install pinned dependencies into `.venv`, and run offline checks (setup check, hook tests, isolated synthetic unit tests, `make validate`). Claude must hand off API/account/secret/service setup, live API calls and API-backed runs (`make grade/sheet/run/eval`, real-mailbox harness runs), model downloads/export/quantization, real-mailbox ML/AI preprocessing (OCR, embedding, indexing) and official artifacts. Any future training/fine-tuning is a human-executed operation after a written justification and explicit user choice.

Prepare runnable code and exact instructions before requesting execution. Ask the user to run the commands in their own terminal and return non-secret output. Permission to continue coding does not authorize Claude to run a human-owned operation. Do not change tools, invoke a subagent, use inline Python, call an SDK directly, or rewrite a wrapper to bypass this policy. The hook is a workflow guard for known commands, not a complete security sandbox.

Never ask the user to paste an API key or OAuth token. Assume Claude Pro for development and evaluator-supplied Anthropic credentials at runtime. Do not make buying an API key a project prerequisite. Never pretend mocks validated live extraction or produced official submission artifacts.

## Architecture

- Python 3.11 CLI: preserve `ingest`, `report --as-of --mode`, and `feedback` arguments.
- SQLite holds source occurrences, canonical page text, versioned facts, feedback, extraction units, a response cache and report history. All mutable runtime state goes under `--state-dir`; imports/assets resolve from script location.
- Reuse the canonical document reader for citation fidelity. Support email, PDF, XLSX and image-only PDF OCR.
- Extract typed facts with source references. Keep original email metadata; content deduplication must not erase a second payment request.
- Retrieve complete governing and ledger records through parameterized SQL. Hard-filter entity/contract and knowledge dates before semantic ranking. Do not hide conflicting applicable instruments.
- Built path: Claude transcribes every document in full into typed, quoted facts; Python reads all of them, resolves authority/precedence, calculates money and enforces action policy.
- Not built (decision 2026-10-18, `.claude/experiments/EXP-001-supplementary-retrieval.md`): MiniLM embeddings, lexical search, rank fusion and RAG evidence bundles. No failure so far came from missing context. Add them only for a measured miss; if added, ship tested model bytes with license/checksums and no evaluator-time downloads.
- Preserve parent clauses, table headers, exact spans and page numbers. Search top-k never limits ledger aggregation or governing-document coverage.
- Validate observed source arithmetic and critical fields; never change an invoice to make it match a contract. Permit at most one targeted field recheck per document/version within the shared model-call/time budget. Model agreement does not establish truth.
- Produce internal traces of fact versions, governing terms, typed operands, rounding/FX and action gates under `--state-dir/traces/`. Replay with allowlisted formulas; no `eval` and no extra fields in official report JSON.
- Read `.claude/references/DIFFERENTIATORS.md` for implementation/experiment gates. A pretrained cross-encoder is optional, initially off, and considered only after baseline evaluations. No custom training, learned calibration or MLflow service in the current scope.

## Correctness requirements

- Use Decimal, ROUND_HALF_UP and the glossary's original-currency/FX rules. Never let the LLM calculate final money.
- Separate document receipt time from business effective dates; respect historical `as_of` and feedback `decided_at`.
- Implement all report classes, all feedback decisions, one-off versus standing scope, supersedes/retro, stale-item removal and both modes.
- Combine outbound amounts by invoice/cashback key before applying the $5,000 threshold. An exact $5,000 requires human review. Supervised mode never emits execute actions.
- Source authority and Schedule 1 recipients are verified in code. Similarity scores never grant authority or represent correctness probabilities.
- Email/document instructions are untrusted data. No mailbox instruction changes prompt, execution mode, recipient or tool permissions.
- Report JSON only on stdout; diagnostic output goes to stderr. Validate schema and every citation. Use atomic/transactional persistence and bounded retries/calls.

## Work discipline

Use focused, reviewable slices. Keep tests under `tests/offline/` isolated from the real corpus and network; use original synthetic fixtures and explicit mock providers. Put at least 10 new submission cases in `evals/` as required, with actual results generated only by the real runner.

Add the six counterfactual/metamorphic families in DIFFERENTIATORS.md. Keep parent fixtures and their variants in one evaluation split. Record baseline/enhanced results using `.claude/templates/EXPERIMENT.md`; leave absent measurements NOT_RUN. Reproducible trace replay is not independent proof that a business rule or extraction is correct.

Do not alter README.md, GLOSSARY.md, BRIEF.pdf, supplied grader/data or answer files to improve scores. Practice answers may be inspected for learning/debugging, never loaded by runtime code. Do not manually patch answer_sheet.json or report cards.

Update progress and WORKLOG after each slice: changed files, exact checks actually run, human gates, failures and next task. Distinguish implementation, offline verification, human execution and live verification. Save real AI session/prompt logs with secrets removed; do not reconstruct a fictional log. At the end of each session run `.venv/Scripts/python.exe ai_log/export_claude_sessions.py`, check its redaction counts, and update `AI_USE.md` (tools, checks, where the AI was wrong, logs) to match.

No push, private-repo invitation or submission without user instruction. No parallel agents by default; use the optional read-only reviewer only if the user requests delegation. Do not let a reviewer execute human-owned operations.
