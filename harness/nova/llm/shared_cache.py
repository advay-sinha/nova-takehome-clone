"""Optional response cache shared across state folders, for local development only.

Enabled only when the gitignored `harness/.local-llm.json` names a file under "shared_cache". The grader's machine
never has that file, so official runs there always call the model. Locally it lets a re-run of the same mailbox (the
second grading mode, an eval case run again after a rule fix) reuse the answer to an identical request instead of
paying for it twice. The key is the request's own cache key (prompt version, model, system, user text, schema), so
any change to a document, prompt or schema misses the cache.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import load_local

_SCHEMA = ("CREATE TABLE IF NOT EXISTS shared_llm_cache (key TEXT PRIMARY KEY, purpose TEXT, response_json TEXT "
           "NOT NULL, model TEXT, created_at TEXT)")


class SharedCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=30)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(_SCHEMA)
        self.db.commit()

    def get(self, key: str) -> dict | None:
        row = self.db.execute("SELECT response_json FROM shared_llm_cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, purpose: str, data: dict, model: str, now: str) -> None:
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO shared_llm_cache VALUES (?,?,?,?,?)",
                            (key, purpose, json.dumps(data, sort_keys=True), model, now))

    def close(self) -> None:
        self.db.close()


def open_shared(local: dict | None = None) -> SharedCache | None:
    from . import forbid_in_local_only
    forbid_in_local_only("shared model-response cache")
    path = (load_local() if local is None else local).get("shared_cache")
    return SharedCache(Path(path)) if path else None
