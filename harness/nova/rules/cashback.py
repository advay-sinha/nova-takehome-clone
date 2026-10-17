"""Cashback and credits (GLOSSARY "Cashback and credits"): earned and not yet credited, reported once the period has
closed.

rebate (quarterly): Qualifying Spend = freight, fuel, security and Annex D accessorial lines on invoices dated in the
quarter, net of credit notes dated in the quarter (rebate and improvement credits excepted); INR converted per
invoice with the Annex F rate for the invoice month. The tier reached applies to all spend. Owed = earned minus every
rebate credit held for that contract and quarter. Due `credit_due_days_after_period` after the quarter: a claim once
due, tracked before.
promised_credit (annual improvement credit, CYn): pct of the contract year's Qualifying Spend, due within the stated
days after the anniversary; minus improvement credits held for CYn.
margin_step_down (quarterly): once the contract's threshold is crossed, every later invoice in the same window should
bill the handling margin at the stepped-down %. The excess on MARGIN lines of those invoices is summed per quarter of
invoice date (never split into per-invoice overcharges), minus margin credits held for that quarter.
A resent copy of an invoice (same number) counts once; a line billed on two invoice numbers counts twice.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from ..money import dec, q2
from ..world import World, canonical_code, norm_id, to_date
from .common import Candidate

ZERO = Decimal("0")
QS_CODES = {"FRT", "FUEL", "SEC"}
NEVER_QS = {"TAX", "DUTY", "LATE", "COST", "MARGIN"}


def quarter_of(d: date) -> tuple[str, date, date]:
    q = (d.month - 1) // 3 + 1
    start = date(d.year, 3 * q - 2, 1)
    end = (date(d.year + (q == 4), (3 * q) % 12 + 1, 1)) - timedelta(days=1)
    return f"{d.year}-Q{q}", start, end


def _anniversary(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:                                    # 29 February
        return d.replace(year=d.year + years, day=28)


def qualifying_spend(world: World, contract, start: date, end: date) -> tuple[Decimal | None, list[dict], list[dict]]:
    """(QS in USD or None when an Annex F rate is missing, per-invoice trace, evidence)."""
    accessorial_codes = {canonical_code(f.get("code"), f.get("name")) for f in contract.accessorials} | QS_CODES
    lines_by_doc: dict[str, list] = {}
    for ln in world.of("invoice_lines"):
        lines_by_doc.setdefault(ln.doc, []).append(ln)
    total, trace, evidence = ZERO, [], []
    for h in _contract_invoices(world, contract):
        d = to_date(h.get("invoice_date"))
        if not start <= d <= end:
            continue
        spend = ZERO
        for ln in lines_by_doc.get(h.doc, []):
            code = contract.code_for(ln.get("charge_label"))
            if code in accessorial_codes and code not in NEVER_QS:
                spend += dec(ln.get("amount")) or ZERO
        currency = (h.get("currency") or "USD").upper()
        if currency == "INR":
            fx = contract.fx.get(d.isoformat()[:7])
            if fx is None:
                return None, trace, evidence
            spend = q2(spend / fx[0])
        total += spend
        trace.append({"invoice": norm_id(h.get("invoice_id")), "date": str(d), "qs_usd": str(spend)})
    for cn in world.of("credit_notes"):
        if world.contract_of(cn.get("contract_id")) is not contract or cn.get("credit_type") in ("rebate", "improvement"):
            continue
        d = to_date(cn.get("credit_date"))
        if d and start <= d <= end:
            total -= dec(cn.get("amount")) or ZERO
            trace.append({"credit_note": cn.get("credit_id"), "date": str(d), "amount": cn.get("amount")})
            evidence.append(cn.evidence())
    return total, trace, evidence


def _contract_invoices(world: World, contract) -> list:
    """The contract's dated invoice headers, one per invoice number (first received), in date order."""
    seen, out = set(), []
    for h in sorted(world.of("invoices"), key=lambda f: (world.docs[f.doc].received_at, f.doc)):
        key = norm_id(h.get("invoice_id"))
        if key in seen or world.contract_of(h.get("contract_id")) is not contract or to_date(h.get("invoice_date")) is None:
            continue
        seen.add(key)
        out.append(h)
    return sorted(out, key=lambda f: (to_date(f.get("invoice_date")), norm_id(f.get("invoice_id"))))


def _usd(contract, amount: Decimal, currency: str, d: date) -> Decimal | None:
    if (currency or "USD").upper() != "INR":
        return amount
    fx = contract.fx.get(d.isoformat()[:7])
    return q2(amount / fx[0]) if fx else None


def _window_start(contract, basis: str, d: date) -> date:
    """Start of the threshold's counting window containing d: contract year, quarter, calendar year or whole term."""
    eff = contract.msa.effective
    if "contract year" in basis or "anniversary" in basis:
        n = 0
        while _anniversary(eff, n + 1) <= d:
            n += 1
        return _anniversary(eff, n)
    if "quarter" in basis:
        return quarter_of(d)[1]
    if "calendar year" in basis:
        return date(d.year, 1, 1)
    return eff


def margin_step_down(world: World, contract) -> dict[str, dict]:
    """{quarter: {"excess": Decimal, "invoices": [...], "evidence": [...]}} for invoices after the crossing one."""
    block = contract.block("margin")
    pct_from, threshold = dec(block.get("margin_pct")), dec(block.get("step_down_threshold"))
    pct_to = dec(block.get("step_down_pct"))
    if pct_to is None and pct_from is not None and dec(block.get("step_down_by_pct")) is not None:
        pct_to = pct_from - dec(block.get("step_down_by_pct"))
    if block.get("applicable") is False or pct_to is None or threshold is None:
        return {}
    basis = f"{block.get('threshold_basis') or ''} {block.get('rule_text') or ''}".lower()
    strict = "exceed" in basis or "more than" in basis or "above" in basis
    lines_by_doc: dict[str, list] = {}
    for ln in world.of("invoice_lines"):
        lines_by_doc.setdefault(ln.doc, []).append(ln)
    qs_codes = {canonical_code(f.get("code"), f.get("name")) for f in contract.accessorials} | QS_CODES
    out: dict[str, dict] = {}
    window, running, crossed = None, ZERO, False
    for h in _contract_invoices(world, contract):
        d = to_date(h.get("invoice_date"))
        currency = h.get("currency") or "USD"
        start = _window_start(contract, basis, d)
        if start != window:
            window, running, crossed = start, ZERO, False
        lines = lines_by_doc.get(h.doc, [])
        codes = [(ln, contract.code_for(ln.get("charge_label"))) for ln in lines]
        if crossed:                                          # every invoice after the one that crossed
            excess, detail, ev = ZERO, [], []
            cost = sum((dec(ln.get("amount")) or ZERO for ln, c in codes if c == "COST"), ZERO)
            for ln, code in codes:
                billed = dec(ln.get("amount"))
                if code != "MARGIN" or billed is None:
                    continue
                base = dec(ln.get("base_amount"))
                if base is None and cost:
                    base = cost
                if base is None:
                    pct_billed = dec(ln.get("pct")) or pct_from
                    if not pct_billed:
                        continue
                    base = billed * 100 / pct_billed
                correct = q2(base * pct_to / 100)
                if billed > correct:
                    excess += billed - correct
                    detail.append({"line": ln.get("line_no"), "base": str(base), "billed": str(billed),
                                   "correct": str(correct), "pct_to": str(pct_to)})
                    ev.append(ln.evidence())
            usd = _usd(contract, excess, currency, d)
            if excess > 0 and usd is not None:
                q = out.setdefault(quarter_of(d)[0], {"excess": ZERO, "invoices": [], "evidence": []})
                q["excess"] += usd
                q["evidence"] += ev
                q["invoices"].append({"invoice": norm_id(h.get("invoice_id")), "date": str(d), "currency": currency,
                                      "excess": str(excess), "excess_usd": str(usd), "lines": detail})
            continue
        if "shipment" in basis:
            measure = Decimal(len({ln.get("awb") for ln in lines if ln.get("awb")}))
        else:
            want = {"COST"} if "cost" in basis else qs_codes - NEVER_QS
            raw = sum((dec(ln.get("amount")) or ZERO for ln, c in codes if c in want), ZERO)
            measure = _usd(contract, raw, currency, d)
            if measure is None:
                continue
        running += measure
        crossed = running > threshold if strict else running >= threshold
    return out


def _credited(world: World, contract, credit_type: str, period: str) -> tuple[Decimal, list[dict]]:
    total, ev = ZERO, []
    for cn in world.of("credit_notes"):
        if world.contract_of(cn.get("contract_id")) is not contract or cn.get("credit_type") != credit_type:
            continue
        if str(cn.get("period") or "").replace(" ", "").upper() == period.upper():
            total += dec(cn.get("amount")) or ZERO
            ev.append(cn.evidence())
    return total, ev


def _action(c: Candidate, due: date | None, as_of: date) -> None:
    if due is not None and as_of <= due:
        c.internal, c.outbound = "track_credit", None
    else:
        c.outbound = "claim_credit"


def detect(world: World) -> list[Candidate]:
    found = []
    for contract in world.contracts.values():
        if contract.msa is None or contract.msa.effective is None:
            continue
        rebate = contract.block("rebate")
        tiers = sorted(((dec(t.get("min_qualifying_spend")), dec(t.get("pct"))) for t in rebate.get("tiers") or []
                        if dec(t.get("min_qualifying_spend")) is not None and dec(t.get("pct")) is not None),
                       reverse=True)
        end_term = to_date(contract.block("term").get("initial_term_end")) or world.as_of_date
        # ---- quarterly rebate --------------------------------------------------------------------------------------
        if tiers:
            d = contract.msa.effective
            seen = set()
            while d <= min(world.as_of_date, end_term):
                period, start, end = quarter_of(d)
                d = end + timedelta(days=1)
                if period in seen or end >= world.as_of_date:
                    continue                                 # report only once the quarter has closed
                seen.add(period)
                qs, trace, ev = qualifying_spend(world, contract, start, end)
                if qs is None:
                    continue
                pct = next((p for floor, p in tiers if qs >= floor), None)
                if pct is None:
                    continue
                earned = q2(qs * pct / 100)
                credited, cev = _credited(world, contract, "rebate", period)
                owed = earned - credited
                if owed <= 0:
                    continue
                days = dec(rebate.get("credit_due_days_after_period"))
                due = end + timedelta(days=int(days)) if days is not None else None
                c = Candidate("cashback", {"contract_id": contract.id, "period": period, "credit_type": "rebate"},
                              "finding", amount_usd=q2(owed), contract_id=contract.id,
                              trace={"formula": "cashback.rebate", "qs_usd": str(qs), "tier_pct": str(pct),
                                     "earned": str(earned), "credited": str(credited), "invoices": trace,
                                     "credit_due": str(due) if due else None})
                _action(c, due, world.as_of_date)
                if rebate.get("source"):
                    c.add_evidence(rebate["source"] | {"page": rebate["source"].get("page") or 1})
                for e in ev + cev:
                    c.add_evidence(e)
                if not c.evidence:
                    c.add_evidence(contract.msa.fact.evidence())
                found.append(c)
        # ---- annual improvement credit -----------------------------------------------------------------------------
        annual = contract.block("annual_credit")
        pct = dec(annual.get("pct_of_prior_year_qs"))
        if pct is not None and annual.get("applicable") is not False:
            n = 1
            while True:
                start = _anniversary(contract.msa.effective, n - 1)
                end = _anniversary(contract.msa.effective, n) - timedelta(days=1)
                if end >= world.as_of_date or start > end_term:
                    break
                qs, trace, ev = qualifying_spend(world, contract, start, end)
                n += 1
                if qs is None or qs <= 0:
                    continue
                period = f"CY{n - 1}"
                earned = q2(qs * pct / 100)
                credited, cev = _credited(world, contract, "improvement", period)
                owed = earned - credited
                if owed <= 0:
                    continue
                days = dec(annual.get("due_days_after_anniversary"))
                due = end + timedelta(days=1 + int(days)) if days is not None else None
                c = Candidate("cashback", {"contract_id": contract.id, "period": period,
                                           "credit_type": "promised_credit"}, "finding", amount_usd=q2(owed),
                              contract_id=contract.id,
                              trace={"formula": "cashback.annual_credit", "qs_usd": str(qs), "pct": str(pct),
                                     "earned": str(earned), "credited": str(credited), "invoices": trace})
                _action(c, due, world.as_of_date)
                if annual.get("source"):
                    c.add_evidence(annual["source"] | {"page": annual["source"].get("page") or 1})
                for e in cev:
                    c.add_evidence(e)
                if not c.evidence:
                    c.add_evidence(contract.msa.fact.evidence())
                found.append(c)
        # ---- handling margin step-down -----------------------------------------------------------------------------
        margin = contract.block("margin")
        for period, m in sorted(margin_step_down(world, contract).items()):
            year, qn = period.split("-Q")
            if quarter_of(date(int(year), 3 * int(qn), 1))[2] >= world.as_of_date:
                continue                                     # report only once the quarter has closed
            credited, cev = _credited(world, contract, "margin", period)
            owed = q2(m["excess"]) - credited
            if owed <= 0:
                continue
            c = Candidate("cashback", {"contract_id": contract.id, "period": period,
                                       "credit_type": "margin_step_down"}, "finding", amount_usd=q2(owed),
                          contract_id=contract.id,
                          trace={"formula": "cashback.margin_step_down", "excess_usd": str(q2(m["excess"])),
                                 "credited": str(credited), "invoices": m["invoices"]})
            c.outbound = "claim_credit"
            if margin.get("source"):
                c.add_evidence(margin["source"] | {"page": margin["source"].get("page") or 1})
            for e in m["evidence"] + cev:
                c.add_evidence(e)
            found.append(c)
    return found
