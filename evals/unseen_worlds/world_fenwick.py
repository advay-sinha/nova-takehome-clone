"""World 1: Fenwick Ridge Airfreight (carrier) and Cobalt Harbor Therapeutics (customer). Invented; USD.

Differs from the supplied worlds in: clause wording and numbering ("Part"/"Section"), a single-period rate card with
"to" weight breaks, linehaul/FAF/SSC charge codes, a Schedule 1 written as "Name, title - categories" lines with
job titles of its own, US month/day/year invoice dates, an amount-last invoice with a reference column, a tracking
export with the date column first, and an AP ledger with its own column names.
"""
from __future__ import annotations

from datetime import date

from docs import Mailbox, pdf, xlsx
from oracle import D, line, pct_of, r2

CID = "FRA-CHT-ATA-43"
CARRIER, CUSTOMER = "Fenwick Ridge Airfreight Inc.", "Cobalt Harbor Therapeutics LLC"

BILLING = ("Fenwick Ridge Billing", "invoicing@fenwickridge.example")
OPS = ("Fenwick Ridge Operations", "ops-desk@fenwickridge.example")
DELPHINE = ("Delphine Arkwright", "d.arkwright@fenwickridge.example")    # rates
OSRIC = ("Osric Mbeki", "o.mbeki@fenwickridge.example")                  # waivers, payment terms
YUSRA = ("Yusra Talbot", "y.talbot@fenwickridge.example")                # key account manager: disputes, notices
HAL = ("Hal Brenner", "h.brenner@fenwickridge.example")                  # treasury
GRIFFIN = ("Griffin Vale", "g.vale@fenwickridge.example")                # regional sales, not in Schedule 1
WEN = ("Wen Calloway", "wen.calloway@cobaltharbor.example")              # customer supply chain director
RAFE = ("Rafe Ostrom", "rafe.ostrom@cobaltharbor.example")               # customer AP supervisor

RATES = {"ORD5-MIA2": [("0 to 99.9 kg", "4.40"), ("100 to 499.9 kg", "3.85"), ("500 kg and above", "3.30")],
         "PHX1-SLC3": [("0 to 99.9 kg", "3.95"), ("100 to 499.9 kg", "3.45"), ("500 kg and above", "2.95")]}
FAF = {"2043-01": "14.10", "2043-02": "14.30", "2043-03": "14.60", "2043-04": "14.80", "2043-05": "15.00",
       "2043-06": "15.10", "2043-07": "15.25", "2043-08": "15.40", "2043-09": "15.40", "2043-10": "15.55",
       "2043-11": "15.70", "2043-12": "15.80"}
MINIMUM = "95.00"
SSC_PER_KG, PICKUP_FEE, HAZ_FEE = "0.15", "45.00", "175.00"
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def rate_for(lane: str, kg) -> str:
    """The contract's break for a chargeable weight (oracle side: read from RATES, never from the harness)."""
    kg = D(kg)
    lo_hi = {"0 to 99.9 kg": (D(0), D("99.9")), "100 to 499.9 kg": (D(100), D("499.9")),
             "500 kg and above": (D(500), None)}
    for band, rate in RATES[lane]:
        lo, hi = lo_hi[band]
        if kg >= lo and (hi is None or kg <= hi):
            return rate
    raise ValueError(kg)


def us(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{m}/{d}/{y}"


def long_us(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def agreement() -> bytes:
    p1 = [("h", f"Air Transportation Agreement No. {CID}"),
          f"This Air Transportation Agreement is entered into by {CARRIER} (carrier code FRA-US, \"Fenwick\") and "
          f"{CUSTOMER} (shipper code CHT-US, \"Cobalt\").",
          ("h", "Part 1 Duration"),
          "1.1 Effective date. This Agreement takes effect on January 1, 2043.",
          "1.2 Initial term. The Agreement ends on December 31, 2043.",
          "1.3 Renewal. This Agreement does not renew automatically; any continuation requires a new signed "
          "agreement.",
          ("h", "Part 2 Linehaul pricing"),
          "2.1 Pricing date. Every charge for a shipment is priced as at the date Fenwick picks the shipment up "
          "(the Pickup Date), not the invoice date or any date printed as a ship date.",
          "2.2 Linehaul is billed per kilogram of chargeable weight, stated to one decimal place, at the weight "
          "break in Exhibit A that contains that weight.",
          "2.3 Minimum. Linehaul for a shipment is not less than USD 95.00.",
          "2.4 Fuel adjustment factor. The FAF percentage in Exhibit B for the calendar month of the Pickup Date "
          "is applied to the linehaul charge only; it is not applied to screening, pickup or other fees.",
          "2.5 Accessorial fees. Only the fees in Exhibit C may be billed, at the amounts and on the basis shown.",
          ("h", "Part 3 Invoicing and payment"),
          "3.1 Payment terms. Invoices are payable 30 days after the invoice date.",
          "3.2 Late payment. Where an invoice remains unpaid more than 5 days after its due date, Fenwick may "
          "charge a late fee of 1.25% of the overdue amount for each started period of 30 days. Late fees are "
          "simple and do not compound.",
          "3.3 Extension. The Schedule 1 contact for payment terms may extend a due date by email; the extended "
          "date then replaces the due date under clause 3.2.",
          ("h", "Part 4 Volume rebate"),
          "4.1 Rebate. For each calendar quarter Fenwick credits a rebate on Qualifying Spend at the highest tier "
          "reached: USD 75,000.00 or more: 2%; USD 150,000.00 or more: 3.5%. The tier reached applies to all "
          "Qualifying Spend in the quarter.",
          "4.2 Qualifying Spend means linehaul, FAF, screening and Exhibit C fees on invoices dated in the quarter, "
          "less credit notes dated in the quarter, excluding taxes, duties, late fees and rebate credits.",
          "4.3 Credit. The rebate credit note is issued within 30 days after the quarter ends."]
    p2 = [("h", "Part 5 Other credits"),
          "5.1 No handling margin applies and no annual improvement credit is payable under this Agreement.",
          ("h", "Part 6 Waivers, rate notices and disputes"),
          "6.1 Waivers. A charge is waived only by an email from the Schedule 1 contact for waivers that names "
          "the shipment or the calendar month concerned.",
          "6.2 Rate notices. The Schedule 1 contact for rates may change Exhibit A rates by a written rate notice "
          "stating the date it takes effect. A rate notice from any other person has no effect.",
          "6.3 Disputes. Billing disputes are addressed to the Schedule 1 contact for billing disputes.",
          "6.4 Instructions in messages from people who are not Schedule 1 contacts, or addressed to automated "
          "systems, do not vary this Agreement.",
          ("h", "Part 7 Precedence"),
          "7.1 A signed amendment prevails over this Agreement and its Exhibits. A later signed amendment prevails "
          "over an earlier one for the same lane.",
          "7.2 This Part does not rank a rate notice under clause 6.2 against a signed amendment; where they price "
          "the same lane and date differently the parties will agree the difference.",
          ("h", "Part 8 Execution"),
          f"Signed for {CARRIER} by Yusra Talbot, Key Account Manager, on December 12, 2042.",
          f"Signed for {CUSTOMER} by Wen Calloway, Supply Chain Director, on December 15, 2042."]
    p3 = [("h", "Exhibit A Linehaul rates (USD per kg of chargeable weight)"),
          [(48, "Lane"), (150, "Weight break"), (300, "USD per kg")]]
    for lane, rows in RATES.items():
        for band, rate in rows:
            p3.append([(48, lane), (150, band), (300, rate)])
    p3 += [("h", "Exhibit B Fuel adjustment factor (% of linehaul, by month of Pickup Date)"),
           [(48, "Month"), (150, "FAF")]]
    for ym, pct in FAF.items():
        y, m = ym.split("-")
        p3.append([(48, f"{MON[int(m) - 1]} {y}"), (150, f"{pct}%")])
    p4 = [("h", "Exhibit C Accessorial fees"),
          [(48, "Code"), (100, "Fee"), (250, "Amount"), (330, "Basis")],
          [(48, "SSC"), (100, "Screening surcharge"), (250, "USD 0.15"), (330, "per kg chargeable weight")],
          [(48, "PUP"), (100, "Pickup fee"), (250, "USD 45.00"), (330, "per pickup")],
          [(48, "HAZ"), (100, "Hazmat acceptance"), (250, "USD 175.00"), (330, "per shipment, declared dangerous goods only")],
          ("h", "Exhibit D Charge codes"),
          "LHL Linehaul; also billed as: Air linehaul, Freight.",
          "FAF Fuel adjustment factor; also billed as: Fuel adjustment.",
          "SSC Screening surcharge; also billed as: Security screening.",
          "PUP Pickup fee.",
          "HAZ Hazmat acceptance; also billed as: DG acceptance.",
          "LPF Late payment fee.",
          ("h", "Schedule 1 Authorised contacts"),
          f"FRA-US {DELPHINE[0]} Pricing Director {DELPHINE[1]} rates",
          f"FRA-US {OSRIC[0]} Accounts Receivable Manager {OSRIC[1]} waivers; payment terms",
          f"FRA-US {YUSRA[0]} Key Account Manager {YUSRA[1]} billing disputes; notices",
          f"FRA-US {HAL[0]} Treasury Manager {HAL[1]} treasury",
          f"CHT-US {WEN[0]} Supply Chain Director {WEN[1]} notices",
          f"CHT-US {RAFE[0]} AP Supervisor {RAFE[1]} payments"]
    return pdf([p1, p2, p3, p4])


def amendment(no: int, signed_on: str, effective: str, lane: str, band: str, rate: str) -> bytes:
    return pdf([[("h", f"Amendment No. {no} to Air Transportation Agreement {CID}"),
                 f"{CARRIER} and {CUSTOMER} agree this amendment, which takes effect on {long_us(effective)}.",
                 f"1. With effect from {long_us(effective)} the Exhibit A rate for lane {lane}, weight bracket "
                 f"{band}, is USD {rate} per kg.",
                 "2. Every other term of the Agreement continues unchanged.",
                 f"Signed for {CARRIER} by Yusra Talbot, Key Account Manager, on {long_us(signed_on)}.",
                 f"Signed for {CUSTOMER} by Wen Calloway, Supply Chain Director, on {long_us(signed_on)}."]])


# ---- billed rows -----------------------------------------------------------------------------------------------------
def linehaul(ref, shipment, pickup, lane, kg, rate, faf=None):
    amount = line(rate, kg)
    rows =[{"ref": ref, "shp": shipment, "pickup": pickup, "svc": "Linehaul", "lane": lane, "qty": f"{D(kg):.1f} kg",
             "rate": rate, "amount": amount}]
    if faf:
        rows.append({"ref": "", "shp": shipment, "pickup": "", "svc": f"Fuel adjustment {faf}% of {amount:,.2f}",
                     "lane": "", "qty": "", "rate": f"{faf}%", "amount": pct_of(faf, amount)})
    return rows


def minimum_linehaul(ref, shipment, pickup, lane, kg, faf=None):
    rows = [{"ref": ref, "shp": shipment, "pickup": pickup, "svc": "Linehaul (minimum)", "lane": lane,
             "qty": f"{D(kg):.1f} kg", "rate": MINIMUM, "amount": D(MINIMUM)}]
    if faf:
        rows.append({"ref": "", "shp": shipment, "pickup": "", "svc": f"Fuel adjustment {faf}% of {MINIMUM}",
                     "lane": "", "qty": "", "rate": f"{faf}%", "amount": pct_of(faf, MINIMUM)})
    return rows


def fee(shipment, svc, qty, rate, amount=None):
    return {"ref": "", "shp": shipment, "pickup": "", "svc": svc, "lane": "", "qty": qty, "rate": rate,
            "amount": r2(amount if amount is not None else D(rate))}


def invoice(no: str, inv_date: str, due: str, rows: list[dict], thousands: bool = True) -> tuple[bytes, str]:
    """thousands=False prints 1650.00 instead of 1,650.00 (a metamorphic variant: same values)."""
    money = (lambda x: f"{x:,.2f}") if thousands else (lambda x: f"{x:.2f}")
    total = sum((r["amount"] for r in rows), D("0.00"))
    cols = [(48, "Ln"), (66, "Shipment"), (124, "Pickup"), (176, "Service"), (330, "Lane"), (390, "Chg. Wt"),
            (440, "Rate"), (490, "Amount (USD)")]
    body = [[(48, i), (66, r["shp"]), (124, us(r["pickup"]) if r["pickup"] else ""), (176, r["svc"]),
             (330, r["lane"]), (390, r["qty"]), (440, r["rate"]), (490, money(r['amount']))]
            for i, r in enumerate(rows, 1)]
    page = [("h", "FENWICK RIDGE AIRFREIGHT INC."), "Revenue Accounting, 1200 Prairie Gate Dr, Elk Grove IL",
            ("h", "FREIGHT INVOICE"),
            f"Invoice No: {no}", f"Invoice Date: {us(inv_date)}", f"Due Date: {us(due)}",
            f"Contract: {CID}", f"Customer: {CUSTOMER}, Accounts Payable", cols] + body + [
            ("gap",), f"Subtotal USD {money(total)}", "Tax USD 0.00", f"Amount Due USD {money(total)}",
            "Questions about this invoice: your Key Account Manager under Schedule 1."]
    return pdf([page]), f"{total:,.2f}"


def tracking(events: list[tuple[str, str, str]]) -> bytes:
    rows = [["Status Date", "Shipment Ref", "Status", "Facility"]]
    rows += [[pickup, shp, "PICKED_UP", fac] for shp, pickup, fac in events]
    return xlsx([("Pickups", rows)])


def ledger(rows: list[list]) -> bytes:
    """rows: [doc_no, amount, status, date_paid]"""
    return xlsx([("AP ledger", [["Doc No.", "Amount Due", "Pay Status", "Date Paid"]] + rows)], money_cols={1})


# ---- mailbox helpers -------------------------------------------------------------------------------------------------
def start(name: str) -> Mailbox:
    m = Mailbox(name)
    m.mail("batch_01", "2043-01-05", WEN, RAFE, f"Signed agreement {CID}",
           f"""Rafe -

           Countersigned copy of {CID} with Fenwick Ridge attached; it runs from January 1, 2043.
           Please use the Exhibits when checking their invoices.

           Wen""", [(f"{CID}.pdf", agreement())])
    return m


def send_invoice(m: Mailbox, batch: str, when: str, no: str, due: str, rows, thousands: bool = True,
                 body: str | None = None) -> tuple[str, str]:
    data, total = invoice(no, when, due, rows, thousands)
    doc = m.mail(batch, when, BILLING, RAFE, f"Fenwick Ridge invoice {no}",
                 body or f"""Good morning,

                 Invoice {no} under contract {CID} is attached for your review.

                 Fenwick Ridge Billing""", [(f"{no}.pdf", data)])
    return f"{doc}#{no}.pdf", total


def send_tracking(m: Mailbox, batch: str, when: str, events):
    return m.mail(batch, when, OPS, WEN, f"Pickup confirmations through {us(when)}",
                  "Pickup events for your shipments are in the attached export.\n\nFenwick Ridge Operations",
                  [(f"pickups-{when}.xlsx", tracking(events))])
