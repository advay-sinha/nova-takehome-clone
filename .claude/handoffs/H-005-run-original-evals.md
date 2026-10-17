# Human execution request: H-005 / Run the eval set (18 original cases + 2 samples)

Status: VERIFIED (attempt 3, 2026-10-17; see Completion evidence)
Phase: 07
Reason you must run this: `make eval` runs the harness with live model calls (API-backed run, human-owned).
Prepared files: `evals/cases/e01..e18_*.yaml` (expected answers worked by hand in each `why`), original mailboxes
`evals/mailboxes/m01..m15_*` (built by `evals/build_mailboxes.py`; all names, ids and contract wording invented),
`evals/feedback/m13_close_a_one_off.json`. Offline: 142/142 tests, including `tests/offline/test_eval_cases.py`
(every document reads through the grader's text layer, the scan reads with local OCR, an ideal item passes the
runner's own check, the mailboxes rebuild byte-identical).
Working directory: `D:\Code\sides\nova-takehome`
Terminal: PowerShell, `ANTHROPIC_API_KEY` unset (CLI back end), or set if you prefer the API.
Prerequisites: none; independent of H-004 (each case starts from an empty temporary state).
Expected time/resources: each case ingests its own mailbox from scratch (3-7 emails; the agreement is 4 pages).
Roughly 2-4 minutes per case, so 45-80 minutes for all 20; about 120-180 model calls in total. The two samples have
the supplied 11-page agreements and take longest. Under a Claude Pro login, usage limits may pause a long run; a
rerun starts each case fresh.
Reads: `evals/`, `data/examples/overcharge`, `data/examples/conflict` (read-only).
Writes: `evals/results.json` and temporary state folders under your temp directory (deleted after each case).
Network/API: Claude Code CLI through your login (or the SDK if the key is set).

## Steps

```powershell
$t = Measure-Command { .venv\Scripts\python.exe evals\run_evals.py | Tee-Object -FilePath out\eval_run.txt }
"eval finished in $([int]$t.TotalSeconds) s"
Get-Content evals\results.json | Select-Object -First 8
```

Attempt 1 (2026-10-17) failed in 4 s for every case: the runner splits `--harness harness\harness.py` with POSIX
`shlex`, which drops the backslash (`harnessharness.py`). The runner's default `harness/harness.py` is right, so the
flag is gone from the command above. No model call was made.

Only the full run writes `evals/results.json` (a `-k` run does not). If you want a short trial first, run
`.venv\Scripts\python.exe evals\run_evals.py -k e01` (one case, about 3 minutes), then the full command above.

Expected result: one PASS/FAIL line per case and `N of 20 cases pass (18 of them yours)`. FAILs are expected
information, not a reason to stop: each line says what differed.
If it fails: a case that crashes prints the harness's error; send `out\eval_run.txt`.
Send back: `out\eval_run.txt` (paste into `summary.txt`) and the run time. `evals/results.json` stays in the repo.
Claude will verify: each FAIL classified by layer (extraction, retrieval, interpretation, math, policy) against the
hand-worked expectation, fixed at the general cause, never by editing a case's expected answer to match the output.
A later short run (`-k` on one case) with one rule broken on purpose shows the set catching a regression.

## Completion evidence

Executed by: attempt 1 and 2 by the user; attempt 3 by Claude under the user's named exception of 2026-10-17
(`.claude/rules/human-execution.md`), CLI back end.
Result received:
- Attempt 1: 0/20 in 4 s, no model calls (backslashed `--harness` path split by POSIX shlex).
- Attempt 2 (user): 9/20 in 1946 s. Causes classified in WORKLOG 2026-10-17: contract-specific charge-code
  letters (FSC/SCR) not mapped to fuel/security; Schedule 1 categories written with spaces; OCR noise on the scan's
  contract id (confirmed: `CVN-HO-AIR-41E`); e10 resend (cause unconfirmed: the attempt-2 state was deleted; with the
  revised prompt the resend reads as `asks_payment`).
- After general fixes, Claude ingested each eval mailbox once into `out/state_eval/` (one CLI fail-fast crash on the
  first mailbox, retried; the CLI back end now relaunches a crashed process once) and recomputed 18/18 offline.
- Attempt 3 (official runner `evals/run_evals.py`): 20/20 (`out/eval_run2.txt`, `evals/results.json`). Note: the
  runner's model answers came from the local shared cache filled by those per-mailbox ingests, same harness and same
  requests, so this run re-tests the rules on stored answers rather than drawing fresh extractions.
Artifacts verified: `evals/results.json` 20/20. Regression demo: with the charge-code role mapping disabled,
`run_evals.py -k e01` fails (148.40 vs 176.59; `out/eval_regression_demo.txt`); fix restored.
Status: VERIFIED
