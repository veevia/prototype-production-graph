---
doc: product
status: filled
project: Lot Release Workbench (fictional example)
---

# Product — Lot Release Workbench (fictional example)

> **TL;DR:** Cut the median lot review from 11 to 4 minutes without releasing a single out-of-spec lot.

## Problem

- **Problem statement:** Reviewers re-key certificate values to compare them with the specification, which is slow and still misses out-of-spec values.
- **Job (one sentence):** When a lot arrives with its supplier certificate, confirm every result against our specification so compliant lots are released the same shift and the rest are held with a clear reason.
- **Primary persona (one sentence):** A plant QA reviewer who checks 15–20 incoming ingredient lots a shift against supplier certificates.
- **Top pain (one sentence, with evidence):** Re-keying certificate values into a spreadsheet takes a median 11 minutes per lot and still lets out-of-spec values past the first review. — E-01, E-02, E-03
- **Opportunity:** Show every certificate value next to its limit with a derived, explained verdict, so the reviewer decides on one screen without re-keying.
- **POV:** A plant QA reviewer needs to confirm a certificate against the specification without re-keying it because reviewers trust a derived verdict when they can see each value next to its limit (I-02).
- **We design against:** Auto-release with no human decision; A generic document inbox that hides the numbers

## Users

Primary: plant QA reviewers (E-01, E-11). Secondary: the QA lead (escalations, E-06) and supplier quality (notices, E-08).

## Value proposition

Reviewers see every certificate result against its limit, with a derived and explained verdict, and decide on one screen.

## Requirements

| ID | Type | Priority | Requirement | Evidence / assumption | Acceptance |
|---|---|---|---|---|---|
| R-01 | user | P0 | Show every certificate result next to its specification limit, with its result | E-01, E-04 | Each parameter row shows the specification, the certificate value and the result; No value has to be re-keyed |
| R-02 | user | P0 | Derive a verdict (ready, hold, escalate) and show how it was derived | E-07, A-01 | The verdict names the results that drive it; Each row shows its derivation |
| R-03 | business | P0 | Allow release only when every result is within specification | E-03, E-05 | Release is disabled with an 'unlocks when' reason otherwise |
| R-04 | business | P0 | Require a rationale of at least 20 characters for hold and reject | E-05 | A shorter rationale is refused with a message, and focus moves to the field |
| R-05 | user | P0 | Escalate lots with a missing or unreadable result to the QA lead, never lowering the tier | E-06 | An unreadable value makes the verdict 'Escalate to QA lead' |
| R-06 | business | P0 | Record every decision with the reviewer, the time, the rationale and the verdict at that moment | E-05 | The decision log lists every decision, newest first |
| R-07 | user | P1 | Draft the supplier notice from the results that need action, and never send it from the tool | E-08, A-03 | The draft lists every result that needs action; No send control exists |
| R-08 | technical | P0 | Run offline in a browser from one file on the plant tablets | E-10 | Opens from file:// with zero network requests |
| R-09 | user | P1 | Filter the queue by status and search it, with a way back from an empty result | E-11, A-04 | An empty result offers 'Reset filters' |

## Constraints

| ID | Type | Constraint | Source |
|---|---|---|---|
| C-01 | technical | No internet on plant tablets | S-05 SOP §6 (E-10) |
| C-02 | regulatory | Decisions must be attributable to a named reviewer with a time | S-05 SOP §3 |
| C-03 | time | Pilot-ready prototype in six weeks | S-01 brief |
| C-04 | design | Use the Fabrikam Quality UI guide | S-07 |

## Scope

- **In scope:** Lot queue with derived verdicts; Lot review: comparison, verdict, guarded decision with rationale; Draft supplier notice; Decision log; Loading, empty, error and not-found states
- **Out of scope:** Sending supplier notices; LIMS or ERP integration; Editing specifications; Sign-in and multi-user sync
- **Non-goals:** Auto-releasing lots without a human decision; Replacing the QA lead's judgement on escalations; Supplier scorecards

## Success criteria

| ID | Kind | Metric | Baseline | Target | Method |
|---|---|---|---|---|---|
| M-01 | north_star | Median review time per lot | 11 min (time study, n = 40) | ≤ 4 min | Timed moderated sessions, 5 reviewers per round |
| M-02 | supporting | Out-of-spec values caught on first review | 1 of 4 (time study) | 4 of 4 (100%) | Seeded out-of-spec lots in the session set |
| M-03 | guardrail | Wrong releases | 0 | 0 | Every release checked against the specification in the session log |
| M-04 | supporting | Reviewers who try to bypass the release guard | not measured (new) | ≤ 1 of 5 | Session observation |

## Rollback triggers

- If fewer than 4 of 5 reviewers complete S-01 unaided in round one, stop and revisit the comparison layout
- If any session releases an out-of-spec lot, stop the pilot and fix the guard before round two

## Open questions

| ID | Question | Light | Trigger | Expiry | Owner |
|---|---|---|---|---|---|
| Q-01 | Can the plant's LIMS export certificate values as structured data? | 🟡 | The LIMS owner confirms the export format | 2026-10-31 | LIMS owner (fictional) |
