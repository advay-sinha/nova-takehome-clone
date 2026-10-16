# Human execution request: H-<number> / <title>

Status: PREPARED | WAITING_HUMAN | HUMAN_RAN | VERIFIED | FAILED
Phase: <number>
Reason you must run this: <specific human-owned operation from CLAUDE.md>
Prepared files: <existing reviewed script/config paths; never claim nonexistent scripts are runnable>
Working directory: <actual repository root>
Terminal: <WSL Bash recommended; PowerShell only with tested equivalents>
Prerequisites: <versions, local files, account access; no secrets in this document>
Expected time/resources: <estimate; label unknown if unmeasured>
Reads: <inputs>
Writes: <output/state paths>
Network/API: <none, model download or evaluator-compatible call; disclose separately>

## Steps

1. <Open terminal and enter actual directory.>
2. <Run the exact command below, using shell-safe quoting.>
3. <Check the listed artifacts and return the requested non-secret output.>

```bash
<exact verified command after entry point exists>
```

Expected result: <files, dimensions, schema, success message>
If it fails: <stop condition, readable error to share, avoid blind destructive retries>
Send back: <exit status and redacted output; never API keys, tokens or .env contents>
Claude will verify: <read-only checks on returned/generated artifacts>
Resume: <dependent task after result verification>

## Completion evidence

Executed by: <user>
Result received: <date / actual redacted output reference>
Artifacts verified: <paths and checks actually performed>
