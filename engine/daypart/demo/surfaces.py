"""Two served surfaces from one page source (HAC-38 AM-2 D1, addendum G31).

``static/index.html`` holds the shared styles and helpers once, and marks the blocks that belong to
one surface only: ``<!--@member-->…<!--/@member-->`` in markup and ``/*@member*/…/*/@member*/`` in
script (``admin`` likewise). :func:`render_surface` keeps the requested surface's blocks, drops the
other's, and removes every marker, so the member app at ``/`` carries no research-console markup and
the research console at ``/admin`` carries no member journey. The app renders both once at startup,
so a malformed marker fails the build, never a request.
"""

from __future__ import annotations

import re

SURFACES = ("member", "admin")
_MARK = re.compile(r"(?:<!--|/\*)(/?)@(member|admin)(?:-->|\*/)")


class SurfaceMarkupError(ValueError):
    """Unbalanced, nested or mismatched surface markers."""


def render_surface(source: str, surface: str) -> str:
    """``source`` with ``surface``'s blocks kept (markers removed) and every other block dropped."""
    if surface not in SURFACES:
        raise ValueError(f"unknown surface {surface!r}; expected one of {SURFACES}")
    out: list[str] = []
    pos = 0
    open_name: str | None = None
    for m in _MARK.finditer(source):
        closing, name = m.group(1) == "/", m.group(2)
        if not closing:
            if open_name is not None:
                raise SurfaceMarkupError(f"@{name} opened inside @{open_name} at offset {m.start()}")
            out.append(source[pos : m.start()])
            open_name = name
        else:
            if open_name != name:
                raise SurfaceMarkupError(f"/@{name} closes {'@' + open_name if open_name else 'nothing'} at offset {m.start()}")
            if name == surface:
                out.append(source[pos : m.start()])
            open_name = None
        pos = m.end()
    if open_name is not None:
        raise SurfaceMarkupError(f"@{open_name} is never closed")
    out.append(source[pos:])
    return "".join(out)


__all__ = ["SURFACES", "SurfaceMarkupError", "render_surface"]
