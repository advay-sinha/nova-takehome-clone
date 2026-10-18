"""Deterministic row parsing for spreadsheets whose columns the model has named.

The model only says which header labels a field; this module reads every data row of the workbook itself, by true
column position (the text layer drops empty cells, so positions there are unreliable). Each row's quote is the row as
the grader's text layer prints it, so citations resolve exactly.
"""
from __future__ import annotations

import io
import re
from datetime import date, datetime

from . import validate
from .. import textlayer

DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DATE_SLASH = re.compile(r"\b(\d{1,2})([/.-])(\d{1,2})\2(\d{4})\b")
DATE_WORDS = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})\b")
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
CURRENCY = re.compile(r"\b([A-Z]{3})\b")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                      "dec"], 1)}
KIND_TO_FACT = {"tracking_events": "tracking_events", "payment_ledger": "ledger_rows"}


def parse_date(value, fmt: str) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value or "")
    try:
        if (m := DATE_ISO.search(s)):
            return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
        if (m := DATE_SLASH.search(s)):
            a, b, y = int(m[1]), int(m[3]), int(m[4])
            if fmt == "MM/DD/YYYY":
                a, b = b, a
            elif fmt != "DD/MM/YYYY":
                return None          # day/month order unknown: never guess
            return date(y, b, a).isoformat()
        if (m := DATE_WORDS.search(s)) and m[2].lower() in MONTHS:
            return date(int(m[3]), MONTHS[m[2].lower()], int(m[1])).isoformat()
    except ValueError:
        return None
    return None


def parse_amount(text: str) -> tuple[str | None, str | None]:
    """'USD 1,243.96' -> ('1243.96', 'USD')."""
    m = NUMBER.search(text or "")
    c = CURRENCY.search(text or "")
    return (m[0].replace(",", "") if m else None), (c[1] if c else None)


def _sheet_rows(xlsx: bytes, page: int) -> list[list[str]]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx), data_only=True)
    ws = wb.worksheets[page - 1]
    return [[textlayer._cell_text(c) for c in row] for row in ws.iter_rows()]


def parse_table(doc: str, xlsx: bytes, table: dict) -> list[dict]:
    """Rows of one mapped table -> fact rows {kind, doc, page, quote, data, status, issues, origin}."""
    kind = KIND_TO_FACT.get(table.get("kind"))
    if kind is None:
        return []
    page = int(table.get("page") or 1)
    grid = _sheet_rows(xlsx, page)
    lines = [(i, textlayer.SEP.join(t for t in row if t != "")) for i, row in enumerate(grid)]
    lines = [(i, text) for i, text in lines if text]
    want = {c["field"]: validate.norm_text(c["header"]).lower() for c in table.get("columns") or []}
    header_idx = None
    for i, row in enumerate(grid):     # the header row is the one whose cells contain every mapped label
        cells = [validate.norm_text(t).lower() for t in row]
        if want and all(label in cells for label in want.values()):
            header_idx = i
            break
    if header_idx is None:
        return [{"kind": kind, "doc": doc, "page": page, "quote": None, "data": {"_table": table},
                 "status": "rejected", "issues": ["mapped header labels not found in the sheet"], "origin": "table"}]
    header = [validate.norm_text(t).lower() for t in grid[header_idx]]
    col = {field: header.index(label) for field, label in want.items()}
    fmt = table.get("date_format") or "other"
    out = []
    for i, text in lines:
        if i <= header_idx:
            continue
        row = grid[i]
        cell = {f: (row[c] if c < len(row) else "") for f, c in col.items()}
        data, issues = {}, []
        for f, v in cell.items():
            if f in ("date", "invoice_date", "due_date", "paid_date", "scheduled_date"):
                iso = parse_date(v, fmt) if v not in ("", "-") else None
                if v not in ("", "-") and iso is None:
                    issues.append(f"{f} {v!r} is not a date in format {fmt}")
                data[f] = iso
                data[f + "_raw"] = v or None
            elif f == "amount":
                data["amount"], cur = parse_amount(v)
                data.setdefault("currency", cur)
            else:
                data[f] = None if v in ("", "-") else v
        data["_source"] = {"doc": doc, "page": page, "quote": text}
        data["_row"] = i + 1
        out.append({"kind": kind, "doc": doc, "page": page, "quote": text, "data": data,
                    "status": "unverified" if issues else "ok", "issues": issues, "origin": "table"})
    return out
