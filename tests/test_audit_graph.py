"""Regression tests for verified audit findings in graph validation and task packets."""

from __future__ import annotations

import shutil

import yaml

from pdg.executors import render_packet
from pdg.graph import load_workflow, structural_errors

from .conftest import PKG


def _errors_after_tmp_mutation(tmp_path, mutate) -> list[str]:
    src = PKG / "graph" / "workflow.yaml"
    dst = tmp_path / "workflow.yaml"
    shutil.copy(src, dst)
    data = yaml.safe_load(dst.read_text())
    mutate(data)
    dst.write_text(yaml.safe_dump(data, sort_keys=False))
    return structural_errors(load_workflow(dst), root=PKG)


def _node(data, node_id):
    return next(n for n in data["nodes"] if n["id"] == node_id)


def _edge(data, edge_id):
    return next(e for e in data["edges"] if e["id"] == edge_id)


def test_validator_rejects_unknown_gate_hook(tmp_path):
    def typo_review_gate(data):
        _node(data, "n16_feedback_diagnosis")["gate"] = "review_gat"

    errs = _errors_after_tmp_mutation(tmp_path, typo_review_gate)
    assert any("n16_feedback_diagnosis: unknown gate hook 'review_gat'" in e for e in errs)


def test_validator_rejects_target_condition_that_points_to_a_different_node(tmp_path):
    def wrong_target(data):
        _edge(data, "E35")["to"] = "n09_visual_system"

    errs = _errors_after_tmp_mutation(tmp_path, wrong_target)
    assert any("E35: when target n08_interaction_design does not match edge target n09_visual_system" in e for e in errs)


def test_validator_rejects_invalid_subgraph_membership(tmp_path):
    def bad_subgraphs(data):
        _node(data, "n01_context_intake")["subgraph"] = "missing-subgraph"
        next(s for s in data["subgraphs"] if s["id"] == "discovery")["nodes"].append("n99_missing")

    errs = _errors_after_tmp_mutation(tmp_path, bad_subgraphs)
    assert any("n01_context_intake: unknown subgraph missing-subgraph" in e for e in errs)
    assert any("subgraph discovery lists unknown node n99_missing" in e for e in errs)


def test_validator_rejects_empty_retry_and_escalation_policy_text(tmp_path):
    def empty_policy_text(data):
        node = _node(data, "n01_context_intake")
        node["retry"]["behavior"] = ""
        node["escalation"]["after"] = ""
        node["escalation"]["to"] = ""
        node["escalation"]["report"] = ""

    errs = _errors_after_tmp_mutation(tmp_path, empty_policy_text)
    for needle in (
        "n01_context_intake: empty retry.behavior",
        "n01_context_intake: empty escalation.after",
        "n01_context_intake: empty escalation.to",
        "n01_context_intake: empty escalation.report",
    ):
        assert any(needle in e for e in errs), needle


def test_render_packet_includes_work_folder_and_precheck_details():
    packet = {
        "node": "n13_quality_review",
        "attempt": 1,
        "agent": "technical-qa",
        "support_agents": [],
        "purpose": "Review the prototype.",
        "instructions": "Read browser-report.json and quality-report.json.",
        "previous_failures": [],
        "rework": [],
        "inputs": {"artifact:prototype": "work/n12_content_data/a1/prototype"},
        "context": ["Use the tool evidence."],
        "skills": ["prototype-review"],
        "outputs": [{"key": "quality_review", "kind": "json", "required": True, "schema": None, "description": "Review"}],
        "dimensions": [],
        "controls": {"read": [], "write": [], "sections": {}},
        "prompt": "Write the review.",
        "submit": "python -m pdg submit /tmp/project n13_quality_review --output quality_review=<path>",
        "work_dir": "/tmp/project/work/n13_quality_review/a1",
        "precheck": {
            "errors": [],
            "messages": ["browser audit complete"],
            "data": {},
            "outcome": None,
            "outputs": {"browser_report": "browser-report.json", "quality_report": "/tmp/project/work/n13_quality_review/a1/quality-report.json"},
            "dimensions": {
                "functional": {"passed": True, "evidence": "browser smoke passed", "findings": []},
                "a11y": {"passed": False, "evidence": "contrast issue", "findings": [{"id": "F-a11y"}]},
            },
        },
    }

    md = render_packet(packet)
    assert "## Work folder" in md
    assert "- `/tmp/project/work/n13_quality_review/a1`" in md
    assert "`--output` paths are resolved relative to this folder" in md
    assert "## Pre-check" in md
    assert "- output `browser_report` → `browser-report.json`" in md
    assert "- output `quality_report` → `/tmp/project/work/n13_quality_review/a1/quality-report.json`" in md
    assert "- `functional` PASS: browser smoke passed" in md
    assert "- `a11y` FAIL: contrast issue (1 finding)" in md
