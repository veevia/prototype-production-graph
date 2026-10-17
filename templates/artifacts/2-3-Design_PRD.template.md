---
title: "Product PRD — <product / feature>"
type: template
template-for: product-prd
status: canonical
owner: Wei Wei
last-updated: 2026-04-20
loop-phase: design
source: Author artifact template; private programme examples omitted
tags: [type/template, type/prd, purpose/build, loop/design, status/canonical]
---

<!--
  PRODUCT PRD
  The buildable spec. Deeper than the Design Brief; detailed enough that
  engineering can estimate, design can mock, and QA can plan.

  One PRD per shippable unit (a feature, a release, a milestone). Versioned.
  When scope changes materially, version-bump; don't silently edit.

  Remove this comment block before sharing.
-->

# Product PRD — &lt;product / feature name&gt;

> **👥 For cross-functional partners**
>
> **What this is:** The buildable spec — users, stories, requirements, rollout plan, rollback trigger. What we ship, to whom, by when, measured how.
> **Who owns it:** PM + design lead.
> **What we need from you:** Engineering — flag infeasibilities and missing non-functional requirements. Privacy / security / compliance — sign your sections. GTM — confirm positioning lands. Everyone — scrutinize **Non-goals** and **Guardrail metrics**; that's where real risk hides. See `GLOSSARY.md` for terms.

> **TL;DR:** &lt;What this release ships, to whom, and what it must achieve — e.g., "v1.2 ships the async review mode to ops managers in EU tenants, targeting 50% reduction in sync interrupts by end of Q3."&gt;

## Who reviews what

| Function | Own these sections | Sign-off needed? |
|---|---|---|
| PM | Goals (§5), Metrics (§6), User stories (§7), Rollout (§10) | Yes — co-owner |
| Engineering | Requirements (§8), Edge cases, NFRs, Rollout + Rollback (§10) | Yes — feasibility + estimation |
| Design | Design links (§9), User stories (§7) acceptance criteria | Yes — design intent preserved |
| Data / Analytics | Metrics (§6), Instrumentation feasibility | Yes — can we measure this? |
| Security / Privacy | NFRs §8 (Security, Privacy, Compliance) | Yes — binary 🟢/🔴 |
| Legal | Compliance NFRs, Rollout plan | Yes — if regulated domain |
| Marketing / GTM | Background (§2), Rollout communication (§10) | Advisory |

## 1. Metadata

| Field | Value |
|---|---|
| Product / feature | &lt;name&gt; |
| PRD version | v1.0 |
| Author (PM / design lead) | &lt;name&gt; |
| Status | draft / in-review / approved / shipped / deprecated |
| Based on | &lt;links to `design-brief.md`, `design-pov.md`, relevant `persona.md` + `jtbd.md` + `user-journey-map.md`&gt; |
| Related decisions/evidence | &lt;existing rationale or typed-record links, when relevant&gt; |
| Date | YYYY-MM-DD |
| Target ship date | YYYY-MM-DD |

## 2. Background

Context the reader needs to understand the rest. 1–2 paragraphs. Link; don't rewrite.

- **What's the situation today?** &lt;status quo in 2-3 sentences&gt;
- **What's changed to make this the right time?** &lt;trigger — user evidence, competitive move, platform shift&gt;
- **What's the strategic fit?** &lt;how this ladders to company / team bets&gt;

## 3. Problem statement

The single crisp problem this PRD solves. One paragraph. Should match the Design Brief's problem statement verbatim or be a principled refinement.

## 4. Users and personas

Named, linked, and scoped.

| Persona | Role in this release | Link |
|---|---|---|
| &lt;primary&gt; | core user | &lt;link&gt; |
| &lt;secondary&gt; | &lt;supporting&gt; | &lt;link&gt; |

Link to the relevant JTBD(s):

- &lt;link to `jtbd.md`&gt;

## 5. Goals and non-goals

### Goals

Outcomes this PRD commits to. Each is measurable.

- &lt;goal — "Reduce X by Y% by date Z"&gt;
- &lt;goal&gt;
- &lt;goal&gt;

### Non-goals (explicitly out of scope)

The hardest section. The one that prevents the PRD from becoming everything.

- &lt;non-goal — "Not supporting offline mode in v1; reconsider in v1.2 based on usage"&gt;
- &lt;non-goal&gt;

## 6. Success metrics

How we'll know after shipping. Feeds LEARN phase.

### North star

The single metric that matters most.

| Metric | Baseline | Target | Measurement window | Source |
|---|---|---|---|---|
| &lt;north star&gt; | &lt;now&gt; | &lt;end state&gt; | &lt;window&gt; | &lt;data source&gt; |

### Supporting metrics

| Metric | Baseline | Target | Measurement window | Source |
|---|---|---|---|---|
| &lt;adoption&gt; | | | | |
| &lt;engagement&gt; | | | | |
| &lt;quality / error rate&gt; | | | | |
| &lt;guardrail&gt; | | | | |

### Guardrails (things we must NOT degrade)

| Metric | Current | Must not fall below |
|---|---|---|
| &lt;e.g., checkout conversion&gt; | | |
| &lt;e.g., p99 latency&gt; | | |

## 7. User stories

Use standard format: As a &lt;persona&gt;, I want &lt;capability&gt;, so that &lt;outcome&gt;.

Each story should trace back to an HMW from the POV/Brief. If a story can't link to an HMW, it's feature drift — cut it or update the POV.

> **HMW funnel:** Generate many → validate → prioritize → commit → carry → **stories trace back ← you are here**

### Must-have (P0)

| # | Story | Persona | HMW # | Acceptance criteria summary |
|---|---|---|---|---|
| 1 | As &lt;persona&gt;, I want &lt;capability&gt;, so that &lt;outcome&gt;. | &lt;name&gt; | &lt;HMW 1&gt; | &lt;crisp criteria&gt; |
| 2 | ... | ... | | ... |

### Should-have (P1)

| # | Story | Persona | HMW # | Acceptance criteria summary |
|---|---|---|---|---|
| 1 | ... | ... | | ... |

### Could-have (P2, explicit maybe)

Anything that lands in "could-have" must have a clear deferral trigger or it becomes scope creep.

| # | Story | Persona | Deferral trigger |
|---|---|---|---|
| 1 | ... | ... | &lt;what would make us include it&gt; |

## 8. Detailed requirements

For complex features, break down requirements. Keep at the "what," not "how."

### Functional requirements

- &lt;requirement 1&gt;
- &lt;requirement 2&gt;

### Non-functional requirements

| Category | Requirement |
|---|---|
| Performance | &lt;e.g., "p95 action latency &lt; 500ms"&gt; |
| Accessibility | &lt;e.g., "WCAG 2.1 AA"&gt; |
| Security | &lt;e.g., "No PII in logs; encryption at rest"&gt; |
| Privacy | &lt;e.g., "Data retention ≤ 90 days"&gt; |
| Internationalization | &lt;e.g., "RTL supported"&gt; |
| Reliability | &lt;e.g., "SLO 99.9% monthly"&gt; |
| Compliance | &lt;e.g., "GDPR; SOC 2 Type II controls"&gt; |

### Edge cases and error states

Enumerate rather than hope-for-the-best.

- &lt;edge case — and expected behavior&gt;
- &lt;error state — and expected UX&gt;

## 9. Design

Link, don't duplicate.

- **Wireframes:** &lt;link&gt;
- **High-fi mocks:** &lt;link&gt;
- **Prototype:** &lt;link&gt;
- **Design system impact:** &lt;new/changed components&gt;
- **Accessibility plan:** &lt;link or inline&gt;

## 10. Rollout plan

### Launch approach

- &lt;e.g., "Staged rollout: 1% → 10% → 50% → 100%, 7-day gates"&gt;
- &lt;e.g., "Feature flag name: `async_review_v1`"&gt;

### Dependencies

| Dependency | Owner | Needed by |
|---|---|---|
| &lt;e.g., "New API endpoint"&gt; | &lt;team&gt; | YYYY-MM-DD |

### Migration / backward compatibility

&lt;e.g., "Existing review workflow is preserved; users opt in via settings." Or "No migration required."&gt;

### Communication

- Internal: &lt;who, when, how&gt;
- External: &lt;release notes, blog, in-product&gt;

### Rollback plan

The trigger and the mechanism. A PRD without a rollback plan is a wish.

- **Trigger:** &lt;e.g., "p99 latency rises &gt; 20% OR user error reports exceed X/day"&gt;
- **Mechanism:** &lt;e.g., "Disable feature flag; no data migration needed to reverse"&gt;

## 11. Risks and open questions

### Risks

| # | Risk | Likelihood | Impact | Mitigation | Owner | Traffic Light |
|---|---|---|---|---|---|---|
| 1 | &lt;risk&gt; | H/M/L | H/M/L | &lt;mitigation&gt; | &lt;name&gt; | 🟢 🟡 🔴 |

### Open questions

Must be closed before shipping. Each has an owner and a due date.

| # | Question | Owner | Due | Traffic Light |
|---|---|---|---|---|
| 1 | &lt;question&gt; | &lt;name&gt; | YYYY-MM-DD | 🟡 (typical while open) |

## 12. Decisions log (PRD-scoped)

Pointers to relevant existing rationale and durable choices made while writing this PRD. No new
decision file is required for routine clarification; use W5
when its criteria apply. Product choices are not automatically ADRs.

| Evidence / typed record | Title | Traffic Light (if applicable) |
|---|---|---|
| &lt;source path or canonical record ID&gt; | &lt;title&gt; | 🟢 🟡 🔴 |

## 13. Approvals

PRD is not approved until every row has a Traffic Light from the named owner.

| Role | Name | Date | Traffic Light |
|---|---|---|---|
| PM / Design lead | | | 🟢 🟡 🔴 |
| Engineering lead | | | 🟢 🟡 🔴 |
| Design lead (if separate from PM) | | | 🟢 🟡 🔴 |
| Data / analytics | | | 🟢 🟡 🔴 |
| Security / privacy reviewer | | | 🟢 🟡 🔴 |
| Sponsor / exec | | | 🟢 🟡 🔴 |

## 14. Changelog

| Version | Date | Change | Author |
|---|---|---|---|
| v1.0 | YYYY-MM-DD | Initial PRD | &lt;name&gt; |

---

## Quality check

- [ ] TL;DR passes the 10-second test
- [ ] Non-goals section is non-empty
- [ ] At least one guardrail metric is named
- [ ] User stories have acceptance criteria summaries
- [ ] Non-functional requirements cover performance, accessibility, security, privacy (not just "TBD")
- [ ] Edge cases section is filled (not "none")
- [ ] Rollback trigger and mechanism are both stated
- [ ] Every open question has an owner and a due date
- [ ] Every approval row has a Traffic Light
- [ ] All linked artifacts exist (`design-brief.md`, `design-pov.md`, `persona.md`, `jtbd.md`, `user-journey-map.md`)

---

*Template grounded in canonical PM PRD practice, extended with Traffic Light discipline. A PRD without non-goals, guardrails, and a rollback plan isn't a spec — it's a wishlist.*
