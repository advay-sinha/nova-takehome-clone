"""What a detector returns: one candidate per finding key, with its evidence and a typed calculation trace."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

from ..money import money_str

NOT_PAID = re.compile(r"\b(?:unpaid|not\s+paid|partially|part[\s-]paid|unsettled|not\s+settled)\b", re.I)
PAID = re.compile(r"\b(?:paid|settled|cleared|remitted)\b", re.I)
SCHEDULED = re.compile(r"\b(?:scheduled|approved\s+for\s+payment|in\s+payment\s+run)\b", re.I)
OPEN = re.compile(r"\b(?:open|unpaid|outstanding|due|overdue|not\s+paid|unsettled|partially(?:\s+paid)?|part[\s-]paid)\b",
                  re.I)


def ledger_state(row) -> str | None:
    """'paid', 'scheduled' or 'open' from a payment-ledger row, whatever words the ledger uses ("Settled",
    "Cleared", "Outstanding"); None when the status says none of these."""
    status = str(row.get("status") or "")
    yes_no = status.strip().lower().rstrip(".")
    if yes_no in ("yes", "y", "true") and not row.get("scheduled_date"):     # a "Paid?" column
        return "paid"
    if yes_no in ("no", "n", "false") and not row.get("paid_date"):
        return "open"
    if not NOT_PAID.search(status) and (PAID.search(status) or row.get("paid_date")):
        return "paid"
    if SCHEDULED.search(status):
        return "scheduled"
    if OPEN.search(status):
        return "open"
    return None


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
