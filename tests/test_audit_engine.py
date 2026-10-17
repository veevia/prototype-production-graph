"""Engine audit findings: every tamper blocks the run (F18), an unmeasured MUST is never a pass (F19), and a refused
command changes nothing (F20)."""

from __future__ import annotations

import json
import shutil

import pytest
import yaml

from pdg.engine import Engine, EngineError
from pdg.provenance import Ledger

from .conftest import PKG, copy_example, fake_browser


def _step_until(eng: Engine, done, limit: int = 300) -> None:
    for _ in range(limit):
        if done(eng):
            return
        if not eng.step() and not done(eng):
            raise AssertionError(f"stopped at {eng.state.runtime.status.value} before the condition held")
    raise AssertionError("the condition never held")


def _blocked_because(eng: Engine, text: str) -> bool:
    eng.step()
    return eng.state.runtime.status.value == "BLOCKED" and any(
        text in e.reason or any(text in p for p in _report(eng, e)) for e in eng.state.runtime.escalations if e.open)


def _report(eng: Engine, esc) -> list[str]:
    p = eng.project.root / esc.report
    return p.read_text().splitlines() if p.is_file() else []


def _with_config(project, **cfg):
    path = project / "pdg.project.yaml"
    data = yaml.safe_load(path.read_text())
    data.update(cfg)
    path.write_text(yaml.safe_dump(data))


# ------------------------------------------------------------------------------------------------ F18: tamper detection
def test_editing_a_file_inside_a_directory_artifact_blocks_the_run(project, fast_browser):
    eng = Engine(project)
    _step_until(eng, lambda e: e.state.build.prototype is not None)
    rec = eng.state.artifacts[eng.state.build.prototype.artifact]
    built = project / rec.path
    assert built.is_dir()
    page = next(p for p in sorted(built.rglob("*.html")))
    page.write_text(page.read_text().replace("</body>", "<p>edited after review</p></body>"))
    assert _blocked_because(eng, "was modified after registration")


def test_a_same_size_edit_with_its_time_put_back_is_still_caught(project, fast_browser):
    import os
    eng = Engine(project)
    _step_until(eng, lambda e: e.state.build.prototype is not None)
    rec = eng.state.artifacts[eng.state.build.prototype.artifact]
    page = next(p for p in sorted((project / rec.path).rglob("*.html")))
    assert not eng._integrity_problems()                                  # warms the hash cache
    before = page.stat()
    text = page.read_text()
    page.write_text(text[:-1] + ("X" if text[-1] != "X" else "Y"))       # same size, new bytes
    os.utime(page, ns=(before.st_atime_ns, before.st_mtime_ns))           # `touch -r`: the old modification time
    assert any("was modified after registration" in p for p in eng._integrity_problems())


def test_editing_a_frozen_source_blocks_the_run(project, fast_browser):
    eng = Engine(project)
    _step_until(eng, lambda e: e.state.inputs.frozen)
    src = next(s for s in eng.state.inputs.sources if s.path and (project / s.path).is_file() and s.kind != "brief")
    (project / src.path).write_text((project / src.path).read_text() + "\nA line added after the freeze.\n")
    assert _blocked_because(eng, "a frozen input")


@pytest.mark.parametrize("what", ["rules", "workflow"])
def test_changing_the_projects_rules_or_graph_mid_run_blocks_the_run(project, fast_browser, what):
    if what == "rules":
        shutil.copyfile(PKG / "knowledge" / "rules.json", project / "rules.json")
        _with_config(project, rules="rules.json")
    else:
        shutil.copyfile(PKG / "graph" / "workflow.yaml", project / "workflow.yaml")
        _with_config(project, workflow="workflow.yaml")                   # relative to the project (F31)
    eng = Engine(project)
    for _ in range(3):
        eng.step()
    target = project / ("rules.json" if what == "rules" else "workflow.yaml")
    if what == "rules":
        data = json.loads(target.read_text())
        data["note_added_mid_run"] = "a hand edit"
        target.write_text(json.dumps(data, indent=1))
    else:
        target.write_text(target.read_text().replace("purpose: ", "purpose: (edited) ", 1))
    assert _blocked_because(eng, "changed since the run started")


# ------------------------------------------------------------------------------------------------ F19: unmeasured MUSTs
def test_a_check_that_skips_an_enforced_must_dimension_fails_instead_of_passing(project, monkeypatch):
    import pdg.tools.browser as b

    def skips_axe(ctx):
        res = fake_browser(ctx)
        res.dimensions.pop("A11Y-AXE")                                      # a tool bug: the dimension is never measured
        return res

    monkeypatch.setattr(b, "check", skips_axe)
    eng = Engine(project)
    eng.run(max_steps=400)
    st = eng.state
    assert st.runtime.status.value == "BLOCKED"                             # never RUN_PASS on an unmeasured MUST
    assert not any(g.outcome == "pass" for g in st.evaluation.gates)
    fails = [f for n in ("n13_quality_review",) for f in eng.rt(n).failures]
    assert any("A11Y-AXE" in f and "did not report it" in f for f in fails)
    assert not list(project.glob("work/n18_final_verification/a*/release-summary.md"))


def test_an_advisory_dimension_a_check_skips_does_not_fail_the_attempt():
    from pdg.context import CheckResult
    from pdg.evaluation import load_rubrics, unreported_tool_dims
    from pdg.graph import load_workflow
    wf = load_workflow()
    node = next(n for n in wf.nodes if n.id == "n13_quality_review")
    rubrics = load_rubrics()
    fn = next(d["check"]["fn"] for r in node.evaluation for d in rubrics[r]["dimensions"] if d["id"] == "A11Y-AXE")
    rule = next(d.get("rule") for r in node.evaluation for d in rubrics[r]["dimensions"] if d["id"] == "A11Y-AXE")
    ran = {fn: CheckResult()}                                               # the check ran and reported nothing
    assert any(m.startswith("A11Y-AXE") for m in unreported_tool_dims(node, ran, rubrics, {rule: "adopted"}))
    advisory = unreported_tool_dims(node, ran, rubrics, {rule: "validated"})
    assert not any(m.startswith("A11Y-AXE") for m in advisory)             # advisory: reported, never blocking
    assert unreported_tool_dims(node, {}, rubrics, {rule: "adopted"}) == []   # a check that has not run is no defect


# ------------------------------------------------------------------------------------------------ F20: refusals
def test_a_refused_unblock_changes_nothing(project, fast_browser):
    eng = Engine(project)
    _step_until(eng, lambda e: e.state.controls["product"].version >= 1)
    live = project / "controls" / "product.md"
    live.write_text(live.read_text() + "\nA hand edit.\n")
    eng.step()
    assert eng.state.runtime.status.value == "BLOCKED"
    edited, state, ledger = live.read_bytes(), (project / ".pdg" / "state.json").read_bytes(), \
        (project / ".pdg" / "ledger.jsonl").read_bytes()
    with pytest.raises(EngineError):
        eng.unblock("run", "Wei", note="restore it", restore_controls=True, waive=["G-01"])   # 'run' has no intake gaps
    assert live.read_bytes() == edited                                      # the hand edit is still there …
    assert (project / ".pdg" / "state.json").read_bytes() == state          # … and nothing was saved
    assert (project / ".pdg" / "ledger.jsonl").read_bytes() == ledger       # … or ledgered
    eng.unblock("run", "Wei", note="restore it", restore_controls=True)
    assert b"A hand edit." not in live.read_bytes() and not eng.controls.drift()
    assert Ledger(project / ".pdg" / "ledger.jsonl", read_only=True).verify()[0]


# ------------------------------------------------------------------------------------------------ F16: small false passes
def test_the_release_manifest_hashes_a_nested_manifest_json(tmp_path):
    from pdg.gating import package_manifest
    pkg = tmp_path / "package"
    (pkg / "prototype").mkdir(parents=True)
    (pkg / "prototype" / "manifest.json").write_text('{"name": "Lot Release Workbench"}')   # a web app manifest
    (pkg / "prototype" / "index.html").write_text("<!doctype html>")
    (pkg / "manifest.json").write_text("{}")                                             # the package's own manifest
    assert sorted(package_manifest(pkg)) == ["prototype/index.html", "prototype/manifest.json"]


def test_a_review_score_below_the_pass_mark_fails_even_when_marked_passed():
    from pdg.evaluation import load_rubrics, merge_review
    from pdg.graph import load_workflow
    node = next(n for n in load_workflow().nodes if n.id == "n13_quality_review")
    rubrics = load_rubrics()
    dims = [d for r in node.evaluation for d in rubrics[r]["dimensions"] if d["check"]["type"] == "review"]
    states = {d["rule"]: "adopted" for d in dims if d.get("rule")}
    scores = [{"id": d["id"], "score": 5, "evidence": "fine"} for d in dims]
    for s in scores:
        if s["id"] == "DES-HIERARCHY":
            s.update(score=2, passed=True, evidence="the queue has no clear primary action")
    rec = merge_review(node, 1, 1, {}, {"dimensions": scores, "summary": "s"}, rubrics, states, 4.0)
    hier = next(r for r in rec.dimensions if r.id == "DES-HIERARCHY")
    assert hier.status == "fail" and not rec.passed                        # the score decides, not the flag
    scores[[s["id"] for s in scores].index("DES-HIERARCHY")].update(score=5, passed=False)
    rec = merge_review(node, 1, 1, {}, {"dimensions": scores, "summary": "s"}, rubrics, states, 4.0)
    assert next(r for r in rec.dimensions if r.id == "DES-HIERARCHY").status == "fail"   # an explicit fail always fails


def test_the_release_summary_lists_dimensions_that_were_never_scored(project, fast_browser):
    eng = Engine(project)
    eng.run(max_steps=400)
    summary = next(project.glob("work/n18_final_verification/a*/release-summary.md")).read_text()
    assert "## Dimensions not scored (never counted as a pass)" in summary


# ------------------------------------------------------------------------------------------------ F21, F22: state detail
def test_every_validation_round_is_recorded_and_flags_simulated_sessions(project, fast_browser):
    from pdg.models import Defect
    from pdg.tools.learning import check_lessons
    from .conftest import FakeCtx
    eng = Engine(project)
    eng.run(max_steps=400)
    vf = eng.state.research.validation_findings
    assert vf and all(v.simulated for v in vf) and vf[-1].at_version == eng.state.build.version
    # the learning check then refuses a "verified" lesson whose only evidence is a finding from those sessions
    st = eng.state.model_copy(deep=True)
    st.evaluation.defects.append(Defect(id="D-SIM", signature="VAL-TASKS@queue", dimension="VAL-TASKS", severity="P2",
                                        message="a participant missed the queue filter", evidence="session notes",
                                        traced_node="n14_validation", trace_reason="validation finding",
                                        smallest_fix="f", acceptance_check="a", source_nodes=["n14_validation"]))
    ctx = FakeCtx({"lessons": {"summary": "s", "lessons": [{"id": "L-SIM", "statement": "Reviewers miss the queue filter.",
                                                           "scope": "reusable", "evidence_class": "verified",
                                                           "evidence": ["D-SIM"]}]}}, state=st)
    ctx.engine.rules = eng.rules
    assert not check_lessons(ctx).dimensions["LRN-HONEST"].passed


def test_a_node_redispatched_within_the_second_keeps_the_version_it_installed(project, fast_browser):
    from pdg.models import NodeStatus
    eng = Engine(project)
    _step_until(eng, lambda e: e.rt("n04_requirements").status == NodeStatus.PASSED)
    rec = eng.state.controls["product"]
    last = rec.history[-1]
    assert last.node == "n04_requirements" and last.attempt == eng.rt("n04_requirements").attempt
    rt = eng.rt("n04_requirements")                                         # a rework re-dispatch in the same second,
    rt.attempt, rt.status, rt.started_at = rt.attempt + 1, NodeStatus.RUNNING, last.at   # then the process died
    eng.save("simulated-crash")
    text = (project / "controls" / "product.md").read_text()
    resumed = Engine(project)
    assert resumed.state.controls["product"].version == last.version       # the passed attempt's version stands
    assert (project / "controls" / "product.md").read_text() == text


# ------------------------------------------------------------------------------------------------ F28: project config
def test_a_project_config_key_pdg_does_not_read_is_refused(project):
    _with_config(project, **{"dry-run": True})                            # a typo for dry_run
    with pytest.raises(EngineError, match="dry-run"):
        Engine(project)
    _with_config(project, commands={"n11_prototype_development": "npm run build"})
    with pytest.raises(EngineError, match="commands"):
        Engine(project)                                                   # a hook pdg never ran is not silently kept


# ------------------------------------------------------------------------------------------------ C8: risk acceptance
def test_only_a_named_human_accepts_a_risk_and_it_is_recorded_once(project, fast_browser):
    eng = Engine(project)
    _step_until(eng, lambda e: e.state.inputs.frozen and e.state.research.assumptions)
    aid = next(a.id for a in eng.state.research.assumptions if a.riskiest)
    for actor, assumption, reason, match in [("agent:product-strategist", aid, "fine", "named human"),
                                             ("Wei", "A-404", "fine", "not in the research state"),
                                             ("Wei", aid, "  ", "reason")]:
        with pytest.raises(EngineError, match=match):
            eng.accept_risk(assumption, actor, reason)
    assert not eng.state.history.risk_acceptances
    eng.accept_risk(aid, "Wei", "The paper test covers it for this round.")
    assert [(r.assumption, r.actor) for r in eng.state.history.risk_acceptances] == [(aid, "Wei")]
    assert [e["data"]["assumption"] for e in eng.ledger.events("risk_accepted")] == [aid]
