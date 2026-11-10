"""Run the SC1 API journey against a deployed demo and fail on the first wrong step (HAC-38).

The deploy job used to smoke ``/api/health`` only, so the hosted passport returned 500 from the P2
land until the plan-complete land without any check noticing (CTO hand-back 3172f7da). This walks
the member journey the submission promises, with synthetic member ``syn-001``:

journal → next step before a save (409) → text check-in → review (confirm all) → passport (200,
both saved values shown as observed) → next step → choose → lab → refused real-input mode (403).

Standard library only, so CI runs it without the engine's dependencies::

    uv run --no-project python tools/smoke_journey.py https://supermomo668--daypart-demo-playground.us-east.modal.run

Run from ``engine/``, as the ``deploy-demo`` CI job does. Exit status 0 when every step passes, 1 on
the first failure: a wrong status, a network error or a malformed body prints ``FAIL <step>: …``.
The journey is synthetic and writes only to an in-memory demo journal (A&D D-A3).
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

MEMBER = "syn-001"
TEXT = "slept 6 hours and walked 8000 steps"
EXPECTED_VALUES = (6.0, 8000.0)

# (method, path, json body or None) -> (status, parsed json body or None)
Transport = Callable[[str, str, Any], tuple[int, Any]]


class SmokeFailure(AssertionError):
    pass


def http_transport(base: str, timeout: float = 180.0) -> Transport:
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
        raise SmokeFailure(f"{step}: {type(e).__name__}: {e}") from e
    if code != status:
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
    ap.add_argument("--timeout", type=float, default=180.0, help="seconds per request (cold starts are slow)")
    args = ap.parse_args(argv)
    try:
        run(http_transport(args.base_url, args.timeout))
    except SmokeFailure as e:
        print(f"FAIL {e}", file=sys.stderr)
        return 1
    print("SC1 journey ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
