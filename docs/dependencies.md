# Dependency inventory

**TL;DR:** The engine needs Python, Node and Chromium; host skills and enterprise integrations are optional.

## Runtime and tests

Python 3.11+, pydantic, PyYAML, jsonschema and Playwright; pytest for tests. Exact minimum constraints are in `requirements.txt`. Node.js 22+ runs prototype unit tests. Chromium is installed with `python -m playwright install chromium`. axe-core and its license are bundled. The candidate scorer and its tests are copied, not imported from a sibling checkout.

## Source closure

Graph, defaults, rubrics, schemas, role cards, node prompts, eight control templates, their referenced artifact templates, public rule profile, fictional example and regression tests are included. No runtime Python import reaches into Wei_workspace. Kernel comparisons with the author's video workflow and private provenance checks explicitly skip when those optional sources are absent.

## Optional host capabilities

The graph names 74 skill labels below. These are agent guidance, not installed Python dependencies. Use each packet's instructions and rubrics manually or map these labels to your assistant's own skills. The role cards' runtime bindings are examples, not agents launched by the engine. WorkIQ/M365 grounding, wiki retrieval, document conversion, Figma and other MCP integrations are optional source-acquisition tools. They require their own authorization and are not bundled.

- `accessibility-verification`
- `affinity-map`
- `asset-collection`
- `assumption-mapping`
- `code-review-and-quality`
- `code-simplification`
- `competitive-landscape`
- `concept-creator`
- `constraint-mapping`
- `content-designer`
- `content-writing`
- `context-intake`
- `context-pull`
- `crazy-8s`
- `debugging-and-error-recovery`
- `decision-capture`
- `decision-matrix`
- `design-criteria`
- `design-decision-articulator`
- `design-pov-author`
- `design-review`
- `design-system-as-infrastructure`
- `design-system-author`
- `desirability-testing`
- `documentation-and-adrs`
- `drift-check`
- `evidence-tagging`
- `experiment-planner`
- `extreme-clarity`
- `feedback-collector`
- `fishbone-diagram`
- `five-whys`
- `frontend-design`
- `heuristic-evaluation`
- `hitl-boundary-designer`
- `how-might-we`
- `hypothesis-creator`
- `impeccable`
- `information-architecture-designer`
- `interview-debrief`
- `jobs-to-be-done`
- `known-unknown-mapper`
- `mve-mvp-planner`
- `observability-and-instrumentation`
- `pathfinder-prioritizer`
- `performance-optimization`
- `poc-planner`
- `prd-author`
- `problem-framing`
- `problem-statement-builder`
- `prototype-qa`
- `prototype-review`
- `prototyping-assist`
- `prototyping-principles`
- `research-synthesis`
- `rose-bud-thorn`
- `rubric-authoring`
- `security-and-hardening`
- `shipping-and-launch`
- `skill-creator`
- `spec-driven-development`
- `storyboard`
- `success-metrics`
- `terminology-taxonomy-designer`
- `test-driven-development`
- `traffic-light-decisions`
- `usability-metrics`
- `user-journey-map`
- `uxr-feedback-assist`
- `web-artifacts-builder`
- `webapp-testing`
- `wiki-ingest`
- `wiki-query`
- `workiq-grounding`

## Publication boundary

Excluded: customer case studies, private citations and quotations, prior rule snapshots, personal preference decisions/models, run directories, workspace SOPs containing standing grants, the historical build-loop reviewer and private Git history. Public evidence entries are rule recommendations, not customer evidence. Published rules retain author confirmation status, not approval by a new project's principal.
