"""The release summary's human record: every action taken under a human's name, with its wait and flags. vpg's first
real run recorded 20 human decisions made by the agent as "Wei", each within 0–32 s of the gate opening (vpg findings
#18, #26); identity is asserted, not authenticated, so the summary must make such a pattern visible to Wei."""

from __future__ import annotations

from pdg.engine import Engine
from pdg.gating import human_record

from .conftest import copy_example
from .test_real_mode import _drive


def test_instant_decisions_under_a_humans_name_are_listed_and_flagged(tmp_path, fast_browser):
    project = copy_example(tmp_path / "real", dry_run=False)
    eng = Engine(project)
    _drive(eng)                                   # every gate decided by "Wei" the moment it opens, as an agent would
    assert eng.state.runtime.status.value == "RUN_PASS"
    rows, counts = human_record(eng)
    gates = {n.id for n in eng.wf.nodes if n.human_review.required}
    assert counts["actions"] >= len(gates) and counts["fast"] >= len(gates)
    assert all("decided within 60 s of the gate opening" in r for r in rows if "gate decision" in r)
    summary = next(project.glob("work/n18_final_verification/a*/release-summary.md")).read_text()
    assert "## Human record (every action taken under a human's name)" in summary
    # written at N18 before N18's own release decision, so it counts one fast decision fewer than the whole run
    assert f"{counts['fast'] - 1} gate decision(s) made within 60 s of the gate opening" in summary
    assert "| Wei |" in summary


def test_scripted_dry_run_decisions_are_not_in_the_human_record(tmp_path, fast_browser):
    project = copy_example(tmp_path / "dry")
    eng = Engine(project)
    eng.run(max_steps=400)
    rows, counts = human_record(eng)
    assert counts["actions"] == 0 and rows == []           # the dry-run actor is not a human; its approvals are listed
    summary = next(project.glob("work/n18_final_verification/a*/release-summary.md")).read_text()   # elsewhere
    assert "## Human record" in summary and "\n- none" in summary.split("## Human record")[1].split("##")[0]
