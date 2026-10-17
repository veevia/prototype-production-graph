"""CLI audit findings: `check-prototype` checks a real entry and never passes by measuring nothing (F12); malformed input
is refused cleanly, and a refused submission uses no attempt (F15)."""

from __future__ import annotations

import json

import pytest

from pdg.cli import main
from pdg.engine import Engine

from .conftest import PKG, copy_example

PLAN = {"scenarios": [{"id": "S-01", "name": "the page opens", "steps": [{"expect_visible": "h1"}]}], "states": []}


def test_check_prototype_refuses_a_missing_entry(tmp_path, capsys):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(PLAN))
    assert main(["check-prototype", str(tmp_path / "nowhere"), "--plan", str(plan), "--out", str(tmp_path / "o")]) == 4
    assert "no prototype entry" in capsys.readouterr().out


def test_check_prototype_sweeps_the_entry_page_without_an_experience_spec(tmp_path, capsys):
    pytest.importorskip("playwright")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<!doctype html><html lang='en'><head><title>t</title></head><body><main>"
                                     "<h1>Lots</h1><img src='data:image/gif;base64,R0lGODlhAQABAAAAACw='>"
                                     "</main></body></html>")                  # an image without alt text
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(PLAN))
    code = main(["check-prototype", str(site), "--plan", str(plan), "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out
    if "Executable doesn't exist" in out:
        pytest.skip("Chromium is not installed")
    assert code == 1 and "FAIL A11Y-AXE" in out                             # the page itself was swept


def test_check_prototype_with_no_scenarios_is_not_a_pass(tmp_path, capsys):
    pytest.importorskip("playwright")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<!doctype html><html lang='en'><head><title>t</title></head><body><main>"
                                     "<h1>Lots</h1></main></body></html>")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"scenarios": [], "states": []}))
    code = main(["check-prototype", str(site), "--plan", str(plan), "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out
    if "Executable doesn't exist" in out:
        pytest.skip("Chromium is not installed")
    assert code == 1 and "FAIL FUNC-SCENARIOS" in out


def test_check_prototype_unknown_failed_dimension_would_block():
    """B23: a dimension unknown to the local rubrics is conservative, matching recheck-release."""
    from pdg.cli import _prototype_verdict_counts
    from pdg.context import CheckResult
    res = CheckResult()
    res.dim("FUTURE-MUST", False, "new checker found a failure")
    assert _prototype_verdict_counts(None, res) == (1, 0)


def test_an_output_without_a_path_is_refused_and_uses_no_attempt(tmp_path, capsys):
    proj = copy_example(tmp_path / "p", dry_run=False)
    eng = Engine(proj)
    eng.run()
    packet = json.loads((proj / ".pdg" / "tasks" / "n01_context_intake-a1.json").read_text())
    state = (proj / ".pdg" / "state.json").read_bytes()
    code = main(["submit", str(proj), "n01_context_intake", "--token", packet["token"], "--actor", "agent:context-research",
                 "--output", "sources"])
    assert code == 4 and "key=path" in capsys.readouterr().out
    assert (proj / ".pdg" / "state.json").read_bytes() == state


def test_an_invalid_workflow_is_refused_without_a_traceback(tmp_path, capsys):
    bad = tmp_path / "workflow.yaml"
    bad.write_text((PKG / "graph" / "workflow.yaml").read_text().replace("max_attempts: 3", "max_attempts: three", 1))
    assert main(["validate", "--workflow", str(bad)]) == 1                   # invalid, like any structural error
    assert "graph INVALID" in capsys.readouterr().out


@pytest.mark.parametrize("proposal", [[], {"candidates": [{"statement": "no id"}]}, {"candidates": "all of them"},
                                      "{ not json"])
def test_a_malformed_learning_proposal_is_refused_and_applies_nothing(tmp_path, rules_copy, capsys, proposal):
    p = tmp_path / "proposal.json"
    p.write_text(proposal if isinstance(proposal, str) else json.dumps(proposal))
    before = rules_copy.read_bytes()
    assert main(["memory", "apply", "--proposal", str(p), "--approved-by", "Wei", "--rules", str(rules_copy)]) == 3
    assert "refused by memory governance" in capsys.readouterr().out
    assert rules_copy.read_bytes() == before


@pytest.mark.parametrize("flag,value", [("--check-fn", "nonexistent:nothing"), ("--check-dimension", "NOT-A-DIMENSION"),
                                        ("--check-test", "tests/test_nowhere.py::test_x")])
def test_a_rule_cannot_be_validated_with_a_check_that_does_not_exist(tmp_path, rules_copy, capsys, flag, value):
    import json as _json
    rules = _json.loads(rules_copy.read_text())
    rid = next(r["id"] for r in rules["rules"] if r["lifecycle"]["state"] == "candidate")
    before = rules_copy.read_bytes()
    assert main(["memory", "promote", rid, "--to", "validated", "--by", "agent:learning-memory", "--evidence", "run",
                 flag, value, "--rules", str(rules_copy)]) == 3
    assert rules_copy.read_bytes() == before


def test_status_refuses_a_special_file_at_the_ledger_path_instead_of_hanging(tmp_path, capsys):
    import os
    import signal
    proj = copy_example(tmp_path / "p", dry_run=False)
    Engine(proj).run()
    ledger = proj / ".pdg" / "ledger.jsonl"
    ledger.unlink()
    os.mkfifo(ledger)
    old = signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("status hung")))
    signal.alarm(10)
    try:
        assert main(["status", str(proj)]) == 4
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    assert "not a regular file" in capsys.readouterr().out


def test_the_report_draws_the_projects_own_workflow(tmp_path, fast_browser):
    import yaml as _yaml

    from pdg.report import write_report
    proj = copy_example(tmp_path / "p")
    custom = (PKG / "graph" / "workflow.yaml").read_text()
    name = _yaml.safe_load(custom)["name"]
    (proj / "workflow.yaml").write_text(custom.replace(f"name: {name}", "name: Custom review graph", 1))
    cfg = _yaml.safe_load((proj / "pdg.project.yaml").read_text())
    cfg["workflow"] = "workflow.yaml"
    (proj / "pdg.project.yaml").write_text(_yaml.safe_dump(cfg))
    Engine(proj).run(max_steps=3)
    assert "Custom review graph" in write_report(proj).read_text()


def test_r2_28_check_prototype_reads_the_project_it_sits_in(tmp_path, capsys):
    """Field run 2, R2-28: `check-prototype` took no project, so REF-PARITY printed "no reference build declared …
    nothing to compare" on a pre-submit check although sources/references/ held the reference build, and a declared
    `reference:` could not be exercised either. It now reads the project named by --project, or the one it sits in."""
    pytest.importorskip("playwright")
    proj = tmp_path / "proj"
    page = ("<!doctype html><html lang='en'><head><title>t</title></head><body><main data-screen='hub'>"
            "<h1>Hub</h1><p>Three sites need a review.</p></main></body></html>")
    for d in ("drafts/v1", "sources/references/hub", "controls"):
        (proj / d).mkdir(parents=True)
    (proj / "drafts/v1/index.html").write_text(page)
    (proj / "sources/references/hub/index.html").write_text(page)
    (proj / "pdg.project.yaml").write_text("id: demo\n")
    (proj / "controls/evaluation.md").write_text("---\nthresholds:\n  browser:\n    viewports: [700]\n---\n# Evaluation\n")
    plan, exp = tmp_path / "plan.json", tmp_path / "experience.json"
    plan.write_text(json.dumps(PLAN))
    exp.write_text(json.dumps({"screens": [{"id": "hub", "route": None}]}))
    args = ["check-prototype", str(proj / "drafts/v1"), "--plan", str(plan), "--experience", str(exp)]
    code = main([*args, "--out", str(tmp_path / "o1")])
    out = capsys.readouterr().out
    if "Executable doesn't exist" in out:
        pytest.skip("Chromium is not installed")
    assert f"project: {proj.resolve()} (found above the prototype" in out, out
    assert "FAIL REF-PARITY: a reference build is in the sources (sources/references/hub/index.html) but not declared" in out, out
    assert "would block 0 · advisory 1 · deferred 0" in out
    assert code == 3
    rep = json.loads((tmp_path / "o1" / "browser-report.json").read_text())
    assert rep["reference_hint"] == "sources/references/hub/index.html"
    assert {r["viewport"] for r in rep["screens"]} == {700}                 # the project's accepted thresholds
    (proj / "pdg.project.yaml").write_text("id: demo\nreference:\n  entry: sources/references/hub/index.html\n")
    code = main([*args, "--out", str(tmp_path / "o2"), "--project", str(proj)])
    out = capsys.readouterr().out
    assert "PASS REF-PARITY" in out and "no reference build declared" not in out and code == 0, out
    assert main([*args, "--out", str(tmp_path / "o3"), "--project", str(tmp_path / "nowhere")]) == 4
    assert "has no pdg.project.yaml" in capsys.readouterr().out


def test_r2_28_check_prototype_reads_the_accepted_thresholds_and_writes_nothing(tmp_path, capsys):
    """Batch 14 review S7: with a run, the thresholds come from evaluation.md's accepted version (as the gate reads them),
    never from a draft being edited, and nothing in the project changes (no lock, no state write)."""
    pytest.importorskip("playwright")
    proj = copy_example(tmp_path / "p", dry_run=False)
    Engine(proj).save("test")                                               # a run: each control document's accepted version
    ev = proj / "controls" / "evaluation.md"
    ev.write_text("---\nthresholds:\n  browser:\n    viewports: [700]\n---\n" + ev.read_text())   # a draft nobody accepted
    site = proj / "drafts" / "v1"
    site.mkdir(parents=True)
    (site / "index.html").write_text("<!doctype html><html lang='en'><head><title>t</title></head><body><main data-screen='hub'>"
                                     "<h1>Hub</h1></main></body></html>")
    plan, exp = tmp_path / "plan.json", tmp_path / "experience.json"
    plan.write_text(json.dumps(PLAN))
    exp.write_text(json.dumps({"screens": [{"id": "hub", "route": None}]}))
    before = {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in proj.rglob("*")}
    main(["check-prototype", str(site), "--plan", str(plan), "--experience", str(exp), "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out
    if "Executable doesn't exist" in out:
        pytest.skip("Chromium is not installed")
    rep = json.loads((tmp_path / "o" / "browser-report.json").read_text())
    assert 700 not in {r["viewport"] for r in rep["screens"]}, out
    assert {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in proj.rglob("*")} == before


def test_w64_check_prototype_refuses_an_input_that_is_not_its_artifact(tmp_path, capsys):
    """Field run W64: `--experience controls/experience.md` died with a JSONDecodeError traceback, and `--help` did not
    say the flag wants N07's artifact. Each input is now named in the help and refused in one line."""
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<main><h1>Hi</h1></main>")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"scenarios": []}))
    md = tmp_path / "experience.md"
    md.write_text("# Experience\n")
    notes = tmp_path / "notes.json"
    notes.write_text(json.dumps({"journeys": []}))
    bare, idless, listed, array, counted = (tmp_path / f"{n}.json" for n in ("bare", "idless", "listed", "array", "counted"))
    counted.write_text(json.dumps({"scenarios": [], "samples": {"home": 5}}))   # review 2, nit 3
    bare.write_text(json.dumps({"screens": ["home"]}))                   # batch 18 review I3: each one a traceback
    idless.write_text(json.dumps({"screens": [{"route": "/"}]}))
    listed.write_text(json.dumps({"scenarios": [], "samples": ["home"]}))
    array.write_text(json.dumps([]))
    cases = [(["--plan", str(plan), "--experience", str(md)],
              f"refused (nothing checked): --experience {md} is not JSON; it wants N07's experience artifact, "
              "work/n07_experience_architecture/a<N>/experience.json, not the control document"),
             (["--plan", str(plan), "--experience", str(notes)],
              f"refused (nothing checked): --experience {notes} is not N07's experience artifact (no `screens` list)"),
             (["--plan", str(md)], f"refused (nothing checked): --plan {md} is not JSON; it wants N10's plan"),
             (["--plan", str(plan), "--experience", str(bare)], f"refused (nothing checked): --experience {bare} is not N07's experience artifact (a "
                                     "screen that is not an object with a string `id`)"),
             (["--plan", str(plan), "--experience", str(idless)], f"refused (nothing checked): --experience {idless} is not N07's experience "
                                       "artifact (a screen that is not an object with a string `id`)"),
             (["--plan", str(listed)], f"refused (nothing checked): --plan {listed} is not N10's plan (`samples` is not a "
                                       "dict)"),
             (["--plan", str(array)], f"refused (nothing checked): --plan {array} is not a JSON object"),
             (["--plan", str(counted)], f"refused (nothing checked): --plan {counted} is not N10's plan (a `samples` entry "
                                        "that is not a list of routes)"),
             (["--plan", str(tmp_path / "none.json")], f"refused (nothing checked): --plan {tmp_path / 'none.json'} cannot be read")]
    for args, said in cases:
        assert main(["check-prototype", str(site), *args, "--out", str(tmp_path / "o")]) == 4
        out = capsys.readouterr().out
        assert said in out and "Traceback" not in out and len(out.strip().splitlines()) == 1, out
    assert not (tmp_path / "o").exists()
    with pytest.raises(SystemExit):
        main(["check-prototype", "--help"])
    assert "work/n07_experience_architecture/a<N>/experience.json" in " ".join(capsys.readouterr().out.split())


def test_r2_26_check_prototype_reads_the_design_systems_documented_state_fills(tmp_path):
    """R2-26 addendum: `check-prototype --project` passes the design system's own state fills to the suite, as the gate
    does, so a pre-submit check does not flag the canon's documented filter state."""
    from pdg.artifacts import DesignSystemDoc
    from pdg.cli import _project_for_check
    from pdg.models import ProjectInfo, ProjectState
    system = json.loads((PKG / "examples/coa-review/fixtures/n09_visual_system/attempt-1/design-system.json").read_text())
    system["colors"][0]["state_fill_of"] = ["sf-btn"]
    st = ProjectState(schema_version="pdg-state/v1", project=ProjectInfo(id="p", name="p", created="2026-09-29",
                                                                         workflow_id="w", workflow_version="1.0.0"))
    st.design.system = DesignSystemDoc.model_validate(system)
    (tmp_path / ".pdg").mkdir()
    (tmp_path / ".pdg" / "state.json").write_text(st.model_dump_json())
    (tmp_path / "pdg.project.yaml").write_text("id: p\n")
    assert _project_for_check(tmp_path)["documented"] == {system["colors"][0]["name"]: ["sf-btn"]}


def test_check_prototype_lists_findings_under_their_screen(tmp_path, capsys):
    """Field run 2 (19:30Z): 22 RESP findings on one line could not be triaged; each is now on its own line, under its
    screen."""
    pytest.importorskip("playwright")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<!doctype html><html lang='en'><head><title>t</title></head><body><main>"
                                     "<h1>Hub</h1><div style='width:30px;overflow-wrap:anywhere'>Contaminants</div>"
                                     "</main></body></html>")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(PLAN))
    main(["check-prototype", str(site), "--plan", str(plan), "--out", str(tmp_path / "o")])
    out = capsys.readouterr().out
    if "Executable doesn't exist" in out:
        pytest.skip("Chromium is not installed")
    lines = out.splitlines()
    at = next(i for i, x in enumerate(lines) if x.startswith("FAIL RESP-TEXT"))
    assert lines[at + 1] == "  entry (1):", out
    assert lines[at + 2].startswith("    - 'Contaminants' breaks mid-word in div"), out   # the screen, said once


def test_check_prototype_lists_each_screens_findings_once_and_caps_them():
    """Field run 2 and batch 18 review nit 13: a message that opens with its screen does not repeat it under the screen,
    and a screen lists at most 12, then says how many more."""
    from pdg.cli import findings_by_screen
    found = [{"location": "home", "message": f"home: select#s{i} cuts its value"} for i in range(13)]
    found.append({"location": "", "message": "the page overflows"})
    lines = findings_by_screen(found)
    assert lines[:3] == ["  home (13):", "    - select#s0 cuts its value", "    - select#s1 cuts its value"]
    assert lines[12:] == ["    - select#s11 cuts its value", "    … and 1 more", "  (page) (1):", "    - the page overflows"]


def test_r2_26_check_prototype_hands_the_suite_the_documented_state_fills(tmp_path, monkeypatch):
    """Batch 18 review S7: `check-prototype` passes the design system's own state fills on to the suite, not only reads
    them."""
    import pdg.tools.browser as browser
    test_r2_26_check_prototype_reads_the_design_systems_documented_state_fills(tmp_path)
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "index.html").write_text("<main><h1>Hi</h1></main>")
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(PLAN))
    seen: dict = {}

    def fake(*args, **kwargs):
        seen.update(kwargs)
        raise RuntimeError("stop here")
    monkeypatch.setattr(browser, "run_suite", fake)
    assert main(["check-prototype", str(tmp_path / "site"), "--plan", str(plan), "--project", str(tmp_path),
                 "--out", str(tmp_path / "o")]) == 4
    assert list(seen["documented"].values()) == [["sf-btn"]], seen
