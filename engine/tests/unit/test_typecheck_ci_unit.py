"""HAC-38 P1.7 (addendum G20): pyright, basic mode, gates the demo deploy in CI."""

import tomllib
from pathlib import Path

import yaml

ENGINE = Path(__file__).resolve().parents[2]
WORKFLOW = ENGINE.parent / ".github" / "workflows" / "engine.yml"


def _jobs() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())["jobs"]


def test_pyright_config_is_basic_over_daypart():
    cfg = tomllib.loads((ENGINE / "pyproject.toml").read_text())["tool"]["pyright"]
    assert cfg["typeCheckingMode"] == "basic"
    assert cfg["include"] == ["daypart"]
    assert cfg.get("exclude", []) == ["daypart/train/modal_app.py"]


def test_typecheck_job_runs_pinned_pyright_in_engine():
    job = _jobs()["typecheck"]
    assert job["defaults"]["run"]["working-directory"] == "engine"
    runs = " ".join(s.get("run", "") for s in job["steps"])
    assert "uv sync --locked" in runs
    assert "pyright@1." in runs and "--pythonpath .venv/bin/python" in runs


def test_deploy_needs_typecheck():
    assert "typecheck" in _jobs()["deploy-demo"]["needs"]


# --- QG-plan K4: T8.5 / SC5, the I1 builder check runs in CI and gates the deploy ------------------


def test_t8_5_i1_check_runs_in_the_test_job_and_gates_deploy():
    runs = [s.get("run", "") for s in _jobs()["test"]["steps"]]
    assert "uv run python -m daypart.ci.i1_check" in runs
    assert "test" in _jobs()["deploy-demo"]["needs"]


# --- QG-plan K5: SC6, the UI suite is required to run and gates the deploy ---------------------------


def test_demo_ui_runs_with_a_required_browser_and_gates_deploy():
    job = _jobs()["demo-ui"]
    runs = " ".join(s.get("run", "") for s in job["steps"])
    assert "playwright install --with-deps chromium" in runs
    (suite,) = [s for s in job["steps"] if "pytest" in s.get("run", "") and "tests/ui" in s["run"]]
    assert suite["env"]["DAYPART_UI_REQUIRED"] == "1"
    assert "demo-ui" in _jobs()["deploy-demo"]["needs"]
