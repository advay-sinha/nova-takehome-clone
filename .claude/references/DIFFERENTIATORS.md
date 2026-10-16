# Differentiators

Read for phases 02, 04, 05 and 07, or before adding any ML component. The detailed rationale is in `docs/NOVA-SOLUTION-PLAN.md` section 6B. These are planned behaviors, not implemented features or measured gains.

## Priority and limits

1. Finish every required class, complete evidence, exact money, feedback and action policy.
2. Build field constraints and calculation traces alongside that implementation.
3. Extend original evaluations with evidence-changing and invariant-preserving transformations.
4. Consider one pretrained reranker only after a diagnosed ranking failure and phase 07 baseline results.

Complete required correctness and verification before optional experiments. Skip the reranker if required behavior is still incomplete or there is no reproducible failure. Do not reduce mandatory evidence, omit genuine findings or invent results.

## Constraint-assisted extraction

- Keep raw/normalized fields and their exact source spans. Check typed IDs/dates/currencies and document arithmetic only where the invoice provides the relevant operands.
- Separate document-internal inconsistency from a legitimate contract discrepancy. Account for explicit tax, discount, credit and rounding lines. Never force the billed amount to equal the expected contractual amount.
- Check decisive scan values and cross-source identifiers. Disagreement is a signal to inspect evidence, not permission to guess a replacement.
- Distinguish missing held context, extraction uncertainty, authority conflict and a real financial discrepancy. Broaden retrieval for held evidence before a recheck.
- If a critical field remains ambiguous, use one targeted request per document/cache version, batching related fields. Give the evaluator model the original page/crop and field references without a preferred answer. Require observed values and source support.
- Preserve the initial extraction and accepted correction. Same-model agreement is not independent evidence, calibrated confidence or authorization.
- Share a configurable global time/call budget with primary extraction and RAG repairs; reserve serialization time. Cache by source/schema/prompt/model versions. Do not create unbounded repair loops.
- All items receive mandatory deterministic checks. Optional rechecks may be prioritized by uncertainty and possible impact; low-ranked items cannot lose mandatory evidence or disappear from the report.
- If still unresolved, report the technical limitation accurately. Never fabricate a missing document, silently mark clean, or escalate every item indiscriminately. Follow the glossary/schema for genuine business uncertainty; an incomplete technical run must not masquerade as a complete audit.

Test a wrong OCR digit, a legitimate tax adjustment and a real overcharge separately. Offline mocks test control flow; actual accuracy of model rechecks stays unverified until a human-run live test.

## Decision traces and replay

Use the field checklist in `templates/FINDING-TRACE.md`. Each internal trace records:

- Finding key/revision, report `as_of`/mode and source/fact versions.
- Required-record manifest; chosen governing term and applicable precedence rule; relevant rejected alternatives and concrete reasons.
- Formula ID, typed Decimal/date operands with source references, currency, line/finding rounding, FX month/rate and computed amount.
- Exact citation references and results of completeness, authority, conflict, reversibility, mode, recipient and aggregate-threshold gates.
- Confidence features with a heuristic/unverified label, recheck history and replay result.

Write only under `--state-dir/traces/`, keeping the official report schema/stdout unchanged. Use an allowlisted formula dispatcher, never `eval` or model-generated executable code. Replay against the persisted fact versions and compare result with the emitted item. Reusing calculation code verifies consistency; independently computed fixture expectations verify intended behavior. Valid citations alone do not prove correct OCR or authority.

Represent provenance with lists of fact/source IDs; full recomputation is sufficient for the small corpus. Do not add a graph database or incremental invalidation framework. Demo an amendment changing one result and scoped feedback leaving a sibling unchanged. Show evidence and calculations, not private model reasoning.

## Counterfactual and metamorphic cases

Use original fixtures and independently specify expected changes. Add these six families to fast offline tests, alongside at least 10 distinct original YAML submission cases:

| Change | Expected relation |
|---|---|
| Consistent renamed entities/IDs, reordered files/columns | Same semantic money/decisions, with correctly renamed references |
| Authorized waiver sender becomes unauthorized | Waiver effect removed; unrelated items unchanged |
| Amendment receipt crosses `as_of`; effective date unchanged | Historical knowledge boundary respected; later term applies when appropriate |
| One-off feedback for A with similar B present | Only covered A changes |
| Isolated non-FX, uncapped billed overcharge increases by 1.00 | Dispute increases exactly 1.00; governing rate/authority unchanged |
| Future/other-entity decoy or instruction to ignore controls | Applicable evidence, amounts and actions unchanged |

Do not assume linear amount changes across caps, weight bands, credits, FX or thresholds. Put parent fixture and all variants in the same family-based train/tune/holdout split. No tuning on exam output or public answer IDs. API-free component tests and full end-to-end tests have different evidentiary strength; label them.

## Optional pretrained cross-encoder experiment

Prerequisites: core path complete, phase 07 baseline recorded, a specific supplementary-ranking miss and a concrete human model-preparation handoff. Keep the feature off unless its gates pass; no new mandatory dependency solely to make the architecture look sophisticated.

Candidate: `cross-encoder/ms-marco-MiniLM-L6-v2`. It scores paired query/passage inputs, not independent mean-pooled vectors. It is pretrained for passage ranking, not finance correctness. Use a local CPU path and only a compatible export/runtime already understood. Published GPU throughput is not evaluator CPU performance.

1. Predeclare the failure, split, quality/regression/CPU/packaging gates and stop rule in `templates/EXPERIMENT.md`.
2. Prepare about 20 original queries over at least six document/contract families; freeze a family-held-out subset before tuning. Keep all variants of one family together.
3. Compare hybrid versus hybrid+cross-encoder on the same eligible top-20 candidate pool and final top-8 budget. Mandatory SQL evidence bypasses ranking. Expand selected parent clauses and preserve scope/date filters.
4. Human downloads/exports model/tokenizer assets, verifies revision/hash/license and executes any corpus/live run. Local synthetic inference using already prepared assets may be tested offline; label mock scores separately.
5. Record raw recall hits/denominators, mandatory coverage, scope leakage, final finding/amount errors when available, CPU/wall time, call count and asset size.
6. Keep only if at least one untouched-holdout miss is fixed, none is introduced, mandatory coverage is 100%, scope leakage is zero and added wall time is at most 30 seconds per complete report retrieval pass on the same CPU/corpus with step-budget headroom. This time allowance is an engineering choice. A small sample is descriptive, not proof of broad superiority.
7. Disable/remove if inconclusive, packaging fails or gates fail. Freeze before final official runs. Record unavailable live checks as NOT_RUN; never call mock extraction an end-to-end win.

Only one candidate model is in scope. Do not search many models against the holdout. A rejected experiment with clear measurements is a valid design outcome.

## Training and confidence

No training/fine-tuning, learned confidence model, MLflow server or agent debate is planned. Keep an explicit heuristic confidence and report Brier/AUROC only with actual labeled outcomes. Correctness means both verdict and amount. A lower Brier alone does not establish calibration; AUROC needs both outcome classes.

If future evidence justifies training, first explain the failure, representative labels, grouped splits, evaluation, resources and deployment. User chooses the new scope; Claude prepares runnable scripts; human executes training. Never train on public answers, exam labels, mock confidence outputs or near-duplicate split leakage.

## Interview evidence

Prepare a three-minute opening using actual artifacts: one amount's trace, one controlled evidence change, one clean near-miss and one honest retrieval comparison. Explain the first incorrect field when a case fails. Do not build a dashboard for this walkthrough.
