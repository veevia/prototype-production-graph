# Node catalog

> **TL;DR:** Every field of all 19 nodes, generated from `graph/workflow.yaml` (`python -m pdg docs`). Edit the graph, not this file.

## N01 `n01_context_intake` — Context intake

*Understand · Context · subgraph `discovery` · kind **agent***

**Purpose.** Register every source that can ground the product — brief, research, analytics, specs, prior prototypes, design-system authority and feedback — each with an evidence tag, without inventing any.

| Field | Definition |
|---|---|
| Depends on | `START` |
| Inputs | `state:inputs.brief`<br>`files:sources/**`<br>`artifact:gaps`<br>`control:memory`<br>`rework:self` |
| Outputs | `sources` (json, schema sources) — Source registry with evidence tags, plus open questions<br>`intake_notes` (markdown) — What each source contributes and what is missing |
| State read | `inputs.brief`, `research.open_questions` |
| State written | `inputs.sources`, `research.open_questions` |
| Responsible agent | `context-research` |
| Skills | `context-intake`, `context-pull`, `evidence-tagging`, `wiki-query`, `workiq-grounding` |
| Tools | markitdown MCP (convert documents to markdown); WorkIQ MCP (read-only M365 grounding); local file search |
| Context | The brief, verbatim, in sources/brief.md; Project-hub raw intake (00_context_intake/) and wiki (_wiki/), through /context-pull; Earlier rounds, their reviews and Wei's feedback; Project lessons from earlier runs in controls/memory.md; Meeting recordings are cited by id, never quoted |
| Control documents | read memory · write — |
| Completion criteria | The source registry validates against the sources schema<br>Every source has an evidence tag, every local path exists inside the project, and a brief is registered |
| Evaluation checks | `EVD-SOURCES` MUST tool · enforced (R-EVD-001) |
| Failure conditions | No brief registered; A source without an evidence tag; A local source path that does not exist or lies outside the project |
| Retry | 3 attempts — Re-dispatch with the failing registry checks and N02's gap list as context |
| Escalation | after 3 consecutive failed attempts, or the intake loop (E03) traversed twice → Wei: Sources found, sources missing, and the questions only Wei can answer |
| Human review | Not required; N03 is the first human gate |
| Outcomes | pass |
| Provenance | Source ids with sha256, recorded at N02; An evidence tag per source; Ledger: node_dispatched, node_submitted, node_passed |

**Instructions.** Register each source with an id, a project-relative path (or a cited URL), a kind and an evidence tag (observed | reported | assumed). The brief must be registered. Register user evidence (research, interviews, surveys, analytics or feedback) and a design-system authority when they exist. List open questions, and mark a question blocking only when the product cannot be defined without its answer. On a loop back from N02, resolve each gap in `artifact:gaps` by registering the missing source; a gap you cannot resolve stays open. Never summarise a source in place of registering it, and never invent a source, a quote or a participant.

## N02 `n02_evidence_review` — Research and evidence review

*Understand · Context · subgraph `discovery` · kind **gate***

**Purpose.** Turn the sources into tagged evidence, insights, assumptions and declared missing information, then detect context gaps and freeze the immutable inputs once they are sufficient.

| Field | Definition |
|---|---|
| Depends on | `n01_context_intake` |
| Inputs | `state:inputs.sources`<br>`state:inputs.brief`<br>`state:research.open_questions`<br>`artifact:sources`<br>`rework:self` |
| Outputs | `evidence` (json, schema evidence) — Evidence, insights, assumptions, open questions and missing information<br>`research_md` (control, installs research.md) — your copy of research.md, installed into controls/research.md — evidence log, insights, assumptions, open questions<br>`gaps` (json, schema gaps) — Hook output: the gap report with every local source hashed |
| State read | `inputs.sources`, `inputs.brief`, `research.open_questions` |
| State written | `inputs.sources`, `research.evidence`, `research.insights`, `research.assumptions`, `research.open_questions`, `research.missing` |
| Responsible agent | `context-research` |
| Skills | `research-synthesis`, `evidence-tagging`, `assumption-mapping`, `known-unknown-mapper`, `affinity-map` |
| Tools | pdg.tools.evidence:review (hash sources, detect gaps, freeze inputs); pdg.tools.evidence:check_tags |
| Context | Every registered source, read in full; Wei's evidence-tagging discipline: observed > reported > assumed; unlabelled assumptions are the defect; Missing information is declared, never filled in |
| Control documents | read memory · write research |
| Completion criteria | The evidence document validates against its schema<br>Every evidence item cites known sources with a valid tag; every insight cites evidence; the riskiest assumptions are flagged |
| Evaluation checks | `EVD-TAGS` MUST tool · enforced (R-EVD-002)<br>`EVD-RISKIEST` MUST tool · enforced (R-EVD-003)<br>`EVD-MISSING` SHOULD tool · enforced (R-EVD-004) |
| Failure conditions | Evidence cites an unknown source; An insight without evidence; No assumption flagged as riskiest; A registered local source is missing (blocking gap) |
| Retry | 3 attempts — Re-dispatch with the failing evidence checks; gaps are outcomes, not failures |
| Escalation | after gaps_blocking, 3 consecutive failed attempts, or the intake loop traversed twice → Wei: The gap list, and what source or answer would close each gap |
| Human review | Not required; blocking gaps escalate to Wei |
| Outcomes | pass, gaps_resolvable, gaps_blocking |
| Provenance | inputs_frozen ledger event with the inputs sha256; gaps.json kept per attempt; research.md versions archived under .pdg/controls/ |

**Instructions.** Extract each evidence item (E-xx) as a claim, the source ids it comes from and a tag. Group the evidence into insights (each citing evidence ids, with a confidence). List the assumptions the team is treating as fact (A-xx), with importance and certainty, and flag the riskiest. Declare missing information in `missing`: anything the brief asks for that the sources do not contain. Write research.md from the template, and keep its Evidence log append-only. The deterministic hook then hashes every local source and decides: `pass` freezes the inputs, `gaps_resolvable` loops back to intake with the gap list, and `gaps_blocking` escalates to Wei.

## N03 `n03_problem_definition` — Problem and opportunity definition

*Understand · Problem Definition · subgraph `definition` · kind **agent** · 👤 human gate*

**Purpose.** Commit to one problem — the job, the primary persona and the top pain, each in one sentence with evidence — and the opportunity and point of view that follow from it.

| Field | Definition |
|---|---|
| Depends on | `n02_evidence_review` |
| Inputs | `state:research.evidence`<br>`state:research.insights`<br>`state:research.assumptions`<br>`artifact:evidence`<br>`control:research`<br>`rework:self` |
| Outputs | `problem` (json, schema problem) — Problem frame and POV<br>`product_md` (control, installs product.md) — your copy of product.md, installed into controls/product.md — Problem section |
| State read | `research.evidence`, `research.insights`, `research.assumptions` |
| State written | `product.problem`, `product.users`, `product.customer_context` |
| Responsible agent | `product-strategist` |
| Skills | `problem-framing`, `problem-statement-builder`, `design-pov-author`, `jobs-to-be-done`, `how-might-we` |
| Tools | pdg.tools.product:check_problem |
| Context | The problem-frame and POV templates (00_README/_templates/1-0, 2-1); Gate to Design (design-thinking-loop.md): the job, the persona and the top pain in one sentence each, with evidence; Solve the right problem first (wei-isms §2) |
| Control documents | read research · write product |
| Completion criteria | The problem frame validates against its schema<br>Job, persona and top pain are one sentence each; the pain cites known evidence; ≥ 3 How-Might-We questions |
| Evaluation checks | `PRB-ONE-SENTENCE` MUST tool · enforced (R-CBV-001)<br>`PRB-EVIDENCE` MUST tool · enforced (R-CBV-001)<br>`PRB-HMW` SHOULD tool · advisory (R-CBV-002)<br>`PRB-APPROVED` MUST human · enforced (R-GOV-003) |
| Failure conditions | The job, persona or pain runs to more than one sentence; The top pain cites no evidence, or unknown evidence; Fewer than three How-Might-We questions |
| Retry | 3 attempts — Re-dispatch with the failing checks, or with Wei's rejection reason after a rejected gate |
| Escalation | after 3 consecutive failed attempts, or 2 rejections (E07) → Wei: The frame as it stands, and what Wei's rejections asked for |
| Human review | Is this the right problem? (Understand → Design gate) (approver Wei; outcomes approved, rejected) |
| Outcomes | approved, rejected |
| Provenance | Problem frame per attempt; Wei's decision and words in history.approvals; product.md versions archived |

**Instructions.** Write the problem frame: a problem statement, the job, the primary persona, the top pain (with evidence ids), the opportunity, a POV (user · need · insight), who we design against, at least three How-Might-We questions, and the decisions the prototype must enable. The job, the persona and the top pain are one sentence each. Every evidence id must exist in research.evidence. Update product.md's Problem section. Wei approves or rejects the frame at the gate.

## N04 `n04_requirements` — User, business, and technical requirements

*Design · Problem Definition · subgraph `definition` · kind **agent***

**Purpose.** Derive user, business and technical requirements, each traced to evidence or to a named assumption and each P0 with acceptance criteria, plus the business, technical, regulatory and time constraints.

| Field | Definition |
|---|---|
| Depends on | `n03_problem_definition` |
| Inputs | `state:product.problem`<br>`state:research.evidence`<br>`state:research.assumptions`<br>`artifact:problem`<br>`control:product`<br>`control:research`<br>`rework:self` |
| Outputs | `requirements` (json, schema requirements) — Requirements and constraints<br>`product_md` (control, installs product.md) — your copy of product.md, installed into controls/product.md — Requirements and Constraints sections |
| State read | `product.problem`, `research.evidence`, `research.assumptions` |
| State written | `product.requirements`, `product.constraints` |
| Responsible agent | `product-strategist` |
| Skills | `prd-author`, `constraint-mapping`, `jobs-to-be-done`, `spec-driven-development`, `evidence-tagging` |
| Tools | pdg.tools.product:check_requirements |
| Context | The PRD template §7–8 (00_README/_templates/2-3); Constraint mapping: technical, business, regulatory and time limits known to engineers; A requirement without evidence must name the assumption it rests on |
| Control documents | read product, research · write product |
| Completion criteria | The requirements document validates against its schema<br>Every requirement traces to evidence or an assumption; every P0 has acceptance criteria; all three types are present |
| Evaluation checks | `REQ-TRACE` MUST tool · enforced (R-EVD-002)<br>`REQ-ACCEPTANCE` MUST tool · enforced (R-SCP-007)<br>`REQ-TYPES` SHOULD tool · enforced (R-SCP-008)<br>`REQ-CONSTRAINTS` MUST tool · enforced (R-SCP-009) |
| Failure conditions | A requirement with no evidence and no assumption; A P0 without acceptance criteria; A missing requirement type; No constraints |
| Retry | 3 attempts — Re-dispatch with the untraced requirements listed |
| Escalation | after 3 consecutive failed attempts, or a rework cycle whose fix would change locked product.md → Wei: The untraced requirements and the evidence that would support them |
| Human review | Signed with the scope at N05 |
| Outcomes | pass |
| Provenance | Requirement → evidence and assumption links; product.md versions archived |

**Instructions.** Write requirements R-xx with a type (user | business | technical), a statement, a priority (P0 | P1 | P2), the evidence ids or assumption ids they rest on, and acceptance criteria (required for every P0). Include at least one requirement of each type. Write constraints C-xx with a type and a source. Update product.md's Requirements and Constraints sections. Never add a requirement that no evidence or named assumption supports.

## N05 `n05_scope_success` — Product scope and success criteria

*Design · Problem Definition · subgraph `definition` · kind **agent** · 👤 human gate*

**Purpose.** Sign the product scope — objective, value proposition, in and out of scope, non-goals, numeric success criteria, guardrails and specific rollback triggers — and the quality bar every later gate uses.

| Field | Definition |
|---|---|
| Depends on | `n04_requirements` |
| Inputs | `state:product.requirements`<br>`state:product.constraints`<br>`state:product.problem`<br>`artifact:requirements`<br>`control:product`<br>`rework:self` |
| Outputs | `scope` (json, schema scope) — Objective, value proposition, scope, success criteria, rollback triggers<br>`product_md` (control, installs product.md) — your copy of product.md, installed into controls/product.md — Scope and Success criteria<br>`evaluation_md` (control, installs evaluation.md) — your copy of evaluation.md, installed into controls/evaluation.md — the approved quality gates |
| State read | `product.requirements`, `product.constraints`, `product.problem` |
| State written | `product.objective`, `product.value_proposition`, `product.scope`, `product.success_criteria`, `product.rollback_triggers`, `research.open_questions` |
| Responsible agent | `product-strategist` |
| Skills | `success-metrics`, `prd-author`, `traffic-light-decisions`, `extreme-clarity`, `pathfinder-prioritizer` |
| Tools | pdg.tools.product:check_scope |
| Context | The PRD template §5–6, §10–11 and the design-brief template §8, §11; Wei's quality bars: non-goals never empty, scope-out never empty, rollback triggers specific, numbers not adjectives; Gate to Build: PRD signed 🟢; open questions answered or 🟡 with a trigger and an expiry |
| Control documents | read product, research · write product, evaluation · locks on approval product, evaluation |
| Completion criteria | The scope document validates against its schema<br>Non-goals and out-of-scope are non-empty; targets are numeric; rollback triggers are specific; every yellow has a trigger and an expiry |
| Evaluation checks | `SCP-NONGOALS` MUST tool · enforced (R-SCP-003)<br>`SCP-NUMBERS` MUST tool · enforced (R-SCP-005)<br>`SCP-ROLLBACK` MUST tool · enforced (R-SCP-004)<br>`SCP-YELLOW` MUST tool · enforced (R-SCP-002)<br>`SCP-GUARDRAIL` SHOULD tool · advisory (R-SCP-010)<br>`SCP-SIGNOFF` MUST human · enforced (R-GOV-003) |
| Failure conditions | Empty non-goals or out-of-scope; A success target with no number; A vague rollback trigger; A yellow open question without a trigger or an expiry |
| Retry | 3 attempts — Re-dispatch with the failing quality bars, or with Wei's rejection reason |
| Escalation | after 3 consecutive failed attempts, or 2 rejections (E10) → Wei: The scope as drafted and the open questions that block sign-off |
| Human review | Sign the PRD scope and the quality bar (Design → Build gate) (approver Wei; outcomes approved, rejected) |
| Outcomes | approved, rejected |
| Provenance | Wei's sign-off in history.approvals; product.md and evaluation.md locked on approval (approved sha256 recorded) |

**Instructions.** Write the objective and value proposition in one sentence each. List in-scope items, out-of-scope items and non-goals; none may be empty. Write success criteria M-xx with a baseline, a numeric target, a unit and a method: at least one north star and one guardrail. Write rollback triggers that name a measurable condition. Every open question that stays open is a 🟡 with a trigger, an expiry and an owner. Update product.md (Scope and Success criteria) and evaluation.md (the quality bar, with any threshold overrides in its front matter). Wei's approval locks product.md and evaluation.md.

## N06 `n06_concept_ideation` — Concept ideation and comparison

*Design · Concept · subgraph `concept` · kind **agent** · 👤 human gate*

**Purpose.** Generate at least three distinct concepts, compare them against weighted criteria traced to the requirements, name each concept's riskiest assumption, and bring one recommendation to Wei.

| Field | Definition |
|---|---|
| Depends on | `n05_scope_success` |
| Inputs | `state:product.requirements`<br>`state:product.scope`<br>`state:product.success_criteria`<br>`state:research.assumptions`<br>`control:product`<br>`rework:self` |
| Outputs | `concepts` (json, schema concepts) — Criteria, concepts, scores and the recommendation |
| State read | `product.requirements`, `product.scope`, `product.success_criteria`, `research.assumptions` |
| State written | `design.criteria`, `design.concepts`, `design.selected_concept` |
| Responsible agent | `service-experience-designer` (consults `product-strategist`) |
| Skills | `concept-creator`, `crazy-8s`, `design-criteria`, `decision-matrix`, `competitive-landscape` |
| Tools | pdg.tools.concepts:check |
| Context | Design criteria are traced to requirements (design-criteria); Crazy 8s / lightning demos to widen the range before converging; A decision matrix makes a close call defensible; disagreement heard is recorded, never invented |
| Control documents | read product · write — |
| Completion criteria | The concepts document validates against its schema<br>≥ 3 concepts scored on every criterion; weights sum to 1; the selection is a concept; an override has a rationale; every concept names its riskiest assumption |
| Evaluation checks | `CON-OPTIONS` MUST tool · enforced (R-STR-001)<br>`CON-MATRIX` MUST tool · enforced (R-STR-002)<br>`CON-RISK` MUST tool · enforced (R-STR-003)<br>`CON-SELECTED` MUST human · enforced (R-GOV-003) |
| Failure conditions | Fewer than three concepts; Weights that do not sum to 1; An unscored criterion; A below-top selection without a rationale |
| Retry | 3 attempts — Re-dispatch with the failing matrix checks, or with Wei's rejection reason |
| Escalation | after 3 consecutive failed attempts, or 2 rejections (E12) → Wei: The matrix, and the two closest concepts with their trade-offs |
| Human review | Choose the concept to prototype (approver Wei; outcomes approved, rejected) |
| Outcomes | approved, rejected |
| Provenance | The decision matrix per attempt; Wei's choice and reason in history.approvals and history.decisions |

**Instructions.** Write criteria with weights that sum to 1, each tied to requirement ids. Write at least three concepts: a name, a summary, a before/after for the primary persona, the riskiest assumption, and a 1–5 score per criterion. Recommend one concept in `selected`. If it is not the highest weighted score, `rationale` must say why (≥ 40 characters). Record real disagreement only; leave it empty when none was heard. Wei chooses at the gate; a rejection re-opens ideation with Wei's reason.

## N07 `n07_experience_architecture` — Experience architecture and user flows

*Design · UX Design · subgraph `experience` · kind **agent***

**Purpose.** Turn the chosen concept into journeys, a screen inventory with routes, navigation and user flows that cover every P0 requirement, plus the system behaviour the flows depend on.

| Field | Definition |
|---|---|
| Depends on | `n06_concept_ideation` |
| Inputs | `state:design.concepts`<br>`state:design.selected_concept`<br>`state:product.requirements`<br>`state:product.problem`<br>`control:product`<br>`rework:self` |
| Outputs | `experience` (json, schema experience) — Journeys, screens, navigation, flows, system behaviour<br>`experience_md` (control, installs experience.md) — your copy of experience.md, installed into controls/experience.md — journeys, IA, flows |
| State read | `design.concepts`, `design.selected_concept`, `product.requirements`, `product.problem` |
| State written | `design.journeys`, `design.screens`, `design.flows` |
| Responsible agent | `service-experience-designer` |
| Skills | `user-journey-map`, `information-architecture-designer`, `terminology-taxonomy-designer`, `storyboard`, `jobs-to-be-done` |
| Tools | pdg.tools.experience:check_flows |
| Context | The journey-map template (00_README/_templates/1-4); Information architecture: one name per thing, and navigation that follows the domain's own lifecycle; Keep distinct domains as distinct workflows; unify the shell, not the domain logic (Wei, 2026-09-26) |
| Control documents | read product · write experience |
| Completion criteria | The experience document validates against its schema<br>Every P0 requirement is covered by a flow; every flow step names a known screen; every screen is reachable; routes are unique |
| Evaluation checks | `EXP-COVERAGE` MUST tool · enforced (R-IA-002)<br>`EXP-SCREENS` MUST tool · enforced (R-IA-003) |
| Failure conditions | An uncovered P0 requirement; A flow step on an unknown screen; An unreachable screen; A duplicate route |
| Retry | 3 attempts — Re-dispatch with the uncovered requirements and orphan screens |
| Escalation | after 3 consecutive failed attempts → Wei: The coverage matrix of requirements × flows, with the gaps |
| Human review | Reviewed through the prototype at N13–N14 |
| Outcomes | pass |
| Provenance | Requirement → flow coverage matrix recomputed at every attempt; experience.md versions archived |

**Instructions.** Write the journeys (persona, job, stages with doing, pain and opportunity), the screens (stable id, name, purpose, route, kind; and for a record, a form or a route nested under another screen's, its `parent`: the screen that links to it), the navigation, and flows F-xx (the requirement ids they serve, the entry and exit screens, and steps of screen · action · outcome). Every P0 requirement must be covered by at least one flow. Every screen must be reachable from the navigation, a flow, or its parent. Write experience.md's Journeys, Information architecture and Flows sections. The screen ids are the contract the prototype implements with `data-screen`.

## N08 `n08_interaction_design` — UX and interaction design

*Design · UX Design · subgraph `experience` · kind **agent***

**Purpose.** Specify every screen's states (loading, empty, error, success and the domain's own), interactions with triggers, feedback and keyboard behaviour, validation rules, and the focus and feedback rules the prototype must honour.

| Field | Definition |
|---|---|
| Depends on | `n07_experience_architecture` |
| Inputs | `state:design.screens`<br>`state:design.flows`<br>`state:product.requirements`<br>`artifact:experience`<br>`control:experience`<br>`rework:self` |
| Outputs | `interactions` (json, schema interactions) — Screen specs: states, interactions, validation; focus and feedback rules<br>`experience_md` (control, installs experience.md) — your copy of experience.md, installed into controls/experience.md — interactions and states |
| State read | `design.screens`, `design.flows`, `product.requirements` |
| State written | `design.interactions` |
| Responsible agent | `ux-interaction-designer` |
| Skills | `prototyping-principles`, `heuristic-evaluation`, `hitl-boundary-designer`, `content-writing`, `design-review` |
| Tools | pdg.tools.experience:check_interactions |
| Context | The design-handoff template §3–4, §7 (00_README/_templates/2-4); “The prototype looks good but does not work” → every state and error path is specified (Wei, brief 2026-09-26); Requirement-first panels: a locked action says what unlocks it |
| Control documents | read experience, product · write experience |
| Completion criteria | The interaction document validates against its schema<br>Every screen has a spec; list screens specify empty and error states, record screens an error state; every interaction has keyboard behaviour; focus and feedback rules exist |
| Evaluation checks | `EXP-STATES` MUST tool · enforced (R-UX-002)<br>`EXP-KEYBOARD` MUST tool · enforced (R-A11Y-003)<br>`EXP-LOCKED-EXPLAINED` MUST tool · enforced (R-UX-003) |
| Failure conditions | A screen without a spec; A data screen without empty or error states; An interaction without keyboard behaviour |
| Retry | 3 attempts — Re-dispatch with the missing states and interactions listed |
| Escalation | after 3 consecutive failed attempts → Wei: The screens whose behaviour is still unspecified |
| Human review | Reviewed through the prototype at N13–N14 |
| Outcomes | pass |
| Provenance | State inventory per screen; experience.md versions archived |

**Instructions.** Write one screen spec per screen in the experience document: its states (at least the success state, plus the empty and error states for every data screen), its interactions (trigger, response, feedback, keyboard), and its validation rules. Write the global focus rules (focus moves to the new heading on navigation; a visible focus ring everywhere) and feedback rules (status messages are announced; never colour alone). A list that holds a current item names its treatment: the design system's "where you are" mark (a bar, a ring) on a light fill, never a status colour; rest, hover and current visibly ordered (hover lighter than current); every status mark inside an item keeps its colour in every state. A consequential action is never automatic; a locked action states what unlocks it. Update experience.md's Interactions and states section.

## N09 `n09_visual_system` — Visual and design-system definition

*Design · UX Design · subgraph `experience` · kind **agent** · 👤 human gate*

**Purpose.** Define the visual language as tokens with provenance — colour roles, type scale, spacing, radii, motion, components, breakpoints — with every text and UI colour pair meeting WCAG contrast, and the prohibited patterns.

| Field | Definition |
|---|---|
| Depends on | `n07_experience_architecture` |
| Inputs | `state:design.screens`<br>`artifact:experience`<br>`files:sources/**`<br>`control:product`<br>`rework:self` |
| Outputs | `design_system` (json, schema design-system) — Tokens, pairs, components, rules<br>`design_md` (control, installs design.md) — your copy of design.md, installed into controls/design.md — visual language and prohibited patterns |
| State read | `design.screens` |
| State written | `design.system` |
| Responsible agent | `visual-design-system` (consults `accessibility-reviewer`) |
| Skills | `design-system-author`, `design-system-as-infrastructure`, `frontend-design`, `impeccable`, `accessibility-verification` |
| Tools | pdg.tools.design_system:check (WCAG contrast of every declared pair, type-scale and radius counts) |
| Context | The workspace design system (05_Library/DESIGN-SYSTEM-AI-INSTRUCTIONS.md) and the project's brand authority; Design system as infrastructure: reuse tokens and components; off-system output is a defect; One component language across surfaces: type scale, radii, focus ring, status colours (Wei, 2026-09-26) |
| Control documents | read product · write design · locks on approval design |
| Completion criteria | The design-system document validates against its schema<br>Every declared pair meets WCAG contrast, and every ratio design.md states is the one the tokens give; ≤ 8 type sizes, none below 12 px; spacing on a 4 px grid; tokens carry provenance; prohibited patterns listed |
| Evaluation checks | `VIS-CONTRAST` MUST tool · enforced (R-A11Y-002)<br>`VIS-RATIO-STATED` SHOULD tool · enforced (R-VIS-002)<br>`VIS-TYPE` MUST tool · enforced (R-VIS-001)<br>`VIS-RADII` SHOULD tool · enforced (R-VIS-001)<br>`VIS-SPACING` SHOULD tool · advisory (R-VIS-003)<br>`VIS-PROVENANCE` MUST tool · enforced (R-VIS-002)<br>`VIS-PROHIBITED` MUST tool · enforced (R-VIS-004)<br>`VIS-ALERT-RESERVED` MUST tool · enforced (R-VIS-005)<br>`VIS-APPROVED` MUST human · enforced (R-GOV-003) |
| Failure conditions | A declared pair below its contrast minimum; A type size below 12 px or more than 8 sizes; A token without provenance; No prohibited patterns |
| Retry | 3 attempts — Re-dispatch with the failing pairs and counts, or with Wei's rejection reason |
| Escalation | after 3 consecutive failed attempts, or 2 rejections (E17) → Wei: The token set, the failing pairs and the brand constraint in conflict |
| Human review | Approve the visual system (approver Wei; outcomes approved, rejected) |
| Outcomes | approved, rejected |
| Provenance | Contrast ratios recomputed from the token values; design.md locked on approval (approved sha256 recorded) |

**Instructions.** Write colour tokens (name, #rrggbb value, role, provenance), the type scale (≤ 8 sizes, none below 12 px), a 4 px spacing scale, radii (≤ 5), motion rules (respect reduced motion), components with their variants and states, breakpoints, the accessibility rules and the prohibited patterns. Declare every foreground/background pair the UI uses; each must meet 4.5:1 (3:1 for large text and non-text UI). Reserve the alert colour for alerts, and name the status each status colour carries in its role (alert, warning, success, watch…): no hover, current or selected state may take one. A ratio design.md states is the one the tokens give, cut or rounded, never rounded up across 4.5 or 3. Write design.md from the template. Wei approves the visual system, which locks design.md.

## N10 `n10_prototype_planning` — Prototype planning

*Build · Prototype · subgraph `prototype` · kind **agent** · 👤 human gate*

**Purpose.** Choose the fidelity the evidence supports, and plan the goals, the scenarios that exercise every P0 flow, the states to reach, the viewports, the content needs and the measurable test criteria.

| Field | Definition |
|---|---|
| Depends on | `n08_interaction_design`, `n09_visual_system` |
| Inputs | `state:design.flows`<br>`state:design.interactions`<br>`state:design.system`<br>`state:research.assumptions`<br>`state:product.success_criteria`<br>`state:product.requirements`<br>`artifact:interactions`<br>`artifact:design_system`<br>`control:experience`<br>`control:design`<br>`control:evaluation`<br>`rework:self` |
| Outputs | `plan` (json, schema plan) — Fidelity, scenarios, states, viewports, test criteria<br>`prototype_md` (control, installs prototype.md) — your copy of prototype.md, installed into controls/prototype.md — the prototype plan |
| State read | `design.flows`, `design.interactions`, `design.system`, `research.assumptions`, `product.success_criteria`, `product.requirements` |
| State written | `build.plan` |
| Responsible agent | `prototype-developer` (consults `ux-interaction-designer`) |
| Skills | `prototyping-assist`, `poc-planner`, `experiment-planner`, `hypothesis-creator`, `mve-mvp-planner` |
| Tools | pdg.tools.plan:check (fidelity gate, scenario and state coverage) |
| Context | The test-plan template (00_README/_templates/3-1); Build the thinnest slice that tests the riskiest assumption (design-thinking-loop.md, Build); “Development moved too quickly” → validated assumptions and customer alignment before fidelity rises (Wei, brief 2026-09-26) |
| Control documents | read experience, design, evaluation · write prototype · locks on approval prototype |
| Completion criteria | The plan validates against its schema<br>The fidelity gate holds; every P0 flow has a scenario ending in an expectation; every data screen's empty and error states are planned; viewports span ≤ 400 and ≥ 1280 px; every record screen names its worst-case samples |
| Evaluation checks | `PLN-FIDELITY-GATE` MUST tool · enforced (R-FID-001)<br>`PLN-SCENARIOS` MUST tool · enforced (R-VAL-002)<br>`PLN-STATES` MUST tool · enforced (R-UX-002)<br>`PLN-FOCUS` MUST tool · enforced (R-A11Y-003)<br>`PLN-ACCEPTANCE` MUST tool · enforced (R-SCP-007)<br>`PLN-SAMPLES` SHOULD tool · enforced (R-A11Y-004)<br>`PLN-VIEWPORTS` MUST tool · enforced (R-A11Y-004)<br>`PLN-APPROVED` MUST human · enforced (R-GOV-003) |
| Failure conditions | Mid/high fidelity with an unvalidated riskiest assumption; High fidelity without customer alignment; A P0 flow with no scenario; An unplanned empty or error state |
| Retry | 3 attempts — Re-dispatch with the failing gate; lowering the fidelity is a valid fix |
| Escalation | after 3 consecutive failed attempts, or 2 rejections (E19) → Wei: Which assumptions are unvalidated and the cheapest test that would validate each |
| Human review | Approve the fidelity and the prototype plan (approver Wei; outcomes approved, rejected) |
| Outcomes | approved, rejected |
| Provenance | Assumption status at planning time; prototype.md locked on approval |

**Instructions.** Pick a fidelity (low | mid | high). Mid or high fidelity needs every riskiest assumption validated, or accepted as a risk by a named human; high fidelity also needs customer alignment with evidence. Write scenarios S-xx in the step DSL (goto, click, fill, press, select, expect_*, screenshot, axe): at least one per P0 flow, and each ends in an expectation. Only a scenario's first `goto` loads the page cold: a later one that changes only the `#` route keeps the app's state, and one to the URL the page is on returns to the top with the state kept. For each record screen, name in `samples` two or more other records most likely to break its layout. List the states to reach (screen, state, route, marker selector) for every data screen's empty and error states; the viewports (at least one ≤ 400 px and one ≥ 1280 px); the content needs; and the test criteria. Write prototype.md. Wei's approval locks prototype.md.

## N11 `n11_prototype_development` — Prototype development

*Build · Development · subgraph `prototype` · kind **agent***

**Purpose.** Build a working, offline prototype of the planned scenarios on the approved tokens and components, with every screen and state implemented, domain logic unit-tested, and development.md as the implementation-ready foundation.

| Field | Definition |
|---|---|
| Depends on | `n10_prototype_planning` |
| Inputs | `state:build.plan`<br>`state:design.system`<br>`state:design.interactions`<br>`state:design.screens`<br>`artifact:plan`<br>`artifact:design_system`<br>`artifact:interactions`<br>`control:prototype`<br>`control:design`<br>`control:experience`<br>`control:product`<br>`rework:self` |
| Outputs | `prototype_build` (dir) — Prototype source and single-file build (src/, dist/, tests/, build script)<br>`build_manifest` (json, schema build-manifest) — Entry, stack, file hashes, screen selectors, unit tests<br>`development_md` (control, installs development.md) — your copy of development.md, installed into controls/development.md — the implementation-ready foundation |
| State read | `build.plan`, `design.system`, `design.interactions`, `design.screens` |
| State written | `build.code_artifacts` |
| Responsible agent | `prototype-developer` (consults `front-end-engineer`) |
| Skills | `frontend-design`, `web-artifacts-builder`, `design-system-as-infrastructure`, `test-driven-development`, `prototyping-principles` |
| Tools | python build script (assembles the single-file offline build and build-manifest.json); node --check and node --test (Node 22); pdg.tools.prototype:check_static |
| Context | The approved plan (prototype.md), design system (design.md) and interaction spec (experience.md); Single-file offline builds assembled from parts by a reproducible build script (the case-study pattern); “A visually polished prototype is not complete if its primary workflows do not function” (Wei, brief 2026-09-26) |
| Control documents | read prototype, design, experience, product · write development |
| Completion criteria | The prototype build directory was registered<br>The build manifest validates against its schema<br>Manifest hashes match; entry is offline; every screen is implemented; only design tokens are used; no placeholder text<br>Every script passes node --check and the domain unit tests pass |
| Evaluation checks | `BLD-OFFLINE` MUST tool · enforced (R-TEC-002)<br>`BLD-SCREENS` MUST tool · enforced (R-FUN-001)<br>`BLD-TOKENS` MUST tool · enforced (R-VIS-002)<br>`BLD-PLACEHOLDER` MUST tool · enforced (R-FID-003)<br>`BLD-REPRO` SHOULD tool · advisory (R-TEC-004)<br>`BLD-SYNTAX` MUST tool · enforced (R-TEC-003)<br>`BLD-UNIT` MUST tool · enforced (R-TEC-003) |
| Failure conditions | A manifest hash mismatch; A network reference in the build; An unimplemented screen; An off-system colour; A failing unit test |
| Retry | 3 attempts — Re-dispatch with the failing static checks and unit-test output |
| Escalation | after 3 consecutive failed attempts, or the same defect failed 3 corrections → Wei: The failing checks, what was tried, and whether the plan or the design system needs a change request |
| Human review | Reviewed at N13–N15 |
| Outcomes | pass |
| Provenance | Build directory tree hash; build-manifest.json file hashes; Unit-test results in evaluation.test_results |

**Instructions.** Implement every screen in the experience document and mark it with data-screen="<id>". Implement every planned state and mark it with its marker selector. Use only the design-system tokens (CSS custom properties); a colour outside the tokens is a defect. Keep domain logic (derivations, rules, guards) in a module with node unit tests. Build to a self-contained file that runs from file:// with no network requests. Write build-manifest.json (entry, stack, file hashes, screen selectors, unit-test file) and development.md (architecture, technology choices, components, data and APIs, folder structure, implementation standards, testing requirements). On rework, change only what the defect needs.

## N12 `n12_content_data` — Content and realistic data integration

*Build · Prototype · subgraph `prototype` · kind **agent***

**Purpose.** Replace seed data with realistic, labelled, reproducible content — datasets that exercise the planned edge cases and a copy deck in the users' vocabulary — and integrate them into the prototype build under review.

| Field | Definition |
|---|---|
| Depends on | `n11_prototype_development` |
| Inputs | `artifact:prototype_build`<br>`artifact:plan`<br>`state:build.plan`<br>`state:design.screens`<br>`state:research.evidence`<br>`control:prototype`<br>`control:research`<br>`rework:self` |
| Outputs | `prototype` (dir) — The integrated prototype version under review<br>`content` (json, schema content) — Datasets with provenance, copy deck, edge cases |
| State read | `build.plan`, `design.screens`, `research.evidence` |
| State written | `build.prototype`, `build.version`, `build.content_artifacts` |
| Responsible agent | `content-designer` |
| Skills | `content-writing`, `content-designer`, `terminology-taxonomy-designer`, `asset-collection`, `evidence-tagging` |
| Tools | seeded synthetic-data generator; python build script; pdg.tools.content:check |
| Context | “The prototype is too generic” → product-specific, realistic content and meaningful workflows (Wei, brief 2026-09-26); Synthetic or invented data is labelled at the point of decision; missing data is shown as missing, never as zero; Seeded generators make data reproducible |
| Control documents | read prototype, research · write — |
| Completion criteria | The integrated prototype directory was registered<br>The content document validates against its schema<br>Datasets exist and parse; volume meets the plan; provenance is labelled in the UI; every source id is known and every verified field is in the data; every edge case appears in the data; no placeholder text |
| Evaluation checks | `CNT-PLACEHOLDER` MUST tool · enforced (R-FID-003)<br>`CNT-PROVENANCE` MUST tool · enforced (R-FID-002)<br>`CNT-VOLUME` SHOULD tool · advisory (R-FID-004)<br>`CNT-EDGE` MUST tool · enforced (R-FID-005) |
| Failure conditions | Placeholder text in the build; Synthetic data without a visible label; A planned edge case missing from the data; Too few records |
| Retry | 3 attempts — Re-dispatch with the failing content checks |
| Escalation | after 3 consecutive failed attempts → Wei: Which content cannot be made realistic without a real source, and who could supply it |
| Human review | Reviewed at N13–N14 |
| Outcomes | pass |
| Provenance | Dataset seed and generator recorded; The integrated build's tree hash becomes build version N; history.versions entry |

**Instructions.** Generate or curate datasets with a seed and a provenance (real | synthetic | invented | mixed: invented records whose `verified_fields` were checked against the named `source_ids`). Cover every edge case the plan's scenarios need (for example out-of-range, missing and borderline values) and name them in `edge_cases`. Write the copy deck in the users' own vocabulary. Show a visible label in the UI when data is synthetic. Integrate the data and copy into a copy of `artifact:prototype_build` and rebuild; submit the rebuilt directory as `prototype`. Never leave lorem ipsum, TODO or TBD text.

## N13 `n13_quality_review` — Functional, design, and accessibility review

*Build · Validation · subgraph `validation` · kind **review***

**Purpose.** Run every planned scenario in a real browser at every viewport, audit accessibility, responsiveness, console, network and performance, then judge visual hierarchy, product specificity and consistency from the screenshots.

| Field | Definition |
|---|---|
| Depends on | `n12_content_data` |
| Inputs | `artifact:prototype`<br>`artifact:plan`<br>`state:build.plan`<br>`state:build.prototype`<br>`state:design.system`<br>`state:design.screens`<br>`control:design`<br>`control:experience`<br>`control:evaluation`<br>`rework:self` |
| Outputs | `browser_report` (json) — Tool pre-check: scenarios, axe, overflow, targets, text size, focus, console, network, timing<br>`screenshots` (dir) — Screenshots per screen, state and viewport<br>`quality_review` (json, schema review) — The agent's scored review dimensions and findings |
| State read | `build.plan`, `build.prototype`, `design.system`, `design.screens` |
| State written | `evaluation.reviews`, `evaluation.test_results` |
| Responsible agent | `product-ux-critic` (consults `accessibility-reviewer`, `technical-qa`) |
| Skills | `design-review`, `accessibility-verification`, `webapp-testing`, `prototype-qa`, `heuristic-evaluation` |
| Tools | Playwright Chromium through pdg.tools.browser:check; axe-core 4.11.4 (vendored; WCAG 2.0/2.1/2.2 A and AA tags); full-page screenshots per screen, state and viewport |
| Context | Rendered-output inspection finds defects that value checks miss (case-study lesson); Automated accessibility testing finds about 57% of WCAG issues (Deque); the rest needs judgement; “The design is hard to read” → hierarchy, contrast, typography, spacing, density (Wei, brief 2026-09-26) |
| Control documents | read design, experience, evaluation · write — |
| Completion criteria | The browser suite ran and wrote its report<br>Every MUST review dimension is scored with evidence |
| Evaluation checks | `FUNC-SCENARIOS` MUST tool · enforced (R-FUN-001)<br>`FUNC-STATES` MUST tool · enforced (R-UX-002)<br>`VIS-TOKENS-RUNTIME` MUST tool · enforced (R-VIS-002)<br>`VIS-STATE-FILLS` SHOULD tool · enforced (R-VIS-005)<br>`REF-PARITY` SHOULD tool · enforced (R-SCP-001)<br>`FUNC-CONSOLE` MUST tool · enforced (R-TEC-005)<br>`FUNC-OFFLINE` MUST tool · enforced (R-TEC-002)<br>`PERF-LOAD` SHOULD tool · informational (R-TEC-006)<br>`A11Y-AXE` MUST tool · enforced (R-A11Y-001)<br>`A11Y-FOCUS` MUST tool · enforced (R-A11Y-003)<br>`A11Y-FOCUS-VISIBLE-2411` MUST tool · enforced (R-A11Y-003)<br>`A11Y-FOCUS-POINTER` SHOULD tool · enforced (R-A11Y-003)<br>`A11Y-TEXT-SPACING-1412` MUST tool · enforced (R-A11Y-007)<br>`A11Y-TARGET-AA` MUST tool · enforced (R-A11Y-005)<br>`A11Y-TARGET-44` SHOULD tool · advisory (R-A11Y-006)<br>`A11Y-TYPE-MIN` MUST tool · enforced (R-A11Y-007)<br>`A11Y-REDUCED-MOTION` MUST tool · enforced (R-A11Y-009)<br>`A11Y-SEMANTICS` MUST review · enforced (R-A11Y-008)<br>`A11Y-MANUAL` MUST review · enforced (R-A11Y-008)<br>`RESP-OVERFLOW` MUST tool · enforced (R-A11Y-004)<br>`RESP-REFLOW-320` MUST tool · enforced (R-A11Y-004)<br>`RESP-BAND` MUST tool · enforced (R-A11Y-004)<br>`RESP-TEXT` MUST tool · advisory (R-VIS-006)<br>`RESP-LAYOUT` SHOULD review · advisory (R-VIS-006)<br>`DES-HIERARCHY` MUST review · enforced (R-VIS-007)<br>`DES-SPECIFICITY` MUST review · enforced (R-FID-006)<br>`DES-CONSISTENCY` MUST review · enforced (R-VIS-001)<br>`DES-DENSITY` MUST review · enforced (R-VIS-008)<br>`DES-SEMANTIC-COLOR` MUST review · enforced (R-VIS-005)<br>`DES-DERIVATION` MUST review · enforced (R-UX-001)<br>`DES-SCOPE-VISIBLE` MUST review · enforced (R-SCP-006)<br>`DES-DOMAIN` SHOULD review · enforced (R-IA-001)<br>`DES-TASTE` SHOULD human · enforced (R-GOV-003) |
| Failure conditions | The browser suite could not run (escalates: Playwright or Chromium unavailable); A MUST review dimension left unscored |
| Retry | 2 attempts — Re-dispatch with the unscored dimensions; findings are outcomes, not failures |
| Escalation | after 2 consecutive failed attempts, or the browser cannot start → Wei: The tool error, or the dimensions the reviewer could not judge from the evidence |
| Human review | Wei's taste dimensions stay pending until N18 |
| Outcomes | pass |
| Provenance | browser-report.json and screenshots per build version; Review record per attempt in evaluation.reviews |

**Instructions.** The tool pre-check has already run the browser suite: read browser-report.json and the screenshots. Score every review dimension 1–5 (4 meets the bar) with evidence (the screenshot and the element). For every score below 4, file a finding with a severity, the location (screen:viewport), the node it traces to, the smallest fix and an acceptance check. Never re-score a tool dimension; a tool failure cannot be overridden. Never review work you produced.

## N14 `n14_validation` — User and stakeholder validation

*Learn · Validation · subgraph `validation` · kind **review***

**Purpose.** Put the planned scenarios in front of named participants and stakeholders, record task success, time, ease (SEQ) and quotes, and keep simulated input strictly apart from user evidence.

| Field | Definition |
|---|---|
| Depends on | `n12_content_data` |
| Inputs | `artifact:prototype`<br>`artifact:plan`<br>`state:build.plan`<br>`state:product.success_criteria`<br>`feedback:open`<br>`control:research`<br>`control:evaluation`<br>`rework:self` |
| Outputs | `moderator_guide` (markdown) — Tool pre-check: tasks, success criteria and the SEQ question for each scenario<br>`validation` (json, schema validation) — Sessions, tasks, quotes and findings<br>`validation_review` (json, schema review) — Scored review dimensions and findings<br>`research_md` (control, installs research.md) — your copy of research.md, installed into controls/research.md — validation findings appended |
| State read | `build.plan`, `product.success_criteria` |
| State written | `evaluation.reviews`, `research.validation_findings` |
| Responsible agent | `context-research` (consults `product-ux-critic`) |
| Skills | `usability-metrics`, `desirability-testing`, `feedback-collector`, `uxr-feedback-assist`, `interview-debrief` |
| Tools | pdg.tools.validation:prepare (moderator guide from the plan's scenarios); pdg.tools.validation:check (success rate, time, SEQ; simulated input flagged) |
| Context | Task success rate is the bottom line of usability; SEQ is a 7-point post-task question (NN/g, MeasuringU); Three rounds of five users beat one round of fifteen (NN/g); An agent never plays a user: simulated sessions are labelled and never counted as evidence |
| Control documents | read research, evaluation · write research |
| Completion criteria | The validation document validates against its schema<br>Every task maps to a planned scenario; success rate, time and SEQ are computed; simulated sessions are flagged<br>Every MUST review dimension is scored |
| Evaluation checks | `VAL-TASK-SUCCESS` MUST tool · enforced (R-VAL-003)<br>`VAL-SEQ` SHOULD tool · informational (R-VAL-004)<br>`VAL-SIMULATED-FLAGGED` MUST tool · enforced (R-GOV-004)<br>`VAL-INSIGHT` MUST review · enforced (R-VAL-005)<br>`VAL-REAL-USERS` MUST human · enforced (R-VAL-001) |
| Failure conditions | A task on an unknown scenario; A session without the simulated flag; A MUST review dimension left unscored |
| Retry | 2 attempts — Re-dispatch with the failing validation checks |
| Escalation | after 2 consecutive failed attempts → Wei: Which sessions could not be run, and whom to recruit |
| Human review | Real-user validation is a human dimension, confirmed by Wei at N18 |
| Outcomes | pass |
| Provenance | Sessions per build version; simulated input flagged; research.md validation findings are append-only |

**Instructions.** Use the moderator guide the pre-check wrote. For each session record the participant (role and an anonymised id), whether it was simulated, and per task the scenario id, success, time and SEQ, plus verbatim quotes. File findings for failed or hard tasks and for stakeholder concerns, each traced to the node it implicates, with the smallest fix and an acceptance check. Append the validation findings to research.md; its Evidence log is append-only. Score the review dimensions. If no real participant was available, say so: the human dimension stays pending.

## N15 `n15_feasibility_review` — Technical feasibility review

*Build · Validation · subgraph `validation` · kind **review***

**Purpose.** Check that the prototype is a sound implementation foundation — scripts parse, domain tests pass, the bundle stays in budget, nothing depends on the network — and judge whether development.md is buildable for production.

| Field | Definition |
|---|---|
| Depends on | `n12_content_data` |
| Inputs | `artifact:prototype`<br>`artifact:prototype_build`<br>`artifact:build_manifest`<br>`state:build.prototype`<br>`control:development`<br>`control:product`<br>`control:evaluation`<br>`rework:self` |
| Outputs | `feasibility_report` (json) — Tool pre-check: syntax, unit tests, bundle size, dependencies, development.md sections<br>`feasibility_review` (json, schema review) — Scored feasibility dimensions and findings |
| State read | `build.prototype`, `build.code_artifacts` |
| State written | `evaluation.reviews`, `evaluation.test_results` |
| Responsible agent | `front-end-engineer` (consults `technical-qa`) |
| Skills | `code-review-and-quality`, `performance-optimization`, `security-and-hardening`, `test-driven-development`, `observability-and-instrumentation` |
| Tools | pdg.tools.feasibility:check (node --check, node --test, bundle budget, offline dependency audit, development.md sections) |
| Context | Code review across correctness, readability, architecture, security and performance; Staged data proves interaction, not integration: say which seams need real services; A prototype is not a production claim |
| Control documents | read development, product, evaluation · write — |
| Completion criteria | The feasibility pre-check ran and wrote its report<br>Every MUST review dimension is scored |
| Evaluation checks | `TEC-SYNTAX` MUST tool · enforced (R-TEC-003)<br>`TEC-UNIT` MUST tool · enforced (R-TEC-003)<br>`TEC-BUNDLE` SHOULD tool · advisory (R-TEC-007)<br>`TEC-DEPS` MUST tool · enforced (R-TEC-002)<br>`TEC-DEVDOC` MUST tool · enforced (R-TEC-008)<br>`TEC-FEASIBLE` MUST review · enforced (R-TEC-009)<br>`TEC-QUALITY` SHOULD review · enforced (R-TEC-003) |
| Failure conditions | The feasibility pre-check could not run; A MUST review dimension left unscored |
| Retry | 2 attempts — Re-dispatch with the unscored dimensions |
| Escalation | after 2 consecutive failed attempts, or node is unavailable → Wei: The tool error or the unanswerable feasibility questions |
| Human review | Not required |
| Outcomes | pass |
| Provenance | feasibility-report.json per build version; Unit-test results in evaluation.test_results |

**Instructions.** Read feasibility-report.json. Score the review dimensions with evidence. File a finding, with a trace, the smallest fix and an acceptance check, for every architecture, security, performance or maintainability risk that would block turning the prototype into production code. Name the integration seams that stay mocked and what each needs (APIs, auth, persistence). Never claim production readiness.

## N16 `n16_feedback_diagnosis` — Feedback diagnosis

*Learn · Iteration · subgraph `iteration` · kind **gate***

**Purpose.** Turn every blocking finding and every open piece of feedback into a traced defect — the requirement, design decision, node or implementation it comes from, the smallest effective fix and an acceptance check — then gate the version pass, rework or blocked.

| Field | Definition |
|---|---|
| Depends on | `n13_quality_review`, `n14_validation`, `n15_feasibility_review` |
| Inputs | `state:evaluation.reviews`<br>`state:evaluation.feedback`<br>`state:evaluation.defects`<br>`feedback:open`<br>`defects:open`<br>`artifact:browser_report`<br>`artifact:quality_review`<br>`artifact:validation_review`<br>`artifact:feasibility_review`<br>`control:evaluation`<br>`rework:self` |
| Outputs | `interpretation` (json, schema interpretation) — Traced defects and the feedback mapping<br>`gate_report` (json) — Hook output: gate outcome, reasons, blocking defects, targets, comparison |
| State read | `evaluation.reviews`, `evaluation.feedback`, `evaluation.defects` |
| State written | `evaluation.defects`, `evaluation.feedback`, `evaluation.gates`, `evaluation.comparisons` |
| Responsible agent | `orchestrator` (consults `product-ux-critic`, `technical-qa`) |
| Skills | `debugging-and-error-recovery`, `five-whys`, `fishbone-diagram`, `traffic-light-decisions`, `rose-bud-thorn` |
| Tools | pdg.tools.diagnosis:gate (tri-state gate and before/after comparison) |
| Context | The seven-step failure procedure: identify, trace, smallest fix, re-run only what is affected, compare, record, escalate; Tool findings arrive pre-traced; confirm or re-trace them; Wei's words are feedback, not instructions to redesign everything (“you made an over design”, 2026-09-26) |
| Control documents | read evaluation · write — |
| Completion criteria | The interpretation validates against its schema<br>Every open feedback item and blocking agent/human finding is mapped; every defect has a known trace, a smallest fix and an acceptance check |
| Evaluation checks | `GAT-TRACE` MUST tool · enforced (R-GOV-005)<br>`GAT-FEEDBACK` MUST tool · enforced (R-GOV-006)<br>`GAT-ESCALATE` MUST tool · enforced (R-GOV-007) |
| Failure conditions | An unmapped feedback item; A blocking finding without a defect; A defect traced to an unknown node or without a fix |
| Retry | 3 attempts — Re-dispatch with the unmapped findings and feedback listed |
| Escalation | after Gate outcome blocked, or 3 consecutive failed attempts → Wei: Open defects, their traces, what was tried in each cycle, and what unblocks the run |
| Human review | Blocked gates escalate to Wei |
| Outcomes | pass, rework, blocked |
| Provenance | Gate result per cycle in evaluation.gates; Before/after comparison per rework cycle; Ledger: gate, regeneration_plan |

**Instructions.** For every blocking agent or human finding and every open feedback item, write a defect: a stable signature (dimension@location), the severity, the evidence, the node it traces to and why (trace_reason), the smallest fix and an acceptance check. Blocking tool findings are mapped automatically from their own trace; re-trace one only with a reason. Map every feedback item to defects or dismiss it with a reason. Trace to the earliest node whose output is wrong, not to the last node that touched it. The deterministic gate then decides: pass (nothing blocking), rework (routable defects and budget left) or blocked (needs Wei: a locked document, an unroutable trace, a defect that failed 3 corrections, or the cycle budget spent).

## N17 `n17_targeted_rework` — Targeted redesign or redevelopment

*Build · Iteration · subgraph `iteration` · kind **tool***

**Purpose.** Plan the smallest correction — re-open only the nodes the defects trace to (a design node for redesign, a build node for redevelopment), snapshot their outputs for the before/after comparison, and hand each target its defects.

| Field | Definition |
|---|---|
| Depends on | `n16_feedback_diagnosis` |
| Inputs | `state:evaluation.gates`<br>`state:evaluation.defects`<br>`artifact:gate_report`<br>`rework:self` |
| Outputs | `regeneration_plan` (json) — Targets, defects per target, before-snapshot |
| State read | `evaluation.gates`, `evaluation.defects` |
| State written | `evaluation.defects`, `history.revisions` |
| Responsible agent | `orchestrator` |
| Skills | `debugging-and-error-recovery`, `code-simplification`, `drift-check`, `design-decision-articulator`, `traffic-light-decisions` |
| Tools | pdg.tools.regen:plan; pdg.tools.regen:check_targeted |
| Context | Minimal regeneration: fingerprints skip unaffected work; Change only what the defect needs; never restart the whole project to fix one defect |
| Control documents | read — · write — |
| Completion criteria | The regeneration plan was written<br>Every target is a regeneration target traced by an open defect; no untraced node is re-opened |
| Evaluation checks | `RGN-TARGETED` MUST tool · enforced (R-SCP-001) |
| Failure conditions | A target no defect traces to; A target outside the regeneration targets |
| Retry | 2 attempts — Tool errors only |
| Escalation | after No routable target (E40), or a loop edge's traversal budget spent → Wei: The defects that could not be routed and the rework history |
| Human review | Not required |
| Outcomes | rework, no_target |
| Provenance | regeneration-plan.json per cycle; Ledger: regeneration_plan, invalidated; history.revisions per target |

**Instructions.** Deterministic. Build the regeneration plan from the gate: the target nodes (only regeneration targets), the defects per target with their smallest fix and acceptance check, and a snapshot of each target's current output hashes. The engine then fires one `target:<node>` loop edge per target, invalidating the target and its flow descendants; unchanged fingerprints are memo-skipped. A plan with no target escalates.

## N18 `n18_final_verification` — Final verification and delivery

*Build · Validation · subgraph `delivery` · kind **tool** · 👤 human gate*

**Purpose.** Recompute every release condition from disk, package the prototype with its evidence and a hashed manifest, list every human dimension still pending, and ask Wei to release or request changes.

| Field | Definition |
|---|---|
| Depends on | `n16_feedback_diagnosis` |
| Inputs | `state:evaluation.gates`<br>`state:evaluation.defects`<br>`state:evaluation.reviews`<br>`state:build.prototype`<br>`state:history.approvals`<br>`artifact:prototype`<br>`artifact:gate_report`<br>`control:product`<br>`control:evaluation`<br>`rework:self` |
| Outputs | `release_report` (json) — Every release condition with its evidence<br>`release_summary` (markdown) — TL;DR, conditions, pending human dimensions, non-human approvals<br>`package` (dir) — Prototype, control documents and evidence with a sha256 manifest |
| State read | `evaluation.gates`, `evaluation.defects`, `evaluation.reviews`, `build.prototype`, `history.approvals` |
| State written | `history.decisions`, `history.versions` |
| Responsible agent | `technical-qa` (consults `orchestrator`) |
| Skills | `shipping-and-launch`, `prototype-review`, `traffic-light-decisions`, `extreme-clarity`, `documentation-and-adrs` |
| Tools | pdg.tools.release:verify (recompute conditions, verify the ledger, package with sha256 manifest) |
| Context | A technical pass is not a release: Wei decides; Dry-run approvals are labelled not human in the package; Simulated validation is listed as simulated, never as user evidence |
| Control documents | read product, evaluation · write — |
| Completion criteria | The release report was written<br>The package directory was registered |
| Evaluation checks | `REL-CONDITIONS` MUST tool · enforced (R-GOV-008)<br>`REL-PACKAGE` MUST tool · enforced (R-GOV-009)<br>`REL-HONEST` MUST tool · enforced (R-GOV-004)<br>`REL-DECISION` MUST human · enforced (R-GOV-003) |
| Failure conditions | A release condition fails on recompute; A manifest hash mismatch; The ledger fails verification |
| Retry | 2 attempts — Tool errors only; a failed condition escalates |
| Escalation | after A failed release condition, or 2 change-request loops (E42) → Wei: The failing condition with its evidence |
| Human review | Release this prototype version, or request changes with feedback (approver Wei; outcomes approved, changes_requested) |
| Outcomes | approved, changes_requested |
| Provenance | release-report.json and package manifest (sha256 per file); Wei's release decision in history.approvals |

**Instructions.** Deterministic. Verify the latest gate passed on the current build version, that no blocking defect is open and that every review is current; re-hash the prototype, verify the ledger, and package the prototype, the control documents, the reviews, the gate history, the comparisons and the approvals with a sha256 manifest. The release summary leads with a TL;DR and lists pending human dimensions and non-human approvals. Wei releases the version or requests changes with feedback, which loops back to diagnosis (E42).

## N19 `n19_learning_memory` — Learning and memory update

*Learn · Iteration · subgraph `delivery` · kind **gate***

**Purpose.** Capture what this run taught — defects, effective corrections, rule observations and Wei's feedback — separate project-specific notes from reusable lessons, and propose rule changes that only a named human can apply.

| Field | Definition |
|---|---|
| Depends on | `n18_final_verification` |
| Inputs | `state:evaluation.defects`<br>`state:evaluation.comparisons`<br>`state:evaluation.feedback`<br>`state:knowledge.enforced`<br>`state:history.approvals`<br>`artifact:release_report`<br>`control:memory`<br>`rework:self` |
| Outputs | `lessons` (json, schema lessons) — Lessons classified by scope and evidence<br>`memory_md` (control, installs memory.md) — your copy of memory.md, installed into controls/memory.md — project lessons and patterns<br>`learning_proposal` (json) — Hook output: rule observations and new candidates, for `pdg memory apply` |
| State read | `evaluation.defects`, `evaluation.comparisons`, `evaluation.feedback`, `knowledge.enforced` |
| State written | `knowledge.lessons`, `knowledge.proposal` |
| Responsible agent | `learning-memory` |
| Skills | `rubric-authoring`, `evidence-tagging`, `decision-capture`, `skill-creator`, `wiki-ingest` |
| Tools | pdg.tools.learning:propose (rule observations and candidates); pdg.tools.learning:check_lessons |
| Context | Rule lifecycle: candidate → validated → approved → adopted → monitored → revised | retired; Evidence before any change to default behaviour; Learning never edits product truth, requirements, evidence or approved design principles |
| Control documents | read memory · write memory |
| Completion criteria | The lessons document validates against its schema<br>Every lesson has evidence and a scope; referenced rules exist; nothing targets a protected scope |
| Evaluation checks | `LRN-EVIDENCE` MUST tool · enforced (R-LRN-001)<br>`LRN-SCOPE` MUST tool · enforced (R-LRN-002)<br>`LRN-PROTECTED` MUST tool · enforced (R-LRN-003)<br>`LRN-HONEST` MUST tool · enforced (R-GOV-004) |
| Failure conditions | A lesson without evidence; A lesson that changes a protected scope; A reference to an unknown rule |
| Retry | 2 attempts — Re-dispatch with the failing lessons |
| Escalation | after 2 consecutive failed attempts → Wei: The lessons that could not be evidenced |
| Human review | Rule changes are applied by Wei with `pdg memory apply` |
| Outcomes | pass |
| Provenance | learning-proposal.json; memory.md versions archived; rules-changelog.jsonl on apply |

**Instructions.** Write lessons, each with a scope (reusable | project_specific), an evidence class (verified | inferred | recommendation | missing), its evidence (defect ids, comparisons, feedback ids, ledger events) and, when it observes an existing rule, the rule id and whether the rule helped. Update memory.md: project-specific notes stay there. The deterministic hook writes learning-proposal.json; the rule base changes only when Wei runs `pdg memory apply`.

