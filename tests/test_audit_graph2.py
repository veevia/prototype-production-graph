"""Second-pass audit regressions for gate hook validation."""

from __future__ import annotations

import shutil

import yaml

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


def test_validator_requires_the_review_gate_hook_exactly_once(tmp_path):
    def remove_review_gate(data):
        _node(data, "n16_feedback_diagnosis").pop("gate")

    errs = _errors_after_tmp_mutation(tmp_path, remove_review_gate)
    assert any("required gate hook review_gate appears 0 times" in e for e in errs)


def test_validator_rejects_swapping_review_gate_to_another_allowed_hook(tmp_path):
    def swap_to_learning(data):
        _node(data, "n16_feedback_diagnosis")["gate"] = "learning"

    errs = _errors_after_tmp_mutation(tmp_path, swap_to_learning)
    assert any("required gate hook review_gate appears 0 times" in e for e in errs)
    assert any("required gate hook learning appears 2 times" in e for e in errs)


def test_validator_requires_review_gate_to_have_reviewer_flow_inputs(tmp_path):
    def remove_reviewers(data):
        data["edges"] = [e for e in data["edges"] if e["id"] not in {"E24", "E25", "E26"}]

    errs = _errors_after_tmp_mutation(tmp_path, remove_reviewers)
    assert any("review_gate node n16_feedback_diagnosis has no reviewer flow inputs" in e for e in errs)
