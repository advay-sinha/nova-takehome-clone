"""SQLite state under --state-dir: document occurrences, page text, raw blobs and feedback files.

Every email and every attachment is one occurrence keyed by its evidence path ('batch_01/0003.eml',
'batch_01/0003.eml#INV-1.pdf'), so the same attachment bytes sent twice stay two occurrences. Raw bytes live once
per sha256 under blobs/. A batch is written in one transaction; blobs are written atomically before it commits.
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from pathlib import Path

from .config import state_paths

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS batches (
    batch TEXT PRIMARY KEY, source_dir TEXT NOT NULL, email_count INTEGER NOT NULL, ingested_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (
    doc TEXT PRIMARY KEY,          -- evidence path, as cited in reports
    batch TEXT NOT NULL,
    email_doc TEXT NOT NULL,       -- the .eml occurrence this arrived with (itself for an email)
    kind TEXT NOT NULL,            -- eml | pdf | xlsx | other
    name TEXT NOT NULL,            -- file or attachment name
    sha256 TEXT NOT NULL,
    received_at TEXT,              -- UTC 'YYYY-MM-DDTHH:MM:SSZ' from the email Date header; NULL if unreadable
    sender_name TEXT, sender_addr TEXT, to_addrs TEXT, cc_addrs TEXT, subject TEXT,
    headers_json TEXT,             -- Message-ID, In-Reply-To, References
    is_scan INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER NOT NULL DEFAULT 0,
    read_error TEXT);
CREATE INDEX IF NOT EXISTS documents_sha ON documents (sha256);
CREATE INDEX IF NOT EXISTS documents_received ON documents (received_at);
CREATE INDEX IF NOT EXISTS documents_email ON documents (email_doc);
CREATE TABLE IF NOT EXISTS pages (
    doc TEXT NOT NULL, page INTEGER NOT NULL, text TEXT NOT NULL,
    method TEXT NOT NULL,          -- textlayer | ocr
    ocr_json TEXT,                 -- raw OCR lines with scores, kept apart from the text
    PRIMARY KEY (doc, page));
CREATE TABLE IF NOT EXISTS extraction_units (
    unit TEXT PRIMARY KEY,         -- 'bundle:<email doc>' | 'long:<doc>' | 'table:<doc>'
    kind TEXT NOT NULL, batch TEXT NOT NULL, docs_json TEXT NOT NULL,
    status TEXT NOT NULL,          -- pending | done | failed
    attempts INTEGER NOT NULL DEFAULT 0, cache_key TEXT, backend TEXT, model TEXT, usage_json TEXT,
    elapsed_s REAL, error TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS llm_cache (
    key TEXT PRIMARY KEY, purpose TEXT NOT NULL, response_json TEXT NOT NULL, backend TEXT, model TEXT,
    usage_json TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, unit TEXT NOT NULL, kind TEXT NOT NULL, doc TEXT, page INTEGER,
    quote TEXT, data_json TEXT NOT NULL,
    status TEXT NOT NULL,          -- ok | unverified | rejected
    issues_json TEXT NOT NULL,
    origin TEXT NOT NULL);         -- llm | table | clone
CREATE INDEX IF NOT EXISTS facts_kind ON facts (kind, status);
CREATE INDEX IF NOT EXISTS facts_doc ON facts (doc);
CREATE INDEX IF NOT EXISTS facts_unit ON facts (unit);
CREATE TABLE IF NOT EXISTS doc_kinds (doc TEXT PRIMARY KEY, kind TEXT NOT NULL, summary TEXT, unit TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS doc_checks (
    doc TEXT PRIMARY KEY,
    status TEXT NOT NULL,          -- consistent | extraction_suspect | document_inconsistent | not_checkable
    issues_json TEXT NOT NULL, recheck_fields_json TEXT NOT NULL,
    recheck TEXT NOT NULL,         -- none | scheduled | accepted | unresolved
    recheck_detail_json TEXT, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS report_history (
    mode TEXT NOT NULL, key TEXT NOT NULL, as_of TEXT NOT NULL, item_id TEXT NOT NULL, verdict TEXT NOT NULL,
    amount TEXT, item_json TEXT NOT NULL, PRIMARY KEY (mode, key, as_of));
CREATE TABLE IF NOT EXISTS feedback_files (
    sha256 TEXT PRIMARY KEY, path TEXT NOT NULL, after_batch TEXT, decided_at TEXT, body_json TEXT NOT NULL,
    loaded_at TEXT NOT NULL);
"""


class Store:
    def __init__(self, state_dir: str | Path):
        self.paths = state_paths(state_dir)
        self.paths["root"].mkdir(parents=True, exist_ok=True)
        self.paths["blobs"].mkdir(exist_ok=True)
        self.db = sqlite3.connect(self.paths["db"])
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # ---- blobs --------------------------------------------------------------------------------------------------------
    def put_blob(self, sha: str, data: bytes) -> None:
        target = self.paths["blobs"] / sha
        if target.exists():
            return
        fd, tmp = tempfile.mkstemp(dir=self.paths["blobs"], prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def get_blob(self, sha: str) -> bytes:
        return (self.paths["blobs"] / sha).read_bytes()

    # ---- documents ----------------------------------------------------------------------------------------------------
    def upsert_document(self, row: dict, pages: list[dict]) -> bool:
        """Insert or refresh one occurrence and its pages. Returns False when the same doc+bytes is already stored."""
        old = self.db.execute("SELECT sha256 FROM documents WHERE doc = ?", (row["doc"],)).fetchone()
        if old is not None and old["sha256"] == row["sha256"]:
            return False
        cols = list(row)
        self.db.execute(f"INSERT OR REPLACE INTO documents ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                        [row[c] for c in cols])
        self.db.execute("DELETE FROM pages WHERE doc = ?", (row["doc"],))
        self.db.executemany("INSERT INTO pages (doc, page, text, method, ocr_json) VALUES (?, ?, ?, ?, ?)",
                            [(row["doc"], p["page"], p["text"], p["method"], p.get("ocr_json")) for p in pages])
        return True

    def record_batch(self, batch: str, source_dir: str, email_count: int, now: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO batches (batch, source_dir, email_count, ingested_at) VALUES (?,?,?,?)",
                        (batch, source_dir, email_count, now))

    def documents_received_by(self, as_of: str) -> list[sqlite3.Row]:
        """Occurrences received by the end of `as_of` (UTC). Unknown receipt times never count."""
        return self.db.execute("SELECT * FROM documents WHERE received_at IS NOT NULL AND received_at <= ? "
                               "ORDER BY received_at, doc", (f"{as_of}T23:59:59Z",)).fetchall()

    def pages_of(self, doc: str) -> list[str]:
        return [r["text"] for r in self.db.execute("SELECT text FROM pages WHERE doc = ? ORDER BY page", (doc,))]

    # ---- extraction ---------------------------------------------------------------------------------------------------
    def add_unit(self, unit: str, kind: str, batch: str, docs: list[str], now: str) -> None:
        self.db.execute("INSERT OR IGNORE INTO extraction_units (unit, kind, batch, docs_json, status, updated_at) "
                        "VALUES (?,?,?,?,'pending',?)", (unit, kind, batch, json.dumps(docs), now))

    def units(self, statuses: tuple[str, ...]) -> list[sqlite3.Row]:
        marks = ",".join("?" * len(statuses))
        return self.db.execute(f"SELECT * FROM extraction_units WHERE status IN ({marks}) ORDER BY batch, unit",
                               statuses).fetchall()

    def finish_unit(self, unit: str, status: str, now: str, **fields) -> None:
        cols = {"status": status, "updated_at": now, **fields}
        sets = ", ".join(f"{k} = ?" for k in cols)
        self.db.execute(f"UPDATE extraction_units SET {sets}, attempts = attempts + 1 WHERE unit = ?",
                        [*cols.values(), unit])

    def cache_get(self, key: str) -> dict | None:
        row = self.db.execute("SELECT response_json FROM llm_cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row["response_json"]) if row else None

    def cache_put(self, key: str, purpose: str, data: dict, backend: str, model: str, usage: dict, now: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO llm_cache (key, purpose, response_json, backend, model, usage_json, "
                        "created_at) VALUES (?,?,?,?,?,?,?)",
                        (key, purpose, json.dumps(data, sort_keys=True), backend, model, json.dumps(usage), now))

    def replace_facts(self, unit: str, rows: list[dict], origin: str) -> None:
        self.db.execute("DELETE FROM facts WHERE unit = ?", (unit,))
        self.db.executemany(
            "INSERT INTO facts (unit, kind, doc, page, quote, data_json, status, issues_json, origin) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            [(unit, r["kind"], r["doc"], r["page"], r["quote"], json.dumps(r["data"], sort_keys=True), r["status"],
              json.dumps(r["issues"]), r.get("origin", origin)) for r in rows])

    def set_doc_kind(self, doc: str, kind: str, summary: str | None, unit: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO doc_kinds (doc, kind, summary, unit) VALUES (?,?,?,?)",
                        (doc, kind, summary, unit))

    def set_doc_check(self, doc: str, result: dict, recheck: str, now: str, detail: dict | None = None) -> None:
        self.db.execute("INSERT OR REPLACE INTO doc_checks (doc, status, issues_json, recheck_fields_json, recheck, "
                        "recheck_detail_json, updated_at) VALUES (?,?,?,?,?,?,?)",
                        (doc, result["status"], json.dumps(result["issues"]), json.dumps(result["recheck_fields"]),
                         recheck, json.dumps(detail) if detail else None, now))

    def doc_check(self, doc: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM doc_checks WHERE doc = ?", (doc,)).fetchone()

    def billing_facts(self, doc: str, statuses: tuple[str, ...] = ("ok", "unverified")) -> tuple[dict | None, list[dict]]:
        """(header, lines) data dicts of one document's usable billing facts."""
        marks = ",".join("?" * len(statuses))
        rows = self.db.execute(f"SELECT kind, data_json FROM facts WHERE doc = ? AND kind IN ('invoices', "
                               f"'invoice_lines') AND status IN ({marks}) ORDER BY id", (doc, *statuses)).fetchall()
        headers = [json.loads(r["data_json"]) for r in rows if r["kind"] == "invoices"]
        return (headers[0] if headers else None), [json.loads(r["data_json"]) for r in rows if r["kind"] == "invoice_lines"]

    def facts(self, kind: str, statuses: tuple[str, ...] = ("ok", "unverified")) -> list[sqlite3.Row]:
        marks = ",".join("?" * len(statuses))
        return self.db.execute(f"SELECT * FROM facts WHERE kind = ? AND status IN ({marks}) ORDER BY id",
                               (kind, *statuses)).fetchall()

    def document(self, doc: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM documents WHERE doc = ?", (doc,)).fetchone()

    # ---- feedback -----------------------------------------------------------------------------------------------------
    def add_feedback_file(self, sha: str, path: str, body: dict, now: str) -> bool:
        if self.db.execute("SELECT 1 FROM feedback_files WHERE sha256 = ?", (sha,)).fetchone():
            return False
        self.db.execute("INSERT INTO feedback_files (sha256, path, after_batch, decided_at, body_json, loaded_at) "
                        "VALUES (?,?,?,?,?,?)", (sha, path, body.get("after_batch"), body.get("decided_at"),
                                                 json.dumps(body, sort_keys=True), now))
        return True
