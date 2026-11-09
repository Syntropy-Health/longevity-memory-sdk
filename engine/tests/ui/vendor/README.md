# Vendored test assets

`axe.min.js` is axe-core **4.13.0**, unmodified, from the npm registry tarball
`https://registry.npmjs.org/axe-core/-/axe-core-4.13.0.tgz`
(npm integrity `sha512-UzGt8zg7Ny8djbYMhxl2zuEevVa7r2gJjYY5Lwr1xM7+XU2nd6CkIWFTVcCIbAP63vSz71NaVyyuSk9lHKcy0A==`).

- `axe.min.js` sha256: `c24f097bd2f451d4f933e8bc7d8d539f8672a2ebcb5cc9f9f3eec8ca9470a0c1`
- Licence: Mozilla Public License 2.0, copied as `axe-core.LICENSE`.

It lives under `tests/ui/`, not `daypart/demo/static/`, so the demo never serves it (plan G10).
The UI suite injects it into the page under test. `tests/ui/test_journey_a11y.py` checks the sha256
before use, so a changed file fails the suite instead of silently changing the checks.
