# P4 phase deep gate findings (base 5ced742) — 2 fresh reviewers (accuracy, tests)
P1 LOW docs/daypart/FHDIC.md:108 CI redeploy wording omits the path filter (README/architecture fixed in B2).
P2 LOW assumptions-limits.md:36,:102 gap list omits "screenings and check-ups" (registry_a4.json gaps, passport/view.py:63).
P3 LOW architecture.md attribution-boundary row says "pinned LHM SDK"; the job checks the repo-root LHM (syntropy/, tests/, pyproject.toml, uv.lock) against f170784.
P4 MEDIUM test _ledger_table_body_lines drops a final ledger row with no leading pipe (GFM renders it); dead path/undefined tag on it passes.
P5 MEDIUM test_mismatch_row_withholds_every_number does not check the split cell (G25: run id, prompt set, data sha only).
P6 LOW link-resolution-relative-to-linking-file not proven (no file in sources/ has relative links).
INFO: L19 label vs UI rendering; registration close 2026-11-10 18:29 UTC goes in the CTO hand-off.
