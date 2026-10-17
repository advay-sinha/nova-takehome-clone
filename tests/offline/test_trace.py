"""Trace replay: reported amounts recompute from their own traces, and tampering is detected."""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from factkit import Kit  # noqa: E402
from nova.report import build  # noqa: E402
from nova.trace import replay, replay_dir  # noqa: E402


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.k = Kit()
        self.k.contract()
        self.k.picked_up("PW1", "2040-03-02")
        self.inv = self.k.invoice(1, "2040-03-20", [{"awb": "PW1", "label": "Air freight", "qty": "118",
                                                     "rate": "4.20", "amount": "495.60"}])[1]
        build(self.k.store, "2040-04-30", "supervised")
        self.path = next((self.k.store.paths["traces"] / "2040-04-30" / "supervised").glob("overcharge_*.json"))
        self.trace = json.loads(self.path.read_text())

    def tearDown(self):
        self.k.close()

    def test_report_replays(self):
        results = replay_dir(self.k.store.paths["root"], "2040-04-30", "supervised")
        self.assertTrue(results and all(ok for ok, _ in results), results)
        self.assertEqual(self.trace["item"]["amount_usd"], "23.60")       # (4.20 - 4.00) x 118

    def test_tampered_operand_or_amount_is_detected(self):
        t = copy.deepcopy(self.trace)
        t["calculation"]["lines"][0]["correct"] = "480.00"
        self.assertFalse(replay(t)[0])
        t = copy.deepcopy(self.trace)
        t["item"]["amount_usd"] = "23.61"
        self.assertFalse(replay(t)[0])

    def test_unknown_formula_is_refused(self):
        t = copy.deepcopy(self.trace)
        t["calculation"]["formula"] = "__import__('os').system('x')"
        ok, msg = replay(t)
        self.assertFalse(ok)
        self.assertIn("unknown formula", msg)


if __name__ == "__main__":
    unittest.main()
