# Research: graph engineering and tools for the prototype design workflow

> **TL;DR:** The engine uses a researched graph model: a Pregel-style superstep graph with typed state,
> bounded loops, checkpoints and human interrupts. Evidence comes from real measurement (Playwright + axe-core),
> usability metrics come from published methods, and simulated input is always labelled. Every tool below carries a
> citation or a local observation from this machine.

**Provenance.** Graph-engineering concepts are source-verified against
[LangGraph's architecture reference](https://docs.langchain.com/oss/python/langgraph/overview) and 40+ cited sources.
The tooling and usability rows come from source-verified documentation and local execution benchmarks. Evidence tags:
cited documentation = *reported*; local runs = *observed*; the mapping to nodes = *workflow binding*.

## 1. Graph-engineering choices

| Concept | Choice in `pdg` | Basis |
|---|---|---|
| Directed graph with cycles vs DAG | Flow edges form a DAG; rework and rejection are separate, bounded **loop** edges | LangGraph Pregel BSP; Dagster lineage DAG |
| Supersteps | Parallel execution, then serial judge-and-commit in topological order | Pregel / LangGraph super-steps |
| Shared typed state + reducers | pydantic `ProjectState`; append-only reducer paths batch without conflict | LangGraph state reducers (`Annotated[T, reducer]`) |
| Conditional routing | Edges fire on declared outcomes and `target:<node>` | LangGraph `add_conditional_edges`, `Command(goto=)` |
| Checkpoints, resume, time travel | Snapshot per pass, failure, human wait and escalation; crash resume; `rollback` | LangGraph checkpointers keyed by thread; checkpoint per super-step (docs.langchain.com/oss/python/langgraph/persistence) |
| Human interrupts | `WAITING_HUMAN` gates resumed by `pdg approve` (mirrors `interrupt()` + `Command(resume=…)`) | docs.langchain.com/oss/python/langgraph/interrupts |
| Fan-out / fan-in | n08 ∥ n09 and n13 ∥ n14 ∥ n15, with join = all | `Send(node, arg)` map-reduce (reference.langchain.com/python/langgraph/types/Send) |
| Retry policy | Per-node `retry.max_attempts`, retry context in the next packet, escalation when spent | LangGraph `RetryPolicy(max_attempts=3, …)` (docs.langchain.com/oss/python/langgraph/fault-tolerance) |
| Content-addressed caching | Input fingerprints by content; memo restore; artifacts keyed by sha256 | Bazel action graph; Dagster assets |
| Workflow patterns | Prompt chaining (definition), parallelisation (validation), orchestrator-workers (diagnosis → rework), evaluator-optimizer (gate loop) | Anthropic, "Building Effective Agents" (anthropic.com/engineering/building-effective-agents) |
| Context discipline | Task packets carry the smallest high-signal context: inputs by reference | Anthropic, "Effective context engineering for AI agents" (anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| Spec-driven order | Constitution (rules) → specify (product) → plan (prototype.md) → tasks (packets) → implement → converge (gate) | GitHub Spec Kit (github.com/github/spec-kit) |

**Not adopted as a dependency:** LangGraph, Burr, CrewAI Flows and Semantic Kernel Process. None provides evaluation
nodes or governed learning, which are the two things this workflow most needs. A standalone engine keeps the package
runnable with Python and Node alone ([architecture notes](../../CONTRIBUTING.md#architecture)).

## 2. Tools bound to nodes

| Tool | Node(s) | Verified capability | Source |
|---|---|---|---|
| Playwright Chromium through `pdg.tools.browser:check` | n13 | Viewport emulation; `page.on("console")` and `pageerror`; request monitoring for offline checks; keyboard events; full-page screenshots; `emulate_media(reduced_motion="reduce")` | playwright.dev/python/docs/emulation, /api/class-consolemessage, /network, /api/class-keyboard, /screenshots, /api/class-page · *observed:* with the pinned Playwright, the suite runs 4 scenarios × 3 viewports in about 15 s |
| axe-core 4.11.4 (vendored) | n13 | Tags `wcag2a` `wcag2aa` `wcag21a` `wcag21aa` `wcag22aa`; `runOnly` by tag; finds about 57% of WCAG issues automatically; MPL-2.0 | github.com/dequelabs/axe-core (doc/API.md, README, LICENSE); deque.com/blog/automated-testing-study-identifies-57-percent-of-digital-accessibility-issues · *observed:* reports `color-contrast` on the draft build and 0 violations on the corrected build (`tests/test_browser.py`) |
| Full-page screenshots per screen, state and viewport | n13 | `page.screenshot(full_page=True)` | playwright.dev/python/docs/screenshots · *observed:* written to `work/n13_quality_review/a<n>/screenshots/` |
| `pdg.tools.design_system:check` | n09 | WCAG 1.4.3 contrast ≥ 4.5:1 (3:1 large text) for every declared pair; ≤ 8 type sizes and ≤ 5 radii | w3.org/TR/WCAG22/#contrast-minimum · *observed:* `test_wcag_contrast_matches_known_values` |
| Browser thresholds (in `browser:check`) | n13 | Reflow at 320 px (1.4.10 AA); targets ≥ 24 px (2.5.8 AA, enforced) and ≥ 44 px (2.5.5 AAA, advisory); visible focus (2.4.7 AA) | w3.org/TR/WCAG22/#reflow, #target-size-minimum; w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html, focus-visible.html |
| `node --check` and `node --test` (Node 22) | n11, n15 | Syntax check; the built-in test runner | *observed:* Node 22; the technical fixture's domain tests pass (`tests/test_prototype_unit.py`) |
| Python build script; seeded synthetic-data generator | n11, n12 | A deterministic single-file offline build with `build-manifest.json`; seeded data | *observed:* two builds are byte-identical (`test_the_build_is_reproducible`) |
| `pdg.tools.validation:prepare` and `validation:check` | n14 | Task success rate ("the bottom line of usability"), time on task, SEQ (7-point post-task item); 5 participants find about 85% of problems in a round | nngroup.com/articles/success-rate-the-simplest-usability-metric/; measuringu.com/seq-prediction/; nngroup.com/articles/why-you-only-need-to-test-with-5-users/ |
| Document-to-Markdown converter (optional MCP server) | n01 | Converts documents to Markdown for registration as sources | project-configured; not bundled |
| Read-only meeting and document connector (optional MCP server) | n01 | Brings authorized meetings, mail and files into the project's sources | project-configured; not bundled |
| Local file search | n01 | Registers files in `sources/` | *observed:* standard shell tools |
| Deterministic `pdg.tools.*` checks (evidence, product, concepts, experience, plan, prototype, content, feasibility, diagnosis, regen, release, learning) | n02–n19 | Schema validation, counts, hashes and recomputation from state and disk | *observed:* `tests/test_tools.py`, `tests/test_engine.py`, and the dry run |

**Considered, not bound:** Lighthouse (accessibility score is an axe-derived subset; developer.chrome.com/docs/lighthouse/overview),
chrome-devtools-mcp `lighthouse_audit` (excludes performance; github.com/ChromeDevTools/chrome-devtools-mcp),
Storybook a11y and interaction tests (single-component scope; storybook.js.org/docs/writing-tests/accessibility-testing),
and the Figma MCP server (`get_design_context`, `get_screenshot`; developers.figma.com/docs/figma-mcp-server/tools-and-prompts/).
Any of them can be bound to n09 or n13 later: a tool binding is a graph edit plus a rubric dimension.

## 3. Limits of the evidence

- axe-core finds about 57% of issues **by volume**. Keyboard behaviour beyond focus visibility, screen-reader output and
  cognitive load need human review, which is why `design-quality` has review and human dimensions.
- Viewport emulation is not device testing: it sets user agent, viewport and touch, not device GPU or sensors.
- Simulated validation (the dry run) exercises the pipeline, not the product. Success rates from simulated sessions
  are never evidence.

**Unverified (from the research pass):** Brooke's original 1996 SUS chapter (the "68 average" rests on MeasuringU's
secondary analysis); whether any axe-core rule carries a `wcag22aaa` tag; an independent source for the "20–30%" prior
belief that Deque's 57% is contrasted with; the exact deprecation date of Figma's original MCP tool names; whether a
locally installed chrome-devtools-mcp matches the upstream tool reference.
