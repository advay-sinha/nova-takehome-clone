"""What a detector returns: one candidate per finding key, with its evidence and a typed calculation trace."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..money import money_str


@dataclass
class Candidate:
    cls: str                       # overcharge | duplicate | waived_but_billed | late_fee_not_owed | late_fee_risk |
                                   # cashback | expiry
    key: dict                      # invoice_id / contract_id, period, credit_type
    verdict: str                   # finding | no_finding | conflict | cannot_determine
    amount_usd: Decimal | None = None
    amount_range: tuple[Decimal, Decimal] | None = None
    deadline: str | None = None
    evidence: list[dict] = field(default_factory=list)
    missing_doc: dict | None = None
    outbound: str | None = None    # dispute | claim_credit | request_document (None = internal or no action)
    internal: str | None = None    # alert | payment_reminder | track_credit
    contract_id: str | None = None
    lane: str | None = None
    signals: dict = field(default_factory=dict)    # inputs for confidence and the unattended-action test
    trace: dict = field(default_factory=dict)      # typed operands and steps; written under --state-dir/traces
    retro: bool = False

    def add_evidence(self, ev: dict | None) -> None:
        if ev and ev.get("quote") and ev not in self.evidence:
            self.evidence.append(ev)

    def amount_str(self) -> str | None:
        return money_str(self.amount_usd) if self.amount_usd is not None else None
