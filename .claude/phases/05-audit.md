# Phase 05: Financial calculations and all findings

Complete required correctness and verification before optional experiments. Read progress and the previous phase's evidence before starting. Preserve the user execution policy.

## Implement

Implement governing-term precedence and pickup-date priority; Decimal financial calculations. Cover overcharge, duplicate, waived_but_billed, late_fee_not_owed, late_fee_risk, rebate/margin_step_down/promised_credit and expiry. Complete SQL aggregation regardless of search top-k. Test original-currency rounding, FX month, aliases, credit overlap and window edges.

Use templates/FINDING-TRACE.md to emit internal typed decision traces with fact versions, governing rule, operands, rounding/FX and gate results. Add allowlisted replay checking; no eval and no official JSON schema extensions. Full recomputation is sufficient. Check results against independent expected amounts, not only the same calculation code.

## Human execution gate

Human executes full practice/exam mailbox runs and any real preprocessing. Offline arithmetic/unit tests and synthetic fixtures are allowed.

Prepare exact reviewed commands using `/nova-handoff`, then wait for the user's output. Do not treat user approval as an execution result. Continue independent code only if useful.

## Exit evidence

Every report class implemented with positive/clean controls. No LLM final math, no web FX, no missing rate silently assumed, no top-k financial aggregation.

One finding replays from persisted evidence to exact reported amount; a mismatched operand/report amount is detected. Trace fidelity is not claimed to prove extraction correctness.

Record actual files/checks, limitations, open handoff IDs and the next task in progress/WORKLOG. Separate IMPLEMENTED, VERIFIED_OFFLINE and VERIFIED_LIVE. Commit a coherent slice when appropriate; publishing remains user-directed.
