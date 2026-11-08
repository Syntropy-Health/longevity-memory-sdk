# Handoff — worktree-agent, daypart (HAC-38)

**Trigger:** iteration-complete P3.2 · 2026-11-08

## State
- Branch `daypart/hac-fhdic-build`, pushed. P3.2 (plan task 12, UI and a11y CI) is closed by boundary commit
  aaf5ad5 with QGR `…qgr-iteration-complete-20261108-0034-f0bbc10.md` (base ada2950, the P3.1 boundary).
- P3.2 = `engine/tests/ui/test_journey_a11y.py` (22 tests, Python Playwright + vendored axe-core 4.13.0,
  sha-pinned), `ui` uv group (not default), `demo-ui` CI job (DAYPART_UI_REQUIRED=1) that `deploy-demo` needs.
- QG: 25 raw, 19 merged, 8 kept (K1–K8), all test/doc fixes, one commit each; each new test proven red on an
  index.html mutant. Dev doc has a P3 section on running the UI suite.
- Tests at aaf5ad5: UI 22 passed (x3), engine 2600 passed / 22 skipped (the UI module without browser env),
  root 352 / 3 skipped, pyright 0. CI was green on 3ead811 (demo-ui included).
- P2 still waits for the CTO to land on `daypart/build` (0564ef6).

## Next
- P3.3 = task 13, the dashboard rename (`daypart/demo/dashboard.py`, T1.4,
  `tests/unit/test_dashboard_strings_unit.py`). Then `/phase-complete` P3 + the Reviewer's review-ux pass.

## Notes
- Run engine tests with `env -u MUSE_API_KEY -u META_MODEL_API_KEY`.
- Local UI suite: DAYPART_UI_CHROMIUM=/paperclip/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux-arm64/chrome-headless-shell
  with LD_LIBRARY_PATH/FONTCONFIG_FILE from /tmp/hac48/libs/root (memory headless-chromium-libs).
- Sealed suite: overlay origin/daypart/hac39-sealed into a detached worktree; run pytest only.
- Below-threshold, not fixed: workflow `permissions:` block and SHA-pinned actions (pre-existing, workflow-wide).
