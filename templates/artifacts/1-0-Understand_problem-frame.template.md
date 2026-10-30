---
title: "Problem Frame — <engagement>"
type: template
template-for: problem-frame
status: template
owner: <owner>
last-updated: YYYY-MM-DD
loop-phase: understand
light: green | yellow | red
trigger: <what closes a yellow>      # yellow only
expiry: <YYYY-MM-DD>                  # yellow only
references:
  - <sources/...>
informs: <downstream decision or scope>
tags: [type/template, type/problem-frame, purpose/discover, loop/understand, status/template]
---
# <engagement> — Problem Frame

**TL;DR:** <one-sentence people-problem + who has it>.

> The Problem Frame is the front link of the design loop — the pre-research artifact
> that grounds an engagement before any persona, JTBD, or solution work. Authored with
> the `problem-framing` skill. It gates entry into the Understand phase.

## Problem statement

<The problem in the user's language. NO solution noun — not "an agent", "a dashboard",
"an ontology", "a platform". Name the decision the user cannot make today.>
[observed|reported|assumed | <source-slug>]

## Decisions to enable

The future system exists to let specific people make specific decisions. Design backward from these:

- <decision the product must let a user make> — made by <role>, <cadence>, with <data> today [tag | source]
- ...

## Feasibility gap (want vs achievable — the Venn center)

- **Want:** <stakeholder ask> [reported | <source>]
- **Achievable now:** <constraint-bounded reality> [observed | <source>]
- **Design target (the overlap):** <where we play — the thing to build against>

## Known / unknown data map

- **Known-known:** <data we have and trust>
- **Known-unknown:** <data we know we lack> [open | <source>]
- **Unknown-unknown (riskiest):** <the assumption that, if wrong, breaks the concept>

## Stakeholder alignment map

| Stakeholder | Wants | Conflicts with |
|---|---|---|
| <name (role)> | <position> | <whom / what> |

## Readiness to research

🟢🟡🔴 — <one-line rationale>
- **trigger:** <what closes a yellow>      # yellow only — required
- **expiry:** <YYYY-MM-DD>                  # yellow only — required

> Evidence note: tag every claim `observed` / `reported` / `assumed`. Before any of this
> enters a customer deck, validate the load-bearing claims against primary sources
> (Evidence over opinion.)
