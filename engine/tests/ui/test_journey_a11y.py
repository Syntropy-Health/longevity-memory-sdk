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
# AM-2 D1 (G31): the member app is served at "/", the research console at "/admin".
# Visual spec rev 3 §2 (HAC-68): the member routes; #checkin stays an alias of #today.
ROUTES = ["today", "review", "passport", "next", "timeline"]
# Rev 3 §4 (G36): the console routes are hashes under /admin, #pipeline by default. HAC-76: the real-input
# screen is gone and the playground is #sessions; #research (the API's simulated-source evidence link) and
# #playground (older bookmarks) are its aliases.
ALIASES = {"checkin": "today", "research": "sessions", "playground": "sessions"}
ADMIN_ROUTES = ["pipeline", "lab", "inventory", "sessions"]
# AM-2 D2 (G32): the board removed the demo banner and these tags (HAC-66); T1.2 now checks they are absent.
REMOVED_TAGS = ("Demo mode", "synthetic inputs and simulated results", "Synthetic data only", "Not for clinical use",
                "Research view (optional)")
REAL_PHRASE = "Your real input, evaluation from vetted sources"
SAVED = re.compile(r"Your clone updated|to your clone")
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
    return page.locator(f"#screen-{ALIASES.get(route, route)}")


def url(base_url: str, route: str) -> str:
    """The route's URL on its surface: the research console's routes live under /admin."""
    admin = ALIASES.get(route.split("/")[0], route.split("/")[0]) in ADMIN_ROUTES
    return f"{base_url}admin#{route}" if admin else f"{base_url}#{route}"


def goto(page: Page, base_url: str, route: str) -> None:
    page.goto(url(base_url, route))
    expect(screen(page, route)).to_be_visible()


def fresh_journal(page: Page, base_url: str) -> None:
    """An empty journal ("Start a fresh journal") instead of the seeded persona's (AM-2 D2)."""
    goto(page, base_url, "checkin")
    wait_route_ready(page, "checkin")
    page.click("#fresh-btn")  # even while the first (persona) journal is still being created
    page.wait_for_function(
        "(() => { const v = JSON.parse(sessionStorage.getItem('chc.session.v1') || 'null');"
        " return !!v && typeof v.journal === 'string' && v.displayName === null; })()"
    )


def axe_violations(page: Page, axe_source: str) -> list[dict[str, Any]]:
    """T10.1: serious or critical violations for the WCAG 2.0/2.1 A and AA tags."""
    # rev 3's one-shot entrance motion (520 ms) fades rows in from opacity 0: measure the settled page
    page.wait_for_function("document.getAnimations().every(a => a.playState !== 'running')")
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


def assert_no_tags(page: Page, where: str) -> None:
    """T1.2 as amended by AM-2 D2: no demo banner or removed tag, and never the real-input phrase."""
    text = page.inner_text("body")
    for tag in REMOVED_TAGS:
        assert tag not in text, (where, tag)
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
    # rev 3 §3.3: "Your clone updated", or the rev 2 saved notice if the timeline GET failed
    expect(page.locator("#rv-msg")).to_contain_text(SAVED)


def saved_journal(page: Page, base_url: str) -> None:
    """A realistic state: one text check-in, reviewed and saved."""
    check_in_text(page, base_url)
    wait_review(page)
    confirm_all_and_save(page)


def wait_route_ready(page: Page, route: str) -> None:
    ready = {
        "checkin": "#ci-files-btn",
        "today": "#ci-files-btn",
        "review": "#screen-review h1",
        "passport": "#pp-cards article",
        "next": "#ns-panel button",
        "timeline": "#tl-days details",
        "pipeline": "#pipe-offline li",
        "lab": "#lab-rows tr",
        "inventory": "#ainv-rows tr",
        "sessions": "#r-start",
        "playground": "#r-start",
        "research": "#r-start",
    }[route]
    expect(page.locator(ready).first).to_be_visible()


def research_episode(page: Page) -> None:
    """On ``#sessions``: start a session and send one message, so the session form, the days-logged grid and
    the log are drawn (the content most likely to overflow at 375 px; QG P3 B3)."""
    expect(page.locator("#r-member option").first).to_be_attached()
    page.click("#r-start")
    expect(page.locator("#r-step")).to_be_enabled()
    page.click("#r-step")
    expect(page.locator("#r-log > *").first).to_be_attached()


# ---------------------------------------------------------------- R1, R10: every route, realistic state


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["1280", "375"])
def test_every_route_no_tags_axe_and_reflow(browser: Browser, page_errors, base_url: str, axe_source: str, viewport):
    """T1.2, T10.1, T10.3 on the 5 member routes (and the "Your clone updated" moment), walked in journey
    order on the seeded persona's journal with one more check-in, then every research-console route (AM-2 D1)."""
    page = _new_page(browser, page_errors, viewport=viewport)
    seen: list[str] = []

    def check(route: str) -> None:
        where = f"#{route} @ {viewport['width']}px"
        assert_no_tags(page, where)
        assert_axe_clean(page, axe_source, where)
        assert_no_hscroll(page, where)
        seen.append(route)

    goto(page, base_url, "today")
    wait_route_ready(page, "today")
    expect(page.locator("#clone-aside")).to_be_visible()  # the seeded landing with its "Your clone" aside
    check("today")

    page.fill("#ci-text", TEXT_CHECKIN)
    page.click("#ci-submit")
    wait_review(page)
    check("review")  # pending review: the proposal cards and decision radios

    confirm_all_and_save(page)
    expect(page.locator("#rv-msg .clone-updated")).to_be_visible()
    check("updated")  # rev 3 §3.3: the "Your clone updated" moment
    goto(page, base_url, "passport")
    wait_route_ready(page, "passport")
    page.locator("details.thread > summary").first.click()
    expect(page.locator("details.thread").first).to_have_attribute("open", "")
    check("passport")  # a ready card, the sourced range rows, an open thread, the inventory

    goto(page, base_url, "next")
    wait_route_ready(page, "next")
    check("next")

    goto(page, base_url, "timeline")
    wait_route_ready(page, "timeline")
    page.click("#tl-more")  # a second page of days, and a closed entry opened
    page.locator("#tl-days details:not([open]) > summary").first.click()
    check("timeline")

    goto(page, base_url, "pipeline")  # the console's default route (rev 3 §4.1)
    wait_route_ready(page, "pipeline")
    check("pipeline")

    goto(page, base_url, "lab")
    wait_route_ready(page, "lab")
    check("lab")

    goto(page, base_url, "inventory")
    wait_route_ready(page, "inventory")
    check("inventory")

    goto(page, base_url, "sessions")  # T10.3 says every route (QG P3 B3)
    research_episode(page)
    check("sessions")

    assert seen == ["today", "review", "updated", "passport", "next", "timeline"] + ADMIN_ROUTES
    page.context.close()


def test_direct_load_focuses_each_h1(browser: Browser, page_errors, base_url: str):
    """G27 (9): a direct load or reload of a route URL leaves focus on that screen's h1 (the #checkin
    alias lands on #today's)."""
    for route in ROUTES + ["checkin"] + ADMIN_ROUTES + ["research"]:
        page = _new_page(browser, page_errors, viewport=DESKTOP)
        for _ in range(2):  # the first load, then a reload of the same URL
            if _:
                page.reload()
            else:
                page.goto(url(base_url, route))
            expect(screen(page, route)).to_be_visible()
            focused = page.evaluate("document.activeElement && document.activeElement.id")
            assert focused == f"h-{ALIASES.get(route, route)}", f"#{route}: focus on {focused!r}"
            assert page.evaluate("window.scrollY") == 0, f"#{route} scrolled on load"
        page.context.close()


# ---------------------------------------------------------------- R2, R3, R8, R9 static UI


def test_t2_1_checkin_heading_label_and_warning(page: Page, base_url: str):
    goto(page, base_url, "checkin")
    # rev 3 §3.1: the seeded persona is greeted by first name; a fresh journal has the plain question
    expect(page.locator("#screen-today h1")).to_have_text(re.compile(r"^What matters today(, \S+)?\?$"))
    box = page.get_by_label("Your check-in")
    expect(box).to_have_count(1)
    assert box.evaluate("e => e.tagName") == "TEXTAREA"
    # rev 3 (AM-2 D2): the privacy notice is one neutral hint, still in aria-describedby
    expect(page.locator("#ci-pii")).to_be_visible()
    expect(page.locator("#ci-pii")).to_have_text("Leave out names, e-mail addresses, phone numbers and dates of birth.")
    assert "ci-pii" in (box.get_attribute("aria-describedby") or "").split()
    expect(page.locator("#real-data-warning")).to_have_count(0)


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


def test_hac76_console_offers_no_real_input_and_the_server_still_refuses(page: Page, base_url: str):
    """HAC-76 (board, HAC-74): the console no longer offers a real-input request or a mode toggle; the
    server still refuses real input (AD7) and an old #input link opens the overview."""
    page.goto(f"{base_url}admin#input")
    expect(screen(page, "pipeline")).to_be_visible()
    expect(page.locator("#ri-btn")).to_have_count(0)
    expect(page.get_by_text(re.compile("real input", re.I))).to_have_count(0)
    r = page.request.post(f"{base_url}api/mode", data={"real_input": True})
    assert r.status == 403 and r.json()["error"] == "real_input_refused"
    assert len(r.json()["open_gates"]) == len(load_checklist()) == 12


# ---------------------------------------------------------------- R10: keyboard-only journey


# A control drawn invisible (the decision radios: ``.opt input`` has opacity 0) shows its ring on the
# visible sibling it styles (``.opt input:focus-visible + span``), so the ring is read there (QG P3 K3).
RING_JS = """e => { const r = getComputedStyle(e).opacity === '0' && e.nextElementSibling ? e.nextElementSibling : e;
  const s = getComputedStyle(r);
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
    """check-in (fixture) → review → passport → open a thread → choose → back to the passport, with no
    mouse; then the learning lab on the research console (AM-2 D1: its own page)."""
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
    # rev 3 §3.3: "Your clone updated" takes focus; its first action is the passport
    expect(page.locator("#rv-msg .clone-updated")).to_be_focused()
    expect(page.locator("#rv-msg")).to_contain_text("Saved 1 value")

    kb.to("#rv-msg a[href='#passport']")
    kb.press("Enter")
    wait_route_ready(page, "passport")
    expect(page.locator("#h-passport")).to_be_focused()  # in-app navigation moves focus to the h1 (K7)
    kb.to("details.thread > summary")
    kb.press("Enter")
    expect(page.locator("details.thread[open]")).to_have_count(1)

    kb.to("#pp-body a[href='#next']")
    kb.press("Enter")
    wait_route_ready(page, "next")
    expect(page.locator("#h-next")).to_be_focused()
    kb.to("#ns-panel button.btn--primary")
    expect(page.locator("#ns-panel button.btn--primary")).to_have_text("Choose")
    kb.press("Space")
    expect(page.locator("#ns-result")).to_contain_text("Goal set")

    kb.to("#ns-result a[href='#timeline']")  # rev 3 §3.5 (was "Back to your passport")
    kb.press("Enter")
    wait_route_ready(page, "timeline")
    expect(page.locator("#h-timeline")).to_be_focused()
    kb.to("#tl-days details > summary")  # the newest entry, open
    newest = page.locator("#tl-days details").first
    expect(newest).to_have_attribute("open", "")
    kb.press("Enter")  # Enter toggles a timeline entry (rev 3 §5)
    expect(newest).not_to_have_attribute("open", "")
    kb.press("Space")
    expect(newest).to_have_attribute("open", "")
    kb.to("#tl-more")
    kb.press("Enter")
    expect(page.locator("#tl-days h2").nth(7)).to_be_focused()  # focus moves to the first day it added
    kb.press("Tab")  # focus leaves the last stop, so its ring is settled before the page changes

    goto(page, base_url, "lab")
    wait_route_ready(page, "lab")
    expect(page.locator("#h-lab")).to_be_focused()
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
    expect(page.locator("#rv-msg .clone-updated")).to_be_visible()
    bad = page.evaluate(MOTION_JS)
    assert bad == [], f"clone updated: {bad[:10]}"  # rev 3 §3.3: the ring pulse and row rise are removed too
    for route in ROUTES + ADMIN_ROUTES:  # every route on both surfaces (QG P3 B3, AM-2 D1)
        goto(page, base_url, route)
        if route == "sessions":
            research_episode(page)
        else:
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
    expect(msg).to_contain_text("Your clone cannot help with this.")  # rev 3 §3.1
    expect(page.locator("#ci-form")).to_be_hidden()
    expect(page.locator("#clone-aside")).to_be_hidden()  # it replaces both columns
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
    fresh_journal(page, base_url)  # the seeded persona already has saved check-ins
    goto(page, base_url, "next")
    msg = page.locator("#ns-msg")
    expect(msg).to_contain_text("Check in first")
    expect(page.locator("#ns-panel")).to_be_hidden()
    expect(msg.locator("a[href='#today']")).to_have_count(1)
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
    expect(msg).to_contain_text("error 500" if failure == "500" else "could not reach the server")
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
    page.goto(url(base_url, "lab"))
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
    expect(msg).to_contain_text("could not reach the server")
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
    expect(msg).to_contain_text("This is a fault on our side, not in what you wrote")
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
    goto(page, base_url, "inventory")
    goto(page, base_url, "lab")
    expect(page.locator("#lab-msg")).to_contain_text("error 503")
    expect(page.locator("#lab-body")).to_be_hidden()


def test_inventory_deep_link_focuses_the_inventory_heading(browser: Browser, page_errors, base_url: str):
    """G27 (9): a direct load of #passport/inventory focuses and scrolls to the inventory h2."""
    page = _new_page(browser, page_errors, viewport=MOBILE)
    page.goto(f"{base_url}#passport/inventory")
    wait_route_ready(page, "passport")
    expect(page.locator("#h-inventory")).to_be_focused()
    expect(page.locator("#h-inventory")).to_be_in_viewport()
    page.context.close()


# ---------------------------------------------------------------- next-step POST failures (QG P3.2 K6)


@pytest.mark.parametrize("failure", ["500", "network", "409"])
def test_next_choice_post_failure(page: Page, base_url: str, axe_source: str, failure: str):
    """HAC-48 rev 2 §3.4.1, §3.8: a failed choice keeps the panel, focuses the notice and Try again
    re-sends it; a 409 no_saved_checkin hides the panel and focuses "Check in first"."""
    saved_journal(page, base_url)
    posts = {"n": 0}

    def broken(route: Route) -> None:
        if route.request.method != "POST":
            route.continue_()
            return
        posts["n"] += 1
        if posts["n"] > 1:
            route.continue_()
        elif failure == "500":
            route.fulfill(status=500, content_type="application/json", body='{"error": "internal"}')
        elif failure == "409":
            route.fulfill(status=409, content_type="application/json", body='{"error": "no_saved_checkin"}')
        else:
            route.abort("failed")

    page.route(re.compile(r".*/api/journals/[^/]+/next-step$"), broken)
    goto(page, base_url, "next")
    wait_route_ready(page, "next")
    page.locator("#ns-panel button.btn--primary").click()
    msg = page.locator("#ns-msg")
    alert = msg.locator("[role=alert]")
    expect(alert).to_have_count(1)
    expect(alert).to_be_focused()
    if failure == "409":
        expect(alert).to_contain_text("Check in first")
        expect(page.locator("#ns-panel")).to_be_hidden()
        expect(msg.locator("a[href='#today']")).to_have_count(1)
        assert_axe_clean(page, axe_source, "#next POST 409")
        return
    expect(alert).to_contain_text("error 500" if failure == "500" else "could not reach the server")
    expect(page.locator("#ns-panel button.btn--primary")).to_be_visible()
    assert_axe_clean(page, axe_source, f"#next POST {failure}")
    msg.get_by_role("button", name="Try again").click()
    expect(page.locator("#ns-result")).to_contain_text("Goal set")
    assert posts["n"] == 2


# ---------------------------------------------------------------- A&D §4.1: a flagged value is never confirmed


FLAG_CASES = [("unit_assumed", "slept 6", "unit"), ("ambiguous_date", "slept 6 hours on monday", "date")]


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["1280", "375"])
@pytest.mark.parametrize("flag,text,field", FLAG_CASES, ids=[c[0] for c in FLAG_CASES])
def test_flagged_proposal_correct_states_the_shown_field(
    browser: Browser, page_errors, base_url: str, axe_source: str, flag: str, text: str, field: str, viewport
):
    """QG P3 K5 (and R1, G29): on a ``unit_assumed`` / ``ambiguous_date`` proposal Confirm is disabled;
    an unedited Correct sends the unit / date shown, the save succeeds, and the open Correct fields pass
    axe and reflow."""
    page = _new_page(browser, page_errors, viewport=viewport)
    posted: list[str] = []
    page.on("request", lambda r: posted.append(r.post_data or "") if r.method == "POST" and r.url.endswith("/review") else None)
    check_in_text(page, base_url, text)
    wait_review(page)
    art = page.locator("#rv-list article").first
    expect(art.locator("ul.tags")).to_contain_text(FLAG_LABELS[flag])
    expect(art.locator("input[type=radio][value=confirm]")).to_be_disabled()
    expect(art.locator(".notice")).to_contain_text("It cannot be confirmed")
    art.locator("input[type=radio][value=correct]").check()
    expect(art.locator(".correct-fields")).to_be_visible()
    shown = art.locator("[id$='-u']").input_value() if field == "unit" else art.locator("input[type=date]").input_value()
    where = f"#review Correct open ({flag}) @ {viewport['width']}px"
    assert_axe_clean(page, axe_source, where)
    assert_no_hscroll(page, where)
    page.click("#rv-submit")
    expect(page.locator("#rv-msg")).to_contain_text(SAVED)
    decision = json.loads(posted[-1])["decisions"][0]
    assert decision["action"] == "correct" and decision.get(field) == shown, (decision, shown)
    page.context.close()


FLAG_LABELS = {"unit_assumed": "Unit assumed", "ambiguous_date": "Ambiguous date"}


# ---------------------------------------------------------------- visual spec rev 3, member surface (HAC-38 P6.2)


def _api(page: Page, base_url: str, path: str) -> Any:
    return page.request.get(f"{base_url}api/journals/{_journal_id(page)}{path}").json()


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["1280", "375"])
def test_rev3_today_seeded_landing_matches_the_api(browser: Browser, page_errors, base_url: str, axe_source: str, viewport):
    """§2, §3.1: the persona chip, the greeting and every "Your clone" number come from the journal's own GETs."""
    page = _new_page(browser, page_errors, viewport=viewport)
    goto(page, base_url, "today")
    wait_route_ready(page, "today")
    aside = page.locator("#clone-aside")
    expect(aside).to_be_visible()
    persona = page.request.get(f"{base_url}api/personas").json()[0]
    first = persona["display_name"].split()[0]
    expect(page.locator("#h-today")).to_have_text(f"What matters today, {first}?")
    tl, pp = _api(page, base_url, "/timeline"), _api(page, base_url, "/passport")
    entries = tl["entries"]
    days = len({e["as_of"][:10] for e in entries})
    obs = sum(len(e["appends"]) for e in entries)
    ready = sum(1 for c in pp["cards"] if c["status"] == "ready")
    assert tl["omitted"] == 0
    expect(page.locator("#clone-stats li")).to_have_text(
        [f"{days} days of history", f"{len(entries)} saved check-ins", f"{obs} observations", f"{ready} cards ready"]
    )
    expect(page.locator("#persona")).to_have_text(f"{persona['display_name'][0]}{persona['display_name']} · {tl['member_id']}")
    expect(page.locator("nav[aria-label=Member] a[aria-current=page]")).to_have_text(re.compile("Today$"))
    assert page.evaluate("[...document.querySelectorAll('a[href]')].filter(a => /admin|dashboard/.test(a.getAttribute('href'))).length") == 0
    where = f"#today seeded @ {viewport['width']}px"
    assert_axe_clean(page, axe_source, where)
    assert_no_hscroll(page, where)
    page.context.close()


def test_rev3_fresh_journal_today_has_no_aside_and_an_empty_timeline(page: Page, base_url: str, axe_source: str):
    fresh_journal(page, base_url)
    goto(page, base_url, "today")
    wait_route_ready(page, "today")
    expect(page.locator("#h-today")).to_have_text("What matters today?")
    expect(page.locator("#clone-aside")).to_be_hidden()
    expect(page.locator("#ci-date")).to_be_visible()
    goto(page, base_url, "timeline")
    msg = page.locator("#tl-msg")
    expect(msg).to_contain_text("No updates yet")
    expect(msg).to_contain_text("Your first saved check-in starts the timeline.")
    expect(msg.locator("a[href='#today']")).to_have_text("Check in")
    expect(page.locator("#tl-body")).to_be_hidden()
    assert_axe_clean(page, axe_source, "#timeline empty")


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["1280", "375"])
def test_rev3_timeline_days_entries_and_paging(browser: Browser, page_errors, base_url: str, axe_source: str, viewport):
    """§3.6: newest first, grouped by day, the newest open and marked new, 7 days a page, and the C5 note."""
    page = _new_page(browser, page_errors, viewport=viewport)
    goto(page, base_url, "timeline")
    wait_route_ready(page, "timeline")
    tl = _api(page, base_url, "/timeline")
    days = sorted({e["as_of"][:10] for e in tl["entries"]}, reverse=True)
    expect(page.locator("#tl-note")).to_be_visible()
    expect(page.locator("#tl-days section.tl-day")).to_have_count(min(7, len(days)))
    expect(page.locator("#tl-days h2").first).to_contain_text("Today · ")
    newest = tl["entries"][-1]
    first = page.locator("#tl-days .tl > li").first
    expect(first).to_have_class("is-new")
    expect(first.locator("details")).to_have_attribute("open", "")
    expect(first.locator(".tl-title")).to_have_text(f"Check-in saved · {len(newest['appends'])} observations")
    chips = [f"↻ Updated: {c['title']}" for c in newest["passport_changes"] if c["change"] == "value_changed"]
    expect(first.locator(".tl-chips li")).to_have_text(chips)
    expect(page.locator("#tl-days details[open]")).to_have_count(1)
    page.click("#tl-more")
    expect(page.locator("#tl-days section.tl-day")).to_have_count(min(14, len(days)))
    expect(page.locator("#tl-days h2").nth(7)).to_be_focused()
    where = f"#timeline @ {viewport['width']}px"
    assert_axe_clean(page, axe_source, where)
    assert_no_hscroll(page, where)
    page.context.close()


@pytest.mark.parametrize("failure", ["502", "404"])
def test_rev3_timeline_get_failure_states(page: Page, base_url: str, axe_source: str, failure: str):
    goto(page, base_url, "today")
    wait_route_ready(page, "today")
    body = '{"error": "unknown_journal"}' if failure == "404" else '{"error": "bad_gateway"}'
    page.route(re.compile(r".*/api/journals/[^/]+/timeline$"),
               lambda route: route.fulfill(status=int(failure), content_type="application/json", body=body))
    goto(page, base_url, "timeline")
    if failure == "404":
        expect(page.locator("#session-msg")).to_contain_text("This session has ended")
    else:
        expect(page.locator("#tl-msg")).to_contain_text("We had a problem on our side (error 502)")
        expect(page.locator("#h-timeline")).to_be_focused()  # a failed GET leaves focus on the h1
    expect(page.locator("#tl-body")).to_be_hidden()
    assert_axe_clean(page, axe_source, f"#timeline {failure}")


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["1280", "375"])
def test_rev3_clone_updated_moment(browser: Browser, page_errors, base_url: str, axe_source: str, viewport):
    """§3.3: after a 200 save, the panel built from this check-in's timeline entry takes focus, animates once."""
    page = _new_page(browser, page_errors, viewport=viewport, reduced_motion="no-preference")
    saved_journal(page, base_url)
    panel = page.locator("#rv-msg .clone-updated")
    expect(panel).to_be_focused()
    expect(panel).to_have_attribute("role", "status")
    expect(panel).to_have_attribute("aria-labelledby", "cu-t")
    expect(page.locator("#cu-t")).to_have_text("Your clone updated")
    checkin = page.evaluate("location.hash").split("/", 1)[1]
    entry = next(e for e in _api(page, base_url, "/timeline")["entries"] if e["checkin_id"] == checkin)
    keys = (["Observed"] if entry["appends"] else []) + [
        {"became_ready": "Card ready", "value_changed": "Updated", "now_observed": "Now observed", "withheld": "Withheld"}[c["change"]]
        for kind in ("became_ready", "value_changed", "now_observed", "withheld") for c in entry["passport_changes"] if c["change"] == kind
    ] + (["Next step"] if entry["next_step"]["changed"] else [])
    expect(panel.locator("ul.delta > li > .k")).to_have_text(keys)
    assert not re.search(r"\b0 (cards?|observations?)\b", panel.inner_text())
    # one-shot motion: the rows rise once in 520 ms and nothing loops
    anim = panel.locator("ul.delta > li").first.evaluate("e => [getComputedStyle(e).animationDuration, getComputedStyle(e).animationIterationCount]")
    assert anim == ["0.52s", "1"], anim
    where = f"clone updated @ {viewport['width']}px"
    assert_axe_clean(page, axe_source, where)
    assert_no_hscroll(page, where)
    panel.get_by_role("link", name="View timeline").click()
    wait_route_ready(page, "timeline")
    expect(page.locator("#h-timeline")).to_be_focused()
    page.context.close()


def test_rev3_clone_updated_falls_back_when_the_timeline_get_fails(page: Page, base_url: str):
    """§3.3: the save already happened, so a failed timeline GET shows the rev 2 saved notice, not an error."""
    check_in_text(page, base_url)
    wait_review(page)
    page.route(re.compile(r".*/api/journals/[^/]+/timeline$"),
               lambda route: route.fulfill(status=503, content_type="application/json", body='{"error": "unavailable"}'))
    for radio in page.locator("#rv-list input[type=radio][value=confirm]").all():
        radio.check()
    page.click("#rv-submit")
    msg = page.locator("#rv-msg")
    expect(msg).to_contain_text(re.compile(r"Saved \d+ values? to your clone"))
    expect(msg.locator(".clone-updated")).to_have_count(0)
    expect(msg).not_to_contain_text("Something went wrong")
    expect(msg.locator(".notice")).to_be_focused()


def test_rev3_nav_route_changes_focus_each_h1_and_mark_the_page(page: Page, base_url: str):
    goto(page, base_url, "today")
    wait_route_ready(page, "today")
    for route in ["timeline", "passport", "next", "review", "today"]:
        page.locator(f"nav[aria-label=Member] a[href^='#{route}']").click()
        expect(screen(page, route)).to_be_visible()
        expect(page.locator(f"#h-{route}")).to_be_focused()
        expect(page.locator("nav[aria-label=Member] a[aria-current=page]")).to_have_count(1)
        expect(page.locator(f"nav[aria-label=Member] a[href^='#{route}']")).to_have_attribute("aria-current", "page")


def test_rev3_skip_link_is_first_and_keeps_the_route(page: Page, base_url: str):
    goto(page, base_url, "passport")
    wait_route_ready(page, "passport")
    first = page.evaluate("""() => [...document.querySelectorAll('a[href], button, input, select, textarea, summary, [tabindex="0"]')]
      .find(e => e.offsetParent !== null || getComputedStyle(e).position === 'absolute')""" + "?.className")
    assert first == "skip"  # the first stop in tab order
    page.focus("a.skip")
    expect(page.locator("a.skip")).to_be_in_viewport()  # it shows itself when focused
    page.keyboard.press("Enter")
    expect(page.locator("#main")).to_be_focused()
    assert page.evaluate("location.hash") == "#passport"
    expect(screen(page, "passport")).to_be_visible()


# ---------------------------------------------------------------- visual spec rev 3, research console (HAC-38 P6.2 part B)


CONSOLE_NAV = "nav[aria-label='Research console']"


def _console_prep(page: Page, route: str) -> None:
    """Draw each console screen's richest state before it is measured."""
    if route == "sessions":
        research_episode(page)
    else:
        wait_route_ready(page, route)


def _tab_through(page: Page) -> Keyboard:
    """Tab from the skip link through every stop of the page (sidebar, then content) until focus wraps
    back to the skip link or leaves the page."""
    page.focus("a.skip")
    kb = Keyboard(page)
    for _ in range(Keyboard.MAX_STOPS):
        desc = kb._step("Tab")
        if page.evaluate("document.activeElement === document.body || document.activeElement.classList.contains('skip')"):
            break
        assert desc
    else:
        raise AssertionError("Tab never wrapped")
    kb.press("Shift+Tab")  # settle the last stop
    # the wrap itself (focus on <body> past the last stop) is not a stop
    kb.focused = [f for f in kb.focused if not f[0].startswith("BODY")]
    kb.rings = [r for r in kb.rings if not r[0].startswith("BODY")]
    return kb


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["1280", "375"])
def test_rev3_console_routes_axe_reflow_focus_and_rings(browser: Browser, page_errors, base_url: str, axe_source: str, viewport):
    """§4, §5 on every console route: the nav moves focus to the h1 and marks its page; axe has no serious or
    critical violation; nothing scrolls sideways; every Tab stop shows the spec ring and differs from unfocused."""
    page = _new_page(browser, page_errors, viewport=viewport)
    page.goto(f"{base_url}admin")
    expect(screen(page, "pipeline")).to_be_visible()  # the default route
    expect(page.locator("#h-pipeline")).to_be_focused()
    for route in ADMIN_ROUTES:
        page.locator(f"{CONSOLE_NAV} a[href='#{route}']").click()
        expect(screen(page, route)).to_be_visible()
        expect(page.locator(f"#h-{route}")).to_be_focused()
        expect(page.locator(f"{CONSOLE_NAV} a[aria-current=page]")).to_have_count(1)
        expect(page.locator(f"{CONSOLE_NAV} a[href='#{route}']")).to_have_attribute("aria-current", "page")
        expect(screen(page, route).locator(".a-crumb")).to_have_count(0)  # HAC-76: no route path on screen
        expect(screen(page, route).locator(".a-top .a-lede")).to_be_visible()
        _console_prep(page, route)
        where = f"/admin#{route} @ {viewport['width']}px"
        assert_no_tags(page, where)
        assert_axe_clean(page, axe_source, where)
        assert_no_hscroll(page, where)
        kb = _tab_through(page)
        assert len(kb.rings) >= 8, (where, kb.rings)
        same = [(d, f) for d, f, u in kb.rings if f == u]
        assert same == [], f"{where}: focused elements with no visible focus change: {same}"
        thin = [(d, f) for d, f in kb.focused if not _strong_ring(f)]
        assert thin == [], f"{where}: focused elements without the spec focus ring: {thin}"
        small = page.evaluate("""() => [...document.querySelectorAll('.a-side a, .a-main .btn')]
          .filter(e => e.offsetParent !== null && e.getBoundingClientRect().height < 44).map(e => e.textContent.trim())""")
        assert small == [], f"{where}: tap targets under 44 px: {small}"
    page.context.close()


def test_rev3_console_reduced_motion_zeroes_every_duration(browser: Browser, page_errors, base_url: str):
    page = _new_page(browser, page_errors, viewport=MOBILE, reduced_motion="reduce")
    for route in ADMIN_ROUTES:
        goto(page, base_url, route)
        _console_prep(page, route)
        bad = page.evaluate(MOTION_JS)
        assert bad == [], f"/admin#{route} @ 375px: {bad[:10]}"
    page.context.close()


def test_rev3_console_skip_link_dashboard_and_member_link(page: Page, base_url: str):
    goto(page, base_url, "lab")
    wait_route_ready(page, "lab")
    first = page.evaluate("""() => [...document.querySelectorAll('a[href], button, input, select, textarea, summary, [tabindex="0"]')]
      .find(e => e.offsetParent !== null || getComputedStyle(e).position === 'absolute')""" + "?.className")
    assert first == "skip"
    page.focus("a.skip")
    expect(page.locator("a.skip")).to_be_in_viewport()
    page.keyboard.press("Enter")
    expect(page.locator("#main")).to_be_focused()
    assert page.evaluate("location.hash") == "#lab"
    dash = page.locator(f"{CONSOLE_NAV} a", has_text="Charts")
    expect(dash).to_have_attribute("href", "/results")
    expect(dash).to_have_attribute("target", "_blank")
    expect(dash).to_have_attribute("rel", "noopener")
    expect(dash).to_have_accessible_name(re.compile(r"Charts\s*\(opens in a new tab\)"))
    expect(page.get_by_role("link", name="← Member app")).to_have_attribute("href", "/")
    expect(page.locator(".a-brand .tag--console")).to_have_css("text-transform", "uppercase")


def _lab(page: Page, base_url: str) -> dict[str, Any]:
    return page.request.get(f"{base_url}api/lab").json()


def _pc(v: float) -> str:
    return f"{v * 100:.1f}%"


def test_rev3_pipeline_shows_the_real_lab_numbers(page: Page, base_url: str, axe_source: str):
    """§4.1 (HAC-76 plain-language pass): the headline tiles and training steps print /api/lab's own fields
    as percentages under plain labels; the check-in lane is 5 static steps."""
    goto(page, base_url, "pipeline")
    wait_route_ready(page, "pipeline")
    t = _lab(page, base_url)
    rows = {r["row"]: r for r in t["rows"]}
    base, sft, dpo = rows["base"], rows["sft"], rows["dpo"]
    kpis = page.locator("#pipe-kpis > li")
    expect(kpis).to_have_count(4)
    expect(kpis.nth(0).locator(".kpi-k")).to_have_text("Safety rule pass rate")
    expect(kpis.nth(0).locator(".kpi-v")).to_have_text(_pc(dpo["metrics"]["boundary_pass_rate"]))
    expect(kpis.nth(0).locator(".kpi-s")).to_have_text(f"Before training: {_pc(base['metrics']['boundary_pass_rate'])}")
    expect(kpis.nth(1).locator(".kpi-k")).to_have_text("Coaching quality pass rate")
    expect(kpis.nth(1).locator(".kpi-v")).to_have_text(_pc(dpo["metrics"]["rubric_pass_rate"]))
    expect(kpis.nth(2).locator(".kpi-v")).to_have_text("✓ Passed" if t["i1_passed"] else "⚠ Not passed")
    for i in range(4):
        expect(kpis.nth(i).locator(".kpi-d")).to_be_visible()
    live = page.get_by_role("list", name="Every check-in, 5 steps")
    expect(live.locator("> li")).to_have_count(5)
    expect(live.locator(".stage-desc")).to_have_count(5)
    expect(page.locator("#lane-live")).to_contain_text("No AI model is used in this loop.")
    off = page.get_by_role("list", name="Training, 4 steps")
    stages = off.locator("> li")
    expect(stages).to_have_count(4)
    expect(stages.nth(0)).to_contain_text(_pc(base["metrics"]["boundary_pass_rate"]))
    expect(stages.nth(1)).to_contain_text(f"(+{sft['gate']['delta'] * 100:.1f} points)")
    expect(stages.nth(1)).to_contain_text("✓ Passed its check")
    grpo = rows["grpo"]  # HAC-79: the ran grpo arm is a "policy" row, scored with simulated members
    assert grpo["kind"] == "policy"
    expect(stages.nth(3)).to_contain_text(f"Adherence{_pc(grpo['metrics']['mean_adherence'])}")
    expect(stages.nth(3)).to_contain_text(f"Safety-rule breaches{_pc(grpo['metrics']['episode_violation_rate'])}")
    expect(stages.nth(3).locator(".stage-desc")).to_have_text(
        "Learned which kind of message to send each day from how simulated members responded.")
    for word in ("Planned", "proposed", "not recorded", "GRPO", "episode"):
        expect(stages.nth(3)).not_to_contain_text(word)
    expect(page.locator("#screen-pipeline")).to_contain_text("Simulated outcomes are not patient outcomes.")
    # a step links its results row, which the deep link marks (and opens the run records)
    stages.nth(1).locator("a").click()
    expect(screen(page, "lab")).to_be_visible()
    expect(page.locator(f"#lab-rows tr[data-run-id='{sft['run_id']}']")).to_have_attribute("aria-current", "true")
    expect(page.locator("#lab-rows tr[aria-current=true]")).to_have_count(1)
    expect(page.locator("#lab-records")).to_have_attribute("open", "")
    # HAC-79 + HAC-76: the ran grpo policy is listed first with the coaching approaches, in plain words
    gr = page.locator(f"#env-rows tr[data-run-id='{grpo['run_id']}']")
    expect(page.locator("#env-rows tr").first).to_have_attribute("data-run-id", grpo["run_id"])
    expect(gr.locator("td[data-label='Coaching approach'] strong")).to_have_text("Step 3 · Practice with simulated members")
    expect(gr.locator("td[data-label='Average adherence']")).to_have_text(_pc(grpo["metrics"]["mean_adherence"]))
    expect(gr.locator("td[data-label='Sessions with a safety-rule breach']")).to_have_text(
        _pc(grpo["metrics"]["episode_violation_rate"]))
    expect(page.locator(f"#lab-rows tr[data-run-id='{grpo['run_id']}']")).to_have_count(0)  # not a prompt-scored step
    assert_axe_clean(page, axe_source, "lab deep link")


_G5_SPLIT_WORDS = """([sel, cellSel]) => Array.from(document.querySelectorAll(sel)).map(t => {
  const out = []; let cells = 0;
  t.querySelectorAll(cellSel).forEach(c => {
    cells++;
    const w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      if (n.parentElement.closest('.run-id')) continue;
      const re = /\\S+/g; let m;
      while ((m = re.exec(n.data))) {
        const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
        if (r.getClientRects().length > 1) out.push(m[0]);
      }
    }
  });
  return { cells: cells, split: out }; })"""


@pytest.mark.parametrize("width", [1280, 1920])
@pytest.mark.parametrize(("route", "tables"), [("lab", 3), ("inventory", 1)])
def test_hac76_g5_results_tables_never_break_a_word(browser: Browser, page_errors, base_url: str, width: int,
                                                    route: str, tables: int):
    """G5 (HAC-74): at 1280 the lab table broke words mid-word. Every table cell's words now fit on their
    line: no word in a header or cell is split across lines (run ids and digests excepted). Each screen is
    checked on its own route (a hidden screen has no line boxes) and every table must have cells."""
    page = _new_page(browser, page_errors, viewport={"width": width, "height": 1000})
    goto(page, base_url, route)
    wait_route_ready(page, route)
    if route == "lab":
        page.locator("#lab-records > summary").click()
    got = page.evaluate(_G5_SPLIT_WORDS, [f"#screen-{route} table", "th, td"])
    assert len(got) == tables, f"#{route}: {len(got)} tables"
    for i, t in enumerate(got):
        assert t["cells"] > 0, f"#{route} table {i}: no cells checked"
        assert t["split"] == [], f"#{route} table {i} @{width}px: words broken across lines: {t['split']}"
    assert_no_hscroll(page, f"{route} @ {width}px")
    page.context.close()


@pytest.mark.parametrize("width", [375, 390, 1280, 1920])
def test_hac76_headline_tiles_never_break_a_word(browser: Browser, page_errors, base_url: str, width: int):
    """G5 on the overview: a headline tile's number and label never split mid-word ("100.0 / %",
    "Passe / d" at 375 before the 1-up phone layout)."""
    page = _new_page(browser, page_errors, viewport={"width": width, "height": 900})
    goto(page, base_url, "pipeline")
    wait_route_ready(page, "pipeline")
    expect(page.locator("#pipe-kpis > li")).to_have_count(4)
    (tiles,) = page.evaluate(_G5_SPLIT_WORDS, ["#pipe-kpis", ":scope > li"])
    assert tiles["cells"] == 4
    assert tiles["split"] == [], f"@{width}px: words broken across lines: {tiles['split']}"
    # the training steps (narrow cards in the horizontal lane at 1280): "150 sessio / ns" before HAC-82's merge fix
    (steps,) = page.evaluate(_G5_SPLIT_WORDS, ["#pipe-offline", ":scope > li .stage"])
    assert steps["cells"] == 4
    assert steps["split"] == [], f"training steps @{width}px: words broken across lines: {steps['split']}"
    assert_no_hscroll(page, f"pipeline @ {width}px")
    page.context.close()


def test_rev3_pipeline_mocked_lab_mismatch_and_nulls(page: Page, base_url: str):
    real = json.loads(json.dumps(_lab(page, base_url)))
    for r in real["rows"]:
        if r["row"] == "dpo":
            r.update(status="provenance mismatch", metrics={"boundary_pass_rate": None, "rubric_pass_rate": None}, gate=None)
        if r["row"] == "base":
            r["metrics"]["boundary_pass_rate"] = 0.4567
    page.route(re.compile(r".*/api/lab$"), lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(real)))
    goto(page, base_url, "pipeline")
    wait_route_ready(page, "pipeline")
    k1 = page.locator("#pipe-kpis > li").nth(0)
    expect(k1.locator(".kpi-v")).to_have_text("⚠ provenance mismatch")
    expect(k1.locator(".kpi-s")).to_contain_text("Before training: 45.7%")  # the mocked number, read per request
    dpo = page.locator("#pipe-offline > li").nth(2)
    expect(dpo).to_contain_text("⚠ provenance mismatch")
    assert not re.search(r"\d%", dpo.inner_text()), dpo.inner_text()


@pytest.mark.parametrize("viewport", [DESKTOP, MOBILE], ids=["1280", "375"])
def test_rev3_pipeline_failed_lab_keeps_the_live_lane(browser: Browser, page_errors, base_url: str, axe_source: str, viewport):
    page = _new_page(browser, page_errors, viewport=viewport)
    calls = {"n": 0}

    def broken(route: Route) -> None:
        calls["n"] += 1
        if calls["n"] > 1:
            route.continue_()
        else:
            route.fulfill(status=500, content_type="application/json", body='{"error": "internal"}')

    page.route(re.compile(r".*/api/lab$"), broken)
    goto(page, base_url, "pipeline")
    msg = page.locator("#pipe-msg")
    expect(msg).to_contain_text("We had a problem on our side (error 500)")
    expect(page.locator("#h-pipeline")).to_be_focused()  # a failed GET leaves focus on the h1
    expect(page.locator("#lane-live")).to_be_visible()
    expect(page.get_by_role("list", name="Every check-in, 5 steps").locator("> li")).to_have_count(5)
    expect(page.locator("#lane-offline")).to_be_hidden()
    expect(page.locator("#pipe-kpis")).to_be_hidden()
    where = f"pipeline 500 @ {viewport['width']}px"
    assert_axe_clean(page, axe_source, where)
    assert_no_hscroll(page, where)
    msg.get_by_role("button", name="Try again").click()
    wait_route_ready(page, "pipeline")
    expect(page.locator("#pipe-kpis")).to_be_visible()
    expect(msg.locator(".notice")).to_have_count(0)
    assert calls["n"] == 2
    page.context.close()


def test_rev3_pipeline_layout_vertical_below_72rem_horizontal_from_72rem(browser: Browser, page_errors, base_url: str):
    for width, horizontal in ((1280, True), (1100, False), (375, False)):
        page = _new_page(browser, page_errors, viewport={"width": width, "height": 900})
        goto(page, base_url, "pipeline")
        wait_route_ready(page, "pipeline")
        tops = page.locator("#pipe-live > li").evaluate_all("els => els.map(e => Math.round(e.getBoundingClientRect().top))")
        assert (len(set(tops)) == 1) is horizontal, (width, tops)
        page.context.close()


def test_rev3_console_old_links_and_path_routes_resolve(page: Page, base_url: str):
    """G36: /admin#research and /admin#lab/<run> keep working; /admin/<route>[#<run>] is rewritten to the hash form."""
    for old in ("research", "playground"):
        page.goto(f"{base_url}admin#{old}")
        expect(screen(page, "sessions")).to_be_visible()
        expect(page.locator(f"{CONSOLE_NAV} a[href='#sessions']")).to_have_attribute("aria-current", "page")
    run = next(r["run_id"] for r in _lab(page, base_url)["rows"] if r["row"] == "dpo")
    page.goto(f"{base_url}admin#lab/{run}")
    expect(page.locator(f"#lab-rows tr[data-run-id='{run}']")).to_have_attribute("aria-current", "true")
    page.goto(f"{base_url}admin/lab#{run}")
    expect(page.locator(f"#lab-rows tr[data-run-id='{run}']")).to_have_attribute("aria-current", "true")
    assert page.evaluate("location.pathname + location.hash") == f"/admin#lab/{run}"
    page.goto(f"{base_url}admin/playground")
    expect(page.locator("#h-sessions")).to_be_focused()
    assert page.evaluate("location.pathname + location.hash") == "/admin#playground"
    assert page.request.get(f"{base_url}admin/input").status == 404  # HAC-76: the real-input screen is gone
    page.goto(f"{base_url}admin#nope")
    expect(screen(page, "pipeline")).to_be_visible()  # an unknown route opens the default
