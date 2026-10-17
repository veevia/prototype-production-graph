"""N16 interpretation drafting helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import Interpretation
from .engine_common import latest_reviews_by_node
from .evaluation import node_dimensions
from .gating import signatures
from .graph import load_workflow
from .models import ProjectState
from .util import read_json


def default_trace_node(eng, dimension: str) -> str:
    for node in eng.wf.nodes:
        for dim in node_dimensions(node, eng.rubrics):
            if dim.get("id") == dimension:
                return node.id
    return eng.idx.gate_node


def draft_interpretation(eng) -> dict[str, Any]:
    return {"defects": [], "feedback": [], "answered_findings": [], "summary": "Drafted from current reviews."}


def draft_sidecar(eng) -> dict[str, Any]:
    findings = []
    for review in eng.state.evaluation.reviews:
        if review.build_version != eng.state.build.version:
            continue
        for finding in review.findings:
            findings.append({
                "finding": f"{review.node}:{finding.signature}",
                "signature": finding.signature,
                "dimension": finding.dimension,
                "severity": finding.severity,
                "message": finding.message,
                "evidence": finding.evidence,
                "default_traced_node": finding.traced_node or default_trace_node(eng, finding.dimension),
                "blocking": finding.blocking,
            })
    current = {f["signature"] for f in findings} | {f["finding"].split(":", 1)[1] for f in findings}
    refailed = [{"id": d.id, "signature": d.signature, "aliases": sorted(d.aliases)}
                for d in eng.state.evaluation.defects if d.status == "resolved" and signatures(d) & current]
    return {"findings": findings, "refailed_resolved_defects": refailed,
            "answered_findings_slots": [{"finding": f["finding"], "reason": "", "evidence": "", "checked_by": ""}
                                       for f in findings]}


def write_draft(eng, path: Path) -> Path:
    doc = draft_interpretation(eng)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    path.with_suffix(".findings.json").write_text(json.dumps(draft_sidecar(eng), indent=2, ensure_ascii=False) + "\n")
    return path


def interpretation_gaps(project: Path, path: Path, workflow_path: str | Path | None = None) -> list[str]:
    interp = Interpretation.model_validate(json.loads(path.read_text()))
    state = ProjectState.model_validate(read_json(project / ".pdg" / "state.json"))
    wf = load_workflow(workflow_path)
    nodes = {n.id for n in wf.nodes}
    mapped = {m.feedback_id for m in interp.feedback if m.defect_ids or m.dismissed_reason}
    mapped |= {fid for d in interp.defects for fid in d.from_feedback}
    errs = [f"feedback {f.id} ('{f.text[:60]}') is neither mapped to a defect nor dismissed"
            for f in state.evaluation.feedback if f.status == "open" and f.id not in mapped]
    latest = latest_reviews_by_node(state.evaluation.reviews)
    current = {f"{r.node}:{f.signature}": f for r in latest.values()
               if r.build_version == state.build.version for f in r.findings}
    covered = {x for d in interp.defects for x in d.from_findings} | {d.signature for d in interp.defects}
    for a in interp.answered_findings:
        f = current.get(a.finding)
        if f is None:
            errs.append(f"answer to {a.finding}: no current finding has that node:signature")
        elif f.by == "tool":
            errs.append(f"answer to {a.finding}: a tool finding cannot be answered away; fix the build or the tool")
        elif not (a.evidence.strip() and a.checked_by.strip() and a.reason.strip()):
            errs.append(f"answer to {a.finding} needs its reason, its evidence and who checked")
        else:
            covered.add(a.finding)
    for key, f in current.items():
        if f.blocking and f.by != "tool" and key not in covered and f.signature not in covered:
            errs.append(f"blocking {f.by} finding {key} has no defect")
    for d in interp.defects:
        if d.traced_node not in nodes:
            errs.append(f"defect {d.id} traces to unknown node {d.traced_node}")
        if not d.smallest_fix.strip() or not d.acceptance_check.strip():
            errs.append(f"defect {d.id} needs a smallest fix and an acceptance check")
    return errs
