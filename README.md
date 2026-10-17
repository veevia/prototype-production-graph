# Prototype Production Graph (pdg)

[![Tests](https://github.com/veevia/prototype-production-graph/actions/workflows/test.yml/badge.svg)](https://github.com/veevia/prototype-production-graph/actions/workflows/test.yml)

**TL;DR:** Turn a product brief into a verified, working prototype. One YAML graph takes the brief through evidence,
definition, concepts, experience design and the build, then parallel reviews, targeted rework and a human release.

![The Prototype Production Graph: 19 steps in 8 phases. A brief moves through discovery and evidence, problem and product definition, concept, experience design, and prototype and development; three reviews judge each build in parallel; defects return only to the step that made them; a named person approves at six human gates, including the release, and blocking problems escalate to that person.](docs/images/pdg-overview.png)

- **One graph drives the work.** 19 nodes, 43 edges and 8 subgraphs in [`graph/workflow.yaml`](graph/workflow.yaml)
  define every step, review and rework path, and 22 rubrics define when each one is done.
- **Agents create; tools measure; people approve.** Your coding assistant, or you, works from file-based task packets;
  deterministic checks, including real-browser tests of the prototype, measure the result; named people decide.
- **Resumable and auditable:** checkpoints, artifact lineage and a hash-chained ledger record every step and decision.
- **No hosted service required.** pdg needs no LLM API, cloud service, Microsoft account or the author's workspace.

> The fictional example proves the workflow mechanics, not design quality, real user research or production
> readiness. See [non-goals and limitations](#non-goals-and-limitations).

## How it works

A brief moves through eight phases: discovery and evidence, problem and product definition, concept, experience
design, prototype and development, validation, iteration, and delivery and learning.

- **Three reviews judge every build in parallel** once content and data are in (N12): the functional, design and
  accessibility review (N13), which drives the prototype in real Chromium with axe-core; user and stakeholder
  validation (N14); and technical feasibility (N15).
- **Defects go back only to the step that made them.** Feedback diagnosis (N16) traces each defect to its source, and
  targeted rework (N17) reopens only those steps, anywhere from the problem frame (N03) to content and data (N12).
  Everything else is kept.
- **People approve at six human gates:** the problem frame (N03), the scope and quality bar (N05), the concept (N06),
  the visual system (N09), the prototype plan and fidelity (N10), and the release (N18), where they can instead request
  changes.
- **Every loop is bounded.** Rejections, retries and rework cycles have budgets (at most four rework cycles by default).
  A spent budget stops the run with an escalation report instead of looping silently.
- **Blocking problems escalate to a named human.** Blocking evidence gaps (N02), a diagnosis that cannot proceed (N16)
  and a defect with no step to return to (N17) stop the run and write a report to `.pdg/escalations/`.
- **Every run ends by learning.** N19 proposes reusable lessons; they reach the shared rule base only when a person
  applies them.

The diagram is an overview. The [graph specification](docs/graph-spec.md) and the generated
[graph diagram](docs/graph.svg) are rebuilt from the YAML and checked in CI.

## Install and verify

You need Python **3.11+**, Node.js **22+** and Chromium installed through Playwright. Installing Chromium needs network
access once; everything else runs locally.

```bash
git clone https://github.com/veevia/prototype-production-graph.git
cd prototype-production-graph
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -c constraints.txt   # the exact versions CI verifies
python -m playwright install chromium

python -m pdg validate                                # check the workflow graph
python -m pdg docs --check                            # confirm the generated docs match the graph
python -m pdg dry-run --out /tmp/pdg-community-demo   # run the fictional example end to end (about 3 minutes)
python -m pdg ledger-verify /tmp/pdg-community-demo   # check the run's hash-chained ledger
python -m pdg report /tmp/pdg-community-demo          # write an HTML run report
```

The dry run builds the fictional Lot Release Workbench with scripted agents. Its first build intentionally fails review;
only the affected steps are reworked, and build v2 passes. Dry-run approvals are labelled `dry-run-auto`, and simulated
sessions are not real user research. Use a new output directory each time you repeat it.

Run commands from this checkout: it is a source checkout, not a published package. The full regression suite
(`python -m pytest -q`) drives real Chromium and takes about 40 minutes; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Use it on your own project

1. **Create a project.**

   ```bash
   python -m pdg init ../my-prototype --name "My prototype"
   ```

   Paste the requester's brief, verbatim, into `sources/brief.md`, and add authorized sources such as research,
   analytics or your design system. Then set `humans: [Your Name]` in `pdg.project.yaml`: the human gates accept
   decisions only from the people listed there.

2. **Run until the graph stops** for an agent (`WAITING_AGENT`), a human (`WAITING_HUMAN`) or an escalation
   (`BLOCKED`), or until the prototype passes (`RUN_PASS`).

   ```bash
   python -m pdg run ../my-prototype
   python -m pdg status ../my-prototype   # node states, waits and escalations
   python -m pdg tasks ../my-prototype    # open task packets
   ```

3. **Resolve the stop.** `submit` and `approve` record the result and continue the run.
   - `WAITING_AGENT`: give each task packet in `.pdg/tasks/` to your coding assistant, or do the work yourself. Write
     the declared outputs, then run the submit command printed in the packet, which carries its dispatch token. Add
     `--dry-run` to check the outputs without using an attempt.
   - `WAITING_HUMAN`: the named approver decides. Record their actual decision, adding `--reject` to send the work
     back; never invent an approval.
   - `BLOCKED`: read the report in `.pdg/escalations/` and fix the cause; then a named human unblocks the node.

   ```bash
   python -m pdg submit ../my-prototype <node> --token <token> --actor agent:<agent> --output <key>=<path>
   python -m pdg approve ../my-prototype <node> --actor "<your name>" --reason "<their decision>"
   python -m pdg unblock ../my-prototype <node> --actor "<your name>" --note "<what was fixed>"
   ```

4. **Before handoff, verify the ledger** and review the run report.

   ```bash
   python -m pdg ledger-verify ../my-prototype
   python -m pdg report ../my-prototype
   ```

Run `run` again after an interruption; the engine resumes from its saved state. No standing delegation is inherited
from the author's workspace: release, publication, risk acceptance and rule changes each need their own explicit
authorization. After a pdg upgrade, `pdg status` reports changed engine code or rule fingerprints; inspect it and run
`pdg recheck-release` rather than bypassing the checks.

The role cards use **Wei** as the example principal. Your `humans` setting names your own approvers; a name is not
authentication, and pdg is a trusted local workflow, not a sandbox for hostile agents.

## Project map

| Directory | Purpose |
|---|---|
| `graph/` | The workflow definition, the single graph authority |
| `pdg/` | Engine, CLI, state, provenance, deterministic checks, reports and privacy-policy selection |
| `agents/`, `prompts/` | 13 role cards and 19 node instructions |
| `rubrics/`, `config/`, `schemas/` | 22 quality rubrics, thresholds, and artifact and state contracts |
| `templates/control/`, `templates/artifacts/` | Eight shared control documents and the artifact templates they reference |
| `knowledge/` | The public quality-rule profile; no customer case studies or personal preferences |
| `examples/coa-review/` | Fictional sources, prototype, fixtures and expected outputs |
| `scoring/` | Bundled dependency-free candidate scoring tool and its tests |
| `vendor/axe-core/` | Offline accessibility checker, with its MPL-2.0 license |
| `tests/`, `.github/workflows/` | Regression suite and GitHub Actions checks |
| `docs/` | Architecture, catalogs, evaluation, state and learning guides |

## Documentation

| Guide | Covers |
|---|---|
| [Architecture](docs/architecture.md) | How the declarative graph drives the deterministic engine |
| [Graph specification](docs/graph-spec.md) | Node, edge and subgraph fields and the validator's rules, with the [generated diagram](docs/graph.svg) |
| [Node catalog](docs/node-catalog.md) and [edge catalog](docs/edge-catalog.md) | Every node and edge, generated from the graph |
| [Agent catalog](docs/agent-catalog.md) | The 13 agent roles and the nodes they own or support |
| [Orchestration](docs/orchestration.md) | How the engine schedules and batches ready nodes |
| [Evaluation and gates](docs/evaluation-and-gates.md) | Rubrics, tool and review checks, and the human gates |
| [Rubric catalog](docs/rubric-catalog.md) | Every rubric dimension and when it blocks |
| [Control documents](docs/control-documents.md) and [control access](docs/control-access.md) | The eight documents people read and sign, and who may change each section |
| [State model](docs/state-model.md) | Typed state, checkpoints and resumability |
| [Self-improvement](docs/self-improvement.md) | Learning proposals and the governed rule base |
| [Dependencies](docs/dependencies.md) | Runtime requirements, the source closure and optional host skills |
| [Evidence in the public distribution](docs/previous-iterations.md) | What the public rule profile's evidence is, and what is withheld |
| [Graph engineering and tools](docs/research/graph-engineering-and-tools.md) | The graph model and tools the engine is built on |

## Agents, skills and integrations

The graph names 74 skill labels and optional host tools. They guide whoever executes a packet; they are not Python
imports or services that pdg installs. Each packet carries the node's instructions, inputs, schemas, rubrics and submit
command, so you can do the work yourself or map the role cards to your own assistant. WorkIQ, wiki retrieval, Figma,
MCP tools and the author's custom agents are optional; use authorized local sources and your own design system instead.

## What is not included

No proprietary skill collection, Microsoft credentials, customer hub, runtime session, private transcript, private Git
history or personal scoring model is included. The sample privacy vocabulary is fictional: configure your own
identifiers locally before recording sensitive review data. Static identifier checks are not a privacy guarantee.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) for the checks, the contribution boundaries and how updates flow from the
author's workspace to this repository.

## Non-goals and limitations

- Not a design generator, agent host, model provider, authentication service or production backend.
- Browser checks and rubric scores do not substitute for real usability research or production readiness.
- Do not publish project sources, ledgers, reviews or credentials with contributions.

Original project code is MIT-licensed; vendored axe-core keeps its MPL-2.0 license.
See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
