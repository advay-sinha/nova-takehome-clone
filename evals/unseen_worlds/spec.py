"""Case registry and expected-item helpers for the unseen-world suite.

A case is a mailbox plus one or more report points. Each report point lists the complete set of items the glossary
says must be reported as finding, conflict or cannot_determine on that date (anything else reported with one of those
verdicts is a false positive), and the keys that must stay unreported or no_finding (named controls).
"""
from __future__ import annotations

from decimal import Decimal

CASES: dict[str, callable] = {}


def case(case_id: str, world: str, split: str, families: list[str]):
    assert split in ("dev", "holdout")

    def register(fn):
        assert case_id not in CASES, case_id
        fn.meta = {"id": case_id, "world": world, "split": split, "families": families}
        CASES[case_id] = fn
        return fn
    return register


def ikey(invoice_id: str, cls: str) -> dict:
    return {"invoice_id": invoice_id, "class": cls}


def money(x) -> str:
    return f"{Decimal(x):.2f}"


def item(key: dict, verdict: str, why: str, supervised: str, autonomous: str, amount=None, amount_range=None,
         deadline: str | None = None, missing_doc: str | None = None, evidence_docs: list[str] = (),
         learned_at: bool = False, retro: bool = False, supersedes: bool = False) -> dict:
    out = {"key": key, "verdict": verdict, "actions": {"supervised": supervised, "autonomous": autonomous},
           "why": why}
    if amount is not None:
        out["amount_usd"] = money(amount)
    if amount_range is not None:
        out["amount_range"] = [money(a) for a in amount_range]
    if deadline:
        out["deadline"] = deadline
    if missing_doc:
        out["missing_doc"] = missing_doc
    if evidence_docs:
        out["evidence_docs"] = list(evidence_docs)
    if learned_at:
        out["learned_at"] = True
    if retro:
        out["retro"] = True
    if supersedes:
        out["supersedes"] = True
    return out


def control(key: dict, why: str) -> dict:
    return {"key": key, "why": why}


def report(as_of: str, expect: list[dict], controls: list[dict] = (), after: str | None = None) -> dict:
    """A report point, run after ingesting every batch up to and including `after` (default: all batches)."""
    out = {"as_of": as_of, "expect": list(expect), "controls": list(controls)}
    if after:
        out["after"] = after
    return out
