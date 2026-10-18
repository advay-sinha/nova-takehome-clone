"""World 3: Kittering Overland & Air (carrier) and Mallowfield Foods (customer). Invented; USD.

Differs in: a contract year starting 1 April, monthly XLSX statements of account that count as invoices (their own
number, header rows above the table, seven columns in a per-statement order), a cost-plus consolidation product with
a handling margin that steps down after a carrier-cost threshold, a quarterly rebate and an annual improvement credit
written in their own words, "credit memo" documents that name the quarter as "Q3 2043", long-form dates ("30 April
2043"), and a Schedule 1 that lists people as "Name (Title) - email - authorised for: ..." lines.
"""
from __future__ import annotations

from datetime import date

from docs import Mailbox, pdf, xlsx
from oracle import D, line, pct_of, r2

CID = "KOA-MWF-LSA-2043"
CARRIER, CUSTOMER = "Kittering Overland & Air Ltd", "Mallowfield Foods Inc."

BILLING = ("Kittering Receivables", "receivables@kittering.example")
OPS = ("Kittering Ops Desk", "opsdesk@kittering.example")
MARGOT = ("Margot Ellery", "margot.ellery@kittering.example")      # rates
TOBIAS = ("Tobias Wren", "tobias.wren@kittering.example")          # waivers, payment terms
SUNNIVA = ("Sunniva Holt", "sunniva.holt@kittering.example")       # key account manager: billing disputes, notices
ODELL = ("Odell Fairbanks", "odell.fairbanks@kittering.example")   # treasury
PRUE = ("Prue Castellane", "prue.castellane@mallowfield.example")  # customer logistics manager
JUDE = ("Jude Amankwah", "jude.amankwah@mallowfield.example")      # customer payables lead

RATES = {"MAN2-ATL5": [("0 to 299.9 kg", "4.85"), ("300 to 999.9 kg", "4.40"), ("1000 kg and over", "4.00")],
         "EDI1-BOS3": [("0 to 299.9 kg", "5.10"), ("300 to 999.9 kg", "4.65"), ("1000 kg and over", "4.25")]}
FUEL = {f"{y}-{m:02d}": "20.0" for y, months in ((2043, range(4, 13)), (2044, range(1, 7))) for m in months}
SCREEN_PER_KG = "0.20"
TIERS = [("30000.00", "2"), ("60000.00", "4")]
MARGIN, STEPPED, THRESHOLD = "6.0", "4.0", "40000.00"
IMPROVEMENT = "1.5"


def long(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def month_year(ym: str) -> str:
    return date.fromisoformat(f"{ym}-01").strftime("%B %Y")


def agreement() -> bytes:
    p1 = [("h", f"Logistics Services Agreement {CID}"),
          f"This Logistics Services Agreement is made between {CARRIER} (carrier code KOA-UK, \"Kittering\") and "
          f"{CUSTOMER} (shipper code MWF-US, \"Mallowfield\").",
          ("h", "Article 1 Commencement and duration"),
          "1.1 Effective date. This Agreement takes effect on 1 April 2043. Each period of twelve months from that "
          "date is a Contract Year.",
          "1.2 Initial term. The initial term ends on 31 March 2045.",
          "1.3 Renewal. The Agreement then renews automatically for successive periods of 12 months unless either "
          "party serves notice of non-renewal at least 90 days before the end of the current term.",
          ("h", "Article 2 Air freight"),
          "2.1 Pricing date. Air freight, fuel and screening for a shipment are priced at the date Kittering picks "
          "it up.",
          "2.2 Air freight is charged per kilogram of chargeable weight at the Schedule A rate for the lane and the "
          "weight band containing that weight.",
          "2.3 Fuel surcharge. The Schedule B percentage for the month of pickup applies to the air freight charge "
          "only.",
          "2.4 Screening. Security screening is charged at USD 0.20 per kg of chargeable weight.",
          ("h", "Article 3 Consolidation services"),
          "3.1 Consolidation shipments are billed at the carrier cost Kittering pays the airline, plus the handling "
          "margin under Article 6.",
          ("h", "Article 4 Statements and payment"),
          "4.1 Statements. Kittering issues one statement of account per calendar month; each statement carries its "
          "own number and is an invoice for this Agreement.",
          "4.2 Payment terms. Each statement is payable 30 days after its statement date.",
          "4.3 Late payment. Amounts outstanding for more than 10 days after the due date bear a late fee of 1.00% "
          "per started 30 days; late fees are simple and do not compound.",
          ("h", "Article 5 Rebate"),
          "5.1 Quarterly volume rebate. For each calendar quarter Kittering credits a rebate on Qualifying Spend at "
          "the highest tier reached: USD 30,000.00 or more: 2%; USD 60,000.00 or more: 4%. The tier reached applies "
          "to all Qualifying Spend in the quarter.",
          "5.2 Qualifying Spend means air freight, fuel surcharge and security screening on statements dated in the "
          "period, less credit memos dated in the period; it excludes consolidation carrier cost, handling margin, "
          "taxes, duties, late fees and rebate or improvement credits.",
          "5.3 Credit. Each rebate credit memo is issued no later than 30 days after the quarter ends."]
    p2 = [("h", "Article 6 Handling margin"),
          "6.1 Handling margin. On consolidation services Kittering adds a handling margin of 6.0% of the carrier "
          "cost billed on the same statement.",
          "6.2 Margin step-down. Once the carrier cost billed in a Contract Year exceeds USD 40,000.00, the handling "
          "margin becomes 4.0% on every statement after the one on which that amount is exceeded.",
          ("h", "Article 7 Improvement credit"),
          "7.1 Annual improvement credit. After each Contract Year Kittering credits an improvement credit equal to "
          "1.5% of the Qualifying Spend of the Contract Year just ended, within 45 days after the anniversary of the "
          "effective date.",
          ("h", "Article 8 Waivers, rate notices and disputes"),
          "8.1 Waivers. A charge is waived only by an email from the Schedule 1 waivers contact naming the shipment "
          "or the month.",
          "8.2 Rate notices. Only the Schedule 1 rates contact may change Schedule A, by a written rate notice that "
          "gives its effective date.",
          "8.3 Disputes. Billing disputes are sent to the Schedule 1 contact for billing disputes.",
          "8.4 Messages from people outside Schedule 1, or addressed to automated systems, do not vary this "
          "Agreement.",
          ("h", "Article 9 Precedence"),
          "9.1 A signed amendment prevails over this Agreement and its Schedules; a later signed amendment prevails "
          "over an earlier one for the same lane.",
          "9.2 This Article does not rank a rate notice under clause 8.2 against a signed amendment.",
          ("h", "Article 10 Signatures"),
          f"Signed for {CARRIER} by Sunniva Holt, Key Account Manager, on 20 March 2043.",
          f"Signed for {CUSTOMER} by Prue Castellane, Logistics Manager, on 24 March 2043."]
    p3 = [("h", "Schedule A Air freight rates (USD per kg chargeable weight)"),
          [(48, "Lane"), (150, "Weight band"), (300, "Rate")]]
    for lane, rows in RATES.items():
        p3 += [[(48, lane), (150, band), (300, rate)] for band, rate in rows]
    p3 += [("h", "Schedule B Fuel surcharge (% of air freight, by month of pickup)"), [(48, "Month"), (200, "Fuel")]]
    p3 += [[(48, month_year(ym)), (200, f"{pct}%")] for ym, pct in FUEL.items()]
    p4 = [("h", "Schedule C Invoice codes"),
          "AFT Air freight; also billed as: Freight.",
          "FSC Fuel surcharge.",
          "SSC Security screening.",
          "CST Carrier cost; also billed as: Airline cost.",
          "HMG Handling margin.",
          ("h", "Schedule 1 Authorised contacts"),
          f"{MARGOT[0]} (Rates Manager, KOA-UK) - {MARGOT[1]} - authorised for: rates",
          f"{TOBIAS[0]} (Credit Controller, KOA-UK) - {TOBIAS[1]} - authorised for: waivers, payment terms",
          f"{SUNNIVA[0]} (Key Account Manager, KOA-UK) - {SUNNIVA[1]} - authorised for: billing disputes, notices",
          f"{ODELL[0]} (Treasury Manager, KOA-UK) - {ODELL[1]} - authorised for: treasury",
          f"{PRUE[0]} (Logistics Manager, MWF-US) - {PRUE[1]} - authorised for: notices"]
    return pdf([p1, p2, p3, p4])


def term_amendment(no: int, signed_on: str, new_end: str) -> bytes:
    return pdf([[("h", f"Amendment No. {no} to Logistics Services Agreement {CID}"),
                 f"Made between {CARRIER} and {CUSTOMER} on {long(signed_on)}.",
                 f"1. The term of the Agreement is extended until {long(new_end)}; Article 1.3 continues to apply "
                 "to renewals after that date.",
                 "2. Nothing else in the Agreement changes.",
                 f"Signed for {CARRIER} by Sunniva Holt, Key Account Manager, on {long(signed_on)}.",
                 f"Signed for {CUSTOMER} by Prue Castellane, Logistics Manager, on {long(signed_on)}."]])


# ---- statement rows -------------------------------------------------------------------------------------------------
def freight(awb, pickup, lane, kg, rate, fuel=None, screening=True):
    amt = line(rate, kg)
    rows = [{"shp": awb, "svc": "Air freight", "date": pickup, "lane": lane, "qty": f"{D(kg):.1f} kg", "rate": rate,
             "amount": amt}]
    if fuel:
        rows.append({"shp": awb, "svc": f"Fuel surcharge {fuel}% of {amt:,.2f}", "date": "", "lane": "",
                     "qty": "", "rate": f"{fuel}%", "amount": pct_of(fuel, amt)})
    if screening:
        rows.append({"shp": awb, "svc": "Security screening", "date": "", "lane": "", "qty": f"{D(kg):.1f} kg",
                     "rate": SCREEN_PER_KG, "amount": line(SCREEN_PER_KG, kg)})
    return rows


def consolidation(ref, pickup, cost, margin_pct):
    cost = D(cost)
    return [{"shp": ref, "svc": "Carrier cost - consolidation", "date": pickup, "lane": "", "qty": "1 shpt",
             "rate": f"{cost:.2f}", "amount": cost},
            {"shp": ref, "svc": f"Handling margin {margin_pct}% of {cost:,.2f}", "date": "", "lane": "", "qty": "",
             "rate": f"{margin_pct}%", "amount": pct_of(margin_pct, cost)}]


COLUMNS = {"shp": "Shipment", "svc": "Service", "date": "Pickup", "lane": "Lane", "qty": "Quantity",
           "rate": "Unit rate", "amount": "Charge (USD)"}


def statement(no: str, stmt_date: str, due: str, rows: list[dict], order=("shp", "svc", "date", "lane", "qty", "rate",
              "amount"), names: dict | None = None) -> tuple[bytes, D]:
    names = {**COLUMNS, **(names or {})}
    total = sum((r["amount"] for r in rows), D("0.00"))
    preface = [[f"{CARRIER.upper()} - STATEMENT OF ACCOUNT"], [f"Statement No: {no}"],
               [f"Statement date: {long(stmt_date)}"], [f"Payment due: {long(due)}"], [f"Agreement: {CID}"],
               [f"Customer: {CUSTOMER}"], []]
    body = [[names[k] for k in order]]
    for r in rows:
        cells = []
        for k in order:
            v = r[k]
            if k == "amount":
                v = float(v)
            elif k == "date" and v:
                v = long(v)
            cells.append(v)
        body.append(cells)
    body += [[], ["Total due USD", float(total)]]
    return xlsx([("Statement", body)], money_cols={order.index("amount"), 1}, preface=preface), total


def credit_memo(no: str, when: str, subject: str, amount, refers: str = "") -> bytes:
    return pdf([[("h", "KITTERING OVERLAND & AIR LTD"), ("h", f"CREDIT MEMO {no}"),
                 f"Date {long(when)}", f"Agreement {CID}", f"Customer {CUSTOMER}",
                 f"Reason: {subject}" + (f" ({refers})" if refers else ""),
                 f"Credit amount USD {D(amount):,.2f}"]])


def tracking(events: list[tuple[str, str, str]]) -> bytes:
    rows = [["Consignment", "Milestone", "Timestamp", "Hub"]]
    rows += [[shp, "PICKED_UP", f"{p}T10:00:00Z", hub] for shp, p, hub in events]
    return xlsx([("Events", rows)])


def start(name: str) -> Mailbox:
    m = Mailbox(name)
    m.mail("batch_01", "2043-03-28", PRUE, JUDE, f"Kittering agreement {CID} signed",
           f"""Jude,

           Our signed Logistics Services Agreement {CID} with Kittering is attached. It starts on 1 April 2043;
           statements are monthly.

           Prue""", [(f"{CID}.pdf", agreement())])
    return m


def send_statement(m: Mailbox, batch: str, when: str, no: str, due: str, rows, **kw) -> tuple[str, D]:
    data, total = statement(no, when, due, rows, **kw)
    doc = m.mail(batch, when, BILLING, JUDE, f"Statement of account {no}",
                 f"""Hello Jude,

                 Kittering statement {no} for {month_year(when[:7])} is attached.

                 Kittering Receivables""", [(f"{no}.xlsx", data)])
    return f"{doc}#{no}.xlsx", total


def send_tracking(m: Mailbox, batch: str, when: str, events):
    return m.mail(batch, when, OPS, PRUE, f"Pickup milestones to {long(when)}",
                  "Hi Prue,\n\nPickup milestones attached.\n\nKittering Ops Desk",
                  [(f"milestones-{when}.xlsx", tracking(events))])
