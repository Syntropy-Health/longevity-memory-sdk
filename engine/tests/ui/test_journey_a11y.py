"""UI and accessibility suite for the Clinical Human Clone journey (A&D R1, R2, R3, R8, R9, R10).

Runs the real FastAPI app in a background uvicorn thread and drives it with headless Chromium
(Python Playwright, plan G10). axe-core is the vendored, sha-pinned copy in ``vendor/`` (AD9).

The ``demo-ui`` CI job runs this module with ``DAYPART_UI_REQUIRED=1``, which turns a missing
Playwright or browser into a failure. Without it (the default ``test`` job, which does not install
the ``ui`` group) the module is skipped. ``DAYPART_UI_CHROMIUM`` points at a local browser binary
when ``playwright install`` cannot run.

T-ids: T1.2, T2.1, T3.3, T8.4, T9.4, T10.1–T10.4, plus the HAC-48 rev 2 states and the G27
direct-load focus check.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

REQUIRED = os.environ.get("DAYPART_UI_REQUIRED") == "1"

try:
    from playwright.sync_api import Browser, Page, Route, expect, sync_playwright
except ImportError:  # the `ui` dependency group is not installed
    if REQUIRED:
        raise
    pytest.skip("playwright not installed (uv sync --group ui)", allow_module_level=True)

import uvicorn

from daypart.checkin.crisis import HANDOFF_TEXT
from daypart.demo.app import create_app
from daypart.governance.real_input import load_checklist

VENDOR = Path(__file__).parent / "vendor"
AXE_SHA256 = "c24f097bd2f451d4f933e8bc7d8d539f8672a2ebcb5cc9f9f3eec8ca9470a0c1"
AXE_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
ROUTES = ["checkin", "review", "passport", "next", "lab"]
BANNER = "Demo mode: synthetic inputs and simulated results"
REAL_PHRASE = "Your real input, evaluation from vetted sources"
TEXT_CHECKIN = "slept 6 hours and walked 8000 steps"
CRISIS_TEXT = "slept 3 hours, I want to end my life"
TIMEOUT_MS = 20_000
MOBILE = {"width": 375, "height": 812}
DESKTOP = {"width": 1280, "height": 800}


# ---------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def axe_source() -> str:
    raw = (VENDOR / "axe.min.js").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == AXE_SHA256, "vendored axe.min.js changed; see vendor/README.md"
    return raw.decode("utf-8")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError("demo app did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="module")
def browser() -> Iterator[Browser]:
    exe = os.environ.get("DAYPART_UI_CHROMIUM") or None
    with sync_playwright() as pw:
        try:
            b = pw.chromium.launch(executable_path=exe)
        except Exception as e:  # browser binary missing
            if REQUIRED:
                raise
            pytest.skip(f"chromium unavailable: {e}")
        yield b
        b.close()


def _new_page(browser: Browser, errors: list[str], **ctx: Any) -> Page:
    context = browser.new_context(**ctx)
    context.set_default_timeout(TIMEOUT_MS)
    page = context.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    return page


@pytest.fixture
def page_errors() -> Iterator[list[str]]:
    errors: list[str] = []
    yield errors
    assert errors == [], f"uncaught page errors: {errors}"


@pytest.fixture
def page(browser: Browser, page_errors: list[str]) -> Iterator[Page]:
    p = _new_page(browser, page_errors, viewport=DESKTOP)
    yield p
    p.context.close()


# ---------------------------------------------------------------- helpers


def screen(page: Page, route: str):
    return page.locator(f"#screen-{route}")


def goto(page: Page, base_url: str, route: str) -> None:
    page.goto(f"{base_url}#{route}")
    expect(screen(page, route)).to_be_visible()


def axe_violations(page: Page, axe_source: str) -> list[dict[str, Any]]:
    """T10.1: serious or critical violations for the WCAG 2.0/2.1 A and AA tags."""
    if not page.evaluate("typeof window.axe !== 'undefined'"):
        page.add_script_tag(content=axe_source)
    found = page.evaluate(
        """async (tags) => (await axe.run(document, {runOnly: {type: 'tag', values: tags}}))
             .violations.map(v => ({id: v.id, impact: v.impact, nodes: v.nodes.map(n => n.target.join(' '))}))""",
        AXE_TAGS,
    )
    return [v for v in found if v["impact"] in ("serious", "critical")]


def assert_axe_clean(page: Page, axe_source: str, where: str) -> None:
    bad = axe_violations(page, axe_source)
    assert bad == [], f"{where}: {json.dumps(bad, indent=1)}"


def assert_no_hscroll(page: Page, where: str) -> None:
    """T10.3: nothing scrolls sideways."""
    sw, cw = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert sw <= cw, f"{where}: scrollWidth {sw} > clientWidth {cw}"


def assert_banner(page: Page, where: str) -> None:
    """T1.2: the visible text has the demo banner and never the real-input phrase."""
    text = page.inner_text("body")
    assert BANNER in text, where
    assert REAL_PHRASE not in text, where


def check_in_text(page: Page, base_url: str, text: str = TEXT_CHECKIN) -> None:
    goto(page, base_url, "checkin")
    page.fill("#ci-text", text)
    page.click("#ci-submit")


def wait_review(page: Page) -> None:
    page.wait_for_function("location.hash.startsWith('#review/')")
    expect(page.locator("#rv-list article").first).to_be_visible()


def confirm_all_and_save(page: Page) -> None:
    for radio in page.locator("#rv-list input[type=radio][value=confirm]").all():
        radio.check()
    page.click("#rv-submit")
    expect(page.locator("#rv-msg")).to_contain_text("to your clone")


def saved_journal(page: Page, base_url: str) -> None:
    """A realistic state: one text check-in, reviewed and saved."""
    check_in_text(page, base_url)
    wait_review(page)
    confirm_all_and_save(page)


def wait_route_ready(page: Page, route: str) -> None:
    ready = {
        "checkin": "#ci-files-btn",
        "review": "#screen-review h1",
        "passport": "#pp-cards article",
        "next": "#ns-panel button",
        "lab": "#lab-rows tr",
    }[route]
    expect(page.locator(ready).first).to_be_visible()


# ---------------------------------------------------------------- R1, R10: every route, realistic state


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["1280", "375"])
def test_every_route_banner_axe_and_reflow(browser: Browser, page_errors, base_url: str, axe_source: str, viewport):
    """T1.2, T10.1, T10.3 on the 5 routes, walked in journey order with real data."""
    page = _new_page(browser, page_errors, viewport=viewport)
    seen: list[str] = []

    def check(route: str) -> None:
        where = f"#{route} @ {viewport['width']}px"
        assert_banner(page, where)
        assert_axe_clean(page, axe_source, where)
        assert_no_hscroll(page, where)
        seen.append(route)

    goto(page, base_url, "checkin")
    wait_route_ready(page, "checkin")
    check("checkin")

    page.fill("#ci-text", TEXT_CHECKIN)
    page.click("#ci-submit")
    wait_review(page)
    check("review")  # pending review: the proposal cards and decision radios

    confirm_all_and_save(page)
    goto(page, base_url, "passport")
    wait_route_ready(page, "passport")
    page.locator("details.thread > summary").first.click()
    expect(page.locator("details.thread").first).to_have_attribute("open", "")
    check("passport")  # a ready card, the sourced range rows, an open thread, the inventory

    goto(page, base_url, "next")
    wait_route_ready(page, "next")
    check("next")

    goto(page, base_url, "lab")
    wait_route_ready(page, "lab")
    check("lab")

    assert seen == ROUTES
    page.context.close()


def test_direct_load_focuses_each_h1(browser: Browser, page_errors, base_url: str):
    """G27 (9): a direct load or reload of a route URL leaves focus on that screen's h1."""
    for route in ROUTES + ["research"]:
        page = _new_page(browser, page_errors, viewport=DESKTOP)
        for _ in range(2):  # the first load, then a reload of the same URL
            if _:
                page.reload()
            else:
                page.goto(f"{base_url}#{route}")
            expect(screen(page, route)).to_be_visible()
            focused = page.evaluate("document.activeElement && document.activeElement.id")
            assert focused == f"h-{route}", f"#{route}: focus on {focused!r}"
            assert page.evaluate("window.scrollY") == 0, f"#{route} scrolled on load"
        page.context.close()


# ---------------------------------------------------------------- R2, R3, R8, R9 static UI


def test_t2_1_checkin_heading_label_and_warning(page: Page, base_url: str):
    goto(page, base_url, "checkin")
    expect(page.locator("#screen-checkin h1")).to_have_text("What matters today?")
    box = page.get_by_label("Your check-in")
    expect(box).to_have_count(1)
    assert box.evaluate("e => e.tagName") == "TEXTAREA"
    expect(page.locator("#real-data-warning")).to_be_visible()
    expect(page.locator("#real-data-warning")).to_contain_text("Do not enter real health data")


def test_t3_3_voice_and_video_disabled(page: Page, base_url: str):
    goto(page, base_url, "checkin")
    for kind in ("Voice", "Video"):
        b = page.get_by_role("button", name=re.compile(rf"{kind}.*Not available"))
        expect(b).to_have_count(1)
        expect(b).to_be_visible()
        expect(b).to_be_disabled()


def test_t8_4_lab_says_simulated_not_patient_outcomes(page: Page, base_url: str):
    goto(page, base_url, "lab")
    wait_route_ready(page, "lab")
    assert "Simulated outcomes are not patient outcomes" in page.inner_text("#screen-lab")


def test_t9_4_real_input_refusal_lists_every_gate(page: Page, base_url: str, axe_source: str):
    goto(page, base_url, "checkin")
    page.click("#ri-btn")
    panel = page.locator("#ri-panel")
    expect(panel).to_contain_text("Real input is off and cannot be turned on in this build")
    expect(page.locator("#ri-btn")).to_have_attribute("aria-expanded", "true")
    gates = load_checklist()
    assert len(gates) == 12
    items = panel.locator("ol li")
    expect(items).to_have_count(len(gates))
    text = panel.inner_text()
    for g in gates:
        assert g.label in text, g.label
    assert_axe_clean(page, axe_source, "real-input refusal")
    page.click("#ri-btn")
    expect(page.locator("#ri-btn")).to_have_attribute("aria-expanded", "false")
    expect(panel.locator("ol")).to_have_count(0)


# ---------------------------------------------------------------- R10: keyboard-only journey


RING_JS = """e => { const s = getComputedStyle(e);
  return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow].join('|'); }"""


class Keyboard:
    """Moves focus with Tab / Shift+Tab only and records each focused element's ring.

    ``focused`` holds (description, focused ring) for every stop, so each one is checked against the
    spec ring. ``rings`` holds (description, focused ring, unfocused ring): the unfocused ring is read
    only once focus has really left the element, so a stop that a key is pressed on stays pending
    until the next Tab moves on (QG P3.2 K5). A stop removed from the page before focus left it is
    listed in ``dropped``. ``targets`` are the stops ``to()`` was asked to reach.
    """

    MAX_STOPS = 200

    def __init__(self, page: Page):
        self.page = page
        self.focused: list[tuple[str, str]] = []
        self.rings: list[tuple[str, str, str]] = []
        self.dropped: list[str] = []
        self.targets: list[str] = []
        self._pending: tuple[Any, str, str] | None = None

    def _settle_previous(self) -> None:
        if self._pending is None:
            return
        handle, desc, focused = self._pending
        state = handle.evaluate("e => !e.isConnected ? 'gone' : e === document.activeElement ? 'focused' : 'left'")
        if state == "focused":  # a key was pressed on it and focus stayed: read it after the next move
            return
        self._pending = None
        if state == "left":
            self.rings.append((desc, focused, handle.evaluate(RING_JS)))
        else:
            self.dropped.append(desc)
        handle.dispose()

    def press(self, key: str) -> None:
        self.page.keyboard.press(key)
        self._settle_previous()

    def _step(self, key: str) -> str:
        self.page.keyboard.press(key)
        self._settle_previous()
        if self._pending is not None:  # focus did not move (a single focusable element): keep the old one
            self._pending[0].dispose()
            self._pending = None
        handle = self.page.evaluate_handle("document.activeElement")
        desc = handle.evaluate(
            "e => e.tagName + (e.id ? '#' + e.id : '') + ' ' + (e.value && e.type === 'radio' ? e.value : (e.textContent || '').trim().slice(0, 40))"
        )
        ring = handle.evaluate(RING_JS)
        self.focused.append((desc, ring))
        self._pending = (handle, desc, ring)
        return desc

    def to(self, match: str, *, text: str = "", back: bool = False) -> None:
        """Tab (or Shift+Tab) until ``document.activeElement`` matches the CSS selector ``match``
        and, when given, contains ``text``."""
        key = "Shift+Tab" if back else "Tab"
        probe = "([s, t]) => { const e = document.activeElement; return !!e && e.matches(s) && (e.textContent || '').includes(t); }"
        for _ in range(self.MAX_STOPS):
            desc = self._step(key)
            if self.page.evaluate(probe, [match, text]):
                self.targets.append(desc)
                return
        raise AssertionError(f"{key} never reached {match}")


def test_t10_2_keyboard_only_journey(page: Page, base_url: str):
    """check-in (fixture) → review → passport → open a thread → choose → lab, with no mouse."""
    goto(page, base_url, "checkin")
    wait_route_ready(page, "checkin")
    kb = Keyboard(page)

    kb.to("#ci-images-btn")
    kb.press("Enter")
    expect(page.locator("#ci-images")).to_be_visible()
    kb.to("#ci-images button", text="bathroom scale")  # one unflagged proposal
    kb.press("Enter")
    wait_review(page)

    # review: Tab into the decision group, arrows move the choice, Space sets Confirm
    kb.to("#rv-list input[type=radio][value=confirm]")
    kb.press("ArrowDown")
    expect(page.locator("#rv-list input[value=correct]").first).to_be_checked()
    expect(page.locator("#rv-list .correct-fields").first).to_be_visible()
    kb.press("ArrowUp")
    confirm = page.locator("#rv-list input[value=confirm]").first
    expect(confirm).to_be_checked()
    expect(confirm).to_be_focused()
    kb.press("Space")
    expect(confirm).to_be_checked()
    kb.to("#rv-submit")
    kb.to("#rv-list input[type=radio]", back=True)  # Shift+Tab goes back to the decision group
    expect(confirm).to_be_focused()
    kb.to("#rv-submit")
    kb.press("Enter")
    expect(page.locator("#rv-msg")).to_contain_text("Saved 1 value to your clone")

    kb.to("#rv-msg a[href='#passport']")
    kb.press("Enter")
    wait_route_ready(page, "passport")
    kb.to("details.thread > summary")
    kb.press("Enter")
    expect(page.locator("details.thread[open]")).to_have_count(1)

    kb.to("#pp-body a[href='#next']")
    kb.press("Enter")
    wait_route_ready(page, "next")
    kb.to("#ns-panel button.btn--primary")
    expect(page.locator("#ns-panel button.btn--primary")).to_have_text("Choose")
    kb.press("Space")
    expect(page.locator("#ns-result")).to_contain_text("Goal set")

    kb.to("#ns-result a[href='#lab']")
    kb.press("Enter")
    wait_route_ready(page, "lab")
    expect(page.locator("#screen-lab")).to_contain_text("Simulated outcomes are not patient outcomes")
    kb.to("#lab-body .table-wrap")  # the scrollable table region is reachable too
    kb.to("a", back=True)
    kb.press("Shift+Tab")  # settle the last stop

    assert len(kb.rings) >= 15, kb.rings
    checked = {d for d, _, _ in kb.rings}
    unchecked = [t for t in kb.targets if t not in checked]
    assert unchecked == [], f"journey stops never compared focused vs unfocused: {unchecked}"
    same = [(d, f) for d, f, u in kb.rings if f == u]
    assert same == [], f"focused elements with no visible focus change: {same}"
    # the spec's ring (HAC-35 §5, stricter than T10.2's "differs"): a solid outline of at least 2 px
    thin = [(d, f) for d, f in kb.focused if not _strong_ring(f)]
    assert thin == [], f"focused elements without the spec focus ring: {thin}"


def _strong_ring(ring: str) -> bool:
    style, width, _color, _shadow = ring.split("|", 3)
    return style == "solid" and float(width.removesuffix("px") or 0) >= 2


# ---------------------------------------------------------------- R10: reduced motion


MOTION_JS = """() => {
  const bad = [], zero = v => v.split(',').every(x => parseFloat(x) === 0);
  for (const e of document.querySelectorAll('*')) {
    for (const pseudo of [null, '::before', '::after']) {
      const s = getComputedStyle(e, pseudo);
      if (!zero(s.animationDuration) || !zero(s.transitionDuration))
        bad.push(e.tagName + (e.id ? '#' + e.id : '') + (pseudo || '') + ' ' + s.animationDuration + ' ' + s.transitionDuration);
    }
  }
  return bad;
}"""


def test_t10_4_reduced_motion_zeroes_every_duration(browser: Browser, page_errors, base_url: str):
    page = _new_page(browser, page_errors, viewport=DESKTOP, reduced_motion="reduce")
    saved_journal(page, base_url)
    for route in ROUTES:
        goto(page, base_url, route)
        wait_route_ready(page, route)
        bad = page.evaluate(MOTION_JS)
        assert bad == [], f"#{route}: {bad[:10]}"
    page.context.close()

    # control: without the preference the stylesheet does animate, so the check above is not vacuous
    page = _new_page(browser, page_errors, viewport=DESKTOP, reduced_motion="no-preference")
    goto(page, base_url, "checkin")
    assert page.evaluate(MOTION_JS) != []
    page.context.close()


# ---------------------------------------------------------------- HAC-48 rev 2 states as behaviour


def test_crisis_handoff_replaces_review(page: Page, base_url: str, axe_source: str):
    check_in_text(page, base_url, CRISIS_TEXT)
    msg = page.locator("#ci-msg")
    expect(msg).to_contain_text(HANDOFF_TEXT)
    expect(page.locator("#ci-form")).to_be_hidden()
    assert page.evaluate("location.hash") == "#checkin"
    assert page.evaluate("document.activeElement.closest('#ci-msg') !== null")
    assert msg.locator("a").count() == 0, "the hand-off adds no link"
    assert msg.locator("button").all_inner_texts() == ["Write a different check-in"]
    assert_axe_clean(page, axe_source, "crisis hand-off")
    msg.locator("button").click()
    expect(page.locator("#ci-form")).to_be_visible()
    expect(page.locator("#ci-text")).to_be_focused()
    expect(page.locator("#ci-text")).to_have_value("")


def test_next_before_any_saved_checkin_says_check_in_first(page: Page, base_url: str, axe_source: str):
    goto(page, base_url, "next")
    msg = page.locator("#ns-msg")
    expect(msg).to_contain_text("Check in first")
    expect(page.locator("#ns-panel")).to_be_hidden()
    expect(msg.locator("a[href='#checkin']")).to_have_count(1)
    assert_axe_clean(page, axe_source, "#next 409")


def test_next_stale_step_refetches_and_never_resends(page: Page, base_url: str, axe_source: str):
    """HAC-48 rev 2 §3.4.2: a 422 unknown_step re-GETs the step once, shows the new suggestion and
    the "changed" note, and never re-sends the choice."""
    saved_journal(page, base_url)
    posts: list[str] = []
    gets = {"n": 0}

    def stale(route: Route) -> None:
        if route.request.method == "POST":
            posts.append(route.request.post_data or "")
            route.fulfill(status=422, content_type="application/json", body='{"error": "unknown_step"}')
            return
        gets["n"] += 1
        if gets["n"] == 1:
            route.continue_()
            return
        real = route.fetch().json()  # the refetch: a newer step than the one on screen
        real.update(step_id="newer-step", text="A newer suggestion after your latest check-in.")
        route.fulfill(status=200, content_type="application/json", body=json.dumps(real))

    page.route(re.compile(r".*/api/journals/[^/]+/next-step$"), stale)
    goto(page, base_url, "next")
    wait_route_ready(page, "next")
    old_text = page.locator("#ns-panel .suggestion").inner_text()
    page.locator("#ns-panel button.btn--primary").click()
    note = page.locator("#ns-msg")
    expect(note).to_contain_text("This suggestion has changed")
    expect(note.locator("[tabindex]").first).to_be_focused()
    expect(page.locator("#ns-panel .suggestion")).to_have_text("A newer suggestion after your latest check-in.")
    assert old_text != "A newer suggestion after your latest check-in."
    expect(page.locator("#ns-panel")).not_to_have_attribute("aria-busy", "true")
    page.wait_for_timeout(2_000)  # longer than any plausible automatic retry
    assert gets["n"] == 2, gets
    assert len(posts) == 1, posts
    assert_axe_clean(page, axe_source, "#next 422 unknown_step")


@pytest.mark.parametrize("failure", ["500", "network"])
def test_server_or_network_error_shows_notice_and_retries(page: Page, base_url: str, axe_source: str, failure: str):
    calls = {"n": 0}

    def broken(route: Route) -> None:
        calls["n"] += 1
        if calls["n"] > 1:
            route.continue_()
        elif failure == "500":
            route.fulfill(status=500, content_type="application/json", body='{"error": "internal"}')
        else:
            route.abort("failed")

    page.route(re.compile(r".*/api/lab$"), broken)
    goto(page, base_url, "lab")
    msg = page.locator("#lab-msg")
    expect(msg).to_contain_text("Something went wrong")
    expect(msg).to_contain_text("error 500" if failure == "500" else "could not reach the demo server")
    expect(page.locator("#lab-body")).to_be_hidden()
    assert_axe_clean(page, axe_source, f"lab {failure}")
    msg.get_by_role("button", name="Try again").click()
    wait_route_ready(page, "lab")
    expect(msg.locator(".notice")).to_have_count(0)
    assert calls["n"] == 2



# ---------------------------------------------------------------- AM-1 range row and review label (QG P3.2 K1)


def _journal_id(page: Page) -> str:
    return page.evaluate("JSON.parse(sessionStorage.getItem('chc.session.v1')).journal")


def test_passport_range_rows_and_review_label_match_the_api(page: Page, base_url: str):
    """HAC-48 rev 2 §3.3.1–2: each ready card's first meta row is its sourced range (shown and spoken
    text, population, source link) or "no reference range"; a withheld card has no range row; the
    passport meta carries the review label once."""
    saved_journal(page, base_url)
    goto(page, base_url, "passport")
    wait_route_ready(page, "passport")
    api = page.request.get(f"{base_url}api/journals/{_journal_id(page)}/passport").json()
    arts = page.locator("#pp-cards > article")
    expect(arts).to_have_count(len(api["cards"]))
    shown = none = 0
    for i, c in enumerate(api["cards"]):
        art = arts.nth(i)
        first_dt = art.locator("dl.meta > dt").first
        if c["status"] != "ready":
            expect(art.locator("dl.meta > dt", has_text="Reference range")).to_have_count(0)
            continue
        if c.get("reference_range_status") == "shown":
            r = c["reference_range"]
            lo, hi, unit = r["low"], r["high"], r["unit"]
            expect(first_dt).to_have_text("Reference range")
            dd = art.locator("dl.meta > dd").first
            expect(dd.locator("span[aria-hidden=true]")).to_have_text(f"{lo:g}–{hi:g} {unit}")
            expect(dd.locator(".visually-hidden")).to_have_text(f"{lo:g} to {hi:g} {unit}")
            expect(dd.locator(".ref-pop")).to_have_text(r["population"])
            src = dd.locator("a.ref-src")
            expect(src).to_have_attribute("href", r["source_url"])
            host = re.sub(r"^https://([^/]+).*$", r"\1", r["source_url"])
            expect(src).to_have_text(f"Range source: {host}")
            shown += 1
        elif c.get("reference_range_status") == "none":
            expect(first_dt).to_have_text("Reference range")
            expect(art.locator("dl.meta > dd").first).to_contain_text("no reference range")
            none += 1
    assert shown >= 1 and none >= 1, (shown, none)  # the saved sleep value is sourced, the steps value is not
    review = page.locator("#pp-meta dt", has_text="Review")
    expect(review).to_have_count(1)
    dd = page.locator("#pp-meta dt:has-text('Review') + dd")
    expect(dd).to_have_text("Reviewed (board sign-off, 7 Nov 2026)")


# ---------------------------------------------------------------- timeout and extractor fault (QG P3.2 K2)


def test_lab_request_times_out_at_15_s(page: Page, base_url: str):
    """HAC-48 rev 2 §3.8: a request with no answer within 15 s is aborted and shows the network notice."""
    held: list[Route] = []
    calls = {"n": 0}

    def hang(route: Route) -> None:
        calls["n"] += 1
        if calls["n"] > 1:
            route.continue_()
        else:
            held.append(route)  # never answered: only the page's own timer can end this request

    page.clock.install()
    page.route(re.compile(r".*/api/lab$"), hang)
    page.goto(f"{base_url}#lab")
    expect(screen(page, "lab")).to_be_visible()
    for _ in range(100):  # the route handler runs while Playwright waits
        if held:
            break
        page.wait_for_timeout(20)
    assert held, "the lab request was not sent"
    msg = page.locator("#lab-msg")
    page.clock.run_for(14_000)
    expect(msg.locator(".notice")).to_have_count(0)
    page.clock.run_for(1_500)
    expect(msg).to_contain_text("could not reach the demo server")
    msg.get_by_role("button", name="Try again").click()
    wait_route_ready(page, "lab")
    assert calls["n"] == 2
    for r in held:
        try:
            r.abort()
        except Exception:  # already ended by the page's abort
            pass


def test_extractor_fault_says_nothing_was_saved_and_keeps_the_form(page: Page, base_url: str):
    """HAC-48 rev 2 §3.8: 500 extractor_output_invalid has its own notice, not the generic one."""
    page.route(
        re.compile(r".*/api/checkins$"),
        lambda route: route.fulfill(status=500, content_type="application/json", body='{"error": "extractor_output_invalid"}'),
    )
    check_in_text(page, base_url)
    msg = page.locator("#ci-msg")
    expect(msg).to_contain_text("Something went wrong reading your check-in, so nothing was saved")
    expect(msg).to_contain_text("This is a fault in the demo, not in what you wrote")
    expect(msg.locator("[role=alert]")).to_have_count(1)
    expect(msg).not_to_contain_text("error 500")
    expect(page.locator("#ci-form")).to_be_visible()
    assert page.evaluate("location.hash") == "#checkin"


def test_lab_failure_after_a_good_load_hides_the_table(page: Page, base_url: str):
    """QG P3.2 K4: #lab-body starts hidden in the markup, so prove the failure path hides a shown table."""
    goto(page, base_url, "lab")
    wait_route_ready(page, "lab")
    expect(page.locator("#lab-body")).to_be_visible()
    page.route(
        re.compile(r".*/api/lab$"),
        lambda route: route.fulfill(status=503, content_type="application/json", body='{"error": "unavailable"}'),
    )
    goto(page, base_url, "checkin")
    goto(page, base_url, "lab")
    expect(page.locator("#lab-msg")).to_contain_text("error 503")
    expect(page.locator("#lab-body")).to_be_hidden()
