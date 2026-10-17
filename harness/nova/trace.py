"""Replay internal traces: recompute each reported amount from the typed operands its trace recorded, with an
allowlisted formula per finding type (no eval, nothing from model text). A mismatch means the report and its own
calculation disagree. Replay shows consistency only: it does not prove an extraction or a business rule right."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from .money import dec, q2

ZERO = Decimal("0")


def _fx(calc: dict, amount: Decimal) -> Decimal:
    fx = calc.get("fx") or {}
    rate = dec(fx.get("inr_per_usd"))
    return q2(amount / rate) if rate else q2(amount)


def _overcharge(calc, item):
    total = sum((max(ZERO, dec(s["billed"]) - dec(s["correct"])) for s in calc.get("lines", [])), ZERO)
    return _fx(calc, total)


def _resend(calc, item):
    return q2(dec(calc["total"]))


def _overlap(calc, item):
    total = sum((dec(x["amount"]) for x in calc.get("duplicated", [])), ZERO) - (dec(calc.get("credited")) or ZERO)
    return _fx(calc, total)


def _waiver(calc, item):
    return _fx(calc, sum((dec(x["amount"]) for x in calc.get("lines", [])), ZERO))


def _late_not_owed(calc, item):
    billed = sum((dec(t["billed"]) for t in calc.get("targets", [])), ZERO)
    correct = sum((dec(t["correct"]) for t in calc.get("targets", [])), ZERO)
    return _fx(calc, billed - correct)


def _late_risk(calc, item):
    return _fx(calc, q2(dec(calc["pct"]) / 100 * dec(calc["principal"])))


def _rebate(calc, item):
    return q2(q2(dec(calc["qs_usd"]) * dec(calc["tier_pct"]) / 100) - dec(calc["credited"]))


def _annual(calc, item):
    return q2(q2(dec(calc["qs_usd"]) * dec(calc["pct"]) / 100) - dec(calc["credited"]))


def _margin(calc, item):
    """Each line's excess recomputes from base x stepped-down %; a USD invoice's excess is its own USD amount."""
    total = ZERO
    for inv in calc.get("invoices", []):
        excess = sum((dec(ln["billed"]) - q2(dec(ln["base"]) * dec(ln["pct_to"]) / 100) for ln in inv["lines"]), ZERO)
        if excess != dec(inv["excess"]) or (inv["currency"].upper() != "INR" and excess != dec(inv["excess_usd"])):
            return None
        total += dec(inv["excess_usd"])
    return q2(total) - dec(calc["credited"])


FORMULAS = {
    "overcharge.sum_positive_line_diffs": _overcharge,
    "duplicate.resend_total": _resend,
    "duplicate.overlap_minus_credit": _overlap,
    "waiver.sum_waived_lines": _waiver,
    "late_fee.billed_minus_correct": _late_not_owed,
    "late_fee.one_month_risk": _late_risk,
    "cashback.rebate": _rebate,
    "cashback.annual_credit": _annual,
    "cashback.margin_step_down": _margin,
}


def replay(trace: dict) -> tuple[bool, str]:
    item, calc = trace["item"], trace.get("calculation") or {}
    formula = calc.get("formula")
    if item.get("verdict") != "finding":
        return True, f"{item['id']}: {item.get('verdict')}, no amount to replay"
    if formula == "expiry.window":
        days = (date.fromisoformat(calc["operative_date"]) - date.fromisoformat(item["deadline"])).days
        return days == 0, f"{item['id']}: deadline {'matches' if days == 0 else 'differs from'} the operative date"
    if "override_amount" in calc:
        expected = q2(dec(calc["override_amount"]["amount_usd"]))
    elif formula in FORMULAS:
        expected = FORMULAS[formula](calc, item)
    else:
        return False, f"{item['id']}: unknown formula {formula!r}"
    reported = dec(item.get("amount_usd"))
    ok = reported is not None and expected == reported
    return ok, f"{item['id']}: replayed {expected}, reported {reported}"


def replay_dir(state_dir: str | Path, as_of: str, mode: str) -> list[tuple[bool, str]]:
    folder = Path(state_dir) / "traces" / as_of / mode
    return [replay(json.loads(p.read_text(encoding="utf-8"))) for p in sorted(folder.glob("*.json"))]
