"""World 1 (Fenwick Ridge / Cobalt Harbor) cases. Amounts come from oracle.py on the printed contract terms."""
from __future__ import annotations

from oracle import finding, line, pct_of
from spec import case, control, ikey, item, report
import world_fenwick as W

DEV = "dev"


@case("w1_d01_weight_break_upper_edge", "fenwick", DEV, ["A", "H"])
def d01():
    m = W.start("w1_d01_weight_break_upper_edge")
    # 100.0 kg sits in "100 to 499.9 kg" (3.85) but is billed at the 0-99.9 rate; 99.9 kg at 4.40 is right.
    a, _ = W.send_invoice(m, "batch_01", "2043-03-20", "FRA-0043-1021", "2043-04-19",
                          W.linehaul("A1", "FR7730012", "2043-03-09", "ORD5-MIA2", "100.0", "4.40", W.FAF["2043-03"]))
    b, _ = W.send_invoice(m, "batch_01", "2043-03-21", "FRA-0043-1022", "2043-04-20",
                          W.linehaul("A1", "FR7730015", "2043-03-10", "ORD5-MIA2", "99.9", "4.40", W.FAF["2043-03"])
                          + W.linehaul("A2", "FR7730016", "2043-03-11", "ORD5-MIA2", "500.0", "3.30", W.FAF["2043-03"]))
    W.send_tracking(m, "batch_01", "2043-03-24", [("FR7730012", "2043-03-09", "ORD5"), ("FR7730015", "2043-03-10", "ORD5"),
                                                  ("FR7730016", "2043-03-11", "ORD5")])
    billed = [line("4.40", "100.0"), pct_of("14.60", line("4.40", "100.0"))]
    correct = [line("3.85", "100.0"), pct_of("14.60", line("3.85", "100.0"))]
    amt = finding(billed, correct)
    return m, {"why": "Exhibit A: 100.0 kg is in the 100 to 499.9 kg break (3.85), 99.9 kg in 0 to 99.9 (4.40), 500.0 "
                      "kg in 500 and above (3.30); FAF March 14.60% on linehaul.",
               "reports": [report("2043-03-31", [
                   item(ikey("FRA-0043-1021", "overcharge"), "finding",
                        f"(440.00 + 64.24) - (385.00 + 56.21) = {amt}; pickup from the tracking export",
                        "draft:dispute", "execute:dispute", amount=amt)],
                   [control(ikey("FRA-0043-1022", "overcharge"), "99.9 kg at 4.40 and 500.0 kg at 3.30 are the "
                            "contract breaks: the edge weights are billed right")])]}


@case("w1_d02_minimum_and_fees_clean", "fenwick", DEV, ["A"])
def d02():
    m = W.start("w1_d02_minimum_and_fees_clean")
    faf = W.FAF["2043-04"]
    W.send_invoice(m, "batch_01", "2043-04-16", "FRA-0043-1104", "2043-05-16",
                   W.minimum_linehaul("B7", "FR7731101", "2043-04-08", "PHX1-SLC3", "20.0", faf)
                   + [W.fee("FR7731101", "Screening surcharge", "20.0 kg", "0.15", line("0.15", "20.0")),
                      W.fee("FR7731101", "Pickup fee", "1 pickup", "45.00")])
    W.send_invoice(m, "batch_01", "2043-04-17", "FRA-0043-1105", "2043-05-17",
                   W.linehaul("B8", "FR7731102", "2043-04-09", "PHX1-SLC3", "650.0", "2.95", faf)
                   + [W.fee("FR7731102", "Screening surcharge", "650.0 kg", "0.15", line("0.15", "650.0"))])
    W.send_tracking(m, "batch_01", "2043-04-20", [("FR7731101", "2043-04-08", "PHX1"), ("FR7731102", "2043-04-09", "PHX1")])
    return m, {"why": "20.0 kg x 3.95 = 79.00 is below the USD 95.00 minimum, so 95.00 linehaul and FAF 14.80% of "
                      "95.00 = 14.06 are right; screening 0.15/kg and the 45.00 pickup fee match Exhibit C; 650.0 kg "
                      "at the 500 kg and above break 2.95 = 1,917.50, FAF 283.79.",
               "reports": [report("2043-04-30", [], [
                   control(ikey("FRA-0043-1104", "overcharge"), "minimum linehaul is not an overcharge of 20 kg x 3.95"),
                   control(ikey("FRA-0043-1105", "overcharge"), "heaviest break billed at its own rate")])]}


@case("w1_d03_fuel_on_fees", "fenwick", DEV, ["A"])
def d03():
    m = W.start("w1_d03_fuel_on_fees")
    lh = line("3.85", "240.0")                 # 924.00
    ssc = line("0.15", "240.0")                # 36.00
    wrong_faf = pct_of("14.30", lh + ssc)      # FAF billed on linehaul + screening
    rows = [{"ref": "C1", "shp": "FR7732040", "pickup": "2043-02-11", "svc": "Linehaul", "lane": "ORD5-MIA2",
             "qty": "240.0 kg", "rate": "3.85", "amount": lh},
            W.fee("FR7732040", "Screening surcharge", "240.0 kg", "0.15", ssc),
            {"ref": "", "shp": "FR7732040", "pickup": "", "svc": f"Fuel adjustment 14.30% of {lh + ssc:,.2f}",
             "lane": "", "qty": "", "rate": "14.30%", "amount": wrong_faf}]
    rows += W.linehaul("C2", "FR7732041", "2043-02-12", "PHX1-SLC3", "75.0", "3.95", "14.30")
    W.send_invoice(m, "batch_01", "2043-02-18", "FRA-0043-0877", "2043-03-20", rows)
    W.send_tracking(m, "batch_01", "2043-02-20", [("FR7732040", "2043-02-11", "ORD5"), ("FR7732041", "2043-02-12", "PHX1")])
    amt = finding([wrong_faf], [pct_of("14.30", lh)])
    return m, {"why": "Clause 2.4 applies FAF to linehaul only; the carrier applied 14.30% to linehaul plus screening.",
               "reports": [report("2043-02-28", [
                   item(ikey("FRA-0043-0877", "overcharge"), "finding",
                        f"14.30% of 960.00 = 137.28 billed, 14.30% of 924.00 = 132.13 owed: {amt}",
                        "draft:dispute", "execute:dispute", amount=amt)])]}


@case("w1_d04_backdated_amendment_after_invoice", "fenwick", DEV, ["B", "J"])
def d04():
    m = W.start("w1_d04_backdated_amendment_after_invoice")
    faf = W.FAF["2043-05"]
    W.send_invoice(m, "batch_01", "2043-05-15", "FRA-0043-1290", "2043-06-14",
                   W.linehaul("D1", "FR7733300", "2043-05-10", "PHX1-SLC3", "300.0", "3.45", faf))
    W.send_tracking(m, "batch_01", "2043-05-18", [("FR7733300", "2043-05-10", "PHX1")])
    amd = m.mail("batch_02", "2043-06-03", W.YUSRA, W.RAFE, f"Amendment No. 1 to {W.CID} - executed",
                 """Rafe,

                 Amendment No. 1 is now signed by both sides (attached). It reprices PHX1-SLC3 from May 1, 2043.

                 Yusra Talbot
                 Key Account Manager, Fenwick Ridge""",
                 [(f"Amendment-1-{W.CID}.pdf", W.amendment(1, "2043-06-02", "2043-05-01", "PHX1-SLC3",
                                                            "100 to 499.9 kg", "3.20"))])
    billed = [line("3.45", "300.0"), pct_of(faf, line("3.45", "300.0"))]
    correct = [line("3.20", "300.0"), pct_of(faf, line("3.20", "300.0"))]
    amt = finding(billed, correct)
    return m, {"why": "Billed at the Exhibit A rate, which was right until signed Amendment No. 1 arrived in batch_02 "
                      "repricing the lane from 2043-05-01, before the 2043-05-10 pickup.",
               "reports": [
                   report("2043-05-29", [], [control(ikey("FRA-0043-1290", "overcharge"),
                                                     "before the amendment arrives the Exhibit A rate 3.45 governs")],
                          after="batch_01"),
                   report("2043-06-15", [
                       item(ikey("FRA-0043-1290", "overcharge"), "finding",
                            f"(1,035.00 + 155.25) - (960.00 + 144.00) = {amt}; key exists only because of the "
                            "backdated amendment, so retro: true and no supersedes",
                            "draft:dispute", "execute:dispute", amount=amt, retro=True,
                            evidence_docs=[f"{amd}#Amendment-1-{W.CID}.pdf"])])]}


@case("w1_d05_rate_notice_authority", "fenwick", DEV, ["B", "I"])
def d05():
    m = W.start("w1_d05_rate_notice_authority")
    m.mail("batch_01", "2043-05-20", W.GRIFFIN, W.RAFE, "ORD5-MIA2 pricing update",
           """Hi Rafe,

           Quick note: effective June 1, 2043 the ORD5-MIA2 100 to 499.9 kg rate moves to USD 4.05 per kg.

           Cheers,
           Griffin Vale
           Regional Sales, Fenwick Ridge""")
    m.mail("batch_01", "2043-05-21", W.DELPHINE, W.RAFE, f"Rate notice under clause 6.2 of {W.CID}",
           """Dear Cobalt Harbor team,

           Under clause 6.2: effective June 1, 2043 the PHX1-SLC3 rate for the 0 to 99.9 kg break is USD 4.15 per kg.

           Delphine Arkwright
           Pricing Director, Fenwick Ridge""")
    faf = W.FAF["2043-06"]
    W.send_invoice(m, "batch_01", "2043-06-12", "FRA-0043-1388", "2043-07-12",
                   W.linehaul("E1", "FR7734410", "2043-06-04", "ORD5-MIA2", "180.0", "4.05", faf))
    W.send_invoice(m, "batch_01", "2043-06-13", "FRA-0043-1389", "2043-07-13",
                   W.linehaul("E1", "FR7734420", "2043-06-05", "PHX1-SLC3", "60.0", "4.15", faf))
    W.send_tracking(m, "batch_01", "2043-06-16", [("FR7734410", "2043-06-04", "ORD5"), ("FR7734420", "2043-06-05", "PHX1")])
    amt = finding([line("4.05", "180.0"), pct_of(faf, line("4.05", "180.0"))],
                  [line("3.85", "180.0"), pct_of(faf, line("3.85", "180.0"))])
    return m, {"why": "Griffin Vale is not in Schedule 1, so his rate has no effect; Delphine Arkwright is the rates "
                      "contact and her notice governs PHX1-SLC3 from 2043-06-01.",
               "reports": [report("2043-06-20", [
                   item(ikey("FRA-0043-1388", "overcharge"), "finding",
                        f"(729.00 + 110.08) - (693.00 + 104.64) = {amt}", "draft:dispute", "execute:dispute",
                        amount=amt)],
                   [control(ikey("FRA-0043-1389", "overcharge"), "billed at the authorised rate notice: 60.0 x 4.15")])]}


@case("w1_d06_same_shipment_on_two_invoices", "fenwick", DEV, ["C"])
def d06():
    m = W.start("w1_d06_same_shipment_on_two_invoices")
    faf = W.FAF["2043-07"]
    s2 = W.linehaul("F2", "FR7735002", "2043-07-02", "PHX1-SLC3", "140.0", "3.45", faf)
    W.send_invoice(m, "batch_01", "2043-07-08", "FRA-0043-1452", "2043-08-07",
                   W.linehaul("F1", "FR7735001", "2043-07-01", "ORD5-MIA2", "140.0", "3.85", faf) + s2
                   + W.linehaul("F3", "FR7735003", "2043-07-03", "ORD5-MIA2", "140.0", "3.85", faf))
    W.send_tracking(m, "batch_01", "2043-07-10", [("FR7735001", "2043-07-01", "ORD5"), ("FR7735002", "2043-07-02", "PHX1"),
                                                  ("FR7735003", "2043-07-03", "ORD5")])
    faf8 = W.FAF["2043-07"]
    q = W.linehaul("G1", "FR7735009", "2043-07-29", "ORD5-MIA2", "88.0", "4.40", faf8) + \
        [dict(r, ref="G2" if r["ref"] else "") for r in s2]
    W.send_invoice(m, "batch_02", "2043-08-05", "FRA-0043-1530", "2043-09-04", q)
    W.send_tracking(m, "batch_02", "2043-08-06", [("FR7735009", "2043-07-29", "ORD5")])
    amt = sum(r["amount"] for r in s2)
    return m, {"why": "FR7735002's linehaul and FAF appear on FRA-0043-1452 and again on the later FRA-0043-1530; "
                      "three shipments of identical weight on one invoice are not duplicates of each other.",
               "reports": [report("2043-08-12", [
                   item(ikey("FRA-0043-1530", "duplicate"), "finding",
                        f"duplicated lines on the later invoice: 483.00 + 73.66 = {amt}", "draft:dispute",
                        "execute:dispute", amount=amt)],
                   [control(ikey("FRA-0043-1452", "duplicate"), "the earlier invoice is never the duplicate; its "
                            "three equal-weight shipments are different AWBs")])]}
