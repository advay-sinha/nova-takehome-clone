# Experiment: supplementary retrieval (lexical / MiniLM hybrid) and optional cross-encoder

Status: PLANNED (retrieval not built); cross-encoder DEFERRED
This file records decisions and NOT_RUN measurements only. No results have been produced.

## Before running

- Hypothesis and diagnosed failure: none yet. The current path extracts every document in full with Claude and
  Python reads every governing record, ledger row and feedback fact by SQL, so no audit step depends on ranked
  passages today. Retrieval would only supply extra clause text (for example an unfamiliar charge label) to a later
  interpretation step that is not built either.
- Scope: offline retrieval over original fixtures first; live end-to-end only through a human handoff.
- Baseline commit/config: NOT_RUN (no retrieval code exists).
- Enhanced commit/config: NOT_RUN.
- Dataset manifest/hash: to be original fixtures from `evals/mailboxes/` plus synthetic test pages; no public answers.
- Family split: to be frozen before tuning, keeping each mailbox and all its variants in one split.
- Query count and relevant source IDs: NOT_PREPARED.
- Same candidate pool/final limit: eligible top 20 -> final 8 in both arms (DIFFERENTIATORS.md).
- Model/runtime/revision/asset hashes/license: NOT_PREPARED (MiniLM encoder and any cross-encoder need a human
  model-preparation handoff; none has been requested).
- Machine/CPU/thread settings and cold/warm protocol: NOT_RUN.
- Human handoff IDs: none.
- Keep rule: keep retrieval only if it fixes at least one held-out miss, adds none, keeps mandatory-record coverage
  at 100% and cross-entity leakage at zero, within the step budget.
- Stop rule: any mandatory-evidence loss, leakage, packaging failure or budget overrun.

## Measurements

| Metric | Baseline | Enhanced | Evidence path / interpretation |
|---|---|---|---|
| Mandatory-record coverage | NOT_RUN | NOT_RUN | Mandatory records come from SQL, not ranking |
| Held-out relevant passages recovered @8 | NOT_RUN | NOT_RUN | |
| Held-out ranking misses fixed / newly introduced | NOT_RUN | NOT_RUN | |
| Cross-entity/future-document leakage | NOT_RUN | NOT_RUN | |
| Correct findings and exact amounts | NOT_RUN | NOT_RUN | Eval run pending (H-005) |
| Wrongly disputed money | NOT_RUN | NOT_RUN | |
| Recheck fields fixed / harmed / unresolved | NOT_RUN | NOT_RUN | No live document has needed a recheck yet |
| Full-report retrieval wall time | NOT_RUN | NOT_RUN | |
| Full-step wall time and timeout headroom | NOT_RUN | NOT_RUN | Practice batch_01 extraction: 399 s of 600 s (H-003), not a retrieval measure |
| Model calls / input-output tokens | NOT_RUN | NOT_RUN | |
| Model bytes / peak memory | NOT_RUN | NOT_RUN | |
| Brier / AUROC if actual outcomes support them | NOT_RUN | NOT_RUN | Confidence is a hand-set heuristic |

## Decision

Final (2026-10-18): retrieval and RAG NOT BUILT for the submission. Practice grade 99.8/100 and my eval set 20/20;
no failure in either came from missing context, and the brief does not ask for retrieval.
Keep / disable / defer: cross-encoder DEFERRED. Its prerequisites are a phase 07 retrieval baseline and a diagnosed
supplementary-ranking miss; neither exists. Retrieval itself is deferred until the eval run (H-005) shows a failure
that missing clause context explains.
Regression evidence: not applicable.
Limitations: no retrieval baseline; the eval set has not been run live yet.
Final feature flag: none (no code).
Reproduction commands: none yet.
Actual run results: none.
Next step: classify H-005 failures by layer; open this experiment only if one is a retrieval/context failure.
