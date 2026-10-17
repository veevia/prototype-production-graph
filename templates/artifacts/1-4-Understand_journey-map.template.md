---
title: "User Journey Map — <persona> doing <job>"
type: template
template-for: user-journey-map
status: canonical
owner: Wei Wei
last-updated: 2026-04-20
loop-phase: understand
source: Author artifact template; private programme examples omitted
tags: [type/template, type/journey-map, purpose/discover, loop/understand, status/canonical]
---

<!--
  USER JOURNEY MAP
  Traces one persona doing one job across stages of the experience. Includes
  what they think, feel, do, and where it fails.

  One persona + one job per file. If you need to map multiple personas or
  jobs, create separate files and cross-reference.

  Remove this comment block before sharing.
-->

# User Journey Map — &lt;persona&gt; doing &lt;job label&gt;

> **👥 For cross-functional partners**
>
> **What this is:** The user's path through a task — what they do, think, and feel at each step — with pain points and opportunities called out.
> **Who owns it:** Design lead.
> **What we need from you:** Look at the moments of truth (the steps where the experience is won or lost). Tell us what you know about those steps from your function. See `GLOSSARY.md` for terms.

> **TL;DR:** &lt;The single most important pain point in this journey — e.g., "Between discovering the feature and first successful use, 3 of 5 participants dropped out at step 4 (configuration), where we ask for info they don't have yet."&gt;

## Who reviews what

| Function | Focus on | React to |
|---|---|---|
| PM | Moments of truth (§4), Opportunities (§6) | Validate priority; connect to roadmap |
| Engineering | Backstage (§7), Pain points with technical root causes | Flag feasibility of proposed changes |
| Marketing / GTM | Stages 1–2 (Awareness, Consideration) | Flag messaging gaps |
| Support / Success | Pain points (§5) — which ones generate tickets? | Add data on frequency |
| Executive sponsor | TL;DR + Opportunities (§6) | Confirm investment areas |

## 1. Metadata

| Field | Value |
|---|---|
| Persona | &lt;link to `persona.md`&gt; |
| Job (JTBD) | &lt;link to `jtbd.md`&gt; |
| Based on research | &lt;link to `ux-research-report.md`&gt; |
| Scope | &lt;current state / future state / both&gt; |
| Fidelity | &lt;sketch / detailed / validated&gt; |

## 2. Scenario

A short narrative that grounds the journey. 2–3 sentences.

&lt;e.g., "Maya's team adopted a new review tool last month. It's Tuesday afternoon; she has 6 PRs queued and a 4:30 meeting. She opens the tool for the first time this week."&gt;

## 3. Journey stages

Sequential stages of the experience. Each stage gets its own column of evidence. Keep stages at a single level of abstraction — don't mix "awareness" with "clicks submit button."

### Stage table

| # | Stage | Doing (actions) | Thinking (mental state) | Feeling (emotion) | Pain / Friction | Opportunity |
|---|---|---|---|---|---|---|
| 1 | &lt;Awareness&gt; | &lt;what they do&gt; | &lt;what they're thinking&gt; | &lt;emotion&gt; 😊😐😟 | &lt;friction point&gt; | &lt;design opening&gt; |
| 2 | &lt;Consideration / Trigger&gt; | | | | | |
| 3 | &lt;First attempt / Onboarding&gt; | | | | | |
| 4 | &lt;Active use / Core action&gt; | | | | | |
| 5 | &lt;Completion / Outcome&gt; | | | | | |
| 6 | &lt;Reflection / Return&gt; | | | | | |

### Emotional arc

Visualize highs and lows across stages.

```
Stage:     1      2      3      4      5      6
           |      |      |      |      |      |
  😊       ●             ●                    ●
  😐              ●
  😟                           ●      ●
```

## 4. Moments of truth

The specific moments where the journey makes or breaks adoption. Usually 2–4 per journey.

| Moment | Why it matters | Current state | Desired state |
|---|---|---|---|
| &lt;e.g., "First successful action"&gt; | &lt;determines if user returns&gt; | &lt;what happens today&gt; | &lt;what should happen&gt; |

## 5. Pain points (ranked)

Extracted from §3 and ranked by impact × frequency. Evidence-tagged.

| # | Pain point | Stage | Evidence tag | Impact | Frequency |
|---|---|---|---|---|---|
| 1 | &lt;pain&gt; | 4 | observed / reported / assumed | high / med / low | high / med / low |
| 2 | ... | | | | |
| 3 | ... | | | | |

## 6. Opportunities (ranked)

Where the journey could be reshaped. Each opportunity cites pain points and carries an HMW.

> **HMW funnel:** Generate many → validate with evidence → **prioritize through the journey ← you are here** → commit 1–3 in the POV.

| # | Opportunity | Addresses pain # | HMW | Effort hint |
|---|---|---|---|---|
| 1 | &lt;design opening&gt; | 1, 3 | How might we &lt;...&gt; so that &lt;...&gt;? | low / med / high |
| 2 | | | | |

## 7. Backstage (optional — service blueprint light)

For journeys that involve humans or systems behind the scenes, add a backstage row. Skip if not relevant.

| Stage | User-facing | Front-stage (system / human touchpoint) | Backstage (internal process) |
|---|---|---|---|
| 4 | &lt;what user sees&gt; | &lt;agent, notification, UI&gt; | &lt;team queue, ML model, policy check&gt; |

## 8. Design implications

What this journey commits the design to.

- **Must:** &lt;non-negotiable, usually tied to a moment of truth&gt;
- **Should:** &lt;strong default based on pain ranking&gt;
- **Avoid:** &lt;anti-pattern observed in current journey&gt;

## 9. Assumptions to validate

Parts of the journey still tagged `assumed`. Where the next loop should focus research.

- &lt;assumption&gt;
- &lt;assumption&gt;

---

## Quality check

- [ ] TL;DR names the most important insight, not a summary of the whole journey
- [ ] Every stage has entries in Doing / Thinking / Feeling columns (no blank rows)
- [ ] At least one pain point is `observed` (not all `assumed`)
- [ ] Moments of truth are called out (2–4 recommended)
- [ ] Pain points ranked by impact, not by where they appear in the stage order
- [ ] Opportunities cite pain points by number
- [ ] Each opportunity has an HMW (or explicit "not yet framed")
- [ ] Assumptions-to-validate section is filled (or explicit "no open assumptions")

---

*Template grounded in NN/g journey mapping practice and ISE journey curriculum. A journey map without emotional and evidence columns is a flowchart; this template insists on both.*
