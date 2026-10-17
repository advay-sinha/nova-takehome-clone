"""The three grader-facing commands. Diagnostics go to stderr; only `report` writes to stdout (via harness.py)."""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import time

from .config import SCHEMA_VERSION
from .extract.run import plan_batch, run_pending
from .llm import load_config, select_provider
from .reader import read_batch, sha256
from .report import build as build_report
from .store import Store

REPORT_RESERVE_S = 120     # time kept back in `report` for building the report after finishing extraction
WRITE_RESERVE_S = 20


def _now() -> str:
    # Operational timestamp only (when this process ran). Business logic uses email Date headers and --as-of.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _extract(store, cfg: dict, seconds: float, step: str) -> None:
    stats = run_pending(store, lambda: select_provider(cfg), cfg, seconds)
    log(f"{step}: extraction {stats}")
    if stats.get("pending") or stats.get("failed"):
        log(f"{step}: WARNING {stats.get('pending', 0)} unit(s) pending and {stats.get('failed', 0)} failed; "
            "they are retried by the next step")


def ingest(batch_dir: str, state_dir: str) -> None:
    start = time.monotonic()
    folder = Path(batch_dir)
    if not folder.is_dir():
        raise ValueError(f"batch folder not found: {batch_dir}")
    items = read_batch(folder)
    store = Store(state_dir)
    try:
        for it in items:
            store.put_blob(it["row"]["sha256"], it["data"])
        changed = 0
        with store.db:
            for it in items:
                changed += store.upsert_document(it["row"], it["pages"])
            store.record_batch(folder.name, str(folder.resolve()),
                               sum(1 for it in items if it["row"]["kind"] == "eml"), _now())
        errors = [it["row"]["doc"] for it in items if it["row"].get("read_error")]
        log(f"ingest {folder.name}: {len(items)} documents, {changed} new or changed, {len(errors)} unreadable")
        for doc in errors:
            log(f"  unreadable: {doc}")
        with store.db:
            plan_batch(store, folder.name)
        cfg = load_config()
        _extract(store, cfg, cfg["step_budget_s"] - (time.monotonic() - start) - WRITE_RESERVE_S, "ingest")
    finally:
        store.close()


def _check_date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        raise ValueError(f"--as-of must be YYYY-MM-DD, got {value!r}")
    date.fromisoformat(value)
    return value


def report(as_of: str, mode: str, state_dir: str) -> dict:
    start = time.monotonic()
    _check_date(as_of)
    store = Store(state_dir)
    try:
        if store.units(("pending", "failed")):
            cfg = load_config()
            _extract(store, cfg, cfg["step_budget_s"] - (time.monotonic() - start) - REPORT_RESERVE_S, "report")
        known = store.documents_received_by(as_of)
        out = build_report(store, as_of, mode)
        items = len(out["findings"]) + sum(len(v) for v in out["portfolio"].values())
        log(f"report {as_of} {mode}: {len(known)} documents received by then; {items} item(s)")
        return out
    finally:
        store.close()


def feedback(feedback_file: str, state_dir: str) -> None:
    path = Path(feedback_file)
    raw = path.read_bytes()
    body = json.loads(raw.decode("utf-8"))
    if not isinstance(body, dict) or not isinstance(body.get("items"), list):
        raise ValueError(f"{feedback_file}: expected a feedback object with an 'items' list")
    store = Store(state_dir)
    try:
        with store.db:
            added = store.add_feedback_file(sha256(raw), str(path.resolve()), body, _now())
        log(f"feedback {path.name}: {len(body['items'])} items" + ("" if added else " (already loaded)"))
    finally:
        store.close()
