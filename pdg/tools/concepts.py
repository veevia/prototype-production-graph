"""N06: concept comparison."""

from __future__ import annotations

from ..artifacts import ConceptsDoc
from ..context import CheckResult, NodeContext


def check(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = ConceptsDoc.model_validate(ctx.json("concepts"))
    t = ctx.thresholds["concepts"]
    res.dim("CON-OPTIONS", len(doc.concepts) >= t["min_concepts"], f"{len(doc.concepts)} concepts (min {t['min_concepts']})")
    reqs = {r.id for r in ctx.state.product.requirements}
    wsum = sum(c.weight for c in doc.criteria)
    crit = {c.id for c in doc.criteria}
    unscored = [f"{c.id}:{k}" for c in doc.concepts for k in crit if not (1 <= c.scores.get(k, 0) <= 5)]
    untraced = [c.id for c in doc.criteria if not c.requirement_ids or any(r not in reqs for r in c.requirement_ids)]
    totals = {c.id: sum(c.scores.get(k.id, 0) * k.weight for k in doc.criteria) for c in doc.concepts}
    top = max(totals, key=totals.get) if totals else None
    sel_ok = doc.selected in totals
    override_ok = doc.selected == top or len(doc.rationale.strip()) >= t["min_override_rationale_chars"]
    ok = abs(wsum - 1) <= t["weight_tolerance"] and not unscored and not untraced and sel_ok and override_ok
    res.dim("CON-MATRIX", ok, f"weights sum {wsum:.2f}; scores {({k: round(v, 2) for k, v in totals.items()})}; "
            f"selected {doc.selected} (top {top})" + (f"; unscored {unscored}" if unscored else "")
            + (f"; criteria not traced to requirements {untraced}" if untraced else ""))
    res.dim("CON-RISK", all(c.riskiest_assumption.strip() for c in doc.concepts), "every concept names its riskiest assumption"
            if all(c.riskiest_assumption.strip() for c in doc.concepts) else "a concept has no riskiest assumption")
    return res
