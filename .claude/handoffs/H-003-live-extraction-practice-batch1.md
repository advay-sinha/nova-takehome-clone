# Human execution request: H-003 / First live extraction of practice batch_01

Status: VERIFIED
Phase: 02
Reason you must run this: real-mailbox ingest with live model calls through the local Claude Code CLI (human-owned).
Prepared files: `harness/harness.py`, `harness/nova/{app,store,reader,ocr,textlayer}.py`, `harness/nova/extract/{run,schema,prompts,validate,tables}.py`, `harness/nova/llm/*`. Offline suite 51/51.
Working directory: `D:\Code\sides\nova-takehome`
Terminal: PowerShell, `ANTHROPIC_API_KEY` unset (CLI back end).
Prerequisites: H-002 verified; `harness\.local-llm.json` present.
Expected time/resources: unmeasured. About 40 extraction units (one call per email bundle, one per agreement, one per large spreadsheet; resent attachments are copied without a call). The step budget is 540 s; units that do not fit stay pending, and the report command finishes them. Uses a noticeable part of your Pro usage; stop if you hit a usage limit.
Reads: `data/scenarios/batch_01` (read-only).
Writes: `out/state_live_practice/` (gitignored by `out/state_*/`), including the two log files below.
Network/API: Claude Code CLI to Anthropic through your login.

## Steps

1. Run the block below. It ingests batch_01, then runs one report, which finishes any pending units. Both steps are timed.

```powershell
New-Item -ItemType Directory -Force out\state_live_practice | Out-Null
$t = Measure-Command { .venv\Scripts\python.exe harness\harness.py ingest data\scenarios\batch_01 --state-dir out\state_live_practice 2> out\state_live_practice\ingest_b1.log }
"ingest exit $LASTEXITCODE in $([int]$t.TotalSeconds) s"
$t = Measure-Command { .venv\Scripts\python.exe harness\harness.py report --as-of 2035-05-31 --state-dir out\state_live_practice > out\state_live_practice\report_b1.json 2> out\state_live_practice\report_b1.log }
"report exit $LASTEXITCODE in $([int]$t.TotalSeconds) s"
Get-Content out\state_live_practice\ingest_b1.log, out\state_live_practice\report_b1.log
```

2. Send back the printed exit codes, seconds and log lines.

Expected result: ingest exit 0, with an `ingest: extraction {...}` line counting done/facts/rejected units (pending is allowed). Report exit 0 (findings are still empty until phase 05).
If it fails: send the logs. If you hit a Pro usage limit, stop and say so; the state is reusable, and a rerun continues pending units.
Send back: exit codes, seconds, log lines. No credentials are involved.
Claude will verify (read-only SQL on `out/state_live_practice/nova.sqlite3`): unit statuses, call latency per unit, cache and usage records, facts per kind and status, the reasons for rejected and unverified facts, the doc-kind classification of every document, contract tables (rate rows, fuel, accessorials, Schedule 1) against the PDF pages, and tracking/ledger rows parsed from the spreadsheets.
Resume: 02d (arithmetic constraints and the bounded recheck) and the phase 05 rules are tuned on what this shows.

## Completion evidence

Executed by: user, 2026-10-17.
Result received (`summary.txt`): ingest exit 0 in 399 s; report exit 0 in 1 s; `ingest batch_01: 82 documents, 82 new or changed, 0 unreadable`; `extraction {'done': 44, 'facts': 917, 'rejected': 0, 'cloned': 1}`.
Artifacts verified (read-only SQL on `out/state_live_practice/nova.sqlite3`):
- Units: 41 bundles (median 16.0 s, max 82.0 s), 2 agreements (144.2 s, 177.6 s; the critical path), 1 table map (6.4 s), 1 clone; no errors. Tokens: output 165,241; cache read 395,343; cache creation 122,391.
- Facts: 917 = 640 from the model + 277 tracking rows parsed by Python; 0 rejected; 6 unverified. All 6 were validator bugs, not model errors: 5 sentence-final dates ("...to 2035-04-03.") and 1 invoice total printed on page 2 of 2. After the fix, re-validating the cached answers gives 640/640 ok.
- Completeness against the agreement pages: rate lines 30 (US) / 40 (IN) / 5 (amendment) -> 60 / 80 / 5 rate rows (one per period); fuel 13/13 each; FX 13/13; accessorials 10/10 and 9/9; charge codes 18/18 each; Schedule 1 6/6 and 7/7; every rate value is inside its own quote line. Every document got a kind.
Follow-ups made: incremental commit with `extract k/N` progress (user request); long PDFs read in 4-page chunks in parallel; validator date boundary and same-document field lookup fixed with regression tests.
