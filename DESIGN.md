# Design

Final state, 2026-10-18. Practice grade 99.8/100, my eval set 20/20, exam sheet produced (see SOLUTION.md).

## Fact model

Every email and attachment is an occurrence keyed by the path the grader cites (`batch_01/0003.eml#INV.pdf`), with
its UTC receipt time from the Date header, sender and page text from the grader's own reader (OCR for scans). A
resent identical file stays a separate occurrence. Claude transcribes each document into typed facts: contracts and
terms, rate/fuel/FX/accessorial rows, charge-code aliases, Schedule 1 people, invoices and lines, credit notes,
ledger and tracking rows, waivers, extensions, rate notices, status events. Every fact carries `{doc, page, quote}`.
Python verifies each quote on its page and checks numbers and dates in the same document (date order learned per
sender). Numeric checks compare whole values, not substrings of larger numbers or IDs; invoice arithmetic is
checked, and a misread gets one targeted re-read. Money is a printed string parsed
to Decimal. All state is SQLite under `--state-dir`.

## Conflicts

Each term is chosen per pickup date from the documents in force: signed MSA and amendments first (the latest
effective amendment wins), then rate notices, which count only when their sender is the Schedule 1 rates person.
The MSA's precedence clause, extracted as typed flags, ranks them. When two sources
with authority give different correct amounts and the clause does not rank them (amendment against a Schedule 1
rate notice), the key becomes a conflict with both sources cited and the range of possible overcharges. An
unauthorised sender, quoted text or an unsigned draft never creates a conflict; the stronger source decides.

## Confidence

A hand-set score: 0.95 for a fully evidenced deterministic result (0.85 conflict, 0.8 missing document), lowered for
a pickup date not from tracking, unverified fields, unpriced lines, INR conversion or thin evidence. It stays a
labelled heuristic: on the practice card its Brier score is 0.0084, but AUROC is not measurable with no wrong item,
so it is not calibrated. No similarity score feeds it.

## People in the loop

Supervised mode never executes outbound actions: disputes, claims and document requests are drafts, and
anything of $5,000 or more summed per invoice or cashback key goes to human_review. In autonomous mode an action
executes only when all five unattended checks pass: complete evidence received by as_of with a tracked
pickup date, no conflict on that contract, lane, charge and rate period, under $5,000, reversible, and every term
from level 1–2 with a Schedule 1 recipient. Every affected shipment is checked; freight conflicts include dependent
fuel. Rejected citations block execution and are never reinserted into evidence. Items lacking enough resolvable
citations are omitted with a diagnostic. Conflicts always escalate. Mailbox text is data; instructions in it change nothing.

## Feedback

Feedback files are stored verbatim and each decision becomes a level-2 fact effective from `decided_at`, scoped by
`applies_to` and its valid dates. A standing fact applies only when every filter matches: a confirmed person counts
for that contract and category only, an accepted rate for that contract, lane and date range only. A one-off decision
(close, reject, override, waiver approval) touches only its key, so a sibling invoice keeps its own answer. Changed
items carry `learned_at`. Tests check each decision and that none spreads beyond its scope.

## New documents

Each batch is stored, then planned into extraction units (email bundles, long PDFs in parallel 4-page chunks,
large spreadsheets by column map). Answers are saved as each arrives, and unfinished work is retried by the next
step. Reports recompute everything from stored facts as of the requested date, so a backdated amendment changes
later reports but not earlier ones. A key whose verdict or amount changes gets a new id that cites the old one in
`supersedes`; a new key on an invoice already held at the last report sets `retro`; stale keys disappear because
nothing is carried over.

## Cost

Measured on the whole practice mailbox (163 documents, 82 calls) through Claude Code with `claude-opus-5-5`: 262k
output, 221k cache-write and 735k cache-read tokens. At API prices ($4/$20 per million input/output, $0.20 cache
read, cache writes at 2× input) that is about $7.16, roughly $44 per 1,000 documents, 73% of it output. Wall time
was 643 s, about 66 minutes per 1,000 documents at 4 parallel calls. These are estimates from my runs; the grader's
SDK path may differ. About 46% of output tokens are the model's
thinking rather than the JSON answer, so extracting at a lower effort could roughly halve cost; untested, because
the validated results were all at medium. Locally, a response cache shared across state folders means a rerun never
pays twice for the same request, and a usage-limit reply stops new calls and leaves units pending instead of failed.

## What I'd do next

Measure extraction at lower effort and a cheaper model for short emails, which could halve cost. Add retrieval over
clause text only when an eval case shows a clause my extraction fields miss: I planned embeddings and RAG, but no
failure so far came from missing context, so I left them out. Calibrate confidence once there are wrong answers to
learn from. Least sure about: hidden-set layouts and wording, and margin step-down clauses, which no supplied
contract uses.
