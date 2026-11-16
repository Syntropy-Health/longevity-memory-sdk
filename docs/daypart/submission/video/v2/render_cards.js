// Renders the v2 cards (cards.html) to frame sequences, deterministically: every CSS animation is
// paused and stepped to t = i/fps before each screenshot, so a card's build-in is identical on
// every run. Writes <out>/<name>/f%04d.png for t in [0, secs]; the edit holds the last frame.
//
// Usage: node render_cards.js <jobs.json> <out_dir> <fonts_dir>
//   jobs.json: [{"name": "s01", "card": "title", "w": 1150, "secs": 3.4, "params": {...}}]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const [jobsFile, out, fonts] = process.argv.slice(2);
  const jobs = JSON.parse(fs.readFileSync(jobsFile, 'utf8'));
  const fps = 30;
  const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
  const css = `@font-face{font-family:'Space Grotesk';src:url('file://${fonts}/SpaceGrotesk.ttf');font-weight:300 700}
    @font-face{font-family:'JetBrains Mono';src:url('file://${fonts}/JetBrainsMono.ttf');font-weight:100 800}`;
  for (const j of jobs) {
    const page = await browser.newPage({ viewport: { width: j.w, height: 1080 }, deviceScaleFactor: 1 });
    const qs = new URLSearchParams({ card: j.card, w: String(j.w), ...(j.params || {}) });
    await page.goto(`file://${path.resolve(__dirname, 'cards.html')}?${qs}`);
    await page.addStyleTag({ content: css });
    await page.evaluate(() => document.fonts.ready);
    const dir = path.join(out, j.name);
    fs.mkdirSync(dir, { recursive: true });
    const n = Math.round((j.secs || 0) * fps);
    for (let i = 0; i <= n; i++) {
      // Every animation is paused and offset by --t (cards.html), so a frame is a pure function of t.
      await page.evaluate((t) => document.documentElement.style.setProperty('--t', String(t)), j.at != null ? j.at : i / fps);
      await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
      await page.screenshot({ path: path.join(dir, `f${String(i).padStart(4, '0')}.png`) });
    }
    await page.close();
    console.log(j.name, n + 1, 'frames');
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
