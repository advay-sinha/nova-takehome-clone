"""Source-preserving primitives for the credential-free document reader."""
from __future__ import annotations

import calendar
import re
from datetime import date

from .schema import DEFS, FACTS_SCHEMA
from .tables import parse_date
from .validate import PageIndex, norm_text

NUM = r"\d[\d,]*(?:\.\d+)?"
ID = r"[A-Z0-9]+(?:[-/][A-Z0-9]+)+"
AWB = r"(?:[A-Z]{2,6}\d{5,}(?:-[A-Z]\d+)?|\d{3}-\d{8})"
LANE = r"(?<![A-Z0-9-])[A-Z]{2,5}\d?-[A-Z]{2,5}\d?(?![A-Z0-9-])"
MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE = (r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.]\d{1,2}[/.]\d{4}|"
        r"\d{1,2}[ -]" + MONTH + r"[ -]\d{4}|" + MONTH + r"\s+\d{1,2},\s+\d{4})(?!\d)")
BAND = r"(?:minimum charge|\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*kg|\d+(?:\.\d+)?\s*\+\s*kg|\d+(?:\.\d+)?\s*kg\s+and\s+over)"


def blank(schema):
    if "$ref" in schema:
        return blank(DEFS[schema["$ref"].rsplit("/", 1)[1]])
    if "anyOf" in schema:
        return None
    if schema.get("type") == "object":
        return {k: blank(v) for k, v in schema["properties"].items()}
    if schema.get("type") == "array":
        return []
    if schema.get("type") == "boolean":
        return False
    if schema.get("type") == "integer":
        return 1
    return ""


def fact(collection, **values):
    return blank(FACTS_SCHEMA["properties"][collection]["items"]) | values


def capture(pattern, text, group=1, flags=re.I):
    m = re.search(pattern, text, flags)
    return m[group] if m else None


def number(pattern, text):
    value = capture(pattern, text)
    return value.replace(",", "") if value is not None else None


def iso(text, order=None):
    if not text:
        return None
    text = norm_text(text)
    m = re.search(DATE, text, re.I)
    if not m:
        return None
    token = m[0]
    if re.fullmatch(r"\d{1,2}-[A-Za-z]+-\d{4}", token):
        token = token.replace("-", " ")
    if (m := re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", token)):
        token = f"{m[2]} {m[1]} {m[3]}"
    return parse_date(token, {"DMY": "DD/MM/YYYY", "MDY": "MM/DD/YYYY"}.get(order, "other"))


def month(text):
    if (m := re.search(r"\b(\d{4})-(\d{2})(?!-\d)", text)):
        return f"{m[1]}-{m[2]}"
    if (m := re.search(r"\b([A-Za-z]{3,9})\s+(\d{4})\b", text)):
        names = {n.lower()[:3]: i for i, n in enumerate(calendar.month_name) if n}
        if m[1].lower()[:3] in names:
            return f"{m[2]}-{names[m[1].lower()[:3]]:02d}"
    return None


def band_bounds(label):
    if "minimum" in label.lower():
        return None, None, True
    values = re.findall(r"\d+(?:\.\d+)?", label)
    return (values[0] if values else None, values[1] if len(values) > 1 else None, False)


class Document:
    def __init__(self, payload, order=None):
        self.doc = payload["doc"]
        self.kind = payload["kind"]
        self.scan = payload.get("is_scan", False)
        self.pages = payload["pages"]
        self.text = "\n".join(self.pages)
        self.flat = norm_text(self.text)
        self.order = PageIndex._date_order(self.pages) or order

    def lines(self):
        for p, text in enumerate(self.pages, 1):
            for line in text.splitlines():
                if line.strip():
                    yield p, line.strip()

    def source(self, page, quote):
        quote = norm_text(quote)
        text = norm_text(self.pages[page - 1])
        if len(re.sub(r"\s", "", quote)) < 12:
            i = text.find(quote)
            quote = text[max(0, i - 30):i + len(quote) + 60]
        return {"doc": self.doc, "page": page, "quote": quote}

    def find(self, pattern, flags=re.I):
        for p, page in enumerate(self.pages, 1):
            if (m := re.search(pattern, norm_text(page), flags)):
                return m, self.source(p, m[0])
        return None, None

    def clauses(self):
        result = []
        for p, page in enumerate(self.pages, 1):
            current = []
            for line in page.splitlines():
                start = re.match(r"^\d{1,2}\.\d{1,2}\s", line)
                stop = start or re.match(r"^(?:\d{1,2} [A-Z]|Initials:|Confidential|Annex |Appendix |Schedule )", line)
                if stop and current:
                    result.append((norm_text(" ".join(current)), self.source(p, " ".join(current))))
                    current = []
                if start or (current and not stop):
                    current.append(line)
            if current:
                result.append((norm_text(" ".join(current)), self.source(p, " ".join(current))))
        return result

    def clause(self, pattern):
        found = [(t, s) for t, s in self.clauses() if re.search(pattern, t, re.I)]
        return (" ".join(t for t, _ in found), found[0][1]) if found else ("", None)

    def date(self, pattern):
        return iso(capture(pattern + r"\s*[:|]?\s*(" + DATE + ")", self.flat), self.order)
