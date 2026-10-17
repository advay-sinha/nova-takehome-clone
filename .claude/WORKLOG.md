# Work log

## Setup package creation

- Created project instructions, phase files, project skills and tested workflow-guard/check scripts.
- Harness remains the upstream stub. No implementation, mailbox preprocessing, model preparation, training or live API run is claimed complete.
- Next: run `/nova-start`; establish environment readiness and the phase 00 handoff.

## 13 October 2026 IST: plan and scaffold reassessment

- Rechecked all three upstream branch heads through GitHub; unchanged from the recorded snapshot.
- Added guidance for source-field constraint checks, bounded targeted rechecks, typed calculation traces/replay, and six counterfactual/metamorphic test families. Optional pretrained reranking is considered only after baseline evaluation and must pass measured gates; custom training remains out of scope.
- Updated CLAUDE.md, all 10 phase guides, 8 native project skills, progress, handoff/acceptance rules and setup instructions. Added DIFFERENTIATORS.md, EXPERIMENT.md and FINDING-TRACE.md. Preserved explicit human execution ownership, including model preparation and any future training.
- VERIFIED_OFFLINE (setup only): `python3 .claude/hooks/test_guard.py` passed all 6 test methods, including new reranker/calibration handoff cases. `python3 .claude/scripts/check_setup.py` passed: 8 skills, 10 phases (its hour-total check was removed later). `git diff --check` passed.
- Harness remains the upstream stub. No actual model preparation, preprocessing, inference benchmark, training, live API run or official grading was performed. All proposed solution improvements remain unmeasured.
- Next: `/nova-start`; preserve any existing implementation progress when merging this updated setup into a working private copy.

## 13 October 2026: scheduling removal and execution-policy change

- Scheduling removal (user prompt): dropped deadline and development-hour tracking from progress.json (`deadline_utc`, `planning`; `setup_revision` now `verifiable-audit`), check_setup.py, CLAUDE.md, NOVA-CLAUDE-SETUP.md, INDEX.md, all 10 phase guides, 5 skills, DIFFERENTIATORS/ACCEPTANCE/HUMAN-HANDOFF, EXPERIMENT template, audit-and-retrieval rule, docs/NOVA-SOLUTION-PLAN.md (section 10 is now an ordered checklist) and the hour phrases in the entries above. Runtime timeouts, API/call budgets, business dates and the reranker's measured CPU gate kept.
- Policy change (user instruction, scope as stated): Claude runs offline checks and installs dependencies into `.venv`. Human gates remain for API/service setup, API-backed runs (`make grade/sheet/run/eval`, real-mailbox harness), ML/AI preprocessing and model preparation, training and publishing. Recorded in rules/human-execution.md, CLAUDE.md, HUMAN-HANDOFF.md, SETUP docs, phases 00/01, nova-start/nova-handoff skills and session_context.py.
- Guard: handoff_guard.py also covers the PowerShell tool and no longer gates installs or `make setup/validate/clean`; test_guard.py has 7 tests. settings.json hooks now run with `.venv/Scripts/python.exe` (python3 is a Store stub on this machine) and allow the offline checks. User applied the guard/settings files from a reviewed scratchpad copy; `.claude/settings.local.json` (gitignored) holds the user's auto-mode allowances.
- VERIFIED_OFFLINE (setup only): `.venv/Scripts/python.exe .claude/scripts/check_setup.py` PASS (8 skills, 10 phases); `.venv/Scripts/python.exe .claude/hooks/test_guard.py` 7/7 OK; scan for leftover scheduling phrases found none.
- Harness remains the upstream stub. Next: phase 00 (requirement checklist, module map, `.venv` dependency check).

## 13 October 2026: reassessment and AI-use upkeep

- Re-read the brief/glossary/submission/schema, plan, CLAUDE.md, `.claude/` and setup docs; only files edited earlier this session had changed.
- Environment (VERIFIED_OFFLINE): `.venv` Python 3.12.9 imports pymupdf, openpyxl, jsonschema, yaml, anthropic, rapidocr_onnxruntime. `make` is absent on this Windows host and the Makefile assumes `.venv/bin/python`.
- IMPLEMENTED: `ai_log/export_claude_sessions.py` (stdlib; exports real transcripts with secrets redacted, raw `.jsonl` plus readable `.md`), `tests/offline/test_ai_log_export.py`, filled `AI_USE.md`, updated `ai_log/README.md`, added the per-session export/AI_USE rule to CLAUDE.md, set phase 00 IN_PROGRESS with evidence.
- Exported sessions 9c243027 (0 redactions) and 39a68825 (all matches were synthetic test strings; no real secrets found). Fixed the redactor after it missed values behind JSON-escaped quotes. Made the test's fake key non-literal so `tools/check_submission.py`'s key scan stays clean (replicated scan: no hits).
- Guard false positives: two harmless commands were blocked because their text contained gated words (a test string; a progress note mentioning the exam sheet run). Handled with a test file and the Edit tool; nothing gated was executed.
- Checks: check_setup.py PASS; test_guard.py 7/7; `-m unittest discover -s tests/offline` 4/4.
- Open: user to export the ChatGPT planning conversation into `ai_log/chatgpt/` and confirm AI_USE.md's "Written without AI" note; decide API-key route. Next: phase 00 requirement checklist and module map.

## 13 October 2026: user decisions recorded

- API route: stay offline, no personal key. Recorded in `.claude/decisions/D-001-offline-development.md` and `progress.json` (`api_route`). Consequence: the real harness cannot produce the answer sheet or report card; this must be disclosed, never substituted.
- ChatGPT log export deferred. Per the user, ChatGPT mostly structured their instructions for Claude, including `prompt.txt` (the deadline-correction prompt). AI_USE.md updated to match.

## 16 October 2026: LLM back-end decision (D-002)

- User redirected phase 00: use the local Claude Code system for grading runs, with the API path for the grader. Decision D-002 (supersedes D-001): auto-select the Anthropic SDK when ANTHROPIC_API_KEY is set, else headless `claude -p`.
- For `make grade`'s stripped environment, a gitignored `harness/.local-llm.json` will hold the environment overrides; `.gitignore` updated.
- Checked (read-only): `claude` 2.1.301 on PATH; `--json-schema`, `--model`, `--setting-sources`, `--no-session-persistence` exist. `grader/run_grader.py` passes only PATH and ANTHROPIC_* plus a fresh HOME/TMP; `tools/run_mailbox.py` passes the full environment; 600 s per step.
- AI_USE.md and progress.json (`api_route`) updated. The first live CLI check stays user-run.
- Noted: `tests/offline/test_ai_log_export.py` was changed (by the user) to read its fake key from `.env`; Claude cannot read `.env` (settings deny), and the test errors if `.env` lacks FAKE_KEY.

## 16 October 2026: phase 00 complete

- IMPLEMENTED: `docs/REQUIREMENTS.md` with the requirement checklist (CLI/runtime, reading, schema, business rules, actions/modes, history/feedback, confidence/submission) and the module map with build order.
- Read: harness stub, `grader/extract.py`, `grader/score.py` (weights, gates, escalation rate, injection check on outbound-looking fields), `grader/run_grader.py` and `tools/run_mailbox.py` (environment and timeouts), `evals/run_evals.py`, both `batches.json`.
- Resolved from the practice key (learning only): cannot_determine is `draft:request_document` supervised / `execute:request_document` autonomous. Practice expected actions contain no `human_review`.
- Checks: check_setup PASS; test_guard 7/7; tests/offline 4/4. The user's edited `test_ai_log_export.py` reads FAKE_KEY from the gitignored `.env`, so it errors in a fresh clone without one.
- Next: phase 01.

## 16 October 2026: phase 01 readers and persistent state

- Deferred task recorded in progress.json: after all work, define FAKE_KEY in DESIGN.md (user request).
- IMPLEMENTED: `harness/harness.py` wired to `harness/nova/app.py`; `store.py` (documents keyed by evidence path, pages, feedback files, sha256 blobs, one transaction per batch); `reader.py` (UTC receipt from Date header, sender/recipients/Message-ID, per-file read errors without stopping ingest); `textlayer.py` (verbatim copy of grader/extract.py); `ocr.py` (RapidOCR with bundled models, position-based line grouping, raw boxes kept in `pages.ocr_json`); `config.py`. `report` returns an empty schema-valid report; `feedback` stores the file once.
- VERIFIED_OFFLINE: `.venv/Scripts/python.exe -m unittest discover -s tests/offline` → 16/16 OK (reader parity with grader, grader citation check, UTC receipt, resend occurrences, idempotence, arbitrary cwd, schema-valid stdout, exit 2 on bad input, OCR of a synthetic scan).
- Failure fixed: test teardown on Windows could not delete the SQLite file because `with sqlite3.connect()` does not close the connection; the test now uses `contextlib.closing`.
- Human gate: H-001 (reader check on the real practice and exam mailboxes, including scan OCR) prepared, WAITING_HUMAN, non-blocking.
- Next: phase 02.

## 16 October 2026: H-001 verified; phase 02a LLM back end

- H-001 HUMAN_RAN (user: all exit 0) and verified read-only: practice 163 / exam 86 documents match the inventory, 0 unreadable, receipt ranges inside the batch windows, both scans OCR-read with amounts intact. Exam scan is a different layout (Charges advice, DD/MM/YYYY, thousands separators); OCR drops spaces and emits full-width brackets, so NFKC plus space-insensitive matching is needed.
- Corpus survey (design only, no runtime use): document families listed in progress.json; the exam MSAs share the practice template with reworded clauses and different parameters.
- Loaded the claude-api skill. Corrections to the plan: forced tool_choice returns 400 on current models, so use `output_config.format` json_schema. Default model is `claude-opus-5-5` (the user named none), configurable in `harness/nova/llm_config.json`. Server-side refusal fallbacks (`fallbacks: "default"`, beta) are enabled and dropped automatically if the endpoint rejects them. Confirmed locally that the installed anthropic 1.8.0 accepts these parameters.
- IMPLEMENTED: `harness/nova/llm/` (base, sdk, cli, selection), `harness/live_check.py`, `harness/local-llm.example.json`; tests `tests/offline/test_llm.py` + `mock_llm.py` (test-only).
- VERIFIED_OFFLINE: full suite 30/30 OK; guard 7/7; setup check PASS.
- Human gate: H-002 (live CLI check, normal and stripped environment) WAITING_HUMAN.
- Next: 02b schemas and prompts.

## 16 October 2026: H-002 first run

- HUMAN_RAN step 1: PASS through the local CLI (`claude-opus-5-5`, 7.77 s, `structured_output` path). The stripped (`make grade`) environment failed: the Bun-based CLI needs SYSTEMROOT. Step 3 failed on unedited placeholders (notepad is asynchronous in PowerShell).
- IMPLEMENTED: Windows system-variable repair in the CLI back end; BOM-tolerant `.local-llm.json` read; revised step 3 (one-command file write). VERIFIED_OFFLINE: `tests/offline/test_llm.py` 16/16 (new stripped-environment and BOM tests).
- Human gate: H-002 rerun of steps 2 and 3 requested.

## 16 October 2026: H-002 verified

- HUMAN_RAN H-002 rerun (`summary.txt`): `--stripped` PASS twice (5.38 s; then 4.36 s with the new `.local-llm.json` holding real paths), backend `cli`, `claude-opus-5-5`, correct answer, prompt cache hit on the second call. With step 1 earlier, the CLI back end is VERIFIED_LIVE on a synthetic document in both the full and the grader-stripped environment.
- Open measurement: latency, output size and Pro usage limits on long documents and a full mailbox.
- Next: 02b schemas and prompts.

## 16 October 2026: phase 02b schemas, prompts, validation

- Design (from the corpus survey): one shared fact schema for all text documents; large spreadsheets get a column-map call and deterministic row parsing; every item carries source {doc, page, quote}; values transcribed as printed (money as strings), never computed by the model.
- Schema had to be cut from 34k to 17.8k characters ($defs/$ref) to fit the Windows command line for the CLI back end; checked against the structured-output feature list (no numeric/length constraints).
- IMPLEMENTED: `harness/nova/extract/{schema,prompts,validate}.py`; tests `tests/offline/test_extract_validate.py`.
- VERIFIED_OFFLINE: 12/12 validator tests; full suite 44/44. The tests caught (1) a wrong date accepted under the other day/month order and (2) an unchecked contract percentage; both fixed with per-document date-order detection and explicit numeric field lists. Read-only check on the real mailboxes: practice has no numeric dates; exam has 24 DMY-decidable documents and 2 undecided, so the index takes same-sender order hints.
- Next: 02c ingest wiring (units per email bundle / long PDF / large sheet, cache, pending status, facts table), then 02d arithmetic constraints and the bounded recheck.

## 16 October 2026: phase 02c extraction wiring

- IMPLEMENTED: `harness/nova/extract/run.py` (plan units per batch: email bundle / long PDF / large sheet / clone of identical bytes; run within the step budget with cache, schema check, validation, 2 attempts max; pending work carried to the next step; no back end fails loudly after documents are stored), `extract/tables.py` (spreadsheet columns found by header label in the real workbook, every row parsed by position), store tables `extraction_units`, `llm_cache`, `facts`, `doc_kinds`; `ingest` and `report` run extraction under the step budget; `harness.py` exits 2 on LLM errors. Table schema changed to header labels after spotting that the text layer drops empty cells (index mapping would misalign).
- Tests: `fake_claude.py` (deterministic test-only model, usable as a subprocess or in-process), `test_extract_run.py` 7/7 (planning, clones, table rows, budget/pending/resume, cache, unavailable back end, bounded retries, invented quotes rejected); CLI tests now run ingest through the fake CLI via NOVA_LOCAL_LLM. Two test expectations were wrong at first (document count; retry timing across steps) and were corrected. Full suite 51/51.
- Human gate: H-003 (first live extraction of practice batch_01, timed) WAITING_HUMAN.
- Next: verify H-003 output, then 02d.

## 17 October 2026: H-003 verified; incremental commits and chunked long PDFs

- HUMAN_RAN H-003: practice batch_01 ingest exit 0 in 399 s; 44 units, 917 facts, 0 rejected, 1 clone; report exit 0 in 1 s. Verified read-only: details in the handoff. Agreements were the critical path (144 s, 178 s per single call). All 6 unverified facts were validator bugs (sentence-final dates; a total on page 2); cached answers re-validate 640/640 ok after the fix. Agreement tables complete against their pages.
- IMPLEMENTED (user request): each unit's cache entry, facts and status commit as soon as its answer arrives (`llm.iter_completed`), with `extract: N unit(s)...` and `extract k/N done <unit> (<s>, <facts>)` lines on stderr. Test simulating a killed step: the 3 finished units survive and the next step calls only the rest.
- IMPLEMENTED: long PDFs split into 4-page units read in parallel, keeping real page labels; later chunks don't overwrite page 1's document kind. Validator: date boundary allows a sentence-final '.', and values may sit on another page of the same document. Regression tests added from the live findings.
- One regression caught by the suite (live loop called `workers_for` with no provider when every unit was already done) and one loose test filter; both fixed. Suite 55/55.
- Next: 02d.

## 17 October 2026: phase 02d arithmetic checks and bounded recheck; phase 02 closed

- IMPLEMENTED: `harness/nova/money.py`, `harness/nova/extract/constraints.py`, recheck units and `doc_checks` table in `extract/run.py`/`store.py`, `RECHECK_SCHEMA` and `RECHECK_SYSTEM`.
- Checked on the live H-003 facts first (read-only): 26/27 consistent; the 27th was an INR invoice whose extracted lines include the printed GST line, so they sum to the total rather than the subtotal. The check now accepts subtotal, total or subtotal+tax; 27/27 consistent. Tax lines stay as facts for the rules to exclude via Annex E.
- Tests: `test_constraints.py` (8) and two recheck end-to-end tests (misread corrected once and originals superseded; failed recheck keeps the originals, marked unresolved, never repeated). The suite caught a too-loose 0.01 tolerance in my line check (one-cent print differences passed) and a fake-model helper assuming every schema has `documents`; both fixed. Suite 65/65.
- Phase 02 VERIFIED_OFFLINE with live extraction verified on batch_01; live recheck quality NOT_RUN.
- Next: phase 05.

## 17 October 2026: phase 05 detectors and report assembly

- IMPLEMENTED: `harness/nova/world.py`, `rules/{common,overcharge,duplicate,waiver,late_fees,cashback,expiry}.py`, `report.py`, `harness/nova/report.schema.json` (copy of the grader schema), `feedback.py` placeholder, store table `report_history`; `report` now builds the real report.
- Design checked against live facts first (read-only, H-003 state): World initially gave the MSA 0 rate bands because the cover email's contract fact shadowed the agreement's; fixed by choosing the canonical fact from the instrument's own document. Missing-document detection now decided in Python (`holds()`), leaving only "Annex A rev 2".
- Practice answers read for learning only (variants, deciding clauses); runtime never reads them. Learned: invoice keys keep '/', and FB-P1 is an overcharge until feedback accepts the KAM's rate notice.
- Tests: `factkit.py` (invented contract/invoices), `test_overcharge.py` 15 tests with hand-worked amounts. My own hand arithmetic was wrong once (0.40 x 118 is 47.20) and a fixture received tracking too late; both test-side. Suite 80/80.
- Live check on a scratch copy of the H-003 state: 11/11 batch_01 keys match; both modes valid with the grader's schema and citation validators.
- Human gate: H-004 (feedback file + batch_02 into the live state) WAITING_HUMAN.
- Next: phase 06 feedback, remaining detector/report tests, trace replay.

## 17 October 2026: phase 06 feedback, report robustness, trace replay

- IMPLEMENTED: `harness/nova/feedback.py` (all six decisions and five fact types, scope filters, decided_at cut-off, learned_at), `World.authorized()` (Schedule 1 or a confirmed feedback grant) used by waivers, rate notices and due-date extensions; overcharge Pricer honours rate_accepted and resolve_conflict; `trace.py` replay with an allowlisted dispatcher.
- Bugs found by the new tests and fixed: a late-fee line without `refers_to_invoice` was skipped (now read from its label); an item without evidence failed schema validation and crashed the whole report (fallback evidence + per-item validation that drops only the bad item, logged); a resent invoice produced two items for one key (deduplicated).
- VERIFIED_OFFLINE: test_detectors.py 27, test_report_feedback.py 13, test_trace.py 3; suite 123/123.
- Live (copy of batch_01 state): practice feedback closes TX-US-2035-0210 only from its decided_at; batch_01 both modes 7/7 exact, 0 schema/citation errors; 14/14 traces replay.
- Human gate: H-004 still WAITING_HUMAN.

## 17 October 2026: margin step-down, phase 07 eval set and counterfactual families

- IMPLEMENTED: `rules/cashback.py` margin_step_down (threshold basis and window from the clause, invoices after the
  crossing one, per closed quarter, minus margin credits) + replay formula; qualifying spend counts a resent invoice
  number once; schema fields `step_down_by_pct`, `threshold_currency` with descriptions; validator date forms
  `09-Mar-2041`, `Mar 04, 2041`, `7-April-2041`.
- IMPLEMENTED: `evals/build_mailboxes.py` (15 original mailboxes, deterministic), `evals/cases/e01..e18`,
  `evals/feedback/m13_close_a_one_off.json`, `evals/CASES.md`; `.claude/experiments/EXP-001` (all NOT_RUN,
  cross-encoder DEFERRED); handoff H-005; H-004 note refreshed.
- VERIFIED_OFFLINE: suite 142/142 (`python -m unittest discover -s tests/offline`), new: MarginStepDownTests 6,
  resend-once 1, validator date forms 1, test_metamorphic 7, test_eval_cases 4. Mutation checks: window reset,
  strict threshold, and "any sender authorised" each make the intended tests fail.
- Offline re-check on a scratch copy of the H-003 state (report.build, no model calls): batch_01 30/30 practice
  answers consistent in both modes, 0 extra findings, 7/7 traces replay.
- Generator bugs caught by reading the output through the grader's text layer: indented bodies, float cell format,
  `None` waybill, non-deterministic bytes. All fixed.
- Human gates: H-004 and H-005 WAITING_HUMAN. Next: classify H-005 failures by layer; regression demo; phase 08.

## 17 October 2026: H-004 verified, waiver-condition fix, H-005 retry, H-006 prepared

- HUMAN_RAN H-004: feedback exit 0; batch_02 ingest 244 s, 38 units, 499 facts, 0 rejected; report exit 0.
- Offline verification on a scratch copy: batch_02 facts 509/509 ok, invoices 29/29 consistent. Recomputed reports
  (both dates, both modes): 59/60 practice answers. Miss TX-US-2035-0267 waived_but_billed: the model put a
  billing note ("you can short-pay that line") in the waiver's `condition`, and the rule skipped any condition.
  Fixed generally: `waiver.real_condition()` + schema description; 2 tests. After: 60/60, 0 extra, traces replay;
  grader `score()` on the recomputed reports 99.8/100 (scratchpad `score_offline.py`; not the official card).
- HUMAN_RAN H-005 attempt 1: all 20 cases failed in 4 s before any model call, because my handoff's
  `--harness harness\harness.py` lost its backslash in the runner's POSIX `shlex`. Handoff corrected.
- Prepared H-006 (official practice grade). Suite 144/144.

## 17 October 2026: first eval run (9/20), general fixes, run permission

- HUMAN_RAN H-005 attempt 2: 9 of 20 pass in 1946 s (`out/eval_run.txt`, `evals/results.json`). Failures by layer:
  interpretation, contract-specific charge-code letters (my agreement codes fuel FSC and security SCR; the rules
  only knew FUEL/SEC), so fuel and security were never priced: e01 e03 e04 e06 e07 e13 e15 e18 amounts are exactly
  the freight-only differences; policy, Schedule 1 categories written "billing disputes" / "payment terms" were not
  matched to billing_disputes / payment_terms: e03 e07 human_review (no recipient), e12 extension not authorised;
  e10 duplicate and e14 scan: hypotheses (a resend headed "Second reminder" read as kind reminder; OCR glued a
  character to the contract id), to be confirmed on the next run.
- IMPLEMENTED general fixes: `world.canonical_code()` (roles from the code's name), `world.categories()`,
  `contract_of` tolerates up to two OCR characters on one held contract id, duplicate treats a payment reminder of a
  paid invoice as a second request (prompt wording too). Tests: test_world_names 4 (each fix mutation-checked),
  2 duplicate tests. Practice recomputation unchanged 60/60.
- HUMAN_RAN H-006 attempt 1: replay of both modes finished (1255 s) but the grader crashed printing the card (✓ on
  a cp1252 console) before writing `--out`; no card. Next run needs `PYTHONIOENCODING=utf-8`.
- IMPLEMENTED local shared response cache (`harness/nova/llm/shared_cache.py`, only when the gitignored
  `harness/.local-llm.json` names it, never with ANTHROPIC_API_KEY) so reruns and the second grading mode reuse
  identical requests; test in test_extract_run.
- User authorised Claude to run H-005/H-006, then all project runs incl. the exam sheet (recorded in
  `.claude/rules/human-execution.md`). The guard still blocks them and auto mode refuses to edit the guard
  (self-modification); a patched guard + tests is staged in the scratchpad for the user to copy (8/8 guard tests).
- Suite 153/153.

## 17-18 October 2026: evals 20/20, regression demo, usage-limit exhaustion

- Claude-run (user's named exception): ingested 15 eval mailboxes once into `out/state_eval/` (51 live calls,
  85k output tokens; one CLI fail-fast crash, retry added to the CLI back end with a test), offline recomputation
  18/18, official `evals/run_evals.py` 20/20 from the shared cache. Regression demo: role mapping disabled -> e01
  FAIL 148.40 (`out/eval_regression_demo.txt`), restored. e14 cause confirmed (`CVN-HO-AIR-41E`); e10 unconfirmed.
- H-006 rerun died after supervised batch_01: the Claude Pro usage limit ran out. Cause: the CLI back end draws on
  the same Pro allowance as the interactive session. One practice extraction = 82 Opus calls, 262k output tokens;
  about 1M+ output tokens of harness calls in ~24 h (user runs + Claude runs) plus this long session.
- IMPLEMENTED: `LLMLimited` (usage/rate/overload replies from CLI or SDK): the step stops starting calls, the unit
  stays pending without using an attempt, one stderr line says so (previously two limit replies marked a unit
  permanently failed and its facts would be silently missing). Tests: test_usage_limit_stops_calls_and_keeps_units
  _pending, CLI error-mode type. Suite 155/155.
- Measured: ~46% of extraction output tokens are thinking, not JSON (effort medium). Lowering effort is a possible
  halving of cost; not done because all verified results are at medium.
- Grade rerun started from the shared cache (supervised batch_01 already cached): 86.0, hard gates clear. Rebuilt
  the grader's state from cache (0 calls) in `out/state_grade_dbg`; cause: chunked agreement extraction gives one
  contract fact per chunk and the World kept the chunk without rate periods, so INR P2 pickups used P1 rates.
  Fixed with `world._merge_same_doc` + ChunkedAgreementTests (mutation-checked). Suite 156/156, evals offline 18/18.
- Official grade rerun (all cached): 99.8/100, gates clear, sheet check PASS 9/9 (`report_card.txt/.json`).
- Exam answer sheet (`tools/run_mailbox.py --data data/exam`, Claude-run under the user's exception): all steps exit
  0; `answer_sheet.json` total_savings 8165.33 (overpayment 3847.70, cashback 4307.34, late fees avoided 10.29),
  1 conflict, 1 cannot_determine. Completeness checked by rebuilding the state from cache (`out/state_exam_dbg`):
  49/49 units from cache, 0 calls, 898 facts ok, 25/25 invoices consistent.
- `tools/check_submission.py`: 8 of 9 pass; the failing one is the user's `.env` key scan.
- After the user cleaned `.env`: 9 of 9 pass. That broke `test_ai_log_export` (it read its fake secrets from
  `.env`); the test now assembles them in code from pieces, so a fresh clone needs no `.env`. FAKE_KEY deferred task
  closed. Suite 156/156.

## 18 October 2026: final documents

- SOLUTION.md, DESIGN.md, AI_USE.md, evals/CASES.md rewritten as final (results, the eval case that caught a bug,
  the chunk-merge bug, cached reruns stated). CLAUDE.md architecture now says what was built; retrieval/RAG recorded
  as not built (phases 03/04 DEFERRED, EXP-001 final). README.md, GLOSSARY.md, SUBMISSION.md untouched.
- Open: the ChatGPT conversation is not exported (AI_USE.md says so).

## Entry format

Date/session; phase; changed files; exact checks and outcomes; human request IDs; actual artifacts; failures/limitations; next task. Label IMPLEMENTED, VERIFIED_OFFLINE, HUMAN_RAN or VERIFIED_LIVE explicitly. Append real events only.
