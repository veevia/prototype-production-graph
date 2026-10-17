---
title: "<Domain / workflow> JTBD Analysis"
type: template
template-for: jtbd-analysis
status: canonical
owner: Wei Wei
last-updated: 2026-04-30
loop-phase: understand
source: Author artifact template; private programme examples omitted
tags: [type/template, type/jtbd, purpose/discover, loop/understand, status/canonical]
---

# <Domain / workflow> JTBD Analysis

Source inputs: `<research source / survey name>`, response #<n>, <persona / team context>.

**ID conventions used throughout:** `G#` Goals · `C#` Challenges · `SS#` Success Signals · `KS#` Key Signals · `J#` JTBDs · `5.x` Product Opportunities · `P#` Process steps (Appendix A).

## Persona

| Attribute | Detail |
| --- | --- |
| User | <Name or representative user> |
| Role | <Role / title> |
| Functional team | <Team / function> |
| Tooling context | <Systems, tools, channels, dashboards, documents> |
| Critical tools | <Most important tools for the workflow> |
| Key collaborators | <Internal and external collaborators> |

## 1. Customer Goals and Motivation

### Goals

| ID | Goal | Motivation |
| --- | --- | --- |
| G1 | <Goal 1> | <Why this matters to the persona, workflow, customer, or business> |
| G2 | <Goal 2> | <Why this matters> |
| G3 | <Goal 3> | <Why this matters> |
| G4 | <Goal 4> | <Why this matters> |

## 2. Problem Space

**Umbrella HMW:** How might we help <persona / team> <desired progress> while <reducing the main friction, risk, or manual burden>?

| ID | Challenge | Impact | HMW |
| --- | --- | --- | --- |
| C1 | <What makes the current workflow hard, slow, risky, fragmented, or inconsistent?> | <What happens because of this challenge?> | How might we <specific opportunity framed as a design question>? |
| C2 | <Challenge 2> | <Impact 2> | How might we <HMW 2>? |
| C3 | <Challenge 3> | <Impact 3> | How might we <HMW 3>? |
| C4 | <Challenge 4> | <Impact 4> | How might we <HMW 4>? |

## 3. Success Metrics

### Success Signals

| ID | Success Signal |
| --- | --- |
| SS1 | <Observable improvement, e.g., faster decision-making> |
| SS2 | <Observable improvement, e.g., better visibility across systems> |
| SS3 | <Observable improvement, e.g., more reliable risk assessment> |
| SS4 | <Observable improvement> |
| SS5 | <Observable improvement> |

### Key Signals

| ID | Signal | Authoritative system | Metric / source |
| --- | --- | --- | --- |
| KS1 | <Signal name> | <System / dashboard / forum> | <Metric, evidence, or business indicator> |
| KS2 | <Signal name> | <System> | <Metric / source> |
| KS3 | <Signal name> | <System> | <Metric / source> |
| KS4 | <Signal name> | <System> | <Metric / source> |
| KS5 | <Signal name> | <System> | <Metric / source> |

## 4. Jobs to Be Done Mapping

| ID | JTBD | When I... | I want to... | So I can... | Key challenge | Success signal |
| --- | --- | --- | --- | --- | --- | --- |
| J1 | <Short job label> | <triggering situation / workflow moment> | <desired action, capability, or support> | <business, quality, risk, or workflow outcome> | <main blocker or risk> | <how we know this job is succeeding> |
| J2 | <Short job label> | <triggering situation / workflow moment> | <desired action, capability, or support> | <outcome> | <main blocker or risk> | <success signal> |
| J3 | <Short job label> | <triggering situation / workflow moment> | <desired action, capability, or support> | <outcome> | <main blocker or risk> | <success signal> |
| J4 | <Short job label> | <triggering situation / workflow moment> | <desired action, capability, or support> | <outcome> | <main blocker or risk> | <success signal> |

## 5. Product Opportunities

Opportunities below are framed using the Product Opportunity Assessment Canvas. Solution directions are intentionally broad (data sourcing, integration, automation, AI, process, tooling) rather than AI-only. Each canvas references upstream IDs (`J#`, `C#`, `KS#`) so the opportunity's evidence base is traceable. Add one canvas per opportunity, typically one per JTBD.

### 5.1 <Opportunity name>

| Canvas element | Detail |
| --- | --- |
| Linked JTBD | J<n> — <JTBD label> |
| Linked challenges | C<n>, C<n> |
| Linked signals | KS<n>, KS<n> |
| Problem to solve | <Specific problem this opportunity addresses, in user/workflow terms> |
| Target customer | <Primary persona(s) and supporting roles> |
| Value / outcome | <Business, quality, risk, or efficiency outcome if solved> |
| Today's alternative | <How users cope today: manual workflow, workaround, partial tooling> |
| Solution directions | (a) <data / integration approach>; (b) <automation or workflow approach>; (c) <UX or process approach>; (d) <AI assist where appropriate>; (e) <other levers>. |
| Where AI can help | <AI/LLM/data/knowledge-base/ontology, agentic UX, or multi-agent angles for this specific opportunity. Examples: RAG over a curated knowledge base; document-AI extraction; ontology-driven entity resolution; agent that drafts and routes; multi-agent split between retriever, analyzer, writer> |
| Success metric | <Measurable signal: time saved, decision quality, coverage, override/error rate, confidence> |

### 5.2 <Opportunity name>

| Canvas element | Detail |
| --- | --- |
| Linked JTBD | J<n> — <JTBD label> |
| Linked challenges | C<n>, C<n> |
| Linked signals | KS<n>, KS<n> |
| Problem to solve | <...> |
| Target customer | <...> |
| Value / outcome | <...> |
| Today's alternative | <...> |
| Solution directions | <...> |
| Where AI can help | <...> |
| Success metric | <...> |

---

## Appendix A. Process and Tool Landscape

Use this appendix when the workflow spans multiple lifecycle stages and authoritative systems. Pull rows directly from a process-flow artifact (e.g., a touchpoint diagram, swim-lane, or process-flow spreadsheet) so each step has a stable `P#` ID that can be referenced from §4 and §5.

| ID | Lifecycle stage | Touchpoint | Authoritative system | Persona role | Key collaborators |
| --- | --- | --- | --- | --- | --- |
| P1 | <Stage> | <Touchpoint / trigger> | <System or system-of-record> | <Persona's role at this step> | <Other functions / teams> |
| P2 | <Stage> | <Touchpoint> | <System> | <Role> | <Collaborators> |
| P3 | <Stage> | <Touchpoint> | <System> | <Role> | <Collaborators> |
| P4 | <Stage> | <Touchpoint> | <System> | <Role> | <Collaborators> |

**Dual viewing audience (optional):** if the workflow has both an internal-user view and an external-user view (e.g., a supplier portal, customer self-service, partner workspace), capture the audience split here, including security boundaries (Company × Facility × Function, Region, Role, etc.).

<!--
## Design Handoff Notes

Use this optional section when the JTBD analysis is mature enough to inform product/design direction.

| Screen/state | Primary user action | Expected system response |
| --- | --- | --- |
| <Screen or workflow state> | <What the user needs to do> | <How the system should respond> |
| <Screen or workflow state> | <User action> | <Expected response> |

## Accessibility Requirements

| Interaction pattern | Requirement |
| --- | --- |
| Keyboard navigation | <Keyboard access requirement> |
| Screen reader support | <Labeling, announcement, and state-change requirement> |
| Visual accessibility | <Contrast, text zoom, target size, and non-color-only status requirement> |
| Data tables | <Headers, sorting, row context, and status-label requirement> |
| Dynamic content | <Loading, refresh, error, and completion announcement requirement> |

## Validation Needed

Before using this JTBD as final product/design direction, validate assumptions through user interviews, contextual inquiry, or evidence review. Priority validation questions:

1. <What decision, workflow, or source-system assumption needs validation?>
2. <What evidence is required before users trust the recommended action?>
3. <Where does the current workflow break down most often?>
4. <Which success signal matters most to the persona or business?>
-->
