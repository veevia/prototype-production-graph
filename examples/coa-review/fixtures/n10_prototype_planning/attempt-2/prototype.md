---
doc: prototype
status: filled
project: Lot Release Workbench (fictional example)
---

# Prototype plan — Lot Release Workbench (fictional example)

> **TL;DR:** A mid-fidelity, functional, offline build that tests the release guard, the rationale rule and the notice draft; the riskiest assumption (A-01) is already validated on paper (E-07).

## Goals

- Test whether reviewers release compliant lots from the derived verdict without re-keying certificate values (riskiest assumption A-01)
- Test whether the release guard and the 20-character rationale are understood without coaching
- Show every state a reviewer can meet: loading, empty, error, not found

## Fidelity

**mid** — A paper prototype already validated the riskiest assumption A-01 (E-07: 4 of 5 reviewers released from the derived verdict without re-keying). The next question is behavioural (guards, rationale, notice), which needs a clickable, functional build with realistic data — not production visuals.

## Scenarios

- **S-01** (F-01) Release a compliant lot from the queue — 16 steps; success: L-2418 is released with a rationale and appears first in the decision log
- **S-02** (F-02) Hold an out-of-spec lot and draft the supplier notice — 14 steps; success: L-2431 is on hold and a draft notice is saved, not sent
- **S-03** (F-03) Escalate a lot with an unreadable result — 9 steps; success: L-2437 cannot be released and a short rationale is refused with a clear message
- **S-04** (F-04) Recover from a failed load and an empty search — 9 steps; success: The reviewer retries, searches, and resets back to the full queue

## Required interactions

Filter and search; open a lot; choose and record a decision; draft and save a notice.

## Content

- 16+ lots across six ingredient specifications
- one out-of-spec, one missing and one borderline result at least
- a lot with both an out-of-spec and a missing result (tier rule)
- supplier contacts for the notice draft

## States

| Screen | State | Route | Marker |
|---|---|---|---|
| queue | loading | `?loading=hold#/queue` | `[data-state="loading"]` |
| queue | error | `?fail=1#/queue` | `[data-state="error"]` |
| queue | empty | `#/queue?q=no-such-lot` | `[data-state="empty"]` |
| lot | error | `#/lot/L-0000` | `[data-state="error"]` |
| notice | error | `#/lot/L-0000/notice` | `[data-state="error"]` |
| audit | empty | `?log=empty#/audit` | `[data-state="empty"]` |
| audit | error | `?storage=off#/audit` | `[data-state="error"]` |

## Worst-case records

- `lot`: `#/lot/L-2431`, `#/lot/L-2437`

## Test criteria

| ID | Metric | Threshold |
|---|---|---|
| T-01 | task success rate on S-01..S-04 | 80% |
| T-02 | median time to release a compliant lot | ≤ 4 min (baseline 11 min) |
| T-03 | reviewers who try to bypass the release guard | ≤ 1 of 5 |

## Out of scope

- Sending notices (drafts only)
- LIMS or ERP integration
- Authentication and multi-user sync
- Editing specifications

*Revision (rework cycle 1):* S-01 now checks that the comparison table's first row is visible on arrival at every viewport — the acceptance check of D-001.
