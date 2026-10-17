"""Load, index and validate the workflow graph (graph/workflow.yaml).

`structural_errors` is the contract `python -m pdg validate` enforces and the engine re-checks before it opens a run:
the engine refuses a graph that fails any rule. `workspace_errors` adds the checks that need the surrounding workspace
(skills must exist in 03_Agents-and-Skills/INDEX.md); a standalone checkout skips them, and a workspace whose index is
missing gets a warning.
"""

from __future__ import annotations

import importlib
import re
from collections import defaultdict, deque
from functools import cached_property
from pathlib import Path
from typing import Any, Callable

import yaml

from .artifacts import ARTIFACT_MODELS
from .models import (CONTROL_DOCS, LIFECYCLE_STEPS, PHASES, STAGES, EdgeDef, EdgeKind, NodeDef, NodeKind, ProjectState,
                     Workflow)
from .util import PKG_ROOT, model_has_path

DEFAULT_WORKFLOW = PKG_ROOT / "graph" / "workflow.yaml"
ESCALATE = "@escalate"
SEVERITIES = ["P1", "P2", "P3", "P4"]
_ALLOWED_GATE_HOOKS = frozenset({"freeze_inputs", "review_gate", "regeneration_plan", "release", "learning"})
_REQUIRED_GATE_HOOKS = frozenset({"freeze_inputs", "review_gate", "regeneration_plan", "learning"})


def load_workflow(path: str | Path | None = None) -> Workflow:
    data = yaml.safe_load(Path(path or DEFAULT_WORKFLOW).read_text())
    return Workflow.model_validate(data)


def outcome_matches(when: str, outcome: str | None, targets: list[str] | None = None) -> bool:
    if when == "*":
        return outcome is not None
    if when.startswith("target:"):
        return when.split(":", 1)[1] in (targets or [])
    return outcome in when.split("|")


def resolve_tool(ref: str) -> Callable[..., Any]:
    module, _, fn = ref.partition(":")
    mod = importlib.import_module(f"pdg.tools.{module}")
    return getattr(mod, fn)


class GraphIndex:
    def __init__(self, wf: Workflow):
        self.wf = wf
        self.nodes = {n.id: n for n in wf.nodes}
        self.incoming: dict[str, list[EdgeDef]] = defaultdict(list)
        self.outgoing: dict[str, list[EdgeDef]] = defaultdict(list)
        for e in wf.edges:
            self.incoming[e.target].append(e)
            self.outgoing[e.source].append(e)

    def flow_in(self, node_id: str) -> list[EdgeDef]:
        return [e for e in self.incoming[node_id] if e.kind == EdgeKind.FLOW]

    def flow_out(self, node_id: str) -> list[EdgeDef]:
        return [e for e in self.outgoing[node_id] if e.kind == EdgeKind.FLOW]

    def loops_out(self, node_id: str) -> list[EdgeDef]:
        return [e for e in self.outgoing[node_id] if e.kind == EdgeKind.LOOP]

    def escalates_out(self, node_id: str) -> list[EdgeDef]:
        return [e for e in self.outgoing[node_id] if e.kind == EdgeKind.ESCALATE]

    @cached_property
    def topo(self) -> list[str]:
        """Topological order of the flow DAG (START first). Raises ValueError on a flow cycle."""
        names = [self.wf.start] + list(self.nodes) + [self.wf.end]
        indeg = {n: 0 for n in names}
        succ: dict[str, list[str]] = defaultdict(list)
        for e in self.wf.edges:
            if e.kind == EdgeKind.FLOW and e.source in indeg and e.target in indeg:
                succ[e.source].append(e.target)
                indeg[e.target] += 1
        order_key = {n: i for i, n in enumerate(names)}
        queue = deque(sorted((n for n in names if indeg[n] == 0), key=order_key.get))
        out: list[str] = []
        while queue:
            n = queue.popleft()
            out.append(n)
            for m in sorted(succ[n], key=order_key.get):
                indeg[m] -= 1
                if indeg[m] == 0:
                    queue.append(m)
        if len(out) != len(names):
            cyc = sorted(n for n in names if indeg[n] > 0)
            raise ValueError(f"flow edges form a cycle through {cyc}")
        return out

    def descendants(self, node_id: str) -> set[str]:
        """Every node reachable from `node_id` over flow edges (excluding END)."""
        seen: set[str] = set()
        stack = [node_id]
        while stack:
            cur = stack.pop()
            for e in self.flow_out(cur):
                if e.target in self.nodes and e.target not in seen:
                    seen.add(e.target)
                    stack.append(e.target)
        return seen

    def section_owners(self, doc: str) -> dict[str, str]:
        """Section title → owning node of a shared control document; {"*": writer} for a single-writer document."""
        writers = [n for n in self.wf.nodes if doc in n.controls.write]
        if len(writers) == 1:
            return {"*": writers[0].id}
        return {sec: n.id for n in writers for sec in n.controls.sections.get(doc, [])}

    def ancestors(self, node_id: str) -> set[str]:
        seen: set[str] = set()
        stack = [node_id]
        while stack:
            cur = stack.pop()
            for e in self.flow_in(cur):
                if e.source in self.nodes and e.source not in seen:
                    seen.add(e.source)
                    stack.append(e.source)
        return seen

    def order(self, ids: set[str] | list[str]) -> list[str]:
        pos = {n: i for i, n in enumerate(self.topo)}
        return sorted(ids, key=lambda n: pos.get(n, 10**6))

    @property
    def regen_node(self) -> str | None:
        return next((n.id for n in self.wf.nodes if n.gate == "regeneration_plan"), None)

    @property
    def freeze_node(self) -> str | None:
        return next((n.id for n in self.wf.nodes if n.gate == "freeze_inputs"), None)

    @property
    def gate_node(self) -> str | None:
        return next((n.id for n in self.wf.nodes if n.gate == "review_gate"), None)

    def reviewer_nodes(self) -> list[str]:
        gate = self.gate_node
        return [e.source for e in self.flow_in(gate)] if gate else []


def control_reads(node: NodeDef) -> list[str]:
    docs = list(node.controls.read)
    for ref in node.inputs:
        if ref.startswith("control:"):
            docs.append(ref.split(":", 1)[1])
    return sorted(set(docs))


# ----------------------------------------------------------------------------------------------------- validation

_REQUIRED_LISTS = ["depends_on", "inputs", "context", "state_read", "state_write", "skills", "tools", "outputs",
                   "completion", "evaluation", "failure_conditions", "provenance", "outcomes"]
_REQUIRED_TEXT = ["name", "lifecycle_step", "purpose", "agent", "instructions", "prompt"]
_EDGE_TEXT = ["transfers", "threshold", "behavior"]
_INPUT_RE = re.compile(r"^(state|artifact|control|files|defects|feedback|rework):.+$")


def structural_errors(wf: Workflow, root: Path = PKG_ROOT) -> list[str]:
    errs: list[str] = []
    idx = GraphIndex(wf)
    ids = [n.id for n in wf.nodes]
    known = set(ids) | {wf.start, wf.end, ESCALATE}
    subgraphs = {s.id: s for s in wf.subgraphs}

    # 1. identity and brief order
    if len(ids) != len(set(ids)):
        errs.append("duplicate node ids")
    if len({e.id for e in wf.edges}) != len(wf.edges):
        errs.append("duplicate edge ids")
    if len(wf.nodes) != len(LIFECYCLE_STEPS):
        errs.append(f"expected {len(LIFECYCLE_STEPS)} nodes (one per lifecycle step), found {len(wf.nodes)}")
    for i, n in enumerate(wf.nodes):
        if n.num != i + 1:
            errs.append(f"{n.id}: num {n.num} out of order (expected {i + 1})")
        if i < len(LIFECYCLE_STEPS) and n.lifecycle_step != LIFECYCLE_STEPS[i]:
            errs.append(f"{n.id}: lifecycle_step '{n.lifecycle_step}' ≠ brief step {i + 1} '{LIFECYCLE_STEPS[i]}'")
        if n.phase not in PHASES:
            errs.append(f"{n.id}: unknown phase {n.phase}")
        if n.stage not in STAGES:
            errs.append(f"{n.id}: unknown stage {n.stage}")
        if n.subgraph not in subgraphs:
            errs.append(f"{n.id}: unknown subgraph {n.subgraph}")
        elif n.id not in subgraphs[n.subgraph].nodes:
            errs.append(f"{n.id}: not listed in subgraph {n.subgraph}")
        if n.gate and n.gate not in _ALLOWED_GATE_HOOKS:
            errs.append(f"{n.id}: unknown gate hook '{n.gate}'")
    for s in wf.subgraphs:
        for node_id in s.nodes:
            if node_id not in set(ids):
                errs.append(f"subgraph {s.id} lists unknown node {node_id}")
            elif next(n for n in wf.nodes if n.id == node_id).subgraph != s.id:
                errs.append(f"subgraph {s.id} lists {node_id}, but the node declares subgraph "
                            f"{next(n for n in wf.nodes if n.id == node_id).subgraph}")
    for gate in sorted(_REQUIRED_GATE_HOOKS):
        count = sum(1 for n in wf.nodes if n.gate == gate)
        if count != 1:
            errs.append(f"required gate hook {gate} appears {count} times (expected exactly 1)")
    if idx.gate_node and not idx.reviewer_nodes():
        errs.append(f"review_gate node {idx.gate_node} has no reviewer flow inputs")
    for e in wf.edges:
        for end in (e.source, e.target):
            if end not in known:
                errs.append(f"{e.id}: unknown endpoint {end}")
    if errs:
        return errs

    # 2. edge semantics
    try:
        _ = idx.topo
    except ValueError as exc:
        errs.append(str(exc))
        return errs
    seen_flow: set[tuple[str, str]] = set()
    for e in wf.edges:
        if e.kind == EdgeKind.FLOW:
            if (e.source, e.target) in seen_flow:
                errs.append(f"{e.id}: duplicate flow edge {e.source} → {e.target}")
            seen_flow.add((e.source, e.target))
            if e.target == ESCALATE:
                errs.append(f"{e.id}: a flow edge cannot target {ESCALATE}")
        elif e.kind == EdgeKind.LOOP:
            if not e.max_traversals or e.max_traversals < 1:
                errs.append(f"{e.id}: loop edge needs max_traversals ≥ 1 (unbounded loop)")
            if e.target not in idx.nodes:
                errs.append(f"{e.id}: loop edge must target a node")
            elif e.target != e.source and e.target not in idx.ancestors(e.source):
                errs.append(f"{e.id}: loop edge {e.source} → {e.target} does not go upstream")
            # one budget: a rework edge that allows fewer cycles than the policy made the gate say "rework" and the run
            # then block on the edge (field run W23); it now matches the policy (backlog N-03)
            if (e.source == idx.regen_node and e.max_traversals is not None
                    and e.max_traversals != wf.policies.max_rework_cycles):
                errs.append(f"{e.id}: rework edge allows {e.max_traversals} traversals but policies.max_rework_cycles is "
                            f"{wf.policies.max_rework_cycles}; make them equal")
        elif e.kind == EdgeKind.ESCALATE and e.target != ESCALATE:
            errs.append(f"{e.id}: escalate edge must target {ESCALATE}")
        if e.transition == "deterministic" and e.when != "*":
            errs.append(f"{e.id}: deterministic transition needs when '*' (has '{e.when}')")
        if e.transition == "conditional" and e.when == "*":
            errs.append(f"{e.id}: conditional transition cannot use when '*'")
        if e.when.startswith("target:"):
            target = e.when.split(":", 1)[1]
            if target not in idx.nodes:
                errs.append(f"{e.id}: target condition names unknown node {target}")
            elif e.target != target:
                errs.append(f"{e.id}: when target {target} does not match edge target {e.target}")
            if idx.nodes.get(e.source) and idx.nodes[e.source].gate != "regeneration_plan":
                errs.append(f"{e.id}: target: edges belong only to the regeneration node")
        for f in _EDGE_TEXT:
            if not getattr(e, f):
                errs.append(f"{e.id}: empty {f}")
    sev = wf.policies.blocking_severities
    if not sev or sev != SEVERITIES[:len(sev)]:
        errs.append(f"blocking_severities must start at P1 and be contiguous (got {sev})")

    # 3. reachability
    reach = {wf.start}
    frontier = [wf.start]
    while frontier:
        cur = frontier.pop()
        for e in idx.outgoing[cur]:
            if e.kind != EdgeKind.ESCALATE and e.target not in reach:
                reach.add(e.target)
                frontier.append(e.target)
    for n in ids:
        if n not in reach:
            errs.append(f"{n}: unreachable from {wf.start}")
    for n in ids:
        if not _reaches_end(idx, n):
            errs.append(f"{n}: {wf.end} is not reachable from this node")

    # 4. no dead-end outcome; human outcomes are node outcomes
    regen = idx.regen_node
    for n in wf.nodes:
        out_edges = idx.outgoing[n.id]
        for o in n.outcomes:
            if not any(outcome_matches(e.when, o) for e in out_edges if not e.when.startswith("target:")):
                if not (n.id == regen and any(e.when.startswith("target:") for e in out_edges)):
                    errs.append(f"{n.id}: outcome '{o}' has no outgoing edge (dead end)")
        if n.human_review.required:
            for o in n.human_review.outcomes:
                if o not in n.outcomes:
                    errs.append(f"{n.id}: human outcome '{o}' is not a node outcome")
            if n.human_review.dry_run_decision not in n.human_review.outcomes:
                errs.append(f"{n.id}: dry_run_decision is not a human outcome")
        for e in out_edges:
            if e.when not in ("*",) and not e.when.startswith("target:"):
                for o in e.when.split("|"):
                    if o not in n.outcomes:
                        errs.append(f"{e.id}: when '{o}' is not an outcome of {n.id}")

    # 5. join deadlock safety
    errs += _join_errors(wf, idx)

    # 6. dependencies are the flow predecessors
    for n in wf.nodes:
        preds = sorted(e.source for e in idx.flow_in(n.id) if e.source != wf.start)
        if sorted(n.depends_on) != preds and not (n.depends_on == ["START"] and not preds):
            errs.append(f"{n.id}: depends_on {sorted(n.depends_on)} ≠ flow predecessors {preds}")

    # 7. completeness and resolvable references
    for n in wf.nodes:
        for f in _REQUIRED_LISTS:
            if not getattr(n, f):
                errs.append(f"{n.id}: empty {f}")
        for f in _REQUIRED_TEXT:
            if not getattr(n, f):
                errs.append(f"{n.id}: empty {f}")
        if not n.retry.behavior.strip():
            errs.append(f"{n.id}: empty retry.behavior")
        for f in ("after", "to", "report"):
            if not getattr(n.escalation, f).strip():
                errs.append(f"{n.id}: empty escalation.{f}")
        for ref in n.inputs:
            if not _INPUT_RE.match(ref):
                errs.append(f"{n.id}: malformed input ref '{ref}'")
            elif ref.startswith("state:") and not model_has_path(ProjectState, ref[6:]):
                errs.append(f"{n.id}: input state path '{ref[6:]}' is not in the typed state")
            elif ref.startswith("control:") and ref[8:] not in CONTROL_DOCS:
                errs.append(f"{n.id}: unknown control document '{ref[8:]}'")
        for p in n.state_read + n.state_write:
            if not model_has_path(ProjectState, p):
                errs.append(f"{n.id}: state path '{p}' is not in the typed state")
        for o in n.outputs:
            if o.schema_name and o.schema_name not in ARTIFACT_MODELS:
                errs.append(f"{n.id}: output {o.key} has unknown schema '{o.schema_name}'")
            if o.kind == "control":
                if o.doc not in CONTROL_DOCS:
                    errs.append(f"{n.id}: output {o.key} installs unknown control document '{o.doc}'")
                elif o.doc not in n.controls.write:
                    errs.append(f"{n.id}: output {o.key} installs {o.doc} but controls.write does not allow it")
            for field, path in o.state_fields.items():
                if not any(path == w or path.startswith(w + ".") for w in n.state_write):
                    errs.append(f"{n.id}: output {o.key} writes {path}, which is not in state_write")
        for d in n.controls.read + n.controls.write + n.controls.lock_on_approval:
            if d not in CONTROL_DOCS:
                errs.append(f"{n.id}: unknown control document '{d}'")
        for d in n.controls.lock_on_approval:
            if d not in n.controls.write:
                errs.append(f"{n.id}: locks {d} on approval but does not write it")
            if not n.human_review.required:
                errs.append(f"{n.id}: lock_on_approval needs a human gate")
        if not (root / n.prompt).is_file():
            errs.append(f"{n.id}: prompt {n.prompt} not found")
        for a in [n.agent] + n.support_agents:
            if not (root / "agents" / f"{a}.yaml").is_file():
                errs.append(f"{n.id}: agent {a} has no definition in agents/")
        for r in n.evaluation:
            if not (root / "rubrics" / f"{r}.yaml").is_file():
                errs.append(f"{n.id}: rubric {r} not found in rubrics/")
        refs = [c.fn for c in n.completion if c.fn] + ([n.run.tool] if n.run and n.run.tool else [])
        for ref in refs:
            try:
                resolve_tool(ref)
            except (ImportError, AttributeError) as exc:
                errs.append(f"{n.id}: tool {ref} does not resolve ({exc.__class__.__name__})")
        if n.kind in (NodeKind.TOOL, NodeKind.REVIEW, NodeKind.GATE) and not (n.run and n.run.tool):
            errs.append(f"{n.id}: {n.kind.value} node needs run.tool")
    for doc in CONTROL_DOCS:
        writers = [n for n in wf.nodes if doc in n.controls.write]
        if not writers:
            errs.append(f"control document {doc} has no writer node")
        if len(writers) > 1:  # shared documents: every section has exactly one owner, and every heading is owned
            tpl = PKG_ROOT / "templates" / "control" / f"{doc}.md"
            headings = re.findall(r"(?m)^## (.+?)\s*$", tpl.read_text()) if tpl.is_file() else []
            owned: dict[str, str] = {}
            for n in writers:
                secs = n.controls.sections.get(doc)
                if not secs:
                    errs.append(f"{n.id}: writes shared control document {doc} but declares no owned sections")
                    continue
                for sec in secs:
                    if sec in owned:
                        errs.append(f"{n.id}: section '{sec}' of {doc}.md is already owned by {owned[sec]}")
                    elif sec != "_preamble" and sec not in headings:
                        errs.append(f"{n.id}: section '{sec}' is not a heading of templates/control/{doc}.md")
                    owned.setdefault(sec, n.id)
            for h in headings:
                if h not in owned:
                    errs.append(f"control document {doc}: section '{h}' has no owner among its writers")
            if "_preamble" not in owned:
                errs.append(f"control document {doc}: no writer owns the preamble (title, TL;DR)")
    for n in wf.nodes:
        for doc in n.controls.sections:
            if doc not in n.controls.write:
                errs.append(f"{n.id}: declares sections of {doc} but does not write it")
    targets = wf.policies.regeneration_targets
    for t in targets:
        if t not in idx.nodes:
            errs.append(f"regeneration target {t} is not a node")
        elif regen and not any(e.when == f"target:{t}" for e in idx.loops_out(regen)):
            errs.append(f"regeneration target {t} has no target:{t} loop edge from {regen}")
    for f in wf.policies.single_flight_resources:
        if not any(f in n.resources for n in wf.nodes):
            errs.append(f"single-flight resource {f} is used by no node")
    errs += rubric_placement_errors(wf, root)
    return errs


def _reaches_end(idx: GraphIndex, start: str) -> bool:
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        if cur == idx.wf.end:
            return True
        for e in idx.outgoing[cur]:
            if e.kind != EdgeKind.ESCALATE and e.target not in seen:
                seen.add(e.target)
                stack.append(e.target)
    return False


def _join_errors(wf: Workflow, idx: GraphIndex) -> list[str]:
    """A branch outcome must never strand a join: for every outcome of a branching node, no node reachable from the
    activated successors may also wait on a successor this outcome leaves inactive."""
    errs: list[str] = []
    for n in wf.nodes:
        flows = idx.flow_out(n.id)
        if len({e.when for e in flows}) < 2:
            continue
        for o in n.outcomes:
            active = {e.target for e in flows if outcome_matches(e.when, o)}
            inactive = {e.target for e in flows if not outcome_matches(e.when, o)} - active
            if not active:
                continue
            reach_a = set(active)
            for a in active:
                reach_a |= idx.descendants(a) if a in idx.nodes else set()
            dead = set(inactive)
            for b in inactive:
                dead |= idx.descendants(b) if b in idx.nodes else set()
            dead -= reach_a
            for j in reach_a:
                for e in idx.flow_in(j):
                    if e.source in dead:
                        errs.append(f"{n.id}: outcome '{o}' strands join {j} (it also waits on {e.source})")
        # a join predecessor's non-satisfying outcomes must loop or escalate
    for j in wf.nodes:
        ins = idx.flow_in(j.id)
        if len(ins) < 2:
            continue
        for e in ins:
            src = idx.nodes.get(e.source)
            if not src:
                continue
            for o in src.outcomes:
                if outcome_matches(e.when, o):
                    continue
                handled = any(outcome_matches(x.when, o) for x in idx.outgoing[src.id] if x.kind != EdgeKind.FLOW)
                if not handled:
                    errs.append(f"{src.id}: outcome '{o}' neither feeds join {j.id} nor loops/escalates (deadlock)")
    return errs


def rubric_placement_errors(wf: Workflow, root: Path = PKG_ROOT) -> list[str]:
    errs: list[str] = []
    for n in wf.nodes:
        for r in n.evaluation:
            path = root / "rubrics" / f"{r}.yaml"
            if not path.is_file():
                continue
            rub = yaml.safe_load(path.read_text())
            for d in rub.get("dimensions", []):
                ctype = d.get("check", {}).get("type")
                if d.get("level") != "MUST":
                    continue
                if ctype == "review" and n.kind not in (NodeKind.REVIEW, NodeKind.GATE):
                    errs.append(f"{n.id}: MUST review dimension {d['id']} (rubric {r}) sits on a non-review node")
                if ctype == "human" and not (n.human_review.required or n.kind == NodeKind.REVIEW):
                    errs.append(f"{n.id}: MUST human dimension {d['id']} (rubric {r}) needs a human gate or review node")
                if ctype == "tool":
                    fn = d.get("check", {}).get("fn")
                    try:
                        resolve_tool(fn)
                    except Exception:  # noqa: BLE001 - reported as a validation error
                        errs.append(f"rubric {r}: dimension {d['id']} tool {fn} does not resolve")
            for d in rub.get("dimensions", []):
                fn = d.get("check", {}).get("fn")
                if d.get("check", {}).get("type") == "tool" and fn not in _node_fns(n):
                    errs.append(f"{n.id}: rubric {r} dimension {d['id']} needs check {fn}, which the node never runs")
    return errs


def _node_fns(n: NodeDef) -> set[str]:
    return {c.fn for c in n.completion if c.fn} | ({n.run.tool} if n.run and n.run.tool else set())


def workspace_errors(wf: Workflow, root: Path = PKG_ROOT) -> tuple[list[str], list[str]]:
    """Checks that need the surrounding workspace. Returns (errors, warnings)."""
    skills = root.parent.parent / "03_Agents-and-Skills"   # not parents[1]: a checkout at /app has no grandparent
    index = skills / "INDEX.md"
    if not index.is_file():   # a standalone checkout has no skills folder, so nothing to check against
        return [], ([f"workspace skill index not found at {index}; skill bindings not checked"] if skills.is_dir() else [])
    text = index.read_text()
    errs = []
    for n in wf.nodes:
        for s in n.skills:
            if not re.search(rf"(`|/|\[){re.escape(s)}(`|/|\])", text):
                errs.append(f"{n.id}: skill '{s}' is not in 03_Agents-and-Skills/INDEX.md")
    return errs, []
