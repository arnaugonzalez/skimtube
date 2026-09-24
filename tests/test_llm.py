import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from conftest import FAKE_LLM

from yt_collector import llm
from yt_collector.config import load


@pytest.fixture
def server():
    """Local OpenAI-compatible endpoint replaying a scripted list of (status, body)."""
    script, received = [], []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers["Content-Length"])
            received.append({"path": self.path, "auth": self.headers.get("Authorization"),
                             "body": json.loads(self.rfile.read(length))})
            status, body = script.pop(0)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1", script, received
    srv.shutdown()


def ok(text):
    return 200, {"choices": [{"message": {"content": text}}]}


def cfg_for(tmp_path, url, **extra):
    return load(tmp_path, env={"YTC_LLM_BASE_URL": url, "YTC_LLM_MODEL": "m", **extra})


def test_openai_success_sends_model_messages_and_key(tmp_path, server):
    url, script, received = server
    script.append(ok("  ## TL;DR\n- x  "))
    out = llm.complete(cfg_for(tmp_path, url, YTC_LLM_API_KEY="secret"), "sys", "user")
    assert out == "## TL;DR\n- x"
    req = received[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["auth"] == "Bearer secret"
    assert req["body"]["model"] == "m"
    assert [m["role"] for m in req["body"]["messages"]] == ["system", "user"]


def test_openai_no_key_sends_no_auth_header(tmp_path, server):
    url, script, received = server
    script.append(ok("fine"))
    llm.complete(cfg_for(tmp_path, url), "s", "u")
    assert received[0]["auth"] is None


def test_openai_retries_transient_errors(tmp_path, server, monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    url, script, _ = server
    script.extend([(429, {"error": "slow down"}), (503, {}), ok("third time")])
    assert llm.complete(cfg_for(tmp_path, url), "s", "u") == "third time"


def test_openai_auth_error_is_not_retried(tmp_path, server):
    url, script, received = server
    script.append((401, {"error": "bad key"}))
    with pytest.raises(llm.LLMError, match="HTTP 401"):
        llm.complete(cfg_for(tmp_path, url), "s", "u")
    assert len(received) == 1


@pytest.mark.parametrize("body", [{"choices": []}, {"weird": 1},
                                  {"choices": [{"message": {"content": "  "}}]}])
def test_openai_bad_shapes(tmp_path, server, body):
    url, script, _ = server
    script.append((200, body))
    with pytest.raises(llm.LLMError):
        llm.complete(cfg_for(tmp_path, url), "s", "u")


def test_openai_unreachable(tmp_path, monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    with pytest.raises(llm.LLMError, match="cannot reach"):
        llm.complete(cfg_for(tmp_path, "http://127.0.0.1:9/v1"), "s", "u")


def test_command_provider(tmp_path):
    cfg = load(tmp_path, env={"YTC_LLM_PROVIDER": "command", "YTC_LLM_COMMAND": FAKE_LLM})
    assert llm.complete(cfg, "system", "a video about models").startswith("## TL;DR")


def test_command_provider_failures(tmp_path):
    cfg = load(tmp_path, env={"YTC_LLM_PROVIDER": "command", "YTC_LLM_COMMAND": FAKE_LLM})
    with pytest.raises(llm.LLMError, match="exited 1"):
        llm.complete(cfg, "s", "FAIL please")
    cfg = load(tmp_path, env={"YTC_LLM_PROVIDER": "command",
                              "YTC_LLM_COMMAND": "definitely-not-a-binary-xyz"})
    with pytest.raises(llm.LLMError, match="not found"):
        llm.complete(cfg, "s", "u")
    cfg = load(tmp_path, env={"YTC_LLM_PROVIDER": "command",
                              "YTC_LLM_COMMAND": f"{sys.executable} -c pass"})
    with pytest.raises(llm.LLMError, match="empty"):
        llm.complete(cfg, "s", "u")
