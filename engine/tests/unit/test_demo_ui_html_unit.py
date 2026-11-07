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
SCREENS = ("checkin", "review", "passport", "next", "lab", "research")


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


def _without_research(html: str) -> str:
    """The page source with the ``<section id="research">`` element (and everything in it) cut out."""
    m = re.search(r'<section\b[^>]*\bid="research"[^>]*>', html)
    assert m, "no <section id=\"research\">"
    depth, i = 1, m.end()
    tag = re.compile(r"<(/?)section\b[^>]*>")
    while depth:
        t = tag.search(html, i)
        assert t, "unclosed research section"
        depth += -1 if t.group(1) else 1
        i = t.end()
    return html[: m.start()] + html[i:]


# --- T1.1 ---------------------------------------------------------------------------------------


def test_t1_1_names_and_no_research_words_outside_research(html):
    assert "Clinical Human Clone" in html
    assert "Health Clone Passport" in html
    assert "pattern passport" not in html.lower()  # nowhere, the research view included
    outside = _without_research(html)
    assert "Daypart playground" not in outside
    assert "pattern passport" not in outside.lower()
    assert not re.search(r"\bIntent\b", outside)
    assert not re.search(r"\bDraft\b", outside)
    research = _by_id(_tree(html), "research").text()
    assert "Research view (optional)" in research
    assert re.search(r"\bIntent\b", research) and re.search(r"\bDraft\b", research)


# --- structure: routes, h1s, nav, banner ----------------------------------------------------------


def test_one_main_one_h1_per_screen(html):
    root = _tree(html)
    mains = [n for n in root.iter() if n.tag == "main"]
    assert len(mains) == 1
    for s in SCREENS:
        sec = _by_id(root, s)
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


def test_banner_is_first_in_body_outside_main_with_role_status(html):
    root = _tree(html)
    body = next(n for n in root.iter() if n.tag == "body")
    first = next(c for c in body.children if isinstance(c, _Node))
    assert "banner" in (first.attrs.get("class") or "").split()
    assert first.attrs.get("role") == "status"
    assert "Demo mode: synthetic inputs and simulated results" in first.text()
    main = next(n for n in root.iter() if n.tag == "main")
    assert not _is_inside(first, main)


def test_step_nav_has_five_links(html):
    root = _tree(html)
    nav = next(n for n in root.iter() if n.tag == "nav" and n.attrs.get("aria-label") == "Journey")
    hrefs = [n.attrs.get("href") for n in nav.iter() if n.tag == "a"]
    assert hrefs == ["#checkin", "#review", "#passport", "#next", "#lab"]


def test_footer_disclaimer_research_link_and_loinc_notice(html):
    root = _tree(html)
    foot = next(n for n in root.iter() if n.tag == "footer")
    text = " ".join(foot.text().split())
    assert "Synthetic data only. Not for clinical use." in text
    assert any(n.tag == "a" and n.attrs.get("href") == "#research" for n in foot.iter())
    assert "LOINC" in text and "Regenstrief Institute" in text
    assert any(n.tag == "a" and n.attrs.get("href") == "https://loinc.org/license/" for n in foot.iter())


# --- T2.1, T3.3, T8.4, T9.4 (static parts) -----------------------------------------------------------


def test_t2_1_checkin_heading_labelled_textarea_and_warning(html):
    root = _tree(html)
    sec = _by_id(root, "checkin")
    h1 = next(n for n in sec.iter() if n.tag == "h1")
    assert h1.text().strip() == "What matters today?"
    areas = [n for n in sec.iter() if n.tag == "textarea"]
    assert len(areas) == 1 and areas[0].attrs.get("maxlength") == "500"
    tid = areas[0].attrs.get("id")
    assert tid and any(n.tag == "label" and n.attrs.get("for") == tid for n in sec.iter())
    assert "Do not enter real health data" in sec.text()


def test_t3_3_voice_and_video_disabled_not_available(html):
    sec = _by_id(_tree(html), "checkin")
    buttons = [n for n in sec.iter() if n.tag == "button" and "disabled" in n.attrs]
    for word in ("Voice", "Video"):
        hits = [b for b in buttons if word in b.text()]
        assert len(hits) == 1, word
        assert "Not available" in hits[0].text()


def test_t8_4_lab_footnote(html):
    sec = _by_id(_tree(html), "lab")
    assert "Simulated outcomes are not patient outcomes." in sec.text()


def test_t9_4_real_input_button_controls_a_live_region(html):
    root = _tree(html)
    btns = [n for n in root.iter() if n.tag == "button" and n.text().strip() == "Real input"]
    assert len(btns) == 1
    b = btns[0]
    assert b.attrs.get("aria-expanded") == "false"
    panel = _by_id(root, b.attrs.get("aria-controls") or "")
    assert panel.attrs.get("aria-live") == "polite"


# --- palette and escaping ----------------------------------------------------------------------------


def test_only_the_six_token_colours(html):
    found = {m.upper() for m in re.findall(r"(?<![&\w])#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b", html)}
    assert found == ALLOWED_HEX, found - ALLOWED_HEX
    assert not re.search(r"\b(rgba?|hsla?)\(", html)


def test_no_html_sinks_with_data(html):
    for rhs in re.findall(r"innerHTML\s*=\s*([^;\n]*)", html):
        assert rhs.strip() in ("''", '""'), rhs
    for sink in ("outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
        assert sink not in html, sink
    # every href set from script goes through the allow-list helper (https: or '#')
    assert not re.search(r"setAttribute\(\s*['\"]href", html)
    for rhs in re.findall(r"\.href\s*=\s*([^;\n]*)", html):
        assert rhs.strip().startswith("safeHref("), rhs


def test_no_external_resources(html):
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
    blocks = re.findall(r"<script>(.*?)</script>", _without_research(html), re.S)
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
    assert "This demo cannot help with this. Nothing from your check-in was saved." in hand
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
    assert "This is a fault in the demo, not in what you wrote. Try again, or use a demo input." in js
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
    assert "We could not reach the demo server. Check your connection and try again." in js
    assert "The demo had a problem on its side (error " in js and "Try again in a moment." in js
    assert '"Try again"' in js
    assert "Something went wrong, so nothing was saved" not in js  # the network copy makes no saving claim
    assert "genericError" not in js
    # error notices never carry the server's body
    assert not re.search(r"\bdetail\b", js)


def test_rev2_get_failure_notice_sits_directly_under_h1(html):
    root = _tree(html)
    for s in ("passport", "next", "lab"):
        sec = _by_id(root, s)
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
