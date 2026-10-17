"""N19: lesson checks, and the learning-proposal hook (see pdg.gating.learning_proposal)."""

from __future__ import annotations

import re

from ..artifacts import LessonsDoc
from ..context import CheckResult, NodeContext
from ._common import finding
from ..gating import learning_proposal

PROTECTED_SCOPES = {"product_truth", "requirements", "evidence", "approved_design_principles"}
_TARGET = (r"(?:requirements?|product\s+truth|evidence(?:\s+log)?|approved\s+design(?:\s+principles?)?|"
           r"design\s+principles?)")
# The lesson would edit a protected scope: an edit verb that governs a protected target ("rewrite the requirements"),
# or the target made the subject of a passive edit ("requirements should be rewritten"). A lesson that merely mentions
# one ("when requirements change, re-run the trace") is not an edit.
PROTECTED_EDIT = re.compile(
    rf"\b(?:rewrite|change|alter|update|modify|replace|edit|revise|relax|drop|remove|delete|loosen)\s+(?:\w+\s+){{0,3}}?{_TARGET}\b"
    rf"|\b{_TARGET}\s+(?:\w+\s+){{0,3}}?(?:be|is|are|get|gets)\s+(?:\w+\s+)?"
    r"(?:rewritten|changed|altered|updated|modified|replaced|edited|revised|relaxed|dropped|removed|deleted|loosened)\b")


def propose(ctx: NodeContext) -> CheckResult:
    return learning_proposal(ctx)


def check_lessons(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = LessonsDoc.model_validate(ctx.json("lessons"))
    st = ctx.state
    rules = {r["id"] for r in ctx.engine.rules.rules}
    known = ({f.id for f in st.evaluation.feedback} | {d.id for d in st.evaluation.defects} | {e.id for e in st.research.evidence}
             | {x.id for x in st.product.requirements} | {x.id for x in st.product.constraints} | set(st.artifacts) | rules
             | {f"comparison:cycle-{c.cycle}" for c in st.evaluation.comparisons})
    ledger = getattr(ctx.engine, "ledger", None)   # the instructions allow a ledger event, cited as ledger:<seq> (W27)
    if ledger is not None:
        known |= {f"ledger:{e['seq']}" for e in ledger.events()}
    no_ev = [l.id for l in doc.lessons if not l.evidence]
    unresolved = [f"{l.id}→{e}" for l in doc.lessons for e in l.evidence if e not in known]
    res.dim("LRN-EVIDENCE", bool(doc.lessons) and not no_ev and not unresolved,
            f"{len(doc.lessons)} lessons; without evidence: {no_ev or 'none'}; evidence that does not exist in this run: "
            f"{unresolved or 'none'}",
            [finding("LRN-EVIDENCE", f"{ref.split('→')[0]} cites {ref.split('→')[1]}, which does not exist in this run", "P2",
                     ref.split("→")[0], "n19_learning_memory", "cite only evidence this run produced",
                     "every cited id resolves") for ref in unresolved[:8]])
    unknown = [f"{l.id}→{l.rule_id}" for l in doc.lessons if l.rule_id and l.rule_id not in rules]
    res.dim("LRN-SCOPE", not unknown, f"scopes: {sorted({l.scope for l in doc.lessons})}; unknown rules: {unknown or 'none'}")
    configured_protected = set(getattr(ctx.engine.rules, "data", {}).get("protected_scopes", PROTECTED_SCOPES))

    def target_scope(lesson) -> str:
        return lesson.target_scope or lesson.category or ""

    def edits_protected_statement(statement: str) -> bool:
        return bool(PROTECTED_EDIT.search(statement.lower()))

    protected = [l.id for l in doc.lessons if l.scope == "reusable"
                 and (target_scope(l) in configured_protected or edits_protected_statement(l.statement))]
    res.dim("LRN-PROTECTED", not protected, f"lessons that would edit a protected scope: {protected or 'none'}")
    fb = {f.id: f for f in st.evaluation.feedback}
    df = {d.id: d for d in st.evaluation.defects}
    grounded = ({e.id for e in st.research.evidence} | {x.id for x in st.product.requirements}
                | {x.id for x in st.product.constraints})

    def simulated(ref: str) -> bool:
        if ref in fb:
            return fb[ref].simulated
        d = df.get(ref)
        if not d:
            return False
        if d.feedback_ids:
            return all(fb[x].simulated for x in d.feedback_ids if x in fb)
        if "n14_validation" in d.source_nodes and st.research.validation_findings:
            return all(v.simulated for v in st.research.validation_findings)
        return False

    def real(ref: str) -> bool:
        return (ref in fb or ref in df or ref in grounded) and not simulated(ref)

    over = [l.id for l in doc.lessons if l.evidence_class == "verified" and not any(real(e) for e in l.evidence)]
    res.dim("LRN-HONEST", not over, f"verified lessons without non-simulated evidence: {over or 'none'}",
            [finding("LRN-HONEST", f"{lid} is classed verified but rests only on simulated or derived evidence", "P2", lid,
                     "n19_learning_memory", "class it inferred (or cite real evidence)",
                     "every verified lesson cites a non-simulated item") for lid in over])
    return res
