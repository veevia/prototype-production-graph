# State model

> **TL;DR:** One typed, versioned `ProjectState` (pydantic, `pdg-state/v1`) holds everything a run knows. Nodes change
> it only through their declared writes. Every write is re-validated, every save is atomic, and every input a node
> depends on is fingerprinted by content.

## Shape

`.pdg/state.json` is validated against `schemas/state.schema.json` (generated from `pdg/models.py`).

| Section | Holds |
|---|---|
| `project` | id, name, creation time, workflow id and version |
| `inputs` | the brief, the source registry (each source evidence-tagged), `frozen` + `inputs_sha256` after N02, waivers |
| `product` | objective, value proposition, customer context, users, problem, requirements, constraints, scope, success criteria, rollback triggers |
| `research` | evidence, insights, assumptions, open questions, missing information, validation findings |
| `design` | criteria, concepts, selected concept, journeys, screens, flows, interactions, design system |
| `build` | plan, current prototype (version, artifact, entry, sha256, stack), build version, code and content artifacts |
| `artifacts` | content-addressed records: id `<node>/<key>/a<n>`, path, sha256, attempt, `current`, lineage inputs |
| `evaluation` | reviews (per node, attempt and build version), test results, feedback, defects, gates, comparisons |
| `history` | decisions, approvals (with `human: true/false`), checkpoints, change requests, delegations, risk acceptances, ratifications, revisions, versions |
| `knowledge` | the rule base in force (path, version, sha256), enforced and advisory rule ids, lessons, the learning proposal |
| `runtime` | run status, per-node runtime (status, attempt, streak, token, fingerprints, memo hits), loop traversals, batches, rework cycles, escalations, config fingerprint, dry-run flag |
| `controls` | per control document: version, status (template · accepted · locked), accepted sha256, lock owner, unlock set, history |

## The 14 state items

<!-- STATE-ITEMS:START -->
| State item (brief §5) | Where it lives in `ProjectState` |
|---|---|
| Product objective | `product.objective`, `product.value_proposition` |
| Customer and user context | `product.customer_context`, `product.users`, `product.problem` |
| Source evidence | `inputs.sources`, `research.evidence`, `research.insights` |
| Assumptions and open questions | `research.assumptions`, `research.open_questions`, `research.missing` |
| Requirements and constraints | `product.requirements`, `product.constraints` |
| Product scope | `product.scope`, `product.success_criteria`, `product.rollback_triggers` |
| Concepts and decisions | `design.criteria`, `design.concepts`, `design.selected_concept`, `history.decisions` |
| User journeys and flows | `design.journeys`, `design.screens`, `design.flows` |
| Design specifications | `design.interactions`, `design.system` |
| Prototype and code artifacts | `build.plan`, `build.prototype`, `build.code_artifacts`, `build.content_artifacts`, `artifacts` |
| Test results and feedback | `evaluation.reviews`, `evaluation.test_results`, `evaluation.feedback`, `research.validation_findings` |
| Defects and revision history | `evaluation.defects`, `evaluation.gates`, `evaluation.comparisons`, `history.revisions`, `history.versions` |
| Approvals and checkpoints | `history.approvals`, `history.checkpoints`, `history.change_requests`, `history.delegations`, `history.risk_acceptances` |
| Reusable lessons | `knowledge.lessons`, `knowledge.rules_version`, `knowledge.enforced` |
<!-- STATE-ITEMS:END -->

The generator asserts that every path exists in the model, so this table cannot drift from the code.

## How state changes

1. **Declared writes only.** An artifact output maps to a `state_write` path; the validator rejects any other path.
   At commit the engine writes through a JSON round trip and re-validates the section with its pydantic model, so a
   malformed agent output never reaches the state.
2. **Reducers.** Append-only collections (`evaluation.reviews`, `evaluation.feedback`, `evaluation.test_results`,
   `research.validation_findings`, `history.decisions`, `history.revisions`, `history.versions`,
   `build.code_artifacts`, `build.content_artifacts`) only grow. Because two appends cannot conflict, nodes that only
   append to the same path share a batch (n13 ∥ n14 ∥ n15).
3. **Engine-managed paths.** The engine alone sets `build.prototype` and `build.version`, and applies gate side
   effects: freezing the inputs (N02), defect status (N16/N17) and the learning proposal (N19).
4. **Build versions** increase only when the prototype's content changes. A rebuild that produces identical bytes
   keeps its version (`build_unchanged` on the ledger), so the reviews of that content still hold.
5. **Atomic persistence.** State is written to a temporary file and renamed. Checkpoints are named snapshots
   (`pdg status --checkpoints`, `pdg rollback`).
6. **One durable unit per human action.** A decision, feedback, brief revision, change request, unblock, accepted configuration,
   accepted risk, invalidation, rollback, archive or ratification changes the state in memory and buffers its ledger events. The state is saved once, at
   the end, carrying those events (`runtime.pending_ledger`, write-ahead); only then are they written to the ledger.
   Human actions may also carry `recorded_by`, `source` and `interprets` so the ledger distinguishes a human's own
   command from an agent transcription. A risk acceptance also stores the sha256 of the accepted assumption statement;
   legacy acceptances without that hash still count, but status and gate evidence mark them unbound.
   - A failure before the save leaves nothing behind: the in-memory state is put back, and a rollback also puts the
     control documents back.
   - A failure after the save keeps the events in the state. The CLI says `saved, but the ledger is behind`, and the
     next command that changes the run writes them, exactly once.
   - A node's commit keeps its own protection, the commit journal.
7. **Change-route unlocks.** An approved change request unlocks every control document written by its re-run nodes as a
   set until each locking gate re-approves. Older states with one `unlocked_for` value still load.
8. **The ledger is anchored to the state.** Every save records the ledger's last event (`runtime.ledger_tail`: seq and
   hash). A hash chain alone cannot see events cut from its end, or a whole ledger replaced by a new valid one. A
   ledger that no longer contains the recorded event is therefore refused in four places: the engine will not open
   the run, and `pdg ledger-verify`, the report and N18's release conditions all report it. Only a named human may
   accept the loss (`pdg accept-ledger-break <project> --actor <name> --reason <words>`). The break is ledgered, kept in
   `runtime.ledger_breaks` (a rollback never removes it) and listed in the release summary. It records which
   events survived and which were lost, and a last human action whose events could not be written is written again
   after the break. A damaged chain (an edited middle line) cannot be accepted: only a backup repairs it.
9. **Concurrent changes are refused.** The project lock serialises pdg commands. Beneath it, the engine saves
   `state.json` or appends to the ledger only if the file is exactly as the engine last read or wrote it (inode, size,
   modification time). Otherwise it raises `ConcurrentChange` and writes nothing. State, ledger, lock and hashed files
   are opened as regular files only, so a named pipe or device in their place is refused (`NotRegularFile`) instead
   of hanging the run while it holds the lock.

## Fingerprints and memoisation

A node's fingerprint hashes its definition, its prompt and the **content** of every input ref:

- `artifact:` refs hash artifact contents (sha256), not ids, so an identical re-run upstream does not force a re-run.
- `control:` refs hash only the sections written upstream of the node. Sections owned by the node itself or its
  descendants are feedback: feedback reaches a node only through a declared loop edge, which forces a re-run anyway.
  The same exclusion applies to artifacts that descendants produce.
- `state:` refs hash the value at the path. A path that a descendant also writes (for example, N05 adds open
  questions that N02 reads) makes the memo conservative. At worst this costs one extra re-run after an identical
  upstream re-run, and it never skips a needed one.

When a node passes, the engine stores its **stable** fingerprint, which leaves out its transient rework context. A
stale node whose stable fingerprint is unchanged is restored (`memo_hit`) instead of re-run, unless it is a rework
target (`force_rerun`). An outcome that loops back clears the stored fingerprint, because it was judged wrong and must
never be restored.
