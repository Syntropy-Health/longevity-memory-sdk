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
ALLOWED_HEX = {"183446", "2B6F8A", "E8F2F3", "247F72", "A65C16", "FFFFFF"}
# AM-2 D1 (G31): the member app at "/" and the research console at "/admin" are separate shells.
MEMBER_SCREENS = ("checkin", "review", "passport", "next")
ADMIN_SCREENS = ("lab", "inventory", "research")
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


def _without_research(html: str) -> str:  # the admin console minus its playground section
    """The page source with the ``<section id="screen-research">`` element (and everything in it) cut out."""
    m = re.search(r'<section\b[^>]*\bid="screen-research"[^>]*>', html)
    assert m, "no <section id=\"screen-research\">"
    depth, i = 1, m.end()
    tag = re.compile(r"<(/?)section\b[^>]*>")
    while depth:
        t = tag.search(html, i)
        assert t, "unclosed research section"
        depth += -1 if t.group(1) else 1
        i = t.end()
    return html[: m.start()] + html[i:]


# --- T1.1 ---------------------------------------------------------------------------------------


def test_t1_1_names_and_no_research_words_outside_research(html, admin):
    assert "Clinical Human Clone" in html
    assert "Health Clone Passport" in html
    assert "pattern passport" not in (html + admin).lower()  # nowhere, the research console included
    # AM-2 D1: the member app carries no research markup at all (was: research section cut out)
    assert 'id="screen-research"' not in html
    assert "Daypart playground" not in html
    assert not re.search(r"\bIntent\b", html)
    assert not re.search(r"\bDraft\b", html)
    research = _by_id(_tree(admin), "screen-research").text()
    assert "Research playground" in research
    assert re.search(r"\bIntent\b", research) and re.search(r"\bDraft\b", research)
    assert "Daypart playground" not in _without_research(admin)


def test_am2_d1_member_app_has_no_admin_screens_and_admin_has_no_journey(html, admin):
    member_ids = {n.attrs.get("id") for n in _tree(html).iter()}
    admin_ids = {n.attrs.get("id") for n in _tree(admin).iter()}
    for s in ADMIN_SCREENS:
        assert "screen-" + s not in member_ids and "screen-" + s in admin_ids
    for s in MEMBER_SCREENS:
        assert "screen-" + s in member_ids and "screen-" + s not in admin_ids
    assert "ri-btn" not in member_ids and "ri-btn" in admin_ids  # the real-input control is admin-only


def test_am2_d1_member_never_links_the_research_console(html):
    hrefs = [n.attrs.get("href") or "" for n in _tree(html).iter() if n.tag == "a"]
    assert not [h for h in hrefs if h.startswith("/admin") or re.match(r"#(lab|research|inventory)\b", h)]
    assert "/results" not in hrefs and "/docs" not in hrefs
    js = _script(html)
    assert '"#lab"' not in js and "Continue to the learning lab" not in js


def test_am2_d1_admin_console_links_back_to_the_member_app(admin):
    root = _tree(admin)
    nav = next(n for n in root.iter() if n.tag == "nav" and n.attrs.get("aria-label") == "Research console")
    assert [n.attrs.get("href") for n in nav.iter() if n.tag == "a"] == ["#lab", "#inventory", "#research"]
    hrefs = {n.attrs.get("href") for n in root.iter() if n.tag == "a"}
    assert "/" in hrefs and "/results" in hrefs


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
    # AM-2 D2 (G32): the demo-mode banner is gone; the site header now opens the page.
    root = _tree(html)
    body = next(n for n in root.iter() if n.tag == "body")
    first = next(c for c in body.children if isinstance(c, _Node))
    assert first.tag == "header" and "site-head" in (first.attrs.get("class") or "").split()
    main = next(n for n in root.iter() if n.tag == "main")
    assert not _is_inside(first, main)


def test_step_nav_has_four_member_links(html):
    # AM-2 D1: the learning lab moved to the research console, so the journey nav has 4 links.
    root = _tree(html)
    nav = next(n for n in root.iter() if n.tag == "nav" and n.attrs.get("aria-label") == "Journey")
    hrefs = [n.attrs.get("href") for n in nav.iter() if n.tag == "a"]
    assert hrefs == ["#checkin", "#review", "#passport", "#next"]


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
    sec = _by_id(root, "screen-checkin")
    h1 = next(n for n in sec.iter() if n.tag == "h1")
    assert h1.text().strip() == "What matters today?"
    areas = [n for n in sec.iter() if n.tag == "textarea"]
    assert len(areas) == 1 and areas[0].attrs.get("maxlength") == "500"
    tid = areas[0].attrs.get("id")
    assert tid and any(n.tag == "label" and n.attrs.get("for") == tid for n in sec.iter())
    # AM-2 D2: the "public demo" warning became a privacy note; the PII tripwire is unchanged.
    assert "Keep personal details out" in sec.text()
    assert "Do not enter real health data" not in sec.text() and "public demo" not in sec.text()


def test_t3_3_voice_and_video_disabled_not_available(html):
    sec = _by_id(_tree(html), "screen-checkin")
    buttons = [n for n in sec.iter() if n.tag == "button" and "disabled" in n.attrs]
    for word in ("Voice", "Video"):
        hits = [b for b in buttons if word in b.text()]
        assert len(hits) == 1, word
        assert "Not available" in hits[0].text()


def test_t8_4_lab_footnote(admin):
    sec = _by_id(_tree(admin), "screen-lab")
    assert "Simulated outcomes are not patient outcomes." in sec.text()


def test_t9_4_real_input_button_controls_a_live_region(admin):
    # AM-2 D2: the real-input control lives in the research console only.
    root = _tree(admin)
    btns = [n for n in root.iter() if n.tag == "button" and n.text().strip() == "Real input"]
    assert len(btns) == 1
    b = btns[0]
    assert b.attrs.get("aria-expanded") == "false"
    panel = _by_id(root, b.attrs.get("aria-controls") or "")
    assert panel.attrs.get("aria-live") == "polite"


# --- palette and escaping ----------------------------------------------------------------------------


@pytest.mark.parametrize("surface", ["html", "admin"])
def test_only_the_six_token_colours(surface, request):
    html = request.getfixturevalue(surface)
    found = {m.upper() for m in re.findall(r"(?<![&\w])#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b", html)}
    assert found == ALLOWED_HEX, found - ALLOWED_HEX
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
    assert "synthetic" in d and "not medical advice" in d


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
    src = _without_research(html) if 'id="screen-research"' in html else html
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
    assert re.search(r"\.notice--handoff\{border-color:var\(--ink\)\}", css)
    assert ".notice--handoff .handoff-text" in css
    assert ".notice:focus{" in css
    assert ".ref-pop,.ref-src{display:block}" in css
    assert ".visually-hidden{" in css
    assert ".spec{" not in css and "[data-screen]{display:none}" not in css


def test_rev2_crisis_handoff_notice(html):
    js = _script(html)
    hand = _section(js, "function showHandoff", "\n}\n")
    assert '"handoff"' in hand  # notice kind → .notice--handoff
    assert "Please talk to a person about this" in hand
    assert "This app cannot help with this. Nothing from your check-in was saved." in hand
    assert "Write a different check-in" in hand
    assert '"alert"' in hand and "focus" in hand
    assert "real-data-warning" in hand and ".hidden = true" in hand
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
    assert "This is a fault on our side, not in what you wrote. Try again, or import a file." in js
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
    assert "The service had a problem on its side (error " in js and "Try again in a moment." in js
    low = " ".join(_string_literals(js)).lower()
    assert not re.search(r"\b(the|this|a) demo\b|demo (file|image|input|server|session)", low), low
    assert '"Try again"' in js
    assert "Something went wrong, so nothing was saved" not in js  # the network copy makes no saving claim
    assert "genericError" not in js
    # error notices never carry the server's body
    assert not re.search(r"\bdetail\b", js)


def test_rev2_get_failure_notice_sits_directly_under_h1(html, admin):
    # AM-2 D1: the lab is on the research console now; the inventory screen joins it there.
    for page, s in ((html, "passport"), (html, "next"), (admin, "lab"), (admin, "inventory")):
        sec = _by_id(_tree(page), "screen-" + s)
        kids = [c for c in sec.children if isinstance(c, _Node)]
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


_THREAD = ["STEP_NAMES", "ADMIN_HASH", "memberLink", "viewText", "thread"]
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


_LAB = ["ROW_NAMES", "cell", "parts", "rate", "labRow"]


def test_c6_lab_base_row_shows_the_file_digest_as_text():
    got = _run_page(
        _BASE + _LAB,
        """
        var tr = labRow({ row: "base", kind: "model", status: "ok", run_id: "tag/base", file_digest: "0123456789ab",
          split: { prompt_set_version: "v1", n: 10 }, seed: 0, failures: 1, degenerate: 0, metrics: {} });
        var id = tr.children[1];
        var mono = id.querySelectorAll("code").filter(function (c) { return c.textContent === "0123456789ab"; });
        return { text: id.textContent, mono: mono.map(function (c) { return c.className; }),
                 links: id.querySelectorAll("a").map(function (a) { return a.textContent; }) };
        """,
    )
    assert "file digest 0123456789ab" in got["text"]
    assert got["mono"] == ["mono"]
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


_CHECKIN = ["persist", "updateNav", "journalPending", "adoptJournal", "createJournal", "ensureJournal", "ciBusy", "showCheckin",
            "loadFixtures", "submitCheckin"]
_CI_DOM = """
mk("ci-load-msg"); var body = mk("ci-body"); ["ci-files", "ci-images"].forEach(function (i) { var b = mk(i); b.append(el("ul")); });
mk("nav-review", "a");
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
    sec = _by_id(_tree(html), "screen-checkin")
    kids = [c for c in sec.children if isinstance(c, _Node)]
    assert kids[0].tag == "h1" and kids[1].attrs.get("id") == "ci-load-msg"


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
        ["ci-msg", "ci-count", "ci-intro", "real-data-warning", "session-msg", "nav-review"].forEach(function (i) { mk(i); });
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
          formHidden: $("ci-form").hidden, introHidden: $("ci-intro").hidden, warnHidden: $("real-data-warning").hidden,
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
    assert got["formHidden"] and got["introHidden"] and got["warnHidden"]
    assert got["textarea"] == ""
    # the UI adds no number, link or href of its own (substring bans: no word boundaries to slip past)
    hand = _section(_script(html), "function showHandoff", "\n}\n")
    for banned in ("988", "911", "href", "link(", "btnLink(", "tel:", "http", "lifeline"):
        assert banned not in hand, banned


def test_k1_lab_mismatch_and_missing_seed_rows_render_the_a_and_d_words():
    """QG P3 K1: A&D §4.8 / T8.3 and G25: an adapter mismatch row shows "provenance mismatch" (the API
    ``status``, verbatim) and no number; a missing seed renders "not recorded" (T8.3's UI half)."""
    got = _run_page(
        _BASE + _LAB,
        """
        var mm = labRow({ row: "sft", kind: "model", status: "provenance mismatch", run_id: "tag/sft",
          split: { prompt_set_version: "v1", n: 10, training_rows: 99, data_sha256: "abcdefabcdef0000" },
          seed: 3, failures: 1, degenerate: 0, metrics: { boundary_pass_rate: 0.9, rubric_pass_rate: 0.8 } });
        var ns = labRow({ row: "base", kind: "model", status: "ok", run_id: "tag/base",
          split: { prompt_set_version: "v1", n: 10 }, seed: null, failures: 1, degenerate: 0, metrics: {} });
        var gp = labRow({ row: "grpo", kind: "proposed", status: "proposed, not built", reason: "not run" });
        function cells(tr) { return tr.children.map(function (c) { return [c.getAttribute("data-label"), c.textContent]; }); }
        return { mm: cells(mm), ns: cells(ns), gp: cells(gp) };
        """,
    )
    mm = dict(got["mm"])
    assert "provenance mismatch" in mm["Run ID"]  # the A&D's words, case and all
    assert "n =" not in mm["Split"] and "training rows" not in mm["Split"]
    for label in ("Seed", "Failures", "Metric"):
        assert not re.search(r"\d", mm[label]), (label, mm[label])
    assert "not shown" in mm["Metric"]
    assert dict(got["ns"])["Seed"] == "not recorded"
    gp = dict(got["gp"])
    assert "proposed, not built" in gp["Run ID"] and gp["Metric"] == "No number. Reason: not run"
    assert not re.search(r"\d", gp["Metric"])
    for row in (got["mm"], got["ns"], got["gp"]):
        assert all(label for label, _ in row)  # every cell has data-label (the 375 px stacked layout)


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
