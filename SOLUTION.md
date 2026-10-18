# My solution

Final state, 2026-10-18.

## How to run it

Python 3.11+ with `harness/requirements.txt` (`make setup`, or on Windows `python -m venv .venv` and
`.venv/Scripts/python.exe -m pip install -r harness/requirements.txt`). Nothing else is needed: the OCR model for
scanned invoices ships inside `rapidocr-onnxruntime`, and nothing is downloaded at run time.

The grader's three commands are unchanged (`ingest`, `report --as-of --mode`, `feedback`).
- With `ANTHROPIC_API_KEY` set, the harness calls Claude (`claude-opus-5-5`, configured in
  `harness/nova/llm_config.json`) through the Anthropic SDK and honours `ANTHROPIC_BASE_URL`.
- Without a key it uses a logged-in Claude Code CLI on PATH, which is how I ran it locally. The optional, gitignored
  `harness/.local-llm.json` (template: `harness/local-llm.example.json`) lets that CLI find its login inside the
  grader's stripped environment.
- With neither, the local document reader extracts explicit clauses, labelled invoice rows, spreadsheet headers
  and scoped email statements into the same typed facts. It reads the actual mailbox, including local OCR, without
  API calls, a model response cache or saved answers. Contract-specific identifiers, codes, rates and contacts come
  from the documents. A recognised invoice with no parseable billed rows fails with an actionable error.
  Authentication or rate-limit failures from an already configured model retain their existing error/retry handling.
- `harness.py --local-reader-only <command> ...` (or `NOVA_LOCAL_READER_ONLY=1`) forces the local reader even when a
  key or CLI is present; constructing a provider or touching the response cache then raises. `make grade-local`,
  `sheet-local`, `eval-local` and `eval-unseen` use it and write to `out/local_only/`, never the submission files.

`make test` runs the offline synthetic suite using the same virtualenv as the harness. `make test-mutations`
verifies twenty deliberately broken controls in temporary copies; every unmodified control must pass first, and
crashes, import errors and skipped tests do not count as a detected regression. Neither command calls a model.

The unchanged supplied grading workflow runs `make setup`, `make grade` and `make validate`. With an empty
`ANTHROPIC_API_KEY` and no Claude CLI, grading now uses the local reader. Providing a key still selects the SDK.
Run the offline checks separately with the commands above.

Each step keeps to a 540 s budget. Work that does not fit, or that hits a usage limit, stays pending and is finished
by the next step. Progress lines (`extract k/N done ...`) go to stderr, the report to stdout.

## What works

- **Committed baseline results.** Practice grade (`report_card.txt`): 99.8/100 in both modes, every hard gate clear, answer-sheet check
  9/9. My own eval set: 20/20, 18 of them mine (`evals/results.json`). Exam answer sheet (`answer_sheet.json`, as of
  2031-02-28): total savings $8,165.33, with the report's schema and every citation valid.
  These committed artifacts predate the action-guard and local-reader changes and have not been overwritten.
- **Fresh credential-free validation.** From empty state, with no model settings or response cache: `make grade`
  scores 99.831/100 in both modes, all five hard gates clear and all nine answer-sheet rows matching. The eval runner
  passes 20/20. A fresh exam run reproduces the committed totals, class ids and amounts, deadlines, conflict and
  missing-document entries, including $8,165.33 total savings. This validates the local path on these mailboxes;
  it does not measure a fresh live model extraction or establish performance on unseen layouts.
- **Unseen synthetic worlds** (`evals/unseen_worlds/`, notes in `SUITE.md`): four invented worlds with their own
  contract structure, Schedule 1 layouts, currencies, invoice/statement layouts, dates and spreadsheet headers;
  expected answers from a glossary-only Decimal oracle; local reader only. Development 25 cases, 50/50 case-runs
  (both modes). Holdout, run once on the frozen reader: 20/24 case-runs (10 of 12 cases); the two failures (all-
  ambiguous dotted dates, an amendment extending the term) were fixed generally with tests, and two fresh holdout
  cases then passed first time (final holdout 28/28). The suite drove the reader fixes listed in `SUITE.md`.
- **Reading.** Every email, PDF and Excel sheet is read with the grader's own text layer, so quotes resolve. Receipt
  times are in UTC; a resent file stays a separate occurrence; scans are read by local OCR. The practice and exam
  mailboxes (163 and 86 documents) have no unreadable document.
- **Extraction.** With model access: one structured Claude call per email bundle, long PDFs in parallel 4-page chunks, large spreadsheets
  mapped by header and parsed row by row in Python. Every fact must quote its page, and its numbers and dates must be
  on it. Invoice arithmetic is checked, and a misread document is re-read once. The live practice and exam
  extractions had 0 rejected facts. Without model access, the local reader reads agreements before billing units,
  learns charge aliases, maps spreadsheet columns by header and preserves clause, page and quote provenance. It uses
  the same schema, evidence, arithmetic, authority, financial and action checks. It handles amount-first and
  amount-last invoice layouts, missing OCR spaces, scoped waivers and dated rate notices; bank footers cannot become
  fuel-charge rows. It can resume a partially completed model extraction without dropping later agreement pages.
- **Detection.** Every class, in both modes:
  - overcharge: rate bands and periods, minimums, fuel on the correct base, Annex accessorials and the contract's own
    conditions, amendments, rate-notice authority, unranked conflicts, missing revised annexes, INR converted once;
  - duplicates: a paid invoice asked for again, and the same shipment line on two invoice numbers, net of credits;
  - waivers: only from the Schedule 1 waivers contact, naming the shipment or month; a quoted-only waiver asks for
    the original;
  - late fees not owed (extensions, grace, months, compounding) and late-fee risk;
  - cashback: quarterly rebate, annual improvement credit and handling-margin step-down (no supplied contract uses
    a margin, so that is tested on invented data only);
  - expiry.

  Actions apply the $5,000 sum per key and the five unattended checks. Open conflicts are scoped to contract,
  lane, charge and rate period across every affected shipment; freight conflicts also cover dependent fuel.
  Rejected citations prevent unattended execution and stay out of the published evidence. An item without the
  required number of resolvable citations is omitted with a diagnostic on stderr.
- **Feedback.** All six decisions apply from `decided_at`, only inside their scope, with `learned_at`. The report
  history gives stable ids, `supersedes` and `retro`.
- **Traces.** Every reported amount replays from its internal trace (`harness/nova/trace.py`, traces under
  `--state-dir/traces/`), with an allowlisted set of formulas.
- **Tests.** 188 offline tests on synthetic data, no network, including the six counterfactual families
  (`tests/offline/test_metamorphic.py`), conflict isolation, citation loss and complete numeric-value matching.
  Local-reader regressions cover altered layouts and wording, currency, OCR, bank footers, quoted and conditional
  waivers, draft authority, prompt injection, ambiguous dates, unsupported billing and partial-run recovery.
  Eight selected control regressions are also checked by `make test-mutations`. CLI crash fixtures and generated
  spreadsheet ZIP metadata are portable across Windows and Linux.

## What doesn't

- **No embedding search or RAG.** My plan included them; the brief does not ask for them. Every document is
  transcribed in full and the rules read all facts, so nothing depends on ranking. No failure in the practice runs or
  my evals came from missing context, so I left them out rather than add calls, cost and risk without a measured gain
  (`.claude/experiments/EXP-001-supplementary-retrieval.md`). The gap this leaves is clause wording that falls outside
  my extraction fields, which the rules then see only as free text.
- **Confidence** is a hand-set heuristic. The practice card gives a Brier score of 0.0084, but AUROC could not be
  measured because no item was wrong, so it is not calibrated.
- **Runs and cost.** One practice batch took 399 s of the 600 s step limit. A hidden batch with many long contracts
  could need two steps; unfinished work is saved and completed by the next one.
- **Local-reader coverage.** The fallback recognises explicit document structures, not arbitrary natural language.
  Unrecognised clauses can remain unextracted; a new invoice layout may need model access or an additional tested
  parser. Partially parsed invoices still go through arithmetic checks and expose unresolved extraction issues.
  No trained model, embeddings or additional external service was introduced.
- **Cached model reruns.** The committed practice card, eval run and exam sheet reused model answers my harness had already
  extracted (a local response cache, never present on the grader's machine). They show the rules are right on those
  extractions, not that every fresh model extraction comes out the same. The fresh credential-free checks above
  read source documents again and use no model-response cache.

## The eval case that caught a bug

`e01_wrong_bracket_rate`, with seven others failing for the same reason. My first run of my own eval set passed 9 of
20. The rules had been written against the practice contract, which codes fuel as `FUEL`. My eval agreement codes it
`FSC` and security `SCR`, so no fuel or security line was ever priced. e01 came out at 148.40 (the freight
difference alone) instead of 176.59.

The same run showed three more problems:
- Schedule 1 categories written "billing disputes" with a space were not matched. That left autonomous disputes
  without a recipient (e03, e07) and a due-date extension unauthorised (e12).
- OCR had added an "E" to the scanned invoice's contract id (e14).

The fixes are general: contract codes map to charge roles by the charge's name, categories are normalised, and a
contract id with up to two stray OCR characters still matches the one held contract it fits. After them the set
passes 20 of 20. To show the set catches a regression, I disabled the code mapping again, and e01 failed at 148.40
(`out/eval_regression_demo.txt`).

The practice grade caught one more bug of mine. Long agreements are read in page chunks, and only one chunk's
contract fact was used, so rate periods printed on another page went missing and Indian-rupee invoices were priced
in the wrong period (86.0 before the fix, 99.8 after). The practice answers showed me this one; the fix merges the
chunks of one document and has its own test.

## Submission status (against SUBMISSION.md)

| Item | Status |
|---|---|
| Repo and commit hash | the commit pushed with this file (given in the reply email) |
| SOLUTION.md | this file |
| answer_sheet.json, report_card.txt/.json | done: practice card 99.8/100; exam sheet as of 2031-02-28, schema and citations valid |
| evals/ with 10+ own cases and results.json | 18 own cases on 15 original mailboxes; results.json 20/20 |
| DESIGN.md | done |
| AI_USE.md and prompt log | done; full logs in `ai_log/` |
| `make validate` (`tools/check_submission.py`) | 9 of 9 checks pass |
