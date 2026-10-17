"""Check every extracted item against the pages it cites. Model output is a proposal; only what this module confirms
reaches the audit rules.

- rejected:   the cited doc is not part of the input, the page does not exist, or the quote is not on that page
              (or is shorter than 12 non-space characters). The item is dropped from use and kept for the record.
- unverified: the quote is real, but a number or date the item states cannot be found on the cited page.
              Eligible for the single targeted recheck; rules treat its values as uncertain.
- ok:         quote found and every checked value found on the page.

Matching collapses whitespace and applies NFKC. OCR pages (which drop spaces) are compared with all spaces removed.
"""
from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

MIN_QUOTE = 12

# Which fields of each fact list are numbers or dates that must appear on the cited page.
NUMERIC_FIELDS = {
    "rate_rows": ["rate"], "fuel_rows": ["pct"], "accessorials": ["fee"], "fx_rows": ["inr_per_usd"],
    "invoices": ["total"], "invoice_lines": ["quantity", "rate", "pct", "base_amount", "amount"],
    "credit_notes": ["amount"], "ledger_rows": ["amount"], "rate_notices": ["rate"],
    "air_waybills": ["actual_weight_kg", "chargeable_weight_kg", "total_chargeable_weight_kg"],
}
DATE_FIELDS = {
    "invoices": ["invoice_date", "due_date"], "invoice_lines": ["pickup_date"], "credit_notes": ["credit_date"],
    "ledger_rows": ["invoice_date", "due_date", "paid_date"], "status_events": ["date"],
    "rate_notices": ["effective_from"], "due_date_extensions": ["new_due_date"], "air_waybills": ["executed_date"],
}
MONTH_FIELDS = {"fuel_rows": ["month"], "fx_rows": ["month"]}
NESTED_BLOCKS = ("term", "payment", "rebate", "margin", "annual_credit", "pricing_rules", "precedence")
BLOCK_NUMERIC = {
    "term": ["renewal_term_months", "non_renewal_notice_days"],
    "payment": ["due_days_after_invoice", "late_fee_pct_per_month", "grace_days"],
    "rebate": ["credit_due_days_after_period"],
    "margin": ["margin_pct", "step_down_pct", "step_down_by_pct", "step_down_threshold"],
    "annual_credit": ["pct_of_prior_year_qs", "due_days_after_anniversary"],
    "pricing_rules": ["chargeable_weight_divisor", "storage_free_days"],
}
BLOCK_DATES = {"term": ["initial_term_end", "non_renewal_notice_deadline"]}
SLASH_DATE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")
NUMBER = re.compile(r"(?<![\w.])(?:USD|INR)?\s*([-+]?\d+(?:,\d+)*(?:\.\d+)?)(?![\d.])", re.I)


def norm_text(s: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", s or "").split())


def squash(s: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s or ""))


def plain_number(s: str) -> str:
    return re.sub(r"[,\s]", "", unicodedata.normalize("NFKC", str(s)))


class PageIndex:
    """Text of the pages an extraction call was given, keyed by doc."""

    def __init__(self, docs: list[dict], order_hints: dict[str, str] | None = None):
        """order_hints: doc -> 'DMY'/'MDY' learned from other documents of the same sender, used only when a
        document's own dates cannot show the order."""
        self.pages = {d["doc"]: list(d["pages"]) for d in docs}
        self.scan = {d["doc"]: bool(d.get("is_scan")) for d in docs}
        hints = order_hints or {}
        self.date_order = {doc: self._date_order(pages) or hints.get(doc) for doc, pages in self.pages.items()}

    @staticmethod
    def _date_order(pages: list[str]) -> str | None:
        """'DMY' or 'MDY' from numeric dates whose first or second part exceeds 12; None if no such date."""
        dmy = mdy = False
        for a, b, _ in SLASH_DATE.findall("\n".join(pages)):
            dmy |= int(a) > 12
            mdy |= int(b) > 12
        return "DMY" if dmy and not mdy else "MDY" if mdy and not dmy else None

    def page_text(self, doc: str, page: int) -> str | None:
        pages = self.pages.get(doc)
        if pages is None or not isinstance(page, int) or not 1 <= page <= len(pages):
            return None
        return pages[page - 1]

    def quote_on_page(self, doc: str, page: int, quote: str) -> str | None:
        """None when the quote resolves; otherwise why it does not."""
        if doc not in self.pages:
            return f"cites {doc!r}, which was not in the input"
        text = self.page_text(doc, page)
        if text is None:
            return f"{doc} has no page {page}"
        if len(re.sub(r"\s", "", quote or "")) < MIN_QUOTE:
            return "quote shorter than 12 non-space characters"
        if self.scan[doc]:
            ok = squash(quote) in squash(text)
        else:
            ok = norm_text(quote) in norm_text(text)
        return None if ok else f"quote not found on {doc} page {page}"

    def has_value(self, doc: str, page: int, value: str) -> bool:
        """On the cited page, or elsewhere in the same document (a header's total can sit on its last page)."""
        want = plain_number(value)
        pages = self.pages.get(doc, [])
        try:
            number = Decimal(want.rstrip("%"))
        except InvalidOperation:
            return any(want in plain_number(t) for t in pages)  # month fields, e.g. 2041-03
        # Compare complete printed values. Removing all spaces first can join adjacent table cells,
        # and a substring check would accept 118 from 1,118 or 20 from the year 2041.
        return any(Decimal(token.replace(",", "")) == number
                   for text in pages for token in NUMBER.findall(unicodedata.normalize("NFKC", text)))

    def date_issue(self, doc: str, page: int, iso: str) -> str | None:
        """None when `iso` is written on the cited page, or elsewhere in the same document, in a form that cannot
        mean another date."""
        issue = self._date_issue(doc, page, iso)
        if issue is None or not self.pages.get(doc):
            return issue
        for other in range(1, len(self.pages[doc]) + 1):
            if other != page and self._date_issue(doc, other, iso) is None:
                return None
        return issue

    def _date_issue(self, doc: str, page: int, iso: str) -> str | None:
        try:
            d = date.fromisoformat(iso)
        except (TypeError, ValueError):
            return f"{iso!r} is not an ISO date"
        text = norm_text(self.page_text(doc, page) or "")
        mon, month = calendar.month_abbr[d.month], calendar.month_name[d.month]
        unambiguous = {d.isoformat(), f"{d.day} {mon} {d.year}", f"{d.day:02d} {mon} {d.year}",
                       f"{d.day} {month} {d.year}", f"{month} {d.day}, {d.year}", f"{mon} {d.day}, {d.year}",
                       f"{mon} {d.day:02d}, {d.year}", f"{d.day:02d}-{mon}-{d.year}", f"{d.day}-{mon}-{d.year}",
                       f"{d.day:02d}-{month}-{d.year}", f"{d.day}-{month}-{d.year}"}
        dmy = {f"{d.day:02d}/{d.month:02d}/{d.year}", f"{d.day}/{d.month}/{d.year}", f"{d.day:02d}.{d.month:02d}.{d.year}"}
        mdy = {f"{d.month:02d}/{d.day:02d}/{d.year}", f"{d.month}/{d.day}/{d.year}"}
        scan = self.scan.get(doc)

        def on_page(forms):
            if scan:
                return any(squash(f) in squash(text) for f in forms)
            # Not inside a longer number or date, but a sentence-ending '.' after the date is fine.
            return any(re.search(r"(?<!\d)(?<!\d[/.])" + re.escape(f) + r"(?!\d|[/.]\d)", text) for f in forms)

        if on_page(unambiguous):
            return None
        order = self.date_order.get(doc)
        if d.day == d.month and on_page(dmy):
            return None
        if order == "DMY" and on_page(dmy) or order == "MDY" and on_page(mdy):
            return None
        if order is None and on_page(dmy | mdy):
            return f"{iso} is written day/month or month/day and this document does not show which"
        return f"{iso} not on the cited page in this document's date format"


def _numeric_issue(index: PageIndex, src: dict, field: str, value) -> str | None:
    if value is None:
        return None
    try:
        Decimal(plain_number(value).rstrip("%"))
    except InvalidOperation:
        return f"{field} {value!r} is not a number"
    if not index.has_value(src["doc"], src["page"], value):
        return f"{field} {value!r} not on the cited page"
    return None


def check_item(index: PageIndex, kind: str, item: dict) -> tuple[str, list[str]]:
    src = item.get("source") or {}
    why = index.quote_on_page(src.get("doc"), src.get("page"), src.get("quote"))
    if why:
        return "rejected", [why]
    issues = []
    for f in NUMERIC_FIELDS.get(kind, []):
        if (msg := _numeric_issue(index, src, f, item.get(f))):
            issues.append(msg)
    for f in DATE_FIELDS.get(kind, []):
        v = item.get(f)
        if v is not None and (msg := index.date_issue(src["doc"], src["page"], v)):
            issues.append(f"{f}: {msg}")
    for f in MONTH_FIELDS.get(kind, []):
        v = item.get(f)
        if v is not None and not (re.fullmatch(r"\d{4}-\d{2}", v) and index.has_value(src["doc"], src["page"], v)):
            issues.append(f"{f} {v!r} not on the cited page")
    if kind == "contracts":
        for block in NESTED_BLOCKS:
            b = item.get(block) or {}
            bsrc = b.get("source")
            if bsrc and (why := index.quote_on_page(bsrc.get("doc"), bsrc.get("page"), bsrc.get("quote"))):
                issues.append(f"{block}: {why}")
            elif bsrc:
                for f in BLOCK_NUMERIC.get(block, []):
                    if (msg := _numeric_issue(index, bsrc, f"{block}.{f}", b.get(f))):
                        issues.append(msg)
                for f in BLOCK_DATES.get(block, []):
                    if b.get(f) is not None and (msg := index.date_issue(bsrc["doc"], bsrc["page"], b[f])):
                        issues.append(f"{block}.{f}: {msg}")
                for t in b.get("tiers") or []:
                    for f in ("min_qualifying_spend", "pct"):
                        if (msg := _numeric_issue(index, bsrc, f"{block}.tiers.{f}", t.get(f))):
                            issues.append(msg)
        for listed in ("rate_periods", "amendment_changes", "other_terms"):
            for sub in item.get(listed) or []:
                s = sub.get("source") or {}
                if (why := index.quote_on_page(s.get("doc"), s.get("page"), s.get("quote"))):
                    issues.append(f"{listed}: {why}")
    return ("unverified" if issues else "ok"), issues


def validate_facts(index: PageIndex, data: dict, fact_lists: list[str]) -> list[dict]:
    """-> one row per extracted item: {kind, doc, page, quote, data, status, issues}."""
    rows = []
    for kind in fact_lists:
        for item in data.get(kind) or []:
            if not isinstance(item, dict):
                continue
            status, issues = check_item(index, kind, item)
            src = item.get("source") or {}
            rows.append({"kind": kind, "doc": src.get("doc"), "page": src.get("page"), "quote": src.get("quote"),
                         "data": {k: v for k, v in item.items() if k != "source"} | {"_source": src},
                         "status": status, "issues": issues})
    return rows
