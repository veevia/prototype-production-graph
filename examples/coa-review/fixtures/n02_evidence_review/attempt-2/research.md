---
doc: research
status: filled
project: Lot Release Workbench (fictional example)
---

# Research — Lot Release Workbench (fictional example)

> **TL;DR:** Re-keying certificate values is the time sink and the error source (I-01: E-01, E-02, E-03); a paper test says a derived verdict can replace it (E-07).

Tags: `observed` · `reported` · `assumed`. The two logs are append-only.

## Evidence log
<!-- append-only -->
- E-01 · observed · 4 of 5 reviewers re-key certificate values from the PDF into a spreadsheet before comparing them with the specification · S-02
- E-02 · observed · The median review takes 11 minutes per lot (n = 40); re-keying is about 6 of them · S-03
- E-03 · observed · 3 of 4 out-of-spec lots were missed on first review (37 of 40 lots correct first time) · S-03
- E-04 · observed · Reviewers want each value next to its limit before deciding · S-02
- E-05 · reported · The SOP requires a written rationale for every hold or reject, attributable to a named reviewer with a time · S-05
- E-06 · observed · Unreadable values are escalated by phone to the QA lead, with no record · S-02
- E-07 · observed · In the paper test, 4 of 5 reviewers released a compliant lot from the derived verdict without re-keying · S-04
- E-08 · reported · Supplier notices are drafted by the reviewer and sent by the supplier-quality manager · S-02, S-05
- E-09 · observed · The QA lead agreed the lot-release flow and that the tool never releases a lot itself · S-04
- E-10 · reported · Plant tablets have no internet access; tools must run offline · S-05
- E-11 · observed · Reviewers handle 15–20 lots a shift · S-03, S-01
- E-12 · reported · Status is shown as icon + text + colour; red is reserved for failures · S-07

## Insights

| ID | Insight | Evidence | Confidence |
|---|---|---|---|
| I-01 | Re-keying is both the time sink and the error source | E-01, E-02, E-03 | high |
| I-02 | Reviewers trust a derived verdict when they can see the value next to its limit | E-04, E-07 | medium |
| I-03 | Escalations for unreadable values are invisible today | E-06 | medium |
| I-04 | Every decision must be attributable and explained; sending stays with supplier quality | E-05, E-08 | high |

## Assumptions

| ID | Assumption | Importance | Certainty | Riskiest | Validation |
|---|---|---|---|---|---|
| A-01 | Reviewers will release from a derived verdict without re-keying values | high | medium | yes | validated E-07 |
| A-02 | Showing the derivation next to each result is enough to catch a misread | medium | medium | no | unvalidated  |
| A-03 | The supplier-quality manager will reuse the reviewer's notice draft | medium | low | no | unvalidated  |
| A-04 | Sixteen lots represent a realistic shift queue | low | medium | no | unvalidated  |

## Open questions

| ID | Question | Blocking | Light | Trigger | Expiry | Owner |
|---|---|---|---|---|---|---|
| Q-01 | Can the plant's LIMS export certificate values as structured data? | no | 🟡 | The LIMS owner confirms the export format | 2026-10-31 | LIMS owner (fictional) |

## Missing information

- MISSING: Structured certificate exports from the LIMS (none provided)
- MISSING: Usage analytics of the current spreadsheet
- MISSING: The supplier-quality manager's view of notice drafts

## Validation findings
<!-- append-only -->
