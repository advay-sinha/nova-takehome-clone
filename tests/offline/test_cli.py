"""The three commands as the grader calls them: fresh processes, an unrelated cwd, state only under --state-dir.

Runs harness.py on the synthetic mailbox from fixtures.py; no corpus, network or model call.
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "harness" / "harness.py"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "harness"))

from fixtures import build_mailbox  # noqa: E402
from nova.store import Store  # noqa: E402

SCHEMA = json.loads((ROOT / "grader" / "schema" / "report.schema.json").read_text())


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.mailbox = build_mailbox(base / "mailbox")
        self.state = base / "state"
        self.cwd = base / "elsewhere"   # the grader runs from an unrelated folder
        self.cwd.mkdir()
        local = base / "local-llm.json"   # the CLI back end runs a fake, never the real claude
        local.write_text(json.dumps({"claude_command": [sys.executable, str(Path(__file__).with_name("fake_claude.py"))]}))
        self.env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"} | {"NOVA_LOCAL_LLM": str(local)}

    def tearDown(self):
        self.tmp.cleanup()

    def run_cmd(self, *args):
        return subprocess.run([sys.executable, str(HARNESS), *args], cwd=self.cwd, capture_output=True, text=True,
                              timeout=300, env=self.env)

    def ingest(self, batch):
        r = self.run_cmd("ingest", str(self.mailbox / batch), "--state-dir", str(self.state))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")
        return r

    def doc_count(self):
        with closing(sqlite3.connect(self.state / "nova.sqlite3")) as db:   # 'with conn' alone never closes it
            return db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def test_ingest_report_feedback(self):
        self.ingest("batch_01")
        self.ingest("batch_02")
        self.assertEqual(self.doc_count(), 10)   # 5 emails + 5 attachments
        r = self.run_cmd("report", "--as-of", "2041-06-30", "--mode", "autonomous", "--state-dir", str(self.state))
        self.assertEqual(r.returncode, 0, r.stderr)
        rep = json.loads(r.stdout)            # stdout is JSON and nothing else
        jsonschema.validate(rep, SCHEMA)
        self.assertEqual((rep["as_of"], rep["mode"]), ("2041-06-30", "autonomous"))
        fb = self.cwd / "fb.json"
        fb.write_text(json.dumps({"schema_version": "1.0", "after_batch": "batch_01",
                                  "decided_at": "2041-04-02T10:00:00Z", "items": []}))
        for _ in range(2):
            r = self.run_cmd("feedback", str(fb), "--state-dir", str(self.state))
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("already loaded", r.stderr)

    def test_reingest_is_idempotent_and_keeps_resends(self):
        self.ingest("batch_01")
        first = self.doc_count()
        r = self.ingest("batch_01")
        self.assertEqual(self.doc_count(), first)
        self.assertIn("0 new or changed", r.stderr)
        store = Store(self.state)
        try:
            rows = store.db.execute("SELECT doc FROM documents WHERE name = 'PW-OB-2041-0107.pdf' ORDER BY doc").fetchall()
            self.assertEqual([x["doc"] for x in rows], ["batch_01/0002.eml#PW-OB-2041-0107.pdf",
                                                        "batch_01/0004.eml#PW-OB-2041-0107.pdf"])
            self.assertEqual(len(list((self.state / "blobs").iterdir())), 7)  # identical PDFs stored once
        finally:
            store.close()

    def test_as_of_counts_utc_end_of_day(self):
        self.ingest("batch_01")
        store = Store(self.state)
        try:
            docs = lambda d: {r["doc"] for r in store.documents_received_by(d)}  # noqa: E731
            self.assertIn("batch_01/0002.eml", docs("2041-03-05"))      # 21:40 UTC on the 5th
            self.assertNotIn("batch_01/0003.eml", docs("2041-03-28"))
            self.assertIn("batch_01/0003.eml#ap-register-2041-03-29.xlsx", docs("2041-03-29"))
        finally:
            store.close()

    def test_bad_input_fails_cleanly(self):
        r = self.run_cmd("report", "--as-of", "2041/06/30", "--state-dir", str(self.state))
        self.assertEqual((r.returncode, r.stdout), (2, ""))
        r = self.run_cmd("ingest", str(self.mailbox / "batch_99"), "--state-dir", str(self.state))
        self.assertEqual(r.returncode, 2)
        bad = self.cwd / "bad.json"
        bad.write_text("[]")
        self.assertEqual(self.run_cmd("feedback", str(bad), "--state-dir", str(self.state)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
