"""Document-set completeness: which papers does this deal need, and are they there?

Deterministic on purpose. Rules come from the dataset README and the
CareBridge bundle (NDA + MSA + BAA + intercompany subcontractor BAA), which is
the one deal AtliQ is known to have set up correctly.
"""
from __future__ import annotations

import re

import pandas as pd

from data_loader import load_tracker
from rules import HEALTHCARE_CLIENT_NAMES, DocProfile, Finding

PHI_TERMS = ["protected health information", "phi", "hipaa", "patient", "electronic health record", "ehr",
             "diagnosis", "clinical", "readmission", "business associate"]
GDPR_TERMS = ["gdpr", "regulation (eu) 2016/679", "art. 28", "standard contractual clauses"]
EU_COUNTRIES = ["germany", "france", "netherlands", "spain", "italy", "ireland", "belgium", "austria", "sweden",
                "denmark", "poland", "finland", "portugal"]


def _has_word(text: str, term: str) -> bool:
    return bool(re.search(rf"\b{re.escape(term)}\b", text))


def _bundle(rows: pd.DataFrame) -> list[dict]:
    return [
        {"id": r.contract_id, "doc_type": r.doc_type, "status": r.status or "(blank)", "signed": r.signed_date,
         "notes": r.notes}
        for r in rows.itertuples()
    ]


def _doc_present(rows: pd.DataFrame, needle: str) -> pd.DataFrame:
    return rows[rows["doc_type"].str.contains(needle, case=False, regex=False)]


def missing_attachments(text: str) -> list[Finding]:
    """References like 'attached as Annex 3' where no Annex 3 section exists."""
    out = []
    refs = set(re.findall(r"(Annex(?:ure)?|Schedule|Exhibit|Appendix)\s+([A-Z0-9]{1,2})\b", text))
    for kind, label in sorted(refs):
        heading = re.search(rf"^\s*#{{1,4}}\s*\**{kind}\s+{label}\b", text, re.M | re.I) or \
                  re.search(rf"^\s*\**{kind.upper()}\s+{label}\b", text, re.M)
        if heading:
            continue
        lines = [l.strip(" -*|") for l in text.splitlines() if re.search(rf"\b{kind}\s+{label}\b", l)]
        sentence = min(lines, key=len) if lines else f"{kind} {label}"
        ctx_all = " ".join(lines).lower()
        critical = any(re.search(rf"{kind.lower()}\s+{label.lower()}\W{{0,6}}\(?[^)]{{0,10}}({w})", ctx_all) or
                       re.search(rf"({w})[^.;]{{0,60}}{kind.lower()}\s+{label.lower()}\b", ctx_all)
                       for w in ["data processing", "dpa", "business associate", "rate card", "statement of work", "sow", "security"])
        out.append(Finding("Completeness", "High" if critical else "Low", f"{kind} {label} is referenced but not attached",
                           "The contract incorporates a document that is not in this draft, so you would be agreeing to terms you have not seen.",
                           f"Ask for {kind} {label} before signing and review it with the main agreement.",
                           clause_ref=f"{kind} {label}", quote=sentence[:400]))
    return out


def check_completeness(text: str, p: DocProfile, tracker_rows: pd.DataFrame) -> tuple[list[Finding], list[dict], list[dict]]:
    """Returns (findings, required_documents checklist, tracker bundle)."""
    tl = text.lower()
    findings: list[Finding] = []
    required: list[dict] = []
    df = load_tracker()
    rows = tracker_rows if tracker_rows is not None else df.iloc[0:0]
    counterparty = rows["counterparty"].iloc[0] if len(rows) else ""

    phi = sum(_has_word(tl, t) for t in PHI_TERMS) >= 2
    gdpr = any(t in tl for t in GDPR_TERMS) or (p.counterparty_country.lower() in EU_COUNTRIES and "personal data" in tl)

    def req(doc: str, present: bool, detail: str):
        required.append({"document": doc, "status": "Present" if present else "Missing", "detail": detail})

    # --- healthcare bundle -------------------------------------------------
    if phi and p.atliq_role in {"supplier", "nda"}:
        nda = _doc_present(rows, "NDA")
        baa = _doc_present(rows, "BAA")
        msa = rows[rows["doc_type"].str.contains("MSA|Services", case=False, regex=True)]
        req("NDA", len(nda) > 0, ", ".join(f"{r.contract_id} ({r.status})" for r in nda.itertuples()) or "none in tracker")
        req("Services agreement / MSA", len(msa) > 0 or p.doc_type in {"MSA", "Services agreement"},
            ", ".join(f"{r.contract_id} ({r.status})" for r in msa.itertuples()) or "this document")
        signed_baa = baa[baa["status"].str.lower() == "signed"]
        req("HIPAA BAA (signed together with the MSA)", len(signed_baa) > 0 or p.doc_type == "HIPAA BAA",
            ", ".join(f"{r.contract_id} ({r.status})" for r in baa.itertuples()) or "none in tracker")
        sub = df[df["doc_type"].str.contains("Subcontractor BAA", case=False) & df["notes"].str.contains(counterparty.split()[0] if counterparty else "zzz", case=False)]
        req("Subcontractor BAA for every party touching PHI (Pune team, freelancers)", len(sub) > 0,
            "Existing intercompany BAA C-044 covers CareBridge only" if len(sub) == 0 else ", ".join(sub["contract_id"]))
        if len(signed_baa) == 0 and p.doc_type != "HIPAA BAA":
            findings.append(Finding("Completeness", "High", "HIPAA BAA not signed",
                                    "This deal involves PHI. No signed BAA with this client exists in the tracker; the MSA alone does not authorise AtliQ to receive PHI.",
                                    "Sign the BAA together with the MSA, and stop any PHI transfer until it is signed.", clause_ref="Tracker"))
        if len(sub) == 0:
            findings.append(Finding("Completeness", "High", "No subcontractor BAA for people who will touch the data",
                                    "HIPAA requires the same restrictions to flow down to every subcontractor (Pune team via an intercompany BAA, each freelancer via a subcontractor BAA) before data changes hands.",
                                    "Draft per-engagement subcontractor BAAs (intercompany + each freelancer) mirroring the client BAA, signed before access.",
                                    clause_ref="Tracker / C-044",
                                    precedent="CareBridge (2025) did this right: NDA + MSA + BAA + intercompany subcontractor BAA."))
        if re.search(r"outside the united states", tl):
            findings.append(Finding("Completeness", "High", "PHI must stay in the US — check who already has the data",
                                    "This draft forbids PHI outside the US. The Pune team cannot work on identifiable data for this client.",
                                    "Confirm no PHI has left the US; delete any copies offshore; staff PHI work with named US personnel only.",
                                    clause_ref="Offshore restriction", quote=re.search(r"[^.\n]*outside the united states[^.\n]*", text, re.I).group(0)[:400]))

    # --- contractor / subcontractor on a healthcare project -----------------
    if p.atliq_role == "buyer" and phi:
        upstream = re.search("|".join(re.escape(n) for n in HEALTHCARE_CLIENT_NAMES), tl)
        upstream_name = upstream.group(0).title() if upstream else "the healthcare client"
        own_baa = _doc_present(rows, "BAA")
        req(f"Subcontractor BAA between AtliQ and this contractor (flows down {upstream_name}'s BAA)", len(own_baa) > 0,
            "none in tracker" if len(own_baa) == 0 else ", ".join(own_baa["contract_id"]))
        if len(own_baa) == 0:
            findings.append(Finding("Completeness", "High", f"Missing subcontractor BAA — contractor will work on {upstream_name} health data",
                                    f"The engagement covers {upstream_name}'s EHR/patient systems. Being US-based solves the offshore restriction but not HIPAA: "
                                    "a subcontractor BAA with the same restrictions as the client BAA must be signed before access.",
                                    "Add a subcontractor BAA to this contractor's paperwork (alongside the contractor agreement and NDA) before any access to PHI.",
                                    clause_ref="Schedule / Project",
                                    quote=(re.search(r"[^\n]*(electronic health record|patient)[^\n]*", text, re.I).group(0)[:400]
                                           if re.search(r"electronic health record|patient", text, re.I) else ""),
                                    precedent="Dhaval: 'US-based, so the offshore thing is solved.' (Harrington huddle) — offshore yes, HIPAA no."))

    # --- GDPR -----------------------------------------------------------------
    if gdpr:
        dpa_in_tracker = _doc_present(rows, "DPA")
        attached = bool(re.search(r"^\s*#{1,4}\s*(annex|schedule|exhibit)\s+\w+\s*[—-]\s*data processing", text, re.M | re.I))
        req("GDPR Art. 28 Data Processing Agreement + SCCs for transfer to India", attached or len(dpa_in_tracker) > 0,
            "attached" if attached else ("tracker: " + ", ".join(dpa_in_tracker["contract_id"]) if len(dpa_in_tracker) else "referenced but not attached; none in tracker"))

    # --- generic -------------------------------------------------------------
    if p.atliq_role == "supplier" and not phi and len(rows):
        nda = _doc_present(rows, "NDA")
        if len(nda):
            req("NDA", True, ", ".join(f"{r.contract_id} ({r.status})" for r in nda.itertuples()))

    findings.extend(missing_attachments(text))
    return findings, required, _bundle(rows)
