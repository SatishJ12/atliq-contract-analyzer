"""Conflict check: does this draft collide with something AtliQ already signed?

Two layers:
1. Register rules: each obligation in commitment_register.json has a trigger
   (industry + geography + service, rate floor, keyword). These are precise and
   explainable, and they cover the cases that already hurt AtliQ.
2. Retrieval: TF-IDF similarity between the draft's clauses and every clause in
   signed_contracts/, so a reviewer (or Claude) sees the closest precedents even
   when no register rule fires.
"""
from __future__ import annotations

import re
from datetime import date

from data_loader import DATASET_TODAY, Clause, load_register, signed_clauses
from rules import GCC_TERMS, DocProfile, Finding

GCC_FLAT = {t: country for country, terms in GCC_TERMS.items() for t in terms}


def _is_active(entry: dict, today: date = DATASET_TODAY) -> bool:
    ends = entry.get("ends")
    if not ends:
        return True
    return date.fromisoformat(ends) >= today


def _lines_with(text: str, terms: list[str], limit: int = 4) -> list[str]:
    out = []
    for line in text.splitlines():
        ll = line.lower()
        if any(re.search(rf"\b{re.escape(t)}\b", ll) for t in terms):
            out.append(re.sub(r"\s+", " ", line.strip(" |*-")))
        if len(out) >= limit:
            break
    return out


def _gcc_hits(text: str) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    tl = text.lower()
    for term, country in GCC_FLAT.items():
        if re.search(rf"\b{re.escape(term)}\b", tl):
            hits.setdefault(country, []).append(term)
    # "GCC" or "Middle East" alone is a signal too
    if re.search(r"\bgcc\b|gulf cooperation council", tl):
        hits.setdefault("GCC (named)", []).append("gcc")
    return hits


def _strip_atliq_addresses(text: str) -> str:
    """Remove lines that only describe AtliQ / signatures so 'Pune' etc. don't count as scope."""
    return "\n".join(l for l in text.splitlines() if "atliq" not in l.lower())


def check_al_noor(entry: dict, text: str, p: DocProfile) -> Finding | None:
    trig = entry["triggers"]
    body = _strip_atliq_addresses(text)
    bl = body.lower()
    if not any(w in bl for w in trig["industry"]):
        return None
    if not any(w in bl for w in trig["services"]):
        return None
    gcc = _gcc_hits(body)
    if not gcc:
        return Finding("Prior commitment", "Info", "Hospitality analytics deal: Al Noor GCC non-compete checked",
                       "No GCC country, city or property found in this draft, so the Al Noor restriction (REG-01) does not appear to apply. "
                       "Confirm the property list before signing.",
                       clause_ref=entry["clause"], quote=entry["quote"], source="register")
    countries = ", ".join(sorted(gcc))
    evidence = _lines_with(body, [t for ts in gcc.values() for t in ts])
    seaside = "seaside" in bl
    return Finding(
        "Prior commitment", "High",
        f"Conflicts with Al Noor GCC non-compete (in force until 14 Sep 2029): {countries}",
        f"Signed Al Noor MSA cl. 12.1 bars AtliQ and its Affiliates from analytics/AI/revenue-management work for any 'Hospitality Business' in the GCC, "
        "wherever the work is performed. Cl. 1.11 defines that as anyone who owns or operates hotels, resorts or serviced apartments, or who provides "
        f"distribution, revenue-management or guest-analytics services to them (so hotel booking platforms count too). This draft covers that kind of work touching {countries}. "
        "The Feb 2026 waiver covered the Seaside Hotels (Muscat) SOW only" + ("" if seaside else " and does not help here") + ". "
        "Evidence in this draft: " + " / ".join(evidence[:3]),
        "Do not sign until one of: (a) a new written waiver from Al Noor under cl. 12.4 (as done for Seaside, Feb 2026); "
        "(b) GCC properties carved out of scope; or (c) counsel (Mehta Rao) confirms the restriction does not apply. Do not tell the client anything firm yet (counsel's advice, 25 Sep).",
        clause_ref=f"{entry['source_file']} cl. {entry['clause']}", quote=entry["quote"],
        precedent="22 Sep queue meeting: nobody could find the Al Noor contract; Bhavin thought it had expired. It runs to 14 Sep 2029.",
        source="register")


_RATE_RE = re.compile(r"\|\s*([A-Za-z /&()-]*?(?:engineer|developer|analyst|architect|scientist|manager|lead)[A-Za-z /&()-]*?)\s*\|\s*(?:USD\s*)?\$?\s?(\d{2,3})", re.I)


def check_crestline_mfn(entry: dict, text: str, p: DocProfile) -> Finding | None:
    if p.atliq_role != "supplier":
        return None
    card = entry["rate_card"]
    hits = []
    for role, rate in _RATE_RE.findall(text):
        r = role.strip().lower()
        r = re.sub(r"^sr\.?\s", "senior ", r)
        for card_role, floor in sorted(card.items(), key=lambda kv: -len(kv[0])):
            if card_role in r:
                if int(rate) < floor:
                    hits.append((role.strip(), int(rate), card_role, floor))
                break
    if not hits:
        return None
    detail = "; ".join(f"{r} ${x}/hr vs Crestline ${f}/hr" for r, x, _, f in hits)
    return Finding(
        "Prior commitment", "High", "Rate below Crestline's MFN floor — triggers retroactive credit",
        f"Crestline MSA cl. 6.4 (AtliQ Inc and Affiliates, until 31 Jul 2027) guarantees Crestline rates no worse than any other customer for similar services. "
        f"This draft offers: {detail}. Crestline would be owed the difference retroactively and can audit (cl. 6.5).",
        "Either hold the rate at the Crestline floor, restructure the discount (e.g. a fixed-fee milestone or volume rebate) after counsel checks it is not 'substantially similar', "
        "or price the Crestline credit into the deal.",
        clause_ref=f"{entry['source_file']} cl. 6.4", quote=entry["quote"],
        precedent="Dhaval: 'We never discount, so it's harmless — fine.' (Jul 2024). The $72 Lakeshore rate was 'ok'd on a call'.",
        source="register")


def check_northwind_pipekit(entry: dict, text: str, p: DocProfile) -> Finding | None:
    tl = text.lower()
    if "pipekit" not in tl:
        return None
    sole = bool(re.search(r"sole owner|solely own|warrants that it (is|owns)", tl))
    ev = _lines_with(text, ["pipekit"], 3)
    return Finding(
        "Prior commitment", "High" if sole else "Medium",
        "PipeKit reuse: AtliQ assigned PipeKit IP to Northwind" + (" — 'sole owner' warranty may be untrue" if sole else ""),
        "Northwind MSA cl. 9.2 vested all IP in the deliverables, 'including any … tools, frameworks, libraries and pre-existing materials incorporated', in Northwind. "
        "The Northwind pipeline incorporated PipeKit (SOW-1 S1.2). " + ("This draft has AtliQ warrant it is the sole owner of PipeKit and indemnify against breach. " if sole else "")
        + "Evidence: " + " / ".join(ev[:2]),
        "Before signing: get counsel's view on what Northwind now owns; ask Northwind for a licence-back or confirmation; meanwhile soften the warranty to "
        "'owns or is entitled to license' and cap the related indemnity.",
        clause_ref=f"{entry['source_file']} cl. 9.2", quote=entry["quote"],
        precedent="Pranav: 'PipeKit can be reused like we did for Northwind' (tracker C-028). K: 'I skimmed the IP and boilerplate' on Northwind.",
        source="register")


def check_cloudspan(entry: dict, text: str, p: DocProfile) -> Finding | None:
    tl = text.lower()
    trig = entry["triggers"]
    if not any(w in tl for w in trig["platform"]):
        return None
    if not (p.atliq_role == "partner" or any(w in tl for w in trig["partner"])):
        return None
    if "cloudspan" in tl:
        return None
    india = "india" in tl
    gcc = bool(_gcc_hits(text))
    if not (india or gcc):
        return Finding("Prior commitment", "Info", "Platform partnership outside CloudSpan's exclusive territory",
                       "CloudSpan exclusivity covers India and the GCC only.", clause_ref=entry["clause"], quote=entry["quote"], source="register")
    where = " and ".join(x for x, ok in [("India", india), ("the GCC", gcc)] if ok)
    return Finding(
        "Prior commitment", "High", f"Breaches CloudSpan partner exclusivity in {where} (until 31 Aug 2028)",
        "CloudSpan cl. 7.1 bars AtliQ and its Affiliates from acting as implementation, reseller or referral partner for any competing "
        "cloud data-warehouse / lakehouse / unified analytics platform in India or the GCC. This draft appoints AtliQ as a partner for such a platform "
        f"with a territory including {where}.",
        "Limit the territory to Europe (which K deliberately kept free in the CloudSpan deal), or exit CloudSpan first (90-day mutual termination for convenience) "
        "and weigh the 12% referral revenue and certified-engineer commitment.",
        clause_ref=f"{entry['source_file']} cl. 7.1", quote=entry["quote"],
        precedent="K on CloudSpan (Aug 2025): 'We can't do Europe — Europe is where we're growing.' Europe is free; India and GCC are not.",
        source="register")


def check_keyword(entry: dict, text: str, p: DocProfile) -> Finding | None:
    kws = entry["triggers"].get("keywords", [])
    tl = text.lower()
    if not kws or not any(re.search(rf"\b{re.escape(k)}\b", tl) for k in kws):
        return None
    if entry["id"] == "REG-04":
        return None  # handled by check_northwind_pipekit
    if entry["id"] == "REG-06":
        if p.atliq_role == "nda":
            return None
        return Finding("Prior commitment", "High", "Existing intercompany BAA does not cover this engagement",
                       "The AtliQ Inc ↔ Pvt Ltd subcontractor BAA (C-044) is scoped to the CareBridge engagement only. "
                       "If anyone outside AtliQ Inc (Pune team, freelancers) will touch PHI or de-identified data for this client, a new per-engagement subcontractor BAA is needed first.",
                       "Draft a per-engagement subcontractor BAA (Pune and every freelancer) flowing down the client BAA's restrictions before any data moves.",
                       clause_ref=f"{entry['source_file']} cl. {entry['clause']}", quote=entry["quote"],
                       precedent="Pranav: 'does the CareBridge setup cover this too?' K: 'should do'. Nobody checked (Harrington huddle, 27 Sep).",
                       source="register")
    if not _is_active(entry):
        return Finding("Prior commitment", "Info", f"{entry['type']} with {entry['counterparty']} — expired {entry['ends']}",
                       entry["plain_english"], clause_ref=f"{entry['source_file']} cl. {entry['clause']}", quote=entry["quote"], source="register")
    return Finding("Prior commitment", entry["severity"] if entry["severity"] != "Info" else "Low",
                   f"Related commitment: {entry['type']} ({entry['counterparty']})", entry["plain_english"],
                   clause_ref=f"{entry['source_file']} cl. {entry['clause']}", quote=entry["quote"], source="register")


DISPATCH = {"REG-01": check_al_noor, "REG-03": check_crestline_mfn, "REG-04": check_northwind_pipekit, "REG-05": check_cloudspan}


def check_commitments(text: str, p: DocProfile) -> list[Finding]:
    out = []
    for entry in load_register():
        fn = DISPATCH.get(entry["id"])
        if fn is None and entry.get("triggers", {}).get("keywords"):
            fn = check_keyword
        if fn is None:
            continue
        if fn is not check_keyword and not _is_active(entry):
            continue
        f = fn(entry, text, p)
        if f:
            out.append(f)
    return out


# --------------------------------------------------------------------------- #
# Retrieval over signed contracts
# --------------------------------------------------------------------------- #
_INDEX = None

RESTRICTIVE_HINTS = ["non-compet", "exclusiv", "shall not", "solicit", "favorable", "favourable", "intellectual property",
                     "assign", "restricted", "competing", "territory", "pipekit", "affiliate", "liquidated", "liability"]


def _index():
    global _INDEX
    if _INDEX is None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        docs = [c for c in signed_clauses() if len(c.text) > 80]
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True, min_df=1)
        mat = vec.fit_transform([c.heading + " " + c.text for c in docs])
        _INDEX = (vec, mat, docs)
    return _INDEX


def similar_signed_clauses(query: str, k: int = 5, min_score: float = 0.08) -> list[tuple[Clause, float]]:
    from sklearn.metrics.pairwise import cosine_similarity

    vec, mat, docs = _index()
    sims = cosine_similarity(vec.transform([query]), mat)[0]
    order = sims.argsort()[::-1][:k]
    return [(docs[i], float(sims[i])) for i in order if sims[i] >= min_score]


def precedent_matches(p: DocProfile, k_per_clause: int = 2, max_total: int = 8) -> list[dict]:
    """For the draft's risk-relevant clauses, the closest clauses AtliQ has already signed."""
    results, seen = [], set()
    for c in p.clauses:
        tl = c.text.lower()
        if len(c.text) < 80 or not any(h in tl for h in RESTRICTIVE_HINTS):
            continue
        for sc, score in similar_signed_clauses(c.text, k=k_per_clause, min_score=0.18):
            key = (sc.source, sc.ref)
            if key in seen:
                continue
            seen.add(key)
            results.append({"draft_ref": c.ref, "draft_text": c.text[:300], "signed_source": sc.source,
                            "signed_ref": sc.ref, "signed_text": sc.text[:500], "score": round(score, 2)})
    results.sort(key=lambda r: -r["score"])
    return results[:max_total]
