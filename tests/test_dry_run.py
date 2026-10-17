"""The whole graph end to end on the fictional example, with the real browser suite (no stubs): intake loop, a rework
cycle that routes defects back to design and build, a before/after comparison, release verification and learning."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdg.dryrun import run
from pdg.provenance import Ledger

from .conftest import PKG

pytest.importorskip("playwright")


def test_the_dry_run_passes_end_to_end_with_honest_labels(tmp_path):
    rules = PKG / "knowledge" / "rules.json"
    rules_before = rules.read_bytes()
    out = run(tmp_path / "dry", keep=True, quiet=True)
    assert out["passed"], [c for c in out["checks"] if not c["ok"]]
    assert out["status"] == "RUN_PASS" and out["build_version"] == 2 and out["rework_cycles"] == 1
    project = Path(out["project"])
    ok, n, _ = Ledger(project / ".pdg" / "ledger.jsonl", read_only=True).verify()
    assert ok and n > 100
    st = json.loads((project / ".pdg" / "state.json").read_text())
    assert st["history"]["approvals"] and not any(a["human"] for a in st["history"]["approvals"])
    assert all(f["simulated"] for f in st["evaluation"]["feedback"])            # never presented as user evidence
    pkg = next(project.glob("work/n18_final_verification/a*/package"))
    manifest = json.loads((pkg / "manifest.json").read_text())
    assert manifest and (pkg / "RELEASE-SUMMARY.md").read_text().count("not a human approval") >= 5
    assert "DRY RUN" in (pkg / "RELEASE-SUMMARY.md").read_text()
    art = st["artifacts"][st["knowledge"]["proposal"]]
    proposal = json.loads((project / art["path"]).read_text())
    assert proposal["candidates"] and st["knowledge"]["lessons"]
    assert rules.read_bytes() == rules_before                                   # proposed, never applied by itself
    expected = PKG / "examples" / "coa-review" / "expected" / "controls"
    for doc in sorted(expected.glob("*.md")):                                   # the requirements, flows and specs it produces
        assert (project / "controls" / doc.name).read_text() == doc.read_text(), doc.name
