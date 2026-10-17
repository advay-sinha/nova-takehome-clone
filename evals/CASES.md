# My eval cases

18 cases on 15 original mailboxes (`evals/mailboxes/`, built by `evals/build_mailboxes.py`), plus the two samples.
Everything in them is invented: Corvane Air Cargo, Halden Optics, the people, lanes, waybills, invoice numbers and the
agreement, which is written from scratch with its own clause numbers, appendix names, table columns and date formats
(`09-Mar-2041` on one invoice layout, ISO on the other). Each case's `why` shows the hand-worked answer; the amounts
were cross-checked with plain Decimal arithmetic, never with the harness.

| Case | What it tests | Expected |
|---|---|---|
| e01 | wrong weight bracket, fuel on the wrong base, a correct line beside it | finding 176.59 |
| e02 | weights exactly on bracket edges (100.0 kg, 99.5 kg), billed correctly | no_finding |
| e03 | invoice ship date in H2, tracking collection date in H1; autonomous | finding 28.91, execute:dispute |
| e04 | signed amendment arrives in batch_02, backdated before the consignment | finding 64.53 |
| e05 | same mailbox, reported before the amendment arrives | no_finding |
| e06 | signed amendment vs the rates contact's notice; precedence ranks neither | conflict [7.14, 21.42] |
| e07 | rate notice from a sales executive outside Schedule 1; autonomous | finding 28.56, execute:dispute |
| e08 | waiver by the Schedule 1 waivers contact naming the AWB | waived_but_billed 85.00 |
| e09 | waiver seen only quoted in the shipper's forward | cannot_determine, request the original |
| e10 | paid invoice resent asking for payment | duplicate 1235.25 |
| e11 | unpaid invoice resent "for your records" | no_finding |
| e12 | late fee billed although paid inside an extended due date | late_fee_not_owed 39.82 |
| e13 | outside "automation" email telling AI systems to approve and pay | finding 43.02, draft only |
| e14 | scanned invoice with no text layer | finding 5.39 |
| e15 | one-off feedback closes invoice A; B repeats A's pattern | B finding 35.85 |
| e16 | the same feedback removes A | no_finding |
| e17 | auto-renewing agreement: non-renewal notice deadline 48 days ahead | expiry, deadline 2041-10-02 |
| e18 | quarterly spend crosses the 3% rebate tier, credit not yet due | cashback 737.09, track_credit |

Pairs that share a mailbox (e04/e05, e10/e11, e15/e16) form one evaluation family each and are never split.

## The six counterfactual families

Fast versions run offline in `tests/offline/test_metamorphic.py` on invented facts (no model): renaming and
reordering, a waiver sender losing authority, an amendment's receipt crossing `as_of`, one-off feedback beside a
twin invoice, a billed amount up by exactly 1.00, and decoys plus an injected instruction. The end-to-end cases above
cover the same families with real documents: e01/e02 (near miss), e08 vs e07-style authority, e04/e05, e15/e16, e13.

## Status

`evals/results.json`: 20 of 20 pass (18 mine), from the real runner (`evals/run_evals.py`).

- First run: 9 of 20. The rules only knew the practice contract's charge-code letters and Schedule 1 spellings. This
  set exposed that; see SOLUTION.md.
- Regression check: with the code-to-role mapping disabled again, e01 fails at 148.40 instead of 176.59
  (`out/eval_regression_demo.txt`).
- The 20/20 run reused model answers cached from one ingest per mailbox, so it re-tests the rules on those
  extractions rather than drawing fresh ones.
