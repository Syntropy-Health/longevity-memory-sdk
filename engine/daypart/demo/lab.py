"""Learning lab rows (A&D §4.8, R8 provenance, AD6): every field from a formula over the committed JSON.

``lab_rows(results_dir)`` reads ``boundary_eval.json``, ``training.json``, ``metrics.json`` and
``pipeline.json``. A missing, malformed or non-numeric source field is ``None`` (the UI renders
``NOT_RECORDED``); a row's number is shown only when its own source fields exist. An sft/dpo row
whose adapter does not match ``training.json`` is ``PROVENANCE_MISMATCH`` with no number. grpo is
``PROPOSED`` with its reason and no number. The lab always renders.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import pydantic
from pydantic import ConfigDict

FOOTER = "Simulated outcomes are not patient outcomes."
NOT_RECORDED = "not recorded"
PROPOSED = "proposed, not built"
PROVENANCE_MISMATCH = "provenance mismatch"
MODEL_ROWS: tuple[str, ...] = ("base", "sft", "dpo")
DIGEST_CHARS = 12

Status = Literal["ok", "provenance mismatch", "proposed, not built"]


class Split(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt_set_version: str | None = None  # model rows
    n: int | None = None  # prompts (model rows) or episodes = n_scenarios x len(seeds) (env rows)
    training_rows: int | None = None  # sft/dpo
    data_sha256: str | None = None  # sft/dpo
    n_scenarios: int | None = None  # env rows
    horizon: int | None = None  # env rows


class LabRow(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    row: str
    kind: Literal["model", "env_baseline", "proposed"]
    status: Status
    run_id: str | None = None
    file_digest: str | None = None  # base only: sha256(boundary_eval.json)[:12], a file digest
    split: Split | None = None
    seed: int | list[int] | None = None  # model rows: meta.seed; env rows: the arm's seeds
    cohort_seed: int | None = None  # sft/dpo: meta.cohort_seed
    failures: int | None = None
    degenerate: int | None = None  # model rows, shown separately from failures
    metrics: dict[str, float | None] = {}
    gate: dict[str, Any] | None = None  # sft: r3, dpo: r4, as recorded
    reason: str | None = None  # grpo


class LabTable(pydantic.BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[LabRow, ...]
    member_failure_count: int | None
    i1_passed: bool | None
    footer: str = FOOTER


# --- tolerant readers -----------------------------------------------------------------------------


def _read(d: Path, name: str) -> tuple[dict[str, Any], bytes | None]:
    try:
        raw = (d / name).read_bytes()
        data = json.loads(raw)
    except (OSError, ValueError, RecursionError):
        return {}, None
    return (data, raw) if isinstance(data, dict) else ({}, None)


def _get(obj: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(obj, Mapping):
            return None
        obj = obj.get(key)
    return obj


def _num(v: Any) -> float | None:
    """A finite number, else None: NaN, +-Infinity and values too large for a float are not numbers."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except OverflowError:
        return None
    return f if math.isfinite(f) else None


def _int(v: Any) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _str(v: Any) -> str | None:
    return v if isinstance(v, str) and v else None


def _basename(v: Any) -> str | None:
    s = _str(v)
    return PurePosixPath(s).name or None if s is not None else None


def _round_product(rate: float, count: int) -> int | None:
    """round(rate * count), or None when the product is not a finite number (a huge count)."""
    try:
        return round(rate * count)
    except (OverflowError, ValueError):
        return None


def _failures(n: int | None, rate: float | None) -> int | None:
    if n is None or rate is None:
        return None
    passed = _round_product(rate, n)
    return n - passed if passed is not None else None


# --- rows ----------------------------------------------------------------------------------------


def _model_row(name: str, be: Mapping[str, Any], be_raw: bytes | None, tr: Mapping[str, Any],
               pl: Mapping[str, Any]) -> LabRow:
    m = _get(be, "models", name)
    n = _int(_get(m, "n"))
    rate = _num(_get(m, "boundary_pass_rate"))
    tag = _str(pl.get("tag"))
    split = Split(prompt_set_version=_str(be.get("prompt_set_version")), n=n)
    metrics = {"boundary_pass_rate": rate, "rubric_pass_rate": _num(_get(m, "rubric_pass_rate"))}
    common: dict[str, Any] = {"row": name, "kind": "model", "seed": _int(_get(be, "meta", "seed")),
                              "failures": _failures(n, rate), "degenerate": _int(_get(m, "degenerate"))}
    if name == "base":
        digest = hashlib.sha256(be_raw).hexdigest()[:DIGEST_CHARS] if be_raw is not None else None
        return LabRow(status="ok", run_id=f"{tag}/base" if tag else None, file_digest=digest, split=split,
                      metrics=metrics, **common)
    adapter = _basename(_get(be, "meta", "adapters", name))
    run_id = f"{tag}/{adapter}" if tag and adapter else None
    split = split.model_copy(update={"training_rows": _int(_get(tr, name, "rows")),
                                     "data_sha256": _str(_get(pl, "data", f"{name}_sha256"))})
    if adapter is None or adapter != _basename(_get(tr, name, "adapter")):
        # The cross-check failed: provenance only, no number (A&D §4.8).
        return LabRow(row=name, kind="model", status=PROVENANCE_MISMATCH, run_id=run_id,
                      split=Split(prompt_set_version=split.prompt_set_version, data_sha256=split.data_sha256),
                      metrics=dict.fromkeys(metrics))
    gate = _get(be, "r3" if name == "sft" else "r4")
    return LabRow(status="ok", run_id=run_id, split=split, cohort_seed=_int(_get(be, "meta", "cohort_seed")),
                  metrics=metrics, gate=dict(gate) if isinstance(gate, Mapping) else None, **common)


def _env_row(arm: Mapping[str, Any], mx: Mapping[str, Any], name: str) -> LabRow:
    m = arm.get("metrics") if isinstance(arm.get("metrics"), Mapping) else {}
    version, digest = _str(mx.get("runs_version")), _str(mx.get("runs_digest"))
    raw_seeds = _get(m, "seeds")
    seeds = [s for s in raw_seeds if _int(s) is not None] if isinstance(raw_seeds, list) else None
    if seeds is not None and len(seeds) != len(raw_seeds or []):
        seeds = None
    n_sc, rate = _int(_get(m, "n_scenarios")), _num(_get(m, "episode_violation_rate"))
    episodes = n_sc * len(seeds) if n_sc is not None and seeds is not None else None
    return LabRow(
        row=name,
        kind="env_baseline",
        status="ok",
        run_id=f"{version}@{digest[:DIGEST_CHARS]}/{name}" if version and digest else None,
        split=Split(n=episodes, n_scenarios=n_sc, horizon=_int(_get(m, "horizon"))),
        seed=seeds,
        failures=_round_product(rate, episodes) if rate is not None and episodes is not None else None,
        metrics={"mean_adherence": _num(_get(m, "mean_adherence")), "episode_violation_rate": rate},
    )


def _grpo_row(arms: list[Mapping[str, Any]]) -> LabRow:
    arm = next((a for a in arms if a.get("name") == "grpo"), {})
    return LabRow(row="grpo", kind="proposed", status=PROPOSED, reason=_str(arm.get("reason")))


def _default_dir() -> Path:
    from daypart.demo.dashboard_data import default_metrics_path, results_dir

    return results_dir(default_metrics_path())


def lab_rows(results_dir: str | os.PathLike[str] | None = None) -> LabTable:
    """The lab table over ``results_dir`` (default: the committed ``docs/daypart/results``)."""
    d = Path(results_dir) if results_dir is not None else _default_dir()
    be, be_raw = _read(d, "boundary_eval.json")
    tr, _ = _read(d, "training.json")
    mx, _ = _read(d, "metrics.json")
    pl, _ = _read(d, "pipeline.json")
    arms = [a for a in mx.get("arms", []) if isinstance(a, Mapping)] if isinstance(mx.get("arms"), list) else []
    rows = [_model_row(name, be, be_raw, tr, pl) for name in MODEL_ROWS]
    # An arm with no string name is left out: a row name or run id is never invented (AD6, G25).
    rows += [_env_row(a, mx, name) for a in arms
             if a.get("kind") == "env_baseline" and a.get("status") == "ok" and (name := _str(a.get("name")))]
    rows.append(_grpo_row(arms))
    i1 = next((a for a in arms if a.get("name") == "i1_gate"), None)
    passed = _get(i1, "metrics", "passed")
    return LabTable(
        rows=tuple(rows),
        member_failure_count=_int(_get(pl, "data", "member_failure_count")),
        i1_passed=passed if isinstance(passed, bool) else None,
    )


__all__ = [
    "FOOTER",
    "NOT_RECORDED",
    "PROPOSED",
    "PROVENANCE_MISMATCH",
    "LabRow",
    "LabTable",
    "Split",
    "lab_rows",
]
