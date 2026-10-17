"""Document arithmetic checks: extraction problems versus documents that do not add up as printed. Invented values."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness"))

from nova.extract.constraints import check_document  # noqa: E402
from nova.money import dec, money_str, q2  # noqa: E402


def line(n, qty=None, rate=None, amount=None, pct=None, base=None, label="Air freight"):
    return {"line_no": str(n), "quantity": qty, "rate": rate, "amount": amount, "pct": pct, "base_amount": base,
            "charge_label": label, "awb": "PW1"}


GOOD = [line(1, "241", "6.01", "1448.41"), line(2, pct="20.16", base="1448.41", amount="292.00", label="Fuel"),
        line(3, "1", "116.13", "116.13", label="Delivery fee")]


class MoneyTests(unittest.TestCase):
    def test_half_up_and_parsing(self):
        self.assertEqual(q2(dec("0.125")), dec("0.13"))
        self.assertEqual(q2(dec("2.675")), dec("2.68"))          # Decimal, so no binary-float surprise
        self.assertEqual(dec("USD 1,243.96"), dec("1243.96"))
        self.assertEqual(dec("18.38%"), dec("18.38"))
        self.assertIsNone(dec("n/a"))
        self.assertEqual(money_str(dec("3")), "3.00")


class ConstraintTests(unittest.TestCase):
    def test_consistent(self):
        header = {"subtotal": "1856.54", "tax": "0.00", "total": "1856.54"}
        self.assertEqual(check_document(header, GOOD, False)["status"], "consistent")

    def test_tax_line_extracted_as_a_line(self):
        # H-003: lines included a GST line, so they add up to the total, not the subtotal
        lines = GOOD + [line(4, pct="18.00", base="116.13", amount="20.90", label="GST")]
        header = {"subtotal": "1856.54", "tax": "20.90", "total": "1877.44"}
        self.assertEqual(check_document(header, lines, False)["status"], "consistent")

    def test_skipped_line_is_an_extraction_problem(self):
        header = {"subtotal": "1856.54", "tax": None, "total": "1856.54"}
        res = check_document(header, GOOD[:2], False)
        self.assertEqual(res["status"], "extraction_suspect")
        self.assertIn("all line amounts and the totals", res["recheck_fields"])

    def test_printed_line_that_does_not_add_up(self):
        # text layer, totals agree with the lines: the carrier printed it that way; never "corrected"
        lines = [line(1, "241", "6.69", "1612.30")]
        res = check_document({"subtotal": "1612.30", "tax": None, "total": "1612.30"}, lines, False)
        self.assertEqual(res["status"], "document_inconsistent")
        self.assertEqual(res["recheck_fields"], [])

    def test_ocr_line_mismatch_is_rechecked(self):
        lines = [line(1, "241", "6.69", "1612.30")]
        res = check_document({"subtotal": "1612.30", "tax": None, "total": "1612.30"}, lines, True)
        self.assertEqual(res["status"], "extraction_suspect")
        self.assertEqual(res["recheck_fields"], ["line 1"])

    def test_minimum_charge_and_missing_operands_skipped(self):
        lines = [line(1, "10", "3.33", "91.00", label="Air freight (minimum charge)"), line(2, None, None, "45.40")]
        self.assertEqual(check_document(None, lines, False)["status"], "consistent")

    def test_subtotal_tax_total_disagree(self):
        res = check_document({"subtotal": "100.00", "tax": "18.00", "total": "120.00"},
                             [line(1, "1", "100.00", "100.00")], False)
        self.assertEqual(res["status"], "extraction_suspect")


if __name__ == "__main__":
    unittest.main()
