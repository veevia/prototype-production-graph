"""Executors: who does a node's work.

- TaskPacketExecutor — real agents. Writes `.pdg/tasks/<node>-a<n>.md|json` (everything the agent needs: purpose,
  instructions, prompt, inputs, allowed outputs and schemas, rubric dimensions, previous failures, rework defects, and the
  exact `pdg submit` command with its dispatch token) and returns a pending result. The agent submits later.
- ScriptedExecutor — dry runs and tests. Replays `fixtures/<node>/attempt-<n>/fixture.yaml` (falling back to the latest
  earlier attempt). A fixture may run real commands first (for example the prototype's build script) and then names
  its outputs. Scripted human decisions are applied by the dry-run actor and labelled not human.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .artifacts import ARTIFACT_MODELS
from .context import NodeContext, NodeResult
from .util import PKG_ROOT, rel

if TYPE_CHECKING:  # pragma: no cover
    from .engine import Engine


class Executor:
    name = "base"

    def execute(self, ctx: NodeContext) -> NodeResult:  # pragma: no cover - interface
        raise NotImplementedError


def run_command(cmd: list[str], cwd: Path, log: Path, timeout: float = 600.0, env: dict[str, str] | None = None) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    full_env = {**os.environ, **(env or {})}
    full_env.pop("ELECTRON_RUN_AS_NODE", None)
    with log.open("a") as f:
        f.write(f"$ {' '.join(cmd)}\n")
        f.flush()
        proc = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout, env=full_env)
        f.write(f"[exit {proc.returncode}]\n")
    return proc.returncode


class FixtureError(Exception):
    pass


class ScriptedExecutor(Executor):
    name = "scripted"

    def __init__(self, fixtures: str | Path):
        self.fixtures = Path(fixtures)

    def _dir(self, node_id: str, attempt: int) -> Path:
        base = self.fixtures / node_id
        for n in range(attempt, 0, -1):
            d = base / f"attempt-{n}"
            if d.is_dir():
                return d
        raise FixtureError(f"no fixture for {node_id} (looked for attempt-1..{attempt} under {rel(base, self.fixtures.parent)})")

    def _expand(self, s: str, ctx: NodeContext, fixture: Path) -> str:
        def art(m: re.Match) -> str:
            p = ctx.artifact(m.group(1))
            if p is None:
                raise FixtureError(f"{ctx.node.id}: fixture needs artifact:{m.group(1)}, which does not exist yet")
            return str(p)
        s = re.sub(r"\{artifact:([a-z_]+)\}", art, s)
        return (s.replace("{python}", sys.executable).replace("{project}", str(ctx.project))
                 .replace("{work}", str(ctx.work)).replace("{fixture}", str(fixture)).replace("{pkg}", str(PKG_ROOT)))

    def execute(self, ctx: NodeContext) -> NodeResult:
        fdir = self._dir(ctx.node.id, ctx.attempt)
        spec = yaml.safe_load((fdir / "fixture.yaml").read_text()) or {}
        for cmd in spec.get("run", []):
            argv = [self._expand(a, ctx, fdir) for a in cmd]
            code = run_command(argv, ctx.project, ctx.work / "command.log")
            if code != 0:
                raise FixtureError(f"{ctx.node.id}: fixture command failed ({code}): {' '.join(argv)} — see "
                                   f"{rel(ctx.work / 'command.log', ctx.project)}")
        outputs = {}
        for key, path in (spec.get("outputs") or {}).items():
            p = Path(self._expand(str(path), ctx, fdir))
            outputs[key] = str(p if p.is_absolute() else fdir / p)
        review = None
        if spec.get("review"):
            review = json.loads((fdir / spec["review"]).read_text())
        return NodeResult(outputs=outputs, review=review, decision=spec.get("decision"),
                          feedback=spec.get("feedback", []), actor="agent:scripted-fixture",
                          messages=[f"fixture {rel(fdir, self.fixtures.parent)}"])


class TaskPacketExecutor(Executor):
    name = "task-packet"

    def execute(self, ctx: NodeContext) -> NodeResult:
        eng = ctx.engine
        node = ctx.node
        tasks = eng.project.root / ".pdg" / "tasks"
        tasks.mkdir(parents=True, exist_ok=True)
        packet = eng.task_packet(ctx)
        base = tasks / f"{node.id}-a{ctx.attempt}"
        base.with_suffix(".json").write_text(json.dumps(packet, indent=1, ensure_ascii=False, default=str) + "\n")
        base.with_suffix(".md").write_text(render_packet(packet))
        return NodeResult(pending=True, messages=[f"task packet {rel(base.with_suffix('.md'), eng.project.root)}"])


def schema_path(name: str | None) -> str | None:
    if not name or name not in ARTIFACT_MODELS:
        return None
    return str(PKG_ROOT / "schemas" / "artifacts" / f"{name}.schema.json")


def render_packet(p: dict[str, Any]) -> str:
    lines = [f"# Task packet — {p['node']} · attempt {p['attempt']}", "",
             f"**Agent:** `{p['agent']}`" + (f" (consult: {', '.join(p['support_agents'])})" if p['support_agents'] else ""),
             f"**Purpose:** {p['purpose']}", "", "## Instructions", "", p["instructions"], ""]
    if p.get("work_dir"):
        lines += ["## Work folder", "", f"- `{p['work_dir']}`",
                  "- `--output` paths are resolved relative to this folder unless they are absolute.", ""]
    if p.get("rerun"):
        r = p["rerun"]
        lp = r["last_passed"]
        lines += ["## Why this attempt", "", f"This node passed before (attempt a{lp['attempt']}); it runs again because "
                  f"{(r.get('reason') or 'the run re-opened it').rstrip('.')}.", ""]
        if r.get("changed_inputs"):
            lines += ["What changed in your inputs since that pass:", ""]
            for c in r["changed_inputs"]:
                lines.append(f"- `{c['input']}`: {c['was']} → {c['now']}")
                if c.get("diff"):
                    lines += ["", "```diff", *c["diff"], "```", ""]
        else:
            lines += ["None of your artifact or control inputs changed; state inputs may have.", ""]
        lines += ["", f"Your last passed attempt (a{lp['attempt']}) submitted:", ""]
        lines += [f"- `{k}` → `{v}`" for k, v in lp["outputs"].items()]
        lines += ["", "If nothing you own needs to change, you may submit those files again. For a control document, copy "
                  "the current `controls/<doc>.md` and re-apply only your sections: other writers' sections may have "
                  "changed since.", ""]
    if p.get("rejudge"):
        rj = p["rejudge"]
        lines += ["## Re-judged under a new configuration", "",
                  f"A configuration change ({', '.join(rj.get('changed') or []) or 'the judging'}) changed how this node is "
                  "judged, so its last pass no longer stands.", ""]
        if rj.get("dims"):
            lines += ["Dimensions new or changed since it passed:", ""] + [f"- {d}" for d in rj["dims"]] + [""]
        fails = rj.get("last_pass") or []
        if fails:
            lines += [f"Your last passed output (a{rj.get('passed_attempt')}) now fails these checks; fix them first:", ""]
            lines += [f"- `{f['dim']}`: {f['evidence']}" for f in fails] + [""]
        elif rj.get("rechecked", True):
            lines += [f"Your last passed output (a{rj.get('passed_attempt')}) passes the tool checks re-run on it here "
                      f"({', '.join(rj.get('rechecked') or [])}); the browser suite and reviews judge it after you submit.", ""]
        else:   # a gate's hook, or no tool check that can run without a browser (batch 7 review S2)
            lines += ["None of this node's checks could be re-run on its last passed output here; they all run when you "
                      "submit.", ""]
    if p.get("carried"):
        cr = p["carried"]
        lines += ["## Your parked submission", "",
                  f"Your submission from attempt a{cr['attempt']} ({cr['at']}) was parked while the run was blocked, and "
                  f"was never judged: {cr['why']}. Its files are still here:", ""]
        lines += [f"- `{k}` → `{v}`" for k, v in cr["outputs"].items()]
        lines += ["", "Check them against this packet, and submit again what still holds.", ""]
    if p.get("acceptance"):
        ac = p["acceptance"]
        lines += ["## Before you submit: the acceptance lines to trace", "",
                  "PLN-ACCEPTANCE fails a P0 line with no trace in `acceptance_trace`; an untraced P1 line is listed. Copy "
                  "each line as it stands here, with its requirement id, and give exactly one of: `scenario` + 1-based "
                  "`step` of an expectation, a `forbidden_text` entry, `covered_by` one of the checks below, or "
                  "`out_of_scope` with the reason.", ""]
        lines += [f"- **{x['requirement']}** ({x['priority']}) {x['acceptance']}" for x in ac["lines"]]
        lines += ["- none" if not ac["lines"] else "", "`covered_by` may name (a MUST check every build round runs): "
                  + ", ".join(f"`{d}` ({n})" for d, n in sorted(ac["checks"].items())), ""]
    if p.get("acceptance_owed"):
        lines += ["## Acceptance lines the plan counts on your checks for", "",
                  "The plan traced these requirement lines to your dimensions instead of a scenario step. Score each "
                  "named dimension with its line in mind, and report a line the build does not meet as a finding.", ""]
        lines += [f"- `{x['check']}`: **{x['requirement']}** {x['acceptance']}" for x in p["acceptance_owed"]] + [""]
    if p.get("fidelity_gate") is not None:
        fg = p["fidelity_gate"]
        lines += ["## Before you submit: the fidelity gate", "",
                  "At mid or high fidelity, every riskiest assumption must be validated with evidence, or accepted as a risk "
                  "by a named human (`pdg accept-risk <project> <id> --actor Wei --reason \"…\"`), before the plan can "
                  "pass PLN-FIDELITY-GATE. Low fidelity needs neither.", ""]
        lines += [f"- **{a['id']}** {a['statement']} — " + (f"accepted as a risk by {a['accepted_by']}" if a["accepted_by"]
                  else "not accepted: a mid or high plan that leaves it unvalidated fails, so ask Wei first") for a in fg]
        lines += ["- none: the gate holds at any fidelity"] if not fg else []
        lines.append("")
    if p.get("open_feedback"):
        fb = p["open_feedback"]
        lines += [f"## Open feedback ({len(fb)}): map every item", "",
                  "Each item becomes a defect, joins one, or is dismissed with a reason; none may stay open.", ""]
        lines += [f"- **{f['id']}** by `{f['actor']}`" + (" (simulated)" if f.get("simulated") else "")
                  + (f" at `{f['at']}`" if f.get("at") else "") + (f", severity {f['severity']}" if f.get("severity") else "")
                  + f": {f['text']}" for f in fb]
        lines.append("")
    if p.get("rerun_changes"):
        lines += ["## Change requests and invalidations since your last pass", "",
                  "Carry these oldest first. If one names a document you write and it has not been applied yet, say so in "
                  "your submission.", ""]
        for c in p["rerun_changes"]:
            suffix = " — names a document this node writes; confirm it is applied" if c.get("unapplied_to_own_document") else ""
            lines.append(f"- **{c['id']}** ({c['kind']}): {c['reason']}{suffix}")
        lines.append("")
    if p.get("control_locks"):
        lines += ["## Locked control documents", "",
                  "This node writes a locked control document. A change request unlocks it before you submit:", ""]
        lines += [f"- `{x['doc']}.md` locked by {x['locked_by']}: `{x['command']}`" for x in p["control_locks"]]
        lines.append("")
    if p.get("blocking_traced_here"):
        lines += ["## Blocking defects traced to this node", "",
                  "Whatever re-ran this node, these are open work items for this node. Fix the smallest thing and prove "
                  "the acceptance check.", ""]
        lines += [f"- **{d['id']}** `{d['signature']}` ({d['severity']}, {d['status']}): {d['message']}"
                  f" Fix: {d['smallest_fix']} Acceptance: {d['acceptance_check']}"
                  for d in p["blocking_traced_here"]]
        lines.append("")
    if p.get("convergence"):
        conv = p["convergence"]
        if conv.get("trend"):
            lines += ["## Convergence signal", "", "Blocking trend: " + " → ".join(str(x) for x in conv["trend"]), ""]
        if conv.get("recurring"):
            lines += ["Recurring components/screens across cycles:", ""]
            lines += [f"- `{g['component']}`: {', '.join(g['defects'])}" for g in conv["recurring"]]
            lines.append("")
    if p.get("cycle_fixes"):
        lines += ["## Fixes in this rework cycle: update what you own that asserts them", "",
                  "These defects are being fixed elsewhere in this cycle (the node named on each). Their fixes can change "
                  "copy, states or layout that your work asserts, such as a scenario's expected text. Check each one "
                  "against your outputs and update any expectation it makes stale; change nothing else.", ""]
        lines += [f"- **{d['id']}** `{d['signature']}` → `{d['traced_node']}` ({d['severity']}): {d['message']}"
                  f" Fix: {d['smallest_fix']} Fixed when: {d['acceptance_check']}" for d in p["cycle_fixes"]]
        lines.append("")
    if p.get("precheck"):
        pre = p["precheck"]
        lines += ["## Pre-check", ""]
        for key, path in (pre.get("outputs") or {}).items():
            lines.append(f"- output `{key}` → `{path}`")
        for dim_id, dim in (pre.get("dimensions") or {}).items():
            verdict = "PASS" if dim.get("passed") else "FAIL"
            evidence = dim.get("evidence") or "no evidence recorded"
            findings = dim.get("findings") or []
            suffix = f" ({len(findings)} finding{'s' if len(findings) != 1 else ''})" if findings else ""
            lines.append(f"- `{dim_id}` {verdict}: {evidence}{suffix}")
        for err in pre.get("errors") or []:
            lines.append(f"- error: {err}")
        for msg in pre.get("messages") or []:
            lines.append(f"- message: {msg}")
        lines.append("")
    if p.get("previous_failures"):
        lines += ["## The previous attempt failed because", ""] + [f"- {f}" for f in p["previous_failures"]] + [""]
    if p.get("rework"):
        lines += ["## Rework: fix exactly these defects " + ("(and nothing else, apart from the advisory defects below)"
                                                             if p.get("advisory") else "(and nothing else)"), ""]
        for d in p["rework"]:
            lines += [f"- **{d['id']}** `{d['signature']}` ({d['severity']}): {d['message']}",
                      f"  - smallest fix: {d['smallest_fix']}", f"  - acceptance check: {d['acceptance_check']}"]
        lines.append("")
    if p.get("in_rework"):
        lines += ["## Still in rework (keep these fixed)", "",
                  "Traced to this node and not yet judged by the gate. Whatever re-opened the node, do not regress them.", ""]
        lines += [f"- **{d['id']}** `{d['signature']}` ({d['severity']}): {d['message']} Fixed when: "
                  f"{d['acceptance_check'] or '(no acceptance check)'}" for d in p["in_rework"]]
        lines.append("")
    if p.get("advisory"):
        lines += ["## Advisory defects traced to this node (optional: fix if cheap)", "",
                  "They do not block and are never routed here on their own. Each resolves at a gate once this node has "
                  "re-run and no review reports it, so fix them now, while this node runs anyway.", ""]
        for d in p["advisory"]:
            lines += [f"- **{d['id']}** `{d['signature']}` ({d['severity']}): {d['message']}",
                      f"  - smallest fix: {d['smallest_fix']}"]
        lines.append("")
    if p.get("open_advisories"):
        lines += [f"## Open advisory defects ({len(p['open_advisories'])}): each waits on its node re-running", "",
                  "The gate routes only blocking defects. An advisory resolves once its node has re-run and the reviewer "
                  "that found it no longer reports it; a rework cycle surely re-runs only its targets, so an advisory "
                  "elsewhere can stay open for good (if it names a control document, that document keeps contradicting "
                  "the build). For each one that should be fixed now, do what it says; the gate report lists those a "
                  "rework cycle may leave open.", ""]
        lines += [f"- **{d['id']}** `{d['signature']}` ({d['severity']}, {d['dimension']}) → {d['traced_node']}: "
                  f"{' '.join(str(d['message']).split())} To fix it now: {d['remedy']}" for d in p["open_advisories"]]
        lines.append("")
    if p.get("reverify"):
        lines += ["## Open defects you are asked to re-verify", "",
                  "A defect resolves at the next gate only when no current review reports its signature. If one is still "
                  "true, file it again with the same dimension and location (and `element`, if the signature has one); "
                  "if it is fixed, file nothing for it. A **deferred** one waits on a person's decision, not a fix: the gate "
                  "neither routes nor resolves it, and filing nothing leaves it as it is. If it still holds, you need not "
                  "file it again (file it only to update its description). If this build no longer shows it, put its id in "
                  "the review's `no_longer_holds` list: the gate names it for that person's decision (field run W61).", ""]
        lines += [f"- **{d['id']}** `{d['signature']}` ({d['severity']}, {d['status']}"
                  + (f"; deferred: waits on {d['deferred_trigger'] or 'a decision'}; still true: nothing to file; no longer "
                     "true: list it in `no_longer_holds`" if d.get("deferred") else "")
                  + f"): {d['message']} Fixed when: {d['acceptance_check'] or '(no acceptance check)'}" for d in p["reverify"]]
        lines.append("")
    if p.get("under_review"):
        b = p["under_review"]
        lines += ["## The build under review", "", f"Build v{b['version']}, `{b['entry']}`, sha256 `{b['sha256']}`. State "
                  f"it as `\"build\": \"{b['sha256'][:16]}\"` in your review; a review naming another build is refused.", ""]
    if p.get("still_fixed"):
        lines += [f"## Still fixed? Re-check the {len(p['still_fixed'])} resolved defects this review found", "",
                  "A later fix can quietly undo an earlier one. Re-run each acceptance check on this build. If one fails "
                  "again, report it at exactly its signature: it re-opens with its history. If it holds, file nothing.", ""]
        lines += [f"- **{d['id']}** `{d['signature']}` (resolved at v{d['resolved_at_version']}): "
                  f"{d['acceptance_check'] or '(no acceptance check)'}" for d in p["still_fixed"]]
        lines.append("")
    lines += ["## Inputs", ""] + [f"- `{k}` → {v}" for k, v in p["inputs"].items()] + [""]
    lines += ["## Context", ""] + [f"- {c}" for c in p["context"]] + [""]
    lines += ["## Load these skills", ""] + [f"- `{s}`" for s in p["skills"]] + [""]
    lines += ["## Outputs to submit", "",
              "Pre-submit without using an attempt: run `python -m pdg check-node <project> "
              f"{p['node']} --output key=path …`. It runs the schema, this node's tool checks and gate preconditions. "
              f"`python -m pdg check-output {p['node']} <key> <file>` is a schema-only alias for older packets.", ""]
    for o in p["outputs"]:
        extra = f" — schema `{o['schema']}`" if o.get("schema") else ""
        lines.append(f"- `{o['key']}` ({o['kind']}{', required' if o['required'] else ', optional'}){extra}: {o['description']}")
    lines += ["", "## Quality bar (scored after you submit)", ""]
    for d in p["dimensions"]:
        lines.append(f"- `{d['id']}` {d['level']} · {d['check']} · {d['mode']}: {d['name']} — {d['threshold']}")
    secs = p["controls"].get("sections") or {}
    writes = [d + (f" (your sections: {', '.join(s.replace('_preamble', 'preamble') for s in secs[d])})" if d in secs else "")
              for d in p["controls"]["write"]]
    lines += ["", "## Control documents", "", f"- read: {', '.join(p['controls']['read']) or '—'}",
              f"- write: {'; '.join(writes) or '—'}"]
    if p["controls"]["write"]:
        lines += ["- How to write one: copy `controls/<doc>.md` into your work folder, change only your sections there, and "
                  "submit that copy. Never edit `controls/` directly: the engine installs your sections after its checks."]
    lines += ["", "## Prompt", "", p["prompt"], "",
              "## Submit", "", "```bash", p["submit"], "```", ""]
    return "\n".join(lines)
