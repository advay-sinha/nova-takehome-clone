"""Extraction planning and running on the synthetic mailbox with an explicit in-process mock model."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fake_claude  # noqa: E402
from fixtures import INVOICE_LINE, build_mailbox  # noqa: E402
from mock_llm import MockProvider  # noqa: E402
from nova.extract.run import plan_batch, run_pending  # noqa: E402
from nova.llm import LLMUnavailable, load_config  # noqa: E402
from nova.reader import read_batch  # noqa: E402
from nova.store import Store  # noqa: E402

CFG = load_config()


class ExtractRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        mailbox = build_mailbox(base / "mailbox", extra=True)
        self.store = Store(base / "state")
        for it in read_batch(mailbox / "batch_01"):
            self.store.put_blob(it["row"]["sha256"], it["data"])
            with self.store.db:
                self.store.upsert_document(it["row"], it["pages"])
        with self.store.db:
            plan_batch(self.store, "batch_01")
        self.mock = MockProvider(lambda req: fake_claude.respond(req.user, req.schema))
        # never read the developer's harness/.local-llm.json (it may name a shared cache)
        self.local = base / "local-llm.json"
        self.local.write_text("{}")
        self._env = os.environ.get("NOVA_LOCAL_LLM")
        os.environ["NOVA_LOCAL_LLM"] = str(self.local)

    def tearDown(self):
        if self._env is None:
            os.environ.pop("NOVA_LOCAL_LLM", None)
        else:
            os.environ["NOVA_LOCAL_LLM"] = self._env
        self.store.close()
        self.tmp.cleanup()

    def unit(self, name):
        return self.store.db.execute("SELECT * FROM extraction_units WHERE unit = ?", (name,)).fetchone()

    def test_units_planned(self):
        units = {r["unit"]: r["kind"] for r in self.store.db.execute("SELECT unit, kind FROM extraction_units")}
        self.assertEqual(units["clone:batch_01/0004.eml#PW-OB-2041-0107.pdf"], "clone")
        self.assertEqual(units["long:batch_01/0005.eml#MSA-PW-OB-EXP-08.pdf@1-4"], "long")    # 5 pages: 2 chunks
        self.assertEqual(units["long:batch_01/0005.eml#MSA-PW-OB-EXP-08.pdf@5-5"], "long")
        self.assertEqual(units["table:batch_01/0006.eml#tracking-2041-03.xlsx"], "table")
        self.assertEqual(json.loads(self.unit("bundle:batch_01/0002.eml")["docs_json"]),
                         ["batch_01/0002.eml", "batch_01/0002.eml#PW-OB-2041-0107.pdf"])
        self.assertEqual(json.loads(self.unit("bundle:batch_01/0004.eml")["docs_json"]), ["batch_01/0004.eml"])
        with self.store.db:
            self.assertEqual(plan_batch(self.store, "batch_01"), 0)       # planning is idempotent

    def test_run_stores_validated_facts_clones_and_table_rows(self):
        stats = run_pending(self.store, lambda: self.mock, CFG, 300)
        self.assertEqual(stats.get("failed", 0), 0)
        self.assertEqual(stats["cloned"], 1)
        lines = self.store.facts("invoice_lines")
        by_doc = {r["doc"]: r for r in lines}
        first = by_doc["batch_01/0002.eml#PW-OB-2041-0107.pdf"]
        self.assertEqual((first["status"], first["quote"]), ("ok", INVOICE_LINE))
        clone = by_doc["batch_01/0004.eml#PW-OB-2041-0107.pdf"]       # resend: same facts, its own path
        self.assertEqual((clone["origin"], json.loads(clone["data_json"])["_source"]["doc"]),
                         ("clone", "batch_01/0004.eml#PW-OB-2041-0107.pdf"))
        events = self.store.facts("tracking_events")
        self.assertEqual(len(events), 70)
        self.assertEqual(json.loads(events[0]["data_json"])["date"], "2041-03-01")
        self.assertTrue(all(e["status"] == "ok" for e in events))
        self.assertEqual(self.unit("long:batch_01/0005.eml#MSA-PW-OB-EXP-08.pdf@5-5")["status"], "done")
        chunk_inputs = [r.user for r in self.mock.calls
                        if "=== DOCUMENT batch_01/0005.eml#MSA-PW-OB-EXP-08.pdf" in r.user]
        self.assertEqual(len(chunk_inputs), 2)
        self.assertTrue(any("--- page 5 ---" in t and "--- page 1 ---" not in t for t in chunk_inputs))
        kinds = dict(self.store.db.execute("SELECT doc, kind FROM doc_kinds"))
        self.assertEqual(kinds["batch_01/0002.eml#PW-OB-2041-0107.pdf"], "invoice")

    def test_budget_leaves_pending_then_resumes(self):
        stats = run_pending(self.store, lambda: self.mock, CFG, 0)
        self.assertGreater(stats["pending"], 0)
        self.assertEqual(self.mock.calls, [])
        self.assertEqual(self.unit("bundle:batch_01/0002.eml")["status"], "pending")
        run_pending(self.store, lambda: self.mock, CFG, 300)
        self.assertEqual(self.store.units(("pending", "failed")), [])

    def test_cache_avoids_repeat_calls(self):
        run_pending(self.store, lambda: self.mock, CFG, 300)
        calls = len(self.mock.calls)
        with self.store.db:
            self.store.db.execute("UPDATE extraction_units SET status = 'pending', attempts = 0")
        run_pending(self.store, lambda: self.mock, CFG, 300)
        self.assertEqual(len(self.mock.calls), calls)
        self.assertEqual(self.store.units(("pending", "failed")), [])

    def test_shared_cache_reused_by_a_fresh_state_only_when_configured(self):
        shared = Path(self.tmp.name) / "shared" / "cache.sqlite3"
        self.local.write_text(json.dumps({"shared_cache": str(shared)}))
        run_pending(self.store, lambda: self.mock, CFG, 300)
        first = len(self.mock.calls)
        self.assertGreater(first, 0)
        other = Store(Path(self.tmp.name) / "state2")
        try:
            for it in read_batch(Path(self.tmp.name) / "mailbox" / "batch_01"):
                other.put_blob(it["row"]["sha256"], it["data"])
                with other.db:
                    other.upsert_document(it["row"], it["pages"])
            with other.db:
                plan_batch(other, "batch_01")
            stats = run_pending(other, lambda: self.mock, CFG, 300)
            self.assertEqual(len(self.mock.calls), first)                 # every answer came from the shared file
            self.assertEqual(other.units(("pending", "failed")), [])
            self.assertGreater(stats.get("facts", 0), 0)
            self.local.write_text("{}")                                   # not configured: nothing shared
            third = Store(Path(self.tmp.name) / "state3")
            for it in read_batch(Path(self.tmp.name) / "mailbox" / "batch_01"):
                third.put_blob(it["row"]["sha256"], it["data"])
                with third.db:
                    third.upsert_document(it["row"], it["pages"])
            with third.db:
                plan_batch(third, "batch_01")
            run_pending(third, lambda: self.mock, CFG, 300)
            self.assertGreater(len(self.mock.calls), first)
            third.close()
        finally:
            other.close()

    def test_usage_limit_stops_calls_and_keeps_units_pending(self):
        from nova.llm import LLMLimited

        def limited(req):
            raise LLMLimited("CLI usage/rate limit: You've hit your usage limit")

        blocked = MockProvider(limited)
        stats = run_pending(self.store, lambda: blocked, dict(CFG, concurrency={"mock": 1}), 300)
        self.assertEqual(len(blocked.calls), 1)                          # no further calls after the first limit
        self.assertEqual(stats.get("failed", 0), 0)
        rows = self.store.db.execute("SELECT status, attempts FROM extraction_units WHERE kind != 'clone'").fetchall()
        self.assertTrue(rows and all(r["status"] == "pending" and r["attempts"] == 0 for r in rows), [tuple(r) for r in rows])
        run_pending(self.store, lambda: self.mock, CFG, 300)              # the limit resets: everything completes
        self.assertEqual(self.store.units(("pending", "failed")), [])

    def test_no_back_end_fails_loudly_and_keeps_work(self):
        def unavailable():
            raise LLMUnavailable("no back end")
        with self.assertRaises(LLMUnavailable):
            run_pending(self.store, unavailable, CFG, 300)
        self.assertEqual(self.unit("bundle:batch_01/0002.eml")["status"], "pending")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 12)  # 6 emails + 6

    def test_bad_answers_fail_with_bounded_retries(self):
        bad = MockProvider(lambda req: {"unexpected": True})
        stats = run_pending(self.store, lambda: bad, CFG, 300)
        self.assertGreater(stats["failed"], 0)
        first = len(bad.calls)
        run_pending(self.store, lambda: bad, CFG, 300)                # a later step retries each failed unit once
        self.assertEqual(len(bad.calls), 2 * first)
        self.assertEqual(self.unit("bundle:batch_01/0002.eml")["attempts"], 2)
        run_pending(self.store, lambda: bad, CFG, 300)
        self.assertEqual(len(bad.calls), 2 * first)                   # attempts exhausted: no further calls

    def test_each_unit_is_saved_as_soon_as_it_completes(self):
        answered = []

        def dies_after_three(req):
            if len(answered) == 3:
                raise RuntimeError("process killed")       # stands in for the grader's step timeout
            answered.append(req)
            return fake_claude.respond(req.user, req.schema)
        cfg = CFG | {"concurrency": {"mock": 1}}
        with self.assertRaises(RuntimeError):
            run_pending(self.store, lambda: MockProvider(dies_after_three), cfg, 300)
        done = self.store.db.execute("SELECT COUNT(*) FROM extraction_units WHERE status = 'done' "
                                     "AND kind != 'clone'").fetchone()[0]
        cached = self.store.db.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
        self.assertEqual((done, cached), (3, 3))                # nothing finished before the crash is lost
        run_pending(self.store, lambda: self.mock, CFG, 300)     # the next step only calls for the rest
        self.assertEqual(len(self.mock.calls), 9 - 3)
        self.assertEqual(self.store.units(("pending", "failed")), [])

    def test_progress_is_logged(self):
        import contextlib
        import io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            run_pending(self.store, lambda: self.mock, CFG, 300)
        text = err.getvalue()
        self.assertIn("extract: 9 unit(s), 0 from cache, 9 to call", text)
        self.assertRegex(text, r"extract 9/9 done \S+ \(\d+\.\d s, \d+ facts\)")

    def _misread(self, recheck_answer):
        """Facts call misreads the invoice line amount (495.60 -> 459.60, a value also printed on the page) and adds
        the header; the recheck answers with `recheck_answer(correct_output)`."""
        doc = "batch_01/0002.eml#PW-OB-2041-0107.pdf"

        def respond(req):
            out = fake_claude.respond(req.user, req.schema)
            header = {"invoice_id": "PW-OB-2041-0107", "doc_type": "invoice", "issuer": None, "bill_to": None,
                      "contract_id": None, "invoice_date": "2041-03-05", "due_date": None, "currency": "USD",
                      "subtotal": None, "tax": None, "total": "495.60", "marked_as": None,
                      "source": {"doc": doc, "page": 1, "quote": "Total USD 495.60"}}
            if req.purpose == "recheck":
                return recheck_answer({"invoices": [header], "invoice_lines": out["invoice_lines"]})
            if f"=== DOCUMENT {doc}" in req.user:
                out["invoices"] = [header]
                for ln in out["invoice_lines"]:
                    ln["amount"] = "459.60"
            return out
        return doc, MockProvider(respond)

    def test_misread_is_rechecked_once_and_replaced(self):
        doc, mock = self._misread(lambda good: good)
        run_pending(self.store, lambda: mock, CFG, 300)
        check = self.store.doc_check(doc)
        self.assertEqual((check["status"], check["recheck"]), ("consistent", "accepted"))
        self.assertIn("459.60", json.loads(check["recheck_detail_json"])["before"][0])
        header, lines = self.store.billing_facts(doc)
        self.assertEqual([ln["amount"] for ln in lines], ["495.60"])          # only the re-read facts are used
        old = self.store.db.execute("SELECT COUNT(*) FROM facts WHERE doc = ? AND status = 'superseded'",
                                    (doc,)).fetchone()[0]
        self.assertEqual(old, 2)                                               # originals kept for the record
        self.assertEqual(sum(r.purpose == "recheck" for r in mock.calls), 1)

    def test_failed_recheck_keeps_original_and_is_not_repeated(self):
        def still_wrong(good):
            for ln in good["invoice_lines"]:
                ln["amount"] = "459.60"
            return good
        doc, mock = self._misread(still_wrong)
        run_pending(self.store, lambda: mock, CFG, 300)
        check = self.store.doc_check(doc)
        self.assertEqual((check["status"], check["recheck"]), ("extraction_suspect", "unresolved"))
        _, lines = self.store.billing_facts(doc)
        self.assertEqual([ln["amount"] for ln in lines], ["459.60"])          # never silently replaced
        with self.store.db:
            self.store.db.execute("UPDATE extraction_units SET status = 'pending', attempts = 0 "
                                  "WHERE kind != 'recheck'")
        run_pending(self.store, lambda: mock, CFG, 300)
        self.assertEqual(sum(r.purpose == "recheck" for r in mock.calls), 1)  # at most one recheck per document

    def test_invented_quote_is_rejected(self):
        def lying(req):
            out = fake_claude.respond(req.user, req.schema)
            for line in out.get("invoice_lines", []):
                line["source"]["quote"] = line["source"]["quote"].replace("495.60", "395.60")
            return out
        run_pending(self.store, lambda: MockProvider(lying), CFG, 300)
        rows = self.store.db.execute("SELECT status FROM facts WHERE kind = 'invoice_lines'").fetchall()
        self.assertTrue(rows and all(r["status"] == "rejected" for r in rows))
        self.assertEqual(self.store.facts("invoice_lines"), [])        # rejected facts never reach the rules


if __name__ == "__main__":
    unittest.main()
