---
title: "Design Brief — <project>"
type: template
template-for: design-brief
status: canonical
owner: Wei Wei
last-updated: 2026-04-20
loop-phase: design
source: Author artifact template; private programme examples omitted
tags: [type/template, type/brief, purpose/align, loop/design, status/canonical]
---

<!--
  DESIGN BRIEF — ISE UDB-aligned
  The plan before any work is done. A written doc to understand and align on:
    Why this effort is worth spending time on
    Who owns it and how the team is organized (RACI)
    How we'll approach the problem
    What people can expect from us (outcomes + outputs)
    When they should expect it

  A good brief can be read in 5 minutes and referred to all quarter.
  Aim for ~1 hour of drafting before sending to Crit / async review.

  Grounded in ISE's Universal Design Brief: 1-Liner Why → Background →
  Hypothesis → Goal → People Problems/JTBD → Team (RACI) → Outputs &
  Outcomes (Shared Knowledge vs Solution) → Timeline → Principles → UEF →
  Assumptions → Main Scenarios.

  Remove this comment block before sharing.
-->

# Design Brief — &lt;project name&gt;

> **👥 For cross-functional partners**
>
> **What this is:** The one-page alignment doc — the problem, the audience, the outcomes we're chasing, and the constraints we respect. *Not* the PRD; that comes next.
> **Who owns it:** Design lead (Accountable) + Sponsor.
> **What we need from you:** Sign or flag. Disagreement goes in §Disagreement *before* sign-off, not after. See `GLOSSARY.md` for terms.

> **TL;DR:** &lt;What we're making, for whom, and what it must achieve — e.g., "An async review mode for ops managers that intercepts 50%+ of would-be sync interrupts, shipped by Q3."&gt;

## Who reviews what

| Function | Focus on | Sign-off needed? |
|---|---|---|
| PM | Goals (§5), People Problems (§6), Scope (§11) | Yes — co-owner |
| Engineering | Constraints (§16), Risks (§14), Timeline (§9) | Yes — feasibility |
| Marketing / GTM | Why statement (§2), Principles (§10), Scope (§11) | Advisory |
| Legal / Privacy | Constraints (§16 policy/compliance row), Risks (§14) | Yes — if regulated |
| Executive sponsor | TL;DR + Sign-off (§19) | Yes — green light to proceed |

## 1. Metadata

| Field | Value |
|---|---|
| Project | &lt;name&gt; |
| Client / sponsor | &lt;customer or internal sponsor&gt; |
| Date | YYYY-MM-DD |
| Contributors | &lt;names + disciplines&gt; |
| Based on | &lt;links to `design-pov.md`, `persona.md`, `jtbd.md`, `user-journey-map.md`, `ux-research-report.md`&gt; |
| Status | draft / review / approved |

## 2. 1-Liner Why Statement *(required)*

Why is this important? One sentence, starts with *"We believe,"* focuses on the user. Not the *how* (strategy) or the *what* (specific solutions).

&gt; **We believe** &lt;...&gt;.

Example: *"We believe people should get their favorite video content with little effort."*

## 3. Background

How did this effort start and why are we investing now? What's been tried? What leadership strategy drives this? What's changed in the market that forces this? Short — fits on one slide.

&lt;Add here.&gt;

## 4. Hypothesis

ISE format: *"Based on [XYZ observations], if we do [ABC], then we expect [metrics] to move."*

&lt;Add here.&gt;

## 5. Goal of our design effort *(required)*

What does Design want to show with this effort? Choose one primary intent:

- High-level vision for a pitch or debate
- Specific solutions to execute
- Alignment workshop
- New ideas sprint
- Other: &lt;...&gt;

&lt;Add here. Include non-goal if helpful.&gt;

### Non-goals

- &lt;...&gt;
- &lt;...&gt;

## 6. People Problems / JTBD *(required)*

Rooted in research (generative or user study). Pick 1–3 focus problems. More than 3 means the brief isn't focused.

Also consider the ~16% of users with a disability — what's the people problem viewed through that lens?

| # | People problem / JTBD | Evidence tag | Link to research |
|---|---|---|---|
| 1 | &lt;problem statement, or JTBD "When…I want to…so I can…"&gt; | observed / reported / assumed | &lt;`ux-research-report.md` §#&gt; |
| 2 | ... | ... | ... |
| 3 | ... | ... | ... |
### How Might We (from POV)

Carry the committed HMW statements from `2-1-Design_POV.md` §9 verbatim. Do not rewrite — if they need rewriting, update the POV first.

> **HMW funnel:** Generate many → validate with evidence → prioritize through the journey → **commit 1–3 in the POV → carry in the brief ← you are here**

- **How might we** &lt;verbatim from POV §9&gt;?
- **How might we** &lt;...&gt;?
## 7. Team — RACI *(required)*

One **Accountable**, one or more **Responsible**.

- **R = Responsible:** on the hook to deliver the outputs.
- **A = Accountable:** single POC who ensures on-track, quality work. One person — empowerment requires clear ownership.
- **C = Consulted:** subject-matter experts; 2-way communication.
- **I = Informed:** kept up-to-date in FYI mode; 1-way.

| Role (RACI) | Name | Discipline | Team | Expectations |
|---|---|---|---|---|
| Accountable | &lt;name&gt; | Design Lead | | Runs the effort end-to-end; signs the brief |
| Responsible | &lt;name&gt; | &lt;PD / Researcher / Eng&gt; | | Delivers &lt;specific output&gt; |
| Responsible | | | | |
| Consulted | &lt;name&gt; | &lt;SME&gt; | | 2-way; review &lt;scope&gt; before sign-off |
| Consulted | &lt;name&gt; | &lt;Sponsor / Exec&gt; | | Approves the brief; unblocks when escalated |
| Informed | &lt;name&gt; | &lt;leadership&gt; | | FYI on weekly status |

## 8. Outputs & Outcomes *(required)*

Outputs are tangible artifacts. Outcomes are the alignment and knowledge shifts we're aiming for. Both matter.

### 8a. Shared Knowledge outcomes

Alignment and understanding we commit to produce.

- [ ] Lit review from existing research (high-level findings)
- [ ] Gap analysis vs competitors (&lt;which ones&gt;)
- [ ] Experience audit via UEF (see §12)
- [ ] Current data / metrics readout and insights
- [ ] Stakeholder and subject-matter expert perspectives captured
- [ ] Alignment on principles, goals, success (via Spicy Debate, IPC exercises)
- [ ] Alignment on how this ladders up to org goals
- [ ] &lt;other&gt;

### 8b. Solution outputs

Tangible concepts, POV statements, and design artifacts.

- [ ] Research and/or Engineering plan to validate
- [ ] Concepts illustrated with designs / demos / prototypes
- [ ] POV on suggested solution(s) and opportunity
- [ ] Feedback from people in RACI & extended team
- [ ] Inclusive Product Council (IPC) review
- [ ] Accessibility review (AX Design Checklist + MVA Scorecard)
- [ ] MVP or milestone plan to validate core hypotheses
- [ ] Content Design contributions (if any)
- [ ] Detailed Shop / production work (if applicable)
- [ ] POV share-out to team, extended team, leads

## 9. Proposed timeline & milestones

High-level only. Detailed milestones live in the PRD / project plan.

| Phase | End date | Gate |
|---|---|---|
| Design | YYYY-MM-DD | PRD signed 🟢 |
| Build | YYYY-MM-DD | Prototype testable |
| Learn | YYYY-MM-DD | Measurement against §5 outcomes |

### Rollout stages *(if applicable)*

ISE-style staged rollout vocabulary — use those that fit, skip those that don't:

- **Dogfood** (internal users) — date: &lt;...&gt;
- **Smoke Test** (small external cohort) — date: &lt;...&gt;
- **Learning Candidate** (structured experiment) — date: &lt;...&gt;
- **Geo Test** (regional rollout) — date: &lt;...&gt;
- **Back Test** (expansion + learning validation) — date: &lt;...&gt;

## 10. Guiding principles

Good principles help make decisions and have a **viable opposite** (*"Simple Design"* isn't a principle — no one aims for complex). 3–5 principles, each with a corollary.

| # | Principle | Corollary — what we reject |
|---|---|---|
| 1 | &lt;e.g., "Async by default"&gt; | &lt;e.g., "No new sync push notifications"&gt; |
| 2 | ... | ... |
| 3 | ... | ... |

### Responsible, inclusive, accessible principles

- **Responsible Innovation dimensions** — which of the 10 RI dimensions are most relevant (e.g., Wellbeing, Economic Security, Safety, Inclusivity, Privacy)? List 1–2:
- **Product Equity** — which equity principles apply?
- **Inclusive Product** — how do we hold the line on diverse representation?
- **Accessibility** — the AX Design Checklist will be applied; owner: &lt;name&gt;

## 11. Scope

Both in and out. The "out" list matters more than the "in" list.

### In scope

- &lt;...&gt;
- &lt;...&gt;

### Out of scope (explicitly)

- &lt;item — with one-line reason&gt;
- &lt;item — with one-line reason&gt;

Scope-out that reads *"we'll think about that later"* is a warning sign — name it as a risk in §14.

## 12. Current experience evaluation (UEF)

What are your findings and learnings from auditing the existing experience? Gaps, inconsistencies, redundancies, opportunities?

Apply the Universal Evaluation Framework (UEF) before building anything net-new. Link the audit if already completed.

- **Audited surface:** &lt;what was audited&gt;
- **Key gaps:** &lt;...&gt;
- **Key inconsistencies:** &lt;...&gt;
- **Opportunities revealed:** &lt;...&gt;
- **Audit link:** &lt;...&gt;

## 13. Assumptions

What we're assuming to be true to move forward. Listing them invites challenge.

- &lt;...&gt;
- &lt;...&gt;

## 14. Risks

Top 3–5 risks to the outcomes. Each with an owner and a Traffic Light.

| # | Risk | Impact if realized | Owner | Traffic Light |
|---|---|---|---|---|
| 1 | &lt;risk&gt; | &lt;impact&gt; | &lt;name&gt; | 🟢 🟡 🔴 |
| 2 | ... | ... | ... | ... |

## 15. Main scenarios

The few scenarios we plan to illustrate — priority order. Focuses design; avoids edge-case rabbit holes early.

1. &lt;e.g., happy path for primary persona&gt;
2. &lt;e.g., logged-out state&gt;
3. &lt;e.g., low-connectivity / offline&gt;

## 16. Constraints

| Type | Constraint |
|---|---|
| Time | &lt;e.g., "Ship by end of Q3"&gt; |
| Resourcing | &lt;e.g., "3 designers, 4 engineers for 2 sprints"&gt; |
| Technical | &lt;e.g., "Must run inside the existing review tool; no new auth"&gt; |
| Policy / compliance | &lt;e.g., "Data residency: EU data stays in EU"&gt; |
| Brand / design system | &lt;e.g., "Follows DS v4; no new pattern inventions without review"&gt; |

## 17. Spicy Debate questions

Questions the team needs to align on before locking the brief. Not every brief has these — add only where there's real disagreement.

- &lt;...&gt;
- &lt;...&gt;

## 18. Disagreement heard

| Who | Function | Their objection | How resolved |
|---|---|---|---|
| &lt;name&gt; | &lt;PM / Eng / Legal / …&gt; | &lt;concern&gt; | &lt;outcome or "logged as open"&gt; |

Or: *"Dissent invited on &lt;date&gt;, none surfaced despite prompting."*

## 19. Sign-off

| Role | Name | Date | Traffic Light |
|---|---|---|---|
| Accountable (Design Lead) | | | 🟢 🟡 🔴 |
| Sponsor | | | 🟢 🟡 🔴 |
| Engineering Lead | | | 🟢 🟡 🔴 |
| PM | | | 🟢 🟡 🔴 |

## 20. Changelog

| Date | Change | By |
|---|---|---|
| YYYY-MM-DD | Initial brief | &lt;name&gt; |

---

## Quality check

- [ ] TL;DR passes the 10-second test
- [ ] 1-Liner Why starts with "We believe" and focuses on the user
- [ ] Hypothesis follows "based on…, if we…, then…" format
- [ ] 1–3 People Problems / JTBDs, each with evidence tag
- [ ] RACI has exactly one Accountable
- [ ] Outputs & Outcomes split into Shared Knowledge vs Solution
- [ ] Principles have corollaries (what we reject)
- [ ] Responsible Innovation dimensions named
- [ ] Accessibility owner named
- [ ] UEF audit linked or explicitly skipped with reason
- [ ] Scope-out list is non-empty
- [ ] Risks have owners and Traffic Lights
- [ ] Sign-off row has real names, not just roles

---

*Grounded in ISE's Universal Design Brief (UDB). Shared Knowledge vs Solution outputs, UEF current-state audit, and Responsible/Inclusive/Accessible principles are ISE-distinctive. A brief that fits in 5 minutes gets read; one that runs 10 pages gets skimmed.*
