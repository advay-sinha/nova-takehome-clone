"""Reader parity with the grader's text layer, UTC receipt times and OCR line grouping. Synthetic data only."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import INVOICE_LINE, build_mailbox  # noqa: E402
from nova.ocr import group_lines  # noqa: E402
from nova.reader import read_batch, utc_iso  # noqa: E402

from grader.extract import Mailbox  # noqa: E402  (tests may use the grader; the harness never does)


class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.mailbox = build_mailbox(Path(cls.tmp.name))
        cls.docs = {d["row"]["doc"]: d for b in ("batch_01", "batch_02") for d in read_batch(cls.mailbox / b)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pages_match_grader(self):
        grader = Mailbox(self.mailbox)
        for doc, d in self.docs.items():
            pages, scan = grader.pages(doc)
            with self.subTest(doc=doc):
                if d["row"]["is_scan"]:
                    self.assertTrue(scan)
                    self.assertEqual(len(d["pages"]), len(pages))
                else:
                    self.assertEqual([p["text"] for p in d["pages"]], pages)

    def test_quote_resolves_where_reader_puts_it(self):
        grader = Mailbox(self.mailbox)
        self.assertIsNone(grader.check("batch_01/0002.eml#PW-OB-2041-0107.pdf", 1, INVOICE_LINE))
        self.assertIn(INVOICE_LINE, self.docs["batch_01/0002.eml#PW-OB-2041-0107.pdf"]["pages"][0]["text"])

    def test_receipt_is_utc(self):
        self.assertEqual(self.docs["batch_01/0002.eml"]["row"]["received_at"], "2041-03-05T21:40:00Z")
        self.assertEqual(utc_iso("Mon, 07 Jan 2041 09:15:00"), "2041-01-07T09:15:00Z")  # no zone: UTC
        self.assertIsNone(utc_iso("not a date"))

    def test_resend_is_a_separate_occurrence(self):
        a = self.docs["batch_01/0002.eml#PW-OB-2041-0107.pdf"]["row"]
        b = self.docs["batch_01/0004.eml#PW-OB-2041-0107.pdf"]["row"]
        self.assertEqual(a["sha256"], b["sha256"])
        self.assertNotEqual(a["received_at"], b["received_at"])

    def test_attachment_metadata(self):
        row = self.docs["batch_01/0003.eml#ap-register-2041-03-29.xlsx"]["row"]
        self.assertEqual((row["kind"], row["page_count"], row["email_doc"]), ("xlsx", 1, "batch_01/0003.eml"))
        self.assertEqual(self.docs["batch_01/0001.eml"]["row"]["sender_addr"], "lena.sorell@ostravabio.example")

    def test_scan_is_read_by_ocr(self):
        d = self.docs["batch_02/0001.eml#PW-OB-2041-0219.pdf"]
        self.assertEqual(d["row"]["is_scan"], 1)
        self.assertEqual(d["pages"][0]["method"], "ocr")
        squashed = d["pages"][0]["text"].replace(" ", "")
        self.assertIn("PW-OB-2041-0219", squashed)
        self.assertIn("812.40", squashed)


class GroupLinesTests(unittest.TestCase):
    @staticmethod
    def box(x0, y0, x1, y1):
        return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]

    def test_rows_and_order(self):
        results = [(self.box(300, 100, 380, 120), "495.60", 0.98),
                   (self.box(20, 102, 120, 121), "Airfreight", 0.95),
                   (self.box(20, 140, 90, 160), "Total", 0.99),
                   (self.box(130, 99, 200, 119), "118kg", 0.90)]
        lines = group_lines(results)
        self.assertEqual([ln["text"] for ln in lines], ["Airfreight 118kg 495.60", "Total"])
        self.assertEqual(lines[0]["score"], 0.9)

    def test_empty(self):
        self.assertEqual(group_lines([]), [])
        self.assertEqual(group_lines(None), [])


if __name__ == "__main__":
    unittest.main()
