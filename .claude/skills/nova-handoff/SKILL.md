---
name: nova-handoff
description: Prepare step-by-step human execution instructions for API/service setup, ML/AI preprocessing, model preparation/training or API-backed corpus runs.
---

# nova-handoff

Task: $ARGUMENTS. Read rules/human-execution.md and references/HUMAN-HANDOFF.md. Finish required implementation/config preparation first. Verify target script exists and its arguments are documented without starting the real operation. Create a numbered handoff from templates/HANDOFF.md with actual cwd/shell, prerequisites, commands, reads/writes, network/cost/resource disclosure, expected outputs and failure steps. Never include credentials. Set progress BLOCKED_HUMAN where appropriate, ask the user to execute and return sanitized results, then stop dependent work. On completion verify artifacts read-only and record actual evidence.

For optional reranker preparation, first verify a diagnosed failure, the phase 07 baseline and that required correctness work is complete; use references/DIFFERENTIATORS.md. Specify paired tokenizer/classification runtime, pinned revision, hashes/license, offline load check and CPU benchmark. For any future learned confidence or training, obtain the user’s scope choice before preparing its execution handoff.

All paths above are relative to `.claude/` unless they name root project files. Root CLAUDE.md and the user execution policy apply throughout.
