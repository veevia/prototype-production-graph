"""The contract between the engine and the work: what a node sees, what a tool check returns, what an execution yields."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .models import NodeDef, ProjectState

if TYPE_CHECKING:  # pragma: no cover
    from .engine import Engine


@dataclass
class DimOutcome:
    """A deterministic tool's verdict on one rubric dimension. The engine decides whether it blocks (rule lifecycle)."""

    passed: bool
    evidence: str = ""
    findings: list[dict[str, Any]] = field(default_factory=list)   # artifacts.Finding fields


@dataclass
class CheckResult:
    errors: list[str] = field(default_factory=list)          # structural problems: always blocking
    dimensions: dict[str, DimOutcome] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    outcome: str | None = None                                 # hooks that decide the node's outcome
    outputs: dict[str, str] = field(default_factory=dict)      # key → path written by a tool node or a pre-check
    own: set[str] = field(default_factory=set)                 # dims that judge the node's own artifact, not the build

    def dim(self, dim_id: str, passed: bool, evidence: str = "", findings: list[dict[str, Any]] | None = None,
            own: bool = False) -> None:
        """`own=True`: the dimension judges the node's own output (a label, a schema-like rule), not the prototype. On a
        review node, where a failing check is a finding about the build, an own-artifact MUST failure fails the attempt
        instead, so the node retries it itself (field run W35)."""
        if own:
            self.own.add(dim_id)
        cur = self.dimensions.get(dim_id)
        if cur is None:
            self.dimensions[dim_id] = DimOutcome(passed, evidence, list(findings or []))
        else:  # the same dimension checked in several places: it passes only if every check passed
            cur.passed = cur.passed and passed
            cur.evidence = "; ".join(x for x in (cur.evidence, evidence) if x)
            cur.findings += list(findings or [])

    def to_dict(self) -> dict[str, Any]:
        return {"errors": self.errors, "messages": self.messages, "data": self.data, "outcome": self.outcome,
                "outputs": self.outputs, "own": sorted(self.own),
                "dimensions": {k: {"passed": v.passed, "evidence": v.evidence, "findings": v.findings}
                               for k, v in self.dimensions.items()}}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CheckResult":
        return cls(errors=d.get("errors", []), messages=d.get("messages", []), data=d.get("data", {}),
                   outcome=d.get("outcome"), outputs=d.get("outputs", {}), own=set(d.get("own", [])),
                   dimensions={k: DimOutcome(v["passed"], v.get("evidence", ""), v.get("findings", []))
                               for k, v in d.get("dimensions", {}).items()})


@dataclass
class NodeResult:
    outputs: dict[str, str] = field(default_factory=dict)      # key → path (absolute, or relative to the work dir)
    review: dict[str, Any] | None = None                       # an agent's review document (review nodes)
    pending: bool = False                                      # a task packet was issued; the agent submits later
    decision: dict[str, Any] | None = None                     # a scripted human-gate decision (dry runs only)
    feedback: list[dict[str, Any]] = field(default_factory=list)   # scripted feedback items (dry runs only)
    actor: str = ""
    messages: list[str] = field(default_factory=list)


@dataclass
class NodeContext:
    engine: "Engine"
    node: NodeDef
    attempt: int
    work: Path
    token: str
    fingerprint: str
    submitted: dict[str, Path] = field(default_factory=dict)  # this attempt's registered outputs (after submission)
    precheck: CheckResult | None = None
    integrity: list[str] = field(default_factory=list)  # problems found before judging (they fail the attempt)

    @property
    def project(self) -> Path:
        return self.engine.project.root

    @property
    def state(self) -> ProjectState:
        return self.engine.state

    @property
    def thresholds(self) -> dict[str, Any]:
        return self.engine.thresholds()

    def out(self, name: str) -> Path:
        """A path inside this attempt's work directory, for files a tool writes."""
        p = self.work / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def output(self, key: str) -> Path | None:
        """This attempt's output for `key` (submitted, or written by the pre-check), else None."""
        if key in self.submitted:
            return self.submitted[key]
        if self.precheck and key in self.precheck.outputs:
            return Path(self.precheck.outputs[key])
        return None

    def artifact(self, key: str) -> Path | None:
        """The current artifact for `key` (this attempt's own output first, then the latest upstream one)."""
        own = self.output(key)
        if own is not None:
            return own
        recs = self.engine.current(key)
        return (self.project / recs[-1].path) if recs else None

    def json(self, key: str) -> Any:
        p = self.artifact(key)
        if p is None or not p.is_file():
            return None
        return json.loads(p.read_text())

    def control_text(self, doc: str) -> str:
        p = self.project / "controls" / f"{doc}.md"
        return p.read_text() if p.is_file() else ""
