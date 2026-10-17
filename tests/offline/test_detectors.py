"""Duplicate, waiver, late-fee, cashback and expiry rules on invented data; amounts worked by hand in comments."""
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from factkit import CID, KAM, WAIVERS, Kit  # noqa: E402
from nova.rules import cashback, duplicate, expiry, late_fees, waiver  # noqa: E402

D = Decimal


def keyed(cands):
    return {(c.cls, c.key.get("invoice_id") or c.key.get("contract_id"), c.key.get("period")): c for c in cands}


class Base(unittest.TestCase):
    def setUp(self):
        self.k = Kit()
        self.k.contract()

    def tearDown(self):
        self.k.close()

    def ledger(self, inv, inv_date, due, amount, status, paid=None, received="2040-06-01", n=800):
        doc = self.k.doc(f"batch_01/{n:04d}.eml#ap-register.xlsx", received, "ap@ostravabio.example", "table")
        self.k.fact("ledger_rows", doc, {"invoice_id": inv, "invoice_date": inv_date, "due_date": due,
                                         "amount": amount, "currency": "USD", "status": status, "paid_date": paid},
                    quote=f"{inv} | {inv_date} | due {due} | USD {amount} | {status} | {paid or '-'}")


class DuplicateTests(Base):
    def resend(self, kind, n=31, received="2040-05-10"):
        line = [{"awb": "PW10", "label": "Delivery fee", "qty": "1", "rate": "100.00", "amount": "100.00"}]
        self.k.invoice(30, "2040-04-01", line, invoice_id="PW-OB-2040-0030")
        doc, inv = self.k.invoice(n, received, line, invoice_id="PW-OB-2040-0030")
        self.k.fact("payment_requests", doc.split("#")[0], {"invoice_id": inv, "kind": kind},
                    quote=f"Please process payment for {inv} now ({kind}).")
        return inv

    def test_paid_invoice_asked_again(self):
        inv = self.resend("asks_payment")
        self.ledger(inv, "2040-04-01", "2040-05-01", "100.00", "paid", "2040-04-20")
        got = keyed(duplicate.detect(self.k.world("2040-06-30")))
        self.assertEqual(got[("duplicate", inv, None)].amount_usd, D("100.00"))

    def test_copy_or_unpaid_is_fine(self):
        inv = self.resend("copy")
        self.ledger(inv, "2040-04-01", "2040-05-01", "100.00", "paid", "2040-04-20")
        self.assertEqual(duplicate.detect(self.k.world("2040-06-30")), [])

    def test_unpaid_resend_is_fine(self):
        inv = self.resend("asks_payment")
        self.ledger(inv, "2040-04-01", "2040-05-01", "100.00", "open")
        self.assertEqual(duplicate.detect(self.k.world("2040-06-30")), [])

    def test_reminder_to_pay_a_paid_invoice(self):
        # found by eval e10: "Second reminder ... please arrange payment" was read as kind 'reminder'
        inv = self.resend("reminder")
        self.ledger(inv, "2040-04-01", "2040-05-01", "100.00", "paid", "2040-04-20")
        self.assertEqual(keyed(duplicate.detect(self.k.world("2040-06-30")))[("duplicate", inv, None)].amount_usd,
                         D("100.00"))

    def test_reminder_or_for_records_otherwise_fine(self):
        inv = self.resend("reminder")
        self.ledger(inv, "2040-04-01", "2040-05-01", "100.00", "open")
        self.assertEqual(duplicate.detect(self.k.world("2040-06-30")), [])
        k2 = self.k
        self.tearDown()
        self.setUp()
        inv = self.resend("for_records")
        self.ledger(inv, "2040-04-01", "2040-05-01", "100.00", "paid", "2040-04-20")
        self.assertEqual(duplicate.detect(self.k.world("2040-06-30")), [])
        self.assertIsNot(k2, self.k)

    def rebill(self, awb2="PW20", label2="Screening fee", credit=None):
        sec = lambda awb, label: {"awb": awb, "label": label, "qty": "118", "rate": "0.15", "amount": "17.70"}
        self.k.invoice(40, "2040-03-01", [sec("PW20", "Security surcharge")])
        doc, later = self.k.invoice(41, "2040-07-01", [sec(awb2, label2)])
        if credit:
            cn = self.k.doc("batch_01/0042.eml#CN.pdf", "2040-07-05", kind="credit_note")
            self.k.fact("credit_notes", cn, {"credit_id": "CN-1", "credit_date": "2040-07-05", "contract_id": CID,
                                             "credit_type": "invoice_correction", "period": None,
                                             "refers_to_invoice": later, "refers_to_awb": None, "amount": credit})
        return later

    def test_same_charge_billed_months_later_under_an_alias(self):
        later = self.rebill()
        got = keyed(duplicate.detect(self.k.world("2040-08-01")))
        self.assertEqual(got[("duplicate", later, None)].amount_usd, D("17.70"))
        self.assertEqual(len(got), 1)                               # the earlier invoice is never the finding

    def test_other_shipment_or_full_credit_is_fine(self):
        self.rebill(awb2="PW21")
        self.assertEqual(duplicate.detect(self.k.world("2040-08-01")), [])

    def test_credit_reduces_or_cancels(self):
        later = self.rebill(credit="7.70")
        self.assertEqual(keyed(duplicate.detect(self.k.world("2040-08-01")))[("duplicate", later, None)].amount_usd,
                         D("10.00"))


class FullCreditTests(DuplicateTests):
    def test_full_credit_then_rebill_is_fine(self):
        self.rebill(credit="17.70")
        self.assertEqual(duplicate.detect(self.k.world("2040-08-01")), [])


class WaiverTests(Base):
    def setup_case(self, sender, awb="PW50", quoted=False, condition=None):
        self.k.picked_up("PW50", "2040-03-02")
        doc = self.k.doc("batch_01/0050.eml", "2040-03-05", sender, "waiver")
        self.k.fact("waivers", doc, {"charge": "Delivery fee", "awbs": [awb], "months": [], "invoice_ids": [],
                                     "condition": condition, "is_quoted_or_forwarded": quoted,
                                     "quoted_author": "Ines Duarte" if quoted else None},
                    quote=f"we waive the Delivery fee on AWB {awb}")
        return self.k.invoice(51, "2040-03-20", [{"awb": "PW50", "label": "Delivery fee", "qty": "1",
                                                  "rate": "100.00", "amount": "100.00"}])[1]

    def test_authorised_waiver(self):
        inv = self.setup_case(WAIVERS)
        c = keyed(waiver.detect(self.k.world("2040-04-30")))[("waived_but_billed", inv, None)]
        self.assertEqual((c.verdict, c.amount_usd), ("finding", D("100.00")))

    def test_counterfactual_unauthorised_sender(self):
        self.setup_case(KAM)                    # same text, sender without waiver authority: owed
        self.assertEqual(waiver.detect(self.k.world("2040-04-30")), [])

    def test_waiver_names_another_shipment(self):
        self.setup_case(WAIVERS, awb="PW99")
        self.assertEqual(waiver.detect(self.k.world("2040-04-30")), [])

    def test_quoted_only_asks_for_the_original(self):
        inv = self.setup_case(KAM, quoted=True)
        c = keyed(waiver.detect(self.k.world("2040-04-30")))[("waived_but_billed", inv, None)]
        self.assertEqual((c.verdict, c.outbound), ("cannot_determine", "request_document"))
        self.assertEqual(c.missing_doc["holder"]["person"], "Ines Duarte")   # its author is the waivers contact

    def test_conditional_waiver_is_not_assumed(self):
        self.setup_case(WAIVERS, condition="if paid by 2040-03-31")
        self.assertEqual(waiver.detect(self.k.world("2040-04-30")), [])

    def test_billing_note_is_not_a_condition(self):
        # found on live practice batch_02: the model put "you can short-pay that line" in `condition`
        inv = self.setup_case(WAIVERS, condition="Where this is on an invoice already, just short-pay the line.")
        c = keyed(waiver.detect(self.k.world("2040-04-30")))[("waived_but_billed", inv, None)]
        self.assertEqual((c.verdict, c.amount_usd), ("finding", D("100.00")))

    def test_real_condition_wording(self):
        for text in ("provided the March invoices are settled by 15 April", "subject to volumes staying above 2 t",
                     "only if the shipment is rebooked", "If you have paid it already, a credit note follows, "
                     "provided you send the remittance", "if paid by 2040-03-31"):
            self.assertTrue(waiver.real_condition(text), text)
        for text in (None, "", "No credit note will be issued; leave that charge unpaid.",
                     "If it was invoiced already you may short pay it.", "Please deduct it from your next payment."):
            self.assertFalse(waiver.real_condition(text), text)


class LateFeeTests(Base):
    def fee_invoice(self, target, amount, n=61):
        return self.k.invoice(n, "2040-05-20", [{"awb": None, "label": f"Late fee on {target}", "qty": "1",
                                                 "pct": "1.50", "base": "1000.00", "amount": amount,
                                                 "lane": None}])[1]

    def extend(self, sender, inv, new_due):
        doc = self.k.doc("batch_01/0062.eml", "2040-04-05", sender, "due_date_extension")
        self.k.fact("due_date_extensions", doc, {"invoice_id": inv, "new_due_date": new_due,
                                                 "is_quoted_or_forwarded": False},
                    quote=f"We extend the due date of invoice {inv} to {new_due}.")

    def test_paid_inside_extension_fee_not_owed(self):
        self.ledger("PW-OB-2040-0060", "2040-03-01", "2040-04-01", "1000.00", "paid", "2040-04-12")
        self.extend(WAIVERS, "PW-OB-2040-0060", "2040-04-20")          # payment_terms contact
        inv = self.fee_invoice("PW-OB-2040-0060", "15.00")
        c = keyed(late_fees.detect(self.k.world("2040-06-30")))[("late_fee_not_owed", inv, None)]
        self.assertEqual(c.amount_usd, D("15.00"))

    def test_extension_by_someone_else_does_not_count(self):
        self.ledger("PW-OB-2040-0060", "2040-03-01", "2040-04-01", "1000.00", "paid", "2040-04-12")
        self.extend(KAM, "PW-OB-2040-0060", "2040-04-20")
        self.fee_invoice("PW-OB-2040-0060", "15.00")              # 11 days late > 5 grace: one month 15.00 owed
        self.assertEqual(late_fees.detect(self.k.world("2040-06-30")), [])

    def test_compounding_months(self):
        # 45 days late -> 2 months: 1.5% x 1000.00 = 15.00, then 1.5% x 1015.00 = 15.225 -> 15.23; owed 30.23
        self.ledger("PW-OB-2040-0060", "2040-03-01", "2040-04-01", "1000.00", "paid", "2040-05-16")
        inv = self.fee_invoice("PW-OB-2040-0060", "31.00")
        c = keyed(late_fees.detect(self.k.world("2040-06-30")))[("late_fee_not_owed", inv, None)]
        self.assertEqual(c.amount_usd, D("0.77"))

    def test_risk_window_edges(self):
        # as_of 2040-06-01: due in 14 days -> risk (1.5% x 2000.00 = 30.00); 15 days, today, overdue -> no risk
        for n, due in ((1, "2040-06-15"), (2, "2040-06-16"), (3, "2040-06-01"), (4, "2040-05-20")):
            self.ledger(f"PW-OB-2040-07{n:02d}", "2040-05-01", due, "2000.00", "open", n=900 + n)
        got = keyed(late_fees.detect(self.k.world("2040-06-01")))
        self.assertEqual(list(got), [("late_fee_risk", "PW-OB-2040-0701", None)])
        c = got[("late_fee_risk", "PW-OB-2040-0701", None)]
        self.assertEqual((c.amount_usd, c.deadline, c.internal), (D("30.00"), "2040-06-15", "payment_reminder"))

    def test_risk_principal_less_disputed(self):
        self.ledger("PW-OB-2040-0701", "2040-05-01", "2040-06-15", "2000.00", "open")
        got = late_fees.detect(self.k.world("2040-06-01"), lambda inv: D("400.00"))
        self.assertEqual(got[0].amount_usd, D("24.00"))             # 1.5% x 1600.00


class CashbackExpiryTests(Base):
    def setUp(self):
        self.k = Kit()
        self.k.contract(rebate={"tiers": [{"min_qualifying_spend": "1000.00", "pct": "5"},
                                          {"min_qualifying_spend": "5000.00", "pct": "10"}],
                                "credit_due_days_after_period": "45"},
                        annual_credit={"pct_of_prior_year_qs": "1.00", "due_days_after_anniversary": "60"})

    def spend(self, n, day, amount, label="Air freight"):
        self.k.invoice(n, day, [{"awb": f"PW{n}", "label": label, "qty": "1", "rate": amount, "amount": amount}],
                       invoice_date=day)

    def test_rebate_tier_applies_to_all_spend_after_quarter_closes(self):
        # Q1 2040: 3000.00 freight + 2500.00 fuel = 5500.00 >= 5000 -> 10% of all = 550.00; tax excluded
        self.spend(70, "2040-02-01", "3000.00")
        self.spend(71, "2040-03-15", "2500.00", "FSC")
        self.spend(72, "2040-03-20", "900.00", "GST")
        early = keyed(cashback.detect(self.k.world("2040-03-31")))
        self.assertNotIn(("cashback", CID, "2040-Q1"), early)       # quarter not closed yet
        c = keyed(cashback.detect(self.k.world("2040-04-10")))[("cashback", CID, "2040-Q1")]
        self.assertEqual((c.amount_usd, c.internal), (D("550.00"), "track_credit"))   # due 2040-05-15
        c = keyed(cashback.detect(self.k.world("2040-06-01")))[("cashback", CID, "2040-Q1")]
        self.assertEqual(c.outbound, "claim_credit")

    def test_rebate_already_credited(self):
        self.spend(70, "2040-02-01", "3000.00")
        cn = self.k.doc("batch_01/0075.eml#CN.pdf", "2040-04-20", kind="credit_note")
        self.k.fact("credit_notes", cn, {"credit_id": "CN-9", "credit_date": "2040-04-20", "contract_id": CID,
                                         "credit_type": "rebate", "period": "2040-Q1", "amount": "150.00"})
        self.assertNotIn(("cashback", CID, "2040-Q1"), keyed(cashback.detect(self.k.world("2040-06-01"))))

    def test_resent_invoice_counts_once_in_spend(self):
        self.spend(70, "2040-02-01", "3000.00")
        self.k.invoice(76, "2040-02-20", [{"awb": "PW70", "label": "Air freight", "qty": "1", "rate": "3000.00",
                                           "amount": "3000.00"}], invoice_date="2040-02-01",
                       invoice_id="PW-OB-2040-0070")                  # the same invoice sent again
        c = keyed(cashback.detect(self.k.world("2040-06-01")))[("cashback", CID, "2040-Q1")]
        self.assertEqual(c.amount_usd, D("150.00"))                     # 3000.00 x 5%, not 6000.00 x 10%

    def test_expiry_window(self):
        # term ends 2041-01-09: 60 days before is 2040-11-10
        self.assertIn(("expiry", CID, None), keyed(expiry.detect(self.k.world("2040-11-10"))))
        self.assertNotIn(("expiry", CID, None), keyed(expiry.detect(self.k.world("2040-11-09"))))
        self.assertIn(("expiry", CID, None), keyed(expiry.detect(self.k.world("2041-01-09"))))
        self.assertNotIn(("expiry", CID, None), keyed(expiry.detect(self.k.world("2041-01-10"))))

    def test_signed_extension_moves_the_date(self):
        doc = self.k.doc("batch_01/0080.eml#EXT.pdf", "2040-11-01", "lena.sorell@ostravabio.example", "amendment")
        self.k.fact("contracts", doc, {"contract_id": f"{CID}/AMD-9", "kind": "amendment", "amends_contract_id": CID,
                                       "signed": True, "effective_date": "2040-11-01",
                                       "term": {"initial_term_end": "2042-01-09"}})
        self.assertEqual(expiry.detect(self.k.world("2040-12-01")), [])


class MarginStepDownTests(Base):
    """Handling margin 10% on carrier cost, 6% once cumulative carrier cost in the contract year reaches 10,000.00."""

    def setUp(self):
        self.k = Kit()
        self.margin = {"applicable": True, "margin_pct": "10", "step_down_pct": "6", "step_down_threshold": "10000.00",
                       "threshold_basis": "cumulative carrier cost in each Contract Year"}

    def contract(self, **margin):
        doc = self.k.contract(margin=self.margin | margin)
        for code, name, aliases in (("COST", "Carrier cost", ["Linehaul cost pass-through"]),
                                    ("MARGIN", "Handling margin", ["Forwarding margin"])):
            self.k.fact("charge_codes", doc, {"contract_id": CID, "code": code, "name": name, "aliases": aliases})

    def bill(self, n, day, cost, margin, pct="10"):
        self.k.invoice(n, day, [{"awb": f"PW{n}", "label": "Linehaul cost pass-through", "amount": cost},
                                {"awb": f"PW{n}", "label": "Forwarding margin", "pct": pct, "base": cost,
                                 "amount": margin}], invoice_date=day)

    def test_invoices_after_the_crossing_one_sum_per_quarter(self):
        self.contract()
        self.bill(80, "2040-01-20", "6000.00", "600.00")
        self.bill(81, "2040-02-10", "5000.00", "500.00")     # cumulative 11,000 crosses here: still billed at 10%
        self.bill(82, "2040-03-05", "2000.00", "200.00")     # should be 120.00 -> 80.00
        self.bill(83, "2040-03-25", "1500.00", "90.00", "6")  # already stepped down -> 0
        self.bill(84, "2040-04-02", "1000.00", "100.00")     # Q2: 100.00 - 60.00 = 40.00
        found = keyed(cashback.detect(self.k.world("2040-04-10")))
        c = found[("cashback", CID, "2040-Q1")]
        self.assertEqual((c.key["credit_type"], c.amount_usd, c.outbound), ("margin_step_down", D("80.00"),
                                                                            "claim_credit"))
        self.assertNotIn(("cashback", CID, "2040-Q2"), found)          # quarter not closed
        self.assertEqual(keyed(cashback.detect(self.k.world("2040-07-01")))[("cashback", CID, "2040-Q2")].amount_usd,
                         D("40.00"))
        self.assertEqual([x for x in cashback.detect(self.k.world("2040-04-10")) if x.cls != "cashback"], [])

    def test_margin_credit_held_and_not_applicable(self):
        self.contract()
        self.bill(80, "2040-01-20", "11000.00", "1100.00")
        self.bill(82, "2040-03-05", "2000.00", "200.00")
        cn = self.k.doc("batch_01/0085.eml#CN.pdf", "2040-05-02", kind="credit_note")
        self.k.fact("credit_notes", cn, {"credit_id": "CN-12", "credit_date": "2040-05-02", "contract_id": CID,
                                         "credit_type": "margin", "period": "2040-Q1", "amount": "80.00"})
        self.assertEqual(cashback.detect(self.k.world("2040-06-01")), [])

    def test_not_applicable(self):
        self.contract(applicable=False)
        self.bill(80, "2040-01-20", "11000.00", "1100.00")
        self.bill(82, "2040-03-05", "2000.00", "200.00")
        self.assertEqual(cashback.detect(self.k.world("2040-06-01")), [])

    def test_exceeds_is_strict_and_step_down_by_points(self):
        self.contract(step_down_pct=None, step_down_by_pct="4",
                      threshold_basis="when cumulative carrier cost exceeds the threshold in a Contract Year")
        self.bill(80, "2040-01-20", "10000.00", "1000.00")   # reaches but does not exceed
        self.bill(81, "2040-02-10", "500.00", "50.00")       # exceeds here
        self.bill(82, "2040-03-05", "2000.00", "200.00")     # 200.00 - 2000 x 6% = 80.00
        c = keyed(cashback.detect(self.k.world("2040-04-10")))[("cashback", CID, "2040-Q1")]
        self.assertEqual(c.amount_usd, D("80.00"))

    def test_report_item_and_trace_replay(self):
        from nova.report import build
        from nova.trace import replay_dir
        self.contract()
        self.bill(80, "2040-01-20", "11000.00", "1100.00")
        self.bill(82, "2040-03-05", "2000.00", "200.00")
        report = build(self.k.store, "2040-04-10", "supervised")
        items = [i for i in report["portfolio"]["cashback"] if i["credit_type"] == "margin_step_down"]
        self.assertEqual([(i["period"], i["amount_usd"], i["action"]) for i in items],
                         [("2040-Q1", "80.00", "draft:claim_credit")])
        results = replay_dir(self.k.store.paths["root"], "2040-04-10", "supervised")
        self.assertTrue(results and all(ok for ok, _ in results), results)

    def test_window_resets_each_contract_year(self):
        self.contract()
        self.bill(80, "2040-12-20", "11000.00", "1100.00")   # CY1 (from 2040-01-10) crosses
        self.bill(81, "2041-01-15", "2000.00", "200.00")     # CY2 starts 2041-01-10: count restarts, 10% is right
        self.assertNotIn(("cashback", CID, "2041-Q1"), keyed(cashback.detect(self.k.world("2041-04-05"))))


if __name__ == "__main__":
    unittest.main()
