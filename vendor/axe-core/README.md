# Vendored axe-core

- **Version:** 4.11.4 (`axe.min.js`, sha256 `fb83a4378d978ecb7d2dae48a3a3778a84c971ac692f3afd45d714fba89c0f0d`)
- **Source:** the `axe-core` npm package, copied on 2026-09-26 from an installed copy of the package.
- **Licence:** Mozilla Public License 2.0 (`LICENSE`, and the header at the top of `axe.min.js`), unmodified.
- **Used by:** `pdg/tools/browser.py`, which injects it into the prototype page to run WCAG rule checks.
  Set `PDG_AXE_PATH` to use a different copy.

Update: replace both files from a newer `axe-core` release, update the version and hash above, and re-run
`python -m pytest -q tests/test_browser.py`.
