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
def test_main_reports_fail_line_on_transport_errors(monkeypatch, capsys, sleeps, transport):
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


# --- P5.2: the smoke tolerates a Modal rollover (CTO hand-back 83506a31) -------------------------
# Right after `modal deploy` the old and new containers both serve, and journals live in memory per
# container (D-A3), so a call can land on the container that never saw the journal: 404
# unknown_journal. The whole journey is retried with a fresh journal, only for that kind of miss or
# a network error; a real 500 or a wrong value still fails on the first try.


class _Sleeps(list):
    def __call__(self, seconds):
        self.append(seconds)


@pytest.fixture
def sleeps(monkeypatch):
    s = _Sleeps()
    monkeypatch.setattr(smoke, "_sleep", s)
    return s


def _count_creates(call):
    creates = []

    def wrapped(method, path, body):
        if path == "/api/journals":
            creates.append(1)
        return call(method, path, body)

    return wrapped, creates


def test_unknown_journal_on_try_1_passes_on_try_2(client, sleeps, capsys):
    call = _transport(client)
    misses = []

    def rollover(method, path, body):
        if path.endswith("/next-step") and not misses:
            misses.append(path)
            return 404, {"error": "unknown_journal"}
        return call(method, path, body)

    wrapped, creates = _count_creates(rollover)
    smoke.run_with_retry(wrapped)
    assert len(creates) == 2, "the retry must start over with a fresh journal"
    assert len(sleeps) == 1
    out = capsys.readouterr().out
    assert "retry" in out and "unknown_journal" in out
    assert "ok  passport: 200" in out


def test_unknown_checkin_is_the_same_rollover(client, sleeps):
    call = _transport(client)
    misses = []

    def rollover(method, path, body):
        if path.endswith("/review") and not misses:
            misses.append(path)
            return 404, {"error": "unknown_checkin"}
        return call(method, path, body)

    smoke.run_with_retry(rollover)
    assert len(sleeps) == 1


def test_network_error_on_try_1_passes_on_try_2(client, sleeps):
    call = _transport(client)
    misses = []

    def flaky(method, path, body):
        if not misses:
            misses.append(path)
            raise urllib.error.URLError("connection reset")
        return call(method, path, body)

    smoke.run_with_retry(flaky)
    assert len(sleeps) == 1


def test_passport_500_fails_without_retry(client, sleeps):
    call = _transport(client)

    def passport_500(method, path, body):
        return (500, None) if path.endswith("/passport") else call(method, path, body)

    wrapped, creates = _count_creates(passport_500)
    with pytest.raises(smoke.SmokeFailure, match="passport: expected 200, got 500"):
        smoke.run_with_retry(wrapped)
    assert len(creates) == 1 and sleeps == []


def test_wrong_value_fails_without_retry(client, sleeps):
    call = _transport(client)

    def drop_observed(method, path, body):
        status, data = call(method, path, body)
        if path.endswith("/passport") and isinstance(data, dict):
            data = {**data, "cards": [c for c in data["cards"] if c.get("origin") != "observed"]}
        return status, data

    with pytest.raises(smoke.SmokeFailure, match="passport: expected observed values"):
        smoke.run_with_retry(drop_observed)
    assert sleeps == []


@pytest.mark.parametrize("status", [500, 409, 503])
def test_rollover_code_on_a_non_404_fails_without_retry(client, sleeps, status):
    # Only a 404 means "this container never saw the journal"; a 500 is a real failure whatever its body.
    call = _transport(client)

    def odd(method, path, b):
        return (status, {"error": "unknown_journal"}) if path.endswith("/passport") else call(method, path, b)

    wrapped, creates = _count_creates(odd)
    with pytest.raises(smoke.SmokeFailure, match=f"passport: expected 200, got {status}"):
        smoke.run_with_retry(wrapped)
    assert len(creates) == 1 and sleeps == []


@pytest.mark.parametrize("body", [{"error": "unknown_step"}, {"error": "not_found"}, None])
def test_other_404s_fail_without_retry(client, sleeps, body):
    call = _transport(client)

    def other_404(method, path, b):
        return (404, body) if path.endswith("/passport") else call(method, path, b)

    with pytest.raises(smoke.SmokeFailure, match="passport: expected 200, got 404"):
        smoke.run_with_retry(other_404)
    assert sleeps == []


def test_persistent_rollover_gives_up_after_5_tries(sleeps):
    calls = []

    def always_gone(method, path, body):
        calls.append(path)
        if path == "/api/journals":
            return 201, {"journal_id": f"j{len(calls)}"}
        return 404, {"error": "unknown_journal"}

    with pytest.raises(smoke.SmokeFailure, match=r"next step before any save: expected 409, got 404.*after 5 tries"):
        smoke.run_with_retry(always_gone)
    assert calls.count("/api/journals") == 5
    assert len(sleeps) == 4
    assert sleeps == [10.0, 20.0, 30.0, 40.0], "back-off grows 10/20/30/40 s"


@pytest.mark.parametrize(
    ("try_cost", "expected_sleeps", "tries"),
    [
        # 70 s a try: ends at 70 (+10 = 80 ok), 150 (+20 = 170 ok), 240 (over): 3 tries, 2 sleeps.
        pytest.param(70.0, [10.0, 20.0], 3, id="70s-tries"),
        # The next try would start exactly at the budget: allowed (the budget is inclusive).
        pytest.param(170.0, [10.0], 2, id="lands-on-budget"),
        # Only the coming delay pushes it over the budget: no retry.
        pytest.param(175.0, [], 1, id="delay-crosses-budget"),
    ],
)
def test_retry_stops_when_the_time_budget_is_spent(monkeypatch, sleeps, try_cost, expected_sleeps, tries):
    now = [0.0]
    monkeypatch.setattr(smoke, "_clock", lambda: now[0])
    creates = []

    def slow_gone(method, path, body):
        # Two calls a try (create journal, next step), each half the try's cost.
        now[0] += try_cost / 2
        if path == "/api/journals":
            creates.append(1)
            return 201, {"journal_id": "j"}
        return 404, {"error": "unknown_journal"}

    def tick(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(smoke, "_sleep", tick)
    with pytest.raises(smoke.SmokeFailure, match=f"unknown_journal.*after {tries} tries"):
        smoke.run_with_retry(slow_gone, budget=180.0)
    assert sleeps == expected_sleeps
    assert len(creates) == tries


def test_main_retries_a_network_error_then_reports_fail_line(monkeypatch, sleeps, capsys):
    def refused(m, p, b):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(smoke, "http_transport", lambda base, timeout: refused)
    assert smoke.main(["https://example.invalid"]) == 1
    assert len(sleeps) == 4
    assert capsys.readouterr().err.startswith("FAIL create journal:")


def test_main_passes_after_a_rollover(monkeypatch, sleeps, client):
    call = _transport(client)
    misses = []

    def rollover(method, path, body):
        if path.endswith("/next-step") and not misses:
            misses.append(path)
            return 404, {"error": "unknown_journal"}
        return call(method, path, body)

    monkeypatch.setattr(smoke, "http_transport", lambda base, timeout: rollover)
    assert smoke.main(["https://example.invalid"]) == 0
    assert len(sleeps) == 1
