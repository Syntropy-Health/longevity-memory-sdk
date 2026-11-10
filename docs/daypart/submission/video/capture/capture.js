// Records the FHDIC demo-video footage from the HOSTED build (HAC-65).
//
// One browser context records the whole judge journey as a single real take; every segment's
// start and end offset is written to clips.json so the edit can cut it without restaging anything.
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
const CHECKIN_TEXT = 'slept 6 hours and walked 8000 steps';
// "crisis line" is a boundary-v1 crisis marker: it triggers the real hand-off without graphic wording.
const SAFETY_TEXT = 'Can you give me a crisis line to call?';

const t0 = Date.now();
const clips = [];
let open = null;
const now = () => (Date.now() - t0) / 1000;
function begin(id, title) { open = { id, title, start: now() }; }
function end(extra = {}) { clips.push({ ...open, end: now(), ...extra }); open = null; }
const pause = (p, ms) => p.waitForTimeout(ms);

async function shot(p, name) { await p.screenshot({ path: path.join(OUT, `${name}-${WIDTH}.png`) }); }

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {});
  const ctx = await browser.newContext({
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 1,
    recordVideo: { dir: OUT, size: { width: WIDTH, height: HEIGHT } },
  });
  const p = await ctx.newPage();
  const log = [];
  p.on('response', (r) => { if (r.url().includes('/api/')) log.push({ t: now(), status: r.status(), method: r.request().method(), url: r.url().replace(URL, '') }); });

  // S2: synthetic check-in, review and correction
  await p.goto(URL, { waitUntil: 'networkidle' });
  begin('s2-checkin-review', 'Synthetic check-in, review before saving');
  await pause(p, 1500);
  await p.locator('#ci-text').click();
  await p.locator('#ci-text').pressSequentially(CHECKIN_TEXT, { delay: 45 });
  await pause(p, 600);
  await p.locator('#ci-submit').click();
  await p.locator('#rv-list').waitFor({ state: 'visible', timeout: 60000 });
  await pause(p, 2000);
  await shot(p, 's2-review');
  // Confirm every row the system found.
  const confirms = p.locator('#rv-list input[type=radio][value=confirm]');
  for (let i = 0; i < await confirms.count(); i++) { await confirms.nth(i).check(); await pause(p, 700); }
  await p.locator('#rv-submit').click();
  await pause(p, 2500);
  await shot(p, 's2-saved');
  end();

  // S3: passport with provenance
  begin('s3-passport', 'Health Clone Passport and evidence thread');
  await p.locator('nav a, nav button').filter({ hasText: 'Passport' }).first().click();
  await pause(p, 3000);
  await shot(p, 's3-passport');
  const thread = p.locator('summary', { hasText: 'Evidence thread' }).first();
  if (await thread.count()) { await thread.scrollIntoViewIfNeeded(); await thread.click(); await pause(p, 3000); await shot(p, 's3-evidence'); }
  end();

  // S4a: bounded next step
  begin('s4a-next-step', 'Suggested next step: choose, defer or ask a professional');
  await p.locator('nav a, nav button').filter({ hasText: 'Next step' }).first().click();
  await pause(p, 3500);
  await shot(p, 's4a-next');
  end();

  // S4b: a real safety refusal (crisis hand-off) and the real-input refusal
  begin('s4b-safety', 'Crisis hand-off: nothing extracted or saved');
  await p.locator('nav a, nav button').filter({ hasText: 'Check in' }).first().click();
  await pause(p, 1200);
  await p.locator('#ci-text').fill('');
  await p.locator('#ci-text').pressSequentially(SAFETY_TEXT, { delay: 45 });
  await p.locator('#ci-submit').click();
  await p.locator('.notice--handoff').waitFor({ state: 'visible', timeout: 60000 }).catch(() => {});
  await pause(p, 3500);
  await shot(p, 's4b-handoff');
  end();

  begin('s4c-real-input', 'Real-input request refused by the server');
  await p.locator('#ri-btn').scrollIntoViewIfNeeded();
  await p.locator('#ri-btn').click();
  await pause(p, 3500);
  await shot(p, 's4c-real-input');
  end();

  // S5: learning lab, baseline vs candidate
  begin('s5-lab', 'Learning lab: baseline vs candidate on synthetic episodes');
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.locator('nav a, nav button').filter({ hasText: 'Learning lab' }).first().click();
  await pause(p, 3000);
  await shot(p, 's5-lab');
  await p.mouse.wheel(0, 500);
  await pause(p, 2500);
  end();

  const video = await p.video().path();
  await ctx.close();
  await browser.close();
  const meta = {
    url: URL, build_sha: process.env.BUILD_SHA || 'unknown', viewport: `${WIDTH}x${HEIGHT}`,
    recorded_at: new Date(t0).toISOString(), video: path.basename(video), source: 'real recording of the hosted build (Playwright recordVideo)',
    clips: clips.map((c) => ({ ...c, start: +c.start.toFixed(2), end: +c.end.toFixed(2) })), api: log,
  };
  fs.writeFileSync(path.join(OUT, `clips-${WIDTH}.json`), JSON.stringify(meta, null, 2));
  console.log(JSON.stringify({ video: meta.video, clips: meta.clips.map((c) => [c.id, c.start, c.end]), errors: log.filter((l) => l.status >= 400) }, null, 1));
})().catch((e) => { console.error(e); process.exit(1); });
