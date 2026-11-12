"""HAC-86: the submission deck at /deck in headless Chromium.

Keyboard, click and hash navigation; axe (the vendored, sha-pinned copy) at desktop and phone width;
no horizontal page scroll; ?export=1 lays every slide out at 1600x900 for the PDF and the video frames.
Skipped like test_journey_a11y.py unless the `ui` group is installed; DAYPART_UI_REQUIRED=1 makes it required.
"""

from __future__ import annotations

import hashlib
import os
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

REQUIRED = os.environ.get("DAYPART_UI_REQUIRED") == "1"

try:
    from playwright.sync_api import Browser, Page, expect, sync_playwright
except ImportError:
    if REQUIRED:
        raise
    pytest.skip("playwright not installed (uv sync --group ui)", allow_module_level=True)

import uvicorn

from daypart.demo.app import create_app

VENDOR = Path(__file__).parent / "vendor"
AXE_SHA256 = "c24f097bd2f451d4f933e8bc7d8d539f8672a2ebcb5cc9f9f3eec8ca9470a0c1"
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
DESKTOP = {"width": 1280, "height": 800}
MOBILE = {"width": 375, "height": 812}
N = 10


@pytest.fixture(scope="module")
def axe_source() -> str:
    raw = (VENDOR / "axe.min.js").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == AXE_SHA256
    return raw.decode("utf-8")


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError("demo app did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    exe = os.environ.get("DAYPART_UI_CHROMIUM") or None
    with sync_playwright() as pw:
        try:
            b = pw.chromium.launch(executable_path=exe)
        except Exception as e:
            if REQUIRED:
                raise
            pytest.skip(f"chromium unavailable: {e}")
        yield b
        b.close()


def _page(browser: Browser, errors: list[str], viewport: dict) -> Page:
    # reduced motion: no slide transition, so axe measures the settled slide, not one mid-fade
    p = browser.new_context(viewport=viewport, reduced_motion="reduce").new_page()
    p.on("pageerror", lambda e: errors.append(str(e)))
    return p


def _axe(page: Page, axe_source: str) -> list:
    if not page.evaluate("typeof window.axe !== 'undefined'"):
        page.add_script_tag(content=axe_source)
    return page.evaluate(
        "async (tags) => (await axe.run(document, {runOnly: {type: 'tag', values: tags}}))"
        ".violations.map(v => ({id: v.id, nodes: v.nodes.map(n => n.target)}))",
        AXE_TAGS,
    )


def test_keyboard_click_and_hash_navigation(browser: Browser, base_url: str):
    errors: list[str] = []
    page = _page(browser, errors, DESKTOP)
    page.goto(f"{base_url}/deck")
    current = page.locator(".slide.is-current")
    expect(current).to_have_attribute("id", "s1")
    expect(page.locator("#count")).to_have_text(f"1 / {N}")
    page.keyboard.press("ArrowRight")
    expect(current).to_have_attribute("id", "s2")
    assert page.evaluate("location.hash") == "#/2"
    page.keyboard.press("End")
    expect(current).to_have_attribute("id", f"s{N}")
    expect(page.locator("#next")).to_be_disabled()
    page.keyboard.press("Home")
    expect(current).to_have_attribute("id", "s1")
    page.click("#next")
    expect(current).to_have_attribute("id", "s2")
    page.click(".sections a[data-section='technical']")
    expect(current).to_have_attribute("data-section", "technical")
    expect(page.locator(".sections a[data-section='technical']")).to_have_attribute("aria-current", "true")
    page.keyboard.press("n")
    expect(page.locator("#notes-panel")).to_be_visible()
    expect(page.locator("#notes-body")).to_contain_text("Ledger rows:")
    page.goto(f"{base_url}/deck#/9")
    expect(page.locator(".slide.is-current")).to_have_attribute("id", "s9")
    # only the current slide is exposed to assistive technology
    assert page.locator(".slide[aria-hidden='false']").count() == 1
    assert errors == []


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["1280", "375"])
def test_axe_clean_and_no_horizontal_scroll(browser: Browser, base_url: str, axe_source: str, viewport):
    errors: list[str] = []
    page = _page(browser, errors, viewport)
    page.goto(f"{base_url}/deck")
    expect(page.locator(".slide").first).to_be_visible()
    if viewport is MOBILE:  # phone width: every slide is on the one page; one axe run covers them all
        assert page.evaluate("document.documentElement.scrollWidth") <= viewport["width"]
        assert _axe(page, axe_source) == []
    else:  # presenting: only the current slide is rendered, so check each one
        for i in range(1, N + 1):
            page.evaluate(f"location.hash = '#/{i}'")
            expect(page.locator(".slide.is-current")).to_have_attribute("id", f"s{i}")
            assert page.evaluate("document.documentElement.scrollWidth") <= viewport["width"]
            assert _axe(page, axe_source) == [], f"slide {i}"
    assert errors == []


def test_export_lays_out_every_slide_at_1600x900(browser: Browser, base_url: str):
    errors: list[str] = []
    page = _page(browser, errors, {"width": 1600, "height": 900})
    page.goto(f"{base_url}/deck?export=1")
    slides = page.locator("section.slide")
    expect(slides).to_have_count(N)
    for i in range(N):
        box = slides.nth(i).bounding_box()
        assert box and round(box["width"]) == 1600 and round(box["height"]) == 900
        # nothing on the slide spills past its frame
        over = slides.nth(i).evaluate(
            "s => [...s.querySelectorAll('.frame > *')].filter(e => e.getBoundingClientRect().bottom > s.getBoundingClientRect().bottom + 1).length"
        )
        assert over == 0, f"slide {i + 1} overflows"
    assert page.locator(".nav").is_hidden()
    assert errors == []
