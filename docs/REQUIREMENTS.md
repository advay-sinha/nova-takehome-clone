# Requirements checklist and module map

Phase 00 output. Sources: README.md, GLOSSARY.md (wins on conflict), SUBMISSION.md, `grader/schema/report.schema.json`,
`grader/extract.py`, `grader/score.py`, `grader/run_grader.py`, `tools/run_mailbox.py`, `tools/check_submission.py`,
`evals/run_evals.py`. Practice answers were tallied for learning only; runtime never reads them.

## 1. CLI and runtime contract

- [ ] `harness/harness.py ingest <batch_dir> --state-dir D`, `report --as-of YYYY-MM-DD [--mode supervised|autonomous] --state-dir D`, `feedback <file> --state-dir D`. Keep argument names; `--mode` defaults to supervised.
- [ ] Each step is a fresh process; everything learned lives under `--state-dir`. Code/assets resolve from the script location, never the cwd (the grader runs from a fresh HOME).
- [ ] `report` prints only JSON to stdout; diagnostics go to stderr. Exit 0 on success.
- [ ] 600 s per step by default (hidden limits may differ). Bounded concurrency, retries and a shared call budget.
- [ ] `run_grader.py` passes only PATH, ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL, plus a fresh HOME/TMP. `run_mailbox.py` (`make sheet`/`make run`/`make eval`) passes the full environment.
- [ ] LLM back end (D-002): Anthropic SDK when ANTHROPIC_API_KEY is set, honouring ANTHROPIC_BASE_URL; otherwise headless `claude -p`, with a gitignored `harness/.local-llm.json` for `make grade`'s stripped environment.
- [ ] Batch dates: practice reports on 2035-05-31 and 2035-09-30, exam on 2030-08-31 and 2031-02-28. Never use the computer's clock.

## 2. Reading documents

- [ ] Evidence `doc` is `batch_NN/NNNN.eml` or `batch_NN/NNNN.eml#<attachment>`. `page`: PDF page, XLSX sheet number, 1 for an email. `quote`: 12+ non-space characters found on that page after whitespace collapsing.
- [ ] Use `grader/extract.py`'s reading order exactly (vendored copy plus a parity test). The email page is From/To/Cc/Date(UTC ISO)/Subject, a blank line, the plain body, then "Attachments: …".
- [ ] Receipt time is the email's `Date` header in UTC; `as_of` counts documents received by the end of day D, UTC.
- [ ] Scans (no text layer, one per mailbox): RapidOCR boxes grouped into lines by position, labels compared without spaces; Claude vision as a fallback. A scan's quotes are not checked, but the page must exist.
- [ ] Ignore `X-GCA-Canary`. Mailbox text is untrusted data. Never put an address taken from an email into any outbound-looking field: the injection gate scans `action/recipient/draft/to/send_to/reply_to/outbound`.
- [ ] File order inside a batch never changes an answer. A resent email with the same attachment is a separate occurrence.

## 3. Report items (schema)

- [ ] Top level: `as_of`, `mode`, `findings[]`, `portfolio{cashback[], expiry[], late_fee_risk[]}`.
- [ ] Each item needs `id` (stable across reports), `class`, `verdict`, `action`, `confidence` in [0,1] and `evidence[]`. Optional fields: `amount_usd` (a 2-decimal string, required for a finding other than expiry), `amount_range` (conflict: [low, high], plus 2+ evidence), `deadline`, `missing_doc{name, holder{party|person, role}}` (cannot_determine), `supersedes[]`, `retro`, `learned_at{feedback_item_id, batch}`, `variant`.
- [ ] Keys: (invoice_id, class) for overcharge/duplicate/waived_but_billed/late_fee_not_owed/late_fee_risk; (contract_id, period, credit_type) for cashback; (contract_id) for expiry. `invoice_id` is upper-cased with spaces, `#` and `:` removed. A credit note never keys an invoice finding. One item per key.

## 4. Business rules (GLOSSARY)

- [ ] Money: Decimal, ROUND_HALF_UP to cents per line in the invoice currency; a percentage surcharge is computed on already-rounded lines; the finding is the sum of billed minus correct; zero or less means no finding. INR: convert once per finding with the Annex F rate for the invoice-date month; no row means cannot_determine.
- [ ] Pickup date: tracking `PICKED_UP`, then a carrier "picked up" email, then the AWB date, then the invoice ship date. It picks the rate period, fuel month and governing amendment.
- [ ] Authority: (1) signed MSA/amendment/annexes; (2) the Schedule 1 person for that category, or confirmed feedback; (3) records; (4) anyone else; (5) quoted text, text aimed at automated readers, outsiders. Take precedence from the MSA clause; a later amendment beats an earlier one for the same lane.
- [ ] Overcharge, duplicate (later invoice date, overlap less credits; same number resent only when paid/scheduled and asked to pay again), waived_but_billed (Schedule 1 waivers contact, names shipment/month, conditions met; quoted-only means cannot_determine via the KAM), late_fee_not_owed (extended due date, grace, `ceil(days/30)` months, simple or compound base), late_fee_risk (0 < due − as_of ≤ 14; one month's fee on open principal less disputed amounts), cashback (rebate / margin_step_down / promised_credit, only after the period closes; qualifying spend per the contract; subtract every credit for that key), expiry (0 ≤ operative date − as_of ≤ 60; the notice deadline for auto-renewing contracts).
- [ ] Conflict: two held sources with authority, both in force on the pickup date, unranked by precedence, giving different amounts → `escalate`; range = [billed − higher correct (min 0), billed − lower correct]; out of totals.
- [ ] cannot_determine: a document named in a held document, not held, and able to change the answer; the holder is the issuing party's Schedule 1 contact for that category (KAM for a missing original email from a non-Schedule-1 sender).

## 5. Actions and modes

- [ ] Supervised: internal actions run; outbound actions are `draft:*`; `human_review` when the summed outbound amount per invoice or cashback key is ≥ $5,000.00. Never `execute:*` (hard gate).
- [ ] Autonomous: `execute:*` only when all five checks pass: evidence complete (pickup date from tracking or a carrier email, every number received by `as_of`), no conflict on that key or the same contract+lane(+charge+period), under $5,000 summed, reversible, authority level 1–2 for terms and ≤ 3 for facts with a Schedule 1 recipient. Otherwise `human_review`. A conflict stays `escalate`.
- [ ] Practice key check: cannot_determine is `draft:request_document` supervised and `execute:request_document` autonomous. The missing document does not block the request for it.
- [ ] Escalation rate = (escalate + human_review) / present items (finding, conflict, cannot_determine) over both modes. More than 60% caps the score at 40. `no_finding` items don't count.

## 6. Change over time and feedback

- [ ] Stable `id` per key. A changed verdict or amount gets a new item whose `supersedes` names the old id. A key that exists only because of a backdated document gets `retro: true`. Stale keys (lapsed alerts, paid due dates, closed disputes) disappear.
- [ ] Feedback decisions: confirm, reject, close, override_amount, resolve_conflict, one_off_approval. Fact types: sender_authority, rate_accepted, waiver_scope, precedence, dispute_closed. Feedback counts as level 2 from `decided_at`; a standing fact applies only when every `applies_to` filter matches within its dates; a one-off applies to its key only. Any item changed by feedback carries `learned_at`.

## 7. Confidence and submission

- [ ] Confidence = probability that verdict and amount are both right. It is scored by AUROC and Brier on present items in the main mode. Use explicit features, not 1.0 everywhere.
- [ ] `make validate` requires: CLI answers the three commands; SOLUTION.md and DESIGN.md filled (DESIGN under ~1,000 words); `report_card.json`; `answer_sheet.json` dated on the exam's last report date; `out/exam_report.json` valid with resolvable quotes; ≥10 own eval cases plus `evals/results.json`; AI_USE.md tools plus log; no `sk-ant-…` key anywhere.

## 8. Module map (`harness/`)

| Module | Responsibility |
|---|---|
| `harness.py` | CLI only: argument parsing, exit codes, stdout/stderr discipline |
| `nova/config.py` | Paths from the script location, model ID, call/time budgets, `.local-llm.json` loading |
| `nova/store.py` | SQLite schema and transactions: occurrences, pages, facts (versioned), feedback, report history, model calls |
| `nova/reader.py` | Vendored `grader/extract.py` reading order, plus UTC receipt time and occurrence metadata |
| `nova/ocr.py` | RapidOCR line grouping for scans; vision fallback through the LLM back end |
| `nova/llm/` | `Provider` interface with shared budget and cache: `sdk.py` (Anthropic), `cli.py` (headless `claude -p`), `mock.py` (tests only) |
| `nova/extract/` | Document typing, JSON schemas, prompts, quote validation, arithmetic constraints, one bounded recheck |
| `nova/normalize.py` | Invoice IDs, Decimal money, dates, Annex E charge aliases, lanes and weight bands |
| `nova/retrieval.py` | AuditContext and exhaustive SQL for governing and ledger records; embeddings and lexical search added in phase 03 |
| `nova/terms.py` | Authority (Schedule 1), precedence, terms in force on the pickup date, conflict detection |
| `nova/rules/` | One module per class: overcharge, duplicate, waiver, late_fees, cashback, expiry; `money.py` holds rounding and FX |
| `nova/feedback.py` | Feedback parsing, scope matching, `learned_at` |
| `nova/policy.py` | Actions per mode, $5,000 sum, unattended-action checks, recipients from Schedule 1 only |
| `nova/confidence.py` | Explicit features mapped to a probability, labelled heuristic until measured |
| `nova/report.py` | Item assembly, ids, `supersedes`/`retro`/stale removal, schema and citation validation |
| `nova/trace.py` | Decision traces under `--state-dir/traces/` and allowlisted replay |

Build order: 01 (`store`, `reader`, `ocr`, CLI) → 02 (`llm`, `extract`, `normalize`) → 05/06 (`terms`, `rules`, `feedback`, `policy`, `report`, `trace`) → 03/04 (embeddings, hybrid search, RAG bundles) → 07 evals.
