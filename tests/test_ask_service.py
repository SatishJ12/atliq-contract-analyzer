"""Ask about this contract calls the v2 AI service (POST /api/ask). A local stub server stands in for it."""
import json
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import analyzer  # noqa: E402


class Stub(BaseHTTPRequestHandler):
    status = 200
    body: dict = {"answer": "Clause 9.2 gives AtliQ the IP."}
    seen: list = []

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length", 0))
        Stub.seen.append({"path": self.path, "token": self.headers.get("X-Access-Token"),
                          "type": self.headers.get("Content-Type"), "json": json.loads(self.rfile.read(n))})
        out = json.dumps(Stub.body).encode()
        self.send_response(Stub.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


@pytest.fixture
def service(monkeypatch):
    monkeypatch.delenv("ATLIQ_ACCESS_TOKEN", raising=False)
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    Stub.status, Stub.body, Stub.seen = 200, {"answer": "Clause 9.2 gives AtliQ the IP."}, []
    yield f"http://127.0.0.1:{srv.server_port}/"
    srv.shutdown()


def test_ask_posts_question_text_and_token_to_the_service(service):
    out = analyzer.ask_about_contract("Who owns the IP?", "CONTRACT TEXT", "x.md", access_token="tok", api_url=service)
    assert out == "Clause 9.2 gives AtliQ the IP."
    req = Stub.seen[0]
    assert req["path"] == "/api/ask"                       # trailing slash on the URL is tolerated
    assert req["token"] == "tok" and req["type"] == "application/json"
    assert req["json"] == {"question": "Who owns the IP?", "text": "CONTRACT TEXT", "filename": "x.md"}


def test_server_side_token_is_used_when_none_is_typed(service, monkeypatch):
    monkeypatch.setenv("ATLIQ_ACCESS_TOKEN", "server-tok")
    monkeypatch.setenv("ATLIQ_API_URL", service)
    analyzer.ask_about_contract("q", "t", "x.md")                    # the configured service
    analyzer.ask_about_contract("q", "t", "x.md", api_url=service)   # same URL typed into the settings box
    assert [s["token"] for s in Stub.seen] == ["server-tok", "server-tok"]


def test_server_side_token_never_goes_to_a_typed_url(service, monkeypatch):
    monkeypatch.setenv("ATLIQ_ACCESS_TOKEN", "server-tok")
    monkeypatch.setenv("ATLIQ_API_URL", "https://atliq-contract-api.onrender.com")
    analyzer.ask_about_contract("q", "t", "x.md", api_url=service)
    assert Stub.seen[0]["token"] is None
    analyzer.ask_about_contract("q", "t", "x.md", access_token="typed", api_url=service)
    assert Stub.seen[1]["token"] == "typed"                          # a token the visitor typed themselves still goes


def test_no_token_sends_no_header(service):
    analyzer.ask_about_contract("q", "t", "x.md", api_url=service)
    assert Stub.seen[0]["token"] is None


def test_api_url_comes_from_env_else_render_default(monkeypatch):
    monkeypatch.delenv("ATLIQ_API_URL", raising=False)
    assert analyzer.ask_api_url() == "https://atliq-contract-api.onrender.com"
    monkeypatch.setenv("ATLIQ_API_URL", "https://example.test/")
    assert analyzer.ask_api_url() == "https://example.test"


@pytest.mark.parametrize("status, body, expect", [
    (401, {"detail": "The AI modes need an access token."}, "needs its access token"),
    (429, {"detail": "Today's AI budget is used up. Try again tomorrow."}, "budget is used up"),
    (422, {"detail": [{"msg": "too long"}]}, "too long"),
    (502, {"detail": "The AI service could not answer right now."}, "could not answer right now"),
    (500, {}, "error (500)"),
])
def test_service_errors_become_plain_messages(service, status, body, expect):
    Stub.status, Stub.body = status, body
    out = analyzer.ask_about_contract("q", "t", "x.md", api_url=service)
    assert expect in out and "tabs above" in out


def test_unreachable_service_says_it_may_be_waking_up():
    out = analyzer.ask_about_contract("q", "t", "x.md", api_url="http://127.0.0.1:9")
    assert "Could not reach the AI service" in out and "wait a minute" in out


def test_browser_build_uses_synchronous_xhr(monkeypatch):
    sent = {}

    class FakeXHR:
        status, responseText = 200, json.dumps({"answer": "from browser"})

        @classmethod
        def new(cls):
            return cls()

        def open(self, method, url, is_async):
            sent.update(method=method, url=url, is_async=is_async)

        def setRequestHeader(self, k, v):  # noqa: N802
            sent.setdefault("headers", {})[k] = v

        def send(self, data):
            sent["data"] = json.loads(data)

    monkeypatch.setitem(sys.modules, "js", types.SimpleNamespace(XMLHttpRequest=FakeXHR))
    monkeypatch.setattr(analyzer, "_in_browser", lambda: True)
    out = analyzer.ask_about_contract("q", "t", "x.md", access_token="tok", api_url="https://svc.test")
    assert out == "from browser"
    assert sent["url"] == "https://svc.test/api/ask" and sent["is_async"] is False
    assert sent["headers"]["X-Access-Token"] == "tok" and sent["data"]["question"] == "q"
