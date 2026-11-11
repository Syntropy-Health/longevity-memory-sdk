"""HAC-38 P3 task 11: the rebuilt journey UI (``demo/static/index.html``) and the renamed API.

Static checks on the served HTML (T1.1, T2.1, T3.3, T8.4, T9.4, the palette, the banner and the
escaping rules) plus T1.3 (no real-input phrase in any new JSON response) and T1.5 (the OpenAPI
title). The browser checks (axe, keyboard, 375 px, reduced motion) live in the ``demo-ui`` job.
"""

from __future__ import annotations

import re
from pathlib import Path
from html.parser import HTMLParser

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from daypart.demo.app import create_app  # noqa: E402

REAL_INPUT_PHRASE = "Your real input, evaluation from vetted sources"
# Visual spec rev 3 §1 (HAC-68): the member and console palettes plus the shared provenance / warning hues.
ALLOWED_HEX = {"070B14", "0F1729", "16213A", "EAF0FA", "A9B8D0", "5E7397", "24324F", "9AA8FF",  # member
               "09090B", "111114", "18181C", "EDEDF0", "A6A6B0", "71717E", "26262C", "F08CF5",  # console
               "4FD8C4", "F6B95C",  # observed (provenance), warn (system warning)
               "000"}  # not a colour: the opaque mask layer of the .panel--glow gradient border
# the decorative alpha variants: glows, the console grid, the panel highlight and the shadows
ALLOWED_ALPHA_HEX = {"9AA8FF2E", "4FD8C41F", "F08CF526", "FFFFFF0A", "FFFFFF0D", "00000099", "000000CC"}
# AM-2 D1 (G31): the member app at "/" and the research console at "/admin" are separate shells.
# Rev 3 §2: the member screens are Today (was #checkin, kept as its alias), Review, Passport, Next, Timeline.
MEMBER_SCREENS = ("today", "review", "passport", "next", "timeline")
# Rev 3 §4 (G36): the console screens, hash routes under /admin. HAC-76: the real-input screen is gone and
# the playground is #sessions (#playground and #research are its aliases).
ADMIN_SCREENS = ("pipeline", "lab", "inventory", "sessions")
SCREENS = MEMBER_SCREENS
# AM-2 D2 (G32): the board removed these tags from both surfaces (HAC-66, 2026-11-10).
REMOVED_TAGS = ("Demo mode", "synthetic inputs and simulated results", "Synthetic data only", "Not for clinical use",
                "Research view (optional)")


@pytest.fixture(scope="module")
def client():
    with pytest.MonkeyPatch.context() as mp:
        mp.delenv("DAYPART_REAL_INPUT", raising=False)
        with TestClient(create_app(cohort_seed=0)) as c:
            yield c


@pytest.fixture(scope="module")
def html(client) -> str:
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    return r.text


@pytest.fixture(scope="module")
def admin(client) -> str:
    r = client.get("/admin")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    return r.text


# --- a tiny DOM walker (stdlib only) ------------------------------------------------------------


class _Node:
    def __init__(self, tag: str, attrs: dict[str, str | None], parent: _Node | None) -> None:
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children: list[_Node | str] = []

    def text(self) -> str:
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def iter(self):
        yield self
        for c in self.children:
            if isinstance(c, _Node):
                yield from c.iter()


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Tree(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root", {}, None)
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, dict(attrs), self.cur)
        self.cur.children.append(node)
        if tag not in _VOID:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.children.append(_Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.children.append(data)


def _tree(html: str) -> _Node:
    p = _Tree()
    p.feed(html)
    p.close()
    return p.root


def _by_id(root: _Node, ident: str) -> _Node:
    found = [n for n in root.iter() if n.attrs.get("id") == ident]
    assert len(found) == 1, f"expected one #{ident}, found {len(found)}"
    return found[0]


def _without_research(html: str) -> str:  # the admin console minus its simulated-sessions section
    """The page source with the ``<section id="screen-sessions">`` element (and everything in it) cut out
    (rev 3 §4.4 renamed #research → #playground; HAC-76 renamed it #sessions)."""
    m = re.search(r'<section\b[^>]*\bid="screen-sessions"[^>]*>', html)
    assert m, "no <section id=\"screen-sessions\">"
    depth, i = 1, m.end()
    tag = re.compile(r"<(/?)section\b[^>]*>")
    while depth:
        t = tag.search(html, i)
        assert t, "unclosed research section"
        depth += -1 if t.group(1) else 1
        i = t.end()
    return html[: m.start()] + html[i:]


def _visible(page: str) -> str:
    """The words a reader sees: the page minus its <script> and <style> blocks and comments."""
    page = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S)
    page = re.sub(r"<!--.*?-->", " ", page, flags=re.S)
    return " ".join(_tree(page).text().split())


# --- T1.1 ---------------------------------------------------------------------------------------


def test_t1_1_names_and_no_research_words_outside_research(html, admin):
    assert "Clinical Human Clone" in html
    assert "Health Clone Passport" in html
    assert "pattern passport" not in (html + admin).lower()  # nowhere, the research console included
    # AM-2 D1: the member app carries no research markup at all (was: research section cut out)
    for gone in ('id="screen-research"', 'id="screen-playground"', 'id="screen-sessions"'):
        assert gone not in html, gone
    assert "Daypart playground" not in html
    assert not re.search(r"\bIntent\b", html)
    assert not re.search(r"\bDraft\b", html)
    # HAC-76: the sessions screen is in plain words: no playground, episode, intent, draft or membrane
    sessions = _visible(_section(admin, '<section id="screen-sessions"', "<script>"))
    assert "Simulated coaching sessions" in sessions and "Coaching approach" in sessions
    for word in ("playground", "Episode", "Intent", "Draft", "membrane", "Horizon"):
        assert not re.search(rf"\b{word}\b", sessions, re.I), word
    assert "Daypart playground" not in admin


def test_am2_d1_member_app_has_no_admin_screens_and_admin_has_no_journey(html, admin):
    member_ids = {n.attrs.get("id") for n in _tree(html).iter()}
    admin_ids = {n.attrs.get("id") for n in _tree(admin).iter()}
    for s in ADMIN_SCREENS:
        assert "screen-" + s not in member_ids and "screen-" + s in admin_ids
    for s in MEMBER_SCREENS:
        assert "screen-" + s in member_ids and "screen-" + s not in admin_ids
    # HAC-76: the real-input screen and its request control are gone from both surfaces
    for gone in ("screen-input", "ri-btn", "ri-panel"):
        assert gone not in member_ids and gone not in admin_ids, gone


def test_am2_d1_member_never_links_the_research_console(html):
    hrefs = [n.attrs.get("href") or "" for n in _tree(html).iter() if n.tag == "a"]
    assert not [h for h in hrefs if h.startswith("/admin") or re.match(r"#(lab|research|inventory|pipeline|playground|input)\b", h)]
    assert "/results" not in hrefs and "/docs" not in hrefs
    js = _script(html)
    assert '"#lab"' not in js and "Continue to the learning lab" not in js


def test_am2_d1_admin_console_links_back_to_the_member_app(admin):
    # HAC-76: the console nav is Overview · Results · Health areas · Simulated sessions · Charts ↗ (the
    # real-input item is gone); "← Member app" sits under it.
    root = _tree(admin)
    nav = next(n for n in root.iter() if n.tag == "nav" and n.attrs.get("aria-label") == "Research console")
    links = [n for n in nav.iter() if n.tag == "a"]
    assert [n.attrs.get("href") for n in links] == ["#pipeline", "#lab", "#inventory", "#sessions", "/results"]
    assert [" ".join(a.text().split())[1:].strip() for a in links] == [
        "Overview", "Results", "Health areas", "Simulated sessions", "Charts (opens in a new tab)"]
    dash = links[-1]
    assert dash.attrs.get("target") == "_blank" and dash.attrs.get("rel") == "noopener"
    hidden = [n for n in dash.iter() if "visually-hidden" in (n.attrs.get("class") or "")]
    assert len(hidden) == 1 and hidden[0].text().strip() == "(opens in a new tab)"
    back = [n for n in root.iter() if n.tag == "a" and n.attrs.get("href") == "/"]
    assert len(back) == 1 and " ".join(back[0].text().split()) == "← Member app" and not _is_inside(back[0], nav)
    hrefs = {n.attrs.get("href") for n in root.iter() if n.tag == "a"}
    assert "/" in hrefs and "/results" in hrefs
    # no hostname anywhere in the console's links: the dashboard is the app's own relative /results
    assert not [h for h in hrefs if h and re.match(r"(https?:)?//", h) and "loinc.org" not in h], hrefs


def test_am2_d1_one_h1_per_admin_screen(admin):
    root = _tree(admin)
    for s in ADMIN_SCREENS:
        sec = _by_id(root, "screen-" + s)
        h1s = [n for n in sec.iter() if n.tag == "h1"]
        assert len(h1s) == 1 and h1s[0].attrs.get("tabindex") == "-1", s


def test_am2_d2_removed_tags_on_neither_surface(html, admin):
    for page in (html, admin):
        text = " ".join(_tree(page).text().split())
        for tag in REMOVED_TAGS:
            assert tag not in text and tag not in page, tag
    assert 'class="banner"' not in html and 'class="banner"' not in admin


# --- structure: routes, h1s, nav, banner ----------------------------------------------------------


def test_one_main_one_h1_per_screen(html):
    root = _tree(html)
    mains = [n for n in root.iter() if n.tag == "main"]
    assert len(mains) == 1
    for s in SCREENS:
        sec = _by_id(root, "screen-" + s)
        assert sec.tag == "section" and _is_inside(sec, mains[0])
        h1s = [n for n in sec.iter() if n.tag == "h1"]
        assert len(h1s) == 1 and h1s[0].attrs.get("tabindex") == "-1", s
    assert len([n for n in root.iter() if n.tag == "h1"]) == len(SCREENS)


def _is_inside(node: _Node, ancestor: _Node) -> bool:
    n = node.parent
    while n is not None:
        if n is ancestor:
            return True
        n = n.parent
    return False


def test_header_is_first_in_body_outside_main(html):
    # AM-2 D2 (G32): the demo-mode banner is gone. Rev 3 §5: a skip link comes first, then the member header.
    root = _tree(html)
    body = next(n for n in root.iter() if n.tag == "body")
    first, second = [c for c in body.children if isinstance(c, _Node)][:2]
    assert first.tag == "a" and first.attrs.get("class") == "skip" and first.attrs.get("href") == "#main"
    assert second.tag == "header" and "m-head" in (second.attrs.get("class") or "").split()
    main = next(n for n in root.iter() if n.tag == "main")
    assert main.attrs.get("id") == "main" and main.attrs.get("tabindex") == "-1"
    assert not _is_inside(second, main)


def test_member_nav_has_five_items(html):
    # Rev 3 §2 (AM-2 D1): Today · Review · Passport · Next · Timeline (was a 4-link "Journey" step nav).
    root = _tree(html)
    nav = next(n for n in root.iter() if n.tag == "nav" and n.attrs.get("aria-label") == "Member")
    links = [n for n in nav.iter() if n.tag == "a"]
    assert [a.attrs.get("href") for a in links] == ["#today", "#review", "#passport", "#next", "#timeline"]
    assert [" ".join(a.text().split())[1:].strip() for a in links] == ["Today", "Review", "Passport", "Next", "Timeline"]
    assert not any(n.attrs.get("aria-label") == "Journey" for n in root.iter() if n.tag == "nav")


@pytest.mark.parametrize("surface", ["html", "admin"])
def test_footer_loinc_notice_and_no_disclaimer(surface, request):
    # AM-2 D2: the "Synthetic data only. Not for clinical use." line and the research link are gone;
    # the LOINC notice stays on both surfaces (T5.6).
    root = _tree(request.getfixturevalue(surface))
    foot = next(n for n in root.iter() if n.tag == "footer")
    text = " ".join(foot.text().split())
    assert "Synthetic data only" not in text and "Not for clinical use" not in text
    assert not any(n.tag == "a" and n.attrs.get("href") == "#research" for n in foot.iter())
    assert "LOINC" in text and "Regenstrief Institute" in text
    assert any(n.tag == "a" and n.attrs.get("href") == "https://loinc.org/license/" for n in foot.iter())


# --- T2.1, T3.3, T8.4, T9.4 (static parts) -----------------------------------------------------------


def test_t2_1_checkin_heading_labelled_textarea_and_warning(html):
    root = _tree(html)
    sec = _by_id(root, "screen-today")
    h1 = next(n for n in sec.iter() if n.tag == "h1")
    assert h1.text().strip() == "What matters today?"  # the fresh-journal text; a persona's adds the first name
    areas = [n for n in sec.iter() if n.tag == "textarea"]
    assert len(areas) == 1 and areas[0].attrs.get("maxlength") == "500"
    tid = areas[0].attrs.get("id")
    assert tid and any(n.tag == "label" and n.attrs.get("for") == tid for n in sec.iter())
    # Rev 3 §3.1 (AM-2 D2): the privacy notice became one neutral hint, still in aria-describedby; the PII
    # refusal is unchanged (was: the "Keep personal details out" notice, #real-data-warning).
    hint = _by_id(root, "ci-pii")
    assert " ".join(hint.text().split()) == "Leave out names, e-mail addresses, phone numbers and dates of birth."
    assert "ci-pii" in (areas[0].attrs.get("aria-describedby") or "").split()
    assert "real-data-warning" not in html and "Keep personal details out" not in html
    assert "Do not enter real health data" not in html and "public demo" not in sec.text()


def test_t3_3_voice_and_video_disabled_not_available(html):
    sec = _by_id(_tree(html), "screen-today")
    buttons = [n for n in sec.iter() if n.tag == "button" and "disabled" in n.attrs]
    for word in ("Voice", "Video"):
        hits = [b for b in buttons if word in b.text()]
        assert len(hits) == 1, word
        assert "Not available" in hits[0].text()


def test_t8_4_lab_footnote(admin):
    sec = _by_id(_tree(admin), "screen-lab")
    assert "Simulated outcomes are not patient outcomes." in sec.text()


def test_hac76_no_real_input_or_mode_toggle_on_either_surface(html, admin):
    """HAC-76 (board, HAC-74): a production prototype advertises no real-input request or mode toggle.
    The server still refuses real input (AD7); the page just stops offering it."""
    for page in (html, admin):
        root = _tree(page)
        assert not [n for n in root.iter() if n.tag == "button" and "real input" in n.text().lower()]
        text = _visible(page).lower()
        for phrase in ("real input", "demonstration", "playground", "judges?", "demo mode"):
            assert not re.search(rf"\b{phrase}\b", text), phrase
        blocks = re.findall(r"<script\b[^>]*>(.*?)</script>", page, re.S)
        assert blocks, "no <script> block"
        for js in blocks:  # every script, the simulated-sessions one included
            assert "/api/mode" not in js and "realInput" not in js
    # the real-input screen's styles went with it: nowhere in the stylesheet
    css = _style(admin)
    for rule in (".ri-panel", ".gates", ".a-crumb", ".screen-intro"):
        assert not re.search(rf"{re.escape(rule)}(?![\w-])", css), rule


# --- palette and escaping ----------------------------------------------------------------------------


@pytest.mark.parametrize("surface", ["html", "admin"])
def test_only_the_rev3_token_colours(surface, request):
    # Rev 3 §1 replaced the six rev 2 tokens with one palette per surface (both ship in the shared CSS).
    html = request.getfixturevalue(surface)
    found = {m.upper() for m in re.findall(r"(?<![&\w])#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b", html)}
    assert found == ALLOWED_HEX, found ^ ALLOWED_HEX
    alpha = {m.upper() for m in re.findall(r"(?<![&\w])#([0-9A-Fa-f]{8})\b", html)}
    assert alpha == ALLOWED_ALPHA_HEX, alpha ^ ALLOWED_ALPHA_HEX
    assert not re.search(r"\b(rgba?|hsla?)\(", html)


@pytest.mark.parametrize("surface", ["html", "admin"])
def test_no_html_sinks_with_data(surface, request):
    html = request.getfixturevalue(surface)
    for rhs in re.findall(r"innerHTML\s*=\s*([^;\n]*)", html):
        assert rhs.strip() in ("''", '""'), rhs
    for sink in ("outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert sink not in html, sink
    # every href set from script goes through the allow-list helper (https: or '#')
    assert not re.search(r"setAttribute\(\s*['\"]href", html)
    for rhs in re.findall(r"\.href\s*=\s*([^;\n]*)", html):
        assert rhs.strip().startswith("safeHref("), rhs


@pytest.mark.parametrize("surface", ["html", "admin"])
def test_no_external_resources(surface, request):
    html = request.getfixturevalue(surface)
    assert not re.search(r"<(script|link|img|iframe)\b[^>]*\b(src|href)=\"(https?:)?//", html)
    assert "@import" not in html and "@font-face" not in html


# --- T1.5 -------------------------------------------------------------------------------------------


def test_t1_5_openapi_title_and_description(client):
    info = client.get("/openapi.json").json()["info"]
    assert info["title"] == "Clinical Human Clone API"
    d = info["description"].lower()
    # P6.2 (G38): production-style wording, as P6.1 did for the UI copy (was "Synthetic data only … Not
    # for clinical use"); the synthetic-data disclosure is in docs/daypart/submission/assumptions-limits.md.
    # HAC-76: on-screen labels went; the API contract (T1.5) keeps "Real input is off in this build".
    assert "not medical advice" in d and "real input is off in this build" in d and "playground" not in d
    for word in ("synthetic", "simulated", "demo", "not for clinical use", "clinically", "fda", "regulat", "approved", "reviewed by"):
        assert word not in d, word


# --- T1.3 -------------------------------------------------------------------------------------------


def test_t1_3_no_real_input_phrase_in_new_json(client):
    bodies = []

    def hit(r, *ok):
        assert r.status_code in ok, (r.status_code, r.text)
        bodies.append(r.text)
        return r.json()

    hit(client.get("/api/mode"), 200)
    hit(client.post("/api/mode", json={"real_input": True}), 403)
    member = client.get("/api/members").json()[0]["member_id"]
    jid = hit(client.post("/api/journals", json={"member_id": member}), 201)["journal_id"]
    hit(client.get(f"/api/journals/{jid}/next-step"), 409)
    hit(client.get("/api/fixtures"), 200)
    ci = hit(client.post("/api/checkins", json={"journal_id": jid, "text": "slept 6 hours and walked 8000 steps"}), 201)
    decisions = [
        {"proposal_id": p["proposal_id"], "action": "discard" if p["blocking"] else "confirm"} for p in ci["proposals"]
    ]
    hit(client.post(f"/api/checkins/{ci['checkin_id']}/review", json={"decisions": decisions}), 200)
    hit(client.post(f"/api/checkins/{ci['checkin_id']}/review", json={"decisions": decisions}), 409)
    hit(client.get(f"/api/journals/{jid}/passport"), 200)
    step = hit(client.get(f"/api/journals/{jid}/next-step"), 200)
    hit(client.post(f"/api/journals/{jid}/next-step", json={"step_id": step["step_id"], "choice": "choose"}), 200)
    hit(client.post(f"/api/journals/{jid}/next-step", json={"step_id": "ns-stale", "choice": "defer"}), 422)
    hit(client.get("/api/lab"), 200)
    hit(client.get("/api/inventory"), 200)
    hit(client.post("/api/journals", json={"member_id": "cur-001"}), 404)
    for b in bodies:
        assert REAL_INPUT_PHRASE not in b


def _run_safe_href(cases: list[str]) -> list[object]:
    """Run the page's own safeHref in node over ``cases``."""
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    html = (Path(__file__).resolve().parents[2] / "daypart/demo/static/index.html").read_text()
    m = re.search(r"function safeHref\(u\) \{.*?\n\}", html, re.S)
    assert m, "safeHref not found"
    js = m.group(0) + f"\nconsole.log(JSON.stringify({json.dumps(cases)}.map(safeHref)));"
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, check=True, timeout=30)
    return json.loads(out.stdout)


def test_safe_href_links_same_origin_api_paths_only() -> None:
    """Evidence-thread links to /api/... are same-origin and get linked; everything else is refused."""
    got = _run_safe_href([
        "/api/fixtures/scale-photo",
        "/api/journals/j1/observations/r1",
        "#lab/run-1",
        "https://medlineplus.gov/ency/article/002341.htm",
        "//evil.example/api/x",
        "/\\evil.example",
        "/results",
        "javascript:alert(1)",
        "http://example.com/",
        "/api/../etc",
        "",
        "/api/%2e%2e/results",
        "/api/%2E%2e/docs",
        "/api/x/%2E./y",
        "/api/x%2fy",
        "/api/x%5Cy",
        "/api//evil",
        "data:text/html,x",
        " javascript:alert(1)",
        "/api/journals/j1/observations/r%201",
    ])
    assert got == [
        "/api/fixtures/scale-photo",
        "/api/journals/j1/observations/r1",
        "#lab/run-1",
        "https://medlineplus.gov/ency/article/002341.htm",
        None, None, None, None, None, None, None,
        None, None, None, None, None, None, None, None,
        "/api/journals/j1/observations/r%201",
    ]


# --- HAC-48 rev 2: the six states that replaced the interim treatment ---------------------------------


def _script(html: str) -> str:
    """The journey script (the last <script> block), research view excluded."""
    src = _without_research(html) if 'id="screen-sessions"' in html else html
    blocks = re.findall(r"<script>(.*?)</script>", src, re.S)
    assert blocks, "no journey script"
    return blocks[-1]


def _section(src: str, start: str, end: str) -> str:
    i = src.index(start)
    return src[i : src.index(end, i)]


def _style(html: str) -> str:
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    assert m
    return m.group(1)


def _string_literals(js: str) -> list[str]:
    return [a or b for a, b in re.findall(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'', js)]


def _run_js(names: list[str], expr: str) -> object:
    """Run the named top-level functions/vars of the page script in node and return ``expr`` (JSON)."""
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    src = (Path(__file__).resolve().parents[2] / "daypart/demo/static/index.html").read_text()
    parts = []
    for n in names:
        m = re.search(r"^(?:function " + re.escape(n) + r"\(.*?\n\}|var " + re.escape(n) + r" = .*?;)$", src, re.S | re.M)
        assert m, f"{n} not found"
        parts.append(m.group(0))
    js = "var S = { today: null };\n" + "\n".join(parts) + f"\nconsole.log(JSON.stringify({expr}));"
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, check=True, timeout=30)
    return json.loads(out.stdout)


# A tiny DOM for node: enough of Element/document for the page's own helpers. ``mk(id, tag)`` adds a
# connected element; ``RESP`` is the queue fetch answers from ([status, json] or "network"); ``CALLS``
# records each fetch as [method, path, body].
_DOM_STUB = r"""
var ALL = [];
class El {
  constructor(tag) { this.tagName = String(tag).toUpperCase(); this.childNodes = []; this.attrs = {}; this.className = "";
    this.hidden = false; this.style = {}; this.dataset = {}; this.value = ""; this.listeners = {}; this.parentNode = null; this.id = ""; ALL.push(this); }
  get textContent() { return this.childNodes.map(function (c) { return typeof c === "string" ? c : c.textContent; }).join(""); }
  set textContent(v) { this.replaceChildren(String(v)); }
  get children() { return this.childNodes.filter(function (c) { return typeof c !== "string"; }); }
  append() { for (var i = 0; i < arguments.length; i++) { var n = arguments[i];
    if (typeof n !== "string") { if (n.parentNode) n.parentNode.childNodes.splice(n.parentNode.childNodes.indexOf(n), 1); n.parentNode = this; }
    this.childNodes.push(n); } }
  prepend() { var old = this.childNodes; this.childNodes = []; this.append.apply(this, arguments); this.childNodes = this.childNodes.concat(old); }
  replaceChildren() { this.childNodes.forEach(function (c) { if (typeof c !== "string") c.parentNode = null; }); this.childNodes = []; this.append.apply(this, arguments); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null; }
  hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k); }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); }
  click() { (this.listeners.click || []).forEach(function (f) { f({ preventDefault: function () {} }); }); }
  focus() { document.activeElement = this; }
  scrollIntoView() {}
  all() { var out = []; this.children.forEach(function (c) { out.push(c); out = out.concat(c.all()); }); return out; }
  matches(sel) { var m = /^([a-z0-9]*)((?:\.[\w-]+)*)$/i.exec(sel); if (!m) throw new Error("selector " + sel);
    if (m[1] && this.tagName !== m[1].toUpperCase()) return false; var cls = this.className.split(/\s+/);
    return m[2].split(".").filter(Boolean).every(function (c) { return cls.indexOf(c) >= 0; }); }
  querySelectorAll(sel) { return this.all().filter(function (e) { return e.matches(sel); }); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
}
function connected(e) { while (e) { if (e === document.body) return true; e = e.parentNode; } return false; }
var document = { body: null, activeElement: null, title: "",
  createElement: function (t) { return new El(t); },
  getElementById: function (id) { return ALL.find(function (e) { return e.id === id && connected(e); }) || null; },
  querySelectorAll: function (s) { return document.body.querySelectorAll(s); },
  querySelector: function (s) { return document.body.querySelector(s); } };
document.body = new El("body"); document.activeElement = document.body;
function mk(id, tag) { var e = new El(tag || "div"); e.id = id; document.body.append(e); return e; }
function Option(text, value) { var o = new El("option"); o.textContent = text; o.value = value; return o; }
var location = { hash: "" };
var S = { journal: "j1", today: null, checkins: {}, lastCheckin: null };
var RESP = [], CALLS = [];
var fetch = async function (path, init) {
  CALLS.push([init.method, path, init.body === undefined ? null : JSON.parse(init.body)]);
  var r = RESP.shift();
  if (r === undefined || r === "network") throw new TypeError("network");
  return { status: r[0], ok: r[0] >= 200 && r[0] < 300, json: async function () { return r[1]; } };
};
"""


def _run_page(names: list[str], body: str) -> object:
    """Run the named page functions/vars over :data:`_DOM_STUB`; ``body`` is async JS that returns a value."""
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    src = (Path(__file__).resolve().parents[2] / "daypart/demo/static/index.html").read_text()
    parts = []
    for n in names:
        m = re.search(
            r"^(?:(?:async )?function " + re.escape(n) + r"\(.*?\n\}|var " + re.escape(n) + r" = .*?;)$", src, re.S | re.M
        )
        assert m, f"{n} not found"
        parts.append(m.group(0))
    js = (
        _DOM_STUB + "\n".join(parts)
        + "\n(async function () {\n" + body + "\n})().then(function (v) { console.log(JSON.stringify(v)); },"
        + " function (e) { console.error(e && e.stack || e); process.exit(1); });"
    )
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# The helpers every DOM-backed test needs.
_BASE = ["$", "el", "attrs", "safeHref", "link", "nr", "clear", "notice", "bullets", "para", "btnLink",
         "MONTHS", "fmtDay", "fmtDate", "fmtUnit", "fmtNum", "plural"]
_API = ["TIMEOUT_MS", "api", "code", "failed", "serverError", "showError", "isGone"]


def test_rev2_css_brings_over_handoff_info_and_range_rules(html):
    css = _style(html)
    # rev 3 §3.1: the hand-off bar is the surface text colour (was the rev 2 --ink token)
    assert re.search(r"\.notice--handoff\{border-left-color:var\(--c-text\)\}", css)
    assert ".handoff-text{font-weight:600}" in css
    assert '.notice[tabindex="-1"]:focus,.clone-updated[tabindex="-1"]:focus{' in css
    assert ".ref-pop,.ref-src{display:block}" in css
    assert ".visually-hidden{" in css
    assert ".spec{" not in css and "[data-screen]{display:none}" not in css


def test_rev2_crisis_handoff_notice(html):
    js = _script(html)
    hand = _section(js, "function showHandoff", "\n}\n")
    assert '"handoff"' in hand  # notice kind → .notice--handoff
    assert "Please talk to a person about this" in hand
    # rev 3 §3.1: the only copy change (was "This app cannot help with this.")
    assert "Your clone cannot help with this. Nothing from your check-in was saved." in hand
    assert "Write a different check-in" in hand
    assert '"alert"' in hand and "focus" in hand
    # it replaces both columns: the check-in form and the "Your clone" aside (was: the real-data notice)
    assert "setAside(false)" in hand and ".hidden = true" in hand
    assert "A person can help with this" not in js and '"Start again"' not in hand
    # the UI adds no phone number, link or emergency copy of its own: the API text is the body
    assert "tel:" not in html
    assert not re.search(r"\b(911|999|112|988|000)\b", js)
    assert "emergency" not in js.lower()
    note = _section(js, "function notice(", "\n}\n")
    assert "notice--handoff" in note and "aria-labelledby" in note


def test_rev2_checkin_server_copy(html):
    js = _script(html)
    assert "Something went wrong reading your check-in, so nothing was saved" in js
    assert "This is a fault on our side, not in what you wrote. Try again, or add a file." in js  # rev 3 (was "import a file")
    assert "That is too long, so nothing was saved" in js
    assert "Keep your check-in to 500 characters." in js
    assert "extractor_output_invalid" in js


def test_rev2_next_no_saved_checkin_and_stale_step(html):
    js = _script(html)
    assert "Check in first" in js
    assert "A next step comes from your last saved check-in, and you have not saved one yet." in js
    assert "Go to check-in" in js
    assert "No suggestion yet" not in js
    assert "This suggestion has changed" in js
    assert "A newer check-in was saved, so here is the new suggestion. Your choice was not recorded. Choose again below." in js
    nxt = _section(js, "/* ---------- #next", "/* ---------- #lab")
    assert '"aria-busy"' in nxt and '"aria-disabled"' in nxt


def test_rev2_generic_server_and_network_errors(html):
    js = _script(html)
    assert "AbortController" in js
    assert re.search(r"^var TIMEOUT_MS = 15000;$", js, re.M)  # exactly 15 s (§3.8), not 150000
    # AM-2 D2: production copy (was "the demo server" / "The demo had a problem")
    assert "We could not reach the server. Check your connection and try again." in js
    # rev 3 §3.8 (was "The service had a problem on its side (error N)")
    assert "We had a problem on our side (error " in js and "Try again in a moment." in js
    low = " ".join(_string_literals(js)).lower()
    assert not re.search(r"\b(the|this|a) demo\b|demo (file|image|input|server|session)", low), low
    assert '"Try again"' in js
    assert "Something went wrong, so nothing was saved" not in js  # the network copy makes no saving claim
    assert "genericError" not in js
    # error notices never carry the server's body
    assert not re.search(r"(?<!tl-)\bdetail\b", js)  # rev 3's timeline class .tl-detail is not a server field


def test_rev2_get_failure_notice_sits_directly_under_h1(html, admin):
    # AM-2 D1: the lab is on the research console now; the inventory screen joins it there.
    # Rev 3 §3.4, §3.6: an eyebrow line may sit above the h1; the notice slot still follows the h1 directly.
    # Rev 3 §4 (G38): a console h1 sits in the page header (.a-top: crumb, h1, data source); the slot follows it.
    for page, s in ((html, "passport"), (html, "next"), (html, "timeline"), (admin, "pipeline"), (admin, "lab"),
                    (admin, "inventory")):
        sec = _by_id(_tree(page), "screen-" + s)
        kids = [c for c in sec.children if isinstance(c, _Node)]
        if kids[0].tag == "p" and kids[0].attrs.get("class") == "eyebrow":
            kids = kids[1:]
        if page is admin:
            assert kids[0].attrs.get("class") == "a-top", s
            assert [n for n in kids[0].iter() if n.tag == "h1"], s
        else:
            assert kids[0].tag == "h1", s
        assert kids[1].tag == "div" and (kids[1].attrs.get("id") or "").endswith("-msg"), s


def test_rev2_suppressed_explanation_copy_and_no_review_claims(html):
    assert "No reviewed source applies, so no explanation is shown." in html
    low = html.lower()
    for word in ("vetted", "clinically", "approved", "validated"):
        assert word not in low, word


def test_rev2_reference_range_meta_row(html):
    js = _script(html)
    pp = _section(js, "/* ---------- #passport", "/* ---------- #next")
    assert '"Reference range"' in pp
    assert '"Range source: "' in pp
    assert '"no reference range"' in pp
    assert "ref-pop" in pp and "ref-src" in pp and "visually-hidden" in pp
    assert '"aria-hidden"' in pp
    assert "Where a public source states a reference range, the card shows it with the group it applies to and the source. It is reference text only, not a judgement of your value." in html
    # AM-1: no words relating the value to the range, and no plausible bounds, in any passport string
    banned = re.compile(r"\b(high|low|normal|abnormal|in range|out of range|within|above|below|plausible)\b", re.I)
    for s in _string_literals(pp):
        assert not banned.search(s), s
    assert "plausible" not in pp


def test_rev2_range_text_has_a_spoken_twin():
    got = _run_js(["fmtUnit", "fmtNum", "rangeText"], "[rangeText({low:60,high:100,unit:'/min'}), rangeText({low:null,high:7,unit:'{h}'})]")
    assert got[0] == {"visible": "60–100 /min", "spoken": "60 to 100 /min"}
    assert got[1]["visible"] == got[1]["spoken"] and "7 h" in got[1]["visible"]


def test_rev2_review_label_once_in_passport_meta(html):
    got = _run_js(
        ["MONTHS", "fmtDay", "reviewLabel"],
        "[reviewLabel('reviewed: board sign-off 2026-11-07'), reviewLabel('something else'), reviewLabel(null)]",
    )
    assert got == ["Reviewed (board sign-off, 7 Nov 2026)", "something else", None]
    js = _script(html)
    assert js.count('"Review"') == 1


# --- QG P3.1 fixes ------------------------------------------------------------------------------------


def test_c2_correct_sends_unit_and_date_only_when_changed():
    """The server clears unit_assumed / ambiguous_date when unit / date is sent, so a prefilled
    value the person left alone must not be sent (extract_text.py ``"unit" in fields``)."""
    got = _run_js(
        ["correction"],
        "[correction({unit:'kg',date:'2026-11-07',value:70}, '70', 'kg', '2026-11-07'),"
        " correction({unit:'kg',date:'2026-11-07',value:70}, '71', '[lb_av]', '2026-11-06'),"
        " correction({unit:null,date:null,value:null}, '', '', ''),"
        " correction({unit:'kg',date:null,value:70}, '70', '', '2026-11-05')]",
    )
    assert got == [
        {"value": 70},
        {"value": 71, "unit": "[lb_av]", "date": "2026-11-06"},
        {},
        {"value": 70, "date": "2026-11-05"},
    ]


def test_r1_correct_on_a_flagged_proposal_states_the_shown_unit_and_date():
    """QG P3 R1: A&D §4.1, ``unit_assumed`` clears when ``correct`` states a unit explicitly (and
    ``ambiguous_date`` a date). On a flagged proposal Confirm is disabled and Correct is the way to accept
    it, so the unit / date shown in the Correct fields is sent even when unchanged; otherwise a single-unit
    concept (heart rate, only ``/min``) or a right guessed date could never be cleared."""
    got = _run_js(
        ["correction"],
        "[correction({unit:'/min',date:'2026-11-07',value:62,flags:['unit_assumed']}, '62', '/min', '2026-11-07'),"
        " correction({unit:'h',date:'2026-09-28',value:7,flags:['ambiguous_date']}, '7', 'h', '2026-09-28'),"
        " correction({unit:'kg',date:'2026-11-07',value:70,flags:['contradiction']}, '70', 'kg', '2026-11-07'),"
        " correction({unit:'/min',date:'2026-11-07',value:62,flags:['unit_assumed','ambiguous_date']}, '62', '', '')]",
    )
    assert got == [
        {"value": 62, "unit": "/min"},
        {"value": 7, "date": "2026-09-28"},
        {"value": 70},
        {"value": 62},
    ]


def test_c1_correct_unit_select_offers_the_allowed_units():
    units = "{'29463-7':['kg','[lb_av]','g'],'8867-4':['/min']}"
    got = _run_js(
        ["fmtUnit", "unitChoices"],
        f"[unitChoices({{concept_code:'29463-7',unit:'[lb_av]'}}, {units}),"
        f" unitChoices({{concept_code:'29463-7',unit:'mm[Hg]'}}, {units}),"
        f" unitChoices({{concept_code:null,unit:'kg'}}, {units}),"
        f" unitChoices({{concept_code:'8867-4',unit:'/min'}}, null)]",
    )
    # the proposal's unit first, selected, only when allowed
    assert got[0] == [{"value": "[lb_av]", "label": "[lb_av]", "selected": True},
                      {"value": "kg", "label": "kg"}, {"value": "g", "label": "g"}]
    # a mismatched unit is shown as the current value but is not a selectable choice
    head, rest = got[1][0], got[1][1:]
    assert head["value"] == "" and head["selected"] and head["disabled"] and "mm[Hg]" in head["label"]
    assert [o["value"] for o in rest] == ["kg", "[lb_av]", "g"] and not any(o.get("disabled") for o in rest)
    assert got[2] is None and got[3] is None  # no concept or no unit list: no select of allowed units


def test_c1_review_fetches_the_allowed_units(html):
    js = _script(html)
    rv = _section(js, "/* ---------- #review", "/* ---------- #passport")
    assert '"/api/units"' in rv and "unitChoices(p, units)" in rv


_REVIEW = ["persist", "correction", "decisionsRv", "pid", "rvCurrent", "unitsPending", "loadUnits", "rvSeq", "showReview", "savedNotice", "alreadySavedNotice", "submitReview", "sessionEnded"]


def test_c3_already_saved_revisit_shows_no_count():
    got = _run_page(
        _BASE + _API + _REVIEW,
        """
        S.checkins = { c1: { proposals: [], status: "pending_review", result: null } };
        ["rv-intro", "rv-msg", "rv-list", "session-msg"].forEach(function (i) { mk(i); });
        mk("rv-form", "form"); mk("rv-submit", "button");
        rvCurrent = "c1";
        RESP.push([409, { error: "already_saved" }]);
        await submitReview({ preventDefault: function () {} });
        var first = $("rv-msg").textContent;
        await showReview("c1");  // revisit
        var again = $("rv-msg").querySelector(".notice-title").textContent;
        return [first, again, $("rv-msg").textContent];
        """,
    )
    assert "Already saved" in got[0]
    assert got[1] == "Already saved"
    assert not re.search(r"Saved \d", got[2]), got[2]


_THREAD = ["STEP_NAMES", "ADMIN_CONSOLE_ROUTES", "ADMIN_HASH", "memberLink", "viewText", "thread"]
_STEPS_TAIL = """{ label: "Memory core-v1+u1", ontology_version: "core-v1+u1", readiness: "ready", link: "#passport/inventory" },
  { label: "none", status: "suppressed", links: [], note: "no source" },
  { label: "none", rule_version: "boundary-v1", run_id: null, link: "" }"""


def _thread_links(step0: str, step1: str) -> object:
    return _run_page(
        _BASE + _THREAD,
        f"""
        var d = thread([{step0}, {step1}, {_STEPS_TAIL}]);
        var lis = d.querySelectorAll("li");
        return [0, 1].map(function (i) {{
          return {{ text: lis[i].textContent, links: lis[i].querySelectorAll("a").map(function (a) {{ return [a.href, a.textContent]; }}) }};
        }});
        """,
    )


def test_c4_thread_links_same_origin_api_steps():
    got = _thread_links(
        '{ label: "Demo file", ref: "scale-photo", link: "/api/fixtures/scale-photo" }',
        '{ label: "Saved observation", event_id: "e1", record_id: "r1", link: "/api/journals/j1/observations/r1" }',
    )
    assert [h for h, _ in got[0]["links"]] == ["/api/fixtures/scale-photo"]
    assert [h for h, _ in got[1]["links"]] == ["/api/journals/j1/observations/r1"]
    assert "check-in" not in got[0]["text"]  # a demo file is not a check-in
    # an unsafe link is never an <a>
    bad = _thread_links('{ label: "Demo file", ref: "x", link: "/api/%2e%2e/results" }',
                        '{ label: "Saved observation", event_id: "e1", record_id: "r1", link: "javascript:alert(1)" }')
    assert bad[0]["links"] == [] and bad[1]["links"] == []


def test_am2_d1_learning_run_link_is_text_in_the_member_app():
    got = _run_page(
        _BASE + _THREAD,
        """
        var d = thread([{ label: "Your text", ref: "ci-1", link: "#review/ci-1" },
          { label: "Saved observation", event_id: "e1", record_id: "r1", link: "/api/journals/j1/observations/r1" },
          { label: "Memory", ontology_version: "core-v1+u1", readiness: "ready", link: "#passport/inventory" },
          { label: "none", status: "suppressed", links: [], note: "no source" },
          { label: "boundary-v1", rule_version: "boundary-v1", run_id: "tag/dpo", link: "#lab/tag/dpo" }]);
        var li = d.querySelectorAll("li")[4];
        return { text: li.textContent, links: li.querySelectorAll("a").length };
        """,
    )
    assert got == {"text": got["text"], "links": 0} and "tag/dpo" in got["text"]


def test_b4_member_never_links_any_console_route():
    """QG P6.2 B4: the member app treats every console route (``app.ADMIN_ROUTES``) and the #research
    alias as the console's, so an evidence link to any of them is text, never a link."""
    import json

    from daypart.demo.app import ADMIN_ROUTE_ALIASES, ADMIN_ROUTES

    console = list(ADMIN_ROUTES) + list(ADMIN_ROUTE_ALIASES)
    got = _run_page(_BASE + ["ADMIN_CONSOLE_ROUTES", "ADMIN_HASH", "memberLink"], f"""
        var c = {json.dumps(console)};
        return {{ routes: ADMIN_CONSOLE_ROUTES, bare: c.map(function (r) {{ return memberLink("#" + r); }}),
          deep: c.map(function (r) {{ return memberLink("#" + r + "/x"); }}),
          member: ["#passport", "#review/ci-1", "#timeline", "#labs", "/api/journals/j1/observations/r1"].map(memberLink) }};
    """)
    assert sorted(got["routes"]) == sorted(console)
    assert not any(got["bare"]) and not any(got["deep"])
    assert all(got["member"])  # member routes, and a word that only starts like a console route, stay links


def test_c5_simulated_source_is_never_called_a_check_in():
    sim = _thread_links('{ label: "Simulated cohort", ref: "simulated-cohort/seed-0", link: "#research" }',
                        '{ label: "simulated series", event_id: null, record_id: null, link: "#research" }')
    for step in sim:
        assert "check-in" not in step["text"], step
        # AM-2 D1 (G31): the member app never links into the research console, so the simulated
        # cohort source is named as text (was: a "view in research view" link to #research).
        assert step["links"] == []
    assert "simulated-cohort/seed-0" in sim[0]["text"]
    own = _thread_links('{ label: "Your text", ref: "ci-1", link: "#review/ci-1" }',
                        '{ label: "Saved observation", event_id: "e1", record_id: "r1", link: "/api/journals/j1/observations/r1" }')
    assert own[0]["links"] == [["#review/ci-1", "view check-in ci-1"]]


_LAB = ["ROW_NAMES", "ROW_SHORT", "cell", "parts", "pct", "pts", "count", "intOrNull", "mismatched", "mismatchTag",
        "rowPct", "envName", "stepName", "runAnchor", "modelRow", "envRow", "recordRow"]


def test_c6_lab_base_row_shows_the_file_digest_as_text():
    got = _run_page(
        _BASE + _LAB,
        """
        var tr = recordRow({ row: "base", kind: "model", status: "ok", run_id: "tag/base", file_digest: "0123456789ab",
          split: { prompt_set_version: "v1", n: 10 }, seed: 0, failures: 1, degenerate: 0, metrics: {} });
        var id = tr.children[1];
        var mono = id.querySelectorAll("code").filter(function (c) { return c.textContent === "0123456789ab"; });
        return { text: id.textContent, mono: mono.map(function (c) { return c.className; }),
                 links: id.querySelectorAll("a").map(function (a) { return a.textContent; }) };
        """,
    )
    assert "file digest 0123456789ab" in got["text"]
    assert got["mono"] == ["mono run-id"]  # the only cells that may break anywhere (G5)
    assert "0123456789ab" not in got["links"]  # text only, never a link


_CARD = ["card", "rangeText", "rangeHost", "rangeCell", "STEP_NAMES", "viewText", "thread"]


def _card_explain(step3: str, extra: str = "") -> object:
    return _run_page(
        _BASE + _CARD,
        f"""
        var c = {{ title: "Pulse", origin: "observed", status: "ready", value: 72, unit: "/min", source: "Your text",
          method: "m", limits: ["l"], reference_range_status: "none", data_age_days: 0, explanation: null {extra},
          thread: {{ steps: [{{ label: "none" }}, {{ label: "none" }}, {{ label: "m", ontology_version: "v", link: "" }}, {step3},
            {{ label: "none", rule_version: "r" }}] }} }};
        var art = card(c, 0);
        return {{ explain: art.querySelector(".explain").textContent, value: art.querySelector(".card-value").textContent }};
        """,
    )


def test_d1_no_reviewed_source_copy_only_when_there_is_no_source():
    none = _card_explain('{ label: "none", status: "suppressed", links: [] }')
    assert "No reviewed source applies, so no explanation is shown." in none["explain"]
    sourced = _card_explain(
        '{ label: "MedlinePlus: Vital signs", status: "suppressed", links: ["https://medlineplus.gov/x"],'
        ' note: "the explanation failed the safety check, so it is not shown" }'
    )
    assert "No reviewed source applies" not in sourced["explain"]
    assert "Not enough evidence" in sourced["explain"]


_NEXT = ["journalPending", "createJournal", "ensureJournal", "sessionEnded", "nsBusy", "noSaved", "loadStep",
         "renderStep", "nsPanelBusy", "choose"]


def _stale_then(second: str) -> object:
    return _run_page(
        _BASE + _API + _NEXT,
        f"""
        ["ns-msg", "ns-panel", "ns-result", "session-msg"].forEach(function (i) {{ mk(i); }});
        RESP.push([422, {{ error: "unknown_step" }}], {second});
        await choose("ns-1", "choose");
        var n = $("ns-msg").querySelector(".notice");
        return {{ calls: CALLS.map(function (c) {{ return c[0]; }}), title: n && n.querySelector(".notice-title").textContent,
          role: n && n.getAttribute("role"), tabindex: n && n.getAttribute("tabindex"), focused: document.activeElement === n,
          panelHidden: $("ns-panel").hidden }};
        """,
    )


def test_d4_stale_step_refetch_409_is_a_post_alert_with_focus():
    got = _stale_then('[409, { error: "no_saved_checkin" }]')
    assert got["calls"] == ["POST", "GET"]  # never re-sends the choice
    assert got["title"] == "Check in first"
    assert got["role"] == "alert" and got["tabindex"] == "-1" and got["focused"] and got["panelHidden"]


@pytest.mark.parametrize("second", ['[503, null]', '"network"'])
def test_d4_stale_step_refetch_failure_takes_focus(second):
    got = _stale_then(second)
    assert got["calls"] == ["POST", "GET"]
    assert got["title"] == "Something went wrong"
    assert got["role"] == "alert" and got["tabindex"] == "-1" and got["focused"]


# rev 3: updateNav also draws the journal's identity (applyIdentity), and #today loads the "Your clone" aside
_IDENTITY = ["WEEKDAYS", "fmtShortDay", "fmtWeekday", "firstName", "applyIdentity"]
_TL = ["fmtValue", "shiftDate", "TL_CHIPS", "tlChanges", "tlAppends", "tlStep", "tlTitle", "tlChips", "tlAdded", "tlSentences",
       "deltaRows", "tlDays", "tlDayLabel"]
_CHECKIN = ["persist", "updateNav", "journalPending", "adoptJournal", "createJournal", "ensureJournal", "ciBusy", "showCheckin",
            "loadFixtures", "submitCheckin", "setAside", "cloneSeq", "loadClone", "renderClone"] + _IDENTITY + _TL
_CI_DOM = """
mk("ci-load-msg"); var body = mk("ci-body"); ["ci-files", "ci-images"].forEach(function (i) { var b = mk(i); b.append(el("ul")); });
mk("nav-review", "a"); mk("ci-grid"); mk("clone-aside", "aside"); mk("ci-form", "form");
function state() { var n = $("ci-load-msg").querySelector(".notice");
  return { title: n && n.querySelector(".notice-title").textContent, role: n && n.getAttribute("role"),
           bodyHidden: $("ci-body").hidden, text: $("ci-load-msg").textContent }; }
"""


def test_d5_checkin_journal_failure_shows_the_generic_notice_and_try_again_reloads():
    got = _run_page(
        _BASE + _API + _CHECKIN,
        _CI_DOM + """
        S.journal = null;
        RESP.push([503, null]);
        await showCheckin();
        var failed = state();
        // AM-2 D2 (G32): the journal is the seeded persona's (GET /api/personas, then POST {persona})
        RESP.push([200, [{ persona_id: "persona-v1", display_name: "Rowan Ellis" }]],
                  [201, { journal_id: "j9", today: "2026-11-07", persona_id: "persona-v1", display_name: "Rowan Ellis" }], [200, []]);
        $("ci-load-msg").querySelector("button").click();
        await new Promise(function (r) { setTimeout(r, 50); });
        return [failed, state(), S.journal, S.displayName, CALLS.map(function (c) { return [c[0], c[1], c[2]]; })];
        """,
    )
    assert got[0]["title"] == "Something went wrong" and got[0]["role"] == "alert" and got[0]["bodyHidden"]
    assert "(error 503)" in got[0]["text"]
    assert got[1]["title"] is None and not got[1]["bodyHidden"] and got[2] == "j9" and got[3] == "Rowan Ellis"
    assert got[4][1:3] == [["GET", "/api/personas", None], ["POST", "/api/journals", {"persona": "persona-v1"}]]


@pytest.mark.parametrize("resp", ['[500, null]', '"network"'])
def test_d5_checkin_fixture_list_failure_shows_the_generic_notice(resp):
    got = _run_page(_BASE + _API + _CHECKIN, _CI_DOM + f"RESP.push({resp}); await showCheckin(); return state();")
    assert got["title"] == "Something went wrong" and got["role"] == "alert" and got["bodyHidden"]


def test_d5_checkin_load_notice_sits_directly_under_h1(html):
    # rev 3 §3.1: the h1 now sits in the left column of #today, under the eyebrow date
    hero = _by_id(_tree(html), "ci-hero")
    kids = [c for c in hero.children if isinstance(c, _Node)]
    assert kids[0].attrs.get("id") == "ci-date" and kids[1].tag == "h1" and kids[2].attrs.get("id") == "ci-load-msg"


def test_d6_inventory_copy_matches_spec():
    got = _run_js(
        ["plural", "invTag"],
        "[invTag([{status:'ready'}]), invTag([{status:'ready'},{status:'withheld'},{status:'withheld'}]),"
        " invTag([{status:'withheld'}]), invTag([])]",
    )
    assert got == [
        {"covered": True, "text": "✓ 1 card"},
        {"covered": True, "text": "✓ 3 cards"},
        {"covered": False, "text": "○ Gap: no data yet"},
        {"covered": False, "text": "○ Gap: no data yet"},
    ]


def test_u1_no_element_id_equals_a_route_hash(html):
    """A section id equal to the route hash (#checkin) makes the browser fragment-scroll on a direct load,
    which drops the h1 focus to BODY. Screens are ``screen-<route>``; route() still focuses the h1."""
    root = _tree(html)
    ids = {n.attrs.get("id") for n in root.iter()}
    assert not ids & set(SCREENS), ids & set(SCREENS)
    for s in SCREENS:
        assert _by_id(root, "screen-" + s).tag == "section"
    js = _script(html)
    rt = _section(js, "function route()", "\n}\n")
    assert '$("screen-" + s).hidden' in rt and '$("h-" + r.base).focus()' in rt
    assert _by_id(root, "inventory").tag == "ul"  # the #passport/inventory scroll target is kept


def test_u2_display_rounding_and_dimensionless_unit():
    got = _run_js(["fmtUnit", "fmtNum", "fmtRound"],
                  "[fmtRound(57.14285714285714), fmtRound(2.5), fmtRound(3), fmtRound(0.1 + 0.2), fmtRound(NaN),"
                  " fmtUnit('1'), fmtUnit('{score}'), fmtUnit('/min'), fmtNum(36.555)]")
    assert got == ["57.14", "2.5", "3", "0.3", None, "", "score", "/min", "36.555"]


def _card_value(kind: str, origin: str, value: str, unit: str) -> str:
    return _run_page(
        _BASE + _CARD + ["fmtRound"],
        f"""
        var c = {{ title: "t", kind: "{kind}", origin: "{origin}", status: "ready", value: {value}, unit: "{unit}", source: "s",
          method: "m", limits: ["l"], reference_range_status: "withheld", data_age_days: 0, explanation: null,
          thread: {{ steps: [] }} }};
        return card(c, 0).querySelector(".card-value").textContent;
        """,
    )


def test_u2_cards_round_scores_but_keep_saved_observations_as_recorded():
    assert _card_value("pattern", "observed", "57.14285714285714", "{score}").strip() == "57.14 score"
    assert _card_value("observation", "simulated", "6.666666", "h").strip() == "6.67 h"
    assert _card_value("observation", "observed", "36.555", "Cel").strip() == "36.555 Cel"  # as recorded
    assert _card_value("observation", "observed", "0", "1").strip() == "0"  # no dimensionless "1"


_SUBMIT = _BASE + _API + _CHECKIN + ["CI_ERRORS", "PII_REASONS", "setCiError", "resetCheckin", "updateCount", "setBusy", "showHandoff"]
_HANDOFF_TEXT = "Please contact someone you trust or a local crisis service now."


def _handoff_run() -> dict:
    return _run_page(
        _SUBMIT,
        """
        ["ci-msg", "ci-count", "ci-intro", "ci-grid", "clone-aside", "session-msg", "nav-review"].forEach(function (i) { mk(i); });
        var form = mk("ci-form", "form"); var ta = el("textarea"); ta.id = "ci-text"; form.append(ta); var sb = el("button"); sb.id = "ci-submit"; form.append(sb);
        ta.value = "something the person wrote";
        location.hash = "#checkin";
        RESP.push([200, { status: "handoff", text: %s }]);
        await submitCheckin({ text: ta.value });
        var box = $("ci-msg"), n = box.querySelector(".notice");
        return { kind: n && n.className, hash: location.hash, calls: CALLS.length,
          handoff: (box.querySelector(".handoff-text") || { textContent: null }).textContent,
          links: box.querySelectorAll("a").length, buttons: box.querySelectorAll("button").map(function (b) { return b.textContent; }),
          focused: document.activeElement === n, role: n && n.getAttribute("role"),
          formHidden: $("ci-form").hidden, introHidden: $("ci-intro").hidden, asideHidden: $("clone-aside").hidden,
          textarea: ta.value, checkins: Object.keys(S.checkins).length };
        """ % repr(_HANDOFF_TEXT).replace("'", '"'),
    )


def test_t1_handoff_response_routes_to_show_handoff_without_review_or_next():
    got = _handoff_run()
    assert got["kind"] == "notice notice--handoff", got
    assert got["role"] == "alert" and got["focused"]
    assert got["hash"] == "#checkin" and got["checkins"] == 0 and got["calls"] == 1  # never routes to #review
    assert got["links"] == 0  # no #review / #next (or any) link
    assert got["buttons"] == ["Write a different check-in"]  # no extra button


def test_t2_handoff_body_is_the_api_text_verbatim_and_the_form_is_gone(html):
    got = _handoff_run()
    assert got["handoff"] == _HANDOFF_TEXT  # verbatim, nothing added or replaced
    assert got["formHidden"] and got["introHidden"] and got["asideHidden"]  # both columns (was: the real-data notice)
    assert got["textarea"] == ""
    # the UI adds no number, link or href of its own (substring bans: no word boundaries to slip past)
    hand = _section(_script(html), "function showHandoff", "\n}\n")
    for banned in ("988", "911", "href", "link(", "btnLink(", "tel:", "http", "lifeline"):
        assert banned not in hand, banned


def test_k1_lab_mismatch_and_missing_seed_rows_render_the_a_and_d_words():
    """QG P3 K1: A&D §4.8 / T8.3 and G25: an adapter mismatch row shows "provenance mismatch" (the API
    ``status``, verbatim) and no number; a missing seed renders "not recorded" (T8.3's UI half). HAC-76:
    the plain results row and the run record both hold to it."""
    got = _run_page(
        _BASE + _LAB,
        """
        var mmr = { row: "sft", kind: "model", status: "provenance mismatch", run_id: "tag/sft",
          split: { prompt_set_version: "v1", n: 10, training_rows: 99, data_sha256: "abcdefabcdef0000" },
          seed: 3, failures: 1, degenerate: 0, metrics: { boundary_pass_rate: 0.9, rubric_pass_rate: 0.8 } };
        var ns = recordRow({ row: "base", kind: "model", status: "ok", run_id: "tag/base",
          split: { prompt_set_version: "v1", n: 10 }, seed: null, failures: 1, degenerate: 0, metrics: {} });
        var gpr = { row: "grpo", kind: "proposed", status: "proposed, not built", reason: "not run" };
        function cells(tr) { return tr.children.map(function (c) { return [c.getAttribute("data-label"), c.textContent]; }); }
        return { mm: cells(modelRow(mmr)), mmrec: cells(recordRow(mmr)), ns: cells(ns), gp: cells(modelRow(gpr)), gprec: cells(recordRow(gpr)) };
        """,
    )
    mm = dict(got["mm"])
    assert mm["Safety rule pass rate"] == "⚠ provenance mismatch" and mm["Coaching quality pass rate"] == "⚠ provenance mismatch"
    assert "provenance mismatch" in mm["Outcome"]
    for label in ("Trained on", "Safety rule pass rate", "Coaching quality pass rate", "Outcome"):
        assert not re.search(r"\d", mm[label]), (label, mm[label])
    rec = dict(got["mmrec"])
    assert "provenance mismatch" in rec["Run ID"]  # the A&D's words, case and all
    assert "n =" not in rec["Test set"] and "training rows" not in rec["Test set"]
    for label in ("Seed", "Failures"):
        assert not re.search(r"\d", rec[label]), (label, rec[label])
    assert dict(got["ns"])["Seed"] == "not recorded"
    gp = dict(got["gp"])
    assert gp["Training step"] == "Step 3 · Practice with simulated members"
    assert gp["Outcome"] == "○ Planned, not builtnot run"  # the reason verbatim from the API, on its own line
    assert gp["Safety rule pass rate"] == "Not built yet" and not re.search(r"\d", gp["Coaching quality pass rate"])
    assert "proposed, not built" in dict(got["gprec"])["Run ID"]
    for row in (got["mm"], got["mmrec"], got["ns"], got["gp"], got["gprec"]):
        assert all(label for label, _ in row)  # every cell has data-label (the 375 px stacked layout)


def test_hac76_results_tables_speak_plain_language_and_read_every_number_from_the_api():
    """HAC-76: the results tables name each step and approach in words and show each rate as a percentage
    of the API's own number; nothing is rounded twice or invented."""
    from daypart.demo import lab
    import json

    t = lab.lab_rows().model_dump(mode="json")
    got = _run_page(
        _BASE + _LAB,
        """
        var t = LAB;
        function cells(tr) { return tr.children.map(function (c) { return c.textContent; }); }
        return { models: t.rows.filter(function (r) { return r.kind === "model" || r.kind === "proposed"; }).map(function (r) { return cells(modelRow(r)); }),
          envs: t.rows.filter(function (r) { return r.kind === "env_baseline" || r.kind === "policy"; }).map(function (r) { return cells(envRow(r)); }) };
        """.replace("LAB", json.dumps(t)),
    )
    rows = {r["row"]: r for r in t["rows"]}
    pc = lambda v: f"{v * 100:.1f}%"  # noqa: E731
    pt = lambda v: ("+" if v >= 0 else "−") + f"{abs(v * 100):.1f} points"  # noqa: E731
    base, sft, dpo = rows["base"], rows["sft"], rows["dpo"]
    assert got["models"][0] == ["Starting model, before training", "General model, no coaching training",
                                pc(base["metrics"]["boundary_pass_rate"]), pc(base["metrics"]["rubric_pass_rate"]),
                                "Reference point for the steps below"]
    assert got["models"][1][:4] == ["Step 1 · Learning from example replies", f"{sft['split']['training_rows']:,} example replies",
                                    pc(sft["metrics"]["boundary_pass_rate"]), pc(sft["metrics"]["rubric_pass_rate"])]
    assert got["models"][1][4] == f"✓ Passed its checkSafety {pt(sft['gate']['delta'])} · vs. starting model"
    assert got["models"][2][1] == f"{dpo['split']['training_rows']:,} pairs of better and worse replies"
    assert got["models"][2][4] == (f"✓ Passed its checkQuality {pt(dpo['gate']['rubric_delta'])} · vs. step 1 · "
                                   f"safety regressions: {dpo['gate']['boundary_regressions']}")
    envs = [r for r in t["rows"] if r["kind"] in ("env_baseline", "policy")]
    assert len(envs) == len(got["envs"])
    for r, row in zip(envs, got["envs"]):
        assert row[1] == pc(r["metrics"]["mean_adherence"]) and row[2] == pc(r["metrics"]["episode_violation_rate"])
        assert row[3] == f"{r['split']['n']} sessions{r['split']['n_scenarios']} members, {r['split']['horizon']} days each"
        assert "env_" not in row[0] and "_" not in row[0]
    assert {row[0] for row in got["envs"]} >= {"No coaching message", "A random approach each day"}


def test_k6_footer_carries_the_attribution_loinc_notice_verbatim(html):
    """QG P3 K6: D-A5 / T5.6: the LOINC notice in the UI footer is the ATTRIBUTION notice word for word."""
    attribution = (Path(__file__).resolve().parents[3] / "ATTRIBUTION.md").read_text()
    sec = attribution[attribution.index("### LOINC") :]
    notice = next(p for p in sec.split("\n\n")[1:] if p.strip()).strip()
    assert notice.startswith("This material contains content from LOINC")
    root = _tree(html)
    foot = next(n for n in root.iter() if n.tag == "footer")
    assert " ".join(notice.split()) in " ".join(foot.text().split())
    hrefs = {n.attrs.get("href") for n in foot.iter() if n.tag == "a"}
    assert {"https://loinc.org", "https://loinc.org/license/"} <= hrefs


_REFUSAL = ["FLAG_NAMES", "CORRECTION_WHY", "pTitle", "focusTarget", "refusalItem", "refused"]


def _refusal(body: dict) -> dict:
    import json

    return _run_page(
        _BASE + _API + _REVIEW + _REFUSAL,
        f"""
        S.checkins = {{ c1: {{ status: "pending_review", result: null, proposals: [
          {{ proposal_id: "p1", concept_code: "8867-4", display: "Heart rate", unit: "/min", flags: [] }},
          {{ proposal_id: "p2", concept_code: null, display: "zzz", unit: null, flags: ["unknown_code"] }} ] }} }};
        ["rv-intro", "rv-msg", "rv-list", "session-msg", "rv-p1-first", "rv-p1-u", "rv-p1-d", "rv-p1-v", "rv-p1-t",
         "rv-p2-first", "rv-p2-t"].forEach(function (i) {{ mk(i); }});
        mk("rv-form", "form"); mk("rv-submit", "button");
        document.querySelector = function () {{ return null; }};  // no decision radios in this stub
        rvCurrent = "c1";
        RESP.push([422, {json.dumps(body)}]);
        await submitReview({{ preventDefault: function () {{}} }});
        var n = $("rv-msg").children[0];
        var items = n.querySelectorAll("li").map(function (li) {{
          var a = li.querySelector("a"), target = null;
          if (a) {{ document.activeElement = document.body; a.click(); target = document.activeElement.id; }}
          return {{ text: li.textContent, target: target }};
        }});
        document.activeElement = document.body;
        return {{ title: n.querySelector(".notice-title").textContent, role: n.getAttribute("role"),
                 tabindex: n.getAttribute("tabindex"), items: items, formHidden: $("rv-form").hidden, posts: CALLS.length }};
        """,
    )


def _focused_notice(body: dict) -> dict:
    return _run_page(
        _BASE + _API + _REVIEW + _REFUSAL,
        f"""
        S.checkins = {{ c1: {{ status: "pending_review", result: null, proposals: [] }} }};
        ["rv-intro", "rv-msg", "rv-list", "session-msg"].forEach(function (i) {{ mk(i); }});
        mk("rv-form", "form"); mk("rv-submit", "button");
        rvCurrent = "c1";
        RESP.push([422, {__import__("json").dumps(body)}]);
        await submitReview({{ preventDefault: function () {{}} }});
        return document.activeElement === $("rv-msg").children[0];
        """,
    )


def test_k4_missing_decision_lists_each_value_and_links_its_first_choice():
    """QG P3 K4: A&D §4.2 / T4.3: 422 ``missing_decision`` keeps the form, announces "Nothing was saved"
    as a focused alert and links each listed value to its first decision (unknown ids: the list)."""
    got = _refusal({"error": "missing_decision", "missing": ["p1", "ghost"]})
    assert got["title"] == "Nothing was saved" and got["role"] == "alert" and got["tabindex"] == "-1"
    assert got["formHidden"] is False and got["posts"] == 1
    assert [i["target"] for i in got["items"]] == ["rv-p1-first", "rv-list"]
    assert got["items"][0]["text"] == "Heart rate: choose a decision."
    assert got["items"][1]["text"].startswith("A value: ")
    empty = _refusal({"error": "missing_decision", "missing": []})
    assert [i["text"] for i in empty["items"]] == ["Choose one decision for each value."]


def test_k4_unresolved_flags_names_each_flag_and_links_the_card():
    got = _refusal({"error": "unresolved_flags", "proposals": [{"proposal_id": "p2", "flags": ["unknown_code", "weird"]}]})
    assert got["title"] == "Nothing was saved" and got["role"] == "alert"
    assert got["items"] == [{"text": "“zzz”: still flagged (Unknown code, weird). Correct it, discard it or save it as unmapped.",
                             "target": "rv-p2-t"}]


def test_k4_invalid_correction_links_each_reason_to_its_field():
    reasons = ["unit_not_allowed", "date_outside_window", "not_a_whole_number", "unknown_concept", "bogus"]
    got = _refusal({"error": "invalid_correction", "proposals": [{"proposal_id": "p1", "reasons": reasons}]})
    assert [i["target"] for i in got["items"]] == ["rv-p1-u", "rv-p1-d", "rv-p1-v", "rv-p1-t", "rv-p1-t"]
    assert got["items"][0]["text"] == "Heart rate: the unit is not one this measure allows."
    assert got["items"][1]["text"] == "Heart rate: the date must be within the last 28 days."
    assert got["items"][4]["text"] == "Heart rate: this correction cannot be saved."
    empty = _refusal({"error": "invalid_correction", "proposals": []})
    assert [i["text"] for i in empty["items"]] == ["Check each value and try again."] and empty["formHidden"] is False


@pytest.mark.parametrize("err", ["missing_decision", "unresolved_flags", "invalid_correction"])
def test_k4_refusal_notice_takes_focus(err):
    assert _focused_notice({"error": err}) is True


_PCARD = ["FLAG_NAMES", "FLAG_WHY", "ACTIONS", "SOURCE_KINDS", "pTitle", "shiftDate", "unitChoices", "updateCountRv", "proposalCard"]
_FLAGGED = (
    '{ proposal_id: "p1", concept_code: "8867-4", display: "Heart rate", value: 62, unit: "/min", date: "2026-09-27",'
    ' flags: ["unit_assumed"], blocking: true, confidence: "medium", method: "rules-v1", source_kind: "text" }'
)
_AMBIG = (
    '{ proposal_id: "p2", concept_code: "93832-4", display: "Sleep", value: 7, unit: "h", date: "2026-09-28",'
    ' flags: ["ambiguous_date"], blocking: true, confidence: "medium", method: "rules-v1", source_kind: "text" }'
)
# decisionsRv asks for the checked radio by name; the stub DOM has no attribute selectors.
_CHECKED = """document.querySelector = function (sel) { var m = /name="([^"]+)"/.exec(sel);
  return ALL.find(function (e) { return e.name === m[1] && e.checked && connected(e); }) || null; };"""


def test_k5_flagged_proposal_card_cannot_be_confirmed():
    """QG P3 K5: A&D §4.1: a blocking flag is never confirmed. Confirm is disabled, Correct is the first
    decision, and the card says why (aria-describedby on the fieldset)."""
    got = _run_page(
        _BASE + _REVIEW + _PCARD,
        f"""
        var units = {{ "8867-4": ["/min"], "93832-4": ["h", "min"] }};
        var list = mk("rv-list");
        function look(p) {{
          var art = proposalCard(p, units); list.append(art);
          var radios = art.querySelectorAll("input").filter(function (i) {{ return i.type === "radio"; }});
          var fs = art.querySelector("fieldset");
          return {{ cls: art.className, ids: radios.map(function (r) {{ return [r.value, r.id, r.disabled === true]; }}),
                   described: fs.getAttribute("aria-describedby"), why: (art.querySelector("p.notice") || {{ textContent: null }}).textContent }};
        }}
        var p1 = {_FLAGGED};
        var free = Object.assign({{}}, p1, {{ proposal_id: "p3", flags: [], blocking: false, confidence: "high" }});
        return [look(p1), look(free)];
        """,
    )
    blocked, free = got
    assert "proposal--blocked" in blocked["cls"]
    assert blocked["ids"][0] == ["confirm", "", True]
    assert blocked["ids"][1] == ["correct", "rv-p1-first", False]
    assert blocked["described"] == "rv-p1-why"
    assert "The unit was not written, so it was assumed." in blocked["why"] and "It cannot be confirmed" in blocked["why"]
    assert free["ids"][0] == ["confirm", "rv-p3-first", False] and free["described"] is None and free["why"] is None


def test_k5_correct_decision_reads_value_unit_and_date_fields():
    """QG P3 K5 / R1 (G29): an unedited Correct on a flagged card states the shown unit (unit_assumed) or
    date (ambiguous_date); edited fields are read from their own inputs."""
    got = _run_page(
        _BASE + _REVIEW + _PCARD,
        f"""
        {_CHECKED}
        var units = {{ "8867-4": ["/min"], "93832-4": ["h", "min"] }};
        var p1 = {_FLAGGED}, p2 = {_AMBIG};
        S.checkins = {{ c1: {{ status: "pending_review", result: null, proposals: [p1, p2] }} }};
        rvCurrent = "c1";
        var list = mk("rv-list");
        [p1, p2].forEach(function (p) {{ list.append(proposalCard(p, units)); }});
        function pick(base) {{ ALL.find(function (e) {{ return e.name === base + "-d" && e.value === "correct"; }}).checked = true; }}
        pick("rv-p1"); pick("rv-p2");
        $("rv-p1-u").value = "/min";  // a select's value is its selected option in a browser
        $("rv-p2-u").value = "h";
        var unedited = decisionsRv().decisions;
        $("rv-p1-v").value = "64"; $("rv-p2-d").value = "2026-09-29";
        return [unedited, decisionsRv().decisions];
        """,
    )
    assert got[0] == [
        {"proposal_id": "p1", "action": "correct", "value": 62, "unit": "/min"},
        {"proposal_id": "p2", "action": "correct", "value": 7, "date": "2026-09-28"},
    ]
    assert got[1] == [
        {"proposal_id": "p1", "action": "correct", "value": 64, "unit": "/min"},
        {"proposal_id": "p2", "action": "correct", "value": 7, "date": "2026-09-29"},
    ]


def test_b2_overlapping_review_loads_render_each_card_once():
    """QG P3 B2: two showReview calls for the same check-in while /api/units is pending (leave and come
    back on a slow network) must draw each proposal card once, not twice with duplicate ids."""
    got = _run_page(
        _BASE + _API + _REVIEW + _PCARD,
        f"""
        {_CHECKED}
        S.checkins = {{ c1: {{ status: "pending_review", result: null, proposals: [{_FLAGGED}, {_AMBIG}] }} }};
        ["rv-intro", "rv-msg", "rv-list", "rv-status", "session-msg"].forEach(function (i) {{ mk(i); }});
        mk("rv-form", "form");
        RESP.push([200, {{ units: {{ "8867-4": ["/min"], "93832-4": ["h", "min"] }} }}]);
        var a = showReview("c1"), b = showReview("c1");
        await Promise.all([a, b]);
        var ids = ALL.filter(function (e) {{ return e.id && connected(e); }}).map(function (e) {{ return e.id; }});
        return {{ cards: $("rv-list").children.length, dup: ids.filter(function (x, i) {{ return ids.indexOf(x) !== i; }}),
                 gets: CALLS.length }};
        """,
    )
    assert got == {"cards": 2, "dup": [], "gets": 1}


def test_k3_member_facing_api_labels_never_say_demo(client):
    """QG P6.1 C6 (AM-2 D2): strings the member app renders from the API (the import pickers and the
    passport card source) use production wording too, not only the page's own copy."""
    fx = client.get("/api/fixtures").json()
    assert fx and not [f["label"] for f in fx if "demo" in f["label"].lower()]
    member = client.get("/api/members").json()[0]["member_id"]
    jid = client.post("/api/journals", json={"member_id": member}).json()["journal_id"]
    ci = client.post("/api/checkins", json={"journal_id": jid, "fixture_id": "demo-scale-photo"}).json()
    decisions = [{"proposal_id": p["proposal_id"], "action": "discard" if p["blocking"] else "confirm"} for p in ci["proposals"]]
    assert client.post(f"/api/checkins/{ci['checkin_id']}/review", json={"decisions": decisions}).status_code == 200
    pp = client.get(f"/api/journals/{jid}/passport").json()
    labels = {c["source"] for c in pp["cards"]} | {c["thread"]["steps"][0]["label"] for c in pp["cards"]}
    assert "Imported photo" in labels
    assert not [s for s in labels if "demo" in s.lower()], labels


def test_k2_persona_checkin_links_say_already_saved():
    got = _run_page(
        _BASE + _IDENTITY + ["persist", "updateNav", "adoptJournal", "alreadySavedNotice", "savedNotice", "rvSeq", "rvCurrent", "showReview"],
        """
        mk("nav-review", "a"); mk("rv-intro", "p"); mk("rv-msg"); mk("rv-form", "form"); mk("rv-list");
        var sessionStorage = { setItem: function () {} };
        adoptJournal({ journal_id: "j1", today: "2026-09-29", display_name: "Rowan Ellis", saved_checkins: ["j1-c1", "j1-c2"] });
        await showReview("j1-c2");
        return [$("rv-msg").textContent, $("rv-form").hidden, Object.keys(S.checkins)];
        """,
    )
    assert "Already saved" in got[0] and "not available" not in got[0] and got[1] is True and got[2] == ["j1-c1", "j1-c2"]


def test_k4_only_the_newest_passport_load_draws():
    """QG P6.1 U1: two overlapping #passport loads (a slow first, a fast second) draw once, with the
    newest data, so a re-render never pulls the cards from under a keyboard user's focus."""
    got = _run_page(
        _BASE + _API + ["journalPending", "ensureJournal", "ppSeq", "showPassport"],
        """
        mk("pp-msg"); mk("pp-body");
        var RENDERS = [];
        globalThis.renderPassport = function (pp) { RENDERS.push(pp.as_of); };
        var gates = [];
        fetch = function (path) {
          return new Promise(function (resolve) {
            gates.push(function (asOf) {
              resolve({ status: 200, ok: true, json: async function () {
                return path.indexOf("/passport") >= 0 ? { as_of: asOf, cards: [] } : { verticals: [] }; } });
            });
          });
        };
        var first = showPassport(""), second = showPassport("");
        await new Promise(function (r) { setTimeout(r, 10); });
        gates[2]("new"); gates[3]("new");      // the second load answers first
        await second;
        gates[0]("old"); gates[1]("old");      // then the first, stale load
        await first;
        return RENDERS;
        """,
    )
    assert got == ["new"]


def test_t9_fresh_journal_during_the_first_load_is_fresh():
    """QG P6.1 T9 (regression for O1, b2f3ace): "Start a fresh journal" pressed while the persona
    journal is still being created ends on a fresh, empty journal, never the persona's."""
    got = _run_page(
        _BASE + _API + _IDENTITY + ["persist", "updateNav", "adoptJournal", "journalPending", "createJournal", "ensureJournal",
                        "resetCheckin", "startAgain", "sessionEnded"],
        """
        mk("nav-review", "a"); mk("session-msg");
        var sessionStorage = { setItem: function () {}, removeItem: function () {} };
        globalThis.resetCheckin = function () {}; globalThis.route = function () {};
        S.journal = null;
        var release;
        var held = new Promise(function (r) { release = r; });
        fetch = async function (path, init) {
          CALLS.push([init.method, path, init.body === undefined ? null : JSON.parse(init.body)]);
          if (path === "/api/personas") await held;  // the first load is slow
          var r = path === "/api/personas" ? [200, [{ persona_id: "persona-v1", display_name: "Rowan Ellis" }]]
            : path === "/api/members" ? [200, [{ member_id: "syn-001" }]]
            : init.body && JSON.parse(init.body).persona ? [201, { journal_id: "jp", today: "2026-09-29", display_name: "Rowan Ellis", saved_checkins: [] }]
            : [201, { journal_id: "jf", today: "2026-09-29" }];
          return { status: r[0], ok: true, json: async function () { return r[1]; } };
        };
        var first = ensureJournal();
        var again = startAgain(true);       // clicked while the persona journal is pending
        release();
        await first; await again;
        return [S.journal, S.displayName, CALLS[CALLS.length - 1]];
        """,
    )
    assert got[0] == "jf" and got[1] is None and got[2] == ["POST", "/api/journals", {"member_id": "syn-001"}]


# --- HAC-38 P6.2 part A: visual spec rev 3 on the member app (HAC-68) ------------------------------


def test_rev3_each_surface_sets_its_palette_on_body(html, admin):
    for page, surface in ((html, "member"), (admin, "admin")):
        bodies = [n for n in _tree(page).iter() if n.tag == "body"]
        assert len(bodies) == 1 and bodies[0].attrs.get("data-surface") == surface, surface
    css = _style(html)
    assert '[data-surface="member"]{' in css and '[data-surface="admin"]{' in css
    assert "[data-shell]" not in css and "SPEC ·" not in css  # the mockup-only rules are dropped


def test_rev3_member_shell_header_persona_and_footer(html):
    root = _tree(html)
    head = next(n for n in root.iter() if n.tag == "header")
    assert "m-head" in head.attrs.get("class", "")
    assert any("orb" in (n.attrs.get("class") or "") for n in head.iter())
    text = " ".join(head.text().split())
    assert "Clinical Human Clone" in text and "HEALTH CLONE PASSPORT" in text
    persona = _by_id(root, "persona")
    assert _is_inside(persona, head) and "hidden" in persona.attrs  # filled from the journal, never a placeholder
    foot = next(n for n in root.iter() if n.tag == "footer")
    assert "m-foot" in foot.attrs.get("class", "")
    assert [n.tag for n in foot.iter() if n.tag in ("p", "a", "button")] == ["p", "a", "a"]  # the LOINC notice only


def test_rev3_member_render_links_no_console_dashboard_or_real_input(html):
    root = _tree(html)
    hrefs = [n.attrs.get("href") or "" for n in root.iter() if n.tag == "a"]
    assert not [h for h in hrefs if "admin" in h or "dashboard" in h or h.startswith("/") and h != "/"], hrefs
    shipped = re.sub(r"<!--.*?-->", "", html, flags=re.S)  # markup and script, not the source comments
    assert "/admin" not in shipped and "/dashboard" not in shipped
    ids = {n.attrs.get("id") for n in root.iter()}
    assert not ids & {"ri-btn", "ri-panel", "screen-lab", "screen-research", "screen-inventory", "screen-pipeline",
                      "screen-playground", "screen-input"}
    assert not [n for n in root.iter() if n.tag in ("a", "button") and "Real input" in n.text()]


def test_rev3_nav_marks_the_page_and_checkin_is_an_alias_of_today(html):
    js = _script(html)
    rt = _section(js, "function route()", "\n}\n")
    assert '"page"' in rt and ".mnav a" in rt
    got = _run_page(
        ["$", "SCREENS", "ALIASES", "parseHash"],
        """
        var out = [];
        ["#checkin", "#today", "#checkin/x", "#timeline", "#nope", "", "#review/c1"].forEach(function (h) {
          location.hash = h; var r = parseHash(); out.push([r.base, r.rest]); });
        return out;
        """,
    )
    assert got == [["today", ""], ["today", ""], ["today", "x"], ["timeline", ""], ["today", ""], ["today", ""], ["review", "c1"]]


def test_rev3_member_copy_is_neutral(html):
    js = _script(html)
    for s in ("Add a file", "Add an image", "Only the bundled files can be used", "Write a sentence or add a file",
              "Your clone cannot help with this.", "We had a problem on our side (error ",
              "We could not reach the server.", "This session has ended", "What your clone knows", "View timeline"):
        assert s in html, s
    for s in ("Import a device file", "Import a photo", "This app cannot help", "The service had a problem on its side",
              "What the clone knows", "Continue to the learning lab"):
        assert s not in html, s
    assert '"Mode"' not in js  # rev 3 §3.4: no Mode row on the passport
    low = " ".join(_string_literals(js)).lower()
    assert not re.search(r"\bdemo\b", low.replace("not_a_demo_fixture", "")), low


def test_rev3_timeline_screen_markup_and_c5_note(html):
    root = _tree(html)
    sec = _by_id(root, "screen-timeline")
    kids = [c for c in sec.children if isinstance(c, _Node)]
    assert [k.tag for k in kids[:4]] == ["p", "h1", "div", "p"]
    assert kids[1].attrs.get("id") == "h-timeline" and kids[1].text() == "How your clone changed"
    assert kids[2].attrs.get("id") == "tl-msg"
    note = kids[3]
    assert note.attrs.get("id") == "tl-note" and "muted" in note.attrs.get("class", "")
    # C5 (P6.1): an entry shows what its save changed on that save's day; no day-only entries are drawn
    assert " ".join(note.text().split()) == "Each entry shows what one saved check-in added and changed, on the day it was saved."
    more = _by_id(root, "tl-more")
    assert more.tag == "button" and more.text() == "Show earlier days" and "btn--secondary" in more.attrs.get("class", "")


def test_rev3_today_aside_and_two_columns(html):
    root = _tree(html)
    grid = _by_id(root, "ci-grid")
    aside = _by_id(root, "clone-aside")
    assert aside.tag == "aside" and _is_inside(aside, grid) and "hidden" in aside.attrs  # fresh journal: no aside
    assert aside.attrs.get("aria-labelledby") == "h-clone" and _by_id(root, "h-clone").text() == "Your clone"
    form = _by_id(root, "ci-form")
    assert "panel--glow" in form.attrs.get("class", "")
    assert "panel--glow" in _by_id(root, "ns-panel").attrs.get("class", "")
    assert _by_id(root, "fresh-btn").text() == "Start a fresh journal"


_ENTRY = """{ index: 2, checkin_id: "c2", as_of: "2026-09-29T12:00:00Z",
  appends: [{ display: "Sleep duration", value: 7.5, unit: "h" }, { display: "Steps", value: 9360, unit: "{steps}" }],
  passport_changes: [
    { title: "Heart rate", change: "became_ready" }, { title: "Sleep duration (hours)", change: "value_changed" },
    { title: "Body weight", change: "now_observed" }, { title: "Pulse", change: "withheld" }, { title: "X", change: "bogus" }],
  next_step: { before: { text: "old" }, after: { text: "Would you like to walk after lunch?" }, changed: true } }"""
_QUIET = """{ index: 3, checkin_id: "c3", as_of: "2026-09-29T12:00:00Z", appends: [], passport_changes: [],
  next_step: { before: { text: "same" }, after: { text: "same" }, changed: false } }"""


def test_rev3_timeline_entry_maps_each_api_field_once():
    got = _run_page(
        _BASE + _TL,
        f"""
        var e = {_ENTRY}, q = {_QUIET};
        var first = Object.assign({{}}, e, {{ index: 1, next_step: {{ before: null, after: {{ text: "First." }}, changed: true }} }});
        return {{ title: tlTitle(e), firstTitle: tlTitle(first), quietTitle: tlTitle(q),
          chips: tlChips(e).children.map(function (c) {{ return [c.className, c.textContent]; }}),
          firstChip: tlChips(first).children.map(function (c) {{ return c.textContent; }}).pop(),
          quietChips: tlChips(q), sentences: tlSentences(e), quiet: tlSentences(q), firstSentences: tlSentences(first) }};
        """,
    )
    assert got["title"] == "Check-in saved · 2 observations"
    assert got["firstTitle"] == "First check-in saved · 2 observations"
    assert got["quietTitle"] == "Check-in saved"
    assert got["chips"] == [
        ["tag tag--ready", "✓ Card ready: Heart rate"],
        ["tag", "↻ Updated: Sleep duration (hours)"],
        ["tag tag--observed", "● Now observed: Body weight"],
        ["tag tag--withheld", "○ Withheld: Pulse"],
        ["tag tag--live", "→ New next step"],
    ]  # an unknown change kind gets no chip
    assert got["firstChip"] == "→ First next step"
    assert got["quietChips"] is None  # no change: no chip list, never a "0 cards" chip
    assert got["sentences"][0] == "Added: Sleep duration 7.5 h, Steps 9360 steps."
    assert got["sentences"][-1] == "Next step changed to “Would you like to walk after lunch?”"
    assert got["quiet"] == ["No passport card changed.", "Next step unchanged."]
    assert got["firstSentences"][-1] == "First next step: “First.”"  # QG P6.2 K8: no step before this save
    banned = re.compile(r"\b(high|low|normal|abnormal|better|worse|improv\w*|up|down|increas\w*|decreas\w*)\b", re.I)
    for s in got["sentences"]:
        assert not banned.search(s), s  # a value change states that it changed, never its direction


def _clone_updated(entry: str, written: int = 2, records: int = 3) -> dict:
    return _run_page(
        _BASE + _TL + ["savedLine", "cloneUpdated"],
        f"""
        var r = {{ written: Array({written}).fill("e"), records: Array({records}).fill("r") }};
        var box = cloneUpdated(r, {entry});
        var ul = box.querySelector("ul.delta");
        return {{ role: box.getAttribute("role"), tabindex: box.getAttribute("tabindex"), labelled: box.getAttribute("aria-labelledby"),
          h2: box.querySelector("h2").id + "|" + box.querySelector("h2").textContent, line: box.querySelector("p.small").textContent,
          ring: box.querySelector("span.cu-ring").getAttribute("aria-hidden"),
          rows: ul ? ul.children.map(function (li) {{ return [li.children[0].textContent, li.children[1].textContent]; }}) : null,
          label: ul ? ul.getAttribute("aria-label") : null,
          links: box.querySelectorAll("a").map(function (a) {{ return [a.href, a.textContent, a.className]; }}) }};
        """,
    )


def test_rev3_clone_updated_panel_is_built_from_the_entry():
    got = _clone_updated(_ENTRY)
    assert (got["role"], got["tabindex"], got["labelled"]) == ("status", "-1", "cu-t")
    assert got["h2"] == "cu-t|Your clone updated" and got["ring"] == "true"
    assert got["line"] == "Saved 2 values · 1 saved as unmapped · discarded values were not stored"
    assert got["label"] == "What changed"
    assert got["rows"] == [
        ["Observed", "2 new observations added: Sleep duration 7.5 h, Steps 9360 steps"],
        ["Card ready", "Heart rate now has enough data and is ready on your passport."],
        ["Updated", "Sleep duration (hours) now shows your latest value."],
        ["Now observed", "Body weight now shows a value you saved, not a simulated one."],
        ["Withheld", "Pulse is withheld on your passport for now."],
        ["Next step", "New suggestion: “Would you like to walk after lunch?”"],
    ]
    assert got["links"] == [["#passport", "Open your passport", "btn btn--primary"],
                            ["#next", "See your next step", "btn btn--secondary"],
                            ["#timeline", "View timeline", "btn btn--secondary"]]


_SHUFFLED = """{ index: 4, checkin_id: "c4", as_of: "2026-09-29T12:00:00Z", appends: [],
  passport_changes: [{ title: "Pulse", change: "withheld" }, { title: "Body weight", change: "now_observed" },
    { title: "Heart rate", change: "became_ready" }, { title: "Sleep duration (hours)", change: "value_changed" }],
  next_step: { before: { text: "a" }, after: { text: "a" }, changed: false } }"""


def test_rev3_clone_updated_rows_follow_the_kind_order_not_the_api_order():
    """QG P6.2 K9: the API lists the changes in any order; the delta rows always run Card ready,
    Updated, Now observed, Withheld (rev 3 §3.3). The timeline chips keep the API's order."""
    got = _clone_updated(_SHUFFLED, written=1, records=1)
    assert [r[0] for r in got["rows"]] == ["Card ready", "Updated", "Now observed", "Withheld"]
    chips = _run_page(_BASE + _TL, f"return tlChips({_SHUFFLED}).children.map(function (c) {{ return c.textContent; }});")
    assert chips == ["○ Withheld: Pulse", "● Now observed: Body weight", "✓ Card ready: Heart rate",
                     "↻ Updated: Sleep duration (hours)"]


def test_rev3_clone_updated_omits_empty_kinds_and_never_says_zero():
    got = _clone_updated(_QUIET, written=1, records=1)
    assert got["rows"] is None and got["label"] is None
    assert got["line"] == "Saved 1 value · discarded values were not stored"
    assert not re.search(r"\b0 ", got["line"])


_SAVE = _BASE + _API + _REVIEW + _TL + ["savedLine", "cloneUpdated"]


def _save_then(timeline: str) -> dict:
    return _run_page(
        _SAVE,
        f"""
        S.checkins = {{ c2: {{ proposals: [], status: "pending_review", result: null }} }};
        ["rv-intro", "rv-msg", "rv-list", "session-msg"].forEach(function (i) {{ mk(i); }});
        mk("rv-form", "form"); mk("rv-submit", "button");
        var sessionStorage = {{ setItem: function () {{}} }};
        rvCurrent = "c2";
        RESP.push([200, {{ status: "saved", written: ["e1"], records: ["r1"] }}], {timeline});
        await submitReview({{ preventDefault: function () {{}} }});
        var n = $("rv-msg").children[0];
        return {{ cls: n.className, role: n.getAttribute("role"), focused: document.activeElement === n, text: n.textContent,
          calls: CALLS.map(function (c) {{ return c[0] + " " + c[1]; }}), formHidden: $("rv-form").hidden }};
        """,
    )


def test_rev3_save_shows_clone_updated_from_this_checkins_entry():
    # QG P6.2 K3: c2's entry comes first, so "the last entry" is not this check-in's
    got = _save_then(f'[200, {{ entries: [{_ENTRY}, {_QUIET}] }}]')
    assert got["cls"] == "clone-updated" and got["role"] == "status" and got["focused"] and got["formHidden"]
    assert "Your clone updated" in got["text"] and "Heart rate now has enough data" in got["text"]  # c2's entry, not c3's
    assert got["calls"] == ["POST /api/checkins/c2/review", "GET /api/journals/j1/timeline"]


# QG P6.2 K3: the last case has entries, but none for this check-in (c3's only)
@pytest.mark.parametrize("timeline", ['[503, null]', '"network"', '[200, { entries: [] }]', f'[200, {{ entries: [{_QUIET}] }}]'])
def test_rev3_save_falls_back_to_the_saved_notice_without_an_error(timeline):
    got = _save_then(timeline)
    assert got["cls"] == "notice notice--ok" and got["role"] == "status" and got["focused"]
    assert "Saved 1 value to your clone" in got["text"]
    assert "Something went wrong" not in got["text"] and "error" not in got["text"]


@pytest.mark.parametrize("held", ["POST", "GET"])
def test_rev3_save_never_draws_on_a_review_the_route_moved_to(held):
    """QG P6.2 K10: the person opens #review/c3 while c2's save (POST) or its timeline GET is in flight.
    c2's save is recorded, but c3's screen keeps its own form and message and keeps focus, and c3's
    Save is not blocked by c2's call."""
    got = _run_page(
        _SAVE,
        f"""
        S.checkins = {{ c2: {{ proposals: [], status: "pending_review", result: null }},
                       c3: {{ proposals: [], status: "pending_review", result: null }} }};
        ["rv-intro", "rv-msg", "rv-list", "session-msg"].forEach(function (i) {{ mk(i); }});
        mk("rv-form", "form"); mk("rv-submit", "button");
        var sessionStorage = {{ setItem: function () {{}} }};
        var release, gate = new Promise(function (r) {{ release = r; }});
        fetch = async function (path, init) {{
          CALLS.push([init.method, path]);
          if (init.method === "{held}") await gate;
          var body = init.method === "POST" ? {{ status: "saved", written: ["e1"], records: ["r1"] }} : {{ entries: [{_ENTRY}] }};
          return {{ status: 200, ok: true, json: async function () {{ return body; }} }};
        }};
        rvCurrent = "c2";
        var save = submitReview({{ preventDefault: function () {{}} }});
        await new Promise(function (r) {{ setTimeout(r, 10); }});
        rvCurrent = "c3";                          /* what showReview("c3") leaves: its own form and message */
        var mine = el("p", null, "c3 form"); clear($("rv-msg")).append(mine); $("rv-form").hidden = false; mine.focus();
        var busyWhileHeld = rvBusy;
        release(); await save;
        return {{ msg: $("rv-msg").textContent, formHidden: $("rv-form").hidden, focus: document.activeElement === mine,
          saved: S.checkins.c2.status, busy: rvBusy, busyWhileHeld: busyWhileHeld,
          disabled: $("rv-submit").getAttribute("aria-disabled"), calls: CALLS.map(function (c) {{ return c[0]; }}) }};
        """,
    )
    assert got["msg"] == "c3 form" and got["formHidden"] is False and got["focus"]  # c3's screen is untouched
    assert got["saved"] == "saved"  # c2's save happened and is recorded
    assert got["busy"] is False and got["disabled"] is None
    if held == "GET":
        assert got["busyWhileHeld"] is False  # the save settled: c3's Save is not silently ignored during the GET
        assert got["calls"] == ["POST", "GET"]
    else:
        assert got["calls"] == ["POST"]  # the route moved on: no timeline GET for a panel nobody sees


_TIMELINE = _BASE + _API + _TL + ["journalPending", "ensureJournal", "sessionEnded", "TL_PAGE", "showTimeline", "tlMore", "tlEntry"]
_TL_DOM = """
["tl-msg", "tl-body", "tl-days", "tl-omitted", "tl-more-row", "session-msg"].forEach(function (i) { mk(i); });
S.today = "2026-09-29";
function day(n) { var d = new Date(Date.UTC(2026, 8, 29 - n, 12)); return d.toISOString().slice(0, 10); }
function entry(i, d) { return { index: i, checkin_id: "c" + i, as_of: d + "T12:00:00Z", appends: [{ display: "Steps", value: 9000 + i, unit: "{steps}" }],
  passport_changes: [], next_step: { before: { text: "a" }, after: { text: "a" }, changed: false } }; }
"""


def test_rev3_timeline_groups_days_newest_first_and_pages_by_7():
    got = _run_page(
        _TIMELINE,
        _TL_DOM + """
        var es = []; for (var i = 1; i <= 10; i++) es.push(entry(i, day(i === 10 ? 0 : 10 - i)));  // 10 saves on 10 days, save order
        es.splice(9, 0, entry(99, day(0)));  // two saves today
        RESP.push([200, { entries: es, omitted: 0 }]);
        await showTimeline();
        function heads() { return $("tl-days").querySelectorAll("h2").map(function (h) { return h.textContent; }); }
        var first = { heads: heads(), moreHidden: $("tl-more-row").hidden, bodyHidden: $("tl-body").hidden,
          items: $("tl-days").querySelectorAll("details").map(function (d) { return [d.open === true, d.parentNode.className]; }).slice(0, 3),
          today: $("tl-days").querySelectorAll("section")[0].querySelectorAll("li").filter(function (li) { return li.className !== "tag"; }).length };
        tlMore(true);
        return { first: first, heads: heads(), moreHidden: $("tl-more-row").hidden, focused: document.activeElement.textContent };
        """,
    )
    f = got["first"]
    assert f["heads"] == ["Today · 29 Sep", "Yesterday · 28 Sep", "27 Sep", "26 Sep", "25 Sep", "24 Sep", "23 Sep"]
    assert f["moreHidden"] is False and f["bodyHidden"] is False
    assert f["items"] == [[True, "is-new"], [False, ""], [False, ""]]  # only the newest is open, with the teal node
    assert got["heads"][7:] == ["22 Sep", "21 Sep", "20 Sep"] and got["moreHidden"] is True
    assert got["focused"] == "22 Sep"  # "Show earlier days" moves focus to the first day it added


def test_rev3_timeline_groups_a_backdated_save_under_its_own_day():
    """QG P6.2 K1: the API lists saves in save order, but a backdated save ("yesterday I slept…") made
    after today's carries an older day. Each day has one header, days run newest first, a day lists its
    saves newest first, and the newest save (the last the API lists) is the open, teal entry."""
    got = _run_page(
        _TIMELINE,
        _TL_DOM + """
        var es = [entry(1, day(2)), entry(2, day(0)), entry(3, day(1)), entry(4, day(0)), entry(5, day(3))];
        RESP.push([200, { entries: es, omitted: 0 }]);
        await showTimeline();
        return $("tl-days").querySelectorAll("section").map(function (sec) {
          return [sec.querySelector("h2").textContent].concat(sec.querySelectorAll("details").map(function (d) {
            return [d.querySelector("span.tl-time").textContent.trim().replace(" ›", ""), d.open === true, d.parentNode.className]; })); });
        """,
    )
    assert got == [
        ["Today · 29 Sep", ["save 4", False, ""], ["save 2", False, ""]],
        ["Yesterday · 28 Sep", ["save 3", False, ""]],
        ["27 Sep", ["save 1", False, ""]],
        ["26 Sep", ["save 5", True, "is-new"]],  # the newest save is backdated: it stays on its own day
    ]


def test_rev3_clone_aside_last_updated_is_the_latest_day_not_the_last_save():
    """QG P6.2 K1: "Last updated" names the latest day the clone holds; a backdated last save does not
    move it back. "Latest update" is still the newest save."""
    got = _run_page(
        _CLONE,
        _CLONE_DOM + f"""
        var today = Object.assign({{}}, {_ENTRY}, {{ index: 1 }});
        var back = Object.assign({{}}, {_QUIET}, {{ index: 2, as_of: "2026-09-26T12:00:00Z" }});
        RESP.push([200, {{ entries: [today, back], omitted: 0 }}], [200, {{ cards: [] }}]);
        await loadClone();
        return [$("clone-built").textContent, $("clone-latest").textContent];
        """,
    )
    assert got[0] == "Built from 2 days of your saved check-ins. Last updated 29 Sep 2026."
    assert got[1] == "Check-in saved"  # the newest save (the backdated one) is the latest update


def test_rev3_timeline_says_how_many_older_check_ins_are_not_shown():
    """QG P6.2 K7: the API keeps the newest 60 saves; ``omitted`` older ones are named under the feed."""
    got = _run_page(
        _TIMELINE,
        _TL_DOM + """
        var out = [];
        for (var om of [0, 1, 3]) {
          RESP.push([200, { entries: [entry(1, day(0))], omitted: om }]);
          await showTimeline();
          out.push([$("tl-omitted").hidden, $("tl-omitted").textContent]);
        }
        return out;
        """,
    )
    assert got == [[True, ""], [False, "1 older check-in is not shown."], [False, "3 older check-ins are not shown."]]


def test_rev3_only_the_newest_timeline_load_draws():
    """QG P6.2 K11: two overlapping #timeline loads; the slow first answer never replaces the newer feed."""
    got = _run_page(
        _TIMELINE,
        _TL_DOM + _GATED + """
        var first = showTimeline(), second = showTimeline();
        await new Promise(function (r) { setTimeout(r, 10); });
        gates[1]({ entries: [entry(2, day(0))], omitted: 0 }); await second;   // the newer load answers first
        gates[0]({ entries: [entry(1, day(5))], omitted: 7 }); await first;    // then the stale one
        return [$("tl-days").querySelectorAll("h2").map(function (h) { return h.textContent; }),
                $("tl-days").querySelectorAll("span.tl-time").map(function (t) { return t.textContent; }), $("tl-omitted").hidden];
        """,
    )
    assert got == [["Today · 29 Sep"], ["save 2 ›"], True]


def test_rev3_timeline_empty_failed_and_ended_states():
    got = _run_page(
        _TIMELINE,
        _TL_DOM + """
        var out = {};
        globalThis.startAgain = function () {};
        RESP.push([200, { entries: [] }]); await showTimeline();
        var n = $("tl-msg").children[0];
        out.empty = [n.className, n.querySelector(".notice-title").textContent, n.textContent,
                     n.querySelectorAll("a").map(function (a) { return a.href + "|" + a.textContent; }), $("tl-body").hidden];
        RESP.push([502, null]); await showTimeline();
        n = $("tl-msg").children[0];
        out.failed = [n.getAttribute("role"), n.textContent, $("tl-body").hidden];
        RESP.push([404, { error: "unknown_journal" }]); await showTimeline();
        out.ended = [$("session-msg").textContent, $("tl-body").hidden];
        return out;
        """,
    )
    assert got["empty"][0] == "notice notice--info" and got["empty"][1] == "No updates yet"
    assert "Your first saved check-in starts the timeline." in got["empty"][2]
    assert got["empty"][3] == ["#today|Check in"] and got["empty"][4] is True
    assert got["failed"][0] == "alert" and "We had a problem on our side (error 502)" in got["failed"][1] and got["failed"][2]
    assert "This session has ended" in got["ended"][0] and got["ended"][1]


_CLONE = _BASE + _API + _IDENTITY + _TL + ["setAside", "cloneSeq", "loadClone", "renderClone", "sessionEnded"]
_CLONE_DOM = """
["ci-grid", "clone-built", "clone-stats", "clone-latest", "session-msg"].forEach(function (i) { mk(i); });
mk("clone-aside", "aside").hidden = true; mk("ci-form", "form");
function tiles() { return $("clone-stats").children.map(function (li) { return li.textContent; }); }
"""


def test_rev3_clone_aside_stats_come_from_the_api_only():
    got = _run_page(
        _CLONE,
        _CLONE_DOM + f"""
        var e1 = Object.assign({{}}, {_QUIET}, {{ index: 1, as_of: "2026-09-28T12:00:00Z", appends: [{{ display: "Steps", value: 1, unit: "1" }}] }});
        RESP.push([200, {{ entries: [e1, {_ENTRY}], omitted: 0 }}], [200, {{ cards: [{{ status: "ready" }}, {{ status: "withheld" }}, {{ status: "ready" }}] }}]);
        await loadClone();
        var full = {{ tiles: tiles(), built: $("clone-built").textContent, hidden: $("clone-aside").hidden, grid: $("ci-grid").className,
          latest: $("clone-latest").textContent }};
        RESP.push([200, {{ entries: [{_ENTRY}], omitted: 60 }}], [503, null]);
        await loadClone();
        var partial = {{ tiles: tiles(), built: $("clone-built").textContent }};
        RESP.push([200, {{ entries: [] }}], [200, {{ cards: [] }}]);
        await loadClone();
        return {{ full: full, partial: partial, fresh: [$("clone-aside").hidden, $("ci-grid").className] }};
        """,
    )
    assert got["full"]["tiles"] == ["2 days of history", "2 saved check-ins", "3 observations", "2 cards ready"]
    assert got["full"]["built"] == "Built from 2 days of your saved check-ins. Last updated 29 Sep 2026."
    assert got["full"]["hidden"] is False and got["full"]["grid"] == "grid-2"
    assert got["full"]["latest"].startswith("Check-in saved · 2 observations") and "✓ Card ready: Heart rate" in got["full"]["latest"]
    # 60 older saves left out: the day and observation totals are unknown and the passport failed, so those tiles go
    assert got["partial"]["tiles"] == ["61 saved check-ins"]
    assert got["partial"]["built"] == "Built from your saved check-ins. Last updated 29 Sep 2026."
    assert got["fresh"] == [True, ""]  # no saved check-in: no aside, one column


def test_rev3_identity_greets_by_first_name_and_names_the_passport():
    got = _run_page(
        _BASE + _IDENTITY,
        """
        ["persona-txt", "ci-date", "pp-eyebrow"].forEach(function (i) { mk(i); }); mk("persona", "p"); mk("persona-av", "span");
        mk("h-today", "h1"); mk("h-passport", "h1");
        function look() { return [$("h-today").textContent, $("ci-date").hidden ? null : $("ci-date").textContent, $("h-passport").textContent,
          $("pp-eyebrow").hidden, $("persona").hidden, $("persona-av").textContent, $("persona-txt").textContent]; }
        S.displayName = "Rowan Ellis"; S.memberId = "syn-007"; S.today = "2026-09-29";
        applyIdentity(); var persona = look();
        S.displayName = null; S.memberId = "syn-001"; S.today = null;
        applyIdentity(); return [persona, look()];
        """,
    )
    assert got[0] == ["What matters today, Rowan?", "Tuesday 29 Sep", "Rowan's passport", False, False, "R", "Rowan Ellis · syn-007"]
    assert got[1] == ["What matters today?", None, "Health Clone Passport", True, False, "", "syn-001"]


def test_rev3_member_api_strings_never_reach_an_html_sink(html):
    js = _script(html)
    for start, end in (("/* ---------- #timeline", "/* ---------- #lab"), ("function cloneUpdated", "\n}\n"),
                       ("async function loadClone", "/* Fills the bundled-file pickers"), ("function applyIdentity", "\n}\n")):
        part = _section(js, start, end)
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            assert sink not in part, (start, sink)


# --- HAC-38 P6.2 part B: visual spec rev 3 on the research console (HAC-68 §4, §5) -----------------------


def test_rev3_console_shell_skip_link_sidebar_and_brand(admin):
    root = _tree(admin)
    body = next(n for n in root.iter() if n.tag == "body")
    first, second = [c for c in body.children if isinstance(c, _Node)][:2]
    assert first.tag == "a" and first.attrs.get("class") == "skip" and first.attrs.get("href") == "#main"
    assert second.attrs.get("class") == "a-shell"
    side = next(n for n in second.children if isinstance(n, _Node))
    assert side.tag == "aside" and side.attrs.get("class") == "a-side"
    brand = next(n for n in side.iter() if "a-brand" in (n.attrs.get("class") or ""))
    badge = [n for n in brand.iter() if "tag--console" in (n.attrs.get("class") or "")]
    assert len(badge) == 1 and badge[0].text() == "Research console"  # drawn uppercase by .tag--console
    assert "Clinical Human Clone" in brand.text()
    nav = next(n for n in side.iter() if n.tag == "nav")
    assert nav.attrs.get("aria-label") == "Research console" and "a-nav" in nav.attrs.get("class", "")
    mains = [n for n in root.iter() if n.tag == "main"]
    assert len(mains) == 1 and mains[0].attrs.get("id") == "main" and mains[0].attrs.get("tabindex") == "-1"
    assert not _is_inside(mains[0], side)
    for s in ADMIN_SCREENS:
        assert _is_inside(_by_id(root, "screen-" + s), mains[0]), s
    # the console carries none of the member shell
    assert not [n for n in root.iter() if "m-head" in (n.attrs.get("class") or "") or n.attrs.get("aria-label") == "Member"]
    css = _style(admin)
    for gone in (".site-head", ".steps", ".site-foot", ".research-label", "p.brand"):  # the temporary pre-rev-3 block
        assert gone not in css, gone
    assert "site-head" not in admin and 'class="steps"' not in admin


def test_hac76_console_page_header_has_a_plain_h1_and_lede_and_no_route_or_api_labels(admin):
    """HAC-76 (board, HAC-74): no route path crumb and no ``GET /api/...`` label on screen; each console
    page opens with a plain h1 and a one-line explanation."""
    root = _tree(admin)
    for s in ADMIN_SCREENS:
        top = next(n for n in _by_id(root, "screen-" + s).iter() if n.attrs.get("class") == "a-top")
        h1 = [n for n in top.iter() if n.tag == "h1"]
        assert len(h1) == 1 and h1[0].attrs.get("id") == "h-" + s, s
        lede = [n for n in top.iter() if n.attrs.get("class") == "a-lede"]
        assert len(lede) == 1 and len(lede[0].text().split()) >= 8, s
        assert not [n for n in top.iter() if "mono" in (n.attrs.get("class") or "").split()], s
    text = _visible(admin)
    assert not re.search(r"\b(GET|POST) /api/", text) and "/admin/" not in text
    assert 'class="a-crumb"' not in admin
    for jargon in ("p95", "DSL", "Layer 0", "Membrane", "EventLog", "Learning lab", "Concept inventory", "Vertical"):
        assert jargon not in text, jargon


def test_rev3_console_router_routes_aliases_and_default(admin):
    js = _script(admin)
    assert 'var SCREENS = ["pipeline", "lab", "inventory", "sessions"];' in js  # SCREENS[0] is the default
    # the API's #research evidence link and older #playground bookmarks still resolve
    assert 'var ALIASES = { research: "sessions", playground: "sessions" };' in js
    rt = _section(js, "function route()", "\n}\n")
    assert ".a-nav a" in rt and '"page"' in rt and '"step"' not in rt
    assert "pipeline: showPipeline" in rt and "sessions:" in rt and "input:" not in rt
    from daypart.demo.app import ADMIN_ROUTE_ALIASES, ADMIN_ROUTES

    assert ADMIN_ROUTES == ADMIN_SCREENS  # /admin/<route> is served for exactly these, plus the aliases
    assert ADMIN_ROUTE_ALIASES == ("playground", "research")


def test_rev3_console_path_routes_serve_the_shell(client, admin):
    for s in ADMIN_SCREENS + ("playground", "research"):
        r = client.get(f"/admin/{s}")
        assert r.status_code == 200 and r.text == admin, s
    assert client.get("/admin/nope").status_code == 404
    assert client.get("/admin/today").status_code == 404  # never a member route
    assert client.get("/admin/input").status_code == 404  # HAC-76: the real-input screen is gone
    # AD7 stays server-side: the request is still refused
    assert client.post("/api/mode", json={"real_input": True}).status_code == 403
    js = _script(admin)
    assert 'history.replaceState(null, "", "/admin#" + m[1]' in js


def test_rev3_pipeline_lanes_stage_counts_and_copy(admin):
    root = _tree(admin)
    sec = _by_id(root, "screen-pipeline")
    live = _by_id(root, "pipe-live")
    assert live.tag == "ol" and live.attrs.get("aria-label") == "Every check-in, 5 steps"
    stages = [c for c in live.children if isinstance(c, _Node)]
    assert len(stages) == 5 and all(c.tag == "li" for c in stages)
    names = [next(n for n in li.iter() if n.attrs.get("class") == "stage-name").text() for li in stages]
    assert names == ["Member checks in", "Member reviews", "Saved to the record", "Passport updated", "Next step suggested"]
    for li in stages:  # HAC-76: one plain sentence per step, no version codes
        desc = [n.text() for n in li.iter() if n.attrs.get("class") == "stage-desc"]
        assert len(desc) == 1 and desc[0].endswith("."), desc
        assert not [n for n in li.iter() if n.tag == "dl"]
    text = " ".join(sec.text().split())
    assert "↺ The next check-in starts again at step 1. No AI model is used in this loop." in text
    assert "● automatic, every saved check-in" in text and "○ offline, not on each check-in" in text
    assert "Simulated outcomes are not patient outcomes." in text
    off = _by_id(root, "pipe-offline")
    assert off.tag == "ol" and not [c for c in off.children if isinstance(c, _Node)]  # drawn from /api/lab only
    for ident in ("pipe-results", "pipe-kpis", "lane-offline"):  # hidden until /api/lab answers
        assert "hidden" in _by_id(root, ident).attrs, ident
    assert "hidden" not in _by_id(root, "lane-live").attrs  # the live lane is static and always shown


def test_rev3_pipeline_live_lane_names_only_code_that_exists():
    """§4.1: the check-in lane states only what the running code does. HAC-76: the steps are in words and
    each path's running constant sits in the "Technical details, for reviewers" disclosure; the next-step
    policy selects by rules and checks with the membrane: nothing in the loop imports a model client."""
    from daypart.checkin import next_step
    from daypart.checkin.models import METHOD_FIXTURE, METHOD_TEXT
    from daypart.memory.registry import SLICE_VERSION
    from daypart.passport.view import READY_WINDOW_DAYS

    src = (Path(__file__).resolve().parents[2] / "daypart/demo/static/index.html").read_text()
    live = _section(src, '<ol class="pipe" id="pipe-live"', "</ol>")
    # QG P6.2 B1 (G36): the step states only what runs: typed text takes the PII and crisis screens and
    # the rules; a file takes the allow-list, and is never said to pass the text screens
    checkin = _section(live, '<span class="stage-name">Member checks in</span>', "</p>")
    assert ("Typed text is read by rules after personal details and crisis language are screened; "
            "a file is accepted only from the approved list.") in checkin
    assert "bundled file" not in checkin and "A sentence or a file" not in checkin
    assert f"A value counts as current for {READY_WINDOW_DAYS} days." in live
    assert "A rule-based suggestion, checked against the safety rules" in live
    tech = _section(src, '<details class="thread records" id="pipe-live-tech">', "</details>")
    assert (f"<dt>text</dt><dd>{METHOD_TEXT}</dd><dt>screen</dt><dd>PII + crisis</dd>"
            f"<dt>file</dt><dd>{METHOD_FIXTURE}</dd><dt>gate</dt><dd>sha256 allow-list</dd>") in tech
    assert f"<dd>{SLICE_VERSION}</dd>" in tech
    assert f"<dd>value ≤ {READY_WINDOW_DAYS} days old</dd>" in tech
    assert f"<dd>{next_step.POLICY_VERSION} (rules)</dd>" in tech and "<dd>membrane post()</dd>" in tech
    assert "<summary>Technical details, for reviewers</summary>" in tech and " open" not in tech.split(">")[0]
    loop = Path(next_step.__file__).read_text()
    for client in ("anthropic", "openai", "httpx", "requests", "modal", "transformers", "torch", "muse"):
        assert not re.search(rf"^\s*(import|from)\s+{client}\b", loop, re.M), client


def _lab_literals() -> set[str]:
    """Every number and run id the committed lab rows carry, as the page would print them."""
    from daypart.demo import lab

    t = lab.lab_rows().model_dump(mode="json")
    out: set[str] = set()

    def walk(v: object) -> None:
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, float) and v not in (0.0, 1.0):
            out.update({f"{v:.3f}", repr(v)})
        elif isinstance(v, int) and not isinstance(v, bool) and v >= 100:
            out.add(str(v))
        elif isinstance(v, str) and "/" in v and v[0].isalnum():
            out.add(v)

    walk(t)
    for r in t["rows"]:
        if r["run_id"]:
            out.add(r["run_id"].split("/")[0])  # the run prefix
    return out


def test_rev3_console_has_no_hard_coded_lab_numbers(admin):
    """§4.1: every pipeline and lab number is read per request from /api/lab, never written into the page."""
    found = _lab_literals()
    assert {"0.319", "0.681", "4040", "0.645"} <= found  # the literals the mockup drew from f66f132
    src = (Path(__file__).resolve().parents[2] / "daypart/demo/static/index.html").read_text()
    for lit in sorted(found):
        for page in (admin, src):
            assert not re.search(rf"(?<![\w.]){re.escape(lit)}(?![\w])", page), lit
    assert "needs a trained reward model" not in src  # the grpo reason comes from the API verbatim


_PIPE = ["$", "el", "attrs", "safeHref", "link", "nr", "clear", "notice", "plural", "TIMEOUT_MS", "api", "serverError",
         "parts", "pct", "pts", "count", "intOrNull", "labRowNamed", "mismatched", "mismatchTag", "rowPct", "envName", "runAnchor",
         "ROW_NAMES", "kpi", "pipeKpis", "OFFLINE", "withPts", "offlineStage", "pipeOffline", "pipeSeq", "showPipeline"]
_PIPE_BODY = """
mk("pipe-msg"); var res = mk("pipe-results", "section"), kp = mk("pipe-kpis", "ul"), lane = mk("lane-offline", "section"), ol = mk("pipe-offline", "ol"); mk("pipe-note", "p");
res.hidden = true; kp.hidden = true; lane.hidden = true;
RESP.push(RESPONSE);
await showPipeline();
function txt(e) { return e.textContent; }
return { kpis: kp.children.map(function (li) { return li.children.map(txt); }),
  stages: ol.children.map(function (li) { return [li.className, li.querySelector("span.stage-name").textContent,
    li.querySelectorAll("span.tag").map(txt), li.querySelectorAll("dt").map(txt), li.querySelectorAll("dd").map(txt),
    li.querySelectorAll("a").map(function (a) { return [a.textContent, a.href, a.title]; }),
    li.querySelectorAll("p.stage-desc").map(txt)]; }),
  label: ol.getAttribute("aria-label"), note: $("pipe-note").textContent,
  hidden: [res.hidden, kp.hidden, lane.hidden], msg: $("pipe-msg").textContent };
"""


def _pc(v: float) -> str:  # the page's percentage: one decimal
    return f"{v * 100:.1f}%"


def _pt(v: float) -> str:  # the page's change in percentage points, with its own sign
    return ("+" if v >= 0 else "−") + f"{abs(v * 100):.1f} points"


def _pipeline(response: object) -> dict:
    import json

    got = _run_page(_PIPE, _PIPE_BODY.replace("RESPONSE", json.dumps(response)))
    assert isinstance(got, dict)
    return got


def _env_name(row: str) -> str:
    """The page's envName(), written out independently: the plain name of a simulated-member approach."""
    k = row.removeprefix("env_")
    if k == "always_none":
        return "No coaching message"
    if k == "random_intent":
        return "A random approach each day"
    if k.startswith("always_"):
        return "Always " + k.removeprefix("always_").replace("_", " ")
    return k.replace("_", " ")


def _grpo_proposed(t: dict) -> dict:
    """The proposed-grpo shape (arm not run). HAC-75 made the committed grpo arm run; these tests pin the
    proposed path, and the test_hac79_* tests pin the ran ("policy") path (HAC-79)."""
    for r in t["rows"]:
        if r["row"] == "grpo":
            r.update(kind="proposed", status="proposed, not built", reason="needs a trained reward model (4.2)",
                     run_id=None, split=None, seed=None, failures=None, metrics={})
    return t


def test_rev3_pipeline_maps_every_lab_field_1_to_1():
    """Every overview number is one /api/lab field, as a percentage (HAC-76: was 3 decimals), under a
    plain-language label with a one-line explanation."""
    from daypart.demo import lab

    t = _grpo_proposed(lab.lab_rows().model_dump(mode="json"))
    rows = {r["row"]: r for r in t["rows"]}
    base, sft, dpo, grpo = rows["base"], rows["sft"], rows["dpo"], rows["grpo"]
    envs = [r for r in t["rows"] if r["kind"] == "env_baseline"]
    best = max(envs, key=lambda r: r["metrics"]["mean_adherence"])
    got = _pipeline([200, t])
    assert got["hidden"] == [False, False, False] and got["msg"] == ""
    k1, k2, k3, k4 = got["kpis"]
    assert k1[:2] == ["Safety rule pass rate", _pc(dpo["metrics"]["boundary_pass_rate"])]
    assert k1[3] == f"Before training: {_pc(base['metrics']['boundary_pass_rate'])}"
    assert k2[:2] == ["Coaching quality pass rate", _pc(dpo["metrics"]["rubric_pass_rate"])]
    assert k2[3] == f"Before training: {_pc(base['metrics']['rubric_pass_rate'])}"
    assert k3[:2] == ["Test members kept out of training", "✓ Passed" if t["i1_passed"] else "⚠ Not passed"] and len(k3) == 3
    assert k4[:2] == ["Best simulated adherence", _pc(best["metrics"]["mean_adherence"])]
    assert k4[3] == "Approach: " + _env_name(best["row"])
    for k in got["kpis"]:  # one plain sentence under every number
        assert k[2].endswith(".") and len(k[2].split()) >= 6, k
    assert got["label"] == "Training, 4 steps"
    b, s, p, g = got["stages"]
    assert b[:4] == ["", "Starting model", [], ["Safety rules", "Quality"]]
    assert b[4] == [_pc(base["metrics"]["boundary_pass_rate"]), _pc(base["metrics"]["rubric_pass_rate"])]
    assert b[5] == [["Run record", "#lab/" + base["run_id"], base["run_id"]]]
    assert b[6] == ["A general language model before any coaching training."]
    assert s[1:3] == ["Learning from example replies", ["✓ Passed its check"]]
    assert s[4] == [f"{_pc(sft['metrics']['boundary_pass_rate'])} ({_pt(sft['gate']['delta'])})", _pc(sft["metrics"]["rubric_pass_rate"])]
    assert s[5] == [["Run record", "#lab/" + sft["run_id"], sft["run_id"]]]
    assert s[6] == ["Trained on example coaching replies that follow the safety rules."]
    assert p[1:3] == ["Learning from preferred replies", ["✓ Passed its check"]]
    assert p[4] == [_pc(dpo["metrics"]["boundary_pass_rate"]), f"{_pc(dpo['metrics']['rubric_pass_rate'])} ({_pt(dpo['gate']['rubric_delta'])})"]
    assert p[5] == [["Run record", "#lab/" + dpo["run_id"], dpo["run_id"]]]
    assert p[6] == ["Shown pairs of a better and a worse reply, and trained to prefer the better one."]
    assert g[:6] == ["is-proposed", "Practice with simulated members", ["○ Planned, not built"], [], [], []]
    assert isinstance(grpo["reason"], str) and grpo["reason"]
    # the planned step's reason is the API's own text, verbatim, after "Not built: "
    assert g[6] == ["Would learn from simulated members' responses over many days.", "Not built: " + grpo["reason"]]
    assert got["note"] == (f"Each step is tested on the same {base['split']['n']} held-out practice prompts. "
                           "The trained model is evaluated here only; the check-in loop above does not use it in this prototype.")


def test_rev3_pipeline_nulls_and_provenance_mismatch():
    """A null field is "— not recorded" (nr); a mismatch row shows its tag and no number anywhere."""
    from daypart.demo import lab

    t = _grpo_proposed(lab.lab_rows().model_dump(mode="json"))
    for r in t["rows"]:
        if r["row"] == "dpo":
            r.update(status="provenance mismatch", metrics={"boundary_pass_rate": None, "rubric_pass_rate": None}, gate=None,
                     split={**r["split"], "n": None, "training_rows": None})
        if r["row"] == "sft":
            r["metrics"]["boundary_pass_rate"] = None
            r["gate"] = {"passed": False}
        if r["row"] == "grpo":
            r["reason"] = None
    t.update(i1_passed=None, member_failure_count=None)
    t["rows"] = [r for r in t["rows"] if r["kind"] != "env_baseline"]
    got = _pipeline([200, t])
    k1, k2, k3, k4 = got["kpis"]
    assert k1[1] == "⚠ provenance mismatch" and k2[1] == "⚠ provenance mismatch"
    assert k3[1] == "not recorded"
    assert k4[1] == "not recorded" and k4[3] == "Approach: not recorded"
    _b, s, p, g = got["stages"]
    assert s[2] == ["⚠ Did not pass its check"] and s[4][0] == "not recorded"  # no change shown without a number
    assert p[2] == ["⚠ provenance mismatch"] and p[3] == [] and p[5] == []  # no number, no gate, no link
    assert g[2] == ["○ Planned, not built"]


@pytest.mark.parametrize("resp", [[500, {"error": "internal"}], "network", [200, {"rows": "x"}]])
def test_rev3_pipeline_failed_lab_get_hides_numbers(resp):
    got = _pipeline(resp)
    assert got["hidden"] == [True, True, True] and got["kpis"] == [] and got["stages"] == []
    assert "Something went wrong" in got["msg"]
    assert ("error 500" in got["msg"]) if resp[0] == 500 else True


def test_rev3_pipeline_delta_signs():
    """QG P6.2 K13 (HAC-76: in points): a change carries its own sign; zero is "+0.0 points"; a null is none."""
    got = _run_js(["pct", "pts"], "[pts(-0.021), pts(0.0214), pts(0), pts(null), pct(0.319149), pct(1), pct(null)]")
    assert got == ["−2.1 points", "+2.1 points", "+0.0 points", None, "31.9%", "100.0%", None]


def test_rev3_only_the_newest_pipeline_load_draws():
    """QG P6.2 K12: two overlapping #pipeline loads; the stale first answer (here a failure) neither
    hides the newer KPIs and offline lane nor adds a notice, and draws no stale numbers."""
    import json

    from daypart.demo import lab

    t = lab.lab_rows().model_dump(mode="json")
    got = _run_page(
        _PIPE,
        """
        mk("pipe-msg"); mk("pipe-results", "section"); var kp = mk("pipe-kpis", "ul"), lane = mk("lane-offline", "section"), ol = mk("pipe-offline", "ol"); mk("pipe-note", "p");
        kp.hidden = true; lane.hidden = true;
        var answers = [];
        fetch = function () { return new Promise(function (resolve) { answers.push(resolve); }); };
        var first = showPipeline(), second = showPipeline();
        await new Promise(function (r) { setTimeout(r, 10); });
        answers[1]({ status: 200, ok: true, json: async function () { return LAB; } }); await second;
        var drawn = kp.textContent;
        answers[0]({ status: 500, ok: false, json: async function () { return { error: "internal" }; } }); await first;
        return [kp.hidden, lane.hidden, $("pipe-msg").textContent, kp.textContent === drawn, ol.children.length];
        """.replace("LAB", json.dumps(t)),
    )
    assert got == [False, False, "", True, 4]


def test_rev3_lab_deep_link_marks_the_row_and_keeps_stacking(admin):
    js = _script(admin)
    lab = _section(js, "async function showLab", "\nfunction modelRow")
    assert 'setAttribute("aria-current", "true")' in lab and '$("lab-records").open = true' in lab
    css = _style(admin)
    assert 'table.stack tr[aria-current="true"] td{background:var(--a-raised)}' in css
    assert "@media (max-width:40rem){\n  table.stack thead" in css and "content:attr(data-label)" in css


def test_hac76_g5_table_text_breaks_at_spaces_only(admin):
    """G5 (HAC-74): the body's overflow-wrap:anywhere broke lab cells mid-word at 1280; table text now
    wraps at spaces and only run ids and digests may break anywhere."""
    css = _style(admin)
    assert "table.stack th,table.stack td{overflow-wrap:normal;word-break:normal;" in css
    assert "table.stack .run-id{overflow-wrap:anywhere}" in css
    assert not re.search(r"\.gates(?![\w-])", css)  # the gates list went with the real-input screen


def test_rev3_inventory_table_maps_the_api_and_has_no_cards_column(admin, client):
    root = _tree(admin)
    sec = _by_id(root, "screen-inventory")
    heads = [" ".join(n.text().split()) for n in sec.iter() if n.tag == "th"]
    assert heads == ["Health area", "Measures", "Status"]  # /api/inventory has no card count, so no Cards column
    assert "cards" not in " ".join(str(k) for k in client.get("/api/inventory").json())
    got = _run_page(["$", "el", "nr", "clear", "notice", "TIMEOUT_MS", "api", "serverError", "cell", "MONTHS", "fmtDay", "reviewLabel",
                     "invSeq", "showInventory"], """
      mk("ainv-msg"); var body = mk("ainv-body"); body.hidden = true; mk("ainv-meta", "dl"); var rows = mk("ainv-rows", "tbody"); mk("ainv-list");
      RESP.push([200, INV]);
      await showInventory();
      return [body.hidden, rows.children.map(function (tr) { return [tr.className].concat(tr.children.map(function (td) {
        return td.getAttribute("data-label") + "=" + td.textContent; })); })];
    """.replace("INV", __import__("json").dumps(client.get("/api/inventory").json())))
    inv = client.get("/api/inventory").json()
    assert got[0] is False
    want = [["", f"Health area={v['label']}", f"Measures={len(v['concepts'])}", "Status=✓ Covered"] for v in inv["verticals"]]
    want += [["proposed", f"Health area={g}", "Measures=0", "Status=○ Not covered yet"] for g in inv["gap_labels"]]
    assert got[1] == want


_GATED = """
var gates = [];
fetch = function (path) { return new Promise(function (resolve) { gates.push(function (body) {
  resolve({ status: 200, ok: true, json: async function () { return body; } }); }); }); };
"""


def test_b2_only_the_newest_lab_load_draws():
    """QG P6.2 B2: #lab/A then quickly #lab/B: the slow first /api/lab answer never redraws the table
    or marks run A."""
    got = _run_page(
        ["$", "el", "nr", "clear", "notice", "plural", "TIMEOUT_MS", "api", "serverError", "labRowNamed", "mismatched",
         "labSeq", "showLab"],
        _GATED + """
        mk("lab-msg"); mk("lab-body"); mk("lab-meta", "dl"); mk("lab-cap-sub", "span"); mk("env-wrap"); mk("lab-records", "details");
        var rows = mk("lab-rows", "tbody"); mk("env-rows", "tbody"); mk("rec-rows", "tbody");
        var drawn = 0;
        function row(r) { var tr = el("tr"); tr.dataset.runId = r.run_id; return tr; }
        globalThis.modelRow = function (r) { drawn++; return row(r); };
        globalThis.envRow = row; globalThis.recordRow = function () { return el("tr"); };
        var t = { rows: [{ run_id: "A", kind: "model" }, { run_id: "B", kind: "model" }], i1_passed: true, member_failure_count: 0 };
        var first = showLab("A"), second = showLab("B");
        await new Promise(function (r) { setTimeout(r, 10); });
        gates[1](t); await second;   // the newer load answers first
        gates[0](t); await first;    // then the stale one
        return [drawn, rows.children.filter(function (tr) { return tr.getAttribute("aria-current") === "true"; })
          .map(function (tr) { return tr.dataset.runId; })];
        """,
    )
    assert got == [2, ["B"]]


def test_b2_only_the_newest_inventory_load_draws():
    got = _run_page(
        ["$", "el", "nr", "clear", "notice", "TIMEOUT_MS", "api", "serverError", "cell", "MONTHS", "fmtDay", "reviewLabel",
         "invSeq", "showInventory"],
        _GATED + """
        mk("ainv-msg"); mk("ainv-body"); mk("ainv-meta", "dl"); var rows = mk("ainv-rows", "tbody"); mk("ainv-list");
        function inv(label) { return { loinc_version: "2.80", reviewer_status: null, verticals: [{ label: label, concepts: [] }], gap_labels: [] }; }
        var first = showInventory(), second = showInventory();
        await new Promise(function (r) { setTimeout(r, 10); });
        gates[1](inv("new")); await second;
        gates[0](inv("old")); await first;
        return rows.children.map(function (tr) { return tr.children[0].textContent; });
        """,
    )
    assert got == ["new"]


def test_rev3_sessions_have_no_optional_chip_or_synthetic_tag(admin):
    sec = _by_id(_tree(admin), "screen-sessions")
    text = " ".join(sec.text().split())
    assert "(optional)" not in text and "synthetic" not in text.lower() and "Research console" not in text
    assert "research-label" not in admin
    for ident in ("r-member", "r-intent", "r-text", "r-start", "r-step", "r-days", "r-log", "r-cards"):
        _by_id(_tree(admin), ident)


def test_rev3_real_input_stays_refused_server_side(client):
    """HAC-76 removed the real-input screen; AD7 still holds: the build cannot allow real input and the
    API refuses every request with the open gates."""
    from daypart.governance import real_input

    assert real_input.REAL_INPUT_BUILD_ALLOWED is False
    r = client.post("/api/mode", json={"real_input": True})
    assert r.status_code == 403 and len(r.json()["open_gates"]) == 12


def test_rev3_console_api_strings_never_reach_an_html_sink(admin):
    js = _script(admin)
    for start, end in (("/* ---------- #lab", "/* ---------- #inventory"), ("/* ---------- #inventory", "/* ---------- wiring")):
        part = _section(js, start, end)
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            assert sink not in part, (start, sink)


def test_rev3_console_reduced_motion_and_tap_targets(admin):
    css = _style(admin)
    assert "@media (prefers-reduced-motion:reduce){\n  *,*::before,*::after{animation-duration:0s!important;animation-delay:0s!important;transition-duration:0s!important" in css
    assert ".a-nav a{display:flex;align-items:center;gap:var(--s2);min-height:var(--tap)" in css
    assert ".a-side-foot a{display:inline-flex;align-items:center;min-height:var(--tap)}" in css
    assert "--tap:44px" in css


# ---------- HAC-79: the ran grpo arm (kind "policy") and the passport Inclinations block ----------


def test_hac79_pipeline_grpo_policy_stage_shows_env_metrics_not_boundary():
    """A ran grpo row is scored with simulated members: the 4th training step shows adherence, breaches and
    sessions from the API row 1:1, as percentages under plain labels (HAC-76), with a one-sentence
    description in the past tense; never "Planned", never the safety/quality pair it has no field for."""
    from daypart.demo import lab

    t = lab.lab_rows().model_dump(mode="json")
    grpo = next(r for r in t["rows"] if r["row"] == "grpo")
    assert grpo["kind"] == "policy"  # the committed arm runs (HAC-75)
    got = _pipeline([200, t])
    g = got["stages"][3]
    assert g[:4] == ["", "Practice with simulated members", [], ["Adherence", "Safety-rule breaches", "Sessions tested"]]
    m = grpo["metrics"]
    assert g[4] == [_pc(m["mean_adherence"]), _pc(m["episode_violation_rate"]), str(grpo["split"]["n"])]
    assert g[5] == [["Run record", "#lab/" + grpo["run_id"], grpo["run_id"]]]
    assert g[6] == ["Learned which kind of message to send each day from how simulated members responded."]
    text = " ".join(g[1:2] + g[2] + g[3] + g[4] + g[6])
    for word in ("not recorded", "Planned", "proposed", "GRPO", "episode", "violation", "env"):
        assert word not in text, word
    # the best-adherence tile counts the ran policy with the approaches, named in words
    scored = [r for r in t["rows"] if r["kind"] in ("env_baseline", "policy")]
    best = max(scored, key=lambda r: r["metrics"]["mean_adherence"])
    k4 = got["kpis"][3]
    assert k4[1] == _pc(best["metrics"]["mean_adherence"])
    assert k4[3] == "Approach: " + ("Step 3 · Practice with simulated members" if best["kind"] == "policy" else _env_name(best["row"]))


def test_hac79_pipeline_grpo_policy_nulls_are_not_recorded():
    from daypart.demo import lab

    t = lab.lab_rows().model_dump(mode="json")
    for r in t["rows"]:
        if r["row"] == "grpo":
            r.update(metrics={"mean_adherence": None, "episode_violation_rate": None}, split={**r["split"], "n": None})
    g = _pipeline([200, t])["stages"][3]
    assert g[4] == ["not recorded", "not recorded", "not recorded"]


def test_hac79_lab_policy_row_renders_like_an_env_row():
    """In #lab a ran grpo policy is a coaching approach row (adherence, breaches, sessions), in words and
    percentages; its run record keeps the ids in the collapsed reviewers' table."""
    got = _run_page(
        _BASE + _LAB + ["plural"],
        """
        var r = { row: "grpo", kind: "policy", status: "ok", run_id: "eval-v1@abc/grpo",
          split: { n: 150, n_scenarios: 50, horizon: 14 }, seed: [0, 1, 2], failures: 0,
          metrics: { mean_adherence: 0.84, episode_violation_rate: 0.0 } };
        function cells(tr) { return tr.children.map(function (c) { return [c.getAttribute("data-label"), c.textContent]; }); }
        var gp = envRow(r);
        return { cls: gp.className || "", run: gp.dataset.runId, cells: cells(gp), rec: cells(recordRow(r)) };
        """,
    )
    c = dict(got["cells"])
    assert got["cls"] == "" and got["run"] == "eval-v1@abc/grpo"
    assert c == {"Coaching approach": "Step 3 · Practice with simulated membersLearned in training, not a fixed rule",
                 "Average adherence": "84.0%", "Sessions with a safety-rule breach": "0.0%",
                 "Tested on": "150 sessions50 members, 14 days each"}
    rec = dict(got["rec"])
    assert rec["Step or approach"] == "Step 3" and rec["Run ID"] == "eval-v1@abc/grpo"
    assert rec["Test set"] == "scenarios 50 · sessions 150 · days 14"
    assert rec["Seed"] == "0, 1, 2" and rec["Failures"] == "0 sessions"
    assert "episode" not in str(got) and "proposed" not in str(got)


_INCL = {
    "drivers": [
        {"driver_id": "a", "label": "Mornings are busy", "direction": "makes_harder", "weight": "strong"},
        {"driver_id": "b", "label": "A clear plan", "direction": "helps", "weight": "moderate"},
    ],
    "insights": [{"insight_id": "i1", "title": "Plan around it", "action": "Do one thing.", "reason": "Why: A clear plan.", "driver": "b"}],
    "note": "Estimated from simulated members, not from patient data.",
}


def _incl(inc: object) -> dict:
    import json

    got = _run_page(
        _BASE + ["renderInclinations"],
        """
        var box = mk("pp-incl");
        renderInclinations(INC);
        function txt(e) { return e.textContent; }
        return { kids: box.children.map(function (e) { return [e.tagName.toLowerCase(), e.id || "", e.getAttribute("aria-labelledby") || ""]; }),
          tags: box.querySelectorAll("span.tag").map(function (e) { return [e.className, e.textContent]; }),
          h4: box.querySelectorAll("h4").map(txt), h3: box.querySelectorAll("h3").map(txt),
          art: box.querySelectorAll("article").map(function (a) { return [a.getAttribute("aria-labelledby"), a.getAttribute("aria-describedby")]; }),
          text: box.textContent };
        """.replace("INC", json.dumps(inc)),
    )
    assert isinstance(got, dict)
    return got


def test_hac79_inclinations_order_headings_and_tags():
    got = _incl(_INCL)
    kinds = [k[0] for k in got["kids"]]
    assert kinds == ["p", "h3", "ul", "h3", "div"]  # the simulated caveat first, before the numbers it qualifies
    assert got["kids"][2][2] == "h-incl-drv" and got["kids"][4][2] == "h-incl-ins"  # lists named by their visible headings
    assert got["h3"] == ["What weighs most", "Next steps"] and got["h4"] == ["Plan around it"]  # h2 > h3 > h4
    # QG U1: no Helps / Makes-it-harder tag (it read as "forgetting helps me"); the tag is the weight only
    assert got["tags"] == [["tag", "◆ Weighs strongly"], ["tag", "◆ Weighs moderately"]]
    assert "Helps" not in str(got["tags"]) and "harder" not in str(got["tags"])
    assert "tag--withheld" not in str(got["tags"])  # withheld means "no data", not a direction
    assert got["art"] == [["pp-ins0", "pp-drv-1"]] and "Linked to: A clear plan" in got["text"]


@pytest.mark.parametrize("inc", [None, {"drivers": [], "insights": []}])
def test_hac79_inclinations_absent_is_not_enough_data(inc):
    got = _incl(inc)
    assert got["text"] == "Not available for this journal." and got["h3"] == []  # QG D10: failure-neutral
