"""Build the FHDIC web deck (HAC-86, v2 HAC-105) served by the demo app at /deck.

    python docs/daypart/submission/deck/build_web_deck.py

Writes engine/daypart/demo/deck/index.html and copies screens/*.jpg next to it. The CSS, the script and
the vendored font (deck.css, deck.js, fonts/) are hand-written files in the same folder.

Top-down: Problem (2 slides), Design (3), Technical solution (4), Close (1). Every number on a slide is
in DATA below, keyed by the evidence-ledger row it comes from (docs/daypart/submission/evidence-ledger.md);
each slide names its rows in a data-ledger attribute and in its speaker notes, and each chart and stat
names its own. Charts, counters and diagrams are drawn from DATA, so a figure cannot disagree with the
ledger. v2 (HAC-105) is a visual overhaul: aurora and mesh backgrounds, glass bento cards with a pointer
spotlight, animated counters and bars, staggered reveals (deck/CREDITS.md names the 21st components).
Standard library only.
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
    # L21 evidence thread steps; L22 freshness window in days
    "thread_steps": 5, "fresh_days": 14,
}

COLOR = {"base": "var(--c-base)", "act": "var(--c-act)", "obs": "var(--c-obs)", "warn": "var(--c-warn)"}


def esc(s: str) -> str:
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- building blocks
class Seq:
    """Reveal order inside one slide: each call hands out the next stagger step."""

    def __init__(self) -> None:
        self.i = 0

    def __call__(self) -> int:
        self.i += 1
        return self.i


def num(v: float, dec: int = 0, ledger: str = "") -> str:
    """An animated counter. The page carries the final value, so export, print and no-JS read it as is."""
    led = f' data-ledger="{ledger}"' if ledger else ""
    return f'<span class="num" data-to="{v}" data-dec="{dec}"{led}>{v:.{dec}f}</span>'


def card(body: str, d: int, cls: str = "", ledger: str = "", tag: str = "div", extra: str = "") -> str:
    led = f' data-ledger="{ledger}"' if ledger else ""
    return f'<{tag} class="card glow rv {cls}" style="--d:{d}"{led}{extra}>{body}</{tag}>'


def shot(name: str, alt: str) -> str:
    return f'<div class="img"><img src="{ASSET}screens/{name}.jpg" alt="{esc(alt)}" loading="eager"></div>'


def label(text: str, tone: str = "") -> str:
    return f'<p class="eyebrow {tone}">{esc(text)}</p>'


def shot_card(name: str, title: str, cap: str, alt: str, d: int, cls: str = "", tone: str = "act", stat: str = "") -> str:
    head = f'<div class="ch"><p class="eyebrow t-{tone}">{esc(title)}</p>{stat}</div><p class="cap">{esc(cap)}</p>'
    return card(head + shot(name, alt), d, f"shotcard {cls}")


def glyph(kind: str) -> str:
    paths = {
        "see": '<circle cx="32" cy="32" r="11" fill="none" stroke="currentColor" stroke-width="4"/><path d="M4 32 C16 12 48 12 60 32 C48 52 16 52 4 32Z" fill="none" stroke="currentColor" stroke-width="4"/>',
        "correct": '<path d="M12 34 L26 48 L54 16" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
        "act": '<path d="M10 32 H50 M36 16 L52 32 L36 48" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>',
    }
    return f'<span class="glyph" aria-hidden="true"><svg viewBox="0 0 64 64">{paths[kind]}</svg></span>'


def bars(rows, title: str, sub: str, ledger: str, aria: str, d: int, cls: str = "") -> str:
    """Horizontal bars on a common 0..max axis. rows: (label, value, max, color_key, chance|None, text)."""
    out = [f'<figure class="chart {cls}" data-ledger="{ledger}" role="img" aria-label="{esc(aria)}">'
           f'<figcaption><b>{esc(title)}</b><span>{esc(sub)}</span></figcaption><div class="rows">']
    for i, (lab, v, mx, ck, chance, text) in enumerate(rows):
        tick = f'<em style="--ch:{chance:.3f}"></em>' if chance is not None else ""
        out.append(f'<div class="row" style="--r:{i}"><span class="lab">{esc(lab)}</span>'
                   f'<span class="track"><i style="--v:{v / mx:.4f};--c:{COLOR[ck]}"></i>{tick}</span>'
                   f'<span class="val">{esc(text)}</span></div>')
    out.append("</div></figure>")
    return card("".join(out), d, "chartcard")


def node(title: str, sub: str, tone: str = "act", d: int = 0) -> str:
    return (f'<li class="node t-{tone}" style="--n:{d}"><b>{esc(title)}</b><span>{esc(sub)}</span></li>')


# ---------------------------------------------------------------- figures
def fig_week(q: Seq) -> str:
    weeks = [("Week 1", "Forgetting gets in the way"), ("Week 2", "Weekends are harder"), ("Week 3", "Mood drops; wants to reach out")]
    cells = "".join(card(f'<p class="eyebrow t-warn">{esc(w)}</p><span class="wk-n" aria-hidden="true">{k:02d}</span><p class="say">{esc(s)}</p>', q(), "week")
                    for k, (w, s) in enumerate(weeks, 1))
    bubbles = "".join(f'<li style="--n:{i}"><span>“Time for your daily walk!”</span><b aria-hidden="true">?</b></li>' for i in range(3))
    remind = card(f'<p class="eyebrow">A generic reminder</p><ul class="bubbles" aria-label="The same reminder, three weeks running">{bubbles}</ul>'
                  '<p class="cap">Same words every week, and no reason given.</p>', q(), "remind")
    return (f'<div class="fig b-week" data-ledger="L80" role="group" aria-label="A member\'s barrier changes each week while a generic reminder repeats">'
            f'<div class="weeks">{cells}</div><span class="vs rv" style="--d:{q()}" aria-hidden="true">→</span>{remind}</div>')


def fig_pillars(q: Seq) -> str:
    items = [("see", "obs", "See", "Every value shows its source, age and method.", "passport",
              "Passport card: Heart rate 63 per minute with source, age and method."),
             ("correct", "act", "Correct", "Nothing is saved until you review it.", "review",
              "Review screen: Sleep duration 6 h with Confirm, Correct, Discard."),
             ("act", "warn", "Act", "One next step with its reason, or a person.", "next",
              "Suggested next step with its reason and Choose, Defer, Ask a professional.")]
    cells = "".join(card(f'<div class="ph t-{tone}">{glyph(g)}<p class="word">{esc(w)}</p></div><p class="cap">{esc(c)}</p>{shot(img, alt)}', q(), "pillar")
                    for g, tone, w, c, img, alt in items)
    return f'<div class="fig b-3">{cells}</div>'


def fig_flow(q: Seq) -> str:
    steps = [("Check-in", "one sentence", "act"), ("Review", "confirm or correct", "act"), ("Passport", "every value sourced", "act"),
             ("Inclinations", "what weighs most", "act"), ("Next step", "choose · defer · ask", "act"), ("A person", "pain or crisis", "warn")]
    rail = card('<ol class="rail" aria-label="Member flow">' + "".join(node(h, s, t, i) for i, (h, s, t) in enumerate(steps)) + "</ol>",
                q(), "railcard", ledger="L5 L24 L47 L80")
    return (f'<div class="fig b-flow">{rail}'
            + shot_card("today", "Check-in", "One sentence, or one of 4 bundled files.",
                        "Check-in screen: What matters today, Rowan? with a one-sentence text box.", q())
            + shot_card("review", "Review", "3 values from one sentence, each with its words.",
                        "Review screen: Sleep duration 6 h, quoted from 'slept 6 hours', with Confirm, Correct, Discard.", q())
            + "</div>")


def fig_passport(q: Seq) -> str:
    stat_steps = f'<p class="stat t-act" data-ledger="L21">{num(DATA["thread_steps"])}<small>steps</small></p>'
    stat_days = f'<p class="stat t-warn" data-ledger="L22">{num(DATA["fresh_days"])}<small>days</small></p>'
    return ('<div class="fig b-pass">'
            + shot_card("passport", "Health Clone Passport", "Observed, ready, range sourced.",
                        "Passport card: Heart rate 63 per minute, observed, ready, reference range with source.", q(), "tall", "obs")
            + shot_card("evidence", "Evidence thread", "Check-in to card, every step.",
                        "Evidence thread with 5 steps: source, observation, memory, explanation, evaluation.", q(), "", "act", stat_steps)
            + shot_card("withheld", "Withheld", "Too old to show, so no number.",
                        "A withheld card that shows no number because the last value is older than 14 days.", q(), "", "warn", stat_days)
            + "</div>")


def fig_incl(q: Seq) -> str:
    return ('<div class="fig b-incl">'
            + shot_card("inclinations", "Inclinations", "What weighs most; each next step linked to it.",
                        "Inclinations: forgetting weighs strongly; two next steps, each with its reason and the answer it links to.", q(), "tall", "obs")
            + shot_card("next", "Next step", "Choose, defer or ask a professional.",
                        "Suggested next step after a pain report, with Choose, Defer and Ask a professional.", q())
            + shot_card("handoff", "Crisis", "A fixed hand-off to a person; nothing saved.",
                        "Crisis hand-off message pointing to a person.", q(), "", "warn")
            + "</div>")


def fig_arch(q: Seq) -> str:
    live = [("Check-in", "sentence or 1 of 4 bundled files"), ("Safety checks", "crisis language, personal data"),
            ("Proposals", "value + its words + method"), ("Your review", "confirm, correct or discard"),
            ("Memory", "confirmed only, append-only"), ("Passport", "+ next step, checked by boundary rules")]
    off = [("Synthetic members", "175 members, fixed seeds"), ("Training", "SFT · DPO · reward model · GRPO"),
           ("Evaluation", "141 held-out prompts, 150 simulated episodes"), ("Versioned results", "run id + data hash, read by the console")]
    lane_live = card('<p class="eyebrow t-act">Live · every check-in · fixed rules, no model call</p>'
                     '<ol class="lane">' + "".join(node(h, s, "act", i) for i, (h, s) in enumerate(live)) + "</ol>",
                     q(), "lanecard live", ledger="L6 L10 L11 L24 L55")
    lane_off = card('<p class="eyebrow t-obs">Offline · training and evaluation</p>'
                    '<ol class="lane">' + "".join(node(h, s, "obs", i) for i, (h, s) in enumerate(off)) + "</ol>",
                    q(), "lanecard off", ledger="L57 L59 L66 L67")
    link = f'<p class="bridge rv" style="--d:{q()}" data-ledger="L76 L80"><span aria-hidden="true">↑</span> Inclinations read the reward model</p>'
    return (f'<div class="fig b-arch" role="group" aria-label="Architecture: a live lane of fixed rules and an offline lane that trains and evaluates">'
            f'{lane_live}{link}{lane_off}</div>')


def fig_memory(q: Seq) -> str:
    R = DATA["rules"]
    pipe = [("Proposal", "value + its words, method, confidence", "act"), ("Your review", "confirm, correct or discard, all at once", "warn"),
            ("Memory", "confirmed values only, append-only", "act"), ("Passport", "shown as recorded, never as a score", "act")]
    chips = ["Fresh within 14 days, or withheld", "A range is shown, never judged", "5-step evidence thread per card",
             "Crisis language → a person", "Personal data → refused whole", "Next step passes boundary rules"]
    path = card('<p class="eyebrow">Memory path</p><ol class="lane four">' + "".join(node(h, s, t, i) for i, (h, s, t) in enumerate(pipe)) + "</ol>",
                q(), "mempath", ledger="L5 L23")
    honesty = card('<p class="eyebrow t-obs">Honesty layer</p><ul class="chips">'
                   + "".join(f'<li style="--n:{i}">{esc(c)}</li>' for i, c in enumerate(chips)) + "</ul>",
                   q(), "honesty", ledger="L10 L11 L20 L21 L22 L24 L47 L48")
    s1 = card(f'<p class="eyebrow t-obs">Boundary rules</p><p class="big t-obs">{num(R["caught"])}<i>/</i>{num(R["violations"])}</p><p class="cap">labelled rule violations caught</p>',
              q(), "statcard", ledger="L65")
    s2 = card(f'<p class="eyebrow t-act">Compliant rows</p><p class="big t-act">{num(R["false_pos"])}<i>/</i>{num(R["compliant"])}</p><p class="cap">false alarms on compliant rows</p>',
              q(), "statcard", ledger="L65")
    foot = f'<p class="note rv" style="--d:{q()}">{R["rows"]}-row sealed test set, {R["n_rules"]} rules.</p>'
    return f'<div class="fig b-mem">{path}{honesty}<div class="stats">{s1}{s2}{foot}</div></div>'


def fig_reward(q: Seq) -> str:
    a, ch = DATA["rm_top"]
    pipe = card('<ol class="vpipe">'
                + node("Question library (Jev)", "7 short check-in questions", "act", 0)
                + node("Hidden traits", "barrier, rhythm, motivation…", "act", 1)
                + '<li class="node t-obs rm" style="--n:2"><b>Interpretable reward model</b><span>every score is a sum of named terms that add up exactly</span>'
                  '<span class="terms" aria-hidden="true"><i class="a">who the member is</i><i class="b">+ what the message adds</i><i class="eq">= score</i></span></li>'
                + node("GRPO policy", "learns which of 7 message types to send", "act", 3)
                + "</ol>", q(), "pipecard", ledger="L74 L76 L79")
    rows = [(lab, v, 1.0, "act", c, f"{v:.0%}") for lab, v, c in DATA["jev"]]
    chart = bars(rows, "Trait recovery from 7 answers", "58 held-out simulated members · tick = chance", "L75",
                 "Bar chart: from 7 answers, hidden traits are recovered 76 to 91 percent of the time against chance of 17 to 33 percent.", q())
    rm = card(f'<p class="big t-obs">{num(round(a * 100))}<i>%</i></p><p class="cap">reward model’s top message type matches the simulator’s · chance {ch:.0%}</p>',
              q(), "statcard wide", ledger="L78")
    return f'<div class="fig b-rew">{pipe}<div class="col">{chart}{rm}</div></div>'


def fig_results(q: Seq) -> str:
    b = DATA["boundary"]
    ad = DATA["adherence"]
    hero_b = card(f'<p class="eyebrow t-obs">Trained stages, boundary pass</p><p class="hero t-obs">{num(b[1][1])}<i>/</i>{b[1][2]}</p>'
                  f'<p class="cap">base model {b[0][1]} of {b[0][2]}</p>', q(), "herocard", ledger="L60")
    rows_b = [(lab, n, d, ck, None, f"{n} of {d}") for lab, n, d, ck in b]
    chart_b = bars(rows_b, "Boundary pass rate", "prompts passed, of 141 held-out prompts", "L59 L60",
                   "Bar chart: boundary pass rate on 141 held-out prompts: base model 45, fine-tuned 141, preference-tuned 141.", q())
    hero_a = card(f'<p class="eyebrow t-obs">Learned policy, mean adherence</p><p class="hero t-obs">{num(ad[3][1], 3)}</p>'
                  f'<p class="cap">best scripted approach {ad[2][1]:.3f}</p>', q(), "herocard", ledger="L66 L79")
    rows_a = [(lab, v, 1.0, ck, None, f"{v:.3f}") for lab, v, ck in ad]
    chart_a = bars(rows_a, "Mean simulated adherence", "150 episodes of 14 days · 0 to 1", "L66 L79",
                   "Bar chart: mean simulated adherence: no support 0.637, random 0.719, always problem-solving 0.833, learned policy 0.840.", q())
    return f'<div class="fig b-res"><div class="col">{hero_b}{chart_b}</div><div class="col">{hero_a}{chart_a}</div></div>'


def fig_close(q: Seq) -> str:
    steps = ["Name a clinical reviewer and the intended use", "Close the 12 governance gates for real input",
             "Run a consented pilot with a pre-registered measure", "Grow the learned policy beyond message type"]
    ol = card('<p class="eyebrow">Next</p><ol class="steps">' + "".join(f'<li style="--n:{i}">{esc(s)}</li>' for i, s in enumerate(steps)) + "</ol>",
              q(), "stepcard", ledger="L56 L73 L79")
    links = [(DEMO_URL, "Live prototype"), (DECK_URL, "This deck"), (REPO_URL, "Source")]
    ls = "".join(f'<a class="link glow rv" style="--d:{q()}" href="{u}"><span>{esc(k)}</span><b>{esc(u.removeprefix("https://"))}</b><i aria-hidden="true">↗</i></a>'
                 for u, k in links)
    return f'<div class="fig b-close">{ol}<div class="links">{ls}</div></div>'


# ---------------------------------------------------------------- slides
SECTIONS = [("problem", "Problem"), ("design", "Design"), ("technical", "Technical"), ("next", "Next")]


def slides():
    S = []

    def add(section, h, lead, fig, ledger, notes, heading="h2", bg="mesh"):
        S.append(dict(section=section, h=h, lead=lead, fig=fig, ledger=ledger, notes=notes, heading=heading, bg=bg))

    add("problem", "Healthy routines break when the week changes.",
        "For people keeping a healthy routine going. Barriers shift week to week, and generic reminders neither know you nor explain why.",
        fig_week, "L37 L41 L71 L80",
        "Who it is for and what fails today. Framing follows the challenge statement (L37, L41); team and aim as the owner supplied them (L71). "
        "The three barriers are the kinds the Inclinations section names (L80). No statistic about the problem: the pack has no sourced figure.",
        heading="h1", bg="aurora")
    add("problem", "A record you can see, correct and act on.",
        "Clinical Human Clone turns a one-line check-in into a reviewed health record and one bounded next step.",
        fig_pillars, "L5 L21 L24 L71",
        "Why it matters: the aim is a record the person can see, correct and act on (L71). Built: provenance on every card (L21), "
        "nothing saved before review (L5), a next step that passes the boundary rules or routes to a person (L24).")
    add("design", "One sentence in, a reviewed record out.",
        "Check in, review, see it in the passport, learn what helps, then choose a next step. Pain or crisis goes to a person.",
        fig_flow, "L5 L24 L45 L47 L55 L80",
        "The member journey on the hosted build: /#today, /#review. One four-part sentence gave 3 values, each with its words (L45). "
        "Nothing reaches memory before the review (L5). File check-in accepts 4 bundled files (L55). Pain routes the next step to a person (L24); crisis gets a fixed hand-off (L47).")
    add("design", "Every value shows where it came from.",
        "Each card names its source, age and method. A 5-step evidence thread traces it. Stale values are withheld, not guessed.",
        fig_passport, "L20 L21 L22 L50 L51",
        "Health Clone Passport on the hosted build (/#passport). Every card has a 5-step evidence thread (L21); ready only if at most 14 days old, else withheld with no number (L22, L51). "
        "A range sits beside the value and is never interpreted (L20, L50).")
    add("design", "Next steps fit the person, and reach a person when it matters.",
        "Inclinations show what weighs most and link each next step to it. Pain or crisis language routes to a human.",
        fig_incl, "L24 L47 L53 L80",
        "Inclinations: the answers that weigh most, and up to three next steps each linked to one, with its reason (L80). "
        "The next step passes the boundary rules and offers choose, defer or ask a professional (L24, L53). Crisis language gets a fixed hand-off and is not extracted (L47).")
    add("technical", "Rules run live; learning stays offline.",
        "The check-in loop uses fixed rules with no model call. Training and evaluation run offline and publish versioned results.",
        fig_arch, "L6 L10 L11 L24 L55 L57 L59 L66 L67 L76 L80",
        "Live: deterministic rules, no model call at runtime (L6); crisis check before extraction (L10); personal-data refusal (L11); next step through the boundary rules (L24); 4 bundled files (L55). "
        "Offline: 175 synthetic members (L67), SFT and DPO (L57), 141 held-out prompts (L59), 150 simulated episodes (L66). The passport's Inclinations read the reward model (L76, L80). "
        "Versioning by run id and data hash: technical appendix §4.")
    add("technical", "Memory keeps only what the person confirmed.",
        "Proposals wait for review. Memory is append-only. The honesty layer shows ranges without verdicts and withholds what it cannot support.",
        fig_memory, "L5 L10 L11 L20 L21 L22 L23 L24 L47 L48 L65",
        "Memory: only the review commits, all-or-nothing (L5); a confirmed value is shown as recorded, never as a score (L23). Honesty layer: 14-day freshness (L22), ranges never interpreted (L20), "
        "5-step thread (L21), crisis hand-off (L10, L47), personal data refused whole (L11, L48), boundary rules on the next step (L24). "
        "Boundary rules: 74 of 74 labelled violations, 0 false positives on 128 compliant rows of a sealed 202-row corpus, 8 rules (L65).")
    add("technical", "7 questions, a readable reward, a learned policy.",
        "Short answers reveal what drives each member. The reward model scores messages as named terms; GRPO learns which message to send.",
        fig_reward, "L74 L75 L76 L78 L79",
        "Question library: 7 questions (L74). Per-trait recovery on 58 held-out simulated members, 76–91% against chance 17–33% (L75; per-trait values from metrics.json, arm jev). "
        "Reward model: every score is a sum of named terms that add up exactly (L76); top message type matches the simulator's for 83%, chance 17% (L78). "
        "GRPO picks among 7 message types (L79; technical appendix §4a).")
    add("technical", "Both trained stages pass every boundary check; the learned policy edges ahead.",
        "Boundary pass rate on 141 held-out prompts, and mean simulated adherence across 150 episodes against scripted approaches.",
        fig_results, "L59 L60 L66 L79",
        "Boundary pass rate: base 45 of 141, SFT and DPO 141 of 141 (L60) on 141 held-out prompts, 51 check-in and 90 probe (L59). "
        "Adherence: 0.637 no support, 0.719 random, 0.833 always problem-solving (L66); GRPO 0.840, 0 rule violations (L79).")
    add("next", "Next: a clinical reviewer, a consented pilot, a measured result.",
        "The prototype runs today. Try the journey, then read the code.",
        fig_close, "L56 L73 L79 L81",
        "Runs today: hosted build, SC1 smoke 9 of 9 (L81). Real input needs the 12 governance gates closed (L56). No clinical evidence yet, hence the reviewer and pilot (L73). "
        "The learned policy chooses a message type only (L79).", bg="aurora")
    return S


def background(kind: str) -> str:
    # aurora: ported from 21st AuroraBackground (deck/CREDITS.md); mesh: static gradient blobs + a faint grid
    if kind == "aurora":
        return '<div class="bg" aria-hidden="true"><div class="aurora"></div><div class="vignette"></div><div class="grid"></div></div>'
    return '<div class="bg" aria-hidden="true"><div class="mesh"></div><div class="grid"></div></div>'


def render() -> str:
    S = slides()
    n = len(S)
    first: dict[str, int] = {}
    for i, s in enumerate(S, 1):
        first.setdefault(s["section"], i)
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width, initial-scale=1">'
             '<title>Clinical Human Clone · FHDIC submission deck</title>'
             '<meta name="description" content="Clinical Human Clone and the Health Clone Passport: problem, design and technical solution, with the live prototype.">'
             '<meta name="theme-color" content="#05070D">'
             f'<link rel="preload" href="{ASSET}fonts/InterVariable.woff2" as="font" type="font/woff2" crossorigin>'
             f'<link rel="stylesheet" href="{ASSET}deck.css"></head><body>'
             '<a class="skip" href="#stage">Skip to the slides</a>'
             '<main id="stage" class="stage" aria-roledescription="slide deck" aria-label="Clinical Human Clone submission deck">']
    for i, s in enumerate(S, 1):
        sec = dict(SECTIONS)[s["section"]]
        hd = s["heading"]
        fig = s["fig"](Seq())
        parts.append(
            f'<section class="slide s-{s["section"]} bg-{s["bg"]}" id="s{i}" data-section="{s["section"]}" data-ledger="{s["ledger"]}" '
            f'aria-roledescription="slide" aria-label="{i} of {n}: {esc(sec)}">{background(s["bg"])}<div class="frame">'
            f'<div class="top"><span class="kicker"><b>{esc(sec)}</b><span class="idx">{i:02d}</span></span>'
            f'<span class="brand"><span class="orb" aria-hidden="true"></span><span>Clinical Human Clone</span></span></div>'
            f'<{hd}>{esc(s["h"])}</{hd}><p class="lead">{esc(s["lead"])}</p>'
            f'{fig}'
            f'<div class="foot"><span>Team Syntropy · [Wellness] Sustaining Healthy Behaviors</span><span>{i} / {n}</span></div>'
            f'<aside class="notes" data-ledger="{s["ledger"]}"><p>{esc(s["notes"])}</p><p>Ledger rows: {esc(s["ledger"])} '
            f'(docs/daypart/submission/evidence-ledger.md).</p></aside></div></section>')
    parts.append('</main><div id="progress" class="progress" aria-hidden="true"></div>'
                 '<nav class="nav" aria-label="Deck navigation"><button id="prev" type="button" aria-label="Previous slide">←</button>'
                 '<div class="sections">')
    for key, lab in SECTIONS:
        parts.append(f'<a href="#/{first[key]}" data-section="{key}" data-to="{first[key]}" aria-current="false">{lab}</a>')
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
