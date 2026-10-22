# Prototype Production Graph (`pdg`)

[![Tests](https://github.com/veevia/prototype-production-graph/actions/workflows/test.yml/badge.svg)](https://github.com/veevia/prototype-production-graph/actions/workflows/test.yml)

**TL;DR:** Turn a product brief into a verified, working prototype. One declarative graph takes the brief through
evidence, problem framing, concepts, UX architecture and the build, then parallel reviews, targeted rework and human
release sign-off.

![Animated overview of the Prototype Production Graph. 19 steps in 8 phases build up from a brief to a verified prototype, then a tour lights each phase in turn: discovery and evidence, problem and product definition, concept, experience design, prototype and development, three parallel reviews, iteration, and delivery and learning. Defects return only to the step that made them, a named person approves at six human gates, including the release, and blocking problems escalate to that person.](docs/images/pdg-overview.gif)

## Why use `pdg`?

Frontier models can generate a plausible UI from a single prompt, but high-stakes product work still fails when models
invent missing requirements, skip edge states, misjudge browser layout or accessibility, or overwrite approved specs
during iteration.

`pdg` separates **generation** from **measurement** and **governance**:

- **Agents create; tools measure; people approve.** Agents work from self-contained file packets; deterministic checks
  and real-browser tests verify the output; named humans decide at six gates.
- **Evidence before pixels.** Sources and claims are tagged (`observed`, `reported`, `assumed`). Missing context is
  surfaced explicitly rather than fabricated (`N01`–`N05`), and ≥ 3 concepts are compared before converging (`N06`).
- **Real-browser verification, not prompt self-grading.** `N13` drives the built prototype in headless Chromium with
  `axe-core` across mobile, tablet and desktop viewports—checking WCAG contrast, 320 px reflow, target sizes, keyboard
  focus and every screen state. A reviewer agent cannot override a failed tool check.
- **Surgical rework, not start-over loops.** Feedback diagnosis (`N16`) traces each defect to the earliest node that
  caused it (`N03`–`N12`), and targeted rework (`N17`) re-runs only affected steps while keeping untouched work.
- **No lock-in or hosted service.** Runs locally with Python, Node and Chromium. Works with any coding assistant (GitHub
  Copilot, Claude Code, Cursor, or manual execution) with a resumable state and a SHA-256 hash-chained ledger.

### How `pdg` compares

`pdg` complements your existing design skills, MCP tools and coding assistants by adding the deterministic runtime and
product-design governance they leave out:

| Category | Common open-source approaches | Where they stop | What `pdg` adds |
|---|---|---|---|
| **UI & prototyping skills** | `frontend-design` skills, prompt packs, one-shot UI generators | Polish visual styling on a single pass, but invent missing requirements, skip edge/error states, and break working screens during edits. | **Evidence tags (`N01`–`N02`), ≥ 3 concepts (`N06`), full state specs (`N08`), and surgical root-cause rework (`N16`–`N17`).** |
| **Design-to-code bridges** | Figma MCP, screenshot-to-code, component libraries | Translate existing mockups into code, assuming the problem, flows and edge cases are already solved. | **Upstream product discovery (`N01`–`N07`)** plus **downstream usability & feasibility reviews (`N14`–`N15`)**. |
| **Spec-driven SDLC packs** | `spec-kit`, `hve-core`, `.instructions.md` collections | Rely on the LLM following Markdown instructions; jump straight from spec to code with no UX or browser verification harness. | **Hard Python state machine**, section-locked control docs, and **real Chromium + `axe-core` pre-checks (`N13`)** agents cannot override. |
| **Agent graph SDKs** | LangGraph, CrewAI, AutoGen | Provide low-level graph primitives, leaving you to build your own design stages, rubrics, browser checks and audit trail. | **Ready-to-run 19-node design graph**, 22 rubrics (98 dimensions), governed rule learning (`N19`), and a SHA-256 ledger. |

## How it works

A brief moves through **8 phases** and **19 nodes** defined in [`graph/workflow.yaml`](graph/workflow.yaml) and scored
by **22 rubrics**:

| Phase | Nodes | What happens |
|---|---|---|
| **1. Discovery & evidence** | `N01`–`N02` | Register sources with evidence tags, extract insights and riskiest assumptions, detect gaps, and freeze inputs. |
| **2. Problem & scope** | `N03`–`N05` | Define the problem frame (`N03` 👤), requirements (`N04`), and measurable scope & quality bar (`N05` 👤). |
| **3. Concept** | `N06` | Compare ≥ 3 distinct concepts against weighted criteria and lock the chosen direction (`N06` 👤). |
| **4. Experience design** | `N07`–`N09` | Map journeys and flows (`N07`), specify interaction states (`N08`) in parallel with visual tokens (`N09` 👤). |
| **5. Prototype & build** | `N10`–`N12` | Approve the fidelity and test plan (`N10` 👤), build the offline prototype (`N11`), and wire realistic data (`N12`). |
| **6. Parallel validation** | `N13`–`N15` | Run three reviews in parallel: Chromium + `axe-core` quality (`N13`), usability validation (`N14`), and feasibility (`N15`). |
| **7. Targeted iteration** | `N16`–`N17` | Diagnose findings into traced defects (`N16`) and reopen only the originating nodes (`N17`) within bounded budgets. |
| **8. Delivery & learning** | `N18`–`N19` | Recompute release checks for human sign-off (`N18` 👤) and propose reusable lessons for the rule base (`N19`). |

## Quick onboarding

### 1. Install and run the demo

Requires **Python 3.11+**, **Node.js 22+**, and Chromium via Playwright.

```bash
git clone https://github.com/veevia/prototype-production-graph.git
cd prototype-production-graph
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints.txt
python -m playwright install chromium

python -m pdg validate                                # verify the workflow graph
python -m pdg docs --check                            # verify generated docs and schemas
python -m pdg dry-run --out /tmp/pdg-demo             # run the fictional example end to end (~3 min)
python -m pdg ledger-verify /tmp/pdg-demo             # verify the hash-chained ledger
python -m pdg report /tmp/pdg-demo                    # write the HTML run report
```

The dry run builds the fictional *Lot Release Workbench* ([`examples/coa-review/`](examples/coa-review/README.md)): its
first build intentionally fails review, reworks only the affected nodes, and passes on the next build.

### 2. Run on your own project

1. **Initialize a project** and configure your brief and approver:

   ```bash
   python -m pdg init ../my-prototype --name "My prototype"
   ```

   Put your brief in `../my-prototype/sources/brief.md`, add supporting sources under `sources/`, and set
   `humans: [Your Name]` in `../my-prototype/pdg.project.yaml`.

2. **Advance the workflow** until it waits for an agent (`WAITING_AGENT`), a human gate (`WAITING_HUMAN`), or an
   escalation (`BLOCKED`):

   ```bash
   python -m pdg run ../my-prototype
   python -m pdg status ../my-prototype
   python -m pdg tasks ../my-prototype
   ```

3. **Complete the active step** and continue:
   - **Agent task (`WAITING_AGENT`):** hand the packet in `.pdg/tasks/` to your coding assistant (or complete it
     yourself), write the declared outputs, and run the packet's submit command (use `--dry-run` to pre-check):
     ```bash
     python -m pdg submit ../my-prototype <node> --token <token> --actor agent:<agent> --output <key>=<path>
     ```
   - **Human gate (`WAITING_HUMAN`):** record the named approver's decision (or `--reject --feedback "…"`):
     ```bash
     python -m pdg approve ../my-prototype <node> --actor "<your name>" --reason "<decision>"
     ```
   - **Escalation (`BLOCKED`):** inspect `.pdg/escalations/`, resolve the blocker, and unblock:
     ```bash
     python -m pdg unblock ../my-prototype <node> --actor "<your name>" --note "<what was fixed>"
     ```

## Repository structure & docs

| Path | Purpose | Guide |
|---|---|---|
| `graph/workflow.yaml` | Single declarative authority for nodes, edges and policies | [Graph spec](docs/graph-spec.md) · [Diagram](docs/graph.svg) |
| `pdg/` | Deterministic engine, CLI, state, control locks, ledger and tools | [Architecture](docs/architecture.md) · [Orchestration](docs/orchestration.md) · [State model](docs/state-model.md) |
| `rubrics/`, `config/`, `schemas/` | 22 quality rubrics, thresholds, and JSON schemas | [Evaluation & gates](docs/evaluation-and-gates.md) · [Rubric catalog](docs/rubric-catalog.md) |
| `templates/control/`, `templates/artifacts/` | Eight shared control documents with section ownership and locks | [Control documents](docs/control-documents.md) · [Control access](docs/control-access.md) |
| `agents/`, `prompts/` | 13 role cards and 19 node task instructions | [Node catalog](docs/node-catalog.md) · [Edge catalog](docs/edge-catalog.md) · [Agent catalog](docs/agent-catalog.md) |
| `knowledge/`, `scoring/` | Governed design rules (`rules.json`) and candidate preference scorer | [Self-improvement](docs/self-improvement.md) · [Design principles](knowledge/design-principles.md) |
| `examples/coa-review/` | End-to-end fictional workbench, fixtures and expected outputs | [Example guide](examples/coa-review/README.md) · [Dependencies](docs/dependencies.md) |

## Non-goals and boundaries

- **Not a hosted service, model provider or UI generator.** `pdg` governs and verifies the workflow locally.
- **Automated checks complement, not replace, real user research.** Browser checks and simulated dry-run sessions do not
  substitute for testing with real users or production security review.
- **License:** MIT for project code; MPL-2.0 for vendored `axe-core`. See [LICENSE](LICENSE),
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

