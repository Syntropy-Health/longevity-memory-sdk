"""``tools/smoke_journey.py``: the post-deploy SC1 journey (HAC-38, CTO hand-back 3172f7da).

The smoke runs against the real app through a TestClient transport, so it is known to pass on a
healthy build, and it must fail when the passport 500s (the hosted defect it exists to catch).
"""

from __future__ import annotations

import importlib.util
import sys
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
