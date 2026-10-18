"""Read explicit agreement clauses, rate tables and authority schedules into typed facts.

Only printed terms are extracted. Contract-specific codes, periods, parties and amounts are document data.
The existing rules engine still resolves authority, precedence and financial decisions.
"""
from __future__ import annotations

import re
from datetime import date

from .local_common import BAND, DATE, ID, LANE, NUM, band_bounds, is_heading, capture, fact, iso, month, number


def read_contract(doc, out):
    if doc.kind == "eml":
        return False
    amendment = bool(re.search(r"Amendment\s+(?:No\.?|reference)", doc.flat, re.I))
    cid = capture(r"Agreement\s+(?:No\.?\s*)?(" + ID + r")\b", doc.flat, flags=0)
    if not cid:
        cid = capture(r"(?:Agreement(?:\s+\([^)]*\))?|to)\s+(" + ID + r")\b", doc.flat, flags=0)
    if not cid:
        return False
    # An agreement is a titled "... Agreement" document with numbered clauses; invoices and notices quote a
    # contract number but carry no clause structure.
    numbered = sum(1 for _, line in doc.lines() if re.match(r"\d{1,2}\.\d{1,2}\s+\S", line))
    if not (amendment or re.search(r"(?:Services|Freight) Agreement|Master Agreement", doc.flat, re.I)
            or (re.search(r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*\s+Agreement\b", doc.flat) and numbered >= 2)):
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
        grace_days=number(r"(?:unpaid|outstanding for) more than\s+(" + NUM + r")\s+days", payment)
        or number(r"\bwithin\s+(" + NUM + r")\s+days?\s+(?:after|of|past)\s+the\s+due\s+date", payment)
        or number(r"grace period of\s+(" + NUM + r")\s+days", payment) or number(r"(" + NUM + r")[- ]day grace", payment),
        compounding=(False if re.search(r"do not compound|simple|no compounding", payment, re.I) else
                     True if re.search(r"principal plus|compound", payment, re.I) else None),
        extension_by_category="payment_terms" if "extend" in payment.lower() else None)
    # "5.1 Rebate.", "5.1 Volume rebate." or "5.1 Quarterly volume rebate.": up to two words may lead the heading.
    rebate, rsrc = doc.clause(r"^\d+\.\d+ (?:[A-Za-z]+ ){0,2}?(?:Volume rebate|Rebate|Thresholds|Credit\.|Qualifying Spend)")
    tiers = [{"min_qualifying_spend": a.replace(",", ""), "pct": b}
             for a, b in re.findall(r"(?:USD|INR)\s+(" + NUM + r")(?:\s+or more)?\s*:\s*(" + NUM + r")%", rebate)]
    c["rebate"].update(source=doc.clause(r"^\d+\.\d+ (?:[A-Za-z]+ ){0,2}?(?:Volume rebate|Rebate\.)")[1] or rsrc, tiers=tiers,
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
    # Any other named pricing window with a pickup date range: "Validity 1: consignments collected 01.01.2043 to
    # 30.06.2043", "Season B (shipments picked up 1 May 2043 - 31 Aug 2043)".
    window = (r"\b((?:Validity|Period|Season|Window|Tariff|Column)\s+[A-Z0-9]{1,3})\s*[:(]\s*[^.;:()]{0,60}?("
              + DATE + r")\s*(?:to|-|–|until|through)\s*(" + DATE + ")")
    for p, page in enumerate(doc.pages, 1):
        for m in re.finditer(window, " ".join(page.split()), re.I):
            span = (iso(m[2], doc.order), iso(m[3], doc.order))
            # The same window already read under its short label ("P1" from "Period P1: pickups ...") is not new.
            if m[1] not in {v["label"] for v in periods} and span not in {(v["pickup_from"], v["pickup_to"]) for v in periods}:
                periods.append({"label": m[1], "pickup_from": span[0], "pickup_to": span[1], "source": doc.source(p, m[0])})
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
        if is_heading(line):
            section = line.lower()
        if "fuel" in section and (m := re.fullmatch(r"(.+?)\s+(" + NUM + r")%", line)):
            if month(m[1]):
                out["fuel_rows"].append(fact("fuel_rows", contract_id=cid, month=month(m[1]), pct=m[2], source=doc.source(p, line)))
        if "exchange rate" in section and (m := re.fullmatch(r"(.+?)\s+(" + NUM + ")", line)) and month(m[1]):
            out["fx_rows"].append(fact("fx_rows", contract_id=cid, month=month(m[1]), inr_per_usd=m[2],
                                       source=doc.source(p, line)))
        if re.search(r"accessorial|ancillary|additional (?:charges|fees)", section):
            m = re.match(r"([A-Z]+)\s+(.+?)\s+(?:(USD|INR)\s+)?(" + NUM + r")\s*(?:(USD|INR)\s+)?(per .+)", line)
            if m:
                quote = line
                if line.endswith(" in") and i + 1 < len(lines) and lines[i + 1][0] == p:
                    quote += " " + lines[i + 1][1]
                out["accessorials"].append(fact("accessorials", contract_id=cid, code=m[1], name=m[2], fee=m[4],
                    currency=m[3] or m[5], basis=m[6], condition=quote if "only" in quote else None, source=doc.source(p, quote)))
        if re.search(r"\bcodes\b", section):
            m = re.match(r"(?:Code\s+)?([A-Z]+):?\s+([^;]+?)(?:;\s*also (?:billed|invoiced) as:\s*(.+))?\.?$", line)
            if m and not is_heading(line) and not line.startswith("Initials:"):
                out["charge_codes"].append(fact("charge_codes", contract_id=cid, code=m[1], name=m[2].rstrip("."),
                    aliases=[a.strip().rstrip(".") for a in (m[3] or "").split(",") if a.strip()], source=doc.source(p, line)))
        if section.startswith("schedule"):
            entry = line
            person = _person(entry, c["carrier_code"], c["shipper_code"])
            # An entry wrapped onto the next line ("authorised for: waivers," / "payment terms").
            nxt = lines[i + 1] if i + 1 < len(lines) else None
            if nxt and nxt[0] == p and "@" in line and "@" not in nxt[1] and not is_heading(nxt[1]) and (
                    person is None or re.search(r"[,;:]\s*$", line)):
                entry = f"{line} {nxt[1]}"                 # the quote, as printed
                # A break inside a token ("nash@aldous-" / "stratford.example>") is joined without the space.
                joined = f"{line}{nxt[1]}" if line.endswith("-") else entry
                person = _person(joined, c["carrier_code"], c["shipper_code"]) or person
            if person:
                out["authorised_persons"].append(fact("authorised_persons", contract_id=cid, **person,
                                                      source=doc.source(p, entry)))
    if amendment:
        c["effective_date"] = doc.date(r"(?:Effective from|takes effect on|effective(?:\s+(?:from|on|as of))?)")
        # A term change written as a sentence: "the initial term expires on 31st July 2044", "the term is
        # extended to 30 June 2045". Only the new end is taken; renewal terms stay those of the agreement.
        m, src = doc.find(r"\b(?:initial\s+)?term\b[^.]{0,40}?\b(?:expires|ends|continues until|runs until|is extended "
                          r"(?:to|until))\s+(?:on\s+)?(" + DATE + ")")
        if m:
            c["term"].update(initial_term_end=iso(m[1], doc.order), source=src)
        for p, page in enumerate(doc.pages, 1):
            flat = " ".join(page.split())
            for m in re.finditer(r"(?:\d+\.\s+)?(?:The )?(?:Annex|Appendix|Exhibit|Schedule)\s+\w+ rates for "
                                 r"(?:lane|route)(?:\(s\)|s)?\s+.*?\.(?=\s|$)", flat):
                text = m[0]
                lanes = re.findall(LANE, text)
                date_from = iso(capture(r"applies from\s+(" + DATE + ")", text), doc.order) or c["effective_date"]
                c["amendment_changes"].append({"what": text, "lanes": lanes, "effective_from": date_from,
                    "effective_to": None, "source": doc.source(p, text)})
                name = capture(r"((?:Annex|Appendix|Exhibit|Schedule)\s+\w+\s+(?:rev(?:ision)?\.?|version)\s+\d+)", text)
                if name:
                    out["referenced_documents"].append(fact("referenced_documents", name=name,
                        referenced_by=cid, held_in_this_input=False, applies_to=", ".join(lanes), source=doc.source(p, text)))
        # Prose amendments can change one weight break rather than supply a complete replacement table: any
        # sentence that names a lane, a weight break and a per-kg price, in whatever order the drafter chose.
        for p, page in enumerate(doc.pages, 1):
            flat = " ".join(page.split())
            for sentence in re.split(r"(?<=\.)\s+(?=[A-Z(])", flat):
                lanes = re.findall(LANE, sentence)
                price = re.search(r"\b(USD|INR)\s+(" + NUM + r")\s+per\s+kg", sentence)
                band = re.search(BAND, sentence, re.I)
                if not (lanes and price and band):
                    continue
                start = iso(capture(r"(?:with effect from|effective(?:\s+from|\s+on)?|on or after|applies from|from)\s+("
                                    + DATE + ")", sentence), doc.order) or c["effective_date"]
                source = doc.source(p, sentence)
                lo, hi, minimum = band_bounds(band[0])
                for lane in dict.fromkeys(lanes):
                    out["rate_rows"].append(fact("rate_rows", contract_id=cid, lane=lane, band=band[0], band_min_kg=lo,
                        band_max_kg=hi, is_minimum_charge=minimum, rate=price[2], currency=price[1], source=source))
                c["amendment_changes"].append({"what": sentence, "lanes": list(dict.fromkeys(lanes)),
                    "effective_from": start, "effective_to": None, "source": source})
    out["contracts"].append(c)
    return True


CATEGORY = r"(?:rates|pricing|waivers?|payment terms|billing disputes|disputes|notices|treasury|payments)"


def _person(line, carrier_code=None, shipper_code=None):
    # "Waivers; Payment terms: Lennart Szabo, Credit Manager <lennart@x.example>, ASC-US".
    m = re.fullmatch(r"(" + CATEGORY + r"(?:\s*(?:,|;|and|&)\s*" + CATEGORY + r")*)\s*:\s*(.+?),\s*(.+?)\s*"
                     r"<([\w.+-]+@[\w.-]+)>\s*(?:,\s*([A-Z0-9-]+))?\.?", line.strip(), re.I)
    if m:
        return {"name": m[2].strip(), "title": m[3].strip(), "party": m[5] or carrier_code, "email": m[4],
                "categories": [x.strip() for x in re.split(r"\s*(?:,|;|\band\b|&)\s*", m[1]) if x.strip()]}
    # "Margot Ellery (Rates Manager, KOA-UK) - margot@x.example - authorised for: rates, notices".
    m = re.fullmatch(r"(.+?)\s*\(\s*(.+?),\s*([A-Z0-9-]+)\s*\)\s*[-–|]\s*([\w.+-]+@[\w.-]+)\s*[-–|]\s*"
                     r"(?:authori[sz]ed\s+for|categories)\s*:\s*(.+)", line.strip(), re.I)
    if m:
        return {"name": m[1].strip(), "title": m[2].strip(), "party": m[3], "email": m[4],
                "categories": [x.strip() for x in re.split(r"\s*(?:,|;|\band\b)\s*", m[5].rstrip(".")) if x.strip()]}
    # Category first, party in words: "Waivers, Payment terms Arjun Mehrotra Credit Manager arjun@x.example".
    m = re.fullmatch(r"(" + CATEGORY + r"(?:\s*(?:,|;|and|&)\s*" + CATEGORY + r")*)\s*(\((?:customer|shipper|carrier)\))?"
                     r"\s+(.+?)\s+([\w.+-]+@[\w.-]+)", line.strip(), re.I)
    if m:
        name, title = _split_name_title(m[3], require_title_noun=False)
        if name:
            customer = bool(m[2]) and m[2].lower() in ("(customer)", "(shipper)")
            return {"name": name, "title": title, "party": shipper_code if customer else carrier_code,
                    "categories": [c.strip() for c in re.split(r"\s*(?:,|;|\band\b|&)\s*", m[1]) if c.strip()],
                    "email": m[4]}
    m = re.fullmatch(r"(.+?),\s*(.+?),\s*([A-Z0-9-]+):\s*(.+?)\s*<([^<>\s]+@[^<>\s]+)>", line)
    if m:
        return {"name": m[1], "title": m[2], "party": m[3], "categories": re.split(r"[,;]\s*", m[4]), "email": m[5]}
    m = re.fullmatch(r"([A-Z0-9-]+)\s+(.+?)\s+([\w.+-]+@[\w.-]+)\s+(.+)", line)
    if m:
        role = re.search(r"\b(?:Pricing Manager|Credit Controller|Key Account Manager|Treasury Lead|Logistics Director|AP Lead)\b", m[2])
        name, title = (m[2][:role.start()].strip(), role[0]) if role else _split_name_title(m[2])
        if name and title:
            return {"name": name, "title": title, "party": m[1],
                    "categories": re.split(r"[,;]\s*", m[4]), "email": m[3]}
    return None


TITLE_NOUNS = {"manager", "director", "lead", "head", "controller", "officer", "supervisor", "analyst", "coordinator",
               "specialist", "executive", "accountant", "clerk", "president", "vp", "partner", "administrator",
               "representative", "associate", "chief", "treasurer", "counsel", "planner", "buyer", "agent"}
NAME_PARTICLES = {"de", "da", "del", "della", "van", "von", "der", "la", "le", "bin", "al", "ter", "dos", "du"}


def _split_name_title(text: str, require_title_noun: bool = True) -> tuple[str | None, str | None]:
    """'Osric Mbeki Accounts Receivable Manager' -> ('Osric Mbeki', 'Accounts Receivable Manager'). The title must
    end in a job-title noun (unless the row's categories already mark it as a Schedule 1 entry); the name is the
    first two words, longer only for name particles ('Ana de Souza')."""
    words = text.split()
    if len(words) < 3 or (require_title_noun and words[-1].lower().strip(".,") not in TITLE_NOUNS):
        return None, None
    n = 2
    while n < len(words) - 1 and words[n - 1].lower() in NAME_PARTICLES:
        n += 1
    return " ".join(words[:n]), " ".join(words[n:])
