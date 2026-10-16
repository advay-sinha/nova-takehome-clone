# Nova Claude Code setup package

Merge this package into your **private nova-takehome repository root**, then open that root in WSL Ubuntu. The package contains project instructions, native Claude skills, phase guides and workflow hooks; it does not implement the audit harness.

Read `.claude/SETUP.md` for installation and startup. From your repository root, you can verify these configuration files with:

```bash
python3 .claude/hooks/test_guard.py
python3 .claude/scripts/check_setup.py
claude
```

In Claude Code, start with `/nova-start`. The model should implement code, install pinned dependencies into `.venv` and run offline checks itself, and give you concrete manual execution requests for API/service setup and calls, real ML/AI preprocessing, model asset preparation, any future training and API-backed grader/eval runs. It must wait for your execution results before claiming those steps completed.

Complete required correctness and verification before optional experiments; optional reranking is considered only after baseline evaluation. Claude Pro is the development assistant; the evaluator supplies the runtime Anthropic key.

Commands: `/nova-start`, `/nova-status`, `/nova-phase 03`, `/nova-handoff preprocess`, `/nova-retrieval`, `/nova-eval`, `/nova-review`, `/nova-package`.

The hooks block known human-owned commands and edits to supplied brief/grader/data through the matched Claude tools. They are workflow guards, not a complete sandbox for arbitrary shell code. Check your effective Claude settings and do not use permission bypass flags. Synthetic offline tests remain available to Claude.

The embedded plan includes manual execution ownership and the updated verification/trace/evaluation approach. Read `.claude/references/DIFFERENTIATORS.md` for concrete keep/skip rules for the optional pretrained reranker. No custom training is planned.

If upgrading an existing setup, preserve actual progress, WORKLOG, handoffs and implementation. Merge configuration changes; do not overwrite completed work with the starter status in this package.

No personal/global skill installation, upstream push, invitation or assignment submission is included.
