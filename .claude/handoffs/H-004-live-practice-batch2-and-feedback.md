# Human execution request: H-004 / Practice feedback file and batch_02 into the live state

Status: VERIFIED (2026-10-17; see Completion evidence)
Phase: 05/06
Reason you must run this: real-mailbox ingest with live model calls (human-owned).
Prepared files: harness as of the phase 05 detectors and report assembly (`harness/nova/rules/*`, `report.py`, `world.py`). Offline suite 80/80 when written; 142/142 now (feedback, traces, margin step-down, eval checks added). On a copy of your batch_01 state, both report modes match the practice key for batch_01 (11/11 keys) with 0 schema and 0 citation errors.
Working directory: `D:\Code\sides\nova-takehome`
Terminal: PowerShell, `ANTHROPIC_API_KEY` unset (CLI back end).
Prerequisites: H-003 state in `out\state_live_practice` (do not delete it).
Expected time/resources: similar to H-003 (about 400 s, about 45 calls). Progress lines `extract k/N done ...` now appear in the log as each call completes, and each answer is saved immediately.
Reads: `data/scenarios/feedback/W1_batch_01.json`, `data/scenarios/batch_02` (read-only).
Writes: `out/state_live_practice/` only.
Network/API: Claude Code CLI through your login.

## Steps

Same order as the grader: feedback after batch_01, then batch_02, then the batch_02 reports.

```powershell
.venv\Scripts\python.exe harness\harness.py feedback data\scenarios\feedback\W1_batch_01.json --state-dir out\state_live_practice 2> out\state_live_practice\feedback_b1.log; "feedback exit $LASTEXITCODE"
$t = Measure-Command { .venv\Scripts\python.exe harness\harness.py ingest data\scenarios\batch_02 --state-dir out\state_live_practice 2> out\state_live_practice\ingest_b2.log }
"ingest exit $LASTEXITCODE in $([int]$t.TotalSeconds) s"
.venv\Scripts\python.exe harness\harness.py report --as-of 2035-09-30 --mode supervised --state-dir out\state_live_practice > out\state_live_practice\report_b2_supervised.json 2> out\state_live_practice\report_b2.log; "report exit $LASTEXITCODE"
Get-Content out\state_live_practice\feedback_b1.log, out\state_live_practice\report_b2.log
Get-Content out\state_live_practice\ingest_b2.log | Select-Object -Last 6
```

Expected result: all exits 0. The ingest log ends with `ingest: extraction {...}`. The report log shows the item count. (Updated 2026-10-17: feedback is now applied by the harness; I recompute both report dates and modes from this state without new calls.)
If it fails: send the logs; a rerun continues from what was saved.
Send back: the printed exit codes, seconds and log lines (paste into `summary.txt`).
Claude will verify: batch_02 extraction quality (as for H-003), then build both modes for both report dates on a copy of the state and compare with the practice key, including feedback effects once phase 06 is in.

## Completion evidence

Executed by: the user, PowerShell, CLI back end (2026-10-17).
Result received: feedback exit 0 (1 item); ingest batch_02 exit 0 in 244 s, 38/38 units, 499 facts, 0 rejected,
1 cloned; report 2035-09-30 supervised exit 0, 163 documents, 16 items.
Artifacts verified (offline, on a scratch copy; no model calls): batch_02 facts 509/509 ok, invoice checks 29/29
consistent. Reports recomputed for both dates and modes: 59/60 practice answers at first; the miss
(TX-US-2035-0267, waived_but_billed) came from the waiver rule treating the model's `condition` text "If it has
already been invoiced, you can short-pay that line." as a condition. Fixed in general (schema description +
`waiver.real_condition`, tests). After the fix 60/60, 0 extra findings, traces 7/7 and 17/17 replay; the grader's
`score()` on these recomputed reports: 99.8/100, hard gates clear, answer-sheet check 9/9. Not an official card
(H-006).
Status: VERIFIED
