# Deck credits (HAC-105, deck v2)

The deck is plain HTML, CSS and JS with no framework and no runtime CDN. The patterns below come from 21st.dev
components and were ported by hand to vanilla CSS and JS. Retrieval was on the free tier: 2 code retrievals per
day, shared by both connections, used on 2026-11-16.

| used in the deck | 21st component | how it was used |
|---|---|---|
| `.aurora` background on slides 1 and 10 (`deck.css`) | **AuroraBackground** by dhileepkumargm, https://21st.dev/@dhileepkumargm/components/aurora-background-1 (code retrieved) | Same technique: a 100° repeating linear gradient at 300% size, its position drifting, under a radial fade to the slide colour. Framer Motion is replaced by a CSS keyframe. Colours are the member app tokens (periwinkle, teal, deep indigo). Static under reduced motion and in export. |
| `.glow` spotlight cards on every slide (`deck.css`, `deck.js`) | **Spotlight Card (GlowCard)** by jahed, https://21st.dev/@jahed/components/spotlight-card (code retrieved) | Same effect: a radial light at the pointer fills the card and lights its edge through a masked border ring, with hue shifting by pointer x. The pointer is mapped into each card's own coordinates (`--x`/`--y`), not `background-attachment: fixed`, because slides are transformed. Off under reduced motion and touch; dropped from the PDF. |
| bento layouts on slides 3–9 (`.b-*` in `deck.css`) | inspiration only: **Bento Grid** by kokonutd, https://21st.dev/@kokonutd/components/bento-grid, and by manuarora700 (Aceternity), https://21st.dev/@manuarora700/components/bento-grid | Built by hand with CSS grid: tall feature cells spanning 2 rows, and stat tiles. No code was retrieved. |
| animated counters (`.num[data-to]` in `deck.js`) | inspiration only: **Number Ticker** by danielpetho, https://21st.dev/@danielpetho/components/basic-number-ticker | Built by hand: an ease-out-expo tween from 0 to the value already printed in the page, so export, print and no-JS show the exact ledger value. No code was retrieved. |

The display font is **Inter** 4.1 by Rasmus Andersson (variable woff2, `fonts/InterVariable.woff2`), from
https://github.com/rsms/inter/releases/tag/v4.1 under the SIL Open Font License 1.1 (`fonts/Inter-LICENSE.txt`).
