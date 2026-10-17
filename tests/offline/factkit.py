"""Build a state store of invented documents and facts directly, for rule tests (no extraction, no model).

All names, lanes, ids, rates and dates here are made up for the tests and match no supplied mailbox."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness"))

from nova.store import Store  # noqa: E402
from nova.world import World  # noqa: E402

CARRIER = "PW-US"
RATES = "rhea.voss@pellwick.example"
KAM = "omar.lind@pellwick.example"
WAIVERS = "ines.duarte@pellwick.example"
TREASURY = "kit.amari@pellwick.example"
CID = "PW-OB-EXP-07"


class Kit:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "state")
        self.n = 0

    def close(self):
        self.store.close()
        self.tmp.cleanup()

    def doc(self, doc: str, received: str, sender: str = "billing@pellwick.example", kind: str = "other") -> str:
        email = doc.split("#")[0]
        with self.store.db:
            for d in {email, doc}:
                self.store.db.execute(
                    "INSERT OR IGNORE INTO documents (doc, batch, email_doc, kind, name, sha256, received_at, sender_addr,"
                    " page_count) VALUES (?,?,?,?,?,?,?,?,1)",
                    (d, d.split("/")[0], email, "eml" if d == email else "pdf", d.rsplit("/", 1)[-1], d,
                     f"{received}T09:00:00Z", sender))
            self.store.set_doc_kind(doc, kind, None, "test")
        return doc

    def fact(self, kind: str, doc: str, data: dict, quote: str | None = None, status: str = "ok") -> dict:
        self.n += 1
        quote = quote or f"{kind} quote number {self.n:04d} for the test"
        row = {"kind": kind, "doc": doc, "page": 1, "quote": quote,
               "data": data | {"_source": {"doc": doc, "page": 1, "quote": quote}}, "status": status, "issues": []}
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO facts (unit, kind, doc, page, quote, data_json, status, issues_json, origin) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"test:{self.n}", kind, doc, 1, quote, __import__("json").dumps(row["data"]), status, "[]", "test"))
        return data

    def world(self, as_of: str) -> World:
        return World(self.store, as_of)

    # ---- a standard invented contract ----------------------------------------------------------------------------
    def contract(self, received="2040-01-05", **over):
        doc = self.doc("batch_01/0001.eml#MSA.pdf", received, "lena.sorell@ostravabio.example", "contract")
        msa = {"contract_id": CID, "kind": "master_agreement", "amends_contract_id": None, "signed": True,
               "effective_date": "2040-01-10", "carrier_code": CARRIER, "shipper_code": "OB-US", "currency": "USD",
               "rate_periods": [{"label": "P1", "pickup_from": "2040-01-10", "pickup_to": "2040-07-09"},
                                {"label": "P2", "pickup_from": "2040-07-10", "pickup_to": "2041-01-09"}],
               "precedence": {"later_amendment_prevails": True, "rate_notice_vs_amendment_unranked": True},
               "pricing_rules": {"dg_dry_ice_rule": "Dry ice used only as refrigerant does not attract the DG fee",
                                 "delivery_fee_rule": "payable only where the Carrier delivers",
                                 "customs_rule": "for the Shipper's account unless the Carrier's documents caused it",
                                 "storage_free_days": "3"},
               "term": {"initial_term_end": "2041-01-09", "auto_renews": False},
               "payment": {"due_days_after_invoice": "30", "late_fee_pct_per_month": "1.50", "grace_days": "5",
                           "compounding": True},
               "amendment_changes": []} | over
        self.fact("contracts", doc, msa)
        for lane, rows in {"KLX1-ORB2": [("0", "44.5", "5.10", "5.20"), ("45", "99.5", "4.60", "4.70"),
                                         ("100", "299.5", "4.00", "4.10"), ("300", None, "3.50", "3.60")]}.items():
            self.fact("rate_rows", doc, {"contract_id": CID, "lane": lane, "band": "minimum charge",
                                         "band_min_kg": None, "band_max_kg": None, "is_minimum_charge": True,
                                         "period_label": "P1", "rate": "80.00"})
            for lo, hi, p1, p2 in rows:
                for label, rate in (("P1", p1), ("P2", p2)):
                    self.fact("rate_rows", doc, {"contract_id": CID, "lane": lane,
                                                 "band": f"{lo}-{hi} kg" if hi else f"{lo}+ kg", "band_min_kg": lo,
                                                 "band_max_kg": hi, "is_minimum_charge": False, "period_label": label,
                                                 "rate": rate})
        for month, pct in (("2040-03", "20.00"), ("2040-09", "21.00"), ("2040-10", "22.00")):
            self.fact("fuel_rows", doc, {"contract_id": CID, "month": month, "pct": pct})
        for code, name, fee, basis, cond in (("SEC", "Security surcharge", "0.15", "per chargeable kg", None),
                                             ("DG", "Dangerous goods fee", "120.00", "per shipment", None),
                                             ("DRYICE", "Dry ice handling fee", "40.00", "per shipment", None),
                                             ("DLV", "Delivery fee", "100.00", "per shipment", None),
                                             ("STOR", "Storage", "25.00", "per storage day", None),
                                             ("PEAK", "Peak season surcharge", "0.30", "per chargeable kg",
                                              "for pickups in September to November only")):
            self.fact("accessorials", doc, {"contract_id": CID, "code": code, "name": name, "fee": fee,
                                            "currency": "USD", "basis": basis, "condition": cond})
        for code, name, aliases in (("FRT", "Air freight", ["Express freight"]), ("FUEL", "Fuel surcharge", ["FSC"]),
                                    ("SEC", "Security surcharge", ["Screening fee"]),
                                    ("DG", "Dangerous goods fee", ["DG handling"]),
                                    ("DRYICE", "Dry ice handling fee", []), ("DLV", "Delivery fee", []),
                                    ("STOR", "Storage", []), ("PEAK", "Peak season surcharge", ["PSS"]),
                                    ("TAX", "Sales tax", ["GST"]), ("LATE", "Late payment fee", ["Late fee"])):
            self.fact("charge_codes", doc, {"contract_id": CID, "code": code, "name": name, "aliases": aliases})
        for name, email, cats in (("Rhea Voss", RATES, ["rates"]), ("Omar Lind", KAM, ["notices", "billing_disputes"]),
                                  ("Ines Duarte", WAIVERS, ["waivers", "payment_terms"]),
                                  ("Kit Amari", TREASURY, ["treasury"])):
            self.fact("authorised_persons", doc, {"contract_id": CID, "name": name, "title": "Lead", "party": CARRIER,
                                                  "categories": cats, "email": email})
        return doc

    def invoice(self, n: int, received: str, lines: list[dict], invoice_date: str | None = None, currency="USD",
                contract=CID, invoice_id=None):
        invoice_id = invoice_id or f"PW-OB-2040-{n:04d}"
        doc = self.doc(f"batch_01/{n:04d}.eml#{invoice_id}.pdf", received, kind="invoice")
        total = sum(float(ln["amount"]) for ln in lines)
        self.fact("invoices", doc, {"invoice_id": invoice_id, "doc_type": "invoice", "contract_id": contract,
                                    "invoice_date": invoice_date or received, "due_date": None, "currency": currency,
                                    "subtotal": f"{total:.2f}", "tax": "0.00", "total": f"{total:.2f}"})
        for i, ln in enumerate(lines, 1):
            self.fact("invoice_lines", doc, {"invoice_id": invoice_id, "line_no": str(i), "awb": ln.get("awb"),
                                             "lane": ln.get("lane", "KLX1-ORB2"), "pickup_date": ln.get("pickup"),
                                             "charge_label": ln["label"], "quantity": ln.get("qty"),
                                             "rate": ln.get("rate"), "pct": ln.get("pct"),
                                             "base_amount": ln.get("base"), "amount": ln["amount"]},
                      quote=f"{i} {ln.get('awb')} {ln['label']} {ln['amount']} line of {invoice_id}")
        return doc, invoice_id

    def picked_up(self, awb: str, day: str, received: str | None = None):
        doc = self.doc(f"batch_01/0900.eml#tracking-{awb}.xlsx", received or day, "ops@ostravabio.example", "table")
        self.fact("tracking_events", doc, {"awb": awb, "event": "PICKED_UP", "date": day, "station": "KLX1"},
                  quote=f"{awb} | PICKED_UP | {day} | KLX1 | -")
