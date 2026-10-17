"""Expiry (GLOSSARY "Expiry"): a contract whose operative date is 0-60 days after as_of. The operative date is the end
of the term, or the non-renewal notice deadline when the contract renews itself; a signed extension (an amendment
that sets a later end) moves it. Internal alert only; no money."""
from __future__ import annotations

from datetime import timedelta

from ..money import dec
from ..world import World, to_date
from .common import Candidate


def operative_date(contract) -> tuple:
    """(date, evidence) from the agreement's term, moved by the latest signed amendment that sets a new end."""
    term, ev = contract.block("term"), None
    end = to_date(term.get("initial_term_end"))
    src = term.get("source")
    for amd in sorted(contract.amendments, key=lambda a: a.effective or to_date("1900-01-01")):
        t = amd.fact.get("term") or {}
        if amd.signed is not False and to_date(t.get("initial_term_end")):
            end, term, src = to_date(t.get("initial_term_end")), t, t.get("source") or amd.fact.data.get("_source")
    if src:
        ev = src | {"page": src.get("page") or 1}
    if term.get("auto_renews"):
        deadline = to_date(term.get("non_renewal_notice_deadline"))
        days = dec(term.get("non_renewal_notice_days"))
        if deadline is None and end is not None and days is not None:
            deadline = end - timedelta(days=int(days))
        return deadline, ev
    return end, ev


def detect(world: World) -> list[Candidate]:
    found = []
    for contract in world.contracts.values():
        if contract.msa is None:
            continue
        when, ev = operative_date(contract)
        if when is None:
            continue
        gap = (when - world.as_of_date).days
        if 0 <= gap <= 60:
            c = Candidate("expiry", {"contract_id": contract.id}, "finding", deadline=when.isoformat(),
                          internal="alert", contract_id=contract.id,
                          trace={"formula": "expiry.window", "operative_date": str(when), "days_left": gap})
            c.add_evidence(ev)
            if not c.evidence:
                c.add_evidence(contract.msa.fact.evidence())      # no quoted term clause: cite the agreement
            found.append(c)
    return found
