# Decision: auto-select the LLM back end (Anthropic SDK or local Claude Code CLI)

Date: 2026-10-16. Decided by: user. Supersedes D-001 (offline, no key).

Context and observed failure: Without a personal API key, the real harness could not produce the practice report card or the exam answer sheet (D-001). The user has Claude Code (`claude` 2.1.301, Pro login) on this machine, and its headless mode (`claude -p --output-format json --json-schema ...`) can serve the same structured extraction calls.
Options: (a) stay offline (D-001); (b) auto-select: Anthropic SDK when ANTHROPIC_API_KEY is set, local Claude Code CLI otherwise; (c) CLI only behind an explicit local flag.
Chosen option and why: (b), the user's choice. The grader's machine always has ANTHROPIC_API_KEY, so it always takes the SDK path. Locally the user can run `make run`/`make sheet`/`make grade` with the real harness. Prompts, schemas, validation and caching are shared, so the only difference between the two paths is transport.
make grade detail: `grader/run_grader.py` passes only PATH and ANTHROPIC_* and a fresh empty HOME. The CLI path reads a gitignored local file, `harness/.local-llm.json`, that names the environment overrides (for example USERPROFILE/HOME/APPDATA) the CLI needs to find the user's login. The grader's machine never has this file. `tools/run_mailbox.py` keeps the full environment, so `make sheet`/`make run` should not need it.
Evidence / test: none yet. Offline tests will cover back-end selection, command construction and response parsing with a fake CLI. One live check under the stripped environment is user-run.
Time and runtime impact: none for the grader. Locally, each CLI call pays process start-up time and counts against the Pro usage limits. Calls run with bounded concurrency and a content-addressed cache so a step stays inside its 600 s limit.
Human execution needed: every run that makes live model calls (CLI or SDK) remains user-run, including the first live check and all grade/sheet/run/eval runs.
Unverified assumptions:
- Headless `claude -p` works with a Pro login under the overridden environment.
- Its structured output matches the SDK path closely enough for the same validators.
- The Pro usage limits allow a full mailbox run.
Guardrails:
- The CLI path runs from an empty temp directory with `--setting-sources` limited, no session persistence, and no tools, so project files, hooks and MCP servers never enter extraction.
- Mailbox text stays untrusted data.
- No credentials are copied, printed or stored.
- Local CLI outputs are labelled as such in SOLUTION.md; they are not the grader's live SDK results.
Revisit condition: the CLI path fails the live check, hits usage limits, or the user obtains an API key.
