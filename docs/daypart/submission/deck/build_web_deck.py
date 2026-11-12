"""Build the FHDIC web deck (HAC-86) served by the demo app at /deck.

    python docs/daypart/submission/deck/build_web_deck.py

Writes engine/daypart/demo/deck/index.html and copies screens/*.jpg next to it. The CSS and the
navigation script (deck.css, deck.js) are hand-written files in the same folder.

Top-down: Problem (2 slides), Design (3), Technical solution (4), Close (1). Every number on a slide is
in DATA below, keyed by the evidence-ledger row it comes from (docs/daypart/submission/evidence-ledger.md);
each slide names its rows in a data-ledger attribute and in its speaker notes. Charts and diagrams are
inline SVG drawn from DATA, so a chart cannot disagree with the ledger. Standard library only.
"""
from __future__ import annotations

import html
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "engine" / "daypart" / "demo" / "deck"
DEMO_URL = "https://supermomo668--daypart-demo-playground.us-east.modal.run"
DECK_URL = DEMO_URL + "/deck"
REPO_URL = "https://github.com/Syntropy-Health/longevity-memory-sdk"
ASSET = "/deck/"  # served by daypart.demo.app

# ---------------------------------------------------------------- numbers, by ledger row
DATA = {
    # L60: boundary pass rate on 141 held-out prompts (L59: 51 check-in + 90 probe, seed 0)
    "boundary": [("Base model", 45, 141, "base"), ("Fine-tuned (SFT)", 141, 141, "act"), ("Preference-tuned (DPO)", 141, 141, "obs")],
    # L66 scripted baselines and L79 GRPO: mean simulated adherence, 150 episodes of 14 days
    "adherence": [("No support", 0.637, "base"), ("Random message", 0.719, "base"),
                  ("Always problem-solving", 0.833, "base"), ("Learned policy (GRPO)", 0.840, "obs")],
    # L75: per-trait recovery on 58 held-out simulated members, chance in brackets
    # (values: docs/daypart/results/metrics.json, arm jev, heldout_recovery.axis_accuracy / chance_accuracy)
    "jev": [("Health-information confidence", 0.914, 0.333), ("Main barrier", 0.845, 0.167),
            ("Weekly rhythm", 0.793, 0.200), ("What prompts reaching out", 0.793, 0.200),
            ("How much the routine matters", 0.759, 0.333)],
    # L78: reward model's top message type matches the simulator's, chance 1 in 6
    "rm_top": (0.828, 0.167),
    # L65: boundary rules on the sealed 202-row corpus, 8 rules
    "rules": dict(caught=74, violations=74, false_pos=0, compliant=128, rows=202, n_rules=8),
}

COLOR = {"base": "#5E7397", "act": "#9AA8FF", "obs": "#4FD8C4", "warn": "#F6B95C",
         "text": "#EAF0FA", "muted": "#A9B8D0", "hair": "#24324F", "surface": "#0F1729", "raised": "#16213A"}


def esc(s: str) -> str:
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- SVG helpers
def t(x, y, s, size=20, cls="", anchor="start", weight=400, fill=None):
    f = f' fill="{fill}"' if fill else ""
    c = f' class="{cls}"' if cls else ""
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}"{c}{f}>{esc(s)}</text>'


def box(x, y, w, h, stroke, fill=COLOR["surface"], dash=False, r=18, sw=2):
    d = ' stroke-dasharray="8 6"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>'


def arrow(x1, y1, x2, y2, color=COLOR["muted"], dash=False):
    d = ' stroke-dasharray="6 6"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="2.5"{d} '
            f'marker-end="url(#ah)"/>')


DEFS = (f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{COLOR["muted"]}"/></marker></defs>')


def svg(vw, vh, body, label, ledger):
    # .sv scrolls sideways at phone width, where a 16:9 diagram would be too small to read
    return (f'<div class="sv" tabindex="0" role="region" aria-label="Figure: {esc(label.split(":")[0])}">'
            f'<svg class="d" viewBox="0 0 {vw} {vh}" role="img" aria-label="{esc(label)}" data-ledger="{ledger}" '
            f'preserveAspectRatio="xMidYMin meet" style="--vw:{vw}">{DEFS}{body}</svg></div>')


def node(x, y, w, h, title, lines, stroke, dash=False, title_size=26, sub_size=19):
    out = [box(x, y, w, h, stroke, dash=dash), t(x + 20, y + 40, title, title_size, weight=700)]
    for i, ln in enumerate(lines):
        out.append(t(x + 20, y + 72 + i * (sub_size + 7), ln, sub_size, "m"))
    return "".join(out)


def hbars(rows, vw, label_w, title, sub, fmt, ledger, aria, top=0):
    """Horizontal bars, 0..max on a common axis. rows: (label, value, max, color_key, chance|None)."""
    bar_x, bar_w, rh = label_w, vw - label_w - 120, 62
    out = [t(0, top + 26, title, 24, weight=700), t(0, top + 56, sub, 18, "m")]
    y0 = top + 90
    for i, (lab, v, mx, ck, chance) in enumerate(rows):
        y = y0 + i * rh
        frac = v / mx
        out += [t(0, y + 30, lab, 20),
                f'<rect x="{bar_x}" y="{y + 8}" width="{bar_w}" height="34" rx="8" fill="{COLOR["raised"]}"/>',
                f'<rect x="{bar_x}" y="{y + 8}" width="{max(bar_w * frac, 4):.1f}" height="34" rx="8" fill="{COLOR[ck]}"/>',
                t(bar_x + bar_w + 14, y + 33, fmt(v, mx), 22, weight=700)]
        if chance is not None:
            cx = bar_x + bar_w * chance
            out.append(f'<line x1="{cx:.1f}" y1="{y + 2}" x2="{cx:.1f}" y2="{y + 48}" stroke="{COLOR["warn"]}" stroke-width="4"/>')
    return out, y0 + len(rows) * rh


# ---------------------------------------------------------------- figures
def fig_week():
    out = [t(0, 26, "YOUR WEEK CHANGES", 18, "m mono"), t(860, 26, "A GENERIC REMINDER DOES NOT", 18, "m mono")]
    weeks = [("Week 1", ["Forgetting gets", "in the way"]), ("Week 2", ["Weekends are", "harder"]), ("Week 3", ["Mood drops;", "wants to reach out"])]
    for i, (wk, lines) in enumerate(weeks):
        x = i * 262
        out += [box(x, 50, 240, 300, COLOR["warn"]), t(x + 22, 92, wk, 24, weight=700),
                f'<circle cx="{x + 42}" cy="150" r="18" fill="{COLOR["warn"]}" opacity=".9"/>']
        out += [t(x + 22, 216 + j * 30, ln, 22) for j, ln in enumerate(lines)]
    out.append(arrow(790, 200, 850, 200))
    for j in range(3):
        y = 50 + j * 104
        out += [box(860, y, 580, 84, COLOR["base"], r=42), t(900, y + 52, "“Time for your daily walk!”", 24),
                f'<circle cx="{1392}" cy="{y + 42}" r="22" fill="none" stroke="{COLOR["muted"]}" stroke-width="2"/>',
                t(1392, y + 51, "?", 26, "m", "middle", 700)]
    out.append(t(860, 386, "Same words every week, and no reason given.", 21, "m"))
    return svg(1440, 400, "".join(out), "Diagram: a member's barrier changes each week (forgetting, weekends, mood) while a generic reminder repeats the same words with no reason.", "L80")


def fig_flow():
    steps = [("Check-in", ["one sentence"], "act"), ("Review", ["confirm or correct"], "act"),
             ("Passport", ["every value sourced"], "act"), ("Inclinations", ["what weighs most"], "act"),
             ("Next step", ["choose · defer · ask"], "act"), ("A person", ["pain or crisis"], "warn")]
    w, g = 212, 33.6
    out = []
    for i, (h_, sub, ck) in enumerate(steps):
        x = i * (w + g)
        out.append(node(x, 10, w, 108, h_, sub, COLOR[ck], dash=(ck == "warn"), title_size=25, sub_size=18))
        if i < len(steps) - 1:
            out.append(arrow(x + w + 3, 64, x + w + g - 3, 64))
    return svg(1440, 128, "".join(out), "Member flow: check-in, review, passport, Inclinations, next step, and a hand-off to a person after pain or crisis.", "L5 L24 L47 L80")


def fig_arch():
    out = [t(0, 24, "LIVE · EVERY CHECK-IN · FIXED RULES, NO MODEL CALL", 18, "m mono", fill=COLOR["act"])]
    live = [("Check-in", ["sentence or 1 of 4", "bundled files"]), ("Safety checks", ["crisis language,", "personal data"]),
            ("Proposals", ["value + its words", "+ method"]), ("Your review", ["confirm, correct", "or discard"]),
            ("Memory", ["confirmed only,", "append-only"]), ("Passport", ["+ next step, checked", "by boundary rules"])]
    w, g = 210, 36
    for i, (h_, sub) in enumerate(live):
        x = i * (w + g)
        out.append(node(x, 44, w, 132, h_, sub, COLOR["act"], title_size=24, sub_size=18))
        if i < len(live) - 1:
            out.append(arrow(x + w + 3, 110, x + w + g - 3, 110))
    out.append(t(0, 282, "OFFLINE · TRAINING AND EVALUATION", 18, "m mono", fill=COLOR["obs"]))
    off = [("Synthetic members", ["175 members, fixed seeds"]), ("Training", ["SFT · DPO · reward model", "· GRPO"]),
           ("Evaluation", ["141 held-out prompts,", "150 simulated episodes"]), ("Versioned results", ["run id + data hash,", "read by the console"])]
    w2, g2 = 330, 40
    for i, (h_, sub) in enumerate(off):
        x = i * (w2 + g2)
        out.append(node(x, 302, w2, 126, h_, sub, COLOR["obs"], dash=True, title_size=24, sub_size=18))
        if i < len(off) - 1:
            out.append(arrow(x + w2 + 3, 365, x + w2 + g2 - 3, 365))
    # the passport's Inclinations read the trained reward model
    out.append(arrow(1335, 302, 1335, 180, COLOR["obs"], dash=True))
    out.append(t(1320, 250, "Inclinations read the reward model", 18, "m", "end"))
    return svg(1440, 432, "".join(out), "Architecture: the live path runs check-in, safety checks, proposals, review, memory and passport with fixed rules; an offline lane trains and evaluates on synthetic members and publishes versioned results.", "L6 L10 L11 L24 L55 L57 L59 L66 L67 L76 L80")


def fig_memory():
    out = []
    nodes = [("Proposal", ["value + its words,", "method, confidence"], "act"), ("Your review", ["confirm, correct or", "discard, all at once"], "warn"),
             ("Memory", ["confirmed values only,", "append-only"], "act"), ("Passport", ["shown as recorded,", "never as a score"], "act")]
    w, g = 200, 34
    for i, (h_, sub, ck) in enumerate(nodes):
        x = i * (w + g)
        out.append(node(x, 0, w, 130, h_, sub, COLOR[ck], title_size=24, sub_size=17))
        if i < len(nodes) - 1:
            out.append(arrow(x + w + 3, 65, x + w + g - 3, 65))
    out += [box(0, 168, 902, 262, COLOR["obs"], fill="#0B1322", dash=True), t(24, 206, "HONESTY LAYER", 18, "mono", fill=COLOR["obs"], weight=700)]
    chips = ["Fresh within 14 days, or withheld", "A range is shown, never judged", "5-step evidence thread per card",
             "Crisis language → a person", "Personal data → refused whole", "Next step passes boundary rules"]
    for i, c in enumerate(chips):
        x = 24 + (i % 2) * 438
        y = 228 + (i // 2) * 64
        out += [box(x, y, 418, 50, COLOR["hair"], fill=COLOR["surface"], r=25, sw=1.5),
                f'<circle cx="{x + 26}" cy="{y + 25}" r="7" fill="{COLOR["obs"]}"/>', t(x + 46, y + 32, c, 19)]
    return svg(902, 432, "".join(out), "Memory path: proposal, your review, append-only memory, passport; under it the honesty layer: freshness within 14 days or withheld, ranges never judged, a 5-step evidence thread, crisis hand-off, personal data refused, next step checked by boundary rules.", "L5 L10 L11 L20 L21 L22 L23 L24 L47 L48")


def fig_reward():
    out = [node(0, 0, 330, 104, "Question library (Jev)", ["7 short check-in questions"], COLOR["act"], title_size=23, sub_size=18),
           arrow(334, 52, 384, 52),
           node(388, 0, 312, 104, "Hidden traits", ["barrier, rhythm, motivation…"], COLOR["act"], title_size=23, sub_size=18),
           arrow(350, 108, 350, 146),
           box(0, 150, 700, 168, COLOR["obs"]), t(20, 188, "Interpretable reward model", 23, weight=700),
           t(20, 216, "every score is a sum of named terms that add up exactly", 17, "m")]
    # stacked term bar: illustrative proportions, no values
    out += [f'<rect x="20" y="236" width="300" height="38" rx="8" fill="{COLOR["obs"]}"/>',
            f'<rect x="324" y="236" width="190" height="38" rx="8" fill="{COLOR["act"]}"/>',
            t(536, 263, "= score", 22, weight=700),
            t(20, 302, "who the member is", 17, "m"), t(324, 302, "+ what the message adds", 17, "m"),
            arrow(350, 322, 350, 356),
            node(0, 360, 700, 72, "GRPO policy", [], COLOR["act"], title_size=23),
            t(200, 400, "learns which of 7 message types to send", 18, "m")]
    return svg(700, 434, "".join(out), "Pipeline: a 7-question library recovers hidden traits; an interpretable reward model scores a message as member terms plus message terms; a GRPO policy learns which of 7 message types to send.", "L74 L76 L79")


def fig_jev():
    rows = [(lab, v, 1.0, "act", ch) for lab, v, ch in DATA["jev"]]
    out, y = hbars(rows, 700, 330, "Trait recovery from 7 answers", "58 held-out simulated members · orange tick = chance",
                   lambda v, m: f"{v:.0%}", "L75", "")
    a, ch = DATA["rm_top"]
    y += 14
    out += [f'<line x1="0" y1="{y}" x2="700" y2="{y}" stroke="{COLOR["hair"]}" stroke-width="2"/>']
    r2, _ = hbars([("Reward model: top message type", a, 1.0, "obs", ch)], 700, 330, "", "", lambda v, m: f"{v:.0%}", "L78", "", top=y - 76)
    out += r2[2:]
    return svg(700, y + 46, "".join(out), "Bar chart: from 7 answers, hidden traits are recovered 76 to 91 percent of the time against chance of 17 to 33 percent; the reward model's top message type matches the simulator's for 83 percent, chance 17 percent.", "L75 L78")


def fig_boundary():
    rows = [(lab, n, d, ck, None) for lab, n, d, ck in DATA["boundary"]]
    out, y = hbars(rows, 700, 250, "Boundary pass rate", "prompts passed, of 141 held-out prompts",
                   lambda v, m: f"{int(v)} of {int(m)}", "L60", "")
    return svg(700, y + 8, "".join(out), "Bar chart: boundary pass rate on 141 held-out prompts: base model 45, fine-tuned 141, preference-tuned 141.", "L59 L60")


def fig_adherence():
    rows = [(lab, v, 1.0, ck, None) for lab, v, ck in DATA["adherence"]]
    out, y = hbars(rows, 700, 250, "Mean simulated adherence", "150 episodes of 14 days · 0 to 1",
                   lambda v, m: f"{v:.3f}", "L66 L79", "")
    return svg(700, y + 8, "".join(out), "Bar chart: mean simulated adherence: no support 0.637, random 0.719, always problem-solving 0.833, learned policy 0.840.", "L66 L79")


def shot(name, cap_b, cap, alt):
    return (f'<figure class="shot"><div class="img"><img src="{ASSET}screens/{name}.jpg" alt="{esc(alt)}" loading="eager"></div>'
            f'<figcaption><b>{esc(cap_b)}</b> · {esc(cap)}</figcaption></figure>')


def glyph(kind, color):
    paths = {
        "see": f'<circle cx="32" cy="32" r="12" fill="none" stroke="{color}" stroke-width="4"/><path d="M4 32 C16 12 48 12 60 32 C48 52 16 52 4 32Z" fill="none" stroke="{color}" stroke-width="4"/>',
        "correct": f'<path d="M12 34 L26 48 L54 16" fill="none" stroke="{color}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
        "act": f'<path d="M10 32 H50 M36 16 L52 32 L36 48" fill="none" stroke="{color}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
    }
    return f'<svg viewBox="0 0 64 64" width="56" height="56" aria-hidden="true" style="width:calc(56 * var(--u));height:calc(56 * var(--u))">{paths[kind]}</svg>'


# ---------------------------------------------------------------- slides
SECTIONS = [("problem", "Problem"), ("design", "Design"), ("technical", "Technical"), ("next", "Next")]


def slides():
    R = DATA["rules"]
    S = []

    def add(section, h, lead, fig, ledger, notes, fig_cls="", heading="h2"):
        S.append(dict(section=section, h=h, lead=lead, fig=fig, ledger=ledger, notes=notes, fig_cls=fig_cls, heading=heading))

    add("problem", "Healthy routines break when the week changes.",
        "For people keeping a healthy routine going. Barriers shift week to week, and generic reminders neither know you nor explain why.",
        fig_week(),
        "L37 L41 L71 L80",
        "Who it is for and what fails today. Framing follows the challenge statement (L37, L41); team and aim as the owner supplied them (L71). "
        "The three barriers are the kinds the Inclinations section names (L80). No statistic about the problem: the pack has no sourced figure.",
        heading="h1")
    add("problem", "A record you can see, correct and act on.",
        "Clinical Human Clone turns a one-line check-in into a reviewed health record and one bounded next step.",
        f'<div class="card">{glyph("see", COLOR["obs"])}<p class="big c-obs">See</p><p>Every value shows its source, age and method.</p><figure class="shot"><div class="img"><img src="{ASSET}screens/passport.jpg" alt="Passport card: Heart rate 63 per minute with source, age and method."></div></figure></div>'
        f'<div class="card">{glyph("correct", COLOR["act"])}<p class="big c-act">Correct</p><p>Nothing is saved until you review it.</p><figure class="shot"><div class="img"><img src="{ASSET}screens/review.jpg" alt="Review screen: Sleep duration 6 h with Confirm, Correct, Discard."></div></figure></div>'
        f'<div class="card">{glyph("act", COLOR["warn"])}<p class="big c-warn">Act</p><p>One next step with its reason, or a person.</p><figure class="shot"><div class="img"><img src="{ASSET}screens/next.jpg" alt="Suggested next step with its reason and Choose, Defer, Ask a professional."></div></figure></div>',
        "L5 L21 L24 L71", "Why it matters: the aim is a record the person can see, correct and act on (L71). Built: provenance on every card (L21), "
        "nothing saved before review (L5), a next step that passes the boundary rules or routes to a person (L24).", "cols-3")
    add("design", "One sentence in, a reviewed record out.",
        "Check in, review, see it in the passport, learn what helps, then choose a next step. Pain or crisis goes to a person.",
        fig_flow() + '<div class="fig cols-2" style="margin-top:0">'
        + shot("today", "Check-in", "one sentence, or one of 4 bundled files", "Check-in screen: What matters today, Rowan? with a one-sentence text box.")
        + shot("review", "Review", "3 values from one sentence, each with its words", "Review screen: Sleep duration 6 h, quoted from 'slept 6 hours', with Confirm, Correct, Discard.")
        + "</div>",
        "L5 L24 L45 L47 L55 L80", "The member journey on the hosted build: /#today, /#review. One four-part sentence gave 3 values, each with its words (L45). "
        "Nothing reaches memory before the review (L5). File check-in accepts 4 bundled files (L55). Pain routes the next step to a person (L24); crisis gets a fixed hand-off (L47).",
        "rows-flow")
    add("design", "Every value shows where it came from.",
        "Each card names its source, age and method. A 5-step evidence thread traces it. Stale values are withheld, not guessed.",
        shot("passport", "Passport card", "observed, ready, range sourced", "Passport card: Heart rate 63 per minute, observed, ready, reference range with source.")
        + shot("evidence", "Evidence thread", "5 steps, check-in to card", "Evidence thread with 5 steps: source, observation, memory, explanation, evaluation.")
        + shot("withheld", "Withheld", "no value in 14 days, no number", "A withheld card that shows no number because the last value is older than 14 days."),
        "L20 L21 L22 L50 L51", "Passport on the hosted build (/#passport). Every card has a 5-step evidence thread (L21); ready only if at most 14 days old, else withheld with no number (L22, L51). "
        "A range sits beside the value and is never interpreted (L20, L50).", "cols-3")
    add("design", "Next steps fit the person, and reach a person when it matters.",
        "Inclinations show what weighs most and link each next step to it. Pain or crisis language routes to a human.",
        shot("inclinations", "Inclinations", "what weighs most; each next step linked to it", "Inclinations: forgetting weighs strongly; two next steps, each with its reason and the answer it links to.")
        + '<div class="stack">'
        + shot("next", "Next step", "choose, defer or ask a professional", "Suggested next step after a pain report, with Choose, Defer and Ask a professional.")
        + shot("handoff", "Crisis", "a fixed hand-off to a person; nothing saved", "Crisis hand-off message pointing to a person.")
        + "</div>",
        "L24 L47 L53 L80", "Inclinations: the answers that weigh most, and up to three next steps each linked to one, with its reason (L80). "
        "The next step passes the boundary rules and offers choose, defer or ask a professional (L24, L53). Crisis language gets a fixed hand-off and is not extracted (L47).",
        "cols-21")
    add("technical", "Rules run live; learning stays offline.",
        "The check-in loop uses fixed rules with no model call. Training and evaluation run offline and publish versioned results.",
        fig_arch(),
        "L6 L10 L11 L24 L55 L57 L59 L66 L67 L76 L80",
        "Live: deterministic rules, no model call at runtime (L6); crisis check before extraction (L10); personal-data refusal (L11); next step through the boundary rules (L24); 4 bundled files (L55). "
        "Offline: 175 synthetic members (L67), SFT and DPO (L57), 141 held-out prompts (L59), 150 simulated episodes (L66). The passport's Inclinations read the reward model (L76, L80). "
        "Versioning by run id and data hash: technical appendix §4.")
    add("technical", "Memory keeps only what the person confirmed.",
        "Proposals wait for review. Memory is append-only. The honesty layer shows ranges without verdicts and withholds what it cannot support.",
        fig_memory()
        + f'<div class="stack"><div class="card"><p class="big c-obs">{R["caught"]} / {R["violations"]}</p><p>labelled rule violations caught by the boundary rules</p></div>'
        f'<div class="card"><p class="big c-act">{R["false_pos"]} / {R["compliant"]}</p><p>false alarms on compliant rows</p></div>'
        f'<p class="lead" style="margin:0;font-size:calc(19 * var(--u))">{R["rows"]}-row sealed test set, {R["n_rules"]} rules.</p></div>',
        "L5 L10 L11 L20 L21 L22 L23 L24 L47 L48 L65",
        "Memory: only the review commits, all-or-nothing (L5); a confirmed value is shown as recorded, never as a score (L23). Honesty layer: 14-day freshness (L22), ranges never interpreted (L20), "
        "5-step thread (L21), crisis hand-off (L10, L47), personal data refused whole (L11, L48), boundary rules on the next step (L24). "
        "Boundary rules: 74 of 74 labelled violations, 0 false positives on 128 compliant rows of a sealed 202-row corpus, 8 rules (L65).",
        "cols-12")
    add("technical", "7 questions, a readable reward, a learned policy.",
        "Short answers reveal what drives each member. The reward model scores messages as named terms; GRPO learns which message to send.",
        fig_reward() + fig_jev(),
        "L74 L75 L76 L78 L79",
        "Question library: 7 questions (L74). Per-trait recovery on 58 held-out simulated members, 76–91% against chance 17–33% (L75; per-trait values from metrics.json, arm jev). "
        "Reward model: every score is a sum of named terms that add up exactly (L76); top message type matches the simulator's for 83%, chance 17% (L78). "
        "GRPO picks among 7 message types (L79; technical appendix §4a).", "cols-2")
    add("technical", "Both trained stages pass every boundary check; the learned policy edges ahead.",
        "Boundary pass rate on 141 held-out prompts, and mean simulated adherence across 150 episodes against scripted approaches.",
        fig_boundary() + fig_adherence(),
        "L59 L60 L66 L79",
        "Boundary pass rate: base 45 of 141, SFT and DPO 141 of 141 (L60) on 141 held-out prompts, 51 check-in and 90 probe (L59). "
        "Adherence: 0.637 no support, 0.719 random, 0.833 always problem-solving (L66); GRPO 0.840, 0 rule violations (L79).", "cols-2")
    add("next", "Next: a clinical reviewer, a consented pilot, a measured result.",
        "The prototype runs today. Try the journey, then read the code.",
        '<ol class="steps"><li>Name a clinical reviewer and the intended use</li><li>Close the 12 governance gates for real input</li>'
        '<li>Run a consented pilot with a pre-registered measure</li><li>Grow the learned policy beyond message type</li></ol>'
        f'<div class="links"><a class="link" href="{DEMO_URL}"><span>Live prototype</span><b>{esc(DEMO_URL.removeprefix("https://"))}</b></a>'
        f'<a class="link" href="{DECK_URL}"><span>This deck</span><b>{esc(DECK_URL.removeprefix("https://"))}</b></a>'
        f'<a class="link" href="{REPO_URL}"><span>Source</span><b>{esc(REPO_URL.removeprefix("https://"))}</b></a></div>',
        "L56 L73 L79 L81",
        "Runs today: hosted build, SC1 smoke 9 of 9 (L81). Real input needs the 12 governance gates closed (L56). No clinical evidence yet, hence the reviewer and pilot (L73). "
        "The learned policy chooses a message type only (L79).", "cols-12")
    return S


def render() -> str:
    S = slides()
    n = len(S)
    first = {}
    for i, s in enumerate(S, 1):
        first.setdefault(s["section"], i)
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width, initial-scale=1">'
             '<title>Clinical Human Clone · FHDIC submission deck</title>'
             '<meta name="description" content="Clinical Human Clone: problem, design and technical solution, with the live prototype.">'
             f'<link rel="stylesheet" href="{ASSET}deck.css"></head><body>'
             '<a class="skip" href="#stage">Skip to the slides</a>'
             '<main id="stage" class="stage" aria-roledescription="slide deck" aria-label="Clinical Human Clone submission deck">']
    for i, s in enumerate(S, 1):
        sec = dict(SECTIONS)[s["section"]]
        fig_style = ' style="grid-template-rows:auto 1fr"' if s["fig_cls"] == "rows-flow" else ""
        fig_cls = "" if s["fig_cls"] == "rows-flow" else s["fig_cls"]
        hd = s["heading"]
        parts.append(
            f'<section class="slide s-{s["section"]}" id="s{i}" data-section="{s["section"]}" data-ledger="{s["ledger"]}" '
            f'aria-roledescription="slide" aria-label="{i} of {n}: {esc(sec)}"><div class="frame">'
            f'<div class="top"><span class="kicker"><b>{esc(sec)}</b></span>'
            f'<span class="brand"><span class="orb" aria-hidden="true"></span><span>Clinical Human Clone</span></span></div>'
            f'<{hd}>{esc(s["h"])}</{hd}><p class="lead">{esc(s["lead"])}</p>'
            f'<div class="fig {fig_cls}"{fig_style}>{s["fig"]}</div>'
            f'<div class="foot"><span>Team Syntropy · [Wellness] Sustaining Healthy Behaviors</span><span>{i} / {n}</span></div>'
            f'<aside class="notes" data-ledger="{s["ledger"]}"><p>{esc(s["notes"])}</p><p>Ledger rows: {esc(s["ledger"])} '
            f'(docs/daypart/submission/evidence-ledger.md).</p></aside></div></section>')
    parts.append('</main><div id="progress" class="progress" aria-hidden="true"></div>'
                 '<nav class="nav" aria-label="Deck navigation"><button id="prev" type="button" aria-label="Previous slide">←</button>'
                 '<div class="sections">')
    for key, label in SECTIONS:
        parts.append(f'<a href="#/{first[key]}" data-section="{key}" data-to="{first[key]}" aria-current="false">{label}</a>')
    parts.append('</div><span id="count" class="count" aria-hidden="true"></span>'
                 '<button id="notes-btn" type="button" aria-expanded="false" aria-controls="notes-panel">Notes</button>'
                 '<button id="next" type="button" aria-label="Next slide">→</button></nav>'
                 '<section id="notes-panel" class="notes-panel" hidden aria-label="Speaker notes"><h2>Speaker notes</h2><div id="notes-body"></div></section>'
                 '<div id="live" class="sr" aria-live="polite"></div>'
                 f'<script src="{ASSET}deck.js"></script></body></html>\n')
    return "".join(parts)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "screens").mkdir(exist_ok=True)
    for f in sorted((HERE / "screens").glob("*.jpg")):
        shutil.copy2(f, OUT / "screens" / f.name)
    (OUT / "index.html").write_text(render(), encoding="utf-8")
    print(f"{OUT / 'index.html'}: {len(slides())} slides")
