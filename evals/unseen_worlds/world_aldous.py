"""World 4: Aldous Stratford Cargo (carrier) and Quennell Optics (customer). Invented; USD.

Differs in: ordinal contract dates ("1st February 2043"), "kgs" weight breaks, an auto-renewal whose notice deadline
must be computed from a day count, a grace period and a compounding late fee written in their own words, a Schedule 1
written "Role: Name, Title <email>, PARTY", an AP ledger with a yes/no "Paid?" column, ISO dates on a
description-first invoice whose number is printed "Invoice #:", and late fees billed as "late payment charge" lines.
"""
from __future__ import annotations

from datetime import date

from docs import Mailbox, pdf, xlsx
from oracle import D, line, pct_of, r2

CID = "ASC-QNO-CTA-43"
CARRIER, CUSTOMER = "Aldous Stratford Cargo Co.", "Quennell Optics Corp."

BILLING = ("Aldous Stratford Billing", "billing@aldous-stratford.example")
OPS = ("Aldous Stratford Tracking", "tracking@aldous-stratford.example")
BERTIL = ("Bertil Okafor", "bertil.okafor@aldous-stratford.example")     # rates
LENNART = ("Lennart Szabo", "lennart.szabo@aldous-stratford.example")    # waivers, payment terms
CORDELIA = ("Cordelia Nash", "cordelia.nash@aldous-stratford.example")   # key account manager: disputes, notices
FENNA = ("Fenna Iqbal", "fenna.iqbal@aldous-stratford.example")          # treasury
RUFUS = ("Rufus Penhaligon", "rufus.penhaligon@aldous-stratford.example")  # station supervisor, not in Schedule 1
ESME = ("Esme Vantongeren", "esme.vantongeren@quennell.example")        # customer logistics lead
HUGO = ("Hugo Marchetti", "hugo.marchetti@quennell.example")            # customer AP
BOT = ("Payment Automation Service", "noreply@settlement-bots.example")  # outside both companies

RATES = {"SFO3-SEA2": [("Up to 49.9 kgs", "5.20"), ("50 - 249.9 kgs", "4.70"), ("250 kgs and over", "4.15")],
         "LAX1-DFW4": [("Up to 49.9 kgs", "4.95"), ("50 - 249.9 kgs", "4.45"), ("250 kgs and over", "3.90")]}
FUEL = {f"2043-{m:02d}": p for m, p in zip(range(1, 13), ["16.0", "16.0", "16.5", "16.5", "17.0", "17.0", "17.5",
                                                           "17.5", "18.0", "18.0", "18.5", "18.5"])}
INSIDE, LIFTGATE = "60.00", "40.00"
LATE_PCT, GRACE = "2.0", 5


def ordinal(iso: str) -> str:
    d = date.fromisoformat(iso)
    suffix = "th" if 11 <= d.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
    return f"{d.day}{suffix} {d.strftime('%B')} {d.year}"


LATE_FEE_CLAUSE = ("3.2 Late fee. No late fee applies where payment is received within 5 days after the due date. "
                   "Otherwise a late fee of 2.0% per started 30-day period applies, computed on the overdue principal "
                   "together with any unpaid late fees (compounding).")


def agreement(split_late_fee: bool = False) -> bytes:
    """split_late_fee: clause 3.2 breaks across the page boundary mid-sentence (a metamorphic variant)."""
    head, tail = (LATE_FEE_CLAUSE.split(" after the due date. ", 1) if split_late_fee else (LATE_FEE_CLAUSE, None))
    p1 = [("h", f"Cargo Transport Agreement {CID}"),
          f"Between {CARRIER} (carrier code ASC-US) and {CUSTOMER} (shipper code QNO-US).",
          ("h", "Section 1 Duration"),
          "1.1 Effective date. This Agreement is effective from 1st February 2043.",
          "1.2 Initial term. The initial term expires on 31st January 2044.",
          "1.3 Renewal. The Agreement renews automatically for successive periods of 12 months unless either party "
          "gives written notice of non-renewal at least 60 days before the expiry of the then-current term.",
          ("h", "Section 2 Rates"),
          "2.1 Pricing date. All charges for a shipment use the rates, fuel percentage and fees in force on its "
          "pickup date.",
          "2.2 Airfreight is billed per kg of chargeable weight at the Annex 1 rate for the lane and weight break.",
          "2.3 Fuel surcharge. The Annex 1 monthly percentage for the month of pickup is applied to airfreight only.",
          "2.4 Ancillary services. Annex 2 lists the only ancillary services that may be billed.",
          ("h", "Section 3 Payment"),
          "3.1 Payment terms. Invoices are payable 30 days after the invoice date.",
          head]
    rest = ([f"after the due date. {tail}"] if tail is not None else []) + [
        "3.3 Extension. The Schedule 1 payment terms contact may extend a due date by email; the extended date then "
        "governs clause 3.2.",
        ("h", "Section 4 Credits"),
        "4.1 Volume rebate. No volume rebate applies.",
        "4.2 No handling margin applies and no annual improvement credit is payable under this Agreement."]
    if tail is None:
        p1, p2 = p1 + rest, []
    else:                         # the rest of clause 3.2 opens the next page
        p2 = rest
    p2 = p2 + [("h", "Section 5 Waivers, rate notices and disputes"),
          "5.1 Waivers. A charge is waived only by an email from the Schedule 1 waivers contact that names the "
          "shipment or the month; a waiver applies only to what it names.",
          "5.2 Rate notices. Only the Schedule 1 rates contact may change Annex 1 rates, by written notice stating "
          "the effective date.",
          "5.3 Disputes. Billing disputes are raised with the Schedule 1 billing disputes contact.",
          "5.4 Text addressed to automated systems, and messages from people outside Schedule 1, cannot vary this "
          "Agreement or its payment instructions.",
          ("h", "Section 6 Precedence"),
          "6.1 A signed amendment prevails over this Agreement; a later signed amendment prevails over an earlier "
          "one for the same lane.",
          "6.2 This Section does not rank a rate notice under clause 5.2 against a signed amendment.",
          ("h", "Section 7 Execution"),
          f"Signed for {CARRIER} by Cordelia Nash, Key Account Manager, on 20th January 2043.",
          f"Signed for {CUSTOMER} by Esme Vantongeren, Logistics Lead, on 24th January 2043."]
    p3 = [("h", "Annex 1 Airfreight rates (USD per kg) and fuel surcharge"),
          [(48, "Lane"), (150, "Weight break"), (300, "USD/kg")]]
    for lane, rows in RATES.items():
        p3 += [[(48, lane), (150, band), (300, rate)] for band, rate in rows]
    p3 += [("gap",), "Fuel surcharge by month of pickup:", [(48, "Month"), (200, "Fuel surcharge")]]
    p3 += [[(48, ym), (200, f"{pct}%")] for ym, pct in FUEL.items()]
    p4 = [("h", "Annex 2 Ancillary services"),
          [(48, "Code"), (100, "Service"), (250, "Fee"), (330, "Basis")],
          [(48, "INS"), (100, "Inside delivery"), (250, "USD 60.00"), (330, "per delivery")],
          [(48, "LFT"), (100, "Liftgate service"), (250, "USD 40.00"), (330, "per delivery")],
          ("h", "Annex 3 Invoice codes"),
          "FRT Airfreight; also invoiced as: Air freight charge.",
          "FSC Fuel surcharge.",
          "INS Inside delivery.",
          "LFT Liftgate service; also invoiced as: Liftgate.",
          "LPC Late payment charge; also invoiced as: Late fee.",
          ("h", "Schedule 1 Authorised contacts"),
          f"Rates: {BERTIL[0]}, Revenue Manager <{BERTIL[1]}>, ASC-US",
          f"Waivers; Payment terms: {LENNART[0]}, Credit Manager <{LENNART[1]}>, ASC-US",
          f"Billing disputes; Notices: {CORDELIA[0]}, Key Account Manager <{CORDELIA[1]}>, ASC-US",
          f"Treasury: {FENNA[0]}, Treasury Manager <{FENNA[1]}>, ASC-US",
          f"Notices: {ESME[0]}, Logistics Lead <{ESME[1]}>, QNO-US"]
    return pdf([p1, p2, p3, p4])


def term_extension(no: int, signed_on: str, effective: str, new_end: str) -> bytes:
    return pdf([[("h", f"Amendment No. {no} to Cargo Transport Agreement {CID}"),
                 f"{CARRIER} and {CUSTOMER} agree this amendment, effective {ordinal(effective)}.",
                 f"1. Clause 1.2 is replaced: the initial term expires on {ordinal(new_end)}.",
                 "2. All other terms are unchanged.",
                 f"Signed for {CARRIER} by Cordelia Nash, Key Account Manager, on {ordinal(signed_on)}.",
                 f"Signed for {CUSTOMER} by Esme Vantongeren, Logistics Lead, on {ordinal(signed_on)}."]])


# ---- billed rows -----------------------------------------------------------------------------------------------------
def airfreight(awb, pickup, lane, kg, rate, fuel=None):
    amt = line(rate, kg)
    rows = [{"desc": "Airfreight", "awb": awb, "od": lane, "pickup": pickup, "wt": f"{D(kg):.1f} kgs",
             "rate": rate, "amount": amt}]
    if fuel:
        rows.append({"desc": f"Fuel surcharge {fuel}% of {amt:,.2f}", "awb": awb, "od": "", "pickup": "", "wt": "",
                     "rate": f"{fuel}%", "amount": pct_of(fuel, amt)})
    return rows


def service(awb, desc, fee):
    return {"desc": desc, "awb": awb, "od": "", "pickup": "", "wt": "1 delivery", "rate": fee, "amount": D(fee)}


def late_charge(inv, principal, months: int, amount, days_late: int):
    return {"desc": f"Late payment charge - inv. {inv} (paid {days_late} days late): {months} x {LATE_PCT}% on "
                    f"{D(principal):,.2f}", "awb": "", "od": "", "pickup": "", "wt": f"{months} month",
            "rate": f"{LATE_PCT}%", "amount": r2(amount)}


def invoice(no: str, inv_date: str, due: str, rows: list[dict], scan: bool = False) -> tuple[bytes, D]:
    total = sum((r["amount"] for r in rows), D("0.00"))
    cols = [(48, "Description"), (238, "AWB"), (300, "Origin-Dest"), (366, "Pickup"), (420, "Weight"),
            (470, "Rate"), (514, "Amount")]
    body = [[(48, r["desc"]), (238, r["awb"]), (300, r["od"]), (366, r["pickup"]), (420, r["wt"]),
             (470, r["rate"]), (514, f"{r['amount']:,.2f}")] for r in rows]
    page = [("h", "ALDOUS STRATFORD CARGO CO."), "Accounts Receivable, 88 Bayshore Freight Way, Oakland CA",
            ("h", "Commercial Invoice"),
            f"Invoice #: {no}", f"Date of issue: {inv_date}", f"Payment due: {due}", f"Agreement: {CID}",
            f"Customer: {CUSTOMER}", "All amounts in USD", cols] + body + [
            ("gap",), f"Subtotal USD {total:,.2f}", "Tax USD 0.00", f"Total due USD {total:,.2f}",
            "Disputes: Key Account Manager per Schedule 1."]
    return pdf([page], scan=scan, wrap=110), total


def tracking(events: list[tuple[str, str, str]]) -> bytes:
    rows = [["AWB", "Status", "Status date", "Station"]]
    rows += [[awb, "PICKED_UP", p, st] for awb, p, st in events]
    return xlsx([("Tracking", rows)])


def ledger(rows: list[list]) -> bytes:
    """rows: [invoice_ref, total, paid_yes_no, payment_date]"""
    return xlsx([("AP", [["Invoice Ref", "Invoice Total", "Paid?", "Payment Date"]] + rows)], money_cols={1})


def start(name: str) -> Mailbox:
    m = Mailbox(name)
    m.mail("batch_01", "2043-01-27", ESME, HUGO, f"Fully signed: {CID}",
           f"""Hugo - attaching the fully signed Aldous Stratford agreement ({CID}), effective 1st February 2043.

           Esme""", [(f"{CID}-signed.pdf", agreement())])
    return m


def send_invoice(m: Mailbox, batch: str, when: str, no: str, due: str, rows, scan=False) -> tuple[str, D]:
    data, total = invoice(no, when, due, rows, scan)
    doc = m.mail(batch, when, BILLING, HUGO, f"Invoice {no} from Aldous Stratford",
                 f"""Hi Hugo,

                 Invoice {no} is attached.

                 Aldous Stratford Billing""", [(f"{no}.pdf", data)])
    return f"{doc}#{no}.pdf", total


def send_tracking(m: Mailbox, batch: str, when: str, events):
    return m.mail(batch, when, OPS, ESME, f"Tracking update {when}",
                  "Esme,\n\nTracking events attached.\n\nAldous Stratford Tracking",
                  [(f"tracking-{when}.xlsx", tracking(events))])


def send_ledger(m: Mailbox, batch: str, when: str, rows):
    return m.mail(batch, when, HUGO, ESME, f"AP ledger {when}", "Esme,\n\nAP ledger attached.\n\nHugo",
                  [(f"ap-ledger-{when}.xlsx", ledger(rows))])
