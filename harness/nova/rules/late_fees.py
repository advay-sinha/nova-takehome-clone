"""Late fees (GLOSSARY "Late fees").

Not owed: days_late = paid date - due date, where the due date is the extended one if the contract's payment-terms
contact extended it in their own email. No fee within the grace days; otherwise ceil(days_late / 30) months, each
round_half_up(r% x base): compounding bases add the earlier unpaid fees, simple bases do not. The finding is billed
fees minus the correct fee, on the invoice that billed them.

Risk: an unpaid invoice whose due date is 1-14 days after as_of: one month's fee on the open amount less anything
already disputed on it, in the invoice's currency (converted once later), deadline = the due date.
"""
from __future__ import annotations

import math
from decimal import Decimal

from ..money import dec, q2
from ..world import World, norm_id, norm_label, to_date
from .common import Candidate, ledger_state
from .duplicate import _ledger

ZERO = Decimal("0")


def due_date(world: World, contract, inv: str, ledger_row, header) -> tuple:
    """(due date, the extension fact used or None, the feedback item that authorised it or None). Only the
    payment-terms contact's own email (or a person feedback confirmed for that category) extends it."""
    due = to_date(ledger_row.get("due_date")) if ledger_row is not None else None
    if due is None and header is not None:
        due = to_date(header.get("due_date"))
    best, best_item = None, None
    for f in world.of("due_date_extensions"):
        if norm_id(f.get("invoice_id")) != inv or f.get("is_quoted_or_forwarded") or contract is None:
            continue
        person, item = world.authorized(contract, f.doc, "payment_terms")
        if person is None:
            continue
        new = to_date(f.get("new_due_date"))
        if new and (best is None or world.docs[f.doc].received_at > world.docs[best.doc].received_at):
            best, best_item = f, item
    if best is not None:
        return to_date(best.get("new_due_date")), best, best_item
    return due, None, None


def correct_fee(principal: Decimal, pct: Decimal, days_late: int, grace: int, compounding: bool) -> tuple:
    if days_late <= grace or days_late <= 0:
        return ZERO, []
    months = math.ceil(days_late / 30)
    base, total, steps = principal, ZERO, []
    for i in range(months):
        fee = q2(pct / 100 * base)
        steps.append({"month": i + 1, "base": str(base), "fee": str(fee)})
        total += fee
        if compounding:
            base += fee
    return total, steps


def detect(world: World, disputed=lambda inv: ZERO) -> list[Candidate]:
    found = []
    ledger = _ledger(world)
    headers = {norm_id(h.get("invoice_id")): h for h in world.of("invoices")}
    # ---- fees billed that are not owed -----------------------------------------------------------------------------
    by_invoice: dict[str, list] = {}
    for ln in world.of("invoice_lines"):
        hdr = headers.get(norm_id(ln.get("invoice_id")))
        contract = world.contract_of(hdr.get("contract_id")) if hdr else None
        is_late = (contract.code_for(ln.get("charge_label")) == "LATE") if contract else False
        if is_late or "latefee" in norm_label(ln.get("charge_label")):
            by_invoice.setdefault(norm_id(ln.get("invoice_id")), []).append(ln)
    for inv, fee_lines in by_invoice.items():
        hdr = headers.get(inv)
        contract = world.contract_of(hdr.get("contract_id")) if hdr else None
        if contract is None:
            continue
        pay = contract.block("payment")
        pct, grace = dec(pay.get("late_fee_pct_per_month")), int(dec(pay.get("grace_days")) or 0)
        if pct is None:
            continue
        per_target: dict[str, list] = {}
        known = set(ledger) | set(headers)
        for ln in fee_lines:
            target = norm_id(ln.get("refers_to_invoice"))
            if not target:              # "Late fee on <invoice>: ..." when the field itself was not filled
                label = norm_id(ln.get("charge_label"))
                target = max((k for k in known if k and k in label and k != inv), key=len, default="")
            per_target.setdefault(target, []).append(ln)
        billed_total, correct_total, steps, evidence, learned = ZERO, ZERO, [], [], None
        for target, lines in per_target.items():
            row = ledger.get(target)
            paid = to_date(row.get("paid_date")) if row is not None else None
            due, ext, fb_item = due_date(world, contract, target, row, headers.get(target))
            learned = learned or (fb_item.learned() if fb_item else None)
            principal = (dec(row.get("amount")) if row is not None else None) or dec(lines[0].get("base_amount"))
            if not target or paid is None or due is None or principal is None:
                continue                                    # cannot judge without paid date, due date and principal
            principal -= disputed(target)
            days = (paid - due).days
            correct, fee_steps = correct_fee(principal, pct, days, grace, bool(pay.get("compounding")))
            billed = sum((dec(x.get("amount")) or ZERO for x in lines), ZERO)
            billed_total += billed
            correct_total += correct
            steps.append({"late_invoice": target, "due": str(due), "extended_by": ext.doc if ext else None,
                          "paid": str(paid), "days_late": days, "grace": grace, "pct": str(pct),
                          "principal": str(principal), "fees": fee_steps, "correct": str(correct),
                          "billed": str(billed)})
            if billed > correct:
                if ext is not None:
                    evidence.append(ext.evidence())
                if row is not None:
                    evidence.append(row.evidence())
                evidence += [x.evidence() for x in lines]
        over = billed_total - correct_total
        if over > 0:
            c = Candidate("late_fee_not_owed", {"invoice_id": inv, "class": "late_fee_not_owed"}, "finding",
                          amount_usd=q2(over), outbound="dispute", contract_id=contract.id,
                          signals={"currency": (hdr.get("currency") or "USD").upper()},
                          trace={"formula": "late_fee.billed_minus_correct", "targets": steps})
            if learned:
                c.signals["learned_at"] = learned
            for ev in evidence:
                c.add_evidence(ev)
            if pay.get("source"):
                c.add_evidence(pay["source"] | {"page": pay["source"].get("page") or 1})
            found.append(c)
    # ---- unpaid invoices about to start costing a fee ---------------------------------------------------------------
    for inv, row in ledger.items():
        if ledger_state(row) != "open":
            continue
        hdr = headers.get(inv)
        contract = world.contract_of(hdr.get("contract_id")) if hdr else None
        if contract is None and len(world.contracts) == 1:
            contract = next(iter(world.contracts.values()))
        if contract is None:
            continue
        pay = contract.block("payment")
        pct = dec(pay.get("late_fee_pct_per_month"))
        due, ext, fb_item = due_date(world, contract, inv, row, hdr)
        amount = dec(row.get("amount"))
        if pct is None or due is None or amount is None:
            continue
        gap = (due - world.as_of_date).days
        if not 0 < gap <= 14:
            continue
        principal = amount - disputed(inv)
        fee = q2(pct / 100 * principal)
        c = Candidate("late_fee_risk", {"invoice_id": inv, "class": "late_fee_risk"}, "finding", amount_usd=fee,
                      deadline=due.isoformat(), internal="payment_reminder", contract_id=contract.id,
                      signals={"currency": (row.get("currency") or (hdr.get("currency") if hdr else None) or "USD").upper(),
                               "invoice_date": row.get("invoice_date")},
                      trace={"formula": "late_fee.one_month_risk", "principal": str(principal), "pct": str(pct),
                             "due": str(due), "days_to_due": gap})
        if fb_item is not None:
            c.signals["learned_at"] = fb_item.learned()
        c.add_evidence(row.evidence())
        if ext is not None:
            c.add_evidence(ext.evidence())
        if pay.get("source"):
            c.add_evidence(pay["source"] | {"page": pay["source"].get("page") or 1})
        found.append(c)
    return found
