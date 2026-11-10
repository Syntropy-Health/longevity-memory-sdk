# Capture harness (HAC-65)

`capture.js` records the judge journey from the **hosted** build as one real Playwright take and
writes `clips-<width>.json`: URL, deployed commit (`BUILD_SHA`), viewport, each segment's offsets
and URL, the screenshots taken, and every API call's status.

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

Takes used (2026-11-10, hosted build `e50ebb71aaeb7b61a42cd81c7481e1a17e49fe98`):
[`clips-1280.json`](clips-1280.json) (the video's footage) and [`clips-375.json`](clips-375.json)
(the judge-path check at phone width). The only status of 400 or above in either take is the
expected 403 refusal of real input. The `.webm` recordings are not committed; the MP4 cut from the
1280 take is attached to HAC-65.
