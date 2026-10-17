"""Overcharge rule on invented contracts and invoices. Expected amounts are worked by hand in the comments."""
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from factkit import CID, KAM, RATES, TREASURY, Kit  # noqa: E402
from nova.rules import overcharge  # noqa: E402

AS_OF = "2040-12-31"


def freight(awb, qty, rate, pickup=None, label="Air freight"):
    return {"awb": awb, "label": label, "qty": qty, "rate": rate, "pickup": pickup,
            "amount": f"{Decimal(qty) * Decimal(rate):.2f}"}


def fuel(awb, base, pct, label="Fuel surcharge"):
    amt = (Decimal(base) * Decimal(pct) / 100).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")
    return {"awb": awb, "label": label, "base": base, "pct": pct, "amount": f"{amt:.2f}"}


class OverchargeTests(unittest.TestCase):
    def setUp(self):
        self.k = Kit()
        self.k.contract()

    def tearDown(self):
        self.k.close()

    def run_rule(self, as_of=AS_OF):
        return {c.key["invoice_id"]: c for c in overcharge.detect(self.k.world(as_of))}

    def bill(self, n, awb, pickup, qty, rate, received="2040-03-20", extra=(), **kw):
        self.k.picked_up(awb, pickup)
        base = freight(awb, qty, rate)
        return self.k.invoice(n, received, [base, fuel(awb, base["amount"], "20.00"), *extra], **kw)[1]

    def test_wrong_rate_with_fuel(self):
        # 118 kg, P1 band 100-299.5 = 4.00; billed 4.20: freight 495.60 - 472.00 = 23.60;
        # fuel 20%: 99.12 - 94.40 = 4.72; total 28.32
        inv = self.bill(1, "PW100", "2040-03-02", "118", "4.20")
        got = self.run_rule()[inv]
        self.assertEqual((got.verdict, got.amount_usd, got.outbound), ("finding", Decimal("28.32"), "dispute"))
        docs = {e["doc"] for e in got.evidence}
        self.assertIn("batch_01/0001.eml#MSA.pdf", docs)                 # the governing rate row is cited
        self.assertIn("batch_01/0900.eml#tracking-PW100.xlsx", docs)           # and the pickup date's source

    def test_band_boundary_and_minimum(self):
        # 44.5 kg is in band 0-44.5 (5.10): clean. 45 kg is in 45-99.5 (4.60): 229.50 - 207.00 = 22.50 (+ fuel 4.50)
        clean = self.bill(2, "PW200", "2040-03-02", "44.5", "5.10")
        wrong = self.bill(3, "PW201", "2040-03-02", "45", "5.10")
        # 10 kg x 5.10 = 51.00 < minimum 80.00, so 80.00 is right; billed 85.00 flat: 5.00 too much
        self.k.picked_up("PW202", "2040-03-02")
        mini = self.k.invoice(4, "2040-03-20", [{"awb": "PW202", "label": "Air freight", "qty": "10", "rate": "8.50",
                                                 "amount": "85.00"}])[1]
        got = self.run_rule()
        self.assertNotIn(clean, got)
        self.assertEqual(got[wrong].amount_usd, Decimal("27.00"))
        self.assertEqual(got[mini].amount_usd, Decimal("5.00"))

    def test_rate_period_follows_pickup_date(self):
        # pickup in P2 (from 2040-07-10): 118 kg at 4.10 is right; the same rate in P1 would be 0.10/kg too much
        p2 = self.bill(5, "PW300", "2040-08-01", "118", "4.10", received="2040-08-20")
        p1 = self.bill(6, "PW301", "2040-03-02", "118", "4.10")
        got = self.run_rule()
        self.assertNotIn(p2, got)
        self.assertEqual(got[p1].amount_usd, Decimal("14.16"))       # 11.80 freight + 2.36 fuel

    def amendment(self, rate="3.80", signed=True, effective="2040-02-01", changes=None, n=10):
        doc = self.k.doc(f"batch_01/{n:04d}.eml#AMD.pdf", "2040-01-25", "lena.sorell@ostravabio.example", "amendment")
        self.k.fact("contracts", doc, {"contract_id": f"{CID}/AMD-{n}", "kind": "amendment",
                                       "amends_contract_id": CID, "signed": signed, "effective_date": effective,
                                       "amendment_changes": changes or [{"lanes": ["KLX1-ORB2"],
                                                                         "effective_from": effective,
                                                                         "effective_to": None, "what": "new rates"}]})
        self.k.fact("rate_rows", doc, {"contract_id": f"{CID}/AMD-{n}", "lane": "KLX1-ORB2", "band": "100-299.5 kg",
                                       "band_min_kg": "100", "band_max_kg": "299.5", "is_minimum_charge": False,
                                       "period_label": None, "rate": rate})
        return doc

    def notice(self, sender, rate="4.20", n=20):
        doc = self.k.doc(f"batch_01/{n:04d}.eml", "2040-02-10", sender, "rate_notice")
        self.k.fact("rate_notices", doc, {"contract_id": CID, "lane": "KLX1-ORB2", "band": "100-299.5 kg",
                                          "rate": rate, "currency": "USD", "effective_from": "2040-02-15",
                                          "effective_to": None})

    def test_signed_amendment_beats_agreement_unsigned_does_not(self):
        # amendment 3.80: billed 4.00 x 118 = 472.00 vs 448.40 -> 23.60 + fuel 4.72 = 28.32
        self.amendment()
        inv = self.bill(7, "PW400", "2040-03-02", "118", "4.00")
        self.assertEqual(self.run_rule()[inv].amount_usd, Decimal("28.32"))

    def test_unsigned_amendment_ignored(self):
        self.amendment(signed=False)
        inv = self.bill(8, "PW401", "2040-03-02", "118", "4.00")
        self.assertNotIn(inv, self.run_rule())

    def test_notice_needs_schedule1_rates_authority(self):
        self.notice(KAM)                                          # the KAM has notices, not rates
        inv = self.bill(9, "PW500", "2040-03-02", "118", "4.20")
        self.assertEqual(self.run_rule()[inv].amount_usd, Decimal("28.32"))

    def test_authorised_notice_changes_agreement_rate(self):
        self.notice(RATES)
        inv = self.bill(11, "PW501", "2040-03-02", "118", "4.20")
        self.assertNotIn(inv, self.run_rule())

    def test_unranked_notice_against_amendment_is_a_conflict(self):
        # amendment 3.80 vs notice 4.20, billed 4.20: amendment says 0.40 x 118 = 47.20 + fuel 9.44 = 56.64; notice 0
        self.amendment()
        self.notice(RATES)
        inv = self.bill(12, "PW600", "2040-03-02", "118", "4.20")
        got = self.run_rule()[inv]
        self.assertEqual(got.verdict, "conflict")
        self.assertEqual(got.amount_range, (Decimal("0.00"), Decimal("56.64")))
        self.assertGreaterEqual(len({e["doc"] for e in got.evidence}), 2)        # both sources cited

    def test_ranked_notice_is_not_a_conflict(self):
        self.k.close()
        self.k = Kit()
        self.k.contract(precedence={"rate_notice_vs_amendment_unranked": False})
        self.amendment()
        self.notice(RATES)
        inv = self.bill(13, "PW601", "2040-03-02", "118", "4.20")
        got = self.run_rule()[inv]
        self.assertEqual((got.verdict, got.amount_usd), ("finding", Decimal("56.64")))

    def test_change_relying_on_missing_document(self):
        doc = self.amendment(changes=[{"lanes": ["KLX1-ORB2"], "effective_from": "2040-03-01", "effective_to": None,
                                       "what": "rates replaced by Annex B rev 3 (attached)"}])
        self.k.fact("referenced_documents", doc, {"name": "Annex B rev 3", "referenced_by": doc,
                                                  "held_in_this_input": False, "applies_to": "KLX1-ORB2"})
        after = self.bill(14, "PW700", "2040-03-02", "118", "4.20")
        before = self.bill(15, "PW701", "2040-02-20", "118", "4.20")       # before the change: priced normally
        got = self.run_rule()
        self.assertEqual(got[after].verdict, "cannot_determine")
        self.assertEqual(got[after].missing_doc["name"], "Annex B rev 3")
        self.assertEqual(got[after].missing_doc["holder"]["person"], "Rhea Voss")    # carrier's rates contact
        self.assertEqual(got[after].outbound, "request_document")
        self.assertEqual(got[before].verdict, "finding")

    def test_dry_ice_only_does_not_attract_dg_fee(self):
        dg = {"awb": "PW800", "label": "DG handling", "qty": "1", "rate": "120.00", "amount": "120.00"}
        inv = self.bill(16, "PW800", "2040-03-02", "118", "4.00", extra=[dg])
        decl = self.k.doc("batch_01/0016.eml#DGD.pdf", "2040-03-20", kind="dg_declaration")
        self.k.fact("dg_declarations", decl, {"awb": "PW800", "un_numbers": ["UN1845"], "refrigerant_only": True})
        mixed = self.bill(17, "PW801", "2040-03-02", "118", "4.00", extra=[dict(dg, awb="PW801")])
        decl2 = self.k.doc("batch_01/0017.eml#DGD.pdf", "2040-03-20", kind="dg_declaration")
        self.k.fact("dg_declarations", decl2, {"awb": "PW801", "un_numbers": ["UN1845", "UN1170"],
                                               "refrigerant_only": False})
        got = self.run_rule()
        self.assertEqual(got[inv].amount_usd, Decimal("120.00"))
        self.assertNotIn(mixed, got)

    def test_peak_surcharge_only_in_its_months(self):
        # 118 kg x 0.30 = 35.40, owed only for September-November pickups
        peak = lambda awb: {"awb": awb, "label": "PSS", "qty": "118", "rate": "0.30", "amount": "35.40"}
        march = self.bill(18, "PW900", "2040-03-02", "118", "4.00", extra=[peak("PW900")])
        self.k.picked_up("PW901", "2040-09-15")
        base = freight("PW901", "118", "4.10")
        sept = self.k.invoice(19, "2040-09-30", [base, fuel("PW901", base["amount"], "21.00"), peak("PW901")])[1]
        got = self.run_rule()
        self.assertEqual(got[march].amount_usd, Decimal("35.40"))
        self.assertNotIn(sept, got)

    def test_inr_converted_once_per_finding(self):
        # same 23.60 + 4.72 = 28.32 INR over; Annex F March 80.00: 28.32 / 80 = 0.354 -> 0.35
        # (converting per line would give 0.30 + 0.06 = 0.36)
        doc = "batch_01/0001.eml#MSA.pdf"
        self.k.fact("fx_rows", doc, {"contract_id": CID, "month": "2040-03", "inr_per_usd": "80.00"})
        inv = self.bill(20, "PW950", "2040-03-02", "118", "4.20", currency="INR", invoice_date="2040-03-20")
        self.assertEqual(self.run_rule()[inv].amount_usd, Decimal("0.35"))

    def test_inr_without_annex_f_row_cannot_be_determined(self):
        inv = self.bill(21, "PW951", "2040-03-02", "118", "4.20", currency="INR", invoice_date="2040-03-20")
        got = self.run_rule()[inv]
        self.assertEqual(got.verdict, "cannot_determine")
        self.assertEqual(got.missing_doc["holder"]["person"], "Kit Amari")    # the treasury contact

    def test_documents_received_after_as_of_do_not_count(self):
        inv = self.bill(22, "PW960", "2040-03-02", "118", "4.20", received="2040-04-02")
        self.assertNotIn(inv, self.run_rule(as_of="2040-04-01"))
        self.assertIn(inv, self.run_rule(as_of="2040-04-02"))


if __name__ == "__main__":
    unittest.main()
