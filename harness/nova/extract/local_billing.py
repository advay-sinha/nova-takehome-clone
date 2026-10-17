"""Read labelled billing rows and spreadsheet headers without a model or fixed column positions."""
from __future__ import annotations

import re

from .local_common import AWB, DATE, ID, LANE, NUM, capture, fact, iso, month
from .tables import _sheet_rows, parse_table
from ..world import norm_label


def table_rows(doc, blob):
    if doc.kind != "xlsx":
        return None
    rows = []
    for p in range(1, len(doc.pages) + 1):
        grid = _sheet_rows(blob, p)
        for line_no, cells in enumerate(grid[:12], 1):
            fields = {}
            for cell in cells:
                n = norm_label(cell)
                field = next((field for field, names in {
                    "awb": {"awb", "waybill", "shipment", "shipmentid", "airwaybill"},
                    "event": {"event", "milestone", "eventtype"},
                    "date": {"date", "eventdate", "eventtime", "timestamp", "occurredat"},
                    "station": {"station", "location", "hub"},
                    "reason": {"reason", "reasoncode", "remarks"},
                    "invoice_id": {"invoice", "invoiceno", "invoicenumber", "invoiceid", "documentnumber"},
                    "invoice_date": {"invoicedate", "issuedon", "issuedate"},
                    "due_date": {"due", "duedate", "paymentdue", "settleby"},
                    "amount": {"amount", "total", "invoiceamount", "balance"},
                    "currency": {"currency", "ccy"}, "status": {"status", "state", "paymentstatus"},
                    "paid_date": {"paiddate", "paidon", "settledon", "settlementdate"},
                    "scheduled_date": {"scheduleddate", "scheduledon", "scheduledpayment"},
                }.items() if n in names), None)
                if field:
                    fields[field] = cell
            if {"awb", "event", "date"} <= fields.keys():
                kind = "tracking_events"
            elif {"invoice_id", "amount", "status"} <= fields.keys():
                kind = "payment_ledger"
            else:
                continue
            fmt = {"DMY": "DD/MM/YYYY", "MDY": "MM/DD/YYYY"}.get(doc.order, "other")
            rows += parse_table(doc.doc, blob, {"page": p, "kind": kind, "header_line": line_no,
                "columns": [{"field": k, "header": v} for k, v in fields.items()], "date_format": fmt})
            break
    return rows or None


def read_invoice(doc, out, labels):
    inv = next((value for _, line in doc.lines() if (value := capture(
        r"(?:invoice(?:\s*(?:number|no\.?))?|freight\s*bill\s*no\.?|charges\s*advice|statement\s*of\s*account)\s*[:#]?\s*(" + ID + r")", line))), None)
    if not inv or re.search(r"credit note", doc.flat, re.I):
        return False
    cid = capture(r"(?:contract\s*(?:reference)?|service\s+agreement|agreement)\s*[:#]?\s*(" + ID + r")", doc.flat)
    currency = capture(r"(?:currency|amount|total|balance due|net|charges)\s*(?:(?:due|payable)\s*)?\(?\s*(USD|INR)\b", doc.flat)
    _, source = doc.find(re.escape(inv))
    header = fact("invoices", invoice_id=inv, doc_type="statement" if "STATEMENT OF ACCOUNT" in doc.flat.upper() else "invoice",
        contract_id=cid, currency=currency, invoice_date=doc.date(r"(?:invoice\s*date|statement\s*date|document\s*date|issued on)"),
        due_date=doc.date(r"(?:due\s*date|payment\s*due|payable\s*by|settle\s*by)"), source=source)
    for field, pattern in [("total", r"(?:total\s*(?:due|payable)?|balance due)\s*(?:USD|INR)?\s*[|:]?\s*(" + NUM + r")\s*$"),
                           ("subtotal", r"(?:subtotal|net charges|charges)\s*(?:USD|INR)?\s*[|:]?\s*(" + NUM + r")\s*$")]:
        for _, line in doc.lines():
            if (m := re.match(pattern, line, re.I)):
                header[field] = m[1].replace(",", "")
    for _, line in doc.lines():
        if re.match(r"(?:GST|sales\s*tax|tax)\b", line, re.I) and (m := re.search(r"(?:USD|INR)\s*(" + NUM + r")\s*$", line)):
            header["tax"] = m[1].replace(",", "")
    out["invoices"].append(header)
    first_amount = bool(re.search(r"Net\s*\(?[A-Z]{3}\)?\s+Units\s+Unit price", doc.flat, re.I))
    for p, line in doc.lines():
        if " | " in line and doc.kind == "xlsx":
            cells = line.split(" | ")
            if len(cells) == 5 and re.fullmatch(NUM, cells[-1]):
                qty = capture(r"^(" + NUM + ")", cells[2])
                out["invoice_lines"].append(fact("invoice_lines", invoice_id=inv, charge_label=cells[0],
                    period_ref=cells[1], quantity=qty, unit=capture(NUM + r"\s*(.+)", cells[2]),
                    rate=cells[3].replace(",", ""), amount=cells[4].replace(",", ""), source=doc.source(p, line)))
            continue
        parsed = billing_line(line, labels, first_amount, doc.order)
        if parsed:
            out["invoice_lines"].append(fact("invoice_lines", invoice_id=inv, **parsed, source=doc.source(p, line)))
    return True


def billing_line(line, labels, first_amount=False, order=None):
    if re.match(r"(?:subtotal|total|tax|GST|sales tax|balance due|net charges|payment|settlement|page|terms|please remit|remit)\b", line, re.I):
        return None
    awb = capture(r"\b(" + AWB + r")\b", line, flags=0)
    if awb is None and not re.search(r"late\s*(?:fee|payment)|overdue interest", line, re.I):
        return None
    label_match = None
    for label in sorted(set(labels), key=lambda s: -len(norm_label(s))):
        # OCR may remove spaces beside digits, but a code inside a word (e.g. FSC in IFSC) is not a charge.
        pattern = r"(?<![A-Za-z])" + r"\s*".join(re.escape(w) for w in label.split()) + r"(?![A-Za-z])"
        if (m := re.search(pattern, line, re.I)):
            label_match = m
            break
    if label_match is None:
        return None
    label = label_match[0]
    # Remove identifiers, dates and the description before reading numeric cells from the right.
    rest = line[:label_match.start()] + " " + line[label_match.end():]
    rest = re.sub(DATE, " ", rest)
    lane = capture(r"\b(" + LANE + r")\b", rest, flags=0)
    for pattern in [AWB, LANE, ID]:
        rest = re.sub(r"\b" + pattern + r"\b", " ", rest)
    line_no = capture(r"^(\d+)\s+", line)
    if line_no:
        rest = re.sub(r"^\d+\s+", "", rest)
    tokens = list(re.finditer(NUM + r"%?", rest))
    if len(tokens) < 2:
        return None
    amount_i, rate_i, qty_i = (-3, -1, -2) if first_amount else (-1, -2, -3)
    if len(tokens) < 3 and first_amount:
        return None
    amount, rate = tokens[amount_i][0], tokens[rate_i][0]
    if "%" in amount:
        return None
    qty_match = tokens[qty_i] if len(tokens) >= 3 else None
    qty = qty_match[0] if qty_match else None
    pct = rate.rstrip("%") if rate.endswith("%") else None
    unit = None
    if qty_match:
        unit = capture(r"^\s*(kg|shpt|shipment|consignment|days?|months?|fee|pieces?)\b", rest[qty_match.end():])
    base = qty if pct and qty and not unit else None
    if pct:
        # A percentage's base can be written in the description before the numeric cells.
        base = capture(r"%\s*of\s*(" + NUM + ")", line) or base
        if base is None and re.search(r"late\s*fee", label, re.I):
            base = capture(r"(?:USD|INR)\s*(" + NUM + r")\s*overdue", line)
    return {"line_no": line_no, "awb": awb, "lane": lane,
        "pickup_date": iso(capture("(" + DATE + ")", line), order), "charge_label": label,
        "quantity": qty.replace(",", "") if qty and unit else None, "unit": unit,
        "rate": rate.replace(",", "") if not pct else None, "pct": pct,
        "base_amount": base.replace(",", "") if base else None, "amount": amount.replace(",", ""),
        "refers_to_invoice": capture(r"(?:late fee|overdue interest)\s+on\s+(" + ID + ")", line)}


def read_transport(doc, out):
    awb = capture(r"(?:AIR\s+WAYBILL|declaration for AWB)\s+(" + AWB + ")", doc.flat)
    if not awb:
        return False
    _, source = doc.find(re.escape(awb))
    if "DECLARATION" in doc.flat.upper():
        nums = sorted(set(re.findall(r"UN\s*\d{4}", doc.flat)))
        out["dg_declarations"].append(fact("dg_declarations", awb=awb, un_numbers=[n.replace(" ", "") for n in nums],
            description=capture(r"Goods:\s*(.+?)(?=\s+UN|$)", doc.flat),
            refrigerant_only=bool(re.search(r"refrigerant", doc.flat, re.I)) and set(n.replace(" ", "") for n in nums) <= {"UN1845"},
            source=source))
        return "dg_declaration"
    out["air_waybills"].append(fact("air_waybills", awb=awb,
        master_awb=capture(r"Master AWB\s+(" + AWB + ")", doc.flat),
        is_house=bool(re.search(r"this document covers house", doc.flat, re.I)), executed_date=doc.date(r"Executed on"),
        origin=capture(r"Origin\s+(\w+)", doc.flat), destination=capture(r"Destination\s+(\w+)", doc.flat),
        pieces=capture(r"(?:Total pieces|Pieces)\s+(" + NUM + ")", doc.flat),
        actual_weight_kg=capture(r"Actual weight\s+(" + NUM + r")\s*kg", doc.flat),
        chargeable_weight_kg=capture(r"(?<!Total )Chargeable weight\s+(" + NUM + r")\s*kg", doc.flat),
        total_chargeable_weight_kg=capture(r"Total chargeable weight\s+(" + NUM + r")\s*kg", doc.flat),
        dimensions=capture(r"Dimensions\s+(.+?)(?=\s+Chargeable|\s+Nature|$)", doc.flat),
        goods=capture(r"Nature of goods:\s*(.+?)(?=\s+Handling|$)", doc.flat), source=source))
    return "air_waybill"


def read_credit(doc, out):
    credit = capture(r"CREDIT NOTE\s*(?:No\.?\s*)?(" + ID + ")", doc.flat)
    if not credit:
        return False
    amount = capture(r"(?:Total|Amount|Credit)\s+(?:USD|INR)\s+(" + NUM + ")", doc.flat)
    if amount is None:
        return False
    _, src = doc.find(re.escape(credit))
    kind = next((k for k in ("rebate", "improvement", "margin") if re.search(r"\b" + k + r"\b", doc.flat, re.I)), "invoice_correction")
    out["credit_notes"].append(fact("credit_notes", credit_id=credit, credit_date=doc.date(r"(?:Credit date|Date)"),
        contract_id=capture(r"(?:Contract reference|Agreement)\s+(" + ID + ")", doc.flat), credit_type=kind,
        period=capture(r"\b(\d{4}-Q[1-4]|CY\d+)\b", doc.flat), refers_to_invoice=capture(r"invoice\s+(" + ID + ")", doc.flat),
        refers_to_awb=capture(r"AWB\s+(" + AWB + ")", doc.flat), amount=amount.replace(",", ""),
        currency=capture(r"\b(USD|INR)\b", doc.flat), source=src))
    return True
