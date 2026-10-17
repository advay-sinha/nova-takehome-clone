"""Duplicates (GLOSSARY "Duplicates").

1. Same invoice number sent twice: a finding only when the ledger shows it paid or scheduled and the later copy asks
   for payment again; a copy, reminder or "for your records" resend is fine. Amount: the invoice total.
2. Two invoice numbers billing the same shipment line (same AWB, or house AWB when given, and the same Annex E charge
   code): flag the invoice with the later invoice date, for the duplicated lines only, less any credit note that
   reverses them. A shared master AWB alone is not a duplicate.
"""
from __future__ import annotations

from decimal import Decimal

from ..money import dec, q2
from ..world import World, norm_id, to_date
from .common import Candidate

ZERO = Decimal("0")
SKIP_CODES = {"TAX", "DUTY", "LATE"}


def _ledger(world: World) -> dict[str, object]:
    """Latest ledger row per invoice (rows from later-received registers win)."""
    rows = sorted(world.of("ledger_rows"), key=lambda f: (world.docs[f.doc].received_at, f.id))
    return {norm_id(f.get("invoice_id")): f for f in rows}


def detect(world: World) -> list[Candidate]:
    found: dict[str, Candidate] = {}
    ledger = _ledger(world)
    headers = sorted(world.of("invoices"), key=lambda f: (world.docs[f.doc].received_at, f.doc))
    # ---- 1. the same invoice number sent again --------------------------------------------------------------------
    by_id: dict[str, list] = {}
    for h in headers:
        by_id.setdefault(norm_id(h.get("invoice_id")), []).append(h)
    asks = {}
    for f in world.of("payment_requests"):
        asks.setdefault(norm_id(f.get("invoice_id")), []).append(f)
    for inv, copies in by_id.items():
        emails = []
        for h in copies:
            e = world.docs[h.doc].email_doc
            if e not in emails:
                emails.append(e)
        if len(emails) < 2:
            continue
        row = ledger.get(inv)
        if row is None or str(row.get("status") or "").lower() not in ("paid", "scheduled"):
            continue
        for later in emails[1:]:
            reqs = [r for r in asks.get(inv, []) if world.docs[r.doc].email_doc == later]
            # The ledger shows it paid or scheduled, so a resend that asks for payment, or reminds the reader to pay,
            # requests the money a second time; a copy or for-records resend does not.
            if not any(r.get("kind") in ("asks_payment", "reminder") for r in reqs):
                continue
            total = dec(next(h for h in copies if world.docs[h.doc].email_doc == later).get("total"))
            if total is None or total <= 0:
                continue
            c = Candidate("duplicate", {"invoice_id": inv, "class": "duplicate"}, "finding", amount_usd=q2(total),
                          outbound="dispute")
            c.add_evidence(row.evidence())
            for r in reqs:
                c.add_evidence(r.evidence())
            hdr = world.contract_of(copies[0].get("contract_id"))
            c.contract_id = hdr.id if hdr else None
            c.signals = {"currency": (copies[0].get("currency") or "USD").upper(), "kind": "resend"}
            c.trace = {"formula": "duplicate.resend_total", "ledger_status": row.get("status"),
                       "total": str(total), "resend_email": later}
            found[inv] = c
            break
    # ---- 2. the same shipment line under two invoice numbers -------------------------------------------------------
    first_seen: dict[tuple, tuple] = {}
    lines_by_doc: dict[str, list] = {}
    for f in world.of("invoice_lines"):
        lines_by_doc.setdefault(f.doc, []).append(f)
    dated = sorted(((to_date(h.get("invoice_date")) or to_date(world.docs[h.doc].received_at), h) for h in headers),
                   key=lambda x: (x[0], x[1].doc))
    seen_ids = set()
    for inv_date, h in dated:
        inv = norm_id(h.get("invoice_id"))
        if inv in seen_ids:
            continue                                      # resends of the same number are handled above
        seen_ids.add(inv)
        contract = world.contract_of(h.get("contract_id"))
        dup_lines = []
        for ln in lines_by_doc.get(h.doc, []):
            code = contract.code_for(ln.get("charge_label")) if contract else None
            if code in SKIP_CODES:
                continue
            shipment = norm_id(ln.get("house_awb") or ln.get("awb"))
            ref = shipment or norm_id(ln.get("period_ref"))
            if not ref or not code:
                continue
            k = (contract.id if contract else None, ref, code)
            if k in first_seen and first_seen[k][0] != inv:
                dup_lines.append((ln, first_seen[k][1]))
            else:
                first_seen.setdefault(k, (inv, ln))
        if not dup_lines:
            continue
        amount = sum((dec(ln.get("amount")) or ZERO for ln, _ in dup_lines), ZERO)
        credited = ZERO
        for cn in world.of("credit_notes"):
            refs = {norm_id(cn.get("refers_to_invoice")), norm_id(cn.get("refers_to_awb"))}
            if inv in refs or any(norm_id(ln.get("house_awb") or ln.get("awb")) in refs for ln, _ in dup_lines):
                if cn.get("credit_type") in ("invoice_correction", "other", None):
                    credited += dec(cn.get("amount")) or ZERO
        owed = amount - credited
        if owed <= 0:
            continue
        c = found.get(inv) or Candidate("duplicate", {"invoice_id": inv, "class": "duplicate"}, "finding",
                                        outbound="dispute", contract_id=contract.id if contract else None)
        c.amount_usd = q2(owed)
        for ln, earlier in dup_lines:
            c.add_evidence(earlier.evidence())
            c.add_evidence(ln.evidence())
        if contract:
            for code in {contract.code_for(ln.get("charge_label")) for ln, _ in dup_lines}:
                if code in contract.code_facts and norm_id(code) not in ("FRT",):
                    c.add_evidence(contract.code_facts[code].evidence())
        c.signals = {"currency": (h.get("currency") or "USD").upper(), "kind": "rebilled"}
        c.trace = {"formula": "duplicate.overlap_minus_credit", "duplicated": [
            {"label": ln.get("charge_label"), "amount": ln.get("amount"), "first_billed_on": e.get("invoice_id")}
            for ln, e in dup_lines], "credited": str(credited)}
        found[inv] = c
    return list(found.values())
