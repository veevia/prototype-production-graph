# Contributing

**TL;DR:** Change one workflow concern, prove it with regression tests and the fictional dry run, and never include private project data.

## Development

Use Python 3.11+ and Node.js 22+. Follow the setup in [README.md](README.md), then:

```bash
python -m pdg validate
python -m pdg docs
python -m pdg docs --check
python -m pytest -q
python -m pytest -q scoring/test_vpg_score.py
```

The suite uses real Chromium for browser tests; other tests stub the browser to
exercise state transitions. Tests explicitly skip private workspace-only evidence
checks when their sources are absent. A skip is not proof of customer validation.
Generated catalogs and schemas must be regenerated rather than edited manually.

CI installs the exact versions in `constraints.txt` and splits the suite into three
parallel jobs per Python version (see `.github/workflows/test.yml`). Locally,
`python -m pytest -q` still runs all of it. Raise a pinned version only after the
full suite passes with it: a new Playwright brings a new Chromium.

Preserve human gates, explicit failures, rule lifecycle enforcement, and provenance.
Add a regression test for behavior changes. Do not weaken a check to make an example pass.

## Scope-out

Automatic model execution, cloud hosting, and secret storage are outside this repository's scope.
