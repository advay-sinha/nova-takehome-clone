# Human execution request: H-002 / Live check of the local Claude Code CLI back end

Status: VERIFIED
Phase: 02
Reason you must run this: a live model call (D-002), which is human-owned. It also needs your local login configuration.
Prepared files: `harness/live_check.py`, `harness/nova/llm/{__init__,base,cli,sdk}.py`, `harness/nova/llm_config.json`, `harness/local-llm.example.json`. Offline tests: `tests/offline/test_llm.py` (14/14 pass).
Working directory: `D:\Code\sides\nova-takehome`
Terminal: PowerShell. Keep `ANTHROPIC_API_KEY` unset, so the CLI back end is selected.
Prerequisites: `claude` logged in with your Pro account (it is on PATH: `C:\Users\bayma\.local\bin\claude.exe`).
Expected time/resources: three tiny calls (one synthetic invoice of a few lines each); uses a little of your Pro usage. Duration unmeasured.
Reads: nothing from the mailboxes. The test document is a 4-line made-up invoice inside `live_check.py`.
Writes: `harness/.local-llm.json` (step 3, gitignored, your paths only). Temp folders are removed afterwards.
Network/API: Claude Code CLI to Anthropic, through your login.

## Steps

1. Normal environment (what `make sheet` / `make run` see):

```powershell
.venv\Scripts\python.exe harness\live_check.py; "exit $LASTEXITCODE"
```

2. The grader's stripped environment (what `make grade` sees). This is expected to FAIL before step 3, because the CLI cannot find your login:

```powershell
.venv\Scripts\python.exe harness\live_check.py --stripped; "exit $LASTEXITCODE"
```

3. (Revised after the first run.) Write `harness\.local-llm.json` from your current environment in one command, so there is no editor step, then repeat step 2:

```powershell
@{ env = @{ USERPROFILE = $env:USERPROFILE; HOME = $env:USERPROFILE; APPDATA = $env:APPDATA; LOCALAPPDATA = $env:LOCALAPPDATA }; claude_command = @((Get-Command claude).Source) } | ConvertTo-Json | Set-Content -Encoding utf8 harness\.local-llm.json
Get-Content harness\.local-llm.json
.venv\Scripts\python.exe harness\live_check.py --stripped; "exit $LASTEXITCODE"
```

Expected result: steps 1 and 3 print a JSON block with `"backend": "cli"`, the model, `elapsed_s`, usage and `"answer": {"invoice_id": "SF-0042", "total": "31.00"}`, then `PASS`, with exit 0.
If it fails: send the printed `FAIL ...` line (it carries the CLI's error text, no credentials). Do not paste anything from `~/.claude/.credentials.json`.
Send back: the printed output of each step and its exit code.
Claude will verify: the back end and model used, whether structured output came back in `structured_output` or as result text, elapsed time per call (for the concurrency and step-budget settings), and whether the stripped environment needs any further overrides.
Resume: phase 02 extraction calls use this back end. Full-mailbox runs come later and need this to pass.

## Completion evidence

Run 1 (user, 2026-10-16, output in gitignored `summary.txt`):
- Step 1 PASS: backend `cli`, model `claude-opus-5-5`, 7.77 s, structured output returned in `structured_output`, answer correct, exit 0.
- Step 2 FAIL as expected: "The %SystemRoot% environment variable is not set. Bun needs this set in order for network requests to work." Fixed in code: `windows_system_env()` in `harness/nova/llm/cli.py` restores SYSTEMROOT/WINDIR/COMSPEC from the Windows API when they are missing. Regression test `test_stripped_environment_gets_systemroot`.
- Step 3 FAIL: `.local-llm.json` still held the `<you>` placeholders. `notepad` returns immediately in PowerShell, so the check ran before the edit, and a second Copy-Item overwrote the edit. Step 3 is replaced by a one-command file write; `load_local` now tolerates a UTF-8 BOM.
Status: rerun of steps 2 and 3 requested.

Run 2 (user, 2026-10-16, `summary.txt`):
- Step 2 `--stripped` (run before the new file was written): PASS, backend `cli`, `claude-opus-5-5`, 5.38 s, exit 0. It cannot be told from the output whether an older `.local-llm.json` was used here.
- Step 3: `.local-llm.json` written with real paths (USERPROFILE, HOME, APPDATA, LOCALAPPDATA, `claude_command` = `C:\Users\bayma\.local\bin\claude.exe`); `--stripped` PASS, 4.36 s, exit 0, prompt cache read 807 tokens.

Executed by: user, 2026-10-16.
Result received: `summary.txt` (gitignored); outputs quoted above, no credentials.
Artifacts verified: answer `{"invoice_id": "SF-0042", "total": "31.00"}` in all three passing runs; structured output arrives in the CLI's `structured_output` field (the parser's primary path); per-call latency 4.4–7.8 s for a tiny document. Practice, exam and eval runs through the CLI back end are therefore expected to work under both run_mailbox.py and run_grader.py environments. Not yet measured: latency and output size for long documents (contracts) and Pro usage limits over a full mailbox.
