# Phase 02: Typed extraction and source provenance

Complete required correctness and verification before optional experiments. Read progress and the previous phase's evidence before starting. Preserve the user execution policy.

## Implement

Define schemas for contracts, annexes, contacts, amendments, invoices/lines, credits, tracking, ledgers and email facts. Implement evaluator Anthropic provider and explicit fixture provider. Validate types, dates, IDs, exact source spans and missing fields. Cache by content/schema/prompt/model versions without losing occurrence dates.

Read references/DIFFERENTIATORS.md. Add document-internal arithmetic/type/identity constraints with explicit tax/discount handling. Distinguish contract discrepancies from extraction errors. Implement one targeted critical-field recheck per document/version inside a shared time/call budget; preserve original and corrected observations with sources. Test an OCR digit error, a valid tax adjustment and a genuine overcharge separately.

## Human execution gate

Live provider smoke test and full-corpus extraction belong to human. First create small bounded smoke-test script; give output checks without credentials. No key means live accuracy remains unverified.

Prepare exact reviewed commands using `/nova-handoff`, then wait for the user's output. Do not treat user approval as an execution result. Continue independent code only if useful.

## Exit evidence

Representative original fixtures parse through mocks with validated schema; governing tables/contacts are complete; source spans retained; no layout/customer hardcodes.

Constraint tests distinguish extraction inconsistency from business discrepancy. Recheck control flow is bounded; same-model agreement is never authority or calibrated confidence. Live correction quality stays unverified until a human-run test.

Record actual files/checks, limitations, open handoff IDs and the next task in progress/WORKLOG. Separate IMPLEMENTED, VERIFIED_OFFLINE and VERIFIED_LIVE. Commit a coherent slice when appropriate; publishing remains user-directed.
