"""T1.4 (HAC-38 plan task 13): the Streamlit dashboard is the "research view" of the Clinical Human Clone.

The page title and the page header say "Clinical Human Clone: research view". ``main()`` is run against a
stand-in for ``streamlit`` that records every heading (page title, ``title``, ``header``, ``subheader``,
heading markdown) and accepts any other call as a no-op, so the test needs no Streamlit runtime.
"T1.4 headers" is read as the page title plus the ``st.title`` header; section subheaders keep their
descriptive names but must not carry the old Daypart names (addendum G28).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from daypart.demo import dashboard

NAME = "Clinical Human Clone: research view"
MISSING = "/nonexistent/metrics.json"


class _Stop(Exception):
    pass


class _Noop:
    """Any Streamlit call that is not a heading: callable, chainable, usable as a context manager."""

    def __call__(self, *a: Any, **kw: Any) -> _Noop:
        return self

    def __getattr__(self, name: str) -> _Noop:
        return self

    def __getitem__(self, key: Any) -> _Noop:
        return self

    def __enter__(self) -> _Noop:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class _FakeSt:
    def __init__(self, *, bare_stop: bool = False) -> None:
        self.page_config: dict[str, Any] = {}
        self.titles: list[str] = []
        self.headings: list[str] = []
        self.errors: list[str] = []
        self.bare_stop = bare_stop

    def set_page_config(self, *a: Any, **kw: Any) -> None:
        if a:
            kw.setdefault("page_title", a[0])
        self.page_config = kw

    def title(self, body: str, *a: Any, **kw: Any) -> None:
        self.titles.append(body)
        self.headings.append(body)

    def header(self, body: str, *a: Any, **kw: Any) -> None:
        self.headings.append(body)

    def subheader(self, body: str, *a: Any, **kw: Any) -> None:
        self.headings.append(body)

    def markdown(self, body: str, *a: Any, **kw: Any) -> None:
        if body.lstrip().startswith("#") or body.lstrip().startswith("**"):
            self.headings.append(body)

    def error(self, body: Any, *a: Any, **kw: Any) -> None:
        self.errors.append(str(body))

    def stop(self) -> None:
        # Under ``streamlit run`` stop() raises; outside a script run ("bare mode") it returns.
        if not self.bare_stop:
            raise _Stop

    def columns(self, spec: Any, *a: Any, **kw: Any) -> list[_Noop]:
        n = spec if isinstance(spec, int) else len(spec)
        return [_Noop() for _ in range(n)]

    def __getattr__(self, name: str) -> _Noop:
        return _Noop()


def _run(monkeypatch: pytest.MonkeyPatch, argv: list[str], **kw: Any) -> _FakeSt:
    fake = _FakeSt(**kw)
    monkeypatch.setattr(dashboard, "st", fake)
    monkeypatch.setattr(sys, "argv", ["dashboard.py", *argv])
    try:
        dashboard.main()
    except _Stop:
        pass
    return fake


@pytest.fixture
def shown(monkeypatch: pytest.MonkeyPatch) -> _FakeSt:
    """The whole page, rendered from the committed results."""
    return _run(monkeypatch, [])


def test_page_title_is_the_research_view(shown: _FakeSt) -> None:
    assert shown.page_config.get("page_title") == NAME


def test_page_header_is_the_research_view(shown: _FakeSt) -> None:
    assert shown.titles == [NAME]


def test_full_page_rendered(shown: _FakeSt) -> None:
    assert len(shown.headings) > 1  # the run reached the section subheaders, not just the title


def test_old_daypart_names_are_gone(shown: _FakeSt) -> None:
    for text in [shown.page_config.get("page_title", ""), *shown.headings]:
        assert "Daypart" not in text and "benchmark" not in text.lower(), text


def test_constants_name_the_research_view() -> None:
    assert dashboard.PAGE_TITLE == NAME
    assert dashboard.PAGE_HEADER == NAME


def test_missing_metrics_shows_error_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _run(monkeypatch, ["--metrics", MISSING])
    assert fake.titles == [NAME]
    assert len(fake.errors) == 1 and "no metrics file" in fake.errors[0]


def test_missing_metrics_in_bare_mode_returns_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Outside a script run ``st.stop()`` returns; ``main()`` must not go on to read an unset ``doc``."""
    fake = _run(monkeypatch, ["--metrics", MISSING], bare_stop=True)
    assert len(fake.errors) == 1
    assert fake.headings == [NAME]  # nothing after the error was drawn


def test_import_does_not_render_the_page() -> None:
    """Importing the module (pytest collection, a sealed test) must not run ``main()``.

    QG P3 K2: a stub ``streamlit`` records every call; a bare import must record none (the exit code and
    stderr alone pass even when ``main()`` runs, because a bare-mode ``st.stop()`` returns quietly)."""
    engine = Path(__file__).resolve().parents[2]
    env = {**os.environ, "DAYPART_METRICS": MISSING}
    env.pop("MUSE_API_KEY", None)
    probe = (
        "import json, sys, types\n"
        "calls = []\n"
        "class Rec:\n"
        "    def __init__(self, name): self.name = name\n"
        "    def __call__(self, *a, **k): calls.append(self.name); return Rec(self.name + '()')\n"
        "    def __getattr__(self, n): return Rec(self.name + '.' + n)\n"
        "    def __enter__(self): return self\n"
        "    def __exit__(self, *a): return False\n"
        "    def __iter__(self): return iter([Rec(self.name + '[0]'), Rec(self.name + '[1]'), Rec(self.name + '[2]')])\n"
        "st = types.ModuleType('streamlit')\n"
        "st.__getattr__ = lambda n: Rec('st.' + n)\n"
        "sys.modules['streamlit'] = st\n"
        "import daypart.demo.dashboard\n"
        "print(json.dumps(calls))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe], cwd=engine, env=env, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert json.loads(proc.stdout.strip().splitlines()[-1]) == []
