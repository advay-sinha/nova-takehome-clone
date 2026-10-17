"""Deterministic stand-in for the model on the synthetic fixtures (tests only).

`respond(user, schema)` answers like a careful extractor would on fixtures.py documents: it lists every document,
transcribes invoice lines it can see with verbatim quotes, and maps tracking tables by header label. Run as a script it
mimics `claude -p --output-format json` (the harness's CLI back end), so CLI-level tests make no real model call.
"""
from __future__ import annotations

import json
import re
import sys

LINE = re.compile(r"^(\d+) (\S+) (\d{4}-\d{2}-\d{2}) (.+?) (\S+-\S+) (\d+) kg ([\d.]+) ([\d.]+)$")


def _documents(user: str) -> list[tuple[str, list[str]]]:
    docs, cur = [], None
    for line in user.split("\n"):
        if m := re.match(r"=== DOCUMENT (\S+) ", line):
            cur = (m[1], [])
            docs.append(cur)
        elif line.startswith("--- page ") and cur is not None:
            cur[1].append("")
        elif line.startswith("=== END") or cur is None or not cur[1]:
            continue
        else:
            cur[1][-1] += ("\n" if cur[1][-1] else "") + line
    return docs


def facts(user: str, schema: dict) -> dict:
    out = {k: [] for k in schema["properties"]}
    for doc, pages in _documents(user):
        if "documents" in out:            # the recheck schema has no documents list
            out["documents"].append({"doc": doc, "kind": "invoice" if "Invoice" in pages[0] else "other",
                                     "summary": pages[0].split("\n")[0][:60]})
        for p, text in enumerate(pages, 1):
            for line in text.split("\n"):
                if m := LINE.match(line.strip()):
                    out["invoice_lines"].append({
                        "invoice_id": "PW-OB-2041-0107", "line_no": m[1], "awb": m[2], "house_awb": None,
                        "pickup_date": m[3], "charge_label": m[4], "lane": m[5], "quantity": m[6], "unit": "kg",
                        "rate": m[7], "pct": None, "base_amount": None, "amount": m[8], "period_ref": None,
                        "refers_to_invoice": None, "source": {"doc": doc, "page": p, "quote": line.strip()}})
    return out


def table_map(user: str) -> dict:
    tables = []
    for n, line in re.findall(r"^(\d+): (.*)$", user, re.M):
        if line.startswith("AWB | Event | Date"):
            tables.append({"page": 1, "kind": "tracking_events", "header_line": int(n),
                           "columns": [{"field": "awb", "header": "AWB"}, {"field": "event", "header": "Event"},
                                       {"field": "date", "header": "Date"}, {"field": "station", "header": "Station"}],
                           "date_format": "YYYY-MM-DD", "notes": None})
    return {"tables": tables}


def respond(user: str, schema: dict) -> dict:
    return table_map(user) if "tables" in schema["properties"] else facts(user, schema)


if __name__ == "__main__":
    args = sys.argv[1:]
    schema = json.loads(args[args.index("--json-schema") + 1])
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "",
                      "structured_output": respond(sys.stdin.read(), schema),
                      "usage": {"input_tokens": 1, "output_tokens": 1}}))
