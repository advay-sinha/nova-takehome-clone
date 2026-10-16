---
name: nova-phase
description: Implement or resume a numbered Nova phase with acceptance checks and human execution gates.
---

# nova-phase

Requested phase: $ARGUMENTS. Read CLAUDE.md, progress, phases/INDEX and the matching phase document. If no number is supplied, use current_phase. If ambiguous/invalid, report the valid 00-09 values. Check dependencies and open human gates. Implement a small coherent slice, run only permitted isolated offline checks, and update actual evidence. Prepare human-run commands before requesting them. Do not silently skip phase exits or execute a human-owned task.

Complete required correctness and verification before optional experiments. Read references/DIFFERENTIATORS.md for phases 02/04/05/07; implement its verification/trace/testing tasks within the phase. Optional reranking is gated after the phase 07 baseline and before final runs.

All paths above are relative to `.claude/` unless they name root project files. Root CLAUDE.md and the user execution policy apply throughout.
