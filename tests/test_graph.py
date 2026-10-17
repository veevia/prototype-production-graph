"""Graph construction and the validator's guarantees (the engine refuses a graph that fails them)."""

from __future__ import annotations

import copy

import yaml

from pdg.graph import GraphIndex, load_workflow, structural_errors, workspace_errors
from pdg.models import LIFECYCLE_STEPS, EdgeKind, Workflow

from .conftest import PKG


def _wf():
    return load_workflow()


def _mutated(fn) -> list[str]:
    data = yaml.safe_load((PKG / "graph" / "workflow.yaml").read_text())
    fn(data)
    return structural_errors(Workflow.model_validate(data))


def test_graph_is_valid_and_covers_the_lifecycle_in_order():
    wf = _wf()
    assert structural_errors(wf) == []
    assert [n.lifecycle_step for n in wf.nodes] == LIFECYCLE_STEPS
    assert len(wf.nodes) == 19 and len(wf.edges) == 43
    assert {n.phase for n in wf.nodes} == {"Understand", "Design", "Build", "Learn"}
    assert sum(n.human_review.required for n in wf.nodes) == 6


def test_every_node_defines_every_required_field():
    for n in _wf().nodes:
        for f in ("purpose", "depends_on", "inputs", "outputs", "state_read", "state_write", "agent", "skills", "tools",
                  "completion", "evaluation", "retry", "escalation", "failure_conditions", "provenance"):
            assert getattr(n, f), (n.id, f)


def test_graph_is_not_linear_rework_returns_to_design_and_build_nodes():
    wf = _wf()
    idx = GraphIndex(wf)
    loops = {(e.source, e.target) for e in wf.edges if e.kind == EdgeKind.LOOP}
    for t in ("n04_requirements", "n07_experience_architecture", "n08_interaction_design", "n09_visual_system",
              "n10_prototype_planning", "n11_prototype_development", "n12_content_data"):
        assert ("n17_targeted_rework", t) in loops
    assert ("n18_final_verification", "n16_feedback_diagnosis") in loops
    assert ("n02_evidence_review", "n01_context_intake") in loops
    assert idx.descendants("n08_interaction_design") >= {"n10_prototype_planning", "n16_feedback_diagnosis"}
    assert "n09_visual_system" not in idx.descendants("n08_interaction_design")


def test_parallel_fan_out_and_join():
    idx = GraphIndex(_wf())
    assert {e.target for e in idx.flow_out("n12_content_data")} == {"n13_quality_review", "n14_validation", "n15_feasibility_review"}
    assert {e.source for e in idx.flow_in("n16_feedback_diagnosis")} == {"n13_quality_review", "n14_validation", "n15_feasibility_review"}
    assert {e.source for e in idx.flow_in("n10_prototype_planning")} == {"n08_interaction_design", "n09_visual_system"}


def test_validator_rejects_a_flow_cycle():
    errs = _mutated(lambda d: d["edges"].append({"id": "EX", "from": "n05_scope_success", "to": "n03_problem_definition", "kind": "flow",
                                                  "transition": "deterministic", "when": "*", "transfers": ["x"], "threshold": "x", "behavior": "x"}))
    assert any("cycle" in e for e in errs)


def test_validator_rejects_an_unbounded_loop():
    def f(d):
        next(e for e in d["edges"] if e["id"] == "E03").pop("max_traversals")
    assert any("unbounded loop" in e for e in _mutated(f))


def test_validator_rejects_a_loop_that_does_not_go_upstream():
    def f(d):
        next(e for e in d["edges"] if e["id"] == "E03")["to"] = "n05_scope_success"
    assert any("does not go upstream" in e for e in _mutated(f))


def test_validator_rejects_an_unreachable_node():
    def f(d):
        d["edges"] = [e for e in d["edges"] if e["to"] != "n06_concept_ideation"]
    errs = _mutated(f)
    assert any("unreachable" in e for e in errs)


def test_validator_rejects_a_dead_end_outcome():
    def f(d):
        n = next(n for n in d["nodes"] if n["id"] == "n16_feedback_diagnosis")
        n["outcomes"] = ["pass", "rework", "blocked", "defer"]  # every edge out of N16 is conditional
    assert any("dead end" in e for e in _mutated(f))


def test_validator_rejects_a_join_deadlock():
    def f(d):
        n = next(n for n in d["nodes"] if n["id"] == "n08_interaction_design")
        n["outcomes"] = ["pass", "defer"]
        d["edges"].append({"id": "EX", "from": "n08_interaction_design", "to": "@escalate", "kind": "escalate",
                           "transition": "conditional", "when": "defer", "transfers": ["x"], "threshold": "x", "behavior": "x"})
        next(e for e in d["edges"] if e["id"] == "E15").update(transition="conditional", when="pass")
        n12 = next(n for n in d["nodes"] if n["id"] == "n12_content_data")
        n12["outcomes"] = ["pass", "skip"]
        d["edges"].append({"id": "EY", "from": "n12_content_data", "to": "n18_final_verification", "kind": "flow",
                           "transition": "conditional", "when": "skip", "transfers": ["x"], "threshold": "x", "behavior": "x"})
    errs = _mutated(f)
    assert any("strands join" in e or "deadlock" in e for e in errs)


def test_validator_rejects_deterministic_edges_with_conditions_and_locks_without_gates():
    def f(d):
        next(e for e in d["edges"] if e["id"] == "E02")["when"] = "pass"
        n = next(n for n in d["nodes"] if n["id"] == "n07_experience_architecture")
        n["controls"]["lock_on_approval"] = ["experience"]
    errs = _mutated(f)
    assert any("deterministic transition" in e for e in errs)
    assert any("lock_on_approval needs a human gate" in e for e in errs)


def test_validator_rejects_a_rubric_check_the_node_never_runs():
    def f(d):
        next(n for n in d["nodes"] if n["id"] == "n01_context_intake")["evaluation"] = ["evidence"]
    assert any("never runs" in e for e in _mutated(f))


def test_validator_rejects_state_writes_outside_state_write():
    def f(d):
        n = next(n for n in d["nodes"] if n["id"] == "n04_requirements")
        n["state_write"] = ["product.requirements"]
    assert any("not in state_write" in e for e in _mutated(f))


def test_every_skill_exists_in_the_workspace_index():
    errs, warns = workspace_errors(_wf())
    assert errs == [], errs
    if warns:  # outside the workspace the check degrades to a warning
        assert "not found" in warns[0]


def test_workspace_error_for_an_unknown_skill():
    wf = copy.deepcopy(_wf())
    wf.nodes[0].skills.append("no-such-skill-xyz")
    errs, warns = workspace_errors(wf)
    assert errs or warns
    if not warns:
        assert any("no-such-skill-xyz" in e for e in errs)


def test_agent_runtime_bindings_are_known_custom_agents_or_builtins():
    index = (PKG.parents[1] / "03_Agents-and-Skills" / "INDEX.md")
    text = index.read_text() if index.exists() else ""
    for p in (PKG / "agents").glob("*.yaml"):
        a = yaml.safe_load(p.read_text())
        b = a["runtime_binding"]
        assert b.startswith("built-in:") or (not text or f"`{b}`" in text), (p.name, b)


def _node(data, nid):
    return next(n for n in data["nodes"] if n["id"] == nid)


def test_validator_requires_one_owner_per_section_of_a_shared_control_document():
    def drop(d):
        del _node(d, "n14_validation")["controls"]["sections"]
    assert any("declares no owned sections" in e for e in _mutated(drop))

    def overlap(d):
        _node(d, "n14_validation")["controls"]["sections"]["research"].append("Insights")
    assert any("already owned by n02_evidence_review" in e for e in _mutated(overlap))

    def unknown(d):
        _node(d, "n14_validation")["controls"]["sections"]["research"] = ["Validation findings", "Findings v2"]
    assert any("is not a heading of templates/control/research.md" in e for e in _mutated(unknown))

    def orphan(d):
        _node(d, "n08_interaction_design")["controls"]["sections"]["experience"] = ["_preamble"]
        _node(d, "n07_experience_architecture")["controls"]["sections"]["experience"].remove("_preamble")
    errs = _mutated(orphan)
    assert any("'Interactions and states' has no owner" in e for e in errs)


def test_section_owners_map_shared_and_single_writer_documents():
    idx = GraphIndex(_wf())
    research = idx.section_owners("research")
    assert research["Validation findings"] == "n14_validation" and research["_preamble"] == "n02_evidence_review"
    assert idx.section_owners("memory") == {"*": "n19_learning_memory"}


def test_validator_rejects_a_depends_on_mismatch_and_an_empty_field():
    def dep(d):
        _node(d, "n10_prototype_planning")["depends_on"] = ["n08_interaction_design"]
    assert any("depends_on" in e and "flow predecessors" in e for e in _mutated(dep))

    def empty(d):
        _node(d, "n04_requirements")["failure_conditions"] = []
    assert any("n04_requirements: empty failure_conditions" in e for e in _mutated(empty))


def test_validator_rejects_unknown_references():
    def refs(d):
        n = _node(d, "n07_experience_architecture")
        n["agent"] = "no-such-agent"
        n["prompt"] = "prompts/missing.md"
        n["evaluation"] = n["evaluation"] + ["no-such-rubric"]
        n["inputs"] = n["inputs"] + ["state:design.nowhere"]
        n["outputs"][0]["schema"] = "no-such-schema"
    errs = _mutated(refs)
    for needle in ("agent no-such-agent has no definition", "prompt prompts/missing.md not found",
                   "rubric no-such-rubric not found", "'design.nowhere' is not in the typed state", "unknown schema 'no-such-schema'"):
        assert any(needle in e for e in errs), needle


def test_validator_rejects_nodes_out_of_lifecycle_order():
    def swap(d):
        a, b = _node(d, "n03_problem_definition"), _node(d, "n04_requirements")
        a["lifecycle_step"], b["lifecycle_step"] = b["lifecycle_step"], a["lifecycle_step"]
    assert any("lifecycle_step" in e and "brief step" in e for e in _mutated(swap))


def test_validator_rejects_a_node_that_cannot_reach_end():
    def strand(d):
        d["edges"] = [e for e in d["edges"] if e["id"] != "E43"]   # n19 → END
    errs = _mutated(strand)
    assert any("END is not reachable" in e for e in errs)


def test_a_rework_edge_must_allow_as_many_cycles_as_the_policy():
    """Backlog N-03: the policy allowed 4 rework cycles and each rework edge 3, so the two budgets disagreed (W23)."""
    import yaml
    from pdg.graph import structural_errors
    from pdg.models import Workflow
    from pdg.util import PKG_ROOT
    data = yaml.safe_load((PKG_ROOT / "graph" / "workflow.yaml").read_text())
    next(e for e in data["edges"] if e["id"] == "E38")["max_traversals"] = 3
    errs = structural_errors(Workflow.model_validate(data))
    assert any(e.startswith("E38: rework edge allows 3 traversals but policies.max_rework_cycles is") for e in errs)
