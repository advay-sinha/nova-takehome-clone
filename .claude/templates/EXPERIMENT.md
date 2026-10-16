# Experiment: <descriptive name>

Status: PLANNED | BLOCKED_HUMAN | RUN | REJECTED | KEPT
This template contains no experiment results. Replace placeholders only with actual evidence.

## Before running

- Hypothesis and diagnosed failure: <specific query/field and source-backed expected result>
- Scope: <offline retrieval / mocked integration / live end-to-end>
- Baseline commit/config: <actual identifiers>
- Enhanced commit/config: <actual identifiers>
- Dataset manifest/hash: <original fixtures; no runtime public-answer lookup>
- Family split: <tuning families and untouched holdout families; keep all variants together>
- Query count and relevant source IDs: <independently reviewed>
- Same candidate pool/final limit: <for reranking, eligible top 20 -> final 8 in both arms>
- Model/runtime/revision/asset hashes/license: <actual values, or NOT_PREPARED>
- Machine/CPU/thread settings and cold/warm protocol: <same for both arms>
- Human handoff IDs: <model preparation/corpus/live runs; no secrets>
- Keep rule: <declare before results; follow DIFFERENTIATORS.md>
- Stop rule: <quality, regression, packaging, CPU or mandatory correctness failure>

## Measurements

Use NOT_RUN for missing measurements; do not replace it with zero. Include numerator/denominator for tiny datasets. Separate held-out evidence from tuning and mock results.

| Metric | Baseline | Enhanced | Evidence path / interpretation |
|---|---|---|---|
| Mandatory-record coverage | NOT_RUN | NOT_RUN | Must remain 100% |
| Held-out relevant passages recovered @8 | NOT_RUN | NOT_RUN | Hits / total relevant |
| Held-out ranking misses fixed / newly introduced | NOT_RUN | NOT_RUN | Pairwise query IDs |
| Cross-entity/future-document leakage | NOT_RUN | NOT_RUN | Must remain zero |
| Correct findings and exact amounts | NOT_RUN | NOT_RUN | Real or mock provider clearly labeled |
| Wrongly disputed money | NOT_RUN | NOT_RUN | Required for financial benefit claim |
| Recheck fields fixed / harmed / unresolved | NOT_RUN | NOT_RUN | Verified against original sources |
| Full-report retrieval wall time | NOT_RUN | NOT_RUN | Same CPU/corpus; include added seconds |
| Full-step wall time and timeout headroom | NOT_RUN | NOT_RUN | Do not infer live timings from mocks |
| Model calls / input-output tokens | NOT_RUN | NOT_RUN | Actual or explicitly estimated |
| Model bytes / peak memory | NOT_RUN | NOT_RUN | Runtime packaging cost |
| Brier / AUROC if actual outcomes support them | NOT_RUN | NOT_RUN | Correct = verdict AND amount |

## Decision

Keep / disable / defer: <decision and evidence>
Regression evidence: <mandatory evidence, policy and amounts unchanged where expected>
Limitations: <small sample, missing live access, hardware mismatch, etc.>
Final feature flag: <path/value>
Reproduction commands: <only existing reviewed entry points; human runs gated operations>
Actual run results: <artifact paths and received output; no fabricated logs>
Next step: <final audit or necessary general fix>
