---
name: nova-status
description: Resume Nova work, inspect progress, identify open human gates and the next useful implementation task.
---

# nova-status

Read CLAUDE.md, progress, latest WORKLOG and outstanding handoffs. Verify reported artifacts rather than trusting stale status. Summarize current phase, implemented work, exact verification level, human-owned blockers and next action. Resume the next authorized coding slice; ask the user only for a concrete human operation or essential missing context. Never advance a live verification gate without actual results.

Include the optional-experiment decision. Do not assume model improvements. Complete required correctness and verification before optional experiments.

All paths above are relative to `.claude/` unless they name root project files. Root CLAUDE.md and the user execution policy apply throughout.
