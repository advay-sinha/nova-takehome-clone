"""World 2 (Sarvani / Brennholt, INR) cases. Amounts from oracle.py on the printed terms; USD via Annex F once."""
from __future__ import annotations

from oracle import conflict_range, finding, inr_to_usd, line, pct_of
from spec import case, control, ikey, item, report
import world_sarvani as W

DEV = "dev"


@case("w2_d07_inr_slab_edge_single_conversion", "sarvani", DEV, ["A", "H"])
def d07():
    m = W.start("w2_d07_inr_slab_edge_single_conversion")
    fuel = W.FUEL["2043-03"]
    W.send_invoice(m, "batch_01", "2043-03-16", "SAL-INV-43-0712", "2043-04-06",
                   W.freight("176-55012345", "2043-03-09", "BLR2-DEL1", "100.5", "182.50", fuel)
                   + W.freight("176-55012346", "2043-03-10", "BLR2-DEL1", "99.9", "182.50", fuel))
    W.send_tracking(m, "batch_01", "2043-03-18", [("176-55012345", "2043-03-09", "BLR"), ("176-55012346", "2043-03-10", "BLR")])
    inr = finding([line("182.50", "100.5"), pct_of(fuel, line("182.50", "100.5"))],
                  [line("168.00", "100.5"), pct_of(fuel, line("168.00", "100.5"))])
    usd = inr_to_usd(inr, W.FX["2043-03"])
    per_line = inr_to_usd(line("182.50", "100.5") - line("168.00", "100.5"), W.FX["2043-03"]) + inr_to_usd(
        pct_of(fuel, line("182.50", "100.5")) - pct_of(fuel, line("168.00", "100.5")), W.FX["2043-03"])
    assert usd != per_line            # the case tells single conversion from per-line conversion
    return m, {"why": "100.5 kg is in the 100 kg + slab (Validity 1: INR 168.00) but billed at the 45 - 99.9 kg rate "
                      "182.50; 99.9 kg at 182.50 is right. Fuel March 22.0% on freight.",
               "reports": [report("2043-03-20", [
                   item(ikey("SAL-INV-43-0712", "overcharge"), "finding",
                        f"INR (18,341.25 + 4,035.08) - (16,884.00 + 3,714.48) = {inr}; / Annex F March 2043 83.3333 "
                        f"once = USD {usd} (per-line conversion would give {per_line})",
                        "draft:dispute", "execute:dispute", amount=usd)])]}


@case("w2_d08_no_annex_f_row", "sarvani", DEV, ["B", "I"])
def d08():
    m = W.start("w2_d08_no_annex_f_row")
    W.send_invoice(m, "batch_01", "2043-07-10", "SAL-INV-43-0905", "2043-07-31",
                   W.freight("176-55019001", "2043-07-03", "BLR2-DEL1", "60.0", "201.50", W.FUEL["2043-07"]))
    W.send_invoice(m, "batch_01", "2043-07-11", "SAL-INV-43-0906", "2043-08-01",
                   W.freight("176-55019002", "2043-07-04", "MAA3-BOM1", "60.0", "166.00", W.FUEL["2043-07"]))
    W.send_tracking(m, "batch_01", "2043-07-12", [("176-55019001", "2043-07-03", "BLR"), ("176-55019002", "2043-07-04", "MAA")])
    return m, {"why": "Annex F lists months up to June 2043; the July invoice is overbilled in INR (60.0 kg is the 45 - "
                      "99.9 kg slab, Validity 2 187.00, billed 201.50) but its USD amount needs a July rate the "
                      "agreement does not give. The correctly billed July invoice is simply clean.",
               "reports": [report("2043-08-05", [
                   item(ikey("SAL-INV-43-0905", "overcharge"), "cannot_determine",
                        "no Annex F row for July 2043: ask the Schedule 1 treasury contact (Imran Qadri)",
                        "draft:request_document", "execute:request_document", missing_doc="Annex F")],
                   [control(ikey("SAL-INV-43-0906", "overcharge"), "billed at the Validity 2 rate 166.00: nothing "
                            "to convert, so the missing FX row does not matter")])]}


@case("w2_d09_paid_invoice_resent_across_batches", "sarvani", DEV, ["C"])
def d09():
    m = W.start("w2_d09_paid_invoice_resent_across_batches")
    rows_x = W.freight("176-55013001", "2043-02-06", "MAA3-BOM1", "80.0", "161.75", W.FUEL["2043-02"]) + \
        [W.charge("176-55013001", "Documentation", "1 AWB", "350.00")]
    rows_y = W.freight("176-55013002", "2043-02-24", "BLR2-DEL1", "40.0", "196.00", W.FUEL["2043-02"])
    W.send_invoice(m, "batch_01", "2043-02-12", "SAL-INV-43-0418", "2043-03-05", rows_x)
    W.send_invoice(m, "batch_01", "2043-03-03", "SAL-INV-43-0466", "2043-03-24", rows_y)
    W.send_tracking(m, "batch_01", "2043-03-04", [("176-55013001", "2043-02-06", "MAA"), ("176-55013002", "2043-02-24", "BLR")])
    total_x = sum(r["amount"] for r in rows_x)
    total_y = sum(r["amount"] for r in rows_y)
    m.mail("batch_01", "2043-03-08", W.SAMIR, W.LEENA, "Payables position 08.03.2043",
           "Leena,\n\nPayables extract attached.\n\nSamir", [("payables-2043-03-08.xlsx", W.ledger([
               ["SAL-INV-43-0418", "12.02.2043", "05.03.2043", float(total_x), "Settled", "02.03.2043"],
               ["SAL-INV-43-0466", "03.03.2043", "24.03.2043", float(total_y), "Open", None]]))])
    m.mail("batch_02", "2043-03-27", W.BILLING, W.SAMIR, "OVERDUE: SAL-INV-43-0418 - payment pending",
           f"""Dear Sir/Madam,

           Our ledger shows SAL-INV-43-0418 as outstanding. Kindly process payment of INR {total_x:,.2f} at the
           earliest. The invoice is attached again.

           Sarvani Accounts""", [("SAL-INV-43-0418.pdf", W.invoice("SAL-INV-43-0418", "2043-02-12", "2043-03-05", rows_x))])
    m.mail("batch_02", "2043-03-28", W.BILLING, W.SAMIR, "SAL-INV-43-0466 - copy for your records",
           """Dear Sir/Madam,

           As requested, a duplicate copy of SAL-INV-43-0466 for your records only. No action is needed.

           Sarvani Accounts""", [("SAL-INV-43-0466.pdf", W.invoice("SAL-INV-43-0466", "2043-03-03", "2043-03-24", rows_y))])
    usd = inr_to_usd(total_x, W.FX["2043-02"])
    return m, {"why": "The payables extract shows SAL-INV-43-0418 settled on 02.03.2043 and the carrier asks for it "
                      "again in batch_02: a duplicate for the invoice total. SAL-INV-43-0466 is open and is resent "
                      "only for records.",
               "reports": [report("2043-03-31", [
                   item(ikey("SAL-INV-43-0418", "duplicate"), "finding",
                        f"invoice total INR {total_x} / Annex F February 2043 83.2275 = USD {usd}",
                        "draft:dispute", "execute:dispute", amount=usd)],
                   [control(ikey("SAL-INV-43-0466", "duplicate"), "unpaid invoice resent for records only")])]}


@case("w2_d10_amendment_vs_rate_notice_conflict", "sarvani", DEV, ["B", "I"])
def d10():
    m = W.start("w2_d10_amendment_vs_rate_notice_conflict")
    amd = m.mail("batch_01", "2043-03-25", W.NEHA, W.SAMIR, f"Signed Amendment No. 1 - {W.CID}",
                 "Samir,\n\nPlease find the signed Amendment No. 1.\n\nNeha Varghese\nKey Account Manager",
                 [(f"Amendment-1-{W.CID}.pdf", W.amendment(1, "2043-03-24", "2043-04-01", "MAA3-BOM1", "100 kg +", "140.00"))])
    notice = m.mail("batch_01", "2043-04-08", W.KAVYA, W.SAMIR, "Rate notice - route MAA3-BOM1",
                    """Dear Brennholt team,

                    Under clause 6.2 of the agreement, the rate for route MAA3-BOM1, slab 100 kg +, becomes INR 145.00
                    per kg with effect from 15.04.2043.

                    Kavya Raghunathan
                    Head of Pricing, Sarvani Air Logistics""")
    fuel = W.FUEL["2043-04"]
    W.send_invoice(m, "batch_01", "2043-04-24", "SAL-INV-43-0611", "2043-05-15",
                   W.freight("176-55016100", "2043-04-20", "MAA3-BOM1", "150.0", "149.50", fuel))
    W.send_tracking(m, "batch_01", "2043-04-25", [("176-55016100", "2043-04-20", "MAA")])
    billed = line("149.50", "150.0") + pct_of(fuel, line("149.50", "150.0"))
    a = line("140.00", "150.0") + pct_of(fuel, line("140.00", "150.0"))
    b = line("145.00", "150.0") + pct_of(fuel, line("145.00", "150.0"))
    lo, hi = conflict_range(billed, a, b)
    rng = [inr_to_usd(lo, W.FX["2043-04"]), inr_to_usd(hi, W.FX["2043-04"])]
    return m, {"why": "The signed amendment (140.00 from 01.04.2043) and the rates contact's notice (145.00 from "
                      "15.04.2043) both govern a 20.04.2043 pickup; clause 7.2 ranks neither.",
               "reports": [report("2043-04-30", [
                   item(ikey("SAL-INV-43-0611", "overcharge"), "conflict",
                        f"billed INR {billed}; correct {b} (notice) or {a} (amendment): INR [{lo}, {hi}] / 83.4180 "
                        f"= USD {rng}", "escalate", "escalate", amount_range=rng,
                        evidence_docs=[f"{amd}#Amendment-1-{W.CID}.pdf", notice])])]}


@case("w2_d11_tracking_date_decides_validity", "sarvani", DEV, ["A", "H"])
def d11():
    m = W.start("w2_d11_tracking_date_decides_validity")
    fuel = W.FUEL["2043-07"]
    rows = W.freight("176-55017500", "2043-06-30", "MAA3-BOM1", "75.0", "166.00", fuel)   # invoice prints 30.06
    W.send_invoice(m, "batch_01", "2043-07-08", "SAL-INV-43-0870", "2043-07-29", rows)
    W.send_tracking(m, "batch_01", "2043-07-09", [("176-55017500", "2043-07-01", "MAA")])   # collected 01.07
    return m, {"why": "The milestone report (first in the glossary's pickup order) has the consignment picked up "
                      "01.07.2043, so Validity 2 (166.00) and July fuel (23.0%) apply; the invoice's printed "
                      "30.06.2043 would wrongly suggest Validity 1 (161.75) and June fuel.",
               "reports": [report("2043-07-30", [], [control(ikey("SAL-INV-43-0870", "overcharge"),
                                                             "billed exactly at the Validity 2 rate and July fuel")])]}


@case("w2_d12_amendment_names_missing_annex", "sarvani", DEV, ["B", "I"])
def d12():
    m = W.start("w2_d12_amendment_names_missing_annex")
    amd = m.mail("batch_01", "2043-04-28", W.NEHA, W.SAMIR, f"Amendment No. 2 - {W.CID} (signed)",
                 "Samir,\n\nSigned Amendment No. 2 is attached.\n\nNeha Varghese\nKey Account Manager",
                 [(f"Amendment-2-{W.CID}.pdf", W.amendment_with_annex(2, "2043-04-27", "2043-05-01", "BLR2-DEL1",
                                                                       "Annex A revision 2"))])
    fuel = W.FUEL["2043-05"]
    W.send_invoice(m, "batch_01", "2043-05-19", "SAL-INV-43-0688", "2043-06-09",
                   W.freight("176-55018100", "2043-05-12", "BLR2-DEL1", "130.0", "171.00", fuel))
    W.send_invoice(m, "batch_01", "2043-05-20", "SAL-INV-43-0689", "2043-06-10",
                   W.freight("176-55018101", "2043-05-13", "MAA3-BOM1", "130.0", "149.50", fuel))
    W.send_tracking(m, "batch_01", "2043-05-21", [("176-55018100", "2043-05-12", "BLR"), ("176-55018101", "2043-05-13", "MAA")])
    return m, {"why": "Signed Amendment No. 2 replaces the BLR2-DEL1 rates from 01.05.2043 with Annex A revision 2, "
                      "which is not attached or held; the rate for a 12.05.2043 BLR2-DEL1 pickup cannot be known. "
                      "MAA3-BOM1 keeps its Annex A rate and is billed right.",
               "reports": [report("2043-05-23", [
                   item(ikey("SAL-INV-43-0688", "overcharge"), "cannot_determine",
                        "Annex A revision 2 is named by the amendment and not held: ask the rates contact "
                        "(Kavya Raghunathan)", "draft:request_document", "execute:request_document",
                        missing_doc="Annex A revision 2", evidence_docs=[f"{amd}#Amendment-2-{W.CID}.pdf"])],
                   [control(ikey("SAL-INV-43-0689", "overcharge"), "the other route is untouched by the amendment")])]}
