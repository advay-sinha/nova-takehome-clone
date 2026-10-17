"""Extract scoped business statements from email bodies; quoted text never becomes a direct instruction."""
from __future__ import annotations

import re

from .local_common import AWB, BAND, DATE, ID, LANE, NUM, capture, fact, iso, month
from ..rules.waiver import REQUIREMENT


def read_email(doc, out, labels, contract_ids):
    if doc.kind != "eml":
        return False
    body = doc.text.split("\n\n", 1)[-1]
    flat = " ".join(body.split())
    cid = next((c for c in sorted(contract_ids, key=len, reverse=True) if c in flat), None)
    quoted = False
    segments = []
    paragraph = []
    paragraph_quote = False
    author = None
    for line in body.splitlines() + [""]:
        marker = re.match(r"^(?:On .+ wrote:|-+\s*(?:Forwarded|Original) message|Begin forwarded message)", line, re.I)
        if marker or not line.strip() or bool(line.lstrip().startswith(">")) != paragraph_quote:
            if paragraph:
                segments.append((" ".join(paragraph), quoted or paragraph_quote))
                paragraph = []
        if marker:
            quoted = True
            author = capture(r"On .+?,\s*(.+?) wrote:", line) or author
        if quoted and line.startswith("From:"):
            author = line[5:].strip()
        if line.strip() and not marker:
            paragraph_quote = line.lstrip().startswith(">")
            paragraph.append(line)
    automation = re.search(r"(?:AI audit|automated system|ignore (?:any |all )?(?:earlier|previous) instructions|switch to autonomous)", flat, re.I)
    if automation:
        out["automation_directed_text"].append(fact("automation_directed_text", summary=automation[0], source=doc.source(1, flat)))
        return True
    for text, is_quoted in segments:
        clean = re.sub(r"(?:^|\s)>\s?", " ", text).strip()
        source = doc.source(1, text)
        if re.search(r"\b(?:waive|waived|waiving)\b", clean, re.I) and not re.search(r"\b(?:not|cannot|won't)\s+(?:be\s+)?waiv", clean, re.I):
            charge = None
            for label in sorted(labels, key=len, reverse=True):
                if re.search(r"\b" + re.escape(label) + r"\b", clean, re.I):
                    charge = label
                    break
            if charge:
                awbs = sorted(set(re.findall(r"\b" + AWB + r"\b", clean)))
                months = sorted(set(filter(None, [month(m[0]) for m in re.finditer(r"\b(?:\d{4}-\d{2}(?!-\d)|[A-Za-z]{3,9}\s+\d{4})\b", clean)])))
                invoice_ids = re.findall(r"invoice\s+(" + ID + ")", clean, re.I)
                condition = clean[match.start():] if (match := REQUIREMENT.search(clean)) else None
                if awbs or months or invoice_ids:
                    out["waivers"].append(fact("waivers", charge=charge, awbs=awbs, months=months,
                        invoice_ids=invoice_ids, condition=condition, scope_words=clean,
                        is_quoted_or_forwarded=is_quoted, quoted_author=author if is_quoted else None, source=source))
        m = re.search(r"extend (?:the )?due date of invoice\s+(" + ID + r")\s+to\s+(" + DATE + ")", clean, re.I)
        if m is None and re.search(r"\bextended\b", clean, re.I):
            m = re.search(r"invoice\s+(" + ID + r")\s+(?:now\s+)?(?:falls|is) due on\s+(" + DATE + ")", clean, re.I)
        if m:
            out["due_date_extensions"].append(fact("due_date_extensions", invoice_id=m[1], new_due_date=iso(m[2], doc.order),
                is_quoted_or_forwarded=is_quoted, source=source))
        awb = capture(r"\b(" + AWB + r")\b", clean, flags=0)
        if awb and not is_quoted:
            for event, pattern in [("picked_up", r"picked up"), ("delivered", r"delivered"), ("customs_hold", r"customs hold"),
                                   ("collected", r"collected by (?:the )?consignee"), ("released", r"released")]:
                m = re.search(pattern + r".*?\bon\s+(" + DATE + ")", clean, re.I)
                if m:
                    out["status_events"].append(fact("status_events", awb=awb, event=event, date=iso(m[1], doc.order),
                        station=capture(r"\bat\s+([A-Z]{2,5}\d?)\b", clean, flags=0), cause=clean,
                        carrier_fault=True if re.search(r"CARRIER_|carrier.s (?:error|documents)|filed by the carrier", clean, re.I) else
                                      False if re.search(r"SHIPPER_|shipper.s", clean, re.I) else None, source=source))
    # Rates are facts only; the resolver checks the sender's rates authority and the effective period.
    direct = " ".join(t for t, q in segments if not q)
    # A requirement may be in the next paragraph. Preserve it conservatively instead of losing the condition
    # at the paragraph boundary; the financial rules require proof before acting on a conditional waiver.
    if (requirement := REQUIREMENT.search(direct)):
        for waiver in out["waivers"]:
            if waiver["source"]["doc"] == doc.doc and not waiver["is_quoted_or_forwarded"] and not waiver["condition"]:
                waiver["condition"] = direct[requirement.start():]
    start = iso(capture(r"(?:effective|from)\s+(" + DATE + ")", direct), doc.order)
    end = iso(capture(r"(?:effective|from)\s+" + DATE + r"\s+(?:to|until|through)\s+(" + DATE + ")", direct), doc.order)
    for m in re.finditer(r"(" + LANE + r")\s+(" + BAND + r")\s*[:=]\s*(?:(USD|INR)\s*)?(" + NUM + r")\s*(USD|INR)?", direct):
        out["rate_notices"].append(fact("rate_notices", contract_id=cid, lane=m[1], band=m[2], rate=m[4],
            currency=m[3] or m[5], effective_from=start, effective_to=end, source=doc.source(1, m[0])))
    if not out["rate_notices"] or not any(f["source"]["doc"] == doc.doc for f in out["rate_notices"]):
        m = re.search(r"(" + LANE + r").*?\b(" + BAND + r").*?\b(USD|INR)\s+(" + NUM + r")\s+per kg", direct)
        if m and start:
            out["rate_notices"].append(fact("rate_notices", contract_id=cid, lane=m[1], band=m[2], rate=m[4],
                currency=m[3], effective_from=start, effective_to=end, source=doc.source(1, m[0])))
    invoice_ids = sorted(set(re.findall(r"(?:invoice|bill)\s+(" + ID + ")", direct, re.I)))
    if not invoice_ids:
        invoice_ids = re.findall(r"Subject:.*?\b(" + ID + ")", doc.text)
    kind = ("for_records" if re.search(r"for your records|do not pay|no payment (?:is )?required", direct, re.I) else
            "asks_payment" if re.search(r"(?:arrange|process|request|make) (?:the )?payment|unpaid|outstanding|please pay", direct, re.I) else
            "reminder" if "reminder" in direct.lower() else "copy")
    for invoice_id in invoice_ids:
        out["payment_requests"].append(fact("payment_requests", invoice_id=invoice_id, kind=kind,
            source=doc.source(1, direct if direct else body)))
    return True
