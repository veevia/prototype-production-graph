"""Standalone source closure and non-destructive workspace exports."""

from __future__ import annotations

import importlib.util
import json

import pytest

from pdg.privacy import privacy_path

from .conftest import PKG


def exporter():
    path = PKG / "scripts/export_public.py"
    if not path.exists():
        pytest.skip("workspace exporter is not a dependency of the public engine")
    spec = importlib.util.spec_from_file_location("pdg_public_export", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_privacy_policy_uses_private_vocabulary_only_when_present(tmp_path):
    public = tmp_path / "knowledge/public/privacy.json"
    assert privacy_path(tmp_path) == public
    private = tmp_path / "knowledge/case-studies/hub-programmes-2026/deidentify_TENANT.json"
    private.parent.mkdir(parents=True)
    private.write_text("{}")
    assert privacy_path(tmp_path) == private


def test_export_sync_is_repeatable_and_check_never_writes(tmp_path):
    ex = exporter()
    dest = tmp_path / "public"
    files = {"pdg/example.py": b"v1\n", "README.md": b"hello\n"}
    assert ex.sync(dest, files) == ["README.md", "pdg/example.py"]
    assert not dest.exists()
    assert len(ex.sync(dest, files, apply=True)) == 2
    assert ex.sync(dest, files) == []
    before = (dest / ex.RECEIPT).read_bytes()
    assert ex.sync(dest, {"README.md": b"hello\n"}, apply=True) == ["pdg/example.py"]
    assert not (dest / "pdg/example.py").exists()
    assert (dest / ex.RECEIPT).read_bytes() != before


def test_export_refuses_edits_and_unowned_collisions_before_writes(tmp_path):
    ex = exporter()
    dest = tmp_path / "public"
    ex.sync(dest, {"a": b"old", "z": b"old"}, apply=True)
    (dest / "z").write_bytes(b"community edit")
    with pytest.raises(ValueError, match="edited"):
        ex.sync(dest, {"a": b"new", "z": b"new"}, apply=True)
    assert (dest / "a").read_bytes() == b"old"
    with pytest.raises(ValueError, match="edited"):
        ex.sync(dest, {"a": b"new"}, apply=True)
    (dest / "unknown").write_bytes(b"other work")
    with pytest.raises(ValueError, match="unowned"):
        ex.sync(dest, {"unknown": b"new"}, apply=True)


def test_export_refuses_local_deletions_and_source_workspace_destinations(tmp_path):
    ex = exporter()
    dest = tmp_path / "public"
    ex.sync(dest, {"a": b"old"}, apply=True)
    (dest / "a").unlink()
    with pytest.raises(ValueError, match="deleted"):
        ex.sync(dest, {"a": b"new"}, apply=True)
    with pytest.raises(ValueError, match="outside"):
        ex.sync(PKG / ".." / "public", {"a": b"new"}, apply=True)


@pytest.mark.parametrize("name", ["../outside", "/absolute", ".git/config"])
def test_export_refuses_unsafe_paths(tmp_path, name):
    with pytest.raises(ValueError, match="unsafe"):
        exporter().sync(tmp_path / "public", {name: b"bad"}, apply=True)
    assert not (tmp_path / "public").exists()


def test_export_refuses_symlink_source_or_destination(tmp_path):
    ex = exporter()
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        ex.sync(link, {"a": b"bad"}, apply=True)
    dest = tmp_path / "public"
    dest.mkdir()
    (dest / "nested").symlink_to(target, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        ex.sync(dest, {"nested/file": b"bad"}, apply=True)


def test_export_scan_blocks_secret_shapes_and_personal_paths():
    ex = exporter()
    for content in (b"ghp_" + b"x" * 36, b"/Users/" + b"example/private/project"):
        with pytest.raises(ValueError, match="refused"):
            ex.scan({"README.md": content})


def test_export_scan_requires_a_privacy_policy(tmp_path):
    ex = exporter()
    with pytest.raises(ValueError, match="regular"):
        ex.scan({"README.md": b"ordinary text"}, tmp_path)
    policy = tmp_path / "knowledge/public/privacy.json"
    policy.parent.mkdir(parents=True)
    policy.write_text("{}")
    with pytest.raises(ValueError, match="blocked identifiers"):
        ex.scan({"README.md": b"ordinary text"}, tmp_path)


def test_public_rule_projection_drops_private_text_and_preserves_enforcement():
    ex = exporter()
    rules, evidence = ex.public_rules(PKG)
    original = json.loads((PKG / "knowledge/rules.json").read_text())
    public = json.loads(rules)
    assert [(r["id"], r["lifecycle"]["state"]) for r in public["rules"]] == [
        (r["id"], r["lifecycle"]["state"]) for r in original["rules"]]
    for source, projected in zip(original["rules"], public["rules"]):
        for key in ("scope", "basis", "check", "threshold", "calibration_pending", "adopted_in", "confirmed_by_wei"):
            assert source[key] == projected[key], (source["id"], key)
    assert len(json.loads(evidence)["records"]) == len(original["rules"])
    assert all(not r["observations"] and not r["previous_versions"] and not r["note"] for r in public["rules"])
    assert all(r["evidence"] == ["PUBLIC-" + r["id"]] for r in public["rules"])
    assert [[h.get("awaits_confirmation") for h in r["lifecycle"]["history"]] for r in public["rules"]] == [
        [h.get("awaits_confirmation") for h in r["lifecycle"]["history"]] for r in original["rules"]]
    assert b"chat:" not in rules and b"confirm all" not in rules


def test_candidate_scorer_resolves_without_a_runtime_import_from_a_sibling():
    from pdg.review import _default_score_tool
    bundled = PKG / "scoring/vpg_score.py"
    selected = _default_score_tool()
    assert selected.is_file()
    if bundled.exists():
        assert selected == bundled
    else:
        assert selected == PKG.parent / "video-production/scoring/vpg_score.py"


def test_public_control_template_references_are_bundled():
    import yaml
    if not (PKG / "templates/artifacts").is_dir():
        pytest.skip("artifact snapshots are materialized by the public exporter")
    for path in (PKG / "templates/control").glob("*.md"):
        fm = yaml.safe_load(path.read_text().split("---", 2)[1])
        for ref in fm.get("canonical_templates", []):
            assert (PKG / ref).is_file(), ref


def test_export_names_public_counterparts_for_workspace_only_paths(tmp_path):
    """The public checkout told agents and new projects to open workspace folders it does not have: prompts and the graph
    named `00_README/_templates/…` and `05_Library/…`, and every `pdg init` copied `02_Workflows/…` into controls/."""
    ex = exporter()
    assert ex.public_paths("Follow `00_README/_templates/1-0-Understand_problem-frame.template.md`, use "
                           "05_Library/DESIGN-SYSTEM-AI-INSTRUCTIONS.md and the rubrics in "
                           "`02_Workflows/prototype-design/rubrics/`.") == (
        "Follow `templates/artifacts/1-0-Understand_problem-frame.template.md`, use "
        "templates/artifacts/DESIGN-SYSTEM-AI-INSTRUCTIONS.md and the rubrics in pdg's `rubrics/`.")
    policy = tmp_path / "knowledge/public/privacy.json"
    policy.parent.mkdir(parents=True)
    policy.write_text('{"banned": ["no-such-identifier"]}')
    with pytest.raises(ValueError, match="workspace-only path"):
        ex.scan({"prompts/n99_example.md": b"Read 05_Library/guide.md first."}, tmp_path)
    ex.scan({"CONTRIBUTING.md": b"Export from `02_Workflows/prototype-design/`.",
             "tests/test_example.py": b"skip unless (workspace / '00_README').is_dir()"}, tmp_path)


def test_export_ships_images_as_pixels_only(tmp_path):
    """The README's cover image is the first binary file in the export: its bytes skip the text checks, so a text,
    EXIF or content-credential chunk (where generators record prompts and provenance) refuses the export instead."""
    import struct
    import zlib
    ex = exporter()
    policy = tmp_path / "knowledge/public/privacy.json"
    policy.parent.mkdir(parents=True)
    policy.write_text('{"banned": ["no-such-identifier"]}')

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    head = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
    tail = chunk(b"IDAT", zlib.compress(b"\x00\x00")) + chunk(b"IEND", b"")
    ex.scan({"docs/images/cover.png": head + tail}, tmp_path)
    with pytest.raises(ValueError, match="image metadata"):
        ex.scan({"docs/images/cover.png": head + chunk(b"tEXt", b"prompt\x00draw the private roadmap") + tail}, tmp_path)
    for cover in (PKG / "docs/images/pdg-overview.png", PKG / "community/pdg-overview.png"):
        if cover.exists():
            assert ex.png_metadata(cover.read_bytes()) == [], cover


def test_the_distribution_names_no_workspace_only_folders():
    ex = exporter()
    if not (PKG / "templates/artifacts").is_dir():
        pytest.skip("workspace sources name the workspace's own folders; the public exporter rewrites them")
    skip = ex.NOISE | {".git", ".venv"}
    leaks = [p.relative_to(PKG).as_posix() for p in sorted(PKG.rglob("*"))
             if p.is_file() and not set(p.relative_to(PKG).parts) & skip
             and not ex.names_workspace(p.relative_to(PKG).as_posix())
             and ex.WORKSPACE_ONLY.search(p.read_bytes().decode("utf-8", "replace"))]
    assert leaks == []
