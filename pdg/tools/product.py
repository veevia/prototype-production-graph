"""N03–N05: problem frame, requirements traceability, scope quality bars."""

from __future__ import annotations

import re

from ..artifacts import ProblemFrame, RequirementsDoc, ScopeDoc
from ..context import CheckResult, NodeContext
from ._common import sentences, words

VAGUE = re.compile(r"\b(if things go (bad|wrong)|as needed|when appropriate|tbd|if necessary|"
                   r"(?:any|some)\s+(?:problems?|issues?|concerns?|trouble|difficult(?:y|ies)|complaints?))\b", re.I)
# A trigger names a measurable condition: a number, a quantified event ("if ANY session releases…", "FEWER than…"), or
# a generic incident class. Product vocabulary is never on this list: the check must work for any product.
MEASURABLE_EVENT = re.compile(
    r"\d|%|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|half|twice)\b"
    r"|\b(?:any|every|each|none)\b"
    r"|\bP[0-4]\b|\bsev(?:erity)?[\s-]*[0-4]\b|\b(?:incident|outage|breach|violation|crash|data\s+loss)\b",
    re.I,
)


def check_problem(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = ProblemFrame.model_validate(ctx.json("problem"))
    t = ctx.thresholds["problem"]
    long = [n for n, v in (("job", doc.job), ("primary_persona", doc.primary_persona), ("top_pain", doc.top_pain.statement))
            if sentences(v) > 1 or words(v) > t["max_sentence_words"]]
    res.dim("PRB-ONE-SENTENCE", not long, "one sentence each" if not long else f"more than one sentence or > "
            f"{t['max_sentence_words']} words: {long}")
    known = {e.id for e in ctx.state.research.evidence}
    ev = doc.top_pain.evidence_ids
    res.dim("PRB-EVIDENCE", bool(ev) and all(e in known for e in ev), f"top pain cites {ev or 'nothing'}"
            + (f"; unknown: {[e for e in ev if e not in known]}" if any(e not in known for e in ev) else ""))
    res.dim("PRB-HMW", len(doc.how_might_we) >= t["min_hmw"], f"{len(doc.how_might_we)} How-Might-We questions")
    return res


def check_requirements(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = RequirementsDoc.model_validate(ctx.json("requirements"))
    ev = {e.id for e in ctx.state.research.evidence}
    asm = {a.id for a in ctx.state.research.assumptions}
    ids = [r.id for r in doc.requirements]
    if len(ids) != len(set(ids)):
        res.errors.append("duplicate requirement ids")
    untraced = [r.id for r in doc.requirements
                if not ([e for e in r.evidence_ids if e in ev] or [a for a in r.assumption_ids if a in asm])
                or any(e not in ev for e in r.evidence_ids) or any(a not in asm for a in r.assumption_ids)]
    res.dim("REQ-TRACE", not untraced and bool(doc.requirements),
            f"{len(doc.requirements) - len(untraced)}/{len(doc.requirements)} traced" + (f"; untraced: {untraced}" if untraced else ""))
    no_acc = [r.id for r in doc.requirements if r.priority == "P0" and not r.acceptance]
    res.dim("REQ-ACCEPTANCE", not no_acc, f"P0 without acceptance criteria: {no_acc or 'none'}")
    types = {r.type for r in doc.requirements}
    res.dim("REQ-TYPES", types >= {"user", "business", "technical"}, f"types present: {sorted(types)}")
    res.dim("REQ-CONSTRAINTS", bool(doc.constraints) and all(c.source for c in doc.constraints),
            f"{len(doc.constraints)} constraints")
    return res


def check_scope(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = ScopeDoc.model_validate(ctx.json("scope"))
    res.dim("SCP-NONGOALS", bool(doc.scope.non_goals) and bool(doc.scope.out_of_scope) and not any(
        x.strip().lower() in ("none", "n/a", "-") for x in doc.scope.non_goals + doc.scope.out_of_scope),
        f"{len(doc.scope.non_goals)} non-goals, {len(doc.scope.out_of_scope)} out-of-scope")
    no_num = [m.id for m in doc.success_criteria if not re.search(r"\d", m.target)]
    north = [m.id for m in doc.success_criteria if m.kind == "north_star"]
    res.dim("SCP-NUMBERS", bool(north) and not no_num and bool(doc.success_criteria),
            f"north star {north or 'missing'}; targets without a number: {no_num or 'none'}")
    vague = [t for t in doc.rollback_triggers if VAGUE.search(t) or not MEASURABLE_EVENT.search(t)]
    res.dim("SCP-ROLLBACK", bool(doc.rollback_triggers) and not vague, f"{len(doc.rollback_triggers)} triggers"
            + (f"; vague: {vague}" if vague else ""))
    bad_y = [q.id for q in doc.open_questions if q.light == "yellow" and not q.resolved and not (q.trigger and q.expiry and q.owner)]
    res.dim("SCP-YELLOW", not bad_y, f"yellow questions missing trigger/expiry/owner: {bad_y or 'none'}")
    res.dim("SCP-GUARDRAIL", any(m.kind == "guardrail" for m in doc.success_criteria), "guardrail metric "
            + ("present" if any(m.kind == "guardrail" for m in doc.success_criteria) else "missing"))
    return res
