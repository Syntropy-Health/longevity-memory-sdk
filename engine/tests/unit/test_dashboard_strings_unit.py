"""T1.4 (HAC-38 plan task 13): the Streamlit dashboard is the "research view" of the Clinical Human Clone.

The page title and the page header say "Clinical Human Clone: research view". ``main()`` is run against a
stand-in for ``streamlit`` that records the two calls and stops at the first other call, so the test needs
no Streamlit runtime.
"""

from __future__ import annotations

from typing import Any

import pytest

from daypart.demo import dashboard

NAME = "Clinical Human Clone: research view"


class _Stop(Exception):
    pass


class _FakeSt:
    def __init__(self) -> None:
        self.page_config: dict[str, Any] = {}
        self.titles: list[str] = []

    def set_page_config(self, **kw: Any) -> None:
        self.page_config = kw

    def title(self, text: str) -> None:
        self.titles.append(text)

    def __getattr__(self, name: str) -> Any:  # anything after the header ends the run
        raise _Stop(name)


@pytest.fixture
def shown(monkeypatch: pytest.MonkeyPatch) -> _FakeSt:
    fake = _FakeSt()
    monkeypatch.setattr(dashboard, "st", fake)
    with pytest.raises(_Stop):
        dashboard.main()
    return fake


def test_page_title_is_the_research_view(shown: _FakeSt) -> None:
    assert shown.page_config.get("page_title") == NAME


def test_page_header_is_the_research_view(shown: _FakeSt) -> None:
    assert shown.titles == [NAME]


def test_old_daypart_names_are_gone(shown: _FakeSt) -> None:
    for text in [shown.page_config.get("page_title", ""), *shown.titles]:
        assert "Daypart" not in text and "benchmark" not in text.lower()


def test_constants_name_the_research_view() -> None:
    assert dashboard.PAGE_TITLE == NAME
    assert dashboard.PAGE_HEADER == NAME
