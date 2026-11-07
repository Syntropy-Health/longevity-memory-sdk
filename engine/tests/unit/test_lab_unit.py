"""HAC-38 P2 task 9: the learning lab rows (A&D §4.8, R8 provenance, AD6).

Covers T8.1-T8.3: ``lab_rows()`` over the committed results gives base, sft and dpo plus the 3 env
baselines, each field from its §4.8 formula; grpo is "proposed, not built" with no numbers; a
missing source field is null ("not recorded") and an adapter mismatch shows "provenance mismatch"
with no number. Synthetic only.
"""

import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

import pytest

from daypart.demo.lab import (
    FOOTER,
    NOT_RECORDED,
    PROPOSED,
    PROVENANCE_MISMATCH,
    LabTable,
    lab_rows,
)

RESULTS = Path(__file__).resolve().parents[3] / "docs" / "daypart" / "results"
FILES = ("boundary_eval.json", "training.json", "metrics.json", "pipeline.json")


def _load(d, name):
    return json.loads((Path(d) / name).read_text("utf-8"))


@pytest.fixture()
def copy(tmp_path):
    for f in FILES:
        shutil.copy(RESULTS / f, tmp_path / f)
    return tmp_path


def _edit(d, name, fn):
    data = _load(d, name)
    fn(data)
    (Path(d) / name).write_text(json.dumps(data), "utf-8")


def _rows(table):
    return {r.row: r for r in table.rows}


def _numbers(obj):
    if isinstance(obj, bool):
        return []
    if isinstance(obj, (int, float)):
        return [obj]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in _numbers(v)]
    if isinstance(obj, (list, tuple)):
        return [n for v in obj for n in _numbers(v)]
    return []


# --- T8.1 ----------------------------------------------------------------------------------------


def test_t8_1_rows_and_order():
    table = lab_rows(RESULTS)
    assert isinstance(table, LabTable)
    assert [r.row for r in table.rows] == [
        "base", "sft", "dpo",
        "env_always_none", "env_always_barrier_problem_solving", "env_random_intent",
        "grpo",
    ]


def test_t8_1_model_rows_follow_the_formulas():
    be, tr, pl = _load(RESULTS, "boundary_eval.json"), _load(RESULTS, "training.json"), _load(RESULTS, "pipeline.json")
    rows = _rows(lab_rows(RESULTS))
    tag = pl["tag"]
    for name in ("base", "sft", "dpo"):
        r, m = rows[name], be["models"][name]
        assert r.status == "ok"
        assert r.split.prompt_set_version == be["prompt_set_version"] == "boundary-heldout-v1"
        assert r.split.n == m["n"]
        assert r.seed == be["meta"]["seed"]
        assert r.failures == m["n"] - round(m["boundary_pass_rate"] * m["n"])
        assert r.degenerate == m["degenerate"]
        assert r.metrics["boundary_pass_rate"] == m["boundary_pass_rate"]
        assert r.metrics["rubric_pass_rate"] == m["rubric_pass_rate"]
        assert r.run_id and r.split and r.seed is not None and r.failures is not None
    assert rows["base"].run_id == f"{tag}/base" == "hac28-20261105T081951Z/base"
    assert rows["base"].file_digest == hashlib.sha256((RESULTS / "boundary_eval.json").read_bytes()).hexdigest()[:12]
    for name in ("sft", "dpo"):
        r = rows[name]
        assert r.run_id == f"{tag}/{PurePosixPath(be['meta']['adapters'][name]).name}"
        assert r.split.training_rows == tr[name]["rows"]
        assert r.split.data_sha256 == pl["data"][f"{name}_sha256"]
        assert r.cohort_seed == be["meta"]["cohort_seed"]
    assert rows["sft"].run_id == "hac28-20261105T081951Z/daypart-sft-7cdcffc336f1"
    assert rows["dpo"].run_id == "hac28-20261105T081951Z/daypart-dpo-947059e60fcf"
    assert rows["sft"].gate == be["r3"] and rows["dpo"].gate == be["r4"]
    assert rows["base"].gate is None


def test_t8_1_env_baselines_follow_the_formulas():
    mx = _load(RESULTS, "metrics.json")
    rows = _rows(lab_rows(RESULTS))
    arms = {a["name"]: a for a in mx["arms"] if a["kind"] == "env_baseline"}
    assert len(arms) == 3
    for name, arm in arms.items():
        r, m = rows[name], arm["metrics"]
        assert r.status == "ok"
        assert r.run_id == f"eval-v1@{mx['runs_digest'][:12]}/{name}"
        assert r.split.n_scenarios == m["n_scenarios"] and r.split.horizon == m["horizon"]
        assert r.split.n == m["n_scenarios"] * len(m["seeds"])
        assert r.seed == list(m["seeds"])
        assert r.failures == round(m["episode_violation_rate"] * m["n_scenarios"] * len(m["seeds"]))
        assert r.run_id and r.split and r.seed is not None and r.failures is not None
        assert r.metrics == {"mean_adherence": m["mean_adherence"], "episode_violation_rate": m["episode_violation_rate"]}


def test_header_and_footer():
    pl, mx = _load(RESULTS, "pipeline.json"), _load(RESULTS, "metrics.json")
    table = lab_rows(RESULTS)
    assert table.member_failure_count == pl["data"]["member_failure_count"] == 0
    i1 = next(a for a in mx["arms"] if a["name"] == "i1_gate")
    assert table.i1_passed is i1["metrics"]["passed"] is True
    assert table.footer == FOOTER == "Simulated outcomes are not patient outcomes."


# --- T8.2 ----------------------------------------------------------------------------------------


def test_t8_2_grpo_is_proposed_with_no_numbers():
    mx = _load(RESULTS, "metrics.json")
    g = _rows(lab_rows(RESULTS))["grpo"]
    assert g.status == PROPOSED == "proposed, not built"
    assert g.reason == next(a for a in mx["arms"] if a["name"] == "grpo")["reason"]
    assert _numbers(g.model_dump()) == []
    assert g.run_id is None and g.split is None and g.failures is None


# --- T8.3 ----------------------------------------------------------------------------------------


def test_t8_3_missing_seed_is_null(copy):
    _edit(copy, "boundary_eval.json", lambda d: d["meta"].pop("seed"))
    rows = _rows(lab_rows(copy))
    for name in ("base", "sft", "dpo"):
        assert rows[name].seed is None
        assert rows[name].failures is not None  # the row's own fields still show
    assert NOT_RECORDED == "not recorded"


@pytest.mark.parametrize("name", ["sft", "dpo"])
def test_t8_3_adapter_mismatch_shows_no_number(copy, name):
    _edit(copy, "training.json", lambda d: d[name].update(adapter="/vol/adapters/daypart-other-000000000000"))
    rows = _rows(lab_rows(copy))
    r = rows[name]
    assert r.status == PROVENANCE_MISMATCH == "provenance mismatch"
    assert _numbers(r.model_dump()) == []
    other = "dpo" if name == "sft" else "sft"
    assert rows[other].status == "ok" and rows["base"].status == "ok"


def test_missing_training_adapter_is_a_mismatch(copy):
    _edit(copy, "training.json", lambda d: d["sft"].pop("adapter"))
    assert _rows(lab_rows(copy))["sft"].status == PROVENANCE_MISMATCH


@pytest.mark.parametrize("missing", FILES)
def test_a_missing_artefact_still_renders(copy, missing):
    (copy / missing).unlink()
    table = lab_rows(copy)
    assert [r.row for r in table.rows][:3] == ["base", "sft", "dpo"]
    assert table.footer == FOOTER


def test_malformed_artefact_still_renders(copy):
    (copy / "boundary_eval.json").write_text("{not json", "utf-8")
    rows = _rows(lab_rows(copy))
    assert rows["base"].run_id is None or rows["base"].failures is None
    assert rows["base"].metrics == {"boundary_pass_rate": None, "rubric_pass_rate": None}
    assert rows["base"].file_digest is None


def test_missing_pass_rate_gives_no_failures(copy):
    _edit(copy, "boundary_eval.json", lambda d: d["models"]["base"].pop("boundary_pass_rate"))
    r = _rows(lab_rows(copy))["base"]
    assert r.failures is None and r.metrics["boundary_pass_rate"] is None
    assert r.metrics["rubric_pass_rate"] is not None


def test_missing_runs_digest_gives_no_env_run_id(copy):
    _edit(copy, "metrics.json", lambda d: d.pop("runs_digest"))
    r = _rows(lab_rows(copy))["env_random_intent"]
    assert r.run_id is None and r.failures is not None


def test_non_numeric_fields_are_not_recorded(copy):
    _edit(copy, "boundary_eval.json", lambda d: d["models"]["base"].update(n="141", boundary_pass_rate=True))
    r = _rows(lab_rows(copy))["base"]
    assert r.split.n is None and r.failures is None and r.metrics["boundary_pass_rate"] is None


# --- route ---------------------------------------------------------------------------------------


def test_api_lab_route():
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient

    from daypart.demo.app import create_app

    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("DAYPART_REAL_INPUT", raising=False)
        with TestClient(create_app(cohort_seed=0)) as c:
            r = c.get("/api/lab")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == json.loads(lab_rows(RESULTS).model_dump_json())
    assert body["footer"] == FOOTER


# --- QG P2.4 -------------------------------------------------------------------------------------


def _arm(d, name):
    return next(a for a in d["arms"] if a.get("name") == name)


def _write_raw(d, name, text):
    (Path(d) / name).write_text(text, "utf-8")


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity", "1e400", "1" + "0" * 400])
def test_k1_non_finite_or_huge_numbers_are_not_recorded(copy, token):
    """K1: json.loads accepts NaN/Infinity/1e400 and huge ints; each is "not a number" -> null, never a 500."""
    be = _load(copy, "boundary_eval.json")
    be["models"]["base"]["boundary_pass_rate"] = "@RATE@"
    be["models"]["base"]["rubric_pass_rate"] = "@RATE@"
    _write_raw(copy, "boundary_eval.json", json.dumps(be).replace('"@RATE@"', token))
    mx = _load(copy, "metrics.json")
    _arm(mx, "env_random_intent")["metrics"]["episode_violation_rate"] = "@RATE@"
    _arm(mx, "env_random_intent")["metrics"]["mean_adherence"] = "@RATE@"
    _write_raw(copy, "metrics.json", json.dumps(mx).replace('"@RATE@"', token))
    table = lab_rows(copy)
    rows = _rows(table)
    base, env = rows["base"], rows["env_random_intent"]
    assert base.failures is None and base.metrics == {"boundary_pass_rate": None, "rubric_pass_rate": None}
    assert env.failures is None
    assert env.metrics == {"mean_adherence": None, "episode_violation_rate": None}
    json.loads(table.model_dump_json())  # strict-JSON serialisable (the route's JSONResponse refuses NaN)


def test_k1_huge_count_gives_no_failures(copy):
    be = _load(copy, "boundary_eval.json")
    be["models"]["base"]["n"] = "@N@"
    _write_raw(copy, "boundary_eval.json", json.dumps(be).replace('"@N@"', "1" + "0" * 400))
    mx = _load(copy, "metrics.json")
    _arm(mx, "env_random_intent")["metrics"]["n_scenarios"] = "@N@"
    _arm(mx, "env_random_intent")["metrics"]["episode_violation_rate"] = 0.1
    _write_raw(copy, "metrics.json", json.dumps(mx).replace('"@N@"', "1" + "0" * 400))
    rows = _rows(lab_rows(copy))
    assert rows["base"].failures is None and rows["env_random_intent"].failures is None


def test_k2_failures_formulas_at_non_zero_rates(copy):
    """K2: every committed env rate is 0.0 and sft/dpo pass 1.0, so pin both formulas at non-zero rates."""
    def env(d):
        m = _arm(d, "env_random_intent")["metrics"]
        m.update(episode_violation_rate=0.1, n_scenarios=50, seeds=[0, 1, 2])

    _edit(copy, "metrics.json", env)
    _edit(copy, "boundary_eval.json", lambda d: d["models"]["sft"].update(n=141, boundary_pass_rate=0.95))
    rows = _rows(lab_rows(copy))
    assert rows["env_random_intent"].split.n == 150
    assert rows["env_random_intent"].failures == 15  # round(0.1 * 50 * 3)
    assert rows["sft"].failures == 141 - round(0.95 * 141) == 7

