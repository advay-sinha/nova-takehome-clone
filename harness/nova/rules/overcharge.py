"""Overcharge: billed lines priced against the terms in force on each shipment's pickup date (GLOSSARY "Amounts",
"Which document wins", "Conflict, cannot_determine").

Per line: base freight by lane, weight band and rate period (minimum charge applies when rate x weight is lower);
fuel as the pickup month's percentage of the correct base freight; per-kg and flat accessorials from Annex D; and the
contract's own conditional rules (dry ice vs DG fee, peak months, storage days, delivery, customs holds), each applied
only when the contract states it. Lines are rounded half up in the invoice currency; the finding sums billed minus
correct over the overcharged lines and converts INR once with the Annex F rate of the invoice month.

Governing rate: a signed amendment in force beats the agreement (a later one beats an earlier one); a rate notice
counts only from the carrier's Schedule 1 'rates' person; a notice and an amendment that disagree for the same lane and
pickup date are a conflict when the contract leaves them unranked; a change that relies on a document not held makes
the key cannot_determine.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ..money import dec, q2
from ..world import Band, Contract, Fact, World, canonical_code, norm_id, norm_label, to_date
from .common import Candidate

ZERO = Decimal("0")
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
FLAT_CODES = {"DG", "DRYICE", "DLV", "CUSTOMS", "ACCT", "SPROG", "PPROG", "HDL"}
NOT_PRICED = {"TAX", "DUTY", "LATE", "COST", "MARGIN"}


@dataclass
class RateChoice:
    """Outcome of resolving the base-freight rate for one shipment."""
    status: str                              # ok | conflict | missing | unknown
    rate: Decimal | None = None
    minimum: Decimal | None = None
    source: str | None = None                # msa | amendment | notice | feedback
    evidence: list[dict] = field(default_factory=list)
    alt: "RateChoice | None" = None          # the other side of a conflict
    missing: Fact | None = None              # the referenced document a change relies on
    change: dict | None = None
    rejected: list[str] = field(default_factory=list)


def months_of(condition: str | None) -> set[int] | None:
    """'for pickups in September to November only' -> {9, 10, 11}; None when no month range is stated."""
    if not condition:
        return None
    names = [MONTHS[m] for m in re.findall("|".join(MONTHS), condition.lower())]
    if not names:
        abbrevs = re.findall(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", condition.lower())
        names = [i for a in abbrevs for m, i in MONTHS.items() if m.startswith(a)]
    if len(names) == 2 and re.search(r"\bto\b|-|through|until", condition.lower()):
        a, b = names
        return set(range(a, b + 1)) if a <= b else set(range(a, 13)) | set(range(1, b + 1))
    return set(names) or None


def parse_band(text: str) -> tuple[Decimal | None, Decimal | None, bool]:
    t = str(text or "").lower()
    if "minimum" in t:
        return None, None, True
    if (m := re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*(\d+(?:\.\d+)?)|\+)", t)):
        return Decimal(m[1]), (Decimal(m[2]) if m[2] else None), False
    return None, None, False


class Pricer:
    def __init__(self, world: World, contract: Contract, overrides=None):
        self.w, self.c = world, contract
        self.overrides = overrides or []     # feedback-sourced rate decisions (phase 06), level 2
        self.prec = contract.block("precedence")
        self.rules = contract.block("pricing_rules")
        self.learned = None                              # the feedback item that changed a price, if any

    # ---- base freight ----------------------------------------------------------------------------------------------
    def _period_ok(self, band: Band, pickup: date) -> bool:
        if not band.period:
            return True
        lo, hi = self.c.periods.get(str(band.period), (None, None))
        if lo is None and hi is None:
            return True
        return (lo is None or pickup >= lo) and (hi is None or pickup <= hi)

    @staticmethod
    def _pick(bands: list[Band], lane: str, weight: Decimal, ok) -> tuple[Band | None, Band | None]:
        lane_bands = [b for b in bands if b.lane == lane and ok(b)]
        band = next((b for b in lane_bands if b.contains(weight)), None)
        minimum = next((b for b in lane_bands if b.is_minimum), None)
        return band, minimum

    def _choice(self, band, minimum, source) -> RateChoice:
        ev = [b.fact.evidence() for b in (band, minimum) if b is not None]
        return RateChoice("ok", band.rate if band else None, minimum.rate if minimum else None, source, ev)

    def freight(self, lane: str, weight: Decimal, pickup: date) -> RateChoice:
        lane = lane.upper()
        rejected = []
        base = None
        if self.c.msa:
            band, minimum = self._pick(self.c.msa.bands, lane, weight, lambda b: self._period_ok(b, pickup))
            if band:
                base = self._choice(band, minimum, "msa")
        # Amendments in force on the pickup date; the latest effective one wins for the lanes it changes.
        amended = None
        for amd in sorted(self.c.amendments, key=lambda a: a.effective or date.min):
            if amd.signed is False:
                rejected.append(f"{amd.id}: not signed")
                continue
            changes = [ch for ch in amd.fact.get("amendment_changes") or [] if lane in [norm_id(x) for x in ch.get("lanes") or []]]
            if not changes and any(b.lane == lane for b in amd.bands):
                changes = [{"effective_from": amd.effective.isoformat() if amd.effective else None, "what": ""}]
            for ch in changes:
                frm, to = to_date(ch.get("effective_from")) or amd.effective, to_date(ch.get("effective_to"))
                if (frm and pickup < frm) or (to and pickup > to):
                    continue
                missing = next((r for r in self.c.referenced if r.doc == amd.doc
                                and norm_label(r.get("name")) in norm_label(ch.get("what"))), None)
                if missing:
                    amended = RateChoice("missing", source="amendment", missing=missing, change=ch,
                                         evidence=[amd.fact.evidence()] + ([ch["source"] | {"page": ch["source"].get("page") or 1}]
                                                                          if isinstance(ch.get("source"), dict) else []))
                    continue
                band, minimum = self._pick(amd.bands, lane, weight, lambda b: True)
                if band:
                    amended = self._choice(band, minimum, "amendment")
        governing = amended or base
        # Rate notices: only from the carrier's Schedule 1 'rates' person; effective on their stated dates.
        notice = None
        for f in self.w.of("rate_notices"):
            if norm_id(f.get("lane")) != lane:
                continue
            if f.get("contract_id") and self.w.contract_of(f.get("contract_id")) is not self.c:
                continue
            frm, to = to_date(f.get("effective_from")), to_date(f.get("effective_to"))
            if (frm and pickup < frm) or (to and pickup > to):
                continue
            lo, hi, is_min = parse_band(f.get("band"))
            person, item = self.w.authorized(self.c, f.doc, "rates")
            accepted = self.w.feedback.rate_accepted(self.c.id, lane, pickup) if self.w.feedback else None
            if person is None and accepted is None:
                rejected.append(f"notice {f.doc} from {self.w.sender(f.doc) or 'unknown'}: no Schedule 1 rates authority")
                continue
            if item is not None or (person is None and accepted is not None):
                self.learned = item or accepted           # feedback made this notice count
            rate = dec(f.get("rate"))
            if rate is None:
                continue
            if is_min:
                notice = notice or RateChoice("ok", None, None, "notice", [])
                notice.minimum, notice.evidence = rate, notice.evidence + [f.evidence()]
            elif (lo is None or weight >= lo) and (hi is None or weight <= hi):
                notice = notice or RateChoice("ok", None, None, "notice", [])
                notice.rate, notice.evidence = rate, notice.evidence + [f.evidence()]
        for ov in self.overrides:                 # feedback: accepted rate / precedence decisions (phase 06)
            governing, notice = ov(lane, weight, pickup, governing, notice)
        if governing is None and notice is None:
            return RateChoice("unknown", rejected=rejected)
        if governing is not None and governing.status == "missing":
            governing.rejected = rejected
            return governing
        if notice is not None and notice.rate is not None:
            if governing is None or governing.source == "msa":
                notice.minimum = notice.minimum or (governing.minimum if governing else None)
                notice.rejected = rejected
                return notice                      # a notice changes Annex A rates (agreement only)
            if governing.source == "amendment" and notice.rate != governing.rate:
                resolved = self.w.feedback.precedence(self.c.id, lane, pickup) if self.w.feedback else None
                if resolved is not None:                  # a person decided which source wins here
                    self.learned = resolved
                    use = norm_label(resolved.value.get("use"))
                    chosen = governing if "amendment" in use else notice
                    chosen.rejected = rejected + [f"precedence set by feedback {resolved.id}"]
                    return chosen
                if self.prec.get("rate_notice_vs_amendment_unranked") is False:
                    governing.rejected = rejected + ["notice ranked below the amendment by the precedence clause"]
                    return governing
                return RateChoice("conflict", governing.rate, governing.minimum, "amendment", governing.evidence,
                                  alt=notice, rejected=rejected)
        governing.rejected = rejected
        return governing

    # ---- one line --------------------------------------------------------------------------------------------------
    def accessorial(self, code: str) -> Fact | None:
        for f in self.c.accessorials:
            if canonical_code(f.get("code"), f.get("name")) == code:
                return f
        for f in self.c.accessorials:              # Annex D without codes: match the name through Annex E
            if self.c.code_for(f.get("name")) == code:
                return f
        return None


def freight_amount(choice: RateChoice, weight: Decimal) -> Decimal | None:
    if choice.rate is None:
        return choice.minimum
    amount = q2(choice.rate * weight)
    if choice.minimum is not None and amount < choice.minimum:
        return choice.minimum
    return amount


def _events(world: World, awb: str) -> dict[str, date]:
    out = {}
    for f in world.of("tracking_events"):
        if norm_id(f.get("awb")) == norm_id(awb) and (d := to_date(f.get("date"))):
            out.setdefault(norm_label(f.get("event")), d)
    return out


def _price_shipment(world, pricer, lines, pickup, scenario: str) -> list[tuple[Fact, Decimal | None, str]]:
    """Correct amount per line of one shipment (same AWB) under one rate scenario ('main' or 'alt')."""
    c, rules = pricer.c, pricer.rules
    out = []
    frt_correct = None
    freight_lines = [ln for ln in lines if c.code_for(ln.get("charge_label")) == "FRT"]
    for ln in freight_lines:
        weight, lane = dec(ln.get("quantity")), ln.get("lane")
        if weight is None or not lane or pickup is None:
            out.append((ln, None, "freight not priceable: weight, lane or pickup date missing"))
            continue
        choice = pricer.freight(lane, weight, pickup)
        if scenario == "alt" and choice.status == "conflict":
            choice = choice.alt
        if choice.status not in ("ok", "conflict"):
            out.append((ln, None, f"freight rate {choice.status}"))
            continue
        amt = freight_amount(choice, weight)
        frt_correct = (frt_correct or ZERO) + amt if amt is not None else frt_correct
        out.append((ln, amt, f"{choice.source} rate {choice.rate} x {weight} kg (minimum {choice.minimum})"))
    dg = [f for f in world.of("dg_declarations") if lines and norm_id(f.get("awb")) == norm_id(lines[0].get("awb"))]
    codes_billed = {c.code_for(ln.get("charge_label")) for ln in lines}
    events = _events(world, lines[0].get("awb")) if lines and lines[0].get("awb") else {}
    for ln in lines:
        code = c.code_for(ln.get("charge_label"))
        if code in ("FRT", None) or code in NOT_PRICED:
            continue
        qty = dec(ln.get("quantity")) or Decimal("1")
        if code == "FUEL":
            month = pickup.strftime("%Y-%m") if pickup else None
            pct = c.fuel.get(month, (None, None))[0] if month else None
            if pct is None or frt_correct is None:
                out.append((ln, None, "fuel not priceable: no fuel month or no priced freight"))
                continue
            out.append((ln, q2(frt_correct * pct / 100), f"fuel {pct}% of correct freight {frt_correct} ({month})"))
            continue
        acc = pricer.accessorial(code)
        fee = dec(acc.get("fee")) if acc else None
        if fee is None:
            out.append((ln, None, f"{code}: no Annex D fee"))
            continue
        basis = norm_label(acc.get("basis"))
        correct = q2(fee * qty) if ("kg" in basis or "day" in basis or "month" in basis) else fee
        why = f"{code} Annex D {fee} {acc.get('basis')}"
        months = months_of(acc.get("condition"))
        if months and pickup and pickup.month not in months:
            correct, why = ZERO, why + f"; not owed: pickup month {pickup.month} outside {sorted(months)}"
        dg_rule = norm_label(rules.get("dg_dry_ice_rule"))
        if code == "DG" and dg and "dryice" in dg_rule:
            only_ice = all(set(f.get("un_numbers") or []) <= {"UN1845"} and f.get("refrigerant_only") for f in dg)
            if only_ice:
                correct, why = ZERO, why + "; not owed: dry ice used only as refrigerant does not attract the DG fee"
        if code == "DRYICE" and dg and "DG" in codes_billed and "dryice" in dg_rule:
            if any(set(f.get("un_numbers") or []) - {"UN1845"} for f in dg):
                correct, why = ZERO, why + "; not owed: mixed shipment bears only the DG fee"
        if code == "DLV" and rules.get("delivery_fee_rule") and ("collectedbyconsignee" in events or "collected" in events):
            correct, why = ZERO, why + "; not owed: collected by the consignee, no delivery performed"
        if code == "CUSTOMS" and rules.get("customs_rule"):
            if any(norm_id(f.get("awb")) == norm_id(ln.get("awb")) and f.get("event") == "customs_hold"
                   and f.get("carrier_fault") is True for f in world.of("status_events")):
                correct, why = ZERO, why + "; not owed: hold caused by the carrier's documents"
        if code == "STOR" and (free := dec(rules.get("storage_free_days"))) is not None:
            arrived = events.get("arrivedfacility")
            released = events.get("delivered") or events.get("collectedbyconsignee") or events.get("collected")
            if arrived and released:
                days = max(0, (released - arrived).days - int(free))
                correct, why = q2(fee * days), why + f"; {days} storage day(s) = {released} - {arrived} - {free} free"
        out.append((ln, correct, why))
    return out


def detect(world: World, overrides_for=lambda c: []) -> list[Candidate]:
    found = []
    for header, lines in world.invoices():
        c = world.contract_of(header.get("contract_id"))
        if c is None or not lines:
            continue
        pricer = Pricer(world, c, overrides_for(c))
        invoice_id = norm_id(header.get("invoice_id"))
        currency = (header.get("currency") or "USD").upper()
        by_awb: dict[str, list[Fact]] = {}
        for ln in lines:
            by_awb.setdefault(norm_id(ln.get("awb")) or "-", []).append(ln)
        totals = {"main": ZERO, "alt": ZERO}
        has_conflict, missing, unpriced, pickup_sources = None, None, [], set()
        cand = Candidate("overcharge", {"invoice_id": invoice_id, "class": "overcharge"}, "no_finding",
                         contract_id=c.id)
        steps = []
        for awb, ship in by_awb.items():
            if awb == "-":
                continue
            pickup, psource, pfact = world.pickup(awb, ship[0])
            pickup_sources.add(psource)
            for ln in ship:
                if c.code_for(ln.get("charge_label")) == "FRT" and ln.get("lane") and pickup:
                    choice = pricer.freight(ln.get("lane"), dec(ln.get("quantity")) or ZERO, pickup)
                    if choice.status == "missing":
                        missing = (choice, ln)
                    elif choice.status == "conflict":
                        has_conflict = (choice, ln)
                    cand.lane = cand.lane or str(ln.get("lane")).upper()
            for scenario in ("main", "alt"):
                for ln, correct, why in _price_shipment(world, pricer, ship, pickup, scenario):
                    billed = dec(ln.get("amount"))
                    if correct is None or billed is None:
                        if scenario == "main":
                            unpriced.append(f"{ln.get('charge_label')}: {why}")
                        continue
                    diff = billed - correct
                    if scenario == "main":
                        steps.append({"awb": awb, "label": ln.get("charge_label"), "billed": str(billed),
                                      "correct": str(correct), "diff": str(diff), "why": why, "pickup": str(pickup),
                                      "pickup_source": psource})
                    if diff > 0:
                        totals[scenario] += diff
                        if scenario == "main":
                            cand.add_evidence(ln.evidence())
            if pfact is not None and pfact.kind != "invoice_lines":
                cand.add_evidence(pfact.evidence())
        cand.signals = {"pickup_sources": sorted(s for s in pickup_sources if s), "unpriced": unpriced,
                        "currency": currency}
        cand.trace = {"formula": "overcharge.sum_positive_line_diffs", "invoice": invoice_id, "contract": c.id,
                      "currency": currency, "lines": steps}
        if pricer.learned is not None:
            cand.signals["learned_at"] = pricer.learned.learned()
            cand.trace["feedback"] = pricer.learned.id
        if missing is not None:
            choice, ln = missing
            holder = c.contact("rates", (c.block("carrier_code") or None)) or c.contact("rates")
            cand.verdict, cand.outbound = "cannot_determine", "request_document"
            cand.missing_doc = {"name": choice.missing.get("name"),
                                "holder": {k: v for k, v in {"party": holder.party if holder else c.msa and c.msa.fact.get("carrier_code"),
                                                             "person": holder.name if holder else None,
                                                             "role": holder.title if holder else None}.items() if v}}
            cand.evidence = [choice.missing.evidence()] + [e for e in choice.evidence if e.get("quote")] + [ln.evidence()]
            found.append(cand)
            continue
        fx_note = None
        if currency == "INR":
            month = (header.get("invoice_date") or "")[:7]
            fx = c.fx.get(month)
            if fx is None:
                holder = c.contact("treasury")
                cand.verdict, cand.outbound = "cannot_determine", "request_document"
                cand.missing_doc = {"name": f"Annex F exchange rate for {month}",
                                    "holder": {k: v for k, v in {"party": holder.party if holder else None,
                                                                 "person": holder.name if holder else None,
                                                                 "role": holder.title if holder else None}.items() if v}}
                if totals["main"] > 0:
                    found.append(cand)
                continue
            rate, fx_fact = fx
            fx_note = (rate, fx_fact)
            for k in totals:
                totals[k] = q2(totals[k] / rate)
            cand.trace["fx"] = {"month": month, "inr_per_usd": str(rate)}
        if has_conflict is not None and totals["main"] != totals["alt"]:
            choice, ln = has_conflict
            lo, hi = sorted([totals["main"], totals["alt"]])
            cand.verdict, cand.amount_range = "conflict", (max(ZERO, lo), hi)
            cand.evidence = [ln.evidence()] + choice.evidence + choice.alt.evidence
            cand.trace["conflict"] = {"amendment_total": str(totals["main"]), "notice_total": str(totals["alt"])}
            found.append(cand)
            continue
        if totals["main"] > 0:
            cand.verdict, cand.amount_usd, cand.outbound = "finding", q2(totals["main"]), "dispute"
            for awb, ship in by_awb.items():
                if awb != "-" and ship[0].get("lane"):
                    pickup = world.pickup(awb, ship[0])[0]
                    if pickup:
                        choice = pricer.freight(ship[0].get("lane"), dec(ship[0].get("quantity")) or ZERO, pickup)
                        for ev in choice.evidence:
                            cand.add_evidence(ev)
            if fx_note:
                cand.add_evidence(fx_note[1].evidence())
            found.append(cand)
    return found
