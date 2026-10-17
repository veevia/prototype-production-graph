from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import pdg.review as review_mod
from pdg.archive import plan
from pdg.cli import main, read_status
from pdg.engine import Engine
from pdg.engine_human import HumanActionsMixin
from pdg.models import Approval, ArtifactRecord, CheckpointRef, NodeStatus, ProjectState
from pdg.release_shelf import export, latest_release_path
from pdg.review import build, record
from pdg.privacy import privacy_path
from .conftest import copy_example


TENANT = privacy_path()


def _listed_product_word() -> str:
    words = json.loads(TENANT.read_text())["banned"]
    return next(w for w in words if "-" in w or " " in w)


def _separator_identifier_variant() -> str:
    data = json.loads(TENANT.read_text())
    banned = [str(w).lower() for group in ("preference_product_words", "banned", "whole_words")
              for w in data.get(group, [])]
    word = next(w for w in data["banned"]
                if " " in w and not any(b and b in w.replace(" ", "-").lower() for b in banned))
    return word.replace(" ", "-")


def _artifact(key: str, path: str, sha: str = "sha", attempt: int = 1) -> ArtifactRecord:
    return ArtifactRecord(id=f"n18_final_verification/{key}/a{attempt}", key=key, node="n18_final_verification",
                          attempt=attempt, kind="dir" if key == "package" else "markdown", path=path, sha256=sha,
                          bytes=1, created="2026-10-04T00:00:00Z", current=True)


def _state(package_sha: str = "pkg", summary_sha: str = "sum") -> ProjectState:
    package = _artifact("package", "work/n18_final_verification/a1/package", package_sha)
    summary = _artifact("release_summary", "work/n18_final_verification/a1/release-summary.md", summary_sha)
    state = ProjectState.model_validate({"schema_version": "t", "project": {
        "id": "demo", "name": "Demo", "created": "now", "workflow_id": "w", "workflow_version": "1"}})
    state.artifacts = {package.id: package, summary.id: summary}
    state.history.approvals.append(Approval(node="n18_final_verification", decision="approved", actor="agent:orchestrator",
                                            human=False, on_behalf_of="Wei", delegation="DL-004", reason="release",
                                            at="2026-10-04T12:00:00Z", build_version=3,
                                            outputs={"package": package_sha, "release_summary": summary_sha}))
    return state


def _add_release(state: ProjectState, version: int, attempt: int) -> None:
    package = _artifact("package", f"work/n18_final_verification/a{attempt}/package", f"pkg{version}", attempt)
    summary = _artifact("release_summary", f"work/n18_final_verification/a{attempt}/release-summary.md",
                        f"sum{version}", attempt)
    state.artifacts[package.id] = package
    state.artifacts[summary.id] = summary
    state.history.approvals.append(Approval(node="n18_final_verification", decision="approved", actor="Wei",
                                            human=True, reason=f"release v{version}", at=f"2026-10-0{version}T12:00:00Z",
                                            build_version=version,
                                            outputs={"package": package.sha256, "release_summary": summary.sha256}))


def test_release_shelf_exports_versions_latest_and_index(tmp_path):
    project = tmp_path / "p"
    pkg = project / "work/n18_final_verification/a1/package/prototype"
    pkg.mkdir(parents=True)
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\n")
    (pkg / "index.html").write_text("<h1>release</h1>")
    (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
        json.dumps({"files": {"prototype/index.html": "x"}}))
    (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")

    rows = export(project, _state())

    assert rows[0].version == 3
    assert (project / "releases/v3/prototype/index.html").read_text() == "<h1>release</h1>"
    assert (project / "releases/records/v3-release-summary.md").read_text() == "# Summary\n"
    assert (project / "releases/latest.html").is_symlink() is False
    index = (project / "RELEASES.md").read_text()
    assert "v3" in index and "Wei" in index and "DL-004" in index
    assert not (project / "releases/.pdg-release-owner.json").exists()


def test_in_project_shelf_survives_project_copy(tmp_path):
    project = tmp_path / "p"
    pkg = project / "work/n18_final_verification/a1/package/prototype"
    pkg.mkdir(parents=True)
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\n")
    (pkg / "index.html").write_text("<h1>release</h1>")
    (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
        json.dumps({"files": {"prototype/index.html": "x"}}))
    (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
    export(project, _state())
    import shutil
    copy = tmp_path / "copy"
    shutil.copytree(project, copy)

    export(copy, _state())

    assert (copy / "releases/v3/prototype/index.html").is_file()
    assert not (copy / "releases/.pdg-release-owner.json").exists()


def test_release_shelf_keeps_existing_copy_when_source_is_archived(tmp_path):
    project = tmp_path / "p"
    project.mkdir()
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\n")
    state = ProjectState.model_validate({"schema_version": "t", "project": {
        "id": "demo", "name": "Demo", "created": "now", "workflow_id": "w", "workflow_version": "1"}})
    _add_release(state, 1, 1)
    _add_release(state, 2, 2)
    _add_release(state, 3, 3)
    for attempt, text in ((1, "one"), (2, "two")):
        pkg = project / f"work/n18_final_verification/a{attempt}/package/prototype/dist"
        pkg.mkdir(parents=True)
        (pkg / "prototype.html").write_text(text)
        (project / f"work/n18_final_verification/a{attempt}/package/manifest.json").write_text(
            json.dumps({"files": {"prototype/dist/prototype.html": "x"}}))
        (project / f"work/n18_final_verification/a{attempt}/release-summary.md").write_text(f"# v{attempt}\n")
    export(project, state)
    shutil_copy = (project / "releases/v1/prototype/dist/prototype.html").read_text()
    assert shutil_copy == "one"
    shutil_path = project / "work/n18_final_verification/a1"
    import shutil
    shutil.rmtree(shutil_path)
    shutil.rmtree(project / "work/n18_final_verification/a3", ignore_errors=True)

    export(project, state)

    assert (project / "releases/v1/prototype/dist/prototype.html").read_text() == "one"
    releases = (project / "RELEASES.md").read_text()
    assert "v1" in releases and "v3" in releases and "archived; restore source package" in releases


def test_release_shelf_latest_prefers_dist_entry(tmp_path):
    project = tmp_path / "p"
    project.mkdir()
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\n")
    pkg = project / "work/n18_final_verification/a1/package"
    (pkg / "prototype/base").mkdir(parents=True)
    (pkg / "prototype/dist").mkdir(parents=True)
    (pkg / "prototype/base/reference.html").write_text("reference")
    (pkg / "prototype/dist/prototype.html").write_text("release")
    (pkg / "manifest.json").write_text(json.dumps({"files": {
        "prototype/base/reference.html": "x", "prototype/dist/prototype.html": "y"}}))
    (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
    export(project, _state())
    assert "prototype/dist/prototype.html" in (project / "releases/latest.html").read_text()


def test_release_shelf_configures_root_and_status_prints_latest(tmp_path):
    project = tmp_path / "p"
    pkg = project / "work/n18_final_verification/a1/package/prototype"
    pkg.mkdir(parents=True)
    (project / ".pdg").mkdir()
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\nrelease_shelf: shelf\n")
    (pkg / "index.html").write_text("<h1>release</h1>")
    (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
        json.dumps({"files": {"prototype/index.html": "x"}}))
    (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
    state = _state()
    (project / ".pdg/state.json").write_text(state.model_dump_json())
    export(project, state)

    assert (project / "shelf/v3/prototype/index.html").is_file()
    assert latest_release_path(project) == project / "shelf/latest.html"
    assert read_status(str(project))["latest_release"].endswith("/shelf/latest.html")


def test_release_shelf_allows_parent_hub_and_namespaces_project(tmp_path):
    hub = tmp_path / "hub"
    project = hub / "p"
    pkg = project / "work/n18_final_verification/a1/package/prototype"
    pkg.mkdir(parents=True)
    (project / ".pdg").mkdir()
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\nrelease_shelf: ../releases\n")
    (pkg / "index.html").write_text("<h1>release</h1>")
    (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
        json.dumps({"files": {"prototype/index.html": "x"}}))
    (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
    state = _state()
    (project / ".pdg/state.json").write_text(state.model_dump_json())

    export(project, state)

    assert (hub / "releases/demo/v3/prototype/index.html").is_file()
    assert (hub / "releases/demo-latest.html").is_file()
    assert (hub / "releases/records/demo-v3-release-summary.md").is_file()
    assert (hub / "releases/RELEASES-demo.md").is_file()
    assert read_status(str(project))["latest_release"].endswith("/releases/demo-latest.html")


def test_release_shelf_refuses_symlink_write_targets(tmp_path):
    hub = tmp_path / "hub"
    project = hub / "p"
    pkg = project / "work/n18_final_verification/a1/package/prototype"
    pkg.mkdir(parents=True)
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\nrelease_shelf: ../releases\n")
    (pkg / "index.html").write_text("release")
    (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
        json.dumps({"files": {"prototype/index.html": "x"}}))
    (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
    (hub / "outside").mkdir()
    (hub / "releases").mkdir()
    os.symlink(hub / "outside", hub / "releases/demo")
    with pytest.raises(ValueError, match="symlink"):
        export(project, _state())
    (hub / "releases/demo").unlink()
    os.symlink(hub / "outside", hub / "releases/demo-latest.html")
    with pytest.raises(ValueError, match="symlink"):
        export(project, _state())
    (hub / "releases/demo-latest.html").unlink()
    os.symlink(hub / "outside", hub / "releases/RELEASES-demo.md")
    with pytest.raises(ValueError, match="symlink"):
        export(project, _state())


def test_release_shelf_parent_cannot_be_hub_or_project(tmp_path):
    hub = tmp_path / "hub"
    project = hub / "p"
    project.mkdir(parents=True)
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\nrelease_shelf: ..\n")
    with pytest.raises(ValueError, match="parent hub"):
        export(project, _state())
    sibling = hub / "sibling"
    sibling.mkdir()
    (sibling / "pdg.project.yaml").write_text("id: sibling\n")
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\nrelease_shelf: ../sibling\n")
    with pytest.raises(ValueError, match="must not point at a pdg project"):
        export(project, _state())


def test_release_shelf_escape_is_refused(tmp_path):
    hub = tmp_path / "hub"
    project = hub / "p"
    project.mkdir(parents=True)
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\nrelease_shelf: ../../outside\n")
    with pytest.raises(ValueError, match="parent hub"):
        export(project, _state())


def test_two_projects_share_hub_shelf_without_clobbering(tmp_path):
    hub = tmp_path / "hub"
    states = []
    for pid in ("alpha", "beta"):
        project = hub / pid
        pkg = project / "work/n18_final_verification/a1/package/prototype"
        pkg.mkdir(parents=True)
        (project / "pdg.project.yaml").write_text(f"id: {pid}\nname: {pid}\nrelease_shelf: ../releases\n")
        (pkg / "index.html").write_text(pid)
        (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
            json.dumps({"files": {"prototype/index.html": "x"}}))
        (project / "work/n18_final_verification/a1/release-summary.md").write_text(f"# {pid}\n")
        state = _state()
        state.project.id = pid
        states.append((project, state))

    for project, state in states:
        export(project, state)

    assert (hub / "releases/alpha/v3/prototype/index.html").read_text() == "alpha"
    assert (hub / "releases/beta/v3/prototype/index.html").read_text() == "beta"
    assert (hub / "releases/alpha-latest.html").is_file()
    assert (hub / "releases/beta-latest.html").is_file()
    assert (hub / "releases/RELEASES-alpha.md").is_file()
    assert (hub / "releases/RELEASES-beta.md").is_file()


def test_shared_shelf_refuses_owner_and_casefold_slug_collisions(tmp_path):
    hub = tmp_path / "hub"
    first = hub / "one"
    second = hub / "two"
    for project in (first, second):
        pkg = project / "work/n18_final_verification/a1/package/prototype"
        pkg.mkdir(parents=True)
        (project / "pdg.project.yaml").write_text("id: same\nname: same\nrelease_shelf: ../releases\n")
        (pkg / "index.html").write_text(project.name)
        (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
            json.dumps({"files": {"prototype/index.html": "x"}}))
        (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
    same_state = _state()
    same_state.project.id = "same"
    export(first, same_state)
    other_owner = same_state.model_copy(deep=True)
    other_owner.project.created = "later-created"
    with pytest.raises(ValueError, match="owned by another project"):
        export(second, other_owner)

    other = hub / "other"
    pkg = other / "work/n18_final_verification/a1/package/prototype"
    pkg.mkdir(parents=True)
    (other / "pdg.project.yaml").write_text("id: SAME\nname: same\nrelease_shelf: ../releases\n")
    (pkg / "index.html").write_text("other")
    (other / "work/n18_final_verification/a1/package/manifest.json").write_text(
        json.dumps({"files": {"prototype/index.html": "x"}}))
    (other / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
    upper = _state()
    upper.project.id = "SAME"
    with pytest.raises(ValueError, match="collides"):
        export(other, upper)


def test_shared_shelf_owner_uses_id_and_created_not_path(tmp_path):
    hub = tmp_path / "hub"
    first = hub / "one"
    second = hub / "two"
    states = []
    for project in (first, second):
        pkg = project / "work/n18_final_verification/a1/package/prototype"
        pkg.mkdir(parents=True)
        (project / "pdg.project.yaml").write_text("id: same\nname: same\nrelease_shelf: ../releases\n")
        (pkg / "index.html").write_text(project.name)
        (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
            json.dumps({"files": {"prototype/index.html": "x"}}))
        (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
        st = _state()
        st.project.id = "same"
        st.project.created = "same-created"
        states.append((project, st))

    export(first, states[0][1])
    export(second, states[1][1])

    marker = json.loads((hub / "releases/same/.pdg-release-owner.json").read_text())
    assert marker == {"project_id": "same", "created": "same-created"}


def test_reapproving_same_version_lists_once(tmp_path):
    project = tmp_path / "p"
    pkg = project / "work/n18_final_verification/a1/package/prototype"
    pkg.mkdir(parents=True)
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\n")
    (pkg / "index.html").write_text("release")
    (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
        json.dumps({"files": {"prototype/index.html": "x"}}))
    (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
    state = _state()
    state.history.approvals.append(state.history.approvals[0].model_copy(update={"reason": "release again"}))
    export(project, state)
    assert (project / "RELEASES.md").read_text().count("| v3 |") == 1


def test_release_shelf_cli_rebuilds(tmp_path):
    project = tmp_path / "p"
    pkg = project / "work/n18_final_verification/a1/package/prototype"
    pkg.mkdir(parents=True)
    (project / ".pdg").mkdir()
    (project / ".pdg/ledger.jsonl").write_text("")
    (project / "pdg.project.yaml").write_text("id: demo\nname: Demo\n")
    (pkg / "index.html").write_text("<h1>release</h1>")
    (project / "work/n18_final_verification/a1/package/manifest.json").write_text(
        json.dumps({"files": {"prototype/index.html": "x"}}))
    (project / "work/n18_final_verification/a1/release-summary.md").write_text("# Summary\n")
    (project / ".pdg/state.json").write_text(_state().model_dump_json())

    assert main(["release-shelf", str(project)]) == 0

    assert (project / "releases/v3/prototype/index.html").is_file()


def test_review_record_canonicalizes_run_label_and_invokes_tool(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "version": 22, "run": "the first run", "candidates": [
        {"id": "A"}, {"id": "B"}]}))
    build(project, "2026-10-04")
    order = json.loads((project / "review/blind-order.json").read_text())["F-001"]
    label_order = list(order)
    reply = project / "reply.txt"
    reply.write_text(f"source: Wei, run chat, 2026-10-03T22:26Z\nF-001: {label_order[0]} > {label_order[1]} "
                     f"{label_order[0]}:DES-TASTE=5 why: cleaner # comment\n")
    tool = tmp_path / "score.py"
    log = tmp_path / "score.log"
    tool.write_text("import json, pathlib, sys\n"
                    "data=json.loads(pathlib.Path(sys.argv[sys.argv.index('record') + 1]).read_text())\n"
                    f"pathlib.Path({str(log)!r}).write_text(json.dumps({{'argv': sys.argv, 'data': data}}))\n")

    out = record(project, reply, tool)

    logged = json.loads(log.read_text())
    assert logged["data"]["run"] == "first-run"
    assert "--rank" in logged["argv"] and ",".join(order[label] for label in label_order) in logged["argv"]
    rate = logged["argv"][logged["argv"].index("--rate") + 1]
    assert rate.startswith(order[label_order[0]] + ":")
    assert not list((project / "review/forks").glob("*.canonical.json"))
    assert any("pdg feedback" in line for line in out)


def test_review_record_refuses_raw_ids_duplicates_and_skips_recorded_retry(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "candidates": [{"id": "1"}, {"id": "2"}]}))
    build(project, "2026-10-04")
    reply = project / "reply.txt"
    reply.write_text("F-001: 1 > 2\n")
    with pytest.raises(ValueError, match="unknown"):
        record(project, reply, tmp_path / "score.py")
    reply.write_text("F-001: Option 1 > Option 1\n")
    with pytest.raises(ValueError, match="same option"):
        record(project, reply, tmp_path / "score.py")

    log = tmp_path / "score.log"
    tool = tmp_path / "score.py"
    tool.write_text("import pathlib\n" f"pathlib.Path({str(log)!r}).write_text('called')\n")
    reply.write_text("F-001: Option 1 > Option 2\n")
    record(project, reply, tool)
    log.unlink()
    out = record(project, reply, tool)
    assert any("skipped F-001" in line for line in out)
    assert not log.exists()

    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "version": 23,
                                                   "candidates": [{"id": "1"}, {"id": "2"}]}))
    build(project, "2026-10-05")
    reply.write_text("F-001: Option 2 > Option 1\n")
    record(project, reply, tool)
    assert log.exists()


def test_review_build_writes_blind_order_and_hides_candidate_ids(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (project / "candidates/F-001/A").mkdir(parents=True)
    (project / "candidates/F-001/A/index.html").write_text("A")
    (project / "candidates/F-001/B").mkdir(parents=True)
    (project / "candidates/F-001/B/index.html").write_text("B")
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "version": 1, "candidates": [
        {"id": "A"}, {"id": "B"}, {"id": "C"}]}))

    out = build(project, "2026-10-04")

    order = json.loads((project / "review/blind-order.json").read_text())["F-001"]
    assert list(order.values()) != ["A", "B", "C"]
    assert set(order) == {"Option 1", "Option 2", "Option 3"}
    packet = out["packet"].read_text()
    blind = packet.split("## 2. Reveal", 1)[0]
    assert "Option 1" in blind and "Option 2" in blind
    assert "file://" in blind
    assert "/candidates/F-001/A" not in blind and "/candidates/F-001/B" not in blind
    assert (project / "review/blind/F-001/option-1/index.html").is_file()
    assert "file://" in (project / "review/blind/F-001/option-1/index.html").read_text()


def test_review_record_validates_before_calling_score_tool(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "candidates": [{"id": "A"}, {"id": "B"}]}))
    (forks / "F-002.json").write_text(json.dumps({"fork_id": "F-002", "candidates": [{"id": "A"}, {"id": "B"}]}))
    build(project, "2026-10-04")
    reply = project / "reply.txt"
    reply.write_text("F-001: Option 1 > Option 2\nF-002: Missing option > Option 2\n")
    tool = tmp_path / "score.py"
    log = tmp_path / "score.log"
    tool.write_text("import pathlib\n" f"pathlib.Path({str(log)!r}).write_text('called')\n")
    with pytest.raises(ValueError):
        record(project, reply, tool)
    assert not log.exists()


def test_review_record_refuses_identifier_in_source_or_why(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "run": "sample-v4-pdg",
                                                   "candidates": [{"id": "A"}, {"id": "B"}]}))
    build(project, "2026-10-04")
    tool = tmp_path / "score.py"
    log = tmp_path / "score.log"
    tool.write_text("import json, pathlib, sys\n"
                    "data=json.loads(pathlib.Path(sys.argv[sys.argv.index('record') + 1]).read_text())\n"
                    f"pathlib.Path({str(log)!r}).write_text(json.dumps(data))\n")
    reply = project / "reply.txt"
    reply.write_text("source: Wei, run chat, 2026-10-03T22:26Z\nF-001: Option 1 > Option 2 why: safe\n")
    record(project, reply, tool)
    assert json.loads(log.read_text())["run"] == "third-run"
    raw_product_label = _listed_product_word()
    reply.write_text(f"source: Wei, run chat, 2026-10-03T22:26Z\nF-001: Option 1 > Option 2 why: {raw_product_label} choice\n")
    with pytest.raises(ValueError, match="identifier"):
        record(project, reply, tool)
    reply.write_text(f"source: Wei, run chat, 2026-10-03T22:26Z\nF-001: Option 1 > Option 2 why: {_separator_identifier_variant()} choice\n")
    with pytest.raises(ValueError, match="identifier"):
        record(project, reply, tool)
    reply.write_text("source: Wei quoted product words\nF-001: Option 1 > Option 2 why: another safe\n")
    with pytest.raises(ValueError, match="source must be date and channel"):
        record(project, reply, tool)


def test_review_record_refuses_separator_variant_identifier_in_why(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001",
                                                   "candidates": [{"id": "A"}, {"id": "B"}]}))
    build(project, "2026-10-04")
    tool = tmp_path / "score.py"
    log = tmp_path / "score.log"
    tool.write_text("import pathlib\n" f"pathlib.Path({str(log)!r}).write_text('called')\n")
    reply = project / "reply.txt"
    reply.write_text("source: Wei, run chat, 2026-10-03T22:26Z\n"
                     f"F-001: Option 1 > Option 2 why: {_separator_identifier_variant()} choice\n")

    with pytest.raises(ValueError, match="identifier"):
        record(project, reply, tool)

    assert not log.exists()


def test_review_record_refuses_identifier_in_canonical_fork_json(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "run": "first-run",
                                                   "candidates": [{"id": "A",
                                                                   "label": _separator_identifier_variant(),
                                                                   "rationale": "safe"},
                                                                  {"id": "B", "label": "neutral"}]}))
    build(project, "2026-10-04")
    tool = tmp_path / "score.py"
    log = tmp_path / "score.log"
    tool.write_text("import pathlib\n" f"pathlib.Path({str(log)!r}).write_text('called')\n")
    reply = project / "reply.txt"
    reply.write_text("source: Wei, run chat, 2026-10-03T22:26Z\nF-001: Option 1 > Option 2 why: safe\n")

    with pytest.raises(ValueError, match="identifier"):
        record(project, reply, tool)
    assert not log.exists()


def test_review_record_identifier_failures_write_no_partial_rows(tmp_path):
    product_word = _separator_identifier_variant()
    source_word = next(w for w in json.loads(TENANT.read_text())["banned"]
                       if all(c.islower() or c in " -" for c in w))
    for bad in ("why", "source", "fork"):
        project = tmp_path / bad
        forks = project / "review/forks"
        forks.mkdir(parents=True)
        (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001",
                                                       "candidates": [{"id": "A"}, {"id": "B"}]}))
        label = product_word if bad == "fork" else "neutral"
        (forks / "F-002.json").write_text(json.dumps({"fork_id": "F-002",
                                                       "candidates": [{"id": "A", "label": label}, {"id": "B"}]}))
        build(project, "2026-10-04")
        source = f"Wei, {source_word}, 2026-10-03T22:26Z" if bad == "source" else "Wei, run chat, 2026-10-03T22:26Z"
        why = f" why: {product_word}" if bad == "why" else ""
        reply = project / "reply.txt"
        reply.write_text(f"source: {source}\nF-001: Option 1 > Option 2\nF-002: Option 1 > Option 2{why}\n")
        tool = tmp_path / f"score-{bad}.py"
        log = tmp_path / f"score-{bad}.log"
        tool.write_text("import pathlib\n" f"pathlib.Path({str(log)!r}).write_text('called')\n")

        with pytest.raises(ValueError, match="identifier"):
            record(project, reply, tool)

        assert not log.exists()
        assert not (project / "review/recorded-replies.json").exists()


def test_review_record_refuses_when_identifier_list_is_unavailable(tmp_path, monkeypatch):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001",
                                                   "candidates": [{"id": "A"}, {"id": "B"}]}))
    build(project, "2026-10-04")
    missing_pkg = tmp_path / "missing-pkg"
    missing_pkg.mkdir()
    monkeypatch.setattr(review_mod, "PKG_ROOT", missing_pkg)
    reply = project / "reply.txt"
    reply.write_text("F-001: Option 1 > Option 2 why: safe\n")

    with pytest.raises(ValueError, match="cannot load preference product-word list"):
        record(project, reply, tmp_path / "score.py")


def test_review_record_accepts_new_ordinal_run_labels(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "run": "fourth-run",
                                                   "candidates": [{"id": "A"}, {"id": "B"}]}))
    build(project, "2026-10-04")
    tool = tmp_path / "score.py"
    log = tmp_path / "score.log"
    tool.write_text("import json, pathlib, sys\n"
                    "data=json.loads(pathlib.Path(sys.argv[sys.argv.index('record') + 1]).read_text())\n"
                    f"pathlib.Path({str(log)!r}).write_text(json.dumps(data))\n")
    reply = project / "reply.txt"
    reply.write_text("source: Wei, run chat, 2026-10-03T22:26Z\nF-001: Option 1 > Option 2 why: safe\n")
    record(project, reply, tool)
    assert json.loads(log.read_text())["run"] == "fourth-run"


def test_review_record_refuses_non_ordinal_run_labels(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "run": "hundredth-run",
                                                   "candidates": [{"id": "A"}, {"id": "B"}]}))
    build(project, "2026-10-04")
    reply = project / "reply.txt"
    reply.write_text("source: Wei, run chat, 2026-10-03T22:26Z\nF-001: Option 1 > Option 2 why: safe\n")

    with pytest.raises(ValueError, match="ordinal label"):
        record(project, reply, tmp_path / "score.py")


def test_review_canonical_fork_checks_run_label_for_product_words(tmp_path, monkeypatch):
    fork = tmp_path / "F-001.json"
    fork.write_text(json.dumps({"fork_id": "F-001", "run": "fourth-run",
                                "candidates": [{"id": "A"}, {"id": "B"}]}))
    monkeypatch.setattr(review_mod, "_preference_words", lambda: ["fourthrun"])

    with pytest.raises(ValueError, match="identifier"):
        review_mod._canonical_fork(fork, {})


def test_archive_plan_keeps_referenced_attempt_and_moves_checkpoint(tmp_path):
    root = tmp_path / "p"
    (root / "work/n/a1").mkdir(parents=True)
    (root / "work/n/a2").mkdir(parents=True)
    (root / "README.md").write_text("See work/n/a1/prototype/index.html")
    (root / ".pdg/checkpoints").mkdir(parents=True)
    cp = root / ".pdg/checkpoints/00002-pass-n.json"
    cp.write_text(json.dumps({"artifacts": {"x": {"path": "work/n/a2/file.txt", "current": True}}}))
    checkpoints = [CheckpointRef(seq=1, event="created", node=None, path=".pdg/checkpoints/00001-created-run.json",
                                 at="now"),
                   CheckpointRef(seq=2, event="pass", node="n", path=".pdg/checkpoints/00002-pass-n.json",
                                 at="now"),
                   CheckpointRef(seq=3, event="pass", node="n", path=".pdg/checkpoints/00003-pass-n.json",
                                 at="now")]

    archive_plan = plan(root, [("work/n/a1", 1), ("work/n/a2", 1)], checkpoints, [])

    assert "work/n/a1" in archive_plan.keep
    assert archive_plan.move == [("work/n/a2", 1)]
    assert [c.seq for c in archive_plan.checkpoints] == [2]


def test_archive_keep_inside_candidate_and_transitive_references(tmp_path):
    root = tmp_path / "p"
    (root / "work/n/a1/tool").mkdir(parents=True)
    (root / "work/n/a2").mkdir(parents=True)
    (root / "work/n/a3").mkdir(parents=True)
    (root / "README.md").write_text("See work/n/a2/index.html")
    (root / "work/n/a2/tool.py").write_text("open('work/n/a1/tool/data.json')")
    (root / "review/work").mkdir(parents=True)
    (root / "review/work/notes.md").write_text("work/n/a3 should stay referenced")

    archive_plan = plan(root, [("work/n/a1", 1), ("work/n/a2", 1), ("work/n/a3", 1)], [], ["work/n/a1/tool"])

    assert set(archive_plan.keep) == {"work/n/a1", "work/n/a2", "work/n/a3"}
    assert archive_plan.move == []
    assert archive_plan.unmatched_keep == []

    transitive = plan(root, [("work/n/a1", 1), ("work/n/a2", 1), ("work/n/a3", 1)], [], [])
    assert "work/n/a1" in transitive.keep and any("work/n/a2/tool.py" in r for r in transitive.keep["work/n/a1"])


def test_archive_keep_parent_folder_keeps_child_candidates(tmp_path):
    root = tmp_path / "p"
    (root / "work/n07/a1").mkdir(parents=True)
    (root / "work/n07/a2").mkdir(parents=True)
    archive_plan = plan(root, [("work/n07/a1", 1), ("work/n07/a2", 1)], [], ["work/n07"])
    assert set(archive_plan.keep) == {"work/n07/a1", "work/n07/a2"}


def test_archive_unmatched_keep_refuses_in_cli(tmp_path, capsys):
    root = tmp_path / "p"
    (root / ".pdg").mkdir(parents=True)
    (root / "work/n/a1").mkdir(parents=True)
    (root / "pdg.project.yaml").write_text("id: demo\nname: Demo\n")
    (root / ".pdg/state.json").write_text(ProjectState.model_validate({"schema_version": "t", "project": {
        "id": "demo", "name": "Demo", "created": "now", "workflow_id": "w", "workflow_version": "1"}}).model_dump_json())
    assert main(["archive", str(root), "--keep", "work/n/nope"]) == 4
    assert "did not match" in capsys.readouterr().out


def test_archive_unmatched_keep_refuses_in_engine(tmp_path):
    from pdg.engine import EngineError
    project = copy_example(tmp_path / "p")
    eng = Engine(project)
    eng.run(max_steps=400)
    with pytest.raises(EngineError, match="did not match"):
        eng.archive(tmp_path / "arch", "Wei", ["work/nope"])


def test_archive_plan_reports_dangling_symlink_and_cli_commit_policy(tmp_path, capsys):
    from pdg.archive import dangling_symlinks
    root = tmp_path / "p"
    (root / "work/n/a1").mkdir(parents=True)
    (root / "work/n/a2").mkdir(parents=True)
    (root / "links").mkdir()
    os.symlink("../work/n/a1", root / "links/old")
    assert dangling_symlinks(root, ["work/n/a1"]) == ["links/old"]

    (root / ".pdg").mkdir()
    (root / "pdg.project.yaml").write_text("id: demo\nname: Demo\n")
    (root / ".pdg/state.json").write_text(ProjectState.model_validate({"schema_version": "t", "project": {
        "id": "demo", "name": "Demo", "created": "now", "workflow_id": "w", "workflow_version": "1"}}).model_dump_json())
    assert main(["archive", str(root)]) == 0
    assert "A release commit keeps" in capsys.readouterr().out


def test_n18_approval_survives_release_shelf_failure(tmp_path, fast_browser, monkeypatch):
    project = copy_example(tmp_path / "p")
    eng = Engine(project)
    eng.run(max_steps=400)
    eng.state.runtime.nodes["n18_final_verification"].status = NodeStatus.WAITING_HUMAN
    eng.save("test")

    def fail(self):
        raise OSError("disk full")
    monkeypatch.setattr(HumanActionsMixin, "release_shelf", fail)

    out = eng.decide("n18_final_verification", "approved", "Wei", "release anyway")

    assert out["decision"] == "approved"
    assert any(a.node == "n18_final_verification" and a.reason == "release anyway"
               for a in eng.state.history.approvals)
    assert eng.notices and "release shelf rebuild failed" in eng.notices[0]


def test_cli_approve_prints_release_shelf_notice(tmp_path, fast_browser, monkeypatch, capsys):
    project = copy_example(tmp_path / "p")
    eng = Engine(project)
    eng.run(max_steps=400)
    state = eng.state
    state.runtime.nodes["n18_final_verification"].status = NodeStatus.WAITING_HUMAN
    (project / ".pdg/state.json").write_text(state.model_dump_json())

    def fail(self):
        raise OSError("disk full")
    monkeypatch.setattr(HumanActionsMixin, "release_shelf", fail)

    assert main(["approve", str(project), "n18_final_verification", "--actor", "Wei", "--reason", "release"]) == 0
    assert "release shelf rebuild failed" in capsys.readouterr().out


def test_simple_prints_engine_notices(monkeypatch, capsys):
    import contextlib
    import pdg.cli as cli

    class FakeEngine:
        notices = ["derived view rebuilt later"]
        def run(self):
            return {"project": "demo", "status": "RUN_PASS", "build_version": 1, "rework_cycles": 0,
                    "batches": 0, "ledger_events": 0, "waiting_agent": [], "waiting_human": [],
                    "escalations": [], "open_defects": [], "nodes": {}}

    @contextlib.contextmanager
    def lock(project, command):
        yield

    monkeypatch.setattr(cli, "_locked", lock)
    monkeypatch.setattr(cli, "_engine", lambda project: FakeEngine())
    assert cli._simple(SimpleNamespace(project="p", command="feedback"), lambda e: None) == 0
    assert "derived view rebuilt later" in capsys.readouterr().out


def test_release_shelf_rebuilt_event_counts_releases_not_approvals(tmp_path, fast_browser):
    from pdg.provenance import Ledger
    project = copy_example(tmp_path / "p")
    eng = Engine(project)
    eng.run(max_steps=400)
    eng.release_shelf()
    event = list(Ledger(project / ".pdg/ledger.jsonl", read_only=True).events("release_shelf_rebuilt"))[-1]
    releases = [a for a in eng.state.history.approvals
                if a.node == "n18_final_verification" and a.decision == "approved"]
    assert event["data"]["releases"] == len(releases)
    assert event["data"]["releases"] < len(eng.state.history.approvals)


def test_release_none_with_changes_does_not_print_approve(tmp_path):
    project = tmp_path / "p"
    forks = project / "review/forks"
    forks.mkdir(parents=True)
    (forks / "F-001.json").write_text(json.dumps({"fork_id": "F-001", "candidates": [{"id": "A"}, {"id": "B"}]}))
    build(project, "2026-10-04")
    reply = project / "reply.txt"
    reply.write_text("release: none, with changes: fix spacing\n")
    out = record(project, reply, tmp_path / "score.py")
    assert not any("pdg approve" in line for line in out)


def test_archive_apply_refuses_dangling_symlink_and_moves_checkpoints(tmp_path, fast_browser, monkeypatch):
    import pytest
    from pdg.archive import ArchivePlan
    from pdg.engine import EngineError
    project = copy_example(tmp_path / "p")
    eng = Engine(project)
    eng.run(max_steps=400)
    candidate = eng.archive_candidates()[0][0]
    (project / "review").mkdir(exist_ok=True)
    os.symlink("../" + candidate, project / "review/old-attempt")
    unsafe = ArchivePlan(move=eng.archive_candidates(), checkpoints=[])
    original_plan = eng.archive_plan
    monkeypatch.setattr(eng, "archive_plan", lambda keep=None: unsafe)
    with pytest.raises(EngineError, match="dangling symlink"):
        eng.archive(tmp_path / "arch", "Wei")
    monkeypatch.setattr(eng, "archive_plan", original_plan)
    (project / "review/old-attempt").unlink()

    out = eng.archive(tmp_path / "arch", "Wei")
    manifest = json.loads((Path(out["dest"]) / "manifest.json").read_text())
    assert out["moved"] > 0
    assert manifest["moved_checkpoints"]
    assert not (project / manifest["moved_checkpoints"][0]["path"]).exists()
