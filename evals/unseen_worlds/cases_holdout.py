"""Final holdout cases: written after the reader and rules were frozen (harness hash recorded in SUITE.md) and run
once. Three per world, on scenarios the development cases do not repeat. Amounts from oracle.py."""
from __future__ import annotations

from datetime import date

from oracle import D, finding, inr_to_usd, late_fee_months, line, margin_step_down, pct_of, rebate
from spec import case, control, ikey, item, report
import world_aldous as A
import world_fenwick as F
import world_kittering as K
import world_sarvani as S

HOLD = "holdout"


# ---- world 1 ---------------------------------------------------------------------------------------------------------
@case("w1_h01_accessorials_above_exhibit_c", "fenwick", HOLD, ["A"])
def h01():
    m = F.start("w1_h01_accessorials_above_exhibit_c")
    faf = F.FAF["2043-09"]
    rows = F.linehaul("H1", "FR7736100", "2043-09-08", "ORD5-MIA2", "150.0", "3.85", faf) + \
        [F.fee("FR7736100", "Screening surcharge", "150.0 kg", "0.18", line("0.18", "150.0")),
         F.fee("FR7736100", "Pickup fee", "1 pickup", "55.00")]
    F.send_invoice(m, "batch_01", "2043-09-15", "FRA-0043-1610", "2043-10-15", rows)
    F.send_tracking(m, "batch_01", "2043-09-17", [("FR7736100", "2043-09-08", "ORD5")])
    amt = finding([line("0.18", "150.0"), D("55.00")], [line(F.SSC_PER_KG, "150.0"), D(F.PICKUP_FEE)])
    return m, {"why": "Exhibit C: screening USD 0.15 per kg and pickup USD 45.00; billed 0.18 per kg and 55.00. "
                      "Linehaul and FAF are right.",
               "reports": [report("2043-09-25", [
                   item(ikey("FRA-0043-1610", "overcharge"), "finding", f"(27.00 - 22.50) + (55.00 - 45.00) = {amt}",
                        "draft:dispute", "execute:dispute", amount=amt)])]}


@case("w1_h02_amendment_effective_date_edge", "fenwick", HOLD, ["A", "B"])
def h02():
    m = F.start("w1_h02_amendment_effective_date_edge")
    m.mail("batch_01", "2043-07-21", F.YUSRA, F.RAFE, f"Amendment No. 2 to {F.CID} - signed",
           "Rafe,\n\nSigned Amendment No. 2 attached; it reprices ORD5-MIA2 from August 1, 2043.\n\nYusra Talbot",
           [(f"Amendment-2-{F.CID}.pdf", F.amendment(2, "2043-07-20", "2043-08-01", "ORD5-MIA2", "100 to 499.9 kg",
                                                      "3.60"))])
    F.send_invoice(m, "batch_01", "2043-08-05", "FRA-0043-1489", "2043-09-04",
                   F.linehaul("J1", "FR7737001", "2043-07-31", "ORD5-MIA2", "200.0", "3.85", F.FAF["2043-07"]))
    F.send_invoice(m, "batch_01", "2043-08-06", "FRA-0043-1490", "2043-09-05",
                   F.linehaul("J2", "FR7737002", "2043-08-01", "ORD5-MIA2", "200.0", "3.85", F.FAF["2043-08"]))
    F.send_tracking(m, "batch_01", "2043-08-07", [("FR7737001", "2043-07-31", "ORD5"), ("FR7737002", "2043-08-01", "ORD5")])
    faf = F.FAF["2043-08"]
    amt = finding([line("3.85", "200.0"), pct_of(faf, line("3.85", "200.0"))],
                  [line("3.60", "200.0"), pct_of(faf, line("3.60", "200.0"))])
    return m, {"why": "Signed Amendment No. 2 sets 3.60 for pickups from 2043-08-01. The 2043-07-31 pickup keeps "
                      "Exhibit A 3.85; the 2043-08-01 pickup is on the effective date and takes 3.60.",
               "reports": [report("2043-08-12", [
                   item(ikey("FRA-0043-1490", "overcharge"), "finding", f"(770.00 + 118.58) - (720.00 + 110.88) = {amt}",
                        "draft:dispute", "execute:dispute", amount=amt)],
                   [control(ikey("FRA-0043-1489", "overcharge"), "the day before the amendment takes effect")])]}


@case("w1_h03_rate_accepted_feedback_scope", "fenwick", HOLD, ["J", "B"])
def h03():
    m = F.start("w1_h03_rate_accepted_feedback_scope")
    m.mail("batch_01", "2043-08-25", F.GRIFFIN, F.RAFE, "PHX1-SLC3 small shipments",
           """Rafe,

           From September 1, 2043 the PHX1-SLC3 0 to 99.9 kg rate moves to USD 4.25 per kg.

           Griffin Vale, Regional Sales""")
    f9, f10 = F.FAF["2043-09"], F.FAF["2043-10"]
    F.send_invoice(m, "batch_01", "2043-09-12", "FRA-0043-1701", "2043-10-12",
                   F.linehaul("K1", "FR7738001", "2043-09-05", "PHX1-SLC3", "70.0", "4.25", f9))
    F.send_tracking(m, "batch_01", "2043-09-14", [("FR7738001", "2043-09-05", "PHX1")])
    F.send_invoice(m, "batch_02", "2043-10-10", "FRA-0043-1755", "2043-11-09",
                   F.linehaul("K2", "FR7738002", "2043-10-03", "PHX1-SLC3", "80.0", "4.25", f10))
    F.send_invoice(m, "batch_02", "2043-10-11", "FRA-0043-1756", "2043-11-10",
                   F.linehaul("K3", "FR7738003", "2043-10-04", "PHX1-SLC3", "60.0", "4.40", f10))
    F.send_invoice(m, "batch_02", "2043-10-12", "FRA-0043-1757", "2043-11-11",
                   F.linehaul("K4", "FR7738004", "2043-10-05", "ORD5-MIA2", "150.0", "4.05", f10))
    F.send_tracking(m, "batch_02", "2043-10-13", [("FR7738002", "2043-10-03", "PHX1"), ("FR7738003", "2043-10-04", "PHX1"),
                                                  ("FR7738004", "2043-10-05", "ORD5")])
    a = finding([line("4.25", "70.0"), pct_of(f9, line("4.25", "70.0"))], [line("3.95", "70.0"), pct_of(f9, line("3.95", "70.0"))])
    c = finding([line("4.40", "60.0"), pct_of(f10, line("4.40", "60.0"))], [line("4.25", "60.0"), pct_of(f10, line("4.25", "60.0"))])
    d = finding([line("4.05", "150.0"), pct_of(f10, line("4.05", "150.0"))],
                [line("3.85", "150.0"), pct_of(f10, line("3.85", "150.0"))])
    feedback = {"schema_version": "1.0", "world": "UW1", "after_batch": "batch_01", "decided_at": "2043-09-22T14:00:00Z",
                "decided_by": {"name": "Rafe Ostrom", "role": "AP Supervisor", "entity": "CHT-US"},
                "items": [{"item_id": "uw1-fb-07", "decision": "close", "solicited": True,
                           "finding_key": {"invoice_id": "FRA-0043-1701", "class": "overcharge"},
                           "fact": {"type": "rate_accepted", "subject": {"contract_id": F.CID, "lane": "PHX1-SLC3"},
                                    "value": {"source": "rate notice", "sent_by": "Griffin Vale", "sent_on": "2043-08-25",
                                              "effective_from": "2043-09-01", "effective_to": "2043-12-31"},
                                    "evidence": "Fenwick confirmed the notice in writing"},
                           "scope": {"kind": "standing", "applies_to": {"contract_id": F.CID, "lane": "PHX1-SLC3"},
                                     "valid_from": "2043-09-01", "valid_to": "2043-12-31"}}]}
    return m, {"why": "Griffin Vale is not the rates contact, so FRA-0043-1701 is an overcharge until the AP "
                      "supervisor closes it and accepts his PHX1-SLC3 rate for September-December. After that 4.25 is "
                      "the PHX1-SLC3 rate: 4.25 billed is fine, 4.40 is measured against 4.25 (learned_at); ORD5-MIA2 "
                      "keeps Exhibit A.",
               "feedback": {"batch_01": feedback},
               "reports": [
                   report("2043-09-20", [item(ikey("FRA-0043-1701", "overcharge"), "finding", f"vs Exhibit A 3.95: {a}",
                                              "draft:dispute", "execute:dispute", amount=a)], after="batch_01"),
                   report("2043-10-20", [
                       item(ikey("FRA-0043-1756", "overcharge"), "finding", f"4.40 vs accepted 4.25: {c}",
                            "draft:dispute", "execute:dispute", amount=c, learned_at=True),
                       item(ikey("FRA-0043-1757", "overcharge"), "finding", f"other lane, Exhibit A 3.85: {d}",
                            "draft:dispute", "execute:dispute", amount=d)],
                       [control(ikey("FRA-0043-1701", "overcharge"), "closed by feedback"),
                        control(ikey("FRA-0043-1755", "overcharge"), "billed at the accepted rate")])]}


# ---- world 2 ---------------------------------------------------------------------------------------------------------
@case("w2_h04_inr_fees_and_slab_edges_clean", "sarvani", HOLD, ["A", "H"])
def h04():
    m = S.start("w2_h04_inr_fees_and_slab_edges_clean")
    fuel = S.FUEL["2043-05"]
    rows = S.freight("176-55021001", "2043-05-06", "BLR2-DEL1", "45.0", "182.50", fuel) + \
        [S.charge("176-55021001", "X-ray screening", "45.0 kg", "4.00", line("4.00", "45.0")),
         S.charge("176-55021001", "Documentation", "1 AWB", "350.00")] + \
        S.freight("176-55021002", "2043-05-07", "MAA3-BOM1", "44.9", "174.00", fuel)
    S.send_invoice(m, "batch_01", "2043-05-12", "SAL-INV-43-1001", "2043-06-02", rows)
    S.send_tracking(m, "batch_01", "2043-05-13", [("176-55021001", "2043-05-06", "BLR"), ("176-55021002", "2043-05-07", "MAA")])
    return m, {"why": "45.0 kg opens the 45 - 99.9 kg slab (182.50) and 44.9 kg closes the up to 44.9 kg slab "
                      "(174.00); X-ray 4.00/kg and documentation 350.00 match Annex D; fuel May 22.5% on freight.",
               "reports": [report("2043-05-15", [], [control(ikey("SAL-INV-43-1001", "overcharge"),
                                                             "slab edges and fees billed exactly")])]}


@case("w2_h05_backdated_inr_amendment", "sarvani", HOLD, ["B", "J"])
def h05():
    m = S.start("w2_h05_backdated_inr_amendment")
    fuel = S.FUEL["2043-06"]
    S.send_invoice(m, "batch_01", "2043-06-10", "SAL-INV-43-1105", "2043-07-01",
                   S.freight("176-55022001", "2043-06-05", "MAA3-BOM1", "120.0", "149.50", fuel))
    S.send_tracking(m, "batch_01", "2043-06-11", [("176-55022001", "2043-06-05", "MAA")])
    amd = m.mail("batch_02", "2043-07-05", S.NEHA, S.SAMIR, f"Amendment No. 3 - {S.CID} (signed)",
                 "Samir,\n\nSigned Amendment No. 3 attached, effective 01.06.2043.\n\nNeha Varghese",
                 [(f"Amendment-3-{S.CID}.pdf", S.amendment(3, "2043-07-04", "2043-06-01", "MAA3-BOM1", "100 kg +", "142.00"))])
    inr = finding([line("149.50", "120.0"), pct_of(fuel, line("149.50", "120.0"))],
                  [line("142.00", "120.0"), pct_of(fuel, line("142.00", "120.0"))])
    usd = inr_to_usd(inr, S.FX["2043-06"])
    return m, {"why": "Billed at Annex A Validity 1 (149.50), right until signed Amendment No. 3 arrives in batch_02 "
                      "repricing MAA3-BOM1 100 kg + to 142.00 from 01.06.2043, before the 05.06.2043 pickup.",
               "reports": [
                   report("2043-06-20", [], [control(ikey("SAL-INV-43-1105", "overcharge"), "before the amendment")],
                          after="batch_01"),
                   report("2043-07-08", [item(ikey("SAL-INV-43-1105", "overcharge"), "finding",
                                              f"INR {inr} / Annex F June 83.6110 = {usd}; retro, cites the amendment",
                                              "draft:dispute", "execute:dispute", amount=usd, retro=True,
                                              evidence_docs=[f"{amd}#Amendment-3-{S.CID}.pdf"])])]}


@case("w2_h06_monthly_waiver_inr", "sarvani", HOLD, ["D"])
def h06():
    m = S.start("w2_h06_monthly_waiver_inr")
    m.mail("batch_01", "2043-03-28", S.ARJUN, S.SAMIR, "Documentation charges - March",
           """Dear Samir,

           We waive the documentation charges on all consignments collected in March 2043.

           Arjun Mehrotra
           Credit Manager, Sarvani Air Logistics""")
    f3, f4 = S.FUEL["2043-03"], S.FUEL["2043-04"]
    S.send_invoice(m, "batch_01", "2043-03-30", "SAL-INV-43-0750", "2043-04-20",
                   S.freight("176-55023001", "2043-03-20", "BLR2-DEL1", "60.0", "182.50", f3)
                   + [S.charge("176-55023001", "Documentation", "1 AWB", "350.00")]
                   + S.freight("176-55023002", "2043-03-24", "MAA3-BOM1", "60.0", "161.75", f3)
                   + [S.charge("176-55023002", "Documentation", "1 AWB", "350.00")])
    S.send_invoice(m, "batch_01", "2043-04-12", "SAL-INV-43-0790", "2043-05-03",
                   S.freight("176-55023003", "2043-04-04", "BLR2-DEL1", "60.0", "182.50", f4)
                   + [S.charge("176-55023003", "Documentation", "1 AWB", "350.00")])
    S.send_tracking(m, "batch_01", "2043-04-13", [("176-55023001", "2043-03-20", "BLR"), ("176-55023002", "2043-03-24", "MAA"),
                                                  ("176-55023003", "2043-04-04", "BLR")])
    usd = inr_to_usd(D("700.00"), S.FX["2043-03"])
    return m, {"why": "The Schedule 1 waivers contact waived documentation for March 2043 collections: both March "
                      "documentation charges on SAL-INV-43-0750 are waived (INR 700.00, converted once); the April "
                      "consignment is outside the waiver.",
               "reports": [report("2043-04-18", [
                   item(ikey("SAL-INV-43-0750", "waived_but_billed"), "finding", f"INR 700.00 / 83.3333 = {usd}",
                        "draft:dispute", "execute:dispute", amount=usd)],
                   [control(ikey("SAL-INV-43-0790", "waived_but_billed"), "April is not the waived month")])]}


# ---- world 3 ---------------------------------------------------------------------------------------------------------
def k_ship(awb, pickup, kg):
    return K.freight(awb, pickup, "MAN2-ATL5", kg, "4.00" if D(kg) >= 1000 else "4.40", "20.0")


def k_qs(rows):
    return sum((r["amount"] for r in rows if r["svc"].startswith(("Air freight", "Fuel surcharge", "Security screening"))),
               D("0.00"))


@case("w3_h07_rebate_just_below_tier", "kittering", HOLD, ["F"])
def h07():
    m = K.start("w3_h07_rebate_just_below_tier")
    spend = D("0.00")
    for when, no, due, awb, p, kg in (("2043-07-31", "KOA-ST-4907", "2043-08-30", "MX4479101", "2043-07-09", "2000.0"),
                                      ("2043-08-31", "KOA-ST-4908", "2043-09-30", "MX4479102", "2043-08-12", "2000.0"),
                                      ("2043-09-30", "KOA-ST-4909", "2043-10-30", "MX4479103", "2043-09-10", "1998.0")):
        rows = k_ship(awb, p, kg)
        spend += k_qs(rows)
        K.send_statement(m, "batch_01", when, no, due, rows)
    K.send_tracking(m, "batch_01", "2043-10-01", [("MX4479101", "2043-07-09", "MAN"), ("MX4479102", "2043-08-12", "MAN"),
                                                  ("MX4479103", "2043-09-10", "MAN")])
    assert spend == D("29990.00") and rebate(spend, K.TIERS) == 0
    return m, {"why": "Q3 2043 Qualifying Spend is 29,990.00, ten dollars short of the 30,000.00 tier: no rebate.",
               "reports": [report("2043-11-10", [], [control({"contract_id": K.CID, "period": "2043-Q3",
                                                              "credit_type": "rebate"}, "below the first tier")])]}


@case("w3_h08_margin_threshold_reached_then_exceeded", "kittering", HOLD, ["F"])
def h08():
    m = K.start("w3_h08_margin_threshold_reached_then_exceeded")
    costs = [("2043-04-30", "KOA-ST-5404", "2043-05-30", "15000.00"), ("2043-05-31", "KOA-ST-5405", "2043-06-30", "25000.00"),
             ("2043-06-30", "KOA-ST-5406", "2043-07-30", "5000.00"), ("2043-07-31", "KOA-ST-5407", "2043-08-30", "10000.00"),
             ("2043-08-31", "KOA-ST-5408", "2043-09-30", "8000.00")]
    for i, (when, no, due, cost) in enumerate(costs):
        K.send_statement(m, "batch_01", when, no, due, K.consolidation(f"CN2043-08{i}", when[:8] + "15", cost, K.MARGIN))
    owed = margin_step_down([(c, pct_of(K.MARGIN, c)) for _, _, _, c in costs[3:]], K.STEPPED)
    return m, {"why": "Carrier cost reaches exactly 40,000.00 on the May statement, which does not exceed the threshold; "
                      "the June statement takes it to 45,000.00 and is the crossing statement (still 6.0%). July and "
                      "August should carry 4.0%: one Q3 2043 item; nothing for Q2.",
               "reports": [report("2043-10-05", [
                   item({"contract_id": K.CID, "period": "2043-Q3", "credit_type": "margin_step_down"}, "finding",
                        f"(600.00 - 400.00) + (480.00 - 320.00) = {owed}", "draft:claim_credit", "execute:claim_credit",
                        amount=owed)],
                   [control({"contract_id": K.CID, "period": "2043-Q2", "credit_type": "margin_step_down"},
                            "40,000.00 reached but not exceeded in Q2")])]}


@case("w3_h09_shipment_rebilled_on_next_statement", "kittering", HOLD, ["C"])
def h09():
    m = K.start("w3_h09_shipment_rebilled_on_next_statement")
    s1, s2 = k_ship("MX4479301", "2043-06-03", "500.0"), k_ship("MX4479302", "2043-06-04", "500.0")
    s3 = k_ship("MX4479303", "2043-07-08", "700.0")
    K.send_statement(m, "batch_01", "2043-06-30", "KOA-ST-4806", "2043-07-30", s1 + s2)
    K.send_statement(m, "batch_01", "2043-07-31", "KOA-ST-4807", "2043-08-30", s2 + s3)
    K.send_tracking(m, "batch_01", "2043-08-01", [("MX4479301", "2043-06-03", "MAN"), ("MX4479302", "2043-06-04", "MAN"),
                                                  ("MX4479303", "2043-07-08", "MAN")])
    amt = sum(r["amount"] for r in s2)
    return m, {"why": "MX4479302 is billed on the June statement and again on the July statement; the July statement "
                      "is the duplicate for its lines. Two equal shipments on the June statement are not duplicates.",
               "reports": [report("2043-08-05", [
                   item({"invoice_id": "KOA-ST-4807", "class": "duplicate"}, "finding", f"MX4479302 lines: {amt}",
                        "draft:dispute", "execute:dispute", amount=amt)],
                   [control({"invoice_id": "KOA-ST-4806", "class": "duplicate"}, "the earlier statement")])]}


# ---- world 4 ---------------------------------------------------------------------------------------------------------
@case("w4_h10_monthly_waiver_scope", "aldous", HOLD, ["D"])
def h10():
    m = A.start("w4_h10_monthly_waiver_scope")
    m.mail("batch_01", "2043-04-03", A.LENNART, A.HUGO, "Liftgate charges - April",
           """Hugo,

           We waive the liftgate charges on all of your April 2043 deliveries.

           Lennart Szabo""")
    f4, f5 = A.FUEL["2043-04"], A.FUEL["2043-05"]
    A.send_invoice(m, "batch_01", "2043-04-25", "ASC-43-0300",  "2043-05-25",
                   A.airfreight("235-77125001", "2043-04-14", "SFO3-SEA2", "90.0", "4.70", f4)
                   + [A.service("235-77125001", "Liftgate service", A.LIFTGATE)]
                   + A.airfreight("235-77125002", "2043-04-21", "LAX1-DFW4", "90.0", "4.45", f4)
                   + [A.service("235-77125002", "Liftgate service", A.LIFTGATE)])
    A.send_invoice(m, "batch_01", "2043-05-15", "ASC-43-0310", "2043-06-14",
                   A.airfreight("235-77125003", "2043-05-06", "SFO3-SEA2", "90.0", "4.70", f5)
                   + [A.service("235-77125003", "Liftgate service", A.LIFTGATE)])
    A.send_tracking(m, "batch_01", "2043-05-16", [("235-77125001", "2043-04-14", "SFO"), ("235-77125002", "2043-04-21", "LAX"),
                                                  ("235-77125003", "2043-05-06", "SFO")])
    return m, {"why": "The waivers contact waived liftgate for April 2043 deliveries: both April liftgate charges on "
                      "ASC-43-0300 (80.00); the May delivery on ASC-43-0310 is billable.",
               "reports": [report("2043-05-20", [
                   item(ikey("ASC-43-0300", "waived_but_billed"), "finding", "two April liftgate charges: 80.00",
                        "draft:dispute", "execute:dispute", amount=D("80.00"))],
                   [control(ikey("ASC-43-0310", "waived_but_billed"), "May is outside the waived month")])]}


@case("w4_h11_grace_boundary_five_and_six_days", "aldous", HOLD, ["E"])
def h11():
    m = A.start("w4_h11_grace_boundary_five_and_six_days")
    rows_k = A.airfreight("235-77126001", "2043-05-26", "SFO3-SEA2", "260.0", "4.15", A.FUEL["2043-05"])
    rows_l = A.airfreight("235-77126002", "2043-05-27", "LAX1-DFW4", "260.0", "3.90", A.FUEL["2043-05"])
    _, total_k = A.send_invoice(m, "batch_01", "2043-06-01", "ASC-43-0400", "2043-07-01", rows_k)
    _, total_l = A.send_invoice(m, "batch_01", "2043-06-02", "ASC-43-0401", "2043-07-02", rows_l)
    A.send_ledger(m, "batch_01", "2043-07-15", [["ASC-43-0400", float(total_k), "Yes", "2043-07-06"],
                                                ["ASC-43-0401", float(total_l), "Yes", "2043-07-08"]])
    assert late_fee_months(date(2043, 7, 6), date(2043, 7, 1), A.GRACE) == 0       # 5 days: inside grace
    assert late_fee_months(date(2043, 7, 8), date(2043, 7, 2), A.GRACE) == 1       # 6 days: one month
    fee_k, fee_l = pct_of(A.LATE_PCT, total_k), pct_of(A.LATE_PCT, total_l)
    rows_m = A.airfreight("235-77126003", "2043-07-14", "SFO3-SEA2", "100.0", "4.70", A.FUEL["2043-07"]) + \
        [A.late_charge("ASC-43-0400", total_k, 1, fee_k, 5), A.late_charge("ASC-43-0401", total_l, 1, fee_l, 6)]
    A.send_invoice(m, "batch_01", "2043-07-20", "ASC-43-0430", "2043-08-19", rows_m)
    A.send_tracking(m, "batch_01", "2043-07-21", [("235-77126001", "2043-05-26", "SFO"), ("235-77126002", "2043-05-27", "LAX"),
                                                  ("235-77126003", "2043-07-14", "SFO")])
    return m, {"why": "ASC-43-0400 was paid exactly 5 days after its due date (inside the grace period), so its "
                      "late charge is not owed; ASC-43-0401 was paid 6 days late, so one month (2.0%) is owed and "
                      "billed correctly.",
               "reports": [report("2043-07-25", [
                   item(ikey("ASC-43-0430", "late_fee_not_owed"), "finding", f"only the ASC-43-0400 charge: {fee_k}",
                        "draft:dispute", "execute:dispute", amount=fee_k)])]}


@case("w4_h12_term_extension_removes_alert", "aldous", HOLD, ["G", "J"])
def h12():
    m = A.start("w4_h12_term_extension_removes_alert")
    m.mail("batch_02", "2043-10-18", A.CORDELIA, A.HUGO, f"Amendment No. 1 to {A.CID} - term extended",
           "Hugo,\n\nBoth parties have signed Amendment No. 1 extending the initial term (attached).\n\nCordelia Nash",
           [(f"Amendment-1-{A.CID}.pdf", A.term_extension(1, "2043-10-17", "2043-10-17", "2044-07-31"))])
    key = {"contract_id": A.CID}
    return m, {"why": "Before the amendment the notice deadline is 2043-12-02 (60 days before 31st January 2044), 48 "
                      "days after 2043-10-15: alert. The signed amendment moves the expiry to 31st July 2044, so the "
                      "deadline becomes 2044-06-01, far outside 60 days on 2043-10-20: the alert goes away.",
               "reports": [report("2043-10-15", [item(key, "finding", "notice deadline 2043-12-02", "internal:alert",
                                                      "internal:alert", deadline="2043-12-02")], after="batch_01"),
                           report("2043-10-20", [], [control(key, "the extension moved the deadline to 2044-06-01")])]}


# ---- fresh holdout cases, written after the run-1 failures were fixed (same defect classes, new worlds/wording) ----
@case("w2_h13_all_dates_ambiguous_dotted", "sarvani", HOLD, ["H", "A"])
def h13():
    m = S.start("w2_h13_all_dates_ambiguous_dotted")
    fuel = S.FUEL["2043-01"]
    S.send_invoice(m, "batch_01", "2043-01-12", "SAL-INV-43-0105", "2043-02-02",
                   S.freight("176-55024001", "2043-01-08", "MAA3-BOM1", "50.0", "174.00", fuel))
    S.send_tracking(m, "batch_01", "2043-01-12", [("176-55024001", "2043-01-08", "MAA")])
    inr = finding([line("174.00", "50.0"), pct_of(fuel, line("174.00", "50.0"))],
                  [line("161.75", "50.0"), pct_of(fuel, line("161.75", "50.0"))])
    usd = inr_to_usd(inr, S.FX["2043-01"])
    return m, {"why": "Every numeric date on the invoice (12.01.2043, 02.02.2043, 08.01.2043) has a day of 12 or less; "
                      "written with dots they read day-first, so the invoice is January (Annex F 83.1450). 50.0 kg is "
                      "the 45 - 99.9 kg slab (161.75), billed at the up to 44.9 kg rate 174.00.",
               "reports": [report("2043-01-15", [
                   item(ikey("SAL-INV-43-0105", "overcharge"), "finding", f"INR {inr} / 83.1450 = {usd}",
                        "draft:dispute", "execute:dispute", amount=usd)])]}


@case("w3_h14_term_extended_before_notice_deadline", "kittering", HOLD, ["G", "J"])
def h14():
    m = K.start("w3_h14_term_extended_before_notice_deadline")
    m.mail("batch_02", "2044-11-18", K.SUNNIVA, K.JUDE, f"Amendment No. 1 to {K.CID}",
           "Jude,\n\nThe signed amendment extending our agreement is attached.\n\nSunniva Holt",
           [(f"Amendment-1-{K.CID}.pdf", K.term_amendment(1, "2044-11-17", "2046-03-31"))])
    key = {"contract_id": K.CID}
    assert (date(2045, 3, 31) - date(2044, 12, 31)).days == 90
    return m, {"why": "The agreement renews unless notice is given at least 90 days before the end of the term "
                      "(31 March 2045): deadline 2044-12-31, 46 days after 2044-11-15, so an alert. The signed "
                      "amendment extends the term to 31 March 2046; renewal terms still apply, so the deadline moves "
                      "to 2045-12-31 and the alert disappears on 2044-11-20.",
               "reports": [report("2044-11-15", [item(key, "finding", "notice deadline 2044-12-31", "internal:alert",
                                                      "internal:alert", deadline="2044-12-31")], after="batch_01"),
                           report("2044-11-20", [], [control(key, "deadline moved to 2045-12-31")])]}
