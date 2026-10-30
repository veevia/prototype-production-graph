"""Generic rule references, executable checks, and honest distribution defaults."""

from __future__ import annotations

import ast
import json

import yaml

from pdg.docs import evidence_records
from pdg.memory import STATES

from .conftest import PKG

RULES = json.loads((PKG / "knowledge/rules.json").read_text())


def test_every_rule_has_a_generic_evidence_reference_and_executable_check():
    known = {r["id"] for r in evidence_records()["records"]}
    for rule in RULES["rules"]:
        assert rule["scope"] == "stable"
        assert rule["statement"] and set(rule["evidence"]) <= known
        assert rule["lifecycle"]["state"] in STATES
        assert rule["check"].get("fn") or rule["check"].get("dimensions") or rule["check"].get("test")
        assert rule["basis"] == "distribution-default"
        assert not rule["confirmed_by_human"]
        assert not any(h.get("human") for h in rule["lifecycle"]["history"])


def test_rubrics_and_rule_dimensions_agree():
    rules = {r["id"]: r for r in RULES["rules"]}
    seen = set()
    for path in (PKG / "rubrics").glob("*.yaml"):
        for dimension in yaml.safe_load(path.read_text())["dimensions"]:
            rule = rules[dimension["rule"]]
            assert dimension["id"] in rule["check"].get("dimensions", [])
            seen.add(dimension["id"])
    assert all(set(r["check"].get("dimensions", [])) <= seen for r in rules.values())


def test_referenced_rule_tests_exist():
    for rule in RULES["rules"]:
        ref = rule["check"].get("test")
        if not ref:
            continue
        path, _, name = ref.partition("::")
        functions = {n.name for n in ast.walk(ast.parse((PKG / path).read_text())) if isinstance(n, ast.FunctionDef)}
        assert name in functions


def test_documentation_states_the_private_project_boundary():
    text = (PKG / "docs/previous-iterations.md").read_text()
    assert "private project directory" in text
    assert "never user evidence or human sign-off" in text
