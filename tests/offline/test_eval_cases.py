"""The original eval cases are well formed (no harness or model run here; the real results come from make eval).

Checks: every case's mailbox and feedback exist; every document reads through the grader's text layer (only the one
scan has no text); an item equal to `expect` passes the runner's own comparison and a changed one fails; the
mailboxes are reproducible from evals/build_mailboxes.py.
"""
import json
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "grader"), str(ROOT / "evals")]

from extract import Mailbox  # noqa: E402
import run_evals  # noqa: E402

CASES = sorted(f for f in (ROOT / "evals" / "cases").glob("*.yaml") if not f.name.startswith("sample_"))


def ideal_item(exp: dict) -> dict:
    item = dict(exp["key"]) | {"verdict": exp["verdict"], "amount_usd": exp.get("amount_usd"),
                               "amount_range": exp.get("amount_range"), "action": exp.get("action", "none"),
                               "deadline": exp.get("deadline")}
    if exp.get("missing_doc"):
        item["missing_doc"] = {"name": f"the {exp['missing_doc']} from the sender"}
    return item


class EvalCaseTests(unittest.TestCase):
    def test_at_least_ten_original_cases(self):
        self.assertGreaterEqual(len(CASES), 10)
        self.assertGreaterEqual(len({yaml.safe_load(f.read_text())["mailbox"] for f in CASES}), 10)

    def test_mailboxes_feedback_and_text_layer(self):
        for f in CASES:
            case = yaml.safe_load(f.read_text())
            with self.subTest(case=f.name):
                box = ROOT / case["mailbox"]
                self.assertTrue(sorted(box.glob("batch_*")), "no batches")
                for batch, path in (case.get("feedback") or {}).items():
                    self.assertTrue((box / batch).is_dir())
                    self.assertEqual(json.loads((ROOT / path).read_text())["after_batch"], batch)
                mb = Mailbox(box)
                for eml in sorted(box.rglob("*.eml")):
                    doc = eml.relative_to(box).as_posix()
                    self.assertTrue(mb.pages(doc)[0][0].strip())
                mb._index()
                docs = [d for entries in mb._by_name.values() for d, _ in entries]
                self.assertTrue(docs)
                scans = [d for d in docs if not any(p.strip() for p in mb.pages(d)[0])]
                self.assertLessEqual(len(scans), 1, scans)

    def test_mailboxes_rebuild_byte_identical(self):
        import tempfile
        import build_mailboxes as B
        with tempfile.TemporaryDirectory() as tmp:
            saved, B.OUT = B.OUT, Path(tmp)
            try:
                for box in B.build():
                    box.write()
            finally:
                B.OUT = saved
            built = {p.relative_to(tmp).as_posix(): p.read_bytes() for p in Path(tmp).rglob("*.eml")}
        held = {p.relative_to(B.OUT).as_posix(): p.read_bytes() for p in B.OUT.rglob("*.eml")}
        self.assertEqual(sorted(built), sorted(held))
        self.assertEqual([k for k in built if built[k] != held[k]], [])

    def test_expectations_are_checkable(self):
        for f in CASES:
            case = yaml.safe_load(f.read_text())
            exp = case["expect"]
            with self.subTest(case=f.name):
                self.assertEqual(run_evals.check(case, ideal_item(exp)), [])
                if exp["verdict"] == "no_finding":
                    self.assertEqual(run_evals.check(case, None), [])
                    self.assertNotEqual(run_evals.check(case, ideal_item(exp) | {"verdict": "finding",
                                                                                 "amount_usd": "1.00"}), [])
                else:
                    self.assertNotEqual(run_evals.check(case, None), [])
                if exp.get("amount_usd"):
                    off = f"{float(exp['amount_usd']) + 0.02:.2f}"
                    self.assertNotEqual(run_evals.check(case, ideal_item(exp) | {"amount_usd": off}), [])
                if exp.get("action", "none") not in ("none", "escalate"):
                    self.assertNotEqual(run_evals.check(case, ideal_item(exp) | {"action": "human_review"}), [])


if __name__ == "__main__":
    unittest.main()
