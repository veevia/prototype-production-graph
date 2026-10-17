---
title: "Design POV — <product / feature>"
type: template
template-for: design-pov
status: canonical
owner: Wei Wei
last-updated: 2026-04-20
loop-phase: design
source: Author artifact template; private programme examples omitted
tags: [type/template, type/pov, purpose/align, loop/design, status/canonical]
---

<!--
  DESIGN POINT OF VIEW (POV) — ISE-aligned
  An opinionated design stance. The first artifact of the DESIGN phase —
  translates UNDERSTAND findings into a position the team commits to.

  A POV picks a side. It says who we design FOR and who we design AGAINST.
  If the POV could be the POV for any product, it's not a POV.

  Grounded in ISE's Design POV template: TL;DR → Background → Hypothesis →
  Goals → Principles → HMW → User Flow → UI/UX → Audience → Success Metrics
  → Deep Dive (Why / Why Now / Opportunities / Assumptions / Risks / Out-of-Scope).

  Remove this comment block before sharing.
-->

# Design POV — &lt;product / feature name&gt;

> **👥 For cross-functional partners**
>
> **What this is:** An opinionated stance — who we're designing *for*, who we're designing *against*, and why now. A POV picks a side.
> **Who owns it:** Design lead.
> **What we need from you:** Disagree visibly *before* we build to it. A POV that survives a quiet review doesn't survive contact with users. See `GLOSSARY.md` for terms.

> **TL;DR — the POV in one sentence:**
>
> **We believe** &lt;primary persona&gt; **needs** &lt;change in their life/work&gt; **because** &lt;underlying insight from research&gt;.
>
> **We will win when** &lt;observable outcome&gt;.

Example:

> **We believe** mid-career ops managers need to stop being the synchronous bottleneck for their teams **because** every interrupt costs them 23 minutes of recovery and they measure their own success by throughput, not availability.
>
> **We will win when** ops managers report fewer than 3 sync interrupts per day, measured over a 2-week window.

## Who reviews what

| Function | Focus on | React to |
|---|---|---|
| PM | Goals (§4), Success metrics (§14) | Validate against business strategy |
| Engineering | Technical considerations (§20), User flow (§11) | Flag feasibility blockers early |
| Marketing / GTM | FOR/AGAINST (§5–6), Principles (§10) | Validate market positioning |
| Research / UX | Insight (§7), HMW (§9), Assumptions (§18) | Confirm research supports the stance |
| Legal / Privacy | Risks (§19), Audience (§13) | Flag compliance concerns |
| Executive sponsor | TL;DR + Why Now (§16) + Traffic Light (§25) | Decide: commit, challenge, or block |

## 1. Metadata

| Field | Value |
|---|---|
| Product / feature | &lt;name&gt; |
| Author (Accountable) | &lt;single name — not a committee&gt; |
| Design Lead | &lt;name&gt; |
| Product Manager | &lt;name&gt; |
| Engineering Lead | &lt;name&gt; |
| Stakeholders | &lt;who must review before this moves to Design Brief&gt; |
| Based on | &lt;links to `persona.md`, `jtbd.md`, `user-journey-map.md`, `ux-research-report.md`&gt; |
| Date | YYYY-MM-DD |
| Status | draft / review / approved |
| Version | v1 / v2 / ... |

## 2. Background

Context on why this POV exists now. Previous research, user pain, or business goals that led here. Short — fits on one slide.

&lt;Add here.&gt;

## 3. Hypothesis

ISE format: *based on [observations], if we [do X for Y users], then we expect [Z metric or outcome] to move. We will know this is true when we see [signal].*

&lt;Add here.&gt;

## 4. Goals

What this POV commits to achieve. 2–4 goals max.

- **Goal 1:** &lt;e.g., "Reduce sync-interrupt volume for pilot cohort by 50%"&gt;
- **Goal 2:** &lt;...&gt;
- **Goal 3:** &lt;...&gt;

### Non-goals

What this POV explicitly does *not* try to achieve. Protects focus.

- &lt;...&gt;
- &lt;...&gt;

## 5. Who we design FOR

The primary persona(s). Named explicitly. If more than 2 primary personas, the POV isn't focused enough yet.

| Persona | Link |
|---|---|
| Primary | &lt;link to `persona.md`&gt; |
| Secondary | &lt;link, or "none"&gt; |

## 6. Who we design AGAINST

The anti-persona. The users we're *not* optimizing for — and we're okay with that.

&lt;e.g., "We are not optimizing for first-time users completing a single transaction. They are welcome but they will not shape our decisions."&gt;

Stating this prevents scope drift. If a stakeholder later asks "what about casual users?", the answer is "see the POV."

## 7. The insight

One paragraph. The non-obvious thing research revealed. If this paragraph sounds like it could have been written without research, it's not an insight — it's a platitude.

&lt;e.g., "Ops managers don't just want 'less work'. They want throughput without being seen as unresponsive. This is why they accept the interrupt cost: saying 'not now' is more expensive to their reputation than the 23-minute recovery."&gt;

## 8. The opportunity

What becomes possible if we act on the insight. One paragraph.

&lt;e.g., "If we can surface async-ready updates at moments the manager was going to be interrupted anyway, we intercept the interrupt without forcing them to signal unavailability."&gt;

## 9. How Might We…

Reframe the opportunity as an actionable design challenge the team can brainstorm against. 1–3 HMWs; more than 3 means the POV isn't focused.

- **How might we** &lt;intercept the interrupt&gt; **in a way that** &lt;preserves the manager's social standing&gt;?
- **How might we** &lt;...&gt; **so that** &lt;...&gt;?

## 10. Guiding principles

3–5 principles that will guide every subsequent decision. Principles are commitments, not platitudes — each has a **viable opposite** and a **corollary** (what we reject).

| # | Principle | Corollary — what we reject |
|---|---|---|
| 1 | &lt;e.g., "Async by default"&gt; | &lt;e.g., "We will not add sync push notifications"&gt; |
| 2 | ... | ... |
| 3 | ... | ... |

Principles should also hold up against:

- **Responsible Innovation** — which of the 10 RI dimensions (e.g., Wellbeing, Economic Security, Safety, Inclusivity) most apply here?
- **Accessibility** — how does this principle serve users with disabilities (≈16% of users globally)?
- **Inclusive Product** — does this principle hold across underrepresented personas?

A principle with no corollary is a feel-good statement.

## 11. User flow

The journey the user takes under this POV, in 4–8 steps. Link to a Figma flow or low-fi diagram if one exists.

1. &lt;entry point / trigger&gt;
2. &lt;next step&gt;
3. &lt;...&gt;
4. &lt;success or exit state&gt;

&lt;Figma link or embedded diagram.&gt;

## 12. UI / UX patterns

The interface patterns, components, or interactions that are critical to this POV. Not a spec — the *moves* that matter.

- &lt;e.g., "The async-capture entry lives inside the review surface itself, not as a separate mode"&gt;
- &lt;e.g., "Response quality signals are surfaced in the feed, not only in the review"&gt;
- &lt;...&gt;

## 13. Audience

Who we're building this *for* (users) and who we're building this *with* (stakeholders who shape it).

- **Primary user:** &lt;persona link&gt;
- **Secondary user:** &lt;persona link, or "none"&gt;
- **Buyer / sponsor** (if different): &lt;role&gt;
- **Stakeholder review cohort:** &lt;team, leads, partner orgs&gt;

## 14. Success metrics

How we'll know the POV is right (or wrong). Feeds the PRD. Both quantitative and qualitative.

| Outcome | Metric | Baseline | Target | Window | Evidence type |
|---|---|---|---|---|---|
| &lt;what should change&gt; | &lt;measurable signal&gt; | &lt;now&gt; | &lt;end&gt; | &lt;duration&gt; | quant / qual |

Include at least one **guardrail metric** — a metric we don't want to hurt.

| Guardrail | Metric | Must-not-breach threshold |
|---|---|---|
| &lt;e.g., support ticket volume&gt; | &lt;metric&gt; | &lt;bound&gt; |

If we cannot name a measure, we cannot tell success from confirmation bias.

---

## Deep Dive / Pitch

*This section is for detailed logic behind the design choices. Used when pitching the POV up or across the org.*

### 15. Why

Why is this the right solution, right now, with the right team? The strategic case.

&lt;Add here.&gt;

### 16. Why now

External factors or internal priorities driving urgency. What changes if we wait?

&lt;Add here.&gt;

### 17. Opportunities

Secondary benefits or adjacent wins discovered during the POV process. Not commitments — signals for the roadmap.

- &lt;...&gt;
- &lt;...&gt;

### 18. Assumptions

What we're assuming to be true. List them so they can be challenged and later validated.

- &lt;...&gt;
- &lt;...&gt;

### 19. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | &lt;technical constraint&gt; | L / M / H | L / M / H | &lt;...&gt; |
| 2 | &lt;user confusion&gt; | | | |
| 3 | &lt;market / timing&gt; | | | |

### 20. Technical considerations

Notes for engineering re: feasibility, APIs, performance, existing systems to integrate with.

&lt;Add here.&gt;

### 21. Open questions

Things that still need answers before we can move to Design Brief.

- &lt;...&gt;
- &lt;...&gt;

### 22. Out of scope (for this POV)

- &lt;item — with one-line reason&gt;
- &lt;item — with one-line reason&gt;

### 23. What would make us wrong

The evidence that would invalidate this POV. Per `alignment-playbook.md` — name disagreement upfront.

&lt;e.g., "If in user testing, ops managers prefer the interrupt to async updates even when the async version is equally rich, the 'async-first' premise is wrong and we reframe."&gt;

---

## 24. Disagreement heard

Surface disagreement before locking the POV. One-shot consensus is usually compliance.

| Who | Function | Their objection | How resolved |
|---|---|---|---|
| &lt;name&gt; | &lt;PM / Eng / Legal / …&gt; | &lt;their concern&gt; | &lt;outcome or "logged as open"&gt; |

Or explicitly: *"Dissent invited, none surfaced despite prompting on &lt;date&gt; by &lt;name&gt;."*

## 25. Traffic Light

One Traffic Light on the POV itself. Required before moving to Design Brief.

```yaml
traffic_light: green | yellow | red
traffic_light_owner: <name>
# --- if yellow ---
traffic_light_trigger: <what research or check closes this>
traffic_light_expiry: YYYY-MM-DD
# --- if red ---
traffic_light_blocker: <what blocks commitment>
traffic_light_unblock_owner: <name>
```

## 26. Next steps

- [ ] Review with Design Lead
- [ ] Review with Product Manager
- [ ] Sync with Engineering on feasibility
- [ ] Inclusive Product Council feedback (schedule)
- [ ] Accessibility review (AX Design Checklist)
- [ ] Move to Design Brief (`design-brief.md`)

## 27. Changelog

| Date | Change | By |
|---|---|---|
| YYYY-MM-DD | Initial POV | &lt;name&gt; |

---

## Quality check

- [ ] TL;DR sentence fits in ~50 words, names persona + change + insight + win condition
- [ ] Who we design AGAINST is stated
- [ ] Insight is not restatable as a platitude
- [ ] Each guiding principle has a corollary (what we reject)
- [ ] HMW statements are framed as "How might we X in a way that Y?"
- [ ] Success metrics include at least one guardrail
- [ ] Why Now is answered (not just Why)
- [ ] "What would make us wrong" is named
- [ ] Disagreement section is filled (not skipped)
- [ ] Exactly one Traffic Light

---

*Grounded in ISE's Design POV template. Enhanced with Traffic Light discipline, explicit "design against" anti-persona, corollary principles, guardrail metrics, and disagreement surfacing.*
