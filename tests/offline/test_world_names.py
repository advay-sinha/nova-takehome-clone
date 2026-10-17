"""Contract-specific names: charge-code letters, Schedule 1 category wording, OCR noise on a contract id.

Found by the first run of my own eval mailboxes (agreement codes fuel as FSC and security as SCR, and Schedule 1
writes "billing disputes; notices"): the rules had only understood the practice contract's spellings.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from factkit import CID, Kit  # noqa: E402
from nova.report import build  # noqa: E402
from nova.world import canonical_code, categories  # noqa: E402


class NameTests(unittest.TestCase):
    def test_canonical_code(self):
        cases = {("FSC", "Fuel surcharge"): "FUEL", ("SCR", "Security screening"): "SEC",
                 ("STG", "Storage"): "STOR", ("DGR", "Dangerous goods acceptance"): "DG",
                 ("DI", "Dry ice handling fee"): "DRYICE", ("FRT", "Air freight"): "FRT",
                 ("LPF", "Late payment fee"): "LATE", ("X9", "Final-mile delivery"): "DLV",
                 ("FUEL", "anything"): "FUEL", ("ZZ", "Pallet wrap"): "ZZ", ("CC", "Linehaul cost pass-through"): "COST",
                 ("HM", "Forwarding margin"): "MARGIN"}
        for (code, name), want in cases.items():
            self.assertEqual(canonical_code(code, name), want, (code, name))

    def test_categories(self):
        self.assertEqual(categories(["billing disputes; notices"]), {"billing_disputes", "notices"})
        self.assertEqual(categories(["Waivers", "payment terms"]), {"waivers", "payment_terms"})
        self.assertEqual(categories(["rates and treasury"]), {"rates", "treasury"})
        self.assertEqual(categories(["billing_disputes"]), {"billing_disputes"})


class ChunkedAgreementTests(unittest.TestCase):
    """A long agreement read in page chunks: the first chunk's fact lacks the rate periods a later chunk has.
    Found by the practice grade (INR pickups in P2 were priced at P1 rates)."""

    def test_periods_from_another_chunk_are_used(self):
        k = Kit()
        try:
            k.contract(rate_periods=[])                           # chunk 1: no periods
            doc = "batch_01/0001.eml#MSA.pdf"
            k.fact("contracts", doc, {"contract_id": CID, "kind": "master_agreement", "rate_periods": [
                {"label": "P1", "pickup_from": "2040-01-10", "pickup_to": "2040-07-09"},
                {"label": "P2", "pickup_from": "2040-07-10", "pickup_to": "2041-01-09"}]})   # chunk 2
            k.picked_up("PW7", "2040-08-01")
            inv = k.invoice(7, "2040-08-20", [{"awb": "PW7", "label": "Air freight", "qty": "118", "rate": "4.10",
                                               "amount": "483.80"}])[1]          # P2 rate 4.10: correct
            rep = build(k.store, "2040-09-30", "supervised")
            self.assertNotIn(inv, [i["invoice_id"] for i in rep["findings"] if i["verdict"] != "no_finding"])
            self.assertEqual(set(k.world("2040-09-30").contracts[CID].periods), {"P1", "P2"})
        finally:
            k.close()


class OwnLettersTests(unittest.TestCase):
    """The factkit contract with its codes and Schedule 1 wording rewritten as another carrier might print them."""

    def setUp(self):
        self.k = Kit()
        self.k.contract()
        rename = {"FUEL": "FSC", "SEC": "SCR"}
        with self.k.store.db:
            for fid, kind, raw in self.k.store.db.execute(
                    "SELECT id, kind, data_json FROM facts WHERE kind IN ('charge_codes', 'accessorials', "
                    "'authorised_persons')").fetchall():
                d = json.loads(raw)
                if kind in ("charge_codes", "accessorials") and d.get("code") in rename:
                    d["code"] = rename[d["code"]]
                if kind == "authorised_persons":
                    d["categories"] = ["; ".join(c.replace("_", " ") for c in d["categories"])]
                self.k.store.db.execute("UPDATE facts SET data_json = ? WHERE id = ?", (json.dumps(d), fid))

    def tearDown(self):
        self.k.close()

    def test_fuel_and_recipient_still_found(self):
        # 118 kg at 4.20 vs 4.00 (P1, 100-299.5 kg); fuel 20% (2040-03): (495.60 + 99.12) - (472.00 + 94.40) = 28.32
        self.k.picked_up("PW1", "2040-03-02")
        inv = self.k.invoice(1, "2040-03-20", [
            {"awb": "PW1", "label": "Air freight", "qty": "118", "rate": "4.20", "amount": "495.60"},
            {"awb": "PW1", "label": "Fuel surcharge", "base": "495.60", "pct": "20.00", "amount": "99.12"}])[1]
        rep = build(self.k.store, "2040-04-30", "autonomous")
        item = next(i for i in rep["findings"] if i["invoice_id"] == inv)
        self.assertEqual((item["amount_usd"], item["action"]), ("28.32", "execute:dispute"))

    def test_ocr_noise_on_contract_id(self):
        self.k.picked_up("PW2", "2040-03-02")
        inv = self.k.invoice(2, "2040-03-20", [
            {"awb": "PW2", "label": "Air freight", "qty": "118", "rate": "4.20", "amount": "495.60"}],
            contract=CID + "E")[1]
        rep = build(self.k.store, "2040-04-30", "supervised")
        self.assertEqual(next(i for i in rep["findings"] if i["invoice_id"] == inv)["amount_usd"], "23.60")


if __name__ == "__main__":
    unittest.main()
