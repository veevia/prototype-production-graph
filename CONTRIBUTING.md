# Contributing

**TL;DR:** Change one workflow concern, prove it with regression tests and the technical dry run, and never include
private project data.

## Development

Use Python 3.11+ and Node.js 22+. Follow the setup in [README.md](README.md), then:

```bash
python -m pdg validate
python -m pdg docs
python -m pdg docs --check
python -m pytest -q
python -m pytest -q scoring/test_candidate_score.py
python -m pdg dry-run --out /tmp/pdg-technical-check
python scripts/export_public.py
```

The suite uses real Chromium for browser tests; other tests stub the browser to exercise state transitions. Browser
tests skip when Chromium is not installed, and a skip is not a pass. Generated catalogs and schemas derive from the
graph, role cards, artifact models, rubrics and generic rule profile: change the source of truth, then regenerate them
rather than editing them manually.

CI installs the exact versions in `constraints.txt` and splits the suite into three parallel jobs per Python version
(see `.github/workflows/test.yml`). Locally, `python -m pytest -q` still runs all of it. Raise a pinned version only
after the full suite passes with it: a new Playwright brings a new Chromium.

## Changes

- Preserve graph contracts, human decision gates, tool verdicts, explicit failures, rule lifecycle enforcement,
  provenance and bounded rework.
- Add a regression test for behavior changes. Do not weaken a check to make an example pass.
- Keep artifact templates unfilled: placeholders and generic guidance, never completed business examples.
- Generate technical fixtures in temporary directories; never check in generated datasets or run snapshots.
- Do not add customer scenarios, research results, approvals, proprietary material or learned preferences.
- Keep generic default checks distinct from actual project evidence and decisions.
- Preserve licenses and required attribution.

## Architecture

The runtime is a standalone Python state machine. Generation, deterministic checking and human decisions have
separate responsibilities. Source integrations and assistant bindings are optional and project-configured. The engine is
self-contained: it needs no other repository.

## Publishing

The exporter admits only approved starter paths, refuses project-history rule profiles and credential-shaped content,
and never copies Git history. Its target must be an empty directory outside this repository. Review the resulting
contents before publishing; automated checks do not prove authorization.

## Scope-out

Automatic model execution, cloud hosting and secret storage are outside this repository's scope.
