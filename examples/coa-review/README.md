# Example: Lot Release Workbench (fictional)

> **TL;DR:** A fictional product used to run the whole `pdg` graph end to end: a quality reviewer compares an ingredient
> lot's certificate of analysis with its specification and records a guarded release, hold or reject decision. Every
> company, person, source and data value here is invented. None of it is evidence about a real product.

## The product

Fabrikam Beverages (Microsoft's standard fictional company) releases 15–20 ingredient lots a shift at its Riverside
plant. The brief (`sources/brief.md`) asks for a tool that shows every certificate result beside its specification,
derives a verdict with its reasoning, never releases a lot on its own, drafts a supplier notice for holds, and runs on
offline tablets.

| Screen | Route | What it proves |
|---|---|---|
| Lot queue | `#/queue` | Scan, search and open lots; loading, empty and error states |
| Lot review | `#/lot/<id>` | The comparison table leads; the derived, explained verdict opens the decision panel; the decision needs a rationale |
| Supplier notice | `#/lot/<id>/notice` | A draft notice with no send control; its closing line follows the recorded decision |
| Decision log | `#/audit` | Every decision with who, when and why, after the previous shift's (synthetic) decisions |

Scenario lots: **L-2418** is within specification (release), **L-2431** is out of specification (Brix 67.9; hold and
notice), and **L-2437** is missing a result (escalate). The browser suite runs four scenarios (S-01 release, S-02 hold
and notice, S-03 escalate, S-04 recover from a failed load and an empty search) and seven planned states at 390, 768
and 1440 px.

Test affordances: `?fail=1` fails the first queue load, `?loading=hold` holds the loading state, `?storage=off`
simulates unavailable local storage (every screen that records something then warns), `?log=empty` hides the previous
shift's decisions (a first-day plant), and `#/queue?q=<text>` pre-fills the search.

## Build and open it

```bash
python prototype/build.py --src prototype --out /tmp/lot-release     # from this folder
open /tmp/lot-release/dist/prototype.html                            # one file; works offline
node --test prototype/tests/domain.test.js                           # the verdict rules
```

The build inlines `src/` (HTML, CSS, domain rules, app) and the seeded data into one file, and writes
`build-manifest.json` (entry, stack, files with their sha256, screens, commands, unit tests, dataset, draft overlays
and build info). Two builds are byte-identical.

## What the dry run shows

`python -m pdg dry-run` (from the package root) plays the scripted agent outputs in [`fixtures/`](fixtures/README.md)
through the real engine and the real browser suite:

1. The intake loop fires once: N02 finds a missing design authority, and N01 registers it.
2. The first build (v1) carries a draft overlay. Status chips use an undeclared colour pairing (axe measures 4.23:1),
   and the decision panel sits above the comparison. A **simulated** QA-lead session raises the layout concern.
3. The gate traces the layout defect to interaction design (N08) and the contrast defects to development (N11). One
   rework cycle re-runs N08, N10, N11 and N12; the visual system (N09) is not touched.
4. Build v2 passes all 12 browser runs with 0 axe violations. The comparison resolves D-001–D-004, and the verdict is
   `improved`.
5. Release verification packages v2. Learning proposes one candidate rule (from the layout lesson, classed inferred)
   and one observation (the contrast rule R-A11Y-001 fired and helped), keeps a project-specific note apart, and
   applies nothing.

Every human gate is decided by `dry-run-auto` and recorded `human: false`, and every validation session is labelled
simulated.

## What it produces

[`expected/controls/`](expected/controls/) holds the eight control documents exactly as the dry run leaves them (the
dry-run test fails if a run differs): the [product requirements](expected/controls/product.md) with evidence, scope,
success criteria and rollback triggers; the [experience](expected/controls/experience.md) with journeys, information
architecture, user flows, interactions and states; the [design system](expected/controls/design.md); the
[prototype plan](expected/controls/prototype.md); the [development foundation](expected/controls/development.md); the
[evaluation thresholds](expected/controls/evaluation.md); the [research log](expected/controls/research.md) with the
simulated validation findings labelled; and the project [memory](expected/controls/memory.md).

## Layout

| Path | Contents |
|---|---|
| `pdg.project.yaml` | Project config (`dry_run: true`, fixtures, humans) |
| `sources/` | 7 fictional sources: brief, interviews, time study, paper test, SOP, specifications, UI guidelines |
| `prototype/src/` | `index.html`, `styles.css`, `domain.js` (verdict rules), `app.js` (router, screens, states), `data/seed.json` |
| `prototype/build.py` · `prototype/data/generate.py` | The deterministic build; the seeded synthetic-data generator |
| `prototype/content/copy-deck.md` · `prototype/tests/` | Real copy (no placeholders); Node domain tests |
| `fixtures/` | Scripted agent outputs per node attempt, and `_author.py`, which regenerates them |
| `expected/controls/` | The control documents a dry run produces (a golden snapshot) |
