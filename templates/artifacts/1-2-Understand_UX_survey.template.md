---
title: "UX Survey — <domain / workflow>"
type: template
template-for: ux-survey
status: canonical
owner: Wei Wei
last-updated: 2026-04-30
loop-phase: understand
source: Author artifact template; private programme examples omitted
tags: [type/template, type/survey, purpose/discover, loop/understand, status/canonical]
---

<!--
  UX SURVEY TEMPLATE
  Produced during the UNDERSTAND phase, BEFORE focus groups or interviews.

  Purpose:
  1. Capture current-state context across stakeholder groups quickly (~15–20 min for respondent).
  2. Generate raw inputs that feed directly into:
     - 1-3-Understand_jtbd.template.md (Jobs To Be Done)
     - HMW (How Might We) statements for the Design POV
     - Current-state journey map
     - Focus group discussion guide (validate, don't re-discover)

  HOW TO USE THIS TEMPLATE WITH AI ASSISTANCE
  ============================================
  This template uses two kinds of placeholders:

  * `<FILL: …>` — content the AI should generate from supplied source material
    (meeting notes, customer docs, transcripts, system inventories). The AI
    should propose specific, named options grounded in the source — not generic
    boilerplate.

  * `<TBD: …>` — content the human researcher confirms or edits before sending.

  When invoking AI, attach the source materials and instruct:
    "Generate survey options from the attached <meeting notes / customer doc /
    transcript>. Replace every <FILL: …> with concrete, named options drawn
    from the source. Preserve question structure and types. Flag any options
    you inferred without direct source evidence as `assumed`."

  Every option list must be:
    - Grounded in source (cite the source line / doc when possible)
    - Tagged with one of: observed | reported | assumed (see CLAUDE.md)
    - Mutually exclusive where the type is `Multiple choice`
    - Open-ended ("Other: ___") for any list that may not be exhaustive

  Remove this comment block before sending the survey.
-->

# UX Survey — <FILL: domain / workflow name>

## Intro

* **Primary contact:** <TBD: researcher name>
* **Estimated time:** ~15–20 minutes
* **Audience:** <FILL: comma-separated list of teams / roles / personas drawn from source>
* **Return by:** <TBD: ISO date>

**Why we are asking.** We want to ground <FILL: solution / capability name> in how you actually work today. This survey helps us understand the current state across stakeholder groups, including:

* Your role in the process
* The systems and data you use
* The jobs you are trying to get done
* Pain points and blockers in today's workflow
* The outcomes and success metrics that matter most

**How we will use your responses.** Your inputs will feed:

* Current-state journey map
* Top pain points (clustered)
* Jobs To Be Done (JTBD) per role
* "How Might We" (HMW) statements
* Priority focus areas for solution exploration and the upcoming focus group

---

## Section 1 — Tell me about your experience

### Q1. What is your name?

* **Type:** Short text

### Q2. What is your team / function?

* **Type:** Multiple choice (single select)
* **Options:** *(AI: derive from org chart / stakeholder list in source. Always include "Other".)*
  * <FILL: team-1>
  * <FILL: team-2>
  * <FILL: team-3>
  * <FILL: …>
  * Other: ______

### Q3. What best describes your role in the current process?

* **Type:** Short text

### Q4. Which area(s) of the <FILL: workflow name> flow do you primarily work in?

* **Type:** Multi-select
* **Options:** *(AI: list the named sub-workflows / stages / data domains found in the source. Each option should be a recognizable phase or data area, not a generic verb.)*
  * <FILL: workflow-area-1>
  * <FILL: workflow-area-2>
  * <FILL: workflow-area-3>
  * <FILL: …>
  * Other: ______

### Q5. Which platform(s) / system(s) do you use most often today?

* **Type:** Multi-select
* **Options:** *(AI: list named systems, tools, data platforms mentioned in the source. Include generic fallbacks: Excel, Email/Teams, Power BI.)*
  * <FILL: system-1>
  * <FILL: system-2>
  * <FILL: …>
  * Excel
  * Power BI
  * Email / Teams
  * Other: ______

---

## Section 2 — Your Jobs To Be Done

### Q6. What are the main jobs you are responsible for in <FILL: workflow name>?

* **Type:** Long text
* **Prompt:** Please describe the top 2–3 things you are responsible for.

### Q7. Complete the following JTBD statements

* **Type:** Long text (repeating block)
* **Prompt:** *"When I need to <do something>, I need to <access / review / decide / validate something>, so that I can <achieve an outcome>."*

**Job #1**

* When I need to…
* I need to…
* So that I can…

**Job #2**

* When I need to…
* I need to…
* So that I can…

**Job #3**

* When I need to…
* I need to…
* So that I can…

*(Add more jobs as needed — Job #4, #5, …)*

> **Note for AI generation:** If the source contains role-specific responsibility statements, pre-fill 1–2 example jobs per persona as `<FILL (assumed): …>` so respondents can confirm or correct. Mark them clearly as draft examples.

### Q8. At what point in the process do you usually get involved?

* **Type:** Multiple choice
* **Options:**
  * Early / upstream
  * Mid-process
  * Late / downstream
  * End-to-end
  * Only when there is an issue / escalation
  * Varies depending on the case
  * Other: ______

### Q9. Who do you most often depend on to complete your work?

* **Type:** Long text
* **Prompt:** List teams, roles, or stakeholders you regularly rely on. *(AI: pre-seed with collaborators named in the source as `<FILL (reported): …>` examples.)*

---

## Section 3 — Current-state workflow and pain points

### Q10. What information or signals do you need most to do your job well today?

* **Type:** Long text
* **Prompt:** Examples: <FILL: domain-specific data types from source>.

### Q11. What are the biggest challenges or blockers you face today?

* **Type:** Long text
* **Prompt:** Describe the top 3 pain points in your current workflow.

### Q12. Which of the following issues do you experience today?

* **Type:** Multi-select
* **Options:** *(AI: keep the generic list below AND append 2–4 domain-specific issues drawn from the source.)*
  * Data is spread across too many systems
  * Information is not available in real time
  * Manual data collection / reconciliation
  * Hard to know which signal matters most
  * Difficult to see the full picture
  * Difficult to connect historical issues or trends
  * Unclear ownership / handoffs
  * Too much reliance on Excel / manual reporting
  * Hard to prioritize what action to take
  * Hard to <FILL: domain-specific risk>
  * Duplicate effort across teams
  * <FILL: domain-specific issue 1>
  * <FILL: domain-specific issue 2>
  * Other: ______

### Q13. Where do you spend the most time today?

* **Type:** Multiple choice
* **Options:**
  * Gathering data
  * Validating data
  * Comparing across systems
  * Investigating issues
  * Communicating with other teams
  * Deciding what action to take
  * Documenting / reporting
  * Following up with <FILL: counterpart>
  * Other: ______

### Q14. How confident are you that you can see the full picture needed to make decisions today?

* **Type:** Rating scale (1–5)
* **Anchors:** 1 = Not confident at all → 5 = Very confident

### Q15. If you are not fully confident today, what is usually missing?

* **Type:** Long text

---

## Section 4 — Outcomes and success metrics

### Q16. What outcomes are you trying to achieve in your part of the process?

* **Type:** Long text
* **Prompt:** What does success look like for you?

### Q17. How do you currently measure success?

* **Type:** Long text
* **Prompt:** Include any current KPIs, metrics, service levels, quality measures, cycle times, issue rates, or business outcomes.

### Q18. Which success measures matter most for a future <FILL: solution name> solution?

* **Type:** Drag to re-rank
* **Items:** *(AI: keep generic measures below; append domain-specific success measures derived from source.)*
  1. Better visibility across systems
  2. Faster issue detection
  3. Reduced manual work
  4. Better prioritization of <FILL: domain object>
  5. Faster decision-making
  6. More reliable / accurate <FILL: domain assessment>
  7. Better <FILL: domain action 1>
  8. Better <FILL: domain action 2>
  9. Better <FILL: domain action 3>
  10. Better alignment across teams
  11. Earlier identification of potential <FILL: risk type>
  12. (add your own)

### Q19. If this future solution worked very well, what would improve the most?

* **Type:** Long text

---

## Section 5 — Future opportunity areas

### Q20. Which area would create the most value if improved first?

* **Type:** Multiple choice
* **Options:** *(AI: mirror the workflow areas from Q4 so the team can correlate "where I work" with "where I want value first".)*
  * <FILL: workflow-area-1>
  * <FILL: workflow-area-2>
  * <FILL: workflow-area-3>
  * <FILL: …>
  * Cross-system visibility across all areas
  * Other: ______

### Q21. What is the single most important problem we should focus on first?

* **Type:** Long text

### Q22. What should a future <FILL: solution name> capability help you do better?

* **Type:** Long text
* **Prompt:** Describe the **outcome(s)**, not the technology.

### Q23. Where should the agent / capability show up in your day — if at all?

* **Type:** Multi-select + "why" follow-up
* **Options:** *(AI: use the system-of-record named in your authorized sources. Keep the "not in my day" option — it is a real signal.)*
  * Inside <FILL: system-of-record> (or whichever system I already live in)
  * A daily brief / digest emailed or posted to Teams
  * A chat nudge when something specific happens
  * Only when I explicitly ask it something
  * Not in my day at all — put the value upstream (<FILL: upstream stage>) or downstream (<FILL: downstream stage>)
* **Why:** <free text>

---

## Closing

> Thank you for your time. Your inputs directly shape the focus group, the JTBD per role, and the HMW statements we use in design.

---

## Appendix A — Synthesis crosswalk (researcher only; remove before sending)

This appendix maps each survey question to its downstream artifact. Use it after responses come in to synthesize quickly.

| Q# | Feeds → JTBD field | Feeds → HMW input | Feeds → Journey map stage | Evidence tag default |
| --- | --- | --- | --- | --- |
| Q2, Q3 | Persona / Role | — | Actor lane | observed |
| Q4 | Workflow area | Scope of HMW | Stage selection | observed |
| Q5 | Tooling context | — | Tools per stage | observed |
| Q6 | JTBD label | — | Stage actions | reported |
| Q7 | When I… / I want to… / So I can… | "How might we help <persona> <progress>…" | Stage goals | reported |
| Q8 | Trigger / moment | — | Stage entry point | reported |
| Q9 | Key collaborators | "…across <handoff>" HMW | Handoff arrows | reported |
| Q10 | Inputs needed | — | Information needs per stage | reported |
| Q11 | Key challenge | "…while reducing <friction>" HMW | Pain points per stage | reported |
| Q12 | Key challenge (categorical) | HMW theme cluster | Pain points per stage | observed |
| Q13 | Time sink | "…so that <persona> spends less time on <X>" HMW | Effort indicator | reported |
| Q14 | Confidence baseline | — | Confidence indicator | observed |
| Q15 | Information gap | "…by surfacing <missing signal>" HMW | Pain points | reported |
| Q16, Q17 | Success signal / metric | HMW success criteria | Outcome stage | reported |
| Q18 | Ranked success signals | HMW prioritization | — | observed |
| Q19, Q22 | Desired outcome | HMW outcome framing | Future-state journey | assumed (until validated) |
| Q20 | AI opportunity scope | HMW scope | Future-state stage | observed |
| Q21 | Umbrella HMW seed | **Umbrella HMW** | — | reported |
| Q23 | AI opportunity surface | "…delivered through <surface>" HMW | Future-state touchpoint | assumed |

## Appendix B — Source-to-options generation checklist (for AI-assisted drafting)

Before sending the AI source materials, confirm you have at least one of each:

* [ ] Org chart, stakeholder map, or RACI (→ Q2 team list, Q9 collaborators)
* [ ] Process or workflow diagram (→ Q4 areas, Q8 entry points, Q20 priority)
* [ ] System / tooling inventory or screenshots (→ Q5 platforms, Q23 surface)
* [ ] Meeting notes or transcripts of SME conversations (→ Q6, Q7, Q11, Q15 pre-seeds)
* [ ] Existing KPI / scorecard documents (→ Q17, Q18 ranked items)
* [ ] Any prior research, complaints, support tickets (→ Q11, Q12 domain-specific issues)

After AI generates the draft, the researcher must:

* [ ] Verify every `<FILL: …>` is grounded in source (no hallucinated team names or systems)
* [ ] Confirm every option list has an "Other" escape hatch
* [ ] Remove all `<TBD: …>` and HTML comment blocks
* [ ] Tag any pre-seeded answers (Q7, Q9) as `assumed` so respondents know they are draft examples
* [ ] Pilot-test with one friendly respondent before broad send
