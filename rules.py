"""Deterministic checks: Karandeep's playbook turned into code.

These run with or without an API key. Every finding quotes the clause it is
based on, so a reviewer can check it in seconds. The LLM layer (analyzer.py)
adds judgement on top; it never replaces these.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from data_loader import Clause, split_clauses

SEV_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Info": 3}

GCC_TERMS = {
    "United Arab Emirates": ["united arab emirates", "uae", "dubai", "abu dhabi", "sharjah", "ras al khaimah"],
    "Saudi Arabia": ["saudi", "riyadh", "jeddah", "dammam", "makkah", "mecca", "medina"],
    "Qatar": ["qatar", "doha"],
    "Kuwait": ["kuwait"],
    "Bahrain": ["bahrain", "manama"],
    "Oman": ["oman", "muscat", "salalah"],
}

COUNTRY_TERMS = {
    "USA": ["united states", "usa", "u.s.", "delaware", "texas", "illinois", "ohio", "arizona",
            "california", "new jersey", "chicago", "houston", "austin", "phoenix"],
    "India": ["india", "maharashtra", "mumbai", "pune", "kochi", "kerala", "bengaluru", "new delhi"],
    "UAE": GCC_TERMS["United Arab Emirates"],
    "Saudi Arabia": GCC_TERMS["Saudi Arabia"],
    "Germany": ["germany", "gmbh", "munich", "münchen"],
    "UK": ["united kingdom", "england", "london"],
    "Singapore": ["singapore"],
}

ATLIQ_LIMITS = {"cyber_insurance_usd": 1_000_000}


@dataclass
class Finding:
    category: str
    severity: str
    title: str
    explanation: str
    suggestion: str = ""
    clause_ref: str = ""
    quote: str = ""
    precedent: str = ""
    source: str = "rules"
    verified: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DocProfile:
    doc_type: str = "Agreement"
    is_nda: bool = False
    atliq_entity: str = "Unknown"          # "Inc" | "Pvt Ltd" | "Unknown"
    atliq_label: str = ""                  # defined term for AtliQ, e.g. "Supplier"
    other_label: str = ""
    counterparty_country: str = "Unknown"
    atliq_role: str = "supplier"           # supplier | buyer | partner | nda
    governing_law: str = ""
    title: str = ""
    clauses: list[Clause] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _has(text: str, *words: str) -> bool:
    t = text.lower()
    return any(w in t for w in words)


def _num_in_parens(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"\((\d{1,4})\)", text)]


def _days_values(text: str) -> list[int]:
    vals = [int(n) for n in re.findall(r"\((\d{1,3})\)\s*(?:calendar\s+|business\s+)?days", text, re.I)]
    vals += [int(n) for n in re.findall(r"\b(\d{1,3})\s*(?:calendar\s+)?days", text, re.I)]
    return vals


def _short(text: str, n: int = 420) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def _sections(clauses: list[Clause]) -> dict[str, list[Clause]]:
    out: dict[str, list[Clause]] = {}
    for c in clauses:
        out.setdefault(c.heading, []).append(c)
    return out


def _party_paragraphs(text: str) -> tuple[str, str]:
    """Return (atliq_paragraph, other_paragraphs) from the parties block."""
    head = text[:4000]
    paras = [p for p in re.split(r"\n\s*\n|\n(?=\s*(?:\d\.\d|\d\.|\(\d\)|1\.\d)\s)", head) if p.strip()]
    atliq = [p for p in paras if "atliq" in p.lower() and ("incorporated" in p.lower() or "corporation" in p.lower() or "cin" in p.lower() or "ein" in p.lower() or "registered office" in p.lower() or "principal" in p.lower() or "office" in p.lower())]
    others = [p for p in paras if "atliq" not in p.lower() and re.search(r"incorporated|corporation|company|individual|residing|registered|GmbH|LLC|Inc\.", p, re.I)]
    return (atliq[0] if atliq else ""), "\n".join(others[:2])


def _defined_label(paragraph: str) -> str:
    labels = re.findall(r'\(\s*(?:the\s+|hereinafter\s+)?"\*{0,2}([A-Z][A-Za-z ]+?)\*{0,2}"', paragraph)
    labels = [l for l in labels if l.lower() not in {"atliq", "agreement"}]
    return labels[-1] if labels else ("AtliQ" if "atliq" in paragraph.lower() else "")


# --------------------------------------------------------------------------- #
# Profiling
# --------------------------------------------------------------------------- #
def profile_document(text: str, tracker_country: str = "", tracker_doc_type: str = "") -> DocProfile:
    p = DocProfile()
    p.clauses = split_clauses(text)
    first_heading = re.search(r"^\s*#\s+(.+)$", text, re.M)
    p.title = first_heading.group(1).strip("* ") if first_heading else text.strip().splitlines()[0][:120]
    title_l = (p.title + " " + text[:600]).lower()

    p.is_nda = _has(title_l, "non-disclosure", "nondisclosure", "confidentiality agreement") or tracker_doc_type.lower().endswith("nda")
    if p.is_nda:
        p.doc_type = "Mutual NDA" if "mutual" in title_l else "NDA"
    elif _has(title_l, "business associate"):
        p.doc_type = "HIPAA BAA"
    elif _has(title_l, "contractor agreement", "independent contractor", "consultancy agreement"):
        p.doc_type = "Contractor agreement"
    elif _has(title_l, "subcontractor"):
        p.doc_type = "Subcontractor agreement"
    elif _has(title_l, "partnership", "partner agreement"):
        p.doc_type = "Partnership agreement"
    elif _has(title_l, "statement of work", "sow"):
        p.doc_type = "SOW"
    elif _has(title_l, "pilot"):
        p.doc_type = "Pilot agreement"
    elif _has(title_l, "master", "msa"):
        p.doc_type = "MSA"
    elif _has(title_l, "services agreement"):
        p.doc_type = "Services agreement"

    atliq_para, other_para = _party_paragraphs(text)
    ap = atliq_para.lower()
    if "atliq inc" in ap or "atliq inc." in ap:
        p.atliq_entity = "Inc"
    elif "pvt" in ap or "private limited" in ap:
        p.atliq_entity = "Pvt Ltd"
    else:
        head = text[:3000].lower()
        p.atliq_entity = "Inc" if "atliq inc" in head else ("Pvt Ltd" if "atliq technologies" in head else "Unknown")
    p.atliq_label = _defined_label(atliq_para) or "AtliQ"
    p.other_label = _defined_label(other_para)

    # counterparty country: explicit tracker value wins when clean, else parties block
    tc = tracker_country.replace("?", "").strip()
    if tc:
        p.counterparty_country = {"Saudi Arabia": "Saudi Arabia", "UAE": "UAE"}.get(tc, tc)
    else:
        ol = other_para.lower()
        for country, terms in COUNTRY_TERMS.items():
            if any(re.search(rf"\b{re.escape(t)}\b", ol) for t in terms):
                p.counterparty_country = country
                break

    labels_l = (p.other_label or "").lower()
    if p.is_nda:
        p.atliq_role = "nda"
    elif labels_l in {"vendor", "contractor", "subcontractor", "consultant"} or p.doc_type in {"Contractor agreement", "Subcontractor agreement"}:
        p.atliq_role = "buyer"
    elif p.atliq_label.lower() == "partner" or p.doc_type == "Partnership agreement":
        p.atliq_role = "partner"
    else:
        p.atliq_role = "supplier"

    flat = re.sub(r"\s+", " ", text)
    m = re.search(r"governed by (?:and construed in accordance with )?(?:the )?(?:laws?|laws and regulations in force) (?:of|in) (?:the )?([A-Z][^.;,(]{2,80})", flat)
    if m:
        p.governing_law = re.sub(r"\s+", " ", m.group(1)).strip()
    return p


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #
def check_entity(p: DocProfile, text: str) -> list[Finding]:
    out = []
    if p.atliq_role == "partner":
        return out  # partner deals follow the territory, not the partner's home country
    expected = "Inc" if p.counterparty_country == "USA" else ("Pvt Ltd" if p.counterparty_country != "Unknown" else None)
    if p.atliq_entity == "Unknown":
        out.append(Finding("Entity", "Medium", "Could not tell which AtliQ entity signs",
                           "The parties block does not clearly name AtliQ Inc or AtliQ Technologies Pvt Ltd.",
                           "Name the correct entity in the parties clause and signature block."))
    elif expected and p.atliq_entity != expected:
        full = {"Inc": "AtliQ Inc (US)", "Pvt Ltd": "AtliQ Technologies Pvt Ltd (India)"}
        out.append(Finding(
            "Entity", "High", f"Wrong AtliQ entity: {full[p.atliq_entity]} for a {p.counterparty_country} counterparty",
            f"Per atliq_entities.md, AtliQ Inc serves US clients only and Pvt Ltd serves everyone else. "
            f"This draft names {full[p.atliq_entity]}, so invoicing entity, tax regime (GST vs US) and bank account will not line up.",
            f"Replace with {full[expected]} in the parties clause, signature block and notices.",
            clause_ref="Parties", quote=_short(_party_paragraphs(text)[0], 300),
            precedent="Entity/invoice mismatches caused payment delays twice in 2025 (atliq_entities.md)."))
    # invoicing entity differs from contracting entity
    other_entity_words = ("atliq technologies pvt", "atliq technologies private") if p.atliq_entity == "Inc" else ("atliq inc",)
    for c in p.clauses:
        cl = c.text.lower()
        if "invoice" in cl and any(w in cl for w in other_entity_words):
            out.append(Finding("Entity", "High", "Invoicing entity differs from the contracting entity",
                               "The contract is signed by one AtliQ entity but invoices are raised by the other.",
                               "Make the contracting party and the invoicing party the same entity.",
                               clause_ref=c.ref, quote=_short(c.text)))
    return out


def check_governing_law(p: DocProfile) -> list[Finding]:
    if not p.governing_law and p.doc_type == "SOW":
        return []  # an SOW issued under an MSA inherits the MSA's governing law
    if not p.governing_law:
        return [Finding("Governing law", "Medium", "No governing-law clause found",
                        "Could not find a 'governed by the laws of…' clause.", "Add governing law and venue.")] if not p.is_nda else []
    law = p.governing_law.lower()
    us_state = any(s in law for s in ["delaware", "texas", "illinois", "ohio", "arizona", "new york", "california", "new jersey", "state of"])
    ok = (p.atliq_entity == "Pvt Ltd" and "india" in law) or (p.atliq_entity == "Inc" and us_state)
    if ok:
        return []
    sev = "Medium"
    expl = (f"Governing law is {p.governing_law}. Karandeep's checklist: 'gov law → ours (India for Pvt Ltd, US for Inc)'. "
            "AtliQ has no presence there and would have to litigate abroad.")
    precedent = ""
    if p.atliq_entity == "Pvt Ltd" and us_state:
        sev = "Medium"
        expl = (f"A US state's law ({p.governing_law}) applied to the Indian entity. AtliQ Technologies Pvt Ltd would have to "
                "defend claims in US courts.")
    if any(k in law for k in ["england", "wales"]):
        precedent = "Brightwater (English law, signed at the airport) ended in a $9k settlement and $14.2k legal bill. Northwind's English law was accepted as 'not worth losing the deal over'."
    if any(k in law for k in ["saudi", "dubai", "emirate", "arab emirates"]):
        precedent = "Al Noor: DIFC law was accepted as the client's 'group standard'. Onshore Saudi/UAE law is a different, less predictable forum."
    return [Finding("Governing law", sev, f"Foreign governing law: {p.governing_law}", expl,
                    "Ask for Indian law with Mumbai/Pune arbitration (Pvt Ltd) or a US state (Inc); fall back to a neutral seat such as SIAC/LCIA arbitration.",
                    clause_ref="Governing law", quote=f"governed by the laws of {p.governing_law}", precedent=precedent)]


def _ld_text(p: DocProfile) -> list[Clause]:
    secs = _sections(p.clauses)
    hits = []
    for heading, cls in secs.items():
        if any(_has(c.text, "liquidated damages", "service credit", "penalty") for c in cls) or _has(heading, "liquidated", "delay"):
            hits.extend(c for c in cls if _has(c.text, "liquidated", "service credit", "delay", "penalty", "remed"))
    return hits


def check_liquidated_damages(p: DocProfile) -> list[Finding]:
    cls = _ld_text(p)
    if not cls:
        return []
    joined = " ".join(c.text for c in cls).lower()
    main = next((c for c in cls if _has(c.text, "shall pay", "entitled to", "may assess", "liquidated damages of", "service credit equal")), cls[0])
    out = []
    capped = _has(joined, "shall not exceed", "maximum of", "up to a maximum", "not exceed", "capped")
    per_day = bool(re.search(r"each (?:calendar )?day|per day|day or part day|each day", joined))
    on_total = bool(re.search(r"(total )?contract value|total fees|total contract value", joined)) and not re.search(r"milestone fee of (the|that)|affected milestone fee|relevant milestone fee|fees payable for the affected milestone", joined)
    client_excl = bool(re.search(r"caused by (the )?(client|company|customer|lakeshore|blueorchid)|for which it is responsible|attributable to (the )?(supplier|vendor|atliq|service provider)", joined)) or _has(joined, "caused by the client", "caused by the company", "attributable to the client", "act or omission of the client",
                       "caused by lakeshore", "caused by blueorchid", "attributable to the company", "delay caused by", "solely attributable",
                       "for reasons attributable to the supplier", "attributable to vendor", "attributable to atliq")
    cumulative = _has(joined, "in addition to and not in lieu", "in addition to any other right", "cumulative")

    buyer = p.atliq_role == "buyer"
    who = "the vendor" if buyer else "AtliQ"
    problems = []
    if not capped:
        problems.append("no cap")
    if per_day:
        problems.append("charged per day")
    if on_total:
        problems.append("calculated on the total contract value, not the delayed milestone")
    if not client_excl:
        problems.append("no exclusion for delay the client causes")
    if cumulative:
        problems.append("on top of actual damages (not a sole remedy)")

    if not problems:
        return [Finding("Liquidated damages", "Info", "Delay clause matches AtliQ's standard",
                        "Capped, milestone-based, client delays excluded: the same position Karandeep negotiated with Acme, Northwind and Trustline.",
                        clause_ref=main.ref, quote=_short(main.text), precedent="Acme / Northwind / Trustline: 0.5% of milestone per week, cap 5%, client delays excluded.")]

    sev = "High" if (not capped or per_day or not client_excl) else "Medium"
    cap_pct = re.findall(r"(\d{1,2})\s*%|\((\d{1,2})%\)|(\w+) per ?cent \((\d+)%\)", joined)
    if capped and not per_day and client_excl and on_total and "10%" in joined:
        sev = "Medium"
    title = ("Fairness: " if buyer else "") + "Liquidated damages: " + ", ".join(problems)
    expl = (f"{who[0].upper() + who[1:]} would owe delay damages with {', '.join(problems)}. "
            + ("This is the same clause Karandeep rejects when AtliQ is the supplier. " if buyer else "Checklist: 'LDs → cap it. never open ended'. ")
            + ("Uncapped per-day LDs on the full value can exceed the fee itself within weeks." if (per_day and not capped) else ""))
    out.append(Finding("Liquidated damages", sev, title, expl,
                       "Counter with AtliQ's standard: 0.5% of the affected milestone fee per complete week of delay attributable to the supplier, "
                       "capped at 5% of that milestone fee, no LDs for client-caused or force-majeure delay, LDs as sole remedy for delay.",
                       clause_ref=main.ref, quote=_short(main.text),
                       precedent="Brightwater: uncapped 1%/day LD + no client-delay carve-out → $9k settlement + $14.2k legal fees. "
                                 "Acme, Northwind, Trustline all accepted 0.5%/week of milestone, cap 5%. Al Noor's 10% total cap was a one-off strategic exception."))
    return out


def check_liability(p: DocProfile) -> list[Finding]:
    out = []
    buyer = p.atliq_role == "buyer"
    for c in p.clauses:
        t = c.text.lower()
        if "liab" not in t and "indemnif" not in t and "limitation or cap" not in t:
            continue
        unlimited = re.search(r"nothing in this agreement shall limit or exclude (contractor|vendor|partner|supplier|service provider)'?s liability|shall not be subject to any limitation or cap|without limitation for all damages|unlimited liability", t)
        if unlimited:
            out.append(Finding("Liability", "High", ("Fairness: " if buyer else "") + "Unlimited liability for one side",
                               "The clause removes any cap on " + ("the vendor's" if buyer else "AtliQ's") + " liability. Checklist: 'liability → 1x fees. NOT unlimited'.",
                               "Mutual cap at 1x fees paid/payable in the prior 12 months, with standard carve-outs (fraud, wilful misconduct, confidentiality) and a separate, insured super-cap for data breach.",
                               clause_ref=c.ref, quote=_short(c.text),
                               precedent="Kessler Mobility (€120k): K walked away over unlimited liability — 'one bad incident … and the company is gone'."))
            continue
        german_carveout = re.search(r"liable without limitation for damage caused intentionally or by gross negligence", t)
        if german_carveout:
            out.append(Finding("Liability", "Low", "Uncapped only for intent / gross negligence / injury (standard carve-out)",
                               "Looks alarming but is the normal German-law carve-out; the general cap still applies to ordinary negligence.",
                               "Acceptable; confirm a general cap (e.g. 1x fees) applies to everything else.", clause_ref=c.ref, quote=_short(c.text)))
            continue
        one_sided = re.search(r"cap on (client|atliq|datavane|company) liability|(client|atliq|datavane)'s (total )?aggregate liability", t)
        if one_sided:
            protected = one_sided.group(1) or one_sided.group(2)
            protected = {"atliq": "AtliQ"}.get(protected, protected.title())
            sev = "High"
            out.append(Finding("Liability", sev, ("Fairness: " if buyer else "") + f"Only {protected}'s liability is capped",
                               f"The cap protects {protected} only; the other side's exposure is open-ended.",
                               "Make the cap mutual: each party's aggregate liability limited to fees paid/payable in the prior 12 months.",
                               clause_ref=c.ref, quote=_short(c.text)))
            continue
        pct = re.search(r"(\d{3})\s*%\)?\s*of the contract value|one hundred and fifty per cent", t)
        if pct:
            out.append(Finding("Liability", "Medium", "Liability cap above 1x fees",
                               "Cap is set above the contract value. Checklist position is 1x fees.",
                               "Reduce to 1x fees paid/payable in the prior 12 months.", clause_ref=c.ref, quote=_short(c.text)))
    return out


def check_indemnity(p: DocProfile) -> list[Finding]:
    out = []
    buyer = p.atliq_role == "buyer"
    for c in p.clauses:
        t = c.text.lower()
        if "indemn" not in t:
            continue
        if re.search(r"regardless of whether such losses are caused in whole or in part by the negligence|including those arising from the negligence of|arising from the negligence of (the )?(client|company)", t):
            out.append(Finding("Indemnity", "High", ("Fairness: " if buyer else "") + "Indemnity covers the other side's own negligence",
                               "Checklist: 'indemnity → mutual. we don't cover their mistakes'. This indemnity applies even where the client's own negligence caused the loss.",
                               "Mutual indemnity: each party covers losses to the extent caused by its own breach, negligence or wilful misconduct.",
                               clause_ref=c.ref, quote=_short(c.text),
                               precedent="PayTrack (Jan 2025): K rejected 'including … negligence of PayTrack'; PayTrack accepted mutual indemnity."))
        elif re.search(r"any and all losses arising out of or relating to \(a\)", t) and not _has(t, "each party", "mutual"):
            out.append(Finding("Indemnity", "Medium", ("Fairness: " if buyer else "") + "Broad one-way indemnity",
                               "One party indemnifies for anything 'arising out of or relating to' the services, while the other side's indemnity (if any) is narrow.",
                               "Narrow to third-party claims caused by the indemnifying party's breach, negligence or IP infringement, and make it mutual.",
                               clause_ref=c.ref, quote=_short(c.text)))
    return out


def check_payment(p: DocProfile) -> list[Finding]:
    out = []
    buyer = p.atliq_role == "buyer"
    for c in p.clauses:
        t = c.text.lower()
        if not (("pay" in t and "invoice" in t) or "payment terms" in t):
            continue
        if re.search(r"conditional upon .*receipt of payment|pay[- ]when[- ]paid|after atliq receives the corresponding payment", t):
            days = max(_days_values(c.text) or [0])
            out.append(Finding("Payment", "High", "Fairness: pay-when-paid" + (f", up to {days} days" if days else ""),
                               "The vendor is only paid after the end client pays AtliQ, so it carries AtliQ's credit risk. "
                               "Karandeep's own position as a supplier is '30 days, 45 max'.",
                               "Pay within 30 days of a valid invoice, independent of the end client's payment.",
                               clause_ref=c.ref, quote=_short(c.text),
                               precedent="PixelCraft (Oct 2025): K moved a 6-person agency to 30-day payment — 'I don't want our paper to be the thing I hate receiving.'"))
            continue
        days = [d for d in _days_values(c.text) if d >= 30]
        if days and max(days) > 45:
            d = max(days)
            out.append(Finding("Payment", "Medium", ("Fairness: " if buyer else "") + f"Payment term {d} days",
                               f"Payment in {d} days; checklist says '30 days, 45 max'.",
                               "Ask for 30 days (accept up to 45).", clause_ref=c.ref, quote=_short(c.text),
                               precedent="Trustline: 90 days negotiated down to 45."))
        if re.search(r"exchange rate determined by the company at its discretion|bank charges shall be borne by the contractor", t):
            out.append(Finding("Payment", "Medium", "Fairness: currency conversion at AtliQ's discretion",
                               "Contractor is quoted in USD but paid in INR at a rate AtliQ chooses, and bears bank charges.",
                               "Pay in the contract currency (USD) or at a published reference rate; split bank charges.",
                               clause_ref=c.ref, quote=_short(c.text)))
    return out


def check_ip(p: DocProfile) -> list[Finding]:
    out = []
    if p.atliq_role in {"buyer", "nda"}:
        return out
    for c in p.clauses:
        t = c.text.lower()
        if "assign" in t and re.search(r"pre-existing materials|pre-existing materials incorporated|tools, frameworks|pre-existing intellectual", t) and not _has(t, "retain", "retains"):
            out.append(Finding("IP", "High", "AtliQ's pre-existing tools would be assigned to the client",
                               "Checklist: 'IP → client owns what we build for them, we keep our own stuff'. This clause transfers AtliQ's background IP "
                               "(accelerators, libraries) incorporated in the deliverables.",
                               "Client owns deliverables created specifically for it; AtliQ keeps pre-existing materials and grants a perpetual, non-exclusive, royalty-free licence to use them as part of the deliverables.",
                               clause_ref=c.ref, quote=_short(c.text),
                               precedent="Northwind (2025): the same clause assigned PipeKit to Northwind — it is now unclear AtliQ still owns it."))
    return out


def check_nda(p: DocProfile, text: str) -> list[Finding]:
    if not p.is_nda:
        return []
    out = []
    atliq_para, _ = _party_paragraphs(text)
    one_way = "recipient" in atliq_para.lower() or bool(re.search(r'disclosed .{0,60}by or on behalf of (the company|meridian|[A-Z]\w+) to the recipient', text, re.I))
    mutual_title = "mutual" in p.title.lower()
    if one_way and mutual_title:
        out.append(Finding("NDA", "High", "'Mutual' NDA that only binds AtliQ",
                           "The title says mutual, but AtliQ is defined as the 'Recipient' and Confidential Information is only what the other side discloses. "
                           "AtliQ's own architecture and pricing shared in the walkthrough would be unprotected.",
                           "Rewrite with reciprocal definitions (Disclosing Party / Receiving Party apply to both).",
                           clause_ref="Parties / 1.2", quote=_short(atliq_para, 260),
                           precedent="GlobalMart (Mar 2026): they sent one-way, K: 'We only sign mutual — we'll be sharing our architecture too.' They agreed."))
    elif one_way:
        out.append(Finding("NDA", "Medium", "One-way NDA (only AtliQ is bound)",
                           "Karandeep: 'I'd rather sign a mutual NDA than a one-sided one.'",
                           "Ask for a mutual NDA.", clause_ref="Parties", quote=_short(atliq_para, 260)))
    for c in p.clauses:
        t = c.text.lower()
        if re.search(r"shall not.{0,120}provide services.{0,80}(competitor|similar)", t) or (re.search(r"non-?compet", t) and "shall not" in t):
            out.append(Finding("Restrictive covenant", "High", "Non-compete hidden inside an NDA",
                               "This clause stops AtliQ serving the counterparty's competitors after the NDA ends. That is a business restriction, not confidentiality, and it would join the commitment register.",
                               "Delete. Confidentiality obligations already protect their information.",
                               clause_ref=c.ref, quote=_short(c.text)))
        if re.search(r"continue in perpetuity|in perpetuity", t):
            out.append(Finding("NDA", "Low", "Confidentiality lasts forever",
                               "Perpetual obligations are hard to administer; 3-5 years (trade secrets longer) is AtliQ's usual term.",
                               "Limit to 3-5 years from disclosure, trade secrets for as long as they remain secret.", clause_ref=c.ref, quote=_short(c.text)))
        hrs = re.search(r"within (\w+) \((\d+)\) hours", t)
        if hrs and int(hrs.group(2)) <= 12:
            out.append(Finding("NDA", "Low", f"{hrs.group(2)}-hour breach notification",
                               "Very short notification window for a services vendor.", "Ask for 'without undue delay and in any event within 72 hours'.",
                               clause_ref=c.ref, quote=_short(c.text)))
    return out


def check_restrictive_covenants(p: DocProfile) -> list[Finding]:
    out = []
    if p.is_nda:
        return out
    buyer = p.atliq_role == "buyer"
    lbl = (p.atliq_label or "AtliQ").lower()
    for c in p.clauses:
        t = c.text.lower()
        if not re.search(r"non-?compet|exclusiv|shall not.{0,80}(solicit|provide any|market to|act as)|devote .* exclusively", t):
            continue
        if re.search(r"exclusive of|exclusive jurisdiction|non-exclusive|sole and exclusive remedy|exclusive property|exclusive, perpetual|exclusive place", t) and not re.search(r"non-?compet|devote|shall not", t):
            continue
        if buyer:
            if re.search(r"devote .* exclusively|anywhere in the world|non-?compet", t):
                kind = "worldwide post-term non-compete" if re.search(r"anywhere in the world|after termination|after.{0,20}expiry", t) else "full-time exclusivity"
                out.append(Finding("Fairness", "High", f"Fairness: {kind} on a freelancer",
                                   "Bars the contractor from other work during and after the engagement. Heavy for an individual; post-term non-competes are also widely unenforceable (India: Contract Act s.27; many US states restrict them).",
                                   "Drop exclusivity and the post-term non-compete; keep confidentiality and a narrow non-solicit of AtliQ's clients the contractor served.",
                                   clause_ref=c.ref, quote=_short(c.text)))
            continue
        binds_atliq = lbl in t or "partner" in t or "atliq" in t or "supplier" in t or "service provider" in t
        if binds_atliq and re.search(r"shall not.{0,200}(solicit|provide|market|act as)", t) and not re.search(r"neither party shall solicit|neither party shall.{0,40}solicit", t):
            months = _num_in_parens(c.text)
            out.append(Finding("Restrictive covenant", "High", "New restriction on AtliQ's future business",
                               "This clause limits who AtliQ can work for" + (f" (up to {max(months)} months)" if months else "") + ". If signed it must be added to the commitment register.",
                               "Delete, or limit to active solicitation of named accounts AtliQ was introduced to, for the term only.",
                               clause_ref=c.ref, quote=_short(c.text)))
    return out


def check_insurance(p: DocProfile, text: str) -> list[Finding]:
    out = []
    for c in p.clauses:
        t = c.text.lower()
        if "insurance" not in t:
            continue
        amounts = [int(a.replace(",", "")) for a in re.findall(r"\$\s?([\d,]{7,})", c.text)]
        if "five million" in t:
            amounts.append(5_000_000)
        if not amounts:
            continue
        top = max(amounts)
        if "cyber" in t and top > ATLIQ_LIMITS["cyber_insurance_usd"]:
            out.append(Finding("Insurance", "High", f"Requires ${top:,.0f} cyber cover; AtliQ holds $1M",
                               "Karandeep (Harrington huddle, 27 Sep): 'Our cyber policy is $1M btw'. Signing would put AtliQ in breach on day one.",
                               "Either negotiate the limit to $1M-2M, or get a quote to raise cover before signing (cost goes into the deal price).",
                               clause_ref=c.ref, quote=_short(c.text)))
        elif top > 1_000_000:
            out.append(Finding("Insurance", "Medium", f"Insurance requirement up to ${top:,.0f}",
                               "Confirm AtliQ's current policies meet these limits before signing.",
                               "Check the policy schedule; negotiate limits to what AtliQ already holds.", clause_ref=c.ref, quote=_short(c.text)))
    return out


def check_termination(p: DocProfile) -> list[Finding]:
    out = []
    buyer = p.atliq_role == "buyer"
    for c in p.clauses:
        t = c.text.lower()
        if "terminat" in t and re.search(r"no obligation to pay for work in progress|sole obligation shall be to pay fees for deliverables accepted", t):
            out.append(Finding("Termination", "Medium", ("Fairness: " if buyer else "") + "Termination for convenience without paying for work done",
                               "Checklist: 'termination → they pay for work done'. Work in progress would go unpaid.",
                               "Pay for all services performed up to termination plus non-cancellable costs; give at least 30 days' notice.",
                               clause_ref=c.ref, quote=_short(c.text)))
    return out


def check_template_mismatch(p: DocProfile, text: str) -> list[Finding]:
    out = []
    t = text.lower()
    if p.atliq_entity == "Pvt Ltd" and p.counterparty_country == "USA" and re.search(r"\bpan\b|gstin", _party_paragraphs(text)[1].lower() + t[-1500:]):
        out.append(Finding("Entity", "High", "India template sent to a US party",
                           f"The draft asks a US resident for an Indian PAN/GSTIN, pays in INR and is governed by {p.governing_law or 'Indian'} law with Indian courts. "
                           "It was built from the India template with 'only name and rate changed' (tracker C-040).",
                           "Use the AtliQ Inc US contractor template (as used for Daniel Ortiz): USD payment by ACH, US law, W-9.",
                           clause_ref="Parties / Schedule", quote=_short(_party_paragraphs(text)[1], 260)))
    return out


ALL_CHECKS = [check_entity, check_governing_law, check_liquidated_damages, check_liability, check_indemnity,
              check_payment, check_ip, check_nda, check_restrictive_covenants, check_insurance, check_termination,
              check_template_mismatch]


def run_rules(text: str, profile: DocProfile) -> list[Finding]:
    findings: list[Finding] = []
    for fn in ALL_CHECKS:
        try:
            if fn.__code__.co_argcount == 2:
                findings.extend(fn(profile, text))
            else:
                findings.extend(fn(profile))
        except Exception as exc:  # a broken rule should never break the report
            findings.append(Finding("System", "Info", f"Rule {fn.__name__} failed", str(exc)))
    # de-duplicate same title + clause
    seen, unique = set(), []
    for f in findings:
        key = (f.title, f.clause_ref)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return sorted(unique, key=lambda f: SEV_ORDER.get(f.severity, 9))
