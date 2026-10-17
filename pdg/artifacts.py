"""Typed artifact documents: what each node produces, and the item models the shared state reuses.

One source of truth: the JSON schemas in `schemas/artifacts/` are generated from these models (`python -m pdg docs`),
agents read them in their task packets, and the engine validates every submitted JSON artifact against its model.
Field names are the product-design vocabulary of Wei's canonical templates (problem frame, POV, PRD, journey map,
design handoff, test plan, evidence brief): see `00_README/_templates/`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class _Doc(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


EvidenceTag = Literal["observed", "reported", "assumed"]
Light = Literal["green", "yellow", "red"]
Severity = Literal["P1", "P2", "P3", "P4"]


# ------------------------------------------------------------------------------------------------ context & research


class Source(_Doc):
    id: str
    kind: Literal["brief", "research", "interview", "survey", "analytics", "spec", "prototype", "recording",
                  "brand", "design-system", "feedback", "prior-version", "transcript", "data", "url", "other"]
    title: str
    path: str | None = None          # project-relative path (local sources are hashed and frozen at n02)
    url: str | None = None           # a cited remote reference (never fetched by the engine)
    evidence: EvidenceTag
    notes: str = ""
    sha256: str | None = None        # filled by n02
    bytes: int | None = None


class OpenQuestion(_Doc):
    id: str
    question: str
    blocking: bool = False
    owner: str = ""
    light: Light = "yellow"
    trigger: str = ""                # Traffic-Light discipline: a yellow needs a trigger and an expiry
    expiry: str = ""
    resolved: bool = False
    answer: str = ""


class Evidence(_Doc):
    id: str                          # E-xx; referenced by insights, requirements, decisions
    claim: str
    source_ids: list[str]
    tag: EvidenceTag
    quote: str = ""


class Insight(_Doc):
    id: str
    statement: str
    evidence_ids: list[str]
    confidence: Literal["high", "medium", "low"]


class Assumption(_Doc):
    id: str                          # A-xx
    statement: str
    importance: Literal["high", "medium", "low"]
    certainty: Literal["high", "medium", "low"]
    riskiest: bool = False
    validation: Literal["unvalidated", "validated", "invalidated", "accepted_risk"] = "unvalidated"
    evidence_ids: list[str] = Field(default_factory=list)
    accepted_by: str = ""            # a named human, only for accepted_risk


class Gap(_Doc):
    id: str
    severity: Literal["blocking", "resolvable", "note"]
    what: str
    resolve_by: str


class SourcesDoc(_Doc):
    sources: list[Source]
    open_questions: list[OpenQuestion] = Field(default_factory=list)


class EvidenceDoc(_Doc):
    evidence: list[Evidence]
    insights: list[Insight]
    assumptions: list[Assumption]
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)   # information asked for but not available: never invented


class GapReport(_Doc):
    gaps: list[Gap]
    sources: list[Source]


# ------------------------------------------------------------------------------------------------ problem & product


class Pain(_Doc):
    statement: str
    evidence_ids: list[str]


class Pov(_Doc):
    user: str
    need: str
    insight: str


class ProblemFrame(_Doc):
    problem_statement: str
    job: str                          # the job, one sentence (Understand → Design gate)
    primary_persona: str              # one sentence
    top_pain: Pain                    # with evidence
    opportunity: str
    pov: Pov
    how_might_we: list[str]
    decisions_to_enable: list[str]
    against: list[str] = Field(default_factory=list)   # who/what we design AGAINST (POV template §6)


class Requirement(_Doc):
    id: str                           # R-xx
    type: Literal["user", "business", "technical"]
    statement: str
    priority: Literal["P0", "P1", "P2"]
    evidence_ids: list[str] = Field(default_factory=list)
    assumption_ids: list[str] = Field(default_factory=list)
    acceptance: list[str] = Field(default_factory=list)


class Constraint(_Doc):
    id: str                           # C-xx
    type: Literal["business", "technical", "regulatory", "time", "design"]
    statement: str
    source: str


class RequirementsDoc(_Doc):
    requirements: list[Requirement]
    constraints: list[Constraint]


class Metric(_Doc):
    id: str                           # M-xx
    name: str
    kind: Literal["north_star", "supporting", "guardrail"]
    baseline: str
    target: str
    unit: str
    method: str


class Scope(_Doc):
    in_scope: list[str]
    out_of_scope: list[str]
    non_goals: list[str]


class ScopeDoc(_Doc):
    objective: str
    value_proposition: str
    scope: Scope
    success_criteria: list[Metric]
    rollback_triggers: list[str]
    open_questions: list[OpenQuestion] = Field(default_factory=list)
    light: Light


# ------------------------------------------------------------------------------------------------ concept


class Criterion(_Doc):
    id: str
    name: str
    weight: float
    requirement_ids: list[str] = Field(default_factory=list)


class Concept(_Doc):
    id: str
    name: str
    summary: str
    before: str
    after: str
    riskiest_assumption: str
    scores: dict[str, int]            # criterion id → 1..5


class ConceptsDoc(_Doc):
    criteria: list[Criterion]
    concepts: list[Concept]
    selected: str
    rationale: str
    light: Light
    disagreement: list[str] = Field(default_factory=list)   # real disagreement heard; never invented


# ------------------------------------------------------------------------------------------------ experience


class JourneyStage(_Doc):
    name: str
    doing: str
    pain: str = ""
    opportunity: str = ""


class Journey(_Doc):
    id: str
    persona: str
    job: str
    stages: list[JourneyStage]


class Screen(_Doc):
    id: str                           # stable screen id; the prototype marks it with data-screen="<id>"
    name: str
    purpose: str
    route: str
    parent: str | None = None
    kind: Literal["list", "record", "form", "dashboard", "other"] | None = None   # list = a collection that can be empty


class FlowStep(_Doc):
    screen: str
    action: str
    outcome: str


class Flow(_Doc):
    id: str                           # F-xx
    name: str
    requirement_ids: list[str]
    entry: str
    exit: str
    steps: list[FlowStep]


class ExperienceDoc(_Doc):
    journeys: list[Journey]
    screens: list[Screen]
    navigation: list[str]
    flows: list[Flow]
    system_behavior: list[str]


class Interaction(_Doc):
    id: str
    trigger: str
    response: str
    feedback: str
    keyboard: str


class ScreenSpec(_Doc):
    screen: str
    states: dict[str, str]            # state name (loading|empty|error|success|…) → what the user sees
    interactions: list[Interaction]
    validation: list[str] = Field(default_factory=list)


class InteractionDoc(_Doc):
    screens: list[ScreenSpec]
    focus_rules: list[str]
    feedback_rules: list[str]


# ------------------------------------------------------------------------------------------------ visual system


class ColorToken(_Doc):
    name: str
    value: str                        # #rrggbb
    role: str
    provenance: str
    # the components (by CSS class) whose current, selected or pressed state this colour fills on purpose, as the design
    # system documents it (a filter button's active fill): VIS-STATE-FILLS reads that state as documented (R2-26 addendum)
    state_fill_of: list[str] = Field(default_factory=list)


class TypeToken(_Doc):
    name: str
    size_px: float
    weight: int
    line_height: float


class ContrastPair(_Doc):
    fg: str                           # color token name
    bg: str
    use: str
    large_text: bool = False
    non_text: bool = False


class ComponentSpec(_Doc):
    name: str
    variants: list[str]
    states: list[str]


class DesignSystemDoc(_Doc):
    colors: list[ColorToken]
    type_scale: list[TypeToken]
    spacing_px: list[int]
    radii_px: list[int]
    contrast_pairs: list[ContrastPair]
    components: list[ComponentSpec]
    breakpoints_px: list[int]
    motion: list[str]
    prohibited: list[str]
    accessibility: list[str]


# ------------------------------------------------------------------------------------------------ prototype plan


class AssumptionCheck(_Doc):
    assumption_id: str
    status: Literal["validated", "accepted_risk", "unvalidated"]
    evidence_ids: list[str] = Field(default_factory=list)


class Alignment(_Doc):
    status: Literal["aligned", "pending"]
    with_whom: str
    evidence_ids: list[str] = Field(default_factory=list)


class ScenarioStep(_Doc):
    """One step of the browser scenario DSL executed by `pdg.tools.browser` (exactly one action per step)."""
    goto: str | None = None           # a route relative to the entry file, e.g. "#/queue" or "?fail=1#/queue";
                                      # only a scenario's first goto loads cold; a later one that changes only the
                                      # # route keeps the app's state (a ?query change or dropping the # loads
                                      # again), and one to the current URL returns to the top with focus released
    click: str | None = None          # CSS selector
    fill: list[str] | None = None     # [selector, text]
    press: str | None = None          # key name, sent to the focused element
    select: list[str] | None = None   # [selector, value]
    expect_visible: str | None = None
    expect_hidden: str | None = None
    expect_text: list[str] | None = None      # [selector, substring]
    expect_no_text: list[str] | None = None   # [selector, substring]: it matches, and no match shows the substring
    expect_count: list[Any] | None = None     # [selector, n]
    expect_disabled: str | None = None
    expect_enabled: str | None = None
    expect_route: str | None = None           # location.hash must equal this
    expect_focus: str | None = None           # document.activeElement must match this selector
    expect_in_viewport: str | None = None     # the element's top edge is inside the viewport without scrolling
    expect_reachable: str | None = None       # within one screen of scrolling from where the user is (N-18)
    reload: bool | None = None
    screenshot: str | None = None
    axe: str | None = None                    # run axe here, labelled

    @model_validator(mode="after")
    def exactly_one_action(self) -> "ScenarioStep":
        active = [name for name in type(self).model_fields if getattr(self, name) is not None]
        if len(active) != 1:
            got = ", ".join(active) if active else "none"
            raise ValueError(f"scenario step must set exactly one action/expectation field; got {len(active)} ({got})")
        return self


class Scenario(_Doc):
    id: str                           # S-xx
    flow_id: str
    name: str
    steps: list[ScenarioStep]
    success: str


class StateRecover(_Doc):
    """The way out of a state (R-UX-002: an empty state has a way back): the suite presses `click`, then expects the
    state to be gone (backlog B-09: a "Clear filters" with no handler passed every check)."""
    click: str                        # selector of the recovery control, e.g. "#clear-filters"
    expect_hidden: str | None = None  # what disappears once recovered; the state's marker when omitted


class StateCheck(_Doc):
    screen: str
    state: str
    route: str                        # how to reach the state
    marker: str                       # selector that proves the state rendered
    recover: StateRecover | None = None


class FocusTrace(_Doc):
    """Where the plan checks one of N08's focus rules (backlog N-22: a build broke two and passed, because no scenario
    checked them). Exactly one of: a scenario step that is an `expect_focus`, a browser check that covers the rule, or
    the reason it is out of scope for this prototype."""
    rule: str                         # the N08 focus rule, verbatim
    scenario: str | None = None       # S-xx
    step: int | None = None           # 1-based index of its `expect_focus` step
    covered_by: str | None = None     # A11Y-FOCUS or A11Y-FOCUS-VISIBLE-2411
    out_of_scope: str | None = None


class AcceptanceTrace(_Doc):
    """Where the plan checks one acceptance line of a requirement (field run 2, R2-18: a P1 naming rule never reached
    the plan, and every gate passed). Exactly one of: an expectation step, a `forbidden_text` entry, a check a later
    node runs, or the reason it is out of scope for this prototype."""
    requirement: str                  # R-xx
    acceptance: str                   # the acceptance line, verbatim
    scenario: str | None = None       # S-xx
    step: int | None = None           # 1-based index of an expectation step
    forbidden_text: str | None = None # an entry of the plan's forbidden_text (a "never shows X" line)
    covered_by: str | None = None     # a dimension id a node after the plan checks, e.g. FUNC-OFFLINE
    out_of_scope: str | None = None


class TestCriterion(_Doc):
    id: str
    metric: str
    threshold: str


class PrototypePlan(_Doc):
    goals: list[str]
    fidelity: Literal["low", "mid", "high"]
    fidelity_rationale: str
    riskiest_assumptions: list[AssumptionCheck]
    customer_alignment: Alignment
    scenarios: list[Scenario]
    states: list[StateCheck]
    viewports: list[int]
    content_needs: list[str]
    test_criteria: list[TestCriterion]
    out_of_scope: list[str]
    samples: dict[str, list[str]] = Field(default_factory=dict)   # screen id → more of its routes (worst-case records):
                                      # the width checks load them too, beside the records the suite finds linked (W53)
    forbidden_text: list[str] = Field(default_factory=list)   # text no screen or state may show: a "never shows X"
                                                               # acceptance, scanned on every page the suite opens (R2-04)
    focus_trace: list[FocusTrace] = Field(default_factory=list)   # each N08 focus rule, traced (N-22)
    acceptance_trace: list[AcceptanceTrace] = Field(default_factory=list)   # each P0/P1 acceptance line (N-25)


# ------------------------------------------------------------------------------------------------ build & content


class BuildManifest(_Doc):
    entry: str                        # path inside the prototype output dir, e.g. dist/prototype.html
    stack: list[str]
    files: dict[str, str]             # relative path → sha256
    screens: dict[str, str]           # screen id → selector proving it is implemented
    commands: dict[str, str] = Field(default_factory=dict)   # build/test commands, for the handoff
    unit_tests: str | None = None     # a node --test file relative to the prototype dir
    dataset: str | None = None        # the dataset embedded in this build
    unit_tests_dataset: str | None = None   # the dataset the unit tests read ("none": they read none); TEC-UNIT fails
                                            # when it is not `dataset`, so tests cannot stay green on another dataset
    overlays: list[str] = Field(default_factory=list)       # draft overlays applied (recorded, never hidden)
    build: str | None = None          # the build's content fingerprint


class Dataset(_Doc):
    path: str                         # relative to the prototype dir
    records: int
    provenance: Literal["real", "synthetic", "invented", "mixed"]   # mixed: some fields verified against a source
    verified_fields: list[str] = Field(default_factory=list)   # mixed only: the fields a reviewer holds to the source
    source_ids: list[str] = Field(default_factory=list)        # the S-xx / E-xx they were verified against
    generator: str = ""
    seed: int | None = None
    label_shown_in_ui: bool
    primary: str = ""                 # the list holding the records: a top-level key, or key[field=value] for one type;
                                      # empty: the longest top-level list (CNT-VOLUME's evidence names which it counted)

    @field_validator("verified_fields", "source_ids")
    @classmethod
    def _no_blanks(cls, v: list[str]) -> list[str]:
        v = [x.strip() for x in v]
        if not all(v):
            raise ValueError("a blank entry names nothing")
        return v

    @model_validator(mode="after")
    def _mixed_names_what_is_verified(self) -> "Dataset":
        if self.provenance == "mixed" and not (self.verified_fields and self.source_ids):
            raise ValueError("a mixed dataset names its verified_fields and the source_ids they were verified against")
        if self.verified_fields and self.provenance != "mixed":
            raise ValueError("verified_fields apply to a mixed dataset (a real one is verified whole)")
        return self


class ContentDoc(_Doc):
    datasets: list[Dataset]
    copy_deck: str                    # relative path of the copy deck inside the prototype dir
    edge_cases: list[str]             # which realistic edge cases the data exercises


# ------------------------------------------------------------------------------------------------ review & diagnosis


class DimensionScore(_Doc):
    id: str
    score: int | None = None          # 1..5 for review dimensions
    passed: bool | None = None        # for pass/fail dimensions
    evidence: str = ""
    notes: str = ""


class Finding(_Doc):
    dimension: str
    severity: Severity
    message: str
    evidence: str = ""
    location: str = ""                # screen / state / viewport / file
    element: str = ""                 # the element or selector, when one location has several findings of one dimension
    traced_node: str | None = None
    artifact_key: str | None = None
    smallest_fix: str = ""
    acceptance_check: str = ""
    by: Literal["tool", "agent", "human"] = "agent"
    participant: str = ""             # validation findings: the session participant who raised it


class ReviewDoc(_Doc):
    dimensions: list[DimensionScore]
    findings: list[Finding] = Field(default_factory=list)
    summary: str
    reviewer: str = ""                # who performed the review: e.g. "a design reviewer agent in its own context"
    independent: bool | None = None   # True: the reviewer produced none of the work under review (stated, not verified)
    build: str = ""                   # the sha256 (or a 12+ character prefix) of the build reviewed, from the packet (N-06)
    # deferred defects from the packet's re-verify list that this build no longer shows: a person decides on each. Filing
    # nothing about a deferred defect leaves it as it is (field run W61)
    no_longer_holds: list[str] = Field(default_factory=list)


class Task(_Doc):
    scenario_id: str
    success: bool
    time_s: float | None = None
    seq: int | None = None            # Single Ease Question, 1..7
    notes: str = ""


class Session(_Doc):
    participant: str                  # role + anonymised id, never a real name in reusable files
    role: str
    simulated: bool                   # True = scripted/simulated input: NOT user evidence
    tasks: list[Task]
    quotes: list[str] = Field(default_factory=list)


class ValidationDoc(_Doc):
    sessions: list[Session]
    findings: list[Finding] = Field(default_factory=list)
    summary: str


class DefectIn(_Doc):
    id: str
    signature: str                    # stable identity across versions: <dimension>@<location>
    dimension: str
    severity: Severity
    message: str
    evidence: str
    traced_node: str
    artifact_key: str | None = None
    trace_reason: str                 # requirement / design decision / node / implementation it traces to
    smallest_fix: str
    acceptance_check: str
    from_findings: list[str] = Field(default_factory=list)   # "<review node>:<dimension>@<location>"
    from_feedback: list[str] = Field(default_factory=list)   # feedback ids


class FeedbackMapping(_Doc):
    feedback_id: str
    defect_ids: list[str] = Field(default_factory=list)
    dismissed_reason: str = ""


class FindingAnswer(_Doc):
    """The interpreter's answer to a review finding that is not a defect (field run W22). Never a tool finding."""
    finding: str                      # node:signature of a current review finding
    reason: str                       # e.g. "not reproduced"
    evidence: str                     # what was checked, on which build, and what it showed
    checked_by: str                   # who checked: an agent:<role> or a named human


class Interpretation(_Doc):
    defects: list[DefectIn]
    feedback: list[FeedbackMapping] = Field(default_factory=list)
    answered_findings: list[FindingAnswer] = Field(default_factory=list)
    summary: str


# ------------------------------------------------------------------------------------------------ learning


class Lesson(_Doc):
    id: str
    statement: str
    scope: Literal["reusable", "project_specific"]
    evidence_class: Literal["verified", "inferred", "recommendation", "missing"]
    evidence: list[str]
    rule_id: str | None = None        # an existing rule it observes, or None for a new candidate
    helped: bool | None = None
    category: str | None = None       # the rule-base category a new candidate belongs to
    target_scope: str | None = None   # protected target such as requirements/evidence, or a reusable rule category


class LessonsDoc(_Doc):
    lessons: list[Lesson]
    summary: str


ARTIFACT_MODELS: dict[str, type[BaseModel]] = {
    "sources": SourcesDoc, "evidence": EvidenceDoc, "gaps": GapReport, "problem": ProblemFrame,
    "requirements": RequirementsDoc, "scope": ScopeDoc, "concepts": ConceptsDoc, "experience": ExperienceDoc,
    "interactions": InteractionDoc, "design-system": DesignSystemDoc, "plan": PrototypePlan,
    "build-manifest": BuildManifest, "content": ContentDoc, "review": ReviewDoc, "validation": ValidationDoc,
    "interpretation": Interpretation, "lessons": LessonsDoc,
}


def output_problems(spec: Any, path: str | Path) -> list[str]:
    """Why a file cannot be a node's declared output `spec`: the wrong kind, unreadable JSON, or a schema error. Empty
    when it can. `pdg submit` refuses these without using an attempt, and `pdg check-output` runs them beforehand."""
    path = Path(path)
    if spec.kind == "dir":
        return [] if path.is_dir() else [f"output '{spec.key}' must be a directory"]
    if not path.is_file():
        return [f"output '{spec.key}' must be a file"]
    if spec.kind != "json" and not spec.schema_name:
        return []
    try:
        data = json.loads(path.read_text())
        if spec.schema_name:
            ARTIFACT_MODELS[spec.schema_name].model_validate(data)
    except (ValueError, ValidationError) as exc:
        return [f"output '{spec.key}' fails schema '{spec.schema_name or 'json'}': {str(exc)[:600]}"]
    return []

