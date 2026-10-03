"""AtliQ Contract Risk Analyzer — Streamlit prototype (Deliverable 5).

Run:  streamlit run app.py
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

import pandas as pd
import streamlit as st

from analyzer import (EXTRACT_MODEL, REVIEW_MODEL, Report, analyze, ask_about_contract, brief_markdown,
                      llm_available)
from data_loader import DATASET_TODAY, extract_text_from_upload, list_incoming, load_register, load_tracker, read_text

st.set_page_config(page_title="AtliQ Contract Risk Analyzer", page_icon="📑", layout="wide")

SEV_ICON = {"High": "🔴", "Medium": "🟠", "Low": "🔵", "Info": "⚪"}
DECISIONS = ["Not reviewed", "Negotiate", "Accept risk (documented exception)", "Escalate to counsel", "Not applicable"]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner=False)
def cached_analyze(text: str, filename: str, use_llm: bool) -> Report:
    return analyze(text, filename, use_llm=use_llm)


def esc(s: str) -> str:
    """Streamlit markdown treats $...$ as LaTeX; escape dollar signs in contract text."""
    return (s or "").replace("$", "\\$")


ACRONYMS = {"Msa": "MSA", "Sow2": "SOW-2", "Nda": "NDA", "Baa": "BAA"}


def pretty(name: str) -> str:
    return " ".join(ACRONYMS.get(w, w) for w in name.title().split())


MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def deadline_from_notes(notes: str) -> date | None:
    m = re.search(r"(?:by|before)\s+(?:thu\s+|mon\s+|fri\s+)?(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", notes.lower())
    if not m:
        return None
    return date(2026, MONTHS[m.group(2)], int(m.group(1)))


def incoming_label(path) -> str:
    rows = cached_analyze(read_text(path), path.name, False).tracker
    name = pretty(path.stem.split("_", 1)[1].replace("_draft", "").replace("_", " "))
    dl = None
    for r in rows:
        dl = deadline_from_notes(r.get("notes", "")) or dl
    return f"{name}" + (f"  (due {dl:%d %b})" if dl else "")


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.title("📑 AtliQ Contract Risk Analyzer")
    st.caption(f"Prototype on the synthetic AtliQ dataset. Dataset 'today' = {DATASET_TODAY:%d %b %Y}. Not legal advice.")
    if llm_available():
        st.success(f"Claude review on\n\nReview: `{REVIEW_MODEL}`")
        use_llm = st.toggle("Add Claude clause-by-clause review", value=True,
                            help="Rules, commitment register and completeness checks always run. Claude adds context-aware findings; every quote is string-matched against the contract.")
    else:
        if os.environ.get("ATLIQ_BROWSER_BUILD") == "1":
            st.info("Rules + register mode (runs entirely in your browser). The Claude review needs the server version with an API key.")
        else:
            st.info("Rules + register mode. Set `ANTHROPIC_API_KEY` to add Claude's clause-by-clause review.")
        use_llm = False

    st.divider()
    source = st.radio("Contract to review", ["Incoming draft (dataset)", "Upload a contract"], label_visibility="visible")
    text, filename = "", ""
    if source == "Incoming draft (dataset)":
        files = list_incoming()
        if not files:
            st.error("No dataset found. Put the dataset in ./data (see README).")
        else:
            labels = {incoming_label(p): p for p in files}
            default = next((i for i, k in enumerate(labels) if "Gulf Crown" in k), 0)
            choice = st.selectbox("Draft awaiting review", list(labels), index=default)
            path = labels[choice]
            text, filename = read_text(path), path.name
    else:
        browser_build = os.environ.get("ATLIQ_BROWSER_BUILD") == "1"
        types = ["docx", "txt", "md"] if browser_build else ["pdf", "docx", "txt", "md"]
        up = st.file_uploader(("Word (.docx), .txt or .md" if browser_build else "PDF, Word (.docx), .txt or .md"), type=types)
        if browser_build:
            st.caption("This in-browser version reads Word, text and Markdown. PDF upload needs the server version (see README).")
        if up is not None:
            try:
                text, filename = extract_text_from_upload(up.name, up.getvalue()), up.name
            except Exception as exc:
                st.error(f"Could not read that file: {exc}")
            if text and len(text.strip()) < 200:
                st.warning("Very little text was extracted. If this is a scanned PDF it needs OCR first.")


tab_review, tab_register, tab_queue, tab_about = st.tabs(["Review a contract", "Commitment register", "Contract queue", "How it works"])

# --------------------------------------------------------------------------- #
# Review tab
# --------------------------------------------------------------------------- #
with tab_review:
    if not text:
        st.info("Pick an incoming draft or upload a contract in the sidebar.")
    else:
        with st.spinner("Reviewing… (rules, commitment register, document set" + (", Claude" if use_llm else "") + ")"):
            report = cached_analyze(text, filename, use_llm)
        p = report.profile
        c = report.counts()

        cp = report.tracker[0]["counterparty"] if report.tracker else ""
        st.subheader((f"{cp} — " if cp else "") + (p.title.title() if p.title.isupper() else p.title))
        st.caption(f"`{filename}`" + (" · tracker " + ", ".join(t["contract_id"] for t in report.tracker) if report.tracker else " · no tracker match"))
        box = {"blockers": st.error, "negotiate": st.warning, "clear": st.info}[report.verdict_level]
        box(f"**{report.verdict}.**  This tool flags; Karandeep decides.")
        if report.escalate:
            st.warning("**Escalate to counsel:** " + esc(" · ".join(report.escalate)))
        if report.llm_error:
            st.caption(f"Claude review unavailable for this run ({report.llm_error}). Showing deterministic checks only.")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("🔴 High", c["High"])
        m2.metric("🟠 Medium", c["Medium"])
        m3.metric("🔵 Low", c["Low"])
        m4.metric("Deal value", f"${report.value_usd:,.0f}" if report.value_usd else "—")
        dl = None
        for r in report.tracker:
            dl = deadline_from_notes(r.get("notes", "")) or dl
        m5.metric("Due", f"{dl:%d %b}" if dl else "—", delta=f"{(dl - DATASET_TODAY).days} days left" if dl else None, delta_color="off")

        st.markdown(
            f"**Document:** {p.doc_type} &nbsp;·&nbsp; **AtliQ entity on the paper:** {p.atliq_entity} &nbsp;·&nbsp; "
            f"**AtliQ is the:** {p.atliq_role} &nbsp;·&nbsp; **Counterparty country:** {p.counterparty_country} &nbsp;·&nbsp; "
            f"**Governing law:** {p.governing_law or 'not stated'}"
        )
        if report.llm_summary:
            st.markdown(f"> {esc(report.llm_summary)}")
        highs = [f for f in report.findings if f.severity == "High"]
        if highs:
            st.markdown("**Blocking issues**\n" + "\n".join(f"- {esc(f.title)}" for f in highs))

        t_commit, t_find, t_docs, t_prec, t_brief = st.tabs(
            ["Prior commitments", "Clause risks", "Document set", "Precedents & team notes", "Review brief & decisions"])

        decisions_key = f"decisions::{filename}"
        decisions = st.session_state.setdefault(decisions_key, {})

        def render_finding(i: int, f):
            badge = {"rules": "playbook rule", "register": "commitment register", "claude": "Claude", "notes": "team notes"}.get(f.source, f.source)
            with st.expander(f"{SEV_ICON.get(f.severity, '')} **{f.severity}** · {esc(f.title)}", expanded=f.severity == "High"):
                st.caption(esc(f"{f.category} · {f.clause_ref or '—'} · source: {badge}") + ("" if f.verified else " · ⚠️ quote not found in contract"))
                if f.quote:
                    st.markdown(f"> {esc(f.quote)}")
                st.markdown(esc(f.explanation))
                if f.suggestion:
                    st.markdown(f"**Suggested position:** {esc(f.suggestion)}")
                if f.precedent:
                    st.markdown(f"**Precedent:** {esc(f.precedent)}")
                if f.severity in {"High", "Medium"}:
                    col1, col2 = st.columns([1, 2])
                    cur = decisions.get(i, {})
                    d = col1.selectbox("Decision", DECISIONS, index=DECISIONS.index(cur.get("decision", "Not reviewed")), key=f"d-{filename}-{i}")
                    n = col2.text_input("Note / reason", value=cur.get("note", ""), key=f"n-{filename}-{i}")
                    if d != "Not reviewed" or n:
                        decisions[i] = {"decision": d, "note": n, "title": f.title, "severity": f.severity}

        with t_find:
            shown = [(i, f) for i, f in enumerate(report.findings) if f.category not in {"Prior commitment"}]
            if not shown:
                st.write("No clause-level issues found.")
            for i, f in shown:
                render_finding(i, f)

        with t_commit:
            st.caption("Checked against the commitment register built from the 17 signed contracts (see the Commitment register tab).")
            pc = [(i, f) for i, f in enumerate(report.findings) if f.category == "Prior commitment"]
            if not pc:
                st.write("No conflicts with existing commitments were found.")
            for i, f in pc:
                render_finding(i, f)

        with t_docs:
            if report.required_docs:
                st.markdown("**Documents this deal needs**")
                df = pd.DataFrame(report.required_docs)
                df["status"] = df["status"].map(lambda s: ("✅ " if s == "Present" else "❌ ") + s)
                st.dataframe(df, hide_index=True, width="stretch")
            else:
                st.write("No special document-set requirements detected (no PHI / GDPR signals).")
            if report.bundle:
                st.markdown("**What the tracker holds for this counterparty**")
                st.dataframe(pd.DataFrame(report.bundle), hide_index=True, width="stretch")

        with t_prec:
            if report.context_notes:
                st.markdown("**What the team already knows (meeting & negotiation notes)**")
                for name, body in report.context_notes:
                    with st.expander(name):
                        st.markdown(esc(body))
            if report.precedents:
                st.markdown("**Closest clauses AtliQ has already signed** (TF-IDF retrieval over signed_contracts/)")
                for r in report.precedents:
                    with st.expander(f"Draft cl. {r['draft_ref']} ↔ {r['signed_source']} cl. {r['signed_ref']}  (similarity {r['score']})"):
                        st.markdown(f"**This draft:** {esc(r['draft_text'])}…")
                        st.markdown(f"**Signed:** {esc(r['signed_text'])}…")

        with t_brief:
            md = brief_markdown(report, decisions)
            open_high = sum(1 for i, f in enumerate(report.findings) if f.severity == "High" and decisions.get(i, {}).get("decision", "Not reviewed") == "Not reviewed")
            if open_high:
                st.warning(f"{open_high} High finding(s) still have no logged decision.")
            st.download_button("Download review brief (.md)", md, file_name=f"review_brief_{filename.rsplit('.', 1)[0]}.md")
            st.download_button("Download decision log (.json)", json.dumps(decisions, indent=2), file_name=f"decisions_{filename.rsplit('.', 1)[0]}.json")
            st.markdown(esc(md))

        st.divider()
        q = st.text_input("Ask about this contract", placeholder="e.g. Does the Al Noor waiver help here? Who owns the models we build?")
        if q:
            with st.spinner("Thinking…"):
                st.markdown(esc(ask_about_contract(q, text, report)))

# --------------------------------------------------------------------------- #
# Register tab
# --------------------------------------------------------------------------- #
with tab_register:
    st.subheader("What AtliQ has already promised")
    st.caption("Built from the 17 signed contracts. Each entry quotes the clause it comes from. "
               "The tracker's restrictive_clauses column is blank or 'none' for every one of these.")
    reg = load_register()
    rows = []
    for e in reg:
        active = (not e.get("ends")) or date.fromisoformat(e["ends"]) >= DATASET_TODAY
        rows.append({"ID": e["id"], "Severity": e["severity"], "Type": e["type"], "Counterparty": e["counterparty"],
                     "Binds": e["binds"].split(" (")[0], "In force until": e.get("ends") or "—",
                     "Status": "Active" if active else "Expired", "Source": f"{e['source_file']} cl. {e['clause']}"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    for e in reg:
        with st.expander(f"{SEV_ICON.get(e['severity'], '')} {e['id']} · {e['type']} — {e['counterparty']}"):
            st.markdown(f"> {esc(e['quote'])}")
            st.markdown(esc(e["plain_english"]))
            st.caption(esc(f"Binds: {e['binds']} · {e['ends_note']}"))
            if e.get("exceptions"):
                st.caption(esc(f"Exceptions / history: {e['exceptions']}"))

# --------------------------------------------------------------------------- #
# Queue tab
# --------------------------------------------------------------------------- #
with tab_queue:
    st.subheader("Contracts waiting on Karandeep")
    st.caption("Tracker rows in review, draft or with a blank status, ordered by the deadline found in the notes, with a quick rules-only scan of each draft.")
    tr = load_tracker()
    q = tr[tr["status"].isin(["In review", "Draft", "", "Awaiting client"])].copy()
    q["deadline"] = q["notes"].map(deadline_from_notes)
    scans: dict[str, Report] = {}
    for pth in list_incoming():
        r = cached_analyze(read_text(pth), pth.name, False)
        dt = r.profile.doc_type
        for t in r.tracker:
            if t["status"] == "Signed":
                continue
            row_type = t["doc_type"].lower()
            if "BAA" in dt:
                ok = "baa" in row_type
            elif r.profile.is_nda:
                ok = "nda" in row_type
            elif "Contractor" in dt:
                ok = "contractor" in row_type
            else:
                ok = "baa" not in row_type and "nda" not in row_type
            if ok:
                scans[t["contract_id"]] = r
    q["High"] = q["contract_id"].map(lambda cid: scans[cid].counts()["High"] if cid in scans else None)
    q["Status (scan)"] = q["contract_id"].map(lambda cid: scans[cid].verdict if cid in scans else "no draft in dataset")
    q = q.sort_values("deadline", na_position="last")
    st.dataframe(q[["contract_id", "counterparty", "doc_type", "atliq_entity", "client_country", "value_usd", "deadline", "High", "Status (scan)", "notes"]],
                 hide_index=True, width="stretch")

# --------------------------------------------------------------------------- #
# About tab
# --------------------------------------------------------------------------- #
with tab_about:
    st.markdown(f"""
### What it checks
1. **Clause risk vs Karandeep's playbook** — LDs, liability, indemnity, payment, IP, termination, NDAs (deterministic rules quoting the clause).
2. **Entity & governing law** — AtliQ Inc for US clients, Pvt Ltd for everyone else (`atliq_entities.md`).
3. **Prior commitments** — the draft vs the commitment register built from signed contracts (Al Noor GCC non-compete, Crestline MFN, Northwind PipeKit assignment, CloudSpan exclusivity, HIPAA scope), plus TF-IDF retrieval of the closest signed clauses.
4. **Document set** — NDA + MSA + BAA + subcontractor BAAs for PHI; DPA + SCCs for GDPR; attachments that are referenced but missing.
5. **Fairness** — when AtliQ is the buyer, the same standard it asks for itself.
6. **Claude review (optional)** — `{REVIEW_MODEL}` adds context-aware findings with verbatim quotes; any quote not found in the contract is labelled and downgraded.

### Guardrails
- Every finding carries a clause reference and a quote; Claude quotes are string-matched.
- No green "safe to sign" state. The best status is "no blocking issues found, sign-off still required".
- High findings ask for a logged human decision; escalation to counsel is suggested for ≥$150k deals with open Highs, signed-commitment conflicts, HIPAA/GDPR gaps, and non-negotiable templates.
- Synthetic data only. Nothing is sent to counterparties.
""")
