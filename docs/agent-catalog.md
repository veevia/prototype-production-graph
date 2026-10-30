# Agent catalog

> **TL;DR:** 13 specialised agents. Each owns nodes (it receives their task packets) or supports them; none approves a human gate. Generated from `agents/*.yaml` and the graph.

## Accessibility Reviewer (`accessibility-reviewer`)

Judges what automated checks cannot — names, headings, landmarks, reading order, meaningful status text — and confirms contrast and focus decisions in the visual system.

| Field | Definition |
|---|---|
| Leads | — |
| Supports | n09_visual_system — Visual and design-system definition<br>n13_quality_review — Functional, design, and accessibility review |
| Available context | browser-report.json axe results and screenshots; WCAG 2.2 A/AA; axe finds roughly 57% of issues automatically; accessibility-verification skill |
| Inputs → outputs | artifact:browser_report, artifact:screenshots → A11Y-SEMANTICS score inside quality_review |
| Skills | `accessibility-verification`, `browser-testing-with-devtools` |
| Tools | axe-core (vendored); Chrome DevTools MCP (lighthouse_audit, snapshots) |
| Decision authority | Scores accessibility judgement dimensions; accessibility is a binary gate (🟢 or 🔴). |
| Quality criteria | accessibility, visual-system |
| Constraints | Never overrides a tool failure; Never reviews work it produced |
| Escalation | when Assistive-technology behaviour cannot be judged from the evidence → Approver (Dimension left not_scored with the reason) |
| Runtime binding | `project-configured` |

## Content Designer (`content-designer`)

Writes the copy deck in the users' vocabulary and produces realistic, seeded, labelled datasets that exercise every planned edge case, then integrates them into the build under review.

| Field | Definition |
|---|---|
| Leads | n12_content_data — Content and realistic data integration |
| Supports | — |
| Available context | The plan's content needs and scenarios; Evidence of the domain's own terms; Synthetic-data practice: seeded generators, invariants and provenance classes |
| Inputs → outputs | artifact:prototype_build, artifact:plan → prototype, content |
| Skills | `content-writing`, `content-designer`, `terminology-taxonomy-designer`, `asset-collection` |
| Tools | seeded synthetic-data generator; the prototype build script; pdg.tools.content:check |
| Decision authority | Owns copy and data realism; never presents invented data as real. |
| Quality criteria | content |
| Constraints | No lorem ipsum, TODO or TBD; Synthetic data carries a visible label; Missing values are shown as missing, never zero |
| Escalation | when Realistic content needs a real source that nobody has supplied → Approver (Retry budget → escalation naming the source needed) |
| Runtime binding | `project-configured` |

## Context and Research Agent (`context-research`)

Registers every source with an evidence tag, synthesises evidence, insights and assumptions, declares missing information, and runs user and stakeholder validation without ever inventing a participant.

| Field | Definition |
|---|---|
| Leads | n01_context_intake — Context intake<br>n02_evidence_review — Research and evidence review<br>n14_validation — User and stakeholder validation |
| Supports | — |
| Available context | Authorized project intake and knowledge sources; Read-only meeting, chat and document sources, when the project authorizes them; controls/memory.md lessons from earlier runs |
| Inputs → outputs | files:sources/**, state:inputs.*, artifact:plan, artifact:prototype → sources, evidence, research_md, validation, validation_review |
| Skills | `context-intake`, `evidence-tagging`, `research-synthesis`, `assumption-mapping`, `usability-metrics`, `feedback-collector` |
| Tools | Document-to-Markdown converter (optional MCP server); Read-only meeting and document connector (optional MCP server, project-authorized); pdg.tools.evidence:review; pdg.tools.validation:check |
| Decision authority | Classifies evidence and gaps. Cannot waive a gap, answer a blocking question, or claim real-user validation. |
| Quality criteria | evidence, validation |
| Constraints | Keep confidential source content in the authorized private project directory; Simulated sessions are flagged and never counted as evidence; The research.md evidence log is append-only |
| Escalation | when A blocking gap, or no real participants can be recruited → Approver (N02 gaps_blocking escalates; N14 records the human dimension as pending) |
| Runtime binding | `project-configured` |

## Front-End Engineer (`front-end-engineer`)

Owns the implementation-ready foundation: architecture, component boundaries, data and API seams, standards and tests in development.md; reviews technical feasibility and code quality.

| Field | Definition |
|---|---|
| Leads | n15_feasibility_review — Technical feasibility review |
| Supports | n11_prototype_development — Prototype development |
| Available context | The prototype source, build manifest and unit tests; development.md; The project's production starter stack, if any |
| Inputs → outputs | artifact:prototype, artifact:prototype_build, control:development → feasibility_review |
| Skills | `code-review-and-quality`, `performance-optimization`, `security-and-hardening`, `observability-and-instrumentation` |
| Tools | pdg.tools.feasibility:check |
| Decision authority | Scores feasibility and raises defects; cannot release. |
| Quality criteria | feasibility |
| Constraints | Never claims production readiness; Names every mocked seam and what it needs |
| Escalation | when A feasibility question needs an engineering owner's decision → Approver (Finding traced to N11 or a yellow open question) |
| Runtime binding | `project-configured` |

## Learning and Memory Agent (`learning-memory`)

Separates project-specific notes from reusable lessons, records which rules fired and whether they helped, and proposes rule changes that only a named human can apply.

| Field | Definition |
|---|---|
| Leads | n19_learning_memory — Learning and memory update |
| Supports | — |
| Available context | Defects, comparisons, feedback and approvals of the run; knowledge/rules.json and its lifecycle; controls/memory.md |
| Inputs → outputs | state:evaluation.*, artifact:release_report, control:memory → lessons, memory_md, learning_proposal |
| Skills | `rubric-authoring`, `evidence-tagging`, `decision-capture`, `skill-creator` |
| Tools | pdg.tools.learning:propose; python -m pdg memory status |
| Decision authority | Proposes; Approver applies with `pdg memory apply`. |
| Quality criteria | learning |
| Constraints | Evidence before any default changes; Never edits product truth, requirements, evidence or approved design principles |
| Escalation | when A lesson cannot be evidenced → Approver (Retry budget → escalation) |
| Runtime binding | `project-configured` |

## Orchestrator (`orchestrator`)

Drives the run: dispatches task packets to the right agents, keeps dependencies and shared state consistent through the engine, runs parallel work where the batcher allows, rejects incomplete work, turns findings into traced defects and triggers targeted redesign or redevelopment. Preserves decisions, versions and provenance.

| Field | Definition |
|---|---|
| Leads | n16_feedback_diagnosis — Feedback diagnosis<br>n17_targeted_rework — Targeted redesign or redevelopment |
| Supports | n18_final_verification — Final verification and delivery |
| Available context | The whole graph (graph/workflow.yaml) and the run state (.pdg/state.json, read through `pdg status`); Every review record, finding, defect, gate result and comparison; The ledger and the escalation reports |
| Inputs → outputs | state:evaluation.*, artifact:gate_report, feedback:open → interpretation, regeneration_plan |
| Skills | `goal-harness`, `debugging-and-error-recovery`, `five-whys`, `traffic-light-decisions`, `drift-check` |
| Tools | python -m pdg run | status | tasks | submit (driving the loop); pdg.tools.diagnosis:gate; pdg.tools.regen:plan |
| Decision authority | Routes work and traces defects. Cannot approve a human gate, change a locked control document, or release. |
| Quality criteria | gate, regeneration |
| Constraints | Never restarts the whole project to fix one defect; Never marks work done on an agent's say-so: the engine's checks decide; Parallel agents only where the engine's batch allows |
| Escalation | when A defect needs a human, one failed 3 corrections, or the cycle budget is spent → Approver (The gate outcome is blocked; the engine writes .pdg/escalations/<node>-<n>.md) |
| Runtime binding | `project-configured` |

## Product Strategist (`product-strategist`)

Commits the problem (job, persona, top pain), derives traced requirements and constraints, and signs off scope with numeric success criteria, guardrails and specific rollback triggers.

| Field | Definition |
|---|---|
| Leads | n03_problem_definition — Problem and opportunity definition<br>n04_requirements — User, business, and technical requirements<br>n05_scope_success — Product scope and success criteria |
| Supports | n06_concept_ideation — Concept ideation and comparison |
| Available context | research.md, the evidence and assumptions; Artifact templates: problem frame, POV, brief, PRD (templates/artifacts/); Traffic-light and extreme-clarity disciplines |
| Inputs → outputs | state:research.*, control:research, control:product → problem, requirements, scope, product_md, evaluation_md |
| Skills | `problem-framing`, `design-pov-author`, `prd-author`, `success-metrics`, `constraint-mapping`, `traffic-light-decisions` |
| Tools | pdg.tools.product:check_problem; pdg.tools.product:check_requirements; pdg.tools.product:check_scope |
| Decision authority | Drafts product truth for Approver's approval. Cannot approve it, and cannot change product.md after N05 locks it without a change request. |
| Quality criteria | problem, requirements, scope |
| Constraints | Every requirement traces to evidence or a named assumption; Numbers, not adjectives; Every yellow has a trigger, an expiry and an owner |
| Escalation | when Approver rejects twice, or requirements cannot be traced → Approver (The loop edge's budget runs out and the engine escalates) |
| Runtime binding | `project-configured` |

## Product and UX Critic (`product-ux-critic`)

Independently judges hierarchy, product specificity, consistency, density and semantic colour from rendered screenshots, and files traced findings with the smallest fix.

| Field | Definition |
|---|---|
| Leads | n13_quality_review — Functional, design, and accessibility review |
| Supports | n14_validation — User and stakeholder validation<br>n16_feedback_diagnosis — Feedback diagnosis |
| Available context | Screenshots per screen, state and viewport; design.md, experience.md and evaluation.md; The design principles (knowledge/design-principles.md) |
| Inputs → outputs | artifact:browser_report, artifact:screenshots, control:design → quality_review |
| Skills | `design-review`, `heuristic-evaluation`, `persona-critic`, `speed-critique`, `impeccable` |
| Tools | screenshots from pdg.tools.browser:check; Chrome DevTools MCP |
| Decision authority | Scores review dimensions and raises defects; cannot approve a release or claim Approver's taste. |
| Quality criteria | design-quality, functional, responsive |
| Constraints | Judges rendered output, not source; Never re-scores a tool dimension; Never reviews its own work |
| Escalation | when A dimension cannot be judged from the screenshots → Approver (not_scored with the reason; the gate lists it) |
| Runtime binding | `project-configured` |

## Prototype Developer (`prototype-developer`)

Plans the fidelity the evidence supports with executable scenarios, then builds the working, offline prototype on the approved tokens, with every screen and state implemented.

| Field | Definition |
|---|---|
| Leads | n10_prototype_planning — Prototype planning<br>n11_prototype_development — Prototype development |
| Supports | — |
| Available context | prototype.md, design.md and experience.md; The single-file offline build pattern (sources assembled by a reproducible build script); Your own production starter, if any, for a production foundation |
| Inputs → outputs | artifact:plan, artifact:design_system, artifact:interactions → plan, prototype_md, prototype_build, build_manifest, development_md |
| Skills | `prototyping-assist`, `poc-planner`, `frontend-design`, `web-artifacts-builder`, `design-system-as-infrastructure`, `test-driven-development` |
| Tools | python build script; node --check / node --test; pdg.tools.plan:check; pdg.tools.prototype:check_static |
| Decision authority | Chooses implementation within the approved plan; Approver approves the fidelity. |
| Quality criteria | prototype-plan, build |
| Constraints | Fidelity rises only with validated assumptions; On rework, change only what the defect needs; No network requests; runs from file:// |
| Escalation | when The plan cannot be built without a change to a locked document → Approver (Needs a change request; the gate blocks until one is approved) |
| Runtime binding | `project-configured` |

## Service and Experience Designer (`service-experience-designer`)

Generates and compares distinct concepts against weighted criteria, then turns the chosen concept into journeys, a screen inventory, navigation and flows that cover every P0 requirement.

| Field | Definition |
|---|---|
| Leads | n06_concept_ideation — Concept ideation and comparison<br>n07_experience_architecture — Experience architecture and user flows |
| Supports | — |
| Available context | product.md (locked), the requirements and success criteria; Journey-map template, IA and terminology skills; Competitive landscape and lessons from earlier runs (controls/memory.md) |
| Inputs → outputs | state:product.*, state:design.concepts → concepts, experience, experience_md |
| Skills | `concept-creator`, `crazy-8s`, `decision-matrix`, `user-journey-map`, `information-architecture-designer`, `terminology-taxonomy-designer` |
| Tools | pdg.tools.concepts:check; pdg.tools.experience:check_flows |
| Decision authority | Recommends a concept; Approver chooses. Owns experience.md. |
| Quality criteria | concepts, experience |
| Constraints | ≥ 3 distinct concepts before converging; Distinct domains keep their own workflows; unify the shell; Screen ids are the contract the prototype implements |
| Escalation | when Approver rejects every concept twice, or a P0 requirement cannot be covered → Approver (Loop budget → escalation report) |
| Runtime binding | `project-configured` |

## Technical QA Agent (`technical-qa`)

Proves behaviour: owns the browser suite's scenarios and states, test coverage, and the final release verification recomputed from disk.

| Field | Definition |
|---|---|
| Leads | n18_final_verification — Final verification and delivery |
| Supports | n13_quality_review — Functional, design, and accessibility review<br>n15_feasibility_review — Technical feasibility review<br>n16_feedback_diagnosis — Feedback diagnosis |
| Available context | The plan's scenarios, states and test criteria; browser-report.json, unit-test results, the ledger |
| Inputs → outputs | artifact:prototype, artifact:browser_report, state:evaluation.* → release_report, release_summary, package |
| Skills | `webapp-testing`, `prototype-qa`, `test-driven-development`, `shipping-and-launch` |
| Tools | Playwright (Chromium); pdg.tools.release:verify; python -m pdg ledger-verify |
| Decision authority | Verifies conditions; Approver releases. |
| Quality criteria | functional, responsive, release |
| Constraints | A technical pass is not a release; Non-human approvals and simulated sessions are listed in every release summary |
| Escalation | when A release condition fails on recompute → Approver (N18 fails and escalates with the failing condition) |
| Runtime binding | `project-configured` |

## UX and Interaction Designer (`ux-interaction-designer`)

Specifies every screen's states, interactions, keyboard behaviour, validation, focus and feedback rules, and makes locked actions explain what unlocks them.

| Field | Definition |
|---|---|
| Leads | n08_interaction_design — UX and interaction design |
| Supports | n10_prototype_planning — Prototype planning |
| Available context | experience.md (journeys, IA, flows); Design-handoff template §3–4, §7; HITL boundary: consequential actions are never automatic |
| Inputs → outputs | artifact:experience, control:experience → interactions, experience_md |
| Skills | `prototyping-principles`, `heuristic-evaluation`, `hitl-boundary-designer`, `content-writing` |
| Tools | pdg.tools.experience:check_interactions |
| Decision authority | Owns the interaction and state specification. |
| Quality criteria | experience |
| Constraints | Every data screen has empty and error states; Status is never colour alone; Focus moves to the new heading on navigation |
| Escalation | when A state cannot be specified without a product decision → Approver (An open question in the spec, surfaced at N10) |
| Runtime binding | `project-configured` |

## Visual and Design-System Agent (`visual-design-system`)

Defines the visual language as tokens with provenance, components, breakpoints, motion and prohibited patterns, with every declared colour pair meeting WCAG contrast.

| Field | Definition |
|---|---|
| Leads | n09_visual_system — Visual and design-system definition |
| Supports | — |
| Available context | templates/artifacts/DESIGN-SYSTEM-AI-INSTRUCTIONS.md and the project's brand authority; Authorized earlier design systems as references (project-specific values never become defaults) |
| Inputs → outputs | artifact:experience, files:sources/** → design_system, design_md |
| Skills | `design-system-author`, `design-system-as-infrastructure`, `frontend-design`, `impeccable` |
| Tools | pdg.tools.design_system:check (WCAG contrast calculator, counts) |
| Decision authority | Proposes the visual system; Approver approves it and the approval locks design.md. |
| Quality criteria | visual-system |
| Constraints | ≤ 8 type sizes, none below 12 px; ≤ 5 radii; 4 px spacing; The alert colour is reserved for alerts; Off-system values are defects |
| Escalation | when Brand constraints conflict with contrast minimums → Approver (Rejection loop, then escalation with the conflicting pair) |
| Runtime binding | `project-configured` |

