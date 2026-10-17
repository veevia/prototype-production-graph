"""A single-file, offline HTML report of a run: the graph coloured by node status, then gates, defects, comparisons,
approvals (human or not), the pending human dimensions and the ledger timeline. `python -m pdg report <project>`."""

from __future__ import annotations

import html
import json
from pathlib import Path

import yaml

from .docs import svg
from .engine_common import not_needed
from .graph import load_workflow
from .provenance import Ledger, LedgerCorrupt
from .util import read_json

CSS = """body{margin:0;font:15px/1.5 "Segoe UI",system-ui,sans-serif;color:#1B1F24;background:#F6F7F9}
main{max-width:1180px;margin:0 auto;padding:24px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}
.lede{color:#4A5361;margin:0 0 16px}.card{background:#fff;border:1px solid #CDD2D9;border-radius:8px;padding:16px;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #E3E6EA;vertical-align:top}
th{background:#EEF0F3;color:#4A5361;font-size:12px}.ok{color:#1D6B37;font-weight:600}.bad{color:#B3261E;font-weight:600}
.warn{color:#7A4F00;font-weight:600}.kpis{display:flex;flex-wrap:wrap;gap:12px}.kpi{background:#fff;border:1px solid #CDD2D9;border-radius:8px;padding:10px 14px}
.kpi b{display:block;font-size:20px}svg{max-width:100%;height:auto}"""


def write_report(project: Path, out: Path | None = None) -> Path:
    st = read_json(project / ".pdg" / "state.json")
    cfg_file = project / "pdg.project.yaml"
    wf_ref = (yaml.safe_load(cfg_file.read_text()) or {}).get("workflow") if cfg_file.is_file() else None
    wf = load_workflow(project / wf_ref if wf_ref and not Path(wf_ref).is_absolute() else wf_ref)   # the run's own graph
    rt = st["runtime"]
    # a node the passed run left stale (the rework after a gate that passed) is not a node still to run (W62)
    idle = set(not_needed(rt["status"], {n: r["status"] for n, r in rt["nodes"].items()}))
    status = {n: "not needed" if n in idle else r["status"] for n, r in rt["nodes"].items()}
    from .engine import ledger_health
    ledger_path = project / ".pdg" / "ledger.jsonl"
    ok, n_events, msg = ledger_health(ledger_path, rt)
    esc = html.escape

    def table(head: list[str], rows: list[list[str]]) -> str:
        if not rows:
            return "<p>None.</p>"
        return ("<table><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in head) + "</tr></thead><tbody>" +
                "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table>")

    st_class = {"RUN_PASS": "ok", "BLOCKED": "bad"}.get(rt["status"], "warn")
    approvals = st["history"]["approvals"]
    pending = sorted({f"{r['node']}: {d['id']}" for r in st["evaluation"]["reviews"] if r["build_version"] == st["build"]["version"]
                      for d in r["dimensions"] if d["status"] == "pending_human"})
    try:
        events = list(Ledger(ledger_path, read_only=True).events())
    except LedgerCorrupt:   # the header already says BROKEN and why
        events = []
    key_events = [e for e in events if e["type"] in ("gate", "regeneration_plan", "decision", "escalated", "unblocked", "loop_fired",
                                                    "build_version", "run_pass", "inputs_frozen", "change_request_approved", "rollback")]
    body = [f"<h1>Run report — {esc(st['project']['name'])}</h1>",
            f"<p class='lede'>Workflow {esc(wf.id)} v{esc(wf.version)} · status <span class='{st_class}'>{esc(rt['status'])}</span> · "
            f"ledger {'verified' if ok else 'BROKEN'} ({n_events} events)" + (" · <b>DRY RUN</b>: scripted agents; approvals not human" if rt.get("dry_run") else "") + "</p>",
            ("" if ok and not rt.get("ledger_breaks") else
             f"<div class='card'><span class='{'warn' if ok else 'bad'}'>Ledger:</span> {esc(msg)}</div>"),
            "<div class='kpis'>" + "".join(f"<div class='kpi'><b>{esc(str(v))}</b>{esc(k)}</div>" for k, v in [
                ("build version", st["build"]["version"]), ("rework cycles", rt["rework_cycles"]), ("batches", rt["batches"]),
                ("defects resolved", sum(1 for d in st["evaluation"]["defects"] if d["status"] == "resolved")),
                ("defects open", sum(1 for d in st["evaluation"]["defects"] if d["status"] in ("open", "persisting", "needs_human", "in_rework"))),
                ("human approvals", sum(1 for a in approvals if a["human"])), ("non-human approvals", sum(1 for a in approvals if not a["human"]))]) + "</div>",
            "<h2>Graph</h2><div class='card'>" + svg(wf, status) + "</div>",
            "<h2>Gates</h2><div class='card'>" + table(["cycle", "build", "outcome", "blocking", "targets", "reasons"], [
                [esc(str(g["cycle"])), f"v{esc(str(g['build_version']))}", f"<span class='{'ok' if g['outcome'] == 'pass' else 'bad' if g['outcome'] == 'blocked' else 'warn'}'>{esc(g['outcome'])}</span>",
                 esc(", ".join(g["blocking_defects"])), esc(", ".join(g["targets"])), esc("; ".join(g["reasons"]))] for g in st["evaluation"]["gates"]]) + "</div>",
            "<h2>Defects</h2><div class='card'>" + table(["id", "signature", "sev", "status", "traced to", "smallest fix", "acceptance check"], [
                [esc(d["id"]), esc(d["signature"]), esc(d["severity"]), esc(d["status"]), esc(d["traced_node"]), esc(d["smallest_fix"]),
                 esc(d["acceptance_check"])] for d in st["evaluation"]["defects"]]) + "</div>",
            "<h2>Before / after</h2><div class='card'>" + table(["cycle", "targets", "versions", "resolved", "persisting", "new", "verdict"], [
                [esc(str(c["cycle"])), esc(", ".join(c["targets"])), f"v{esc(str(c['before_version']))} → v{esc(str(c['after_version']))}", esc(", ".join(c["resolved"])),
                 esc(", ".join(c["persisting"])), esc(", ".join(c["new"])), esc(c["verdict"])] for c in st["evaluation"]["comparisons"]]) + "</div>",
            "<h2>Decisions at human gates</h2><div class='card'>" + table(["node", "decision", "actor", "human", "reason"], [
                [esc(a["node"]), esc(a["decision"]), esc(a["actor"]), "<span class='ok'>yes</span>" if a["human"] else "<span class='bad'>no (dry run)</span>",
                 esc(a["reason"])] for a in approvals]) + "</div>",
            "<h2>Human dimensions still pending</h2><div class='card'>" + ("<ul>" + "".join(f"<li>{esc(p)}</li>" for p in pending) + "</ul>" if pending else "<p>None.</p>") + "</div>",
            "<h2>Timeline (key ledger events)</h2><div class='card'>" + table(["seq", "time", "event", "detail"], [
                [esc(str(e["seq"])), esc(e["ts"]), esc(e["type"]), esc(json.dumps(e["data"], ensure_ascii=False)[:220])] for e in key_events]) + "</div>"]
    doc = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Run report — {esc(st['project']['name'])}</title><style>{CSS}</style></head><body><main>{''.join(body)}</main></body></html>")
    out = out or project / ".pdg" / "run-report.html"
    out.write_text(doc)
    return out
