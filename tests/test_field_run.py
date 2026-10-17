"""Findings from the first real project run (2026-09-27, a customer prototype). Each test reproduces a defect the run
hit, and fails without its fix."""

from __future__ import annotations

import json
import shlex

from pdg.cli import main
from pdg.engine import Engine

from .conftest import copy_example

AWKWARD = "a project + its folder"   # spaces and a plus sign, as real project names have


def _real(tmp_path):
    return copy_example(tmp_path / AWKWARD, dry_run=False)


# ------------------------------------------------------------------------------------------------ W1: quoted paths
def test_the_packet_submit_command_survives_a_path_with_spaces_and_a_plus(tmp_path):
    proj = _real(tmp_path)
    eng = Engine(proj)
    eng.run()
    packet = json.loads((proj / ".pdg" / "tasks" / "n01_context_intake-a1.json").read_text())
    argv = shlex.split(packet["submit"])
    assert argv[:5] == ["python", "-B", "-m", "pdg", "submit"] and argv[5] == str(proj) and argv[6] == "n01_context_intake"
    md = (proj / ".pdg" / "tasks" / "n01_context_intake-a1.md").read_text()
    assert packet["submit"] in md


def test_init_prints_a_next_step_that_can_be_pasted_into_a_shell(tmp_path, capsys):
    root = tmp_path / AWKWARD
    assert main(["init", str(root), "--name", "x"]) == 0
    out = capsys.readouterr().out
    line = out.split("`")[1]                                  # the backquoted next-step command
    assert shlex.split(line) == ["python", "-B", "-m", "pdg", "run", str(root.resolve())]


# ------------------------------------------------------------------------------------------------ W4: moved citations
def test_a_case_study_citation_survives_its_file_moving_elsewhere(monkeypatch):
    """Another project moved a cited file (uncommitted, in the shared tree) and pdg's own suite failed. A citation is
    provenance for content recorded at a commit, so it must resolve from that commit when the working-tree file moved."""
    from . import test_knowledge as tk
    import pytest
    moved = next((c.split(":")[0] for r in tk.HISTORY["records"] for c in r["citations"]
                  if c.startswith("01_Project-Hubs/")), None)
    if moved is None:
        pytest.skip("private case-study citations are intentionally not distributed")
    if tk._recorded_lines(moved) is None:
        pytest.skip("not a git checkout with the recorded case study")
    real_is_file = type(tk.WORKSPACE / moved).is_file
    monkeypatch.setattr(type(tk.WORKSPACE / moved), "is_file",
                        lambda self: False if str(self).endswith(moved) else real_is_file(self))
    tk.test_every_citation_resolves_to_a_file_and_line_range_that_exist()


# ------------------------------------------------------------------------------------------------ W3: kernel port
def test_an_agent_or_dry_run_name_is_never_human_in_any_spelling_even_if_listed():
    """Ported with vpg v1.1's case-insensitive human check: a misconfigured humans list cannot make an agent human."""
    from pdg.memory import is_human
    for name in ("Agent:orchestrator", "AGENT:x", "agent:x", "Dry-Run-Auto", "dry-run-auto", "  "):
        assert not is_human(name, [name], True), name
    assert is_human("Wei", ["Wei"], True) and not is_human("wei", ["Wei"], True)


# ------------------------------------------------------------------------------------------------ W7: blind config accept
def test_a_config_drift_escalation_names_the_file_that_changed(project, fast_browser):
    """The integrity escalation said only that 'the workflow, rules, rubrics, defaults or project config changed', so
    `pdg accept-config` was a blind approval. It now names each changed file, and the acceptance records them."""
    eng = Engine(project)
    eng.run(max_steps=6)
    assert "pdg.project.yaml" in eng.state.runtime.config_parts
    cfg = project / "pdg.project.yaml"
    cfg.write_text(cfg.read_text() + "\n# a mid-run edit\n")
    eng.run(max_steps=3)
    esc = next(e for e in eng.state.runtime.escalations if e.open and e.node == "run")
    assert "changed pdg.project.yaml" in esc.reason
    assert "changed pdg.project.yaml" in (project / esc.report).read_text()
    eng.accept_config("Wei", "the comment is harmless")
    accepted = list(eng.ledger.events("config_accepted"))[-1]
    assert accepted["data"]["changed"] == ["pdg.project.yaml"]
    assert eng.state.runtime.config_parts["pdg.project.yaml"] == eng._config_files()["pdg.project.yaml"]


def test_a_run_started_before_per_file_hashes_says_the_file_is_unknown(project, fast_browser):
    eng = Engine(project)
    eng.run(max_steps=6)
    eng.state.runtime.config_parts = {}       # a state written before pdg recorded per-file hashes
    eng.state.runtime.config_sha256 = "0" * 64
    eng.run(max_steps=3)
    esc = next(e for e in eng.state.runtime.escalations if e.open and e.node == "run")
    assert "which file is unknown" in esc.reason


# ------------------------------------------------------------------------------------------------ W8: simulated-only validation
def test_the_release_tldr_says_when_validation_was_simulated_only(project, fast_browser):
    """The release summary listed simulated sessions further down, but its TL;DR said only that the build 'passed every
    enforced gate', and VAL-TASK-SUCCESS passes on simulated sessions when there are no real ones. The first line a
    reader sees now says the validation was simulated."""
    eng = Engine(project)
    eng.run(max_steps=400)
    summary = next(project.glob("work/n18_final_verification/a*/release-summary.md")).read_text()
    tldr = next(line for line in summary.splitlines() if line.startswith("> **TL;DR:**"))
    assert "simulated sessions only" in tldr and "not user evidence" in tldr
