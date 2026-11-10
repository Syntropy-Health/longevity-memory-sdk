"""``tools/smoke_journey.py``: the post-deploy SC1 journey (HAC-38, CTO hand-back 3172f7da).

The smoke runs against the real app through a TestClient transport, so it is known to pass on a
healthy build, and it must fail when the passport 500s (the hosted defect it exists to catch).
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import sys
import threading
import urllib.error
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from daypart.demo.app import create_app

TOOL = Path(__file__).resolve().parents[2] / "tools" / "smoke_journey.py"


def _load():
    spec = importlib.util.spec_from_file_location("smoke_journey", TOOL)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("smoke_journey", mod)
    spec.loader.exec_module(mod)
    return mod


smoke = _load()


@pytest.fixture
def client():
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("DAYPART_REAL_INPUT", raising=False)
        with TestClient(create_app(cohort_seed=0), raise_server_exceptions=False) as c:
            yield c


def _transport(client):
    def call(method, path, body):
        r = client.request(method, path, json=body)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, None

    return call


def test_journey_passes_on_healthy_app(client, capsys):
    smoke.run(_transport(client))
    out = capsys.readouterr().out
    assert "ok  passport: 200" in out
    assert "ok  real-input mode refused: 403" in out


def test_journey_fails_when_passport_500s(client):
    # The hosted defect: GET /passport returned 500 while every other step passed.
    call = _transport(client)

    def passport_500(method, path, body):
        if path.endswith("/passport"):
            return 500, None
        return call(method, path, body)

    with pytest.raises(smoke.SmokeFailure, match="passport: expected 200, got 500"):
        smoke.run(passport_500)


def test_journey_fails_when_saved_value_missing_from_passport(client):
    call = _transport(client)

    def drop_observed(method, path, body):
        status, data = call(method, path, body)
        if path.endswith("/passport") and isinstance(data, dict):
            data = {**data, "cards": [c for c in data["cards"] if c.get("origin") != "observed"]}
        return status, data

    with pytest.raises(smoke.SmokeFailure, match="passport: expected observed values"):
        smoke.run(drop_observed)


def test_journey_fails_when_mode_not_refused(client):
    call = _transport(client)

    def mode_open(method, path, body):
        return (200, {}) if path == "/api/mode" else call(method, path, body)

    with pytest.raises(smoke.SmokeFailure, match="real-input mode refused: expected 403"):
        smoke.run(mode_open)


def test_main_exit_status(monkeypatch, client):
    monkeypatch.setattr(smoke, "http_transport", lambda base, timeout: _transport(client))
    assert smoke.main(["https://example.invalid"]) == 0

    def broken(base, timeout):
        return lambda m, p, b: (500, None)

    monkeypatch.setattr(smoke, "http_transport", broken)
    assert smoke.main(["https://example.invalid"]) == 1


def test_deploy_job_runs_the_journey_on_the_hosted_url():
    import yaml

    workflow = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "engine.yml"
    steps = yaml.safe_load(workflow.read_text())["jobs"]["deploy-demo"]["steps"]
    names = [s.get("name", "") for s in steps]
    deploy = names.index("Deploy to Modal")
    smoke_steps = [i for i, s in enumerate(steps) if "tools/smoke_journey.py" in s.get("run", "")]
    assert smoke_steps and smoke_steps[0] > deploy
    run = steps[smoke_steps[0]]["run"]
    assert "https://supermomo668--daypart-demo-playground.us-east.modal.run" in run
    assert "|| true" not in run and not steps[smoke_steps[0]].get("continue-on-error")


# --- QG P5.1 B1: network errors and malformed bodies end in a FAIL line, exit 1 -------------------


@pytest.mark.parametrize(
    "transport",
    [
        pytest.param(lambda m, p, b: (_ for _ in ()).throw(urllib.error.URLError("refused")), id="url-error"),
        pytest.param(lambda m, p, b: (_ for _ in ()).throw(TimeoutError("timed out")), id="timeout"),
        pytest.param(lambda m, p, b: (201, None), id="no-body"),
        pytest.param(lambda m, p, b: (201, []), id="list-body"),
    ],
)
def test_main_reports_fail_line_on_transport_errors(monkeypatch, capsys, transport):
    monkeypatch.setattr(smoke, "http_transport", lambda base, timeout: transport)
    assert smoke.main(["https://example.invalid"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("FAIL create journal:"), err


# --- QG P5.1 B2: the real urllib transport (the only code path CI runs) --------------------------


class _Handler(http.server.BaseHTTPRequestHandler):
    seen: list[tuple[str, str, str | None, bytes]] = []

    def _reply(self):
        n = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(n) if n else b""
        _Handler.seen.append((self.command, self.path, self.headers.get("content-type"), body))
        status, payload = {
            "/conflict": (409, b'{"error": "no_saved_checkin"}'),
            "/boom": (500, b"Internal Server Error"),
            "/empty": (200, b""),
        }.get(self.path, (201, b'{"ok": true}'))
        self.send_response(status)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = _reply

    def log_message(self, *a):
        pass


@pytest.fixture
def stub_url():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    _Handler.seen.clear()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}/"
    finally:
        srv.shutdown()
        srv.server_close()


def test_http_transport_returns_error_statuses_without_raising(stub_url):
    call = smoke.http_transport(stub_url, timeout=5)
    assert call("GET", "/conflict", None) == (409, {"error": "no_saved_checkin"})
    assert call("GET", "/boom", None) == (500, None)
    assert call("GET", "/empty", None) == (200, None)


def test_http_transport_sends_json_and_strips_trailing_slash(stub_url):
    call = smoke.http_transport(stub_url, timeout=5)
    assert call("POST", "/api/journals", {"member_id": "syn-001"}) == (201, {"ok": True})
    assert call("GET", "/api/lab", None) == (201, {"ok": True})
    (m1, p1, ct1, b1), (m2, p2, ct2, b2) = _Handler.seen
    assert (m1, p1, ct1) == ("POST", "/api/journals", "application/json")
    assert json.loads(b1) == {"member_id": "syn-001"}
    assert (m2, p2, ct2, b2) == ("GET", "/api/lab", None, b"")
