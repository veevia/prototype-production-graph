# Evaluation and gates

> **TL;DR:** 22 rubrics (98 dimensions: 77 tool, 13 review, 8 human) define "done" before any work starts. Tool checks
> run first and cannot be overridden by a reviewer. A tri-state gate turns what fails into traced defects, routes them
> back to the node that caused them, and stops for a human when a fix would repeat, change a signed document, or
> exhaust the budget.

## Rubrics

Each file in `rubrics/` binds dimensions to one or more nodes (`evaluation:` in the graph). A dimension has an id, a
level (`MUST` · `SHOULD`), a check (`tool` with a function, `review` by a reviewer agent, or `human`), a threshold,
the brief dimension it serves, and the **rule** in `knowledge/rules.json` that it enforces. The generated
[rubric catalog](rubric-catalog.md) lists them all.

**Enforcement follows the rule's lifecycle state:**

| Rule state | Mode | A failed MUST… |
|---|---|---|
| adopted · monitored | enforced | blocks: the finding is raised to at least P3 |
| validated · approved | advisory | is reported as P4 and never blocks |
| candidate · revised · retired | informational | is recorded only |

A new rule therefore cannot block a run until a named human has approved and adopted it ([self-improvement](self-improvement.md)).
A finding stored as P4 because it does not block (a SHOULD, a rule not yet enforced, a passing dimension) keeps the
reviewer's or tool's own severity as `reported_severity`, so the diagnoser and the release evidence still see a P2
as a P2. P4 alone decides that it does not block, since the gate and release count P1–P3 as blocking.

## Scoring a node

1. **Tool dimensions** are scored from the node's completion checks, or from the pre-check of a review node, which is
   persisted as `work/<node>/a<n>/precheck.json` so the reviewer reads the same results. A tool dimension whose
   check ran but did not report is recorded `not_scored`: a tool defect, never a silent pass. A tool's evidence says
   what it measured and is kept as the dimension's detail line with the attempt. `pdg status --json --evaluation`
   exposes each dimension's score/status/evidence/detail and each defect's id, signature, severity, owner node and
   message, so agents do not read `.pdg/state.json` directly. CNT-VOLUME names the list it counted in each dataset (a dataset may name its `primary` list, or
   one type of it as `key[field=value]`; otherwise the longest list counts). TEC-UNIT says which dataset the unit
   tests read: when the build manifest's `unit_tests_dataset` is not its `dataset`, the tests exercised data the build
   does not ship, and TEC-UNIT fails. The browser suite's screenshots hide scrollbars (headless Chromium's default);
   its report and the reviewer's pre-check say so, because a scroll cue cannot be judged from them.
   Any change to the browser suite or its checks is replayed before landing with `loop/replay_verdicts.py` against the
   private field-run corpus named by `PDG_REPLAY_CORPUS`; stricter flips are investigated before the change lands.
2. **Review dimensions** come from the reviewer agent's review record. A reviewer can add findings, but it cannot
   pass a dimension that a tool MUST failed. A review states who performed it (`reviewer`) and whether that reviewer
   produced none of the reviewed work (`independent`). pdg cannot see which agent ran a node, so both are claims, and
   the release summary lists them as such, flagging a self-review. A re-review packet lists the open defects that
   review reported, with signature and acceptance check: one that is still true is filed again under the same
   signature, and a fixed one is not filed at all, so it resolves.
3. **Human dimensions** stay `pending` and are listed for the human at the next gate and in the run report.

Severity runs from P1 (critical) to P4 (nit). `blocking_severities` is P1–P3.

For N10's fidelity gate, an `accepted_risk` line counts only when `pdg accept-risk` was recorded for the current
assumption statement. New acceptances store the accepted statement's sha256. If the statement changes later, the gate
fails with `A-01 changed after <actor> accepted it on <date>: re-accept`, and `pdg status` lists the changed acceptance.
Older acceptances without a hash still count and are marked unbound.

## The review gate (N16)

The gate applies the failure procedure: identify the failure, trace its cause, choose the smallest effective fix,
re-run only what is affected, compare before and after, record the outcome, and escalate a repeated failure.

**Delegation and transcription.** A named human can grant a scoped, time-limited delegation to an `agent:` actor for selected gate actions
(`decide`, `change_request`, `unblock`, `accept_config`, `invalidate`) and selected human gate nodes. `accept_risk` is
delegable only when the delegation's scope lists `accept_risk` explicitly; it is never implied by an empty or broad node
scope. The grant records the human's verbatim instruction, expiry, scope and delegate in the ledger, and who typed it:
`--recorded-by` is required on the command line and names either the human themself or the `agent:` actor transcribing
their words, with `--source` saying where the words came from (a chat message and its time). A grant an agent typed is
flagged in the human record, and one that states no typist is flagged as such. A delegated action
is never recorded as the agent impersonating the human: the actor stays the agent, the approval/request/risk acceptance
carries `on_behalf_of` and the delegation id, and the release summary flags it as delegated. A grant stops authorizing
anything once its grantor leaves the project's humans list. A grant that covers `unblock` may state how many rework-budget
resets it covers (`--budget-resets N`); an agent's reset beyond that is refused and needs the named human. When several grants cover `unblock`, the latest
one governs, and a refusal names it. The status line
and the gate's GAT-ESCALATE evidence count the resets made, by grant and by human. A grant that states no number is not
limited (the default is D12, Wei's decision). A `decide` grant that would cover `n18_final_verification` is refused
unless `pdg delegate` is run with `--include-release`. Ledger-break acceptance, rollback, archive apply and memory writes
are not delegable.

Every human-only command may record who typed it and the source words with `--recorded-by` and `--source`; when
`--recorded-by agent:<role>` is explicit, `--source` is required. `--interprets` marks a transcription that goes beyond
the source words, and the release's human record lists it as unconfirmed until `pdg ratify <project> <event-or-action-id>
--actor <human> --reason <words>` records the human's confirmation (or `--reverse`). Placeholder text such as `<…>`,
`…` or `Wei's words` is refused for reasons and instructions; when a reason is omitted at a terminal, pdg prompts for it,
and without a terminal it refuses.

**A gate asked again.** A gate that re-runs after an upstream change (a change request, a rework cascade) and waits for
its approver again compares its outputs with the ones last approved: its artifacts, and each control document it writes
as the whole accepted document. `pdg status` and the `awaiting_human` event then say either that the outputs are
byte-identical to the version approved (by whom, when) or which outputs changed, and why the gate re-ran. The approver
still decides: a byte-identical re-ask is shown, never approved automatically.

**Defects.** Every blocking finding and every open feedback item becomes a defect (or is dismissed with a reason):

| Field | Meaning |
|---|---|
| `signature` | `dimension@location`, stable across builds, so the same failure is recognised when it recurs; locations under `work/<node>/a<n>/` are normalised to remove the attempt folder, and a finding that names its `element` adds `#element`, so two findings of one dimension on one screen stay two defects |
| `traced_node` · `trace_reason` | the earliest node whose output is wrong, and why (not the last node that touched it) |
| `smallest_fix` · `acceptance_check` | what to change, and the observable check that proves it changed |
| `source_nodes` · `opened_at_version` | which reviewers found it, and at which build |
| `status` · `failures` · `attempts_at_start` | open → in_rework → resolved or persisting; any blocking one → resolved once its node re-ran and nobody reports it; `needs_human`; `dismissed` |

Tool findings arrive already traced and map automatically. The interpreter agent must map every human and agent
finding and every open feedback item (`interpretation_complete`); an unmapped item fails the node. A review finding the
interpreter checked and disproved is answered instead (`answered_findings`: the finding's `node:signature`, the reason,
the evidence and who checked). The answer stands in for a defect, is recorded on the gate, and is listed at release
beside the finding. A tool finding cannot be answered away: fix the build or the tool. An answer never resolves an
existing defect, which a reviewer's re-report keeps open.
`pdg draft-interpretation <project>` writes a schema-valid N16 skeleton and a `.findings.json` sidecar from current
reviews: each finding's exact signature, its default traced node by dimension, re-failed resolved defect ids and empty
`answered_findings` slots to copy into the interpretation when needed. `check-output --project` and `check-node` refuse
an interpretation that drops a current blocking finding.

**Resolution.** A blocking defect is **resolved** when a correction has run and been re-checked, and its signature is
gone: nobody reports it any more, neither a current review nor the interpreter. A correction has run when the node
that owns the fix re-ran and passed after the defect was last seen or its rework started. That can happen through
targeted rework, an approved change request, or a source Wei added. Every reviewer that found the defect must have
re-reviewed since then too. A fix need not change the prototype: a wording fix in a control document keeps the build
version and still resolves. An interpreter that merely stops mentioning a defect resolves nothing, because its node
must have re-run. A defect in rework whose correction did not resolve it is **persisting**, and its failure count
rises. Any current finding with a defect's signature, blocking or advisory, still reports it: a reviewer re-filing
a problem on a SHOULD dimension files an advisory finding, and that must not resolve a blocking defect. An advisory
defect is never routed, so it resolves the same way once its node re-ran. Without this rule, a defect fixed outside
targeted rework would block the run for good.
Defects saved without an attempt record fall back to checking for a newer build until their
next rework records one.

**Outcome**, recomputed from state and never taken from the agent:

| Outcome | When | Then |
|---|---|---|
| `pass` | every review is current for the build and no blocking defect is open | E27 → release verification |
| `rework` | routable defects remain and the budget allows | E28 → N17 builds the regeneration plan |
| `blocked` | a review is missing or stale; a defect needs a human (its trace is not a regeneration target, the fix would change a locked document, or the rework edge to its node has used all its traversals); a defect failed `max_same_defect_failures` (3) corrections; or `max_rework_cycles` (4) is spent. A rework plan re-run for the same gate (after an unblock) is the same cycle | E29 → escalation report; the run is BLOCKED |

**Comparison.** After each rework cycle the gate records a before/after comparison: the targets, the artifact hashes
before and after, the build versions, the resolved, persisting and new defects, and a verdict (`improved` if
something was resolved and no more new blocking defects appeared than were resolved; `regressed` if more new blocking
defects appeared than were resolved; `unchanged` otherwise). In the example the first cycle resolves D-001–D-004 and
the verdict is `improved`.

## Targeted rework (N17)

The regeneration plan groups the routable defects by traced node and fires the loop edge `target:<node>` (E30–E39)
for each target. Each target re-runs with its defect ids, smallest fixes and acceptance checks as context. Its packet
also lists, apart and as optional, the advisory defects traced to it: they are never put into rework, where a failed
correction would count towards escalation, and each resolves at a gate once its node has re-run and no review
reports it. A rework cycle surely re-runs only its targets (a node after one re-runs only if its inputs changed; one
that did not is memo-restored), so an advisory elsewhere can stay open for good. A rework gate's report therefore lists
these as `stranded_advisories`, each with why and a remedy that works for its node: N16 re-files it at a blocking
severity where the gate can route it, a named human approves a change request where its document is locked (raising it
would block the gate), or a named human invalidates a node the gate cannot route, or any node once the rework budget
is spent (raising it then would block the gate too). N16's packet lists every open advisory with the same remedy. A node
re-opened while its defects are still in rework (by `pdg invalidate`, say) is told to keep them fixed. N16's packet lists
every blocking finding at the current build as `node:signature`, with severity, dimension and message. Its
descendants re-run only if their inputs changed, and unaffected nodes are memo-restored. A defect with no routable
target escalates (E40).

## Release verification (N18)

N18 recomputes seven conditions at release rather than trusting an agent's report. Three re-hash files on disk: the
prototype hashes verify, the ledger verifies and still reaches the last event the state recorded, and every control
document matches its accepted version. Four are recomputed from the engine's saved state: the latest gate passed on
the current build, no blocking defect is open, every review is current, and every upstream node passed. It then writes a package (prototype, control
documents, evidence, ledger, and a sha256 manifest) and a release summary. The summary lists every approval not made
by a human and every simulated validation session before Wei approves the release. Its TL;DR tells a dry run's scripted
approvals apart from approvals an agent made under a delegation (how many, by whom, on whose behalf, under which grant),
and says when the validation used simulated sessions only (task-success metrics then rest on no user evidence),
and its **Delegations** section lists each grant: grantor, delegate, who typed it and from what, scope, expiry, the
human's words, and what was done under it. **Who reviewed** lists each current review's stated reviewer and
independence. **Defects still open at release** lists every open defect (none can block, or release
fails): its severity, the reviewer's own when it was kept advisory, and whether its fix waits on a human because the
node's document is locked; the TL;DR counts them. **Reviewer severities the last gate kept advisory** lists each
reviewer P1–P3 finding the interpretation did not raise to a defect. Every gate records those it raised and kept;
which of them should block is a policy Wei decides. Its **human record** lists
every action taken under a human's name: gate decisions, change requests, unblocks, accepted configurations, risks and
ledger breaks, waivers, restores, rollbacks and delegated actions. It also lists delegation grants and revocations. Each
row shows the reason and, for a gate decision, how long the gate had been waiting. Decisions made within 60 s of the gate
opening, reasons repeated word for word, delegated actions (`delegated by <human> (DL-xxx)`) and transcribed actions
(`typed by agent:<role> from …`, including unconfirmed interpretations) are flagged. Until N19 passes, the summary's
TL;DR says learning is pending. Identity is
asserted by name, so this is how Wei checks that each action was his or was taken under a delegation he granted.
