"""Regression tests for the 6 Oct 2026 code review findings (deterministic layer, no API key needed)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import commitments  # noqa: E402
from analyzer import analyze, brief_markdown  # noqa: E402
from data_loader import INCOMING_DIR, read_text  # noqa: E402
from rules import (DocProfile, Finding, check_governing_law, downgrade_severity, finding_ids, is_us_law,  # noqa: E402
                   profile_document)


@pytest.mark.parametrize("text", ["", "   ", "\n\t\n"])
def test_empty_text_is_refused_with_a_clear_message(text):
    with pytest.raises(ValueError, match="empty"):
        analyze(text, "blank.txt", use_llm=False)
    with pytest.raises(ValueError, match="empty"):
        profile_document(text)


def test_text_without_a_heading_still_gets_a_title():
    r = analyze("Services agreement between AtliQ Inc and a client.\nMore text.", "x.txt", use_llm=False)
    assert r.profile.title.startswith("Services agreement")


@pytest.mark.parametrize("law,us", [
    ("the State of Qatar", False), ("the State of Kuwait", False), ("England and Wales", False), ("India", False),
    ("the State of New York", True), ("Delaware", True), ("the State of Washington", True), ("the United States", True),
])
def test_us_law_matches_real_states_only(law, us):
    assert is_us_law(law) is us


def test_qatar_state_law_is_flagged_for_atliq_inc():
    p = DocProfile(atliq_entity="Inc", governing_law="the State of Qatar")
    assert [f.title for f in check_governing_law(p)] == ["Foreign governing law: the State of Qatar"]
    assert check_governing_law(DocProfile(atliq_entity="Inc", governing_law="the State of New York")) == []


def test_unverified_quote_drops_exactly_one_level():
    assert [downgrade_severity(s) for s in ("High", "Medium", "Low", "Info")] == ["Medium", "Low", "Low", "Info"]


def test_finding_ids_survive_reordering_and_new_findings():
    a = Finding("Liability", "High", "Uncapped", "x", quote="liability shall be unlimited")
    b = Finding("Payment", "Medium", "Net 90", "y", quote="within ninety (90) days")
    c = Finding("IP", "Medium", "IP assigned", "z", quote="all intellectual property vests")
    first = dict(zip(finding_ids([a, b]), [a, b]))
    later = dict(zip(finding_ids([c, b, a]), [c, b, a]))
    assert all(later[k] is v for k, v in first.items())
    # the unverified-quote prefix does not change the id of a finding without a quote
    d = Finding("Other", "Low", "Arabic prevails", "w", clause_ref="15.3")
    e = Finding("Other", "Low", "[Unverified quote] Arabic prevails", "w", clause_ref="15.3")
    assert d.stable_id() == e.stable_id()
    assert len(set(finding_ids([a, a]))) == 2


def test_brief_uses_decisions_keyed_by_finding_id():
    path = next(INCOMING_DIR.glob("*gulf_crown*"))
    r = analyze(read_text(path), path.name, use_llm=False)
    target = next(f for f in r.findings if f.severity == "High")
    fid = finding_ids(r.findings)[r.findings.index(target)]
    md = brief_markdown(r, {fid: {"decision": "Negotiate", "note": "ask for Indian law"}})
    assert "**Decision:** Negotiate — ask for Indian law" in md


def test_missing_signed_contracts_do_not_crash(monkeypatch):
    monkeypatch.setattr(commitments, "_INDEX", None)
    monkeypatch.setattr(commitments, "signed_clauses", lambda: [])
    assert commitments.similar_signed_clauses("liquidated damages") == []
    p = profile_document(read_text(next(INCOMING_DIR.glob("*gulf_crown*"))))
    assert commitments.precedent_matches(p) == []
    monkeypatch.setattr(commitments, "_INDEX", None)  # let later tests rebuild the real index
