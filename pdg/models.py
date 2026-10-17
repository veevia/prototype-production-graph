"""Typed models: the workflow graph definition and the shared project state.

The state separates what may change from what may not:
  inputs      immutable project inputs — the brief and the registered sources, hashed and frozen at n02
  product     objective, customer and user context, problem, requirements, constraints, scope, success criteria
  research    evidence, insights, assumptions, open questions, missing information, validation findings
  design      design criteria, concepts, the selected concept, journeys, screens and flows, interactions, visual system
  build       the prototype plan, the prototype and code artifacts, content and data
  artifacts   content-addressed files with lineage (never deleted; older versions are superseded)
  evaluation  reviews, test results, feedback, defects, gate results, before/after comparisons
  history     decisions, approvals, checkpoints, change requests, revisions, versions (append-only)
  knowledge   the rule base this run is governed by, and the lessons this run proposes
  runtime     execution control: node status, attempts, fingerprints, traversals, escalations
  controls    the eight control documents: status, versions, approval locks
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .artifacts import (Assumption, Concept, Constraint, Criterion, DesignSystemDoc, Evidence, Flow, Insight,
                        InteractionDoc, Journey, Lesson, Metric, OpenQuestion, ProblemFrame, PrototypePlan, Requirement,
                        Scope, Screen, Source)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# --------------------------------------------------------------------------------------------- workflow definition


class NodeKind(str, Enum):
    AGENT = "agent"    # an agent produces the declared outputs from a task packet
    TOOL = "tool"      # a deterministic function in pdg.tools runs in-process
    REVIEW = "review"  # tool checks first (findings), then an agent scores the review dimensions
    GATE = "gate"      # an agent interprets, then a deterministic hook decides the outcome


class EdgeKind(str, Enum):
    FLOW = "flow"          # forward dependency; the target waits for every incoming flow edge (join = all)
    LOOP = "loop"          # bounded back-edge; re-opens an upstream node instead of satisfying a join
    ESCALATE = "escalate"  # stop and report to a named human (BLOCKED); never silently retried


LIFECYCLE_STEPS = [
    "Context intake", "Research and evidence review", "Problem and opportunity definition",
    "User, business, and technical requirements", "Product scope and success criteria",
    "Concept ideation and comparison", "Experience architecture and user flows", "UX and interaction design",
    "Visual and design-system definition", "Prototype planning", "Prototype development",
    "Content and realistic data integration", "Functional, design, and accessibility review",
    "User and stakeholder validation", "Technical feasibility review", "Feedback diagnosis",
    "Targeted redesign or redevelopment", "Final verification and delivery", "Learning and memory update",
]
STAGES = ["Context", "Problem Definition", "Concept", "UX Design", "Prototype", "Development", "Validation", "Iteration"]
PHASES = ["Understand", "Design", "Build", "Learn"]
CONTROL_DOCS = ["product", "research", "experience", "design", "prototype", "development", "evaluation", "memory"]


class Check(_Strict):
    """A completion criterion the engine recomputes from disk and state — never an agent's self-report."""

    type: Literal["artifact", "tool", "state", "review_complete", "interpretation_complete"]
    key: str | None = None
    fn: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    description: str


class OutputSpec(_Strict):
    key: str
    kind: Literal["json", "markdown", "dir", "file", "control"]
    description: str
    schema_name: str | None = Field(default=None, alias="schema")
    doc: str | None = None                                    # kind=control: which control document it installs
    state_fields: dict[str, str] = Field(default_factory=dict)  # JSON field → state path
    required: bool = True


class RetryPolicy(_Strict):
    max_attempts: int = Field(ge=1)
    behavior: str


class EscalationPolicy(_Strict):
    after: str
    to: str
    report: str


class HumanReview(_Strict):
    required: bool
    decision: str
    approver: str = "Wei"
    outcomes: list[str] = Field(default_factory=lambda: ["approved", "rejected"])
    dry_run_decision: str = "approved"


class ControlAccess(_Strict):
    read: list[str] = Field(default_factory=list)
    write: list[str] = Field(default_factory=list)
    lock_on_approval: list[str] = Field(default_factory=list)
    # For a document with several writers: the "## " sections this node owns ("_preamble" = title and TL;DR).
    # Only owned sections are taken from a submission; every other section keeps its accepted text.
    sections: dict[str, list[str]] = Field(default_factory=dict)


class RunSpec(_Strict):
    tool: str | None = None        # "module:function" under pdg.tools: the tool node, review pre-check or gate hook
    command_hook: bool = False     # the project may bind a shell command (build, test) that runs after submission


class NodeDef(_Strict):
    id: str
    num: int
    name: str
    lifecycle_step: str
    phase: str
    stage: str
    subgraph: str
    kind: NodeKind
    purpose: str
    depends_on: list[str]
    inputs: list[str]
    context: list[str]
    state_read: list[str]
    state_write: list[str]
    agent: str                     # the responsible (lead) agent: it receives the task packet
    support_agents: list[str] = Field(default_factory=list)   # consulted by the lead; never addressed by the engine
    skills: list[str]
    tools: list[str]
    instructions: str
    prompt: str
    outputs: list[OutputSpec]
    completion: list[Check]
    evaluation: list[str]          # rubric ids scored at this node
    failure_conditions: list[str]
    retry: RetryPolicy
    escalation: EscalationPolicy
    human_review: HumanReview
    provenance: list[str]
    controls: ControlAccess = Field(default_factory=ControlAccess)
    resources: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=lambda: ["pass"])
    run: RunSpec | None = None
    gate: str | None = None        # engine hook: freeze_inputs | review_gate | regeneration_plan | release | learning


class EdgeDef(_Strict):
    id: str
    source: str = Field(alias="from")
    target: str = Field(alias="to")
    kind: EdgeKind
    transition: Literal["deterministic", "conditional"]
    when: str
    transfers: list[str]
    threshold: str
    behavior: str                  # branch / retry / rollback / approval behaviour
    max_traversals: int | None = None


class Subgraph(_Strict):
    id: str
    name: str
    pattern: str
    purpose: str
    nodes: list[str]


class Policies(_Strict):
    max_rework_cycles: int = Field(ge=1)
    max_same_defect_failures: int = Field(ge=1)
    parallel_limit: int = Field(ge=1)
    single_flight_resources: list[str]
    blocking_severities: list[str]
    dry_run_actor: str
    human_actors: list[str]
    regeneration_targets: list[str]
    schema_version: str = "pdg-state/v1"


class Workflow(_Strict):
    id: str
    name: str
    version: str
    description: str
    start: str = "START"
    end: str = "END"
    policies: Policies
    subgraphs: list[Subgraph]
    nodes: list[NodeDef]
    edges: list[EdgeDef]

    def node(self, node_id: str) -> NodeDef:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(node_id)


# --------------------------------------------------------------------------------------------------- shared state


class NodeStatus(str, Enum):
    # Names follow Workflow OS / vpg where the meaning is the same.
    PLANNED = "PLANNED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_AGENT = "WAITING_AGENT"   # a task packet was issued; waiting for the agent's submission
    WAITING_HUMAN = "WAITING_HUMAN"   # validated; waiting for a named human decision
    VALIDATING = "VALIDATING"
    PASSED = "PASSED"
    ITERATE = "ITERATE"               # completion failed; re-dispatched with the failures as context
    STALE = "STALE"                   # invalidated by rework or a change request; re-checked by fingerprint
    BLOCKED = "BLOCKED"               # escalated to a human; the run stops instead of burning attempts


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    WAITING_AGENT = "WAITING_AGENT"
    WAITING_HUMAN = "WAITING_HUMAN"
    BLOCKED = "BLOCKED"
    RUN_PASS = "RUN_PASS"


class ProjectInfo(_Strict):
    id: str
    name: str
    created: str
    workflow_id: str
    workflow_version: str


class GapWaiver(_Strict):
    gap: str
    by: str
    reason: str
    at: str


class InputsState(_Strict):
    brief: str = ""
    sources: list[Source] = Field(default_factory=list)
    frozen: bool = False
    inputs_sha256: str | None = None
    waivers: list[GapWaiver] = Field(default_factory=list)


class ProductState(_Strict):
    objective: str = ""
    value_proposition: str = ""
    customer_context: str = ""
    users: list[str] = Field(default_factory=list)
    problem: ProblemFrame | None = None
    requirements: list[Requirement] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    scope: Scope | None = None
    success_criteria: list[Metric] = Field(default_factory=list)
    rollback_triggers: list[str] = Field(default_factory=list)


class ValidationFinding(_Strict):
    at_version: int
    participants: int
    simulated: bool
    task_success_rate: float
    mean_seq: float | None = None
    summary: str


class ResearchState(_Strict):
    evidence: list[Evidence] = Field(default_factory=list)
    insights: list[Insight] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    validation_findings: list[ValidationFinding] = Field(default_factory=list)


class DesignState(_Strict):
    criteria: list[Criterion] = Field(default_factory=list)
    concepts: list[Concept] = Field(default_factory=list)
    selected_concept: str | None = None
    journeys: list[Journey] = Field(default_factory=list)
    screens: list[Screen] = Field(default_factory=list)
    flows: list[Flow] = Field(default_factory=list)
    interactions: InteractionDoc | None = None
    system: DesignSystemDoc | None = None


class PrototypeRef(_Strict):
    version: int
    artifact: str                  # artifact id of the prototype dir
    entry: str                     # project-relative path of the entry file
    sha256: str
    stack: list[str] = Field(default_factory=list)


class BuildState(_Strict):
    plan: PrototypePlan | None = None
    prototype: PrototypeRef | None = None
    version: int = 0               # increments every time n11 or n12 produce a new prototype
    code_artifacts: list[str] = Field(default_factory=list)
    content_artifacts: list[str] = Field(default_factory=list)


class ArtifactRecord(_Strict):
    id: str                        # <node>/<key>/a<attempt>
    key: str
    node: str
    attempt: int
    kind: str
    path: str                      # project-relative
    sha256: str
    bytes: int
    created: str
    inputs: list[str] = Field(default_factory=list)   # lineage: ids of the current artifacts the node read
    build_version: int = 0
    current: bool = True
    superseded_by: str | None = None


class DimensionResult(_Strict):
    id: str
    level: Literal["MUST", "SHOULD"]
    check: Literal["tool", "review", "human"]
    status: Literal["pass", "fail", "advisory_fail", "pending_human", "not_scored"]
    enforced: bool
    score: float | None = None
    by: str = ""
    evidence: str = ""
    detail: str = ""              # a compact tool-measure line (pairs, ratios, counts), when the tool supplied one


class FindingRecord(_Strict):
    node: str
    dimension: str
    severity: Literal["P1", "P2", "P3", "P4"]
    message: str
    evidence: str = ""
    location: str = ""
    by: str = "agent"
    traced_node: str | None = None
    smallest_fix: str = ""
    acceptance_check: str = ""
    blocking: bool = False
    reported_severity: Literal["P1", "P2", "P3", "P4"] | None = None   # the reviewer's or tool's own, when a finding
                                                                        # that does not block was stored as P4
    element: str = ""              # names one of several findings of a dimension at one location (field run W14)

    @property
    def signature(self) -> str:
        base = f"{self.dimension}@{self.location}" if self.location else self.dimension
        return f"{base}#{self.element}" if self.element else base


class ReviewRecord(_Strict):
    node: str
    attempt: int
    build_version: int
    dimensions: list[DimensionResult]
    findings: list[FindingRecord]
    overridden: list[str] = Field(default_factory=list)   # agent passes a tool MUST failure overrode (refused)
    passed: bool
    summary: str = ""
    at: str
    reviewer: str = ""                     # who reviewed, as the review states it (not verified)
    independent: bool | None = None        # the review's own claim that its reviewer produced none of the reviewed work
    no_longer_holds: list[str] = Field(default_factory=list)   # deferred defects it says this build no longer shows (W61)


class TestResult(_Strict):
    node: str
    suite: str
    build_version: int
    passed: int
    failed: int
    details: str
    at: str


class Feedback(_Strict):
    id: str
    actor: str
    human: bool
    simulated: bool = False
    text: str
    at: str = ""                   # where in the prototype (screen, state, viewport)
    severity: str = ""
    created: str
    build_version: int = 0
    status: Literal["open", "interpreted", "dismissed"] = "open"
    defect_ids: list[str] = Field(default_factory=list)
    recorded_by: str | None = None
    source: str = ""
    interprets: bool = False


class ClaimedFixed(_Strict):
    """Reviews asked to re-verify a deferred defect said it no longer holds, and no current review reports it (W61)."""
    at: int                                                # the build they said it at
    by: list[str]                                          # the reviews that said so
    silent: list[str] = Field(default_factory=list)        # reviews also asked, which filed nothing about it


class Defect(_Strict):
    id: str
    signature: str
    dimension: str
    severity: Literal["P1", "P2", "P3", "P4"]
    message: str
    evidence: str
    traced_node: str
    trace_reason: str
    artifact_key: str | None = None
    smallest_fix: str
    acceptance_check: str
    source_nodes: list[str] = Field(default_factory=list)
    feedback_ids: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)      # other signatures its findings used: one bug, one identity (W28)
    deferred: str = ""                  # why it waits on a human decision; set, the gate neither routes nor resolves it (W39)
    deferred_by: str = ""
    deferred_trigger: str = ""          # what brings it back: the decision or event that ends the wait
    claimed_fixed: ClaimedFixed | None = None   # deferred, and its reviews said it no longer holds: a person decides (W61)
    status: Literal["open", "in_rework", "resolved", "persisting", "needs_human", "dismissed"] = "open"
    failures: int = 0              # failed corrections of this signature
    opened_at_version: int = 0
    rework_version: int | None = None   # the build when its latest rework started: a correction needs a newer one
    # attempt of the node that owns the fix and of each reviewer that found it, when the defect was last seen or its
    # correction started: a correction counts once they have all re-run past these (empty: recorded before this existed)
    attempts_at_start: dict[str, int] = Field(default_factory=dict)
    resolved_at_version: int | None = None
    history: list[str] = Field(default_factory=list)


class GateResult(_Strict):
    node: str
    cycle: int
    build_version: int
    outcome: Literal["pass", "rework", "blocked"]
    reasons: list[str]
    blocking_defects: list[str]
    targets: list[str]
    at: str
    answered: list[dict[str, str]] = Field(default_factory=list)   # findings the interpreter answered as not a defect
    raised: list[str] = Field(default_factory=list)          # reviewer P1–P3 findings stored advisory, raised to a defect
    kept_advisory: list[str] = Field(default_factory=list)   # the same kind of finding, kept advisory (field run W25)


class Comparison(_Strict):
    cycle: int
    targets: list[str]
    before_version: int
    after_version: int
    before: dict[str, str]         # artifact key → sha256, before the rework
    after: dict[str, str]
    resolved: list[str]
    persisting: list[str]
    new: list[str]
    verdict: Literal["improved", "unchanged", "regressed"]
    at: str
    plan: str = ""                 # the regeneration plan's artifact id: unique across budget resets (field run W38)


class EvaluationState(_Strict):
    reviews: list[ReviewRecord] = Field(default_factory=list)
    test_results: list[TestResult] = Field(default_factory=list)
    feedback: list[Feedback] = Field(default_factory=list)
    defects: list[Defect] = Field(default_factory=list)
    gates: list[GateResult] = Field(default_factory=list)
    comparisons: list[Comparison] = Field(default_factory=list)


class Decision(_Strict):
    id: str
    node: str
    what: str
    light: Literal["green", "yellow", "red"]
    owner: str
    rationale: str
    trigger: str = ""
    expiry: str = ""
    evidence: list[str] = Field(default_factory=list)
    at: str


class Approval(_Strict):
    node: str
    decision: str
    actor: str
    human: bool                    # False for dry-run auto decisions: never presented as a human approval
    on_behalf_of: str | None = None
    delegation: str | None = None
    reason: str
    at: str
    build_version: int = 0
    locked: list[str] = Field(default_factory=list)
    outputs: dict[str, str] = Field(default_factory=dict)   # output key → sha256 approved (a control output: its document)
    recorded_by: str | None = None
    source: str = ""
    interprets: bool = False


class CheckpointRef(_Strict):
    seq: int
    event: str
    node: str | None
    path: str
    at: str


class ChangeRequest(_Strict):
    id: str
    doc: str
    reason: str
    by: str
    human: bool
    on_behalf_of: str | None = None
    delegation: str | None = None
    status: Literal["open", "approved", "applied", "declined"]
    writer: str | None = None
    at: str
    reruns: list[str] = Field(default_factory=list)   # what approving it re-runs: the writer and its descendants (N-05)
    gates: list[str] = Field(default_factory=list)    # the human gates among them, which will ask again
    decided_by: str | None = None                     # who approved or declined an agent's request (N-04)
    decision_reason: str = ""
    recorded_by: str | None = None
    source: str = ""
    interprets: bool = False


DelegationScope = Literal["decide", "change_request", "unblock", "accept_config", "invalidate", "accept_risk"]


class Delegation(_Strict):
    id: str
    by: str
    instruction: str
    scope: list[DelegationScope] = Field(default_factory=list)
    nodes: list[str] = Field(default_factory=list)          # decide only: the gates it may decide
    except_nodes: list[str] = Field(default_factory=list)   # every action: nodes it never covers
    agent: str
    created: str
    expires: str
    revoked_at: str | None = None
    revoked_by: str | None = None
    recorded_by: str | None = None     # who typed the grant: the human, or the agent transcribing their words (None: unstated)
    source: str = ""                   # where the human's words came from, when an agent transcribed them
    budget_resets: int | None = None   # rework-budget resets an unblock under it may make; None: not limited (W59, D12)
    include_release: bool = False      # true only when Wei explicitly lets this grant decide n18_final_verification


class Revision(_Strict):
    node: str
    attempt: int
    reason: Literal["retry", "rework", "loop", "change_request", "resume", "invalidate"]
    detail: str
    at: str


class RiskAcceptance(_Strict):
    """A named human accepts building past an unvalidated riskiest assumption (`pdg accept-risk`)."""
    assumption: str
    actor: str
    on_behalf_of: str | None = None
    delegation: str | None = None
    reason: str
    at: str
    build_version: int = 0
    statement_sha256: str = ""
    recorded_by: str | None = None
    source: str = ""
    interprets: bool = False


class Ratification(_Strict):
    """A named human confirms or reverses a delegated/transcribed action after the fact."""
    target: str
    actor: str
    reason: str
    at: str
    reverse: bool = False


class HistoryState(_Strict):
    decisions: list[Decision] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)
    checkpoints: list[CheckpointRef] = Field(default_factory=list)
    change_requests: list[ChangeRequest] = Field(default_factory=list)
    delegations: list[Delegation] = Field(default_factory=list)
    risk_acceptances: list[RiskAcceptance] = Field(default_factory=list)
    ratifications: list[Ratification] = Field(default_factory=list)
    revisions: list[Revision] = Field(default_factory=list)
    versions: list[dict[str, Any]] = Field(default_factory=list)   # build versions: {version, node, attempt, sha256, at}


class KnowledgeState(_Strict):
    rules_path: str = ""
    rules_version: str = ""
    rules_sha256: str = ""
    enforced: list[str] = Field(default_factory=list)
    advisory: list[str] = Field(default_factory=list)
    lessons: list[Lesson] = Field(default_factory=list)
    proposal: str | None = None    # artifact id of the learning proposal


class Escalation(_Strict):
    id: str
    node: str
    reason: str
    report: str
    at: str
    open: bool = True
    resolved_by: str | None = None
    resolved_at: str | None = None


class PassedChecks(_Strict):
    """The code and the configuration a node's tool checks ran with when it passed: a later change to either is a check
    upgrade its verdict never saw (field run W65)."""
    code: str
    config: str
    git_state: dict[str, Any] | None = None
    recheckable: bool = True   # `pdg recheck-release` can re-run its checks: a gate's are its decision, not re-run


class NodeRuntime(_Strict):
    status: NodeStatus = NodeStatus.PLANNED
    attempt: int = 0               # attempts started
    streak: int = 0                # consecutive failed attempts (reset on pass)
    interruptions: int = 0
    outcome: str | None = None
    token: str | None = None
    fingerprint: str | None = None
    passed_fingerprint: str | None = None
    passed_judging: str | None = None   # how it was judged at its pass: rubric entries, rule states, thresholds (B-03)
    executed: bool = False
    failures: list[str] = Field(default_factory=list)
    rework: list[str] = Field(default_factory=list)       # defect ids this node must fix on its next attempt
    force_rerun: bool = False
    started_at: str | None = None
    finished_at: str | None = None
    duration_s: float | None = None
    memo_hits: int = 0
    rerun_reason: str = ""         # why a node that passed runs again: its own invalidation or an upstream one
    passed_attempt: int = 0        # the attempt that last passed (its outputs are what a re-run starts from)
    passed_checks: PassedChecks | None = None   # a node with tool checks: the code and configuration they ran with (W65)
    judged_checks: PassedChecks | None = None   # the same, for the attempt waiting for a person: its record once approved
    passed_controls: dict[str, int] = Field(default_factory=dict)   # control document → version when the node last passed
    gate_note: str = ""            # a gate asked again: what changed since its last approval
    parked: dict[str, Any] | None = None   # a submission refused while the run was blocked: kept, never judged (W42)
    carried: dict[str, Any] | None = None  # a parked submission withdrawn before it was judged: its files, for the next
                                          # attempt's packet (batch 7 review I1)
    rejudge: dict[str, Any] | None = None  # set by accept-config: what changed in how it is judged, what its last output fails (W43)
    passed_dims: list[str] = Field(default_factory=list)   # the dimensions it passed under (id, level, check, threshold)
    # how it was judged when its current packet was issued: a node out with an agent is re-issued at accept-config only
    # when that moved (config batch 5 review I-A)
    issued_judging: str | None = None
    issued_dims: list[str] = Field(default_factory=list)
    tool_details: list[str] = Field(default_factory=list)


class LedgerBreak(_Strict):
    """A loss of ledger events that a named human accepted because no backup existed (`pdg accept-ledger-break`)."""
    actor: str
    reason: str
    at: str
    lost_after_seq: int            # the last event still in the ledger; 0 when the ledger was rewritten (none verifiable)
    recorded_seq: int = 0          # the last event the state had recorded
    lost_hash: str                 # first 16 hex digits of that recorded event's hash
    problem: str                   # what the engine found
    resumes_at_seq: int            # the first event written after the acceptance
    rechained: int = 0             # events of the last human action written again after the break (their chain was lost)

    def describe(self) -> str:
        what = (f"events {self.lost_after_seq + 1}–{self.recorded_seq} were lost" if self.lost_after_seq
                else f"the ledger was rewritten, so no event up to {self.recorded_seq} can be verified against the state")
        return what + (f"; {self.rechained} event(s) of the last human action were written again after the break"
                       if self.rechained else "")


class RuntimeState(_Strict):
    status: RunStatus = RunStatus.RUNNING
    nodes: dict[str, NodeRuntime] = Field(default_factory=dict)
    loop_traversals: dict[str, int] = Field(default_factory=dict)
    batches: int = 0
    rework_cycles: int = 0
    planned_gate: int = 0          # how many gates there were when the last rework cycle was counted (field run W24)
    escalations: list[Escalation] = Field(default_factory=list)
    config_sha256: str = ""
    config_parts: dict[str, str] = Field(default_factory=dict)   # file → sha256 behind config_sha256, to name a drift
    code_parts: dict[str, str] = Field(default_factory=dict)     # package source → sha256: which code judged the run

    dry_run: bool = False
    ledger_tail: list[Any] = Field(default_factory=list)       # [seq, hash] of the last ledger event when the state was saved
    pending_ledger: list[str] = Field(default_factory=list)    # write-ahead: a human action's events, committed with the state
    ledger_breaks: list[LedgerBreak] = Field(default_factory=list)


class ControlVersion(_Strict):
    version: int
    sha256: str
    node: str
    at: str
    archived: str                  # project-relative path of the archived copy
    attempt: int = 0               # the writer's attempt (0: recorded before attempts were kept, or the template)


class ControlRecord(_Strict):
    doc: str
    status: Literal["template", "accepted", "locked"] = "template"
    version: int = 0
    accepted_sha256: str | None = None
    locked_by: str | None = None   # "<node> by <actor>"
    locked_node: str | None = None # the gate that locked it; its own re-run may rewrite it, then needs re-approval
    unlocked_for: str | None = None
    unlocked_for_nodes: list[str] = Field(default_factory=list)
    history: list[ControlVersion] = Field(default_factory=list)


class ProjectState(_Strict):
    schema_version: str
    project: ProjectInfo
    inputs: InputsState = Field(default_factory=InputsState)
    product: ProductState = Field(default_factory=ProductState)
    research: ResearchState = Field(default_factory=ResearchState)
    design: DesignState = Field(default_factory=DesignState)
    build: BuildState = Field(default_factory=BuildState)
    artifacts: dict[str, ArtifactRecord] = Field(default_factory=dict)
    evaluation: EvaluationState = Field(default_factory=EvaluationState)
    history: HistoryState = Field(default_factory=HistoryState)
    knowledge: KnowledgeState = Field(default_factory=KnowledgeState)
    runtime: RuntimeState = Field(default_factory=RuntimeState)
    controls: dict[str, ControlRecord] = Field(default_factory=dict)


# Append-only collections: the engine appends to them in its serial commit phase, so parallel writers never collide
# (the role reducers play in LangGraph). Only overwrite paths count as batch conflicts.
REDUCER_PATHS = {"evaluation.reviews", "evaluation.test_results", "evaluation.feedback", "research.validation_findings",
                 "history.decisions", "history.versions", "history.revisions", "history.delegations",
                 "build.code_artifacts", "build.content_artifacts"}

# The fourteen state items the brief requires (§5), mapped to where they live. `docs --check` and a test keep this
# mapping true: every path must exist in the model.
STATE_ITEMS: dict[str, list[str]] = {
    "Product objective": ["product.objective", "product.value_proposition"],
    "Customer and user context": ["product.customer_context", "product.users", "product.problem"],
    "Source evidence": ["inputs.sources", "research.evidence", "research.insights"],
    "Assumptions and open questions": ["research.assumptions", "research.open_questions", "research.missing"],
    "Requirements and constraints": ["product.requirements", "product.constraints"],
    "Product scope": ["product.scope", "product.success_criteria", "product.rollback_triggers"],
    "Concepts and decisions": ["design.criteria", "design.concepts", "design.selected_concept", "history.decisions"],
    "User journeys and flows": ["design.journeys", "design.screens", "design.flows"],
    "Design specifications": ["design.interactions", "design.system"],
    "Prototype and code artifacts": ["build.plan", "build.prototype", "build.code_artifacts", "build.content_artifacts",
                                     "artifacts"],
    "Test results and feedback": ["evaluation.reviews", "evaluation.test_results", "evaluation.feedback",
                                  "research.validation_findings"],
    "Defects and revision history": ["evaluation.defects", "evaluation.gates", "evaluation.comparisons",
                                     "history.revisions", "history.versions"],
    "Approvals and checkpoints": ["history.approvals", "history.checkpoints", "history.change_requests",
                                  "history.delegations", "history.risk_acceptances"],
    "Reusable lessons": ["knowledge.lessons", "knowledge.rules_version", "knowledge.enforced"],
}
