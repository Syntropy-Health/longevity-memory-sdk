# P3 deep gate: findings record (reconstructed)

The gate's raw review output (44 findings, run 6be62749, 2026-11-08) lived in the
previous container and was lost when that run was stopped. This file rebuilds the
record from the scorer result posted on HAC-38 (comment 687fdaf8) and the run summary.

Base 179d67d, gate entry a575ab7 (Hash A 91d5ceb). Reviewers: code, security, design,
test, UX, then reviewer-scorer at threshold 80. Prior short hashes: B e232c9b, C d4d41e8.

Kept (>= 80): K1 lab mismatch label verbatim; K2 dashboard import test could not fail;
K3 T10.2 ring read from the invisible radio; K4 review 422 refusal flow untested;
K5 flagged-proposal path untested; K6 LOINC footer paraphrased ATTRIBUTION; K7 G29
supersedes G27(8), cites §4.1.
Fixed below threshold: B1 usage doc "or upload one"; B2 overlapping showReview double
render; B3 #research missing from T10.3/T10.4 loops.
Earlier in the same gate: R1 Correct on a flagged proposal states the shown unit/date.
Not fixed (below threshold, in the dev doc's known issues): no UI test for the
session-ended path; passport card order; no CSP; journal id in one link URL; blank
screen on a crafted #review/__proto__ link.
