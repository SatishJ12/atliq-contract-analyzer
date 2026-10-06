"""Golden test set: the known problems in the 15 drafts (13 incoming + 2 held back in data/demo_uploads).

Run:  python -m pytest -q     (no API key needed; tests the deterministic layer)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analyzer import analyze  # noqa: E402
from data_loader import DEMO_UPLOADS_DIR, INCOMING_DIR, read_text  # noqa: E402


def run(name: str):
    path = next(p for d in (INCOMING_DIR, DEMO_UPLOADS_DIR) for p in d.glob(f"*{name}*"))
    return analyze(read_text(path), path.name, use_llm=False)


def titles(report, severity="High"):
    return " | ".join(f.title for f in report.findings if f.severity == severity)


def test_gulf_crown_conflicts_with_al_noor_non_compete():
    r = run("gulf_crown")
    assert "Al Noor GCC non-compete" in titles(r)
    assert "Saudi Arabia" in titles(r)
    assert r.verdict_level == "blockers"


def test_blueorchid_gcc_properties_hit_al_noor():
    r = run("blueorchid")  # seller thought "just India hotels"; Annexure B lists Dubai and Muscat
    assert "Al Noor GCC non-compete" in titles(r)


def test_travelhub_wrong_entity_and_hotel_distribution():
    r = run("travelhub")
    t = titles(r)
    assert "Wrong AtliQ entity" in t and "Invoicing entity" in t
    assert "Al Noor" in t  # hotel ranking for UAE/KSA = distribution services to hotels (cl. 1.11)


def test_harrington_missing_subcontractor_baa_and_unsigned_baa():
    r = run("harrington_health_msa")
    t = titles(r)
    assert "subcontractor BAA" in t
    assert "HIPAA BAA not signed" in t
    assert "Patient data may already be in Pune" in t
    assert any("non-negotiable" in e for e in r.escalate)


def test_harrington_baa_insurance_gap():
    r = run("harrington_health_baa")
    assert "$5,000,000 cyber cover" in titles(r)


def test_daniel_ortiz_needs_subcontractor_baa():
    r = run("daniel_ortiz_contractor")
    assert "Missing subcontractor BAA" in titles(r)


def test_marcus_reed_india_template_indian_law_for_us_freelancer():
    r = run("marcus_reed")
    t = titles(r)
    assert r.profile.counterparty_country == "USA"
    assert "India" in r.profile.governing_law
    assert "India template sent to a US party" in t
    assert "Wrong AtliQ entity" in t
    assert "non-compete" in t


def test_kriti_pay_when_paid_120_days_is_unfair():
    r = run("kriti")
    t = titles(r)
    assert r.profile.atliq_role == "buyer"
    assert "pay-when-paid, up to 120 days" in t
    assert "Fairness: Liquidated damages" in t


def test_lakeshore_rate_breaks_crestline_mfn():
    assert "Crestline's MFN" in titles(run("lakeshore"))


def test_rheinwerk_pipekit_and_missing_dpa():
    r = run("rheinwerk")
    t = titles(r)
    assert "PipeKit" in t and "Annex 3" in t
    # the German-law liability carve-out only *looks* risky
    assert any("standard carve-out" in f.title and f.severity == "Low" for f in r.findings)


def test_datavane_breaches_cloudspan_exclusivity():
    assert "CloudSpan partner exclusivity" in titles(run("datavane"))


def test_finserve_mutual_in_name_only():
    t = titles(run("finserve"))
    assert "'Mutual' NDA that only binds AtliQ" in t and "Non-compete hidden inside an NDA" in t


def test_clean_documents_have_no_blockers():
    for name in ["sunrise_foods_sow2", "loopmart"]:
        r = run(name)
        assert not [f for f in r.findings if f.severity == "High"], name
