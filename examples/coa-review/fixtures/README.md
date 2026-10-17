# Dry-run fixtures

> **TL;DR:** One folder per node attempt holds what an agent would submit for the fictional example. `ScriptedExecutor`
> plays them through the real engine, so the dry run tests the workflow, not an agent. Regenerate every fixture with
> `python _author.py` from this folder.

## Format

`<node>/attempt-<n>/fixture.yaml`:

```yaml
run:                                   # optional commands, run before the outputs are read
  - ["{python}", "{project}/prototype/build.py", "--src", "{project}/prototype", "--out", "{work}/prototype_build"]
outputs:                               # output key → file (relative to this folder, or a placeholder path)
  prototype_build: "{work}/prototype_build"
  development_md: "development.md"
```

Placeholders: `{python}` (the running interpreter), `{project}`, `{work}` (the attempt's work folder), `{fixture}`
(this attempt's folder), `{artifact:<key>}` (the current artifact's path) and `{pkg}` (the package root). A node
attempt with no folder falls back to the latest earlier attempt, which is how an unchanged re-run is scripted.

## The story

- N01 attempt 1 misses the design authority. N02 reports a resolvable gap, the intake loop (E03) fires, and attempt 2
  registers it.
- N11 attempt 1 builds with `attempt-1/overlay/`, a draft whose status chips use an undeclared token pairing (a real
  contrast failure that axe measures) and whose decision panel sits above the comparison.
- N14 attempt 1 records a **simulated** QA-lead concern about the layout, labelled simulated and never evidence.
- N16 attempt 1 traces the concern to N08 and the tool's contrast findings to N11. Attempt 2 of N08, N10 and N11 fixes
  both, and N16 attempt 2 finds nothing blocking.
- N19 writes three lessons. The one resting on the simulated concern is classed `inferred`, never `verified`.

Shared control documents respect section ownership: N03 and N04 submit only their own sections of `product.md`, and
N07 leaves "Interactions and states" to N08.
