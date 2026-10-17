"""The command line, driven the way a real project uses it: init → brief → run issues a task packet → an agent submits
→ the engine advances. Refusals change nothing and return their documented exit codes (0 · 1 · 2 · 3 · 4)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

from pdg.cli import main
from pdg.engine_common import _package_state_file, package_git_state

from .conftest import PKG

SOURCES = {"sources": [{"id": "S-01", "kind": "brief", "title": "Brief", "path": "sources/brief.md", "evidence": "reported"}],
           "open_questions": []}


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _packet(project, node):
    return json.loads(sorted((project / ".pdg" / "tasks").glob(f"{node}-a*.json"))[-1].read_text())


def test_validate_and_docs_check_pass(capsys):
    assert main(["validate"]) == 0
    assert "graph valid: 19 nodes" in capsys.readouterr().out
    assert main(["docs", "--check"]) == 0


def test_a_real_project_runs_through_task_packets_and_refusals_change_nothing(tmp_path, capsys):
    proj = tmp_path / "demo"
    assert main(["init", str(proj), "--name", "Demo product"]) == 0
    assert (proj / "pdg.project.yaml").exists() and len(list((proj / "controls").glob("*.md"))) == 8
    assert main(["run", str(proj)]) == 4                                   # the brief is still the template
    assert "brief" in capsys.readouterr().out and not (proj / ".pdg" / "state.json").exists()

    (proj / "sources" / "brief.md").write_text("# Brief\n\nA field technician logs a meter reading offline and syncs later.\n")
    assert main(["run", str(proj)]) == 0
    assert "WAITING_AGENT" in capsys.readouterr().out
    pk = _packet(proj, "n01_context_intake")
    md = (proj / ".pdg" / "tasks" / "n01_context_intake-a1.md").read_text()
    assert pk["token"] in md and "python -B -m pdg submit" in md and "EVD-SOURCES" in md

    state, ledger = proj / ".pdg" / "state.json", proj / ".pdg" / "ledger.jsonl"
    before = (_sha(state), _sha(ledger))
    work = proj / "work" / "n01_context_intake" / "a1"
    assert work.is_dir()                                                   # the engine prepared it
    (work / "sources.json").write_text(json.dumps(SOURCES))
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(SOURCES))
    base = ["submit", str(proj), "n01_context_intake", "--actor", "agent:context-research"]
    assert main(base + ["--token", "stale", "--output", "sources=sources.json"]) == 4
    assert main(base + ["--token", pk["token"], "--output", f"sources={outside}"]) == 4
    assert main(base + ["--token", pk["token"], "--output", "nope=sources.json"]) == 4
    assert main(["approve", str(proj), "n03_problem_definition", "--actor", "agent:x", "--reason", "r"]) == 4
    assert main(["status", str(proj)]) == 0 and main(["tasks", str(proj)]) == 0
    assert (_sha(state), _sha(ledger)) == before                          # refusals and reads wrote nothing

    assert main(base + ["--token", pk["token"], "--output", "sources=sources.json"]) == 0
    capsys.readouterr()
    assert main(["status", str(proj), "--json"]) == 0
    s = json.loads(capsys.readouterr().out)
    assert s["nodes"]["n01_context_intake"]["status"] == "PASSED" and s["waiting_agent"] == ["n02_evidence_review"]
    assert main(["ledger-verify", str(proj)]) == 0

    lines = ledger.read_text().splitlines()
    ev = json.loads(lines[2])
    ev["data"]["tampered"] = True
    lines[2] = json.dumps(ev)
    ledger.write_text("\n".join(lines) + "\n")
    assert main(["ledger-verify", str(proj)]) == 1


def test_check_node_runs_submission_checks_without_spending_attempt_or_writing_pdg(tmp_path, capsys):
    proj = tmp_path / "demo"
    assert main(["init", str(proj), "--name", "Demo product"]) == 0
    (proj / "sources" / "brief.md").write_text("# Brief\n\nA field technician logs a meter reading offline.\n")
    staged = proj / "staged"
    staged.mkdir()
    (staged / "sources.json").write_text(json.dumps(SOURCES))
    assert main(["run", str(proj)]) == 0
    capsys.readouterr()
    state = proj / ".pdg" / "state.json"
    ledger = proj / ".pdg" / "ledger.jsonl"
    before = (_sha(state), _sha(ledger))
    packet = _packet(proj, "n01_context_intake")
    assert main(["check-node", str(proj), "n01_context_intake", "--output", f"sources={staged / 'sources.json'}"]) == 0
    out = capsys.readouterr().out
    assert f"sources={staged / 'sources.json'}" in out and "would block 0 · advisory 0 · deferred 0" in out
    assert (_sha(state), _sha(ledger)) == before
    assert packet["token"] == _packet(proj, "n01_context_intake")["token"]


def test_check_node_refusals_exit_4_and_advisories_are_submission_local(tmp_path, capsys):
    from pdg.engine import Engine
    from pdg.models import Defect
    proj = tmp_path / "demo"
    assert main(["init", str(proj), "--name", "Demo product"]) == 0
    (proj / "sources" / "brief.md").write_text("# Brief\n\nA field technician logs a meter reading offline.\n")
    assert main(["run", str(proj)]) == 0
    assert main(["check-node", str(proj), "n01_context_intake"]) == 4
    assert "missing required output" in capsys.readouterr().out
    eng = Engine(proj)
    eng.state.evaluation.defects.append(Defect(id="D-999", signature="VIS-NIT@home", dimension="VIS-NIT", severity="P4",
                                               message="cheap polish", evidence="", traced_node="n11_prototype_development",
                                               trace_reason="review", smallest_fix="polish", acceptance_check="looks ok"))
    eng.save("test")
    staged = proj / "staged"
    staged.mkdir()
    (staged / "sources.json").write_text(json.dumps(SOURCES))
    assert main(["check-node", str(proj), "n01_context_intake", "--output", f"sources={staged / 'sources.json'}"]) == 0
    assert "would block 0 · advisory 0" in capsys.readouterr().out


def test_check_node_releases_project_lock_while_checks_run(tmp_path, monkeypatch):
    import pdg.check_node as cn
    from pdg.lock import holder, project_lock_path
    proj = tmp_path / "demo"
    assert main(["init", str(proj), "--name", "Demo product"]) == 0
    (proj / "sources" / "brief.md").write_text("# Brief\n\nA field technician logs a meter reading offline.\n")
    assert main(["run", str(proj)]) == 0

    def fake_check(eng, node, outputs):
        assert holder(project_lock_path(proj)) is None
        return {"ok": True, "refused": [], "failures": [], "advisory": [], "deferred": [], "dimensions": {},
                "resolved": outputs, "command": "python -m pdg submit demo n01_context_intake"}

    monkeypatch.setattr(cn, "check_node", fake_check)
    assert main(["check-node", str(proj), "n01_context_intake"]) == 0


def test_check_output_project_interpretation_is_read_only_and_does_not_open_engine(tmp_path, monkeypatch, capsys):
    proj = tmp_path / "demo"
    assert main(["init", str(proj), "--name", "Demo product"]) == 0
    (proj / "sources" / "brief.md").write_text("# Brief\n\nA technician logs readings.\n")
    assert main(["run", str(proj)]) == 0
    interp = tmp_path / "interpretation.json"
    interp.write_text(json.dumps({"defects": [], "feedback": [], "answered_findings": [], "summary": "none yet"}))
    import pdg.cli as cli
    monkeypatch.setattr(cli, "_engine", lambda project: (_ for _ in ()).throw(AssertionError("Engine opened")))
    assert main(["check-output", "n16_feedback_diagnosis", "interpretation", str(interp), "--project", str(proj)]) == 0
    assert "ok:" in capsys.readouterr().out


def test_revise_brief_requires_human_authority_and_restores_file_on_failed_save(tmp_path):
    from pdg.engine import Engine
    proj = tmp_path / "demo"
    assert main(["init", str(proj), "--name", "Demo product"]) == 0
    old = "# Brief\n\nOld request.\n"
    (proj / "sources" / "brief.md").write_text(old)
    eng = Engine(proj)
    src = tmp_path / "new.md"
    src.write_text("# Brief\n\nNew request.\n")
    try:
        eng.revise_brief(src, "agent:orchestrator", "new stakeholder words")
    except Exception as exc:
        assert "delegation" in str(exc) or "named human" in str(exc)
    else:
        raise AssertionError("agent revised the brief without authority")
    eng = Engine(proj)
    def fail_write():
        raise RuntimeError("simulated failed save")
    eng._write_state = fail_write
    try:
        eng.revise_brief(src, "Wei", "new stakeholder words")
    except RuntimeError:
        pass
    else:
        raise AssertionError("failed save did not propagate")
    assert (proj / "sources" / "brief.md").read_text() == old


def test_revise_brief_accepts_change_request_delegation(tmp_path):
    import datetime as dt
    from pdg.engine import Engine
    proj = tmp_path / "demo"
    assert main(["init", str(proj), "--name", "Demo product"]) == 0
    (proj / "sources" / "brief.md").write_text("# Brief\n\nOld request.\n")
    eng = Engine(proj)
    until = (dt.datetime.now(dt.UTC) + dt.timedelta(hours=1)).isoformat()
    eng.delegate("Wei", "agent:orchestrator", "Revise the brief for me.", ["change_request"], None, until)
    src = tmp_path / "new.md"
    src.write_text("# Brief\n\nNew request.\n")
    touched = eng.revise_brief(src, "agent:orchestrator", "new words", on_behalf_of="Wei")
    assert eng.state.inputs.brief == src.read_text()
    assert eng.ledger.events("brief_revised")
    assert "n02_evidence_review" in touched


def test_draft_interpretation_writes_schema_valid_output_and_sidecar(tmp_path, capsys):
    proj = tmp_path / "demo"
    assert main(["init", str(proj), "--name", "Demo product"]) == 0
    (proj / "sources" / "brief.md").write_text("# Brief\n\nA technician logs readings.\n")
    assert main(["run", str(proj)]) == 0
    out = tmp_path / "interpretation.json"
    assert main(["draft-interpretation", str(proj), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "finding sidecar:" in text
    assert (tmp_path / "interpretation.findings.json").is_file()
    assert main(["check-output", "n16_feedback_diagnosis", "interpretation", str(out), "--project", str(proj)]) == 0


def test_dispatch_moves_pre_staged_attempt_files_to_pre_dispatch(tmp_path, capsys):
    proj = tmp_path / "demo"
    assert main(["init", str(proj), "--name", "Demo product"]) == 0
    (proj / "sources" / "brief.md").write_text("# Brief\n\nA technician logs readings.\n")
    early = proj / "work" / "n01_context_intake" / "a1" / "sources.json"
    early.parent.mkdir(parents=True)
    early.write_text("{}")
    assert main(["run", str(proj)]) == 0
    out = capsys.readouterr().out
    kept = proj / "work" / "n01_context_intake" / "a1" / ".pre-dispatch" / "sources.json"
    assert kept.read_text() == "{}"
    assert "pre-dispatch" in out


def test_memory_commands_follow_governance(tmp_path, capsys):
    rules = tmp_path / "rules.json"
    shutil.copyfile(PKG / "knowledge" / "rules.json", rules)
    assert main(["memory", "status", "--rules", str(rules)]) == 0
    assert "seed approvals awaiting Wei's confirmation" in capsys.readouterr().out
    before = _sha(rules)
    assert main(["memory", "promote", "R-CBV-002", "--to", "approved", "--by", "agent:learning-curator", "--human",
                 "--rules", str(rules)]) == 3
    assert main(["memory", "confirm", "R-CBV-001", "--by", "agent:learning-curator", "--rules", str(rules)]) == 3
    assert main(["memory", "confirm", "--all-seed", "--by", "agent:learning-curator", "--rules", str(rules)]) == 3
    assert _sha(rules) == before
    v0 = json.loads(rules.read_text())["version"]
    assert main(["memory", "promote", "R-CBV-002", "--to", "approved", "--by", "Wei", "--human",
                 "--evidence", "review 2026-09-26", "--rules", str(rules)]) == 0
    assert json.loads(rules.read_text())["version"] != v0
    assert _sha(PKG / "knowledge" / "rules.json") != _sha(rules)          # the package's rule base is untouched


def test_dry_run_never_deletes_a_folder_it_did_not_create(tmp_path):
    keep = tmp_path / "notes"
    keep.mkdir()
    (keep / "important.md").write_text("keep me")
    assert main(["dry-run", "--out", str(keep)]) == 4
    assert (keep / "important.md").read_text() == "keep me"


def test_status_and_tasks_read_existing_state_without_git_state_key(tmp_path, capsys):
    proj = tmp_path / "existing"
    (proj / ".pdg" / "tasks").mkdir(parents=True)
    (proj / ".pdg" / "state.json").write_text(json.dumps({
        "project": {"id": "existing"},
        "build": {"version": 1, "prototype": {}},
        "runtime": {
            "status": "RUN_PASS", "batches": 1, "rework_cycles": 0,
            "nodes": {"n13_quality_review": {"status": "PASSED", "outcome": "pass", "attempt": 1,
                                             "passed_checks": {"code": "0" * 64, "config": "1" * 64}}},
            "escalations": []
        },
        "evaluation": {"defects": [], "gates": []},
        "history": {"delegations": [], "checkpoints": []}
    }))
    assert main(["status", str(proj)]) == 0
    assert "existing: RUN_PASS" in capsys.readouterr().out
    assert main(["tasks", str(proj)]) == 0
    assert "no open task packets" in capsys.readouterr().out


def test_package_git_state_reports_dirty_pdg_files_when_package_is_in_repo_subdir(tmp_path):
    repo = tmp_path / "repo"
    pkg = repo / "02_Workflows" / "prototype-design"
    (pkg / "pdg" / "tools").mkdir(parents=True)
    (pkg / "loop").mkdir()
    tracked = pkg / "pdg" / "tools" / "browser.py"
    tracked.write_text("print('clean')\n")
    (pkg / "loop" / "field-run-inbox.md").write_text("from: side chat\n")
    subprocess.run(["git", "-C", str(repo), "init"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, stdout=subprocess.DEVNULL)

    tracked.write_text("print('dirty')\n")
    (pkg / "loop" / "field-run-3-inbox.md").write_text("from: field chat\n")
    (pkg / "pdg" / "__pycache__").mkdir()
    (pkg / "pdg" / "__pycache__" / "module.cpython-311.pyc").write_bytes(b"cache")
    state = package_git_state(pkg)

    assert state is not None
    assert state["uncommitted_files"] == ["pdg/tools/browser.py"]
    assert state["diff_sha256"]
    assert _package_state_file("pdg/tools/browser.py")
    assert not _package_state_file("loop/field-run-inbox.md")
    assert not _package_state_file("pdg/__pycache__/module.cpython-311.pyc")


def test_package_git_state_never_fails_on_non_utf8_diffs(tmp_path):
    repo = tmp_path / "repo"
    pkg = repo / "pkg"
    (pkg / "pdg").mkdir(parents=True)
    target = pkg / "pdg" / "binary.py"
    target.write_bytes(b"clean = 'ok'\\n")
    subprocess.run(["git", "-C", str(repo), "init"], check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, stdout=subprocess.DEVNULL)

    target.write_bytes(b"bad = '\xff'\n")

    state = package_git_state(pkg)
    assert state and state["uncommitted_files"] == ["pdg/binary.py"] and state["diff_sha256"]


def test_package_git_state_never_fails_when_git_decode_raises(monkeypatch, tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()

    def boom(*args, **kwargs):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte")

    monkeypatch.setattr(subprocess, "run", boom)

    assert package_git_state(pkg) is None
