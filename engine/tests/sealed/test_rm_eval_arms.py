"""Sealed challenge suite — H1 eval arms ``jev`` / ``rm`` / ``grpo`` (HAC-75, HAC-78).

Written double-blind from docs/daypart/contracts/CONTRACT-slice-E-addendum-HAC-75-rm.md H1
(amends CONTRACT-slice-E-eval-passport.md E1.1 / E1.3, supersedes slice G's G3). The
implementation was never read. Reference scenario manifests come from slice A/C public APIs.

Categories:
  integration/rm-arms-default   the three arms in the committed metrics.json (E3 deliverable)
  integration/rm-arms-run       run() over a small config holding the three arms (shape, determinism)
  integration/rm-arms-i1        I1 builder "rm.train_members" and the CLI line

Ambiguities resolved:
  * The arms' metrics in the default config are read from the committed
    ``docs/daypart/results/metrics.json``; test_eval.py already pins that file byte-equal to a
    fresh ``python -m daypart.eval`` run, so no second full run is made here.
  * "same ``scenario_manifest_sha256`` per seed as the env_baseline arms" is checked on the default
    config (same n_scenarios / seeds / horizon), and on a small config against a reference built from
    ``make_scenarios`` + ``scenario_manifest`` the same way test_eval.py does for env_baseline.
  * ``message_mix`` "one key per intent" is read as one key per ``INTENTS`` entry (``none`` included).
  * ``training`` content is not specified; only its presence is checked.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parents[2]
DELIVERABLE = ENGINE.parent / "docs" / "daypart" / "results" / "metrics.json"
ENV_KEYS = {"policy", "horizon", "n_scenarios", "per_seed", "mean_adherence", "episode_violation_rate", "seeds"}
PER_SEED_KEYS = {
    "seed",
    "n_episodes",
    "mean_adherence",
    "episode_violation_rate",
    "mean_return",
    "scenario_manifest_sha256",
}
JEV_RECOVERY_KEYS = {"n_members", "axis_accuracy", "chance_accuracy", "mood_mean_abs_error"}
RM_HELDOUT_KEYS = {
    "n_members",
    "n_rows",
    "log_loss",
    "brier",
    "auc",
    "base_rate_log_loss",
    "status_only_log_loss",
    "status_only_auc",
}
RM_ATTR_KEYS = {"lift_spearman", "lift_pearson", "top_message_agreement", "top_message_chance"}


def _ev():
    import daypart.eval as ev

    return ev


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _sha(obj) -> str:
    return hashlib.sha256(_canon(obj).encode("utf-8")).hexdigest()


def _categorical_axes_minus_age() -> set[str]:
    from daypart.simmember.latents import AXES

    return set(AXES) - {"age_band"}


def _ref_manifest_sha(cohort_seed, n, seed, horizon) -> str:
    from daypart.simmember.cohort import generate
    from daypart.simmember.env import make_scenarios, scenario_manifest

    scns = [s.model_copy(update={"horizon": horizon}) for s in make_scenarios(generate(cohort_seed), n, seed)]
    return _sha(scenario_manifest(scns))


def _arm(data, name):
    for a in data["arms"]:
        if a["name"] == name:
            return a
    raise AssertionError(f"arm {name} missing")


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


# --------------------------------------------------------------------------- #
# Shape checks shared by the default deliverable and the small run
# --------------------------------------------------------------------------- #


def _check_provenance(m):
    # H1: data synthetic, label contains "not clinical evidence".
    assert m["data"] == "synthetic"
    assert isinstance(m["label"], str) and "not clinical evidence" in m["label"]


def _check_jev(m):
    _check_provenance(m)
    assert isinstance(m["n_questions"], int) and not isinstance(m["n_questions"], bool)
    assert m["n_questions"] >= 5
    qids = m["question_ids"]
    assert isinstance(qids, list) and all(isinstance(q, str) for q in qids)
    assert len(qids) == m["n_questions"] and len(set(qids)) == len(qids)
    assert isinstance(m["n_features"], int) and m["n_features"] >= 1
    rec = m["heldout_recovery"]
    assert set(rec) == JEV_RECOVERY_KEYS
    assert isinstance(rec["n_members"], int) and rec["n_members"] >= 1
    axes = _categorical_axes_minus_age()
    assert set(rec["axis_accuracy"]) == axes
    assert set(rec["chance_accuracy"]) == axes
    for ax in axes:
        assert _is_num(rec["axis_accuracy"][ax]) and 0.0 <= rec["axis_accuracy"][ax] <= 1.0
        assert _is_num(rec["chance_accuracy"][ax]) and 0.0 < rec["chance_accuracy"][ax] <= 1.0
    assert _is_num(rec["mood_mean_abs_error"]) and rec["mood_mean_abs_error"] >= 0.0


def _check_rm(m):
    _check_provenance(m)
    h = m["heldout"]
    assert RM_HELDOUT_KEYS <= set(h)
    for k in RM_HELDOUT_KEYS:
        assert _is_num(h[k]), k
    assert h["n_members"] >= 1 and h["n_rows"] >= 1
    # H1 acceptance numbers.
    assert 0.5 < h["auc"] <= 1.0
    assert h["log_loss"] < h["base_rate_log_loss"]
    assert 0.0 <= h["brier"] <= 1.0
    a = m["attribution_recovery"]
    assert RM_ATTR_KEYS <= set(a)
    for k in RM_ATTR_KEYS:
        assert _is_num(a[k]), k
    assert a["top_message_agreement"] > a["top_message_chance"]
    t = m["train"]
    assert {"n_members", "n_rows"} <= set(t)
    assert t["n_members"] >= 1 and t["n_rows"] >= 1


def _check_grpo(m, n_scenarios, seeds, horizon):
    from daypart.simmember.dynamics import INTENTS

    _check_provenance(m)
    assert ENV_KEYS <= set(m)
    assert {"heldout_members", "message_mix", "training"} <= set(m)
    assert m["n_scenarios"] == n_scenarios and m["horizon"] == horizon and list(m["seeds"]) == list(seeds)
    assert isinstance(m["policy"], str) and m["policy"]
    assert [p["seed"] for p in m["per_seed"]] == list(seeds)
    for p in m["per_seed"]:
        assert set(p) == PER_SEED_KEYS
        assert p["n_episodes"] == n_scenarios
        assert 0.0 <= p["mean_adherence"] <= 1.0
        assert p["episode_violation_rate"] == 0.0
    # H1: episode_violation_rate == 0.0.
    assert m["episode_violation_rate"] == 0.0
    assert 0.0 <= m["mean_adherence"] <= 1.0
    mix = m["message_mix"]
    assert set(mix) == set(INTENTS)
    assert all(_is_num(v) and v >= 0.0 for v in mix.values())
    assert abs(sum(mix.values()) - 1.0) <= 1e-5


# --------------------------------------------------------------------------- #
# Default config: the committed deliverable
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def deliverable():
    assert DELIVERABLE.is_file(), "docs/daypart/results/metrics.json must be committed (E3)"
    return json.loads(DELIVERABLE.read_text(encoding="utf-8"))


@pytest.mark.category("integration/rm-arms-default")
class TestDefaultDeliverable:
    def test_three_arms_ok(self, deliverable):
        for name, kind in (("grpo", "grpo_policy"), ("rm", "reward_model"), ("jev", "jev_library")):
            a = _arm(deliverable, name)
            assert a["kind"] == kind
            assert a["status"] == "ok", a.get("reason")
            assert a["reason"] is None
            assert isinstance(a["metrics"], dict) and a["metrics"]

    def test_summary(self, deliverable):
        assert deliverable["summary"] == {"ok": 12, "not_run": 0, "failed": 0}

    def test_jev_metrics(self, deliverable):
        _check_jev(_arm(deliverable, "jev")["metrics"])

    def test_jev_question_ids_match_library(self, deliverable):
        from daypart.rm.jev import QUESTION_IDS

        m = _arm(deliverable, "jev")["metrics"]
        assert m["question_ids"] == list(QUESTION_IDS)
        assert m["n_questions"] == len(QUESTION_IDS)

    def test_jev_n_features_matches_library(self, deliverable):
        from daypart.rm.jev import FEATURE_NAMES

        assert _arm(deliverable, "jev")["metrics"]["n_features"] == len(FEATURE_NAMES)

    def test_rm_metrics(self, deliverable):
        _check_rm(_arm(deliverable, "rm")["metrics"])

    def test_rm_metrics_equal_evaluate(self, deliverable):
        # H2: ``evaluate(cohort_seed=0)`` is "the rm arm's metrics".
        from daypart.rm.model import evaluate

        got = json.loads(json.dumps(evaluate(0)))
        assert got == _arm(deliverable, "rm")["metrics"]

    def test_grpo_metrics(self, deliverable):
        _check_grpo(_arm(deliverable, "grpo")["metrics"], 50, [0, 1, 2], 14)

    def test_grpo_same_scenarios_as_env_baselines(self, deliverable):
        # H1: same scenario_manifest_sha256 per seed as the env_baseline arms.
        g = {p["seed"]: p["scenario_manifest_sha256"] for p in _arm(deliverable, "grpo")["metrics"]["per_seed"]}
        envs = [a for a in deliverable["arms"] if a["kind"] == "env_baseline"]
        assert len(envs) == 3
        for e in envs:
            for p in e["metrics"]["per_seed"]:
                assert g[p["seed"]] == p["scenario_manifest_sha256"], (e["name"], p["seed"])

    def test_grpo_manifest_matches_reference(self, deliverable):
        for p in _arm(deliverable, "grpo")["metrics"]["per_seed"]:
            assert p["scenario_manifest_sha256"] == _ref_manifest_sha(0, 50, p["seed"], 14)


# --------------------------------------------------------------------------- #
# Small config: run() shape and determinism (E1.3)
# --------------------------------------------------------------------------- #

SMALL_ARMS = [
    {"name": "jev", "kind": "jev_library"},
    {"name": "rm", "kind": "reward_model"},
    {"name": "grpo", "kind": "grpo_policy", "n_scenarios": 2, "seeds": [0, 1], "horizon": 3},
]


@pytest.fixture(scope="module")
def small_runs():
    ev = _ev()
    cfg = ev.RunsConfig.model_validate({"version": "sealed-rm-v1", "cohort_seed": 0, "arms": SMALL_ARMS})
    a = ev.run(cfg, root=ENGINE)
    b = ev.run(cfg, root=ENGINE)
    return ev, a, b


@pytest.mark.category("integration/rm-arms-run")
class TestSmallRun:
    def test_all_ok(self, small_runs):
        _, a, _ = small_runs
        assert [(x["name"], x["kind"], x["status"]) for x in a["arms"]] == [
            ("jev", "jev_library", "ok"),
            ("rm", "reward_model", "ok"),
            ("grpo", "grpo_policy", "ok"),
        ]
        assert a["summary"] == {"ok": 3, "not_run": 0, "failed": 0}

    def test_deterministic_bytes(self, small_runs):
        ev, a, b = small_runs
        assert ev.dumps(a) == ev.dumps(b)

    def test_shapes(self, small_runs):
        _, a, _ = small_runs
        _check_jev(_arm(a, "jev")["metrics"])
        _check_rm(_arm(a, "rm")["metrics"])
        _check_grpo(_arm(a, "grpo")["metrics"], 2, [0, 1], 3)

    def test_grpo_manifest_reference(self, small_runs):
        _, a, _ = small_runs
        for p in _arm(a, "grpo")["metrics"]["per_seed"]:
            assert p["scenario_manifest_sha256"] == _ref_manifest_sha(0, 2, p["seed"], 3)

    def test_no_curated_ids_in_output(self, small_runs):
        # I1: nothing here may read or echo a curated profile.
        import re

        ev, a, _ = small_runs
        assert not re.search(r"\bcur-\d{3}\b", ev.dumps(a))


# --------------------------------------------------------------------------- #
# I1 builder
# --------------------------------------------------------------------------- #


@pytest.mark.category("integration/rm-arms-i1")
class TestI1RmBuilder:
    def test_registered(self):
        from daypart.ci.i1_check import BUILDERS

        assert "rm.train_members" in BUILDERS

    def test_results_ok(self):
        from daypart.ci.i1_check import results

        assert results(0)["rm.train_members"] == "ok"

    def test_rows_synthetic_only(self, cohort0):
        import re

        from daypart.ci.i1_check import BUILDERS

        rows = list(BUILDERS["rm.train_members"](cohort0))
        assert rows, "rm.train_members must build at least one row"
        text = _canon([r if isinstance(r, (dict, list, str, int, float)) else str(r) for r in rows])
        assert not re.search(r"\bcur-\d{3}\b", text)

    def test_cli_line(self):
        proc = subprocess.run(
            [sys.executable, "-m", "daypart.ci.i1_check"],
            cwd=ENGINE,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert proc.returncode == 0, proc.stderr
        assert "I1 ok   rm.train_members" in proc.stdout.splitlines()
