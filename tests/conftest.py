"""Shared test fixtures. Engine tests stub the real browser suite (tests/test_browser.py and tests/test_dry_run.py run it
for real) so the graph mechanics can be exercised in seconds."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

sys.dont_write_bytecode = True   # the package lives in a shared tree: the tests write no bytecode (N-12)
PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))

from pdg.context import CheckResult  # noqa: E402
from pdg.tools._common import finding  # noqa: E402

EXAMPLE = PKG / "examples" / "coa-review"


def copy_example(dest: Path, dry_run: bool = True) -> Path:
    shutil.copytree(EXAMPLE, dest, ignore=shutil.ignore_patterns(".pdg", "work", "controls", "__pycache__", "_runs"))
    if not dry_run:
        cfg = yaml.safe_load((dest / "pdg.project.yaml").read_text())
        cfg["dry_run"] = False
        (dest / "pdg.project.yaml").write_text(yaml.safe_dump(cfg))
    return dest


def fake_browser(ctx):
    """A fast stand-in for pdg.tools.browser:check with the same dimensions and outputs. A build that carries a draft
    overlay fails colour contrast on the queue, exactly like the real suite does."""
    res = CheckResult()
    root = ctx.artifact("prototype")
    man = json.loads((root / "build-manifest.json").read_text())
    bad = bool(man.get("overlays")) or getattr(ctx.engine, "_force_browser_fail", False)
    for dim in ("FUNC-SCENARIOS", "FUNC-STATES", "FUNC-CONSOLE", "FUNC-OFFLINE", "PERF-LOAD", "A11Y-FOCUS",
                "A11Y-FOCUS-VISIBLE-2411", "A11Y-TEXT-SPACING-1412", "A11Y-TARGET-AA", "A11Y-TARGET-44",
                "A11Y-TYPE-MIN", "A11Y-REDUCED-MOTION", "RESP-OVERFLOW", "RESP-REFLOW-320", "VIS-TOKENS-RUNTIME", "REF-PARITY", "RESP-BAND", "RESP-TEXT"):
        res.dim(dim, True, "stubbed")
    screens = ("lot", "notice", "queue")   # where the real suite finds the draft overlay's chip contrast failure
    res.dim("A11Y-AXE", not bad, "stubbed axe", [finding("A11Y-AXE", f"axe color-contrast (serious) on {s}", "P2",
                                                   f"{s}:color-contrast", "n11_prototype_development",
                                                   "use the declared tint pair",
                                                   f"axe reports 0 color-contrast violations on {s}") for s in screens] if bad else [])
    rep = ctx.out("browser-report.json")
    rep.write_text(json.dumps({"stub": True, "overlay": bad}))
    shots = ctx.out("screenshots/.keep")
    shots.write_text("")
    res.outputs = {"browser_report": str(rep), "screenshots": str(shots.parent)}
    res.data["test_results"] = [{"suite": "browser (stub)", "passed": 14, "failed": 0 if not bad else 1, "details": "stub"}]
    return res


@pytest.fixture
def fast_browser(monkeypatch):
    import pdg.tools.browser as b
    monkeypatch.setattr(b, "check", fake_browser)
    return fake_browser


@pytest.fixture
def project(tmp_path):
    return copy_example(tmp_path / "proj")


@pytest.fixture
def rules_copy(tmp_path):
    dst = tmp_path / "knowledge"
    dst.mkdir()
    shutil.copyfile(PKG / "knowledge" / "rules.json", dst / "rules.json")
    return dst / "rules.json"


class FakeCtx:
    """Enough of NodeContext for tool unit tests."""

    def __init__(self, docs: dict, state=None, thresholds=None, work: Path | None = None, humans=("Wei",)):
        from pdg.models import ProjectState
        self._docs = docs
        self.state = state or ProjectState.model_validate({"schema_version": "t", "project": {
            "id": "t", "name": "t", "created": "now", "workflow_id": "w", "workflow_version": "1"}})
        base = yaml.safe_load((PKG / "config" / "defaults.yaml").read_text())["thresholds"]
        self.thresholds = {**base, **(thresholds or {})}
        self.engine = SimpleNamespace(humans=list(humans))
        self.work = work or Path(".")
        self.project = self.work

    def json(self, key):
        return self._docs.get(key)

    def output(self, key):   # no submitted files; a test that needs one assigns its own
        return None

    def out(self, name):
        p = self.work / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
