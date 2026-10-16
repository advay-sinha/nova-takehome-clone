# Phase 07: Generalization and retrieval evaluation

Complete required correctness and verification before optional experiments. Read progress and the previous phase's evidence before starting. Preserve the user execution policy.

## Implement

Author at least 10 original YAML cases beyond samples with original mailboxes. Add retrieval source-recall/coverage tests and structured-only versus lexical versus hybrid ablations. Use changed layouts/names, near misses, scan, amendment, feedback and injection cases. Classify failure at extraction/retrieval/interpretation/math/policy layer; fix general cause.

Read references/DIFFERENTIATORS.md and templates/EXPERIMENT.md. Cover its six counterfactual/metamorphic families with fast original-fixture tests; target 10-12 substantive YAML cases. Freeze family-held-out queries before tuning. Compare actual local retrieval separately from mocked/live interpretation. After the baseline, test one pretrained cross-encoder only if a diagnosed ranking miss justifies it and required correctness work is complete. Compare identical candidate pools/final limits; enforce quality, CPU, packaging and no-leakage gates or disable it.

## Human execution gate

Human runs original make eval and full make grade; explain credentials and input scope. Offline tests may use mocks, but never label mock runner results official.

Prepare exact reviewed commands using `/nova-handoff`, then wait for the user's output. Do not treat user approval as an execution result. Continue independent code only if useful.

## Exit evidence

Original cases exist; real caught bug documented; retrieval metrics and end-to-end checks clearly labeled actual/offline/unverified; public practice score is not treated as proof of generalization.

Six transformation families and original-case coverage recorded. An experiment ledger contains actual results or NOT_RUN; optional reranker has an explicit kept/rejected/deferred decision. No tuned-on-holdout or fabricated accuracy claim.

Record actual files/checks, limitations, open handoff IDs and the next task in progress/WORKLOG. Separate IMPLEMENTED, VERIFIED_OFFLINE and VERIFIED_LIVE. Commit a coherent slice when appropriate; publishing remains user-directed.
