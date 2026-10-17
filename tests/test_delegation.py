"""Scoped human delegation: a named human can authorize one agent to take bounded gate actions without impersonation."""

from __future__ import annotations

import datetime as dt
import json
import shlex
from pathlib import Path

import pytest

from pdg.cli import _summary, main, read_status
from pdg.engine import Engine, EngineError, ledger_health
from pdg.executors import ScriptedExecutor
from pdg.gating import human_record
from pdg.models import NodeStatus
from pdg.provenance import Ledger
from pdg.util import read_json

from .conftest import FakeCtx, copy_example

GATE = "n03_problem_definition"
AGENT = "agent:orchestrator"


def _future(days: int = 1) -> str:
    return (dt.datetime.now(dt.UTC) + dt.timedelta(days=days)).isoformat()


def _past() -> str:
    return (dt.datetime.now(dt.UTC) - dt.timedelta(minutes=5)).isoformat()


def _at_gate(tmp_path: Path, gate: str = GATE) -> tuple[Path, Engine]:
    project = copy_example(tmp_path / "p", dry_run=False)
    eng = Engine(project, executor=ScriptedExecutor(project / "fixtures"))
    eng.run(max_steps=100)
    assert eng.rt(gate).status == NodeStatus.WAITING_HUMAN
    return project, eng


def _events(project: Path, type_: str | None = None) -> list[dict]:
    return list(Ledger(project / ".pdg" / "ledger.jsonl", read_only=True).events(type_))


def test_an_agent_cannot_decide_a_gate_without_delegation(tmp_path):
    project, eng = _at_gate(tmp_path)
    before = (project / ".pdg" / "state.json").read_bytes()
    with pytest.raises(EngineError, match="delegation|named human"):
        eng.decide(GATE, "approved", AGENT, "Wei asked me to proceed.", on_behalf_of="Wei")
    assert (project / ".pdg" / "state.json").read_bytes() == before
    assert not [e for e in _events(project, "decision") if e["data"].get("node") == GATE]


def test_delegated_agent_decision_is_accepted_and_recorded_honestly(tmp_path):
    project, eng = _at_gate(tmp_path)
    delegation = eng.delegate("Wei", AGENT, "Approve the problem gate if the evidence still matches my brief.",
                              ["decide"], [GATE], _future())
    out = eng.decide(GATE, "approved", AGENT, "Evidence still matches Wei's brief.", on_behalf_of="Wei")
    assert out["human"] is False and out["on_behalf_of"] == "Wei" and out["delegation"] == delegation.id
    approval = eng.state.history.approvals[-1]
    assert approval.actor == AGENT and not approval.human
    assert approval.on_behalf_of == "Wei" and approval.delegation == delegation.id
    decision = _events(project, "decision")[-1]["data"]
    assert decision["actor"] == AGENT and decision["human"] is False
    assert decision["on_behalf_of"] == "Wei" and decision["delegation"] == delegation.id
    rows, counts = human_record(eng)
    assert counts["actions"] >= 2
    assert any(f"delegated by Wei ({delegation.id})" in row and AGENT in row for row in rows)
    ok, _, why = ledger_health(project / ".pdg" / "ledger.jsonl", read_json(project / ".pdg" / "state.json")["runtime"])
    assert ok, why


def test_delegated_action_is_not_reported_as_missing_typist(tmp_path, capsys):
    project, eng = _at_gate(tmp_path)
    grant = eng.delegate("Wei", AGENT, "Approve the problem gate if it still matches my brief.",
                         ["decide"], [GATE], _future(), recorded_by="Wei")
    assert main(["approve", str(project), GATE, "--actor", AGENT, "--on-behalf-of", "Wei",
                 "--reason", "Evidence still matches the brief."]) == 0
    out = capsys.readouterr().out
    assert grant.id in out and "human action(s) without typist" not in out
    assert read_status(str(project))["transcribed_actions"] == []


def test_human_action_without_recorded_by_is_flagged_once(tmp_path, capsys):
    project, _ = _at_gate(tmp_path)
    assert main(["approve", str(project), GATE, "--actor", "Wei", "--reason", "Looks right."]) == 0
    out = capsys.readouterr().out
    assert "1 human action(s) without typist; example: decision by Wei" in out
    assert out.count("who typed it is not recorded") == 1
    transcribed = read_status(str(project))["transcribed_actions"]
    assert len(transcribed) == 1 and transcribed[0]["actor"] == "Wei" and transcribed[0]["recorded_by"] == ""


def test_missing_typist_summary_is_bounded_to_one_example():
    status = {"project": "p", "status": "RUNNING", "build_version": 1, "rework_cycles": 0, "batches": 1,
              "ledger_events": 3, "waiting_agent": [], "waiting_human": [], "human_actions": [],
              "transcribed_actions": [{"action": "decision", "actor": "Wei", "recorded_by": ""},
                                      {"action": "unblock", "actor": "Wei", "recorded_by": ""},
                                      {"action": "risk_accepted", "actor": "Wei", "recorded_by": ""}],
              "escalations": [], "open_defects": [], "nodes": {}, "budget_resets": {}}
    out = _summary(status)
    assert "3 human action(s) without typist; example: decision by Wei" in out
    assert out.count("who typed it is not recorded") == 1
    assert "unblock by Wei" not in out and "risk_accepted by Wei" not in out


def test_human_only_actions_are_listed_in_status(tmp_path, capsys):
    project, _ = _at_gate(tmp_path)
    assert main(["status", str(project)]) == 0
    out = capsys.readouterr().out
    assert "human-only actions this run keeps human-only:" in out
    for phrase in ("release gate (N18)", "rollback", "archive --apply", "confirm memory rules",
                   "promote memory rules", "apply memory proposals", "decline a release re-check",
                   "reset a rework budget"):
        assert phrase in out


@pytest.mark.parametrize(
    "label,grant,actor,human,error",
    [
        ("expired", {"expire_after_grant": True}, AGENT, "Wei", "expired"),
        ("out-of-scope", {"scope": ["change_request"]}, AGENT, "Wei", "out of scope"),
        ("wrong-agent", {}, "agent:other", "Wei", "no active delegation|wrong agent"),
        ("wrong-human", {}, AGENT, "NotWei", "no active delegation|wrong human"),
    ],
)
def test_delegated_decision_refuses_expired_revoked_out_of_scope_wrong_actor_or_human(tmp_path, label, grant, actor, human, error):
    project, eng = _at_gate(tmp_path)
    scope = grant.get("scope", ["decide"])
    delegation = eng.delegate("Wei", AGENT, f"{label}: approve only under this grant.", scope,
                              [GATE] if scope == ["decide"] else None, grant.get("expires", _future()))
    if grant.get("expire_after_grant"):
        delegation.expires = _past()
    with pytest.raises(EngineError, match=error):
        eng.decide(GATE, "approved", actor, f"{label} should not be authorized.", on_behalf_of=human)
    assert eng.rt(GATE).status == NodeStatus.WAITING_HUMAN
    assert not [e for e in _events(project, "decision") if e["data"].get("delegation") == delegation.id]


def test_revoked_delegation_no_longer_authorizes_the_agent(tmp_path):
    project, eng = _at_gate(tmp_path)
    delegation = eng.delegate("Wei", AGENT, "Approve once if still aligned.", ["decide"], [GATE], _future())
    eng.revoke_delegation(delegation.id, "Wei")
    with pytest.raises(EngineError, match="revoked"):
        eng.decide(GATE, "approved", AGENT, "Still aligned.", on_behalf_of="Wei")
    assert _events(project, "delegation_revoked")[-1]["data"]["id"] == delegation.id


def test_only_named_humans_can_grant_delegation_and_grants_are_validated(tmp_path):
    _, eng = _at_gate(tmp_path)
    with pytest.raises(EngineError, match="named human"):
        eng.delegate(AGENT, "agent:builder", "Do it.", ["decide"], [GATE], _future())
    with pytest.raises(EngineError, match="agent:"):
        eng.delegate("Wei", "orchestrator", "Do it.", ["decide"], [GATE], _future())
    with pytest.raises(EngineError, match="instruction"):
        eng.delegate("Wei", AGENT, "  ", ["decide"], [GATE], _future())
    with pytest.raises(EngineError, match="scope"):
        eng.delegate("Wei", AGENT, "Do it.", ["accept-ledger-break"], [GATE], _future())
    with pytest.raises(EngineError, match="human gate"):
        eng.delegate("Wei", AGENT, "Do it.", ["decide"], ["n01_context_intake"], _future())
    with pytest.raises(EngineError, match="future"):
        eng.delegate("Wei", AGENT, "Do it.", ["decide"], [GATE], _past())


def test_never_delegable_actions_stay_human_only_even_after_a_grant(tmp_path):
    _, eng = _at_gate(tmp_path)
    eng.delegate("Wei", AGENT, "Approve only the problem gate.", ["decide"], [], _future(),
                 except_nodes=["n18_final_verification"])
    with pytest.raises(EngineError, match="named human"):
        eng.rollback(1, AGENT)


def test_delegated_risk_acceptance_requires_explicit_scope_and_passes_the_plan_gate(tmp_path):
    from pdg.tools import plan

    project, eng = _at_gate(tmp_path)
    aid = next(a.id for a in eng.state.research.assumptions if a.riskiest)
    eng.delegate("Wei", AGENT, "Approve the problem gate only.", ["decide"], [], _future(),
                 except_nodes=["n18_final_verification"])
    with pytest.raises(EngineError, match="out of scope"):
        eng.accept_risk(aid, AGENT, "Wei accepted this assumption for this prototype.", on_behalf_of="Wei")

    delegation = eng.delegate("Wei", AGENT, "Accept the riskiest assumption for this prototype only.",
                              ["accept_risk"], [], _future())
    out = eng.accept_risk(aid, AGENT, "Wei accepted this assumption for this prototype.", on_behalf_of="Wei")
    assert out["actor"] == AGENT and out["on_behalf_of"] == "Wei" and out["delegation"] == delegation.id
    recorded = eng.state.history.risk_acceptances[-1]
    assert recorded.actor == AGENT and recorded.on_behalf_of == "Wei" and recorded.delegation == delegation.id

    plan_doc = json.loads((project / "fixtures" / "n10_prototype_planning" / "attempt-2" / "plan.json").read_text())
    for ac in plan_doc["riskiest_assumptions"]:
        ac["status"] = "accepted_risk"
        ac["evidence_ids"] = []
    res = plan.check(FakeCtx({"plan": plan_doc}, state=eng.state))
    assert res.dimensions["PLN-FIDELITY-GATE"].passed
    assert f"{aid} by {AGENT} on behalf of Wei ({delegation.id})" in res.dimensions["PLN-FIDELITY-GATE"].evidence


def test_delegated_change_request_is_approved_but_names_the_agent(tmp_path):
    project, eng = _at_gate(tmp_path)
    delegation = eng.delegate("Wei", AGENT, "Unlock product for the problem-definition writer if needed.",
                              ["change_request"], [], _future())
    cr = eng.change_request("product", "Wei asked for a scoped document fix.", AGENT,
                            writer=GATE, on_behalf_of="Wei")
    assert cr.status == "approved" and cr.by == AGENT and cr.human is False
    assert cr.on_behalf_of == "Wei" and cr.delegation == delegation.id
    ev = _events(project, "change_request")[-1]["data"]
    assert ev["by"] == AGENT and ev["on_behalf_of"] == "Wei" and ev["delegation"] == delegation.id


def test_cli_can_grant_revoke_and_use_delegation(tmp_path, capsys):
    project, _ = _at_gate(tmp_path)
    assert main(["delegate", str(project), "--by", "Wei", "--agent", AGENT, "--instruction",
                 "Approve the current problem gate if unchanged.", "--scope", "decide", "--nodes", GATE,
                 "--expires", _future(), "--recorded-by", "Wei"]) == 0
    out = capsys.readouterr().out
    assert "DL-001" in out
    assert main(["approve", str(project), GATE, "--actor", AGENT, "--on-behalf-of", "Wei", "--reason",
                 "Still unchanged."]) == 0
    state = read_json(project / ".pdg" / "state.json")
    assert state["history"]["approvals"][-1]["delegation"] == "DL-001"
    assert main(["revoke-delegation", str(project), "DL-001", "--by", "Wei"]) == 0
    events = _events(project, "delegation_revoked")
    assert events and events[-1]["data"]["id"] == "DL-001"


def test_cli_delegate_release_scope_needs_include_release(tmp_path, capsys):
    project, _ = _at_gate(tmp_path)
    base = ["delegate", str(project), "--by", "Wei", "--agent", AGENT, "--instruction",
            "Decide gates until the release.", "--scope", "decide", "--expires", _future(), "--recorded-by", "Wei"]
    assert main(base) == 4
    assert "include-release" in capsys.readouterr().out
    assert main(base + ["--include-release"]) == 0


def test_transcribed_human_action_requires_source_and_can_be_ratified(tmp_path, capsys):
    project, _ = _at_gate(tmp_path)
    assert main(["approve", str(project), GATE, "--actor", "Wei", "--reason", "Looks right.",
                 "--recorded-by", AGENT]) == 4
    assert "source" in capsys.readouterr().out
    assert main(["approve", str(project), GATE, "--actor", "Wei", "--reason", "Looks right.",
                 "--recorded-by", AGENT, "--source", "Wei: Looks right.", "--interprets"]) == 0
    ev = _events(project, "decision")[-1]
    assert ev["data"]["recorded_by"] == AGENT and ev["data"]["source"] == "Wei: Looks right."
    status = main(["status", str(project)])
    assert status == 0
    assert "unconfirmed interpretation" in capsys.readouterr().out
    assert main(["ratify", str(project), str(ev["seq"]), "--actor", "Wei", "--reason", "Yes, that is what I meant."]) == 0
    decision = next(x for x in read_status(str(project))["transcribed_actions"] if x["event"] == str(ev["seq"]))
    assert decision["ratified"] is True
    assert main(["ratify", str(project), str(ev["seq"]), "--actor", "Wei", "--reason", "No, reverse it.",
                 "--reverse"]) == 0
    decision = next(x for x in read_status(str(project))["transcribed_actions"] if x["event"] == str(ev["seq"]))
    assert decision["reversed"] is True and decision["ratified"] is False
    assert main(["ratify", str(project), "99999", "--actor", "Wei", "--reason", "typo"]) == 4
    assert "unknown action" in capsys.readouterr().out
    assert main(["ratify", str(project), str(ev["seq"]), "--actor", AGENT, "--reason", "not human"]) == 4
    assert "named human" in capsys.readouterr().out


def test_stamped_human_action_marks_every_event_it_writes(tmp_path):
    project, eng = _at_gate(tmp_path)
    start = eng.ledger._last[0]
    eng.decide(GATE, "approved", "Wei", "Looks right.", feedback=["tighten the copy"],
               recorded_by=AGENT, source="Wei: Looks right.")
    events = [e for e in _events(project) if e["seq"] > start]
    assert [e["type"] for e in events] == ["feedback", "decision", "node_passed"]
    assert all(e["data"].get("recorded_by") == AGENT for e in events)
    assert all(e["data"].get("source") == "Wei: Looks right." for e in events)
    eng.ledger.append("after_action")
    assert "recorded_by" not in _events(project)[-1]["data"]


def test_placeholder_reasons_are_refused_before_ledgering(tmp_path, capsys):
    project, eng = _at_gate(tmp_path)
    aid = next(a.id for a in eng.state.research.assumptions if a.riskiest)
    assert main(["accept-risk", str(project), aid, "--actor", "Wei", "--reason", "<your words>"]) == 4
    assert "placeholder" in capsys.readouterr().out
    assert main(["approve", str(project), GATE, "--actor", "Wei", "--reason", "Looks right.",
                 "--recorded-by", "Wei", "--source", "<Wei's words>"]) == 4
    assert "source" in capsys.readouterr().out
    with pytest.raises(EngineError, match="placeholder"):
        eng.accept_risk(aid, "Wei", "<your words>")
    assert not _events(project, "risk_accepted")


def test_missing_reason_without_terminal_refuses_before_locking(tmp_path, capsys):
    project, _ = _at_gate(tmp_path)
    assert main(["approve", str(project), GATE, "--actor", "Wei"]) == 4
    assert "required when no terminal is attached" in capsys.readouterr().out


def test_waiting_lists_ready_human_commands(tmp_path, capsys):
    project, _ = _at_gate(tmp_path)
    assert main(["waiting", str(project)]) == 0
    out = capsys.readouterr().out
    assert "approve" in out and "--reason" not in out and "<" not in out and "…" not in out
    assert "accept-risk" not in out
    commands = [line.split("|")[3].strip() for line in out.splitlines()[2:] if line.strip() and line.split("|")[3].strip() != "—"]
    assert commands
    for cmd in commands:
        parts = shlex.split(cmd)
        assert parts[0] == "pdg"
        assert main(parts[1:]) == 4
        assert "required when no terminal is attached" in capsys.readouterr().out


def test_status_json_evaluation_exposes_dimensions_and_defects(tmp_path, capsys):
    project, _ = _at_gate(tmp_path)
    assert main(["status", str(project), "--json", "--evaluation"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert "dimensions" in data["evaluation"] and "defects" in data["evaluation"]
    assert all({"id", "status", "evidence"} <= set(d) for d in data["evaluation"]["dimensions"])
    assert all({"id", "signature", "severity", "status", "owner_node", "message"} <= set(d)
               for d in data["evaluation"]["defects"])


def test_n10_human_precondition_refusal_names_exact_accept_risk_command(tmp_path):
    project, eng = _at_gate(tmp_path)
    src = json.loads((Path(__file__).resolve().parents[1] / "examples/coa-review/fixtures/n10_prototype_planning/attempt-2/plan.json").read_text())
    for ac in src["riskiest_assumptions"]:
        ac["status"] = "accepted_risk"
        ac["evidence_ids"] = []
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(src))
    msg = eng._human_precondition_refusals(eng.node("n10_prototype_planning"), {"plan": str(plan)})[0]
    assert "pdg accept-risk" in msg and "A-01" in msg and "--actor Wei`" in msg and "--reason" not in msg


def test_n16_packet_lists_current_review_finding_keys_not_trace_owner(tmp_path):
    from pdg.models import FindingRecord, ReviewRecord
    from pdg.context import NodeContext

    project, eng = _at_gate(tmp_path)
    eng.state.evaluation.reviews.append(ReviewRecord(
        node="n13_quality_review", attempt=1, build_version=eng.state.build.version, dimensions=[], findings=[
            FindingRecord(node="n13_quality_review", dimension="LAYOUT-COMPARISON-FIRST", severity="P2",
                          message="Bad layout", location="lot", traced_node="n08_interaction_design", blocking=True,
                          smallest_fix="Fix it", acceptance_check="No bad layout")],
        passed=False, summary="s", at="2026-01-01T00:00:00+00:00"))
    ctx = NodeContext(eng, eng.node("n16_feedback_diagnosis"), 1, project / "work/n16_feedback_diagnosis/a1", "tok", "")
    keys = [f["key"] for f in eng.task_packet(ctx)["blocking_findings"]]
    assert keys == ["n13_quality_review:LAYOUT-COMPARISON-FIRST@lot"]


def test_status_marks_learning_pending_live_not_in_release_summary(tmp_path):
    project, eng = _at_gate(tmp_path)
    eng.rt("n18_final_verification").status = NodeStatus.PASSED
    eng.rt("n19_learning_memory").status = NodeStatus.WAITING_AGENT
    eng.save("test")
    assert read_status(str(project))["learning_pending"] is True
    from pdg.cli import _summary
    assert "learning pending" in _summary(read_status(str(project)))


def test_tool_dimension_details_are_kept_on_human_gate_attempt(tmp_path, fast_browser):
    project = copy_example(tmp_path / "dry")
    eng = Engine(project)
    eng.run(max_steps=400)
    details = eng.rt("n18_final_verification").tool_details
    assert any(d.startswith("REL-CONDITIONS:") for d in details)


def test_waiting_agent_age_flags_stale_tasks(tmp_path):
    project, eng = _at_gate(tmp_path)
    rt = eng.rt("n04_requirements")
    rt.status = NodeStatus.WAITING_AGENT
    rt.attempt = 1
    eng.ledger.append("task_issued", node="n04_requirements", attempt=1, agent="product-manager")
    eng.save("test")
    assert read_status(str(project))["waiting_agent"]
    ledger = project / ".pdg" / "ledger.jsonl"
    lines = [json.loads(x) for x in ledger.read_text().splitlines()]
    for ev in lines:
        if ev["type"] == "task_issued":
            ev["ts"] = "2026-01-01T00:00:00+00:00"
    ledger.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    assert read_status(str(project))["waiting_agent_details"][0]["stale"] is True


def test_include_release_is_stored_and_agent_typed_release_grants_are_refused(tmp_path):
    from pdg.models import Delegation

    project, eng = _at_gate(tmp_path)
    with pytest.raises(EngineError, match="include-release"):
        eng.delegate("Wei", AGENT, "All gates.", ["decide"], [], _future())
    with pytest.raises(EngineError, match="must be typed by the named human"):
        eng.delegate("Wei", AGENT, "Release too.", ["decide"], [], _future(), include_release=True,
                     recorded_by=AGENT, source="chat")
    grant = eng.delegate("Wei", AGENT, "Release too.", ["decide"], [], _future(), include_release=True,
                         recorded_by="Wei")
    assert grant.include_release is True
    eng.state.history.delegations.append(Delegation(id="DL-legacy", by="Wei", instruction="old broad grant",
                                                    scope=["decide"], agent=AGENT, created="2026-01-01T00:00:00+00:00",
                                                    expires=_future(), include_release=False))
    with pytest.raises(EngineError, match="does not include the release gate"):
        eng._authority(AGENT, "decide", "n18_final_verification", "Wei")


def test_a_node_list_scopes_decide_only_so_a_grant_that_could_never_apply_is_refused(tmp_path):
    """Field run 2, R2-01: `--nodes` can name only gates, but an unblock names the escalated node (n16, n17) and a change
    request its writer, so `--scope decide,unblock --nodes <gate>` granted an unblock that could never apply. The
    refusal came at the escalation, with the loop already stopped. Now the grant itself is refused, saying what to do."""
    project, eng = _at_gate(tmp_path)
    before = (project / ".pdg" / "state.json").read_bytes()
    with pytest.raises(EngineError, match=r"--nodes scopes `decide` only.*unblock.*--except-nodes"):
        eng.delegate("Wei", AGENT, "Decide the problem gate and unblock anything.", ["decide", "unblock"], [GATE], _future())
    assert (project / ".pdg" / "state.json").read_bytes() == before


def test_except_nodes_keeps_the_release_human_in_one_grant(tmp_path):
    """Backlog D1 in one grant: every gate and every loop action except the release. The deny-list binds every
    node-bound action, including each target of an invalidation."""
    project, eng = _at_gate(tmp_path)
    release = "n18_final_verification"
    eng.delegate("Wei", AGENT, "Run the loop for me, but the release is mine.", ["decide", "unblock", "invalidate"], None,
                 _future(), except_nodes=[release])
    out = eng.decide(GATE, "approved", AGENT, "the frame restates the brief", on_behalf_of="Wei")
    assert out["delegation"] == "DL-001"
    with pytest.raises(EngineError, match=f"out of scope for {release}"):
        eng.invalidate_nodes([release], "try it", AGENT, on_behalf_of="Wei")
    with pytest.raises(EngineError, match=f"out of scope for {release}"):
        eng._authority(AGENT, "decide", release, "Wei")
    assert eng.invalidate_nodes(["n01_context_intake"], "re-read the sources", AGENT, on_behalf_of="Wei")


def test_r2_30_a_grant_near_its_end_says_so_and_a_lapsed_one_says_how_to_renew(tmp_path):
    """Field run 2, R2-30: both of the run's grants expired at 16:30Z; a stakeholder's change request that arrived at 16:24Z
    was refused when the work was ready, and nothing had warned. The status line now gives each grant's time left and,
    in its last 24 hours or once expired, the command that renews it with every limit it had; the refusal names the
    lapsed grant that would have covered the action (config batch 5, part 2 review C1, I5, S1, S7)."""
    from pdg.cli import _summary, read_status
    project, eng = _at_gate(tmp_path)
    soon = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=3, minutes=10)).isoformat()
    later = eng.delegate("Wei", AGENT, "Keep the gates moving.", ["decide"], [GATE], _future(3))
    near = eng.delegate("Wei", AGENT, "Change requests while I am away.", ["change_request", "unblock"], None, soon,
                        except_nodes=["n18_final_verification"], budget_resets=1)
    gone = eng.delegate("Wei", AGENT, "Old grant.", ["invalidate"], None, _future())
    eng.revoke_delegation(gone.id, "Wei")
    text = _summary(read_status(str(project)))
    assert f"delegation {later.id} for {AGENT} (decide on {GATE}) expires in 71 h" in text, text
    renew = (f"pdg delegate {project} --by Wei --agent {AGENT} --scope change_request,unblock --except-nodes "
             "n18_final_verification --budget-resets 1 --expires --instruction --recorded-by")
    assert (f"delegation {near.id} for {AGENT} (change_request, unblock except n18_final_verification, 1 budget reset(s)) "
            f"expires in 3 h 9 min: ask Wei to renew it (`{renew}") in text, text
    assert gone.id not in text, text                                        # revoked: not shown
    assert text == _summary({**eng.status(), "ledger_events": read_status(str(project))["ledger_events"],
                             "project_root": str(project)})
    near.expires = _past()                                                  # only the change-request grant lapsed
    eng.save("test")
    with pytest.raises(EngineError, match=rf"delegation {near.id} expired at .*; ask Wei to renew it \(`pdg delegate"):
        eng._authority(AGENT, "change_request", None, "Wei")             # the decide grant still lives: name this one
    assert f"delegation {near.id} for {AGENT} (change_request, unblock except n18_final_verification, 1 budget reset(s)) " \
           f"expired 5 min ago: ask Wei to renew it" in _summary(read_status(str(project)))
    renewed = eng.delegate("Wei", AGENT, "Change requests, renewed.", ["change_request", "unblock"], None, _future(),
                           except_nodes=["n18_final_verification"], budget_resets=1)
    text = _summary(read_status(str(project)))
    assert f"delegation {near.id} " not in text and f"delegation {renewed.id} " in text, text   # superseded: not shown
    wide = eng.delegate("Wei", AGENT, "Every gate but the release.", ["decide"], None, _future(),
                        except_nodes=["n18_final_verification"])
    narrow = eng.delegate("Wei", AGENT, "Only the problem gate.", ["decide"], [GATE], _future())
    wide.expires = _past()                                                  # the wider decide grant lapsed
    eng.save("test")
    text = _summary(read_status(str(project)))
    assert f"delegation {wide.id} " in text and f"delegation {narrow.id} " in text, text    # a narrower one hides nothing
    early = eng.delegate("Wei", AGENT, "Change requests, renewed early.", ["change_request", "unblock"], None, _future(2),
                         except_nodes=["n18_final_verification"], budget_resets=1)
    renewed.expires = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=2)).isoformat()
    eng.save("test")
    line = next(x for x in _summary(read_status(str(project))).split("\n") if f"delegation {renewed.id} " in x)
    assert "expires in 1 h" in line and "renew" not in line, line                     # already renewed by the early one
    assert early.id
    # a grantor who left the humans list, and an expiry no one can read (review S2, N3)
    import yaml
    cfg = yaml.safe_load((project / "pdg.project.yaml").read_text()) or {}
    odd = eng.delegate("Wei", AGENT, "Unreadable.", ["invalidate"], None, _future())
    odd.expires = "next tuesday"
    eng.save("test")
    assert f"delegation {odd.id} for {AGENT} (invalidate): its expiry 'next tuesday' cannot be read, so it authorizes nothing" \
        in _summary(read_status(str(project)))
    odd.expires = _future()
    eng.save("test")
    from pdg.engine_common import delegation_text, live_delegations
    (row,) = live_delegations([odd.model_dump(mode="json")], dt.datetime.now(dt.UTC), humans=["Ana"])
    assert delegation_text(row).endswith("authorizes nothing: Wei is no longer a named human"), delegation_text(row)
    assert cfg is not None
    near.expires = (dt.datetime.now(dt.UTC) - dt.timedelta(days=2)).isoformat()
    later.expires = narrow.expires = _past()
    eng.save("test")
    with pytest.raises(EngineError, match=rf"delegation {narrow.id} expired at .*; ask Wei to renew it"):
        eng.decide(GATE, "approved", AGENT, "Too late.", on_behalf_of="Wei")
