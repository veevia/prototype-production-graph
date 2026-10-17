"""N10: the fidelity gate ("development moved too quickly") and scenario/state coverage."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from ..artifacts import PrototypePlan
from ..context import CheckResult, NodeContext
from ..evaluation import load_rubrics, node_dimensions
from ..graph import GraphIndex, load_workflow
from ..models import NodeKind
from ..util import sha256_json


def _parse_time(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def _active_risk_delegation(st, ra, humans: list[str]) -> str | None:
    if not (ra.on_behalf_of in humans and ra.delegation):
        return None
    accepted_at = _parse_time(ra.at)
    for d in reversed(st.history.delegations):
        if d.id != ra.delegation or d.by != ra.on_behalf_of or d.agent != ra.actor:
            continue
        if "accept_risk" not in d.scope:
            continue
        if _parse_time(d.created) > accepted_at or _parse_time(d.expires) <= accepted_at:
            continue
        if d.revoked_at and _parse_time(d.revoked_at) <= accepted_at:
            continue
        return f"{ra.actor} on behalf of {ra.on_behalf_of} ({ra.delegation})"
    return None


def _human_acceptance(st, aid: str, humans: list[str]) -> str | None:
    """Who accepted assumption `aid` as a risk: a named human's recorded acceptance (`pdg accept-risk`). Neither an
    `accepted_by` field an agent wrote nor a mention of the id in someone's words is an acceptance ("A-01 is NOT
    accepted" mentions it too)."""
    statement = next((a.statement for a in st.research.assumptions if a.id == aid), "")
    current_sha = sha256_json(statement) if statement else ""
    for ra in reversed(st.history.risk_acceptances):
        if ra.assumption != aid:
            continue
        bound_sha = getattr(ra, "statement_sha256", "")
        if bound_sha and current_sha and bound_sha != current_sha:
            who = ra.on_behalf_of or ra.actor
            return f"{aid} changed after {who} accepted it on {ra.at[:10]}: re-accept"
        suffix = " [unbound]" if not bound_sha else ""
        if ra.actor in humans:
            return f"{ra.actor} ({ra.at[:10]}){suffix}"
        delegated = _active_risk_delegation(st, ra, humans)
        if delegated:
            return delegated + suffix
    return None


FOCUS_CHECKS = ("A11Y-FOCUS", "A11Y-FOCUS-VISIBLE-2411")   # browser checks that can stand for a focus rule
# they measure the focus indicator, so they can stand only for a rule about it: "focus moves to the h1" needs a step
INDICATOR = re.compile(r"\b(ring|outline|indicator|visible|obscur\w*|contrast|highlight)\b", re.I)


def _focus_trace(doc: PrototypePlan, rules: list[str]) -> tuple[bool, str]:
    """Each N08 focus rule is traced to an `expect_focus` step, a browser focus check, or a reason it is out of scope
    (backlog N-22: a build broke two focus rules and passed, because no scenario checked them)."""
    scn = {s.id: s for s in doc.scenarios}
    by_rule = {t.rule.strip(): t for t in doc.focus_trace}
    untraced, broken = [], []
    seen: set[str] = set()
    for t in doc.focus_trace:   # one trace per rule: a second one would silently replace the first (review I4)
        if t.rule.strip() in seen:
            broken.append(f"{t.rule!r}: traced more than once")
        seen.add(t.rule.strip())
    for rule in rules:
        t = by_rule.get(rule.strip())
        if t is None:
            untraced.append(rule)
            continue
        ways = [x for x in (t.scenario or t.step, t.covered_by, t.out_of_scope) if x]
        if len(ways) != 1:
            broken.append(f"{rule!r}: give exactly one of scenario+step, covered_by or out_of_scope")
        elif t.scenario or t.step:
            s = scn.get(t.scenario or "")
            step = s.steps[t.step - 1] if s and t.step and 1 <= t.step <= len(s.steps) else None
            if step is None or not step.expect_focus:
                broken.append(f"{rule!r}: {t.scenario} step {t.step} is not an `expect_focus` step")
        elif t.covered_by and t.covered_by not in FOCUS_CHECKS:
            broken.append(f"{rule!r}: covered_by must be one of {', '.join(FOCUS_CHECKS)}")
        elif t.covered_by and not INDICATOR.search(rule):
            broken.append(f"{rule!r}: {t.covered_by} checks the focus indicator, not where focus goes; trace this rule to "
                          "an `expect_focus` step")
        elif t.out_of_scope is not None and not t.out_of_scope.strip():
            broken.append(f"{rule!r}: an empty out_of_scope reason")
    stale = sorted(set(by_rule) - {r.strip() for r in rules})
    ok = not untraced and not broken
    return ok, (f"{len(rules) - len(untraced)}/{len(rules)} N08 focus rules traced"
                + (f"; untraced {untraced}" if untraced else "") + (f"; {'; '.join(broken)}" if broken else "")
                + (f"; note: traces for rules N08 no longer has {stale}" if stale else ""))


_QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "\u2013": "-", "\u2014": "-"})


def acceptance_key(text: str) -> str:
    """How an acceptance line is matched: case, spacing, curly quotes and a trailing full stop don't count, so a copy
    that differs only in those still traces its line (batch 8b review I1)."""
    return " ".join(text.translate(_QUOTES).split()).rstrip(" .;:").casefold()


def acceptance_checks(idx, rubrics, plan_node: str) -> dict[str, str]:
    """What an acceptance line's `covered_by` may name: a MUST check (tool or review) of a node that judges every build
    between the plan and the gate. A SHOULD check does not block, a rework-only or release check does not run each
    round, and a gate or a human decides rather than checks (review I2). Id → node."""
    gate = idx.gate_node
    rounds = set(idx.descendants(plan_node)) & (idx.ancestors(gate) if gate else set(idx.nodes))
    return {d["id"]: n for n in sorted(rounds) if idx.nodes[n].kind != NodeKind.GATE
            for d in node_dimensions(idx.nodes[n], rubrics)
            if d.get("level") == "MUST" and d.get("check", {}).get("type") in ("tool", "review")}


def acceptance_lines(requirements) -> list[dict[str, str]]:
    """Each P0 and P1 acceptance line, once, as N10 must trace it (a blank line is N04's to fix, not N10's)."""
    out, seen = [], set()
    for r in requirements:
        if r.priority not in ("P0", "P1"):
            continue
        for a in r.acceptance:
            key = (r.id, acceptance_key(a))
            if a.strip() and key not in seen:
                seen.add(key)
                out.append({"requirement": r.id, "priority": r.priority, "acceptance": a.strip()})
    return out


def _later_checks(ctx: NodeContext) -> dict[str, str]:
    eng = ctx.engine
    idx, rubrics = getattr(eng, "idx", None), getattr(eng, "rubrics", None)
    if idx is None or rubrics is None:   # a unit test's stand-in engine: the package's own graph and rubrics
        idx, rubrics = GraphIndex(load_workflow()), load_rubrics()
    plan_node = getattr(getattr(ctx, "node", None), "id", None) or "n10_prototype_planning"
    return acceptance_checks(idx, rubrics, plan_node)


def _acceptance_trace(doc: PrototypePlan, requirements, checks: dict[str, str]) -> tuple[bool, str]:
    """Each P0 acceptance line (R-SCP-007) is traced once to an expectation step, a `forbidden_text` entry, a MUST check
    every build round runs, or a reason; P1 lines are listed when untraced, not required (field run 2, R2-18; backlog
    N-25, D10)."""
    scn = {s.id: s for s in doc.scenarios}
    forbidden = {acceptance_key(x) for x in doc.forbidden_text}
    wanted = {(x["requirement"], acceptance_key(x["acceptance"])): x for x in acceptance_lines(requirements)}
    other = {(r.id, acceptance_key(a)) for r in requirements for a in r.acceptance} - set(wanted)   # P2 lines
    traces: dict[tuple[str, str], Any] = {}
    problems: dict[str, list[str]] = {"P0": [], "P1": []}
    for t in doc.acceptance_trace:
        key = (t.requirement, acceptance_key(t.acceptance))
        if key in traces:
            problems[wanted[key]["priority"] if key in wanted else "P1"].append(
                f"{t.requirement} {t.acceptance!r}: traced more than once")
        traces[key] = t
    untraced: dict[str, list[str]] = {"P0": [], "P1": []}
    for key, line in wanted.items():
        prio, t = line["priority"], traces.get(key)
        label = f"{line['requirement']} {line['acceptance']!r}"
        if t is None:
            untraced[prio].append(f"{line['requirement']}: {line['acceptance']}")
            continue
        ways = [x for x in (t.scenario or t.step, t.forbidden_text, t.covered_by, t.out_of_scope) if x]
        if len(ways) != 1:
            problems[prio].append(f"{label}: give exactly one of scenario+step, forbidden_text, covered_by or out_of_scope")
        elif t.scenario or t.step:
            s = scn.get(t.scenario or "")
            step = s.steps[t.step - 1] if s and t.step and 1 <= t.step <= len(s.steps) else None
            if step is None or not any(k.startswith("expect") and v is not None for k, v in step.model_dump().items()):
                problems[prio].append(f"{label}: {t.scenario} step {t.step} is not an expectation")
        elif t.forbidden_text and acceptance_key(t.forbidden_text) not in forbidden:
            problems[prio].append(f"{label}: {t.forbidden_text!r} is not in the plan's forbidden_text")
        elif t.covered_by and t.covered_by not in checks:
            problems[prio].append(f"{label}: {t.covered_by} is not a MUST check that every build round runs (one of "
                                  "the build, content and review nodes' MUST checks; see the packet)")
        elif t.out_of_scope is not None and not t.out_of_scope.strip():
            problems[prio].append(f"{label}: an empty out_of_scope reason")
    extra = set(traces) - set(wanted)
    p2 = sorted(f"{r}: {traces[(r, a)].acceptance}" for r, a in extra & other)
    stale = sorted(f"{r}: {traces[(r, a)].acceptance}" for r, a in extra - other)
    p0 = sum(1 for v in wanted.values() if v["priority"] == "P0")
    ok = not untraced["P0"] and not problems["P0"]
    return ok, (f"{p0 - len(untraced['P0'])}/{p0} P0 acceptance lines traced"
                + (f"; untraced P0 {untraced['P0']}" if untraced["P0"] else "")
                + (f"; {'; '.join(problems['P0'])}" if problems["P0"] else "")
                + (f"; note: P1 lines untraced (listed, not required: R-SCP-007 covers P0) {untraced['P1']}"
                   if untraced["P1"] else "")
                + (f"; note: P1 traces to fix: {'; '.join(problems['P1'])}" if problems["P1"] else "")
                + (f"; note: traces for P2 lines (optional) {p2}" if p2 else "")
                + (f"; note: traces that match no N04 acceptance line (check the wording against the packet) {stale}"
                   if stale else ""))


def check(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = PrototypePlan.model_validate(ctx.json("plan"))
    t = ctx.thresholds["plan"]
    st = ctx.state
    humans = ctx.engine.humans
    riskiest = {a.id: a for a in st.research.assumptions if a.riskiest}
    plan_status = {a.assumption_id: a for a in doc.riskiest_assumptions}
    known = {e.id for e in st.research.evidence}
    problems, accepted = [], []
    if doc.fidelity in ("mid", "high"):
        for aid in riskiest:
            ac = plan_status.get(aid)
            if ac is None or ac.status == "unvalidated":
                problems.append(f"{aid} is unvalidated")
            elif ac.status == "accepted_risk":
                who = _human_acceptance(st, aid, humans)
                if who is None:
                    problems.append(f"{aid} accepted as a risk, but no named human accepted it (`pdg accept-risk <project> "
                                    f"{aid} --actor Wei`)")
                elif "re-accept" in who:
                    problems.append(who)
                else:
                    accepted.append(f"{aid} by {who}")
            elif ac.status == "validated":
                unknown = [e for e in ac.evidence_ids if e not in known]
                if not ac.evidence_ids:
                    problems.append(f"{aid} marked validated without evidence")
                elif unknown:
                    problems.append(f"{aid} cites evidence that does not exist: {', '.join(unknown)}")
    if doc.fidelity == "high":
        ca = doc.customer_alignment
        unknown = [e for e in ca.evidence_ids if e not in known]
        if not (ca.status == "aligned" and ca.evidence_ids):
            problems.append("high fidelity without customer alignment evidence")
        elif unknown:
            problems.append(f"customer alignment cites evidence that does not exist: {', '.join(unknown)}")
    res.dim("PLN-FIDELITY-GATE", not problems, f"fidelity {doc.fidelity}; riskiest assumptions {sorted(riskiest) or 'none'}"
            + (f"; risks accepted: {', '.join(accepted)}" if accepted else "")
            + (f"; {'; '.join(problems)}" if problems else ": gate holds"))
    flows = {f.id: f for f in st.design.flows}
    p0 = {r.id for r in st.product.requirements if r.priority == "P0"}
    p0_flows = [f.id for f in flows.values() if set(f.requirement_ids) & p0]
    with_scn = {s.flow_id for s in doc.scenarios}
    no_scn = [f for f in p0_flows if f not in with_scn]
    unknown = [s.id for s in doc.scenarios if s.flow_id not in flows]
    no_expect = [s.id for s in doc.scenarios if not any(k.startswith("expect") and v is not None
                                                        for k, v in s.steps[-1].model_dump().items())] if doc.scenarios else []
    # a completing action below the fold at a declared width still passes a click, since Playwright scrolls to it: the
    # scenario checks the control is in view before pressing it (backlog N-18)
    text_targets = sorted({s.id for s in doc.scenarios for st in s.steps
                           for sel in (st.click, (st.fill or [None])[0], (st.select or [None])[0]) if sel and "text=" in sel})
    unchecked = []
    for s in (x for x in doc.scenarios if x.flow_id in set(p0_flows)):
        clicks = [(i, st_.click) for i, st_ in enumerate(s.steps) if st_.click]
        if clicks and not any(clicks[-1][1] in (x.expect_in_viewport, x.expect_reachable) for x in s.steps[:clicks[-1][0]]):
            unchecked.append(s.id)
    res.dim("PLN-SCENARIOS", not no_scn and not unknown and not no_expect and not unchecked and bool(doc.scenarios),
            f"{len(doc.scenarios)} scenarios for {len(p0_flows)} P0 flows" + (f"; P0 flows without a scenario {no_scn}" if no_scn else "")
            + (f"; unknown flows {unknown}" if unknown else "") + (f"; scenarios not ending in an expectation {no_expect}" if no_expect else "")
            + (f"; P0 scenarios that press their last control without checking it is reachable first {unchecked}"
               if unchecked else "")
            + (f"; note: {text_targets} act on a `text=` target, which matches a hidden copy elsewhere first; prefer an "
               "id, a role, or a row class with :has-text()" if text_targets else ""))
    spec = {s.screen: s for s in (st.design.interactions.screens if st.design.interactions else [])}
    needed = {(scr, state) for scr, s in spec.items() for state in ("empty", "error") if state in s.states}
    planned = {(x.screen, x.state) for x in doc.states}
    missing = sorted(f"{a}:{b}" for a, b in needed - planned)
    # R-UX-002's "empty (with a way back)": the suite presses the way back and expects the state gone (backlog B-09)
    no_way_back = sorted(f"{x.screen}:{x.state}" for x in doc.states if x.state == "empty" and not x.recover)
    res.dim("PLN-STATES", not missing and not no_way_back, f"{len(planned)} states planned"
            + (f"; unplanned {missing}" if missing else "")
            + (f"; empty states without a `recover` way back {no_way_back}" if no_way_back else ""))
    rules = list(st.design.interactions.focus_rules) if st.design.interactions else []
    res.dim("PLN-FOCUS", *_focus_trace(doc, rules))
    res.dim("PLN-ACCEPTANCE", *_acceptance_trace(doc, st.product.requirements, _later_checks(ctx)))
    known_screens = {s.id for s in st.design.screens}
    odd = sorted(set(doc.samples) - known_screens)
    if odd:
        res.errors.append(f"`samples` names screens the design does not have: {odd}")
    # a sample is another record of its screen: never a design screen's own route, which is measured as that screen
    design_routes = {s.route for s in st.design.screens}
    not_records = sorted({r for rs in doc.samples.values() for r in rs if not r.strip() or r in design_routes})
    if not_records:
        res.errors.append(f"`samples` must be more records of their screen, not a design screen's route or blank: {not_records}")
    # one record proves the template for one record: the width checks load the plan's worst cases too (W53, L-07)
    thin = sorted(f"{s.id} ({len(set(doc.samples.get(s.id, [])))})" for s in st.design.screens
                  if s.kind == "record" and len(set(doc.samples.get(s.id, []))) < int(t.get("min_samples", 2)))
    records = sum(1 for s in st.design.screens if s.kind == "record")
    res.dim("PLN-SAMPLES", not thin, f"{records} record screen(s)"
            + (f"; fewer than {int(t.get('min_samples', 2))} samples: {', '.join(thin)}" if thin
               else (": each names its worst-case records in `samples`" if records else "")))
    vps = sorted(set(doc.viewports))
    ok_vp = len(vps) >= t["min_viewports"] and vps[0] <= t["mobile_max_px"] and vps[-1] >= t["desktop_min_px"] if vps else False
    res.dim("PLN-VIEWPORTS", ok_vp, f"viewports {vps}")
    return res
