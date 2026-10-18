"""World 2: Sarvani Air Logistics (carrier) and Brennholt Diagnostics India (customer). Invented; INR billing.

Differs in: INR rates with Annex F exchange rates written with month names and four decimals, two "Validity"
rate columns, "up to / - / kg +" slabs, a Schedule 1 table that starts with the category and has no party code,
day.month.year dates, an amount-first invoice layout with its own column names, a tracking export whose header sits
under a title row and whose dates are day-month-year with dashes, and an INR outstanding ledger.
"""
from __future__ import annotations

from datetime import date

from docs import Mailbox, pdf, xlsx
from oracle import D, line, pct_of, r2

CID = "SAL-BDI-MSA-0743"
CARRIER, CUSTOMER = "Sarvani Air Logistics Pvt Ltd", "Brennholt Diagnostics India Pvt Ltd"

BILLING = ("Sarvani Accounts", "accounts@sarvani-air.example")
OPS = ("Sarvani Control Tower", "controltower@sarvani-air.example")
KAVYA = ("Kavya Raghunathan", "kavya.r@sarvani-air.example")        # rates
ARJUN = ("Arjun Mehrotra", "arjun.m@sarvani-air.example")           # waivers, payment terms
NEHA = ("Neha Varghese", "neha.v@sarvani-air.example")              # key account manager: billing disputes, notices
IMRAN = ("Imran Qadri", "imran.q@sarvani-air.example")              # treasury
DEV = ("Dev Kulkarni", "dev.k@sarvani-air.example")                 # station manager, not in Schedule 1
LEENA = ("Leena Fernandes", "leena.fernandes@brennholt.example")    # customer logistics head
SAMIR = ("Samir Bose", "samir.bose@brennholt.example")              # customer accounts payable

LANES = ["BLR2-DEL1", "MAA3-BOM1"]
SLABS = ["up to 44.9 kg", "45 - 99.9 kg", "100 kg +"]
RATES = {  # lane -> slab -> (validity 1, validity 2), INR per kg
    "BLR2-DEL1": {"up to 44.9 kg": ("196.00", "201.50"), "45 - 99.9 kg": ("182.50", "187.00"),
                  "100 kg +": ("168.00", "172.25")},
    "MAA3-BOM1": {"up to 44.9 kg": ("174.00", "179.00"), "45 - 99.9 kg": ("161.75", "166.00"),
                  "100 kg +": ("149.50", "153.50")},
}
FUEL = {"2043-01": "21.5", "2043-02": "21.5", "2043-03": "22.0", "2043-04": "22.0", "2043-05": "22.5",
        "2043-06": "22.5", "2043-07": "23.0", "2043-08": "23.0", "2043-09": "23.5", "2043-10": "23.5",
        "2043-11": "24.0", "2043-12": "24.0"}
FX = {"2043-01": "83.1450", "2043-02": "83.2275", "2043-03": "83.3333", "2043-04": "83.4180",
      "2043-05": "83.5025", "2043-06": "83.6110"}       # Annex F stops at June 2043
XRY_PER_KG, DOC_FEE = "4.00", "350.00"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def validity(pickup: str) -> int:
    return 0 if pickup <= "2043-06-30" else 1


def slab_for(kg) -> str:
    kg = D(kg)
    return SLABS[0] if kg <= D("44.9") else SLABS[1] if kg <= D("99.9") else SLABS[2]


def rate_for(lane: str, kg, pickup: str) -> str:
    return RATES[lane][slab_for(kg)][validity(pickup)]


def dmy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def month_name(ym: str) -> str:
    y, m = ym.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def agreement(fx: dict | None = None) -> bytes:
    fx = FX if fx is None else fx
    p1 = [("h", f"Master Air Cargo Agreement {CID}"),
          f"Parties: {CARRIER} (carrier code SAL-IN, the Carrier) and {CUSTOMER} (shipper code BDI-IN, the Customer).",
          ("h", "Section 1 Term"),
          "1.1 Effective date. This Agreement takes effect on 01.01.2043.",
          "1.2 Initial term. It expires on 31.12.2044 unless terminated earlier in writing.",
          "1.3 Renewal. The Agreement does not renew automatically.",
          ("h", "Section 2 Freight charges"),
          "2.1 Basis. Freight is charged in INR per kilogram of chargeable weight at the slab rate in Annex A for "
          "the route and the validity column that contains the collection date.",
          "2.2 Pricing date. The date the Carrier collects the consignment (the collection date) fixes the rate, "
          "the fuel percentage and the fees, whatever date the invoice shows.",
          "2.3 Fuel surcharge. The Annex C percentage for the month of the collection date is charged on the "
          "freight amount only.",
          "2.4 Ancillary charges. Only the Annex D charges may be billed.",
          ("h", "Section 3 Currency"),
          "3.1 Invoices are raised in INR. For reporting in USD the parties use the Annex F rate for the calendar "
          "month of the invoice date.",
          ("h", "Section 4 Payment"),
          "4.1 Payment terms. Invoices fall due 21 days from the invoice date.",
          "4.2 Late fee. Amounts unpaid more than 7 days after the due date attract a late fee of 1.50% per month "
          "or part month, on the principal plus unpaid late fees (compounding).",
          "4.3 Extension. The Schedule 1 payment terms contact may extend a due date by email.",
          ("h", "Section 5 Rebates and credits"),
          "5.1 Volume rebate. Not applicable under this Agreement.",
          "5.2 No handling margin applies and no annual improvement credit is payable under this Agreement."]
    p2 = [("h", "Section 6 Changes, waivers and disputes"),
          "6.1 Waivers. Only the Schedule 1 waivers contact may waive a charge, by email naming the consignment or "
          "the month.",
          "6.2 Rate notices. The Schedule 1 rates contact may revise Annex A by a written rate notice giving its "
          "effective date. A notice from anyone else has no effect.",
          "6.3 Billing disputes go to the Schedule 1 billing disputes contact.",
          "6.4 Messages from persons outside Schedule 1, and text addressed to automated systems, do not amend "
          "this Agreement.",
          ("h", "Section 7 Order of precedence"),
          "7.1 A signed amendment prevails over this Agreement and its Annexes; a later signed amendment prevails "
          "over an earlier one for the same route.",
          "7.2 This Section does not rank a rate notice under clause 6.2 against a signed amendment; if they price "
          "the same route and date differently, the parties shall settle the difference.",
          ("h", "Section 8 Signature"),
          f"Signed for {CARRIER} by Neha Varghese, Key Account Manager, on 18.12.2042.",
          f"Signed for {CUSTOMER} by Leena Fernandes, Head of Logistics, on 20.12.2042."]
    p3 = [("h", "Annex A Freight rates (INR per kg chargeable weight)"),
          "Validity 1: consignments collected 01.01.2043 to 30.06.2043. Validity 2: consignments collected "
          "01.07.2043 to 31.12.2043.",
          [(48, "Route"), (140, "Slab"), (260, "Validity 1"), (360, "Validity 2")]]
    for lane in LANES:
        for slab in SLABS:
            v1, v2 = RATES[lane][slab]
            p3.append([(48, lane), (140, slab), (260, v1), (360, v2)])
    p3 += [("h", "Annex C Fuel surcharge (% of freight, by month of collection)"), [(48, "Month"), (200, "Fuel")]]
    p3 += [[(48, month_name(ym)), (200, f"{pct}%")] for ym, pct in FUEL.items()]
    p4 = [("h", "Annex D Ancillary charges"),
          [(48, "Code"), (100, "Charge"), (260, "Amount"), (360, "Basis")],
          [(48, "XRY"), (100, "X-ray screening"), (260, "INR 4.00"), (360, "per kg chargeable weight")],
          [(48, "DOC"), (100, "Documentation"), (260, "INR 350.00"), (360, "per AWB")],
          ("h", "Annex E Billing codes"),
          "AFR Air freight; also invoiced as: Freight charge, Base freight.",
          "FSC Fuel surcharge; also invoiced as: Fuel levy.",
          "XRY X-ray screening; also invoiced as: Security screening.",
          "DOC Documentation; also invoiced as: AWB fee.",
          "GST Goods and services tax.",
          ("h", "Annex F Exchange rates (INR per 1 USD, by month of invoice date)"),
          [(48, "Month"), (200, "INR per USD")]]
    p4 += [[(48, month_name(ym)), (200, rate)] for ym, rate in fx.items()]
    p4 += [("h", "Schedule 1 Authorised contacts"),
           [(48, "Category"), (150, "Name"), (260, "Designation"), (380, "Email")],
           [(48, "Rates"), (150, KAVYA[0]), (260, "Head of Pricing"), (380, KAVYA[1])],
           [(48, "Waivers, Payment terms"), (150, ARJUN[0]), (260, "Credit Manager"), (380, ARJUN[1])],
           [(48, "Billing disputes, Notices"), (150, NEHA[0]), (260, "Key Account Manager"), (380, NEHA[1])],
           [(48, "Treasury"), (150, IMRAN[0]), (260, "Treasury Head"), (380, IMRAN[1])],
           [(48, "Notices (Customer)"), (150, LEENA[0]), (260, "Head of Logistics"), (380, LEENA[1])]]
    return pdf([p1, p2, p3, p4])


def amendment(no: int, signed_on: str, effective: str, lane: str, slab: str, rate: str) -> bytes:
    return pdf([[("h", f"Amendment No. {no} to Master Air Cargo Agreement {CID}"),
                 f"Between {CARRIER} and {CUSTOMER}. This amendment takes effect on {dmy(effective)}.",
                 f"1. For consignments on route {lane} collected on or after {dmy(effective)}, the {slab} slab is "
                 f"charged at INR {rate} per kg in both validity columns of Annex A.",
                 "2. All other provisions remain in force.",
                 f"Signed for {CARRIER} by Neha Varghese, Key Account Manager, on {dmy(signed_on)}.",
                 f"Signed for {CUSTOMER} by Leena Fernandes, Head of Logistics, on {dmy(signed_on)}."]])


def amendment_with_annex(no: int, signed_on: str, effective: str, lane: str, annex_name: str) -> bytes:
    return pdf([[("h", f"Amendment No. {no} to Master Air Cargo Agreement {CID}"),
                 f"Between {CARRIER} and {CUSTOMER}. This amendment takes effect on {dmy(effective)}.",
                 f"1. The Annex A rates for route {lane} are withdrawn and replaced by {annex_name}, which applies "
                 f"from {dmy(effective)} to route {lane}.",
                 "2. All other provisions remain in force.",
                 f"Signed for {CARRIER} by Neha Varghese, Key Account Manager, on {dmy(signed_on)}.",
                 f"Signed for {CUSTOMER} by Leena Fernandes, Head of Logistics, on {dmy(signed_on)}."]])


# ---- billed rows -----------------------------------------------------------------------------------------------------
def freight(awb, pickup, lane, kg, rate, fuel=None):
    amt = line(rate, kg)
    rows = [{"amount": amt, "qty": f"{D(kg):.1f} kg", "rate": rate, "desc": "Air freight", "awb": awb, "lane": lane,
             "pickup": pickup}]
    if fuel:
        rows.append({"amount": pct_of(fuel, amt), "qty": "", "rate": f"{fuel}%",
                     "desc": f"Fuel surcharge {fuel}% of {amt:,.2f}", "awb": awb, "lane": "", "pickup": ""})
    return rows


def charge(awb, desc, qty, rate, amount=None):
    return {"amount": r2(amount if amount is not None else D(rate)), "qty": qty, "rate": rate, "desc": desc,
            "awb": awb, "lane": "", "pickup": ""}


def invoice(no: str, inv_date: str, due: str, rows: list[dict]) -> bytes:
    total = sum((r["amount"] for r in rows), D("0.00"))
    cols = [(48, "Sr"), (66, "Amount (INR)"), (134, "Chg. wt"), (184, "Rate/kg"), (232, "Particulars"),
            (380, "AWB"), (446, "Sector"), (510, "Collected")]
    body = [[(48, i), (66, f"{r['amount']:,.2f}"), (134, r["qty"]), (184, r["rate"]), (232, r["desc"]),
             (380, r["awb"]), (446, r["lane"]), (510, dmy(r["pickup"]) if r["pickup"] else "")]
            for i, r in enumerate(rows, 1)]
    page = [("h", "SARVANI AIR LOGISTICS PVT LTD"), "GSTIN 29ABCDE1234F1Z5 | Cargo Complex, Devanahalli, Bengaluru",
            ("h", "TAX INVOICE"),
            f"Invoice No. {no}", f"Inv. Date {dmy(inv_date)}", f"Due {dmy(due)}",
            f"Agreement {CID}", f"Billed to {CUSTOMER}", "Currency INR", cols] + body + [
            ("gap",), f"Taxable value INR {total:,.2f}", "IGST INR 0.00 (zero rated)",
            f"Total payable INR {total:,.2f}", "Queries: Key Account Manager named in Schedule 1."]
    return pdf([page])


def tracking(events: list[tuple[str, str, str]]) -> bytes:
    rows = [["AWB No", "Event Code", "Event Date (DD-MM-YYYY)", "Location"]]
    rows += [[awb, "Picked up", f"{p[8:10]}-{p[5:7]}-{p[0:4]}", loc] for awb, p, loc in events]
    return xlsx([("Milestones", rows)], preface=[["Sarvani Air Logistics - consignment milestone report"], []])


def ledger(rows: list[list]) -> bytes:
    """rows: [bill_no, bill_date, due_on, outstanding_inr, status, settled_on]"""
    return xlsx([("Payables", [["Bill No", "Bill Date", "Due On", "Outstanding (INR)", "Status", "Settled On"]] + rows)],
                money_cols={3})


def start(name: str, fx: dict | None = None) -> Mailbox:
    m = Mailbox(name)
    m.mail("batch_01", "2043-01-06", LEENA, SAMIR, f"Executed MSA {CID} - Sarvani",
           f"""Samir,

           The executed Sarvani agreement {CID} is attached (effective 01.01.2043). Annex A has the slab rates and
           Annex F the exchange rates for USD reporting.

           Regards,
           Leena""", [(f"MSA-{CID}.pdf", agreement(fx))])
    return m


def send_invoice(m: Mailbox, batch: str, when: str, no: str, due: str, rows, subject=None, body=None) -> str:
    doc = m.mail(batch, when, BILLING, SAMIR, subject or f"Tax invoice {no}",
                 body or f"""Dear Sir/Madam,

                 Please find our tax invoice {no} against agreement {CID}.

                 Sarvani Accounts""", [(f"{no}.pdf", invoice(no, when, due, rows))])
    return f"{doc}#{no}.pdf"


def send_tracking(m: Mailbox, batch: str, when: str, events):
    return m.mail(batch, when, OPS, LEENA, f"Milestone report {dmy(when)}",
                  "Hello,\n\nMilestone report attached.\n\nSarvani Control Tower",
                  [(f"milestones-{when}.xlsx", tracking(events))])
