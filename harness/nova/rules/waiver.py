"""Waived but billed (GLOSSARY "Waivers").

A waiver counts when the contract's Schedule 1 waivers contact wrote it in their own email, it names the shipment or
month, and any condition it sets was met. A waiver from anyone else is no finding. A waiver seen only quoted inside
someone else's message is cannot_determine: ask for the original (its author if they are the Schedule 1 waivers
contact, otherwise the carrier's Key Account Manager). It covers only what it names: never later charges.
"""
from __future__ import annotations

import re
from decimal import Decimal

from ..money import dec, q2
from ..world import World, norm_id, norm_label, to_date
from .common import Candidate

ZERO = Decimal("0")
# Words that make a sentence a requirement on the waiver, and words of a note on how to settle the bill.
REQUIREMENT = re.compile(r"\b(provided|providing|subject to|on condition|conditional|only if|as long as|so long as|"
                         r"unless|in return|in exchange|on the basis that|on receipt of|once you|if you|if the "
                         r"(?:shipper|customer|volume|payment|invoice is paid)|by \d{1,2} \w+|before \d)", re.I)
HANDLING = re.compile(r"short[- ]?pay|leave (?:that|the|this) (?:charge|line|amount)? ?unpaid|credit note|deduct|"
                      r"already (?:been )?invoiced|pay the (?:balance|rest)|remit the (?:balance|rest)|"
                      r"no (?:further )?action", re.I)


def real_condition(text: str | None) -> bool:
    """True when the extracted `condition` sets a requirement; a note on how to settle the bill sets none."""
    if not text or not str(text).strip():
        return False
    return bool(REQUIREMENT.search(text)) or not HANDLING.search(text)


def _covered(world, waiver, contract, line) -> bool:
    if contract.code_for(line.get("charge_label")) != contract.code_for(waiver.get("charge")):
        return False
    awbs = {norm_id(a) for a in waiver.get("awbs") or []}
    if awbs:
        return norm_id(line.get("house_awb") or line.get("awb")) in awbs or norm_id(line.get("awb")) in awbs
    months = {str(m)[:7] for m in waiver.get("months") or []}
    if months:
        pickup = world.pickup(line.get("awb"), line)[0] if line.get("awb") else to_date(line.get("pickup_date"))
        when = pickup.isoformat()[:7] if pickup else str(line.get("period_ref") or "")[:7]
        return when in months
    invoices = {norm_id(i) for i in waiver.get("invoice_ids") or []}
    return bool(invoices) and norm_id(line.get("invoice_id")) in invoices


def _approved(world, approval, waiver, contract, line) -> bool:
    """A one-off approval: the named person's waiver covers the named months on this key only."""
    if approval is None or contract.code_for(line.get("charge_label")) != contract.code_for(waiver.get("charge")):
        return False
    who = norm_label(approval.subject.get("person"))
    author = norm_label(waiver.get("quoted_author") or world.docs[world.docs[waiver.doc].email_doc].sender_name)
    if who and who not in author:
        return False
    months = {str(m)[:7] for m in approval.value.get("months") or []}
    pickup = world.pickup(line.get("awb"), line)[0] if line.get("awb") else to_date(line.get("pickup_date"))
    when = pickup.isoformat()[:7] if pickup else str(line.get("period_ref") or "")[:7]
    return not months or when in months


def detect(world: World) -> list[Candidate]:
    found: dict[str, Candidate] = {}
    headers = {f.doc: f for f in world.of("invoices")}
    for waiver in world.of("waivers"):
        for line in world.of("invoice_lines"):
            hdr = headers.get(line.doc)
            contract = world.contract_of(hdr.get("contract_id")) if hdr else None
            if contract is None:
                continue
            inv = norm_id(hdr.get("invoice_id"))
            approval = world.feedback.approval(inv) if world.feedback else None
            approved = _approved(world, approval, waiver, contract, line)
            if not approved and not _covered(world, waiver, contract, line):
                continue
            key = {"invoice_id": inv, "class": "waived_but_billed"}
            if waiver.get("is_quoted_or_forwarded") and not approved:
                author = waiver.get("quoted_author") or ""
                person = next((p for p in contract.persons if "waivers" in p.categories
                               and norm_label(p.name) and norm_label(p.name) in norm_label(author)), None)
                holder = person or next((p for p in contract.persons if "notices" in p.categories
                                         and "keyaccount" in norm_label(p.title)), None) or contract.contact("notices")
                if inv not in found:
                    found[inv] = Candidate("waived_but_billed", key, "cannot_determine", outbound="request_document",
                                           contract_id=contract.id,
                                           missing_doc={"name": f"original waiver email from {author or 'the quoted sender'}",
                                                        "holder": {k: v for k, v in {"party": holder.party if holder else None,
                                                                                    "person": holder.name if holder else None,
                                                                                    "role": holder.title if holder else None}.items() if v}},
                                           evidence=[waiver.evidence(), line.evidence()])
                continue
            person, granted = world.authorized(contract, waiver.doc, "waivers")
            if approved:
                person, granted = person, approval
            elif person is None:
                continue                                    # no authority: the charge is owed
            if real_condition(waiver.get("condition")) and not approved:
                continue                                    # a conditional waiver needs proof the condition was met
            billed = dec(line.get("amount")) or ZERO
            if billed <= 0:
                continue
            c = found.get(inv)
            if c is None or c.verdict != "finding":
                c = Candidate("waived_but_billed", key, "finding", amount_usd=ZERO, outbound="dispute",
                              contract_id=contract.id, signals={"currency": (hdr.get("currency") or "USD").upper()},
                              trace={"formula": "waiver.sum_waived_lines", "lines": []})
                found[inv] = c
            if line.evidence() in c.evidence:
                continue
            c.amount_usd = q2(c.amount_usd + billed)
            c.trace["lines"].append({"label": line.get("charge_label"), "amount": str(billed), "waiver": waiver.doc,
                                     "waived_by": person.name if person else None,
                                     "feedback": granted.id if granted else None})
            if granted is not None:
                c.signals["learned_at"] = granted.learned()
            for ev in (waiver.evidence(), person.fact.evidence() if person and person.fact else None,
                       line.evidence()):
                c.add_evidence(ev)
    return list(found.values())
