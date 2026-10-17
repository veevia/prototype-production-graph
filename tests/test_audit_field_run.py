"""Follow-ups from pdg's first field run (2026-09-28). A side chat ran a real project while the main session read the
run's ledger, task packets and escalation reports. Each test reproduces one finding and fails without its fix."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import shlex
from pathlib import Path

import pytest

from pdg.cli import main
from pdg.context import NodeContext
from pdg.engine import Engine, EngineError
from pdg.executors import ScriptedExecutor
from pdg.gating import human_record
from pdg.models import NodeStatus
from pdg.util import PKG_ROOT

from .conftest import copy_example

AWKWARD = "a project + its folder"          # spaces and a plus sign, like the field run's folder
INTAKE, PROBLEM, REQS = "n01_context_intake", "n03_problem_definition", "n04_requirements"
IA, UX, VIS = "n07_experience_architecture", "n08_interaction_design", "n09_visual_system"
AGENT = "agent:orchestrator"


def _future(days: int = 1) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)).isoformat()


def _packet(eng: Engine, nid: str) -> dict:
    return json.loads((eng.project.root / ".pdg" / "tasks" / f"{nid}-a{eng.rt(nid).attempt}.json").read_text())


def _waiting(eng: Engine, status: NodeStatus) -> list[str]:
    return [n for n in eng.idx.nodes if eng.rt(n).status == status]


def _drive(eng: Engine, stop, hold: frozenset[str] = frozenset(), actor: str = "Wei", on_behalf_of: str | None = None,
           rounds: int = 80) -> None:
    """Play every agent from its task packet with the example's fixtures, and decide every gate not in `hold` as
    `actor`, until `stop(eng)` holds."""
    agents = ScriptedExecutor(eng.project.root / "fixtures")
    for _ in range(rounds):
        eng.run(max_steps=100)
        if stop(eng):
            return
        agent_nodes = _waiting(eng, NodeStatus.WAITING_AGENT)
        gates = [n for n in _waiting(eng, NodeStatus.WAITING_HUMAN) if n not in hold]
        assert agent_nodes or gates, f"stuck at {eng.state.runtime.status.value}"
        for nid in agent_nodes:
            packet, rt = _packet(eng, nid), eng.rt(nid)
            work = eng.project.root / "work" / nid / f"a{rt.attempt}"
            result = agents.execute(NodeContext(eng, eng.node(nid), rt.attempt, work, packet["token"], ""))
            asked = {o["key"] for o in packet["outputs"]}
            eng.submit(nid, {k: v for k, v in result.outputs.items() if k in asked}, packet["token"],
                       f"agent:{packet['agent']}")
        for nid in gates:
            if nid == "n18_final_verification" and on_behalf_of:
                eng.decide(nid, eng.node(nid).human_review.dry_run_decision, on_behalf_of, f"test decision at {nid}")
            else:
                eng.decide(nid, eng.node(nid).human_review.dry_run_decision, actor, f"test decision at {nid}",
                           on_behalf_of=on_behalf_of)
    raise AssertionError("the stop condition was never reached")


# ------------------------------------------------------------------------------------------------ W1, the rest of it
def test_a_node_escalation_report_prints_an_unblock_command_that_pastes_into_a_shell(tmp_path):
    """The report's command used the project path relative to wherever pdg ran, unquoted: with the field run's folder
    name it split into five words."""
    project = copy_example(tmp_path / AWKWARD, dry_run=False)
    eng = Engine(project)
    eng.run(max_steps=1)
    eng._escalate(eng.node(INTAKE), "a test escalation", ["what failed"])
    report = (project / eng.state.runtime.escalations[-1].report).read_text()
    command = report.split("```bash\n")[1].split("\n```")[0]
    assert shlex.split(command)[:6] == ["python", "-m", "pdg", "unblock", str(eng.project.root), INTAKE]


def test_a_run_escalation_report_prints_the_quoted_commands_that_resolve_it(tmp_path, fast_browser):
    project = copy_example(tmp_path / AWKWARD)
    eng = Engine(project)
    eng.run(max_steps=6)
    cfg = project / "pdg.project.yaml"
    cfg.write_text(cfg.read_text() + "\n# a mid-run edit\n")
    eng.run(max_steps=3)
    esc = next(e for e in eng.state.runtime.escalations if e.open and e.node == "run")
    report = (project / esc.report).read_text()
    block = report.split("```bash\n")[1].split("\n```")[0]
    commands = [shlex.split(line) for line in block.splitlines() if line.strip() and not line.startswith("#")]
    assert {c[3] for c in commands} >= {"accept-config", "unblock"}
    assert all(c[:3] == ["python", "-m", "pdg"] and c[4] == str(eng.project.root) for c in commands)


# ------------------------------------------------------------------------------------------------ ignored section edits
def test_submit_says_which_edits_to_another_writers_section_were_not_applied(tmp_path, capsys):
    """The field run's N07 edited N08's section. The engine ignored it and wrote only a ledger event, so the agent
    learned of it only by grepping the ledger."""
    project = copy_example(tmp_path / AWKWARD, dry_run=False)
    eng = Engine(project)
    _drive(eng, lambda e: e.rt(REQS).status == NodeStatus.WAITING_AGENT)
    packet = _packet(eng, REQS)
    work = project / "work" / REQS / f"a{eng.rt(REQS).attempt}"
    work.mkdir(parents=True, exist_ok=True)
    fx = project / "fixtures" / REQS / "attempt-1"
    (work / "requirements.json").write_text((fx / "requirements.json").read_text())
    (work / "product.md").write_text((fx / "product.md").read_text() + "\n## Scope\n\nN04 widens the scope to every lot.\n")
    code = main(["submit", str(project), REQS, "--token", packet["token"], "--actor", f"agent:{packet['agent']}",
                 "--output", "requirements=requirements.json", "--output", "product_md=product.md"])
    out = capsys.readouterr().out
    assert code == 0, out
    note = next(line for line in out.splitlines() if "not applied" in line)
    assert "product.md" in note and "Scope" in note and "n05_scope_success" in note
    assert "widens the scope" not in (project / "controls" / "product.md").read_text()


# ------------------------------------------------------------------------------------------------ the cascade
def _cascade(tmp_path: Path) -> Engine:
    """The field run's cascade in miniature: gates approved through N09, then a named human's change request on the
    experience document re-opens N07, and whatever N07 changes makes N08 and N09 run again."""
    project = copy_example(tmp_path / AWKWARD, dry_run=False)
    eng = Engine(project)
    _drive(eng, lambda e: e.rt(VIS).status == NodeStatus.WAITING_HUMAN and e.rt(UX).status == NodeStatus.PASSED,
           hold=frozenset({VIS}))
    eng.decide(VIS, "approved", "Wei", "The canon, unchanged.")
    eng.change_request("experience", "The case route names a record only a scenario creates.", "Wei", writer=IA)
    eng.run(max_steps=100)
    assert eng.rt(IA).status == NodeStatus.WAITING_AGENT and eng.rt(IA).attempt == 2
    return eng


def _submit_ia_change(eng: Engine) -> None:
    """N07's second attempt changes one flow step and adds a line to its own User flows section."""
    project, packet = eng.project.root, _packet(eng, IA)
    work = project / "work" / IA / f"a{eng.rt(IA).attempt}"
    work.mkdir(parents=True, exist_ok=True)
    exp = json.loads((project / "fixtures" / IA / "attempt-1" / "experience.json").read_text())
    exp["flows"][0]["steps"][0]["action"] += " (the seeded lot)"
    (work / "experience.json").write_text(json.dumps(exp))
    md = (project / "controls" / "experience.md").read_text()      # the current document; only N07's sections change
    assert "## User flows\n" in md
    (work / "experience.md").write_text(md.replace("## User flows\n", "## User flows\n\nF-02 ends on the seeded lot.\n", 1))
    res = eng.submit(IA, {"experience": "experience.json", "experience_md": "experience.md"}, packet["token"],
                     f"agent:{packet['agent']}")
    assert not res["failures"], res["failures"]


def _resubmit_last_outputs(eng: Engine, nid: str) -> None:
    """What the field run's agent did for a node whose own work needed no change: submit its last passed outputs
    again, taking each control document fresh from controls/ (other writers' sections may have moved on)."""
    project, packet = eng.project.root, _packet(eng, nid)
    last = {a.key: a.path for a in eng.state.artifacts.values() if a.node == nid and a.current}
    work = project / "work" / nid / f"a{eng.rt(nid).attempt}"
    work.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for o in packet["outputs"]:
        if o["kind"] == "control":
            (work / f"{o['doc']}.md").write_text((project / "controls" / f"{o['doc']}.md").read_text())
            outputs[o["key"]] = f"{o['doc']}.md"
        elif o["key"] in last:
            outputs[o["key"]] = str(project / last[o["key"]])
    res = eng.submit(nid, outputs, packet["token"], f"agent:{packet['agent']}")
    assert not res["failures"], res["failures"]


def test_a_reissued_node_packet_says_why_it_runs_again_what_changed_and_where_its_last_outputs_are(tmp_path):
    """After the field run's change request, N08's second packet gave no reason, no changed input and no pointer to its
    passed outputs: only N07, the request's target, was told anything."""
    eng = _cascade(tmp_path)
    assert eng.rt(UX).passed_controls.get("experience")          # a pass records the control versions it saw
    assert "CR-001" in _packet(eng, IA)["rerun"]["reason"]
    _submit_ia_change(eng)
    eng.run(max_steps=100)
    assert eng.rt(UX).status == NodeStatus.WAITING_AGENT and eng.rt(UX).attempt == 2
    rerun = _packet(eng, UX)["rerun"]
    assert "CR-001" in rerun["reason"] and IA in rerun["reason"]
    changed = {c["input"]: c for c in rerun["changed_inputs"]}
    assert set(changed) >= {"control:experience", "artifact:experience"}
    assert any("F-02 ends on the seeded lot." in line for line in changed["control:experience"]["diff"])
    assert rerun["last_passed"]["attempt"] == 1
    assert rerun["last_passed"]["outputs"]["interactions"] == f"work/{UX}/a1/interactions.json"
    assert rerun["last_passed"]["outputs"]["experience_md"] == f"work/{UX}/a1/experience_md.md"   # a key N07 shares
    md = (eng.project.root / ".pdg" / "tasks" / f"{UX}-a2.md").read_text()
    why = md.split("## Why this attempt")[1].split("\n## ")[0]
    assert "CR-001" in why and "+F-02 ends on the seeded lot." in why and f"work/{UX}/a1/interactions.json" in why


def test_a_gate_reasked_with_byte_identical_outputs_says_so_and_names_the_upstream_change(tmp_path, capsys):
    """vpg #43 and the field run: after a cascade the gate asked again for a visual system byte-identical to the one
    approved minutes earlier, and nothing said so, or said why it was asking."""
    eng = _cascade(tmp_path)
    _submit_ia_change(eng)
    for _ in range(4):
        eng.run(max_steps=100)
        if eng.rt(VIS).status == NodeStatus.WAITING_HUMAN:
            break
        for nid in _waiting(eng, NodeStatus.WAITING_AGENT):
            _resubmit_last_outputs(eng, nid)
    assert eng.rt(VIS).status == NodeStatus.WAITING_HUMAN and eng.rt(VIS).attempt == 2
    asked = [e for e in eng.ledger.events("awaiting_human") if e["data"]["node"] == VIS][-1]["data"]
    assert asked["unchanged_since"]["actor"] == "Wei" and asked["changed_outputs"] == []
    assert "CR-001" in asked["rerun_reason"]
    assert main(["status", str(eng.project.root)]) == 0
    line = next(ln for ln in capsys.readouterr().out.splitlines() if VIS in ln and "byte-identical" in ln)
    assert "Wei" in line and "CR-001" in line


def test_a_first_time_gate_carries_no_reconfirmation_note(tmp_path):
    project = copy_example(tmp_path / "p", dry_run=False)
    eng = Engine(project, executor=ScriptedExecutor(project / "fixtures"))
    eng.run(max_steps=100)
    assert eng.rt(PROBLEM).status == NodeStatus.WAITING_HUMAN
    asked = [e for e in eng.ledger.events("awaiting_human") if e["data"]["node"] == PROBLEM][-1]["data"]
    assert asked.get("unchanged_since") is None and not eng.rt(PROBLEM).gate_note


# ------------------------------------------------------------------------------------------------ delegation
def _at_gate(tmp_path: Path) -> tuple[Path, Engine]:
    project = copy_example(tmp_path / "p", dry_run=False)
    eng = Engine(project, executor=ScriptedExecutor(project / "fixtures"))
    eng.run(max_steps=100)
    assert eng.rt(PROBLEM).status == NodeStatus.WAITING_HUMAN
    return project, eng


def test_a_delegation_grant_records_who_typed_it_and_where_the_words_came_from(tmp_path):
    """The field run's agent typed `pdg delegate --by Wei` from Wei's chat words; the record showed only "by Wei"."""
    _, eng = _at_gate(tmp_path)
    grant = eng.delegate("Wei", AGENT, "Don't stop the loops until you finish.", ["decide"], [], _future(),
                         except_nodes=["n18_final_verification"],
                         recorded_by=AGENT, source="Wei's chat message, 2026-09-27 19:09 CDT")
    assert grant.recorded_by == AGENT and grant.source.startswith("Wei's chat")
    row = next(r for r in human_record(eng)[0] if grant.id in r)
    assert f"typed by {AGENT}" in row and "Wei's chat message" in row
    unstated = eng.delegate("Wei", AGENT, "Also approve the scope gate.", ["decide"], [], _future(),
                            except_nodes=["n18_final_verification"])
    assert any(unstated.id in r and "who typed it is not recorded" in r for r in human_record(eng)[0])
    with pytest.raises(EngineError, match="recorded_by"):
        eng.delegate("Wei", AGENT, "Approve it.", ["decide"], [], _future(), recorded_by="Somebody")


def test_the_delegate_command_requires_whoever_types_the_grant_to_say_who_they_are(tmp_path):
    project, _ = _at_gate(tmp_path)
    base = ["delegate", str(project), "--by", "Wei", "--agent", AGENT, "--instruction", "Approve the problem gate.",
            "--scope", "decide", "--expires", _future()]
    with pytest.raises(SystemExit):
        main(base)
    assert main(base + ["--except-nodes", "n18_final_verification", "--recorded-by", AGENT,
                        "--source", "chat, 2026-09-27"]) == 0
    grant = json.loads((project / ".pdg" / "state.json").read_text())["history"]["delegations"][-1]
    assert grant["recorded_by"] == AGENT and grant["source"] == "chat, 2026-09-27"


def test_a_delegation_stops_authorizing_once_its_grantor_is_no_longer_a_named_human(tmp_path):
    _, eng = _at_gate(tmp_path)
    eng.delegate("Wei", AGENT, "Approve the problem gate.", ["decide"], [], _future(),
                 recorded_by=AGENT, source="chat", except_nodes=["n18_final_verification"])
    eng.humans = ["Someone Else"]            # the project's humans list changed and the change was accepted
    with pytest.raises(EngineError, match="not a named human"):
        eng.decide(PROBLEM, "approved", AGENT, "Still aligned.", on_behalf_of="Wei")
    assert eng.rt(PROBLEM).status == NodeStatus.WAITING_HUMAN


def test_an_intake_gap_waived_under_a_delegation_is_attributed_to_it(project):
    """`unblock --waive` under a delegation recorded the waiver with the agent's name only, so it was missing from the
    human record and from what the release summary counts under the grant, while N02 honours any waiver."""
    from pdg.gating import _delegation_lines

    from .test_audit_coverage import EVIDENCE, FIXTURES, _PendingFor, _submit_fixture
    eng = Engine(project, executor=_PendingFor(project / "fixtures", {EVIDENCE}))
    eng.run(max_steps=100)
    evidence = json.loads((FIXTURES / EVIDENCE / "attempt-1" / "evidence.json").read_text())
    evidence["open_questions"][0]["blocking"] = True
    assert _submit_fixture(eng, EVIDENCE, {"evidence.json": evidence})["status"] == "BLOCKED"
    grant = eng.delegate("Wei", AGENT, "Keep the run moving past the brand-guide gap.", ["unblock"], [], _future(),
                         recorded_by=AGENT, source="chat")
    eng.unblock(EVIDENCE, AGENT, note="the brand guide arrives with the pilot", waive=["G-DESIGN-AUTHORITY"],
                on_behalf_of="Wei")
    waived = list(eng.ledger.events("gap_waived"))[-1]["data"]
    assert waived["by"] == AGENT and waived["on_behalf_of"] == "Wei" and waived["delegation"] == grant.id
    assert any("intake gap waived G-DESIGN-AUTHORITY" in r and f"delegated by Wei ({grant.id})" in r
               for r in human_record(eng)[0])
    assert "1 intake gap waiver" in _delegation_lines(eng)[0]


def test_a_delegated_real_run_is_never_called_a_dry_run_and_its_summary_lists_the_delegation(tmp_path, fast_browser):
    """Delegated approvals are recorded as not human, and the release summary's TL;DR called any run with a non-human
    approval "a DRY RUN: approvals were scripted", which a delegated real run is not."""
    project = copy_example(tmp_path / "real", dry_run=False)
    eng = Engine(project)
    eng.run(max_steps=1)
    grant = eng.delegate("Wei", AGENT, "Run it end to end; don't stop at the gates.", ["decide"], [], _future(),
                         except_nodes=["n18_final_verification"],
                         recorded_by=AGENT, source="Wei's chat message")
    _drive(eng, lambda e: e.state.runtime.status.value in ("RUN_PASS", "BLOCKED"), actor=AGENT, on_behalf_of="Wei")
    assert eng.state.runtime.status.value == "RUN_PASS", [e.reason for e in eng.state.runtime.escalations]
    summary = next(project.glob("work/n18_final_verification/a*/release-summary.md")).read_text()
    tldr = summary.split("> **TL;DR:**")[1].split("\n")[0]
    assert "DRY RUN" not in summary
    assert "on behalf of Wei" in tldr and grant.id in tldr and "not by Wei" in tldr
    section = summary.split("## Delegations")[1].split("\n## ")[0]
    assert grant.id in section and f"typed by {AGENT}" in section and "Run it end to end" in section
    assert "gate decisions" in section
    assert "## Review findings the interpreter answered" in summary                   # W22's section, listed at release
    assert "## Reviewer severities the last gate kept advisory" in summary            # W25's record, listed at release


# ------------------------------------------------------------------------------------------------ the package review
def test_the_package_review_counts_a_real_projects_files_as_that_projects_not_the_packages(tmp_path):
    """R28 of loop/review.py failed during the field run: the run's own files (task packets, checkpoints) mention
    `python -m pdg`, so the scope check took them for the package loop writing outside its scope."""
    reviewer = PKG_ROOT / "loop" / "review.py"
    if not reviewer.is_file():
        pytest.skip("the historical private-workspace build reviewer is not distributed")
    spec = importlib.util.spec_from_file_location("pdg_review", reviewer)
    review = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(review)
    proj = tmp_path / "hub" / "a run + x"
    (proj / ".pdg" / "tasks").mkdir(parents=True)
    (proj / "pdg.project.yaml").write_text("name: x\n")
    assert review.pdg_project_of(proj / ".pdg" / "tasks" / "n01-a1.md", tmp_path) == proj
    assert review.pdg_project_of(proj / "pdg.project.yaml", tmp_path) == proj
    assert review.pdg_project_of(tmp_path / "hub" / "notes.md", tmp_path) is None


# ------------------------------------------------------------------------------------------------ the side chat's W9–W11
def test_a_review_can_say_who_reviewed_and_the_release_summary_lists_it(project, fast_browser):
    """W9: a review could not record who performed it, so a self-review and an independent one looked the same to the
    gate and the release summary. Independence stays asserted, not verified; the summary says so."""
    from pdg.evaluation import load_rubrics, merge_review
    from pdg.gating import _reviewer_lines
    from pdg.graph import load_workflow
    node = next(n for n in load_workflow().nodes if n.id == "n13_quality_review")
    rubrics = load_rubrics()
    dims = [d for r in node.evaluation for d in rubrics[r]["dimensions"] if d["check"]["type"] == "review"]
    states = {d["rule"]: "adopted" for d in dims if d.get("rule")}
    scores = [{"id": d["id"], "score": 5, "evidence": "fine"} for d in dims]
    rec = merge_review(node, 1, 1, {}, {"dimensions": scores, "summary": "s", "independent": True,
                                        "reviewer": "a design reviewer in its own context"}, rubrics, states, 4.0)
    assert rec.reviewer == "a design reviewer in its own context" and rec.independent is True
    eng = Engine(project)
    eng.run(max_steps=400)
    summary = next(project.glob("work/n18_final_verification/a*/release-summary.md")).read_text()
    section = summary.split("## Who reviewed")[1].split("\n## ")[0]
    assert "n13_quality_review" in section and "reviewer not stated" in section     # the fixtures name no reviewer
    review = next(r for r in reversed(eng.state.evaluation.reviews) if r.node == "n13_quality_review")
    review.reviewer, review.independent = "the agent that built the prototype", False
    assert any("n13_quality_review" in ln and "SELF-REVIEW" in ln for ln in _reviewer_lines(eng))


def test_cnt_volume_counts_the_list_a_dataset_names_and_says_what_it_counted(tmp_path):
    """W10: the check counted the longest list in a dataset file without saying which, so 31 signals passed "≥ 12
    records" although only 10 were of the type the scenarios needed."""
    from pdg.tools import content

    from .conftest import FakeCtx
    root = tmp_path / "prototype"
    root.mkdir()
    (root / "index.html").write_text("<html><body><main><h1>Feed</h1><p>Synthetic data</p></main></body></html>")
    signals = ([{"id": f"R-{i:02d}", "type": "regulatory"} for i in range(21)]
               + [{"id": f"S-{i:02d}", "type": "scientific"} for i in range(10)])
    (root / "seed.json").write_text(json.dumps({"signals": signals, "topics": [{"id": "t1"}, {"id": "t2"}]}))
    (root / "build-manifest.json").write_text(json.dumps({"entry": "index.html"}))

    def volume(records: int, **extra):
        doc = {"datasets": [{"path": "seed.json", "records": records, "provenance": "synthetic",
                             "label_shown_in_ui": True, **extra}], "copy_deck": "copy.md", "edge_cases": []}
        ctx = FakeCtx({"content": doc}, thresholds={"content": {"min_records": 12}}, work=tmp_path)
        ctx.output = lambda key: root if key == "prototype" else None
        return content.check(ctx).dimensions["CNT-VOLUME"]

    longest = volume(31)
    assert longest.passed and "signals, the longest of 2 lists: 31 records" in longest.evidence
    scoped = volume(10, primary="signals[type=scientific]")
    assert not scoped.passed and "signals[type=scientific]: 10 records" in scoped.evidence
    assert not volume(0, primary="cases").passed                              # a list that does not exist counts 0


def test_tec_unit_fails_when_the_unit_tests_read_another_dataset_than_the_build_embeds(tmp_path):
    """W11: the build embedded data/seed.json while its unit tests read src/data/seed.json, so TEC-UNIT stayed green
    on a dataset the build did not ship. A build now declares which dataset its tests read."""
    from pdg.tools import _node, feasibility

    from .conftest import FakeCtx
    if not _node.node_bin():
        pytest.skip("node is not on PATH")
    root = tmp_path / "artifact"
    root.mkdir()
    (root / "index.html").write_text("<main>Prototype</main>")
    (root / "domain.test.js").write_text("import test from 'node:test';\nimport assert from 'node:assert/strict';\n"
                                         "test('adds', () => assert.equal(1 + 1, 2));\n")

    def unit(**declared):
        (root / "build-manifest.json").write_text(json.dumps({
            "entry": "index.html", "stack": ["html", "js"], "files": {}, "screens": {}, "unit_tests": "domain.test.js",
            "dataset": "data/seed.json", **declared}))
        ctx = FakeCtx({}, work=tmp_path)
        ctx.artifact = lambda key: root if key == "prototype" else None
        ctx.control_text = lambda doc: "\n".join(f"## {s}" for s in ctx.thresholds["feasibility"]["devdoc_sections"])
        return feasibility.check(ctx).dimensions["TEC-UNIT"]

    other = unit(unit_tests_dataset="src/data/seed.json")
    assert not other.passed and "read src/data/seed.json, but the build embeds data/seed.json" in other.evidence
    assert unit(unit_tests_dataset="./data/seed.json").passed
    assert "read no dataset" in unit(unit_tests_dataset="none").evidence
    unstated = unit()
    assert unstated.passed and "not declared" in unstated.evidence


def test_a_reviewers_severity_survives_when_its_finding_does_not_block():
    """W12: a finding on a dimension that does not block (a SHOULD, a rule not yet enforced, a passing dimension) was
    stored as P4, so the diagnoser and the release evidence showed a reviewer's P2 as a nit. P4 still decides that it
    does not block (the gate and release count P1–P3 as blocking); the reviewer's own severity is kept beside it."""
    from pdg.evaluation import load_rubrics, merge_review
    from pdg.graph import load_workflow
    node = next(n for n in load_workflow().nodes if n.id == "n15_feasibility_review")
    rubrics = load_rubrics()
    dims = [d for r in node.evaluation for d in rubrics[r]["dimensions"] if d["check"]["type"] == "review"]
    should = next(d for d in dims if d["level"] == "SHOULD")
    passing = next(d for d in dims if d["id"] != should["id"])
    states = {d["rule"]: "adopted" for d in dims if d.get("rule")}
    scores = [{"id": d["id"], "score": 2 if d is should else 5, "evidence": "e"} for d in dims]
    findings = [{"dimension": should["id"], "severity": "P2", "message": "the build logs before it checks the copy",
                 "location": "app.js:951"},
                {"dimension": passing["id"], "severity": "P3", "message": "a note on a passing dimension", "location": "x"}]
    rec = merge_review(node, 1, 1, {}, {"dimensions": scores, "findings": findings, "summary": "s"}, rubrics, states, 4.0)
    stored = {f.dimension: f for f in rec.findings}
    assert (stored[should["id"]].severity, stored[should["id"]].blocking, stored[should["id"]].reported_severity) == ("P4", False, "P2")
    assert (stored[passing["id"]].severity, stored[passing["id"]].reported_severity) == ("P4", "P3")


def test_quoted_words_with_line_breaks_stay_inside_one_release_summary_item(tmp_path):
    """A human's chat words often span lines; pasted raw, they would break the Delegations list."""
    from pdg.gating import _delegation_lines
    _, eng = _at_gate(tmp_path)
    eng.delegate("Wei", AGENT, "Don't stop the loops.\n\nFinish the design\nand the prototype.", ["decide"], [],
                 _future(), recorded_by=AGENT, source="chat,\n19:09 CDT", except_nodes=["n18_final_verification"])
    (line,) = _delegation_lines(eng)
    assert "\n" not in line and "Don't stop the loops. Finish the design and the prototype." in line
    assert "from chat, 19:09 CDT" in line


# ------------------------------------------------------------------------------------------------ the side chat's W14–W15
def test_two_findings_of_one_dimension_on_one_screen_get_two_signatures_when_they_name_their_element():
    """W14: the location convention is `screen:viewport`, so two findings of one dimension on one screen shared one
    signature: one defect covered both, and one of them still present kept every such defect open."""
    from pdg.evaluation import load_rubrics, merge_review
    from pdg.graph import load_workflow
    node = next(n for n in load_workflow().nodes if n.id == "n13_quality_review")
    rubrics = load_rubrics()
    dims = [d for r in node.evaluation for d in rubrics[r]["dimensions"] if d["check"]["type"] == "review"]
    states = {d["rule"]: "adopted" for d in dims if d.get("rule")}
    failing = dims[0]["id"]
    scores = [{"id": d["id"], "score": 2 if d["id"] == failing else 5, "evidence": "e"} for d in dims]
    findings = [{"dimension": failing, "severity": "P2", "message": "the due list stops at six", "location": "home:1280",
                 "element": "due-list"},
                {"dimension": failing, "severity": "P2", "message": "the only example contradicts its panel",
                 "location": "home:1280", "element": "ahead-list"},
                {"dimension": failing, "severity": "P3", "message": "no element named", "location": "feed:1280"}]
    rec = merge_review(node, 1, 1, {}, {"dimensions": scores, "findings": findings, "summary": "s"}, rubrics, states, 4.0)
    sigs = sorted(f.signature for f in rec.findings if f.dimension == failing)
    assert sigs == sorted([f"{failing}@home:1280#due-list", f"{failing}@home:1280#ahead-list", f"{failing}@feed:1280"])


def test_a_reissued_node_is_told_only_the_targets_upstream_of_it(project, fast_browser):
    """W15: after a rework of N08 and N11, N10's packet said it re-ran because "upstream n08, n11 re-opened", but N11 is
    downstream of N10."""
    eng = Engine(project)
    eng.run(max_steps=400)
    assert eng.state.runtime.status.value == "RUN_PASS"
    eng.invalidate([UX, "n11_prototype_development"], "E35, E38 from n17_targeted_rework (rework)")
    reason = eng.rt("n10_prototype_planning").rerun_reason
    assert UX in reason and "n11_prototype_development" not in reason


def test_a_pass_recorded_before_control_versions_were_kept_still_lists_the_changed_control(tmp_path):
    """W15: N10 last passed before pdg recorded the control versions a pass saw, so its re-issued packet left out
    `control:experience` v3 → v4. The ledger orders every install and pass, so the versions are recovered from it."""
    eng = _cascade(tmp_path)
    rt = eng.rt(UX)
    rt.passed_controls, rt.passed_attempt = {}, 0            # as saved by an older pdg
    _submit_ia_change(eng)
    eng.run(max_steps=100)
    changed = {c["input"]: c for c in _packet(eng, UX)["rerun"]["changed_inputs"]}
    assert "control:experience" in changed
    assert any("F-02 ends on the seeded lot." in line for line in changed["control:experience"]["diff"])


# ------------------------------------------------------------------------------------------------ the side chat's W16–W17
def test_an_attempt_that_passes_its_checks_does_not_report_the_failures_before_it(tmp_path):
    """W16: N10's attempt 4 passed every check and went to its gate, but `submit` printed attempt 3's failures and one
    attempt fewer left: the failures and the streak were cleared only when the gate decided."""
    from pdg.context import NodeResult

    class Pending(ScriptedExecutor):                       # the problem node always waits for a real submission
        def execute(self, ctx):
            return NodeResult(pending=True) if ctx.node.id == PROBLEM else super().execute(ctx)

    project = copy_example(tmp_path / "p", dry_run=False)
    eng = Engine(project, executor=Pending(project / "fixtures"))
    eng.run(max_steps=100)
    fx = project / "fixtures" / PROBLEM / "attempt-1"
    work = project / "work" / PROBLEM / f"a{eng.rt(PROBLEM).attempt}"
    work.mkdir(parents=True, exist_ok=True)
    frame = json.loads((fx / "problem.json").read_text())
    frame["top_pain"]["evidence_ids"] = ["E-999"]              # schema-valid, fails PRB-EVIDENCE: a quality failure
    (work / "problem.json").write_text(json.dumps(frame))
    bad = eng.submit(PROBLEM, {"problem": "problem.json", "product_md": str(fx / "product.md")}, eng.rt(PROBLEM).token,
                     "agent:product-strategist")
    assert bad["failures"] and eng.rt(PROBLEM).streak == 1
    eng.run(max_steps=100)
    good = eng.submit(PROBLEM, {"problem": str(fx / "problem.json"), "product_md": str(fx / "product.md")},
                      eng.rt(PROBLEM).token, "agent:product-strategist")
    assert eng.rt(PROBLEM).status == NodeStatus.WAITING_HUMAN
    assert good["failures"] == [] and eng.rt(PROBLEM).streak == 0


def test_the_browser_report_says_its_screenshots_hide_scrollbars(tmp_path):
    """W19: headless Chromium hides scrollbars by default, so no screenshot shows a scroll cue, and a reviewer judging one
    from them cannot tell. Showing them would change the overflow and reflow measurements mid-run, so the report says so."""
    pytest.importorskip("playwright")
    from .test_audit_browser import _run, _write_html
    entry = _write_html(tmp_path / "one.html", '<section data-screen="one"><h1>One</h1></section>',
                        "<style> body { font-family: system-ui, sans-serif; color: #111; background: #fff; } </style>")
    rep, res = _run(entry, tmp_path / "out", screens=[{"id": "one", "route": ""}])
    assert "hidden" in rep["scrollbars"]
    assert any("scrollbars" in m and "hidden" in m for m in res.messages)


# ------------------------------------------------------------------------------------------------ the side chat's W26–W27
def test_a_lesson_may_cite_a_ledger_event_that_exists(project, fast_browser):
    """W27: N19's instructions accept ledger events as a lesson's evidence, but its checker rejected them."""
    from pdg.tools.learning import check_lessons

    from .conftest import FakeCtx
    eng = Engine(project)
    eng.run(max_steps=20)
    last = max(e["seq"] for e in eng.ledger.events())

    def evidence(ref: str):
        ctx = FakeCtx({"lessons": {"summary": "s", "lessons": [{
            "id": "L-1", "statement": "An unblock that re-opens a spent rework edge needs its reason on record.",
            "scope": "project_specific", "evidence_class": "inferred", "evidence": [ref]}]}}, state=eng.state)
        ctx.engine = eng
        return check_lessons(ctx).dimensions["LRN-EVIDENCE"]

    assert evidence(f"ledger:{last}").passed
    assert not evidence(f"ledger:{last + 1000}").passed


@pytest.mark.parametrize("prompt,field", [
    ("n11_prototype_development", "unit_tests_dataset"), ("n12_content_data", "`primary`"),
    ("n13_quality_review", "`element`"), ("n13_quality_review", "independent: true"),
    ("n14_validation", "independent: true"), ("n15_feasibility_review", "independent: true"),
    ("n16_feedback_diagnosis", "answered_findings"), ("n16_feedback_diagnosis", "from_findings"),
])
def test_each_prompt_names_the_fields_its_node_must_write(prompt, field):
    """Backlog B-04: fields added during the first field run were used only because the inbox explained them; no prompt
    or packet named them. Each node's prompt now does."""
    from pdg.util import PKG_ROOT
    assert field in (PKG_ROOT / "prompts" / f"{prompt}.md").read_text()
