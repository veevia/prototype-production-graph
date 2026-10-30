"""Publication boundaries for the domain-agnostic starter kit."""

from __future__ import annotations

import importlib.util
import json
import re

import pytest

from pdg.smoke import materialize

from .conftest import PKG


def exporter():
    spec = importlib.util.spec_from_file_location("public_export", PKG / "scripts/export_public.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("name", [
    "sources/brief.md", "examples/project/data.json", "knowledge/preferences/current.json",
    "knowledge/history/rules-v1.json", ".git/config", "private/notes.md", "../outside",
    "templates/testing/prototype/src/data/seed.json",
])
def test_non_starter_paths_are_refused(name):
    ex = exporter()
    assert not ex.allowed(name)


def test_export_is_history_free_and_refuses_existing_content(tmp_path):
    ex = exporter()
    files = {"README.md": b"Starter\n", "pdg/example.py": b"x = 1\n"}
    dest = tmp_path / "starter"
    ex.export(dest, files)
    assert (dest / "README.md").read_bytes() == b"Starter\n"
    assert not (dest / ".git").exists()
    with pytest.raises(ValueError, match="empty"):
        ex.export(dest, files)


def test_publication_refuses_credential_shapes_and_personal_paths():
    ex = exporter()
    for text in (b"ghp_" + b"x" * 36, b"/Users/" + b"test/private/file"):
        with pytest.raises(ValueError, match="refused"):
            ex.scan({"README.md": text})


def test_publication_rejects_project_rules_and_approval_history():
    ex = exporter()
    rule = {"id": "test", "scope": "project_specific", "lifecycle": {"history": []}}
    with pytest.raises(ValueError, match="project history"):
        ex.scan({"knowledge/rules.json": json.dumps({"rules": [rule]}).encode()})


def test_fixture_data_is_generated_outside_the_repository(tmp_path):
    materialize(tmp_path)
    data = json.loads((tmp_path / "prototype/src/data/seed.json").read_text())
    assert data["generated"]["provenance"] == "synthetic"
    assert {r["id"] for r in data["records"]} == {"R-001", "R-002", "R-003"}
    assert not (PKG / "templates/testing/prototype/src/data/seed.json").exists()


def test_distribution_rule_profile_contains_no_project_or_human_history():
    rules = json.loads((PKG / "knowledge/rules.json").read_text())["rules"]
    assert rules and all(r["scope"] == "stable" for r in rules)
    assert all(not r["confirmed_by_human"] and not r["observations"] and not r["previous_versions"] for r in rules)
    assert not any(h["human"] for r in rules for h in r["lifecycle"]["history"])


def test_artifact_templates_are_unfilled_and_self_contained():
    paths = sorted((PKG / "templates/artifacts").glob("*.md"))
    assert paths
    for path in paths:
        text = path.read_text()
        front = text.split("---", 2)[1]
        assert "status: template" in front and "owner: <owner>" in front, path.name
        assert "last-updated: YYYY-MM-DD" in front, path.name
        assert not re.search(r"^source:", front, re.M), path.name
        assert not re.search(r"GLOSSARY\.md|CLAUDE\.md|_wiki/|\bW[1-5]\b", text), path.name
