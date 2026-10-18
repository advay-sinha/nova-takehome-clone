"""Assemble report.json from detector candidates: currency, actions per mode, confidence, ids and history, citations,
schema check and internal traces. The official JSON carries only schema fields; reasoning lives in the traces.

Actions (GLOSSARY "Actions", "The two modes and the unattended-action test"):
- conflict -> escalate; expiry -> internal:alert; late-fee risk -> internal:payment_reminder; credit not yet due ->
  internal:track_credit.
- outbound remedies (dispute, claim_credit, request_document) are summed per invoice or cashback key: $5,000.00 or
  more -> human_review in both modes. Otherwise supervised -> draft:*, autonomous -> execute:* only when all five
  unattended checks pass, else human_review.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import jsonschema

from . import feedback
from .config import SCHEMA_VERSION
from .extract.validate import PageIndex
from .money import money_str, q2
from .rules import cashback, duplicate, expiry, late_fees, overcharge, waiver
from .rules.common import Candidate
from .world import World, norm_id, to_date

SCHEMA = json.loads((Path(__file__).with_name("report.schema.json")).read_text(encoding="utf-8"))
_VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
THRESHOLD = Decimal("5000.00")
TRUSTED_PICKUP = {"tracking", "carrier_email"}
RECIPIENT_CATEGORY = {"dispute": "billing_disputes", "claim_credit": "billing_disputes"}


def key_str(c: Candidate) -> str:
    k = c.key
    if c.cls == "cashback":
        return f"cashback:{k['contract_id']}/{k['period']}/{k['credit_type']}"
    if c.cls == "expiry":
        return f"expiry:{k['contract_id']}"
    return f"{c.cls}:{k['invoice_id']}"


# ---- currency -------------------------------------------------------------------------------------------------------
def _to_usd(world: World, c: Candidate) -> None:
    """Convert an INR amount once, with the Annex F rate of the invoice month (overcharge converts itself)."""
    if c.signals.get("currency") != "INR" or c.amount_usd is None or c.signals.get("usd_done") or c.cls == "overcharge":
        return
    contract = world.contract_of(c.contract_id)
    inv = c.key.get("invoice_id")
    month = c.signals.get("invoice_date") or next((h.get("invoice_date") for h in world.of("invoices")
                                                   if norm_id(h.get("invoice_id")) == inv), None)
    fx = contract.fx.get(str(month)[:7]) if contract and month else None
    if fx is None:
        holder = contract.contact("treasury") if contract else None
        c.verdict, c.amount_usd, c.outbound, c.internal = "cannot_determine", None, "request_document", None
        c.missing_doc = {"name": f"Annex F exchange rate for {str(month)[:7]}",
                         "holder": {k: v for k, v in {"party": holder.party if holder else None,
                                                      "person": holder.name if holder else None,
                                                      "role": holder.title if holder else None}.items() if v}}
        return
    c.trace["fx"] = {"month": str(month)[:7], "inr_per_usd": str(fx[0]), "amount_inr": str(c.amount_usd)}
    c.amount_usd = q2(c.amount_usd / fx[0])
    c.add_evidence(fx[1].evidence())


# ---- actions --------------------------------------------------------------------------------------------------------
def _shares_conflict(c: Candidate, conflict: Candidate) -> bool:
    if key_str(c) == key_str(conflict):
        return True
    if not c.contract_id or c.contract_id != conflict.contract_id:
        return False
    scopes = c.signals.get("pricing_scopes") or []
    disputed = conflict.signals.get("conflict_scopes") or []
    if not scopes or not disputed:
        return bool(c.lane and c.lane == conflict.lane)
    return any(a["lane"] == b["lane"] and a["charge"] == b["charge"]
               and (a["period"] is None or b["period"] is None or a["period"] == b["period"])
               for a in scopes for b in disputed)


def _unattended_failures(world: World, c: Candidate, outbound_sum: Decimal, conflicts: list[Candidate]) -> list[str]:
    fails = []
    if c.verdict != "cannot_determine" and c.missing_doc:
        fails.append("missing document")
    sources = set(c.signals.get("pickup_sources") or [])
    if c.cls == "overcharge" and sources - TRUSTED_PICKUP:
        fails.append(f"pickup date not from tracking or a carrier email: {sorted(sources - TRUSTED_PICKUP)}")
    if c.signals.get("unverified"):
        fails.append("relies on a field that could not be verified on its page")
    if any(_shares_conflict(c, conflict) for conflict in conflicts):
        fails.append("open conflict on the same contract, lane, charge and rate period")
    if outbound_sum >= THRESHOLD:
        fails.append(f"outbound total {outbound_sum} is $5,000 or more")
    contract = world.contract_of(c.contract_id)
    if c.outbound == "request_document":
        holder = (c.missing_doc or {}).get("holder") or {}
        if not (contract and holder.get("person") and any(p.name == holder["person"] for p in contract.persons)):
            fails.append("document holder not found in Schedule 1")
    else:
        cat = RECIPIENT_CATEGORY.get(c.outbound or "", "billing_disputes")
        if not (contract and contract.contact(cat)):
            fails.append(f"no Schedule 1 {cat} recipient")
    return fails


def _actions(world: World, cands: list[Candidate], mode: str) -> None:
    sums: dict[str, Decimal] = {}
    for c in cands:
        if c.verdict == "finding" and c.outbound and c.amount_usd is not None:
            group = key_str(c) if c.cls == "cashback" else c.key.get("invoice_id")
            sums[group] = sums.get(group, Decimal("0")) + c.amount_usd
    conflicts = [c for c in cands if c.verdict == "conflict"]
    for c in cands:
        group = key_str(c) if c.cls == "cashback" else c.key.get("invoice_id")
        if c.verdict == "conflict":
            c.signals["action"] = "escalate"
        elif c.verdict == "no_finding":
            c.signals["action"] = "none"
        elif c.internal and not c.outbound:
            c.signals["action"] = f"internal:{c.internal}"
        elif c.outbound:
            total = sums.get(group, Decimal("0"))
            if c.verdict == "finding" and total >= THRESHOLD:
                c.signals["action"] = "human_review"
            elif mode == "supervised":
                c.signals["action"] = f"draft:{c.outbound}"
            else:
                fails = _unattended_failures(world, c, total, conflicts)
                c.signals["unattended_failures"] = fails
                c.signals["action"] = "human_review" if fails else f"execute:{c.outbound}"
        else:
            c.signals["action"] = "none"


# ---- confidence -----------------------------------------------------------------------------------------------------
def _confidence(c: Candidate) -> float:
    """Heuristic (not calibrated yet): start high for a fully evidenced deterministic result, lower for each weakness."""
    p = 0.95
    if c.verdict == "conflict":
        p = 0.85
    elif c.verdict == "cannot_determine":
        p = 0.8
    sources = set(c.signals.get("pickup_sources") or [])
    if c.cls == "overcharge" and sources - TRUSTED_PICKUP:
        p -= 0.15
    if c.signals.get("unverified"):
        p -= 0.15
    if c.signals.get("unpriced"):
        p -= 0.05
    if c.signals.get("currency") == "INR":
        p -= 0.02
    if len(c.evidence) < 2:
        p -= 0.1
    return round(max(0.05, min(0.99, p)), 2)


# ---- citations ------------------------------------------------------------------------------------------------------
def _resolvable(store, evidence: list[dict]) -> list[dict]:
    """Keep only citations whose quote is really on the cited page (scans: the page must exist)."""
    out, cache = [], {}
    for ev in evidence:
        doc, page, quote = ev.get("doc"), ev.get("page") or 1, ev.get("quote") or ""
        if doc not in cache:
            row = store.document(doc)
            cache[doc] = PageIndex([{"doc": doc, "kind": row["kind"], "is_scan": row["is_scan"],
                                     "pages": store.pages_of(doc)}]) if row else None
        index = cache[doc]
        if index is None:
            continue
        ok = index.page_text(doc, page) is not None if index.scan[doc] else index.quote_on_page(doc, page, quote) is None
        if ok and {"doc": doc, "page": page, "quote": quote} not in out:
            out.append({"doc": doc, "page": page, "quote": quote})
    return out


# ---- assembly -------------------------------------------------------------------------------------------------------
def candidates(world: World, hooks=None) -> list[Candidate]:
    hooks = hooks or {}
    found = []
    found += overcharge.detect(world, hooks.get("rate_overrides", lambda c: []))
    found += duplicate.detect(world)
    found += waiver.detect(world)
    disputed: dict[str, Decimal] = {}
    for c in found:
        if c.verdict == "finding" and c.amount_usd is not None and c.outbound == "dispute":
            disputed[c.key["invoice_id"]] = disputed.get(c.key["invoice_id"], Decimal("0")) + c.amount_usd
    found += late_fees.detect(world, lambda inv: disputed.get(inv, Decimal("0")))
    found += cashback.detect(world)
    found += expiry.detect(world)
    for c in found:
        _to_usd(world, c)
    return found


def build(store, as_of: str, mode: str, hooks=None) -> dict:
    world = World(store, as_of)
    world.feedback = feedback.load(store, as_of)       # decisions known by as_of, applied inside their scope
    cands = candidates(world, hooks)
    unique: dict[str, Candidate] = {}
    for c in cands:                                    # one item per key (a resent invoice is assessed twice)
        unique.setdefault(key_str(c), c)
    cands = world.feedback.post(world, list(unique.values()))   # close / reject / override_amount on their keys
    for c in cands:
        evidence = _resolvable(store, c.evidence)
        valid = {(ev["doc"], ev["page"], ev["quote"]) for ev in evidence}
        rejected = [ev for ev in c.evidence
                    if (ev.get("doc"), ev.get("page") or 1, ev.get("quote") or "") not in valid]
        if rejected:
            c.signals["unverified"] = True
            c.trace["rejected_evidence"] = rejected
        c.evidence = evidence
    _actions(world, cands, mode)
    previous = {r["key"]: r for r in store.db.execute(
        "SELECT * FROM report_history WHERE mode = ? AND as_of < ? ORDER BY as_of", (mode, as_of))}
    prev_as_of = store.db.execute("SELECT max(as_of) FROM report_runs WHERE mode = ? AND as_of < ?",
                                  (mode, as_of)).fetchone()[0]
    report = {"schema_version": SCHEMA_VERSION, "as_of": as_of, "mode": mode, "findings": [],
              "portfolio": {"cashback": [], "expiry": [], "late_fee_risk": []}}
    history_rows = []
    for c in sorted(cands, key=key_str):
        if c.verdict == "no_finding":
            continue
        key = key_str(c)
        amount = c.amount_str()
        evidence = c.evidence
        needed = 2 if c.verdict == "conflict" else 1
        if len(evidence) < needed:
            print(f"report: dropped {key}: fewer than {needed} resolvable evidence entries", file=sys.stderr)
            continue
        item = {"id": key, "class": c.cls, **{k: v for k, v in c.key.items() if k != "class"},
                "verdict": c.verdict, "amount_usd": amount if c.verdict == "finding" else None,
                "amount_range": [money_str(x) for x in c.amount_range] if c.amount_range else None,
                "deadline": c.deadline, "action": c.signals["action"], "confidence": _confidence(c),
                "evidence": evidence, "missing_doc": c.missing_doc, "supersedes": []}
        prev = previous.get(key)
        if prev is None and prev_as_of is not None and "invoice_id" in c.key and c.cls != "late_fee_risk":
            # new key for an invoice already held at the last report: it exists because of a newer document
            held = [d.received_at for h in world.of("invoices") if norm_id(h.get("invoice_id")) == c.key["invoice_id"]
                    for d in [world.docs[h.doc]]]
            c.retro = bool(held) and min(held) <= f"{prev_as_of}T23:59:59Z"
        if prev is not None:
            same = prev["verdict"] == c.verdict and prev["amount"] == (amount or json.dumps(item["amount_range"]))
            if same:
                item["id"] = prev["item_id"]
            else:
                item["id"] = f"{key}@{as_of}"
                item["supersedes"] = [prev["item_id"]]
        elif prev_as_of is not None and c.retro:
            item["retro"] = True
        if c.signals.get("learned_at"):
            item["learned_at"] = c.signals["learned_at"]
        bucket = "findings" if c.cls not in ("cashback", "expiry", "late_fee_risk") else c.cls
        probe = {"as_of": as_of, "mode": mode, "findings": [item] if bucket == "findings" else [],
                 "portfolio": {k: ([item] if k == bucket else []) for k in ("cashback", "expiry", "late_fee_risk")}}
        problems = list(_VALIDATOR.iter_errors(probe))
        if problems:                          # one bad item must never cost the whole report
            print(f"report: dropped {item['id']}: {problems[0].message}", file=sys.stderr)
            continue
        if c.cls == "cashback":
            report["portfolio"]["cashback"].append(item)
        elif c.cls == "expiry":
            report["portfolio"]["expiry"].append(item)
        elif c.cls == "late_fee_risk":
            report["portfolio"]["late_fee_risk"].append(item)
        else:
            report["findings"].append(item)
        history_rows.append((mode, key, as_of, item["id"], c.verdict, amount or json.dumps(item["amount_range"]),
                             json.dumps(item)))
        _write_trace(store, as_of, mode, item, c)
    jsonschema.validate(report, SCHEMA)
    with store.db:
        store.db.execute("DELETE FROM report_history WHERE mode = ? AND as_of = ?", (mode, as_of))
        store.db.executemany("INSERT INTO report_history VALUES (?,?,?,?,?,?,?)", history_rows)
        store.db.execute("INSERT OR IGNORE INTO report_runs VALUES (?, ?)", (mode, as_of))
    return report


def _write_trace(store, as_of: str, mode: str, item: dict, c: Candidate) -> None:
    folder = store.paths["traces"] / as_of / mode
    folder.mkdir(parents=True, exist_ok=True)
    name = item["id"].replace("/", "_").replace(":", "_").replace("@", "_")
    trace = {"trace_version": "1", "written_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "item": item, "signals": {k: v for k, v in c.signals.items() if k != "action"}, "calculation": c.trace,
             "confidence_label": "heuristic, not calibrated"}
    (folder / f"{name}.json").write_text(json.dumps(trace, indent=1, default=str), encoding="utf-8")
