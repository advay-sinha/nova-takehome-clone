"""World 3 (Kittering / Mallowfield, monthly statements) cases. Cashback arithmetic from oracle.py."""
from __future__ import annotations

from oracle import D, line, margin_step_down, pct_of, rebate
from spec import case, control, item, report
import world_kittering as W

DEV = "dev"
FUEL = "20.0"


def ship(awb, pickup, kg, lane="MAN2-ATL5"):
    rate = {"MAN2-ATL5": W.RATES["MAN2-ATL5"], "EDI1-BOS3": W.RATES["EDI1-BOS3"]}[lane]
    kg_d = D(kg)
    r = rate[0][1] if kg_d < 300 else rate[1][1] if kg_d < 1000 else rate[2][1]
    return W.freight(awb, pickup, lane, kg, r, FUEL)


def qs(rows) -> D:
    """Qualifying spend of statement rows: air freight, fuel and screening (Article 5.2)."""
    return sum((r["amount"] for r in rows if r["svc"].startswith(("Air freight", "Fuel surcharge", "Security screening"))),
               D("0.00"))


def cb_key(period, credit_type):
    return {"contract_id": W.CID, "period": period, "credit_type": credit_type}


@case("w3_d13_quarterly_rebate_due_unpaid", "kittering", DEV, ["F", "H"])
def d13():
    m = W.start("w3_d13_quarterly_rebate_due_unpaid")
    apr = ship("MX4471201", "2043-04-07", "1500.0") + ship("MX4471202", "2043-04-14", "1500.0")
    may = ship("MX4471203", "2043-05-06", "2000.0") + ship("MX4471204", "2043-05-12", "600.0", "EDI1-BOS3")
    jun = ship("MX4471205", "2043-06-09", "1200.0")
    W.send_statement(m, "batch_01", "2043-04-30", "KOA-ST-4304", "2043-05-30", apr)
    W.send_statement(m, "batch_01", "2043-05-31", "KOA-ST-4305", "2043-06-30", may)
    W.send_statement(m, "batch_01", "2043-06-30", "KOA-ST-4306", "2043-07-30", jun)
    W.send_tracking(m, "batch_01", "2043-07-01", [("MX4471201", "2043-04-07", "MAN"), ("MX4471202", "2043-04-14", "MAN"),
                                                  ("MX4471203", "2043-05-06", "MAN"), ("MX4471204", "2043-05-12", "EDI"),
                                                  ("MX4471205", "2043-06-09", "MAN")])
    spend = qs(apr) + qs(may) + qs(jun)
    owed = rebate(spend, W.TIERS)
    return m, {"why": "Q2 2043 Qualifying Spend crosses the USD 30,000.00 tier, so 2% applies to all of it; the credit "
                      "was due by 2043-07-30 and no credit memo arrived.",
               "reports": [report("2043-08-12", [
                   item(cb_key("2043-Q2", "rebate"), "finding", f"QS {spend} x 2% = {owed}", "draft:claim_credit",
                        "execute:claim_credit", amount=owed)])]}


@case("w3_d14_rebate_tier_boundary_part_credited", "kittering", DEV, ["F", "C"])
def d14():
    m = W.start("w3_d14_rebate_tier_boundary_part_credited")
    stmts = [("2043-07-31", "KOA-ST-4307", "2043-08-30", [("MX4472301", "2043-07-08"), ("MX4472302", "2043-07-22")]),
             ("2043-08-31", "KOA-ST-4308", "2043-09-30", [("MX4472303", "2043-08-05"), ("MX4472304", "2043-08-19")]),
             ("2043-09-30", "KOA-ST-4309", "2043-10-30", [("MX4472305", "2043-09-02"), ("MX4472306", "2043-09-16")])]
    spend, events = D("0.00"), []
    for when, no, due, ships in stmts:
        rows = [r for awb, p in ships for r in ship(awb, p, "2000.0")]
        spend += qs(rows)
        events += [(awb, p, "MAN") for awb, p in ships]
        W.send_statement(m, "batch_01", when, no, due, rows)
    W.send_tracking(m, "batch_01", "2043-10-01", events)
    memo = m.mail("batch_01", "2043-10-20", W.BILLING, W.JUDE, "Credit memo KOA-CN-0431 - Q3 2043 rebate",
                  "Hello Jude,\n\nOur credit memo for the Q3 2043 rebate is attached.\n\nKittering Receivables",
                  [("KOA-CN-0431.pdf", W.credit_memo("KOA-CN-0431", "2043-10-20", "Quarterly volume rebate Q3 2043",
                                                     "1200.00"))])
    earned = rebate(spend, W.TIERS)
    owed = earned - D("1200.00")
    assert spend == D("60000.00")
    return m, {"why": "Q3 2043 Qualifying Spend is exactly USD 60,000.00, which reaches the 4% tier ('or more'); the "
                      "carrier credited only 2% (1,200.00).",
               "reports": [report("2043-11-05", [
                   item(cb_key("2043-Q3", "rebate"), "finding", f"60,000.00 x 4% = {earned} less credit memo 1,200.00 "
                        f"= {owed}", "draft:claim_credit", "execute:claim_credit", amount=owed,
                        evidence_docs=[f"{memo}#KOA-CN-0431.pdf"])])]}


@case("w3_d15_margin_step_down", "kittering", DEV, ["F"])
def d15():
    m = W.start("w3_d15_margin_step_down")
    W.send_statement(m, "batch_01", "2043-04-30", "KOA-ST-5304", "2043-05-30",
                     W.consolidation("CN2043-0411", "2043-04-11", "18000.00", W.MARGIN))
    W.send_statement(m, "batch_01", "2043-05-31", "KOA-ST-5305", "2043-06-30",
                     W.consolidation("CN2043-0516", "2043-05-16", "25000.00", W.MARGIN))
    W.send_statement(m, "batch_01", "2043-06-30", "KOA-ST-5306", "2043-07-30",
                     W.consolidation("CN2043-0620", "2043-06-20", "12000.00", W.MARGIN))
    owed = margin_step_down([("12000.00", pct_of(W.MARGIN, "12000.00"))], W.STEPPED)
    return m, {"why": "Carrier cost in Contract Year 1 reaches 43,000.00 on the May statement, exceeding 40,000.00; the "
                      "June statement should carry a 4.0% margin, not 6.0%.",
               "reports": [report("2043-07-10", [
                   item(cb_key("2043-Q2", "margin_step_down"), "finding",
                        f"June: 720.00 billed - 4.0% x 12,000.00 = 480.00: {owed}", "draft:claim_credit",
                        "execute:claim_credit", amount=owed)])]}


@case("w3_d16_annual_improvement_credit_not_yet_due", "kittering", DEV, ["F", "G"])
def d16():
    m = W.start("w3_d16_annual_improvement_credit_not_yet_due")
    jun = [r for i in range(4) for r in ship(f"MX447330{i}", f"2043-06-0{i + 2}", "1000.0")]
    feb = [r for i in range(5) for r in ship(f"MX447340{i}", f"2044-02-0{i + 2}", "1000.0")]
    W.send_statement(m, "batch_01", "2043-06-30", "KOA-ST-4406", "2043-07-30", jun)
    W.send_statement(m, "batch_02", "2044-02-29", "KOA-ST-4502", "2044-03-30", feb)
    W.send_tracking(m, "batch_02", "2044-03-01", [(f"MX447330{i}", f"2043-06-0{i + 2}", "MAN") for i in range(4)]
                    + [(f"MX447340{i}", f"2044-02-0{i + 2}", "MAN") for i in range(5)])
    spend = qs(jun) + qs(feb)
    credit = pct_of(W.IMPROVEMENT, spend)
    return m, {"why": "Contract Year 1 (1 April 2043 - 31 March 2044) Qualifying Spend is 45,000.00; the 1.5% "
                      "improvement credit falls due 45 days after the anniversary (2044-05-16), so on 2044-04-20 it is "
                      "earned but not yet due. Each quarter stays below the 30,000.00 rebate tier.",
               "reports": [report("2044-04-20", [
                   item(cb_key("CY1", "promised_credit"), "finding", f"45,000.00 x 1.5% = {credit}",
                        "internal:track_credit", "internal:track_credit", amount=credit)],
                   [control(cb_key("2043-Q2", "rebate"), "20,000.00 is below the first tier"),
                    control(cb_key("2044-Q1", "rebate"), "25,000.00 is below the first tier")])]}


@case("w3_d17_reordered_statement_columns_clean", "kittering", DEV, ["H", "A"])
def d17():
    m = W.start("w3_d17_reordered_statement_columns_clean")
    rows = ship("MX4474101", "2043-05-03", "1000.0") + ship("MX4474102", "2043-05-04", "999.9") + \
        ship("MX4474103", "2043-05-05", "299.9", "EDI1-BOS3")
    W.send_statement(m, "batch_01", "2043-05-31", "KOA-ST-4605", "2043-06-30", rows,
                     order=("amount", "rate", "qty", "lane", "date", "svc", "shp"),
                     names={"amount": "Line value", "rate": "Price", "qty": "Chg wt", "lane": "Route",
                            "date": "Collected", "svc": "Description", "shp": "AWB/Ref"})
    W.send_tracking(m, "batch_01", "2043-06-01", [("MX4474101", "2043-05-03", "MAN"), ("MX4474102", "2043-05-04", "MAN"),
                                                  ("MX4474103", "2043-05-05", "EDI")])
    return m, {"why": "Every line matches Schedule A at its band edge (1000.0 kg at 4.00, 999.9 kg at 4.40, 299.9 kg at "
                      "5.10), fuel 20.0% on freight only and screening 0.20/kg; the statement's columns are renamed "
                      "and in reverse order.",
               "reports": [report("2043-06-05", [], [control({"invoice_id": "KOA-ST-4605", "class": "overcharge"},
                                                             "band edges billed correctly")])]}


@case("w3_d18_duplicate_net_of_credit_memos", "kittering", DEV, ["C"])
def d18():
    m = W.start("w3_d18_duplicate_net_of_credit_memos")
    s1 = ship("MX4475001", "2043-04-10", "400.0")
    s2 = ship("MX4475002", "2043-04-12", "350.0", "EDI1-BOS3")
    s3 = ship("MX4475003", "2043-05-08", "800.0")
    W.send_statement(m, "batch_01", "2043-04-30", "KOA-ST-4704", "2043-05-30", s1 + s2)
    cn1 = sum(r["amount"] for r in s1)
    m.mail("batch_01", "2043-05-10", W.BILLING, W.JUDE, "Credit memo KOA-CN-0510",
           "Hello Jude,\n\nCredit memo attached: shipment MX4475001 was cancelled and is credited in full.\n\n"
           "Kittering Receivables",
           [("KOA-CN-0510.pdf", W.credit_memo("KOA-CN-0510", "2043-05-10", "Cancellation in full of AWB MX4475001",
                                              cn1, "statement KOA-ST-4704"))])
    W.send_statement(m, "batch_01", "2043-05-31", "KOA-ST-4705", "2043-06-30", s1 + s2 + s3)
    fuel_s2 = s2[1]["amount"]
    m.mail("batch_01", "2043-06-08", W.BILLING, W.JUDE, "Credit memo KOA-CN-0608",
           "Hello Jude,\n\nPartial credit for AWB MX4475002 on statement KOA-ST-4705 attached.\n\n"
           "Kittering Receivables",
           [("KOA-CN-0608.pdf", W.credit_memo("KOA-CN-0608", "2043-06-08", "Partial credit of fuel surcharge, AWB "
                                              "MX4475002", fuel_s2, "statement KOA-ST-4705"))])
    W.send_tracking(m, "batch_01", "2043-06-01", [("MX4475001", "2043-04-10", "MAN"), ("MX4475002", "2043-04-12", "EDI"),
                                                  ("MX4475003", "2043-05-08", "MAN")])
    overlap = sum(r["amount"] for r in s2)
    amt = overlap - fuel_s2
    return m, {"why": "MX4475001 was credited in full on the April statement and billed again in May: fine. "
                      "MX4475002 is on both statements; the later one is the duplicate, net of the partial credit memo "
                      "for its fuel line. MX4475003 is new.",
               "reports": [report("2043-06-10", [
                   item({"invoice_id": "KOA-ST-4705", "class": "duplicate"}, "finding",
                        f"MX4475002 lines on the later statement {overlap} less credit {fuel_s2} = {amt}",
                        "draft:dispute", "execute:dispute", amount=amt)],
                   [control({"invoice_id": "KOA-ST-4704", "class": "duplicate"}, "the earlier statement is never the "
                            "duplicate")])]}
