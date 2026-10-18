# Unseen-world evaluation (local document reader only)

Four invented customer/carrier worlds, written from scratch to test whether the local document reader and the
deterministic rules generalise beyond the supplied templates. Everything runs with the local reader only: no
Anthropic SDK, no Claude CLI, no API key, no model-response cache.

```
python evals/unseen_worlds/build.py                 # rebuild mailboxes and case files (deterministic)
python evals/unseen_worlds/run_unseen.py --split dev        # or holdout | all; -k <text> filters
make eval-unseen SPLIT=holdout                      # same, through make
```

PowerShell: `.venv\Scripts\python.exe evals\unseen_worlds\run_unseen.py --split dev`.

## Local-reader-only guarantee

- `harness.py --local-reader-only` (before the command) sets `NOVA_LOCAL_READER_ONLY=1` and drops
  `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` and `NOVA_LOCAL_LLM` inside the harness process. A flag is needed because
  the supplied grader passes only `PATH`, `HOME`, `TMPDIR` and `ANTHROPIC_*` to the harness.
- With the variable set, extraction goes straight to the local reader. Constructing the SDK or CLI provider, opening
  the shared cache, or reading or writing the per-state response cache raises `LocalOnlyViolation`.
- `tests/offline/test_local_only.py` makes every model path fail (provider constructors, `subprocess.Popen`, both
  caches, `socket.connect`) and still runs ingest and report. It also runs the flag through a grader-like stripped
  environment with a key and a fake CLI configured, and checks neither was used.
- `run_unseen.py` passes the flag and the variable to every child, strips the model variables, gives every case a fresh
  temporary state, and then fails the case unless its database shows only `local`/`local-reader-1` extraction units
  and an empty response cache.

The same flag runs the supplied checks locally, writing to `out/local_only/` rather than the submission artifacts:
`make grade-local`, `make sheet-local`, `make eval-local`. On a machine without make, run the commands those
targets wrap (see the Makefile).

## How the worlds differ from the supplied ones

| | W1 Fenwick Ridge / Cobalt Harbor | W2 Sarvani / Brennholt | W3 Kittering / Mallowfield | W4 Aldous Stratford / Quennell |
|---|---|---|---|---|
| Currency | USD | INR, Annex F by month name, 4 dp | USD | USD |
| Contract | "Part n", Exhibits A-D | "Section n", Annexes A-F | "Article n", Schedules; contract year from 1 April | "Section n", Annexes 1-3 |
| Weight breaks | "0 to 99.9 kg", "500 kg and above" | "up to 44.9 kg", "45 - 99.9 kg", "100 kg +", two Validity columns | "1000 kg and over" | "Up to 49.9 kgs", "250 kgs and over" |
| Schedule 1 | party code, name, title, email, categories | category first, no party code | "Name (Title, PARTY) - email - authorised for:" (wrapped lines) | "Role: Name, Title \<email\>, PARTY" (email wrapped mid-token) |
| Charges | Linehaul / FAF / SSC / PUP / HAZ | AFR / FSC / XRY / DOC | freight, fuel, screening; cost-plus margin | Airfreight, inside delivery, liftgate, late payment charge |
| Invoice | amount-last with reference column, MM/DD/YYYY | amount-first, dd.mm.yyyy | monthly XLSX statements, 7 columns, per-statement order | description-first, ISO dates, "Invoice #:"; one scan |
| Tracking / ledger | date column first, "Doc No." / "Pay Status" | title rows above header, DD-MM-YYYY hint, "Outstanding (INR)" | ISO timestamps | "Paid?" yes/no, "Payment Date" |
| Other | | credit for records vs paid resend | credit memos ("Q3 2043"), margin step-down, annual credit | ordinals ("1st February 2043"), computed notice deadline, compounding fee, injection |

No case copies or renames a supplied, exam or earlier custom mailbox. Every company, person, number and date is
invented.

## Cases

25 development and 14 holdout cases. Each case runs in both modes, so dev is 50 case-runs and holdout is 28. A case
lists, for each report point, the complete set of items the glossary requires (finding, conflict,
cannot_determine), plus named clean controls. 45 report points carry 36 named controls, and 7 cases end with no
expected finding.

| Family | Cases |
|---|---|
| A rates | w1_d01 edge 100.0/99.9 kg, w1_d02 minimum and fees, w1_d03 fuel on fees, w2_d07 slab edge, w2_d11 tracking date picks the validity, w3_d17 band edges, w4_d25 scan, w1_h01 accessorials, w1_h02 amendment effective-date edge, w2_h04 slab edges and fees, w2_h13 dotted dates |
| B precedence | w1_d04 backdated amendment, w1_d05 authorised and unauthorised notices, w2_d08 no Annex F row, w2_d10 amendment vs notice conflict, w2_d12 missing revised annex, w1_h02, w1_h03, w2_h05 |
| C duplicates | w1_d06 same shipment on two invoices (no self-collision), w2_d09 paid invoice resent / copy for records, w3_d14 credit netting, w3_d18 partial and full credit memos, w3_h09 |
| D waivers | w4_d19 named shipment, w4_d20 unauthorised and quoted-only, w4_d24 one-off feedback, w2_h06 monthly INR, w4_h10 monthly scope |
| E late fees | w4_d21 extension and grace, w4_d22 compounding and the 14-day risk edges, w4_h11 grace edge 5 vs 6 days |
| F cashback | w3_d13 rebate due, w3_d14 tier edge with part credit, w3_d15 margin step-down, w3_d16 annual credit not yet due, w3_h07 just below tier, w3_h08 threshold reached then exceeded |
| G expiry | w4_d23 60/61-day edge, w3_d16, w4_h12 and w3_h14 extension removes the alert |
| H extraction | w1_d01, w2_d07, w2_d11, w3_d13, w3_d17, w2_h04, w4_d25 OCR, w2_h13 |
| I safety and evidence | w1_d05, w2_d08, w2_d10 (both sources cited), w2_d12, w4_d20, w4_d24 injection |
| J state and feedback | w1_d04 retro, w4_d24 decided_at and one-off scope, w1_h03 rate_accepted scope, w2_h05 retro, w4_h12, w3_h14 |

## Expected answers

- Worked from GLOSSARY.md. `oracle.py` is a direct Decimal transcription of the glossary formulas and imports nothing
  from the harness, its rules, readers or the grader. `tests/offline/test_unseen_oracle.py` checks it against
  hand-worked numbers.
- Each case states its decisive source, dates, authority and arithmetic in `why`. Asserts inside the builders pin
  edge facts, for example that w2_d07 really separates single from per-line INR conversion, and that the w4 notice
  deadline is 60 days before expiry.
- `build.py` reads every fixture back through the grader's text layer and checks that each expected key and each
  cited evidence document exists. No answer was copied from a harness run. Only the grader's matching helpers (keys,
  amounts within USD 0.01) and its schema/citation validators are reused in scoring.
- Where the brief left a choice I recorded it: a cannot_determine document request executes in autonomous mode, as
  in the supplied practice key; a margin over-billing is claimable once its quarter closes.

## Results (local reader only)

| Run | Code | Case-runs passed | F1 | Amounts exact | Notes |
|---|---|---|---|---|---|
| dev | final | 50 / 50 | 1.00 | 36 / 36 | 48/48 controls read and kept; 8/8 conflict/cannot_determine right |
| holdout run 1 (blind) | frozen `6b96bd63...` | **20 / 24** (10 of 12 cases) | 0.88 | 20 / 20 | w2_h05 and w4_h12 failed in both modes |
| holdout run 2 | after fixes `a4f3420f...` | 28 / 28 | 1.00 | 24 / 24 | adds fresh w2_h13, w3_h14 (first run, passed) |
| holdout run 3 | final `45c1c80d...` | 28 / 28 | 1.00 | 24 / 24 | confirmation after the w4_d25 OCR fix |

All runs had 0 citation errors, 0 schema errors, no execute action in supervised mode and no unsafe execute in
autonomous mode. Runtimes average about 3.5 to 5.6 s per case-run per world, and the dev suite takes about 40 s wall
time with 6 workers. Files are in `results/`, with dev and the three holdout runs kept separately.

Holdout run 1 is the only blind measurement. Its two failures were real general defects:

- **w2_h05.** On an INR invoice whose numeric dates all have a day of 12 or less (10.06.2043), the day/month order
  stayed unknown, so the invoice month and Annex F rate could not be chosen. The reader now reads dotted numeric
  dates day-first when nothing else decides; slashed dates are still never guessed.
- **w4_h12.** A signed amendment that moves the term end was not read, so the expiry alert stayed. Expiry also
  replaced the agreement's whole term block with the amendment's, losing auto-renewal. Both are fixed: the amendment
  sentence is read, and an amendment overlays only what it states.

Each fix has a regression test (`HoldoutFoundTests`) and a mutation. w2_h05 and w4_h12 are now fix-informed and no
longer blind. w2_h13 and w3_h14 were written after the fixes, in other worlds and wording, and passed on their first
run. The w4_d25 scan was added afterwards as a development case. It exposed OCR gluing a waybill to its lane, which
was fixed with a test before holdout run 3.

## Reader defects this suite found

Each defect is pinned in `tests/offline/test_reader_generalisation.py`, or in a rule test where noted:

- weight-break wording;
- agreements titled other ways;
- Exhibit/Part/Section/Article headings;
- clauses cut by a page break;
- named pricing windows, including a regression where a window was read twice;
- fuel and FX months written as names;
- ordinal and dashed dates;
- a header's own date-format hint;
- five Schedule 1 layouts, including wrapped entries;
- spreadsheet headers and statement columns by meaning;
- statements of account;
- amount-first detection;
- "p% of/on base" descriptions;
- credit memos and written quarters;
- grace written as "within n days";
- late payment charges that name their invoice;
- ledger status wording, including yes/no;
- charge roles from aliases;
- retro after an empty report (`test_report_feedback`);
- dotted dates and term extensions (holdout);
- OCR-glued cells (w4_d25).

## Metamorphic tests

`tests/offline/test_unseen_metamorphic.py` runs nine behaviour-preserving variants end to end. Each is compared with
the oracle's answer, not only with the base run:

- reordered invoice rows;
- irrelevant email text and a footer;
- tracking columns renamed with aliases and reordered;
- numbers without thousands separators;
- a clause split across a page break;
- an unrelated clean invoice added;
- an injected instruction;
- tracking moved to a later batch that is still received by as_of;
- a one-off waiver naming a different shipment, which moves the finding and nothing else.

Batch reordering is used only where receipt by as_of is all that matters. Reorders that change supersedes/retro
history are not treated as neutral.

## Mutations

`tools/check_mutations.py` keeps the original 8 mutations and adds 12, each paired with a guard that passes on the
real code. 20/20 are detected.

## Known gaps

- The worlds and the fixes come from the same author in one session, so the suite tests generalisation beyond the
  supplied templates, not independence from my own assumptions. Only holdout run 1 was blind.
- The suite has one conflict case and one scan, and no INR late-fee or INR rebate case.
- Feedback coverage is close, rate_accepted and one_off_approval. `confirm`, `reject`, `override_amount` and
  `resolve_conflict` are only covered by the existing offline tests.
- Confidence calibration is not measured. Every scored item here is right, so AUROC cannot be computed, and the
  heuristic confidence was left unchanged.
- The make targets were not executed on the development host, which has no make. The Python commands they wrap
  were run directly.
