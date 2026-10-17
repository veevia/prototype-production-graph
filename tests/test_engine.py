"""Engine behaviour: routing, state, handoffs, parallelism, checkpoints and resume, gates, targeted rework, memo-skips,
locks, integrity. The browser suite is stubbed here (fast); test_dry_run.py runs the real one."""

from __future__ import annotations

import json
import shutil

import pytest

from pdg.engine import Engine, EngineError, StaleSubmission
from pdg.executors import ScriptedExecutor
from pdg.models import NodeStatus

from .conftest import copy_example


def _events(eng, type_=None):
    return [e for e in eng.ledger.events(type_)]


def _run(project) -> Engine:
    eng = Engine(project)
    eng.run(max_steps=400)
    return eng


def test_rework_cycle_then_pass(project, fast_browser):
    eng = _run(project)
    st = eng.state
    assert st.runtime.status.value == "RUN_PASS"
    assert st.runtime.rework_cycles == 1
    outcomes = [g.outcome for g in st.evaluation.gates]
    assert outcomes == ["rework", "pass"]
    ok, _, _ = eng.ledger.verify()
    assert ok


def test_routing_and_conditional_branches(project, fast_browser):
    eng = _run(project)
    loops = eng.state.runtime.loop_traversals
    assert loops.get("E03") == 1                        # gaps_resolvable → back to intake
    assert loops.get("E35") == 1 and loops.get("E38") == 1   # target:n08 and target:n11
    assert "E36" not in loops                           # the visual system was never a target
    assert eng.rt("n17_targeted_rework").status == NodeStatus.STALE   # ran once; not re-run after the pass
    passes = [e["data"]["outcome"] for e in _events(eng, "node_passed") if e["data"]["node"] == "n02_evidence_review"]
    assert passes == ["gaps_resolvable", "pass"]


def test_targeted_rework_reruns_only_traced_nodes(project, fast_browser):
    eng = _run(project)
    att = {n: eng.rt(n).attempt for n in eng.idx.nodes}
    assert att["n08_interaction_design"] == 2 and att["n11_prototype_development"] == 2
    for untouched in ("n03_problem_definition", "n04_requirements", "n05_scope_success", "n06_concept_ideation",
                      "n07_experience_architecture", "n09_visual_system"):
        assert att[untouched] == 1, untouched
    comp = eng.state.evaluation.comparisons[0]
    assert comp.targets == ["n08_interaction_design", "n11_prototype_development"]
    assert comp.verdict == "improved" and comp.resolved and not comp.persisting
    assert comp.before != comp.after
    reworked = {r.node for r in eng.state.history.revisions if r.reason == "rework"}
    assert reworked == {"n08_interaction_design", "n11_prototype_development"}


def test_state_updates_are_typed_and_persisted(project, fast_browser):
    eng = _run(project)
    st = eng.state
    assert st.product.requirements[0].id == "R-01" and type(st.product.requirements[0]).__name__ == "Requirement"
    assert st.design.selected_concept == "K-1"
    assert st.inputs.frozen and st.inputs.inputs_sha256
    assert all(s.sha256 for s in st.inputs.sources if s.path)
    reloaded = Engine(project)                          # resume from disk: identical typed state
    assert reloaded.state.build.version == st.build.version == 2
    assert reloaded.state.product.scope.non_goals == st.product.scope.non_goals


def test_integrity_ignores_python_bytecode_caches_in_registered_artifacts(project, fast_browser):
    eng = _run(project)
    artifact = next(a for a in eng.state.artifacts.values() if a.kind == "dir" and a.current)
    root = eng.project.root / artifact.path

    cache = root / "tests" / "__pycache__"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "probe.cpython-311.pyc").write_bytes(b"bytecode")
    (cache / "note.txt").write_text("cache-local note")
    (root / "module.pyc").write_bytes(b"bytecode")

    assert not [p for p in eng._integrity_problems() if artifact.id in p]
    assert eng._tree_sha(root) == artifact.sha256


def test_parallel_batches_respect_dependencies_and_conflicts(project, fast_browser):
    eng = _run(project)
    batches = [set(e["data"]["nodes"]) for e in _events(eng, "batch")]
    assert {"n08_interaction_design", "n09_visual_system"} in batches
    assert {"n13_quality_review", "n14_validation", "n15_feasibility_review"} in batches
    for b in batches:                                   # no batch runs two writers of one control document
        writers = [d for n in b for d in eng.node(n).controls.write]
        assert len(writers) == len(set(writers))
    # dependencies: nothing downstream of a node ran in the same batch as it
    for b in batches:
        for n in b:
            assert not (eng.idx.descendants(n) & b)


def test_single_flight_resource_and_control_document_conflicts(project, fast_browser):
    eng = Engine(project)
    n13, n14 = eng.node("n13_quality_review"), eng.node("n14_validation")
    assert not eng._conflicts(n13, n14)
    heavy = n14.model_copy(update={"resources": ["browser"]})
    assert eng._conflicts(n13, heavy)                   # both need the one browser
    assert eng._conflicts(eng.node("n03_problem_definition"), eng.node("n04_requirements"))   # both write product.md


def test_task_packet_handoff_tokens_and_retry_context(tmp_path):
    proj = copy_example(tmp_path / "p", dry_run=False)
    eng = Engine(proj)
    eng.run()
    assert eng.rt("n01_context_intake").status == NodeStatus.WAITING_AGENT
    packet = proj / ".pdg" / "tasks" / "n01_context_intake-a1.json"
    data = json.loads(packet.read_text())
    assert data["agent"] == "context-research" and data["token"] and "pdg submit" in data["submit"]
    assert (proj / ".pdg" / "tasks" / "n01_context_intake-a1.md").read_text().startswith("# Task packet")
    fx = proj / "fixtures" / "n01_context_intake" / "attempt-2"
    with pytest.raises(StaleSubmission):
        eng.submit("n01_context_intake", {"sources": str(fx / "sources.json")}, "wrong-token", "agent:context-research")
    with pytest.raises(EngineError):
        eng.submit("n01_context_intake", {"nonsense": str(fx / "sources.json")}, data["token"], "agent:context-research")
    assert eng.rt("n01_context_intake").attempt == 1    # refused submissions use no attempt
    bad = tmp_path / "p" / "bad.json"
    bad.write_text(json.dumps({"sources": [{"id": "S-01", "kind": "brief", "title": "b", "path": "missing.md", "evidence": "reported"}]}))
    res = eng.submit("n01_context_intake", {"sources": str(bad)}, data["token"], "agent:context-research")
    assert res["status"] == "ITERATE" and res["attempts_left"] == 2
    eng.run()
    retry = json.loads((proj / ".pdg" / "tasks" / "n01_context_intake-a2.json").read_text())
    assert any("EVD-SOURCES" in f or "missing brief" in f or "does not exist" in f for f in retry["previous_failures"])
    res = eng.submit("n01_context_intake", {"sources": str(fx / "sources.json")}, retry["token"], "agent:context-research")
    assert res["status"] == "PASSED"


def test_human_gates_only_named_humans_decide_and_approval_locks(tmp_path, fast_browser):
    proj = copy_example(tmp_path / "p", dry_run=False)
    eng = Engine(proj, executor=ScriptedExecutor(proj / "fixtures"))
    eng.run(max_steps=100)
    assert eng.rt("n03_problem_definition").status == NodeStatus.WAITING_HUMAN
    with pytest.raises(EngineError):
        eng.decide("n03_problem_definition", "approved", "agent:product-strategist", "looks right")
    with pytest.raises(EngineError):
        eng.decide("n03_problem_definition", "maybe", "Wei", "hmm")
    eng.decide("n03_problem_definition", "approved", "Wei", "The job and the pain are right.")
    eng.run(max_steps=100)
    assert eng.rt("n05_scope_success").status == NodeStatus.WAITING_HUMAN
    eng.decide("n05_scope_success", "rejected", "Wei", "Add a guardrail on wrong releases.")
    assert eng.rt("n04_requirements").status == NodeStatus.STALE        # E10 rolls back to requirements
    assert any("Add a guardrail" in f for f in eng.rt("n04_requirements").failures)
    eng.run(max_steps=100)
    eng.decide("n05_scope_success", "approved", "Wei", "Signed.")
    assert eng.state.controls["product"].status == "locked" and eng.state.controls["evaluation"].status == "locked"
    ap = [a for a in eng.state.history.approvals if a.node == "n05_scope_success"]
    assert [a.decision for a in ap] == ["rejected", "approved"] and all(a.human for a in ap)


def test_tri_state_gate_blocks_after_three_failed_corrections(project, fast_browser):
    eng = Engine(project)
    eng._force_browser_fail = True                      # the "fix" never works
    eng.run(max_steps=600)
    st = eng.state
    assert st.runtime.status.value == "BLOCKED"
    last = st.evaluation.gates[-1]
    assert last.outcome == "blocked" and any("failed 3 corrections" in r for r in last.reasons)
    esc = [e for e in st.runtime.escalations if e.open]
    assert esc and (project / esc[0].report).read_text().startswith("# Escalation — n16_feedback_diagnosis")
    assert st.runtime.rework_cycles == 3


def test_checkpoint_resume_after_a_crash_does_not_charge_the_attempt(project, fast_browser):
    class Crash(ScriptedExecutor):
        armed = True

        def execute(self, ctx):
            if ctx.node.id == "n06_concept_ideation" and Crash.armed:
                Crash.armed = False
                raise KeyboardInterrupt("simulated process death")
            return super().execute(ctx)

    eng = Engine(project, executor=Crash(project / "fixtures"))
    with pytest.raises(KeyboardInterrupt):
        eng.run(max_steps=400)
    resumed = Engine(project)                           # a new process: resume from .pdg/state.json
    rt = resumed.rt("n06_concept_ideation")
    assert rt.status == NodeStatus.READY and rt.interruptions == 1 and rt.streak == 0
    assert "interrupted" in rt.failures[0]
    assert any(e["type"] == "resume_reset" for e in resumed.ledger.events())
    resumed.run(max_steps=400)
    assert resumed.state.runtime.status.value == "RUN_PASS"
    ok, _, _ = resumed.ledger.verify()
    assert ok


def test_rollback_restores_a_checkpoint_and_keeps_budgets(project, fast_browser):
    eng = _run(project)
    cp = next(c for c in eng.state.history.checkpoints if c.event == "pass" and c.node == "n06_concept_ideation")
    with pytest.raises(EngineError):
        eng.rollback(cp.seq, "agent:orchestrator")
    out = eng.rollback(cp.seq, "Wei")
    assert out["restored_checkpoint"] == cp.seq
    assert eng.rt("n06_concept_ideation").status == NodeStatus.PASSED
    assert eng.rt("n12_content_data").status != NodeStatus.PASSED
    assert eng.state.runtime.loop_traversals.get("E35") == 1           # budgets never go backwards
    assert any(e["type"] == "rollback" for e in eng.ledger.events())
    eng.run(max_steps=400)
    # The continued timeline differs: the scripted developer reuses its corrected attempt, so build v1 passes the gate
    # at once and defects D-002–D-004 never exist. The scripted lessons still cite them, and the learning node must
    # refuse that rather than record evidence this run never produced.
    assert eng.state.evaluation.gates[-1].outcome == "pass" and eng.state.build.version == 1
    assert eng.rt("n18_final_verification").status == NodeStatus.PASSED
    esc = [e for e in eng.state.runtime.escalations if e.open]
    assert esc and esc[0].node == "n19_learning_memory"
    assert any("does not exist in this run" in f for f in eng.rt("n19_learning_memory").failures)


def test_memo_skip_when_a_forced_rerun_changes_nothing(project, fast_browser):
    eng = _run(project)
    before = {n: eng.rt(n).attempt for n in eng.idx.nodes}
    eng.invalidate_nodes(["n07_experience_architecture"], "re-check the flows", "Wei")
    eng.run(max_steps=400)
    after = {n: eng.rt(n).attempt for n in eng.idx.nodes}
    assert after["n07_experience_architecture"] == before["n07_experience_architecture"] + 1
    hits = {e["data"]["node"] for e in eng.ledger.events("memo_hit")}
    assert {"n08_interaction_design", "n09_visual_system"} <= hits    # identical output → descendants memo-skipped
    assert after["n11_prototype_development"] == before["n11_prototype_development"]
    assert eng.state.runtime.status.value == "RUN_PASS"


def test_locked_documents_need_a_change_request_and_evidence_is_append_only(project, fast_browser):
    eng = _run(project)
    c = eng.controls
    assert c.needs_change_request("n04_requirements", ["product"]) == ["product"]
    draft = project / "draft-product.md"
    draft.write_text(c.text("product").replace("## Constraints\n", "## Constraints\n\nAn unapproved change.\n", 1))
    assert "locked" in c.check_install("n04_requirements", ["product"], "product", draft)[0]
    agent_cr = eng.change_request("product", "reword R-09", "agent:product-strategist", writer="n04_requirements")
    assert agent_cr.status == "open"                    # filed, but only a named human can approve it
    assert "locked" in c.check_install("n04_requirements", ["product"], "product", draft)[0]
    cr = eng.change_request("product", "Reword R-09 after the pilot", "Wei", writer="n04_requirements")
    assert cr.status == "approved" and c.check_install("n04_requirements", ["product"], "product", draft) == []
    # a shared document takes only the writer's own sections; an edit elsewhere is ignored (and reported)
    other = project / "draft-product-scope.md"
    other.write_text(c.text("product").replace("## Scope\n", "## Scope\n\nN04 rewrites scope.\n", 1))
    text, ignored = c.merge("n04_requirements", "product", other)
    assert ignored == ["Scope"] and "N04 rewrites scope" not in text
    # evidence is append-only, even for its owner; another writer's edit to it is ignored
    research = project / "draft-research.md"
    research.write_text(c.text("research").replace("- E-01 ·", "- E-01 (edited) ·"))
    errs = c.check_install("n02_evidence_review", ["research"], "research", research)
    assert errs and "append-only" in errs[0]
    assert c.merge("n14_validation", "research", research)[1] == ["Evidence log"]
    assert not list(eng.ledger.events("control_edits_ignored"))   # the scripted agents stay inside their sections


def test_merge_sections_takes_only_owned_sections():
    from pdg.controls import merge_sections
    accepted = "# Doc\n\n> TL;DR: a\n\n## A\n\nold a\n\n## B\n\nold b\n\n## C\n\nold c\n"
    text, ignored = merge_sections(accepted, "## B\n\nnew b\n", ["B"])            # a partial submission
    assert "new b" in text and "old a" in text and "old c" in text and ignored == []
    text, ignored = merge_sections(accepted, "# Other\n\n## A\n\nhijack\n\n## B\n\nnew b\n\n## D\n\nextra\n", ["B"])
    assert "hijack" not in text and "extra" not in text and "# Doc" in text
    assert ignored == ["_preamble", "A", "D"]
    text, _ = merge_sections(accepted, "# Doc v2\n\n## C\n\nnew c\n\n## E\n\nnew e\n", ["_preamble", "C", "E"])
    assert text.startswith("# Doc v2") and "new c" in text and text.rstrip().endswith("new e")


def test_a_hand_edited_control_document_blocks_the_run(project, fast_browser):
    eng = Engine(project)
    eng.run(max_steps=12)
    live = project / "controls" / "research.md"
    accepted = live.read_text()
    live.write_text("tampered\n")
    eng.run(max_steps=5)
    assert eng.state.runtime.status.value == "BLOCKED"
    assert any("edited outside the workflow" in e.reason or "integrity" in e.reason for e in eng.state.runtime.escalations)
    with pytest.raises(EngineError):
        eng.unblock("run", "agent:orchestrator", restore_controls=True)
    eng.unblock("run", "Wei", "restore the accepted research.md", restore_controls=True)
    assert live.read_text() == accepted
    assert any(p.read_text() == "tampered\n" for p in (project / ".pdg" / "controls").glob("research.hand-edit-*.md"))
    eng.run(max_steps=5)
    assert eng.state.runtime.status.value != "BLOCKED"


def test_tampered_artifact_blocks_the_run(project, fast_browser):
    eng = Engine(project)
    eng.run(max_steps=12)
    art = next(a for a in eng.state.artifacts.values() if a.current and a.key == "sources")
    (project / art.path).write_text("{}")
    eng.run(max_steps=5)
    assert eng.state.runtime.status.value == "BLOCKED"


def test_config_change_blocks_until_a_human_accepts_it(project, fast_browser):
    eng = Engine(project)
    eng.run(max_steps=6)
    cfg = project / "pdg.project.yaml"
    cfg.write_text(cfg.read_text() + "\n# a mid-run edit\n")
    eng.run(max_steps=3)
    assert eng.state.runtime.status.value == "BLOCKED"
    with pytest.raises(EngineError):
        eng.accept_config("agent:orchestrator", "fine")
    eng.accept_config("Wei", "the comment is harmless")
    eng.run(max_steps=400)
    assert eng.state.runtime.status.value == "RUN_PASS"


def test_feedback_reopens_diagnosis(project, fast_browser):
    eng = _run(project)
    fb = eng.add_feedback("The notice draft should name the lot's PO in the subject.", "Wei", at="notice")
    assert fb.human and fb.status == "open"
    assert eng.rt("n16_feedback_diagnosis").status == NodeStatus.STALE
    assert eng.state.runtime.status.value == "RUNNING"


def test_the_engine_refuses_an_invalid_graph(tmp_path, project):
    import yaml
    from .conftest import PKG
    data = yaml.safe_load((PKG / "graph" / "workflow.yaml").read_text())
    next(e for e in data["edges"] if e["id"] == "E03").pop("max_traversals")
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(data))
    with pytest.raises(EngineError, match="refusing to run"):
        Engine(project, workflow_path=bad)


# ---------------------------------------------------------------------------------------------- critic regressions
class PendingFor(ScriptedExecutor):
    """Scripted, except that the named nodes wait for a real submission (on their first dispatch only)."""

    def __init__(self, fixtures, nodes):
        super().__init__(fixtures)
        self.nodes, self.seen = set(nodes), set()

    def execute(self, ctx):
        from pdg.context import NodeResult
        if ctx.node.id in self.nodes and ctx.node.id not in self.seen:
            self.seen.add(ctx.node.id)
            return NodeResult(pending=True)
        return super().execute(ctx)


def _submit_fixture(eng, project, node, attempt=1):
    import yaml
    fx = project / "fixtures" / node / f"attempt-{attempt}"
    work = project / "work" / node / f"a{eng.rt(node).attempt}"
    outs = {}
    for key, name in yaml.safe_load((fx / "fixture.yaml").read_text())["outputs"].items():
        shutil.copy(fx / name, work / name)
        outs[key] = name
    return eng.submit(node, outs, eng.rt(node).token, f"agent:{eng.node(node).agent}")


def test_a_submission_cannot_change_a_review_tools_verdict(project, fast_browser):
    eng = Engine(project, executor=PendingFor(project / "fixtures", ["n13_quality_review"]))
    eng.run(max_steps=200)
    assert eng.rt("n13_quality_review").status == NodeStatus.WAITING_AGENT
    work = project / "work" / "n13_quality_review" / "a1"
    forged = json.loads((work / "precheck.json").read_text())
    forged["dimensions"]["A11Y-AXE"] = {"passed": True, "evidence": "forged", "findings": []}
    (work / "precheck.json").write_text(json.dumps(forged))              # the agent's copy: never read back
    (work / "screenshots" / ".DS_Store").write_text("finder")            # OS noise is not a changed tool output
    with pytest.raises(EngineError, match="written by the engine's own check"):
        eng.submit("n13_quality_review", {"browser_report": "precheck.json"}, eng.rt("n13_quality_review").token, "agent:x")
    assert not _submit_fixture(eng, project, "n13_quality_review")["failures"]
    review = eng.latest_review("n13_quality_review")
    assert any(d.id == "A11Y-AXE" and d.status == "fail" for d in review.dimensions)
    assert any(f.dimension == "A11Y-AXE" and f.blocking for f in review.findings)


def test_editing_a_tool_output_before_submitting_fails_the_attempt(project, fast_browser):
    eng = Engine(project, executor=PendingFor(project / "fixtures", ["n13_quality_review"]))
    eng.run(max_steps=200)
    (project / "work" / "n13_quality_review" / "a1" / "browser-report.json").write_text('{"overlay": false}')
    res = _submit_fixture(eng, project, "n13_quality_review")
    assert res["failures"] and "tool outputs changed after the engine's check ran" in res["failures"][0]
    assert eng.rt("n13_quality_review").attempt == 1 and eng.rt("n13_quality_review").streak == 1


def test_a_submission_after_a_hand_edit_blocks_instead_of_overwriting_it(project, fast_browser):
    eng = Engine(project, executor=PendingFor(project / "fixtures", ["n02_evidence_review"]))
    eng.run(max_steps=50)
    assert eng.rt("n02_evidence_review").status == NodeStatus.WAITING_AGENT
    live = project / "controls" / "research.md"
    live.write_text(live.read_text() + "\nWei's note, written by hand.\n")
    token = eng.rt("n02_evidence_review").token
    res = _submit_fixture(eng, project, "n02_evidence_review")
    assert eng.state.runtime.status.value == "BLOCKED" and "blocked" in res["failures"][0]
    assert "written by hand" in live.read_text()                        # nothing was overwritten
    assert eng.rt("n02_evidence_review").status == NodeStatus.WAITING_AGENT and eng.rt("n02_evidence_review").token == token


def test_relocking_after_a_change_request_keeps_the_signing_gate_as_owner(project, fast_browser):
    eng = _run(project)
    assert eng.state.controls["product"].locked_node == "n05_scope_success"
    eng.change_request("product", "Reword the problem after the pilot", "Wei", writer="n03_problem_definition")
    assert eng.state.runtime.status.value != "RUN_PASS"                  # the change re-opens a finished run
    eng.run(max_steps=400)
    rec = eng.state.controls["product"]
    assert rec.locked_node == "n05_scope_success" and rec.unlocked_for is None
    assert eng.controls.needs_change_request("n03_problem_definition", ["product"]) == ["product"]
    assert eng.controls.needs_change_request("n05_scope_success", ["product"]) == []
    assert eng.state.runtime.status.value == "RUN_PASS"


def test_change_request_unlock_set_drops_a_writer_when_it_passes(project, fast_browser):
    eng = _run(project)
    eng.change_request("product", "Reword the problem after the pilot", "Wei", writer="n03_problem_definition")
    rec = eng.state.controls["product"]
    assert "n03_problem_definition" in rec.unlocked_for_nodes
    eng._pass(eng.node("n03_problem_definition"), eng.rt("n03_problem_definition"), "approved", {})
    assert "n03_problem_definition" not in rec.unlocked_for_nodes


def test_rejection_does_not_close_change_request_unlock_at_n03(project, fast_browser):
    eng = _run(project)
    eng.change_request("product", "Reword the problem after the pilot", "Wei", writer="n03_problem_definition")
    rec = eng.state.controls["product"]
    assert "n03_problem_definition" in rec.unlocked_for_nodes
    rt = eng.rt("n03_problem_definition")
    rt.status = NodeStatus.WAITING_HUMAN
    eng.decide("n03_problem_definition", "rejected", "Wei", "not right yet")
    assert "n03_problem_definition" in rec.unlocked_for_nodes


def test_rejection_does_not_clear_change_request_unlock_at_n05(project, fast_browser):
    eng = _run(project)
    eng.change_request("product", "Let requirements change the signed product doc", "Wei", writer="n04_requirements")
    rec = eng.state.controls["product"]
    assert "n04_requirements" in rec.unlocked_for_nodes
    rt = eng.rt("n05_scope_success")
    rt.status = NodeStatus.WAITING_HUMAN
    eng.decide("n05_scope_success", "rejected", "Wei", "scope still wrong")
    assert "n04_requirements" in rec.unlocked_for_nodes


def test_lock_only_submit_refusal_preserves_live_control_edit(project, fast_browser):
    """B23 review: refusing a locked live control edit must not revert the file or use the attempt."""
    eng = _run(project)
    node = "n03_problem_definition"
    rt = eng.rt(node)
    rt.status, rt.attempt, rt.token = NodeStatus.WAITING_AGENT, rt.attempt + 1, "tok"
    live = project / "controls" / "product.md"
    edited = live.read_text() + "\n## Problem\n\nA late live edit.\n"
    live.write_text(edited)
    work = project / "work" / node / f"a{rt.attempt}"
    work.mkdir(parents=True, exist_ok=True)
    problem = project / eng.current("problem")[-1].path
    with pytest.raises(EngineError, match="not accepted, and no attempt was used: product.md is locked"):
        eng.submit(node, {"problem": str(problem), "product_md": str(live)}, "tok", "agent:product-strategist")
    assert live.read_text() == edited
    assert eng.rt(node).status == NodeStatus.WAITING_AGENT and eng.rt(node).token == "tok"


def test_an_invalidation_during_an_attempt_keeps_the_forced_rework(project, fast_browser):
    eng = _run(project)
    eng.executor = PendingFor(project / "fixtures", ["n12_content_data"])
    eng.invalidate(["n12_content_data"], "rework D-999", force=True)
    eng.state.runtime.status = eng.state.runtime.status.__class__("RUNNING")
    eng.run(max_steps=5)
    assert eng.rt("n12_content_data").status == NodeStatus.WAITING_AGENT
    before = eng.rt("n12_content_data").attempt
    eng.invalidate_nodes(["n11_prototype_development"], "rebuild", "Wei")  # rebuilds identically
    eng.run(max_steps=400)
    hits = [e["data"]["node"] for e in eng.ledger.events("memo_hit")]
    assert eng.rt("n12_content_data").attempt == before + 1 and "n12_content_data" not in hits


def test_a_defect_no_reviewer_found_needs_a_newer_build():
    from types import SimpleNamespace

    from pdg.gating import correction_reran
    d = SimpleNamespace(source_nodes=[], opened_at_version=2)
    assert not correction_reran(d, {}, 2) and correction_reran(d, {}, 3)
    again = SimpleNamespace(source_nodes=[], opened_at_version=2, rework_version=3)   # persisted once, reworked again
    assert not correction_reran(again, {}, 3) and correction_reran(again, {}, 4)
    seen = SimpleNamespace(source_nodes=["n13_quality_review"], opened_at_version=2)
    assert correction_reran(seen, {"n13_quality_review": SimpleNamespace(build_version=3)}, 3)
    assert not correction_reran(seen, {"n13_quality_review": SimpleNamespace(build_version=2)}, 3)


def test_rollback_redispatches_a_node_that_was_waiting_on_an_agent(project, fast_browser):
    eng = Engine(project, executor=PendingFor(project / "fixtures", ["n04_requirements"]))
    eng.run(max_steps=100)
    old = eng.rt("n04_requirements").token
    assert eng.rt("n04_requirements").status == NodeStatus.WAITING_AGENT and old
    eng._checkpoint("manual", None)
    seq = eng.state.history.checkpoints[-1].seq
    _submit_fixture(eng, project, "n04_requirements")
    eng.run(max_steps=20)
    eng.rollback(seq, "Wei")
    assert eng.rt("n04_requirements").status == NodeStatus.READY and eng.rt("n04_requirements").token is None
    with pytest.raises(EngineError):
        eng.submit("n04_requirements", {}, old, "agent:product-strategist")


def test_invalidating_while_blocked_keeps_the_run_blocked(project, fast_browser):
    eng = Engine(project)
    eng._force_browser_fail = True
    eng.run(max_steps=600)
    assert eng.state.runtime.status.value == "BLOCKED"
    attempts = eng.rt("n12_content_data").attempt
    eng.invalidate_nodes(["n12_content_data"], "try again", "Wei")
    eng.run(max_steps=20)
    assert eng.state.runtime.status.value == "BLOCKED" and eng.rt("n12_content_data").attempt == attempts


def test_a_crash_mid_commit_restores_the_state_from_before_the_commit(project, fast_browser):
    class Died(BaseException):
        pass

    real = Engine._pass

    def dying(self, node, rt, outcome, data):
        if node.id == "n04_requirements":                                 # it has just installed its product.md sections
            raise Died()                                                  # the process ends mid-commit
        return real(self, node, rt, outcome, data)

    Engine._pass = dying
    try:
        eng = Engine(project)
        with pytest.raises(Died):
            eng.run(max_steps=50)
    finally:
        Engine._pass = real
    assert (project / ".pdg" / "commit-journal.json").exists()
    resumed = Engine(project)
    assert not (project / ".pdg" / "commit-journal.json").exists()
    assert resumed.rt("n04_requirements").status == NodeStatus.READY
    assert resumed.state.controls["product"].version == 1 and not resumed.controls.drift()   # N03's version, not N04's
    assert "## Requirements" in (project / "controls" / "product.md").read_text()
    assert "| R-01 |" not in (project / "controls" / "product.md").read_text()
    assert any(e["type"] == "commit_rolled_back" for e in resumed.ledger.events())
    resumed.run(max_steps=400)
    assert resumed.state.runtime.status.value == "RUN_PASS"


def test_a_directory_output_with_a_link_outside_the_project_is_refused(project, tmp_path):
    from pdg.context import NodeContext
    eng = Engine(project)
    node = eng.node("n11_prototype_development")
    work = project / "work" / node.id / "a9"
    (work / "build").mkdir(parents=True)
    secret = tmp_path / "secret.txt"
    secret.write_text("not for the package")
    (work / "build" / "leak.txt").symlink_to(secret)
    ctx = NodeContext(eng, node, 9, work, "t", "f")
    _, errs = eng._register_outputs(ctx, {"prototype_build": str(work / "build")}, only={"prototype_build"})
    assert errs and "symbolic links" in errs[0]


def test_a_torn_ledger_line_is_set_aside_and_the_chain_continues(tmp_path):
    from pdg.provenance import Ledger
    led = Ledger(tmp_path / "ledger.jsonl")
    for i in range(3):
        led.append("event", i=i)
    with (tmp_path / "ledger.jsonl").open("a") as f:
        f.write('{"seq": 4, "ts": "x", "type": "half')                    # a crash mid-append
    assert Ledger(tmp_path / "ledger.jsonl", read_only=True).verify()[:2] == (True, 3)   # reading skips the fragment
    again = Ledger(tmp_path / "ledger.jsonl")
    again.append("event", i=4)
    ok, n, _ = again.verify()
    assert ok and n == 4 and list(tmp_path.glob("ledger.jsonl.torn-*"))
    # A ledger changed behind an open Ledger (even by a cut-short append) is refused, not appended to: see
    # tests/test_hardening.py::test_a_ledger_changed_behind_an_open_ledger_is_not_appended_to.


def test_a_directory_output_outside_the_work_folder_is_checked_before_it_is_copied(project, tmp_path):
    from pdg.context import NodeContext
    eng = Engine(project)
    node = eng.node("n11_prototype_development")
    work = project / "work" / node.id / "a9"
    work.mkdir(parents=True)
    src = project / "elsewhere" / "build"
    src.mkdir(parents=True)
    secret = tmp_path / "secret.txt"
    secret.write_text("not for the package")
    (src / "leak.txt").symlink_to(secret)
    _, errs = eng._register_outputs(NodeContext(eng, node, 9, work, "t", "f"), {"prototype_build": str(src)},
                                    only={"prototype_build"})
    assert errs and "symbolic links" in errs[0] and not (work / "prototype_build").exists()
    inner = project / "shared"                                           # a link to a directory inside the project…
    inner.mkdir()
    (inner / "leak.txt").symlink_to(secret)                              # …that links outside
    (src / "leak.txt").unlink()
    (src / "assets").symlink_to(inner, target_is_directory=True)
    _, errs = eng._register_outputs(NodeContext(eng, node, 9, work, "t", "f"), {"prototype_build": str(src)},
                                    only={"prototype_build"})
    assert errs and "symbolic links" in errs[0]


def test_an_agent_that_edits_the_live_control_file_has_its_edit_installed_not_blocked(project, fast_browser):
    eng = Engine(project, executor=PendingFor(project / "fixtures", ["n04_requirements"]))
    eng.run(max_steps=100)
    assert eng.rt("n04_requirements").status == NodeStatus.WAITING_AGENT
    fx = project / "fixtures" / "n04_requirements" / "attempt-1"
    work = project / "work" / "n04_requirements" / "a1"
    shutil.copy(fx / "requirements.json", work / "requirements.json")
    live = project / "controls" / "product.md"
    live.write_text(live.read_text().replace("## Requirements\n", "## Requirements\n\n" +
                    (fx / "product.md").read_text().split("## Requirements\n", 1)[1].split("## Constraints", 1)[0], 1))
    token = eng.rt("n04_requirements").token
    edited = live.read_text()
    with pytest.raises(EngineError):                                     # a typo: refused, and nothing changed
        eng.submit("n04_requirements", {"requirements": "requirments.json", "product_md": str(live)}, token, "agent:x")
    assert live.read_text() == edited and not any(e["type"] == "live_control_edit_submitted" for e in eng.ledger.events())
    res = eng.submit("n04_requirements", {"requirements": "requirements.json", "product_md": str(live)},
                     token, "agent:product-strategist")
    assert not res["failures"] and eng.state.runtime.status.value != "BLOCKED"
    assert "| R-01 |" in live.read_text() and not eng.controls.drift()
    assert any(e["type"] == "live_control_edit_submitted" for e in eng.ledger.events())
