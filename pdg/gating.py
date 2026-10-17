"""Deterministic hooks: the review gate (N16), the regeneration plan (N17), release verification (N18) and the learning
proposal (N19). The gate and the proposal run in the engine's serial commit phase and may update the evaluation state;
the plan and the release check run as tool nodes and only read it (the engine applies their results)."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .artifacts import Interpretation, LessonsDoc
from .context import CheckResult
from .engine_common import release_checks, resets_text
from .evaluation import node_dimensions
from .models import ClaimedFixed, Comparison, Defect, EdgeKind, GateResult, NodeStatus
from .util import now, rel, sha256_file, write_json_atomic

if TYPE_CHECKING:  # pragma: no cover
    from .context import NodeContext
    from .engine import Engine

ACTIVE = {"open", "persisting", "needs_human"}


def signatures(d: Defect) -> set[str]:
    """Every signature a defect answers to: its own and the aliases its findings used (field run W28)."""
    return {d.signature, *d.aliases}


def _owning_reviewer(eng: "Engine", dimension: str) -> str | None:
    """The reviewer whose rubric scores `dimension`, else the quality reviewer. A defect raised from feedback has no
    reviewer who found it, so this one re-verifies it (field run W30, backlog B-02). It re-checks through its packet, not
    through the resolution rule: every reviewer re-reviews a changed build anyway, and a fix that leaves the build
    unchanged must still resolve (vpg #46)."""
    reviewers = eng.idx.reviewer_nodes()
    for r in reviewers:
        if any(d["id"] == dimension for d in node_dimensions(eng.node(r), eng.rubrics)):
            return r
    return "n13_quality_review" if "n13_quality_review" in reviewers else (reviewers[0] if reviewers else None)


_CODE_LINE = re.compile(r"@[^#]*\.[A-Za-z0-9]+:\d+$")    # a `file:line` location with no element
_ATTEMPT_PATH = re.compile(r"(?<=@)work/([^/@#]+/)?a\d+/")


def canonical_signature(sig: str) -> str:
    """A file finding under ``work/<node>/aN/`` names the same issue across attempts."""
    return _ATTEMPT_PATH.sub("work/", sig)


def stable_signature(sig: str) -> bool:
    """Does the signature name one issue across builds? A screen, state or element does; a bare code location does not,
    since the line holds another statement in a later build (field run W40: `build.py:87` re-opened a v2 defect for a
    v7 one)."""
    return not _CODE_LINE.search(canonical_signature(sig))


def _reopen(d: Defect, version: int, why: str, message: str, evidence: str) -> None:
    """A resolved defect reported again is a regression of its fix: it re-opens with its id and history (field run
    W36), instead of a new defect that hides the history. It takes the new report's message and evidence; the old text
    stays in its history (W40)."""
    d.history.append(f"{now()} re-opened at v{version}: {why} (it was resolved at v{d.resolved_at_version}; it said: "
                     f"{d.message[:200]})")
    d.status, d.resolved_at_version = "open", None
    d.message, d.evidence = message, evidence


_DEFECT_ID = re.compile(r"D-(\d+)")


def _next_defect_id(defects: list[Defect], reserved: set[str] | frozenset[str] = frozenset()) -> str:
    """One more than the highest id in use (a count repeats an id once the numbering has a gap: field run W46 held two
    D-179s), and never one reserved by the interpretation being applied."""
    used = {d.id for d in defects} | set(reserved)
    highest = max([int(m.group(1)) for x in used if (m := _DEFECT_ID.fullmatch(x))] + [len(defects)])
    return f"D-{highest + 1:03d}"


def fix_marker(eng: "Engine", d: Defect) -> dict[str, int]:
    """The attempts a correction of `d` must move past: its fix owner's, and each reviewer's that found it (or, for one
    raised from feedback, the reviewer asked to re-verify it: W30, W61)."""
    return {n: eng.rt(n).attempt for n in sorted({d.traced_node, *rechecking_reviewers(eng, d)}) if n in eng.idx.nodes}


def rechecking_reviewers(eng: "Engine", d: Defect) -> list[str]:
    """The reviews asked to re-verify `d`: the ones that found it, else the one whose rubric owns its dimension (W30)."""
    reviewers = eng.idx.reviewer_nodes()
    return [s for s in d.source_nodes if s in reviewers] or [r for r in [_owning_reviewer(eng, d.dimension)] if r]


def said_no_longer_holds(d: Defect, latest: dict, version: int, eng: "Engine") -> list[str]:
    """The reviews asked to re-verify deferred `d` that looked at this build since it was last seen and list it under
    `no_longer_holds`. Its owner does not re-run, so only a review can tell that a fix made on the way left it untrue; and
    only by saying so, since a reviewer need not re-file a deferred defect that still holds (field run W61). A marker that
    does not name the review (an older record) never counts as a look."""
    return [n for n in rechecking_reviewers(eng, d) if claim_refused(d, n, latest, version, eng) == ""]


def claim_refused(d: Defect, n: str, latest: dict, version: int, eng: "Engine") -> str | None:
    """Why review `n`'s claim that deferred `d` no longer holds does not count: None when it made no claim on this build,
    "" when it counts."""
    rv, rt, marker = latest.get(n), eng.rt(n), d.attempts_at_start or {}
    if rv is None or rv.build_version != version or d.id not in rv.no_longer_holds:
        return None
    if rt.status != NodeStatus.PASSED:
        return "its review did not pass"
    if n not in marker:   # an older record: this look starts one, so its next claim counts (batch 17 review 2, I1)
        return "no earlier look of it is on record; its next claim counts"
    if rt.attempt <= marker[n]:
        return "it has not looked again since the defect was last seen"
    return ""


def decide_deferred_command(eng: "Engine", d: Defect) -> str:
    """The command a person runs once they have checked that a deferred defect its reviews said no longer holds does
    not (W61)."""
    at = d.claimed_fixed.at if d.claimed_fixed else "N"
    return (f"pdg decide-deferred {shlex.quote(str(eng.project.root))} {shlex.quote(d.id)} --resolved --reason "
            f"{shlex.quote(f'no longer holds at v{at}')} --actor <name>")


def correction_reran(d: Defect, latest: dict, version: int, eng: "Engine | None" = None) -> bool:
    """Has a correction of `d` run and been re-checked? The node that owns the fix re-ran (and passed) since the defect
    was last seen or its rework started, by any path: targeted rework, a change request, a new source. Every reviewer
    that found it re-reviewed since then too. A fix need not change the build (a wording fix in a control document).
    A defect recorded before attempts were kept falls back to build versions."""
    marker = getattr(d, "attempts_at_start", None) or {}
    if marker and eng is not None:
        def reran(n: str) -> bool:
            rt = eng.rt(n)
            return rt.status == NodeStatus.PASSED and rt.attempt > marker.get(n, rt.attempt)
        owner_ok = d.traced_node not in eng.idx.nodes or reran(d.traced_node)
        return owner_ok and all(reran(s) for s in d.source_nodes if s in latest)
    base = d.rework_version if getattr(d, "rework_version", None) is not None else d.opened_at_version
    sources = [s for s in d.source_nodes if s in latest]
    if sources:
        return all(latest[s] and latest[s].build_version > base for s in sources)
    return version > base


def open_advisories(eng: "Engine") -> list[Defect]:
    """Open advisory defects: never blocking, never routed on their own, each resolved only once its node has re-run and
    no review reports it (field run W54)."""
    return [d for d in eng.state.evaluation.defects
            if d.status in ("open", "persisting") and d.severity not in eng.wf.policies.blocking_severities and not d.deferred]


def advisory_remedy(eng: "Engine", d: Defect, cycles: int) -> str:
    """What gets an advisory fixed now, at a gate that has used `cycles` rework cycles. Re-filing it at a blocking
    severity works only where that gate would route it: a locked document needs a change request, a node the gate cannot
    route or a spent rework budget needs a named human's invalidation, since raising it there would block the gate. N16
    cannot invalidate: that would void its own attempt (W54 review I2)."""
    n, project = d.traced_node, shlex.quote(str(eng.project.root))
    if n not in eng.idx.nodes:
        return f"re-trace it: {n} is not a node of this graph"
    invalidate = f"a named human runs `pdg invalidate {project} {n} --actor <human> --reason \"…\"` after this gate"
    locked = eng.controls.needs_change_request(n, eng.idx.nodes[n].controls.write)
    if locked:
        return (f"a named human approves a change request (`pdg change-request {project} --doc {locked[0]} --writer {n} "
                f"--actor <human> --reason \"…\"`): {', '.join(locked)}.md is locked, so raising it to a blocking severity "
                "would block the gate")
    if n not in eng.wf.policies.regeneration_targets or _spent_rework_edge(eng, n) is not None:
        return f"{invalidate} (the gate cannot route {n})"
    pol = eng.wf.policies
    if cycles >= pol.max_rework_cycles or d.failures >= pol.max_same_defect_failures:
        spent = (f"the rework budget is spent ({cycles}/{pol.max_rework_cycles} cycles)" if cycles >= pol.max_rework_cycles
                 else f"it failed {d.failures} corrections (limit {pol.max_same_defect_failures})")
        return f"{invalidate} ({spent}, so raising it would block the gate)"
    return (f"N16 re-files `{d.signature}` at a blocking severity with its traced node, smallest fix and acceptance "
            f"check, and the gate routes it to {n}; or {invalidate}")


def stranded_advisories(eng: "Engine", targets: list[str]) -> list[tuple[Defect, str]]:
    """(defect, why) for each open advisory a rework cycle may leave open. A cycle surely re-runs only its targets: a
    node after one re-runs only if its inputs changed (one that did not is memo-restored and counts as not re-run), and
    any other node not at all (W54 review I1)."""
    after = {n for t in targets for n in eng.idx.descendants(t)} - set(targets)
    return [(d, "its node follows a target, so it re-runs only if its inputs change" if d.traced_node in after
             else "its node is not in this cycle") for d in open_advisories(eng) if d.traced_node not in targets]


def _spent_rework_edge(eng: "Engine", target: str):
    """The regeneration node's loop edge to `target` when it has used all its traversals, else None."""
    regen = eng.idx.regen_node
    for e in eng.idx.outgoing.get(regen, []) if regen else []:
        if e.kind == EdgeKind.LOOP and e.target == target and e.max_traversals is not None:
            if eng.state.runtime.loop_traversals.get(e.id, 0) >= e.max_traversals:
                return e
    return None


def review_gate(ctx: "NodeContext") -> CheckResult:
    eng = ctx.engine
    st, pol, idx = eng.state, eng.wf.policies, eng.idx
    ev = st.evaluation
    version = st.build.version
    interp = Interpretation.model_validate(json.loads(ctx.output("interpretation").read_text()))
    res = CheckResult()
    reasons: list[str] = []

    reviewers = idx.reviewer_nodes()
    latest = {r: eng.latest_review(r) for r in reviewers}
    stale = [r for r, rv in latest.items() if rv is None or rv.build_version != version]
    current_findings = [f for rv in latest.values() if rv and rv.build_version == version for f in rv.findings]
    for f in current_findings:
        if f.location:
            f.location = canonical_signature(f"{f.dimension}@{f.location}").split("@", 1)[1]
    for di in interp.defects:
        di.signature = canonical_signature(di.signature)
        di.from_findings = [x.split(":", 1)[0] + ":" + canonical_signature(x.split(":", 1)[1])
                            if ":" in x else canonical_signature(x) for x in di.from_findings]
    blocking_findings = [f for f in current_findings if f.blocking]
    interp_sigs = {d.signature for d in interp.defects}
    reserved = {d.id for d in interp.defects}   # the interpretation's own ids: a tool defect never takes one (W46)

    # 1. judge the corrections made since the last gate. Every active defect is judged, not only those in targeted
    # rework: a defect fixed another way (a change request, a new source) resolves once its node re-ran and nobody
    # reports it any more; otherwise a fixed defect would block the run for good (vpg finding #46). An advisory defect
    # is never routed, so this is its only way to resolve (field run W13). Any current finding with the signature,
    # blocking or advisory, still reports it: a SHOULD dimension stores a re-report as advisory (field run W20).
    resolved, persisting = [], []
    refused: list[str] = []   # claims that a deferred defect no longer holds that did not count, and why (W61)
    for d in ev.defects:
        if d.status not in ("in_rework", "open", "persisting", "needs_human"):
            continue
        reran = correction_reran(d, latest, version, eng)
        sigs = signatures(d)
        # its own signature is still reported by any current finding (W20); an alias only by a blocking one, since an
        # advisory folded in as an alias would otherwise keep a fixed defect failing for good (independent audit #4)
        still = (any(f.signature == d.signature or (f.signature in d.aliases and f.blocking) for f in current_findings)
                 or bool(sigs & interp_sigs))
        if d.deferred:   # it waits on a human decision, not a fix: a re-run for other reasons never resolves it (W39)
            asked = rechecking_reviewers(eng, d)
            claims = [n for n in asked if claim_refused(d, n, latest, version, eng) is not None]
            if still:
                if claims:   # the reviews disagree: the report wins, and the claim is named (batch 17 review 2, S3)
                    by = sorted({f.node for f in current_findings if f.signature == d.signature
                                 or (f.signature in d.aliases and f.blocking)}) or ["the interpretation"]
                    refused.append(f"{' and '.join(claims)} {'say' if len(claims) > 1 else 'says'} {d.id} no longer holds, "
                                   f"but {' and '.join(by)} {'report' if len(by) > 1 else 'reports'} it at v{version}")
                if d.claimed_fixed is not None:
                    d.history.append(f"{now()} reported again at v{version}, after a review said it no longer held")
                d.claimed_fixed = None
                d.attempts_at_start = fix_marker(eng, d)   # seen now: only a later review can say it no longer holds
            elif d.claimed_fixed is None:
                # fixed on the way, perhaps: a person decides, not the reviews again (W61). A reviewer that made no claim
                # filed nothing; one whose claim did not count is named with why (batch 17 review 3, S2)
                if (said := said_no_longer_holds(d, latest, version, eng)):
                    d.claimed_fixed = ClaimedFixed(at=version, by=said, silent=[
                        n for n in asked if claim_refused(d, n, latest, version, eng) is None])
                    d.history.append(f"{now()} deferred; at v{version} {', '.join(said)} said it no longer holds, and no "
                                     "current review reports it")
                refused += [f"{n} says {d.id} no longer holds, but {why}" for n in claims
                            if (why := claim_refused(d, n, latest, version, eng))]
            # a marker from before its reviewer was asked: the next look counts (review 2, I1). The whole marker, owner
            # too: one that names only reviewers would never see the owner re-run after a `--fix` (review 3, I1)
            for n, a in fix_marker(eng, d).items():
                d.attempts_at_start.setdefault(n, a)
            continue
        if reran and not still:
            how = "" if d.status == "in_rework" else " (its node re-ran outside targeted rework)"
            d.status, d.resolved_at_version = "resolved", version
            d.history.append(f"{now()} resolved at v{version}{how}")
            resolved.append(d.id)
        elif d.status == "in_rework":
            d.status = "persisting"
            d.failures += 1
            d.history.append(f"{now()} persisting at v{version} (failed corrections: {d.failures})")
            persisting.append(d.id)
        if still and d.status != "resolved":
            d.attempts_at_start = fix_marker(eng, d)   # seen now: only a later re-run can correct it

    # 2. the interpreter's defects (new, or updates of an active one with the same signature)
    new: list[str] = []
    fb_by_id = {f.id: f for f in ev.feedback}
    for di in interp.defects:
        cur = next((d for d in ev.defects if di.signature in signatures(d) and d.status in ACTIVE | {"persisting"}), None)
        sources = sorted({x.split(":", 1)[0] for x in di.from_findings if ":" in x} |
                         ({"n14_validation"} if any(fb_by_id.get(f) and fb_by_id[f].actor.startswith("participant:")
                                                    for f in di.from_feedback) else set()))
        aliases = sorted({x.split(":", 1)[1] for x in di.from_findings if ":" in x} - {di.signature})
        if cur is None and stable_signature(di.signature) and (old := next(
                (d for d in reversed(ev.defects) if d.status == "resolved" and di.signature in signatures(d)), None)) is not None:
            _reopen(old, version, "the interpreter reports its signature again", di.message, di.evidence)
            old.source_nodes = sorted(set(old.source_nodes) | set(sources))
            old.traced_node, old.trace_reason = di.traced_node, di.trace_reason
            old.smallest_fix, old.acceptance_check, old.severity = di.smallest_fix, di.acceptance_check, di.severity
            old.attempts_at_start = fix_marker(eng, old)
            cur = old
            new.append(cur.id)
        elif cur is None:
            cur = Defect(id=di.id if all(d.id != di.id for d in ev.defects) else _next_defect_id(ev.defects, reserved),
                         signature=di.signature, dimension=di.dimension, severity=di.severity, message=di.message,
                         evidence=di.evidence, traced_node=di.traced_node, trace_reason=di.trace_reason,
                         artifact_key=di.artifact_key, smallest_fix=di.smallest_fix, acceptance_check=di.acceptance_check,
                         source_nodes=sources, feedback_ids=list(di.from_feedback), opened_at_version=version,
                         history=[f"{now()} opened at v{version} by the interpreter"])
            cur.attempts_at_start = fix_marker(eng, cur)
            ev.defects.append(cur)
            new.append(cur.id)
        else:
            retraced = cur.traced_node != di.traced_node
            cur.traced_node, cur.trace_reason = di.traced_node, di.trace_reason
            if retraced:
                cur.attempts_at_start = fix_marker(eng, cur)
            cur.smallest_fix, cur.acceptance_check, cur.severity = di.smallest_fix, di.acceptance_check, di.severity
            if di.message.strip() and (di.message, di.evidence) != (cur.message, cur.evidence):
                # the release lists an open defect by its message: it must say what is still wrong now (W45)
                cur.history.append(f"{now()} re-described at v{version} (it said: {cur.message[:200]})")
                cur.message, cur.evidence = di.message, di.evidence
            cur.history.append(f"{now()} re-traced at v{version}")
        cur.aliases = sorted(set(cur.aliases) | set(aliases) - {cur.signature})
        cur.feedback_ids = sorted(set(cur.feedback_ids) | set(di.from_feedback))   # a re-file's feedback too (W45)
        for fid in di.from_feedback:
            if fid in fb_by_id:
                fb_by_id[fid].status = "interpreted"
                fb_by_id[fid].defect_ids = sorted(set(fb_by_id[fid].defect_ids) | {cur.id})
    for m in interp.feedback:
        f = fb_by_id.get(m.feedback_id)
        if f is None:
            continue
        if m.defect_ids:
            f.status, f.defect_ids = "interpreted", sorted(set(f.defect_ids) | set(m.defect_ids))
        elif m.dismissed_reason:
            f.status = "dismissed"

    # 3. blocking tool findings the interpreter did not re-trace are mapped from their own trace
    covered = {x for di in interp.defects for x in di.from_findings} | interp_sigs
    active_sigs = {s for d in ev.defects if d.status in ACTIVE | {"persisting"} for s in signatures(d)}
    for f in blocking_findings:
        f.location = canonical_signature(f"{f.dimension}@{f.location}").split("@", 1)[1] if f.location else f.location
        if f.by != "tool" or f"{f.node}:{f.signature}" in covered or f.signature in covered or f.signature in active_sigs:
            continue
        old = next((d for d in reversed(ev.defects) if d.status == "resolved" and f.signature in signatures(d)), None) \
            if stable_signature(f.signature) else None
        if old is not None:
            _reopen(old, version, f"{f.node}'s tool reports its signature again", f.message, f.evidence)
            old.attempts_at_start = fix_marker(eng, old)
            active_sigs |= signatures(old)
            new.append(old.id)
            continue
        d = Defect(id=_next_defect_id(ev.defects, reserved), signature=f.signature, dimension=f.dimension, severity=f.severity,
                   message=f.message, evidence=f.evidence, traced_node=f.traced_node or "",
                   trace_reason="mapped from the tool's own trace", smallest_fix=f.smallest_fix,
                   acceptance_check=f.acceptance_check, source_nodes=[f.node], opened_at_version=version,
                   history=[f"{now()} opened at v{version} from {f.node} (tool finding)"])
        d.attempts_at_start = fix_marker(eng, d)
        ev.defects.append(d)
        active_sigs.add(d.signature)
        new.append(d.id)

    # 4. decide
    active = [d for d in ev.defects if d.status in ACTIVE | {"persisting"} and d.severity in pol.blocking_severities
              and not d.deferred]
    untraced = [d for d in active if d.traced_node not in idx.nodes or not d.smallest_fix.strip()
                or not d.acceptance_check.strip()]
    res.dim("GAT-TRACE", not untraced, f"{len(active) - len(untraced)}/{len(active)} blocking defects traced with a fix "
            "and an acceptance check" + (f"; untraced: {', '.join(d.id for d in untraced)}" if untraced else ""),
            [{"message": f"{d.id} `{d.signature}` has no routable trace, fix or acceptance check", "severity": "P2"}
             for d in untraced])
    still_open = [f.id for f in ev.feedback if f.status == "open"]
    res.dim("GAT-FEEDBACK", not still_open, f"open feedback after diagnosis: {still_open or 'none'}")
    for d in active:
        # "needs a human" is derived from the conditions below at every gate, so it lifts once they no longer hold: a
        # budget reset restores a spent edge, a change request unlocks a document (backlog B-01)
        why = None
        if d.traced_node not in pol.regeneration_targets:
            why = f"{d.traced_node} is not a regeneration target"
        elif (spent := _spent_rework_edge(eng, d.traced_node)) is not None:
            # one budget: a cycle the policy allows but the target's loop edge cannot carry blocks here, at the gate, not
            # later at N17 with a report that said "rework" (field run W23)
            why = (f"its rework edge {spent.id} ({spent.source} → {spent.target}) has used all {spent.max_traversals} "
                   "traversals (`unblock … --reset-budget` restores them)")
        elif locked := eng.controls.needs_change_request(d.traced_node, idx.nodes[d.traced_node].controls.write):
            why = (f"fixing it changes locked {', '.join(locked)}.md "
                   f"(approve a change request with --writer {d.traced_node})")
        if why:
            d.status = "needs_human"
            d.history.append(f"{now()} needs a human: {why}")
        elif d.status == "needs_human":
            d.status = "open"
            d.history.append(f"{now()} routable again at v{version}: nothing needs a human any more")
    needs_human = [d for d in active if d.status == "needs_human"]
    repeated = [d for d in active if d.failures >= pol.max_same_defect_failures]
    cycles = st.runtime.rework_cycles
    counted = eng.budget_resets()   # a reset restarts the count, so the gate says how many (field run W59)
    resets = resets_text(counted) if counted else ""
    res.dim("GAT-ESCALATE", True, f"failed-correction limit {pol.max_same_defect_failures}; cycles {cycles}/"
            f"{pol.max_rework_cycles}{f' after {resets}' if resets else ''}; repeated: {[d.id for d in repeated] or 'none'}")
    if stale:
        outcome = "blocked"
        reasons.append(f"reviews missing or stale for build v{version}: {', '.join(stale)}")
    elif not active:
        outcome = "pass"
        reasons.append(f"no blocking defect open at build v{version}")
    elif needs_human or repeated or cycles >= pol.max_rework_cycles:
        outcome = "blocked"
        reasons += [f"{d.id} needs a human: {d.history[-1]}" for d in needs_human]
        reasons += [f"{d.id} failed {d.failures} corrections (limit {pol.max_same_defect_failures})" for d in repeated]
        if cycles >= pol.max_rework_cycles:
            reasons.append(f"rework budget spent ({cycles}/{pol.max_rework_cycles} cycles{f', after {resets}' if resets else ''})")
    else:
        outcome = "rework"
        reasons.append(f"{len(active)} blocking defect(s) routed to {', '.join(idx.order({d.traced_node for d in active}))}")
    targets = idx.order({d.traced_node for d in active}) if outcome == "rework" else []
    by_target = {t: [d.id for d in active if d.traced_node == t] for t in targets}

    # 5. before/after comparison for the correction just made
    plan = _latest_plan(eng)
    plan_id = eng.current("regeneration_plan")[-1].id if plan else ""

    def compared(c) -> bool:
        # the plan id, not the cycle number: a budget reset restarts the numbering, and keying on it skipped every later
        # cycle's comparison (field run W38). A comparison saved before the id existed matches on cycle and version.
        return c.plan == plan_id if c.plan else (c.cycle, c.before_version) == (plan["cycle"], plan.get("before_version", 0))

    if plan and plan.get("cycle") and not any(compared(c) for c in ev.comparisons):
        after = {t: {a.key: a.sha256 for a in st.artifacts.values() if a.node == t and a.current}
                 for t in plan.get("targets", [])}
        new_blocking = [x for x in new if any(d.id == x and d.severity in pol.blocking_severities for d in ev.defects)]
        verdict = ("regressed" if len(new_blocking) > len(resolved) else
                   "improved" if resolved else "unchanged")
        ev.comparisons.append(Comparison(cycle=plan["cycle"], targets=plan.get("targets", []),
                                         before_version=plan.get("before_version", 0), after_version=version,
                                         before={f"{t}:{k}": v for t, kv in plan.get("before", {}).items() for k, v in kv.items()},
                                         after={f"{t}:{k}": v for t, kv in after.items() for k, v in kv.items()},
                                         resolved=resolved, persisting=persisting, new=new, verdict=verdict, at=now(),
                                         plan=plan_id))
    gr = GateResult(node=ctx.node.id, cycle=cycles, build_version=version, outcome=outcome, reasons=reasons,
                    blocking_defects=[d.id for d in active], targets=targets, at=now(),
                    answered=[a.model_dump() for a in interp.answered_findings],
                    **_severity_calls(interp, current_findings, pol))
    ev.gates.append(gr)
    # a rework cycle's advisories it may leave open, with what fixes each; a passing gate ships them (the release lists
    # them) and a blocked one's escalation lists every open defect (W54 review I3)
    stranded = stranded_advisories(eng, targets) if outcome == "rework" else []
    claimed = [d for d in ev.defects if d.deferred and d.claimed_fixed is not None
               and d.status in ("open", "persisting", "needs_human", "in_rework")]
    # a review may say only that a deferred defect it was asked to re-verify no longer holds; any other claim is named
    deferred_now = {d.id: d for d in ev.defects if d.deferred and d.status in ("open", "persisting", "needs_human", "in_rework")}
    ignored = refused + [f"{n} says {i} no longer holds, but "
               + ("it is not an open deferred defect" if i not in deferred_now else f"{n} was not asked to re-verify it")
               for n, rv in latest.items() if rv and rv.build_version == version for i in rv.no_longer_holds
               if i not in deferred_now or n not in rechecking_reviewers(eng, deferred_now[i])]
    report = {**gr.model_dump(), "resolved": resolved, "persisting": persisting, "new": new,
              "deferred_claimed_fixed": [{"id": d.id, "signature": d.signature, **d.claimed_fixed.model_dump(),
                                          "decide": decide_deferred_command(eng, d)} for d in claimed],
              "no_longer_holds_ignored": ignored,
              "defects": [d.model_dump() for d in active], "defects_by_target": by_target,
              "stranded_advisories": [{"id": d.id, "signature": d.signature, "severity": d.severity,
                                       "traced_node": d.traced_node, "message": d.message, "why": why,
                                       "remedy": advisory_remedy(eng, d, cycles + 1)} for d, why in stranded]}
    path = ctx.out("gate-report.json")
    write_json_atomic(path, report)
    eng.ledger.append("gate", node=ctx.node.id, outcome=outcome, build_version=version, blocking=gr.blocking_defects,
                      targets=targets, resolved=resolved, persisting=persisting, stranded=[d.id for d, _ in stranded])
    res.outcome = outcome
    res.outputs["gate_report"] = str(path)
    res.data = {"targets": targets, "defects_by_target": by_target, "stranded": [d.id for d, _ in stranded],
                "report": reasons + [f"{d.id} `{d.signature}` → {d.traced_node} ({d.status})" for d in active]
                + [f"{d.id} `{d.signature}` is deferred, and at v{d.claimed_fixed.at} {', '.join(d.claimed_fixed.by)} said it "
                   "no longer holds" + (f" ({', '.join(d.claimed_fixed.silent)}, also asked, filed nothing)"
                                        if d.claimed_fixed.silent else "")
                   + f": a person checks and decides (`{decide_deferred_command(eng, d)}`, or `--keep` if it still holds)"
                   for d in claimed]
                + [f"ignored: {x}" for x in ignored]}
    return res


def _latest_plan(eng) -> dict[str, Any] | None:
    recs = eng.current("regeneration_plan")
    if not recs:
        return None
    return json.loads((eng.project.root / recs[-1].path).read_text())


def regeneration_plan(ctx: "NodeContext") -> CheckResult:
    eng = ctx.engine
    st, pol = eng.state, eng.wf.policies
    gate = st.evaluation.gates[-1] if st.evaluation.gates else None
    res = CheckResult()
    if gate is None or gate.outcome != "rework":
        res.outcome = "no_target"
        res.data = {"report": ["no rework gate to plan from"]}
        path = ctx.out("regeneration-plan.json")
        write_json_atomic(path, {"cycle": None, "targets": []})
        res.outputs["regeneration_plan"] = str(path)
        return res
    targets = [t for t in gate.targets if t in pol.regeneration_targets]
    defects = [d for d in st.evaluation.defects if d.id in gate.blocking_defects]
    by_target = {t: [d.id for d in defects if d.traced_node == t] for t in targets}
    snapshot = {t: {a.key: a.sha256 for a in st.artifacts.values() if a.node == t and a.current} for t in targets}
    plan = {"cycle": st.runtime.rework_cycles + 1, "gate_cycle": gate.cycle, "targets": targets,
            "defects_by_target": by_target, "before_version": st.build.version, "before": snapshot,
            "defects": [{"id": d.id, "signature": d.signature, "traced_node": d.traced_node, "smallest_fix": d.smallest_fix,
                         "acceptance_check": d.acceptance_check} for d in defects],
            "untouched": [n for n in eng.idx.order(set(eng.idx.nodes))
                          if n not in targets and not any(n in eng.idx.descendants(t) for t in targets)]}
    path = ctx.out("regeneration-plan.json")
    write_json_atomic(path, plan)
    res.outputs["regeneration_plan"] = str(path)
    res.outcome = "rework" if targets else "no_target"
    res.data = {"targets": targets, "defects_by_target": by_target,
                "report": [f"cycle {plan['cycle']}: re-open {', '.join(targets) or 'nothing'}"]}
    return res


def check_targeted(ctx: "NodeContext") -> CheckResult:
    eng = ctx.engine
    plan = json.loads(ctx.output("regeneration_plan").read_text())
    res = CheckResult()
    targets = plan.get("targets", [])
    bad = [t for t in targets if t not in eng.wf.policies.regeneration_targets or not plan["defects_by_target"].get(t)]
    res.dim("RGN-TARGETED", not bad, f"targets {targets or '—'}; untouched upstream/sibling nodes: "
            f"{len(plan.get('untouched', []))}" + (f"; unjustified: {bad}" if bad else ""))
    return res


def package_manifest(pkg: Path) -> dict[str, str]:
    """Relative path → sha256 of every file in the release package except its own top-level manifest. A nested
    `manifest.json` (a web app manifest, say) is part of the package and is hashed like any other file."""
    return {rel(p, pkg): sha256_file(p) for p in sorted(pkg.rglob("*")) if p.is_file() and p != pkg / "manifest.json"}


HUMAN_ACTIONS = {   # ledger event → (what it records, the field naming the actor, the field holding the reason)
    "decision": ("gate decision", "actor", "reason"), "change_request": ("change request", "by", "reason"),
    "unblocked": ("unblock", "actor", "note"), "config_accepted": ("configuration accepted", "actor", "reason"),
    "risk_accepted": ("risk accepted", "actor", "reason"), "ledger_break_accepted": ("ledger break accepted", "actor", "reason"),
    "gap_waived": ("intake gap waived", "by", "reason"), "controls_restored": ("controls restored", "actor", ""),
    "rollback": ("rollback", "actor", ""),
    "human_invalidated": ("invalidation", "actor", "reason"), "delegation_granted": ("delegation granted", "by", "instruction"),
    "delegation_revoked": ("delegation revoked", "by", ""),
    "recheck_declined": ("release re-check declined", "actor", "reason"),
    "ratified": ("ratification", "actor", "reason"),
}
FAST_DECISION_S = 60
DELEGATED_KINDS = {"decision": "gate decision", "change_request": "change request", "risk_accepted": "risk acceptance",
                   "unblocked": "unblock", "config_accepted": "configuration acceptance", "gap_waived": "intake gap waiver",
                   "human_invalidated": "forced re-run", "controls_restored": "control restore"}


def human_action_actor(kind: str, data: dict[str, Any]) -> str:
    """The actor whose name a human-only ledger event used, or '' for events outside the human record."""
    if kind not in HUMAN_ACTIONS:
        return ""
    return str(data.get(HUMAN_ACTIONS[kind][1]) or "")


def transcribed_action(kind: str, data: dict[str, Any], humans: list[str]) -> bool:
    """True when a human-only event needs typist/ratification attention. A delegate acting as itself under a grant is not
    an untyped human action; only a named human's missing typist is."""
    actor = human_action_actor(kind, data)
    recorded_by = data.get("recorded_by")
    if recorded_by and actor and recorded_by != actor:
        return True
    if data.get("interprets"):
        return True
    return kind in HUMAN_ACTIONS and actor in humans and not recorded_by


def _one_line(text: Any) -> str:
    """Free text (a human's quoted words, a stated reviewer) inside one Markdown list item."""
    return " ".join(str(text).split())


def _severity_calls(interp: Interpretation, findings: list, pol) -> dict[str, list[str]]:
    """Which reviewer findings stored advisory (with the reviewer's own P1–P3) the interpretation raised to a blocking
    defect, and which it kept advisory. The call is the interpreter's; the record makes it visible (field run W25)."""
    blocking = [di for di in interp.defects if di.severity in pol.blocking_severities]
    cited = {x: di.id for di in blocking for x in di.from_findings} | {di.signature: di.id for di in blocking}
    answered = {a.finding for a in interp.answered_findings}
    raised, kept = [], []
    for f in findings:
        if f.by == "tool" or f.blocking or f.reported_severity not in ("P1", "P2", "P3"):
            continue
        key = f"{f.node}:{f.signature}"
        if key in cited or f.signature in cited:
            raised.append(f"{key} (reviewer {f.reported_severity}) → {cited.get(key) or cited[f.signature]}")
        elif key not in answered:
            kept.append(f"{key} (reviewer {f.reported_severity}): {_one_line(f.message)[:160]}")
    return {"raised": raised, "kept_advisory": kept}


def _kept_advisory_lines(eng: "Engine") -> list[str]:
    """The reviewer severities the last gate kept advisory: known concerns the release did not act on."""
    gates = eng.state.evaluation.gates
    return [f"- {k}" for k in (gates[-1].kept_advisory if gates else [])]


def _open_defect_lines(eng: "Engine") -> list[str]:
    """Every defect still open at release (none can block, or release would have failed): its severity and the reviewer's
    own when the interpretation kept it advisory, and whether fixing it waits on a human (field run W26)."""
    current = eng._current_findings()
    out = []
    for d in eng.state.evaluation.defects:
        if d.status not in ("open", "persisting", "needs_human", "in_rework") or d.deferred:
            continue
        stated = next((f.reported_severity for f in current if f.signature == d.signature and f.reported_severity), None)
        node = eng.idx.nodes.get(d.traced_node)
        locks = [f"{doc}.md ({eng.state.controls[doc].locked_by})" for doc in (node.controls.write if node else [])
                 if doc in eng.state.controls and eng.state.controls[doc].status == "locked"]
        waits = (f"; fixing it changes locked {', '.join(locks)}, so a human decides" if locks
                 else "; waits on a human" if d.status == "needs_human" else "")
        out.append(f"- **{d.id}** {d.severity}{f' (the reviewer said {stated})' if stated else ''} `{d.signature}` → "
                   f"{d.traced_node} ({d.status}){waits}: {_one_line(d.message)}")
    return out


def _answered_lines(eng: "Engine") -> list[str]:
    """Every review finding the interpreter answered as not a defect, with its latest answer (field run W22)."""
    latest: dict[str, dict[str, str]] = {}
    for g in eng.state.evaluation.gates:
        for a in g.answered:
            latest[a["finding"]] = {**a, "build": str(g.build_version)}
    return [f"- `{a['finding']}` at build v{a['build']}: {_one_line(a['reason'])}; checked by {_one_line(a['checked_by'])}: "
            f"{_one_line(a['evidence'])}" for a in latest.values()]


def _reviewer_lines(eng: "Engine") -> list[str]:
    """Who performed each current review, as the review itself states it. pdg cannot see which agent ran a node, so an
    unstated or self-declared review is shown as such rather than presumed independent."""
    out = []
    for n in eng.idx.reviewer_nodes():
        r = eng.latest_review(n)
        if r is None:
            continue
        if r.summary == "tool checks only" and not r.reviewer:
            who = "tool checks only, no agent review"
        else:
            who = (_one_line(r.reviewer) or "reviewer not stated") + {
                True: "; independent of the reviewed work (stated, not verified)",
                False: "; SELF-REVIEW: the reviewer produced work under review",
                None: "; independence not stated"}[r.independent]
        out.append(f"- {n} (build v{r.build_version}): {who}")
    return out


def _delegation_lines(eng: "Engine") -> list[str]:
    """One line per grant: who granted it, who typed it and from what, its scope, and what was done under it."""
    used: dict[str, dict[str, int]] = {}
    for e in eng.ledger.events():
        if e["type"] in DELEGATED_KINDS and e["data"].get("delegation"):
            kinds = used.setdefault(e["data"]["delegation"], {})
            kinds[DELEGATED_KINDS[e["type"]]] = kinds.get(DELEGATED_KINDS[e["type"]], 0) + 1
    out = []
    for d in eng.state.history.delegations:
        typed = (f"typed by {d.recorded_by}{' from ' + _one_line(d.source) if d.source else ''}" if d.recorded_by
                 else "who typed it is not recorded")
        revoked = f"; revoked by {d.revoked_by} at {d.revoked_at[:16]}" if d.revoked_at else ""
        acts = ", ".join(f"{n} {k}{'s' if n != 1 else ''}" for k, n in sorted((used.get(d.id) or {}).items())) or "nothing"
        out.append(f"- **{d.id}** from {d.by} to `{d.agent}`, {typed}; scope {', '.join(d.scope)}; "
                   f"{'nodes ' + ', '.join(d.nodes) if d.nodes else 'every human gate'}; expires {d.expires[:16]}{revoked}. "
                   f"The words: “{_one_line(d.instruction)}” Used for: {acts}.")
    return out


def release_blockers(eng: "Engine") -> list[str]:
    """Blocking defects still open at release. A deferred one waits on Wei and is listed for him, so it does not hold the
    release that the gate let through (independent audit #5)."""
    return [d.id for d in eng.state.evaluation.defects if d.status in ACTIVE | {"in_rework", "persisting"}
            and d.severity in eng.wf.policies.blocking_severities and not d.deferred]


def deferred_lines(st) -> list[str]:
    """The defects deferred for a human decision, for the release summary: decisions for Wei, apart from the known
    defects (field run W39)."""
    return [f"- **{d.id}** {d.severity} `{d.signature}` → {d.traced_node}: {d.message[:140]} Deferred by {d.deferred_by}: "
            f"{d.deferred}. Comes back when: {d.deferred_trigger}. Decide with `pdg decide-deferred … {d.id}`."
            + (f" At v{d.claimed_fixed.at} {', '.join(d.claimed_fixed.by)} said it no longer holds: if a person confirms "
               f"it, `pdg decide-deferred … {d.id} --resolved` (field run W61)." if d.claimed_fixed is not None else "")
            for d in st.evaluation.defects if d.deferred and d.status in ("open", "persisting", "needs_human", "in_rework")]


def change_request_lines(st) -> list[str]:
    """Every change request, its decision and its cost, for the release summary: an agent's request that nobody
    decided stays visible as open (backlog N-04)."""
    return [f"- {c.id} on {c.doc}.md by `{c.by}` → {c.writer}: **{c.status}**"
            + (f" by {c.decided_by} ({c.decision_reason})" if c.decided_by else "")
            + (f"; re-runs {len(c.reruns)} node(s), re-asks {', '.join(c.gates) or 'no gate'}" if c.reruns else "")
            + f". {c.reason[:160]}" for c in st.history.change_requests]


def human_record(eng: "Engine") -> tuple[list[str], dict[str, int]]:
    """Every action taken under a named human's name, from the ledger. Identity is asserted, not authenticated, and an
    agent that types a human's name is recorded as that human, so the record shows what a reader needs to judge that:
    who, what, why, and for a gate decision how long the gate had been waiting. Decisions made within
    FAST_DECISION_S seconds of the gate opening, and reasons repeated word for word, are flagged."""
    import datetime as dt

    def cell(value: Any) -> str:
        return str(value).replace("|", "/").replace("\n", " ")[:120]

    rows, counts, opened, seen = [], {"actions": 0, "fast": 0, "repeated": 0, "untyped": 0}, {}, {}
    ratified = {r.target: r for r in eng.state.history.ratifications}
    for e in eng.ledger.events():
        data, kind = e["data"], e["type"]
        if kind == "awaiting_human":
            opened[data.get("node")] = e["ts"]
            continue
        if kind not in HUMAN_ACTIONS:
            continue
        what, who_key, why_key = HUMAN_ACTIONS[kind]
        actor = str(data.get(who_key, ""))
        delegated_by = str(data.get("on_behalf_of") or "")
        if not eng.is_human(actor) and not (delegated_by and eng.is_human(delegated_by)):
            continue
        why = str(data.get(why_key, "")) if why_key else ""
        flags, wait = [], ""
        if kind == "decision" and data.get("node") in opened:
            secs = (dt.datetime.fromisoformat(e["ts"]) - dt.datetime.fromisoformat(opened.pop(data["node"]))).total_seconds()
            wait = f"{secs:.0f} s"
            if secs < FAST_DECISION_S:
                flags.append(f"decided within {FAST_DECISION_S} s of the gate opening")
                counts["fast"] += 1
        if why.strip() and why.strip() in seen:
            flags.append(f"same reason as event {seen[why.strip()]}")
            counts["repeated"] += 1
        elif why.strip():
            seen[why.strip()] = e["seq"]
        counts["actions"] += 1
        if kind == "delegation_granted":   # typed by the human, or transcribed from their words by an agent?
            typist = data.get("recorded_by")
            flags.append(f"typed by {typist}{' from ' + cell(data['source']) if data.get('source') else ''}"
                         if typist else "who typed it is not recorded")
            if not typist and actor in eng.humans:
                counts["untyped"] += 1
        elif data.get("recorded_by") and data.get("recorded_by") != actor:
            flags.append(f"typed by {data['recorded_by']}{' from ' + cell(data.get('source', '')) if data.get('source') else ''}")
        elif not data.get("recorded_by") and actor in eng.humans:
            flags.append("who typed it is not recorded")
            counts["untyped"] += 1
        if data.get("interprets"):
            rat = ratified.get(str(e["seq"])) or ratified.get(str(data.get("id", "")))
            flags.append(f"interprets source words; reversed by {rat.actor} ({rat.reason})" if rat and rat.reverse
                         else f"interprets source words; ratified by {rat.actor} ({rat.reason})" if rat
                         else "interprets source words; unconfirmed")
        if delegated_by:
            flags.append(f"delegated by {delegated_by} ({data.get('delegation')})")
        target = data.get("node") or data.get("doc") or data.get("assumption") or data.get("gap") or data.get("id") or ""
        rows.append(f"| {e['seq']} | {e['ts'][:19]} | {what}{' ' + cell(target) if target else ''} | {cell(actor)} | "
                    f"{wait or '—'} | {cell(why) or '—'} | {'; '.join(flags) or '—'} |")
    return rows, counts


def release_verify(ctx: "NodeContext") -> CheckResult:
    eng = ctx.engine
    st = eng.state
    res = CheckResult()
    version = st.build.version
    conds: list[tuple[str, bool, str]] = []
    gate = st.evaluation.gates[-1] if st.evaluation.gates else None
    conds.append(("latest gate passed on the current build", bool(gate and gate.outcome == "pass" and gate.build_version == version),
                  f"gate {gate.outcome if gate else '—'} at v{gate.build_version if gate else '—'}; current v{version}"))
    blocking = release_blockers(eng)
    conds.append(("no blocking defect open", not blocking, f"open: {blocking or 'none'}"))
    stale = [r for r in eng.idx.reviewer_nodes() if not eng.latest_review(r) or eng.latest_review(r).build_version != version]
    conds.append(("every review current", not stale, f"stale: {stale or 'none'}"))
    proto = st.build.prototype
    ok_hash, detail = False, "no prototype"
    if proto:
        from .engine import tree_sha
        rec = st.artifacts[proto.artifact]
        ok_hash = tree_sha(eng.project.root / rec.path)[0] == rec.sha256
        detail = f"{rec.id} {rec.sha256[:12]}…"
    conds.append(("prototype hashes verify", ok_hash, detail))
    from .engine import ledger_health
    ok, n, msg = ledger_health(eng.pdg_dir / "ledger.jsonl", st.runtime.model_dump(mode="json"))
    conds.append(("ledger verifies", ok, f"{n} events: {msg}"))   # the chain AND its anchor in the saved state
    ups = [a for a in eng.idx.ancestors(ctx.node.id) if eng.rt(a).status != NodeStatus.PASSED
           and a != eng.idx.regen_node]
    conds.append(("every upstream node passed", not ups, f"not passed: {ups or 'none'}"))
    drift = eng.controls.drift()
    conds.append(("control documents untouched", not drift, "; ".join(drift) or "all match their accepted versions"))
    failed = [c for c in conds if not c[1]]
    res.dim("REL-CONDITIONS", not failed, "; ".join(f"{'✓' if c[1] else '✗'} {c[0]}" for c in conds))
    if failed:
        res.errors += [f"release condition failed: {c[0]} ({c[2]})" for c in failed]
        return res

    pkg = ctx.out("package")
    pkg.mkdir(parents=True, exist_ok=True)
    rec = st.artifacts[proto.artifact]
    shutil.copytree(eng.project.root / rec.path, pkg / "prototype", dirs_exist_ok=True, symlinks=True)
    shutil.copytree(eng.project.root / "controls", pkg / "controls", dirs_exist_ok=True, symlinks=True)
    evid = pkg / "evidence"
    evid.mkdir(exist_ok=True)
    for name, items in [("reviews", st.evaluation.reviews), ("gates", st.evaluation.gates),
                        ("defects", st.evaluation.defects), ("comparisons", st.evaluation.comparisons),
                        ("feedback", st.evaluation.feedback), ("approvals", st.history.approvals),
                        ("decisions", st.history.decisions), ("test-results", st.evaluation.test_results)]:
        write_json_atomic(evid / f"{name}.json", [i.model_dump(mode="json") for i in items])
    shutil.copyfile(eng.pdg_dir / "ledger.jsonl", evid / "ledger.jsonl")
    non_human = [a for a in st.history.approvals if not a.human]
    simulated = [f for f in st.evaluation.feedback if f.simulated]
    pending = sorted({(r.node, d.id) for r in st.evaluation.reviews if r.build_version == version
                      for d in r.dimensions if d.status == "pending_human"})
    advisory = sorted({(r.node, d.id) for r in st.evaluation.reviews if r.build_version == version
                       for d in r.dimensions if d.status == "advisory_fail"})
    unscored = sorted({(r.node, d.id) for r in st.evaluation.reviews if r.build_version == version
                       for d in r.dimensions if d.status == "not_scored"})
    sim_sessions = _simulated_sessions(eng)
    scripted = [a for a in non_human if not a.on_behalf_of]      # the dry-run actor's decisions
    delegated = [a for a in non_human if a.on_behalf_of]         # an agent's decisions under a named human's delegation
    said = []
    if scripted:
        said.append("it is a DRY RUN: approvals were scripted, not human")
    if delegated:
        grantors = ", ".join(sorted({a.on_behalf_of or "" for a in delegated}))
        said.append(f"{len(delegated)} of {len(st.history.approvals)} approval(s) were made by "
                    f"{', '.join(sorted({a.actor for a in delegated}))} on behalf of {grantors} under delegation "
                    f"{', '.join(sorted({a.delegation or '?' for a in delegated}))}, not by {grantors} (see Delegations)")
    parts = ["; ".join(said) or "every approval is human"]
    if sim_sessions and not _sessions(eng, simulated=False):
        parts.append(f"validation used simulated sessions only ({len(sim_sessions)}), which are not user evidence")
    open_lines = _open_defect_lines(eng)
    if open_lines:
        parts.append(f"{len(open_lines)} advisory defect(s) still open (see Defects still open at release)")
    tldr = f"Build v{version} passed every enforced gate after {st.runtime.rework_cycles} rework cycle(s); " + "; ".join(parts)
    lines = ["# Release summary", "", f"> **TL;DR:** {tldr}.", "",
             "## Conditions (recomputed at release: files re-hashed from disk, the rest from the engine's saved state)", ""]
    lines += [f"- {'✓' if c[1] else '✗'} {c[0]} — {c[2]}" for c in conds]
    lines += ["", "## Approvals that were not made by a human", ""]
    lines += [f"- {a.node}: {a.decision} by `{a.actor}`"
              f"{f' on behalf of `{a.on_behalf_of}` ({a.delegation})' if a.on_behalf_of else ''} — {a.reason}"
              for a in non_human] or ["- none"]
    lines += ["", "## Delegations (each action taken under one is the agent's, never the human's)", ""]
    lines += _delegation_lines(eng) or ["- none"]
    lines += ["", "## Who reviewed (as each review states it; pdg does not verify independence)", ""]
    lines += _reviewer_lines(eng) or ["- none"]
    lines += ["", "## Review findings the interpreter answered (not a defect; the reviewer's finding stays on record)", ""]
    lines += _answered_lines(eng) or ["- none"]
    lines += ["", "## Ledger events lost (a break a named human accepted)", ""]
    lines += [f"- {b.describe()}; accepted by {b.actor} ({b.at[:10]}): {b.reason}"
              for b in st.runtime.ledger_breaks] or ["- none"]
    lines += ["", "## Simulated validation (not user evidence)", ""]
    lines += [f"- {s}" for s in sim_sessions] or ["- none"]
    lines += [f"- feedback {f.id} from `{f.actor}` (simulated): {f.text[:120]}" for f in simulated]
    lines += ["", "## Human dimensions still pending (decided by Wei, never by an agent)", ""]
    lines += [f"- {n}: {d}" for n, d in pending] or ["- none"]
    lines += ["", "## Advisory (non-blocking) failures", ""]
    lines += [f"- {n}: {d}" for n, d in advisory] or ["- none"]
    lines += ["", "## Deferred for Wei's decision (each waits on a human, not a fix)", ""]
    lines += deferred_lines(st) or ["- none"]
    lines += ["", "## Defects still open at release (none blocks; each is a known issue)", ""]
    lines += open_lines or ["- none"]
    lines += ["", "## Change requests (an open one was never approved or declined)", ""]
    lines += change_request_lines(st) or ["- none"]
    lines += ["", "## Reviewer severities the last gate kept advisory (the interpreter's call; not acted on)", ""]
    lines += _kept_advisory_lines(eng) or ["- none"]
    rows, hc = human_record(eng)
    lines += ["", "## Human record (every action taken under a human's name)", "",
              f"{hc['actions']} action(s); {hc['fast']} gate decision(s) made within {FAST_DECISION_S} s of the gate opening; "
              f"{hc['repeated']} reason(s) repeated word for word. Identity is asserted by name, not authenticated: check "
              "that each of these was yours.", ""]
    lines += (["| Event | When (UTC) | Action | Actor | Wait | Reason | Flags |", "|---|---|---|---|---|---|---|"] + rows
              if rows else ["- none"])
    lines += ["", "## Dimensions not scored (never counted as a pass)", ""]
    lines += [f"- {n}: {d}" for n, d in unscored] or ["- none"]
    judged = release_checks(st)
    lines += ["", "## Checks this release was judged by (each node's tool checks when it last passed, up to release "
              "verification)", ""]
    for j in judged:
        if not j["code"]:
            lines.append(f"- not recorded (passed before pdg recorded it): {len(j['nodes'])} node(s) "
                         f"({', '.join(j['nodes'])})")
            continue
        gs = j.get("git_state") or {}
        dirty = gs.get("uncommitted_files") or []
        commits = gs.get("commits") or ([gs["commit"]] if gs.get("commit") else [])
        commit_text = f"; commits: {', '.join(c[:12] for c in commits)}" if commits else ""
        dirty_text = f"; uncommitted pdg files: {', '.join(dirty)}" if dirty else ""
        lines.append(f"- pdg code `{j['code'][:12]}` and configuration `{j['config'][:12]}`: "
                     f"{len(j['nodes'])} node(s) ({', '.join(j['nodes'])}){commit_text}{dirty_text}")
    if not judged:
        lines += ["- none recorded"]
    lines += ["", "After a pdg upgrade, `pdg status` says so, and `pdg recheck-release <project>` re-runs these checks on "
              "this build, read-only, and lists what now fails."]
    lines += ["", "## Rework", ""]
    lines += [f"- cycle {c.cycle}: targets {', '.join(c.targets)} · v{c.before_version} → v{c.after_version} · "
              f"resolved {c.resolved or '—'} · persisting {c.persisting or '—'} · {c.verdict}" for c in st.evaluation.comparisons] or ["- none"]
    summary = ctx.out("release-summary.md")
    summary.write_text("\n".join(lines) + "\n")
    shutil.copyfile(summary, pkg / "RELEASE-SUMMARY.md")
    manifest = package_manifest(pkg)
    write_json_atomic(pkg / "manifest.json", {"build_version": version, "files": manifest, "judged_by": judged})
    verified = all(sha256_file(pkg / k) == v for k, v in manifest.items())
    res.dim("REL-PACKAGE", verified and bool(manifest), f"{len(manifest)} files hashed in manifest.json")
    text = summary.read_text()
    honest = (all(a.actor in text for a in non_human) and all(f.id in text for f in simulated)
              and all(b.describe() in text for b in st.runtime.ledger_breaks))
    res.dim("REL-HONEST", honest, f"{len(non_human)} non-human approvals, {len(simulated)} simulated feedback items and "
                                  f"{len(st.runtime.ledger_breaks)} accepted ledger breaks listed")
    report = {"build_version": version, "conditions": [{"condition": c[0], "ok": c[1], "evidence": c[2]} for c in conds],
              "non_human_approvals": [a.model_dump() for a in non_human], "simulated_sessions": sim_sessions,
              "pending_human_dimensions": [f"{n}:{d}" for n, d in pending], "package": rel(pkg, eng.project.root)}
    rpath = ctx.out("release-report.json")
    write_json_atomic(rpath, report)
    res.outputs.update({"release_report": str(rpath), "release_summary": str(summary), "package": str(pkg)})
    res.outcome = "pass"
    res.data = {"report": [tldr]}
    return res


def _sessions(eng, simulated: bool) -> list[str]:
    out = []
    for a in eng.current("validation"):
        doc = json.loads((eng.project.root / a.path).read_text())
        out += [f"{s['participant']} ({s['role']})" for s in doc.get("sessions", []) if bool(s.get("simulated")) == simulated]
    return out


def _simulated_sessions(eng) -> list[str]:
    return _sessions(eng, simulated=True)


def learning_proposal(ctx: "NodeContext") -> CheckResult:
    eng = ctx.engine
    st = eng.state
    lessons = LessonsDoc.model_validate(json.loads(ctx.output("lessons").read_text()))
    rule_of = {dim: d.get("rule") for dim, d in eng.dims.items()}
    observations: dict[str, dict[str, Any]] = {}
    for d in st.evaluation.defects:
        rule = rule_of.get(d.dimension)
        if not rule:
            continue
        # counts, not a yes/no: "every defect resolved" read a rule that drove 25 defects and saw 22 fixed as not
        # helping (backlog B-05). A rule helped when defects it raised were fixed.
        ob = observations.setdefault(rule, {"rule": rule, "fired": True, "defects": 0, "resolved": 0, "open": 0,
                                            "evidence": []})
        ob["evidence"].append(d.id)
        ob["defects"] += 1
        ob["resolved"] += d.status == "resolved"
        ob["open"] += d.status in ("open", "in_rework", "persisting", "needs_human")
    for ob in observations.values():
        ob["helped"] = ob["resolved"] > 0
    for les in lessons.lessons:
        if les.rule_id:
            ob = observations.setdefault(les.rule_id, {"rule": les.rule_id, "fired": False, "helped": les.helped,
                                                       "evidence": []})
            ob["lesson_helped"] = les.helped          # the lesson's own verdict, kept beside the counts
            ob["evidence"] += les.evidence
    for ob in observations.values():
        ob["evidence"] = sorted(set(ob["evidence"]))
    candidates = []
    run_tag = hashlib.sha1(st.project.id.encode()).hexdigest()[:6].upper()
    for les in lessons.lessons:
        if les.rule_id is None and les.scope == "reusable":
            target_scope = les.target_scope or les.category or "evidence_and_process"
            candidates.append({"id": f"R-NEW-{run_tag}-{les.id.replace('-', '')}", "statement": les.statement,
                               "evidence": les.evidence, "evidence_class": les.evidence_class, "scope": "stable",
                               "origin": f"lesson {les.id} from run {st.project.id}",
                               "category": les.category or "evidence_and_process", "target_scope": target_scope})
    proposal = {"run": f"{st.project.id}@v{st.build.version}", "created": now(), "rules_version": eng.rules.version,
                "observations": sorted(observations.values(), key=lambda o: o["rule"]), "candidates": candidates,
                "project_specific": [les.model_dump() for les in lessons.lessons if les.scope == "project_specific"],
                "apply_with": "python -m pdg memory apply --proposal <this file> --approved-by <human>"}
    path = ctx.out("learning-proposal.json")
    write_json_atomic(path, proposal)
    res = CheckResult(outcome="pass", outputs={"learning_proposal": str(path)})
    res.data = {"proposal": f"{ctx.node.id}/learning_proposal/a{ctx.attempt}"}
    eng.ledger.append("learning_proposal", observations=len(observations), candidates=len(candidates))
    return res
