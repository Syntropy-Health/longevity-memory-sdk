"""HAC-38 P6.1 (AM-2 D1, addendum G31): two served surfaces from one page source.

``static/index.html`` marks member-only and admin-only blocks; ``render_surface`` keeps one side and
drops the other, so the member app at ``/`` carries no research-console markup at all and the
research console at ``/admin`` carries no member journey. Markers that are unbalanced, nested or
unknown fail at startup, never at request time.
"""

from __future__ import annotations

import pytest

from daypart.demo.surfaces import SURFACES, SurfaceMarkupError, render_surface


def test_surfaces():
    assert SURFACES == ("member", "admin")


def test_keeps_own_blocks_and_drops_the_other():
    src = "a<!--@member-->M<!--/@member-->b<!--@admin-->A<!--/@admin-->c"
    assert render_surface(src, "member") == "aMbc"
    assert render_surface(src, "admin") == "abAc"


def test_js_comment_markers():
    src = "x;/*@member*/var S=1;/*/@member*//*@admin*/var S=2;/*/@admin*/y;"
    assert render_surface(src, "member") == "x;var S=1;y;"
    assert render_surface(src, "admin") == "x;var S=2;y;"


def test_multiline_blocks():
    src = "<p>shared</p>\n<!--@admin-->\n<section>\nlab\n</section>\n<!--/@admin-->\n<p>end</p>"
    assert render_surface(src, "member") == "<p>shared</p>\n\n<p>end</p>"
    assert "lab" in render_surface(src, "admin")


def test_unmarked_source_is_unchanged():
    assert render_surface("<p>plain</p>", "admin") == "<p>plain</p>"


@pytest.mark.parametrize(
    "src",
    [
        "<!--@member-->open",  # never closed
        "close<!--/@member-->",  # closed, never opened
        "<!--@member--><!--@admin-->x<!--/@admin--><!--/@member-->",  # nested
        "<!--@member-->x<!--/@admin-->",  # closed with the other name
    ],
)
def test_bad_markup_fails(src):
    with pytest.raises(SurfaceMarkupError):
        render_surface(src, "member")


def test_unknown_surface_fails():
    with pytest.raises(ValueError):
        render_surface("x", "staff")


def test_served_page_has_no_markers_left():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "daypart/demo/static/index.html").read_text()
    for s in SURFACES:
        out = render_surface(src, s)
        assert "@member" not in out and "@admin" not in out
