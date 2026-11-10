# Capture harness (HAC-65)

`capture.js` records the judge journey from the **hosted** build as one real Playwright take and
writes `clips-<width>.json`: URL, deployed commit (`BUILD_SHA`), viewport, each segment's offsets
and every API call's status.

```sh
npm i playwright@1                       # in a scratch dir, not in the repo
BUILD_SHA=<deployed sha> node capture.js out 1280
BUILD_SHA=<deployed sha> node capture.js out 375   # judge-path check at phone width
```

Set `CHROME_BIN` to use a local Chromium. On a host without the browser's system libraries,
extract the Debian packages (libglib2.0, libnss3, libnspr4, libatk1.0, libdbus-1, libx11-6,
libxcomposite1, libxdamage1, libxext6, libxfixes3, libxrandr2, libgbm1, libxcb1, libxkbcommon0,
libasound2, libatspi2.0, libatomic1, fonts-liberation) into a user directory and point
`LD_LIBRARY_PATH` and `FONTCONFIG_FILE` at it. No root is needed.

The demo-video edit needs a full ffmpeg with libx264, xfade, drawtext and subtitles. Playwright's
own ffmpeg is too minimal; `imageio-ffmpeg`'s static binary works.

Dry run 2026-11-10 ~01:45 UTC on the hosted build: check-in, review, next step, crisis hand-off,
real-input refusal (403) and lab all work. The passport returns **500** (HAC-38 fix pending).
