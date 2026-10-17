"""Read explicit agreement clauses, rate tables and authority schedules into typed facts.

Only printed terms are extracted. Contract-specific codes, periods, parties and amounts are document data.
The existing rules engine still resolves authority, precedence and financial decisions.
"""
from __future__ import annotations

import re
from datetime import date

from .local_common import BAND, DATE, ID, LANE, NUM, band_bounds, capture, fact, iso, month, number


def read_contract(doc, out):
    if doc.kind == "eml":
        return False
    amendment = bool(re.search(r"Amendment\s+(?:No\.?|reference)", doc.flat, re.I))
    cid = capture(r"Agreement\s+(?:No\.?\s*)?(" + ID + r")\b", doc.flat, flags=0)
    if not cid:
        cid = capture(r"(?:Agreement(?:\s+\([^)]*\))?|to)\s+(" + ID + r")\b", doc.flat, flags=0)
    if not cid:
        return False
    if not (amendment or re.search(r"(?:Services|Freight) Agreement|Master Agreement", doc.flat, re.I)):
        return False
    base = cid
    ref = capture(r"Amendment reference\s+(" + ID + r")", doc.flat)
    if amendment:
        no = capture(r"Amendment No\.?\s*(\d+)", doc.flat)
        cid = ref or (f"{base}/AMD-{no}" if no else base)
    _, src = doc.find(re.escape(ref or base))
    c = fact("contracts", contract_id=cid, kind="amendment" if amendment else "master_agreement",
             amends_contract_id=base if amendment else None, amendment_ref=ref,
             title=next((line for _, line in doc.lines() if "Agreement" in line and not line.startswith("Confidential")), None),
             source=src, signed=bool(re.search(r"Signed for|Executed by duly authorised officers", doc.flat, re.I))
             and not bool(re.search(r"\b(?:draft|unsigned|not executed)\b", doc.flat, re.I)))
    c["dated"] = doc.date(r"(?:Dated|dated)")
    c["currency"] = capture(r"\b(USD|INR)\b", doc.flat)
    for party, role in [("shipper", "Shipper|Customer"), ("carrier", "Carrier")]:
        name = capture(r"\(\d\)\s+((?:(?!\(\d\)).)+?), whose principal office(?:(?!\(\d\)).)*?\(the (?:" + role + r")\)", doc.flat)
        if name:
            c[party] = name
        c[party + "_code"] = capture(party + r"\s+code\s+([A-Z0-9-]+)", doc.flat)
    term, term_src = doc.clause(r"^\d+\.\d+ (?:Effective date|Initial term|Auto-renewal|Renewal|Term\.)")
    c["effective_date"] = iso(capture(r"(?:takes effect on|Effective from|commences on|Effective Date of this Agreement is)\s+(" + DATE + ")", doc.flat), doc.order)
    end = capture(r"(?:ending on|continues until|ends on|expires on)\s+(" + DATE + ")", term)
    renewal, renewal_src = doc.clause(r"^\d+\.\d+ (?:Auto-renewal|Renewal)")
    c["term"].update(initial_term_end=iso(end, doc.order), source=doc.clause(r"Initial term\.|Term\.")[1] or term_src,
        auto_renews=(False if re.search(r"does not renew|no automatic renewal|does not continue after", renewal, re.I) else
                     True if re.search(r"(?:renews?|renewed|extends?) automatically|automatically (?:renews?|renewed|extends?)", renewal, re.I) else None),
        renewal_term_months=number(r"(?:periods of|successive)\s+(" + NUM + r")\s*months", renewal),
        non_renewal_notice_days=number(r"(?:at least|least)\s+(" + NUM + r")\s*days", renewal),
        non_renewal_notice_deadline=iso(capture(r"\bby\s+(" + DATE + ")", renewal), doc.order))
    payment, psrc = doc.clause(r"^\d+\.\d+ (?:Payment terms|Due date|Late fee|Late payment|Compounding|Extension)")
    c["payment"].update(source=doc.clause(r"^\d+\.\d+ (?:Late fee|Late payment)")[1] or psrc,
        due_days_after_invoice=number(r"(?:due|payable)\s+(" + NUM + r")\s+days (?:after|from)", payment),
        late_fee_pct_per_month=number(r"late fee of\s+(" + NUM + r")%", payment),
        grace_days=number(r"(?:unpaid|outstanding for) more than\s+(" + NUM + r")\s+days", payment),
        compounding=(False if re.search(r"do not compound|simple|no compounding", payment, re.I) else
                     True if re.search(r"principal plus|compound", payment, re.I) else None),
        extension_by_category="payment_terms" if "extend" in payment.lower() else None)
    rebate, rsrc = doc.clause(r"^\d+\.\d+ (?:Volume rebate|Rebate|Thresholds|Credit\.|Qualifying Spend)")
    tiers = [{"min_qualifying_spend": a.replace(",", ""), "pct": b}
             for a, b in re.findall(r"(?:USD|INR)\s+(" + NUM + r")(?:\s+or more)?\s*:\s*(" + NUM + r")%", rebate)]
    c["rebate"].update(source=doc.clause(r"^\d+\.\d+ (?:Volume rebate|Rebate\.)")[1] or rsrc, tiers=tiers,
        tier_applies_to_all_spend=True if re.search(r"applies to all", rebate, re.I) else None,
        threshold_currency=capture(r"\b(USD|INR)\s+" + NUM + r"(?:\s+or more)?\s*:", rebate),
        period="quarter" if "quarter" in rebate.lower() else None,
        credit_due_days_after_period=number(r"(?:within|no later than)\s+(" + NUM + r")\s+days", rebate),
        qualifying_spend_definition=doc.clause(r"Qualifying Spend means")[0] or None)
    annual, asrc = doc.clause(r"^\d+\.\d+ (?:Annual improvement|No handling margin)")
    c["annual_credit"].update(source=asrc,
        applicable=False if re.search(r"not applicable|no handling margin", annual, re.I) else bool(annual) or None,
        pct_of_prior_year_qs=number(r"(" + NUM + r")% of the (?:prior|Qualifying Spend of the Contract Year just ended)", annual),
        due_days_after_anniversary=number(r"(?:within|no later than)\s+(" + NUM + r")\s+days", annual))
    margin, msrc = doc.clause(r"^\d+\.\d+ (?:Handling margin|Margin step-down|No handling margin)")
    c["margin"].update(source=msrc, rule_text=margin or None,
        applicable=False if re.search(r"not applicable|no handling margin", margin, re.I) else bool(margin) or None,
        margin_pct=number(r"(?:margin (?:is|of)|margin\.)\s*(" + NUM + r")%", margin),
        step_down_pct=number(r"(?:to|becomes)\s+(" + NUM + r")%", margin),
        step_down_by_pct=number(r"by\s+(" + NUM + r")\s*(?:percentage points|%)", margin),
        step_down_threshold=number(r"(?:USD|INR)\s+(" + NUM + r")", margin), threshold_basis=margin or None,
        threshold_currency=capture(r"\b(USD|INR)\b", margin))
    rules = c["pricing_rules"]
    for field, pattern in [("pricing_date_rule", r"Pricing date"), ("minimum_charge_rule", r"Minimum"),
                           ("fuel_applies_to", r"Fuel surcharge"), ("dg_dry_ice_rule", r"Dry ice|Mixed shipments"),
                           ("delivery_fee_rule", r"\d+\.\d+ Delivery"), ("customs_rule", r"Customs holds"),
                           ("rate_notice_rule", r"rate notices|written rate notice"), ("waiver_rule", r"waiv")]:
        t, s = doc.clause(pattern)
        rules[field] = t or None
        rules["source"] = rules["source"] or s
    rules["chargeable_weight_divisor"] = number(r"cm\s*/\s*(" + NUM + ")", doc.flat)
    rules["weight_rounding"] = capture(r"rounded up to[^.]+(?:\.\d+)?\s*kg", doc.flat, group=0)
    rules["storage_free_days"] = number(r"(" + NUM + r")\s+free days", doc.flat)
    prec, prec_src = doc.clause(r"Unranked instruments|Precedence|Correspondence|Quoted text|does not rank")
    c["precedence"].update(source=prec_src, order_text=prec or None,
        later_amendment_prevails=True if re.search(r"later.*prevails", prec, re.I) else None,
        rate_notice_vs_amendment_unranked=True if re.search(r"neither prevails|does not rank", prec, re.I) else None,
        quoted_text_is_not_notice=True if re.search(r"quoted.*not a notice", prec, re.I) else None)
    periods = []
    for p, line in doc.lines():
        if (m := re.search(r"Period\s+(\S+):\s*pickups\s+(" + DATE + r")\s+to\s+(" + DATE + ")", line, re.I)):
            periods.append({"label": m[1], "pickup_from": iso(m[2]), "pickup_to": iso(m[3]), "source": doc.source(p, line)})
        for m in re.finditer(r"(H[12])\s+(\d{4})\s*\(collected\s+(\d+)\s+([A-Za-z]+)-(\d+)\s+([A-Za-z]+)\)", line):
            periods.append({"label": f"{m[1]} {m[2]}", "pickup_from": iso(f"{m[3]} {m[4]} {m[2]}"),
                            "pickup_to": iso(f"{m[5]} {m[6]} {m[2]}"), "source": doc.source(p, line)})
    c["rate_periods"] = periods
    # Read rows by their band and trailing prices, never by fixed lane or company identifiers.
    rate_lanes = set()
    for p, line in doc.lines():
        if (m := re.fullmatch(r"(" + LANE + r")\s+(" + BAND + r")\s+(.+)", line)):
            prices = re.findall(NUM, m[3])
            if not prices or re.search(r"[^\d.,\sA-Z]", m[3]):
                continue
            lo, hi, minimum = band_bounds(m[2])
            labels = [v["label"] for v in periods]
            if len(prices) > 1 and len(prices) != len(labels):
                continue
            for j, value in enumerate(prices):
                out["rate_rows"].append(fact("rate_rows", contract_id=cid, lane=m[1], band=m[2], band_min_kg=lo,
                    band_max_kg=hi, is_minimum_charge=minimum, rate=value.replace(",", ""), currency=c["currency"],
                    period_label=labels[j] if len(prices) > 1 else None, source=doc.source(p, line)))
            rate_lanes.add(m[1])
    # A contract may state one minimum for every lane instead of repeating it in the rate card.
    minimum_text, minimum_src = doc.clause(r"Minimum\.")
    minimum = number(r"not less than\s+(?:USD|INR)\s+(" + NUM + ")", minimum_text)
    if minimum:
        for lane in sorted(rate_lanes):
            out["rate_rows"].append(fact("rate_rows", contract_id=cid, lane=lane, band="minimum charge",
                is_minimum_charge=True, rate=minimum, currency=c["currency"], source=minimum_src))
    section = ""
    lines = list(doc.lines())
    for i, (p, line) in enumerate(lines):
        if re.match(r"(?:Annex|Appendix|Schedule)\s", line):
            section = line.lower()
        if "fuel surcharge" in section and (m := re.fullmatch(r"(.+?)\s+(" + NUM + r")%", line)):
            if month(m[1]):
                out["fuel_rows"].append(fact("fuel_rows", contract_id=cid, month=month(m[1]), pct=m[2], source=doc.source(p, line)))
        if "exchange rate" in section and (m := re.fullmatch(r"(\d{4}-\d{2})\s+(" + NUM + ")", line)):
            out["fx_rows"].append(fact("fx_rows", contract_id=cid, month=m[1], inr_per_usd=m[2], source=doc.source(p, line)))
        if "accessorial" in section or "ancillary fees" in section:
            m = re.match(r"([A-Z]+)\s+(.+?)\s+(?:(USD|INR)\s+)?(" + NUM + r")\s*(?:(USD|INR)\s+)?(per .+)", line)
            if m:
                quote = line
                if line.endswith(" in") and i + 1 < len(lines) and lines[i + 1][0] == p:
                    quote += " " + lines[i + 1][1]
                out["accessorials"].append(fact("accessorials", contract_id=cid, code=m[1], name=m[2], fee=m[4],
                    currency=m[3] or m[5], basis=m[6], condition=quote if "only" in quote else None, source=doc.source(p, quote)))
        if "charge codes" in section:
            m = re.match(r"(?:Code\s+)?([A-Z]+):?\s+([^;]+?)(?:;\s*also (?:billed|invoiced) as:\s*(.+))?\.?$", line)
            if m and not line.startswith(("Annex ", "Appendix ", "Initials:")):
                out["charge_codes"].append(fact("charge_codes", contract_id=cid, code=m[1], name=m[2].rstrip("."),
                    aliases=[a.strip().rstrip(".") for a in (m[3] or "").split(",") if a.strip()], source=doc.source(p, line)))
        if section.startswith("schedule"):
            person = _person(line)
            if person:
                out["authorised_persons"].append(fact("authorised_persons", contract_id=cid, **person, source=doc.source(p, line)))
    if amendment:
        c["effective_date"] = doc.date(r"(?:Effective from|takes effect on)")
        for p, page in enumerate(doc.pages, 1):
            flat = " ".join(page.split())
            for m in re.finditer(r"(?:\d+\.\s+)?(?:The )?Annex A rates for lane\(s\)\s+.*?\.(?=\s|$)", flat):
                text = m[0]
                lanes = re.findall(LANE, text)
                date_from = iso(capture(r"applies from\s+(" + DATE + ")", text)) or c["effective_date"]
                c["amendment_changes"].append({"what": text, "lanes": lanes, "effective_from": date_from,
                    "effective_to": None, "source": doc.source(p, text)})
                name = capture(r"((?:Annex|Appendix)\s+\w+\s+(?:rev(?:ision)?\.?|version)\s+\d+)", text)
                if name:
                    out["referenced_documents"].append(fact("referenced_documents", name=name,
                        referenced_by=cid, held_in_this_input=False, applies_to=", ".join(lanes), source=doc.source(p, text)))
        # Prose amendments can change one weight bracket rather than supply a complete replacement table.
        m, source = doc.find(r"With effect from\s+(" + DATE + r").*?lane\s+(" + LANE + r"),\s*weight bracket\s+(" + BAND + r"),\s*is\s+(USD|INR)\s+(" + NUM + r")\s+per kg")
        if m:
            lo, hi, minimum = band_bounds(m[3])
            out["rate_rows"].append(fact("rate_rows", contract_id=cid, lane=m[2], band=m[3], band_min_kg=lo,
                band_max_kg=hi, is_minimum_charge=minimum, rate=m[5], currency=m[4], source=source))
            c["amendment_changes"].append({"what": m[0], "lanes": [m[2]], "effective_from": iso(m[1]),
                "effective_to": None, "source": source})
    out["contracts"].append(c)
    return True


def _person(line):
    m = re.fullmatch(r"(.+?),\s*(.+?),\s*([A-Z0-9-]+):\s*(.+?)\s*<([^<>\s]+@[^<>\s]+)>", line)
    if m:
        return {"name": m[1], "title": m[2], "party": m[3], "categories": re.split(r"[,;]\s*", m[4]), "email": m[5]}
    m = re.fullmatch(r"([A-Z0-9-]+)\s+(.+?)\s+([\w.+-]+@[\w.-]+)\s+(.+)", line)
    if m:
        role = re.search(r"\b(?:Pricing Manager|Credit Controller|Key Account Manager|Treasury Lead|Logistics Director|AP Lead)\b", m[2])
        if role:
            return {"name": m[2][:role.start()].strip(), "title": role[0], "party": m[1],
                    "categories": re.split(r"[,;]\s*", m[4]), "email": m[3]}
    return None
