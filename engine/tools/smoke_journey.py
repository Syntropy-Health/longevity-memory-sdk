"""Run the SC1 API journey against a deployed demo and fail on the first wrong step (HAC-38).

The deploy job used to smoke ``/api/health`` only, so the hosted passport returned 500 from the P2
land until the plan-complete land without any check noticing (CTO hand-back 3172f7da). This walks
the member journey the submission promises, with synthetic member ``syn-001``:

journal → next step before a save (409) → text check-in → review (confirm all) → passport (200,
both saved values shown as observed) → next step → choose → lab → refused real-input mode (403).

Standard library only, so CI runs it without the engine's dependencies::

    uv run --no-project python tools/smoke_journey.py https://supermomo668--daypart-demo-playground.us-east.modal.run

Run from ``engine/``, as the ``deploy-demo`` CI job does. Exit status 0 when every step passes, 1 on
failure: a wrong status, a network error or a malformed body prints ``FAIL <step>: …``.
The journey is synthetic and writes only to an in-memory demo journal (A&D D-A3).

Rollover (P5.2, CTO hand-back 83506a31): right after ``modal deploy`` the old and new containers
both serve for a while, and journals live in memory per container, so a call can reach a container
that never saw the journal and get 404 ``unknown_journal`` (or ``unknown_checkin``). Only that miss
and a network error are retried: the whole journey starts over with a fresh journal, up to
``TRIES`` times with growing back-off. No retry starts once it would begin past ``BUDGET_S``
(180 s) from the first try; each request is capped by ``--timeout`` (60 s), and the CI step's
``timeout-minutes`` caps the whole run. A 500, any other wrong status, a wrong value or a malformed
body fails on the first try.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

MEMBER = "syn-001"
TEXT = "slept 6 hours and walked 8000 steps"
EXPECTED_VALUES = (6.0, 8000.0)

# (method, path, json body or None) -> (status, parsed json body or None)
Transport = Callable[[str, str, Any], tuple[int, Any]]


# A 404 with one of these codes means the call reached a container without the journal (rollover).
ROLLOVER_ERRORS = frozenset({"unknown_journal", "unknown_checkin"})
TRIES = 5
BACKOFF_S = (10.0, 20.0, 30.0, 40.0)  # sleeps between tries; 100 s total
BUDGET_S = 180.0

# Indirection so tests can drive the clock and skip real sleeps.
_sleep = time.sleep
_clock = time.monotonic


class SmokeFailure(AssertionError):
    pass


class RolloverMiss(SmokeFailure):
    """A failure the rollover can explain: retry the journey with a fresh journal."""


REQUEST_TIMEOUT_S = 60.0  # the health checks before this step already woke the container


def http_transport(base: str, timeout: float = REQUEST_TIMEOUT_S) -> Transport:
    base = base.rstrip("/")

    def call(method: str, path: str, body: Any) -> tuple[int, Any]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(base + path, data=data, method=method)
        if data is not None:
            req.add_header("content-type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        try:
            return status, json.loads(raw) if raw else None
        except ValueError:
            return status, None

    return call


def _expect(step: str, call: Transport, method: str, path: str, body: Any, status: int) -> Any:
    """Make one call; fail with the step name on a network error, a wrong status or a non-object body."""
    try:
        code, data = call(method, path, body)
    except (OSError, ValueError) as e:  # URLError, TimeoutError, connection reset, bad URL
        raise RolloverMiss(f"{step}: {type(e).__name__}: {e}") from e
    if code != status:
        if code == 404 and isinstance(data, dict) and data.get("error") in ROLLOVER_ERRORS:
            raise RolloverMiss(f"{step}: expected {status}, got 404: {json.dumps(data)[:500]}")
        raise SmokeFailure(f"{step}: expected {status}, got {code}: {json.dumps(data)[:500]}")
    if not isinstance(data, dict):
        raise SmokeFailure(f"{step}: expected a JSON object, got {json.dumps(data)[:500]}")
    print(f"ok  {step}: {code}")
    return data


def run(call: Transport) -> None:
    try:
        _run(call)
    except (KeyError, TypeError, ValueError, AttributeError) as e:  # a 2xx body without the fields
        raise SmokeFailure(f"malformed response: {type(e).__name__}: {e}") from e


def run_with_retry(call: Transport, tries: int = TRIES, budget: float = BUDGET_S) -> None:
    """Run the journey; on a rollover miss start over with a fresh journal, within tries and budget."""
    start = _clock()
    for attempt in range(1, tries + 1):
        try:
            run(call)
            return
        except RolloverMiss as e:
            delay = BACKOFF_S[min(attempt - 1, len(BACKOFF_S) - 1)]
            if attempt == tries or _clock() - start + delay > budget:
                raise SmokeFailure(f"{e} (after {attempt} tries)") from e
            print(f"retry {attempt}/{tries - 1} in {delay:.0f}s (deploy rollover?): {e}")
            _sleep(delay)


def _run(call: Transport) -> None:
    jid = _expect("create journal", call, "POST", "/api/journals", {"member_id": MEMBER}, 201)["journal_id"]
    body = _expect("next step before any save", call, "GET", f"/api/journals/{jid}/next-step", None, 409)
    if body.get("error") != "no_saved_checkin":
        raise SmokeFailure(f"next step before any save: expected no_saved_checkin, got {body}")

    ck = _expect("text check-in", call, "POST", "/api/checkins", {"journal_id": jid, "text": TEXT}, 201)
    proposed = sorted(float(p["value"]) for p in ck["proposals"])
    if tuple(proposed) != EXPECTED_VALUES:
        raise SmokeFailure(f"text check-in: expected values {EXPECTED_VALUES}, got {proposed}")
    decisions = [{"proposal_id": p["proposal_id"], "action": "confirm"} for p in ck["proposals"]]
    _expect("review, confirm all", call, "POST", f"/api/checkins/{ck['checkin_id']}/review", {"decisions": decisions}, 200)

    pp = _expect("passport", call, "GET", f"/api/journals/{jid}/passport", None, 200)
    observed = sorted(float(c["value"]) for c in pp.get("cards", []) if c.get("origin") == "observed")
    if tuple(observed) != EXPECTED_VALUES:
        raise SmokeFailure(f"passport: expected observed values {EXPECTED_VALUES}, got {observed}")

    step = _expect("next step", call, "GET", f"/api/journals/{jid}/next-step", None, 200)
    choice = {"step_id": step["step_id"], "choice": "choose"}
    _expect("choose next step", call, "POST", f"/api/journals/{jid}/next-step", choice, 200)
    lab = _expect("lab", call, "GET", "/api/lab", None, 200)
    if not lab.get("rows"):
        raise SmokeFailure("lab: no rows")
    _expect("real-input mode refused", call, "POST", "/api/mode", {"real_input": True}, 403)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("base_url", help="the deployed playground, e.g. https://…-playground.us-east.modal.run")
    ap.add_argument("--timeout", type=float, default=REQUEST_TIMEOUT_S, help="seconds per request")
    args = ap.parse_args(argv)
    try:
        run_with_retry(http_transport(args.base_url, args.timeout))
    except SmokeFailure as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    print("SC1 journey ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
