# Handoff — worktree-agent, daypart (HAC-38)

**Trigger:** iteration-complete P3.3 · 2026-11-08

## State
- Branch `daypart/hac-fhdic-build`, pushed. P3.3 (plan task 13, dashboard rename, T1.4) is closed by boundary
  commit cf57d54 with QGR `…qgr-iteration-complete-20261108-1534-34eb63d.md` (base aaf5ad5, the P3.2 boundary).
- P3.3 = dashboard title/header "Clinical Human Clone: research view"; dashboard.py import-safe (renders only
  under `streamlit run`, main() returns after st.stop()); README / CLI help / research-screen link say
  "research view: full results"; addendum G28.
- QG: K1 kept and fixed; B1, B2, B4 below threshold fixed; 2 dropped. One commit each.
- Tests at cf57d54: engine 2608 passed / 22 skipped (UI module w/o browser env), root 352 / 3 skipped,
  pyright 0. CI green on 4e7fe00 (run 42434876768, demo-ui included).
- origin/main 0ae02e6 (squash of daypart/build 0564ef6) merged in at 31e24eb. P2 still waits for CTO landing.

## Next
- `/phase-complete` P3 (deep gate over P3.1–P3.3, base 179d67d) + the Reviewer's review-ux pass, then hand to CTO.
- Then P4 (submission pack, plan task 14).

## Open items
_none pending_

## Notes
- PATH needs /paperclip/.local/bin for uv. Run engine tests with `env -u MUSE_API_KEY -u META_MODEL_API_KEY`.
- Root suite: `uv run --all-extras --with pytest --with pytest-asyncio pytest -q` (pytest not in root env).
- Pyright: `cd engine && uv run --with pyright==1.1.414 pyright daypart`.
- Push only via `/opt/airdlc-plugin/tools/git-push` (raw git push is hook-blocked). Work item format `TASK-HAC-38`.
- Local UI suite needs Chromium libs (memory headless-chromium-libs); CI demo-ui is the referee.
- Sealed suite: overlay origin/daypart/hac39-sealed into a detached worktree; run pytest only.
