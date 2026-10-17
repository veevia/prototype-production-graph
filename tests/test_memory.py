"""The governed memory: rule lifecycle gates, human-only approval, versioning, protected scopes, and honest seeds."""

from __future__ import annotations

import json

import pytest

from pdg.context import CheckResult
from pdg.evaluation import evaluate_tool_dims, load_rubrics, mode_for
from pdg.graph import load_workflow
from pdg.memory import MemoryRefusal, RuleBase, is_human


def _rb(path) -> RuleBase:
    return RuleBase(path, humans=["Wei"])


def test_only_named_humans_count_as_human():
    assert is_human("Wei", ["Wei"], True)
    assert not is_human("Wei", ["Wei"], False)                 # the claim must be explicit
    assert not is_human("agent:design-reviewer", ["Wei", "agent:design-reviewer"], True)
    assert not is_human("dry-run (not a human)", ["Wei"], True)
    assert not is_human("Someone", ["Wei"], True)


def test_lifecycle_moves_one_gate_at_a_time_and_approval_needs_a_named_human(rules_copy):
    rb = _rb(rules_copy)
    rid = "R-TEC-006"                                            # a seeded candidate (informational)
    assert rb.get(rid)["lifecycle"]["state"] == "candidate"
    with pytest.raises(MemoryRefusal, match="not a lifecycle transition"):
        rb.transition(rid, "adopted", "Wei", human=True)         # no skipping gates
    with pytest.raises(MemoryRefusal, match="validation evidence"):
        rb.transition(rid, "validated", "agent:learning-curator")
    rb.transition(rid, "validated", "agent:learning-curator", evidence=["tests/test_browser.py::test_final_build"])
    with pytest.raises(MemoryRefusal, match="named human"):
        rb.transition(rid, "approved", "agent:learning-curator", human=True)
    with pytest.raises(MemoryRefusal, match="named human"):
        rb.transition(rid, "approved", "Wei", human=False)
    rb.transition(rid, "approved", "Wei", human=True, evidence=["run 2026-09-26"])
    assert rb.get(rid)["confirmed_by_wei"] is True
    with pytest.raises(MemoryRefusal, match="adopted_in"):
        rb.transition(rid, "adopted", "Wei", human=True)
    rb.transition(rid, "adopted", "Wei", human=True, adopted_in="rubrics/functional.yaml")
    with pytest.raises(MemoryRefusal, match="observation"):
        rb.transition(rid, "monitored", "Wei", human=True)
    states = [h["state"] for h in rb.get(rid)["lifecycle"]["history"]]
    assert states == ["candidate", "validated", "approved", "adopted"]


def test_every_change_is_versioned_and_a_refusal_writes_nothing(rules_copy):
    rb = _rb(rules_copy)
    before = rb.sha256()
    with pytest.raises(MemoryRefusal):
        rb.transition("R-CBV-002", "approved", "agent:x", human=True)
    assert rb.sha256() == before and not (rules_copy.parent / "history").exists()
    v0 = rb.version
    rb.transition("R-CBV-002", "approved", "Wei", human=True, evidence=["review 2026-09-26"])
    major, minor, patch = v0.split(".")
    assert rb.version == f"{major}.{minor}.{int(patch) + 1}"
    assert (rules_copy.parent / "history" / f"rules-v{v0}.json").exists()
    log = [json.loads(x) for x in (rules_copy.parent / "rules-changelog.jsonl").read_text().splitlines()]
    assert log[-1]["rule"] == "R-CBV-002" and log[-1]["to"] == "approved" and log[-1]["human"] is True
    assert _rb(rules_copy).version == rb.version                 # persisted, not just in memory


def test_revision_and_retirement_need_reason_evidence_and_a_human_for_guarded_rules(rules_copy):
    rb = _rb(rules_copy)
    rid = "R-CBV-001"                                            # adopted (seed)
    with pytest.raises(MemoryRefusal, match="reason and evidence"):
        rb.transition(rid, "revised", "Wei", human=True, statement="x")
    with pytest.raises(MemoryRefusal, match="only by a named human"):
        rb.transition(rid, "revised", "agent:learning-curator", reason="r", evidence=["e"], statement="x")
    old = rb.get(rid)["statement"]
    rb.transition(rid, "revised", "Wei", human=True, reason="too strict for workshops", evidence=["run-3"],
                  statement="State the job and the primary persona in one sentence each, with evidence.")
    rule = rb.get(rid)
    assert rule["previous_versions"][-1]["statement"] == old and rule["lifecycle"]["state"] == "revised"


def _seed_base(tmp_path):
    """A small rule base in the seed's own shape: two rules enforced on a seed approval alone, and one candidate."""
    def rule(rid, state, seeded):
        hist = [{"state": "candidate", "at": "2026-09-26", "by": "pdg seed", "human": False, "evidence": [], "reason": "seed"}]
        if seeded:
            hist += [{"state": s, "at": "2026-09-26", "by": "pdg seed", "human": False, "evidence": [], "reason": "seed"}
                     for s in ("validated", "approved", "adopted")]
        return {"id": rid, "statement": rid, "lifecycle": {"state": state, "history": hist}, "check": {"type": "tool"},
                "evidence": ["K01"], "observations": [], "previous_versions": [], "confirmed_by_wei": False}
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"version": "1.0.0", "protected_scopes": [],
                                "rules": [rule("R-A", "adopted", True), rule("R-B", "adopted", True),
                                          rule("R-C", "candidate", False)]}))
    return path


def test_seed_approvals_claim_no_human_decision_until_wei_confirms(tmp_path, rules_copy):
    rb = _rb(_seed_base(tmp_path))
    assert rb.seed_approvals() == ["R-A", "R-B"] and rb.summary()["seed_approvals_awaiting_confirmation"] == ["R-A", "R-B"]
    assert not any(h["human"] for r in rb.rules for h in r["lifecycle"]["history"])      # a seed claims no human decision
    with pytest.raises(MemoryRefusal, match="named human"):
        rb.confirm("R-A", "agent:learning-curator", human=True)
    with pytest.raises(MemoryRefusal, match="only approved rules"):
        rb.confirm("R-C", "Wei", human=True)
    rb.confirm("R-A", "Wei", human=True)
    last = rb.get("R-A")["lifecycle"]["history"][-1]
    assert last["human"] is True and last["by"] == "Wei" and rb.get("R-A")["confirmed_by_wei"] is True
    assert rb.seed_approvals() == ["R-B"]
    with pytest.raises(MemoryRefusal, match="already confirmed"):
        rb.confirm("R-A", "Wei", human=True)
    # the package's own rule base: every human entry is Wei's, and every enforced rule records his decision
    real = _rb(rules_copy)
    assert all(h["by"] == "Wei" for r in real.rules for h in r["lifecycle"]["history"] if h["human"])
    guarded = [r for r in real.rules if r["lifecycle"]["state"] in ("approved", "adopted", "monitored")]
    assert all(r["confirmed_by_wei"] and any(h["human"] for h in r["lifecycle"]["history"]) for r in guarded)


def test_confirming_a_batch_is_one_decision_and_refuses_as_a_whole(tmp_path):
    rb = _rb(_seed_base(tmp_path))
    before = rb.sha256()
    with pytest.raises(MemoryRefusal, match="only approved rules"):
        rb.confirm_many(["R-A", "R-C"], "Wei", human=True)                # one invalid id refuses the batch
    assert rb.sha256() == before and not rb.get("R-A")["confirmed_by_wei"]
    done = rb.confirm_many(rb.seed_approvals(), "Wei", human=True, reason="confirm all",
                           evidence=["chat: 'confirm all'"])
    assert [r["id"] for r in done] == ["R-A", "R-B"] and rb.seed_approvals() == []
    assert rb.version == "1.0.1" and len(list((tmp_path / "history").glob("*.json"))) == 1   # one version, one snapshot
    assert rb.get("R-B")["lifecycle"]["history"][-1]["evidence"] == ["chat: 'confirm all'"]


def test_learning_proposals_add_candidates_only_and_never_touch_protected_scopes(rules_copy):
    rb = _rb(rules_copy)
    proposal = {"run": "dry-run", "observations": [{"rule": "R-CBV-001", "fired": True, "helped": True, "evidence": ["D-001"]}],
                "candidates": [{"id": "R-NEW-LAYOUT-L01", "statement": "Put the evidence before the decision control.",
                                "category": "ux_design", "evidence": ["D-001"], "check": {"type": "review"}}]}
    with pytest.raises(MemoryRefusal, match="named human"):
        rb.apply_proposal(proposal, "agent:learning-curator", human=True)
    bad = {**proposal, "candidates": [{**proposal["candidates"][0], "target_scope": "requirements"}]}
    before = rb.sha256()
    with pytest.raises(MemoryRefusal, match="protected scope"):
        rb.apply_proposal(bad, "Wei", human=True)
    assert rb.sha256() == before
    applied = rb.apply_proposal(proposal, "Wei", human=True)
    assert applied["candidates"] == 1 and applied["observations"] == 1
    new = rb.get("R-NEW-LAYOUT-L01")
    assert new["lifecycle"]["state"] == "candidate"              # a proposal never adopts anything by itself
    assert rb.get("R-CBV-001")["observations"][-1]["helped"] is True
    assert rb.apply_proposal(proposal, "Wei", human=True)["skipped"] == ["R-NEW-LAYOUT-L01"]


def test_enforcement_follows_the_rule_state():
    assert mode_for({"rule": "R"}, {"R": "adopted"}) == "enforced"
    assert mode_for({"rule": "R"}, {"R": "monitored"}) == "enforced"
    assert mode_for({"rule": "R"}, {"R": "validated"}) == "advisory"
    assert mode_for({"rule": "R"}, {"R": "approved"}) == "advisory"
    for s in ("candidate", "revised", "retired"):
        assert mode_for({"rule": "R"}, {"R": s}) == "informational"
    assert mode_for({"rule": "UNKNOWN"}, {}) == "informational"


def test_a_failed_dimension_blocks_only_when_its_rule_is_enforced():
    wf = load_workflow()
    node = next(n for n in wf.nodes if n.id == "n03_problem_definition")
    rubrics = load_rubrics()
    res = CheckResult()
    res.dim("PRB-ONE-SENTENCE", False, "two sentences")
    res.dim("PRB-EVIDENCE", True, "ok")
    res.dim("PRB-HMW", False, "no HMW")
    fns = {d["check"]["fn"] for r in node.evaluation for d in rubrics[r]["dimensions"] if d["check"].get("fn")}
    results = {fn: res for fn in fns}
    rule_of = {d["id"]: d["rule"] for r in node.evaluation for d in rubrics[r]["dimensions"]}
    states = {rule_of["PRB-ONE-SENTENCE"]: "adopted", rule_of["PRB-HMW"]: "validated"}
    _, findings, blocking = evaluate_tool_dims(node, results, rubrics, states)
    assert any("PRB-ONE-SENTENCE" in b for b in blocking)
    assert not any("PRB-HMW" in b for b in blocking)            # advisory: reported, never blocking
    hmw = [f for f in findings if f.dimension == "PRB-HMW"]
    assert hmw and hmw[0].severity == "P4" and not hmw[0].blocking


def test_an_agent_amendment_awaits_wei_and_his_confirmation_records_it(rules_copy):
    """Backlog D8: agents amended adopted rules' checks (enforced at once). Each amendment is marked as awaiting
    Wei's confirmation; `pdg memory confirm` records his decision, by Wei only, and then refuses a second time."""
    rb = _rb(rules_copy)
    pending = rb.pending_amendments()
    assert {"R-A11Y-003", "R-A11Y-007", "R-A11Y-008", "R-SCP-007", "R-VIS-002"} <= set(pending)
    assert "R-VIS-006" not in pending      # validated, not approved: Wei approving the rule covers its amended check
    assert rb.summary()["amendments_awaiting_confirmation"] == pending and not rb.seed_approvals()
    with pytest.raises(MemoryRefusal, match="named human"):
        rb.confirm_many(pending, "agent:main-session", human=True)
    rb.confirm_many(pending, "Wei", human=True, reason="the four WCAG and token amendments are mine")
    assert not _rb(rules_copy).pending_amendments()
    last = _rb(rules_copy).get("R-VIS-002")["lifecycle"]["history"][-1]
    assert last["human"] and last["by"] == "Wei" and "the four WCAG" in last["reason"]
    with pytest.raises(MemoryRefusal, match="already confirmed"):
        _rb(rules_copy).confirm("R-VIS-002", "Wei", human=True)
