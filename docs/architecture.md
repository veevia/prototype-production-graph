# Architecture

> **TL;DR:** A declarative graph (`graph/workflow.yaml`) drives a deterministic engine. Nodes execute in parallel and
> are judged and committed one at a time in graph order. Every output is checked against rubrics before it can change
> state, and every defect is traced to the node that must fix it.

## Components

```
graph/workflow.yaml ──► graph.py ─── load · index · validate (the engine refuses an invalid graph)
                            │
rubrics/ + rules.json ──► evaluation.py ─── dimension modes follow each rule's lifecycle state
                            │
                        engine.py ─── schedule · dispatch · judge · commit · loop · escalate · checkpoint
                        │ ├ engine_config.py ── drift · accept-config · re-judge · parked submissions
                        │ ├ engine_human.py ─── approvals · delegations · change requests · waivers · invalidation ·
                        │ │                     unblock · rollback · archive
                        │ ├ engine_packets.py ─ task packets · status · lineage
                        │ └ engine_common.py ── errors, status groups, shared helpers, the declared engine state
                       ╱    │    ╲
         executors.py  tools/  gating.py ─── review gate · regeneration plan · release verification · learning
     (scripted | packets)  │
                     controls.py ─── the 8 control documents: ownership, locks, change requests, append-only
                     memory.py ───── the governed rule base (candidate → … → adopted → monitored)
                     provenance.py ─ hash-chained ledger + content-addressed artifact records
                     lock.py ─────── one writer per project, and one per rule base
cli.py · dryrun.py · docs.py · report.py ─── the command line, the example run, generated docs, the HTML report
```

`util.py`, `provenance.py` and `lock.py` are adapted from the video production graph's kernel (attribution in each
file). Everything else is specific to product design. [ADR 0001](../CONTRIBUTING.md) explains why the
engine is standalone.

## Node kinds

| Kind | Nodes | What runs | What judges it |
|---|---|---|---|
| `agent` | n01, n03–n12 | An agent via a task packet (or a scripted fixture in a dry run) | Completion checks, then the tool dimensions of the node's rubrics |
| `review` | n13, n14, n15 | A deterministic pre-check (`run.tool`, e.g. the browser suite), then a reviewer agent that reads its results | Tool dimensions from the pre-check. A reviewer cannot override a failed tool MUST; human dimensions stay pending |
| `gate` | n02, n16, n19 | An agent, then a gate hook (`freeze_inputs`, `review_gate`, `learning`) that decides the outcome | The hook's recomputation from state, never the agent's claim |
| `tool` | n17, n18 | Deterministic code: the regeneration plan and release verification | Its own recomputed conditions |

## One step

A step runs **in parallel, then commits serially**, like bulk-synchronous (Pregel) supersteps:

1. **Ready.** A node is ready when all its flow predecessors have passed (join = all) and it is `PLANNED` or `STALE`.
2. **Batch.** Ready nodes are batched up to `parallel_limit`. Two nodes conflict, and so do not share a batch, when
   they write the same non-reducer state path or the same control document, or need the same single-flight resource
   (`browser`). A stale node whose input fingerprint is unchanged is restored from memo instead of re-run.
3. **Execute.** The batch runs on threads. Agents write only into `work/<node>/a<attempt>/`.
4. **Judge and commit**, one node at a time in topological order. Each commit runs this pipeline:
   register artifacts (content-hashed) → check and install control documents (merged by section ownership) →
   completion checks → score rubric dimensions (tool, review, human) → gate hook → typed state writes → pass
   (fire outgoing edges) or fail (retry context, or escalate). A failure anywhere rolls the node's writes back to a
   snapshot, and a commit journal (`.pdg/commit-journal.json`) lets a crashed process resume from the state before the
   commit, so a half-committed node never survives.
5. **Persist.** State is saved atomically after every commit. The ledger appends a hash-chained event for every
   dispatch, decision, install, gate, loop and escalation. Checkpoints are named snapshots that `rollback` can restore.

## Trust boundaries

- **Agents** produce files and nothing else. The engine validates every artifact against its schema, recomputes every
  gate from disk, and refuses outputs that come from outside the project (including links inside a directory output),
  or that carry a stale dispatch token. A review node's tool verdict is stored under `.pdg/prechecks/` with the hash of
  every file the tool wrote. The copy in the agent's work folder is for reading only, and a tool output edited before
  submission fails the attempt.
- **Humans** own six commitments: problem (n03), scope and success (n05), concept (n06), visual system (n09),
  fidelity and plan (n10) and release (n18). Only a named human's decision passes these gates, and dry-run decisions are
  labelled `dry-run-auto`. Approval locks the product and evaluation documents; changing them afterwards needs a
  change request approved by a named human.
- **Integrity.** Before each step the engine re-checks the configuration fingerprint (workflow, rules, rubrics,
  defaults), frozen inputs, control-document drift and artifact hashes. Any mismatch blocks the run until a human
  accepts or restores it.

## Design choices

Each choice is grounded in product design practice and graph-engineering research ([research](research/graph-engineering-and-tools.md)):

| Choice | Why |
|---|---|
| Rubrics are written before the work, and tool checks run before the reviewer agent | Write the behaviour rules and thresholds down before testing, and verify in a real browser first |
| Defects carry a trace (node · location · smallest fix · acceptance check) | Rework reaches the cause, not the symptom; a defect nobody can trace escalates to a human instead of looping |
| Only traced nodes and their descendants re-run; identical inputs are memo-restored | "Do not restart the full workflow when a targeted revision is sufficient" |
| Parallel execution with serial commit | Throughput without write races; a deterministic commit order makes runs reproducible |
| Section ownership in shared documents | Several nodes write one document without clobbering each other; a downstream write never silently invalidates an upstream node |
| Enforcement follows the rule lifecycle | A new rule is advisory until a named human approves it; nothing unreviewed can block a run |
| Scope the change to the request | Unify components and usability, never flatten distinct workflows |
