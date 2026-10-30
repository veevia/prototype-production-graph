"""N01: the source registry."""

from __future__ import annotations


from ..artifacts import SourcesDoc
from ..context import CheckResult, NodeContext


def check_registry(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = SourcesDoc.model_validate(ctx.json("sources"))
    root = ctx.project
    problems = []
    if not any(s.kind == "brief" for s in doc.sources):
        problems.append("no brief registered")
    ids = [s.id for s in doc.sources]
    if len(ids) != len(set(ids)):
        problems.append("duplicate source ids")
    for s in doc.sources:
        if not s.path and not s.url:
            problems.append(f"{s.id}: neither a path nor a URL")
        if s.path:
            p = (root / s.path).resolve()
            try:
                p.relative_to(root)
            except ValueError:
                problems.append(f"{s.id}: {s.path} lies outside the project")
                continue
            if not p.exists():
                problems.append(f"{s.id}: {s.path} does not exist")
    res.dim("EVD-SOURCES", not problems, f"{len(doc.sources)} sources" + (f"; {'; '.join(problems)}" if problems else
            ", all tagged and present"))
    return res
