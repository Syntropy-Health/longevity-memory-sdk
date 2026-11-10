# HAC-38 final plan-complete gate: scored findings (daypart/hac-fhdic-build @ ae86824, scope efb3f65..HEAD)

Threshold: 80. `tools/config` is not present in the worktree, so the documented default is used.
Inputs: code.md (C1-C4), security.md (S1-S7), design.md (D1-D12), test.md (T1-T4), ux/summary.md (0 findings). Own review: none.
Merged: C3 = D3 (Modal scaledown), C4 = S1 (per-journal check-in cap). 27 raw findings became 25 unique: 8 kept, 17 below threshold.
Verification: I read every cited line at ae86824. I re-ran C1, C2 and the T1 precondition through TestClient with the engine .venv and MUSE_API_KEY unset. The tree was not modified.

## Kept (score >= 80)

[KEPT, score 92] K1 (D1) `docs/daypart/submission/organiser-rules.md:16-17`, `docs/workstreams/daypart.md:29-30`: team registration is still shown as `[ ]` **unverified**, but HAC-58 confirmed it on 2026-11-09 (board accepted on HAC-59).
  Verified: both stale lines are present. The pack test (`test_submission_pack_unit.py:294-296`) accepts only met|unverified|not published|open, so writing "verified" would break CI. Registration closes today (2026-11-10 18:29 UTC), which makes the stale line misleading to judges right now.
  Fix: `- [x] ... **met**: registration confirmed with the organiser on 2026-11-09 (HAC-58; board accepted on HAC-59).` Do not use a tracker URL (the host allow-list refuses it). Add a ledger row or an assumption for the claim. Update dev doc lines 29-30 to match.

[KEPT, score 88] K2 (C3 + D3) `engine/deploy/modal_demo.py:65`: `playground` is `min_containers=0, scaledown_window=600`, while `IDLE_SECONDS = 3600.0` (journal.py:37) and the pack claims 60 min idle (AND.md:142/306, usage/daypart.md:9, assumptions-limits.md:59, architecture.md:93, ledger L12).
  Verified: with no traffic, the only container scales down after 10 min and every in-memory journal is lost. A judge who comes back after 10-60 min gets "session ended", which contradicts five shipped claims (SC7). The UI recovers gracefully, so this is a false claim, not a crash.
  Fix: `scaledown_window=3600` on `playground` (or `min_containers=1` during judging, 2026-11-10..20). If cost rules that out, reword J4, L12, the usage doc, assumptions-limits and architecture.md to say 10 min.

[KEPT, score 85] K3 (T1) `engine/daypart/passport/view.py:341` (`_latest_records`): the `rec.status != "mapped"` filter has no test. The mutant that drops it survives.
  Verified: today the code is correct. "weighed 160" gives p-1 29463-7 `unit_assumed`, blocking. After `save_unmapped` the body-weight card is `withheld/simulated/None`. The existing passport tests use only `concept_id=None` unmapped records, so they never reach the status check. A regression here would let a blocking value bypass review into the passport (SC9).
  Fix: add a TestClient test next to `test_pending_and_discarded_values_never_reach_the_passport` (test_passport_view_unit.py:249). Assert the record has `status=="unmapped"` and `concept_id=="chc:body-weight"`, and that card `observation:chc:body-weight` is withheld/simulated/value None with no thread `record_id` for it.

[KEPT, score 82] K4 (T3) `.github/workflows/engine.yml:28-29`: T8.5 (the I1 CI step stays, G5/SC5) is the only T-id with no test.
  Verified: `test_typecheck_ci_unit.py` checks the typecheck job and its `needs` only. Nothing pins the `i1_check` step or `test` in `deploy-demo.needs`.
  Fix: in test_typecheck_ci_unit.py, assert that a `jobs["test"]` step has `run == "uv run python -m daypart.ci.i1_check"` and that `"test" in jobs["deploy-demo"]["needs"]`.

[KEPT, score 80] K5 (T2) `.github/workflows/engine.yml:62-64,78`: nothing checks that `demo-ui` gates the deploy or that `DAYPART_UI_REQUIRED="1"` is set.
  Verified: `needs: [test, typecheck, demo-ui, attribution-boundary]` and `DAYPART_UI_REQUIRED: "1"` are present but untested. Without the variable, the tests/ui suite skips at module level and passes, so the SC6 gate could be removed silently.
  Fix: in the same file as K4, assert `"demo-ui" in jobs["deploy-demo"]["needs"]`, that the demo-ui pytest step over tests/ui has `env["DAYPART_UI_REQUIRED"] == "1"`, and that a chromium install step exists.

[KEPT, score 80] K6 (C1) `engine/daypart/checkin/service.py:223,227` (`_correction_reasons`): `math.isfinite(d.value)` on a huge `StrictInt` raises OverflowError.
  Reproduced: "weight 70 kg today", then review `correct` with value `1` followed by 400 zeros, returns **500 Internal Server Error**. The A&D failure table (AND.md:547) says 422 `invalid_correction`. No state is written, and the lock is released (async with).
  Fix: at the top of the `d.value` branch, `try: fv = float(d.value) except OverflowError: reasons.append("value_out_of_range"); fv = None`. Use `fv` for the whole-number and range checks. Add a unit test with a 400-digit int.

[KEPT, score 80] K7 (D4) `workstreams/daypart/AND.md:192,330-331,339,616-617`: the A&D still says 19 LOINC + 2 local, 12 add_nodes, the 69725-0 GAD-2 cell, symptoms "5 + 1 local", and T5.1 "exactly the 12 codes".
  Verified: all five stale strings are present. The shipped registry, ledger L13-L15, architecture.md and G16 all say 18 + 2 / 11. architecture.md points judges to "the full design in the A&D", and G19 set the precedent of amending the A&D in place.
  Fix: amend in place, citing G3/G4/G16: 18 LOINC + 2 local, 11 add_nodes, drop the 69725-0 cell, symptoms 4 + 1 local, T5.1 "exactly the LOINC codes not in core() (11)". Fold in B5 (line 205 axe path) in the same edit.

[KEPT, score 80] K8 (D9) `README.md:5,137-139`: the root README calls the hosted URL "playground (inputs, outputs and parameters, step by step)". That URL now serves the five-screen Clinical Human Clone journey (ledger L1), and the FHDIC section links FHDIC.md, not the submission pack.
  Verified: both lines are present. The README is the first page judges see, and D-A1 puts the rename in UI copy and docs.
  Fix: relabel to "Clinical Human Clone (five-screen journey)", with the research view named as the secondary link, and link `docs/daypart/submission/README.md` from the FHDIC section.

## Below threshold (reference only, not dispatched)

[BELOW THRESHOLD, score 70] B1 (C2) `service.py:213-231` with `:317-328`: the whole-number check runs only on `correct`.
  Reproduced: "heart rate 64.5 bpm today" is unflagged, and `confirm` saves 64.5 /min against an `integer` concept (registry_a4.json:26). The asymmetry is real, but it needs an unusual input on synthetic data, the A&D failure table scopes the check to `correct`, and the stored value is still plausible.
  Fix if taken: raise a blocking flag in `detect_flags` when an integer/ordinal concept has a fractional value.

[BELOW THRESHOLD, score 68] B2 (C4 + S1) `service.py:172`, `journal.py:241-245`: there is no per-journal cap on check-ins or events.
  Verified: it is unbounded. But the dev doc (docs/workstreams/daypart.md:183) already lists it as accepted residual risk. Exploiting it takes about 150k scripted requests (about 6.6 KB each) against a two-week synthetic demo, and that kind of flood can take the single container down anyway.
  Fix if taken: `MAX_CHECKINS_PER_JOURNAL = 200` → 429 `too_many_checkins`, with a matching cap on events.

[BELOW THRESHOLD, score 65] B3 (D2) SC1 "on the hosted URL": there is no committed hosted-journey proof. The deploy smoke curls only health and `/`.
  Verified: the gap is real. But AND.md:84 says the SCs are checked by `/human-qa`, which is where a hosted run belongs, and K2 covers the realistic hosted dead end.
  Fix if taken: a post-deploy API journey step against `$P`, or a committed hosted-run receipt cited in L1.

[BELOW THRESHOLD, score 60] B4 (D10) `docs/usage/daypart.md:3-4`: the "go live ... once the CTO deploys" caveat is stale, and the P2 API routes are not documented. Low impact doc drift.
  Fix: drop the caveat and add a short P2 API block.

[BELOW THRESHOLD, score 60] B5 (D5) `AND.md:205`: the A&D still gives `demo/static/axe.min.js`, but the file shipped at `tests/ui/vendor/axe.min.js` (G10). Fold into K7.

[BELOW THRESHOLD, score 58] B6 (S2) `app.py:205-228`: the research-playground routes have no MAX_BODY_BYTES cap, and the default 422 echoes `input` back. `_404` reflects the key. Verified, but the routes are optional and served as JSON only (not XSS).
  Fix if taken: an ASGI body-cap middleware, a `RequestValidationError` handler without `input`, and fixed `_404` codes.

[BELOW THRESHOLD, score 55] B7 (D6) `AND.md:211-224` / G14: these codes are missing from the API table: `404 unknown_fixture` (app.py:268), `413 too_large` / `422 invalid_request` on journals and review (app.py:247-249, 316-318), and `200 handoff`. Verified, additive.
  Fix: add a G14 addendum row.

[BELOW THRESHOLD, score 55] B8 (D7) `passport/view.py:278` vs `demo/lab.py`: the dpo run id is derived twice, and the passport links `#lab/<run_id>` on a provenance mismatch. Already disclosed (dev doc:181).
  Fix: take the run_id from `lab.lab_rows()` (null on mismatch).

[BELOW THRESHOLD, score 55] B9 (T4) `next_step.py:153`: the `status != "mapped"` filter is untested for a `save_unmapped` symptom concept. The surviving mutant errs toward clinician_handoff (the safe side).
  Fix: add the syn-004 pain=`save_unmapped` test next to test_next_step_unit.py:452.

[BELOW THRESHOLD, score 50] B10 (S3) `service.py:198-210`: the duplicate check uses `pid not in duplicate` on a list, which is quadratic. Bounded by the 1 MiB cap at about 0.5 s per request.
  Fix: make `duplicate` a set (keep the list for output order), refuse `len(decisions) > len(proposals)` early, and truncate the echoed id lists.

[BELOW THRESHOLD, score 50] B11 (S5) `.github/workflows/engine.yml`: no `permissions:` block, mutable action tags, and modal's transitive dependencies are not locked in the deploy job. Hardening only, since fork PRs never see the secrets.
  Fix: `permissions: contents: read` and SHA-pinned actions.

[BELOW THRESHOLD, score 40] B12 (S4) `journal.py:161`: the check-in id is `journal_id[:8]-c{n}`, and review without `journal_id` is allowed by design (app.py:314-316). The UI always sends journal_id. Brute-forcing about 2^24 guesses against one container, for synthetic data only, is low impact.
  Fix if taken: require `journal_id` on review.

[BELOW THRESHOLD, score 40] B13 (S7) `.claude/usr/unknown/worktree-agent/worktree-agent-handoff.md:24,27`: the file exposes agent-host paths (a home-directory bin path and a plugin tool path). Verified, but there are no secrets or hosts, and `.claude/usr/` handoffs are a tracked convention (see matt-mo/cto).
  Fix if taken: genericise the two paths.

[BELOW THRESHOLD, score 40] B14 (D11) `organiser-rules.md:29-30`: eligibility is still "unverified". I can't tell whether HAC-58 covered team details. Mark it met only if HAC-58's confirmation covers them.

[BELOW THRESHOLD, score 40] B15 (D12) README and architecture claims with no ledger row of their own. Already disclosed in the dev doc, and the ledger-row test is the agreed SC7 mechanism.

[BELOW THRESHOLD, score 35] B16 (S6) no CSP / nosniff / frame-ancestors headers. Defence in depth only. The reviewer verified there are no DOM sinks, and `safeHref` is in place.

[BELOW THRESHOLD, score 35] B17 (D8) the AM-1 label is defined in two places (memory/registry.py:53, evidence/registry.py:30). Drift fails at load time, so this is maintenance only. Fix: import one constant.
