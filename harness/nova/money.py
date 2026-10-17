"""Decimal money helpers. Every rounding in the harness goes through `q2`: half up to cents, ties away from zero
(GLOSSARY "Rounding"). Amounts are parsed from the strings the documents print; floats never touch money."""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")


def dec(value) -> Decimal | None:
    """'1,243.96' / 'USD 1243.96' / '18.38%' / Decimal -> Decimal; None when there is no number."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value))
    if not m:
        return None
    try:
        return Decimal(m.group(0).replace(",", ""))
    except InvalidOperation:
        return None


def q2(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def money_str(x: Decimal) -> str:
    """Report format: 2 decimals, no sign games (callers never report negatives)."""
    return f"{q2(x):.2f}"
