# Phase index

Use `/nova-phase <number>`. Read the selected phase and `.claude/progress.json`. Work in dependency order unless a documented independent task can proceed. Complete required correctness and verification before optional experiments.

| Phase | Focus | Guide |
|---|---|---|
| 00 | Environment and scope | [00-bootstrap.md](00-bootstrap.md) |
| 01 | Readers and persistent state | [01-ingestion.md](01-ingestion.md) |
| 02 | Typed extraction and source provenance | [02-facts.md](02-facts.md) |
| 03 | Structured retrieval and local embeddings | [03-retrieval.md](03-retrieval.md) |
| 04 | Context compilation and grounded interpretation | [04-rag.md](04-rag.md) |
| 05 | Financial calculations and all findings | [05-audit.md](05-audit.md) |
| 06 | Feedback, adaptation and action policy | [06-feedback.md](06-feedback.md) |
| 07 | Generalization and retrieval evaluation | [07-eval.md](07-eval.md) |
| 08 | Exam evidence and arithmetic audit | [08-exam.md](08-exam.md) |
| 09 | Final validation and delivery | [09-package.md](09-package.md) |

Phase files are ordinary reference documents loaded by the project skill, not a built-in Claude scheduler. Do not premark phases complete. Training is not baseline: use HUMAN-HANDOFF.md if a measured need arises.

After phase 07, one optional pretrained reranker may be tested if core correctness is complete, a ranking miss is diagnosed and human model preparation is done. Freeze feature choices before phase 08/final official runs. Model training is outside this plan. Read `../references/DIFFERENTIATORS.md` for trace, verification and experiment criteria.
