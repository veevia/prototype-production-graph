---
doc: development
status: filled
project: Lot Release Workbench (fictional example)
---

# Development — Lot Release Workbench (fictional example)

> **TL;DR:** A dependency-free, single-file offline build proves the interaction and the rules; production needs the LIMS
> certificate feed, sign-in and a server-side decision log.

## Architecture

Static single-page app. `src/domain.js` holds the pure rules (derivation, verdict, guard, rationale, notice draft) and runs
unchanged in the browser and under `node --test`. `src/app.js` renders four hash-routed screens from inlined data and keeps
decisions in `localStorage`. `build.py` inlines CSS, JS and data into `dist/prototype.html` and writes a hashed manifest.

## Technology

HTML5, CSS custom properties (the design tokens), vanilla ES5 JavaScript, Python 3 for the build, Node 22's built-in test
runner. No framework and no network dependency, because plant tablets are offline (C-01).

## Components

Shell (header, navigation, synthetic-data banner, footer) · filter chips · search · data table (stacks below 640 px) · status
chip · verdict panel · decision form (options, rationale, errors) · notice draft · state panels (loading, empty, error, not needed).

## Data and APIs

`data/lots.json`: specifications, suppliers and lots (seeded, synthetic). Mocked seams, and what production needs for each:
- Certificates: inlined JSON → the LIMS export API (open question Q-01).
- Decisions: `localStorage` → a server-side, attributable decision log with sign-in (C-02).
- Notices: saved drafts → hand-off to supplier quality's mailbox (sending stays outside the tool, E-08).

## Folder structure

`src/` (index.html, styles.css, domain.js, app.js, data/seed.json) · `data/` (generate.py, lots.json) · `content/` (copy deck) ·
`tests/` (domain.test.js) · `dist/` (built) · `build-manifest.json`.

## Standards

Tokens only (no colour literal outside `:root`); every screen marked `data-screen`; every state marked `data-state`;
WCAG 2.2 AA; 44 px targets; one h1 per screen; focus moves to the heading on navigation.

## Testing

`node --test tests/domain.test.js` for the rules; the pdg browser suite (Playwright + axe) for scenarios S-01–S-04, states,
responsive behaviour and accessibility at 390, 768 and 1440 px.
