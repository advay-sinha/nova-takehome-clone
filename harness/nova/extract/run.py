"""Plan and run extraction units for stored documents.

Units: 'bundle:<email>' (the email plus its short attachments, one call), 'long:<doc>' (a PDF of 4+ pages, typically
an agreement, one call), 'table:<doc>' (a large spreadsheet: one column-map call, then every row parsed here), and
'clone:<doc>' (an attachment whose exact bytes were already extracted from an earlier occurrence: its facts are copied
with the new doc path, no call). Units that the step budget cannot reach stay pending for the next step. Model calls
run in worker threads; every database write happens on the calling thread.
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone

import jsonschema

from ..llm import BudgetExhausted, CallBudget, LLMError, LLMLimited, LLMRequest, LLMUnavailable, iter_completed
from ..llm import workers_for
from ..llm.shared_cache import open_shared
from . import constraints, prompts, tables
from .schema import FACT_LISTS, FACTS_SCHEMA, RECHECK_SCHEMA, TABLE_MAP_SCHEMA
from .validate import PageIndex, validate_facts

LONG_PDF_PAGES = 4
CHUNK_PAGES = 4            # a long PDF is read in chunks of this many pages, in parallel (H-003: one call per
                           # 11-page agreement took up to 178 s of a 240 s request timeout)
LARGE_SHEET_LINES = 60
MAX_ATTEMPTS = 2


def add_long_units(store, doc: str, batch: str, page_count: int) -> int:
    """Units 'long:<doc>@a-b' covering every page of a long document."""
    n = 0
    for first in range(1, page_count + 1, CHUNK_PAGES):
        last = min(first + CHUNK_PAGES - 1, page_count)
        store.add_unit(f"long:{doc}@{first}-{last}", "long", batch, [doc], _now())
        n += 1
    return n


def _unit_pages(unit_name: str) -> list[int] | None:
    if "@" not in unit_name:
        return None
    first, last = unit_name.rsplit("@", 1)[1].split("-")
    return list(range(int(first), int(last) + 1))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---- planning ---------------------------------------------------------------------------------------------------------
def plan_batch(store, batch: str) -> int:
    """Create units for the batch's documents not yet planned. Returns how many units were added."""
    planned = {d for r in store.db.execute("SELECT docs_json FROM extraction_units") for d in json.loads(r[0])}
    seen_sha = {}
    for r in store.db.execute("SELECT doc, sha256 FROM documents WHERE kind != 'eml' AND read_error IS NULL "
                              "ORDER BY received_at, doc"):
        seen_sha.setdefault(r["sha256"], r["doc"])
    added = 0
    emails = store.db.execute("SELECT doc FROM documents WHERE batch = ? AND kind = 'eml' ORDER BY doc",
                              (batch,)).fetchall()
    for (email_doc,) in emails:
        if email_doc in planned:
            continue
        members = [email_doc]
        atts = store.db.execute("SELECT * FROM documents WHERE email_doc = ? AND kind != 'eml' ORDER BY doc",
                                (email_doc,)).fetchall()
        for a in atts:
            if a["read_error"] or a["page_count"] == 0:
                continue
            first = seen_sha.get(a["sha256"])
            if first and first != a["doc"]:
                store.add_unit(f"clone:{a['doc']}", "clone", batch, [a["doc"], first], _now())
            elif a["kind"] == "pdf" and a["page_count"] >= LONG_PDF_PAGES:
                added += add_long_units(store, a["doc"], batch, a["page_count"]) - 1
            elif a["kind"] == "xlsx" and sum(len(t.split("\n")) for t in store.pages_of(a["doc"])) > LARGE_SHEET_LINES:
                store.add_unit(f"table:{a['doc']}", "table", batch, [a["doc"]], _now())
            else:
                members.append(a["doc"])
                continue
            added += 1
        store.add_unit(f"bundle:{email_doc}", "bundle", batch, members, _now())
        added += 1
    return added


# ---- running ----------------------------------------------------------------------------------------------------------
def _doc_payload(store, doc: str) -> dict:
    row = store.document(doc)
    return {"doc": doc, "kind": row["kind"], "is_scan": bool(row["is_scan"]), "pages": store.pages_of(doc)}


def _order_hints(store, docs: list[str]) -> dict[str, str]:
    """Date order (DMY/MDY) for each doc, learned from all stored documents of the same sender."""
    hints = {}
    for doc in docs:
        row = store.document(doc)
        if not row or not row["sender_addr"]:
            continue
        orders = Counter()
        for (other,) in store.db.execute("SELECT doc FROM documents WHERE sender_addr = ?", (row["sender_addr"],)):
            order = PageIndex._date_order(store.pages_of(other))
            if order:
                orders[order] += 1
        if len(orders) == 1:
            hints[doc] = next(iter(orders))
    return hints


def _request(store, unit, docs: list[dict]) -> LLMRequest:
    if unit["kind"] == "table":
        return LLMRequest("tablemap", prompts.TABLE_SYSTEM, prompts.render_table_pages(docs[0]["doc"], docs[0]["pages"]),
                          TABLE_MAP_SCHEMA, max_tokens=4000)
    if unit["kind"] == "recheck":
        check = store.doc_check(docs[0]["doc"])
        fields = json.loads(check["recheck_fields_json"]) if check else ["every line and the totals"]
        return LLMRequest("recheck", prompts.RECHECK_SYSTEM, prompts.render_recheck(docs[0], fields), RECHECK_SCHEMA)
    return LLMRequest(f"facts:{unit['kind']}", prompts.FACTS_SYSTEM, prompts.render_documents(docs), FACTS_SCHEMA)


def _check_billing(store, unit, docs: list[dict]) -> None:
    """Arithmetic checks for each billing document of a unit; schedule its single recheck when it looks misread."""
    if "@" in unit["unit"]:
        return                    # a chunk holds only part of a long document; its totals cannot be checked alone
    for d in docs:
        header, lines = store.billing_facts(d["doc"])
        if header is None and not lines:
            continue
        result = constraints.check_document(header, lines, bool(d.get("is_scan")))
        recheck = "none"
        if result["status"] == "extraction_suspect":
            store.add_unit(f"recheck:{d['doc']}", "recheck", unit["batch"], [d["doc"]], _now())   # once per doc
            recheck = "scheduled"
        store.set_doc_check(d["doc"], result, recheck, _now())


def _apply_recheck(store, unit, docs: list[dict], data: dict) -> tuple[int, int]:
    """Accept a re-read only if every value is on the page and the document's arithmetic now holds."""
    jsonschema.validate(data, RECHECK_SCHEMA)
    doc = docs[0]
    index = PageIndex(docs, _order_hints(store, [doc["doc"]]))
    rows = validate_facts(index, data, ["invoices", "invoice_lines"])
    usable = [r for r in rows if r["status"] != "rejected"]
    header = next((r["data"] for r in usable if r["kind"] == "invoices"), None)
    lines = [r["data"] for r in usable if r["kind"] == "invoice_lines"]
    after = constraints.check_document(header, lines, bool(doc.get("is_scan")))
    before = store.doc_check(doc["doc"])
    before_issues = json.loads(before["issues_json"]) if before else []
    if after["status"] == "consistent" and lines:
        store.db.execute("UPDATE facts SET status = 'superseded' WHERE doc = ? AND kind IN ('invoices', "
                         "'invoice_lines') AND unit != ? AND status != 'rejected'", (doc["doc"], unit["unit"]))
        store.replace_facts(unit["unit"], rows, "recheck")
        store.set_doc_check(doc["doc"], after, "accepted", _now(), {"before": before_issues})
    else:
        for r in rows:
            r["status"] = "recheck_unaccepted"          # kept for the record, never used
        store.replace_facts(unit["unit"], rows, "recheck")
        kept = {"status": before["status"], "issues": before_issues,
                "recheck_fields": json.loads(before["recheck_fields_json"])} if before else after
        store.set_doc_check(doc["doc"], kept, "unresolved", _now(), {"recheck_issues": after["issues"]})
    return len(rows), sum(r["status"] == "rejected" for r in rows)


def _apply(store, unit, docs: list[dict], data: dict) -> tuple[int, int]:
    """Validate and store one unit's answer. Returns (facts stored, facts rejected)."""
    if unit["kind"] == "recheck":
        return _apply_recheck(store, unit, docs, data)
    if unit["kind"] == "table":
        jsonschema.validate(data, TABLE_MAP_SCHEMA)
        doc = docs[0]["doc"]
        xlsx = store.get_blob(store.document(doc)["sha256"])
        rows = [r for t in data.get("tables") or [] for r in tables.parse_table(doc, xlsx, t)]
        store.set_doc_kind(doc, "table", ", ".join(sorted({t.get("kind", "?") for t in data.get("tables") or []})),
                           unit["unit"])
        if not any(r["status"] != "rejected" for r in rows):          # not a known table: read it as text
            add_long_units(store, doc, unit["batch"], len(docs[0]["pages"]))
    else:
        jsonschema.validate(data, FACTS_SCHEMA)
        index = PageIndex(docs, _order_hints(store, [d["doc"] for d in docs]))
        rows = validate_facts(index, data, FACT_LISTS)
        later_chunk = (_unit_pages(unit["unit"]) or [1])[0] > 1
        for d in data.get("documents") or []:
            if d.get("doc") not in index.pages:
                continue
            known = store.db.execute("SELECT kind FROM doc_kinds WHERE doc = ?", (d["doc"],)).fetchone()
            if later_chunk and known and known[0] != "other":
                continue                  # page 1 classifies a long document; later chunks only add facts
            store.set_doc_kind(d["doc"], d.get("kind") or "other", d.get("summary"), unit["unit"])
    store.replace_facts(unit["unit"], rows, "table" if unit["kind"] == "table" else "llm")
    if unit["kind"] != "table":
        _check_billing(store, unit, docs)
    return len(rows), sum(r["status"] == "rejected" for r in rows)


def _clone(store, unit) -> bool:
    new_doc, source_doc = json.loads(unit["docs_json"])
    src_units = [r[0] for r in store.db.execute("SELECT DISTINCT unit FROM facts WHERE doc = ?", (source_doc,))]
    done = all(store.db.execute("SELECT status FROM extraction_units WHERE unit = ?", (u,)).fetchone()[0] == "done"
               for u in src_units)
    if not src_units or not done:
        return False
    rows = []
    for f in store.db.execute("SELECT * FROM facts WHERE doc = ?", (source_doc,)):
        data = json.loads(f["data_json"])
        data["_source"] = {**data.get("_source", {}), "doc": new_doc}
        data["_cloned_from"] = source_doc
        rows.append({"kind": f["kind"], "doc": new_doc, "page": f["page"], "quote": f["quote"], "data": data,
                     "status": f["status"], "issues": json.loads(f["issues_json"]), "origin": "clone"})
    k = store.db.execute("SELECT kind, summary FROM doc_kinds WHERE doc = ?", (source_doc,)).fetchone()
    with store.db:
        store.replace_facts(unit["unit"], rows, "clone")
        if k:
            store.set_doc_kind(new_doc, k["kind"], k["summary"], unit["unit"])
        store.finish_unit(unit["unit"], "done", _now(), error=None)
    return True


def _finish(store, stats: Counter, provider, u, docs: list[dict], req: LLMRequest, cached: dict | None, res,
            progress: str, shared=None) -> None:
    """Commit one unit's outcome (cache entry, facts, status) in its own transaction and log progress."""
    now = _now()
    if isinstance(res, LLMError):
        with store.db:
            store.finish_unit(u["unit"], "failed", now, error=str(res)[:500])
        stats["failed"] += 1
        log(f"extract {progress} FAILED {u['unit']}: {str(res)[:200]}")
        return
    data = cached if cached is not None else res.data
    key = req.cache_key(provider.model)
    try:
        with store.db:
            if res is not None:
                store.cache_put(key, req.purpose, data, res.backend, res.model, res.usage, now)
                if shared is not None:
                    shared.put(key, req.purpose, data, res.model, now)
            elif store.cache_get(key) is None:          # answer came from the shared cache: keep a local copy
                store.cache_put(key, req.purpose, data, "shared_cache", provider.model, {}, now)
            n, rejected = _apply(store, u, docs, data)
            store.finish_unit(u["unit"], "done", now, cache_key=key, backend=getattr(res, "backend", "cache"),
                              model=provider.model, usage_json=json.dumps(getattr(res, "usage", {}) or {}),
                              elapsed_s=getattr(res, "elapsed_s", 0.0), error=None)
    except jsonschema.ValidationError as e:
        with store.db:
            store.finish_unit(u["unit"], "failed", now, error=f"answer does not match schema: {e.message}"[:500])
        stats["failed"] += 1
        log(f"extract {progress} FAILED {u['unit']}: answer does not match schema")
        return
    stats["done"] += 1
    stats["facts"] += n
    stats["rejected"] += rejected
    how = "cached" if res is None else f"{res.elapsed_s:.1f} s"
    log(f"extract {progress} done {u['unit']} ({how}, {n} facts" + (f", {rejected} rejected)" if rejected else ")"))


def run_pending(store, provider_factory, cfg: dict, seconds: float) -> dict:
    """Run every runnable unit within `seconds`. Use the source-validated local reader when no model backend
    can be constructed; a configured provider's authentication or rate-limit failures keep their normal handling."""
    stats = Counter()
    budget = CallBudget(seconds, int(cfg["max_calls_per_step"]))
    provider = None
    shared = open_shared() if not os.environ.get("ANTHROPIC_API_KEY") else None
    for _ in range(2):                     # second pass picks up units created by the first (e.g. table -> long)
        units = [u for u in store.units(("pending", "failed")) if u["attempts"] < MAX_ATTEMPTS]
        model_units = [u for u in units if u["kind"] in ("bundle", "long", "table", "recheck")]
        if model_units and provider is None:
            try:
                provider = provider_factory()
            except LLMUnavailable:
                if shared is not None:
                    shared.close()
                from .local import run_local
                return run_local(store, budget.remaining_s())
        cached_work, live_work = [], []
        for u in model_units:
            docs = [_doc_payload(store, d) for d in json.loads(u["docs_json"])]
            if (show := _unit_pages(u["unit"])):
                docs[0]["show"] = show
            req = _request(store, u, docs)
            key = req.cache_key(provider.model)
            cached = store.cache_get(key)
            if cached is None and shared is not None:
                cached = shared.get(key)
            (cached_work if cached is not None else live_work).append((u, docs, req, cached))
        total, done_n = len(model_units), 0
        if total:
            log(f"extract: {total} unit(s), {len(cached_work)} from cache, {len(live_work)} to call with "
                f"{workers_for(provider, cfg)} worker(s), {budget.remaining_s():.0f} s budget")
        for u, docs, req, cached in cached_work:
            done_n += 1
            _finish(store, stats, provider, u, docs, req, cached, None, f"{done_n}/{total}", shared)
        live = iter_completed(provider, [w[2] for w in live_work], budget,
                              workers_for(provider, cfg)) if live_work else ()
        for i, res in live:                # each answer is saved as soon as it arrives
            u, docs, req, _ = live_work[i]
            if isinstance(res, (BudgetExhausted, LLMLimited)):
                stats["limited" if isinstance(res, LLMLimited) else "pending"] += 1
                continue                   # stays pending; no attempt is used up
            done_n += 1
            _finish(store, stats, provider, u, docs, req, None, res, f"{done_n}/{total}", shared)
        if budget.stopped:
            log(f"extract: model usage/rate limit reached ({budget.stopped[:160]}); "
                f"{stats['limited'] + stats['pending']} unit(s) left pending for the next step")
            break
        for u in [u for u in store.units(("pending",)) if u["kind"] == "clone"]:
            stats["cloned" if _clone(store, u) else "clone_waiting"] += 1
        if not any(u["kind"] != "clone" for u in store.units(("pending",))):
            break
    if shared is not None:
        shared.close()
    return dict(stats)
