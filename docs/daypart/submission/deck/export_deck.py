"""Print the web deck (HAC-86) to the form PDF and render one PNG per slide.

    python export_deck.py <base_url> [--pdf clinical-human-clone-deck.pdf] [--png <dir>] [--scale 1]

<base_url> serves the demo app (the hosted URL, or a local `daypart-demo` / uvicorn run). The page is
/deck?export=1, which lays every slide out at 1600x900 with no navigation. The PDF is one 1600x900 page
per slide with live links; the PNGs (slide-N.png, 1600x900 at --scale 1) are the video's slide frames.
Needs Python Playwright (engine `ui` group) and Chromium.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url")
    ap.add_argument("--pdf", type=Path, default=HERE / "clinical-human-clone-deck.pdf")
    ap.add_argument("--png", type=Path)
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=a.scale)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(a.base_url.rstrip("/") + "/deck?export=1", wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        slides = page.locator("section.slide")
        n = slides.count()
        if a.png:
            a.png.mkdir(parents=True, exist_ok=True)
            for i in range(n):
                slides.nth(i).screenshot(path=str(a.png / f"slide-{i + 1}.png"))
        page.emulate_media(media="print")
        page.pdf(path=str(a.pdf), width="1600px", height="900px", print_background=True, tagged=True,
                 prefer_css_page_size=True)
        b.close()
    if errors:
        raise SystemExit(f"page errors: {errors}")
    print(f"{n} slides -> {a.pdf} ({a.pdf.stat().st_size / 1e6:.2f} MB)" + (f", PNGs in {a.png}" if a.png else ""))


if __name__ == "__main__":
    main()
