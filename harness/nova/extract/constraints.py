"""Arithmetic checks inside one billing document, using only the values it prints.

They separate two things the audit must never mix up:
- an extraction problem: the facts we hold for the document do not add up although the document itself does
  (a skipped line, a misread digit, swapped fields). Such documents get the single targeted recheck.
- a document that does not add up as printed: recorded as observed. Its values are never changed to make them agree,
  and a billed amount that differs from the contract is a matter for the audit rules, not for this module.

A line whose own arithmetic fails is only judged an extraction problem when the document's totals point the same way
or the page is OCR text; on a text-layer page whose quoted numbers were verified, it is printed that way.
"""
from __future__ import annotations

from decimal import Decimal

from ..money import dec, q2

TOL = Decimal("0")     # a document's own arithmetic is exact; the grader's 0.01 tolerance is for reported amounts


def _line_expected(line: dict) -> tuple[Decimal | None, str | None]:
    """The amount this line's own printed operands imply, and the formula used. None when not derivable."""
    label = (line.get("charge_label") or "").lower()
    if "minimum" in label:
        return None, None                         # a minimum charge is not rate x quantity
    pct, base = dec(line.get("pct")), dec(line.get("base_amount"))
    if pct is not None and base is not None:
        return q2(base * pct / 100), "base_amount x pct / 100"
    qty, rate = dec(line.get("quantity")), dec(line.get("rate"))
    if qty is not None and rate is not None:
        return q2(qty * rate), "quantity x rate"
    return None, None


def check_document(header: dict | None, lines: list[dict], is_scan: bool) -> dict:
    """header/lines: fact data dicts of one document. Returns
    {'status': 'consistent' | 'extraction_suspect' | 'document_inconsistent' | 'not_checkable',
     'issues': [...], 'recheck_fields': [...]}"""
    issues, suspect_lines = [], []
    for ln in lines:
        expected, formula = _line_expected(ln)
        amount = dec(ln.get("amount"))
        if expected is None or amount is None:
            continue
        if abs(expected - amount) > TOL:
            ref = ln.get("line_no") or ln.get("awb") or ln.get("charge_label")
            issues.append(f"line {ref}: {formula} = {expected} but amount {amount}")
            suspect_lines.append(ref)
    totals_ok = None
    if header is not None:
        sub, tax, total = dec(header.get("subtotal")), dec(header.get("tax")), dec(header.get("total"))
        amounts = [dec(ln.get("amount")) for ln in lines]
        line_sum = sum((a for a in amounts if a is not None), Decimal("0"))
        # The extracted lines may or may not include a printed tax line (H-003: a GST line on an INR invoice), so
        # they must add up to the subtotal, or to the total that includes the tax.
        targets = [t for t in (sub, total, (sub + tax) if sub is not None and tax is not None else None)
                   if t is not None]
        if targets and lines:
            totals_ok = any(abs(line_sum - t) <= TOL for t in targets)
            if not totals_ok:
                issues.append(f"lines sum to {line_sum} but subtotal is {sub} and total is {total}")
        if sub is not None and total is not None:
            if abs(sub + (tax or Decimal("0")) - total) > TOL:
                issues.append(f"subtotal {sub} + tax {tax or 0} != total {total}")
                totals_ok = False
    if not issues:
        status = "consistent" if (lines or header) else "not_checkable"
        return {"status": status, "issues": [], "recheck_fields": []}
    # Totals that do not match the extracted lines usually mean a line was skipped or misread; so does any arithmetic
    # failure on OCR text. A text-layer line whose own arithmetic fails while the totals agree is printed that way.
    if is_scan or totals_ok is False:
        fields = [f"line {r}" for r in suspect_lines] + (["all line amounts and the totals"] if totals_ok is False else [])
        return {"status": "extraction_suspect", "issues": issues, "recheck_fields": fields}
    return {"status": "document_inconsistent", "issues": issues, "recheck_fields": []}
