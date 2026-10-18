"""Credential-free extraction, using printed structure and the normal fact/evidence validators.

This path has no model calls, response cache or knowledge of evaluation keys. It is selected when a model provider
cannot be constructed, or explicitly with NOVA_LOCAL_READER_ONLY=1. Model authentication/rate-limit errors during a
configured live run remain errors.
"""
from __future__ import annotations

import json
import time
from collections import Counter

import jsonschema

from .local_billing import read_credit, read_invoice, read_transport, table_rows
from .local_common import Document
from .local_contracts import read_contract
from .local_mail import read_email
from .schema import FACT_LISTS, FACTS_SCHEMA
from .validate import PageIndex, validate_facts

BILLING_LABELS = ("Air freight", "Fuel surcharge", "Security surcharge", "Delivery fee", "Dry ice handling fee",
                  "Dangerous goods fee", "Storage", "Late payment fee", "Late fee", "Import duty", "Handling margin")


def extract(docs, labels=(), contract_ids=(), hints=None):
    out = {k: [] for k in FACTS_SCHEMA["properties"]}
    labels, contract_ids = list(labels) + list(BILLING_LABELS), list(contract_ids)
    for payload in docs:
        doc = Document(payload, (hints or {}).get(payload["doc"]))
        kind = "other"
        if read_contract(doc, out):
            kind = "amendment" if out["contracts"][-1]["kind"] == "amendment" else "contract"
            contract_ids += [f["contract_id"] for f in out["contracts"]]
            labels += [v for f in out["charge_codes"] for v in [f["name"], *f["aliases"]]]
        elif doc.kind != "eml" and read_credit(doc, out):
            kind = "credit_note"
        elif doc.kind != "eml" and read_invoice(doc, out, labels):
            kind = "invoice"
        elif doc.kind != "eml" and (transport := read_transport(doc, out)):
            kind = transport
        elif read_email(doc, out, labels, contract_ids):
            kind = "correspondence"
        out["documents"].append({"doc": doc.doc, "kind": kind, "summary": "Read from explicit document structure"})
    return out


def run_local(store, seconds, reason="no model backend available"):
    from .run import MAX_ATTEMPTS, _apply_recheck, _check_billing, _clone, _doc_payload, _now, _order_hints, log
    from ..llm import LLMUnavailable

    deadline = time.monotonic() + max(0, seconds)
    stats = Counter()
    whole_documents = {d for u in store.units(("done",)) if u["kind"] == "long" and u["backend"] == "local"
                       for d in json.loads(u["docs_json"])}
    log(f"extract: {reason}; using local document reader (no API calls or response cache)")
    for _ in range(2):
        units = [u for u in store.units(("pending", "failed")) if u["attempts"] < MAX_ATTEMPTS and u["kind"] != "clone"]
        # Read agreement tables first so invoice labels come from held contracts.
        units.sort(key=lambda u: (u["kind"] != "long", u["unit"]))
        labels = [v for row in store.facts("charge_codes") for f in [json.loads(row["data_json"])]
                  for v in [f["name"], *f.get("aliases", [])]]
        contract_ids = [json.loads(f["data_json"])["contract_id"] for f in store.facts("contracts")]
        for u in units:
            if time.monotonic() >= deadline:
                stats["pending"] += 1
                continue
            docs = [_doc_payload(store, d) for d in json.loads(u["docs_json"])]
            if u["kind"] == "long" and all(d["doc"] in whole_documents for d in docs):
                # Skip remaining chunks only after this reader has processed the whole source document.
                # A previous model run may have completed only its first chunk before access was lost.
                with store.db:
                    store.finish_unit(u["unit"], "done", _now(), backend="local", model="local-reader-1")
                continue
            hints = _order_hints(store, [d["doc"] for d in docs])
            tables, prose = [], []
            for d in docs:
                tab = table_rows(Document(d, hints.get(d["doc"])), store.get_blob(store.document(d["doc"])["sha256"])) if d["kind"] == "xlsx" else None
                if tab:
                    tables.extend(tab)
                else:
                    prose.append(d)
            data = extract(prose, labels, contract_ids, hints)
            jsonschema.validate(data, FACTS_SCHEMA)
            rows = validate_facts(PageIndex(prose, hints), data, FACT_LISTS) + tables
            for h in data["invoices"]:
                if not any(f["source"]["doc"] == h["source"]["doc"] for f in data["invoice_lines"]):
                    raise LLMUnavailable(f"local reader cannot parse billed rows in {h['source']['doc']}; configure model access for this layout")
            with store.db:
                if u["kind"] == "recheck":
                    _apply_recheck(store, u, docs, {k: data[k] for k in ("invoices", "invoice_lines")})
                else:
                    store.replace_facts(u["unit"], rows, "local")
                    for d in data["documents"]:
                        store.set_doc_kind(d["doc"], d["kind"], d["summary"], u["unit"])
                    for d in docs:
                        if any(r["doc"] == d["doc"] for r in tables):
                            store.set_doc_kind(d["doc"], "table", "Header-mapped table", u["unit"])
                    _check_billing(store, dict(u, unit=u["unit"].split("@")[0]), docs)
                store.finish_unit(u["unit"], "done", _now(), backend="local", model="local-reader-1", error=None)
            labels += [v for f in data["charge_codes"] for v in [f["name"], *f["aliases"]]]
            contract_ids += [f["contract_id"] for f in data["contracts"]]
            if u["kind"] == "long":
                whole_documents.update(d["doc"] for d in docs)
            stats["done"] += 1
            stats["facts"] += len(rows)
            stats["rejected"] += sum(r["status"] == "rejected" for r in rows)
        for u in [u for u in store.units(("pending",)) if u["kind"] == "clone"]:
            stats["cloned" if _clone(store, u) else "clone_waiting"] += 1
    return dict(stats)
