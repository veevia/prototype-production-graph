# Orchestration

> **TL;DR:** The engine runs in steps. Each step picks the ready nodes, batches the ones that cannot conflict,
> executes them in parallel, then judges and commits them one at a time in graph order. Loops re-open only the traced
> nodes and their descendants, with budgets that end in an escalation to a named human, never an endless loop.

## Node lifecycle

```
PLANNED ─► READY ─► RUNNING ─► (WAITING_AGENT) ─► VALIDATING ─► PASSED
                                    │                  │           │ an upstream node re-runs, or a loop / rework targets it
                             WAITING_HUMAN             ▼           ▼
                           (human gates)      retry: READY again  STALE ─► memo_hit (identical inputs) ─► PASSED
                                                  │                 └────► READY (inputs changed, or force_rerun)
                                                  ▼ retry budget spent
                                               BLOCKED (escalated)
```

Run status: `RUNNING`, `WAITING_AGENT` (task packets out), `WAITING_HUMAN` (a gate awaits a decision), `BLOCKED` (an
open escalation), `RUN_PASS` (END reached).

## Scheduling

- **Readiness:** every flow predecessor has passed (join = all). Loop and escalate edges never gate readiness.
- **Batching:** up to `parallel_limit` (4) ready nodes, in topological order, skipping any that conflict with a node
  already chosen: the same non-reducer `state_write` path, the same control document, or the same single-flight
  resource (`browser`). In the example this gives n08 ∥ n09 and n13 ∥ n14 ∥ n15.
- **Memo check:** a `STALE` node whose stable fingerprint equals the one it passed with is restored without running
  (`memo_hit`), unless it is a rework target.
- **Execution:** the batch runs on threads through the executor. Results are then judged and committed serially.

## Executors

| Executor | When | How |
|---|---|---|
| `ScriptedExecutor` | `dry_run: true` | Reads `fixtures/<node>/attempt-<n>/fixture.yaml`, runs its commands (for example the prototype build) with placeholders (`{python} {project} {work} {fixture}`), and returns its outputs. It falls back to the latest earlier attempt. |
| `TaskPacketExecutor` | a real project | Writes `.pdg/tasks/<node>-a<n>.md` and `.json` (agent, skills, inputs, schemas, quality bar, prompt, exact submit command, dispatch token) and returns *pending*. The node waits in `WAITING_AGENT` until `pdg submit`. |

A submission can be dry-run first with `pdg check-node <project> <node> --output key=path …` or `pdg submit --dry-run`.
It resolves paths exactly as `submit` would, runs schema checks, node tool checks and gate preconditions, prints the
exact submit command with real paths, writes nothing under `.pdg/`, and uses no attempt. It holds the project lock only
to load state and then to confirm the run did not change while the checks ran, so long browser checks do not block
normal progress. The older `check-output` and `check-build` commands remain as narrower pre-submit checks.

A submission is refused (exit 4, nothing written) when the token is stale, an output key is undeclared or belongs to
the engine's own check (a tool verdict cannot be resubmitted), a path is missing or lies outside the project, the
node is not waiting, or the node's output asks for a human-only precondition that has not happened yet. For example,
a mid/high N10 plan that marks a riskiest assumption `accepted_risk` is refused before judging until the exact
`pdg accept-risk <project> <A-id> --actor <human>` command has been recorded for the current assumption
statement. If an integrity problem exists (for example a
hand-edited control document), the submission is not accepted and the run blocks; the node keeps its packet and token,
and the agent resubmits after a named human resolves the problem.
If the only failure is that a control document is locked, `submit` refuses with exit 4 and keeps the attempt; the packet
names the lock and the `pdg change-request` command to unlock it.

## Retry and escalation

- A failed attempt records its failures, increments the node's streak and re-dispatches. The next packet lists every
  failure as retry context. An interrupted attempt (the process died) is not charged against the budget. An attempt
  that passes its checks clears them, even while it waits for its gate, so `submit` and `status` report that attempt.
- A node that passed and runs again (its own invalidation, or a change upstream of it) gets a packet that starts with
  **Why this attempt**: the reason (naming only the re-opened nodes upstream of it), each artifact or control input
  that changed since its last pass (a control document with its diff), and the files its last passed attempt
  submitted, which it may submit again when its own work needs no change. A pass saved before pdg recorded the
  control versions it saw recovers them from the ledger, which orders every install and pass.
- Re-run packets also list every change request and invalidation since the last pass, every open feedback item for
  N16, every open blocking defect traced to the node with its smallest fix and acceptance check, and any control locks.
  N16 packets include the blocking trend and active recurring components/screens across cycles.
- After `retry.max_attempts` consecutive failures, the node escalates. The engine writes a report to
  `.pdg/escalations/` (what failed, the rework history, the open defects, what unblocks it, and the exact `pdg unblock`
  command with the project path quoted), sets the run to `BLOCKED`, and appends to the ledger.
- `pdg status` shows waiting task age and flags a task that has waited more than an hour without a submission.
- `pdg waiting <project> [<project>…]` prints one table of pending human-only actions, their exact ready-to-run
  commands, the actor needed and what each action unblocks.
- `pdg unblock <project> <node> --actor Wei --note <words>` gives the node a fresh budget and re-runs it. The
  `--reset-budget`, `--waive <gap>` (intake gaps only) and `--restore-controls` options cover the other cases.

## Loops and targeted rework

| Loop | Fires when | Budget |
|---|---|---|
| E03 n02 → n01 | N02 finds a resolvable intake gap | 2 traversals, then escalate |
| E07 n03 → n03 · E10 n05 → n04 · E12 n06 → n06 · E17 n09 → n09 · E19 n10 → n10 · E42 n18 → n16 | a named human rejects (or requests changes) at a gate; the reason becomes retry context | 2 traversals each, then escalate |
| E30–E39 n17 → n03…n12 | the review gate routes defects to their traced nodes | `max_rework_cycles` (4) overall; `max_same_defect_failures` (3) per defect |

When a loop fires, its targets become `STALE` with `force_rerun` and their defect ids as rework context. Their
descendants become `STALE` without force, so each descendant re-runs only if its inputs actually changed. In the
example's rework cycle, n08, n10, n11 and n12 re-run, n09 is not touched, and the three reviewers re-check the new
build.

## Human gates

Six nodes wait in `WAITING_HUMAN` after their checks pass. `pdg approve <project> <node> --actor Wei`
(to reject, add `--reject --feedback "…"`) decides. The engine refuses an actor who is not a named human, and a decision that is
not a declared outcome. In a dry run, the `dry-run-auto` actor decides and each decision is recorded `human: false`.
If a human command is transcribed by an agent, the command carries `--recorded-by agent:<role> --source <verbatim words>`;
`--interprets` marks a transcription that goes beyond the words until `pdg ratify <project> <event-or-id> --actor <human>
--reason <words>` confirms it (or `--reverse` reverses it).

## Durability

- **One writer per project:** every mutating command takes `.pdg/lock` (with a timeout and holder description).
  `status` reads without the lock and never writes. The rule base has its own lock.
- **Checkpoints:** a snapshot at run creation and at every pass, failure, human wait and escalation. `pdg rollback <project> --checkpoint <seq> --actor Wei`
  (named human) restores one, restores the control documents, and keeps loop budgets so a rollback cannot reset them.
  A node that was waiting on an agent is re-dispatched with a new token; the old packet's token is refused.
- **Crash resume:** a commit writes a journal first. A process that dies mid-commit leaves the journal, and the next
  load restores the state from before the commit and puts the control files back to their accepted versions. Nodes
  that were `RUNNING` are reset to `READY` without charging an attempt. A torn last ledger line is set aside
  (`ledger.jsonl.torn-*`) so the hash chain continues. Loading a healthy run writes nothing.
- **Forced rework survives interruptions:** a rework target keeps `force_rerun` until it passes, so an upstream
  invalidation during its attempt cannot memo-restore it with its defects unfixed.
- **Integrity:** before every step, a changed configuration, a changed frozen input, a hand-edited control document or
  a tampered artifact blocks the run. `tree_sha` ignores file-manager noise plus Python bytecode caches
  (`__pycache__/` and `*.pyc`), so reading a registered artifact with Python does not change its integrity hash.
- **Check code provenance:** `code_updated` events and each node's recorded check code include the pdg git commit, any
  uncommitted package files and a diff hash when the package is in a git repository. Git is best-effort provenance:
  commands keep running when the package is a temporary copy with no git metadata. `pdg status` warns when any run's
  checks ran on uncommitted pdg code, and the release summary lists those files.
- **Release re-checks:** `pdg recheck-release <project>` writes reports under
  `<project>/.pdg/release-recheck/<UTC timestamp>/` by default, beside `.pdg/release-recheck.json`. `--out` selects an
  explicit report folder. If the run changes while the suite is running, the report is not recorded; re-run once the
  run is quiet. The default report folder is run evidence: include it with the run's `.pdg/` state in release commits
  and archive it with the run.

## Release shelf, archive and commit policy

- When N18 is approved, pdg rebuilds a stable release shelf from the approved release records and release packages. The default shelf is
  `<project>/releases/`; `release_shelf: <path>` in `pdg.project.yaml` may point inside the project or inside the
  parent hub folder (for example `../releases`). A shared hub shelf namespaces each run's versions, records, latest
  redirect and release index so projects cannot overwrite one another.
- `pdg release-shelf <project>` rebuilds that shelf for releases made before the feature existed.
- `pdg status` prints the shelf's `latest.html` path when that file exists.
- `pdg archive` scans project files outside `work/` and `.pdg/`, plus kept attempts, before listing candidates. It
  keeps folders referenced by markdown links, HTML links, source-code paths or symlinks, and `--keep <path>` can be
  repeated to hold back additional folders. The listing states what is kept and why.
- `pdg archive --apply` remains human-only. It refuses an archive that would leave a dangling symlink in the run and
  moves checkpoints whose current artifacts depend on moved attempts into the same archive folder and restore script.
  A rollback to an archived checkpoint, or to a checkpoint whose current artifacts are archived, tells the operator
  only the archive folders that hold the missing checkpoint or attempt folders.
- A run commit contains sources, controls, the release shelf, `.pdg/` state and ledger, and each node's final attempt.
  Earlier attempts and screenshot rounds go to `pdg archive`.
