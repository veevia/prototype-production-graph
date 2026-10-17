"""Regression tests for audited learning/memory governance findings."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from .conftest import FakeCtx
from pdg.gating import learning_proposal
from pdg.memory import MemoryRefusal, RuleBase
from pdg.models import Defect, ProjectState, ValidationFinding
from pdg.tools.learning import check_lessons


def _state() -> ProjectState:
    return ProjectState.model_validate({"schema_version": "t", "project": {
        "id": "audit-run", "name": "audit", "created": "now", "workflow_id": "w", "workflow_version": "1"}})


def _rules():
    return SimpleNamespace(version="1.0.16", rules=[{"id": "R-A11Y-001"}])


def test_lrn_protected_flags_structured_protected_scope_and_paraphrased_edits():
    ctx = FakeCtx({
        "lessons": {"summary": "s", "lessons": [{
            "id": "L-REQ",
            "statement": "Change the requirements so the prototype can skip citation work.",
            "scope": "reusable",
            "evidence_class": "inferred",
            "evidence": ["R-A11Y-001"],
            "category": "requirements",
        }]},
    }, state=_state())
    ctx.engine.rules = _rules()

    res = check_lessons(ctx)

    assert not res.dimensions["LRN-PROTECTED"].passed


def test_lrn_honest_refuses_verified_lesson_from_all_simulated_validation_finding():
    st = _state()
    st.research.validation_findings.append(ValidationFinding(at_version=1, participants=2, simulated=True,
                                                             task_success_rate=0.5, mean_seq=3, summary="scripted"))
    base = dict(dimension="VAL-TASKS", severity="P2", message="m", evidence="e", traced_node="n14_validation",
                trace_reason="validation finding", smallest_fix="f", acceptance_check="a")
    st.evaluation.defects.append(Defect(id="D-001", signature="VAL-TASKS@simulated", source_nodes=["n14_validation"],
                                        **base))
    ctx = FakeCtx({
        "lessons": {"summary": "s", "lessons": [{
            "id": "L-SIM",
            "statement": "Users missed the queue control.",
            "scope": "reusable",
            "evidence_class": "verified",
            "evidence": ["D-001"],
        }]},
    }, state=st)
    ctx.engine.rules = _rules()

    res = check_lessons(ctx)

    assert not res.dimensions["LRN-HONEST"].passed


class _Ledger:
    def append(self, *args, **kwargs):
        return None


class _ProposalCtx:
    def __init__(self, tmp_path, state):
        self._work = tmp_path
        self._lessons = tmp_path / "lessons.json"
        self._lessons.write_text(json.dumps({"summary": "s", "lessons": [{
            "id": "L-REQ",
            "statement": "Rewrite the requirements so learning can update product truth.",
            "scope": "reusable",
            "evidence_class": "inferred",
            "evidence": ["R-A11Y-001"],
            "category": "requirements",
        }]}))
        self.engine = SimpleNamespace(state=state, dims={}, rules=_rules(), ledger=_Ledger())
        self.node = SimpleNamespace(id="n19_learning_memory")
        self.attempt = 1

    def output(self, key):
        assert key == "lessons"
        return self._lessons

    def out(self, name):
        p = self._work / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def test_learning_proposal_emits_scope_and_apply_refuses_generated_protected_candidate(tmp_path, rules_copy):
    ctx = _ProposalCtx(tmp_path, _state())

    res = learning_proposal(ctx)
    proposal = json.loads((tmp_path / "learning-proposal.json").read_text())

    assert res.outcome == "pass"
    assert proposal["candidates"][0]["target_scope"] == "requirements"
    rb = RuleBase(rules_copy, humans=["Wei"])
    before = rb.sha256()
    with pytest.raises(MemoryRefusal, match="protected scope"):
        rb.apply_proposal(proposal, "Wei", human=True)
    assert rb.sha256() == before


def test_monitored_requires_observation_after_adoption(rules_copy):
    rb = RuleBase(rules_copy, humans=["Wei"])
    rid = "R-TEC-006"
    rb.transition(rid, "validated", "agent:learning-curator", evidence=["tests/test_browser.py::test_final_build"])
    rb.apply_proposal({"run": "pre-adoption", "observations": [{
        "rule": rid, "fired": True, "helped": True, "evidence": ["D-001"],
    }], "candidates": []}, "Wei", human=True)
    rb.transition(rid, "approved", "Wei", human=True, evidence=["review 2026-09-26"])
    rb.transition(rid, "adopted", "Wei", human=True, adopted_in="rubrics/learning.yaml")

    with pytest.raises(MemoryRefusal, match="after adoption"):
        rb.transition(rid, "monitored", "Wei", human=True)


def test_a_candidate_from_a_learning_proposal_can_graduate_once_it_names_its_check(tmp_path, rules_copy, capsys):
    """A proposal's candidate has no executable check. Validation must be able to attach one; otherwise no learned rule
    could ever be validated, approved and adopted (the governance loop would be a dead end)."""
    from pdg.cli import main
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps({"run": "t@v1", "observations": [], "candidates": [{
        "id": "R-NEW-TEST-L01", "statement": "Every queue screen names its empty state in the users' words.",
        "evidence": ["L-01"], "evidence_class": "inferred", "scope": "stable", "category": "experience_and_flows"}]}))
    rules = str(rules_copy)
    assert main(["memory", "apply", "--proposal", str(proposal), "--approved-by", "Wei", "--rules", rules]) == 0
    assert main(["memory", "promote", "R-NEW-TEST-L01", "--to", "validated", "--by", "agent:learning-memory",
                 "--evidence", "tests/test_audit_tools.py::test_f07", "--rules", rules]) == 3        # no check yet: refused
    assert main(["memory", "promote", "R-NEW-TEST-L01", "--to", "validated", "--by", "agent:learning-memory",
                 "--evidence", "tests/test_audit_tools.py::test_f07", "--check-fn", "experience:check_interactions",
                 "--check-dimension", "EXP-STATES", "--rules", rules]) == 0
    assert main(["memory", "promote", "R-NEW-TEST-L01", "--to", "approved", "--by", "Wei", "--human",
                 "--reason", "matches every queue review", "--rules", rules]) == 0
    assert main(["memory", "promote", "R-NEW-TEST-L01", "--to", "adopted", "--by", "Wei", "--human",
                 "--adopted-in", "rubrics/interaction.yaml", "--rules", rules]) == 0
    rule = next(r for r in json.loads(rules_copy.read_text())["rules"] if r["id"] == "R-NEW-TEST-L01")
    assert rule["lifecycle"]["state"] == "adopted"
    assert rule["check"] == {"fn": "experience:check_interactions", "dimensions": ["EXP-STATES"]}
    assert main(["memory", "promote", "R-NEW-TEST-L01", "--to", "monitored", "--by", "Wei", "--human",
                 "--check-test", "x", "--rules", rules]) == 3                                      # a check only at validation


def test_lrn_protected_flags_edits_of_a_protected_scope_but_not_lessons_that_only_mention_one():
    """The statement fallback must catch a lesson that would edit requirements, product truth, evidence or approved
    design principles, and must not block a sound process lesson that only mentions them (N19 is the last node: a false
    positive there would block a real run)."""
    edits = ["Rewrite the requirements so learning can update product truth.",
             "Requirements should be rewritten when a reviewer disagrees.",
             "Relax the evidence log rules for demos.",
             "Rewrite the approved design principles to allow 11 px labels."]
    mentions = ["When requirements change mid-run, re-run the trace check before the gate.",
                "Evidence ids change between rounds; always cite the latest id.",
                "Trace every requirement to evidence before the scope gate."]
    lessons = [{"id": f"L-{i:02d}", "statement": s, "scope": "reusable", "evidence_class": "inferred",
                "evidence": ["R-A11Y-001"]} for i, s in enumerate(edits + mentions)]
    ctx = FakeCtx({"lessons": {"summary": "s", "lessons": lessons}}, state=_state())
    ctx.engine.rules = _rules()
    evidence = check_lessons(ctx).dimensions["LRN-PROTECTED"].evidence
    flagged = {l["id"] for l in lessons if l["id"] in evidence}
    assert flagged == {f"L-{i:02d}" for i in range(len(edits))}


def test_an_observation_counts_for_monitoring_only_if_its_run_came_after_adoption(tmp_path, rules_copy):
    """C14: an observation is dated by the run that made it (the proposal's time), not by when it was applied."""
    from pdg.memory import MemoryRefusal, RuleBase
    rb = RuleBase(rules_copy)
    rid = next(r["id"] for r in rb.rules if r["lifecycle"]["state"] == "adopted")
    old = {"run": "old@v1", "created": "2026-01-01T00:00:00+00:00", "observations": [{"rule": rid, "fired": True}],
           "candidates": []}
    rb.apply_proposal(old, "Wei", human=True)                             # applied now, but the run was in January
    with pytest.raises(MemoryRefusal, match="after adoption"):
        RuleBase(rules_copy).transition(rid, "monitored", "Wei", human=True)
    rb = RuleBase(rules_copy)
    rb.apply_proposal({**old, "run": "new@v1", "created": "2099-01-01T00:00:00+00:00"}, "Wei", human=True)
    assert RuleBase(rules_copy).transition(rid, "monitored", "Wei", human=True)["lifecycle"]["state"] == "monitored"


def test_apply_refuses_a_protected_candidate_that_names_only_its_category(tmp_path, rules_copy):
    """A proposal written by hand, or before target_scope existed, carries only `category`: a protected category is
    refused just the same, and nothing is written."""
    before = rules_copy.read_bytes()
    proposal = {"run": "old@v1", "observations": [], "candidates": [{
        "id": "R-NEW-OLD-L01", "statement": "Requirements may omit acceptance criteria for P1 items.",
        "evidence": ["L-01"], "evidence_class": "inferred", "category": "requirements"}]}
    with pytest.raises(MemoryRefusal, match="protected scope"):
        RuleBase(rules_copy).apply_proposal(proposal, "Wei", human=True)
    assert rules_copy.read_bytes() == before


def test_a_rule_whose_defects_were_mostly_fixed_reads_as_helping_with_its_counts(tmp_path):
    """Backlog B-05: `helped` meant "every defect on the rule's dimensions resolved", so the first project's R-TEC-003,
    with 22 of its 25 defects resolved, read as not helping, and a lesson's own verdict on the rule was dropped."""
    from pdg.models import Defect
    st = _state()
    for i, status in enumerate(["resolved", "resolved", "open"]):
        st.evaluation.defects.append(Defect(id=f"D-{i:03d}", signature=f"TEC-X@s{i}", dimension="TEC-X", severity="P2",
                                            message="m", evidence="e", traced_node="n11_prototype_development",
                                            trace_reason="r", smallest_fix="f", acceptance_check="c", status=status))
    ctx = _ProposalCtx(tmp_path, st)
    ctx.engine.dims = {"TEC-X": {"rule": "R-A11Y-001"}}
    lessons = json.loads(ctx._lessons.read_text())
    lessons["lessons"].append({"id": "L-TEC", "statement": "The rule caught real build defects.", "scope": "project_specific",
                               "evidence_class": "verified", "evidence": ["D-000"], "rule_id": "R-A11Y-001", "helped": False})
    ctx._lessons.write_text(json.dumps(lessons))
    learning_proposal(ctx)
    (ob,) = [o for o in json.loads((tmp_path / "learning-proposal.json").read_text())["observations"]
             if o["rule"] == "R-A11Y-001"]
    assert (ob["defects"], ob["resolved"], ob["open"], ob["helped"], ob["lesson_helped"]) == (3, 2, 1, True, False)
