// Prints deck.html to the deck PDF and renders one PNG per slide for review (HAC-65).
// Usage: node deck_pdf.js <deck_dir> [png_out_dir]   (needs playwright; CHROME_BIN optional;
//        DSF=1.25 renders the slide PNGs at 1600x900 for the video)
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const dir = path.resolve(process.argv[2] || '.');
  const pngDir = process.argv[3];
  const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: Number(process.env.DSF || 1) });
  await page.goto('file://' + path.join(dir, 'deck.html'), { waitUntil: 'load' });
  await page.pdf({ path: path.join(dir, 'clinical-human-clone-deck.pdf'), width: '13.333in', height: '7.5in', printBackground: true, tagged: true });
  if (pngDir) {
    const n = await page.locator('section.s').count();
    for (let i = 0; i < n; i++) await page.locator('section.s').nth(i).screenshot({ path: path.join(pngDir, `slide-${i + 1}.png`) });
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
