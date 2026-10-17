# Human execution request: H-006 / Official practice grade (`make grade` equivalent)

Status: VERIFIED (attempt 4, 2026-10-18; see Completion evidence)
Phase: 07/08
Reason you must run this: the grader replays the practice mailbox through the harness with live model calls
(API-backed run, human-owned).
Prepared files: harness with the waiver-condition fix (2026-10-17). Offline evidence, not official: reports
recomputed from your H-003/H-004 state and scored with the grader's own `score()` give 99.8/100, all hard gates
clear, answer-sheet check 9/9 (both modes, both batches; no model calls).
Working directory: `D:\Code\sides\nova-takehome`
Terminal: PowerShell, `ANTHROPIC_API_KEY` unset (CLI back end; `harness/.local-llm.json` lets it work in the
grader's fresh HOME, verified in H-002).
Prerequisites: none. The grader uses its own temporary sandboxes, not `out/state_live_practice`.
Expected time/resources: each mode replays both batches from an empty state: batch_01 about 400 s (H-003), feedback,
batch_02 about 250 s (H-004), two reports. About 25 minutes for both modes, about 165 model calls. A step over 600 s
fails that step, so watch for `timed out` in the output.
Reads: `data/scenarios` (read-only).
Writes: `report_card.json`, `report_card.txt` in the repo root (submission files), temporary sandboxes.
Network/API: Claude Code CLI through your login.

## Steps

```powershell
$t = Measure-Command { .venv\Scripts\python.exe grader\run_grader.py --harness "python harness/harness.py" --data data/scenarios --key data/scenarios/answers --mode both --out report_card.json > report_card.txt }
"grade exit $LASTEXITCODE in $([int]$t.TotalSeconds) s"
Get-Content report_card.txt | Select-Object -First 30
```

Use forward slashes inside `--harness "..."` (the grader splits it the POSIX way, as in H-005 attempt 1).
Expected result: exit 0 and a card. Progress goes to the terminal (stderr); the card goes to `report_card.txt`.
If it fails: send the terminal output; a step error is listed in the card's `runs` section.
Send back: the printed lines (paste into `summary.txt`). `report_card.json` and `.txt` stay in the repo.
Claude will verify: the card against the offline 99.8 recomputation; any difference traced to the run (timeouts,
extraction differences between runs) and classified by layer.

## Completion evidence

Executed by: attempt 1 by the user (replay finished, card print crashed on cp1252); attempts 2-4 by Claude under the
user's named exception of 2026-10-17 (`.claude/rules/human-execution.md`).
Result received:
- Attempt 2: stopped after supervised batch_01, Claude Pro usage limit exhausted (see WORKLOG 2026-10-18).
- Attempt 3: 86.0/100, hard gates clear; batch_02 INR invoices priced at P1 rates. Cause: long agreements are now
  extracted in page chunks and the World used one chunk's contract fact, which had no rate periods. Fixed in general
  (`world._merge_same_doc`, test ChunkedAgreementTests, mutation-checked). Found with the practice key; no practice
  id or value in code.
- Attempt 4: 99.8/100, hard gates clear, answer-sheet check PASS 9/9 (`report_card.txt`, `report_card.json`). Its
  model answers came from the local shared cache filled by attempts 2-3 (same harness version and schema).
Artifacts verified: report_card.json/.txt in the repo root.
Status: VERIFIED
