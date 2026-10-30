# Distribution defaults

These generic checks are distribution defaults, not recorded human approvals or project evidence.
Review the checks for each project and configure named approvers in its project file.
Human confirmations are recorded only by an explicit authorized memory action.

Defaults awaiting project review: 63.

| Rule | Check |
|---|---|
| R-CBV-001 | Before design starts, state the job, the primary persona and the top pain in one sentence each, with evidence. |
| R-EVD-001 | Register every source with an evidence tag (observed · reported · assumed); never invent a source, quote or participant. |
| R-EVD-002 | Every product decision traces to evidence or to a named assumption. |
| R-EVD-003 | Make assumptions explicit with importance and certainty, and flag the riskiest before anything is built. |
| R-EVD-004 | Declare missing information; never fill a gap with invention. |
| R-SCP-001 | Change only what the request or the defect scopes: refine, don't redesign, and re-open only the nodes a defect traces to. |
| R-SCP-002 | Scope is signed 🟢 before build; every open 🟡 carries a trigger, an expiry and an owner. |
| R-SCP-003 | Non-goals and out-of-scope lists are never empty. |
| R-SCP-004 | Rollback triggers name a measurable condition, never 'if things go bad'. |
| R-SCP-005 | Success criteria are numbers, not adjectives, with one north-star metric. |
| R-SCP-006 | Unbuilt capability is visibly marked in the UI, never silently omitted or faked (drafts are never 'sent'). |
| R-SCP-007 | Every P0 requirement has acceptance criteria a reviewer can check. |
| R-SCP-008 | Requirements cover user, business and technical needs. |
| R-SCP-009 | Document the constraints (technical, business, regulatory, time) before design starts. |
| R-STR-001 | Compare at least three distinct concepts before converging. |
| R-STR-002 | Make the concept choice defensible: weighted criteria traced to requirements, and an explained override. |
| R-STR-003 | Every concept names its riskiest assumption. |
| R-IA-001 | When sources serve different business units, unify the shell and the components, not their domain workflows. |
| R-IA-002 | Every P0 requirement is covered by a complete, executable user flow. |
| R-IA-003 | Every screen is reachable, with one name and one route. |
| R-UX-001 | Decision-driving values show their derivation on screen. |
| R-UX-002 | Specify and build every state: success, empty (with a way back), error, and the domain's own. |
| R-UX-003 | A locked action says what unlocks it. |
| R-VIS-001 | Optimise for component consistency and usability: one type scale (≤ 8 sizes), one radius set (≤ 5), one focus ring, consistent status colours. |
| R-VIS-002 | Off-system values are defects: every colour comes from a design-system token with provenance. |
| R-VIS-004 | The design system names its prohibited patterns. |
| R-VIS-005 | Each colour carries one meaning: the alert colour is reserved for alerts, and status is never colour alone. |
| R-VIS-007 | Clear hierarchy: one focal point and one primary action per screen. |
| R-VIS-008 | Comparison and audit tasks use tables and compact rows, not decorative cards. |
| R-A11Y-001 | Accessibility is a binary gate: zero axe violations (WCAG 2.0/2.1/2.2 A and AA) on every screen and state. |
| R-A11Y-002 | Every declared colour pair meets WCAG contrast: 4.5:1 for text, 3:1 for large text and UI. |
| R-A11Y-003 | Everything is keyboard operable, with a visible and unobscured focus indicator. |
| R-A11Y-004 | No horizontal overflow from 320 px to desktop: content reflows. |
| R-A11Y-005 | Pointer targets are at least 24 × 24 px (WCAG 2.2 AA). |
| R-A11Y-007 | Rendered text is at least 12 px and does not clip under WCAG text spacing. |
| R-A11Y-008 | Names, headings and landmarks make sense to a screen-reader user; automated checks catch only part of this. |
| R-A11Y-009 | Reduced-motion preferences are honoured. |
| R-FID-001 | Fidelity rises only with validated riskiest assumptions and customer alignment. |
| R-FID-002 | Synthetic, invented and missing data is visible as such at the point of decision. |
| R-FID-003 | No placeholder text: realistic, product-specific copy. |
| R-FID-005 | Data exercises every mechanism the scenarios depend on (out-of-range, missing and borderline values). |
| R-FID-006 | Product-specific, not generic: the domain's own vocabulary, meaningful workflows, contextual relevance. |
| R-FUN-001 | A polished prototype is incomplete unless its primary workflows run end to end in a real browser. |
| R-TEC-002 | The prototype runs offline from one self-contained file, with no network requests. |
| R-TEC-003 | Code parses, and domain logic is unit-tested. |
| R-TEC-005 | No console errors or uncaught exceptions. |
| R-TEC-008 | development.md defines architecture, technology, components, data and APIs, folder structure, standards and testing. |
| R-TEC-009 | Name every mocked seam and what production needs; never present a prototype as production-ready. |
| R-VAL-001 | Validate with real users and stakeholders before raising fidelity or releasing. |
| R-VAL-002 | Every P0 flow has an executable scenario that ends in an expectation. |
| R-VAL-003 | Primary tasks meet a planned, task-level success threshold. |
| R-VAL-005 | Validation findings trace to the flows and requirements they implicate. |
| R-GOV-001 | Never stop after one round: keep build → review → fix running until every gate passes or a genuine blocker is reported. |
| R-GOV-003 | Humans own the commitments: problem, scope, concept, visual system, fidelity and release are named human decisions. |
| R-GOV-004 | Simulated input and non-human approvals are labelled and never presented as evidence. |
| R-GOV-005 | Trace every defect to the responsible node, with the smallest fix and an acceptance check. |
| R-GOV-006 | Interpret every piece of feedback: map it to defects or dismiss it with a reason. |
| R-GOV-007 | Escalate repeated failures instead of looping: three failed corrections or a spent budget stop the run. |
| R-GOV-008 | Release only when every gate passes on the current version, recomputed from disk. |
| R-GOV-009 | Package deliveries with a hashed manifest and their evidence. |
| R-LRN-001 | Lessons carry evidence; defaults change only with evidence. |
| R-LRN-002 | Keep project-specific observations apart from reusable knowledge. |
| R-LRN-003 | Learning never modifies approved product truth, requirements, evidence or design principles. |
