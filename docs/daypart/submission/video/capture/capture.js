// Records the FHDIC demo-video footage from the HOSTED build (HAC-65).
//
// One browser page records the whole judge journey as a single real take, across both surfaces
// (member app at `/`, research console at `/admin`). Every segment's start and end offset, and the
// URL it was filmed on, is written to clips-<width>.json so the edit can cut it without restaging.
// Nothing is mocked or intercepted: the page talks to the hosted API exactly as a judge's would.
//
// Usage:  node capture.js <out_dir> [width=1280]
// Env:    CHROME_BIN (optional browser binary), DEMO_URL (defaults to the hosted playground),
//         BUILD_SHA (the commit the hosted app was deployed from; recorded per clip).
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const URL = process.env.DEMO_URL || 'https://supermomo668--daypart-demo-playground.us-east.modal.run';
const OUT = process.argv[2] || 'out';
const WIDTH = Number(process.argv[3] || 1280);
const HEIGHT = WIDTH >= 1000 ? 720 : 812;
// The sentence the hosted probe used (ledger L45): 3 proposals, "mood 3 out of 5" gives none.
const CHECKIN_TEXT = 'slept 6 hours, pain 4/10, mood 3 out of 5, walked 8000 steps';
const CORRECTED_SLEEP = '6.5';
// "crisis line" is a boundary-v1 crisis marker: it triggers the real hand-off without graphic wording.
const SAFETY_TEXT = 'Can you give me a crisis line to call?';

const t0 = Date.now();
const clips = [];
let open = null;
const now = () => (Date.now() - t0) / 1000;
let page;
function begin(id, title) { open = { id, title, url: page.url(), start: now() }; }
function end(extra = {}) { clips.push({ ...open, end: now(), ...extra }); open = null; }
const pause = (ms) => page.waitForTimeout(ms);
const shots = [];
async function shot(name, opts = {}) {
  const f = `${name}-${WIDTH}.png`;
  await page.screenshot({ path: path.join(OUT, f), ...opts });
  shots.push({ file: f, url: page.url(), t: +now().toFixed(2) });
}
async function smoothScroll(px, steps = 10, ms = 120) {
  for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, px / steps); await pause(ms); }
}
const nav = (hash) => page.locator(`a[href="#${hash}"]`).first();

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
  const ctx = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 1,
    reducedMotion: 'no-preference',
    recordVideo: { dir: OUT, size: { width: WIDTH, height: HEIGHT } },
  });
  page = await ctx.newPage();
  const log = [];
  page.on('response', (r) => { if (r.url().includes('/api/')) log.push({ t: +now().toFixed(2), status: r.status(), method: r.request().method(), url: r.url().replace(URL, '') }); });

  // S2: synthetic check-in, review and one correction
  await page.goto(URL, { waitUntil: 'networkidle' });
  await page.locator('#ci-text').waitFor({ state: 'visible' });
  begin('s2-checkin-review', 'Synthetic check-in, review and correction before saving');
  await pause(1500);
  await shot('s2-today');
  await page.locator('#ci-text').click();
  await page.locator('#ci-text').pressSequentially(CHECKIN_TEXT, { delay: 40 });
  await pause(700);
  await page.locator('#ci-submit').click();
  await page.locator('#rv-list fieldset').first().waitFor({ state: 'visible', timeout: 60000 });
  await pause(2500);
  await shot('s2-review');
  const sets = page.locator('#rv-list fieldset');
  const n = await sets.count();
  for (let i = 0; i < n; i++) {
    const fs_ = sets.nth(i);
    await fs_.scrollIntoViewIfNeeded();
    const legend = (await fs_.locator('legend').innerText()).toLowerCase();
    if (legend.includes('sleep')) {
      await fs_.locator('input[value=correct]').check();
      await pause(600);
      const v = page.locator('#rv-list .correct-fields:not([hidden]) input[type=number]').first();
      await v.fill('');
      await v.pressSequentially(CORRECTED_SLEEP, { delay: 120 });
    } else {
      await fs_.locator('input[value=confirm]').check();
    }
    await pause(900);
  }
  await page.locator('#rv-submit').scrollIntoViewIfNeeded();
  await shot('s2-decided');
  await page.locator('#rv-submit').click();
  await pause(3000);
  await shot('s2-saved');
  end();

  // S3: passport with provenance
  await nav('passport').click();
  await page.locator('#pp-cards').waitFor({ state: 'visible', timeout: 60000 });
  begin('s3-passport', 'Health Clone Passport and evidence thread');
  await pause(2500);
  await shot('s3-passport');
  await smoothScroll(450);
  await pause(1200);
  const thread = page.locator('summary', { hasText: 'Evidence thread' }).first();
  if (await thread.count()) {
    await thread.scrollIntoViewIfNeeded();
    await thread.click();
    await pause(800);
    await thread.evaluate((e) => e.parentElement.scrollIntoView({ block: 'center' }));
    await pause(3500);
    await shot('s3-evidence');
  }
  const withheld = page.locator('#pp-cards article', { hasText: 'Not enough data yet' }).first();
  if (await withheld.count()) {
    await withheld.evaluate((e) => e.scrollIntoView({ block: 'center', behavior: 'smooth' }));
    await pause(3000);
    await shot('s3-withheld');
  }
  end();

  // S4a: bounded next step
  await nav('next').click();
  await page.locator('#ns-panel').waitFor({ state: 'visible', timeout: 60000 });
  begin('s4a-next-step', 'Suggested next step: choose, defer or ask a professional');
  await pause(3000);
  await shot('s4a-next');
  await page.locator('#ns-panel button', { hasText: 'Choose' }).first().click();
  await pause(2500);
  await shot('s4a-chosen');
  end();

  // S4b: a real safety refusal (crisis hand-off): nothing extracted or saved
  await nav('today').click();
  await page.locator('#ci-text').waitFor({ state: 'visible' });
  begin('s4b-safety', 'Crisis hand-off: nothing extracted or saved');
  await pause(1000);
  await page.locator('#ci-text').fill('');
  await page.locator('#ci-text').pressSequentially(SAFETY_TEXT, { delay: 40 });
  await page.locator('#ci-submit').click();
  await page.locator('.notice--handoff').first().waitFor({ state: 'visible', timeout: 60000 }).catch(() => {});
  await page.locator('.notice--handoff').first().evaluate((e) => e.scrollIntoView({ block: 'center' })).catch(() => {});
  await pause(4000);
  await shot('s4b-handoff');
  end();

  // S4d: timeline, the longitudinal record (deck slide 8)
  await nav('timeline').click();
  await page.locator('#tl-body').waitFor({ state: 'visible', timeout: 60000 });
  begin('s4d-timeline', 'How the clone changed: every saved check-in');
  await pause(2500);
  await shot('s4d-timeline');
  await smoothScroll(500);
  await pause(1500);
  end();

  // S5: research console: pipeline, learning lab, real input refusal
  await page.goto(`${URL}/admin/pipeline`, { waitUntil: 'networkidle' });
  begin('s5a-pipeline', 'Research console: the adaptation pipeline');
  await pause(2500);
  await shot('s5a-pipeline');
  await smoothScroll(600, 12);
  await pause(1500);
  end();

  await page.locator('a[href="#lab"], a[href$="/lab"]').first().click();
  await page.waitForLoadState('networkidle');
  begin('s5b-lab', 'Learning lab: base vs fine-tuned on 141 held-out synthetic prompts');
  await pause(3000);
  await shot('s5b-lab');
  await smoothScroll(350, 8, 150);
  await pause(3000);
  await shot('s5b-lab-scrolled');
  end();

  await page.locator('a[href="#input"], a[href$="/input"]').first().click();
  await page.waitForLoadState('networkidle');
  await page.locator('#ri-btn').waitFor({ state: 'visible' });
  begin('s5c-real-input', 'Real-input request refused by the server (403, 12 open gates)');
  await pause(1500);
  await page.locator('#ri-btn').click();
  await pause(3500);
  await shot('s5c-real-input');
  await smoothScroll(400);
  await pause(1500);
  end();

  const video = await page.video().path();
  await ctx.close();
  await browser.close();
  const meta = {
    url: URL, build_sha: process.env.BUILD_SHA || 'unknown', viewport: `${WIDTH}x${HEIGHT}`,
    recorded_at: new Date(t0).toISOString(), video: path.basename(video),
    source: 'real recording of the hosted build (Playwright recordVideo); nothing mocked or intercepted',
    checkin_text: CHECKIN_TEXT, corrected_sleep_hours: Number(CORRECTED_SLEEP), safety_text: SAFETY_TEXT,
    clips: clips.map((c) => ({ ...c, start: +c.start.toFixed(2), end: +c.end.toFixed(2) })), screenshots: shots, api: log,
  };
  fs.writeFileSync(path.join(OUT, `clips-${WIDTH}.json`), JSON.stringify(meta, null, 2));
  console.log(JSON.stringify({ video: meta.video, clips: meta.clips.map((c) => [c.id, c.start, c.end, c.url]), errors: log.filter((l) => l.status >= 400) }, null, 1));
})().catch((e) => { console.error(e); process.exit(1); });
