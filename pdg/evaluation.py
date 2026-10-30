"""Evaluation: rubrics, rule-governed enforcement, review merging, the tri-state gate and before/after comparison.

Deterministic tools measure; agents judge only what tools cannot; named humans decide taste, validation and release.
A dimension's rule (knowledge/rules.json) decides whether it blocks:
  adopted | monitored      → enforced at its declared level (a failed MUST blocks)
  validated | approved     → advisory (reported, never blocking)
  candidate | revised | retired → informational
A tool failure on an enforced MUST dimension cannot be overridden by an agent's score.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .artifacts import ReviewDoc
from .context import CheckResult
from .models import DimensionResult, FindingRecord, NodeDef, ReviewRecord
from .util import PKG_ROOT, now

ENFORCED_STATES = {"adopted", "monitored"}
ADVISORY_STATES = {"validated", "approved"}


def load_rubrics(root: Path = PKG_ROOT) -> dict[str, dict[str, Any]]:
    out = {}
    for p in sorted((root / "rubrics").glob("*.yaml")):
        rub = yaml.safe_load(p.read_text())
        out[rub["id"]] = rub
    return out


def dimension_index(rubrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for rid, rub in rubrics.items():
        for d in rub.get("dimensions", []):
            idx[d["id"]] = {**d, "rubric": rid}
    return idx


def node_dimensions(node: NodeDef, rubrics: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    dims: list[dict[str, Any]] = []
    for r in node.evaluation:
        dims += [{**d, "rubric": r} for d in rubrics.get(r, {}).get("dimensions", [])]
    return dims


def mode_for(dim: dict[str, Any], rule_states: dict[str, str]) -> str:
    state = rule_states.get(dim.get("rule", ""), "candidate")
    if state in ENFORCED_STATES:
        return "enforced"
    if state in ADVISORY_STATES:
        return "advisory"
    return "informational"


def can_fail(dim: dict[str, Any], rule_states: dict[str, str]) -> bool:
    """Whether a dimension can keep its node from passing: a MUST under an enforced rule, or a MUST review or human
    dimension under any rule, since the node's completion asks for it to be scored or decided (config batch 5 review I5)."""
    return dim.get("level") == "MUST" and (mode_for(dim, rule_states) == "enforced"
                                           or dim.get("check", {}).get("type") in ("review", "human"))


def _finding(node: str, dim: dict[str, Any], f: dict[str, Any], blocking: bool, severity: str | None = None) -> FindingRecord:
    stated = f.get("severity", "P3")
    return FindingRecord(node=node, dimension=dim["id"], severity=severity or stated,
                         message=f.get("message", dim.get("name", dim["id"])), evidence=f.get("evidence", ""),
                         location=f.get("location", ""), by=f.get("by", "tool"), traced_node=f.get("traced_node"),
                         smallest_fix=f.get("smallest_fix", ""), acceptance_check=f.get("acceptance_check", ""),
                         blocking=blocking, reported_severity=_lowered(stated, severity), element=f.get("element") or "")


def _lowered(stated: Any, stored: str | None) -> str | None:
    """The finder's own severity when a non-blocking finding is stored as P4, so the diagnoser and the release evidence
    still see what the reviewer or tool meant (P4 alone decides that it does not block)."""
    return stated if stored == "P4" and stated in ("P1", "P2", "P3") else None


def _raise(sev: str) -> str:
    return "P3" if sev == "P4" else sev


def evaluate_tool_dims(node: NodeDef, results: dict[str, CheckResult], rubrics: dict[str, dict[str, Any]],
                       rule_states: dict[str, str], only: set[str] | None = None,
                       ) -> tuple[list[DimensionResult], list[FindingRecord], list[str]]:
    """Score every tool dimension of the node's rubrics from the check results. Returns (records, findings, blocking
    messages). A tool dimension whose fn ran but did not report it is a tool defect, recorded as not_scored. `only`
    limits the scoring to those dimension ids."""
    records: list[DimensionResult] = []
    findings: list[FindingRecord] = []
    blocking: list[str] = []
    for dim in node_dimensions(node, rubrics):
        check = dim.get("check", {})
        if check.get("type") != "tool" or (only is not None and dim["id"] not in only):
            continue
        mode = mode_for(dim, rule_states)
        res = results.get(check.get("fn", ""))
        outcome = res.dimensions.get(dim["id"]) if res else None
        if outcome is None:
            records.append(DimensionResult(id=dim["id"], level=dim["level"], check="tool", status="not_scored",
                                           enforced=mode == "enforced", by=check.get("fn", ""),
                                           evidence="the tool did not report this dimension",
                                           detail="the tool did not report this dimension"))
            continue
        enforced_must = mode == "enforced" and dim["level"] == "MUST"
        if outcome.passed:
            status = "pass"
        else:
            status = "fail" if enforced_must else "advisory_fail"
            fs = outcome.findings or [{"message": f"{dim['id']} failed: {outcome.evidence}", "severity": "P3"}]
            for f in fs:
                sev = _raise(f.get("severity", "P3")) if enforced_must else "P4"
                findings.append(_finding(node.id, dim, {**f, "by": "tool"}, blocking=enforced_must, severity=sev))
            if enforced_must:
                blocking.append(f"{dim['id']} ({dim['name']}): {outcome.evidence}")
        records.append(DimensionResult(id=dim["id"], level=dim["level"], check="tool", status=status,
                                       enforced=mode == "enforced", by=check.get("fn", ""), evidence=outcome.evidence,
                                       detail=outcome.evidence))
    return records, findings, blocking


def unreported_tool_dims(node: NodeDef, results: dict[str, CheckResult], rubrics: dict[str, dict[str, Any]],
                         rule_states: dict[str, str]) -> list[str]:
    """Enforced MUST tool dimensions whose check ran but did not report them. A check that skips a dimension is a tool
    defect, not a design defect: the attempt fails (never a silent pass), and after its retries a human fixes the tool."""
    out = []
    for dim in node_dimensions(node, rubrics):
        check = dim.get("check", {})
        if check.get("type") != "tool" or dim.get("level") != "MUST" or mode_for(dim, rule_states) != "enforced":
            continue
        res = results.get(check.get("fn", ""))
        if res is not None and dim["id"] not in res.dimensions:
            out.append(f"{dim['id']} ({dim['name']}): {check.get('fn')} ran but did not report it (a tool defect; an "
                       "unmeasured MUST is never a pass)")
    return out


def missing_review_dims(node: NodeDef, rubrics: dict[str, dict[str, Any]], review: dict[str, Any] | None) -> list[str]:
    scored = {d["id"] for d in (review or {}).get("dimensions", []) if d.get("score") is not None or d.get("passed") is not None}
    return [d["id"] for d in node_dimensions(node, rubrics)
            if d.get("check", {}).get("type") == "review" and d["level"] == "MUST" and d["id"] not in scored]


def merge_review(node: NodeDef, attempt: int, build_version: int, tool_results: dict[str, CheckResult],
                 agent_review: dict[str, Any] | None, rubrics: dict[str, dict[str, Any]], rule_states: dict[str, str],
                 threshold: float, extra_findings: list[dict[str, Any]] | None = None) -> ReviewRecord:
    records, findings, _ = evaluate_tool_dims(node, tool_results, rubrics, rule_states)
    tool_failed = {r.id for r in records if r.status == "fail"}
    doc = ReviewDoc.model_validate(agent_review) if agent_review else None
    scores = {d.id: d for d in (doc.dimensions if doc else [])}
    overridden = [d for d in scores if d in tool_failed and (scores[d].passed or (scores[d].score or 0) >= threshold)]
    agent_findings = list(doc.findings if doc else []) + [f for f in (extra_findings or [])]
    covered_dims = set()
    for dim in node_dimensions(node, rubrics):
        ctype = dim.get("check", {}).get("type")
        if ctype == "tool":
            continue
        mode = mode_for(dim, rule_states)
        if ctype == "human":
            records.append(DimensionResult(id=dim["id"], level=dim["level"], check="human", status="pending_human",
                                           enforced=mode == "enforced", by="a named human",
                                           evidence="decided by a named human; never scored by an agent"))
            continue
        s = scores.get(dim["id"])
        if s is None or (s.score is None and s.passed is None):
            records.append(DimensionResult(id=dim["id"], level=dim["level"], check="review", status="not_scored",
                                           enforced=mode == "enforced", by=node.agent))
            continue
        # a score decides: `passed: true` never lifts a score below the pass mark, and `passed: false` always fails
        passed = (s.score is None or s.score >= threshold) and s.passed is not False
        enforced_must = mode == "enforced" and dim["level"] == "MUST"
        status = "pass" if passed else ("fail" if enforced_must else "advisory_fail")
        records.append(DimensionResult(id=dim["id"], level=dim["level"], check="review", status=status,
                                       enforced=mode == "enforced", score=s.score, by=node.agent, evidence=s.evidence))
        if not passed:
            mine = [f for f in agent_findings if _get(f, "dimension") == dim["id"]]
            covered_dims.add(dim["id"])
            if not mine:
                mine = [{"message": f"{dim['id']} scored {s.score} < {threshold}: {s.notes or s.evidence}",
                         "severity": "P3", "evidence": s.evidence, "by": "agent"}]
            for f in mine:
                fd = f if isinstance(f, dict) else f.model_dump()
                sev = _raise(fd.get("severity", "P3")) if enforced_must else "P4"
                findings.append(_finding(node.id, dim, {**fd, "by": fd.get("by", "agent")}, blocking=enforced_must,
                                         severity=sev))
    known = {d["id"] for d in node_dimensions(node, rubrics)}
    for f in agent_findings:
        fd = f if isinstance(f, dict) else f.model_dump()
        if fd.get("dimension") in covered_dims:
            continue
        if fd.get("dimension") in known and fd.get("dimension") in tool_failed:
            continue  # the tool already filed its own findings for this dimension
        # a finding outside the rubric, or on a passing dimension: reported as advisory, never blocking
        findings.append(FindingRecord(node=node.id, dimension=fd.get("dimension", "ADVISORY"), severity="P4",
                                      message=fd.get("message", ""), evidence=fd.get("evidence", ""),
                                      location=fd.get("location", ""), by=fd.get("by", "agent"),
                                      traced_node=fd.get("traced_node"), smallest_fix=fd.get("smallest_fix", ""),
                                      acceptance_check=fd.get("acceptance_check", ""), blocking=False,
                                      reported_severity=_lowered(fd.get("severity"), "P4"), element=fd.get("element") or ""))
    passed = not any(r.status == "fail" for r in records)
    return ReviewRecord(node=node.id, attempt=attempt, build_version=build_version, dimensions=records,
                        findings=findings, overridden=overridden, passed=passed,
                        summary=(doc.summary if doc else "tool checks only"), at=now(),
                        reviewer=doc.reviewer.strip() if doc else "", independent=doc.independent if doc else None,
                        no_longer_holds=list(dict.fromkeys(x.strip() for x in doc.no_longer_holds if x.strip())) if doc else [])


def _get(f: Any, key: str) -> Any:
    return f.get(key) if isinstance(f, dict) else getattr(f, key, None)
