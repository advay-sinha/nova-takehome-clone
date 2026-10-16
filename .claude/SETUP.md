# Install and start this project setup

This package contains Claude configuration and guidance, not a completed harness. Merge its root contents into your private copy of `nova-takehome`: `CLAUDE.md`, `.claude/`, `docs/` and `ai_log/`. Do not copy it into the harness subfolder. Existing upstream brief, data, Makefile and grader files remain in place. For an existing setup, preserve actual progress.json, WORKLOG, handoffs and implementation; merge changed guidance/settings rather than resetting work to this package’s starter status. If you already have Claude configuration, compare and merge it rather than overwriting your own rules.

## Recommended Windows workflow

Use WSL Ubuntu for the existing POSIX Makefile and the included Python hooks. The project and Claude session should be opened in the same WSL environment. These are human-executed steps. A native PowerShell Claude session needs its hook command/interpreter adapted; do not claim the WSL configuration works there unmodified.

1. Open the repository root in WSL. Replace the example path with your actual path:

```bash
cd /mnt/c/Users/arnav/Downloads/nova-takehome
python3 --version
git status --short
```

2. Verify the configuration without touching a mailbox or API:

```bash
python3 .claude/hooks/test_guard.py
python3 .claude/scripts/check_setup.py
```

3. Start Claude Code from the repository root:

```bash
claude
```

Use your Claude Pro login. Authenticate in the product's own login flow; do not paste credentials into chat. Review the project trust/settings prompt. Do not use a permission bypass flag.

4. In Claude, run:

```text
/nova-start
```

Claude should inspect readiness, install pinned dependencies into `.venv` and run the offline checks itself. It hands off API/service setup, API-backed runs, ML/AI preprocessing, model preparation and training. After you complete a handoff, return the non-secret command output and ask Claude to verify the files and continue.

5. Use `/nova-phase 01` to work on the first implementation phase, `/nova-status` to resume, `/nova-handoff preprocess` to prepare a manual execution request, and `/nova-review` for an ordinary review in the current session. Use `/nova-package` to prepare final delivery; it does not publish or submit.

## What's installed

- Root `CLAUDE.md`: always-loaded project instructions.
- `.claude/rules/`: execution ownership and audit/RAG rules.
- `.claude/phases/`: ordered task briefs with completion gates.
- `.claude/skills/`: native project skills surfaced as `/nova-*` commands.
- `.claude/hooks/`: session reminder and PreToolUse guard with offline tests.
- `.claude/progress.json`, `WORKLOG.md`: honest resumable state.
- `.claude/references/`: handoff format, acceptance matrix, runtime constraints and DIFFERENTIATORS.md with the experiment gates.
- `.claude/templates/`: execution request, decision, experiment and finding-trace templates.
- `.claude/agents/nova-reviewer.md`: optional read-only reviewer definition, not launched automatically.
- `docs/NOVA-SOLUTION-PLAN.md`: current detailed plan.

`.claude/phases/` is not a built-in Claude scheduler. The `/nova-phase` skill loads the requested file. Project skills follow Claude Code's `.claude/skills/<name>/SKILL.md` layout; no personal-skill installation is needed.

## Checks and limits

The included checks verify configuration files, skill frontmatter, phase references and hook behavior. They do not test the harness, live API extraction, actual embedding assets, or exam correctness. Hooks are additional workflow checks, not a sandbox for arbitrary shell programs. User/global/managed settings can affect Claude's effective permissions; inspect them if a setting behaves unexpectedly.

The grader may run the submitted harness unattended with its own key. These human-execution rules govern Claude's development actions, not the evaluator's operation of the product CLI.

Official references: https://code.claude.com/docs/en/skills ; https://code.claude.com/docs/en/settings ; https://code.claude.com/docs/en/hooks
