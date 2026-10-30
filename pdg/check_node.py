"""Read-only node submission checks shared by ``check-node`` and ``submit --dry-run``."""

from __future__ import annotations

import shlex
import tempfile
from pathlib import Path
from typing import Any

from .context import CheckResult, NodeContext
from .controls import append_only_violations, duplicate_headings, unclosed_fence
from .evaluation import evaluate_tool_dims, unreported_tool_dims
from .models import NodeKind, NodeStatus


def submit_command(project: Path, node: str, outputs: dict[str, str], token: str | None, actor: str | None) -> str:
    parts = ["python", "-B", "-m", "pdg", "submit", str(project), node]
    if token:
        parts += ["--token", token]
    if actor:
        parts += ["--actor", actor]
    for key, path in sorted(outputs.items()):
        parts += ["--output", f"{key}={path}"]
    return " ".join(shlex.quote(p) for p in parts)


def check_node(eng, node_id: str, outputs: dict[str, str]) -> dict[str, Any]:
    """Run the checks a submission would run, without committing state or writing under ``.pdg``."""
    node, rt = eng.node(node_id), eng.rt(node_id)
    if rt.status != NodeStatus.WAITING_AGENT:
        return {"ok": False, "refused": [f"{node_id} is {rt.status.value}, not waiting for a submission"], "failures": [],
                "advisory": [], "deferred": [], "dimensions": {}, "resolved": {}, "command": ""}
    work = eng.project.root / "work" / node_id / f"a{rt.attempt}"
    resolved, refused = _resolve_outputs(eng, outputs, work)
    with tempfile.TemporaryDirectory(prefix="pdg-check-node-") as td:
        ctx = NodeContext(eng, node, rt.attempt, Path(td), rt.token or "", rt.fingerprint or "")
        changed = eng._load_precheck(ctx)
        precheck_outputs = set(ctx.precheck.outputs) if ctx.precheck else set()
        required = [o.key for o in node.outputs if o.required and not eng._produced_by_hook(node, o.key)
                    and o.key not in precheck_outputs]
        for key in required:
            if key not in resolved:
                refused.append(f"missing required output '{key}'")
        unknown = sorted(set(resolved) - {o.key for o in node.outputs})
        if unknown:
            refused.append(f"unknown output key(s) {unknown}")
        tool_keys = sorted(set(resolved) & precheck_outputs)
        if tool_keys:
            refused.append(f"{', '.join(tool_keys)}: written by the engine's own check; submit only your outputs")
        if refused:
            return _report(eng, node_id, resolved, refused=refused)
        snapshot = eng.state.model_copy(deep=True)
        ledger_tail = eng.ledger._last
        try:
            with eng.ledger.deferred():
                refused, failures, advisory, dims = _submission_findings(eng, ctx, resolved, changed)
        finally:
            eng.state = snapshot
            eng.ledger._last = ledger_tail
        return _report(eng, node_id, resolved, refused=refused, failures=failures, advisory=advisory, dimensions=dims)


def _resolve_outputs(eng, outputs: dict[str, str], work: Path) -> tuple[dict[str, str], list[str]]:
    resolved: dict[str, str] = {}
    problems: list[str] = []
    for key, raw in outputs.items():
        p = Path(raw)
        p = (p if p.is_absolute() else work / p).resolve()
        if not p.exists():
            problems.append(f"output {key}: {p} does not exist")
            continue
        try:
            p.relative_to(eng.project.root.resolve())
        except ValueError:
            problems.append(f"output {key}: {p} is outside the project")
            continue
        resolved[key] = str(p)
    return resolved, problems


def _submission_findings(eng, ctx: NodeContext, outputs: dict[str, str], changed: list[str],
                         ) -> tuple[list[str], list[str], list[str], dict[str, Any]]:
    node = ctx.node
    refused = eng._schema_refusals(node, outputs) or eng._wrong_build(node, outputs)
    if not refused:
        live = eng._live_control_outputs(node, outputs)
        refused += eng._lock_only_refusals(node, outputs)
    if not refused:
        regs, refused = eng._register_outputs(ctx, {**(ctx.precheck.outputs if ctx.precheck else {}), **outputs})
        ctx.submitted = {k: eng.project.root / r.path for k, r in regs.items()}
    if not refused:
        live = eng._live_control_outputs(node, outputs)
        refused += eng._integrity_problems(ignore_docs=set(live.values()))
    if not refused:
        live_outputs = eng._live_control_outputs(node, outputs)
        for o in node.outputs:
            if o.kind == "control" and o.key in ctx.submitted:
                if o.key in live_outputs:
                    refused += _live_control_install_problems(eng, node.id, node.controls.write, o.doc, ctx.submitted[o.key])
                else:
                    refused += eng.controls.check_install(node.id, node.controls.write, o.doc, ctx.submitted[o.key])
    if refused:
        return refused, [], [], {}
    failures = ([f"tool outputs changed after the engine's check ran: {', '.join(changed)}"] if changed else [])
    results: dict[str, CheckResult] = {}
    if not failures:
        for chk in node.completion:
            failures += eng._run_check(chk, ctx, results)
    if not failures:
        failures += unreported_tool_dims(node, results, eng.rubrics, eng.rule_states)
    dims: dict[str, Any] = {}
    if not failures:
        if node.kind == NodeKind.REVIEW:
            own = set().union(*(r.own for r in results.values())) if results else set()
            records, _, blocking = evaluate_tool_dims(node, results, eng.rubrics, eng.rule_states, only=own)
        else:
            records, _, blocking = evaluate_tool_dims(node, results, eng.rubrics, eng.rule_states)
        failures += blocking
    else:
        records = []
    if not failures and node.kind == NodeKind.GATE and node.run and node.run.tool:
        hook = eng._call_tool(node.run.tool, ctx)
        results[node.run.tool] = hook
        failures += hook.errors
        failures += unreported_tool_dims(node, {node.run.tool: hook}, eng.rubrics, eng.rule_states)
        records, _, blocking = evaluate_tool_dims(node, {node.run.tool: hook}, eng.rubrics, eng.rule_states)
        failures += blocking
        outcome = hook.outcome or "pass"
        if not failures and outcome not in node.outcomes:
            failures.append(f"outcome '{outcome}' is not one of {node.outcomes}")
    for name, result in results.items():
        dims[name] = result.to_dict()
    advisory = [r.id for r in records if r.status == "advisory_fail"]
    return [], failures, advisory, dims


def _live_control_install_problems(eng, node_id: str, writes: list[str], doc: str, src: Path) -> list[str]:
    if doc not in writes:
        return [f"{node_id} may not write control document {doc}"]
    if src.stat().st_size == 0 or not src.read_text().strip():
        return [f"{doc}.md submitted empty"]
    submitted = src.read_text()
    opened = unclosed_fence(submitted)
    if opened is not None:
        return [f"{doc}.md: the code fence opened at line {opened} is never closed; close it (an open fence swallows "
                "every later section, other writers' included)"]
    dups = duplicate_headings(submitted)
    if dups:
        return [f"{doc}.md: section heading(s) {', '.join(dups)} appear more than once; merge each into one section"]
    text, _ = eng.controls.merge(node_id, doc, src)
    if text.encode() and text == eng.controls.accepted_text(doc):
        return []
    return append_only_violations(eng.controls.accepted_text(doc), text)


def _report(eng, node_id: str, outputs: dict[str, str], refused: list[str] | None = None,
            failures: list[str] | None = None, advisory: list[str] | None = None,
            dimensions: dict[str, Any] | None = None) -> dict[str, Any]:
    deferred = [d.id for d in eng.state.evaluation.defects if d.deferred and d.status in ("open", "needs_human", "persisting")]
    rt = eng.rt(node_id)
    return {"ok": not refused and not failures, "refused": refused or [], "failures": failures or [],
            "advisory": advisory or [], "deferred": deferred, "dimensions": dimensions or {}, "resolved": outputs,
            "command": submit_command(eng.project.root, node_id, outputs, rt.token, f"agent:{eng.node(node_id).agent}")}
