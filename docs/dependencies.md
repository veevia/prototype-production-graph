# Dependency inventory

**TL;DR:** The engine needs Python, Node and Chromium; host skills and enterprise integrations are optional.

## Runtime and tests

Python 3.11+, pydantic, PyYAML, jsonschema and Playwright; pytest for tests. Minimum versions are in `requirements.txt`; `constraints.txt` pins the exact versions CI verifies, because a new Playwright brings a new Chromium that can change browser verdicts. Node.js 22+ runs prototype unit tests. Chromium is installed with `python -m playwright install chromium`. axe-core and its license are bundled. The candidate scorer and its tests are included.

## Source closure

Graph, defaults, rubrics, schemas, role cards, node prompts, eight control templates, their referenced artifact templates, the generic rule profile, the generated technical fixture and regression tests are included. No runtime import reaches outside this repository.

## Optional host capabilities

The graph names 70 skill labels below. These are agent guidance, not installed Python dependencies. Use each packet's instructions and rubrics manually or map these labels to your assistant's own skills. Role cards name no runtime agent bindings; configure your own. Meeting and document grounding, document conversion, Figma and other MCP integrations are optional source-acquisition tools. They require their own authorization and are not bundled.

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

## Publication boundary

Project-specific content (sources, datasets, evidence, approvals, preferences and runs) is never part of this distribution. The technical fixture is generated at run time and is not project evidence. Public evidence entries are rule recommendations, not customer evidence, and distribution defaults are not approvals by a project's principal.
