"""Report assembly (actions per mode, $5,000 sum, history) and every feedback decision, on invented data."""
import hashlib
import json
import sys
import unittest
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parent))

from factkit import CID, KAM, RATES, Kit  # noqa: E402
from nova.report import SCHEMA, build  # noqa: E402

FB_N = [0]


def items(rep):
    return {i["id"].split("@")[0]: i for i in rep["findings"] + [x for v in rep["portfolio"].values() for x in v]}


class ReportBase(unittest.TestCase):
    def setUp(self):
        self.k = Kit()
        self.k.contract()

    def tearDown(self):
        self.k.close()

    def report(self, as_of="2040-12-31", mode="supervised"):
        rep = build(self.k.store, as_of, mode)
        jsonschema.validate(rep, SCHEMA)
        self.assertFalse(mode == "supervised" and any(i["action"].startswith("execute:") for i in items(rep).values()))
        return items(rep)

    def overbill(self, n, awb, pickup, rate="4.20", tracked=True, lane="KLX1-ORB2", received="2040-03-20"):
        if tracked:
            self.k.picked_up(awb, pickup)
        amt = f"{118 * float(rate):.2f}"
        return self.k.invoice(n, received, [{"awb": awb, "label": "Air freight", "qty": "118", "rate": rate,
                                             "amount": amt, "lane": lane, "pickup": pickup}])[1]

    def resend(self, n, total, ledger_status="paid"):
        line = [{"awb": f"PW{n}", "label": "Courier service", "qty": "1", "rate": total, "amount": total}]
        inv = f"PW-OB-2040-{n:04d}"
        self.k.invoice(n, "2040-04-01", line, invoice_id=inv)
        doc, _ = self.k.invoice(n + 1, "2040-05-01", line, invoice_id=inv)
        self.k.fact("payment_requests", doc.split("#")[0], {"invoice_id": inv, "kind": "asks_payment"})
        led = self.k.doc(f"batch_01/{n + 2:04d}.eml#ap.xlsx", "2040-04-20", "ap@ostravabio.example", "table")
        self.k.fact("ledger_rows", led, {"invoice_id": inv, "invoice_date": "2040-04-01", "due_date": "2040-05-01",
                                         "amount": total, "currency": "USD", "status": ledger_status,
                                         "paid_date": "2040-04-15"})
        return inv

    def feedback(self, decided_at, *items_):
        FB_N[0] += 1
        body = {"schema_version": "1.0", "after_batch": "batch_01", "decided_at": decided_at, "items": list(items_)}
        raw = json.dumps(body).encode() + str(FB_N[0]).encode()
        with self.k.store.db:
            self.k.store.add_feedback_file(hashlib.sha256(raw).hexdigest(), "fb.json", body, "now")


class ActionTests(ReportBase):
    def test_exactly_5000_goes_to_human_review_in_both_modes(self):
        big = self.resend(100, "5000.00")
        small = self.resend(110, "4999.99")
        for mode in ("supervised", "autonomous"):
            got = self.report(mode=mode)
            self.assertEqual(got[f"duplicate:{big}"]["action"], "human_review")
            self.assertEqual(got[f"duplicate:{small}"]["action"],
                             "draft:dispute" if mode == "supervised" else "execute:dispute")

    def test_findings_on_one_invoice_are_summed(self):
        # one invoice: duplicate 3000.00 and (Delivery fee 3000.00 vs Annex D 100.00) overcharge 2900.00
        line = [{"awb": "PW120", "label": "Delivery fee", "qty": "1", "rate": "3000.00", "amount": "3000.00"}]
        inv = "PW-OB-2040-0120"
        self.k.picked_up("PW120", "2040-03-02")
        self.k.invoice(120, "2040-04-01", line, invoice_id=inv)
        doc, _ = self.k.invoice(121, "2040-05-01", line, invoice_id=inv)
        self.k.fact("payment_requests", doc.split("#")[0], {"invoice_id": inv, "kind": "asks_payment"})
        led = self.k.doc("batch_01/0122.eml#ap.xlsx", "2040-04-20", "ap@ostravabio.example", "table")
        self.k.fact("ledger_rows", led, {"invoice_id": inv, "invoice_date": "2040-04-01", "due_date": "2040-05-01",
                                         "amount": "3000.00", "status": "paid", "paid_date": "2040-04-15"})
        got = self.report(mode="autonomous")
        self.assertEqual(got[f"overcharge:{inv}"]["action"], "human_review")
        self.assertEqual(got[f"duplicate:{inv}"]["action"], "human_review")

    def test_autonomous_needs_a_tracked_pickup_date(self):
        tracked = self.overbill(130, "PW130", "2040-03-02")
        untracked = self.overbill(131, "PW131", "2040-03-02", tracked=False)
        got = self.report(mode="autonomous")
        self.assertEqual(got[f"overcharge:{tracked}"]["action"], "execute:dispute")
        self.assertEqual(got[f"overcharge:{untracked}"]["action"], "human_review")
        self.assertLess(got[f"overcharge:{untracked}"]["confidence"], got[f"overcharge:{tracked}"]["confidence"])

    def add_second_lane_and_conflict(self):
        doc = "batch_01/0001.eml#MSA.pdf"
        self.k.fact("rate_rows", doc, {"contract_id": CID, "lane": "KLX1-PQR3", "band": "100-299.5 kg",
                                       "band_min_kg": "100", "band_max_kg": "299.5", "is_minimum_charge": False,
                                       "period_label": "P1", "rate": "4.00"})
        amd = self.k.doc("batch_01/0140.eml#AMD.pdf", "2040-01-25", "lena.sorell@ostravabio.example", "amendment")
        self.k.fact("contracts", amd, {"contract_id": f"{CID}/AMD-1", "kind": "amendment", "amends_contract_id": CID,
                                       "signed": True, "effective_date": "2040-02-01",
                                       "amendment_changes": [{"lanes": ["KLX1-ORB2"], "effective_from": "2040-02-01",
                                                              "what": "new rate"}]})
        self.k.fact("rate_rows", amd, {"contract_id": f"{CID}/AMD-1", "lane": "KLX1-ORB2", "band": "100-299.5 kg",
                                       "band_min_kg": "100", "band_max_kg": "299.5", "is_minimum_charge": False,
                                       "period_label": None, "rate": "3.80"})
        note = self.k.doc("batch_01/0141.eml", "2040-02-10", RATES, "rate_notice")
        self.k.fact("rate_notices", note, {"contract_id": CID, "lane": "KLX1-ORB2", "band": "100-299.5 kg",
                                           "rate": "4.20", "effective_from": "2040-02-15", "effective_to": None})

    def test_conflict_escalates_and_does_not_block_another_lane(self):
        self.add_second_lane_and_conflict()
        conflicted = self.overbill(142, "PW142", "2040-03-02")
        other = self.overbill(143, "PW143", "2040-03-02", lane="KLX1-PQR3")
        got = self.report(mode="autonomous")
        self.assertEqual((got[f"overcharge:{conflicted}"]["verdict"], got[f"overcharge:{conflicted}"]["action"]),
                         ("conflict", "escalate"))
        self.assertEqual(got[f"overcharge:{other}"]["action"], "execute:dispute")

    def test_missing_document_request(self):
        amd = self.k.doc("batch_01/0150.eml#AMD.pdf", "2040-01-25", "lena.sorell@ostravabio.example", "amendment")
        self.k.fact("contracts", amd, {"contract_id": f"{CID}/AMD-2", "kind": "amendment", "amends_contract_id": CID,
                                       "signed": True, "effective_date": "2040-03-01",
                                       "amendment_changes": [{"lanes": ["KLX1-ORB2"], "effective_from": "2040-03-01",
                                                              "what": "replaced by Annex A rev 4 (attached)"}]})
        self.k.fact("referenced_documents", amd, {"name": "Annex A rev 4", "held_in_this_input": False})
        inv = self.overbill(151, "PW151", "2040-03-02")
        sup, auto = self.report(), self.report(mode="autonomous")
        self.assertEqual(sup[f"overcharge:{inv}"]["action"], "draft:request_document")
        self.assertEqual(auto[f"overcharge:{inv}"]["action"], "execute:request_document")
        self.assertEqual(sup[f"overcharge:{inv}"]["missing_doc"]["name"], "Annex A rev 4")

    def test_history_supersedes_and_stable_ids(self):
        inv = self.overbill(160, "PW160", "2040-03-02")
        first = self.report(as_of="2040-04-30")[f"overcharge:{inv}"]
        self.assertEqual(self.report(as_of="2040-05-31")[f"overcharge:{inv}"]["id"], first["id"])   # unchanged
        amd = self.k.doc("batch_01/0161.eml#AMD.pdf", "2040-06-10", "lena.sorell@ostravabio.example", "amendment")
        self.k.fact("contracts", amd, {"contract_id": f"{CID}/AMD-3", "kind": "amendment", "amends_contract_id": CID,
                                       "signed": True, "effective_date": "2040-02-01",            # backdated
                                       "amendment_changes": [{"lanes": ["KLX1-ORB2"], "effective_from": "2040-02-01",
                                                              "what": "new rate"}]})
        self.k.fact("rate_rows", amd, {"contract_id": f"{CID}/AMD-3", "lane": "KLX1-ORB2", "band": "100-299.5 kg",
                                       "band_min_kg": "100", "band_max_kg": "299.5", "is_minimum_charge": False,
                                       "period_label": None, "rate": "3.90"})
        later = self.report(as_of="2040-06-30")[f"overcharge:{inv}"]
        self.assertEqual(later["supersedes"], [first["id"]])
        self.assertNotEqual(later["id"], first["id"])
        self.assertEqual(later["amount_usd"], "35.40")                 # (4.20 - 3.90) x 118
        before = self.report(as_of="2040-05-31")[f"overcharge:{inv}"]   # the old date keeps its answer
        self.assertEqual(before["amount_usd"], "23.60")

    def test_key_created_by_a_backdated_amendment_after_an_empty_report_is_retro(self):
        # Found by the unseen-world suite: the previous report listed nothing, so no history row recorded it, and
        # the new key was not marked retro.
        inv = self.overbill(170, "PW170", "2040-03-02", rate="4.00")    # the contract rate: clean at first
        self.assertEqual(self.report(as_of="2040-04-30"), {})
        amd = self.k.doc("batch_01/0171.eml#AMD.pdf", "2040-06-10", "lena.sorell@ostravabio.example", "amendment")
        self.k.fact("contracts", amd, {"contract_id": f"{CID}/AMD-4", "kind": "amendment", "amends_contract_id": CID,
                                       "signed": True, "effective_date": "2040-02-01",
                                       "amendment_changes": [{"lanes": ["KLX1-ORB2"], "effective_from": "2040-02-01",
                                                              "what": "new rate"}]})
        self.k.fact("rate_rows", amd, {"contract_id": f"{CID}/AMD-4", "lane": "KLX1-ORB2", "band": "100-299.5 kg",
                                       "band_min_kg": "100", "band_max_kg": "299.5", "is_minimum_charge": False,
                                       "period_label": None, "rate": "3.90"})
        item = self.report(as_of="2040-06-30")[f"overcharge:{inv}"]
        self.assertTrue(item.get("retro"))
        self.assertEqual(item["supersedes"], [])
        self.assertEqual(item["amount_usd"], "11.80")                  # (4.00 - 3.90) x 118


class FeedbackTests(ReportBase):
    def waiver_by(self, sender, n, awb, month_pickup, quoted=False):
        self.k.picked_up(awb, month_pickup)
        doc = self.k.doc(f"batch_01/{n:04d}.eml", "2040-03-05", sender, "waiver")
        with self.k.store.db:
            self.k.store.db.execute("UPDATE documents SET sender_name = ? WHERE doc = ?",
                                    ("Omar Lind" if sender == KAM else "Someone", doc))
        self.k.fact("waivers", doc, {"charge": "Delivery fee", "awbs": [awb], "months": [], "invoice_ids": [],
                                     "condition": None, "is_quoted_or_forwarded": quoted, "quoted_author": None})
        return self.k.invoice(n + 1, "2040-03-20", [{"awb": awb, "label": "Delivery fee", "qty": "1",
                                                     "rate": "100.00", "amount": "100.00"}])[1]

    def test_standing_authority_for_its_category_only(self):
        inv = self.waiver_by(KAM, 200, "PW200", "2040-03-02")
        self.assertNotIn(f"waived_but_billed:{inv}", self.report())
        self.feedback("2040-04-01T10:00:00Z", {
            "item_id": "fb-1", "decision": "confirm", "finding_key": {"invoice_id": inv, "class": "waived_but_billed"},
            "fact": {"type": "sender_authority", "subject": {"person": "Omar Lind", "party": "PW-US"},
                     "value": {"categories": ["waivers"]}},
            "scope": {"kind": "standing", "applies_to": {"contract_id": CID, "person": "Omar Lind",
                                                         "category": "waivers"},
                      "valid_from": "2040-01-01", "valid_to": None}})
        got = self.report()[f"waived_but_billed:{inv}"]
        self.assertEqual(got["learned_at"], {"feedback_item_id": "fb-1", "batch": "batch_01"})
        # the same person in another category (rates) is not covered
        note = self.k.doc("batch_01/0210.eml", "2040-02-10", KAM, "rate_notice")
        self.k.fact("rate_notices", note, {"contract_id": CID, "lane": "KLX1-ORB2", "band": "100-299.5 kg",
                                           "rate": "4.20", "effective_from": "2040-02-15", "effective_to": None})
        over = self.overbill(211, "PW211", "2040-03-02")
        self.assertEqual(self.report()[f"overcharge:{over}"]["verdict"], "finding")

    def test_feedback_counts_only_from_decided_at(self):
        inv = self.overbill(220, "PW220", "2040-03-02")
        self.feedback("2040-06-02T10:00:00Z", {"item_id": "fb-2", "decision": "reject",
                                               "finding_key": {"invoice_id": inv, "class": "overcharge"},
                                               "scope": {"kind": "one_off", "applies_to": {"invoice_id": inv}}})
        self.assertIn(f"overcharge:{inv}", self.report(as_of="2040-05-31"))
        self.assertNotIn(f"overcharge:{inv}", self.report(as_of="2040-06-30"))

    def test_close_stops_only_that_key(self):
        a = self.overbill(230, "PW230", "2040-03-02")
        self.feedback("2040-04-01T10:00:00Z", {
            "item_id": "fb-3", "decision": "close", "finding_key": {"invoice_id": a, "class": "overcharge"},
            "fact": {"type": "dispute_closed", "subject": {"invoice_id": a}, "value": {"status": "closed"}},
            "scope": {"kind": "one_off", "applies_to": {"invoice_id": a}}})
        b = self.overbill(231, "PW231", "2040-03-02", received="2040-05-20")     # same wrong rate, new invoice
        got = self.report()
        self.assertNotIn(f"overcharge:{a}", got)
        self.assertEqual(got[f"overcharge:{b}"]["verdict"], "finding")

    def test_override_amount(self):
        inv = self.overbill(240, "PW240", "2040-03-02")
        self.feedback("2040-04-01T10:00:00Z", {
            "item_id": "fb-4", "decision": "override_amount", "finding_key": {"invoice_id": inv, "class": "overcharge"},
            "fact": {"type": "dispute_closed", "value": {"status": "settled", "amount_usd": "12.40"}},
            "scope": {"kind": "one_off", "applies_to": {"invoice_id": inv}}})
        got = self.report()[f"overcharge:{inv}"]
        self.assertEqual((got["amount_usd"], got["learned_at"]["feedback_item_id"]), ("12.40", "fb-4"))

    def test_rate_accepted_standing_on_its_lane_and_dates(self):
        note = self.k.doc("batch_01/0250.eml", "2040-02-10", KAM, "rate_notice")      # no rates authority
        self.k.fact("rate_notices", note, {"contract_id": CID, "lane": "KLX1-ORB2", "band": "100-299.5 kg",
                                           "rate": "4.20", "effective_from": "2040-02-15", "effective_to": None})
        first = self.overbill(251, "PW251", "2040-03-02")
        self.feedback("2040-04-01T10:00:00Z", {
            "item_id": "fb-5", "decision": "close", "finding_key": {"invoice_id": first, "class": "overcharge"},
            "fact": {"type": "rate_accepted", "subject": {"contract_id": CID, "lane": "KLX1-ORB2"}},
            "scope": {"kind": "standing", "applies_to": {"contract_id": CID, "lane": "KLX1-ORB2"},
                      "valid_from": "2040-02-15", "valid_to": "2040-06-30"}})
        at_rate = self.overbill(252, "PW252", "2040-03-10", received="2040-05-20")
        above = self.overbill(253, "PW253", "2040-03-10", rate="4.50", received="2040-05-20")
        outside = self.overbill(254, "PW254", "2040-07-15", received="2040-08-20")      # P2 4.10; after the window
        got = self.report()
        self.assertNotIn(f"overcharge:{first}", got)
        self.assertNotIn(f"overcharge:{at_rate}", got)
        self.assertEqual(got[f"overcharge:{above}"]["amount_usd"], "35.40")    # (4.50 - 4.20) x 118
        self.assertEqual(got[f"overcharge:{above}"]["learned_at"]["feedback_item_id"], "fb-5")
        self.assertEqual(got[f"overcharge:{outside}"]["amount_usd"], "11.80")  # (4.20 - 4.10) x 118, no feedback
        self.assertIsNone(got[f"overcharge:{outside}"].get("learned_at"))

    def test_resolve_conflict_uses_the_named_source(self):
        ActionTests.add_second_lane_and_conflict(self)
        inv = self.overbill(260, "PW260", "2040-03-02")
        self.assertEqual(self.report()[f"overcharge:{inv}"]["verdict"], "conflict")
        self.feedback("2040-04-01T10:00:00Z", {
            "item_id": "fb-6", "decision": "resolve_conflict", "finding_key": {"invoice_id": inv, "class": "overcharge"},
            "fact": {"type": "precedence", "subject": {"contract_id": CID, "lane": "KLX1-ORB2"},
                     "value": {"use": "amendment"}},
            "scope": {"kind": "standing", "applies_to": {"contract_id": CID, "lane": "KLX1-ORB2"},
                      "valid_from": "2040-02-01", "valid_to": None}})
        got = self.report()[f"overcharge:{inv}"]
        self.assertEqual((got["verdict"], got["amount_usd"]), ("finding", "47.20"))   # (4.20 - 3.80) x 118
        self.assertEqual(got["learned_at"]["feedback_item_id"], "fb-6")

    def test_one_off_waiver_approval_does_not_spread(self):
        # counterfactual family: one-off feedback for A with a similar B present -> only A changes
        a = self.waiver_by(KAM, 270, "PW270", "2040-03-02", quoted=True)
        b = self.waiver_by(KAM, 280, "PW280", "2040-03-05", quoted=True)
        self.feedback("2040-04-01T10:00:00Z", {
            "item_id": "fb-7", "decision": "one_off_approval",
            "finding_key": {"invoice_id": a, "class": "waived_but_billed"},
            "fact": {"type": "waiver_scope", "subject": {"person": "Omar Lind"}, "value": {"months": ["2040-03"]}},
            "scope": {"kind": "one_off", "applies_to": {"invoice_id": a}}})
        got = self.report()
        self.assertEqual(got[f"waived_but_billed:{a}"]["verdict"], "finding")
        self.assertEqual(got[f"waived_but_billed:{a}"]["learned_at"]["feedback_item_id"], "fb-7")
        self.assertEqual(got[f"waived_but_billed:{b}"]["verdict"], "cannot_determine")     # B unchanged


if __name__ == "__main__":
    unittest.main()
