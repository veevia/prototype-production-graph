"""The dry run: the fictional example project end to end, with scripted agents and real tools.

It copies examples/coa-review into a scratch directory (the example folder is never written), runs the graph until it
stops, and then proves the outcome from disk instead of trusting the run's own status:
  - RUN_PASS was reached and the ledger verifies;
  - the intake loop fired (a resolvable gap sent N02 back to N01);
  - at least one rework cycle re-ran a design node and a build node, and the nodes outside the rework were not re-run;
  - a before/after comparison recorded every defect as resolved;
  - the prototype's real browser suite passed on the final build version;
  - every human gate was decided by the dry-run actor and labelled not human.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from .engine import Engine, EngineError
from .provenance import Ledger
from .util import PKG_ROOT

EXAMPLE = PKG_ROOT / "examples" / "coa-review"
DESIGN_NODES = {"n03_problem_definition", "n04_requirements", "n05_scope_success", "n06_concept_ideation",
                "n07_experience_architecture", "n08_interaction_design", "n09_visual_system", "n10_prototype_planning"}
BUILD_NODES = {"n11_prototype_development", "n12_content_data"}


def prepare(dest: Path | None = None, example: Path = EXAMPLE) -> Path:
    dest = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="pdg-dry-run-"))
    if dest.exists() and any(dest.iterdir()):
        cfg = dest / "pdg.project.yaml"
        previous = cfg.is_file() and "id: coa-review-example" in cfg.read_text()
        if not previous:  # never delete a folder this command did not create
            raise EngineError(f"{dest} exists and is not a previous dry run; choose an empty or new --out folder")
        shutil.rmtree(dest)
    ignore = shutil.ignore_patterns(".pdg", "work", "controls", "__pycache__", ".DS_Store", "_runs")
    shutil.copytree(example, dest, ignore=ignore, dirs_exist_ok=True)
    return dest


def verify(eng: Engine) -> list[tuple[str, bool, str]]:
    st = eng.state
    rt = st.runtime
    ok, n, msg = Ledger(eng.pdg_dir / "ledger.jsonl", read_only=True).verify()
    loops = rt.loop_traversals
    plans = [json.loads((eng.project.root / a.path).read_text()) for a in st.artifacts.values() if a.key == "regeneration_plan"]
    targets = {t for p in plans for t in p.get("targets", [])}
    reran = {r.node for r in st.history.revisions if r.reason == "rework"}
    untouched = [nid for nid in ("n01_context_intake", "n07_experience_architecture", "n09_visual_system")
                 if eng.rt(nid).attempt <= (2 if nid == "n01_context_intake" else 1)]
    comps = st.evaluation.comparisons
    final_browser = [t for t in st.evaluation.test_results if t.suite.startswith("browser") and t.build_version == st.build.version]
    approvals = st.history.approvals
    checks = [
        ("run reached RUN_PASS", rt.status.value == "RUN_PASS", rt.status.value),
        ("ledger verifies", ok, f"{n} events: {msg}"),
        ("the intake loop fired (N02 → N01)", loops.get("E03", 0) >= 1, f"E03 traversals: {loops.get('E03', 0)}"),
        ("≥ 1 rework cycle", rt.rework_cycles >= 1, f"{rt.rework_cycles} cycle(s)"),
        ("rework re-ran a design node", bool(targets & DESIGN_NODES) and bool(reran & DESIGN_NODES), f"targets {sorted(targets)}"),
        ("rework re-ran a build node", bool(targets & BUILD_NODES) and bool(reran & BUILD_NODES), f"re-run {sorted(reran)}"),
        ("nodes outside the rework were not re-run", len(untouched) == 3,
         ", ".join(f"{x}: {eng.rt(x).attempt} attempt(s)" for x in ("n01_context_intake", "n07_experience_architecture", "n09_visual_system"))),
        ("before/after comparison: every reworked defect resolved", bool(comps) and all(c.resolved and not c.persisting for c in comps),
         "; ".join(f"cycle {c.cycle}: resolved {c.resolved}, verdict {c.verdict}" for c in comps) or "none"),
        ("browser suite passed on the final build", bool(final_browser) and all(t.failed == 0 for t in final_browser),
         "; ".join(f"v{t.build_version} {t.passed} passed / {t.failed} failed" for t in final_browser) or "not run"),
        ("human gates decided by the dry-run actor, labelled not human", bool(approvals) and all(not a.human for a in approvals),
         f"{len(approvals)} decisions, human: {sorted({a.human for a in approvals})}"),
        ("two build versions (v1 draft, v2 corrected)", st.build.version >= 2, f"build v{st.build.version}"),
    ]
    return checks


def run(dest: Path | None = None, keep: bool = True, quiet: bool = False) -> dict[str, Any]:
    project = prepare(dest)
    t0 = time.monotonic()
    eng = Engine(project)
    status = eng.run(max_steps=400)
    checks = verify(eng)
    out = {"project": str(project), "seconds": round(time.monotonic() - t0, 1), "status": status["status"],
           "batches": status["batches"], "build_version": status["build_version"], "rework_cycles": status["rework_cycles"],
           "checks": [{"check": c, "ok": ok, "evidence": ev} for c, ok, ev in checks],
           "passed": all(ok for _, ok, _ in checks)}
    if not quiet:
        print(f"dry run: {project} ({out['seconds']} s, {out['batches']} batches)")
        for c, ok, ev in checks:
            print(f"  {'✓' if ok else '✗'} {c} — {ev}")
        print("PASS" if out["passed"] else "FAIL")
    if not keep:
        shutil.rmtree(project, ignore_errors=True)
    return out
