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

## Source and update ownership

The author currently develops and uses the engine in Wei_workspace, at
`02_Workflows/prototype-design/`. This public repository is a reviewed, filtered
distribution, not a submodule or a mirror of private history.

For workspace maintainers, run from that workflow directory:

```bash
python -B scripts/export_public.py --dest /path/to/prototype-production-graph --check
python -B scripts/export_public.py --dest /path/to/prototype-production-graph --apply
```

The first command reports whether the public checkout matches the current source.
The second copies only the allowlisted distribution, regenerates public docs, and
refuses to overwrite locally edited or unowned destination files. Neither command
commits, pushes, changes GitHub visibility, or modifies an existing project run.
Resolve community contributions back into the workspace source before exporting
again; there is intentionally no automatic bidirectional merge.

After exporting, run this repository's checks, review `git diff`, then explicitly
stage, commit and push in this repository. Never subtree-push the private workflow:
its history contains customer evidence and personal review data.

## Reports and pull requests

Include the command, Python/Node versions, expected result, actual result, and a
minimal fictional reproduction. For sensitive reports, use GitHub's private
vulnerability reporting if enabled; never post credentials or customer evidence.

## Scope-out

Automatic model execution, cloud hosting, secret storage, and distribution of the
author's optional skill library are outside this release.
