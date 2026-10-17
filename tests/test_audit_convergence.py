"""The review gate converges: a defect is resolved once the node that owns its fix has re-run and nobody reports it any
more, whatever path the fix took (targeted rework, a change request, a human adding a source). Found by analogy with
vpg's first real run, which ended BLOCKED at version 8 on 20 already-fixed defects (vpg finding #46)."""

from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path

import pytest

import pdg.tools.browser as browser
from pdg.context import CheckResult, NodeContext
from pdg.engine import Engine, EngineError
from pdg.gating import review_gate

from .conftest import copy_example, fake_browser

GATE, REGEN = "n16_feedback_diagnosis", "n17_targeted_rework"
SOURCES, PROBLEM, INTERACTION = "n02_evidence_review", "n03_problem_definition", "n08_interaction_design"


@pytest.fixture(scope="module")
def finished(tmp_path_factory) -> Path:
    project = copy_example(tmp_path_factory.mktemp("converge") / "proj")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(browser, "check", fake_browser)
        eng = Engine(project)
        eng.run(max_steps=400)
    assert eng.state.runtime.status.value == "RUN_PASS"
    return project


@pytest.fixture
def eng(finished, tmp_path, fast_browser) -> Engine:
    copy = tmp_path / "run"
    shutil.copytree(finished, copy, symlinks=True)
    return Engine(copy)


def _gate(eng: Engine, tmp_path: Path, defects: list[dict] | None = None):
    work = tmp_path / f"gate-{len(eng.state.evaluation.gates)}"
    work.mkdir()
    interpretation = work / "interpretation.json"
    interpretation.write_text(json.dumps({"defects": defects or [], "feedback": [], "summary": "convergence"}))
    ctx = NodeContext(eng, eng.node(GATE), 90, work, "t", "")
    ctx.submitted = {"interpretation": interpretation}
    res = review_gate(ctx)
    return res, eng.state.evaluation.gates[-1]


def _defect(traced_node: str, signature: str = "EVIDENCE-GAP@queue") -> dict:
    return {"id": "D-950", "signature": signature, "dimension": "STAKEHOLDER-FEEDBACK", "severity": "P2",
            "message": "The queue cites a supplier SLA no source supports", "evidence": "Wei's feedback",
            "traced_node": traced_node, "trace_reason": "the claim needs a source", "smallest_fix": "add or drop the source",
            "acceptance_check": "every SLA claim cites a registered source"}


def _d(eng: Engine):
    return next(d for d in eng.state.evaluation.defects if d.id == "D-950")


def _reran(eng: Engine, node: str) -> None:
    """The node that owns the fix re-ran and passed (a change request, a new source, a rework): its attempt moved on."""
    eng.rt(node).attempt += 1


def _review_now(eng: Engine, findings) -> None:
    """A current review by N13 on the current build, carrying exactly these findings."""
    from pdg.models import ReviewRecord
    eng.state.evaluation.reviews.append(ReviewRecord(
        node="n13_quality_review", attempt=eng.rt("n13_quality_review").attempt, build_version=eng.state.build.version,
        dimensions=[], findings=findings, passed=True, at="2026-09-28T00:00:00+00:00"))


def _plan_rework(eng: Engine, targets: dict[str, list[str]]) -> None:
    """N17's side effect, through the engine's own code: the traced defects go into rework."""
    eng._gate_side_effects(eng.node(REGEN), CheckResult(data={"targets": sorted(targets), "defects_by_target": targets}))


def test_a_defect_on_a_node_outside_the_rework_targets_resolves_once_its_node_reran(eng, tmp_path):
    """A missing source (traced to N02) needs a human: Wei adds the source and N02 re-runs. The next gate must resolve
    the defect instead of marking it 'needs a human' again forever."""
    res, gate = _gate(eng, tmp_path, [_defect(SOURCES)])
    assert gate.outcome == "blocked" and _d(eng).status == "needs_human"
    _reran(eng, SOURCES)
    res, gate = _gate(eng, tmp_path)                                         # nobody reports it any more
    assert _d(eng).status == "resolved" and gate.outcome == "pass", gate.reasons


def test_a_correction_that_leaves_the_build_unchanged_still_resolves(eng, tmp_path):
    """A wording fix in experience.md (N08) need not change the prototype, so the build version stays. The corrected
    defect must resolve rather than count as a failed correction (three of those would block the run)."""
    version = eng.state.build.version
    res, gate = _gate(eng, tmp_path, [_defect(INTERACTION)])
    assert gate.outcome == "rework" and gate.targets == [INTERACTION]
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    _reran(eng, INTERACTION)
    res, gate = _gate(eng, tmp_path)
    assert eng.state.build.version == version
    assert _d(eng).status == "resolved" and _d(eng).failures == 0 and gate.outcome == "pass", _d(eng).history


def test_a_defect_fixed_through_a_change_request_resolves_without_another_rework_cycle(eng, tmp_path):
    """The fix changes locked product.md, so it needs a human. Wei approves a change request, N03 re-runs and fixes it:
    the next gate resolves it, instead of routing a second, redundant rework cycle (vpg finding #46)."""
    from pdg.models import NodeStatus
    res, gate = _gate(eng, tmp_path, [_defect(PROBLEM)])
    assert gate.outcome == "blocked" and _d(eng).status == "needs_human"
    cycles = eng.state.runtime.rework_cycles
    eng.change_request("product", "cite the SLA source in the problem statement", "Wei", writer=PROBLEM)
    rt = eng.rt(PROBLEM)
    rt.attempt, rt.status = rt.attempt + 1, NodeStatus.PASSED              # N03 re-ran and passed
    res, gate = _gate(eng, tmp_path)
    assert _d(eng).status == "resolved" and gate.outcome == "pass", (gate.reasons, _d(eng).history)
    assert eng.state.runtime.rework_cycles == cycles


def test_a_defect_whose_node_did_not_rerun_is_not_resolved(eng, tmp_path):
    """The guard: an interpreter that simply stops mentioning a defect resolves nothing."""
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    res, gate = _gate(eng, tmp_path)
    assert _d(eng).status == "open" and gate.outcome == "rework"


def test_a_defect_still_reported_after_its_node_reran_stays_open(eng, tmp_path):
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    _reran(eng, INTERACTION)
    res, gate = _gate(eng, tmp_path, [_defect(INTERACTION)])                # the interpreter still sees it
    assert _d(eng).status == "open" and gate.outcome == "rework"
    res, gate = _gate(eng, tmp_path)                                         # no new re-run since it was last seen
    assert _d(eng).status == "open", "a re-run before the defect was last seen is not a correction of it"


def test_a_reviewer_found_defect_needs_its_reviewer_to_look_again(eng, tmp_path):
    """A defect a reviewer found resolves only after that reviewer re-reviewed, not merely because its node re-ran."""
    found = dict(_defect(INTERACTION, "A11Y-FOCUS@queue"), dimension="A11Y-FOCUS", from_findings=["n13_quality_review:A11Y-FOCUS@queue"])
    _gate(eng, tmp_path, [found])
    assert "n13_quality_review" in _d(eng).source_nodes
    _reran(eng, INTERACTION)
    _gate(eng, tmp_path)
    assert _d(eng).status == "open"
    _reran(eng, "n13_quality_review")
    _gate(eng, tmp_path)
    assert _d(eng).status == "resolved"


def test_an_advisory_defect_resolves_once_its_node_reran_and_nobody_reports_it(eng, tmp_path):
    """Field run W13: a non-blocking (P4) defect is never routed for correction, so under the old rule, "resolves only
    through a correction made for it", it could never resolve, and a P4 fixed in a later rework stayed open in the
    release evidence for good. It now meets the same evidence as a blocking defect fixed another way."""
    _gate(eng, tmp_path, [dict(_defect(INTERACTION), severity="P4")])
    _reran(eng, INTERACTION)
    _gate(eng, tmp_path)
    assert _d(eng).status == "resolved"


def test_an_advisory_defect_a_review_still_reports_stays_open(eng, tmp_path):
    """An advisory defect is reported by an advisory (non-blocking) finding, so that finding keeps it open: judging it
    against blocking findings only would resolve it while a reviewer still reports it."""
    from pdg.models import FindingRecord

    found = dict(_defect(INTERACTION, "A11Y-FOCUS@queue"), dimension="A11Y-FOCUS", severity="P4",
                 from_findings=["n13_quality_review:A11Y-FOCUS@queue"])
    _gate(eng, tmp_path, [found])
    _reran(eng, INTERACTION)
    _reran(eng, "n13_quality_review")
    _review_now(eng, [FindingRecord(node="n13_quality_review", dimension="A11Y-FOCUS", location="queue", severity="P4",
                              message="the focus ring is faint on the queue", blocking=False)])
    _gate(eng, tmp_path)
    assert _d(eng).status == "open"
    _reran(eng, INTERACTION)
    _reran(eng, "n13_quality_review")
    _review_now(eng, [])
    _gate(eng, tmp_path)
    assert _d(eng).status == "resolved"


def test_a_defect_recorded_before_attempts_were_kept_uses_them_from_its_next_rework(eng, tmp_path):
    """A run started on an older pdg has defects without attempt markers. Its next rework records them, so a fix that
    leaves the build unchanged resolves from then on (instead of the old rule: a newer build)."""
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    _d(eng).attempts_at_start = {}                                           # as saved by an older pdg
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    assert _d(eng).attempts_at_start
    _reran(eng, INTERACTION)
    _gate(eng, tmp_path)
    assert _d(eng).status == "resolved"


def test_a_rework_packet_lists_the_advisory_defects_traced_to_its_node(eng, tmp_path):
    """Field run W17: the rework packet listed only the blocking defects under "fix exactly these defects (and nothing
    else)", so the one run that could fix an advisory defect traced to the node was told not to. The advisory ones are
    listed apart, as optional, and never put into rework, where a failed correction could escalate them."""
    from pdg.executors import render_packet
    advisory = dict(_defect(INTERACTION, "A11Y-FOCUS@queue"), id="D-951", dimension="A11Y-FOCUS", severity="P4")
    _gate(eng, tmp_path, [_defect(INTERACTION), advisory])
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    eng.invalidate([INTERACTION], "E3x from n17_targeted_rework (rework)", defects_by_target={INTERACTION: ["D-950"]})
    packet = eng.task_packet(eng._prepare(INTERACTION))
    assert [d["id"] for d in packet["rework"]] == ["D-950"]
    assert [d["id"] for d in packet["advisory"]] == ["D-951"]
    assert next(d for d in eng.state.evaluation.defects if d.id == "D-951").status == "open"   # not in rework
    md = render_packet(packet)
    assert "D-951" in md.split("## Advisory defects traced to this node")[1].split("\n## ")[0]
    assert "(and nothing else)" not in md


def test_a_re_review_packet_lists_the_open_defects_its_node_reported(eng, tmp_path):
    """Field run W18: re-review packets named no defect, though a defect resolves only when no current review reports
    its signature. A reviewer not told what is open cannot re-verify it, and one who re-files a still-true problem under
    another location resolves the old defect and opens a duplicate."""
    from pdg.executors import render_packet
    found = dict(_defect(INTERACTION, "A11Y-FOCUS@queue"), dimension="A11Y-FOCUS",
                 from_findings=["n13_quality_review:A11Y-FOCUS@queue"])
    _gate(eng, tmp_path, [found])
    packet = eng.task_packet(eng._prepare("n13_quality_review"))
    (d,) = packet["reverify"]
    assert (d["id"], d["signature"]) == ("D-950", "A11Y-FOCUS@queue") and d["acceptance_check"]
    section = render_packet(packet).split("## Open defects you are asked to re-verify")[1].split("\n## ")[0]
    assert "D-950" in section and "A11Y-FOCUS@queue" in section and "file nothing" in section
    assert not eng.task_packet(eng._prepare("n15_feasibility_review"))["reverify"]    # another reviewer's defect


def test_a_blocking_defect_a_review_still_reports_as_advisory_is_not_resolved(eng, tmp_path):
    """Field run W20: D-004 (P3, in rework) was re-reported by its reviewer under the same signature, but on a SHOULD
    dimension, so the finding was stored as advisory, and only blocking findings counted as "still reported" for a
    blocking defect: it would have resolved while the reviewer said it was still broken. Any current finding with the
    signature keeps a defect open."""
    from pdg.models import FindingRecord
    found = dict(_defect(INTERACTION, "A11Y-FOCUS@queue"), dimension="A11Y-FOCUS",
                 from_findings=["n13_quality_review:A11Y-FOCUS@queue"])
    _gate(eng, tmp_path, [found])
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    _reran(eng, INTERACTION)
    _reran(eng, "n13_quality_review")
    _review_now(eng, [FindingRecord(node="n13_quality_review", dimension="A11Y-FOCUS", location="queue", severity="P4",
                                    reported_severity="P2", message="still no visible focus on the queue", blocking=False)])
    _gate(eng, tmp_path)
    assert _d(eng).status == "persisting" and _d(eng).failures == 1


def test_a_node_reopened_mid_rework_is_told_which_of_its_defects_are_still_in_rework(eng, tmp_path):
    """Field run W21: N11 passed a rework attempt, then `pdg invalidate` re-opened it before the gate judged the rework.
    Its packet listed the advisory defects but not the 12 still in rework (`_pass` had cleared its rework list), so
    another agent could regress them."""
    from pdg.executors import render_packet
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    _plan_rework(eng, {INTERACTION: ["D-950"]})                  # in rework, not yet judged by a gate
    eng.invalidate([INTERACTION], "invalidated by agent:orchestrator: it missed part of D-950")   # as `pdg invalidate`
    packet = eng.task_packet(eng._prepare(INTERACTION))
    assert packet["rework"] == [] and [d["id"] for d in packet["in_rework"]] == ["D-950"]
    assert "D-950" in render_packet(packet).split("## Still in rework")[1].split("\n## ")[0]


def _interp_ctx(eng: Engine, tmp_path: Path, answers: list[dict]) -> NodeContext:
    work = tmp_path / f"interp-{len(answers)}-{len(list(tmp_path.iterdir()))}"
    work.mkdir()
    p = work / "interpretation.json"
    p.write_text(json.dumps({"defects": [], "feedback": [], "answered_findings": answers, "summary": "answers"}))
    ctx = NodeContext(eng, eng.node(GATE), 91, work, "t", "")
    ctx.submitted = {"interpretation": p}
    return ctx


def test_the_interpreter_can_answer_an_agent_finding_it_disproved_but_never_a_tool_finding(eng, tmp_path):
    """Field run W22: two agent findings did not reproduce on the build, but the interpretation could dismiss feedback
    only, so they stayed unanswered, and a blocking one would have forced a defect for a problem that does not exist.
    An answer needs its evidence and who checked; a tool finding cannot be answered away."""
    from pdg.models import FindingRecord
    _reran(eng, "n13_quality_review")                                   # a new review comes from a new attempt
    _review_now(eng, [FindingRecord(node="n13_quality_review", dimension="A11Y-NAME", location="case", severity="P2",
                                    message="the rationale field has no accessible name", by="agent", blocking=True),
                      FindingRecord(node="n13_quality_review", dimension="A11Y-AXE", location="case", severity="P2",
                                    message="axe: label", by="tool", blocking=True)])
    agent, tool = "n13_quality_review:A11Y-NAME@case", "n13_quality_review:A11Y-AXE@case"
    answer = {"finding": agent, "reason": "not reproduced", "checked_by": "agent:orchestrator",
              "evidence": "get_by_label finds each rationale field once on build v3"}
    gaps = eng._interpretation_gaps(_interp_ctx(eng, tmp_path, [answer]))
    assert not [g for g in gaps if "A11Y-NAME" in g]                     # answered: no defect needed
    assert any("evidence" in g for g in eng._interpretation_gaps(_interp_ctx(eng, tmp_path, [{**answer, "evidence": " "}])))
    assert any("tool finding" in g for g in eng._interpretation_gaps(
        _interp_ctx(eng, tmp_path, [{**answer, "finding": tool}])))
    assert any("no current finding" in g for g in eng._interpretation_gaps(
        _interp_ctx(eng, tmp_path, [{**answer, "finding": "n13_quality_review:NOPE@x"}])))


def test_an_answered_finding_is_recorded_on_the_gate_and_listed_at_release(eng, tmp_path):
    from pdg.gating import _answered_lines
    from pdg.models import FindingRecord
    _reran(eng, "n13_quality_review")
    _review_now(eng, [FindingRecord(node="n13_quality_review", dimension="A11Y-NAME", location="case", severity="P4",
                                    reported_severity="P2", message="no accessible name", by="agent", blocking=False)])
    answer = {"finding": "n13_quality_review:A11Y-NAME@case", "reason": "not reproduced", "checked_by": "agent:orchestrator",
              "evidence": "get_by_label finds each rationale field once on build v3"}
    work = tmp_path / "gate-answer"
    work.mkdir()
    (work / "interpretation.json").write_text(json.dumps({"defects": [], "feedback": [], "answered_findings": [answer],
                                                          "summary": "s"}))
    ctx = NodeContext(eng, eng.node(GATE), 92, work, "t", "")
    ctx.submitted = {"interpretation": work / "interpretation.json"}
    review_gate(ctx)
    assert eng.state.evaluation.gates[-1].answered[0]["finding"] == answer["finding"]
    (line,) = _answered_lines(eng)
    assert "A11Y-NAME@case" in line and "not reproduced" in line and "get_by_label" in line and "agent:orchestrator" in line


def test_the_gate_blocks_itself_when_a_targets_rework_edge_is_spent(eng, tmp_path):
    """Field run W23: the policy allows 4 rework cycles but each N17 → target edge 3 traversals, so the gate said "rework"
    (cycles 3/4) and the run then blocked at N17 on the spent edge: the report and the state disagreed. The gate now
    checks the edge and says blocked itself, naming it."""
    edge = next(e for e in eng.idx.outgoing[eng.idx.regen_node] if e.target == INTERACTION and e.kind.value == "loop")
    eng.state.runtime.loop_traversals[edge.id] = edge.max_traversals
    res, gate = _gate(eng, tmp_path, [_defect(INTERACTION)])
    assert gate.outcome == "blocked" and _d(eng).status == "needs_human"
    assert any(edge.id in r and "traversals" in r for r in gate.reasons)


def _block_on_a_spent_edge(eng: Engine, tmp_path: Path):
    from pdg.models import Escalation
    edge = next(e for e in eng.idx.outgoing[eng.idx.regen_node] if e.target == INTERACTION and e.kind.value == "loop")
    eng.state.runtime.loop_traversals[edge.id] = edge.max_traversals
    _, gate = _gate(eng, tmp_path, [_defect(INTERACTION)])
    assert gate.outcome == "blocked"
    eng.state.runtime.escalations.append(Escalation(id=f"{GATE}-9", node=GATE, reason="E29: outcome 'blocked'",
                                                    report="", at="2026-09-28T16:00:00+00:00"))
    return edge


def test_a_budget_reset_restores_the_spent_rework_edges(eng, tmp_path):
    """Backlog B-01, a regression from the W23 fix: the gate blocked on a spent N17 → target edge, but `unblock
    --reset-budget` reset only the gate's own loops, so the edge stayed spent and the gate blocked again at once. The
    rework edges are the same budget as the cycles, so the reset restores them, and the ledger says which."""
    edge = _block_on_a_spent_edge(eng, tmp_path)
    eng.unblock(GATE, "Wei", note="fund another cycle", reset_budget=True)
    assert eng.state.runtime.loop_traversals[edge.id] == 0
    assert edge.id in list(eng.ledger.events("unblocked"))[-1]["data"]["edges_reset"]


def test_a_defect_blocked_on_a_spent_edge_routes_again_after_the_reset(eng, tmp_path):
    """Backlog B-01: "needs a human" is re-derived at every gate, so once the reset restores the edge the same defect
    routes as rework instead of staying stuck at needs_human."""
    _block_on_a_spent_edge(eng, tmp_path)
    eng.unblock(GATE, "Wei", note="fund another cycle", reset_budget=True)
    _, gate = _gate(eng, tmp_path, [_defect(INTERACTION)])
    assert gate.outcome == "rework" and INTERACTION in gate.targets
    assert _d(eng).status == "open" and "routable again" in _d(eng).history[-1]


def test_a_rework_plan_re_run_for_the_same_gate_is_not_a_new_cycle(eng, tmp_path):
    """Field run W24: unblocking N17 re-ran its plan for the same gate and defects, and the count went from 4 to 5."""
    before = eng.state.runtime.rework_cycles
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    _plan_rework(eng, {INTERACTION: ["D-950"]})                        # N17 again after an unblock: same gate
    assert eng.state.runtime.rework_cycles == before + 1
    _gate(eng, tmp_path)
    _plan_rework(eng, {INTERACTION: ["D-950"]})                        # a new gate: a new cycle
    assert eng.state.runtime.rework_cycles == before + 2


def test_the_release_summary_lists_the_defects_still_open_and_counts_them_in_its_tldr(eng, tmp_path):
    """Field run W26: the run released with advisory defects open (two waiting on locked documents), but the summary
    listed only failed review dimensions, so a reader saw "passed every enforced gate" and no known issue."""
    from pdg.gating import release_verify
    from pdg.models import Defect
    eng.state.evaluation.defects.append(Defect(
        id="D-990", signature="DES-SPACING@queue", dimension="DES-SPACING", severity="P4", message="the queue rows crowd",
        evidence="n13 review", traced_node="n09_visual_system", trace_reason="the spacing scale",
        smallest_fix="widen the row gap", acceptance_check="rows keep 8 px apart", source_nodes=["n13_quality_review"],
        opened_at_version=eng.state.build.version, history=["opened"]))
    work = tmp_path / "release"
    work.mkdir()
    ctx = NodeContext(eng, eng.node("n18_final_verification"), 93, work, "t", "")
    res = release_verify(ctx)
    assert not res.errors, res.errors
    summary = (work / "release-summary.md").read_text()
    tldr = summary.split("> **TL;DR:**")[1].split("\n")[0]
    assert "1 advisory defect(s) still open" in tldr
    section = summary.split("## Defects still open at release")[1].split("\n## ")[0]
    assert "D-990" in section and "n09_visual_system" in section and "DES-SPACING@queue" in section
    assert "locked" in section                                   # the visual system is signed, so its fix needs a human


def test_the_gate_records_which_reviewer_severities_the_interpretation_raised_or_kept_advisory(eng, tmp_path):
    """Field run W25: whether a reviewer's P2 or P3 on a passing dimension blocks is the interpreter's call, and at the
    final gate that call decides between release and stopping for Wei. The engine does not make the call mid-run, but
    the gate now records it, and the release lists the reviewer severities the last gate kept advisory."""
    from pdg.gating import _kept_advisory_lines
    from pdg.models import FindingRecord
    _reran(eng, "n13_quality_review")
    _review_now(eng, [
        FindingRecord(node="n13_quality_review", dimension="DES-DENSITY", location="queue", severity="P4",
                      reported_severity="P2", message="the queue hides the due date", blocking=False),
        FindingRecord(node="n13_quality_review", dimension="DES-DENSITY", location="case", severity="P4",
                      reported_severity="P3", message="the case header wraps at 1024 px", blocking=False)])
    raised = dict(_defect(INTERACTION, "DES-DENSITY@queue"), dimension="DES-DENSITY",
                  from_findings=["n13_quality_review:DES-DENSITY@queue"])
    _gate(eng, tmp_path, [raised])
    gate = eng.state.evaluation.gates[-1]
    assert gate.raised == ["n13_quality_review:DES-DENSITY@queue (reviewer P2) → D-950"]
    assert gate.kept_advisory == ["n13_quality_review:DES-DENSITY@case (reviewer P3): the case header wraps at 1024 px"]
    assert any("DES-DENSITY@case" in ln and "P3" in ln for ln in _kept_advisory_lines(eng))


def _packet(eng: Engine, node_id: str, tmp_path: Path) -> dict:
    work = tmp_path / f"packet-{node_id}"
    work.mkdir(exist_ok=True)
    return eng.task_packet(NodeContext(eng, eng.node(node_id), eng.rt(node_id).attempt + 1, work, "t", ""))


def test_the_gates_packet_lists_every_open_feedback_item(eng, tmp_path):
    """Field run W31: 37 audit findings entered as feedback, and N16's packet said only that it re-ran "because new
    feedback FB-005". It now lists every open item, so the packet alone is enough to map them all."""
    from pdg.executors import render_packet
    for i in range(3):
        eng.add_feedback(f"audit finding {i}: focus hides under the top bar", "agent:a11y-auditor", f"queue:{390 + i}", "P2")
    packet = _packet(eng, GATE, tmp_path)
    assert len(packet["open_feedback"]) == 3 and {f["actor"] for f in packet["open_feedback"]} == {"agent:a11y-auditor"}
    text = render_packet(packet)
    assert "## Open feedback (3): map every item" in text and "audit finding 2" in text
    assert _packet(eng, INTERACTION, tmp_path)["open_feedback"] == []      # a node that doesn't read feedback


def test_a_node_re_running_inside_a_rework_cycle_is_told_the_cycles_fixes(eng, tmp_path):
    """Backlog N-19: a rework renamed a label (the spec's fix at N08, the build's at N11), and N10, which re-ran between
    them without defects of its own, resubmitted a plan whose scenarios still expected the old text. A node re-running
    inside a cycle, without being one of its targets, now gets the cycle's fixes to check its own work against."""
    from pdg.executors import render_packet
    _gate(eng, tmp_path, [_defect(INTERACTION, "UX-H2@queue#'Proposed' reads as a stage")])
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    plan = "n10_prototype_planning"
    fixes = _packet(eng, plan, tmp_path)["cycle_fixes"]
    assert [d["id"] for d in fixes] == ["D-950"] and fixes[0]["traced_node"] == INTERACTION
    assert "## Fixes in this rework cycle" in render_packet(_packet(eng, plan, tmp_path))
    assert _packet(eng, INTERACTION, tmp_path)["cycle_fixes"] == []         # a target has it as rework already
    assert _packet(eng, "n13_quality_review", tmp_path)["cycle_fixes"] == []  # a reviewer re-verifies instead
    from pdg.context import NodeResult
    eng.project.config["dry_run"] = False                                    # a real approver reads the note
    eng._await_human(eng.node(plan), eng.rt(plan), NodeResult(), {})
    assert "this rework cycle fixes D-950" in eng.rt(plan).gate_note


def test_a_rerun_packet_lists_blocking_defects_traced_to_the_node(eng, tmp_path):
    """W73: a change-request cascade still tells a node about open blocking defects traced to it."""
    _gate(eng, tmp_path, [_defect(INTERACTION, "UX-ORDER@home#section-order")])
    packet = _packet(eng, INTERACTION, tmp_path)
    listed = packet["blocking_traced_here"]
    assert [d["id"] for d in listed] == ["D-950"]
    assert listed[0]["smallest_fix"] and listed[0]["acceptance_check"]


def test_check_node_on_a_gate_writes_no_ledger_event(eng, tmp_path):
    """B23: gate hooks append ledger events, so check-node must defer and discard them."""
    from pdg.check_node import check_node
    from pdg.models import NodeStatus
    gate = eng.rt(GATE)
    gate.status, gate.attempt, gate.token = NodeStatus.WAITING_AGENT, gate.attempt + 1, "tok"
    work = eng.project.root / "work" / GATE / f"a{gate.attempt}"
    work.mkdir(parents=True, exist_ok=True)
    out = work / "interpretation.json"
    out.write_text(json.dumps({"defects": [], "feedback": [], "answered_findings": [], "summary": "clean"}))
    before = (eng.project.root / ".pdg" / "ledger.jsonl").read_text()
    rep = check_node(eng, GATE, {"interpretation": str(out)})
    assert not rep["refused"], rep
    assert (eng.project.root / ".pdg" / "ledger.jsonl").read_text() == before


def test_check_node_loads_review_precheck_outputs(eng, tmp_path):
    """B23: review nodes submit only their review; precheck outputs must not be reported missing."""
    from pdg.check_node import check_node
    from pdg.context import CheckResult, NodeContext
    from pdg.models import NodeStatus
    reviewer = "n13_quality_review"
    rt = eng.rt(reviewer)
    rt.status, rt.attempt, rt.token = NodeStatus.WAITING_AGENT, rt.attempt + 1, "tok"
    work = eng.project.root / "work" / reviewer / f"a{rt.attempt}"
    work.mkdir(parents=True, exist_ok=True)
    pre = CheckResult()
    report = work / "browser-report.json"
    report.write_text("{}")
    shots = work / "screenshots"
    shots.mkdir()
    pre.outputs = {"browser_report": str(report), "screenshots": str(shots)}
    ctx = NodeContext(eng, eng.node(reviewer), rt.attempt, work, "tok", "")
    ctx.precheck = pre
    eng._save_precheck(ctx)
    review = work / "quality_review.json"
    review.write_text(json.dumps({"dimensions": [], "findings": [], "summary": "draft"}))
    rep = check_node(eng, reviewer, {"quality_review": str(review)})
    assert not any("browser_report" in r or "screenshots" in r for r in rep["refused"])


def test_check_node_accepts_live_control_edit_that_submit_accepts(eng, tmp_path):
    """B23 round 2: live control outputs ignore their own temporary drift just like submit does."""
    from pdg.check_node import check_node
    from pdg.models import NodeStatus
    node = "n07_experience_architecture"
    rt = eng.rt(node)
    rt.status, rt.attempt, rt.token = NodeStatus.WAITING_AGENT, rt.attempt + 1, "tok"
    latest = eng.current("experience")[-1]
    live = eng.project.root / "controls" / "experience.md"
    live.write_text(live.read_text().replace("## Journeys\n", "## Journeys\n\nJ-live Live edit submitted in place.\n", 1))
    rep = check_node(eng, node, {"experience": str(eng.project.root / latest.path), "experience_md": str(live)})
    assert not rep["refused"], rep["refused"]


def test_rerun_packet_lists_changes_since_last_pass_in_ledger_order(eng, tmp_path):
    from pdg.executors import render_packet
    node = INTERACTION
    eng.change_request("experience", "old request before last pass", "Wei", writer="n07_experience_architecture")
    eng.rt(node).passed_attempt = eng.rt(node).attempt
    eng.ledger.append("node_passed", node=node, attempt=eng.rt(node).attempt, outcome="approved")
    declined = eng.change_request("experience", "declined request", "agent:ux-interaction-designer",
                                  writer="n07_experience_architecture")
    eng.decide_change_request(declined.id, False, "Wei", "not needed")
    eng.change_request("experience", "first request", "Wei", writer="n07_experience_architecture")
    eng.invalidate_nodes([node], "second invalidation", "Wei")
    changes = _packet(eng, node, tmp_path)["rerun_changes"]
    assert not any(c["reason"] == "old request before last pass" for c in changes)
    assert any(c["kind"] == "change_request" and c["reason"] == "first request" for c in changes)
    assert not any(c["reason"] == "declined request" for c in changes)
    assert changes[-1]["kind"] == "invalidation" and changes[-1]["reason"] == "second invalidation"
    assert [c["seq"] for c in changes] == sorted(c["seq"] for c in changes)
    assert len([c for c in changes if "second invalidation" in c["reason"]]) == 1
    assert "first request" in render_packet(_packet(eng, node, tmp_path))


def test_n16_recurrence_groups_include_only_active_defects(eng, tmp_path):
    _gate(eng, tmp_path, [_defect(INTERACTION, "UX-NAV@home:390#back")])
    active = _d(eng)
    active.history.append("reported again")
    resolved = active.model_copy(deep=True)
    resolved.id = "D-951"
    resolved.signature = "UX-NAV@home:390#breadcrumb"
    resolved.status = "resolved"
    resolved.history.append("reported again")
    eng.state.evaluation.defects.append(resolved)
    groups = _packet(eng, GATE, tmp_path)["convergence"]["recurring"]
    assert groups == [{"component": "home", "defects": ["D-950"]}]


def test_a_cycle_after_a_budget_reset_still_gets_its_before_and_after_comparison(eng, tmp_path):
    """Field run W38: comparisons were keyed on the cycle number, which a budget reset restarts, so the audit loop's
    cycles collided with cycles 1 and 2 of the first run and were never recorded. They are keyed on the plan now."""
    import json as _json
    from pdg.models import ArtifactRecord
    done = eng.state.evaluation.comparisons
    assert done, "the example's run compares at least one cycle"
    old = eng.current("regeneration_plan")[-1]
    plan = _json.loads((eng.project.root / old.path).read_text())
    plan.update(cycle=done[0].cycle, before_version=eng.state.build.version)      # the same number, after a reset
    path = eng.project.root / "work" / REGEN / "a90" / "regeneration_plan.json"
    path.parent.mkdir(parents=True)
    path.write_text(_json.dumps(plan))
    old.current = False
    new = old.model_copy(update={"id": f"{REGEN}/regeneration_plan/a90", "attempt": 90, "current": True,
                                 "path": str(path.relative_to(eng.project.root))})
    eng.state.artifacts[new.id] = new
    before = len(done)
    _gate(eng, tmp_path)
    assert len(eng.state.evaluation.comparisons) == before + 1
    assert eng.state.evaluation.comparisons[-1].plan == new.id and eng.state.evaluation.comparisons[-1].cycle == done[0].cycle
    _gate(eng, tmp_path)                                                          # the same plan: compared once
    assert len(eng.state.evaluation.comparisons) == before + 1


def test_the_planning_packet_says_which_riskiest_assumptions_need_a_named_humans_acceptance(eng, tmp_path):
    """Field run 2, R2-03: a mid or high fidelity plan fails PLN-FIDELITY-GATE while a riskiest assumption is neither
    validated nor accepted by a named human, and the agent learned that only by spending an attempt. The packet says so."""
    from pdg.executors import render_packet
    riskiest = [a for a in eng.state.research.assumptions if a.riskiest]
    assert riskiest, "the example has a riskiest assumption"
    eng.state.history.risk_acceptances.clear()
    brief = _packet(eng, "n10_prototype_planning", tmp_path)["fidelity_gate"]
    assert {a["id"] for a in brief} == {a.id for a in riskiest} and all(a["accepted_by"] is None for a in brief)
    text = render_packet(_packet(eng, "n10_prototype_planning", tmp_path))
    assert "## Before you submit: the fidelity gate" in text and "not accepted" in text
    assert _packet(eng, INTERACTION, tmp_path)["fidelity_gate"] is None


def test_a_resolved_defect_reported_again_re_opens_with_its_history(eng, tmp_path):
    """Field run W36: a later fix undid two resolved defects, and pdg noticed neither: the gate judged only open
    defects, and a finding at a resolved signature opened a new defect that hid the history. It re-opens the old one."""
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    d = _d(eng)
    d.status, d.resolved_at_version = "resolved", eng.state.build.version
    again = {**_defect(INTERACTION), "id": "D-977"}
    _gate(eng, tmp_path, [again])
    assert _d(eng).status == "open" and "re-opened" in _d(eng).history[-1]
    assert not [x for x in eng.state.evaluation.defects if x.id == "D-977"]


def test_a_tool_finding_at_a_resolved_signature_re_opens_the_defect(eng, tmp_path):
    """W36 for tool findings, which the gate maps from their own trace when the interpreter does not."""
    from pdg.models import FindingRecord
    _gate(eng, tmp_path, [_defect(INTERACTION, "A11Y-NAME@case")])
    d = _d(eng)
    d.status, d.resolved_at_version = "resolved", eng.state.build.version
    _reran(eng, "n13_quality_review")
    _review_now(eng, [FindingRecord(node="n13_quality_review", dimension="A11Y-NAME", location="case", severity="P2",
                                    message="no accessible name", by="tool", blocking=True, traced_node=INTERACTION,
                                    smallest_fix="name it", acceptance_check="each field has a name")])
    before = len(eng.state.evaluation.defects)
    _gate(eng, tmp_path)
    assert _d(eng).status == "open" and len(eng.state.evaluation.defects) == before


def test_a_reviewers_packet_lists_the_resolved_defects_it_found_as_still_fixed_checks(eng, tmp_path):
    """W36: the regression list. Each reviewer re-checks the resolved defects it found, on every build."""
    from pdg.executors import render_packet
    reviewer = "n13_quality_review"
    _gate(eng, tmp_path, [{**_defect(INTERACTION), "from_findings": [f"{reviewer}:EVIDENCE-GAP@queue"]}])
    d = _d(eng)
    d.status, d.resolved_at_version = "resolved", eng.state.build.version
    packet = _packet(eng, reviewer, tmp_path)
    ids = [x["id"] for x in packet["still_fixed"]]
    assert "D-950" in ids and all(x.status == "resolved" and reviewer in x.source_nodes
                                  for x in eng.state.evaluation.defects if x.id in ids)
    assert f"## Still fixed? Re-check the {len(ids)} resolved defects this review found" in render_packet(packet)
    assert "D-950" not in [x["id"] for x in _packet(eng, "n15_feasibility_review", tmp_path)["still_fixed"]]


def test_one_bug_under_two_signatures_stays_one_defect(eng, tmp_path):
    """Field run W28: two reviewers reported one bug at different signatures, and it stayed two identities. The other
    signatures its findings used become aliases, and a current finding at any alias still reports it."""
    from pdg.models import FindingRecord
    di = {**_defect(INTERACTION, "UX-H1@case:390#result"),
          "from_findings": ["n13_quality_review:UX-H1@case:390#result", "n15_feasibility_review:RESP-FIT@case:390"]}
    _gate(eng, tmp_path, [di])
    assert _d(eng).aliases == ["RESP-FIT@case:390"]
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    for n in (INTERACTION, "n13_quality_review", "n15_feasibility_review"):
        _reran(eng, n)
    _review_now(eng, [FindingRecord(node="n13_quality_review", dimension="RESP-FIT", location="case:390", severity="P2",
                                    message="the result is off screen", by="agent", blocking=True)])
    _gate(eng, tmp_path)
    assert _d(eng).status != "resolved"


def test_a_defect_raised_from_feedback_is_listed_for_the_reviewer_that_owns_its_dimension(eng, tmp_path):
    """Field run W30, backlog B-02: a defect raised from feedback had no source reviewer, so no re-review packet listed
    it and nobody re-checked the fix. The reviewer whose rubric scores its dimension (else N13) now re-verifies it."""
    from pdg.evaluation import node_dimensions
    owned = next(d["id"] for d in node_dimensions(eng.node("n15_feasibility_review"), eng.rubrics))
    _gate(eng, tmp_path, [{**_defect(INTERACTION), "dimension": owned}])
    assert [x["id"] for x in _packet(eng, "n15_feasibility_review", tmp_path)["reverify"]] == ["D-950"]
    assert _packet(eng, "n13_quality_review", tmp_path)["reverify"] == []
    _gate(eng, tmp_path, [{**_defect(INTERACTION, "UX-H3@queue"), "id": "D-951", "dimension": "UX-H3"}])
    assert "D-951" in [x["id"] for x in _packet(eng, "n13_quality_review", tmp_path)["reverify"]]  # unowned: N13


def test_a_wrong_acceptance_check_is_corrected_on_record_before_the_reviews(eng, tmp_path):
    """Field run W37: D-122's check ("at least 200 px wide at 320") could never pass, since the row itself is 182 px, and
    the next place to change it was the next interpretation, after the reviewers had judged against it."""
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    with pytest.raises(EngineError, match="delegation|named human"):
        eng.correct_check("D-950", "fills its row at 320 to 414", "the row is 182 px at 320", "agent:orchestrator")
    out = eng.correct_check("D-950", "the search field fills its row at 320 to 414", "the row is 182 px at 320", "Wei")
    assert out["now"] == _d(eng).acceptance_check and "corrected by Wei" in _d(eng).history[-1]
    assert list(eng.ledger.events("acceptance_check_corrected"))[-1]["data"]["was"] == out["was"]
    reviewer = next(r for r in eng.idx.reviewer_nodes() if any(x["id"] == "D-950" for x in _packet(eng, r, tmp_path)["reverify"]))
    assert _packet(eng, reviewer, tmp_path)["reverify"][-1]["acceptance_check"] == out["now"]


def test_status_says_where_the_latest_build_is_and_how_blocking_defects_trend(eng, tmp_path, capsys):
    """Backlog N-07 and N-02: the first project's README hard-coded the build path, and the gate-by-gate trend a human
    needs to fund another cycle was only in the gate records. Both are in `pdg status` and the escalation report now."""
    from pdg.cli import _summary, read_status
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    eng.save("test")
    s = read_status(str(eng.project.root))
    assert s["latest_build"] == eng.state.build.prototype.entry
    assert [g["blocking"] for g in s["gate_trend"]] == [len(g.blocking_defects) for g in eng.state.evaluation.gates]
    text = _summary(s)
    assert f"latest build: {s['latest_build']}" in text and "blocking defects by gate: " in text
    eng._escalate(eng.node(GATE), "E29: outcome 'blocked'", [])
    report = sorted((eng.project.root / ".pdg" / "escalations").glob(f"{GATE}-*.md"))[-1].read_text()
    assert "Blocking defects by gate: " in report


def test_an_agents_change_request_shows_its_cost_and_is_approved_or_declined_on_record(eng, tmp_path):
    """Backlog N-04 and N-05: an agent's change request stayed open for good, with no command to decide it and no line in
    the release summary, and nobody saw its cost first (CR-001 re-ran N07 to N10 and re-opened two gates)."""
    from pdg.gating import change_request_lines
    writer = "n07_experience_architecture"
    cr = eng.change_request("experience", "the route names a case the data lacks", "agent:ux-interaction-designer",
                            writer=writer)
    assert cr.status == "open" and cr.reruns[0] == writer and "n10_prototype_planning" in cr.gates
    assert set(cr.reruns) == eng.idx.descendants(writer) | {writer}
    with pytest.raises(EngineError, match="delegation|named human"):
        eng.decide_change_request(cr.id, True, "agent:orchestrator", "looks right")
    assert "**open**" in change_request_lines(eng.state)[-1]
    eng.decide_change_request(cr.id, False, "Wei", "the case exists in the seed")
    assert cr.status == "declined" and list(eng.ledger.events("change_request_declined"))[-1]["data"]["id"] == cr.id
    second = eng.change_request("experience", "the rail lacks a count", "agent:ux-interaction-designer", writer=writer)
    eng.decide_change_request(second.id, True, "Wei", "add the count")
    assert second.status == "approved" and eng.rt(writer).status.value != "PASSED"
    lines = change_request_lines(eng.state)
    assert "**declined** by Wei" in lines[-2] and "**approved** by Wei" in lines[-1] and "re-asks" in lines[-1]


def test_a_reviewers_packet_states_the_build_under_review(eng, tmp_path):
    """Backlog N-06: the packet names the build a review must judge, by version, entry and sha256."""
    from pdg.executors import render_packet
    b = _packet(eng, "n13_quality_review", tmp_path)["under_review"]
    assert b == {"version": eng.state.build.version, "sha256": eng.state.build.prototype.sha256,
                 "entry": eng.state.build.prototype.entry}
    assert "## The build under review" in render_packet(_packet(eng, "n13_quality_review", tmp_path))
    assert _packet(eng, INTERACTION, tmp_path)["under_review"] is None


def test_a_deferred_defect_waits_for_a_human_decision_instead_of_resolving_on_a_re_run(eng, tmp_path):
    """Field run W39: a defect deferred for Wei resolved at the next gate once its node re-ran for other reasons, as though
    it had been fixed; only re-filing it at every interpretation kept it open. A deferral is now on record: the gate
    neither routes nor resolves it, and only a human decision ends it."""
    _gate(eng, tmp_path, [{**_defect(INTERACTION), "severity": "P4"}])
    eng.defer("D-950", "adds a capability the spec does not have", "Wei decides the next build's scope", "agent:orchestrator")
    _reran(eng, INTERACTION)
    for r in eng.idx.reviewer_nodes():
        _reran(eng, r)
    _, gate = _gate(eng, tmp_path)
    assert _d(eng).status == "open" and _d(eng).deferred and "D-950" not in gate.blocking_defects
    from pdg.gating import _open_defect_lines, deferred_lines
    assert any("D-950" in line and "Wei decides the next build's scope" in line for line in deferred_lines(eng.state))
    assert not any("D-950" in line for line in _open_defect_lines(eng))      # listed once, as Wei's decision
    out = eng.decide_deferred("D-950", "close", "not in this pilot", "Wei")
    assert out["status"] == "dismissed" and not _d(eng).deferred
    assert list(eng.ledger.events("deferred_decided"))[-1]["data"]["decision"] == "close"


def test_deferring_a_blocking_defect_takes_a_named_human_and_the_gate_stops_routing_it(eng, tmp_path):
    """An agent may park an advisory defect for Wei, since that only lists it; parking a blocking one is Wei's call."""
    _, gate = _gate(eng, tmp_path, [_defect(INTERACTION)])
    assert gate.outcome == "rework"
    with pytest.raises(EngineError, match="delegation|named human"):
        eng.defer("D-950", "a product decision", "Wei decides", "agent:orchestrator")
    eng.defer("D-950", "a product decision, not a build defect", "Wei decides at the scope review", "Wei")
    _, gate = _gate(eng, tmp_path)
    assert gate.outcome == "pass" and "D-950" not in gate.blocking_defects
    eng.decide_deferred("D-950", "fix", "fix it in this build", "Wei")
    _, gate = _gate(eng, tmp_path)
    assert gate.outcome == "rework" and "D-950" in gate.blocking_defects


def test_accepting_a_configuration_re_judges_the_nodes_it_judges_differently(eng, monkeypatch):
    """Backlog B-03 (vpg #59): a stricter threshold was accepted with `accept-config`, the node memo-hit and the run
    passed again under the old verdict. Accepting now re-judges every node whose rubric entries, rule states or
    thresholds moved since it passed, and its descendants re-run after it."""
    content = "n12_content_data"
    assert eng.rt(content).passed_judging and eng.rt(PROBLEM).passed_judging
    th = eng.thresholds()
    th["content"] = {**th["content"], "min_records": 1000}                 # the scratch repro's change
    monkeypatch.setattr(eng, "thresholds", lambda: th)
    eng.accept_config("Wei", "a stricter volume bar")
    event = list(eng.ledger.events("config_accepted"))[-1]["data"]
    assert content in event["rejudged"] and PROBLEM not in event["rejudged"]
    assert eng.rt(content).status.value == "STALE" and eng.rt(PROBLEM).status.value == "PASSED"
    assert eng.rt("n13_quality_review").status.value == "STALE"             # a descendant re-runs after it


def test_a_node_judged_before_the_hash_existed_is_re_judged_when_its_rubric_file_changed(eng, monkeypatch):
    """The two runs live when B-03 landed passed their nodes before `passed_judging` existed: they fall back to the
    rubric files the accepted change touched."""
    plan = "n10_prototype_planning"
    eng.rt(plan).passed_judging = None
    monkeypatch.setattr(eng, "_config_drift", lambda: (["rubrics/prototype-plan.yaml"], "rubrics/prototype-plan.yaml"))
    eng.accept_config("Wei", "N-18: scenarios check the completing control is in view")
    assert plan in list(eng.ledger.events("config_accepted"))[-1]["data"]["rejudged"]
    assert eng.rt(plan).status.value == "STALE"


def test_a_p0_scenario_must_check_its_completing_control_is_reachable_before_pressing_it(eng):
    """Backlog N-18: Playwright scrolls to every click target, so a completing action far below the fold passed every
    scenario (the first project's Close case sat at y 2,497 on a tablet). Each P0 scenario checks it first."""
    import json as _json
    from pdg.tools import plan as plan_tool
    from .conftest import EXAMPLE, FakeCtx
    doc = _json.loads((EXAMPLE / "fixtures" / "n10_prototype_planning" / "attempt-2" / "plan.json").read_text())
    assert plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-SCENARIOS"].passed
    s01 = doc["scenarios"][0]
    s01["steps"] = [st for st in s01["steps"] if "expect_reachable" not in st]
    res = plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-SCENARIOS"]
    assert not res.passed and "S-01" in res.evidence and "reachable" in res.evidence


def test_the_judging_hash_ignores_prose_and_accepting_stamps_the_nodes_it_did_not_re_judge(eng, monkeypatch):
    """Independent audit #7 and #8: the hash covered whole rubric entries, so rewording an example re-asked a gate; and
    a node not re-judged kept no hash, so it stayed on the coarse file-level fallback for good."""
    import copy
    plan = eng.node("n10_prototype_planning")
    before = eng.judging_hash(plan)
    rubrics = copy.deepcopy(eng.rubrics)
    dim = next(d for d in rubrics["prototype-plan"]["dimensions"] if d["id"] == "PLN-SCENARIOS")
    dim["name"], dim["cases"] = dim["name"] + " (reworded)", {"never": ["an example"], "always": []}
    monkeypatch.setattr(eng, "rubrics", rubrics)
    assert eng.judging_hash(plan) == before                                   # prose: no re-judge
    review = next(d for d in rubrics["design-quality"]["dimensions"] if d["check"]["type"] == "review")
    quality = eng.node("n13_quality_review")
    was = eng.judging_hash(quality)
    review["threshold"] = "score ≥ 5"
    assert eng.judging_hash(quality) != was                                   # a review threshold decides a verdict
    eng.rt(PROBLEM).passed_judging = None
    monkeypatch.setattr(eng, "_config_drift", lambda: ([], ""))
    eng.accept_config("Wei", "nothing that judges the problem frame changed")
    assert eng.rt(PROBLEM).passed_judging == eng.judging_hash(eng.node(PROBLEM))


def test_w54_a_rework_gate_names_the_advisories_it_may_leave_open_and_what_fixes_each(eng, tmp_path):
    """Field run 1, W54: N16 traced a contradiction in design.md to n09 as P4. The gate routes only blocking defects and
    an advisory resolves only once its node re-ran, so it stayed open cycle after cycle while the packet said it
    "resolves at the next gate". A rework gate now names, in its report, each advisory its cycle may leave open, why,
    and what fixes it; N16's packet lists every open advisory with the same remedy. A passing gate ships them and a
    blocked one escalates every open defect, so neither lists them again (review I1–I3)."""
    from pdg.executors import render_packet
    upstream = dict(_defect("n07_experience_architecture", "DOC-DRIFT@experience"), id="D-952", severity="P4")
    downstream = dict(_defect("n11_prototype_development", "COPY@queue"), id="D-953", severity="P4")
    waiting = dict(_defect("n10_prototype_planning", "PLAN@queue"), id="D-954", severity="P4")
    locked = dict(_defect("n04_requirements", "REQ-WORDING@R-01"), id="D-955", severity="P4")
    on_target = dict(_defect(INTERACTION, "FOCUS@queue"), id="D-956", severity="P4")
    reviewer = dict(_defect("n13_quality_review", "REVIEW-NOTE@queue"), id="D-957", severity="P4")
    res, gate = _gate(eng, tmp_path, [upstream, downstream, waiting, locked, on_target, reviewer])
    assert gate.outcome == "pass" and res.data["stranded"] == []            # the release lists them
    assert json.loads(Path(res.outputs["gate_report"]).read_text())["stranded_advisories"] == []
    next(d for d in eng.state.evaluation.defects if d.id == "D-954").deferred = "waits on Wei's scope call"
    res, gate = _gate(eng, tmp_path, [_defect(INTERACTION), upstream, downstream, waiting, locked, on_target, reviewer])
    assert gate.outcome == "rework" and gate.targets == [INTERACTION]
    report = {d["id"]: d for d in json.loads(Path(res.outputs["gate_report"]).read_text())["stranded_advisories"]}
    assert sorted(report) == ["D-952", "D-953", "D-955", "D-957"] and res.data["stranded"] == sorted(report)
    # not D-954 (deferred) nor D-956 (its node is the target, which re-runs)
    assert report["D-952"]["why"] == "its node is not in this cycle"
    assert report["D-953"]["why"] == "its node follows a target, so it re-runs only if its inputs change"
    assert "re-files `DOC-DRIFT@experience` at a blocking severity" in report["D-952"]["remedy"]
    assert "pdg invalidate" in report["D-952"]["remedy"] and "after this gate" in report["D-952"]["remedy"]
    assert "pdg change-request" in report["D-955"]["remedy"] and "would block the gate" in report["D-955"]["remedy"]
    assert "the gate cannot route n13_quality_review" in report["D-957"]["remedy"], report["D-957"]["remedy"]
    assert not any("D-952" in line for line in res.data["report"])     # the report file carries it, not the escalation
    events = [json.loads(x) for x in (eng.project.root / ".pdg" / "ledger.jsonl").read_text().splitlines()]
    assert [e for e in events if e["type"] == "gate"][-1]["data"]["stranded"] == ["D-952", "D-953", "D-955", "D-957"]
    packet = _packet(eng, GATE, tmp_path)
    ours = {d["id"]: d for d in packet["open_advisories"]}
    assert sorted(ours) == ["D-952", "D-953", "D-955", "D-956", "D-957"]
    assert ours["D-955"]["remedy"] == report["D-955"]["remedy"]         # the locked case does not depend on the budget
    assert ours["D-952"]["smallest_fix"] and ours["D-952"]["acceptance_check"]   # what re-filing it needs
    section = render_packet(packet).split("## Open advisory defects (5)")[1].split("\n## ")[0]
    assert "D-952" in section and "To fix it now: N16 re-files" in section, section
    assert _packet(eng, INTERACTION, tmp_path)["open_advisories"] == []  # only the gate's packet
    assert "never routed here on their own" in render_packet(_packet(eng, "n07_experience_architecture", tmp_path))
    eng.state.runtime.rework_cycles = eng.wf.policies.max_rework_cycles
    res, gate = _gate(eng, tmp_path, [_defect(INTERACTION), upstream, downstream, locked])
    assert gate.outcome == "blocked" and res.data["stranded"] == []       # the escalation lists every open defect
    assert all(d["severity"] == "P4" for d in _packet(eng, GATE, tmp_path)["open_advisories"])   # advisories only


def test_w54_the_remedies_are_what_the_gate_does(eng, tmp_path):
    """Review I2: re-filing an advisory at a blocking severity routes it where the gate can route; on a node whose
    document another node locked, it blocks the gate instead, which is why that one's remedy is a change request."""
    upstream = dict(_defect("n07_experience_architecture", "DOC-DRIFT@experience"), id="D-952", severity="P3")
    res, gate = _gate(eng, tmp_path, [_defect(INTERACTION), upstream])
    assert gate.outcome == "rework" and "n07_experience_architecture" in gate.targets, gate.targets
    locked = dict(_defect("n04_requirements", "REQ-WORDING@R-01"), id="D-955", severity="P3")
    res, gate = _gate(eng, tmp_path, [_defect(INTERACTION), locked])
    assert gate.outcome == "blocked" and "change request" in " ".join(gate.reasons), gate.reasons



def test_w54_once_the_rework_budget_is_spent_the_remedy_is_an_invalidation(eng, tmp_path):
    """Review of W54, second pass: at the rework budget's end, re-filing an advisory at a blocking severity blocks a gate
    that would have passed. A report advises the next gate (N17 counts this cycle before it), a packet its own gate."""
    pol = eng.wf.policies
    upstream = dict(_defect("n07_experience_architecture", "DOC-DRIFT@experience"), id="D-952", severity="P4")
    eng.state.runtime.rework_cycles = pol.max_rework_cycles - 1
    res, gate = _gate(eng, tmp_path, [_defect(INTERACTION), upstream])
    assert gate.outcome == "rework"
    remedy = json.loads(Path(res.outputs["gate_report"]).read_text())["stranded_advisories"][0]["remedy"]
    assert "rework budget is spent" in remedy and "re-files" not in remedy, remedy
    eng.state.runtime.rework_cycles = pol.max_rework_cycles
    ours = {d["id"]: d for d in _packet(eng, GATE, tmp_path)["open_advisories"]}
    assert "rework budget is spent" in ours["D-952"]["remedy"], ours["D-952"]["remedy"]
    eng.state.runtime.rework_cycles = 0
    assert "re-files" in {d["id"]: d for d in _packet(eng, GATE, tmp_path)["open_advisories"]}["D-952"]["remedy"]


def test_w59_a_grant_that_counts_its_budget_resets_holds_the_agent_to_them(eng, tmp_path):
    """Field run 1, W59: `unblock --reset-budget` under a delegation restored the full budget every time (DL-001 twice,
    DL-002 once), so "4 rework cycles" became "4 per reset". A grant may now say how many resets it covers; a further
    one is a named human's. A grant that says nothing is not limited: that default is Wei's decision (D12)."""
    import datetime as dt

    import pytest

    from pdg.engine_common import EngineError
    from pdg.models import Escalation
    future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat()

    def blocked():
        eng.state.runtime.escalations.append(Escalation(id=f"{GATE}-{len(eng.state.runtime.escalations) + 10}", node=GATE,
                                                        reason="E29: outcome 'blocked'", report="", at="2026-09-29T16:00:00+00:00"))
    with pytest.raises(EngineError, match="scope must include unblock"):
        eng.delegate("Wei", "agent:orchestrator", "Keep going.", ["decide"], [], future, recorded_by="Wei", budget_resets=1)
    grant = eng.delegate("Wei", "agent:orchestrator", "Keep iterating until the bar is met.", ["unblock"], [], future,
                         recorded_by="Wei", budget_resets=1)
    blocked()
    eng.unblock(GATE, "agent:orchestrator", note="one more cycle", reset_budget=True, on_behalf_of="Wei")
    blocked()
    with pytest.raises(EngineError, match=f"{grant.id} covers 1 rework-budget reset"):
        eng.unblock(GATE, "agent:orchestrator", note="and another", reset_budget=True, on_behalf_of="Wei")
    eng.unblock(GATE, "Wei", note="Wei funds another cycle", reset_budget=True)
    assert eng.status()["budget_resets"] == {grant.id: 1, "Wei": 1}
    open_grant = eng.delegate("Wei", "agent:orchestrator", "Keep iterating.", ["unblock"], [], future, recorded_by="Wei")
    for _ in range(2):                                                   # no number stated: not limited
        blocked()
        eng.unblock(GATE, "agent:orchestrator", note="again", reset_budget=True, on_behalf_of="Wei")
    assert eng.status()["budget_resets"][open_grant.id] == 2
    from pdg.cli import _summary, read_status
    resets = f"4 budget reset(s) (1 by {grant.id}, 2 by {open_grant.id}, 1 by Wei)"
    assert resets in _summary(eng.status())
    assert resets in _summary(read_status(str(eng.project.root)))            # `pdg status` reads without the engine
    eng.state.runtime.rework_cycles = eng.wf.policies.max_rework_cycles     # and the gate says the budget was reset
    res, gate = _gate(eng, tmp_path, [_defect("n08_interaction_design")])
    assert gate.outcome == "blocked" and any(f"cycles, after {resets})" in r for r in gate.reasons), gate.reasons
    assert f"after {resets}" in res.dimensions["GAT-ESCALATE"].evidence
    with pytest.raises(EngineError, match="a count"):
        eng.delegate("Wei", "agent:orchestrator", "Keep going.", ["unblock"], [], future, recorded_by="Wei", budget_resets=-1)
    none = eng.delegate("Wei", "agent:orchestrator", "No resets.", ["unblock"], [], future, recorded_by="Wei", budget_resets=0)
    blocked()
    with pytest.raises(EngineError, match=f"{none.id} covers 0 rework-budget reset"):
        eng.unblock(GATE, "agent:orchestrator", note="reset", reset_budget=True, on_behalf_of="Wei")
    # a damaged ledger: `pdg status` still prints, and a capped grant cannot reset what it cannot count (review I4)
    with (eng.project.root / ".pdg" / "ledger.jsonl").open("a") as f:
        f.write("not an event\n")
    assert "budget resets unknown (the ledger is damaged)" in _summary(read_status(str(eng.project.root)))
    with pytest.raises(EngineError, match="cannot be counted"):
        eng.unblock(GATE, "agent:orchestrator", note="reset", reset_budget=True, on_behalf_of="Wei")


def test_a_passed_node_is_not_re_judged_for_a_dimension_that_cannot_fail_it(eng):
    """Config batch 5's dry run: adding SHOULD dimensions to N09, N10 and N13 moved their judging hashes, so accepting
    would have withdrawn N09 and everything after it on the first run, a rebuild for advisory lines. A dimension added
    since the pass that cannot fail it (SHOULD, or its rule not enforced) now leaves the verdict standing; a blocking one
    still re-judges."""
    node = eng.node("n10_prototype_planning")
    rubric = node.evaluation[0]
    changed = [f"rubrics/{rubric}.yaml"]
    assert node.id not in eng._rejudge_after_config(changed)
    added = {"id": "PLN-NEW", "name": "a new plan check", "level": "SHOULD", "check": {"type": "tool", "fn": "plan:check"},
             "threshold": "t", "rule": "R-A11Y-004"}
    eng.rubrics[rubric]["dimensions"].append(added)
    assert node.id not in eng._rejudge_after_config(changed)                # SHOULD: informs only
    added["level"] = "MUST"
    assert node.id in eng._rejudge_after_config(changed)                    # MUST under an enforced rule: can fail it
    added["rule"] = "R-VIS-006"
    assert node.id not in eng._rejudge_after_config(changed)                # MUST under a validated rule: advisory
    from pdg.models import NodeStatus
    eng.rt(node.id).status = NodeStatus.WAITING_AGENT                        # out with an agent: the same test (b16)
    assert node.id not in eng._rejudge_after_config(changed)                # still the advisory MUST
    added["rule"] = "R-A11Y-004"
    assert node.id in eng._rejudge_after_config(changed)                    # a blocking one: its packet is re-issued
    added["level"] = "SHOULD"
    assert node.id not in eng._rejudge_after_config(changed)
    eng.rt(node.id).status = NodeStatus.PASSED
    added.update(level="MUST", rule="R-VIS-006", check={"type": "review"})
    assert node.id in eng._rejudge_after_config(changed)                    # a review its completion must score (review I5)
    eng.rubrics[rubric]["dimensions"].pop()
    eng.rubrics[rubric]["dimensions"][0] = {**eng.rubrics[rubric]["dimensions"][0], "level": "SHOULD"}
    assert node.id in eng._rejudge_after_config(changed)                    # a dimension it passed under changed


def test_a_node_out_with_an_agent_is_compared_with_the_configuration_its_packet_was_issued_under(eng):
    """Config batch 5 reviews I1, I-A: a node re-judged at one accept, or stale when it came, had its packet built under
    that configuration, but it was compared with its last pass, so every later accept withdrew it again and refused while
    it was out with its agent. Its packet now records the judging it was issued under."""
    from pdg.models import NodeStatus
    node = eng.node("n10_prototype_planning")
    rubric = node.evaluation[0]
    part = f"rubrics/{rubric}.yaml"

    def drift() -> None:                                                     # the accepted file no longer matches
        eng.state.runtime.config_parts[part] = "0" * 64
        eng.state.runtime.config_sha256 = "changed"
    eng.rubrics[rubric]["dimensions"].append({"id": "PLN-BLOCK", "name": "a blocking plan check", "level": "MUST",
                                              "check": {"type": "tool", "fn": "plan:check"}, "threshold": "t",
                                              "rule": "R-A11Y-004"})
    drift()
    assert node.id in eng.accept_config("Wei", "a blocking plan check")["rejudged"]
    assert eng.rt(node.id).status == NodeStatus.STALE
    eng._prepare(node.id)                                                    # its packet, under this configuration
    eng.rt(node.id).status = NodeStatus.WAITING_AGENT
    assert eng.rt(node.id).issued_judging == eng.judging_hash(node)
    assert node.id not in eng._rejudge_after_config([part])                  # another accept leaves it with its agent
    eng.rubrics[rubric]["dimensions"][-1]["level"] = "SHOULD"               # a real change to how it is judged
    assert node.id in eng._rejudge_after_config([part])


def _finding_for(eng, d, node="n13_quality_review"):
    """A current finding by `node` that reports defect `d` again, under its own signature."""
    from pdg.models import FindingRecord
    dim, _, loc = d.signature.partition("@")
    f = FindingRecord(node=node, dimension=dim, location=loc, severity=d.severity, message=d.message)
    assert f.signature == d.signature, (f.signature, d.signature)
    return f


def _look_again(eng, says=(), on_this_build=True, findings=(), who=None, passed=True):
    """The reviews asked to re-verify D-950 (or `who`) look again: a review on the build, with its claims and findings."""
    from pdg.gating import rechecking_reviewers
    from pdg.models import NodeStatus, ReviewRecord
    for r in who or rechecking_reviewers(eng, _d(eng)):
        _reran(eng, r)
        eng.rt(r).status = NodeStatus.PASSED if passed else NodeStatus.ITERATE
        eng.state.evaluation.reviews.append(ReviewRecord(
            node=r, attempt=eng.rt(r).attempt, dimensions=[], findings=list(findings), passed=True,
            build_version=eng.state.build.version if on_this_build else eng.state.build.version - 1,
            at="2026-09-29T00:00:00+00:00", no_longer_holds=list(says)))


def test_w61_a_deferred_defect_a_review_says_no_longer_holds_goes_to_a_person(eng, tmp_path):
    """Field run W61: reviewers re-filed deferred defects every round, told that a defect resolves once no review reports
    it, which the gate never does for a deferred one; one fixed on the way would have stayed "waits on Wei". A reviewer
    now files nothing for a deferred defect that still holds, and lists one this build no longer shows under
    `no_longer_holds`: the gate and the release name it for a person, who resolves it or keeps it. Silence changes
    nothing (batch 17 review C1); a claim that does not count is named with why (review 2). Its owner need not re-run:
    the fix came from other work."""
    from pdg.engine import EngineError
    from pdg.executors import render_packet
    from pdg.gating import deferred_lines, rechecking_reviewers
    look_again = lambda **kw: _look_again(eng, **kw)   # noqa: E731

    def claimed_lines(res):
        return [x for x in res.data["report"] if "said it no longer holds: a person checks" in x]

    def ignored(res):
        return [x for x in res.data["report"] if x.startswith("ignored: ")]

    _gate(eng, tmp_path, [{**_defect(INTERACTION), "severity": "P4"}])
    who = rechecking_reviewers(eng, _d(eng))
    other = next(r for r in eng.idx.reviewer_nodes() if r not in who)
    assert len(who) == 1 and set(who) <= set(_d(eng).attempts_at_start), "the marker names the review asked to re-verify it"
    eng.defer("D-950", "adds a capability the spec does not have", "Wei decides the next build's scope", "agent:orchestrator")
    texts = [render_packet(_packet(eng, r, tmp_path)) for r in who]
    assert any("D-950" in t and "deferred: waits on Wei decides the next build's scope; still true: nothing to file; no "
               "longer true: list it in `no_longer_holds`" in t and "filing nothing leaves it as it is" in t
               and "## Open defects you are asked to re-verify" in t for t in texts)
    assert all(x["id"] != "D-950" for x in _packet(eng, other, tmp_path)["reverify"]), "a reviewer not asked lists it"
    eng.state.build.version += 1
    look_again(says=["D-950"], on_this_build=False)                     # the only review is of the older build: it
    res, _ = _gate(eng, tmp_path)                                       # says nothing about this one
    assert _d(eng).claimed_fixed is None and not ignored(res)
    look_again()                                                        # silent: it still holds, nothing to file
    res, _ = _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed is None and not claimed_lines(res) and not ignored(res)
    look_again(says=["D-950"], passed=False)                            # nor does one that did not pass
    res, _ = _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed is None
    assert ignored(res) == [f"ignored: {who[0]} says D-950 no longer holds, but its review did not pass"]
    look_again()                                                        # it passes, silent: the refused claim is gone
    _d(eng).attempts_at_start[other] = eng.rt(other).attempt            # even with a marker for it (asked once, not now)
    look_again(says=["D-950"], who=[other])                             # nor one that was not asked: named, ignored
    res, _ = _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed is None
    assert ignored(res) == [f"ignored: {other} says D-950 no longer holds, but {other} was not asked to re-verify it"]
    look_again(who=[other])                                             # and it files nothing now
    _d(eng).attempts_at_start = {INTERACTION: _d(eng).attempts_at_start.get(INTERACTION, 0)}   # an older record's marker
    look_again(says=["D-950"])                                                                   # names no review
    res, _ = _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed is None and who[0] in _d(eng).attempts_at_start                # a look is on record now
    assert ignored(res) == [f"ignored: {who[0]} says D-950 no longer holds, but no earlier look of it is on record; its "
                            "next claim counts"]
    with pytest.raises(EngineError, match="no review has said D-950 no longer holds.*`--fix` returns it to the open defects"):
        eng.decide_deferred("D-950", "resolved", "looks fixed", "Wei")
    owner = eng.rt(INTERACTION).attempt
    look_again(says=["D-950"])
    res, _ = _gate(eng, tmp_path)                                       # said, looked again, its owner never re-ran
    version = eng.state.build.version
    assert eng.rt(INTERACTION).attempt == owner
    assert _d(eng).status == "open" and _d(eng).deferred and _d(eng).claimed_fixed.model_dump() == {
        "at": version, "by": who, "silent": []}
    cmd = (f"pdg decide-deferred {shlex.quote(str(eng.project.root))} D-950 --resolved --reason "
           f"'no longer holds at v{version}' --actor <name>")
    assert claimed_lines(res) == [f"D-950 `{_d(eng).signature}` is deferred, and at v{version} {who[0]} said it no longer "
                                  f"holds: a person checks and decides (`{cmd}`, or `--keep` if it still holds)"]
    got = json.loads(Path(res.outputs["gate_report"]).read_text())["deferred_claimed_fixed"]
    assert [(q["id"], q["at"], q["by"], q["decide"]) for q in got] == [("D-950", version, who, cmd)], got
    assert any(f"At v{version} {who[0]} said it no longer holds: if a person confirms it, `pdg decide-deferred … D-950 "
               "--resolved`" in x for x in deferred_lines(eng.state))
    eng.state.build.version += 1
    look_again(says=["D-950"])
    _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed.at == version                         # still the first build that said so
    eng.decide_deferred("D-950", "keep", "checked by hand: still true", "Wei")
    assert _d(eng).claimed_fixed is None and _d(eng).deferred          # kept: no longer named
    res, _ = _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed is None                                # the review before the decision is not a new look
    assert ignored(res) == [f"ignored: {who[0]} says D-950 no longer holds, but it has not looked again since the defect "
                            "was last seen"]
    look_again(says=["D-950"])
    _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed.at == eng.state.build.version
    look_again(findings=[_finding_for(eng, _d(eng))])                   # reported again: no longer claimed fixed
    _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed is None and _d(eng).deferred
    assert any("reported again at v" in h and "after a review said it no longer held" in h for h in _d(eng).history)
    look_again(says=["D-950"])                                          # said, while another review reports it: the
    look_again(findings=[_finding_for(eng, _d(eng), other)], who=[other])   # report wins, and the claim is named
    res, _ = _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed is None
    assert ignored(res) == [f"ignored: {who[0]} says D-950 no longer holds, but {other} reports it at "
                            f"v{eng.state.build.version}"]
    look_again(who=[other])                                             # the report stops; the claim came before it
    _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed is None, "a claim made while it was still reported counted after the report stopped"
    look_again(says=["D-950"])
    _gate(eng, tmp_path)
    eng.decide_deferred("D-950", "resolved", "checked: the rail fits since the header change", "Wei")
    d = _d(eng)
    assert (d.status, d.resolved_at_version, d.deferred, d.claimed_fixed) == ("resolved", eng.state.build.version, "", None)
    assert any(x["id"] == "D-950" for x in _packet(eng, who[0], tmp_path)["still_fixed"])   # its reviews re-check it


def test_w61_a_review_also_asked_that_filed_nothing_is_named(eng, tmp_path):
    """Batch 17 review 2, S2: one claim among the reviews asked is enough, and the person deciding sees who else was asked
    and filed nothing (which, for them, means "still true")."""
    from pdg.gating import fix_marker
    _gate(eng, tmp_path, [{**_defect(INTERACTION), "severity": "P4"}])
    a, b = eng.idx.reviewer_nodes()[:2]
    _d(eng).source_nodes = [a, b]
    _d(eng).attempts_at_start = fix_marker(eng, _d(eng))
    eng.defer("D-950", "waits on scope", "Wei decides", "agent:orchestrator")
    _look_again(eng, says=["D-950"], who=[a])
    _look_again(eng, who=[b])
    res, _ = _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed.model_dump() == {"at": eng.state.build.version, "by": [a], "silent": [b]}
    assert any(f"said it no longer holds ({b}, also asked, filed nothing): a person checks" in x for x in res.data["report"])


def test_w61_a_refused_claim_is_not_counted_as_silence(eng, tmp_path):
    """Batch 17 review 3, S2: with two reviewers asked, one's claim counted and the other's was refused; the line called
    the second "also asked, filed nothing" and never named its refusal."""
    from pdg.gating import fix_marker
    _gate(eng, tmp_path, [{**_defect(INTERACTION), "severity": "P4"}])
    a, b = eng.idx.reviewer_nodes()[:2]
    _d(eng).source_nodes = [a, b]
    _d(eng).attempts_at_start = {k: v for k, v in fix_marker(eng, _d(eng)).items() if k != b}   # none on record for b
    eng.defer("D-950", "waits on scope", "Wei decides", "agent:orchestrator")
    _look_again(eng, says=["D-950"], who=[a, b])
    res, _ = _gate(eng, tmp_path)
    assert _d(eng).claimed_fixed.model_dump() == {"at": eng.state.build.version, "by": [a], "silent": []}
    assert (f"ignored: {b} says D-950 no longer holds, but no earlier look of it is on record; its next claim counts"
            in res.data["report"]), res.data["report"]


def test_w61_a_defect_saved_before_markers_still_resolves_after_fix(eng, tmp_path):
    """Batch 17 review 3, I1: seeding only the asked reviewers turned an older defect's empty marker into one without its
    owner, so after `--fix` its owner's re-run never counted and a fixed advisory stayed open."""
    from pdg.models import NodeStatus
    _gate(eng, tmp_path, [{**_defect(INTERACTION), "severity": "P4"}])
    eng.defer("D-950", "waits on scope", "Wei decides", "agent:orchestrator")
    _d(eng).attempts_at_start = {}                                        # as saved by an older pdg
    _gate(eng, tmp_path)                                                  # a gate while it is deferred
    assert INTERACTION in _d(eng).attempts_at_start
    eng.decide_deferred("D-950", "fix", "the scope decision came: fix it", "Wei")
    _reran(eng, INTERACTION)
    eng.rt(INTERACTION).status = NodeStatus.PASSED
    _look_again(eng)
    eng.state.build.version += 1
    _look_again(eng)
    _gate(eng, tmp_path)
    assert _d(eng).status == "resolved", _d(eng).history


def test_w61_the_command_to_decide_quotes_what_a_shell_would_split():
    """Batch 17 review S9: the command is copied into a shell, and a project path may hold a space."""
    from types import SimpleNamespace
    from pdg.gating import decide_deferred_command
    from pdg.models import ClaimedFixed, Defect
    d = Defect(id="D-7", signature="S@x", dimension="S", severity="P4", message="m", evidence="e", traced_node="n09",
               trace_reason="r", smallest_fix="f", acceptance_check="c", claimed_fixed=ClaimedFixed(at=4, by=["n13"]))
    cmd = decide_deferred_command(SimpleNamespace(project=SimpleNamespace(root=Path("/work/My Project"))), d)
    assert cmd == "pdg decide-deferred '/work/My Project' D-7 --resolved --reason 'no longer holds at v4' --actor <name>"


def test_w61_a_new_deferral_is_not_claimed_fixed(eng, tmp_path):
    """Batch 17 review I3: a defect once claimed fixed, routed with --fix and deferred again carried the old "since v3"."""
    from pdg.models import ClaimedFixed
    _gate(eng, tmp_path, [{**_defect(INTERACTION), "severity": "P4"}])
    _d(eng).claimed_fixed = ClaimedFixed(at=3, by=["n13_quality_review"])
    eng.defer("D-950", "waits on scope", "Wei decides", "agent:orchestrator")
    assert _d(eng).claimed_fixed is None


def test_w62_a_passing_run_names_the_nodes_it_did_not_need(eng, capsys):
    """Field run W62: after an invalidation and two passing gates, `pdg status` read RUN_PASS with the rework node STALE,
    so "18 of 19 passed". A node the passing run left stale is named as not needed; in a run still going, it is STALE."""
    from pdg.cli import main
    from pdg.models import NodeStatus, RunStatus
    from pdg.report import write_report
    eng.rt("n17_targeted_rework").status = NodeStatus.STALE
    eng.state.runtime.status = RunStatus.RUNNING
    eng.save("test")
    assert eng.status()["not_needed"] == []
    main(["status", str(eng.project.root)])
    out = capsys.readouterr().out
    assert "not needed" not in out and any(line.split()[:2] == ["n17_targeted_rework", "STALE"] for line in out.splitlines())
    eng.state.runtime.status = RunStatus.RUN_PASS
    eng.save("test")
    assert eng.status()["not_needed"] == ["n17_targeted_rework"]
    main(["status", str(eng.project.root)])
    out = capsys.readouterr().out
    assert "not needed (the run passed without it): n17_targeted_rework" in out, out
    assert any(line.split()[:3] == ["n17_targeted_rework", "not", "needed"] for line in out.splitlines()), out
    assert "· not needed" in write_report(eng.project.root).read_text()


def test_w61_the_review_keeps_what_it_says_no_longer_holds(eng):
    """W61: a reviewer's `no_longer_holds` reaches the review record the gate reads, trimmed, once each."""
    from pdg.evaluation import merge_review, node_dimensions
    node = eng.node("n13_quality_review")
    scores = [{"id": d["id"], "score": 5, "evidence": "ok"} for d in node_dimensions(node, eng.rubrics)
              if d["check"]["type"] in ("review", "llm_judge", "rubric")]
    rec = merge_review(node, 1, 1, {}, {"dimensions": scores, "summary": "s", "no_longer_holds": [" D-950 ", "D-950", ""]},
                       eng.rubrics, {}, 4.0)
    assert rec.no_longer_holds == ["D-950"]


def _code_upgrade(monkeypatch, file="pdg/tools/browser.py", digest="0" * 64):
    """pdg's code on disk changes (one file's hash), as a batch landing on a released project does: what `pdg status`
    reads, and what the engine records at its next step."""
    import pdg.engine_common as ec
    import pdg.engine_config as ecfg
    real = ec.package_code_parts
    upgraded = lambda root: {**real(root), file: digest}   # noqa: E731
    monkeypatch.setattr(ec, "package_code_parts", upgraded)
    monkeypatch.setattr(ecfg, "package_code_parts", upgraded)


def test_w65_each_node_records_what_its_checks_ran_with_and_status_says_when_that_changes(eng, monkeypatch, capsys):
    """Field run W65: batches 13 and 14 landed after the first run's v15 was released, and nothing in pdg ran the new
    checks on it. Each node now records the code and configuration its tool checks ran with when it passed; the release
    summary and the package manifest list them; and both status paths compare them with what is on disk now. A gate's
    checks are its decision and are not re-run, so a gate is not counted."""
    from pdg.cli import main
    from pdg.engine import Engine
    from pdg.engine_common import checks_fingerprint, release_checks
    from pdg.models import NodeKind, RunStatus
    root, rs = eng.project.root, eng.state.runtime
    now_ = checks_fingerprint(rs.code_parts, rs.config_parts)
    passed = [n for n, r in rs.nodes.items() if r.status.value == "PASSED"]
    gates = [n for n in passed if eng.node(n).kind == NodeKind.GATE]
    counted = sorted(set(passed) - set(gates))
    assert gates and all({k: rs.nodes[n].passed_checks.model_dump()[k] for k in ("code", "config")} == now_ for n in passed)
    assert [n for n in passed if not rs.nodes[n].passed_checks.recheckable] == gates
    (summary,) = [p for p in root.rglob("RELEASE-SUMMARY.md") if "package" in p.parts]
    text = summary.read_text()
    assert f"- pdg code `{now_['code'][:12]}` and configuration `{now_['config'][:12]}`: " in text, text
    assert "(field run W65)" not in text
    assert json.loads((summary.parent / "manifest.json").read_text())["judged_by"][0]["code"] == now_["code"]
    assert release_checks(eng.state)[0]["nodes"] == counted

    def both():
        main(["status", str(root)])
        return Engine(root).status()["recheck_due"], capsys.readouterr().out
    due, out = both()
    assert due == {} and "recheck-release" not in out, out
    _code_upgrade(monkeypatch)                               # a code batch lands
    due, out = both()
    assert due == {"changed": ["the code"], "nodes": counted, "unrecorded": []}, due
    assert (f"the code changed since {len(counted)} node(s) of this release were judged: `pdg recheck-release "
            f"{root.resolve()}` re-runs their checks on it, read-only") in out, out
    monkeypatch.undo()
    cfg = root / "pdg.project.yaml"
    cfg.write_text(cfg.read_text() + "\n# a configuration batch lands\n")
    due, out = both()
    assert due["changed"] == ["the configuration"] and "the configuration changed since" in out, (due, out)
    e = Engine(root)
    e.accept_config("Wei", "the project file changed")     # its verdicts stand: their checks did not run again
    assert e.state.runtime.status == RunStatus.RUN_PASS
    assert Engine(root).status()["recheck_due"]["changed"] == ["the configuration"]
    e.state.runtime.status = RunStatus.RUNNING               # re-opened by feedback: the rework re-checks it anyway
    e.save("test")
    assert Engine(root).status()["recheck_due"] == {}


def test_w65_the_two_status_paths_agree_on_a_relative_path_and_survive_a_bad_project_file(eng, monkeypatch, capsys):
    """Batch 19 review 2, I4 and S: `pdg status .` read the project unresolved, so a workflow the project names kept a
    configuration hint the engine did not show; and a malformed project file made status raise."""
    import shutil
    from pdg.cli import read_status
    from pdg.engine import Engine
    root = eng.project.root
    from pdg.util import PKG_ROOT
    shutil.copyfile(PKG_ROOT / "graph" / "workflow.yaml", root / "wf.yaml")
    cfg = root / "pdg.project.yaml"
    cfg.write_text(cfg.read_text() + "\nworkflow: wf.yaml\n")
    e = Engine(root)
    e.accept_config("Wei", "the project names its own workflow")
    from pdg.engine_common import checks_now
    now_ = checks_now(root)
    for r in e.state.runtime.nodes.values():               # as if every node had passed under this configuration
        if r.passed_checks:
            r.passed_checks.config = now_["config"]
    e.save("test")
    assert Engine(root).status()["recheck_due"] == {}
    monkeypatch.chdir(root)
    assert read_status(".")["recheck_due"] == {}
    for bad in ("workflow: [unclosed\n", "- a list, not a mapping\n"):
        cfg.write_text(bad)
        due = read_status(str(root))["recheck_due"]
        assert set(due) == {"unreadable"}, (bad, due)


def test_w65_a_node_that_passed_before_the_records_is_never_taken_as_current(eng, monkeypatch):
    """Batch 19 review 1 I1 and review 2 I3: a node that passed before pdg recorded its checks (all of the first run's,
    or some of a re-opened one) is flagged until a re-check, never assumed current."""
    for n in ("n09_visual_system", "n11_prototype_development"):
        eng.rt(n).passed_checks = None
    eng.save("test")
    due = eng.status()["recheck_due"]
    assert due["unrecorded"] == ["n09_visual_system", "n11_prototype_development"] and due["nodes"] == [], due
    from pdg.engine_common import release_checks
    assert {"code": None, "config": None, "git_state": None,
            "nodes": ["n09_visual_system", "n11_prototype_development"]} in release_checks(eng.state)


def test_w65_a_code_change_mid_run_names_the_nodes_that_passed_before_it(eng, monkeypatch):
    """Batch 19 review I4: a code batch that lands mid-run leaves the nodes that passed before it judged by the old code,
    though the run passes after it. Here the upgrade lands, and only N18 and after re-run."""
    eng.invalidate_nodes(["n18_final_verification"], "a person asked for release verification again", "Wei")
    _code_upgrade(monkeypatch)
    eng.run(max_steps=60)
    assert eng.state.runtime.status.value == "RUN_PASS" and eng.rt("n18_final_verification").status.value == "PASSED"
    due = eng.status()["recheck_due"]
    assert due["changed"] == ["the code"] and "n18_final_verification" not in due["nodes"], due
    assert "n11_prototype_development" in due["nodes"] and "n13_quality_review" in due["nodes"], due


def test_m07_checks_record_git_state_and_status_warns_on_uncommitted_pdg_code(eng, monkeypatch, capsys):
    """M-07: commands never fail because of git, but the verdict record says when checks ran on dirty package code."""
    from pdg.cli import main
    import pdg.engine as engine_mod
    import pdg.engine_config as config_mod
    dirty = {"commit": "abc123", "uncommitted_files": ["pdg/tools/browser.py", "tests/test_browser.py"],
             "diff_sha256": "d" * 64}
    monkeypatch.setattr(engine_mod, "package_git_state", lambda root: dirty)
    monkeypatch.setattr(config_mod, "package_git_state", lambda root: dirty)
    for rt in eng.state.runtime.nodes.values():
        if rt.passed_checks:
            rt.passed_checks.git_state = None

    eng.invalidate_nodes(["n15_feasibility_review"], "a check fix landed", "Wei")
    _code_upgrade(monkeypatch)
    eng.run(max_steps=60)

    events = list(eng.ledger.events("code_updated"))
    assert events and events[-1]["data"]["git_state"] == dirty
    assert eng.rt("n15_feasibility_review").passed_checks.git_state == dirty
    assert main(["status", str(eng.project.root)]) == 0
    assert "checks ran on uncommitted pdg code (2 files)" in capsys.readouterr().out
    summary = next(p for p in eng.project.root.rglob("RELEASE-SUMMARY.md") if "package" in p.parts)
    assert "uncommitted pdg files: pdg/tools/browser.py, tests/test_browser.py" in summary.read_text()


def test_m07_release_checks_group_by_code_and_config_not_by_head_commit(eng):
    from pdg.engine_common import release_checks
    nodes = [n for n, rt in eng.state.runtime.nodes.items() if rt.passed_checks and rt.passed_checks.recheckable][:2]
    assert len(nodes) == 2
    for rt in eng.state.runtime.nodes.values():
        if rt.passed_checks:
            rt.passed_checks.git_state = None
    for i, n in enumerate(nodes):
        eng.rt(n).passed_checks.git_state = {"commit": f"commit-{i}", "uncommitted_files": [f"pdg/file{i}.py"],
                                             "diff_sha256": f"diff-{i}"}

    rows = [r for r in release_checks(eng.state) if set(nodes) <= set(r["nodes"])]

    assert len(rows) == 1
    assert rows[0]["git_state"]["commits"] == ["commit-0", "commit-1"]
    assert rows[0]["git_state"]["uncommitted_files"] == ["pdg/file0.py", "pdg/file1.py"]


def test_w65_a_node_no_person_reviews_records_its_checks_when_it_passes(eng, monkeypatch):
    """W65: a node no person reviews (N15 here) passes as soon as its checks do, and records them then."""
    from pdg.engine_common import checks_now
    assert not eng.node("n15_feasibility_review").human_review.required
    eng.invalidate_nodes(["n15_feasibility_review"], "a person asked for the feasibility review again", "Wei")
    _code_upgrade(monkeypatch)
    eng.run(max_steps=60)
    assert eng.state.runtime.status.value == "RUN_PASS" and eng.rt("n15_feasibility_review").status.value == "PASSED"
    assert eng.rt("n15_feasibility_review").passed_checks.code == checks_now(eng.project.root)["code"]


def test_w65_a_memo_hit_keeps_the_record_of_the_pass_it_restores(eng):
    """Batch 19 review 4: an attempt that waited for a person and was withdrawn must not leave its record on the earlier
    pass a memo hit restores."""
    from pdg.models import NodeStatus, PassedChecks
    rt = eng.rt("n09_visual_system")
    before = rt.passed_checks
    rt.judged_checks = PassedChecks(code="0" * 64, config="0" * 64)   # a later attempt waited, then was withdrawn
    rt.status = NodeStatus.STALE
    assert eng._prepare("n09_visual_system") is None and rt.status == NodeStatus.PASSED   # restored from memo
    assert rt.passed_checks == before


def test_w65_a_waiting_attempt_records_apart_from_the_pass_it_would_replace(eng, monkeypatch):
    """Batch 19 review 4: until a person approves it, a waiting attempt's record is its own (`judged_checks`); the last
    pass keeps its record, which a memo hit may restore."""
    from pdg.engine_common import checks_now
    eng.project.config["dry_run"] = False
    before = eng.rt("n09_visual_system").passed_checks
    eng.invalidate_nodes(["n09_visual_system"], "a person asked for the visual system again", "Wei")
    _code_upgrade(monkeypatch)                               # the upgrade lands before its checks run
    eng.run(max_steps=20)
    rt = eng.rt("n09_visual_system")
    assert rt.status.value == "WAITING_HUMAN"
    assert rt.passed_checks == before and rt.judged_checks.code == checks_now(eng.project.root)["code"] != before.code


def test_w65_a_node_a_person_approves_after_an_upgrade_keeps_the_code_its_checks_ran_with(eng, monkeypatch):
    """Batch 19 review 3, I1: outside a dry run every node waits for a person. Its checks run when it begins to wait; an
    upgrade that lands before the approval must not be recorded as what judged it."""
    eng.project.config["dry_run"] = False                  # a person approves, as in a real run
    eng.invalidate_nodes(["n09_visual_system"], "a person asked for the visual system again", "Wei")
    eng.run(max_steps=20)
    assert eng.rt("n09_visual_system").status.value == "WAITING_HUMAN"
    _code_upgrade(monkeypatch)                               # an upgrade lands while it waits
    eng.run(max_steps=5)                                     # a step records the new code
    for _ in range(40):
        waiting = [n for n, r in eng.state.runtime.nodes.items() if r.status.value == "WAITING_HUMAN"]
        if not waiting:
            break
        for n in waiting:
            eng.decide(n, "approved", "Wei", "looks right")
        eng.run(max_steps=40)
    assert eng.state.runtime.status.value == "RUN_PASS"
    due = eng.status()["recheck_due"]
    assert "n09_visual_system" in due["nodes"], due          # judged by the code before the upgrade


def test_w65_recheck_release_lists_what_fails_now_and_changes_nothing(eng, tmp_path, monkeypatch, capsys):
    """W65: `pdg recheck-release` re-runs every passed node's tool checks, the browser suite included, on what the run
    released, and lists each failure with whether it would block, and a ready feedback command for each that does. A
    check that could not run is listed apart; a check's own error is a failure (review 2, I2). Only its record is written:
    filing a failure as feedback, which re-opens the release, stays a person's action. A clean re-check with the current
    checks settles the status hint; a person may decline to re-open instead, on record."""
    import pdg.tools.browser as browser_mod
    from pdg.cli import main
    from pdg.engine import Engine
    from pdg.models import NodeStatus, RunStatus
    from .conftest import fake_browser

    def upgraded(ctx):   # the new checks find what the old ones passed
        res = fake_browser(ctx)
        res.dim("A11Y-AXE", False, "axe color-contrast (serious) on lot")
        res.dim("A11Y-FOCUS-POINTER", False, "lot: a redrawn row takes focus")
        return res

    def cannot_run(ctx):
        res = fake_browser(ctx)
        res.errors.append("the browser suite could not run: Executable doesn't exist")
        res.data["blocked"] = "Chromium unavailable"
        return res

    def raises(ctx):
        raise RuntimeError("a bug in the new check")

    def returns_nothing(ctx):
        return None

    def errs(ctx):   # a check that reports a real failure through its errors (a dataset missing from the build)
        res = fake_browser(ctx)
        res.errors.append("the build's data has no dataset `lots`")
        return res
    root = eng.project.root
    eng.rt("n17_targeted_rework").status = NodeStatus.STALE   # a node the passed run did not need is not released
    eng.save("test")
    _code_upgrade(monkeypatch)
    monkeypatch.setattr(browser_mod, "check", upgraded)
    state, ledger = (root / ".pdg" / "state.json").read_text(), (root / ".pdg" / "ledger.jsonl").read_text()
    listing = lambda: sorted(str(p) for p in root.rglob("*") if p.is_file() and p.name not in ("lock", "release-recheck.json"))  # noqa: E731
    files = listing()
    for inside in (root / "work", root):                      # never into the run it re-checks (review 2, the Critical)
        assert main(["recheck-release", str(root), "--out", str(inside)]) == 4
        assert "is inside the project" in capsys.readouterr().out
    assert listing() == files
    out = tmp_path / "recheck"
    assert main(["recheck-release", str(root), "--out", str(out)]) == 1
    text = capsys.readouterr().out
    assert "n13_quality_review A11Y-AXE (would block): stubbed axe; axe color-contrast (serious) on lot" in text, text
    assert "n13_quality_review A11Y-FOCUS-POINTER (advisory)" in text, text
    assert (f"  pdg feedback {root} --actor NAME --text 'A11Y-AXE fails on the released v{eng.state.build.version} "
            "(pdg recheck-release): stubbed axe; axe color-contrast (serious) on lot'") in text, text
    assert text.count("  pdg feedback ") == 1                           # the advisory one gets no command
    rep = json.loads((out / "recheck-release.json").read_text())
    assert {(r["node"], r["dim"], r["blocks"]) for r in rep["failures"]} >= {
        ("n13_quality_review", "A11Y-AXE", True), ("n13_quality_review", "A11Y-FOCUS-POINTER", False)}
    assert rep["judged_by"][0]["code"] != rep["checked_with"]["code"]   # judged by the old code, re-checked by the new
    assert "n17_targeted_rework" not in {c["node"] for c in rep["checked"]}
    assert (out / "n13_quality_review" / "browser-report.json").is_file()        # the evidence is kept
    assert main(["recheck-release", str(root), "--out", str(out)]) == 4           # a used folder is never reused
    assert "already holds files" in capsys.readouterr().out
    assert (root / ".pdg" / "state.json").read_text() == state
    assert (root / ".pdg" / "ledger.jsonl").read_text() == ledger
    assert listing() == files
    assert Engine(root).status()["recheck_due"]["rechecked"]["blocking"] == 1
    main(["status", str(root)])
    assert "with the current checks: 1 failure(s) would block, 0 check(s) could not run; none is filed" in capsys.readouterr().out
    for fake, code, said in ((cannot_run, 3, "not checked: n13_quality_review browser:check: the browser suite could not run"),
                             (returns_nothing, 3, "not checked: n13_quality_review browser:check: browser:check returned NoneType"),
                             (raises, 3, "not checked: n13_quality_review browser:check: browser:check raised RuntimeError"),
                             (errs, 1, "n13_quality_review browser:check (would block): the build's data has no dataset")):
        monkeypatch.setattr(browser_mod, "check", fake)
        assert main(["recheck-release", str(root), "--out", str(tmp_path / fake.__name__)]) == code, fake.__name__
        text = capsys.readouterr().out
        assert said in text and "nothing to re-open" not in text, text
        if fake is raises:   # a suite that never ran is no finding to decline (review 3)
            assert main(["recheck-release", str(root), "--decline", "--actor", "Wei", "--reason", "fine"]) == 4
            assert "check(s) did not run on the release" in capsys.readouterr().out
    assert main(["recheck-release", str(root), "--decline", "--actor", "Wei", "--reason", " "]) == 4
    assert "declining needs a reason" in capsys.readouterr().out
    import datetime as dt
    wei = Engine(root)
    wei.delegate("Wei", "agent:gate-bot", "approve my gates while I am away", ["decide"], None,
                 (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat(), recorded_by="Wei", source="test",
                 except_nodes=["n18_final_verification"])
    assert main(["recheck-release", str(root), "--decline", "--actor", "agent:gate-bot", "--on-behalf-of", "Wei",
                 "--reason", "fine"]) == 4                              # a gate grant never covers it (review 3, I2)
    assert "decline_recheck is not delegable" in capsys.readouterr().out
    failing = Engine(root)
    monkeypatch.setattr(failing, "_write_state", lambda: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(Exception):
        failing.decline_recheck("Wei", "the missing dataset is a stub")
    assert "declined" not in json.loads((root / ".pdg" / "release-recheck.json").read_text())   # never committed (I3)
    assert main(["recheck-release", str(root), "--decline", "--actor", "Wei", "--reason", "the missing dataset is a stub"]) == 0
    capsys.readouterr()
    assert Engine(root).status()["recheck_due"] == {}                   # a person declined, on record
    assert list(Engine(root).ledger.events("recheck_declined"))[-1]["data"]["reason"] == "the missing dataset is a stub"

    def concurrent(ctx):   # someone records feedback while the suite runs (the lock is not held)
        (root / ".pdg" / "state.json").write_text((root / ".pdg" / "state.json").read_text() + " ")
        return upgraded(ctx)
    monkeypatch.setattr(browser_mod, "check", concurrent)
    assert main(["recheck-release", str(root), "--out", str(tmp_path / "meanwhile")]) == 5
    text = capsys.readouterr().out
    assert "the run changed while it was re-checked" in text and "once the run is quiet" in text and "pdg feedback" not in text, text
    assert Engine(root).status()["recheck_due"] == {}                   # the declined record stands; nothing new recorded
    monkeypatch.setattr(browser_mod, "check", fake_browser)
    assert main(["recheck-release", str(root), "--out", str(tmp_path / "again")]) == 0
    assert "nothing to re-open" in capsys.readouterr().out
    assert Engine(root).status()["recheck_due"] == {}                   # settled: re-checked clean with these checks
    stale = Engine(root)
    stale.state.build.version += 1                                      # a record of another build declines nothing
    stale.save("test")
    assert main(["recheck-release", str(root), "--decline", "--actor", "Wei", "--reason", "fine"]) == 4
    assert "no re-check with the current checks on this build" in capsys.readouterr().out
    stale = Engine(root)
    stale.state.build.version -= 1                                      # back to the build that was re-checked
    stale.save("test")
    _code_upgrade(monkeypatch, "pdg/cli.py", "1" * 64)                  # and another lands
    assert Engine(root).status()["recheck_due"]["changed"] == ["the code"]
    fresh = Engine(root)
    fresh.state.runtime.status = RunStatus.RUNNING
    fresh.save("test")
    assert main(["recheck-release", str(root), "--out", str(tmp_path / "none")]) == 4
    assert "refused (nothing checked): nothing released to re-check: the run is RUNNING" in capsys.readouterr().out


def test_r3_22_recheck_release_defaults_to_the_project_pdg_folder(eng, monkeypatch, capsys):
    """R3-22/W66: a recheck run from the package folder files its report beside the run record, not under cwd."""
    import pdg.tools.browser as browser_mod
    from pdg.cli import main
    root = eng.project.root
    monkeypatch.setattr(browser_mod, "check", fake_browser)
    monkeypatch.chdir(Path(__file__).resolve().parents[1])

    assert main(["recheck-release", str(root)]) == 0

    out = capsys.readouterr().out
    reports = list((root / ".pdg" / "release-recheck").glob("*/recheck-release.json"))
    assert len(reports) == 1
    assert f"report: {reports[0].resolve()}" in out
    assert not (Path.cwd() / "release-recheck").exists()
