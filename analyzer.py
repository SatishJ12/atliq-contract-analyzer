"""Core review pipeline: profile → rules → register conflicts → completeness → Claude.

Runs fully without an API key (rules + register + retrieval). With
ANTHROPIC_API_KEY set, Claude adds a clause-by-clause review grounded in the
same evidence, and every quote it returns is string-matched against the
contract before it is shown (unverified quotes are labelled, never hidden).
"Ask about this contract" sends the question to the v2 AI service (FastAPI on
Render, which holds the Groq key) at POST {ATLIQ_API_URL}/api/ask, so no model
key is needed here, and it works in the browser build too.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from commitments import check_commitments, precedent_matches
from completeness import check_completeness
from data_loader import (DATASET_TODAY, load_playbook_docs, load_register, match_tracker_rows,
                         related_notes)
from rules import SEV_ORDER, DocProfile, Finding, downgrade_severity, finding_ids, profile_document, run_rules

# Model choice follows the PRD / cost model (Deliverables 3 and 4):
# Haiku 4.5 for extraction-style work, Sonnet 4.6 for the risk review.
REVIEW_MODEL = os.environ.get("ATLIQ_REVIEW_MODEL", "claude-sonnet-4-6")
EXTRACT_MODEL = os.environ.get("ATLIQ_EXTRACT_MODEL", "claude-haiku-4-5")
# Free-text Q&A is answered by the v2 AI service (it holds the Groq key and runs
# llama-3.3-70b-versatile). Callers send the service's access token in X-Access-Token.
DEFAULT_ASK_API_URL = "https://atliq-contract-api.onrender.com"
ASK_TIMEOUT_S = 90  # Render's free tier sleeps when idle and takes up to ~1 min to wake

COUNSEL_VALUE_THRESHOLD = 150_000


def _get_secret(name: str) -> str | None:
    key = os.environ.get(name)
    if key:
        return key
    try:  # Streamlit Cloud secrets
        import streamlit as st

        return st.secrets.get(name)  # type: ignore[attr-defined]
    except Exception:
        return None


def _get_api_key() -> str | None:
    return _get_secret("ANTHROPIC_API_KEY")


def ask_api_url() -> str:
    """Base URL of the v2 AI service (ATLIQ_API_URL env var or secret, else the Render default)."""
    return (_get_secret("ATLIQ_API_URL") or DEFAULT_ASK_API_URL).rstrip("/")


def server_access_token() -> str | None:
    """ATLIQ_ACCESS_TOKEN kept server-side (env var or Streamlit secret); never sent to the page."""
    return _get_secret("ATLIQ_ACCESS_TOKEN")


def llm_available() -> bool:
    """Claude clause-by-clause review (ANTHROPIC_API_KEY)."""
    return bool(_get_api_key())


@dataclass
class Report:
    filename: str
    profile: DocProfile
    tracker: list[dict]
    findings: list[Finding]
    required_docs: list[dict]
    bundle: list[dict]
    precedents: list[dict]
    context_notes: list[tuple[str, str]]
    verdict: str = ""
    verdict_level: str = ""      # blockers | negotiate | clear
    escalate: list[str] = field(default_factory=list)
    llm_summary: str = ""
    llm_questions: list[str] = field(default_factory=list)
    llm_used: bool = False
    llm_error: str = ""
    value_usd: float = 0.0

    def counts(self) -> dict[str, int]:
        c = {"High": 0, "Medium": 0, "Low": 0, "Info": 0}
        for f in self.findings:
            c[f.severity] = c.get(f.severity, 0) + 1
        return c


# --------------------------------------------------------------------------- #
# Grounding check
# --------------------------------------------------------------------------- #
def _norm(s: str) -> str:
    s = s.lower().replace("’", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"[*_`|]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def quote_in_text(quote: str, text: str) -> bool:
    if not quote:
        return False
    q, t = _norm(quote).rstrip("….").strip(), _norm(text)
    if q in t:
        return True
    # tolerate ellipses inside model quotes: every fragment must appear
    parts = [x.strip() for x in re.split(r"…|\.\.\.", q) if len(x.strip()) > 15]
    return bool(parts) and all(x in t for x in parts)


# --------------------------------------------------------------------------- #
# Claude
# --------------------------------------------------------------------------- #
REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "category": {"type": "string", "enum": ["Liquidated damages", "Liability", "Indemnity", "Payment", "IP",
                                                            "Governing law", "Entity", "NDA", "Restrictive covenant", "Data protection",
                                                            "Insurance", "Termination", "Fairness", "Prior commitment", "Completeness", "Other"]},
                    "severity": {"type": "string", "enum": ["High", "Medium", "Low"]},
                    "title": {"type": "string"},
                    "clause_ref": {"type": "string"},
                    "quote": {"type": "string"},
                    "explanation": {"type": "string"},
                    "suggestion": {"type": "string"},
                    "precedent": {"type": "string"},
                },
                "required": ["category", "severity", "title", "clause_ref", "quote", "explanation", "suggestion", "precedent"],
            },
        },
        "questions_for_karandeep": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "findings", "questions_for_karandeep"],
}

SYSTEM_PROMPT = """You are the contract review assistant for AtliQ Technologies, a founder-led IT services company with no legal team. \
The CEO, Karandeep, signs every contract himself, often late at night. Your job is to make sure he knows what he is really signing.

How to work:
- Review the CONTRACT against AtliQ's playbook (Karandeep's checklist), its two-entity structure, its past negotiation positions, and the commitment register of obligations AtliQ has already signed.
- The deterministic checks have already run; their findings are listed. Do not repeat them. Add what they missed: clauses that are risky in context, interactions between clauses, unusual obligations, and anything where AtliQ's past positions suggest a counter.
- When AtliQ is the buyer (agency/freelancer paper), apply the same standard AtliQ wants for itself: flag terms Karandeep would reject if he received them. Label these "Fairness".
- Some clauses only look risky. Do not inflate severity; say so when a clause is standard.
- Every finding must include a verbatim quote copied exactly from the CONTRACT (no paraphrase, 1-3 sentences) and its clause number. If you cannot quote it, do not report it.
- Use precedents from the negotiation notes when relevant (e.g. "Acme accepted 0.5%/week of milestone capped at 5%").
- Never say a contract is "safe" or "compliant". You inform a human decision; you do not make it. This is not legal advice.
- questions_for_karandeep: the 1-4 things only a person at AtliQ can answer (facts not in the documents) before signing.
- summary: 2-3 plain-English sentences a busy CEO can read on a phone.

<playbook>
{playbook}
</playbook>

<commitment_register>
{register}
</commitment_register>
"""


def _system_blocks() -> list[dict]:
    docs = load_playbook_docs()
    playbook = "\n\n".join(f"### {name}\n{body}" for name, body in docs.items())
    register = json.dumps([{k: v for k, v in e.items() if k != "triggers"} for e in load_register()], indent=1)
    return [{"type": "text", "text": SYSTEM_PROMPT.format(playbook=playbook, register=register),
             "cache_control": {"type": "ephemeral"}}]


def _call_claude(text: str, report: Report) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=_get_api_key())
    p = report.profile
    prior = "\n".join(f"- [{f.severity}] {f.title} (cl. {f.clause_ref})" for f in report.findings) or "(none)"
    tracker = json.dumps(report.tracker, indent=1) if report.tracker else "(no tracker row matched)"
    notes = "\n\n".join(f"### {n}\n{b[:2500]}" for n, b in report.context_notes) or "(none)"
    user = f"""Today is {DATASET_TODAY.isoformat()}.

<document_profile>
file: {report.filename}
doc type: {p.doc_type}; AtliQ entity on the paper: {p.atliq_entity}; AtliQ's role: {p.atliq_role}; counterparty country: {p.counterparty_country}; governing law: {p.governing_law or 'not found'}
</document_profile>

<tracker_rows>
{tracker}
</tracker_rows>

<team_notes_about_this_counterparty>
{notes}
</team_notes_about_this_counterparty>

<deterministic_findings_already_reported>
{prior}
</deterministic_findings_already_reported>

<contract>
{text}
</contract>

Return the review as JSON matching the schema."""
    resp = client.messages.create(
        model=REVIEW_MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
        system=_system_blocks(),
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined to review this document.")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Claude's review was cut off (max_tokens). Try a shorter document.")
    body = next((b.text for b in resp.content if b.type == "text"), "")
    return json.loads(body)


def _in_browser() -> bool:
    return sys.platform == "emscripten"  # Pyodide / stlite (GitHub Pages build)


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> tuple[int, dict]:
    """POST JSON and return (status, parsed body). Status 0 means the service could not be reached."""
    data = json.dumps(payload)
    headers = {"Content-Type": "application/json", **headers}
    if _in_browser():
        # urllib has no network in Pyodide. stlite runs Python in a web worker, where a
        # synchronous XMLHttpRequest is allowed and keeps this function synchronous.
        from js import XMLHttpRequest  # type: ignore[import-not-found]

        xhr = XMLHttpRequest.new()
        xhr.open("POST", url, False)
        for k, v in headers.items():
            xhr.setRequestHeader(k, v)
        try:
            xhr.send(data)
        except Exception:
            return 0, {}
        status, body = int(xhr.status), str(xhr.responseText or "")
    else:
        req = urllib.request.Request(url, data=data.encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status, body = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read().decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, OSError):
            return 0, {}
    try:
        parsed = json.loads(body) if body else {}
    except ValueError:
        parsed = {}
    return status, parsed if isinstance(parsed, dict) else {}


def ask_about_contract(question: str, text: str, filename: str, access_token: str | None = None,
                       api_url: str | None = None) -> str:
    """Free-form Q&A grounded in the contract + register, answered by the v2 AI service."""
    base = (api_url or ask_api_url()).rstrip("/")
    token = access_token or server_access_token()
    headers = {"X-Access-Token": token} if token else {}
    status, body = _post_json(f"{base}/api/ask", {"question": question, "text": text, "filename": filename},
                              headers, ASK_TIMEOUT_S)
    if status == 200 and isinstance(body.get("answer"), str):
        return body["answer"]
    detail = body.get("detail") if isinstance(body.get("detail"), str) else ""
    tabs = " The tabs above still have every finding."
    if status == 0:
        return (f"Could not reach the AI service at {base}. Its free hosting sleeps when idle, so wait a minute "
                "and ask again." + tabs)
    if status == 401:
        return "The AI service needs its access token. Paste it under AI service settings and ask again." + tabs
    if status in (413, 422):
        return "The question or contract is too long for the AI service (question up to 1,000 characters)." + tabs
    if status == 429:
        return (detail or "The AI service's usage limit was reached. Try again later.") + tabs
    return (detail or f"The AI service returned an error ({status}).") + tabs


# --------------------------------------------------------------------------- #
# Pipeline
# --------------------------------------------------------------------------- #
def _verdict(report: Report) -> None:
    c = report.counts()
    if c["High"]:
        report.verdict_level = "blockers"
        report.verdict = f"Do not sign yet: {c['High']} blocking issue{'s' if c['High'] != 1 else ''} to resolve"
    elif c["Medium"]:
        report.verdict_level = "negotiate"
        report.verdict = f"Negotiate before signing: {c['Medium']} point{'s' if c['Medium'] != 1 else ''} to push back on"
    else:
        report.verdict_level = "clear"
        report.verdict = "No blocking issues found. Karandeep's sign-off is still required"

    esc = []
    highs = [f for f in report.findings if f.severity == "High"]
    if report.value_usd >= COUNSEL_VALUE_THRESHOLD and highs:
        esc.append(f"Deal value ${report.value_usd:,.0f} ≥ $150k with unresolved High findings")
    if any(f.category == "Prior commitment" and f.severity == "High" for f in report.findings):
        esc.append("Conflict with a signed commitment and no waiver on file")
    if any(f.category == "Completeness" and f.severity == "High" and any(k in f.title for k in ["BAA", "DPA", "Annex", "PHI"]) for f in report.findings):
        esc.append("HIPAA / GDPR document gap")
    notes = " ".join(t.get("notes", "") for t in report.tracker).lower()
    if "non-negotiable" in notes and highs:
        esc.append("Counterparty says template is non-negotiable and High findings remain")
    report.escalate = esc


def _facts_from_team_notes(report: Report) -> list[Finding]:
    """Facts that live only in meeting notes but change the risk of this document."""
    out = []
    phi_doc = any(f.category == "Completeness" and ("PHI" in f.title or "BAA" in f.title) for f in report.findings)
    for name, body in report.context_notes:
        for line in body.splitlines():
            l = line.lower()
            if phi_doc and "pune" in l and re.search(r"real data|dob|diagnosis|forwarded", l):
                out.append(Finding("Data protection", "High", "Patient data may already be in Pune, before any BAA is signed",
                                   "The team notes say a sample extract with what looks like real patient data was forwarded to engineers in Pune. "
                                   "The client's BAA forbids PHI outside the US, and no BAA is signed yet.",
                                   "Stop use of the extract, confirm with the client whether it was PHI, delete offshore copies and record it; "
                                   "assess breach-notification duties with US counsel (Calloway Stern).",
                                   clause_ref=name, quote=line.strip("- ").strip(), source="notes"))
                return out
    return out


def analyze(text: str, filename: str = "uploaded document", use_llm: bool = True) -> Report:
    if not text or not text.strip():
        raise ValueError("The contract text is empty. Paste or upload a contract with text in it.")
    rows = match_tracker_rows(text, filename)
    tracker_country = rows["client_country"].iloc[0] if len(rows) else ""
    tracker_type = rows["doc_type"].iloc[0] if len(rows) else ""
    profile = profile_document(text, tracker_country, tracker_type)

    findings = run_rules(text, profile)
    findings += check_commitments(text, profile)
    comp_findings, required, bundle = check_completeness(text, profile, rows)
    findings += comp_findings

    value = 0.0
    for v in rows["value_usd"] if len(rows) else []:
        try:
            value = max(value, float(v))
        except ValueError:
            pass

    counterparty = rows["counterparty"].iloc[0] if len(rows) else ""
    report = Report(
        filename=filename, profile=profile, tracker=rows.to_dict("records") if len(rows) else [],
        findings=findings, required_docs=required, bundle=bundle,
        precedents=precedent_matches(profile), context_notes=related_notes(counterparty) if counterparty else [],
        value_usd=value,
    )

    report.findings += _facts_from_team_notes(report)

    if use_llm and llm_available():
        try:
            data = _call_claude(text, report)
            report.llm_used = True
            report.llm_summary = data.get("summary", "")
            report.llm_questions = data.get("questions_for_karandeep", [])
            existing = {(f.clause_ref.split()[-1] if f.clause_ref else "", f.category) for f in report.findings}
            for item in data.get("findings", []):
                key = (item.get("clause_ref", "").split()[-1] if item.get("clause_ref") else "", item.get("category"))
                if key in existing:
                    continue
                f = Finding(source="claude", **item)
                f.verified = quote_in_text(f.quote, text)
                if not f.verified:
                    f.title = "[Unverified quote] " + f.title
                    f.severity = downgrade_severity(f.severity)
                report.findings.append(f)
        except Exception as exc:  # keep the deterministic report even if the API fails
            report.llm_error = f"{type(exc).__name__}: {exc}"

    report.findings.sort(key=lambda f: (SEV_ORDER.get(f.severity, 9), f.source != "register"))
    _verdict(report)
    return report


def brief_markdown(report: Report, decisions: dict | None = None) -> str:
    """Exportable Review Brief + decision log (PRD feature F7). decisions are keyed by rules.finding_ids()."""
    decisions = decisions or {}
    p = report.profile
    lines = [f"# Review Brief — {report.filename}", "",
             f"*Generated by the AtliQ Contract Risk Analyzer prototype (dataset date {DATASET_TODAY:%d %b %Y}). Not legal advice.*", "",
             f"**Status:** {report.verdict}", "",
             f"- Document: {p.doc_type} · AtliQ entity: {p.atliq_entity} · AtliQ role: {p.atliq_role} · Counterparty country: {p.counterparty_country} · Governing law: {p.governing_law or 'n/a'}"]
    if report.escalate:
        lines += ["", "**Escalate to counsel:** " + "; ".join(report.escalate)]
    if report.llm_summary:
        lines += ["", "## Summary", report.llm_summary]
    lines += ["", "## Findings"]
    for fid, f in zip(finding_ids(report.findings), report.findings):
        if f.severity == "Info":
            continue
        d = decisions.get(fid, {})
        lines += [f"### [{f.severity}] {f.title}", f"*{f.category} · {f.clause_ref} · source: {f.source}{'' if f.verified else ' · quote NOT verified'}*", ""]
        if f.quote:
            lines += [f"> {f.quote}", ""]
        lines += [f.explanation]
        if f.suggestion:
            lines += ["", f"**Suggested position:** {f.suggestion}"]
        if f.precedent:
            lines += ["", f"**Precedent:** {f.precedent}"]
        if d:
            lines += ["", f"**Decision:** {d.get('decision')} — {d.get('note', '')}"]
        lines.append("")
    if report.required_docs:
        lines += ["## Document set", "| Document | Status | Detail |", "|---|---|---|"]
        lines += [f"| {r['document']} | {r['status']} | {r['detail']} |" for r in report.required_docs]
    if report.llm_questions:
        lines += ["", "## Questions only AtliQ can answer"] + [f"- {q}" for q in report.llm_questions]
    return "\n".join(lines)
