# Control documents

> **TL;DR:** Eight Markdown documents under `<project>/controls/` hold the decisions humans read and sign: product,
> research, experience, design, prototype plan, development notes, evaluation and memory. The engine governs every
> change: who may write which section, what a human's approval locks, what is append-only, and when a hand edit blocks
> the run.

Templates live in `templates/control/`. Each derives from Wei's canonical artifact templates (front matter
`canonical_templates`) and cites the wiki instead of restating it.

## Who writes what

| Document | Writers (owned sections) | Readers | Locked by | Append-only |
|---|---|---|---|---|
| `product.md` | N03 (Problem, Users) · N04 (Requirements, Constraints) · N05 (preamble, Value proposition, Scope, Success criteria, Rollback triggers, Open questions) | N06–N09, N11, N15, N18 | N05 (Wei's PRD sign-off) | — |
| `research.md` | N02 (preamble, Evidence log, Insights, Assumptions, Open questions, Missing information) · N14 (Validation findings) | N03–N05, N12 | — | Evidence log, Validation findings |
| `experience.md` | N07 (preamble, Journeys, Tasks, Information architecture, User flows, System behavior) · N08 (Interactions and states) | N10, N11, N13 | — | — |
| `design.md` | N09 | N10, N11, N13 | N09 (visual system approval) | — |
| `prototype.md` | N10 | N11, N12 | N10 (fidelity and plan approval) | — |
| `development.md` | N11 | N15 | — | — |
| `evaluation.md` | N05 | N10, N13–N16, N18 | N05 | — |
| `memory.md` | N19 | N01, N02 | — | Lessons log |

Canonical sources: problem frame and PRD (product), research report (research), journey map and design handoff
(experience, development), `templates/artifacts/DESIGN-SYSTEM-AI-INSTRUCTIONS.md` (design), test plan (prototype).

## How a change is installed

An agent copies `controls/<doc>.md` into its work folder, changes only its sections there, and submits that copy (the
task packet says so). An agent that edits the live file in place and submits it anyway has that text adopted as its
submission: the live file goes back to the accepted version, and the same checks decide what lands
(`live_control_edit_submitted` on the ledger). At commit, `ControlStore.check_install` refuses a submission (nothing is
written) when:

- the node does not list the document in `controls.write`;
- the submission is empty;
- the document is locked and the node is neither the locking gate nor unlocked by an approved change request;
- an append-only section (a heading followed by `<!-- append-only -->`) lost or rewrote an accepted line;
- the live file was edited outside the workflow since it was accepted (installing would silently erase the edit).

An accepted document is archived as a new version in `.pdg/controls/`, recorded (version, sha256, node) and then
written, in a crash-safe order: archive → record → live file. On resume, a live file that matches an older accepted
version is rolled forward.

## Shared documents: section ownership

Three documents have several writers. Each writer owns named sections (`controls.sections` in the graph), and the
validator requires exactly one owner per section, every template heading owned, and one owner for the preamble.

- Installing takes **only the writer's owned sections** from the submission and keeps every other section as accepted.
  A writer may submit only its own sections (N03 and N04 do in the example); a section it leaves out keeps its text.
- An edit to a section the writer does not own is **ignored and reported**: `control_edits_ignored` on the ledger, and
  a `note:` line in the `submit` output naming each section and its owner. An agent working from a stale copy
  therefore cannot erase another node's work, and the change is never silent. (Until the first field run the only
  report was the ledger event; the agent found its ignored edit by searching the ledger.)
- For memoisation, a reader's fingerprint covers only the sections written upstream of it
  ([state model](state-model.md#fingerprints-and-memoisation)). A validation finding appended by N14 does not force
  N03 to re-run.

## Locks and change requests

A human gate listed in `lock_on_approval` locks the document when a named human approves: N05 locks product and
evaluation, N09 design, N10 prototype. After that:

- The locking gate itself may still revise the document when its own node re-runs, which forces re-approval at that gate.
- Any other writer needs a **change request**: `pdg change-request <project> --doc <doc> --reason "…" --actor Wei
  --writer <node>`. An agent may file one, but it stays `open`. A named human's request re-opens the writer and its
  descendants, unlocks each locked document those rerun nodes write for that writer set (except the signing gate
  itself), re-opens the defects that were waiting on it, and carries the reason in each rerun packet. Each writer is
  removed from the unlock set when it passes by submit or memo, and the signing gate clears the remaining set when it
  re-approves. The original signing gate keeps the lock owner throughout.
- Write a change request's reason as the stakeholder's words, quoted, then the outcome they ask for, paraphrased: not
  the components the build happened to have. A request that names the parts ("title in capitals, capability chip,
  subtitle") needs a second request when the next feedback removes one of them (field run 2, R2-32).
- The review gate marks a defect `needs_human` when fixing it would need a change request, so the run stops and says
  so instead of looping.

## Hand edits

Editing a live control document outside the workflow is detected before the next step (the file's sha256 no longer
matches the accepted version), and the run blocks. A named human restores the accepted versions with
`pdg unblock <project> run --restore-controls --actor Wei`; the displaced text is kept in `.pdg/controls/` as
`<doc>.hand-edit-<time>.md`. To keep the change instead, file a change request for the owning writer and let the
workflow make it.
