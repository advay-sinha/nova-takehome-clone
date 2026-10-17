"""A person's decisions (GLOSSARY "feedback.json") applied to later reports without spreading beyond their scope.

- A feedback fact counts (as authority level 2) only in reports dated on or after its decided_at.
- A standing fact applies only when every applies_to filter matches and the document or shipment is dated inside
  valid_from..valid_to. A one-off decision changes its finding key and nothing else.
- Every item that changes because of feedback carries learned_at {feedback_item_id, batch}.

Decisions: confirm (sender_authority: the person may act for that contract and category), close (dispute_closed: stop
raising the key; rate_accepted: also treat the named notice as the rate for that contract and lane inside the dates),
reject (the key is not a finding), override_amount (use the given amount), resolve_conflict (precedence: use the named
source for that contract and lane from valid_from), one_off_approval (waiver_scope: the waiver covers the named months
on that key only).
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from .money import dec, q2
from .world import norm_id, norm_label, to_date


class Item:
    def __init__(self, raw: dict, envelope: dict):
        self.raw = raw
        self.id = raw.get("item_id")
        self.batch = envelope.get("after_batch")
        self.decided = to_date(envelope.get("decided_at"))
        self.decision = raw.get("decision")
        fact = raw.get("fact") or {}
        self.fact_type, self.subject, self.value = fact.get("type"), fact.get("subject") or {}, fact.get("value") or {}
        scope = raw.get("scope") or {}
        self.scope_kind = scope.get("kind")
        self.applies_to = scope.get("applies_to") or {}
        self.valid_from, self.valid_to = to_date(scope.get("valid_from")), to_date(scope.get("valid_to"))
        key = raw.get("finding_key") or {}
        self.key = (key.get("class"), norm_id(key.get("invoice_id") or key.get("contract_id")), key.get("period"),
                    key.get("credit_type"))

    def learned(self) -> dict:
        return {"feedback_item_id": self.id, "batch": self.batch}

    def in_window(self, when: date | None) -> bool:
        if when is None:
            return False
        return (self.valid_from is None or when >= self.valid_from) and (self.valid_to is None or when <= self.valid_to)

    def matches(self, **filters) -> bool:
        """Every applies_to filter must match the given values (case/space-insensitive)."""
        for k, want in self.applies_to.items():
            if want is None:
                continue
            got = filters.get(k)
            if got is None:
                return False
            n = norm_label if k in ("person", "category") else norm_id
            if n(got) != n(want):
                return False
        return True


class FeedbackState:
    def __init__(self, store, as_of: str):
        cutoff = date.fromisoformat(as_of)
        self.items: list[Item] = []
        for r in store.db.execute("SELECT body_json FROM feedback_files ORDER BY decided_at, loaded_at"):
            body = json.loads(r["body_json"])
            for raw in body.get("items") or []:
                it = Item(raw, body)
                if it.decided is not None and it.decided <= cutoff:     # known only from decided_at
                    self.items.append(it)

    # ---- standing facts used by the rules ----------------------------------------------------------------------------
    def grant(self, contract_id: str, category: str, person: str, when: date | None) -> Item | None:
        for it in self.items:
            if it.decision == "confirm" and it.fact_type == "sender_authority" and it.scope_kind == "standing":
                cats = {norm_label(c) for c in (it.value.get("categories") or [])}
                if norm_label(category) in cats and it.matches(contract_id=contract_id, person=person,
                                                               category=category) \
                        and norm_label(it.subject.get("person")) == norm_label(person) and it.in_window(when):
                    return it
        return None

    def rate_accepted(self, contract_id: str, lane: str, pickup: date) -> Item | None:
        for it in self.items:
            if it.fact_type == "rate_accepted" and it.scope_kind == "standing" \
                    and it.matches(contract_id=contract_id, lane=lane) and it.in_window(pickup):
                return it
        return None

    def precedence(self, contract_id: str, lane: str, pickup: date) -> Item | None:
        for it in self.items:
            if it.decision == "resolve_conflict" and it.fact_type == "precedence" \
                    and it.matches(contract_id=contract_id, lane=lane) and it.in_window(pickup):
                return it
        return None

    def approval(self, invoice_id: str) -> Item | None:
        for it in self.items:
            if it.decision == "one_off_approval" and it.fact_type == "waiver_scope" \
                    and norm_id(it.applies_to.get("invoice_id") or it.key[1]) == norm_id(invoice_id):
                return it
        return None

    # ---- key-level decisions after detection -------------------------------------------------------------------------
    def post(self, world, cands: list) -> list:
        out = []
        for c in cands:
            k = (c.cls, norm_id(c.key.get("invoice_id") or c.key.get("contract_id")), c.key.get("period"),
                 c.key.get("credit_type"))
            decided = [it for it in self.items if it.key == k]
            if any(it.decision in ("close", "reject") for it in decided):
                continue                                         # stop raising this key (only this key)
            for it in decided:
                if it.decision == "override_amount" and (amt := dec(it.value.get("amount_usd"))) is not None:
                    c.verdict, c.amount_usd, c.amount_range = "finding", q2(amt), None
                    c.signals["learned_at"] = it.learned()
                    c.trace["override_amount"] = {"feedback_item": it.id, "amount_usd": str(amt)}
            out.append(c)
        return out


def load(store, as_of: str) -> FeedbackState:
    return FeedbackState(store, as_of)
