"""The unseen-world expected-answer oracle against hand-worked glossary arithmetic (no harness code involved)."""
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals" / "unseen_worlds"))

import oracle as O  # noqa: E402


class OracleTests(unittest.TestCase):
    def test_rounding_is_half_up_away_from_zero(self):
        self.assertEqual(O.r2("2.345"), Decimal("2.35"))
        self.assertEqual(O.r2("2.344999"), Decimal("2.34"))
        self.assertEqual(O.r2("-2.345"), Decimal("-2.35"))

    def test_line_and_percentage_on_a_rounded_base(self):
        freight = O.line("4.35", "187.5")          # 815.625 -> 815.63
        self.assertEqual(freight, Decimal("815.63"))
        self.assertEqual(O.pct_of("17.25", freight), Decimal("140.70"))   # 140.696175 -> 140.70

    def test_finding_is_never_negative(self):
        self.assertEqual(O.finding(["100.00", "18.00"], ["90.00", "16.20"]), Decimal("11.80"))
        self.assertEqual(O.finding(["90.00"], ["100.00"]), Decimal("0.00"))

    def test_inr_converts_once_per_finding(self):
        # per line would be 101.11/83.40=1.2124 -> 1.21 and 101.11 -> 1.21: 2.42; once: 202.22/83.40=2.4247 -> 2.42
        self.assertEqual(O.inr_to_usd("202.22", "83.40"), Decimal("2.42"))
        self.assertEqual(O.inr_to_usd("1000.00", "83.25"), Decimal("12.01"))   # 12.0120...

    def test_conflict_range(self):
        self.assertEqual(O.conflict_range("1200.00", "1100.00", "1150.00"), [Decimal("50.00"), Decimal("100.00")])
        self.assertEqual(O.conflict_range("1000.00", "1100.00", "950.00"), [Decimal("0.00"), Decimal("50.00")])

    def test_late_fee_months_respect_grace_and_ceiling(self):
        due = date(2043, 3, 1)
        self.assertEqual(O.late_fee_months(date(2043, 3, 6), due, 5), 0)
        self.assertEqual(O.late_fee_months(date(2043, 3, 7), due, 5), 1)
        self.assertEqual(O.late_fee_months(date(2043, 4, 1), due, 0), 2)      # 31 days -> 2 months

    def test_compounding_and_simple_late_fees(self):
        self.assertEqual(O.late_fee("1000.00", "1.5", 2, compounding=False), Decimal("30.00"))
        self.assertEqual(O.late_fee("1000.00", "1.5", 2, compounding=True), Decimal("30.23"))   # 15.00 + 15.225->15.23

    def test_rebate_highest_tier_applies_to_all_spend(self):
        tiers = [("30000", "2"), ("60000", "4")]
        self.assertEqual(O.rebate("59999.99", tiers), Decimal("1200.00"))
        self.assertEqual(O.rebate("60000.00", tiers), Decimal("2400.00"))
        self.assertEqual(O.rebate("29999.99", tiers), Decimal("0.00"))

    def test_margin_step_down(self):
        # bases 2,000.00 and 3,333.33 billed at 6% (120.00, 200.00), stepped to 4%: 80.00 and 133.33
        self.assertEqual(O.margin_step_down([("2000.00", "120.00"), ("3333.33", "200.00")], "4"), Decimal("106.67"))

    def test_windows(self):
        as_of = date(2043, 6, 30)
        self.assertTrue(O.in_window(date(2043, 8, 29), as_of, 0, 60))
        self.assertFalse(O.in_window(date(2043, 8, 30), as_of, 0, 60))
        self.assertFalse(O.in_window(as_of, as_of, 0, 14, lo_strict=True))
        self.assertTrue(O.in_window(date(2043, 7, 14), as_of, 0, 14, lo_strict=True))


if __name__ == "__main__":
    unittest.main()
