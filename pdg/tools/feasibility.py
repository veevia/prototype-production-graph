"""N15 pre-check: syntax, unit tests, bundle budget, network dependencies, development.md sections."""

from __future__ import annotations

import json
import os

from ..context import CheckResult, NodeContext
from ..util import write_json_atomic
from . import _node
from .prototype import external_refs


def devdoc_missing(dev: str, sections: list[str]) -> list[str]:
    """Required development.md sections without a real heading (a `## Testing` line inside a code block is not one)."""
    from ..controls import split_sections
    headings = {title.lower() for title, _ in split_sections(dev)[1]}
    return [s for s in sections if not any(h.startswith(s.lower()) for h in headings)]


def check(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    if not _node.node_bin():
        res.errors.append("node is not on PATH")
        res.data["blocked"] = "node unavailable"
        return res
    t = ctx.thresholds["feasibility"]
    root = ctx.artifact("prototype")
    man = json.loads((root / "build-manifest.json").read_text())
    entry = root / man["entry"]
    js = sorted(p for p in root.rglob("*.js") if "node_modules" not in p.parts)
    bad = _node.syntax(js, t["node_timeout_s"])
    res.dim("TEC-SYNTAX", not bad, f"{len(js)} scripts parse" if not bad else f"syntax errors: {bad}")
    passed = failed = 0
    tail = "no unit tests"
    if man.get("unit_tests") and (root / man["unit_tests"]).is_file():
        passed, failed, tail = _node.unit_in_scratch(root / man["unit_tests"], root, t["node_timeout_s"])
    reads, embedded = man.get("unit_tests_dataset"), man.get("dataset")
    other = bool(reads and reads != "none" and embedded and os.path.normpath(reads) != os.path.normpath(embedded))
    said = ("" if not man.get("unit_tests") else
            f"; the tests read {reads}, but the build embeds {embedded}" if other else
            "; the tests read no dataset" if reads == "none" else
            f"; the tests read the embedded dataset {embedded}" if reads and embedded else
            "; which dataset the tests read is not declared (build manifest `unit_tests_dataset`)" if embedded else "")
    res.dim("TEC-UNIT", passed >= 1 and failed == 0 and not other, f"node --test: {passed} passed, {failed} failed{said}")
    kb = entry.stat().st_size / 1024
    res.dim("TEC-BUNDLE", kb <= t["bundle_budget_kb"], f"entry {kb:.0f} KB (budget {t['bundle_budget_kb']} KB)")
    ext = external_refs(entry.read_text())
    res.dim("TEC-DEPS", not ext, "no runtime network dependency" if not ext else f"network references: {ext[:3]}")
    missing = devdoc_missing(ctx.control_text("development"), t["devdoc_sections"])
    res.dim("TEC-DEVDOC", not missing, "development.md has every section" if not missing else f"development.md lacks {missing}")
    report = {"scripts": len(js), "syntax_errors": bad, "unit": {"passed": passed, "failed": failed, "tail": tail},
              "bundle_kb": round(kb, 1), "network_refs": ext, "devdoc_missing": missing}
    path = ctx.out("feasibility-report.json")
    write_json_atomic(path, report)
    res.outputs["feasibility_report"] = str(path)
    res.data["test_results"] = [{"suite": "feasibility: node --test", "passed": passed, "failed": failed, "details": tail}]
    return res
