---
doc: evaluation
status: filled
project: Lot Release Workbench (fictional example)
thresholds: {validation: {min_task_success: 0.8}}
---

# Evaluation — Lot Release Workbench (fictional example)

> **TL;DR:** A version reaches Wei only when S-01–S-04 pass at 390, 768 and 1440 px with zero axe violations, and no blocking defect is open.

## Product quality gates

Every P0 requirement (R-01–R-06, R-08) is covered by a passing scenario; the guardrail M-03 (wrong releases) stays at 0.

## Design quality gates

Hierarchy, specificity, consistency and semantic colour score ≥ 4 of 5 (design-quality rubric).

## Accessibility gates

0 axe violations (WCAG 2.2 A/AA); visible focus; targets ≥ 24 px (44 px on tablets); text ≥ 12 px.

## Usability gates

Task success ≥ 80% on S-01–S-04 (T-01); median release time ≤ 4 min (M-01).

## Functional gates

No console errors; every planned state renders; the release guard and the rationale rule hold.

## Technical gates

Offline single file; domain unit tests pass; bundle ≤ 1.5 MB; development.md complete.
