# Phase 03: Structured retrieval and local embeddings

Complete required correctness and verification before optional experiments. Read progress and the previous phase's evidence before starting. Preserve the user execution policy.

## Implement

Implement AuditContext and exhaustive governing/ledger queries. Apply entity, contract and knowledge-date filters before ranking. Preserve conflicting applicable instruments. Build page/parent-aware tokenizer-bounded chunks, local CPU MiniLM encoder, SQLite vectors, lexical search, cosine similarity and rank fusion. Verify semantic recall with original fixtures.

Keep the cross-encoder feature off during this phase. Add an interface only if trivial; no second model dependency or asset download now. Required evidence remains outside ranking. Record baseline recall/coverage on original queries and keep parent fixture families together for later evaluation.

## Human execution gate

Human downloads/exports/quantizes model assets and runs corpus index creation. Prepare script, model revision and manifest. Model bytes/tokenizer/license/checksums must ship for offline evaluator inference.

Prepare exact reviewed commands using `/nova-handoff`, then wait for the user's output. Do not treat user approval as an execution result. Continue independent code only if useful.

## Exit evidence

Structured-required records complete; cross-entity/future documents excluded; offline model asset checks recorded only after user run; embedding/search tests distinguish actual encoder from mock vectors.

Baseline retrieval is independently testable. Any proposed reranker is explicitly optional and unmeasured, with no runtime dependency when disabled.

Record actual files/checks, limitations, open handoff IDs and the next task in progress/WORKLOG. Separate IMPLEMENTED, VERIFIED_OFFLINE and VERIFIED_LIVE. Commit a coherent slice when appropriate; publishing remains user-directed.
