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
- With neither, it stops with an error rather than returning an empty audit.

Each step keeps to a 540 s budget. Work that does not fit, or that hits a usage limit, stays pending and is finished
by the next step. Progress lines (`extract k/N done ...`) go to stderr, the report to stdout.

## What works

- **Results.** Practice grade (`report_card.txt`): 99.8/100 in both modes, every hard gate clear, answer-sheet check
  9/9. My own eval set: 20/20, 18 of them mine (`evals/results.json`). Exam answer sheet (`answer_sheet.json`, as of
  2031-02-28): total savings $8,165.33, with the report's schema and every citation valid.
- **Reading.** Every email, PDF and Excel sheet is read with the grader's own text layer, so quotes resolve. Receipt
  times are in UTC; a resent file stays a separate occurrence; scans are read by local OCR. The practice and exam
  mailboxes (163 and 86 documents) have no unreadable document.
- **Extraction.** One structured Claude call per email bundle, long PDFs in parallel 4-page chunks, large spreadsheets
  mapped by header and parsed row by row in Python. Every fact must quote its page, and its numbers and dates must be
  on it. Invoice arithmetic is checked, and a misread document is re-read once. The live practice and exam
  extractions had 0 rejected facts.
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

  Actions apply the $5,000 sum per key and the five unattended checks.
- **Feedback.** All six decisions apply from `decided_at`, only inside their scope, with `learned_at`. The report
  history gives stable ids, `supersedes` and `retro`.
- **Traces.** Every reported amount replays from its internal trace (`harness/nova/trace.py`, traces under
  `--state-dir/traces/`), with an allowlisted set of formulas.
- **Tests.** 156 offline tests on synthetic data, no network. They include the six counterfactual families
  (`tests/offline/test_metamorphic.py`), each checked to fail when the rule it protects is broken.

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
- **Cached reruns.** My final practice card, eval run and exam sheet reused model answers my harness had already
  extracted (a local response cache, never present on the grader's machine). They show the rules are right on those
  extractions, not that every fresh extraction comes out the same.

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
