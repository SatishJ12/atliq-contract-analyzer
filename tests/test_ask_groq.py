"""Ask about this contract runs on Groq. These tests stub the Groq client, so no key or network is needed."""
import sys
from pathlib import Path
from types import SimpleNamespace

import groq
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analyzer  # noqa: E402
from data_loader import INCOMING_DIR, read_text  # noqa: E402

HARRINGTON = "2026-09-10_harrington_health_msa_draft.md"


@pytest.fixture
def report():
    text = read_text(INCOMING_DIR / HARRINGTON)
    return text, analyzer.analyze(text, HARRINGTON, use_llm=False)


class FakeGroq:
    calls: list[dict] = []
    error: Exception | None = None

    def __init__(self, api_key):
        assert api_key == "gsk_test"
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        FakeGroq.calls.append(kw)
        if FakeGroq.error:
            raise FakeGroq.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Clause 9.2 says so."))])


@pytest.fixture
def fake_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr(groq, "Groq", FakeGroq)
    FakeGroq.calls, FakeGroq.error = [], None
    return FakeGroq


def _status_error(cls, code):
    resp = httpx.Response(code, request=httpx.Request("POST", "https://api.groq.com"))
    return cls("err", response=resp, body=None)


def test_ask_needs_a_groq_key_not_an_anthropic_key(monkeypatch, report):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert not analyzer.ask_available()
    assert "GROQ_API_KEY" in analyzer.ask_about_contract("Who owns the IP?", *report)


def test_ask_calls_groq_with_the_ask_model(fake_groq, report):
    text, r = report
    assert analyzer.ask_about_contract("Who owns the IP?", text, r) == "Clause 9.2 says so."
    kw = fake_groq.calls[0]
    assert kw["model"] == analyzer.ASK_MODEL == "llama-3.3-70b-versatile"
    assert kw["max_tokens"] == 512
    assert [m["role"] for m in kw["messages"]] == ["system", "user"]
    assert "Al Noor" in kw["messages"][0]["content"]          # register is grounded in
    assert "Who owns the IP?" in kw["messages"][1]["content"]


def test_ask_prompt_fits_groq_free_tier_for_every_draft():
    # ~4 chars per token; free tier is ~12k tokens/min including the 512 max_tokens.
    for path in sorted(INCOMING_DIR.glob("*.md")):
        text = read_text(path)
        msgs = analyzer._ask_messages("Does the Al Noor waiver help here?", text, analyzer.analyze(text, path.name, use_llm=False))
        assert sum(len(m["content"]) for m in msgs) / 4 < 11_000, path.name


@pytest.mark.parametrize("err, expect", [
    (lambda: _status_error(groq.RateLimitError, 429), "free-tier limit"),
    (lambda: _status_error(groq.APIStatusError, 413), "too long"),
    (lambda: _status_error(groq.APIStatusError, 500), "error (500)"),
    (lambda: groq.APIConnectionError(request=httpx.Request("POST", "https://api.groq.com")), "Could not reach Groq"),
])
def test_groq_errors_become_plain_messages(fake_groq, report, err, expect):
    fake_groq.error = err()
    assert expect in analyzer.ask_about_contract("Who owns the IP?", *report)
