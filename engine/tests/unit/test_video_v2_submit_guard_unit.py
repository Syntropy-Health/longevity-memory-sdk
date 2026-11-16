"""HAC-99: make_video_v2.py `presenter` never submits a second paid render after a failed submit.

The HeyGen calls are stubbed (`api`, `wallet`) and urlopen is made to fail, so nothing here touches
the network or spends anything.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import urllib.request
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "docs" / "daypart" / "submission" / "video" / "v2" / "make_video_v2.py"


@pytest.fixture()
def mv(monkeypatch):
    spec = importlib.util.spec_from_file_location("make_video_v2_under_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    def no_network(*a, **k):
        raise AssertionError("network call in a stubbed test")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.setattr(urllib.request, "urlretrieve", no_network)
    monkeypatch.setattr(mod, "wallet", lambda key: 10.0)
    monkeypatch.setenv("HEYGEN_API_KEY", "test-key-not-real")
    return mod


@pytest.fixture()
def work(tmp_path: Path) -> Path:
    (tmp_path / "timeline.json").write_text(json.dumps(
        {"presenter_secs": 59.2, "presenter": {"avatar_id": "av", "engine": "avatar_v"}}))
    (tmp_path / "presenter.wav").write_bytes(b"RIFF0000WAVE")
    return tmp_path


def args(work: Path) -> argparse.Namespace:
    return argparse.Namespace(work=str(work), cap_usd=30.0, poll_timeout=0.0)


def stub_api(monkeypatch, mod, video_post):
    """Record every call; answer the asset upload and the poll; `video_post` answers POST /v3/videos."""
    calls: list[tuple[str, str]] = []

    def api(method, path, key, body=None, raw=None, ctype=None):
        calls.append((method, path))
        if (method, path) == ("POST", "/v3/assets"):
            return {"data": {"asset_id": "asset-1"}}
        if (method, path) == ("POST", "/v3/videos"):
            return video_post()
        if method == "GET" and path.startswith("/v3/videos/"):
            return {"data": {"status": "failed", "failure_message": "stub", "duration": None}}
        raise AssertionError(f"unexpected call {method} {path}")

    monkeypatch.setattr(mod, "api", api)
    return calls


def posts(calls) -> int:
    return calls.count(("POST", "/v3/videos"))


def test_missing_id_raises_and_writes_no_null_video_id(mv, work, monkeypatch):
    calls = stub_api(monkeypatch, mv, lambda: {"data": {"status": "pending"}})
    with pytest.raises(SystemExit, match="no video id"):
        mv.presenter(args(work))
    assert posts(calls) == 1
    log = json.loads((work / "presenter.json").read_text())
    assert "video_id" not in log
    assert log["status"] == "submitting"


def test_rerun_after_missing_id_does_not_post_again(mv, work, monkeypatch):
    calls = stub_api(monkeypatch, mv, lambda: {"data": {}})
    with pytest.raises(SystemExit):
        mv.presenter(args(work))
    calls.clear()
    with pytest.raises(SystemExit, match="Check the wallet"):
        mv.presenter(args(work))
    assert calls == []  # no upload, no submit, no poll


def test_rerun_after_post_timeout_does_not_post_again(mv, work, monkeypatch):
    def timeout():
        raise TimeoutError("read timed out")

    calls = stub_api(monkeypatch, mv, timeout)
    with pytest.raises(TimeoutError):
        mv.presenter(args(work))
    assert json.loads((work / "presenter.json").read_text())["status"] == "submitting"
    calls.clear()
    with pytest.raises(SystemExit, match="Check the wallet"):
        mv.presenter(args(work))
    assert calls == []


def test_returned_id_is_recorded_and_polled(mv, work, monkeypatch):
    calls = stub_api(monkeypatch, mv, lambda: {"data": {"video_id": "vid-1"}})
    mv.presenter(args(work))
    assert posts(calls) == 1
    assert ("GET", "/v3/videos/vid-1") in calls
    log = json.loads((work / "presenter.json").read_text())
    assert log["video_id"] == "vid-1"
    assert log["status"] == "failed"  # the stubbed poll's verdict replaced `submitted`


def test_operator_supplied_id_resumes_polling_without_posting(mv, work, monkeypatch):
    (work / "presenter.json").write_text(json.dumps({"status": "submitting", "video_id": "vid-2", "wallet_before_usd": 10.0}))
    calls = stub_api(monkeypatch, mv, lambda: pytest.fail("must not submit"))
    mv.presenter(args(work))
    assert posts(calls) == 0
    assert ("GET", "/v3/videos/vid-2") in calls


def test_readme_states_plan_before_docs():
    readme = (SCRIPT.parent / "README.md").read_text()
    assert "run `plan` first (free) and then `docs`" in readme
