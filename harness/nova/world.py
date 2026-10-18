"""A read-only view of everything known by a report date, built from verified facts. Rules ask it questions; it never
decides findings itself.

Knowledge cut-off: only documents received by the end of `as_of` (UTC) and their usable facts (ok or unverified).
Contracts: master agreements and amendments, linked by the documents their facts come from, so a rate row on page 9
of an agreement belongs to that agreement even when the row does not repeat the contract number.
Authority: who may change what comes only from Schedule 1 (by sender address and category) and, later, feedback; the
model's opinion of authority is never used.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .money import dec

USABLE = ("ok", "unverified")


def norm_id(s) -> str:
    """GLOSSARY: invoice ids in capitals, with spaces, '#' and ':' removed."""
    return re.sub(r"[\s#:]", "", str(s or "")).upper()


_KG = r"(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilograms?)?"
WEIGHT_BREAKS = [   # (pattern, lower group, upper group); lower and upper bounds are inclusive
    (re.compile(_KG + r"\s*(?:-|–|to|through)\s*" + _KG, re.I), 1, 2),
    (re.compile(_KG + r"\s*\+", re.I), 1, None),
    (re.compile(_KG + r"\s+(?:and|or)\s+(?:over|above|more)", re.I), 1, None),
    (re.compile(r"up\s+to\s+(?:and\s+including\s+)?" + _KG, re.I), None, 1),
]


def parse_band(text) -> tuple[Decimal | None, Decimal | None, bool]:
    """A weight break as printed -> (lower kg, upper kg, is_minimum_charge). Both bounds inclusive; an open end is
    None. Exclusive wordings ("under 100 kg") are not guessed: they return (None, None, False)."""
    t = str(text or "")
    if re.search(r"\bminimum\b", t, re.I):
        return None, None, True
    for pattern, lo, hi in WEIGHT_BREAKS:
        if (m := pattern.search(t)):
            return (Decimal(m[lo]) if lo else Decimal(0)), (Decimal(m[hi]) if hi else None), False
    return None, None, False


def norm_label(s) -> str:
    """Charge labels compared case- and space-insensitively (OCR drops spaces)."""
    return re.sub(r"[^0-9a-z]", "", unicodedata.normalize("NFKC", str(s or "")).lower())


# The rules speak in these charge roles. A contract may use its own code letters (FSC for fuel, SCR for security):
# such a code is mapped to its role by the charge's name; an unrecognised code keeps its own letters.
ROLES = {"FRT", "FUEL", "SEC", "DG", "DRYICE", "DLV", "STOR", "PEAK", "TAX", "DUTY", "LATE", "COST", "MARGIN",
         "CUSTOMS", "ACCT", "SPROG", "PPROG", "HDL"}
ROLE_WORDS = [("DRYICE", ("dryice",)), ("DG", ("dangerous", "dgfee", "dghandling", "hazardous")), ("FUEL", ("fuel",)),
              ("SEC", ("security", "screening")), ("PEAK", ("peak",)), ("STOR", ("storage", "warehous")),
              ("CUSTOMS", ("customs",)), ("LATE", ("latepayment", "latefee", "overdue", "interest")),
              ("DUTY", ("duty", "duties")), ("TAX", ("tax", "gst", "vat")), ("MARGIN", ("margin",)),
              ("COST", ("carriercost", "passthrough", "costpass")), ("DLV", ("delivery",)), ("FRT", ("freight",)),
              ("HDL", ("handling",))]


def canonical_code(code, name=None) -> str:
    raw = re.sub(r"[^0-9A-Z]", "", str(code or "").upper())
    if raw in ROLES:
        return raw
    n = norm_label(name)
    for role, words in ROLE_WORDS:
        if any(w in n for w in words):
            return role
    return raw


CATEGORY_WORDS = {"billingdisputes": "billing_disputes", "billingdispute": "billing_disputes",
                  "disputes": "billing_disputes", "paymentterms": "payment_terms", "paymentterm": "payment_terms",
                  "rate": "rates", "pricing": "rates", "waiver": "waivers", "notice": "notices"}


def categories(values) -> set[str]:
    """Schedule 1 categories as the rules name them: 'billing disputes; notices' -> {billing_disputes, notices}."""
    out = set()
    for v in values or []:
        for part in re.split(r"[;,/]|\band\b", str(v), flags=re.I):
            key = norm_label(part)
            if key:
                out.add(CATEGORY_WORDS.get(key, re.sub(r"[^0-9a-z]+", "_", part.strip().lower()).strip("_")))
    return out


def _empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _merge_same_doc(main: "Fact", others: list["Fact"]) -> "Fact":
    """A long agreement is read in page chunks, and each chunk reports the agreement it sees: the term on one page,
    the rate periods on another. Fill what the first chunk left empty from the others (lists unioned without
    duplicates, nested term blocks field by field); a value the first chunk gave is never overwritten."""
    if not others:
        return main
    data = dict(main.data)
    for o in others:
        for k, v in o.data.items():
            if k.startswith("_") or _empty(v):
                continue
            cur = data.get(k)
            if _empty(cur):
                data[k] = v
            elif isinstance(cur, list) and isinstance(v, list):
                data[k] = cur + [x for x in v if x not in cur]
            elif isinstance(cur, dict) and isinstance(v, dict):
                data[k] = cur | {kk: vv for kk, vv in v.items() if _empty(cur.get(kk)) and not _empty(vv)}
    return Fact(main.id, main.kind, main.doc, main.page, main.quote, data, main.status)


def to_date(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


@dataclass
class Fact:
    id: int
    kind: str
    doc: str
    page: int | None
    quote: str | None
    data: dict
    status: str

    def evidence(self) -> dict:
        return {"doc": self.doc, "page": self.page or 1, "quote": self.quote or ""}

    def get(self, key, default=None):
        return self.data.get(key, default)


@dataclass
class Doc:
    doc: str
    email_doc: str
    batch: str
    received_at: str
    sender_addr: str
    sender_name: str
    subject: str
    kind: str


@dataclass
class Person:
    name: str
    email: str
    party: str | None
    title: str | None
    categories: set[str]
    fact: Fact | None             # None when the authority comes from feedback, not Schedule 1


@dataclass
class Band:
    lane: str
    lo: Decimal | None
    hi: Decimal | None        # None = open-ended ("300+")
    is_minimum: bool
    rate: Decimal
    period: str | None
    fact: Fact

    def contains(self, weight: Decimal) -> bool:
        if self.is_minimum:
            return False
        return (self.lo is None or weight >= self.lo) and (self.hi is None or weight <= self.hi)


@dataclass
class Instrument:
    """A master agreement or an amendment."""
    id: str
    base_id: str
    kind: str                 # master_agreement | amendment
    doc: str
    fact: Fact
    effective: date | None
    signed: bool | None
    bands: list[Band] = field(default_factory=list)


@dataclass
class Contract:
    id: str
    msa: Instrument | None = None
    amendments: list[Instrument] = field(default_factory=list)
    persons: list[Person] = field(default_factory=list)
    periods: dict[str, tuple[date | None, date | None]] = field(default_factory=dict)
    fuel: dict[str, tuple[Decimal, Fact]] = field(default_factory=dict)
    fx: dict[str, tuple[Decimal, Fact]] = field(default_factory=dict)
    accessorials: list[Fact] = field(default_factory=list)
    codes: dict[str, str] = field(default_factory=dict)              # normalized label -> code
    code_facts: dict[str, Fact] = field(default_factory=dict)       # code -> charge-code fact
    referenced: list[Fact] = field(default_factory=list)            # documents named by its instruments

    def block(self, name: str) -> dict:
        return (self.msa.fact.get(name) or {}) if self.msa else {}

    def code_for(self, label: str) -> str | None:
        n = norm_label(label)
        if n in self.codes:
            return self.codes[n]
        for known, code in sorted(self.codes.items(), key=lambda kv: -len(kv[0])):   # "Air freight (MAWB ...)"
            if known and n.startswith(known):
                return code
        return None

    def authority(self, email: str | None, category: str, party: str | None = None) -> Person | None:
        """The Schedule 1 person behind `email` for `category`, or None."""
        email = (email or "").lower()
        for p in self.persons:
            if p.email == email and category in p.categories and (party is None or (p.party or "") == party):
                return p
        return None

    def contact(self, category: str, party_prefix: str | None = None) -> Person | None:
        for p in self.persons:
            if category in p.categories and (party_prefix is None or (p.party or "").startswith(party_prefix)):
                return p
        return None


class World:
    def __init__(self, store, as_of: str):
        self.as_of = as_of
        self.as_of_date = date.fromisoformat(as_of)
        cutoff = f"{as_of}T23:59:59Z"
        kinds = dict(store.db.execute("SELECT doc, kind FROM doc_kinds").fetchall())
        self.docs: dict[str, Doc] = {}
        for r in store.db.execute("SELECT * FROM documents WHERE received_at IS NOT NULL AND received_at <= ?",
                                  (cutoff,)):
            self.docs[r["doc"]] = Doc(r["doc"], r["email_doc"], r["batch"], r["received_at"], r["sender_addr"] or "",
                                      r["sender_name"] or "", r["subject"] or "", kinds.get(r["doc"], "other"))
        marks = ",".join("?" * len(USABLE))
        self.facts: dict[str, list[Fact]] = {}
        for r in store.db.execute(f"SELECT * FROM facts WHERE status IN ({marks}) ORDER BY id", USABLE):
            if r["doc"] not in self.docs:
                continue                      # not received by as_of: does not exist for this report
            f = Fact(r["id"], r["kind"], r["doc"], r["page"], r["quote"], json.loads(r["data_json"]), r["status"])
            self.facts.setdefault(f.kind, []).append(f)
        self.contracts: dict[str, Contract] = {}
        self._build_contracts()
        self.feedback = None          # a feedback.FeedbackState, set by the report builder

    def authorized(self, contract: "Contract", doc: str, category: str) -> tuple["Person | None", object]:
        """Who authorises what `doc` says for `category`: the Schedule 1 person by sender address, or a person a
        feedback decision confirmed for this contract and category (matched by sender name, document dated inside
        the scope). Returns (person or None, the feedback item used or None)."""
        sender = self.sender(doc)
        person = contract.authority(sender, category)
        if person is not None or self.feedback is None:
            return person, None
        d = self.docs.get(doc)
        email = self.docs.get(d.email_doc) if d else None
        name = email.sender_name if email else ""
        item = self.feedback.grant(contract.id, category, name, to_date(d.received_at) if d else None) if name else None
        if item is None:
            return None, None
        return Person(name, sender, item.subject.get("party"), None, {category}, None), item

    def of(self, kind: str) -> list[Fact]:
        return self.facts.get(kind, [])

    def sender(self, doc: str) -> str:
        d = self.docs.get(doc)
        return self.docs[d.email_doc].sender_addr if d and d.email_doc in self.docs else ""

    # ---- contracts ----------------------------------------------------------------------------------------------------
    def _build_contracts(self) -> None:
        # Several facts may describe one instrument (the cover email names it too). The canonical fact comes from the
        # instrument's own document (classified contract/amendment), so its tables and terms attach to it (H-003).
        groups: dict[str, list[Fact]] = {}
        for f in self.of("contracts"):
            if (cid := norm_id(f.get("contract_id"))):
                groups.setdefault(cid, []).append(f)
        doc_instrument: dict[str, Instrument] = {}
        for cid, facts in groups.items():
            facts.sort(key=lambda f: (self.docs[f.doc].kind not in ("contract", "amendment"), f.doc.endswith(".eml"),
                                      f.id))
            f = _merge_same_doc(facts[0], [x for x in facts[1:] if x.doc == facts[0].doc])
            kind = f.get("kind") or "other"
            base = norm_id(f.get("amends_contract_id")) if kind == "amendment" and f.get("amends_contract_id") else cid
            if kind == "amendment" and base == cid and "/" in cid:
                base = cid.split("/")[0]
            inst = Instrument(cid, base, kind, f.doc, f, to_date(f.get("effective_date")), f.get("signed"))
            c = self.contracts.setdefault(base, Contract(base))
            if kind == "amendment":
                c.amendments.append(inst)
            elif c.msa is None:
                c.msa = inst
            for other in facts:
                doc_instrument.setdefault(other.doc, inst)
            for p in f.get("rate_periods") or []:
                c.periods[str(p.get("label"))] = (to_date(p.get("pickup_from")), to_date(p.get("pickup_to")))
        by_id = {i.id: i for c in self.contracts.values() for i in ([c.msa] if c.msa else []) + c.amendments}
        self.instrument_docs = {i.doc for i in by_id.values()}

        def owner(f: Fact) -> tuple[Contract | None, Instrument | None]:
            inst = doc_instrument.get(f.doc) or by_id.get(norm_id(f.get("contract_id")))
            if inst:
                return self.contracts[inst.base_id], inst
            c = self.contracts.get(norm_id(f.get("contract_id")))
            return c, (c.msa if c else None)

        for f in self.of("rate_rows"):
            c, inst = owner(f)
            rate = dec(f.get("rate"))
            if not inst or rate is None:
                continue
            lo, hi = dec(f.get("band_min_kg")), dec(f.get("band_max_kg"))
            band = str(f.get("band") or "")
            if lo is None:
                lo, hi, _ = parse_band(band)
            if "+" in band and hi is not None and lo == hi:
                hi = None
            inst.bands.append(Band(str(f.get("lane") or "").upper(), lo, hi, bool(f.get("is_minimum_charge")), rate,
                                   f.get("period_label"), f))
        for f in self.of("fuel_rows"):
            c, _ = owner(f)
            if c and (pct := dec(f.get("pct"))) is not None:
                c.fuel[str(f.get("month"))] = (pct, f)
        for f in self.of("fx_rows"):
            c, _ = owner(f)
            if c and (rate := dec(f.get("inr_per_usd"))) is not None:
                c.fx[str(f.get("month"))] = (rate, f)
        for f in self.of("accessorials"):
            c, _ = owner(f)
            if c:
                c.accessorials.append(f)
        for f in self.of("charge_codes"):
            c, _ = owner(f)
            code = canonical_code(f.get("code"), f.get("name"))
            # A contract's own word for a role ("Linehaul") may only be explained by its alias ("also billed as:
            # Freight"): the aliases name the same charge, so they may identify the role too.
            for alias in (f.get("aliases") or []) if code not in ROLES else []:
                if (by_alias := canonical_code(f.get("code"), alias)) in ROLES:
                    code = by_alias
                    break
            if c and code:
                c.code_facts[code] = f
                for label in [f.get("name"), *(f.get("aliases") or [])]:
                    if label:
                        c.codes.setdefault(norm_label(label), code)
        for f in self.of("authorised_persons"):
            c, _ = owner(f)
            if c and f.get("email"):
                c.persons.append(Person(f.get("name") or "", str(f.get("email")).lower(), f.get("party"),
                                        f.get("title"), categories(f.get("categories")), f))
        # Documents an agreement or amendment names. Whether one is held is decided here against what is stored,
        # never by the model's flag (a cover email "does not hold" the PDF that was read in another call).
        for f in self.of("referenced_documents"):
            c, _ = owner(f)
            if c and f.doc in self.instrument_docs and not self.holds(f.get("name")):
                c.referenced.append(f)

    def holds(self, name) -> bool:
        """Is a document with this name (file name, contract or amendment id, or title) held by as_of?"""
        n = norm_label(name)
        if not n:
            return True
        for d in self.docs.values():
            att = d.doc.split("#", 1)[1] if "#" in d.doc else ""
            if att and (norm_label(att) == n or norm_label(att.rsplit(".", 1)[0]) == n):
                return True
        ids = {norm_label(i) for c in self.contracts.values()
               for i in ([c.msa.id] if c.msa else []) + [a.id for a in c.amendments]}
        titles = {norm_label(f.get("title")) for f in self.of("contracts") if f.get("title")}
        if n in ids or n in titles or any(i and i in n for i in ids):
            return True
        # A plain part of a held agreement ("Schedule 1", "Annex C") is held with it; a revised or new version of a
        # part ("Annex A rev 2") is a different document and is not.
        revised = re.search(r"\b(rev|revision|revised|version|v\d+|updated|amended|new|replacement)\b", str(name), re.I)
        part = re.match(r"^\s*(annex|schedule|appendix|exhibit)\s*[a-z0-9]+\b", str(name), re.I)
        return bool(part and not revised and any(c.msa for c in self.contracts.values()))

    def contract_of(self, contract_id) -> Contract | None:
        cid = norm_id(contract_id)
        if cid in self.contracts:
            return self.contracts[cid]
        for c in self.contracts.values():
            if any(a.id == cid for a in c.amendments):
                return c
        # A scan's OCR can glue a stray character to the id ("...-41E"): accept one held contract whose id the
        # value starts with, at most two characters longer. Never when two held contracts would fit.
        near = [c for k, c in self.contracts.items() if k and cid.startswith(k) and 0 < len(cid) - len(k) <= 2]
        return near[0] if len(near) == 1 else None

    # ---- shipments ----------------------------------------------------------------------------------------------------
    def pickup(self, awb: str | None, invoice_line: Fact | None = None) -> tuple[date | None, str | None, Fact | None]:
        """GLOSSARY pickup date: tracking PICKED_UP, then a carrier 'picked up' email, then the AWB date, then the
        invoice's ship date. Returns (date, source, fact)."""
        awb_n = norm_id(awb)
        if awb_n:
            for f in self.of("tracking_events"):
                if norm_id(f.get("awb")) == awb_n and norm_label(f.get("event")) in ("pickedup", "pickup"):
                    if (d := to_date(f.get("date"))):
                        return d, "tracking", f
            for f in self.of("status_events"):
                if norm_id(f.get("awb")) == awb_n and f.get("event") == "picked_up" and (d := to_date(f.get("date"))):
                    return d, "carrier_email", f
            for f in self.of("air_waybills"):
                if norm_id(f.get("awb")) == awb_n and (d := to_date(f.get("executed_date"))):
                    return d, "awb", f
        if invoice_line is not None and (d := to_date(invoice_line.get("pickup_date"))):
            return d, "invoice", invoice_line
        return None, None, None

    # ---- billing ------------------------------------------------------------------------------------------------------
    def invoices(self) -> list[tuple[Fact, list[Fact]]]:
        """(header, lines) per billing document received by as_of."""
        headers = {f.doc: f for f in self.of("invoices")}
        lines: dict[str, list[Fact]] = {}
        for f in self.of("invoice_lines"):
            lines.setdefault(f.doc, []).append(f)
        return [(headers[d], lines.get(d, [])) for d in sorted(headers)]
