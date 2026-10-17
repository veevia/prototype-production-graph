# Graph specification

> **TL;DR:** `graph/workflow.yaml` is the only place the workflow is defined: 19 nodes, 43 edges (23 flow, 17 loop,
> 3 escalate) and 8 subgraphs. The validator enforces 14 structural rules, and the engine refuses to run a graph that
> fails any of them.

## File layout

```yaml
id: prototype-design
version: "1.0.0"          # bump on any change; preserved copies live in graph/history/
start: START
end: END
policies: {…}             # budgets, parallelism, humans, blocking severities, rework targets
subgraphs: [{id, name, pattern, purpose, nodes}]
nodes: [{…}]              # in lifecycle order
edges: [{…}]
```

## Node fields

Every node defines every field below. `pdg validate` fails on an empty one.

| Field | Meaning |
|---|---|
| `id` · `num` · `name` · `lifecycle_step` | Identity; `lifecycle_step` maps the node to the brief's 19 steps, in order |
| `phase` · `stage` · `subgraph` | Understand/Design/Build/Learn; the brief's 8 stages; the subgraph |
| `kind` | `agent`, `review`, `gate` or `tool` ([architecture](architecture.md#node-kinds)) |
| `purpose` · `instructions` · `prompt` | What the node is for; what the agent must do; the prompt file |
| `depends_on` | Flow predecessors. The validator checks it equals the incoming flow edges |
| `inputs` | Fingerprinted refs: `state:<path>`, `artifact:<key>`, `control:<doc>`, `files:<glob>`, `feedback:open`, `defects:open`, `rework:self` |
| `context` | What the agent should know that is not an input (the case-study lessons live here) |
| `state_read` · `state_write` | Permission: a node commits only its declared `state_write` paths |
| `outputs` | `{key, kind, schema?, required?, description}`. Schema-bound JSON outputs are validated before commit |
| `agent` · `support_agents` · `skills` · `tools` | Who does the work, with which workspace skills (checked against `03_Agents-and-Skills/INDEX.md`) and tools |
| `completion` | Checks that must hold before the node passes (artifact valid, interpretation complete, …) |
| `evaluation` | Rubric ids. Every tool dimension's check must be run by this node (completion or `run.tool`) |
| `retry` · `escalation` · `failure_conditions` | Attempt budget and retry behaviour; who is told, when, with what report |
| `human_review` | `required: true` makes the node a human gate; `decision` says what is decided |
| `provenance` | What the node leaves behind for audit |
| `controls` | `read`, `write`, `lock_on_approval`, and `sections` (owned sections of a shared document) |
| `outcomes` · `run` · `gate` | Declared outcomes; the tool or hook the engine runs; the gate hook |

## Edge fields

| Field | Meaning |
|---|---|
| `id` · `from` · `to` | `to` may be `END` or `@escalate` |
| `kind` | `flow` (forward, part of the DAG) · `loop` (back to an upstream node, bounded) · `escalate` (stop and report) |
| `transition` · `when` | `deterministic` edges fire on `*`. `conditional` edges fire on an outcome (`approved`, `rework`, …) or a rework target (`target:<node>`) |
| `max_traversals` | Required on loops: the budget after which the source escalates instead |
| `transfers` · `threshold` · `behavior` | What crosses the edge, the condition in words, and what happens |

## Validator guarantees

`pdg validate` (and every engine start) rejects a graph that:

1. has a cycle among flow edges;
2. has a loop edge without `max_traversals`, or one that does not return upstream;
3. has a node unreachable from START, or one that cannot reach END;
4. declares an outcome that no outgoing edge handles (a dead end);
5. can deadlock a join (a join whose predecessors are on mutually exclusive branches);
6. puts conditions on a deterministic edge, or locks a document at a node that is not a human gate;
7. has a `depends_on` that differs from the incoming flow edges, or an empty required field;
8. references an unknown agent, prompt, rubric, schema or state path;
9. binds a rubric tool dimension to a check the node never runs;
10. writes state outside `state_write`, or a control document outside `controls.write`;
11. shares a control document without every writer owning named sections;
12. lets two writers own the same section, names a section the template lacks, or leaves a heading unowned;
13. maps the 19 nodes out of the brief's lifecycle order;
14. (workspace check) names a skill that `03_Agents-and-Skills/INDEX.md` does not list.

Each rule has a seeded-violation test in `tests/test_graph.py`.

## Nodes

<!-- NODES:START -->
| N | Node | Kind | Phase · stage | Subgraph | Human gate | Loops back to |
|---|---|---|---|---|---|---|
| 01 | `n01_context_intake` — Context intake | agent | Understand · Context | discovery | — |  |
| 02 | `n02_evidence_review` — Research and evidence review | gate | Understand · Context | discovery | — | n01_context_intake |
| 03 | `n03_problem_definition` — Problem and opportunity definition | agent | Understand · Problem Definition | definition | yes | n03_problem_definition |
| 04 | `n04_requirements` — User, business, and technical requirements | agent | Design · Problem Definition | definition | — |  |
| 05 | `n05_scope_success` — Product scope and success criteria | agent | Design · Problem Definition | definition | yes | n04_requirements |
| 06 | `n06_concept_ideation` — Concept ideation and comparison | agent | Design · Concept | concept | yes | n06_concept_ideation |
| 07 | `n07_experience_architecture` — Experience architecture and user flows | agent | Design · UX Design | experience | — |  |
| 08 | `n08_interaction_design` — UX and interaction design | agent | Design · UX Design | experience | — |  |
| 09 | `n09_visual_system` — Visual and design-system definition | agent | Design · UX Design | experience | yes | n09_visual_system |
| 10 | `n10_prototype_planning` — Prototype planning | agent | Build · Prototype | prototype | yes | n10_prototype_planning |
| 11 | `n11_prototype_development` — Prototype development | agent | Build · Development | prototype | — |  |
| 12 | `n12_content_data` — Content and realistic data integration | agent | Build · Prototype | prototype | — |  |
| 13 | `n13_quality_review` — Functional, design, and accessibility review | review | Build · Validation | validation | — |  |
| 14 | `n14_validation` — User and stakeholder validation | review | Learn · Validation | validation | — |  |
| 15 | `n15_feasibility_review` — Technical feasibility review | review | Build · Validation | validation | — |  |
| 16 | `n16_feedback_diagnosis` — Feedback diagnosis | gate | Learn · Iteration | iteration | — |  |
| 17 | `n17_targeted_rework` — Targeted redesign or redevelopment | tool | Build · Iteration | iteration | — | 10 rework targets |
| 18 | `n18_final_verification` — Final verification and delivery | tool | Build · Validation | delivery | yes | n16_feedback_diagnosis |
| 19 | `n19_learning_memory` — Learning and memory update | gate | Learn · Iteration | delivery | — |  |
<!-- NODES:END -->

The full per-node contract (inputs, outputs, checks, retry, escalation) is in the generated
[node catalog](node-catalog.md). Edges are in the [edge catalog](edge-catalog.md), and the picture is
[graph.svg](graph.svg) ([Mermaid source](graph.mmd)).

## Changing the graph

1. Edit `graph/workflow.yaml` and bump `version`. Copy the previous version to `graph/history/`.
2. `python -m pdg validate`, then `python -m pdg docs` (regenerates catalogs, schemas and the picture).
3. `python -m pytest -q`.
4. A run in progress blocks on the changed configuration until a named human runs `pdg accept-config`.
