"""Build the FHDIC deck (HAC-65) from one slide spec into two outputs.

    python build_deck.py <screens_src_dir>   # crops real hosted screenshots into screens/
    python build_deck.py                     # reuses screens/ as committed

Outputs, next to this file:
  clinical-human-clone-deck.pptx  editable: native text boxes and shapes, ledger rows in the notes
  deck.html                       the same slides as HTML; deck_pdf.js prints it to the PDF

The organiser's template is not public (HAC-63, ledger P1), so the layout is a plain accessible one,
labelled "Template pending" on every slide. Every number on a slide comes from a ledger row named in
that slide's notes (docs/daypart/submission/evidence-ledger.md). Needs python-pptx and Pillow.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).resolve().parent
SCREENS = HERE / "screens"
W, H = 13.333, 7.5
MX = 0.6
FONT = "Arial"  # HTML uses Liberation Sans, which is metric-compatible

INK, BODY, MUTED = "111318", "2A2F3A", "4A5160"
ACCENT, LINE, PANEL = "2B2F9E", "C9CDD6", "F3F4F7"
CONCEPT = "7A4B00"
DEMO_URL = "https://supermomo668--daypart-demo-playground.us-east.modal.run"
REPO_URL = "https://github.com/Syntropy-Health/longevity-memory-sdk"
FOOTER = "Synthetic / simulated results · Synthetic data only · Not medical advice · Not tested with people"
BUILD = "Screens: real captures of the hosted build (daypart/build e50ebb7), 2026-11-10"

# name: (source png, crop box in 1280x720 px)
CROPS = {
    "today": ("s2-today-1280.png", (80, 90, 700, 560)),
    "review": ("s2-review-1280.png", (80, 95, 830, 515)),
    "passport": ("s3-passport-1280.png", (80, 95, 640, 720)),
    "next": ("s4a-chosen-1280.png", (80, 95, 830, 475)),
    "evidence": ("s3-evidence-1280.png", (88, 200, 632, 560)),
    "range": ("s3-passport-1280.png", (88, 405, 632, 720)),
    "withheld": ("s3-withheld-1280.png", (88, 160, 632, 560)),
    "handoff": ("s4b-handoff-1280.png", (84, 172, 1200, 392)),
    "pii": ("s4c-pii-1280.png", (88, 238, 692, 390)),
    "realinput": ("s5c-real-input-1280.png", (272, 236, 1250, 514)),
    "timeline": ("s4d-timeline-1280.png", (80, 95, 830, 570)),
}


def make_screens(src: Path) -> None:
    SCREENS.mkdir(exist_ok=True)
    for name, (fn, box) in CROPS.items():
        im = Image.open(src / fn).convert("RGB").crop(box)
        im.save(SCREENS / f"{name}.jpg", quality=86, optimize=True)


# ---------- the slide spec ----------
# Elements: ("text", x, y, w, h, paras, opts) · ("img", name, x, y, w, h) · ("rect", x, y, w, h, opts)
# paras: list of paragraphs; a paragraph is a list of runs (text, {bold, color, size, mono}).

def P(*runs):
    return [r if isinstance(r, tuple) else (r, {}) for r in runs]


def b(t, **k):
    return (t, {"bold": True, **k})


def text(x, y, w, h, paras, size=18, color=BODY, bold=False, align="l", anchor="t", mono=False):
    if isinstance(paras, str):
        paras = [P(paras)]
    return ("text", x, y, w, h, paras, dict(size=size, color=color, bold=bold, align=align, anchor=anchor, mono=mono))


def rect(x, y, w, h, fill=None, line=LINE, lw=1.0, dash=False, round_=False):
    return ("rect", x, y, w, h, dict(fill=fill, line=line, lw=lw, dash=dash, round=round_))


def img(name, x, y, w, h):
    return ("img", name, x, y, w, h)


def pill(x, y, w, label, color=CONCEPT, size=11):
    return [rect(x, y, w, 0.3, fill="FFFFFF", line=color, lw=1.25, dash=True, round_=True),
            text(x, y, w, 0.3, label, size=size, color=color, bold=True, align="c", anchor="m")]


def chrome(n, title, message, msg_h=0.9):
    els = [
        text(MX, 0.32, 8, 0.3, [P(b("Clinical Human Clone", color=INK), "  ·  Team Syntropy  ·  [Wellness] Sustaining Healthy Behaviors")], size=12, color=MUTED),
        *pill(W - MX - 1.9, 0.28, 1.9, "TEMPLATE PENDING", color=MUTED),
        text(MX, 0.78, W - 2 * MX, 0.7, title, size=34, color=INK, bold=True),
        text(MX, 1.5, W - 2 * MX, msg_h, message, size=20, color=BODY),
        rect(MX, 6.86, W - 2 * MX, 0.0, line=LINE),
        text(MX, 6.98, 10.5, 0.3, FOOTER, size=12, color=MUTED),
        text(W - MX - 1.0, 6.98, 1.0, 0.3, f"{n} / 8", size=12, color=MUTED, align="r"),
    ]
    return els


def shot(name, x, y, w, h, caption=None, cap_h=0.75, cap_size=13):
    els = [img(name, x, y, w, h)]
    if caption:
        els.append(text(x, y + h + 0.1, w, cap_h, caption, size=cap_size, color=BODY))
    return els


def hbar(x, y, w, label, num, den, note, color=ACCENT, label_w=3.1, size=15):
    """One horizontal bar: label | bar scaled to num/den | 'num of den (pct)'."""
    bar_w = w - label_w - 2.0
    frac = num / den
    return [
        text(x, y + 0.04, label_w - 0.1, 0.4, label, size=size, color=INK, bold=True),
        rect(x + label_w, y, bar_w, 0.42, fill=PANEL, line=LINE),
        rect(x + label_w, y, max(bar_w * frac, 0.02), 0.42, fill=color, line=color),
        text(x + label_w + bar_w + 0.12, y + 0.04, 1.9, 0.4, [P(b(f"{num} of {den}", color=INK), f"  ({frac:.0%})")], size=size, color=BODY),
    ] + ([text(x + label_w, y + 0.46, bar_w + 2, 0.3, note, size=12, color=MUTED)] if note else [])


def slides():
    S = []

    # 1. Problem and user
    s = chrome(1, "Clinical Human Clone",
               "Goals and barriers change week to week. Generic reminders don't show what they know about you, or why they suggest something.")
    s += [
        text(MX, 2.75, 5.6, 2.6, [
            P(b("Who it is for", color=INK)),
            P("A person trying to keep a healthy routine going, whose week does not look like last week."),
            P(""),
            P(b("What the prototype does", color=INK)),
            P("Check in in a sentence, review what the system understood, see where every value came from, and choose a next step."),
        ], size=18),
        text(MX, 5.75, 5.6, 0.9, [P(b("Team aim, not a result: ", color=INK), "a health record the person can see, correct and act on.")], size=15, color=BODY),
        *shot("today", 6.75, 2.6, 5.98, 4.0),
        text(6.75, 6.62, 5.98, 0.24, "Check-in screen, hosted build (fictional member)", size=11, color=MUTED),
    ]
    S.append(dict(els=s, notes="Ledger rows: L37 (challenge numbering), L41 (framing follows the challenge statements; no rubric published), L71 (team name and aim as the owner supplied them). No statistic about the problem: the pack has no sourced figure for it. Illustration: /#today on the hosted build."))

    # 2. The experience
    s = chrome(2, "The experience",
               "Check in, review what the system understood, see it in your passport, and choose a next step. Nothing is saved until you confirm it.")
    cw, gap, y0, ih = 2.88, 0.2, 2.6, 2.6
    items = [
        ("today", "1  Check in", "One sentence, or one of 4 bundled synthetic files. Voice and video show as not available."),
        ("review", "2  Review", "One sentence gave 3 values, each with the words it came from. “mood 3 out of 5” gave none."),
        ("passport", "3  Passport", "Each card: observed or simulated, data age, source and method."),
        ("next", "4  Next step", "Choose, defer or ask a professional. After a pain report it routes to a person."),
    ]
    for i, (nm, head, cap) in enumerate(items):
        x = MX + i * (cw + gap)
        s += [img(nm, x, y0, cw, ih),
              text(x, y0 + ih + 0.12, cw, 0.35, head, size=17, color=INK, bold=True),
              text(x, y0 + ih + 0.5, cw, 1.1, cap, size=14, color=BODY)]
    S.append(dict(els=s, notes="Ledger rows: L5 (nothing reaches memory before the review), L45 (3 proposals from the four-part sentence; mood gives none), L49, L53 (next step choose/defer/ask), L55 (4 bundled synthetic files only). Screens: /#today, /#review, /#passport, /#next on the hosted build, 2026-11-10."))

    # 3. How it works
    s = chrome(3, "How it works",
               "One reproducible path: check-in, proposed values, your review, a scoped memory, the passport and a bounded next step. Each step leaves a trace.")
    boxes = [("Check-in", "a sentence or a bundled synthetic file"),
             ("Safety checks", "crisis language and personal data stop here"),
             ("Proposals", "fixed rules; each value keeps its words and method"),
             ("Your review", "confirm, correct or discard, all at once"),
             ("Memory", "confirmed values only, append-only"),
             ("Passport and next step", "next step passes the boundary rules")]
    bw, bg, by = 1.78, 0.29, 2.75
    s.append(text(MX, by - 0.42, 8, 0.35, "Live, on every check-in", size=15, color=ACCENT, bold=True))
    for i, (h_, d_) in enumerate(boxes):
        x = MX + i * (bw + bg)
        s += [rect(x, by, bw, 1.55, fill=PANEL, line=ACCENT, lw=1.5, round_=True),
              text(x + 0.12, by + 0.12, bw - 0.24, 0.5, h_, size=15, color=INK, bold=True),
              text(x + 0.12, by + 0.78, bw - 0.24, 0.75, d_, size=12.5, color=BODY)]
        if i < len(boxes) - 1:
            s.append(text(x + bw - 0.02, by + 0.55, bg + 0.04, 0.4, "→", size=20, color=ACCENT, bold=True, align="c"))
    lane = [("Synthetic members and scenarios", "175 members, fixed seeds"),
            ("Evaluation", "141 held-out synthetic prompts"),
            ("Fine-tuning", "2 stages, adapters on one base model"),
            ("Frozen comparison", "shown in the learning lab")]
    ly, lw_ = 5.0, 2.86
    s.append(text(MX, ly - 0.42, 8, 0.35, "Offline, separate from the live path", size=15, color=MUTED, bold=True))
    for i, (h_, d_) in enumerate(lane):
        x = MX + i * (lw_ + 0.23)
        s += [rect(x, ly, lw_, 1.3, fill="FFFFFF", line=MUTED, lw=1.25, dash=True, round_=True),
              text(x + 0.12, ly + 0.1, lw_ - 0.24, 0.4, h_, size=14, color=INK, bold=True),
              text(x + 0.12, ly + 0.78, lw_ - 0.24, 0.5, d_, size=12.5, color=BODY)]
        if i < len(lane) - 1:
            s.append(text(x + lw_ - 0.02, ly + 0.38, 0.27, 0.4, "→", size=18, color=MUTED, bold=True, align="c"))
    S.append(dict(els=s, notes="Ledger rows: L6 (deterministic rules, no model call at runtime), L9 (proposal schema revalidated), L10 (crisis check before extraction), L11 (personal-data refusal), L24 (next step passes boundary rules), L43 (hosted build), L57 (two training stages), L59 (141 held-out prompts), L67 (175 synthetic members). No box for anything not built."))

    # 4. Interpretability
    s = chrome(4, "Interpretability",
               "Every value shows where it came from, when, how sure the system is, and what it withholds.")
    cw, y0, ih = 3.9, 2.25, 2.55
    cols = [
        ("evidence", "The evidence thread", "5 steps, from the check-in to the saved value, its memory version, a public source and the safety check."),
        ("range", "A range, never a verdict", "Where a public page states a reference range, it sits beside the value. Nothing is marked high, low or abnormal."),
        ("withheld", "Withheld, not guessed", "No value in the last 14 days: the card shows no number and says so."),
    ]
    for i, (nm, head, cap) in enumerate(cols):
        x = MX + i * (cw + 0.215)
        s += [img(nm, x, y0, cw, ih),
              text(x, y0 + ih + 0.12, cw, 0.35, head, size=17, color=INK, bold=True),
              text(x, y0 + ih + 0.5, cw, 0.95, cap, size=14, color=BODY)]
    s.append(text(MX, 6.42, W - 2 * MX, 0.4, [P(b("What it does not know: ", color=INK), "the inventory lists 5 gaps: lab results, conditions, medications, care history, screenings and check-ups.")], size=14))
    S.append(dict(els=s, notes="Ledger rows: L21 (5-step evidence thread), L22 (ready only if at most 14 days old; otherwise withheld, no number), L20 (range shown, never interpreted), L50 (4 of 24 cards show a sourced range), L51 (pain card withheld at 16 days on the prepared member), L54 (5 gaps). Screens: /#passport on the hosted build after a synthetic check-in."))

    # 5. Learning and evidence (results)
    s = chrome(5, "Learning and evidence",
               "Two fine-tuning stages ran and were compared with the base model on 141 held-out synthetic prompts. None of it is a patient outcome.")
    s.append(text(MX, 2.5, 7.4, 0.4, "Boundary pass rate: prompts passed, of 141 held-out synthetic prompts, seed 0", size=14, color=INK, bold=True))
    s += hbar(MX, 3.05, 7.4, "Base model", 45, 141, "90 of its 141 replies were empty: most of the gap is empty output, not unsafe text.", color=MUTED)
    s += hbar(MX, 3.95, 7.4, "Fine-tuned (stage 1)", 141, 141, None)
    s += hbar(MX, 4.6, 7.4, "Preference-tuned (stage 2)", 141, 141, None)
    s.append(text(MX, 5.25, 7.4, 0.4, "Weak slice: lapse-recovery check, check-in prompts passed, of 51", size=14, color=INK, bold=True))
    s += hbar(MX, 5.7, 7.4, "Fine-tuned (stage 1)", 7, 51, None, color="8A2F2F")
    s += hbar(MX, 6.22, 7.4, "Preference-tuned (stage 2)", 6, 51, None, color="8A2F2F")
    rx = 8.45
    s += [rect(rx, 2.5, W - MX - rx, 2.55, fill=PANEL, line=LINE, round_=True),
          text(rx + 0.2, 2.62, W - MX - rx - 0.4, 2.4, [
              P(b("Simulator: scripted policies", color=INK)),
              P("150 simulated episodes (50 scenarios × 3 seeds), 14 days each. Mean simulated adherence, 0 to 1:"),
              P(b("0.637", color=INK), "  no support"),
              P(b("0.833", color=INK), "  always problem-solving"),
              P(b("0.719", color=INK), "  random"),
          ], size=14)]
    s += pill(rx, 5.3, W - MX - rx, "CONCEPT · reinforcement-learning stage: not built", size=10.5)
    s.append(text(rx, 5.72, W - MX - rx, 0.9, "One seed only, so no spread across seeds is reported. Held-out prompts are synthetic, not written by people.", size=13, color=MUTED))
    S.append(dict(els=s, notes="Ledger rows: L57 (two stages ran), L58 (GRPO, reward model, question library not run), L59 (141 prompts, 51 check-in + 90 probe, seed 0, one seed), L60 (base 45/141, SFT and DPO 141/141), L61 (90 of 141 base replies empty), L62 (lapse-recovery 7/51 SFT, 6/51 DPO), L63 (promotion gates passed), L66 (scripted baselines 0.637 / 0.833 / 0.719, 150 episodes). Illustration source: /admin#lab on the hosted build. 'Fine-tuned' = SFT, 'Preference-tuned' = DPO."))

    # 6. Responsible AI and limits
    s = chrome(6, "Responsible AI and limits", "The prototype refuses what it should not do, and shows you when it does.")
    lw6, rx6 = 6.9, 7.75
    rw6 = W - MX - rx6
    s += [img("handoff", MX, 2.3, lw6, lw6 * 220 / 1116),
          text(MX, 2.3 + lw6 * 220 / 1116 + 0.1, lw6, 0.35, [P(b("Crisis language: ", color=INK), "a fixed hand-off to a person. Nothing is extracted or saved.")], size=13.5),
          img("pii", rx6, 2.3, rw6, rw6 * 152 / 604),
          text(rx6, 2.3 + rw6 * 152 / 604 + 0.1, rw6, 0.35, [P(b("Personal data: ", color=INK), "refused whole. Nothing is saved.")], size=13.5),
          img("realinput", MX, 4.2, lw6, lw6 * 278 / 978),
          text(MX, 4.2 + lw6 * 278 / 978 + 0.1, lw6, 0.35, [P(b("Real health data: ", color=INK), "the server refuses (403). 12 of 12 gates are open.")], size=13.5)]
    s += [rect(rx6, 4.2, rw6, 2.5, fill=PANEL, line=LINE, round_=True),
          text(rx6 + 0.22, 4.32, rw6 - 0.44, 2.3, [
              P(b("Limits", color=INK)),
              P("Synthetic data only. No diagnosis, treatment or dosing. No clinical review: content carries a board sign-off, not a clinician's."),
              P("The boundary rules caught 74 of 74 labelled violations, with 0 false alarms on 128 compliant rows of a 202-row test set. That is a measurement on that set, not a proof."),
          ], size=14)]
    S.append(dict(els=s, notes="Ledger rows: L47 (crisis hand-off, not extracted), L48 (e-mail and self-name refused whole, 422), L56 (403 build_disallowed, 12 of 12 gates open), L65 (74/74, 0 false positives on 128 compliant rows, 202-row corpus; a measurement, not a proof), L73 (no clinical evidence). Screens: /#today and /admin#input on the hosted build, 2026-11-10."))

    # 7. Feasibility
    s = chrome(7, "Feasibility and path to deployment",
               "It runs today as a hosted prototype. Reaching people needs consent, privacy, security, clinical oversight and a validation study first.")
    s += [rect(MX, 2.5, 5.7, 0.85, fill=PANEL, line=ACCENT, lw=1.5, round_=True),
          text(MX + 0.2, 2.6, 5.3, 0.7, [P(b("Runs today. ", color=INK), "Redeployed only when every check passes; the hosted journey passed 9 of 9 steps.")], size=14),
          text(MX, 3.6, 5.7, 0.35, "Governance gates for real input: 12 of 12 open", size=15, color=INK, bold=True)]
    gates = ["Lawful basis", "Informed consent", "Access control", "Encryption", "Retention and deletion", "Audit log",
             "Incident response", "Processor terms", "Jurisdiction review", "Clinical intended use", "Qualified oversight", "Regulatory classification"]
    for i, g in enumerate(gates):
        x = MX + (i // 6) * 2.9
        y = 4.02 + (i % 6) * 0.43
        s += [rect(x, y + 0.06, 0.22, 0.22, fill="FFFFFF", line=MUTED, lw=1.25),
              text(x + 0.34, y + 0.02, 2.5, 0.35, g, size=13.5, color=BODY)]
    vx = 6.85
    s.append(text(vx, 2.5, W - MX - vx, 0.35, "Path to clinical validation: none started", size=15, color=INK, bold=True))
    steps = ["Name a qualified clinical reviewer and the intended use",
             "Close the 12 governance gates; real input also needs a code change",
             "Clinical review of content, rules and boundary rules",
             "Stronger evaluation: more seeds, a larger set written by people",
             "Consented, supervised pilot with a pre-registered measure",
             "Then decide on the reinforcement-learning stage"]
    for i, st in enumerate(steps):
        y = 2.98 + i * 0.6
        s += [rect(vx, y, 0.42, 0.42, fill="FFFFFF", line=CONCEPT, lw=1.25, dash=True, round_=True),
              text(vx, y + 0.07, 0.42, 0.3, str(i + 1), size=13, color=CONCEPT, bold=True, align="c"),
              text(vx + 0.56, y + 0.07, W - MX - vx - 2.2, 0.5, st, size=13.5, color=BODY)]
        s += pill(W - MX - 1.5, y + 0.06, 1.5, "CONCEPT", size=10)
    s.append(text(vx, 6.55, W - MX - vx, 0.3, "No cost, latency or scale figure: none is measured.", size=12.5, color=MUTED))
    S.append(dict(els=s, notes="Ledger rows: L43 (hosted build, deployed by CI after every gate), L44 (hosted smoke 9 of 9), L12 (journals in memory only, single container), L33 (real input cannot be enabled), L56 (12 of 12 gates open), L73 (no clinical evidence), P9 (no cost or scale figure). Validation path: technical-appendix.md section 9; every step is concept, not started."))

    # 8. Impact and next steps
    s = chrome(8, "Impact and next steps",
               "What it would take to show this helps people: a named clinical reviewer, a consented pilot and a pre-registered measure.")
    s += shot("timeline", MX, 2.5, 5.4, 5.4 * 475 / 750, None)
    s.append(text(MX, 2.5 + 5.4 * 475 / 750 + 0.08, 5.4, 0.3, "Timeline: what each saved check-in changed (fictional member)", size=11, color=MUTED))
    nx = 6.4
    s.append(text(nx, 2.5, W - MX - nx, 0.35, "Next steps", size=17, color=INK, bold=True))
    nexts = ["Name a clinical reviewer", "Close the 12 governance gates", "Build the reinforcement-learning stage", "Run a consented pilot with a pre-registered measure"]
    for i, t in enumerate(nexts):
        y = 3.0 + i * 0.55
        s += [text(nx, y, 0.4, 0.4, f"{i + 1}.", size=16, color=ACCENT, bold=True),
              text(nx + 0.4, y, 4.3, 0.45, t, size=16, color=BODY)]
        s += pill(W - MX - 1.3, y + 0.02, 1.3, "CONCEPT", size=10)
    s += [text(nx, 5.3, W - MX - nx, 0.6, [P(b("Aim, not a result: ", color=INK), "people keep healthy routines with a record they can see, correct and act on.")], size=14),
          text(nx, 5.95, W - MX - nx, 0.85, [P(b("Prototype  ", color=INK), (DEMO_URL, {"link": DEMO_URL, "color": ACCENT})),
                                              P(b("Source  ", color=INK), (REPO_URL, {"link": REPO_URL, "color": ACCENT}))], size=11.5)]
    S.append(dict(els=s, notes="Ledger rows: L52 (timeline lists every saved check-in), L58 (RL stage not built), L71 (aim as the owner supplied it), L73 (no clinical evidence). Any impact statement is an aim, never a result. Screen: /#timeline on the hosted build."))
    return S


# ---------- PPTX ----------
def rgb(h):
    return RGBColor.from_string(h)


def to_pptx(spec, out: Path):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    blank = prs.slide_layouts[6]
    for sd in spec:
        sl = prs.slides.add_slide(blank)
        for e in sd["els"]:
            kind = e[0]
            if kind == "rect":
                _, x, y, w, h, o = e
                if h == 0:
                    ln = sl.shapes.add_connector(1, Inches(x), Inches(y), Inches(x + w), Inches(y))
                    ln.line.color.rgb = rgb(o["line"]); ln.line.width = Pt(o["lw"])
                    continue
                shp = sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if o["round"] else MSO_SHAPE.RECTANGLE,
                                          Inches(x), Inches(y), Inches(w), Inches(h))
                if o["round"]:
                    shp.adjustments[0] = min(0.5, 0.12 / max(min(w, h), 0.01))
                if o["fill"]:
                    shp.fill.solid(); shp.fill.fore_color.rgb = rgb(o["fill"])
                else:
                    shp.fill.background()
                if o["line"]:
                    shp.line.color.rgb = rgb(o["line"]); shp.line.width = Pt(o["lw"])
                    if o["dash"]:
                        from pptx.enum.dml import MSO_LINE
                        shp.line.dash_style = MSO_LINE.DASH
                else:
                    shp.line.fill.background()
                shp.shadow.inherit = False
            elif kind == "img":
                _, name, x, y, w, h = e
                pth = SCREENS / f"{name}.jpg"
                iw, ih = Image.open(pth).size
                sc = min(w / iw, h / ih)
                pw, ph = iw * sc, ih * sc
                pic = sl.shapes.add_picture(str(pth), Inches(x), Inches(y), Inches(pw), Inches(ph))
                pic.line.color.rgb = rgb(LINE); pic.line.width = Pt(0.75)
            elif kind == "text":
                _, x, y, w, h, paras, o = e
                tb = sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
                tf = tb.text_frame
                tf.word_wrap = True
                tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Emu(0)
                tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE}[o["anchor"]]
                for i, para in enumerate(paras):
                    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                    p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[o["align"]]
                    p.line_spacing = 1.15
                    if i:
                        p.space_before = Pt(o["size"] * 0.35)
                    for t, ro in para:
                        r = p.add_run(); r.text = t
                        f = r.font
                        f.name = FONT; f.size = Pt(ro.get("size", o["size"]))
                        f.bold = ro.get("bold", o["bold"]); f.color.rgb = rgb(ro.get("color", o["color"]))
                        if ro.get("link"):
                            r.hyperlink.address = ro["link"]
        sl.notes_slide.notes_text_frame.text = sd["notes"] + "\n\n" + BUILD
    prs.core_properties.title = "Clinical Human Clone: FHDIC deck (template pending)"
    prs.core_properties.author = "Team Syntropy"
    prs.save(out)


# ---------- HTML (for the PDF) ----------
def to_html(spec, out: Path):
    PX = 96
    css = f"""@page{{size:{W}in {H}in;margin:0}}*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Liberation Sans',Arial,sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.s{{position:relative;width:{W}in;height:{H}in;overflow:hidden;background:#fff;page-break-after:always}}
.e{{position:absolute}} .t p{{line-height:1.15}} a{{color:inherit}}
img.e{{border:0.75pt solid #{LINE};object-fit:contain;object-position:left top}}"""
    parts = [f"<!doctype html><html lang=en><head><meta charset=utf-8><title>Clinical Human Clone: FHDIC deck (template pending)</title><style>{css}</style></head><body>"]
    for i, sd in enumerate(spec, 1):
        parts.append(f'<section class=s aria-label="Slide {i}">')
        for e in sd["els"]:
            kind = e[0]
            if kind == "rect":
                _, x, y, w, h, o = e
                st = f"left:{x}in;top:{y}in;width:{w}in;height:{max(h, 0)}in;"
                if h == 0:
                    st += f"border-top:{o['lw']}pt solid #{o['line']};"
                else:
                    st += f"background:{'#' + o['fill'] if o['fill'] else 'transparent'};"
                    st += f"border:{o['lw']}pt {'dashed' if o['dash'] else 'solid'} #{o['line']};" if o["line"] else ""
                    st += "border-radius:0.12in;" if o["round"] else ""
                parts.append(f'<div class=e style="{st}"></div>')
            elif kind == "img":
                _, name, x, y, w, h = e
                iw, ih = Image.open(SCREENS / f"{name}.jpg").size
                sc = min(w / iw, h / ih)
                parts.append(f'<img class=e alt="" src="screens/{name}.jpg" style="left:{x}in;top:{y}in;width:{iw * sc}in;height:{ih * sc}in">')
            elif kind == "text":
                _, x, y, w, h, paras, o = e
                al = {"l": "left", "c": "center", "r": "right"}[o["align"]]
                ps = []
                for j, para in enumerate(paras):
                    rs = []
                    for t, ro in para:
                        st = f"font-size:{ro.get('size', o['size'])}pt;color:#{ro.get('color', o['color'])};font-weight:{'700' if ro.get('bold', o['bold']) else '400'}"
                        tt = html.escape(t) if t else "&nbsp;"
                        rs.append(f'<a href="{ro["link"]}" style="{st}">{tt}</a>' if ro.get("link") else f'<span style="{st}">{tt}</span>')
                    mt = f"margin-top:{o['size'] * 0.35}pt;" if j else ""
                    ps.append(f'<p style="{mt}text-align:{al};font-size:{o["size"]}pt">{"".join(rs)}</p>')
                fx = "display:flex;flex-direction:column;justify-content:center;" if o["anchor"] == "m" else ""
                parts.append(f'<div class="e t" style="{fx}left:{x}in;top:{y}in;width:{w}in;height:{h}in">{"".join(ps)}</div>')
        parts.append("</section>")
    parts.append("</body></html>")
    out.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        make_screens(Path(sys.argv[1]))
    spec = slides()
    to_pptx(spec, HERE / "clinical-human-clone-deck.pptx")
    to_html(spec, HERE / "deck.html")
    print(f"{len(spec)} slides -> clinical-human-clone-deck.pptx, deck.html")
