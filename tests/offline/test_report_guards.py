"""Action and citation regressions using invented, fully cited documents; no model or real mailbox."""
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_report_feedback as report_tests
from nova.report import _resolvable


class ConflictScopeTests(report_tests.ReportBase):
    def conflict(self, through=None):
        report_tests.ActionTests.add_second_lane_and_conflict(self)
        if through:
            with self.k.store.db:
                self.k.store.db.execute(
                    "UPDATE facts SET data_json = json_set(data_json, '$.effective_to', ?) "
                    "WHERE kind = 'rate_notices'", (through,))
        return self.overbill(142, "PW142", "2040-03-02")

    def test_conflict_in_another_rate_period_does_not_block(self):
        conflicted = self.conflict(through="2040-06-30")
        later = self.overbill(170, "PW170", "2040-08-02", received="2040-08-20")
        got = self.report(mode="autonomous")
        self.assertEqual(got[f"overcharge:{conflicted}"]["action"], "escalate")
        self.assertEqual(got[f"overcharge:{later}"]["amount_usd"], "47.20")
        self.assertEqual(got[f"overcharge:{later}"]["action"], "execute:dispute")

    def test_freight_conflict_does_not_block_an_independent_delivery_charge(self):
        self.conflict()
        self.k.picked_up("PW171", "2040-03-02")
        _, inv = self.k.invoice(171, "2040-03-20", [
            {"awb": "PW171", "label": "Air freight", "qty": "400", "rate": "3.50", "amount": "1400.00"},
            {"awb": "PW171", "label": "Delivery fee", "qty": "1", "rate": "150.00", "amount": "150.00"}])
        got = self.report(mode="autonomous")[f"overcharge:{inv}"]
        self.assertEqual((got["amount_usd"], got["action"]), ("50.00", "execute:dispute"))

    def test_conflict_on_second_lane_blocks_a_related_freight_dispute(self):
        self.conflict()
        self.k.picked_up("PW172A", "2040-03-02")
        self.k.picked_up("PW172B", "2040-03-02")
        _, inv = self.k.invoice(172, "2040-03-20", [
            {"awb": "PW172A", "lane": "KLX1-PQR3", "label": "Air freight", "qty": "118",
             "rate": "4.20", "amount": "495.60"},
            {"awb": "PW172B", "lane": "KLX1-ORB2", "label": "Air freight", "qty": "400",
             "rate": "3.60", "amount": "1440.00"}])
        got = self.report(mode="autonomous")[f"overcharge:{inv}"]
        self.assertEqual((got["amount_usd"], got["action"]), ("63.60", "human_review"))

    def test_conflicted_invoice_does_not_contaminate_its_other_lane(self):
        report_tests.ActionTests.add_second_lane_and_conflict(self)
        self.k.picked_up("PW173A", "2040-03-02")
        self.k.picked_up("PW173B", "2040-03-02")
        _, conflicted = self.k.invoice(173, "2040-03-20", [
            {"awb": "PW173A", "lane": "KLX1-PQR3", "label": "Air freight", "qty": "118",
             "rate": "4.20", "amount": "495.60"},
            {"awb": "PW173B", "lane": "KLX1-ORB2", "label": "Air freight", "qty": "118",
             "rate": "4.20", "amount": "495.60"}])
        other = self.overbill(174, "PW174", "2040-03-02", lane="KLX1-PQR3")
        got = self.report(mode="autonomous")
        self.assertEqual(got[f"overcharge:{conflicted}"]["action"], "escalate")
        self.assertEqual(got[f"overcharge:{other}"]["action"], "execute:dispute")


class EvidenceGuardTests(report_tests.ReportBase):
    def test_rejected_citation_prevents_unattended_action(self):
        inv = self.overbill(180, "PW180", "2040-03-02")
        good = self.report(mode="autonomous")[f"overcharge:{inv}"]
        self.assertEqual(good["action"], "execute:dispute")
        with self.k.store.db:
            self.k.store.db.execute("DELETE FROM pages WHERE doc = ?",
                                    (f"batch_01/0180.eml#{inv}.pdf",))
        got = self.report(mode="autonomous")[f"overcharge:{inv}"]
        self.assertEqual(got["amount_usd"], good["amount_usd"])
        self.assertEqual(got["action"], "human_review")
        self.assertLess(got["confidence"], good["confidence"])
        self.assertEqual(got["evidence"], _resolvable(self.k.store, got["evidence"]))

    def test_no_resolvable_citation_is_not_reinserted(self):
        inv = self.overbill(181, "PW181", "2040-03-02")
        with self.k.store.db:
            self.k.store.db.execute("DELETE FROM pages")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            got = self.report(mode="autonomous")
        self.assertNotIn(f"overcharge:{inv}", got)
        self.assertIn("resolvable evidence", err.getvalue())


class CurrencyTests(report_tests.ReportBase):
    def test_inr_overcharge_is_converted_once_in_the_report(self):
        # 118 kg at 4.20 billed against the 4.00 band: INR 23.60 over; Annex F March 80.00: 0.295 -> 0.30. The rule
        # converts it; the report must not divide by the rate a second time (0.00, no finding).
        self.k.fact("fx_rows", "batch_01/0001.eml#MSA.pdf", {"contract_id": report_tests.CID, "month": "2040-03",
                                                            "inr_per_usd": "80.00"})
        self.k.picked_up("PW180", "2040-03-02")
        _, inv = self.k.invoice(180, "2040-03-20", [{"awb": "PW180", "label": "Air freight", "qty": "118",
                                                     "rate": "4.20", "amount": "495.60", "pickup": "2040-03-02"}],
                                currency="INR")
        self.assertEqual(self.report().get(f"overcharge:{inv}", {}).get("amount_usd"), "0.30")


if __name__ == "__main__":
    unittest.main()
