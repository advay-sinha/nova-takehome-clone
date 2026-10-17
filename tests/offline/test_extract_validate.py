"""Validation of extracted items against their pages. Synthetic pages only; every value here is invented."""
import json
import sys
import unittest
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))

from nova.extract.prompts import render_documents, render_table_pages  # noqa: E402
from nova.extract.schema import FACT_LISTS, FACTS_SCHEMA, TABLE_MAP_SCHEMA  # noqa: E402
from nova.extract.validate import PageIndex, check_item, validate_facts  # noqa: E402

INVOICE = "\n".join([
    "Pellwick Air Cargo", "Charges advice PW-OB-2041-0107", "Document date 15/03/2041 Payable by 14/04/2041",
    "Route Waybill Charge Basis Rate Amount Collected",
    "KLX1-ORB2 PW55120034 Air freight 1,118 kg 4.20 4,695.60 02/03/2041",
    "KLX1-ORB2 PW55120034 Fuel surcharge 4,695.60 21.50% 1,009.55 02/03/2041",
    "Total payable USD 5,705.15"])
SCAN = "PellwickAirCargo\nInvoicePW-OB-2041-0219\nAirfreight 118kg 4.20 495.60\nTotalUSD495.60"
MSA = "\n".join(["10.1 Payment terms. Payment is due 30 days from the date of each invoice.",
                 "10.2 Late fee. Undisputed amounts outstanding for more than 10 days past the due date incur a late "
                 "fee of 1.74% per month or part thereof."])
DOCS = [{"doc": "batch_01/0002.eml#ADV.pdf", "kind": "pdf", "is_scan": False, "pages": [INVOICE]},
        {"doc": "batch_02/0001.eml#SCAN.pdf", "kind": "pdf", "is_scan": True, "pages": [SCAN]},
        {"doc": "batch_01/0001.eml#MSA.pdf", "kind": "pdf", "is_scan": False, "pages": [MSA]}]


def src(doc, quote, page=1):
    return {"doc": doc, "page": page, "quote": quote}


LINE = {"invoice_id": "PW-OB-2041-0107", "line_no": None, "awb": "PW55120034", "house_awb": None,
        "pickup_date": "2041-03-02", "charge_label": "Air freight", "lane": "KLX1-ORB2", "quantity": "1118",
        "unit": "kg", "rate": "4.20", "pct": None, "base_amount": None, "amount": "4695.60", "period_ref": None,
        "refers_to_invoice": None,
        "source": src("batch_01/0002.eml#ADV.pdf", "KLX1-ORB2 PW55120034 Air freight 1,118 kg 4.20 4,695.60")}


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self.index = PageIndex(DOCS)

    def test_good_line_with_separators_and_ddmm_date(self):
        self.assertEqual(check_item(self.index, "invoice_lines", LINE), ("ok", []))

    def test_wrong_amount_is_unverified(self):
        status, issues = check_item(self.index, "invoice_lines", LINE | {"amount": "4659.60"})
        self.assertEqual(status, "unverified")
        self.assertIn("amount", issues[0])

    def test_wrong_date_is_unverified(self):
        status, issues = check_item(self.index, "invoice_lines", LINE | {"pickup_date": "2041-02-03"})
        self.assertEqual(status, "unverified")

    def test_undecidable_date_order_is_flagged(self):
        page = "Advice PW-OB-2041-0300\nKLX1-ORB2 PW55120099 Air freight 10 kg 4.20 42.00 02/03/2041"
        index = PageIndex([{"doc": "d.pdf", "kind": "pdf", "is_scan": False, "pages": [page]}])
        line = LINE | {"quantity": "10", "amount": "42.00", "pickup_date": "2041-03-02",
                       "source": src("d.pdf", "KLX1-ORB2 PW55120099 Air freight 10 kg 4.20 42.00")}
        status, issues = check_item(index, "invoice_lines", line)
        self.assertEqual(status, "unverified")
        self.assertIn("does not show which", issues[0])
        hinted = PageIndex([{"doc": "d.pdf", "kind": "pdf", "is_scan": False, "pages": [page]}], {"d.pdf": "DMY"})
        self.assertEqual(check_item(hinted, "invoice_lines", line), ("ok", []))
        self.assertEqual(check_item(hinted, "invoice_lines", line | {"pickup_date": "2041-02-03"})[0], "unverified")

    def test_live_regressions_sentence_end_date_and_total_on_last_page(self):
        # Both were wrongly 'unverified' in the first live run (H-003).
        email = "From: A <a@x.example>\n\nWe extend the due date of invoice PW-OB-2041-0107 to 2041-04-03.\nThanks"
        inv = ["Invoice PW-OB-2041-0300\nInvoice date 2041-04-18 Due date 2041-06-02\n1 PW1 2041-04-02 Air freight",
               "Subtotal USD 40112.48\nTotal USD 40112.48"]
        index = PageIndex([{"doc": "e.eml", "kind": "eml", "is_scan": False, "pages": [email]},
                           {"doc": "i.pdf", "kind": "pdf", "is_scan": False, "pages": inv}])
        ext = {"invoice_id": "PW-OB-2041-0107", "new_due_date": "2041-04-03", "is_quoted_or_forwarded": False,
               "source": src("e.eml", "extend the due date of invoice PW-OB-2041-0107 to 2041-04-03.")}
        self.assertEqual(check_item(index, "due_date_extensions", ext), ("ok", []))
        self.assertEqual(check_item(index, "due_date_extensions", ext | {"new_due_date": "2041-04-30"})[0], "unverified")
        header = {"invoice_id": "PW-OB-2041-0300", "invoice_date": "2041-04-18", "due_date": "2041-06-02",
                  "total": "40112.48", "source": src("i.pdf", "Invoice date 2041-04-18 Due date 2041-06-02")}
        self.assertEqual(check_item(index, "invoices", header), ("ok", []))
        self.assertEqual(check_item(index, "invoices", header | {"total": "41112.48"})[0], "unverified")

    def test_date_inside_longer_number_not_matched(self):
        index = PageIndex([{"doc": "x.pdf", "kind": "pdf", "is_scan": False,
                            "pages": ["Ref 12041-04-035 and code 2041-04-0399 appear here"]}])
        self.assertIsNotNone(index.date_issue("x.pdf", 1, "2041-04-03"))

    def test_month_name_dash_and_padded_forms(self):
        index = PageIndex([{"doc": "y.pdf", "kind": "pdf", "is_scan": False,
                            "pages": ["Collected 09-Mar-2041, billed Mar 04, 2041, due 7-April-2041"]}])
        for iso in ("2041-03-09", "2041-03-04", "2041-04-07"):
            self.assertIsNone(index.date_issue("y.pdf", 1, iso), iso)
        self.assertIsNotNone(index.date_issue("y.pdf", 1, "2041-03-08"))

    def test_invented_quote_rejected(self):
        bad = LINE | {"source": src("batch_01/0002.eml#ADV.pdf", "KLX1-ORB2 PW55120034 Air freight 1,118 kg 3.90")}
        self.assertEqual(check_item(self.index, "invoice_lines", bad)[0], "rejected")

    def test_foreign_doc_page_and_short_quote_rejected(self):
        for s in (src("batch_09/0001.eml#X.pdf", LINE["source"]["quote"]),
                  src("batch_01/0002.eml#ADV.pdf", LINE["source"]["quote"], page=2),
                  src("batch_01/0002.eml#ADV.pdf", "4,695.60")):
            with self.subTest(s=s):
                self.assertEqual(check_item(self.index, "invoice_lines", LINE | {"source": s})[0], "rejected")

    def test_scan_compared_without_spaces(self):
        line = LINE | {"invoice_id": "PW-OB-2041-0219", "quantity": "118", "amount": "495.60", "pickup_date": None,
                       "source": src("batch_02/0001.eml#SCAN.pdf", "Air freight 118 kg 4.20 495.60")}
        self.assertEqual(check_item(self.index, "invoice_lines", line), ("ok", []))

    def test_contract_blocks(self):
        payment = {"due_days_after_invoice": "30", "late_fee_pct_per_month": "1.74", "grace_days": "10",
                   "compounding": None, "extension_by_category": None,
                   "source": src("batch_01/0001.eml#MSA.pdf", "incur a late fee of 1.74% per month")}
        contract = {"payment": payment, "source": src("batch_01/0001.eml#MSA.pdf", "10.1 Payment terms. Payment is due")}
        self.assertEqual(check_item(self.index, "contracts", contract), ("ok", []))
        wrong = {"payment": payment | {"late_fee_pct_per_month": "1.47"}, "source": contract["source"]}
        status, issues = check_item(self.index, "contracts", wrong)
        self.assertEqual(status, "unverified")
        self.assertIn("payment.late_fee_pct_per_month", issues[0])

    def test_validate_facts_rows(self):
        data = {k: [] for k in FACTS_SCHEMA["properties"]} | {"invoice_lines": [LINE, LINE | {"amount": "1.00"}]}
        jsonschema.validate(data, FACTS_SCHEMA)
        rows = validate_facts(self.index, data, FACT_LISTS)
        self.assertEqual([r["status"] for r in rows], ["ok", "unverified"])
        self.assertEqual(rows[0]["data"]["_source"]["doc"], "batch_01/0002.eml#ADV.pdf")
        self.assertNotIn("source", rows[0]["data"])


class PromptRenderTests(unittest.TestCase):
    def test_documents_labelled_by_doc_and_page(self):
        text = render_documents(DOCS[:2])
        self.assertIn("=== DOCUMENT batch_01/0002.eml#ADV.pdf (pdf, 1 page(s)) ===", text)
        self.assertIn("(scanned: OCR text)", text)
        self.assertIn("--- page 1 ---", text)

    def test_table_sample_numbered(self):
        text = render_table_pages("batch_01/0040.eml#t.xlsx", ["AWB | Event | Date\nX1 | PICKED_UP | 2041-01-02"])
        self.assertIn("1: AWB | Event | Date", text)
        self.assertIn("2: X1 | PICKED_UP | 2041-01-02", text)

    def test_schemas_are_valid_and_compact(self):
        for s in (FACTS_SCHEMA, TABLE_MAP_SCHEMA):
            jsonschema.Draft202012Validator.check_schema(s)
        self.assertLess(len(json.dumps(FACTS_SCHEMA, separators=(",", ":"))), 20000)   # CLI argument headroom


if __name__ == "__main__":
    unittest.main()
