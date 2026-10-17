"""N02: evidence tags, and the deterministic review hook that hashes sources, finds gaps and decides the outcome."""

from __future__ import annotations

from ..artifacts import EvidenceDoc, Gap, GapReport, SourcesDoc
from ..context import CheckResult, NodeContext
from ..util import sha256_file, write_json_atomic


def check_tags(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = EvidenceDoc.model_validate(ctx.json("evidence"))
    src_ids = {s.id for s in ctx.state.inputs.sources}
    ev_ids = {e.id for e in doc.evidence}
    bad_src = [e.id for e in doc.evidence if not e.source_ids or any(s not in src_ids for s in e.source_ids)]
    bad_ins = [i.id for i in doc.insights if not i.evidence_ids or any(e not in ev_ids for e in i.evidence_ids)]
    res.dim("EVD-TAGS", not (bad_src or bad_ins) and bool(doc.evidence),
            f"{len(doc.evidence)} evidence items, {len(doc.insights)} insights"
            + (f"; unknown/empty sources: {bad_src}" if bad_src else "") + (f"; insights without evidence: {bad_ins}" if bad_ins else ""))
    riskiest = [a.id for a in doc.assumptions if a.riskiest]
    res.dim("EVD-RISKIEST", bool(doc.assumptions) and bool(riskiest),
            f"{len(doc.assumptions)} assumptions; riskiest: {riskiest or 'none flagged'}")
    unresolved = [q.id for q in doc.open_questions if not q.resolved]
    vague_missing = [m for m in doc.missing if m.strip().lower() in {"", "none", "n/a", "nothing"}]
    undeclared_questions = unresolved if unresolved and not doc.missing else []
    res.dim("EVD-MISSING", not vague_missing and not undeclared_questions,
            f"declared missing: {doc.missing or 'nothing'}"
            + (f"; unresolved questions not declared missing: {undeclared_questions}" if undeclared_questions else "")
            + (f"; vague missing entries: {vague_missing}" if vague_missing else ""))
    return res


def review(ctx: NodeContext) -> CheckResult:
    """Hash every local source; classify gaps; pass freezes the inputs (the engine records the hash)."""
    res = CheckResult()
    st = ctx.state
    sources = SourcesDoc.model_validate(ctx.json("sources")).sources if ctx.json("sources") else list(st.inputs.sources)
    ev = EvidenceDoc.model_validate(ctx.json("evidence"))
    gaps: list[Gap] = []
    hashed = []
    for s in sources:
        s = s.model_copy()
        if s.path:
            p = ctx.project / s.path
            if p.is_file():
                s.sha256, s.bytes = sha256_file(p), p.stat().st_size
            elif p.is_dir():
                from ..engine import tree_sha
                s.sha256, s.bytes = tree_sha(p)
            else:
                gaps.append(Gap(id=f"G-MISSING-{s.id}", severity="blocking", what=f"registered source {s.id} ({s.path}) is missing",
                                resolve_by="restore the file or remove it from the registry"))
        hashed.append(s)
    kinds = {s.kind for s in sources}
    if not st.inputs.brief.strip() and "brief" not in kinds:
        gaps.append(Gap(id="G-BRIEF", severity="blocking", what="no brief", resolve_by="write sources/brief.md"))
    if not kinds & {"research", "interview", "survey", "analytics", "feedback", "transcript"}:
        gaps.append(Gap(id="G-USER-EVIDENCE", severity="resolvable", what="no user evidence (research, interviews, surveys, analytics or feedback)",
                        resolve_by="register user research, or waive with a note if the product is a pure probe"))
    if not kinds & {"design-system", "brand"}:
        gaps.append(Gap(id="G-DESIGN-AUTHORITY", severity="resolvable", what="no design-system or brand authority",
                        resolve_by="register the design system or brand guide"))
    for q in ev.open_questions:
        if q.blocking and not q.resolved:
            gaps.append(Gap(id=f"G-Q-{q.id}", severity="blocking", what=f"blocking open question {q.id}: {q.question}",
                            resolve_by=f"{q.owner or 'Wei'} answers it"))
    waived = {w.gap for w in st.inputs.waivers}
    open_gaps = [g for g in gaps if g.id not in waived]
    report = GapReport(gaps=gaps, sources=hashed)
    path = ctx.out("gaps.json")
    write_json_atomic(path, report.model_dump(mode="json"))
    res.outputs["gaps"] = str(path)
    if any(g.severity == "blocking" for g in open_gaps):
        res.outcome = "gaps_blocking"
    elif any(g.severity == "resolvable" for g in open_gaps):
        res.outcome = "gaps_resolvable"
    else:
        res.outcome = "pass"
    res.data = {"sources": [s.model_dump(mode="json") for s in hashed], "gaps": [g.model_dump() for g in open_gaps],
                "report": [f"{g.id} ({g.severity}): {g.what} → {g.resolve_by}" for g in open_gaps] or ["no gaps"]}
    return res
