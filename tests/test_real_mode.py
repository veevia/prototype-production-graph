"""The real (non-dry-run) path, end to end: every agent step goes through a task packet and `submit`, and every gate is
decided by a named human. The fixtures play the agents: each one reads its packet, produces the files the packet asks
for, and submits them with the packet's token. Nothing is scripted inside the engine."""

from __future__ import annotations

import json

from pdg.context import NodeContext
from pdg.engine import Engine
from pdg.executors import ScriptedExecutor
from pdg.models import NodeKind, NodeStatus
from pdg.provenance import Ledger

from .conftest import copy_example


def _drive(eng: Engine, rounds: int = 200) -> tuple[list[str], list[str]]:
    agents = ScriptedExecutor(eng.project.root / "fixtures")
    tasks = eng.project.root / ".pdg" / "tasks"
    submitted, decided = [], []
    for _ in range(rounds):
        eng.run(max_steps=100)
        if eng.state.runtime.status.value in ("RUN_PASS", "BLOCKED"):
            break
        waiting_agent = [n for n in eng.idx.nodes if eng.rt(n).status == NodeStatus.WAITING_AGENT]
        waiting_human = [n for n in eng.idx.nodes if eng.rt(n).status == NodeStatus.WAITING_HUMAN]
        for nid in waiting_agent:
            rt = eng.rt(nid)
            packet = json.loads((tasks / f"{nid}-a{rt.attempt}.json").read_text())
            assert (tasks / f"{nid}-a{rt.attempt}.md").read_text().count(packet["token"]) >= 1
            work = eng.project.root / "work" / nid / f"a{rt.attempt}"
            result = agents.execute(NodeContext(eng, eng.node(nid), rt.attempt, work, packet["token"], ""))
            asked = {o["key"] for o in packet["outputs"]}
            outputs = {k: v for k, v in result.outputs.items() if k in asked}   # only what the packet asks for
            eng.submit(nid, outputs, packet["token"], f"agent:{packet['agent']}")
            submitted.append(f"{nid}/a{rt.attempt}")
        for nid in waiting_human:
            node = eng.node(nid)
            eng.decide(nid, node.human_review.dry_run_decision, "Wei", f"test decision at {nid} (a named human)")
            decided.append(nid)
        if not waiting_agent and not waiting_human:
            break
    return submitted, decided


def test_a_real_project_runs_every_node_on_task_packets_and_named_human_gates(tmp_path, fast_browser):
    project = copy_example(tmp_path / "real", dry_run=False)
    eng = Engine(project)
    submitted, decided = _drive(eng)
    st = eng.state
    assert st.runtime.status.value == "RUN_PASS", [e.reason for e in st.runtime.escalations]
    agent_nodes = {n.id for n in eng.wf.nodes if n.kind != NodeKind.TOOL}
    assert agent_nodes <= {s.split("/")[0] for s in submitted}             # every agent step went through a packet
    assert st.runtime.rework_cycles == 1 and st.build.version == 2          # the same story as the dry run
    assert any(s.startswith("n01_context_intake/a2") for s in submitted)    # the intake loop, on packets too
    assert st.history.approvals and all(a.human and a.actor == "Wei" for a in st.history.approvals)
    assert {a.node for a in st.history.approvals} == {n.id for n in eng.wf.nodes if n.human_review.required}
    ok, n, _ = Ledger(project / ".pdg" / "ledger.jsonl", read_only=True).verify()
    assert ok and n > 100
    summary = next(project.glob("work/n18_final_verification/a*/release-summary.md")).read_text()
    assert "DRY RUN" not in summary and "not a human approval" not in summary
    assert "Simulated validation" in summary                                # simulated sessions stay labelled
