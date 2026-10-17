"""Findings from the second pair of field runs that need the finished example run (see test_audit_convergence.py)."""

from __future__ import annotations

import pytest

from .test_audit_convergence import INTERACTION, _d, _defect, _gate, eng, finished  # noqa: F401 - fixtures

__all__ = ["eng", "finished"]


def test_a_code_line_signature_never_re_opens_a_resolved_defect(eng, tmp_path):
    """Field run W40: `TEC-QUALITY@build.py:87` re-opened a v2 defect for an unrelated v7 finding, because line 87 held
    another statement by then, and the record mixed the two. A bare code location opens a new defect instead."""
    sig = "TEC-QUALITY@build.py:87"
    _gate(eng, tmp_path, [_defect(INTERACTION, sig)])
    old = _d(eng)
    old.status, old.resolved_at_version = "resolved", eng.state.build.version
    _gate(eng, tmp_path, [{**_defect(INTERACTION, sig), "id": "D-977", "message": "the dataset is parsed twice"}])
    assert old.status == "resolved"
    new = next(x for x in eng.state.evaluation.defects if x.id == "D-977")
    assert new.status == "open" and new.message == "the dataset is parsed twice"


def test_attempt_folder_signature_reopens_the_same_defect(eng, tmp_path):
    """R3-10: a finding under work/<node>/aN/ keeps one identity across attempts."""
    sig_a2 = "TEC-FEASIBLE@work/n11_prototype_development/a2/development.md#offline queue"
    sig_a3 = "TEC-FEASIBLE@work/n11_prototype_development/a3/development.md#offline queue"
    _gate(eng, tmp_path, [_defect(INTERACTION, sig_a2)])
    old = _d(eng)
    old.status, old.resolved_at_version = "resolved", eng.state.build.version
    _gate(eng, tmp_path, [{**_defect(INTERACTION, sig_a3), "id": "D-977"}])
    assert old.status == "open"
    assert old.signature == "TEC-FEASIBLE@work/development.md#offline queue"
    assert not [d for d in eng.state.evaluation.defects if d.id == "D-977"]


def test_current_review_attempt_path_counts_as_same_persisting_defect(eng, tmp_path):
    """B23 review: step 1 of the gate canonicalizes current review findings too, so failed corrections count."""
    from pdg.models import FindingRecord
    sig_a2 = "TEC-FEASIBLE@work/n11_prototype_development/a2/development.md#offline queue"
    sig_a3_loc = "work/n11_prototype_development/a3/development.md"
    _gate(eng, tmp_path, [_defect(INTERACTION, sig_a2)])
    from .test_audit_convergence import _plan_rework, _reran, _review_now
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    _reran(eng, INTERACTION)
    eng.rt("n13_quality_review").attempt += 100
    _review_now(eng, [FindingRecord(node="n13_quality_review", dimension="TEC-FEASIBLE", location=sig_a3_loc,
                                    element="offline queue", severity="P2", message="still unfixed", by="agent",
                                    blocking=True)])
    _gate(eng, tmp_path)
    d = _d(eng)
    assert d.status == "persisting" and d.failures == 1


def test_signature_migration_keeps_the_active_duplicate_open(eng, tmp_path):
    """B23 review: an a2 resolved identity plus an a3 open identity must leave the bug active."""
    from pdg.models import Defect
    old = Defect(**_defect(INTERACTION, "TEC-FEASIBLE@work/n11_prototype_development/a2/development.md#offline"))
    old.status, old.resolved_at_version, old.failures = "resolved", eng.state.build.version, 1
    new = Defect(**{**_defect(INTERACTION, "TEC-FEASIBLE@work/n11_prototype_development/a3/development.md#offline"),
                    "id": "D-951"})
    new.failures = 2
    eng.state.evaluation.defects = [old, new]
    assert eng._migrate_defect_signatures()
    active = [d for d in eng.state.evaluation.defects if d.status != "dismissed"]
    assert len(active) == 1 and active[0].id == "D-951"
    assert active[0].status == "open" and active[0].failures == 3
    assert any("D-950" in h for h in active[0].history)


def test_loading_engine_with_pending_signature_merge_does_not_write_ledger(eng, tmp_path):
    """B23 round 2: migration is not a load-time side effect."""
    from pdg.engine import Engine
    from pdg.models import Defect
    old = Defect(**_defect(INTERACTION, "TEC-FEASIBLE@work/n11_prototype_development/a2/development.md#offline"))
    new = Defect(**{**_defect(INTERACTION, "TEC-FEASIBLE@work/n11_prototype_development/a3/development.md#offline"),
                    "id": "D-951"})
    eng.state.evaluation.defects = [old, new]
    eng.save("test")
    ledger_before = (eng.project.root / ".pdg" / "ledger.jsonl").read_text()
    Engine(eng.project.root)
    assert (eng.project.root / ".pdg" / "ledger.jsonl").read_text() == ledger_before


def test_a_re_opened_defect_takes_the_new_report_and_keeps_the_old_one_in_its_history(eng, tmp_path):
    """W40: a re-opened record carried the old message and evidence beside the new fix, so the rework packet described
    the old problem."""
    _gate(eng, tmp_path, [_defect(INTERACTION, "UX-H1@case:390#result")])
    d = _d(eng)
    was = d.message
    d.status, d.resolved_at_version = "resolved", eng.state.build.version
    _gate(eng, tmp_path, [{**_defect(INTERACTION, "UX-H1@case:390#result"), "message": "the result is off screen again",
                           "evidence": "v7 screenshot at 390"}])
    assert d.status == "open" and d.message == "the result is off screen again" and d.evidence == "v7 screenshot at 390"
    assert was[:40] in d.history[-1]


# ------------------------------------------------------------------------------------------------ independent audit
from .test_audit_convergence import GATE, PROBLEM, _plan_rework, _reran, _review_now  # noqa: E402


def test_a_node_scoped_grant_cannot_defer_or_close_a_blocking_defect(eng, tmp_path):
    """Independent audit #2: `defer` and `decide-deferred` name no node, and a node-less action matched any grant, so a
    `decide` grant limited to one gate let an agent park and then close a blocking defect on Wei's behalf."""
    import datetime as dt
    import pytest
    from pdg.engine import EngineError
    later = (dt.datetime.now(dt.UTC) + dt.timedelta(days=1)).isoformat()
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    eng.delegate("Wei", "agent:orchestrator", "Decide the problem gate for me.", ["decide"], [PROBLEM], later)
    with pytest.raises(EngineError, match="out of scope"):
        eng.defer("D-950", "a product call", "Wei decides", "agent:orchestrator", on_behalf_of="Wei")
    eng.delegate("Wei", "agent:orchestrator", "Decide anything for me.", ["decide"], None, later,
                 except_nodes=["n18_final_verification"])
    assert eng.defer("D-950", "a product call", "Wei decides", "agent:orchestrator", on_behalf_of="Wei")["deferred"]


def test_an_advisory_finding_folded_in_as_an_alias_does_not_keep_a_fixed_defect_open(eng, tmp_path):
    """Independent audit #4: the interpreter folded an advisory finding into a blocking defect as an alias; the blocking
    bug was fixed, the advisory stayed, and the defect counted as still reported at every gate until it blocked."""
    from pdg.models import FindingRecord
    di = {**_defect(INTERACTION, "RESP-FIT@case:390"),
          "from_findings": ["n13_quality_review:RESP-FIT@case:390", "n13_quality_review:DES-DENSITY@case:390"]}
    _gate(eng, tmp_path, [di])
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    for n in (INTERACTION, "n13_quality_review"):
        _reran(eng, n)
    _review_now(eng, [FindingRecord(node="n13_quality_review", dimension="DES-DENSITY", location="case:390", severity="P4",
                                    message="dense", by="agent", blocking=False)])
    _gate(eng, tmp_path)
    assert _d(eng).status == "resolved"


def test_a_kept_deferral_does_not_hold_the_release(eng, tmp_path):
    """Independent audit #5: Wei kept a deferred blocking defect for the next build; the gate passed, then the release
    refused "no blocking defect open" for it, so only fixing or closing it could release."""
    from pdg.gating import release_blockers
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    eng.defer("D-950", "the next build's scope", "Wei decides at the scope review", "Wei")
    eng.decide_deferred("D-950", "keep", "carry it to the next build", "Wei")
    assert "D-950" not in release_blockers(eng)


def test_a_budget_reset_also_clears_the_failures_of_a_defect_still_in_rework(eng, tmp_path):
    """Independent audit #6: a defect mid-rework kept its failed corrections through `--reset-budget`, so the next gate
    blocked on "failed 3 corrections" right after the reset that promised to clear them."""
    from pdg.models import Escalation
    _gate(eng, tmp_path, [_defect(INTERACTION)])
    _plan_rework(eng, {INTERACTION: ["D-950"]})
    _d(eng).failures = 2
    eng.state.runtime.escalations.append(Escalation(id=f"{GATE}-9", node=GATE, reason="E29: outcome 'blocked'",
                                                    report="", at="2026-09-28T16:00:00+00:00"))
    assert _d(eng).status == "in_rework"
    eng.unblock(GATE, "Wei", note="fund another cycle", reset_budget=True)
    assert _d(eng).failures == 0


def test_a_resolved_feedback_defect_is_on_its_owning_reviewers_still_fixed_list(eng, tmp_path):
    """Independent audit #12: a resolved defect raised from feedback had no reviewer who found it, so it was on no
    "still fixed?" list; it goes to the reviewer that owns its dimension, like the re-verify list."""
    from .test_audit_convergence import _packet
    _gate(eng, tmp_path, [{**_defect(INTERACTION, "UX-H3@queue"), "dimension": "UX-H3"}])
    d = _d(eng)
    d.status, d.resolved_at_version = "resolved", eng.state.build.version
    assert "D-950" in [x["id"] for x in _packet(eng, "n13_quality_review", tmp_path)["still_fixed"]]


def test_check_build_runs_the_gates_n11_checks_on_a_folder_before_submitting(eng, tmp_path, capsys):
    """Field run 2, R2-10: a builder could not run N11's checks before submitting, and unit tests that passed only in
    place (they read outside the build) reached the gate. `pdg check-build` runs them as the gate does, copy included."""
    import shutil
    from pdg.cli import main
    build = tmp_path / "build"
    shutil.copytree(eng.project.root / eng.current("prototype_build")[-1].path, build)
    assert main(["check-build", str(build), "--project", str(eng.project.root)]) == 0
    out = capsys.readouterr().out
    assert "PASS BLD-TOKENS" in out and "PASS BLD-UNIT" in out and "PASS BLD-SCREENS" in out
    entry = next(p for p in build.rglob("*.html"))
    entry.write_text(entry.read_text().replace("<body", "<p>TODO: write the copy</p><body", 1))
    assert main(["check-build", str(build), "--project", str(eng.project.root)]) == 4
    assert "FAIL BLD-PLACEHOLDER" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------ W42, W43
def _reviewer_waiting_under_drift(tmp_path, reviewer="n15_feasibility_review"):
    """A real run whose reviewer is out with its agent when a rubric it reads changes on disk."""
    from pdg.engine import Engine
    from .conftest import copy_example
    from .test_audit_coverage import _PendingFor
    project = copy_example(tmp_path / "p")
    eng = Engine(project, executor=_PendingFor(project / "fixtures", {reviewer}))
    eng.run(max_steps=400)                                         # callers stub the browser suite
    assert eng.rt(reviewer).status.value == "WAITING_AGENT"
    name = eng.node(reviewer).evaluation[0]
    rubric = f"rubrics/{name}.yaml"
    eng.state.runtime.config_parts[rubric] = "0" * 64            # the accepted hash no longer matches the file
    eng.state.runtime.config_sha256 = "changed"
    # and the change is one its reviewer must score: a packet is re-issued only when how it is judged moved (config 5)
    eng.rubrics[name]["dimensions"].append({"id": "REV-NEW", "name": "a new review dimension", "level": "MUST",
                                            "check": {"type": "review"}, "threshold": "score ≥ 4", "rule": "R-TEC-003"})
    return eng, reviewer


def test_a_submission_made_while_the_run_is_blocked_is_parked_and_its_findings_survive_the_re_judge(tmp_path, monkeypatch):
    """Field run W42: a configuration batch landed with two reviews finished but not submitted. The submit was refused on
    the drift and printed "attempt failed", and accept-config withdrew both tasks, so their findings reached the record
    only because the side chat filed them as feedback by hand. The submission is now parked, and a withdrawn reviewer's
    findings are recorded as feedback."""
    import json as _json
    import pdg.tools.browser as browser_mod
    from .conftest import fake_browser
    from .test_audit_coverage import FIXTURES, _fixture, _submit_fixture
    monkeypatch.setattr(browser_mod, "check", fake_browser)
    eng, reviewer = _reviewer_waiting_under_drift(tmp_path)
    attempt, streak = eng.rt(reviewer).attempt, eng.rt(reviewer).streak
    fx, _ = _fixture(FIXTURES, reviewer, attempt)
    review = _json.loads((fx / "review.json").read_text())
    review["findings"] = [{"dimension": "TEC-QUALITY", "severity": "P3", "message": "the dataset is parsed twice",
                           "location": "build.py", "element": "dataset pre-check", "by": "agent",
                           "smallest_fix": "parse once", "acceptance_check": "one decoder"}]
    res = _submit_fixture(eng, reviewer, replace={"review.json": _json.dumps(review)})
    assert res["parked"] and eng.rt(reviewer).parked and (eng.rt(reviewer).attempt, eng.rt(reviewer).streak) == (attempt, streak)
    impact = eng.config_impact()
    assert reviewer in impact["rejudge"] and reviewer in impact["parked"] and not impact["in_flight"]
    out = eng.accept_config("Wei", "the rubric change")
    (fid,) = out["parked_findings"][reviewer]
    fb = next(f for f in eng.state.evaluation.feedback if f.id == fid)
    assert "the dataset is parsed twice" in fb.text and fb.actor.startswith("agent:") and not fb.human
    assert eng.rt(reviewer).parked is None and eng.rt(reviewer).status.value == "STALE"


def test_accepting_a_configuration_refuses_to_withdraw_work_still_out_with_an_agent(tmp_path, monkeypatch):
    """W42: a reviewer still working when accept-config runs would lose its work; accepting refuses, naming it, unless
    the work is explicitly discarded."""
    import pytest
    import pdg.tools.browser as browser_mod
    from pdg.engine import EngineError
    from .conftest import fake_browser
    monkeypatch.setattr(browser_mod, "check", fake_browser)
    eng, reviewer = _reviewer_waiting_under_drift(tmp_path)
    assert eng.config_impact()["in_flight"] == [reviewer]
    with pytest.raises(EngineError, match=f"still out with an agent: {reviewer}.*--discard-in-flight"):
        eng.accept_config("Wei", "the rubric change")
    eng.accept_config("Wei", "the rubric change", discard_in_flight=True)
    assert list(eng.ledger.events("config_accepted"))[-1]["data"]["discarded"] == [reviewer]


def test_a_re_judged_nodes_packet_says_what_its_last_output_now_fails(eng, tmp_path):
    """Field run W43: accept-config re-judged N11 on the new BLD-TOKENS rule, and its packet did not say that the last
    passed build now failed it on seven undeclared colours; the side chat had to find it by hand."""
    from pdg.executors import render_packet
    from .test_audit_convergence import _packet
    build = "n11_prototype_development"
    sig = next(s for s in eng.rt(build).passed_dims if s.startswith("BLD-TOKENS|"))
    eng.rt(build).passed_dims.remove(sig)                                   # passed before BLD-TOKENS changed
    eng.rt(build).passed_judging = "under the old rubric"
    eng.state.design.system.colors = eng.state.design.system.colors[1:]      # a colour the build uses is undeclared
    eng.state.runtime.config_parts["rubrics/build.yaml"] = "0" * 64
    eng.state.runtime.config_sha256 = "changed"
    eng.accept_config("Wei", "BLD-TOKENS checks the token block against the design system")
    rj = eng.rt(build).rejudge
    assert any(d.startswith("BLD-TOKENS") for d in rj["dims"])
    assert any(f["dim"] == "BLD-TOKENS" for f in rj["last_pass"])
    text = render_packet(_packet(eng, build, tmp_path))
    assert "## Re-judged under a new configuration" in text and "now fails these checks" in text and "BLD-TOKENS" in text


def test_two_nodes_copies_of_one_shared_document_both_stay_current(eng):
    """Backlog N-10 (field run FR-11): N07's and N08's copies of experience.md share an output key, and the later one
    marked the earlier "not current". A control copy now supersedes only its own node's copies."""
    keys = {}
    for n in eng.wf.nodes:
        for o in n.outputs:
            if o.kind == "control":
                keys.setdefault(o.key, set()).add(n.id)
    key, writers = next((k, w) for k, w in keys.items() if len(w) > 1)
    current_writers = {a.node for a in eng.current(key)}
    assert current_writers == {w for w in writers if eng.rt(w).passed_attempt}, (key, current_writers, writers)


# ------------------------------------------------------------------------------------------------ R2-11, R2-14, R2-15, N-08, N-11
def test_a_failing_steps_error_says_what_its_selector_matched(tmp_path):
    """Field run 2, R2-11: a click whose first match was hidden (another tab's copy) timed out with no hint, and the
    builder rewrote the page's text instead of fixing the plan's selector."""
    import pytest
    pytest.importorskip("playwright")
    from .test_audit_browser import _thresholds, _write_html
    import pdg.tools.browser as browser
    entry = _write_html(tmp_path / "p.html", '<main data-screen="one"><div hidden><button>Acme</button></div>'
                                             '<button>Acme</button></main>')
    t = _thresholds()
    t["step_timeout_ms"] = 600
    rep = browser.run_suite(entry, [{"id": "S-01", "flow_id": "F-01", "steps": [{"click": "text=Acme"}]}], [],
                            [{"id": "one", "route": ""}], [390], t, tmp_path / "run")
    err = rep["scenarios"][0]["error"]
    assert "[text=Acme matched 2; visible: 2; the step uses the first match, which is hidden" in err, err


def test_an_obscured_focus_finding_names_what_covers_it_and_a_phone_page_is_tiled(tmp_path):
    """R2-14: the 2.4.11 finding named the hidden focus stop but not what covered it; N-08: a full-page screenshot at
    390 px was too small to read, so a reviewer cropped it by hand."""
    import pytest
    pytest.importorskip("playwright")
    from .test_browser import _suite_for_html
    import yaml
    res = _suite_for_html(tmp_path, """<!doctype html><html><head><style>
body { margin: 0; font-family: sans-serif; } .bar { position: fixed; inset: 0 0 auto 0; height: 84px; z-index: 10; background: #fff; }
.under { position: absolute; top: 24px; left: 24px; z-index: 1; } main { height: 3000px; }
</style></head><body><div class="bar" id="topbar">Sticky header</div>
<main data-screen="home"><a class="under" href="#next">Hidden focus target</a></main></body></html>""", [390])
    msg = res.dimensions["A11Y-FOCUS-VISIBLE-2411"].findings[0]["message"]
    assert "covered by div#topbar.bar" in msg, msg
    rep = yaml.safe_load((tmp_path / "run" / "browser-report.json").read_text())
    assert rep["screens"][0]["tiles"] >= 3 and (tmp_path / "run" / "screenshots" / "home-390-tile1.png").is_file()


def test_status_separates_attempts_started_from_attempts_failed(eng, capsys):
    """Field run 2, R2-15: "attempts 3" read as three tries used for a node never submitted, whose budget was intact."""
    from pdg.cli import main
    rt = eng.rt("n10_prototype_planning")
    rt.attempt, rt.streak = 3, 0
    eng.save("test")
    main(["status", str(eng.project.root)])
    line = next(l for l in capsys.readouterr().out.splitlines() if "n10_prototype_planning" in l)
    assert "attempt 3 · 0 failed · 3 left" in line, line


def test_init_writes_a_note_that_sources_are_raw_intake(tmp_path):
    """Backlog N-11 (field run W29): a repo document copied into sources/ failed the link audit, and editing it to fix
    links would change a frozen input. `pdg init` says so where the files go."""
    from pdg.cli import main
    assert main(["init", str(tmp_path / "proj"), "--name", "A test project"]) == 0
    assert "raw intake" in (tmp_path / "proj" / "sources" / "README.md").read_text()


def test_the_ledger_records_when_the_package_code_changes_under_a_run(eng):
    """Which code judged which attempt: a change to a check can change a verdict, and unlike the configuration it does
    not block, so the ledger records it."""
    first = dict(eng.state.runtime.code_parts)
    eng.state.runtime.code_parts = {**first, "pdg/tools/browser.py": "0" * 64}
    eng.state.runtime.status = eng.state.runtime.status.__class__("RUNNING")
    eng._note_code_change()
    event = list(eng.ledger.events("code_updated"))[-1]["data"]
    assert event["changed"] == ["pdg/tools/browser.py"] and eng.state.runtime.code_parts["pdg/tools/browser.py"] != "0" * 64


def test_archive_moves_only_earlier_attempts_and_a_rollback_that_needs_one_says_so(eng, tmp_path):
    """Backlog N-17 (D5): the first project kept every attempt and screenshot round, 124 MB in 1,219 files. `pdg archive`
    moves only folders no current artifact, current attempt or last pass uses, with a restore script; the run still
    verifies, and a rollback to a checkpoint that needs a moved folder refuses and names the archive."""
    import json
    import shutil
    import subprocess
    from pathlib import Path
    import pytest
    from pdg.engine import EngineError
    from pdg.models import ProjectState
    cands = eng.archive_candidates()
    moved = {r for r, _ in cands}
    assert moved, "the example run has earlier attempts (its rework cycle)"
    assert not moved & {"/".join(Path(a.path).parts[:3]) for a in eng.state.artifacts.values() if a.current}
    with pytest.raises(EngineError, match="named human"):
        eng.archive(tmp_path / "arch", "agent:orchestrator")
    dest = Path(eng.archive(tmp_path / "arch", "Wei")["dest"])
    assert (dest / "restore.sh").is_file() and not eng.archive_candidates() and not eng._integrity_problems()

    def needs_moved(cp) -> bool:
        if not (eng.project.root / cp.path).is_file():
            return True
        old = ProjectState.model_validate(json.loads((eng.project.root / cp.path).read_text()))
        return any("/".join(Path(a.path).parts[:3]) in moved for a in old.artifacts.values() if a.current)
    cp = next(c for c in eng.state.history.checkpoints if needs_moved(c))
    with pytest.raises(EngineError, match="restore the archive first"):
        eng.rollback(cp.seq, "Wei")
    moved_checkpoint = next((m for m in __import__("json").loads((dest / "manifest.json").read_text()).get("moved_checkpoints", [])
                             if m["seq"] == cp.seq), None)
    assert moved_checkpoint
    target = eng.project.root / moved_checkpoint["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dest / moved_checkpoint["path"], target)
    with pytest.raises(EngineError) as ei:
        eng.rollback(cp.seq, "Wei")
    assert "needs files no longer in the project" in str(ei.value)
    assert str(dest) in str(ei.value)
    target.unlink()
    subprocess.run(["bash", str(dest / "restore.sh")], check=True)
    assert {r for r, _ in eng.archive_candidates()} == moved


def test_a_failed_archive_move_puts_every_folder_back_and_a_second_archive_keeps_the_first(eng, tmp_path, monkeypatch):
    """N-17 hardening: archiving is one action, so a move that fails half-way puts back every folder already moved and
    records nothing; and a second archive the same day gets its own folder, so the first restore script still works."""
    import shutil as sh
    import pytest
    cands = eng.archive_candidates()
    assert len(cands) >= 2
    ledger = eng.project.root / ".pdg" / "ledger.jsonl"
    seq, real, calls = ledger.read_bytes(), sh.move, []

    def flaky(src, dst):
        calls.append(src)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(src, dst)
    monkeypatch.setattr(sh, "move", flaky)
    with pytest.raises(OSError, match="disk full"):
        eng.archive(tmp_path / "arch", "Wei")
    monkeypatch.setattr(sh, "move", real)
    assert eng.archive_candidates() == cands and ledger.read_bytes() == seq
    assert all((eng.project.root / r).is_dir() for r, _ in cands)
    first = eng.archive(tmp_path / "arch", "Wei")["dest"]
    assert first.endswith("-2")   # the failed attempt's folder (its guarded restore script) is left as it was
    (eng.project.root / cands[0][0]).mkdir(parents=True)   # another earlier attempt appears later the same day
    (eng.project.root / cands[0][0] / "x.txt").write_text("x")
    second = eng.archive(tmp_path / "arch", "Wei")["dest"]
    assert second.endswith("-3") and (__import__("pathlib").Path(first) / "restore.sh").is_file()


def test_the_cli_previews_an_accept_and_an_archive_without_changing_anything(eng, capsys):
    """W42 and N-17 at the command line: `accept-config --dry-run` and `archive` without --apply read the run under its
    lock and print what would happen; the state and the ledger are byte-identical afterwards."""
    from pdg.cli import main
    root = eng.project.root
    before = [(root / ".pdg" / f).read_bytes() for f in ("state.json", "ledger.jsonl")]
    assert main(["accept-config", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "changed: nothing" in out and "out with an agent, would be lost: none" in out
    assert main(["archive", str(root)]) == 0
    assert "Nothing moved" in capsys.readouterr().out
    assert main(["archive", str(root), "--apply"]) == 4
    assert main(["accept-config", str(root)]) == 4
    assert [(root / ".pdg" / f).read_bytes() for f in ("state.json", "ledger.jsonl")] == before


def test_running_or_importing_pdg_without_minus_b_leaves_no_module_bytecode_in_the_package(tmp_path):
    """N-12: the first run's commands and a side chat's probe script left `pdg/__pycache__/` with every module in the
    shared tree. Importing pdg now turns bytecode off before any other module loads."""
    import os
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    pkg = Path(__file__).resolve().parents[1]
    copy = tmp_path / "pkg"
    shutil.copytree(pkg, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "_runs", "work", "tests",
                                                             "examples", "docs", "loop"))
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX")}
    for argv in (["-m", "pdg", "validate"], ["-c", "import pdg.engine, pdg.cli, pdg.tools.browser"]):
        subprocess.run([sys.executable, *argv], cwd=copy, env=env, capture_output=True, check=False, timeout=120)
    cached = sorted(p.name.split(".")[0] for p in copy.rglob("*.pyc"))
    assert set(cached) <= {"__init__", "__main__"} and "engine" not in cached, cached


# ------------------------------------------------------------------------------------------------ batch 7 review
GATE16 = "n16_feedback_diagnosis"


def _drift_rubric(eng, node_id: str) -> None:
    """Accepting now re-judges node_id: its judging hash is stale, and a rubric file changed."""
    eng.rt(node_id).passed_judging = "under the old rubric"
    rubric = next(f"rubrics/{r}.yaml" for r in eng.node(node_id).evaluation)
    eng.state.runtime.config_parts[rubric] = "0" * 64
    eng.state.runtime.config_sha256 = "changed"


def test_re_judging_the_gate_never_runs_its_decision_on_the_live_record(eng):
    """Review C1: re-judging N16 ran `diagnosis:gate`, the review gate itself, on the live state: accept-config
    recorded a gate no node ran and resolved a defect still in rework. A gate's hook is a decision, not a check."""
    d = eng.state.evaluation.defects[0]
    d.status, d.failures = "in_rework", 0
    eng.save("t")
    ev = eng.state.evaluation
    before = (len(ev.gates), len(ev.comparisons), [(x.id, x.status, x.failures, len(x.history)) for x in ev.defects])
    _drift_rubric(eng, GATE16)
    out = eng.accept_config("Wei", "gate rubric edited")
    assert GATE16 in out["rejudged"]
    ev = eng.state.evaluation
    assert (len(ev.gates), len(ev.comparisons), [(x.id, x.status, x.failures, len(x.history)) for x in ev.defects]) == before
    assert eng.rt(GATE16).rejudge["rechecked"] == [] and eng.rt(GATE16).rejudge["last_pass"] == []


@pytest.mark.parametrize("nid", ["n04_requirements", "n09_visual_system", "n10_prototype_planning",
                                 "n11_prototype_development", "n12_content_data", "n15_feasibility_review",
                                 "n16_feedback_diagnosis", "n18_final_verification"])
def test_re_checking_a_last_pass_changes_neither_the_state_nor_the_project(eng, nid):
    """Review C1/R2: the re-check runs on a copy of the outputs, in a temp folder, and puts the state back."""
    before = eng.state.model_dump_json()
    files = sorted(str(p) for p in eng.project.root.rglob("*") if p.is_file())
    assert eng._recheck_last_pass(eng.node(nid)) == []
    assert eng.state.model_dump_json() == before
    assert sorted(str(p) for p in eng.project.root.rglob("*") if p.is_file()) == files


def test_a_parked_builder_submission_goes_to_its_next_attempt_not_the_bin(tmp_path, monkeypatch):
    """Review I1: the refusal said "submit first … parked, not lost", then accept discarded a non-reviewer's parked
    output. It is now handed to the node's next attempt, and its packet lists the files."""
    import pdg.tools.browser as browser_mod
    from pdg.engine import EngineError
    from .conftest import fake_browser
    from .test_audit_coverage import _submit_fixture
    monkeypatch.setattr(browser_mod, "check", fake_browser)
    eng, node = _reviewer_waiting_under_drift(tmp_path, reviewer="n09_visual_system")
    with pytest.raises(EngineError, match="handed to the node's next attempt"):
        eng.accept_config("Wei", "rubric change")
    assert _submit_fixture(eng, node)["parked"]
    assert eng.config_impact()["parked_fate"][node] == "outputs handed to its next attempt"
    parked_attempt = eng.rt(node).attempt
    eng.accept_config("Wei", "rubric change")
    ev = list(eng.ledger.events("parked_resolved"))[-1]["data"]
    assert ev["carried"] and not ev["discarded"] and ev["reason"] == "configuration accepted"
    assert eng.rt(node).carried["attempt"] == parked_attempt
    from pdg.executors import TaskPacketExecutor
    eng.executor = TaskPacketExecutor()
    eng.run(max_steps=20)
    assert eng.rt(node).attempt > parked_attempt   # re-dispatched: the parked folder is no longer the current attempt
    assert f"work/{node}/a{parked_attempt}" not in {r for r, _ in eng.archive_candidates()}
    md = (eng.project.root / ".pdg" / "tasks" / f"{node}-a{eng.rt(node).attempt}.md").read_text()
    assert "## Your parked submission" in md and f"work/{node}/a{parked_attempt}/" in md


def test_an_invalidation_while_blocked_records_a_parked_review_instead_of_dropping_it(tmp_path, monkeypatch):
    """Review I2: `invalidate` cleared a parked submission with no ledger event, so a reviewer's findings vanished."""
    import json as _json
    import pdg.tools.browser as browser_mod
    from .conftest import fake_browser
    from .test_audit_coverage import FIXTURES, _fixture, _submit_fixture
    monkeypatch.setattr(browser_mod, "check", fake_browser)
    eng, reviewer = _reviewer_waiting_under_drift(tmp_path)
    fx, _ = _fixture(FIXTURES, reviewer, eng.rt(reviewer).attempt)
    review = _json.loads((fx / "review.json").read_text())
    review["findings"] = [{"dimension": "TEC-QUALITY", "severity": "P3", "message": "two decoders", "location": "x",
                           "by": "agent"}]
    assert _submit_fixture(eng, reviewer, replace={"review.json": _json.dumps(review)})["parked"]
    eng.invalidate_nodes(["n11_prototype_development"], "rebuild", "Wei")
    ev = list(eng.ledger.events("parked_resolved"))[-1]["data"]
    assert ev["node"] == reviewer and ev["reason"].startswith("invalidated") and ev["recorded_as_feedback"]
    assert any("two decoders" in f.text for f in eng.state.evaluation.feedback)


def test_a_parked_output_edited_after_parking_is_neither_recorded_nor_carried(tmp_path, monkeypatch):
    """Review S1: parking kept only the paths, so a file edited afterwards became the record."""
    import json as _json
    import pdg.tools.browser as browser_mod
    from pathlib import Path
    from .conftest import fake_browser
    from .test_audit_coverage import _submit_fixture
    monkeypatch.setattr(browser_mod, "check", fake_browser)
    eng, reviewer = _reviewer_waiting_under_drift(tmp_path)
    assert _submit_fixture(eng, reviewer)["parked"]
    path = Path(eng.rt(reviewer).parked["outputs"]["feasibility_review"])
    doc = _json.loads(path.read_text())
    doc["findings"] = [{"dimension": "TEC-QUALITY", "severity": "P1", "message": "added later", "location": "x", "by": "agent"}]
    path.write_text(_json.dumps(doc))
    assert eng.config_impact()["parked_fate"][reviewer].startswith("edited after parking (feasibility_review)")
    out = eng.accept_config("Wei", "rubric change")
    ev = list(eng.ledger.events("parked_resolved"))[-1]["data"]
    assert ev["discarded"] and not ev["carried"] and not out["parked_findings"]
    assert not any("added later" in f.text for f in eng.state.evaluation.feedback)


def test_a_rollback_hands_a_parked_submission_to_the_next_attempt(tmp_path, monkeypatch):
    """Review I2: a rollback replaced the state, and a parked submission with it."""
    import pdg.tools.browser as browser_mod
    from .conftest import fake_browser
    from .test_audit_coverage import _submit_fixture
    monkeypatch.setattr(browser_mod, "check", fake_browser)
    eng, node = _reviewer_waiting_under_drift(tmp_path, reviewer="n09_visual_system")
    assert _submit_fixture(eng, node)["parked"]
    seq = eng.state.history.checkpoints[-2].seq
    eng.rollback(seq, "Wei")
    ev = list(eng.ledger.events("parked_resolved"))[-1]["data"]
    assert ev["carried"] and ev["reason"] == f"rolled back to checkpoint {seq}"
    assert eng.rt(node).carried and eng.rt(node).parked is None


def test_archive_takes_only_attempt_folders_keeps_its_folder_inside_the_destination_and_restore_never_overwrites(
        eng, tmp_path):
    """Review I3, S5, S6: `glob("*/a*")` moved a builder's `app-src`; a project id with `../` left the destination;
    restore.sh nested a folder into one already back; a rollback named only the latest archive."""
    import subprocess
    from pathlib import Path
    import pytest
    from pdg.engine import EngineError
    from pdg.models import ArtifactRecord, CheckpointRef, ProjectState
    src = eng.project.root / "work" / "n11_prototype_development" / "app-src"
    (src / "src").mkdir(parents=True)
    (src / "src" / "App.jsx").write_text("export default () => null")
    assert "work/n11_prototype_development/app-src" not in {r for r, _ in eng.archive_candidates()}
    eng.state.project.id = "../../escape me"
    cands = eng.archive_candidates()
    first, (moved_last, _) = cands[:-1], cands[-1]
    dest = Path(eng.archive(tmp_path / "arch", "Wei")["dest"])
    assert dest.parent == (tmp_path / "arch").resolve() and "escape-me" in dest.name and src.exists()
    (eng.project.root / moved_last).mkdir(parents=True)   # already back: restore must not nest into it
    r = subprocess.run(["bash", str(dest / "restore.sh")], capture_output=True, text=True)
    assert r.returncode == 1 and "already in the project" in r.stderr
    assert not (eng.project.root / moved_last / Path(moved_last).name).exists()
    (eng.project.root / moved_last).rmdir()
    assert first and all((eng.project.root / r).is_dir() for r, _ in first)   # every other folder went back first
    second = Path(eng.archive(tmp_path / "arch", "Wei")["dest"])            # those, again; the last stays in `dest`

    def needed(cp) -> set[str]:
        if not (eng.project.root / cp.path).is_file():
            return {"__checkpoint__"}
        old = ProjectState.model_validate(__import__("json").loads((eng.project.root / cp.path).read_text()))
        return {"/".join(Path(a.path).parts[:3]) for a in old.artifacts.values()
                if a.current and not (eng.project.root / a.path).exists()}
    holds = {str(d): set(eng._archived_folders(d)) for d in (dest, second)}
    for d in (dest, second):
        moved_checkpoints = __import__("json").loads((d / "manifest.json").read_text()).get("moved_checkpoints", [])
        if moved_checkpoints:
            holds[str(d)].add("__checkpoint__")
    old = eng.state.model_copy(deep=True)
    old.artifacts = {"x": ArtifactRecord(id="n/a9/x", key="x", node="n", attempt=9, kind="file",
                                         path=f"{moved_last}/only-here.txt", sha256="x", bytes=1,
                                         created="now", current=True)}
    cp_path = ".pdg/checkpoints/09999-only-one-archive.json"
    (eng.project.root / cp_path).write_text(old.model_dump_json())
    eng.state.history.checkpoints.append(CheckpointRef(seq=9999, event="test", node=None, path=cp_path, at="now"))
    with pytest.raises(EngineError) as one_archive:
        eng.rollback(9999, "Wei")
    assert str(dest) in str(one_archive.value) and str(second) not in str(one_archive.value)
    tried = 0
    for cp in eng.state.history.checkpoints:
        need = needed(cp)
        if not need:
            continue
        with pytest.raises(EngineError) as ei:
            eng.rollback(cp.seq, "Wei")
        named = set(str(ei.value).split("restore.sh` in ")[1].rstrip(")").split(", "))
        assert named == {d for d, folders in holds.items() if folders & need}, (cp.seq, named)
        tried += 1
    assert tried


def test_the_first_look_at_pdg_code_is_ledgered_and_a_submit_records_it_before_its_verdict(tmp_path, monkeypatch):
    """Review S4: the first observation logged nothing, so a live run's first deploy was never ledgered, and `submit`
    judged under new code before the event was written."""
    import pdg.tools.browser as browser_mod
    from .conftest import fake_browser
    from .test_audit_coverage import _submit_fixture
    monkeypatch.setattr(browser_mod, "check", fake_browser)
    eng, node = _reviewer_waiting_under_drift(tmp_path, reviewer="n09_visual_system")
    eng.state.runtime.config_parts = eng._config_files()
    eng.state.runtime.config_sha256 = eng._config_fingerprint()
    eng.state.runtime.code_parts = {}
    eng.save("t")
    seen = len(list(eng.ledger.events()))
    _submit_fixture(eng, node)                  # no step runs in between: the submit itself must note the code first
    events = [e["type"] for e in eng.ledger.events()][seen:]
    assert "code_recorded" in events and "node_submitted" in events
    assert events.index("code_recorded") < events.index("node_submitted")


def test_a_re_check_puts_back_any_state_a_tool_changes(eng, monkeypatch):
    """Review C1, the second guard: whatever a re-run check writes to the run's state is put back."""
    from pdg.context import CheckResult
    node = eng.node("n11_prototype_development")
    before = eng.state.model_dump_json()

    def meddling(fn, ctx):
        eng.state.runtime.rework_cycles += 7
        eng.state.evaluation.defects.clear()
        return CheckResult()
    monkeypatch.setattr(eng, "_call_tool", meddling)
    eng._recheck_last_pass(node)
    assert eng.state.model_dump_json() == before


def test_a_re_judged_packet_never_claims_checks_it_did_not_run(tmp_path):
    """Review S2: with nothing re-runnable (a gate, or no tool check without a browser) the packet said the last output
    "passes every tool check that can be re-run"."""
    import json as _json
    from pdg.engine import Engine
    from pdg.executors import TaskPacketExecutor, render_packet
    from .conftest import copy_example
    project = copy_example(tmp_path / "p")
    Engine(project, executor=TaskPacketExecutor()).run(max_steps=5)   # writes the first real packet
    base = _json.loads(next((project / ".pdg" / "tasks").glob("*.json")).read_text())
    none = render_packet({**base, "rejudge": {"changed": ["rubrics/gate.yaml"], "dims": [], "last_pass": [],
                                              "passed_attempt": 1, "rechecked": []}})
    section = none.split("## Re-judged under a new configuration")[1].split("\n## ")[0]
    assert "None of this node's checks could be re-run" in section and "passes" not in section
    ran = render_packet({**base, "rejudge": {"changed": ["rubrics/build.yaml"], "dims": [], "last_pass": [],
                                             "passed_attempt": 1, "rechecked": ["prototype:check_static"]}})
    assert "passes the tool checks re-run on it here (prototype:check_static)" in ran


# ------------------------------------------------------------------------------------------------ config batch 2
def _plan_doc():
    import json as _json
    from .conftest import EXAMPLE
    return _json.loads((EXAMPLE / "fixtures" / "n10_prototype_planning" / "attempt-2" / "plan.json").read_text())


def test_every_n08_focus_rule_is_traced_to_a_step_a_check_or_a_reason(eng):
    """N-22 (field run 2, R2-13): N08's focus rules need not reach the plan, so a build broke two and passed. PLN-FOCUS
    traces each rule to an `expect_focus` step, a browser focus check, or a stated out-of-scope reason."""
    from pdg.tools import plan as plan_tool
    from .conftest import FakeCtx

    def focus(doc):
        return plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-FOCUS"]
    doc = _plan_doc()
    assert focus(doc).passed, focus(doc).evidence
    doc["focus_trace"] = doc["focus_trace"][1:]
    o = focus(doc)
    assert not o.passed and "untraced" in o.evidence and "h1" in o.evidence
    doc = _plan_doc()
    doc["focus_trace"][0]["step"] = 1                                   # a step that is not an expect_focus
    assert "is not an `expect_focus` step" in focus(doc).evidence
    doc = _plan_doc()
    doc["focus_trace"][1]["covered_by"] = "A11Y-AXE"
    assert "covered_by must be one of" in focus(doc).evidence
    doc = _plan_doc()
    doc["focus_trace"][2] = {"rule": doc["focus_trace"][2]["rule"], "out_of_scope": "no form in this prototype",
                             "covered_by": "A11Y-FOCUS"}
    assert "exactly one of" in focus(doc).evidence
    doc = _plan_doc()
    doc["focus_trace"][2] = {"rule": doc["focus_trace"][2]["rule"], "out_of_scope": "no validation in this prototype"}
    assert focus(doc).passed


def test_an_empty_state_needs_its_way_back_in_the_plan(eng):
    """B-09 and R-UX-002 ("empty (with a way back)"): the suite can only press a way back the plan names."""
    from pdg.tools import plan as plan_tool
    from .conftest import FakeCtx
    doc = _plan_doc()
    assert plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-STATES"].passed
    next(s for s in doc["states"] if s["state"] == "empty").pop("recover")
    o = plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-STATES"]
    assert not o.passed and "queue:empty" in o.evidence and "recover" in o.evidence


def test_a_re_filed_open_defect_says_what_is_still_wrong_and_keeps_its_feedback(eng, tmp_path):
    """Field run W45: N16 re-filed the open D-078 with a new message (only the search's help still split an ID) and a
    feedback id, but the gate kept the v5 message, fixed since v6, and the release listed the defect by it."""
    _gate(eng, tmp_path, [_defect("n11_prototype_development")])
    d = _d(eng)
    first = d.message
    again = {**_defect("n11_prototype_development"), "message": "Only the search's no-match help still splits an ID",
             "evidence": "audit round 5", "from_feedback": ["FB-088"]}
    _gate(eng, tmp_path, [again])
    d = _d(eng)
    assert d.message == "Only the search's no-match help still splits an ID" and d.evidence == "audit round 5"
    assert any(first[:40] in h for h in d.history) and "FB-088" in d.feedback_ids


def test_a_ring_check_cannot_stand_for_where_focus_goes_and_a_rule_is_traced_once(eng):
    """Config batch 2 review I4: `covered_by: A11Y-FOCUS` satisfied "focus moves to the h1", recreating N-22's false
    pass; and a second trace for one rule silently replaced the first."""
    from pdg.tools import plan as plan_tool
    from .conftest import FakeCtx
    doc = _plan_doc()
    for t in doc["focus_trace"]:
        t.pop("scenario", None), t.pop("step", None)
        t["covered_by"] = "A11Y-FOCUS"
    o = plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-FOCUS"]
    assert not o.passed and "checks the focus indicator, not where focus goes" in o.evidence and "h1" in o.evidence
    assert "2 px focus ring" not in o.evidence.split("checks the focus indicator")[0].split(";")[-1]
    doc = _plan_doc()
    doc["focus_trace"].insert(0, {"rule": doc["focus_trace"][0]["rule"], "scenario": "S-01", "step": 1})
    o = plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-FOCUS"]
    assert not o.passed and "traced more than once" in o.evidence


def test_a_failed_visibility_step_says_what_the_page_shows(tmp_path):
    """Field run 2, R2-19: a mutant failed at `{"expect_hidden": "#headerBack"}` with only "Timeout 5000ms exceeded";
    the reader had to work out that the back button still showed."""
    import pytest
    pytest.importorskip("playwright")
    from .test_audit_browser import _thresholds, _write_html
    import pdg.tools.browser as browser
    entry = _write_html(tmp_path / "p.html", '<main data-screen="one"><button id="headerBack">Back</button>'
                                             '<p id="note" hidden>Saved</p></main>')
    t = _thresholds()
    t["step_timeout_ms"] = 400
    rep = browser.run_suite(entry, [{"id": "S-01", "flow_id": "F-01", "steps": [{"expect_hidden": "#headerBack"}]},
                                    {"id": "S-02", "flow_id": "F-01", "steps": [{"expect_visible": "#note"}]},
                                    {"id": "S-03", "flow_id": "F-01", "steps": [{"expect_visible": "#gone"}]}], [],
                            [{"id": "one", "route": ""}], [390], t, tmp_path / "run")
    errs = [s["error"] for s in rep["scenarios"]]
    assert "#headerBack is still visible after 0.4 s (expected hidden)" in errs[0], errs[0]
    assert "#note is on the page but not visible (1 match, none visible) after 0.4 s (expected visible)" in errs[1], errs[1]
    assert "#gone is not on the page after 0.4 s (expected visible)" in errs[2], errs[2]


def test_every_p0_acceptance_line_reaches_the_plan(eng):
    """Field run 2, R2-18: R-08 (P1) said the navigation uses four area names; no step or forbidden text checked it, the
    draft broke it twice and every gate passed. PLN-ACCEPTANCE traces each P0 line (R-SCP-007) once to an expectation
    step, a forbidden_text entry, a later check or a reason; an untraced P1 line is listed."""
    from pdg.tools import plan as plan_tool
    from .conftest import FakeCtx

    def acc(doc):
        return plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-ACCEPTANCE"]
    doc = _plan_doc()
    assert acc(doc).passed and acc(doc).evidence.startswith("9/9 P0 acceptance lines traced"), acc(doc).evidence
    doc["acceptance_trace"] = [t for t in doc["acceptance_trace"] if t["requirement"] != "R-03"]
    o = acc(doc)
    assert not o.passed and "untraced P0" in o.evidence and "R-03" in o.evidence
    doc = _plan_doc()
    r03 = next(t for t in doc["acceptance_trace"] if t["requirement"] == "R-03")
    r03["step"] = 1                                                     # a goto, not an expectation
    assert "is not an expectation" in acc(doc).evidence and not acc(doc).passed
    doc = _plan_doc()
    r08 = next(t for t in doc["acceptance_trace"] if t["requirement"] == "R-08")
    r08["covered_by"] = "A11Y-NOPE"
    assert "is not a MUST check that every build round runs" in acc(doc).evidence
    r08["covered_by"] = "PLN-SCENARIOS"                                 # the plan's own check is not a later one
    assert "is not a MUST check that every build round runs" in acc(doc).evidence
    doc = _plan_doc()
    r08 = next(t for t in doc["acceptance_trace"] if t["requirement"] == "R-08")
    r08.pop("covered_by")
    r08["forbidden_text"] = "http://"
    assert "is not in the plan's forbidden_text" in acc(doc).evidence
    doc["forbidden_text"] = ["http://"]
    assert acc(doc).passed
    doc = _plan_doc()
    doc["acceptance_trace"] = [t for t in doc["acceptance_trace"] if t["requirement"] != "R-09"]
    o = acc(doc)
    assert o.passed and "P1 lines untraced" in o.evidence and "R-09" in o.evidence


def test_the_plan_packet_gives_every_acceptance_line_verbatim_and_the_checks_it_may_name(tmp_path):
    """Batch 8b review C1: N10 was told to copy N04's acceptance lines verbatim but never received them."""
    import json as _json
    from pdg.engine import Engine
    from pdg.executors import TaskPacketExecutor
    from .conftest import copy_example
    from .test_audit_coverage import _PendingFor
    project = copy_example(tmp_path / "p")
    eng = Engine(project, executor=_PendingFor(project / "fixtures", {"n10_prototype_planning"}))
    eng.run(max_steps=200)
    assert eng.rt("n10_prototype_planning").status.value == "WAITING_AGENT"
    eng.executor = TaskPacketExecutor()
    ctx_packet = eng.task_packet(__import__("pdg.context", fromlist=["x"]).NodeContext(
        eng, eng.node("n10_prototype_planning"), eng.rt("n10_prototype_planning").attempt, tmp_path / "w", "t", ""))
    ac = ctx_packet["acceptance"]
    lines = {(x["requirement"], x["acceptance"]) for x in ac["lines"]}
    assert ("R-03", "Release is disabled with an 'unlocks when' reason otherwise") in lines
    assert ("R-09", "An empty result offers 'Reset filters'") in lines and len(lines) == 12
    assert "FUNC-OFFLINE" in ac["checks"] and "DES-DERIVATION" in ac["checks"]
    assert not {"PERF-LOAD", "RGN-TARGETED", "GAT-TRACE", "DES-TASTE"} & set(ac["checks"])   # SHOULD, rework, gate, human
    from pdg.executors import render_packet
    md = render_packet(ctx_packet)
    assert "## Before you submit: the acceptance lines to trace" in md and "**R-03** (P0) Release is disabled" in md
    assert "state:product.requirements" in eng.node("n10_prototype_planning").inputs
    assert _json.loads(_json.dumps(ctx_packet, default=str))["acceptance"]["lines"]


def test_an_acceptance_copy_that_differs_only_in_case_spacing_quotes_or_a_full_stop_still_traces(eng):
    """Batch 8b review I1: exact matching failed a P0 line over a curly quote or a trailing full stop, and blamed N04."""
    from pdg.tools import plan as plan_tool
    from .conftest import FakeCtx
    doc = _plan_doc()
    for t in doc["acceptance_trace"]:
        if t["requirement"] == "R-03":
            t["acceptance"] = "release is  disabled with an \u2018unlocks when\u2019 reason otherwise."
    o = plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-ACCEPTANCE"]
    assert o.passed and "match no N04" not in o.evidence, o.evidence
    doc["acceptance_trace"][0]["acceptance"] = "Something N04 never said"
    o = plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-ACCEPTANCE"]
    assert not o.passed and "match no N04 acceptance line (check the wording against the packet)" in o.evidence


def test_covered_by_names_only_a_must_check_every_round_runs_and_that_reviewer_is_told(eng):
    """Batch 8b review I2: any of 53 later checks passed, a SHOULD, a rework-only and a release check included, and no
    node read the trace. Now only MUST checks of the build, content and review nodes count, and each reviewer's packet
    lists the lines the plan traced to its dimensions."""
    from pdg.tools import plan as plan_tool
    from pdg.artifacts import PrototypePlan
    from .conftest import FakeCtx
    doc = _plan_doc()
    r08 = next(t for t in doc["acceptance_trace"] if t["requirement"] == "R-08")
    for bad in ("PERF-LOAD", "RGN-TARGETED", "REL-LEDGER", "BLD-REPRO"):
        r08["covered_by"] = bad
        o = plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-ACCEPTANCE"]
        assert not o.passed and "is not a MUST check that every build round runs" in o.evidence, (bad, o.evidence)
    eng.state.build.plan = PrototypePlan.model_validate(_plan_doc())
    owed = eng._acceptance_owed(eng.node("n13_quality_review"))
    assert {(x["requirement"], x["check"]) for x in owed} >= {("R-02", "DES-DERIVATION"), ("R-08", "FUNC-OFFLINE"),
                                                             ("R-07", "DES-SCOPE-VISIBLE")}
    assert not eng._acceptance_owed(eng.node("n15_feasibility_review"))


def test_acceptance_edge_cases_are_named_not_failed(eng):
    """Batch 8b review suggestions: a line repeated in one requirement is traced once; a blank line is N04's to fix; a
    trace for a P2 line is optional, not stale; exactly one way, and a reason is never empty."""
    from pdg.tools import plan as plan_tool
    from .conftest import FakeCtx
    reqs = eng.state.product.requirements
    r03 = next(r for r in reqs if r.id == "R-03")
    r03.acceptance = list(r03.acceptance) + [r03.acceptance[0] + ".", "   "]
    r09 = next(r for r in reqs if r.id == "R-09")
    r09.priority = "P2"
    assert [x["requirement"] for x in plan_tool.acceptance_lines(reqs)].count("R-03") == 1   # the packet lists it once
    doc = _plan_doc()
    o = plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-ACCEPTANCE"]
    assert o.passed and "traces for P2 lines (optional)" in o.evidence and "R-09" in o.evidence, o.evidence
    r08 = next(t for t in doc["acceptance_trace"] if t["requirement"] == "R-08")
    r08["out_of_scope"] = "also"
    assert "give exactly one of" in plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-ACCEPTANCE"].evidence
    r08.pop("covered_by")
    r08["out_of_scope"] = "  "
    assert "an empty out_of_scope reason" in plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions[
        "PLN-ACCEPTANCE"].evidence
    doc = _plan_doc()
    doc["acceptance_trace"].append(dict(next(t for t in doc["acceptance_trace"] if t["requirement"] == "R-03")))
    o = plan_tool.check(FakeCtx({"plan": doc}, state=eng.state)).dimensions["PLN-ACCEPTANCE"]
    assert not o.passed and "traced more than once" in o.evidence


def test_a_hidden_first_match_says_to_scope_the_selector(tmp_path):
    """Batch 8b review I3: with a hidden first copy and a visible second one (R2-11's case) the message said the element
    was not visible, pointing the builder at the page instead of the plan's selector."""
    import pytest
    pytest.importorskip("playwright")
    from .test_audit_browser import _thresholds, _write_html
    import pdg.tools.browser as browser
    entry = _write_html(tmp_path / "p.html", '<main data-screen="one"><div hidden><button class="save">Save</button></div>'
                                             '<button class="save">Save</button><p class="x">x</p><p class="x">y</p></main>')
    t = _thresholds()
    t["step_timeout_ms"] = 400
    rep = browser.run_suite(entry, [{"id": "S-01", "flow_id": "F-01", "steps": [{"expect_visible": ".save"}]},
                                    {"id": "S-02", "flow_id": "F-01", "steps": [{"expect_hidden": ".x"}]}], [],
                            [{"id": "one", "route": ""}], [390], t, tmp_path / "run")
    e1, e2 = (s["error"] for s in rep["scenarios"])
    assert "matched 2 times; the first match is hidden and 1 other(s) are visible, so scope the selector" in e1, e1
    assert ".x is still visible (the first of 2 matches; 2 visible)" in e2, e2


def test_a_project_declares_its_reference_build_and_the_suite_receives_it(tmp_path):
    """N-28: `reference:` in pdg.project.yaml is a key pdg reads (an unknown key refuses the run), resolved against the
    project, and handed to the browser suite."""
    from types import SimpleNamespace
    from pdg.engine import Project
    from pdg.tools import browser
    root = tmp_path / "proj"
    (root / "ref").mkdir(parents=True)
    (root / "ref" / "index.html").write_text("<h1>Reference</h1>")
    (root / "pdg.project.yaml").write_text("id: x\nname: x\nreference: {entry: ref/index.html, routes: {queue: '#/q'}}\n")
    project = Project(root)
    assert not project.unknown_keys()
    got = browser._reference(SimpleNamespace(engine=SimpleNamespace(project=project)))
    assert got == {"entry": str(root.resolve() / "ref" / "index.html"), "routes": {"queue": "#/q"}, "expected": []}
    assert browser._reference(SimpleNamespace(engine=SimpleNamespace(project=SimpleNamespace(root=root, config={})))) is None


def test_a_malformed_reference_declaration_fails_parity_only(tmp_path):
    """N-28 review I2: `routes: ['queue']` raised ValueError out of `check()`, losing every browser dimension."""
    from types import SimpleNamespace
    import pytest
    from pdg.tools import browser
    (tmp_path / "r.html").write_text("<h1>r</h1>")
    for bad in ({"entry": "r.html", "routes": ["queue"]}, {"entry": "r.html", "routes": "#/q"}, {"routes": {}},
                {"entry": "r.html", "routes": {"lot": 5}},
                {"entry": "r.html", "expected": [{"property": "colour", "reason": "x"}]},
                {"entry": "r.html", "expected": [{"property": "title"}]}):
        ctx = SimpleNamespace(engine=SimpleNamespace(project=SimpleNamespace(root=tmp_path, config={"reference": bad})))
        with pytest.raises(ValueError):
            browser._reference(ctx)
    ok = {"entry": "r.html", "routes": {"lot": None}, "expected": [{"property": "title", "reason": "new scale"}]}
    ctx = SimpleNamespace(engine=SimpleNamespace(project=SimpleNamespace(root=tmp_path, config={"reference": ok})))
    assert browser._reference(ctx)["routes"] == {"lot": None}


def test_an_obscured_focus_stop_that_nothing_covers_is_named_off_screen(tmp_path):
    """Field run 2, R2-22: a script scrolled the page after each focus move, so the stop ended below the viewport with
    nothing over it; the finding named no cover and the cause took an instrumented replay."""
    import pytest
    pytest.importorskip("playwright")
    from .test_browser import _suite_for_html
    res = _suite_for_html(tmp_path, """<!doctype html><html><head><style>body{margin:0} main{height:4000px}
.far{position:absolute;top:30px;left:20px}</style></head><body><main data-screen="home"><a class="far" href="#x">Stop</a></main>
<script>document.addEventListener('focusin', () => setTimeout(() => window.scrollTo(0, 3000), 0));</script></body></html>""",
                          [1024])
    o = res.dimensions["A11Y-FOCUS-VISIBLE-2411"]
    msg = " ".join(f["message"] for f in o.findings)
    assert not o.passed and "off-screen after focus: the page scrolled it away" in msg and "covered by" not in msg, msg


def test_every_focus_stop_a_timer_scrolls_away_is_read_hidden(tmp_path):
    """R2-22 hardening: the walk waited 10 ms in the driver before each read, and about a third of the reads ran before
    the page's own scroll timer, so the stop read as shown (the test above failed on a loaded machine when both of its
    directions lost that race). The 10 ms are now timed in the page, after the timers the key press set."""
    import pytest
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright
    from pdg.tools import browser
    entry = tmp_path / "p.html"
    entry.write_text("""<!doctype html><html><head><style>body{margin:0} main{height:4000px}</style></head><body><main>"""
                     + "".join(f'<a href="#s{i}">Stop {i}</a><br>' for i in range(20)) + """</main>
<script>document.addEventListener('focusin', (e) => {
  if (e.target.tagName === 'A') setTimeout(() => window.scrollTo(0, 3000), 0);
});</script></body></html>""")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            if "Executable doesn't exist" in str(exc):
                pytest.skip("Chromium is not installed (python -m playwright install chromium)")
            raise
        try:
            page = b.new_page(viewport={"width": 1024, "height": 768})
            page.goto(entry.as_uri())
            hidden = browser._focus_obscured(page, 60)
        finally:
            b.close()
    assert len(hidden) == 40 and all(h["offscreen"] for h in hidden), [(h["direction"], h["text"]) for h in hidden]


def test_a_new_defect_id_is_never_one_already_used_and_a_duplicate_is_repaired(eng, tmp_path):
    """Field run W46: the gate numbered a tool defect D-{count+1}; with a gap in the numbering that was the id the
    interpreter had just used, and the run held two D-179s. Ids now come from the highest in use, never reuse one the
    interpretation reserves, and a run that already holds a duplicate gets the later one renumbered, recorded."""
    from pdg.gating import _next_defect_id
    from pdg.models import Defect
    ev = eng.state.evaluation
    base = dict(signature="X@y", dimension="FUNC-STATES", severity="P2", message="m", evidence="e", traced_node="n11_prototype_development",
                trace_reason="t", smallest_fix="f", acceptance_check="c", opened_at_version=1)
    ev.defects = [Defect(id="D-001", **base), Defect(id="D-005", **base)]
    assert _next_defect_id(ev.defects) == "D-006"
    assert _next_defect_id(ev.defects, {"D-006", "D-007"}) == "D-008"
    ev.defects.append(Defect(id="D-005", **{**base, "signature": "FUNC-STATES@shell"}))
    eng.save("t")
    eng._repair_duplicate_defect_ids()
    ids = [d.id for d in ev.defects]
    assert ids == ["D-001", "D-005", "D-006"] and "renumbered D-005 → D-006" in ev.defects[2].history[-1]
    assert list(eng.ledger.events("defect_renumbered"))[-1]["data"] == {"old": "D-005", "new": "D-006",
                                                                          "signature": "FUNC-STATES@shell"}


def test_the_gate_numbers_a_tool_defect_past_the_interpretations_ids(eng, tmp_path):
    """W46 end to end: a gap in the numbering, the interpreter files the next ids, and the same gate maps a blocking
    tool finding. Every defect id stays unique."""
    ev = eng.state.evaluation
    ev.defects = ev.defects[1:]            # a gap of one below the highest id: the count-based id lands on the interpreter's
    n = max(int(d.id[2:]) for d in ev.defects)
    assert n == len(ev.defects) + 1
    eng.rt("n13_quality_review").attempt += 1      # a newer review than the finished run's, so the gate reads it
    _review_now(eng, [__import__("pdg.models", fromlist=["x"]).FindingRecord(
        node="n13_quality_review", dimension="FUNC-STATES", severity="P1", message="panel rebuilt", location="shell",
        by="tool", traced_node="n11_prototype_development", blocking=True)])
    mine = [_defect("n11_prototype_development", f"DES-CONSISTENCY@feeds{i}") | {"id": f"D-{n + i:03d}"} for i in (1, 2)]
    _gate(eng, tmp_path, mine)
    ids = [d.id for d in eng.state.evaluation.defects]
    assert any(d.signature == "FUNC-STATES@shell" for d in eng.state.evaluation.defects)   # the tool defect was filed
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]


def test_re_running_intake_after_the_freeze_reopens_the_inputs_and_n02_refreezes_them(eng):
    """Field run W48 (a blocker): N01 re-ran after N02 had frozen the inputs, to register new sources. Its write tripped
    the frozen-input check, which escalated the run before N02 could run, and only N02's pass re-freezes: a deadlock.
    The freeze now holds only while N02 stands passed; the step reopens the inputs, ledgered, and N02 re-freezes them."""
    from pdg.artifacts import Source
    root = eng.project.root
    before = eng.state.inputs.inputs_sha256
    assert eng.state.inputs.frozen
    (root / "sources" / "field-verification.md").write_text("# Field verification\n\nThe demo's checks, as run on site.\n")
    eng.invalidate_nodes(["n02_evidence_review"], "N01 registered new sources", "Wei")
    # what N01's re-pass writes (state_write: inputs.sources), while the old freeze still stands
    eng.state.inputs.sources.append(Source(id="S-99", kind="other", title="Field verification",
                                           path="sources/field-verification.md", evidence="observed"))
    eng.save("n01 re-registered the sources")
    assert eng._inputs_sha() != before                     # what the old check called tampering
    eng.run(max_steps=400)
    assert eng.state.runtime.status.value != "BLOCKED", [e.reason[:160] for e in eng.state.runtime.escalations if e.open]
    reopened = list(eng.ledger.events("inputs_reopened"))
    assert reopened and reopened[-1]["data"]["node"] == "n02_evidence_review" and reopened[-1]["data"]["sha256"] == before
    assert eng.state.inputs.frozen and eng.rt("n02_evidence_review").status.value == "PASSED"
    assert eng.state.inputs.inputs_sha256 == eng._inputs_sha()


def test_a_button_below_its_dialogs_visible_box_is_not_in_view(tmp_path):
    """Field run 2, R2-23: a dialog's Create button sat 219 px below the dialog's visible box, and S-07's
    `expect_visible` passed. `expect_in_viewport` now also needs the element inside every scrolling container around it,
    and says which one hides it."""
    import pytest
    pytest.importorskip("playwright")
    from .test_audit_browser import _thresholds, _write_html
    import pdg.tools.browser as browser
    entry = _write_html(tmp_path / "p.html", "<main data-screen='one'><div role='dialog' style='position:fixed;top:40px;"
                        "left:40px;width:400px;height:300px;display:flex;flex-direction:column'><h2>New case</h2>"
                        "<div class='dlg-body' style='overflow:auto;flex:1'><p style='height:600px'>Form</p>"
                        "<button id='create'>Create</button></div><div class='foot'><button id='cancel'>Cancel</button>"
                        "</div></div></main>")
    t = _thresholds()
    t["step_timeout_ms"] = 400
    rep = browser.run_suite(entry, [{"id": "S-01", "flow_id": "F-01", "steps": [{"expect_in_viewport": "#create"}]},
                                    {"id": "S-02", "flow_id": "F-01", "steps": [{"expect_in_viewport": "#cancel"}]}], [],
                            [{"id": "one", "route": ""}], [1440], t, tmp_path / "run")
    s1, s2 = rep["scenarios"]
    assert not s1["passed"] and "#create is not in view without scrolling: outside div.dlg-body, which shows" in s1["error"], s1
    assert s2["passed"], s2


def test_a_reference_in_the_sources_but_not_declared_is_named(tmp_path):
    """Field run 2, R2-25: a refresh kept its reference builds in sources/references/ and REF-PARITY printed PASS,
    "nothing to compare"."""
    from types import SimpleNamespace
    import yaml
    from pdg.context import CheckResult
    from pdg.tools import browser
    from .conftest import PKG
    (tmp_path / "sources" / "references" / "hub").mkdir(parents=True)
    (tmp_path / "sources" / "references" / "hub" / "index.html").write_text("<h1>hub</h1>")
    ctx = SimpleNamespace(engine=SimpleNamespace(project=SimpleNamespace(root=tmp_path, config={})))
    assert browser._reference_hint(ctx) == "sources/references/hub/index.html"
    rep = {"reference": None, "reference_hint": "sources/references/hub/index.html", "scenarios": [], "states": [],
           "screens": [], "axe": [], "reflow_320": [], "reduced_motion": [], "console": [], "requests": [], "timing_ms": [],
           "forbidden_text": [], "tokens": [], "parity": [], "band": [], "band_step": 20}
    res = CheckResult()
    browser.findings_from(rep, yaml.safe_load((PKG / "config" / "defaults.yaml").read_text())["thresholds"]["browser"], res)
    o = res.dimensions["REF-PARITY"]
    assert not o.passed and "is in the sources (sources/references/hub/index.html) but not declared" in o.evidence
    assert browser._reference_hint(SimpleNamespace(engine=SimpleNamespace(project=SimpleNamespace(root=tmp_path / "x",
                                                                                                 config={})))) is None
