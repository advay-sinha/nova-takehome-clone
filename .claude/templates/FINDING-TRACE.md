# Internal finding trace: implementation checklist

This is a design template, not a produced finding, official schema extension or implemented trace exporter. Implement a typed JSON record under `--state-dir/traces/` and use exact glossary formulas.

| Field group | Required content |
|---|---|
| Identity | Trace schema version; finding key/revision; `as_of`; mode; code/config identity |
| Knowledge | Source occurrence IDs/hashes, fact IDs/versions, received/effective dates, feedback version |
| Coverage | Required-record IDs, found/missing-held-context checks, supplementary chunk IDs |
| Governing term | Selected source/span, rate/waiver/payment term, precedence rule; relevant alternatives and rejection reasons |
| Calculation | Allowlisted formula ID; named typed operands and each operand's fact/span; currency and unit |
| Rounding/FX | Ordered operations, Decimal outputs at each required boundary, FX month/rate/source, final amount |
| Policy | Mode, complete evidence, authority, relevant conflict, recipient, reversible action and aggregate amount/threshold checks |
| Confidence | Feature values, heuristic/unverified label and any actual evaluation version; never cosine as probability |
| Rechecks | Trigger, original observation, proposed correction, source support, accepted/rejected reason, call/time count |
| Replay | Status, compared report item/revision, exact mismatch if any, actual check timestamp |

Validate that source/fact IDs belong to the correct entity and knowledge date. Resolve every quote against canonical stored pages. Keep raw observations separate from normalized values and model-proposed changes.

Replay uses typed operands and an allowlisted formula dispatcher; it never runs strings from the model or documents. Recompute from persisted fact versions, then compare report amount and action gates. A shared calculation function cannot independently establish its own correctness: use manually checked expected results and changed-input tests too.

Include a reviewed clean control in the demo/test evidence without inventing a report finding for it. Omitted clean invoices must not inflate the official report or manipulate escalation statistics.
