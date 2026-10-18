"""Independent expected-answer arithmetic for the unseen-world cases, written from GLOSSARY.md alone.

Nothing here imports the harness, its rules, its readers or the grader. Every function is a direct transcription of
one glossary formula in Python Decimal, and tests/offline/test_unseen_oracle.py checks each against hand-worked
numbers. The case builders call these with the same printed numbers they put in the documents; the result is what
the glossary says the answer is, whatever the harness does.
"""
from __future__ import annotations

import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def D(x) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


def r2(x) -> Decimal:
    """Half up to cents, ties away from zero (GLOSSARY: Rounding)."""
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)


def line(rate, qty) -> Decimal:
    """A correct line: rate times quantity, rounded half up to cents."""
    return r2(D(rate) * D(qty))


def pct_of(pct, base) -> Decimal:
    """A percentage surcharge on an already-rounded base."""
    return r2(D(pct) / 100 * D(base))


def finding(billed: list, correct: list) -> Decimal:
    """Billed minus correct over the lines of one finding; never negative (an undercharge is no finding)."""
    diff = sum((D(b) for b in billed), Decimal(0)) - sum((D(c) for c in correct), Decimal(0))
    return diff if diff > 0 else Decimal("0.00")


def inr_to_usd(amount_inr, inr_per_usd) -> Decimal:
    """Convert once per finding: round_half_up(amount_inr / fx, 2)."""
    return r2(D(amount_inr) / D(inr_per_usd))


def conflict_range(billed_total, correct_a, correct_b) -> list[Decimal]:
    """[billed - higher correct (never below 0), billed - lower correct]."""
    hi, lo = max(D(correct_a), D(correct_b)), min(D(correct_a), D(correct_b))
    return [max(D(billed_total) - hi, Decimal("0.00")), D(billed_total) - lo]


def late_fee_months(paid: date, due: date, grace_days: int) -> int:
    """Months of fee owed: 0 inside grace, else ceil(days_late / 30)."""
    days_late = (paid - due).days
    if days_late <= grace_days:
        return 0
    return math.ceil(days_late / 30)


def late_fee(principal, pct, months: int, compounding: bool) -> Decimal:
    """Fee for `months` started months; each month round_half_up(r/100 x base, 2). A compounding base adds the
    earlier unpaid fees; a simple base stays the principal."""
    total, base = Decimal("0.00"), D(principal)
    for _ in range(months):
        fee = pct_of(pct, base)
        total += fee
        if compounding:
            base += fee
    return total


def fee_risk(principal, pct) -> Decimal:
    """One month's fee on the open principal (late-fee risk)."""
    return pct_of(pct, principal)


def rebate(qualifying_spend, tiers: list[tuple]) -> Decimal:
    """Highest tier reached applies to all qualifying spend. tiers: [(min_spend, pct), ...]."""
    pct = Decimal(0)
    for threshold, p in sorted(((D(t), D(p)) for t, p in tiers)):
        if D(qualifying_spend) >= threshold:
            pct = p
    return pct_of(pct, qualifying_spend)


def margin_step_down(lines_after_crossing: list[tuple], stepped_pct) -> Decimal:
    """One quarter's margin step-down: over every invoice after the crossing one, billed margin minus the margin at
    the stepped-down percentage of its base. lines_after_crossing: [(base, billed_margin), ...]."""
    return sum((D(billed) - pct_of(stepped_pct, base) for base, billed in lines_after_crossing), Decimal("0.00"))


def in_window(deadline: date, as_of: date, lo: int, hi: int, lo_strict: bool = False) -> bool:
    """lo <= deadline - as_of <= hi (or lo < ... when lo_strict)."""
    d = (deadline - as_of).days
    return (d > lo if lo_strict else d >= lo) and d <= hi
