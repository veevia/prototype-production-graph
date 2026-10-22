"""Generated documentation: schemas, catalogs, the graph (Mermaid + SVG), the principles library and the de-identified
previous-iterations summary. `python -m pdg docs` writes them; `--check` reports drift instead (CI / review.py).

Everything here is derived from the sources of truth — graph/workflow.yaml, pdg/models.py + pdg/artifacts.py, agents/,
rubrics/, knowledge/rules.json and the available evidence profile. Workspace case-study text passes through its
de-identification map; the public distribution uses recommendation records without private case studies.
"""

from __future__ import annotations

import json
import re
from typing import Any
from xml.sax.saxutils import escape

import yaml

from .artifacts import ARTIFACT_MODELS
from .graph import ESCALATE, GraphIndex, control_reads, load_workflow
from .models import CONTROL_DOCS, STATE_ITEMS, EdgeKind, ProjectState, Workflow
from .privacy import privacy_path
from .util import PKG_ROOT, model_has_path

CASE = PKG_ROOT / "knowledge" / "case-studies" / "hub-programmes-2026"
PHASE_FILL = {"Understand": "#E8F1FB", "Design": "#EAF5EC", "Build": "#FFF4DE", "Learn": "#F2ECFA"}
PHASE_STROKE = {"Understand": "#3A6EA5", "Design": "#2F7A45", "Build": "#9A6A00", "Learn": "#6B4FA3"}
CATEGORY_TITLES = {
    "customer_business_value": "Customer and business value", "product_strategy_scope": "Product strategy and scope",
    "ux_interaction": "User experience and interaction design", "ia_flows": "Information architecture and user flows",
    "visual_design_system": "Visual hierarchy and design-system consistency", "accessibility_responsive": "Accessibility and responsive behaviour",
    "prototype_fidelity_realism": "Prototype fidelity and realism", "technical_feasibility_quality": "Technical feasibility and implementation quality",
    "validation_usability": "Product validation and usability testing", "evidence_and_process": "Evidence, governance and learning",
    "project_specific_decisions": "Project-specific preferences (never defaults)",
}


# ------------------------------------------------------------------------------------------------------ de-identification
def deid_map() -> dict[str, Any]:
    return json.loads(privacy_path(PKG_ROOT).read_text())


def evidence_records() -> dict[str, Any]:
    private = CASE / "iteration-history_TENANT.json"
    path = private if private.exists() else PKG_ROOT / "knowledge/public/evidence.json"
    return json.loads(path.read_text())


def deidentify(text: str, m: dict[str, Any] | None = None) -> str:
    m = m or deid_map()
    for a, b in m["replacements"]:
        text = text.replace(a, b)
    for wword in m.get("whole_words", []):
        text = re.sub(rf"\b(?:the |The )?{re.escape(wword)}\b", "the programme", text)
    return re.sub(r"\b([Tt]he) the\b", r"\1", text)


def leaks(text: str, m: dict[str, Any] | None = None) -> list[str]:
    m = m or deid_map()
    low = text.lower()
    found = [t for t in m["banned"] if t.lower() in low]
    found += [wword for wword in m.get("whole_words", []) if re.search(rf"\b{re.escape(wword)}\b", text)]
    return found


# ------------------------------------------------------------------------------------------------------ generators
def _schemas() -> dict[str, str]:
    out = {f"schemas/artifacts/{name}.schema.json": json.dumps(model.model_json_schema(), indent=1, ensure_ascii=False) + "\n"
           for name, model in sorted(ARTIFACT_MODELS.items())}
    out["schemas/state.schema.json"] = json.dumps(ProjectState.model_json_schema(), indent=1, ensure_ascii=False) + "\n"
    out["schemas/workflow.schema.json"] = json.dumps(Workflow.model_json_schema(by_alias=True), indent=1, ensure_ascii=False) + "\n"
    return out


def _rubrics() -> dict[str, dict[str, Any]]:
    return {yaml.safe_load(p.read_text())["id"]: yaml.safe_load(p.read_text()) for p in sorted((PKG_ROOT / "rubrics").glob("*.yaml"))}


def _rule_states() -> dict[str, str]:
    data = json.loads((PKG_ROOT / "knowledge" / "rules.json").read_text())
    return {r["id"]: r["lifecycle"]["state"] for r in data["rules"]}


def _mode(state: str) -> str:
    return "enforced" if state in ("adopted", "monitored") else "advisory" if state in ("validated", "approved") else "informational"


def _code(items) -> str:
    return ", ".join("`" + str(x) + "`" for x in items)


def _output_line(o) -> str:
    extra = (", schema " + o.schema_name if o.schema_name else "") + (", installs " + o.doc + ".md" if o.doc else "")
    return "`" + o.key + "` (" + o.kind + extra + ") — " + o.description


def _dim_line(d: dict[str, Any], states: dict[str, str]) -> str:
    return "`" + d["id"] + "` " + d["level"] + " " + d["check"]["type"] + " · " + _mode(states.get(d["rule"], "candidate")) + \
        " (" + d["rule"] + ")"


def node_catalog(wf: Workflow) -> str:
    rubrics, states = _rubrics(), _rule_states()
    lines = ["# Node catalog", "", "> **TL;DR:** Every field of all 19 nodes, generated from `graph/workflow.yaml` "
             "(`python -m pdg docs`). Edit the graph, not this file.", ""]
    for n in wf.nodes:
        dims = [d for r in n.evaluation for d in rubrics[r]["dimensions"]]
        agent = "`" + n.agent + "`" + (" (consults " + _code(n.support_agents) + ")" if n.support_agents else "")
        ctl = "read " + (", ".join(n.controls.read) or "—") + " · write " + (", ".join(n.controls.write) or "—")
        if n.controls.lock_on_approval:
            ctl += " · locks on approval " + ", ".join(n.controls.lock_on_approval)
        human = n.human_review.decision
        if n.human_review.required:
            human += " (approver " + n.human_review.approver + "; outcomes " + ", ".join(n.human_review.outcomes) + ")"
        gate = " · 👤 human gate" if n.human_review.required else ""
        lines += [f"## N{n.num:02d} `{n.id}` — {n.name}", "",
                  f"*{n.phase} · {n.stage} · subgraph `{n.subgraph}` · kind **{n.kind.value}**{gate}*", "", f"**Purpose.** {n.purpose}", "",
                  "| Field | Definition |", "|---|---|",
                  "| Depends on | " + _code(n.depends_on) + " |",
                  "| Inputs | " + "<br>".join("`" + i + "`" for i in n.inputs) + " |",
                  "| Outputs | " + "<br>".join(_output_line(o) for o in n.outputs) + " |",
                  "| State read | " + _code(n.state_read) + " |",
                  "| State written | " + _code(n.state_write) + " |",
                  "| Responsible agent | " + agent + " |",
                  "| Skills | " + _code(n.skills) + " |",
                  "| Tools | " + "; ".join(n.tools) + " |",
                  "| Context | " + "; ".join(n.context) + " |",
                  "| Control documents | " + ctl + " |",
                  "| Completion criteria | " + "<br>".join(c.description for c in n.completion) + " |",
                  "| Evaluation checks | " + "<br>".join(_dim_line(d, states) for d in dims) + " |",
                  "| Failure conditions | " + "; ".join(n.failure_conditions) + " |",
                  f"| Retry | {n.retry.max_attempts} attempts — {n.retry.behavior} |",
                  f"| Escalation | after {n.escalation.after} → {n.escalation.to}: {n.escalation.report} |",
                  "| Human review | " + human + " |",
                  "| Outcomes | " + ", ".join(n.outcomes) + " |",
                  "| Provenance | " + "; ".join(n.provenance) + " |", "",
                  f"**Instructions.** {n.instructions}", ""]
    return "\n".join(lines) + "\n"


def edge_catalog(wf: Workflow) -> str:
    lines = ["# Edge catalog", "", "> **TL;DR:** All edges, generated from `graph/workflow.yaml`. Flow edges form a DAG with "
             "join = all; loop edges are bounded; escalate edges stop the run.", "",
             "| ID | From → To | Kind | Transition | When | Transfers | Threshold | Branch / retry / rollback / approval | Max |",
             "|---|---|---|---|---|---|---|---|---|"]
    for e in wf.edges:
        lines.append(f"| {e.id} | `{e.source}` → `{e.target}` | {e.kind.value} | {e.transition} | `{e.when}` | {'; '.join(e.transfers)} | "
                     f"{e.threshold} | {e.behavior} | {e.max_traversals or '—'} |")
    return "\n".join(lines) + "\n"


def control_access(wf: Workflow) -> str:
    """Who reads, writes (whole document or owned sections) and locks each control document."""
    lines = ["<!-- generated by `python -m pdg docs` from graph/workflow.yaml; do not hand-edit -->", "",
             "# Control-document access", "",
             "> **TL;DR:** who may read (R), write (W: the whole document; S: only the sections it owns) or lock on approval "
             "(L) each control document. The engine installs only a writer's owned sections and reports every other edit, "
             "refuses a change to a locked document without an approved change request, and blocks the run on a hand edit "
             "(see [control documents](control-documents.md)).", "",
             "| Node | " + " | ".join(CONTROL_DOCS) + " |", "|---|" + "---|" * len(CONTROL_DOCS)]
    for n in wf.nodes:
        reads = set(control_reads(n))
        cells = []
        for d in CONTROL_DOCS:
            code = "R" if d in reads else ""
            if d in n.controls.write:
                code += "S" if n.controls.sections.get(d) else "W"
            if d in n.controls.lock_on_approval:
                code += "L"
            cells.append(code or "·")
        lines.append(f"| `{n.id}` {n.name} | " + " | ".join(cells) + " |")
    lines += ["", "## Owned sections of shared documents", "",
              "A shared document has several writers; each installs only its own sections.", "",
              "| Document | Section | Writer |", "|---|---|---|"]
    for d in CONTROL_DOCS:
        for n in wf.nodes:
            if d in n.controls.write:
                lines += [f"| {d} | {sec} | `{n.id}` |" for sec in n.controls.sections.get(d, [])]
    return "\n".join(lines) + "\n"


def agent_catalog(wf: Workflow) -> tuple[str, list[str]]:
    drift = []
    lead, sup = {}, {}
    for n in wf.nodes:
        lead.setdefault(n.agent, []).append(f"{n.id} — {n.name}")
        for s in n.support_agents:
            sup.setdefault(s, []).append(f"{n.id} — {n.name}")
    lines = ["# Agent catalog", "", "> **TL;DR:** 13 specialised agents. Each owns nodes (it receives their task packets) or "
             "supports them; none approves a human gate. Generated from `agents/*.yaml` and the graph.", ""]
    for p in sorted((PKG_ROOT / "agents").glob("*.yaml")):
        a = yaml.safe_load(p.read_text())
        if sorted(a.get("leads", [])) != sorted(lead.get(a["id"], [])):
            drift.append(f"agents/{p.name}: leads {a.get('leads')} ≠ graph {lead.get(a['id'], [])}")
        if sorted(a.get("supports", [])) != sorted(sup.get(a["id"], [])):
            drift.append(f"agents/{p.name}: supports {a.get('supports')} ≠ graph {sup.get(a['id'], [])}")
        lines += [f"## {a['name']} (`{a['id']}`)", "", a["responsibility"], "",
                  "| Field | Definition |", "|---|---|",
                  f"| Leads | {'<br>'.join(a.get('leads', [])) or '—'} |", f"| Supports | {'<br>'.join(a.get('supports', [])) or '—'} |",
                  f"| Available context | {'; '.join(a['available_context'])} |",
                  f"| Inputs → outputs | {', '.join(a['inputs'])} → {', '.join(a['outputs'])} |",
                  f"| Skills | {', '.join(f'`{s}`' for s in a['skills'])} |", f"| Tools | {'; '.join(a['tools'])} |",
                  f"| Decision authority | {a['decision_authority']} |", f"| Quality criteria | {', '.join(a['quality_criteria'])} |",
                  f"| Constraints | {'; '.join(a['constraints'])} |",
                  f"| Escalation | when {a['escalation']['when']} → {a['escalation']['to']} ({a['escalation']['how']}) |",
                  f"| Runtime binding | `{a['runtime_binding']}` |", ""]
    return "\n".join(lines) + "\n", drift


def rubric_catalog() -> str:
    rubrics, states = _rubrics(), _rule_states()
    total = sum(len(r["dimensions"]) for r in rubrics.values())
    lines = ["# Rubric catalog", "", f"> **TL;DR:** {len(rubrics)} rubrics, {total} dimensions. A dimension blocks only when "
             "its rule is adopted or monitored (enforced); validated/approved rules are advisory; candidates are informational.", "",
             "| Rubric | Dimension | Level | Check | Mode | Rule | Threshold |", "|---|---|---|---|---|---|---|"]
    for rid, r in rubrics.items():
        for d in r["dimensions"]:
            lines.append(f"| {rid} | `{d['id']}` {d['name']} | {d['level']} | {d['check']['type']}"
                         f"{' `' + d['check']['fn'] + '`' if d['check'].get('fn') else ''} | {_mode(states.get(d['rule'], 'candidate'))} | "
                         f"{d['rule']} | {d.get('threshold', '')} |")
    return "\n".join(lines) + "\n"


def mermaid(wf: Workflow) -> str:
    lines = ["%% generated by `python -m pdg docs` from graph/workflow.yaml", "flowchart TD", "  START([START])", "  END([END])",
             "  ESC{{@escalate: Wei}}"]
    for sg in wf.subgraphs:
        lines.append(f"  subgraph {sg.id}[\"{sg.name}\"]")
        for nid in sg.nodes:
            n = next(x for x in wf.nodes if x.id == nid)
            label = f"N{n.num:02d} {n.name}" + (" 👤" if n.human_review.required else "")
            lines.append(f"    {nid}[\"{label}\"]")
        lines.append("  end")
    for e in wf.edges:
        tgt = "ESC" if e.target == ESCALATE else e.target
        when = "" if e.when == "*" else f"|{e.id} {e.when}|"
        if e.kind == EdgeKind.FLOW:
            lines.append(f"  {e.source} -->{when} {tgt}")
        elif e.kind == EdgeKind.LOOP:
            lines.append(f"  {e.source} -.->|{e.id} {e.when} ≤{e.max_traversals}| {tgt}")
        else:
            lines.append(f"  {e.source} -.->|{e.id} {e.when}| {tgt}")
    lines += ["  classDef understand fill:#E8F1FB,stroke:#3A6EA5", "  classDef design fill:#EAF5EC,stroke:#2F7A45",
              "  classDef build fill:#FFF4DE,stroke:#9A6A00", "  classDef learn fill:#F2ECFA,stroke:#6B4FA3"]
    for ph in ("Understand", "Design", "Build", "Learn"):
        ids = [n.id for n in wf.nodes if n.phase == ph]
        lines.append(f"  class {','.join(ids)} {ph.lower()}")
    return "\n".join(lines) + "\n"


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    lines.append(cur)
    return lines[:2] if len(lines) <= 2 else [lines[0], " ".join(lines[1:])[:width]]


def svg(wf: Workflow, status: dict[str, str] | None = None) -> str:
    """A layered, readable SVG of the graph. `status` (node → status) colours nodes for a run report."""
    idx = GraphIndex(wf)
    depth: dict[str, int] = {}
    for nid in idx.topo:
        if nid in (wf.start, wf.end):
            continue
        preds = [e.source for e in idx.flow_in(nid) if e.source in idx.nodes]
        depth[nid] = 1 + max((depth[p] for p in preds), default=-1)
    rows: dict[int, list[str]] = {}
    for nid, d in depth.items():
        rows.setdefault(d, []).append(nid)
    W, BW, BH, RH, TOP = 1160, 260, 58, 84, 104
    regen_id = idx.regen_node
    pos: dict[str, tuple[float, float]] = {}
    for d, ids in rows.items():
        n = len(ids)
        # the regeneration node sits last in its row, so its rework bus never crosses a sibling
        order = sorted(ids, key=lambda x: (x == regen_id, idx.nodes[x].num))
        for i, nid in enumerate(order):
            cx = 500 + (i - (n - 1) / 2) * (BW + 30)
            pos[nid] = (cx, TOP + d * RH)
    H = TOP + (max(rows) + 1) * RH + 60
    colors = {"PASSED": "#DFF3E4", "BLOCKED": "#FBE3E1", "WAITING_HUMAN": "#FFF1CC", "WAITING_AGENT": "#FFF1CC",
              "ITERATE": "#FBE3E1", "STALE": "#EEEEEE", "not needed": "#F6F6F6", "PLANNED": "#FFFFFF", "READY": "#FFFFFF", "RUNNING": "#E7F0FA"}
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Segoe UI, Helvetica, Arial, sans-serif" role="img" aria-labelledby="t d">',
           f'<title id="t">{escape(wf.name)} — {len(wf.nodes)} nodes, {len(wf.edges)} edges</title>',
           '<desc id="d">Layered view: flow edges solid, bounded loops dashed (blue), targeted rework bus on the right, escalations red.</desc>',
           '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#5A6472"/></marker>'
           '<marker id="b" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#2F6DB5"/></marker></defs>',
           f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>',
           f'<text x="24" y="30" font-size="18" font-weight="600" fill="#1B1F24">{escape(wf.name)}</text>',
           f'<text x="24" y="50" font-size="12" fill="#4A5361">{len(wf.nodes)} nodes · {len(wf.edges)} edges · solid = flow (join = all) · dashed = bounded loop · red = escalate to Wei · 👤 = human gate</text>']
    for e in wf.edges:
        if e.kind != EdgeKind.FLOW or e.source not in pos or e.target not in pos:
            continue
        (x1, y1), (x2, y2) = pos[e.source], pos[e.target]
        out.append(f'<path d="M{x1:.0f} {y1 + BH / 2:.0f} C{x1:.0f} {y1 + BH / 2 + 16:.0f} {x2:.0f} {y2 - BH / 2 - 16:.0f} {x2:.0f} {y2 - BH / 2 - 2:.0f}" '
                   f'fill="none" stroke="#5A6472" stroke-width="1.4" marker-end="url(#a)"/>')
    regen = idx.regen_node
    bus_x = 975
    rt_targets = []
    for e in wf.edges:
        if e.kind != EdgeKind.LOOP:
            continue
        (x1, y1), (x2, y2) = pos[e.source], pos[e.target]
        if e.source == regen:
            rt_targets.append(e.target)
            out.append(f'<path d="M{bus_x} {y2:.0f} L{x2 + BW / 2 + 4:.0f} {y2:.0f}" stroke="#2F6DB5" stroke-width="1.3" stroke-dasharray="5 3" marker-end="url(#b)"/>')
            continue
        lx = min(x1, x2) - BW / 2 - 14
        if e.source == e.target:
            out.append(f'<path d="M{x1 - BW / 2:.0f} {y1 - 8:.0f} C{lx - 26:.0f} {y1 - 30:.0f} {lx - 26:.0f} {y1 + 30:.0f} {x1 - BW / 2:.0f} {y1 + 8:.0f}" '
                       f'fill="none" stroke="#2F6DB5" stroke-width="1.3" stroke-dasharray="5 3" marker-end="url(#b)"/>')
            out.append(f'<text x="{lx - 30:.0f}" y="{y1 + 4:.0f}" font-size="10" fill="#2F6DB5" text-anchor="end">{e.id} {escape(e.when)}</text>')
        else:
            out.append(f'<path d="M{x1 - BW / 2:.0f} {y1:.0f} C{lx - 40:.0f} {y1:.0f} {lx - 40:.0f} {y2:.0f} {x2 - BW / 2:.0f} {y2:.0f}" '
                       f'fill="none" stroke="#2F6DB5" stroke-width="1.3" stroke-dasharray="5 3" marker-end="url(#b)"/>')
            out.append(f'<text x="{lx - 44:.0f}" y="{(y1 + y2) / 2:.0f}" font-size="10" fill="#2F6DB5" text-anchor="end">{e.id} {escape(e.when)} ≤{e.max_traversals}</text>')
    if regen and rt_targets:
        ys = [pos[t][1] for t in rt_targets] + [pos[regen][1]]
        rx, ry = pos[regen]
        out.append(f'<path d="M{rx + BW / 2:.0f} {ry:.0f} L{bus_x} {ry:.0f} L{bus_x} {min(ys):.0f}" fill="none" stroke="#2F6DB5" stroke-width="1.6" stroke-dasharray="5 3"/>')
        out.append(f'<text x="{bus_x + 8}" y="{(min(ys) + ry) / 2:.0f}" font-size="11" fill="#2F6DB5" transform="rotate(90 {bus_x + 8} {(min(ys) + ry) / 2:.0f})" '
                   f'text-anchor="middle">targeted rework: target:&lt;node&gt; loops E30–E39 (≤3 each)</text>')
    for e in wf.edges:
        if e.kind == EdgeKind.ESCALATE:
            x, y = pos[e.source]
            crowded = any(abs(py - y) < 1 and px > x for nid2, (px, py) in pos.items() if nid2 != e.source)
            if crowded:
                out.append(f'<text x="{x - BW / 2 - 8:.0f}" y="{y + BH / 2 + 12:.0f}" font-size="10" fill="#B3261E" text-anchor="end">⚑ {e.id} {escape(e.when)} → Wei</text>')
            else:
                out.append(f'<text x="{x + BW / 2 + 8:.0f}" y="{y - 12:.0f}" font-size="10" fill="#B3261E">⚑ {e.id} {escape(e.when)} → Wei</text>')
    for nid, (x, y) in pos.items():
        n = idx.nodes[nid]
        fill = colors.get((status or {}).get(nid, ""), PHASE_FILL[n.phase]) if status else PHASE_FILL[n.phase]
        title = _wrap(f"N{n.num:02d} {n.name}" + (" 👤" if n.human_review.required else ""), 34)
        tspans = "".join(f'<tspan x="{x - BW / 2 + 10:.0f}" dy="{0 if i == 0 else 15}">{escape(t)}</tspan>' for i, t in enumerate(title))
        ty = y - BH / 2 + 18 if len(title) > 1 else y - 4
        out.append(f'<g><rect x="{x - BW / 2:.0f}" y="{y - BH / 2:.0f}" width="{BW}" height="{BH}" rx="8" fill="{fill}" '
                   f'stroke="{PHASE_STROKE[n.phase]}" stroke-width="1.4"/>'
                   f'<text y="{ty:.0f}" font-size="12.5" font-weight="600" fill="#1B1F24">{tspans}</text>'
                   f'<text x="{x - BW / 2 + 10:.0f}" y="{y + BH / 2 - 9:.0f}" font-size="10.5" fill="#4A5361">{n.kind.value} · {escape(n.agent)}'
                   f'{" · " + escape(str((status or {}).get(nid, ""))) if status else ""}</text></g>')
    ly = H - 30
    for i, (ph, fill) in enumerate(PHASE_FILL.items()):
        out.append(f'<rect x="{24 + i * 130}" y="{ly}" width="16" height="16" rx="3" fill="{fill}" stroke="{PHASE_STROKE[ph]}"/>'
                   f'<text x="{46 + i * 130}" y="{ly + 12}" font-size="12" fill="#1B1F24">{ph}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def principles() -> str:
    data = json.loads((PKG_ROOT / "knowledge" / "rules.json").read_text())
    recs = {r["id"]: r for r in evidence_records()["records"]}
    m = deid_map()
    by: dict[str, list[dict[str, Any]]] = {}
    for r in data["rules"]:
        by.setdefault(r["category"], []).append(r)
    counts: dict[str, int] = {}
    for r in data["rules"]:
        counts[r["lifecycle"]["state"]] = counts.get(r["lifecycle"]["state"], 0) + 1
    lines = ["# Design principles library", "",
             f"> **TL;DR:** {len(data['rules'])} rules in the rule base, each a testable check with its evidence. "
             + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + ". Adopted rules block; validated rules advise until Wei "
             "approves them; candidates only inform.", "",
             "Generated from `knowledge/rules.json` (the governed store) and the de-identified case study. Evidence ids resolve in "
             + ("`knowledge/case-studies/hub-programmes-2026/iteration-history_TENANT.md`."
                if (CASE / "iteration-history_TENANT.json").exists() else "`knowledge/public/evidence.json`.")
             + " **Stable** principles apply to every project; "
             "**project-specific** preferences never become defaults.", "",
             "Basis: *canonical-framework* = Wei's canonical frameworks and workspace constitution · *stated-requirement* = Wei's own "
             "recorded words · *graduated-skill* = Wei's skill library · *observed-pattern* = a verified record whose author is not "
             "identified, or a pattern across records (advisory until approved) · *recommendation* = introduced by this workflow "
             "(informational). A seed approval is recorded as `pdg seed` (human: false): it claims no human decision until Wei confirms it (`pdg memory confirm <rule> --by Wei`).", ""]
    for cat, title in CATEGORY_TITLES.items():
        rules = by.get(cat, [])
        if not rules:
            continue
        lines += [f"## {title}", "", "| Rule | Principle → testable check | Scope | State | Basis | Evidence |", "|---|---|---|---|---|---|"]
        for r in rules:
            dims = ", ".join(f"`{d}`" for d in r["check"].get("dimensions", [])) or (f"`{r['check'].get('test')}`" if r["check"].get("test") else "—")
            ev = "; ".join(f"{e} ({deidentify(recs[e].get('reusable_lesson') or recs[e].get('text', ''), m)[:90]})" for e in r["evidence"] if e in recs)
            thr = f" — threshold: {r['threshold']}" if r.get("threshold") else ""
            cal = " *(calibration pending)*" if r.get("calibration_pending") else ""
            note = f" {deidentify(r['note'], m)}" if r.get("note") else ""
            lines.append(f"| {r['id']} | {deidentify(r['statement'], m)} → {dims}{thr}{cal}{note} | {r['scope']} | {r['lifecycle']['state']} "
                         f"| {r['basis']} | {ev} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def seed_review() -> str:
    """The rules that block a design on a seed approval alone, for Wei to read and confirm. Regenerated on every
    `pdg docs`, so it always lists exactly the rules still awaiting him."""
    data = json.loads((PKG_ROOT / "knowledge" / "rules.json").read_text())
    recs = {r["id"]: r for r in evidence_records()["records"]}
    kind = {"brief": "your brief", "feedback": "your feedback", "framework": "your frameworks and skills",
            "iteration": "an earlier iteration", "memory": "a working preference", "standard": "a published standard"}
    guarded = ("approved", "adopted", "monitored")
    pending = [r for r in data["rules"] if r["lifecycle"]["state"] in guarded and not r.get("confirmed_by_wei")]
    decided = [r for r in data["rules"] if r["lifecycle"]["state"] in guarded and r.get("confirmed_by_wei")]
    if not pending:
        return "\n".join(["# Seed rules awaiting Wei's review", "",
                          f"> **TL;DR:** None. Wei has confirmed every rule that blocks a design ({len(decided)} rules). "
                          "The list stays empty: approving a new rule records his decision directly "
                          "(`pdg memory promote <rule> --to approved --by Wei --human`).", "",
                          "Generated by `python -m pdg docs` from `knowledge/rules.json`."]) + "\n"
    lines = ["# Seed rules awaiting Wei's review", "",
             f"> **TL;DR:** {len(pending)} rules already block a design when they fail. Each restates your own framework, "
             "recorded words or skill library, but its wording was written for you. Read them, then reply `confirm all`, or "
             "name the rules to change or drop. Nothing changes until you reply.", "",
             "Generated by `python -m pdg docs` from `knowledge/rules.json`, so it always lists exactly the rules still "
             "awaiting you. The evidence ids are explained in [previous-iterations](../docs/previous-iterations.md).", "",
             "**How to reply:**", "",
             "- `confirm all`, or `confirm R-…, R-…`: records your confirmation (`pdg memory confirm <rule> --by Wei`).",
             "- `change R-…: <your wording>`: revises the rule. A revised rule only informs until you approve the new wording.",
             "- `drop R-…`: retires the rule, so it no longer blocks or warns.", ""]
    if decided:
        lines += [f"Already decided by you ({len(decided)}): {', '.join(r['id'] for r in decided)}.", ""]
    by: dict[str, list[dict[str, Any]]] = {}
    for r in pending:
        by.setdefault(r["category"], []).append(r)
    for cat, title in CATEGORY_TITLES.items():
        rules = by.get(cat, [])
        if not rules:
            continue
        lines += [f"## {title} ({len(rules)})", "", "| Rule | What it requires | Checked by | Comes from |", "|---|---|---|---|"]
        for r in rules:
            chk = r["check"]
            dims = ", ".join(f"`{d}`" for d in chk.get("dimensions", []))
            src = "; ".join(f"{kind.get(recs[e]['type'], recs[e]['type'])} ({e})" for e in r["evidence"] if e in recs)
            lines.append(f"| {r['id']} | {r['statement'].replace('|', '/')} | {chk.get('type', '')}{': ' + dims if dims else ''} "
                         f"| {src} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def previous_iterations() -> str:
    data = evidence_records()
    if data.get("distribution") == "public":
        return (
            "# Evidence in the public distribution\n\n"
            "**TL;DR:** Customer case studies, private citations, feedback and personal review histories are not distributed.\n\n"
            "The public rule profile preserves the engine's quality defaults, not private evidence or approvals for your "
            "project. Its provenance entries in `knowledge/public/evidence.json` describe recommended checks, not observed "
            "customer outcomes. Original evidence is **MISSING** from this distribution by design.\n\n"
            "The Lot Release Workbench example and every validation session in its dry run are fictional or simulated. "
            "Supply your own authorized evidence under your project's `sources/` directory.\n"
        )
    m = deid_map()
    its = [r for r in data["records"] if r["type"] == "iteration"]
    fbs = [r for r in data["records"] if r["type"] == "feedback"]
    lines = ["# Previous iterations and feedback", "",
             f"> **TL;DR:** {len(its)} verified iteration records across five prototype programmes and a video workflow, and "
             f"{len(fbs)} feedback records, distilled into the rule base. The strongest signal is Wei's own correction: "
             "refine what was asked, keep domains distinct, and optimise component consistency and usability.", "",
             "Generated (de-identified) from the TENANT case study; the full citations with paths are in "
             "`knowledge/case-studies/hub-programmes-2026/iteration-history_TENANT.md`. Structure: Iteration → Decision → Output → "
             "Feedback → Revision → Result → Reusable lesson. Fields the sources do not contain say **MISSING**.", "",
             "## What is verified, inferred, recommended and missing", "",
             "- **Verified context:** every record below is stated in a cited file or session transcript (read 2026-09-26).",
             "- **Inferred patterns:** lessons marked *inferred* generalise across records (for example: first prototypes are framings).",
             "- **New recommendations:** rules with basis *recommendation* (rule base) were introduced by this workflow and stay informational.",
             "- **Missing information:** measured user outcomes, stakeholder acceptance decisions, live integration evidence and most "
             "revision narratives were not recorded; feedback in several records has no identified author, so rules derived from it "
             "are advisory until Wei approves them.", ""]
    for r in its:
        lines += [f"### {r['id']} — {deidentify(r['program'], m)} · {deidentify(r['iteration'], m)}", "",
                  "| Iteration → … → Lesson | |", "|---|---|"]
        for f in data["fields"][1:]:
            lines.append(f"| {f.replace('_', ' ').capitalize()} | {deidentify(str(r[f]), m)} |")
        lines += [f"| Lesson class | {r['lesson_class']} |", ""]
    lines += ["## Feedback log (verbatim; de-identified)", "", "| ID | Who | Feedback |", "|---|---|---|"]
    lines += [f"| {r['id']} | {deidentify(r['who'], m)} | “{deidentify(r['text'], m)}” |" for r in fbs]
    return "\n".join(lines) + "\n"


def _replace_block(text: str, name: str, body: str) -> str:
    start, end = f"<!-- {name}:START -->", f"<!-- {name}:END -->"
    if start not in text:
        return text
    pre, rest = text.split(start, 1)
    _, post = rest.split(end, 1)
    return pre + start + "\n" + body.rstrip() + "\n" + end + post


def _state_items_table() -> str:
    rows = ["| State item (brief §5) | Where it lives in `ProjectState` |", "|---|---|"]
    for item, paths in STATE_ITEMS.items():
        assert all(model_has_path(ProjectState, p) for p in paths), item
        rows.append(f"| {item} | {', '.join(f'`{p}`' for p in paths)} |")
    return "\n".join(rows)


def _nodes_table(wf: Workflow) -> str:
    idx = GraphIndex(wf)
    rows = ["| N | Node | Kind | Phase · stage | Subgraph | Human gate | Loops back to |", "|---|---|---|---|---|---|---|"]
    for n in wf.nodes:
        loops = sorted({e.target for e in idx.loops_out(n.id)})
        rows.append(f"| {n.num:02d} | `{n.id}` — {n.name} | {n.kind.value} | {n.phase} · {n.stage} | {n.subgraph} | "
                    f"{'yes' if n.human_review.required else '—'} | {', '.join(loops) if len(loops) < 4 else f'{len(loops)} rework targets'} |")
    return "\n".join(rows)


def generate(check: bool = False) -> list[str]:
    wf = load_workflow()
    files = _schemas()
    files["docs/node-catalog.md"] = node_catalog(wf)
    files["docs/edge-catalog.md"] = edge_catalog(wf)
    files["docs/control-access.md"] = control_access(wf)
    agents_md, agent_drift = agent_catalog(wf)
    files["docs/agent-catalog.md"] = agents_md
    files["docs/rubric-catalog.md"] = rubric_catalog()
    files["docs/graph.mmd"] = mermaid(wf)
    files["docs/graph.svg"] = svg(wf)
    files["knowledge/design-principles.md"] = principles()
    files["docs/previous-iterations.md"] = previous_iterations()
    files["knowledge/seed-rule-review.md"] = seed_review()
    for doc, blocks in (("docs/graph-spec.md", {"NODES": _nodes_table(wf)}), ("docs/state-model.md", {"STATE-ITEMS": _state_items_table()})):
        p = PKG_ROOT / doc
        if p.exists():
            text = p.read_text()
            for name, body in blocks.items():
                text = _replace_block(text, name, body)
            files[doc] = text
    m = deid_map()
    problems = list(agent_drift)
    for rel_path, content in files.items():
        bad = leaks(content, m)
        if bad:
            problems.append(f"{rel_path}: would contain customer identifiers {bad}")
    if check:
        for rel_path, content in files.items():
            p = PKG_ROOT / rel_path
            if not p.exists() or p.read_text() != content:
                problems.append(f"{rel_path} is out of date")
        return problems
    if problems:
        raise SystemExit("refusing to write docs:\n  " + "\n  ".join(problems))
    for rel_path, content in files.items():
        p = PKG_ROOT / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() or p.read_text() != content:
            p.write_text(content)
    return sorted(files)
