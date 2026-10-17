"""Command line: `python -m pdg <command>`. Exit codes: 0 done or waiting · 1 a check failed (validate, docs --check,
ledger-verify, dry-run) · 2 the run is BLOCKED · 3 a memory-governance refusal · 4 a refused command (nothing changed), or a
human action that was saved while its ledger events wait to be written (the message says which)."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import select
import sys
from pathlib import Path
from typing import Any

from .human_recording import PLACEHOLDER_RE
from .util import BRIEF_PLACEHOLDER, PKG_ROOT, read_json


def _print(obj) -> None:
    print(json.dumps(obj, indent=1, ensure_ascii=False, default=str))


def _summary(status: dict) -> str:
    from .engine_common import HUMAN_ONLY_ACTIONS, delegation_text, resets_text
    resets = resets_text(status.get("budget_resets", {}))
    lines = [f"{status['project']}: {status['status']} · build v{status['build_version']} · {status['rework_cycles']} rework "
             f"cycle(s)" + (f" · {resets}" if resets else "")
             + f" · {status['batches']} batches · {status['ledger_events']} ledger events"]
    if status.get("latest_build"):
        lines.append(f"latest build: {status['latest_build']}")
    if status.get("latest_release"):
        lines.append(f"latest release: {status['latest_release']}")
    if status.get("learning_pending"):
        lines.append("release summary: learning pending until N19 submits and passes")
    due, root = status.get("recheck_due") or {}, shlex.quote(str(status.get("project_root") or "PROJECT"))
    if due.get("nodes") or due.get("unrecorded"):   # a check upgrade the release never saw (W65)
        why = ([f"{' and '.join(due['changed'])} changed since {len(due['nodes'])} node(s) of this release were judged"]
               if due.get("nodes") else []) + ([f"up to {len(due['unrecorded'])} node(s) passed before pdg recorded their "
                                                "checks"]
                                               if due.get("unrecorded") else [])
        lines.append(f"{'; '.join(why)}: `pdg recheck-release {root}` re-runs their checks on it, read-only")
    elif due.get("unreadable"):
        lines.append(f"whether this release needs a re-check is unknown: the configuration on disk cannot be read "
                     f"({due['unreadable']})")
    elif due.get("rechecked"):
        r = due["rechecked"]
        lines.append(f"re-checked {r['at'][:16].replace('T', ' ')} with the current checks: {r['blocking']} failure(s) "
                     f"would block, {r['not_run']} check(s) could not run; none is filed (`pdg feedback {root} …` re-opens "
                     f"the release on one; `pdg recheck-release {root} --decline --actor NAME` records a decision not to)")
    if status.get("not_needed"):   # W62: not a node still to run
        lines.append(f"not needed (the run passed without it): {', '.join(status['not_needed'])}")
    if status.get("uncommitted_check_files"):
        n = len(status["uncommitted_check_files"])
        lines.append(f"checks ran on uncommitted pdg code ({n} file{'s' if n != 1 else ''})")
    for d in status.get("delegations") or []:   # a grant's time left, and how to renew it near its end (R2-30)
        lines.append(f"delegation {delegation_text(d, str(status.get('project_root') or 'PROJECT'))}")
    if status.get("gate_trend"):
        lines.append("blocking defects by gate: " + " → ".join(f"{g['blocking']} (v{g['build']}, {g['outcome']})"
                                                           for g in status["gate_trend"]))
    if status["waiting_agent"]:
        lines.append("waiting for agents: " + ", ".join(status["waiting_agent"]) + "  (see `pdg tasks`)")
        for t in status.get("waiting_agent_details", []):
            lines.append(f"  {t['node']}: waiting {t['age']} since {t['since'][:19]}"
                         + (" — FLAG: no submission for over 1 h" if t.get("stale") else ""))
    if status["waiting_human"]:
        lines.append("waiting for a human decision: " + ", ".join(status["waiting_human"]) + "  (`pdg approve`)")
        lines += [f"  {n}: {note}" for n, note in (status.get("gate_notes") or {}).items() if note]
    for item in status.get("human_actions") or []:
        lines.append(f"awaiting human: {item['action']} for {item['actor']} unblocks {item['unblocks']}: `{item['command']}`")
    untyped = [item for item in status.get("transcribed_actions") or [] if not item.get("recorded_by")]
    for item in [x for x in status.get("transcribed_actions") or [] if x.get("recorded_by")]:
        if item.get("recorded_by"):
            lines.append(f"transcribed human action: {item['action']} by {item['actor']} typed by {item['recorded_by']}"
                         f"{' — unconfirmed interpretation' if item.get('interprets') and not item.get('ratified') else ''}")
    if untyped:
        first = untyped[0]
        lines.append(f"{len(untyped)} human action(s) without typist; example: {first['action']} by {first['actor']} "
                     "— who typed it is not recorded")
    if status.get("human_only_actions"):
        lines.append("human-only actions this run keeps human-only:")
        lines += [f"  - {x}" for x in status["human_only_actions"]]
    for item in status.get("changed_acceptances") or []:
        lines.append(f"changed risk acceptance: {item['message']}")
    for e in status["escalations"]:
        lines.append(f"BLOCKED at {e['node']}: {e['reason']} — report {e['report']}")
    if status.get("parked"):
        lines.append("parked submissions (made while blocked; resubmit once it is resolved): " + ", ".join(status["parked"]))
    if status["open_defects"]:
        lines.append("open defects: " + ", ".join(status["open_defects"]))
    return "\n".join(lines)


def _exit_for(status: dict) -> int:
    return 2 if status["status"] == "BLOCKED" else 0


def cmd_validate(a) -> int:
    import yaml
    from pydantic import ValidationError

    from .graph import load_workflow, structural_errors, workspace_errors
    try:
        wf = load_workflow(a.workflow)
    except (ValidationError, yaml.YAMLError) as exc:   # the file itself is not a workflow: invalid, like any other error
        for line in str(exc).splitlines()[:8]:
            print("error:", line)
        print("graph INVALID: the file does not match the workflow schema")
        return 1
    errs = structural_errors(wf)
    werrs, warns = workspace_errors(wf)
    for w in warns:
        print("warning:", w)
    for e in errs + werrs:
        print("error:", e)
    if errs or werrs:
        print(f"graph INVALID: {len(errs) + len(werrs)} error(s)")
        return 1
    loops = sum(1 for e in wf.edges if e.kind.value == "loop")
    print(f"graph valid: {len(wf.nodes)} nodes, {len(wf.edges)} edges ({loops} bounded loops), {len(wf.subgraphs)} subgraphs, "
          f"{sum(1 for n in wf.nodes if n.human_review.required)} human gates")
    return 0


def cmd_docs(a) -> int:
    from .docs import generate
    drift = generate(check=a.check)
    if a.check:
        for d in drift:
            print("drift:", d)
        print("docs up to date" if not drift else f"{len(drift)} generated file(s) out of date — run `python -m pdg docs`")
        return 1 if drift else 0
    print("generated:", ", ".join(drift))
    return 0


class _BuildCtx:
    """Just enough of a node context for N11's checks on a folder: its outputs, the project's saved state (read-only)
    and the thresholds the gate uses."""

    def __init__(self, build: Path, state, thresholds: dict):
        self._build, self.state, self.thresholds = build, state, thresholds

    def output(self, key: str):
        if key == "prototype_build":
            return self._build
        manifest = self._build / "build-manifest.json"
        return manifest if key == "build_manifest" and manifest.is_file() else None

    artifact = output

    def json(self, key: str):
        return json.loads(self.output(key).read_text())


def cmd_check_build(a) -> int:
    """Run N11's tool checks on a build folder before submitting it, exactly as the gate does: the unit tests run on a
    copy of the folder (field run 2, R2-10). Read-only: it never takes the lock or writes the run."""
    import yaml
    from .controls import front_matter
    from .engine import _deep_merge
    from .evaluation import load_rubrics
    from .models import ProjectState
    from .tools.prototype import check_static, check_unit
    build = Path(a.build).resolve()
    if not (build / "build-manifest.json").is_file():
        print(f"{build} has no build-manifest.json", file=sys.stderr)
        return 4
    th = yaml.safe_load((PKG_ROOT / "config" / "defaults.yaml").read_text())["thresholds"]
    if a.project:
        state = ProjectState.model_validate(read_json(Path(a.project) / ".pdg" / "state.json"))
        ev = Path(a.project) / "controls" / "evaluation.md"
        th = _deep_merge(th, (front_matter(ev.read_text()).get("thresholds") or {}) if ev.is_file() else {})
    else:
        state = ProjectState.model_validate({"schema_version": "check-build", "project": {
            "id": "check-build", "name": "check-build", "created": "", "workflow_id": "", "workflow_version": ""}})
    ctx = _BuildCtx(build, state, th)
    levels = {d["id"]: d["level"] for d in load_rubrics()["build"]["dimensions"]}
    failed = False
    for fn in (check_static, check_unit):
        res = fn(ctx)
        for e in res.errors:
            print(f"error: {e}")
            failed = True
        for dim, out in sorted(res.dimensions.items()):
            must = levels.get(dim) == "MUST"
            failed |= must and not out.passed
            print(f"{'PASS' if out.passed else 'FAIL'} {dim}{'' if must else ' (SHOULD)'}: {out.evidence}")
    if not a.project:
        print("note: no --project, so screens and the design system were not checked")
    return 4 if failed else 0


def cmd_accept_config(a) -> int:
    if a.dry_run:   # changes nothing; the lock only keeps it from reading a run another command is writing
        with _locked(a.project, "accept-config --dry-run"):
            imp = _engine(a.project).config_impact()
        print(f"changed: {', '.join(imp['changed']) or 'nothing'}")
        print(f"re-judged: {', '.join(imp['rejudge']) or 'none'}")
        print(f"withdrawn (re-judged, and their descendants): {', '.join(imp['withdrawn']) or 'none'}")
        print(f"out with an agent, would be lost: {', '.join(imp['in_flight']) or 'none'}")
        print("parked submissions: " + ("; ".join(f"{n} ({imp['parked_fate'][n]})" for n in imp["parked"]) or "none"))
        return 0
    if not a.actor:
        print("refused (nothing changed): --actor is required unless --dry-run")
        return 4
    return _simple(a, lambda e: e.accept_config(a.actor, _reason(a), a.on_behalf_of, a.discard_in_flight,
                                                a.recorded_by, a.source, a.interprets))


def cmd_delegate(a) -> int:
    from .engine import EngineError
    try:
        instruction = _reason(a, "instruction")
        expires = _reason(a, "expires")
        recorded_by = _reason(a, "recorded_by")
    except EngineError as exc:
        print(f"refused: {exc}")
        return 4
    return _simple(a, lambda e: e.delegate(a.by, a.agent, instruction, _split_csv(a.scope),
                                           _split_csv(a.nodes), expires, recorded_by, a.source,
                                           _split_csv(a.except_nodes), a.budget_resets, a.include_release))


def cmd_archive(a) -> int:
    """List (default) or move (`--apply`) a run's earlier attempt folders out of the project."""
    from .engine import EngineError
    try:
        with _locked(a.project, "archive"):
            eng = _engine(a.project)
            plan = eng.archive_plan(a.keep)
            if plan.unmatched_keep:
                print("refused (nothing changed): --keep did not match an archive candidate: "
                      + ", ".join(plan.unmatched_keep))
                return 4
            cands = plan.move
            total = sum(b for _, b in cands)
            if not a.apply:
                for r, b in cands:
                    print(f"  {r}  ({b / 1e6:.1f} MB)")
                for r, why in sorted(plan.keep.items()):
                    print(f"  keep {r}: {'; '.join(why)}")
                for cp in plan.checkpoints:
                    print(f"  checkpoint {cp.seq} moves with archived artifacts: {cp.path}")
                print(f"{len(cands)} earlier attempt folder(s), {total / 1e6:.1f} MB. Nothing moved: add --apply --actor <human> "
                      f"to move them to {Path(a.to).expanduser()}/<date>-pdg-<project>/ (with restore.sh).")
                print("A release commit keeps: sources, controls, the release shelf, .pdg state and ledger, and each node's final attempt. "
                      "Earlier attempts and screenshot rounds belong in this archive.")
                return 0
            if not a.actor:
                print("refused (nothing changed): --apply needs --actor <named human>")
                return 4
            out = eng.archive(Path(a.to), a.actor, keep=a.keep, recorded_by=a.recorded_by, source=a.source,
                              interprets=a.interprets)
    except (EngineError, OSError, ValueError) as exc:
        print(f"refused: {exc}")
        return 4
    print(f"moved {out['moved']} folder(s), {out['bytes'] / 1e6:.1f} MB, to {out['dest']}")
    return 0


def cmd_release_shelf(a) -> int:
    from .engine import EngineError
    try:
        with _locked(a.project, "release-shelf"):
            rows = _engine(a.project).release_shelf()
    except (EngineError, OSError, ValueError) as exc:
        print(f"refused: {exc}")
        return 4
    print(f"rebuilt release shelf: {len(rows)} release(s)")
    return 0


def cmd_review(a) -> int:
    import datetime as dt
    from .review import build, record
    project = Path(a.project).resolve()
    if a.record:
        for line in record(project, Path(a.record), Path(a.score_tool) if a.score_tool else None):
            print(line)
        return 0
    out = build(project, a.date or dt.date.today().isoformat())
    print(f"wrote {out['packet']}")
    print(f"wrote {out['board']}")
    return 0


def cmd_check_output(a) -> int:
    """Check a file against a node's declared output before submitting it: a malformed file is refused anyway, but
    checking first shows the whole error in one step (backlog N-09)."""
    from .artifacts import output_problems
    from .graph import load_workflow
    wf = load_workflow(a.workflow)
    node = next((n for n in wf.nodes if n.id == a.node), None)
    if node is None:
        print(f"unknown node {a.node}", file=sys.stderr)
        return 4
    spec = next((o for o in node.outputs if o.key == a.key), None)
    if spec is None:
        print(f"{a.node} declares no output '{a.key}' (declared: {', '.join(o.key for o in node.outputs)})", file=sys.stderr)
        return 4
    problems = output_problems(spec, a.file)
    if not problems and a.project and spec.schema_name == "interpretation":
        try:
            from .interpretation import interpretation_gaps
            problems += interpretation_gaps(Path(a.project), Path(a.file), a.workflow)
        except (OSError, ValueError, KeyError) as exc:
            problems.append(str(exc))
    for p in problems:
        print(p, file=sys.stderr)
    if not problems:
        what = f"schema '{spec.schema_name}'" if spec.schema_name else f"a {spec.kind} output"
        print(f"ok: {a.file} is a valid {a.node} '{a.key}' ({what})")
    return 4 if problems else 0


def cmd_init(a) -> int:
    root = Path(a.project)
    if (root / ".pdg").exists():
        print(f"refused: {root} already has a run (.pdg/)")
        return 4
    (root / "sources").mkdir(parents=True, exist_ok=True)
    (root / "controls").mkdir(exist_ok=True)
    cfg = root / "pdg.project.yaml"
    if not cfg.exists():
        cfg.write_text(f"id: {root.name}\nname: {a.name}\ndry_run: false\nhumans: [Wei]\n"
                       "# a refresh of an existing build: name it, and REF-PARITY compares every screen with it\n"
                       "# reference: {entry: <path to its entry html, from this folder>, routes: {<screen>: <route, or null to skip>},\n"
                       "#             expected: [{property: title|controls|search|filter|tables, screen: <id>, reason: <why>}]}\n")
    note = root / "sources" / "README.md"
    if not note.exists():   # a copied repo document keeps its links as they are (field run W29, backlog N-11)
        note.write_text("# Sources: raw intake\n\nFiles here are the run's raw inputs. N02 freezes them: after that a change "
                        "blocks the run until a named human accepts it. Copy documents in as they are and never edit them to "
                        "fix links; the workspace's link audit treats a `sources/` folder next to `pdg.project.yaml` as raw "
                        "intake. Register each source in N01's `sources.json`.\n")
    brief = root / "sources" / "brief.md"
    if not brief.exists():
        brief.write_text(f"# Brief — {a.name}\n\n{BRIEF_PLACEHOLDER}\n")
    for p in sorted((PKG_ROOT / "templates" / "control").glob("*.md")):
        dst = root / "controls" / p.name
        if not dst.exists():
            shutil.copyfile(p, dst)
    print(f"initialised {root}: pdg.project.yaml, sources/brief.md, sources/README.md, controls/ (8 templates). Next: write "
          f"the brief, add sources, then `python -B -m pdg run {shlex.quote(str(root))}`.")
    return 0


def _engine(project: str):
    from .engine import Engine
    return Engine(project)


def _locked(project: str, command: str):
    from .lock import project_lock
    return project_lock(project, command)


def cmd_run(a) -> int:
    with _locked(a.project, "run"):
        eng = _engine(a.project)
        status = eng.run(max_steps=a.max_steps)
        notices = list(eng.notices)
    print(_summary(status))
    for n in notices:
        print("note:", n)
    return _exit_for(status)


def _parse_ts(value: str):
    import datetime as dt
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def _fmt_age(ts: str) -> tuple[str, bool]:
    import datetime as dt
    parsed = _parse_ts(ts)
    if parsed is None:
        return "unknown", False
    secs = max(0, (dt.datetime.now(dt.timezone.utc) - parsed).total_seconds())
    return (f"{secs / 3600:.1f} h" if secs >= 3600 else f"{secs / 60:.0f} min"), secs > 3600


def _evaluation_view(st: dict) -> dict[str, Any]:
    dims = [{"node": r["node"], "attempt": r["attempt"], "build_version": r["build_version"],
             "id": d["id"], "score": d.get("score"), "status": d["status"], "passed": d["status"] == "pass",
             "evidence": d.get("evidence", ""), "detail": d.get("detail", "")}
            for r in st["evaluation"].get("reviews", []) for d in r.get("dimensions", [])]
    defects = [{"id": d["id"], "signature": d.get("signature", ""), "severity": d["severity"],
                "status": d["status"], "owner_node": d["traced_node"], "message": d["message"],
                "dimension": d.get("dimension", "")} for d in st["evaluation"].get("defects", [])]
    return {"dimensions": dims, "defects": defects}


def _risk_waits(st: dict, project: str) -> list[dict[str, str]]:
    from .util import sha256_json
    accepted = {r["assumption"]: r for r in st["history"].get("risk_acceptances", [])}
    human = (_project_humans(Path(project)) or ["Wei"])[0]
    waits = []
    for a in st.get("research", {}).get("assumptions", []):
        if not a.get("riskiest"):
            continue
        ra = accepted.get(a["id"])
        cur = sha256_json(a.get("statement", ""))
        changed = bool(ra and ra.get("statement_sha256") and ra.get("statement_sha256") != cur)
        if not changed:
            continue
        actor = (ra.get("on_behalf_of") or ra.get("actor")) if ra else human
        msg = f"{a['id']} changed after {actor} accepted it on {ra.get('at', '')[:10]}: re-accept"
        waits.append({"action": "accept-risk", "actor": actor, "unblocks": "N10 fidelity gate",
                      "command": f"pdg accept-risk {shlex.quote(str(project))} {shlex.quote(a['id'])} "
                                 f"--actor {shlex.quote(actor)}",
                      "message": msg})
    return waits


def read_status(project: str, evaluation: bool = False) -> dict:
    """Read-only status: never takes the lock, never writes, never resumes."""
    import datetime as dt
    from .engine_common import (HUMAN_ONLY_ACTIONS, budget_resets, live_delegations, not_needed, recheck_due,
                                recheck_record, uncommitted_check_files)
    from .gating import transcribed_action
    from .provenance import Ledger, LedgerCorrupt
    p = Path(project) / ".pdg" / "state.json"
    if not p.exists():
        raise FileNotFoundError(f"{project} has no run yet (`pdg run {shlex.quote(str(project))}`)")
    st = read_json(p)
    rt = st["runtime"]
    ledger = Path(project) / ".pdg" / "ledger.jsonl"
    budget = _retry_budgets(Path(project))
    ledger_obj = Ledger(ledger, read_only=True) if ledger.exists() else None
    try:
        events = list(ledger_obj.events()) if ledger_obj else []
    except LedgerCorrupt:
        events = []
    root = str(Path(project).resolve())
    humans = _project_humans(Path(project)) or ["human"]
    human = humans[0]
    task_ts = {e["data"]["node"]: e["ts"] for e in events if e["type"] == "task_issued"}
    waiting_agent_details = []
    for n, r in rt["nodes"].items():
        if r["status"] == "WAITING_AGENT":
            age, stale = _fmt_age(task_ts.get(n, ""))
            waiting_agent_details.append({"node": n, "since": task_ts.get(n, ""), "age": age, "stale": stale})
    ratified = {r["target"]: r for r in st["history"].get("ratifications", [])}
    transcribed = []
    for e in events:
        data = e["data"]
        actor = data.get("actor") or data.get("by")
        rb = data.get("recorded_by")
        if transcribed_action(e["type"], data, humans):
            rat = ratified.get(str(e["seq"])) or ratified.get(str(data.get("id", "")))
            transcribed.append({"event": str(e["seq"]), "action": e["type"], "actor": actor, "recorded_by": rb,
                                "source": data.get("source", ""), "interprets": data.get("interprets", False),
                                "ratified": bool(rat and not rat.get("reverse")), "reversed": bool(rat and rat.get("reverse"))})
    risk_waits = _risk_waits(st, root)
    gate_waits = [{"action": "approve", "actor": human, "unblocks": n,
                   "command": f"pdg approve {shlex.quote(root)} {shlex.quote(n)} --actor {shlex.quote(human)}",
                   "message": r.get("gate_note", "")}
                  for n, r in rt["nodes"].items() if r["status"] == "WAITING_HUMAN"]
    escalation_waits = [{"action": "unblock", "actor": human, "unblocks": e["node"],
                         "command": f"pdg unblock {shlex.quote(root)} {shlex.quote(e['node'])} --actor {shlex.quote(human)}",
                         "message": e["reason"]} for e in rt["escalations"] if e["open"]]
    out = {"project": st["project"]["id"], "project_root": str(Path(project).resolve()), "status": rt["status"],
            "batches": rt["batches"],
            "build_version": st["build"]["version"], "rework_cycles": rt["rework_cycles"],
            # attempts started, and apart from them the failed ones and what is left: "attempts 3" read as three tries
            # used for a node never submitted (field run 2, R2-15)
            "nodes": {n: {"status": r["status"], "outcome": r["outcome"], "attempt": r["attempt"],
                          "failed": r.get("streak", 0), "left": max(0, budget.get(n, 3) - r.get("streak", 0))}
                      for n, r in rt["nodes"].items()},
            "waiting_agent": [n for n, r in rt["nodes"].items() if r["status"] == "WAITING_AGENT"],
            "waiting_agent_details": waiting_agent_details,
            # left stale by an invalidation, and not on the path the passing run took (field run W62)
            "not_needed": not_needed(rt["status"], {n: r["status"] for n, r in rt["nodes"].items()}),
            "learning_pending": rt["nodes"].get("n18_final_verification", {}).get("status") == "PASSED"
            and rt["nodes"].get("n19_learning_memory", {}).get("status") != "PASSED",
            # the code and configuration on disk: a check upgrade shows before any command runs (W65)
            "recheck_due": recheck_due(rt, st["build"]["version"], Path(project), recheck_record(Path(project) / ".pdg")),
            "uncommitted_check_files": uncommitted_check_files(rt),
            "waiting_human": [n for n, r in rt["nodes"].items() if r["status"] == "WAITING_HUMAN"],
            "parked": [n for n, r in rt["nodes"].items() if r.get("parked")],
            "gate_notes": {n: r.get("gate_note", "") for n, r in rt["nodes"].items() if r["status"] == "WAITING_HUMAN"},
            "escalations": [e for e in rt["escalations"] if e["open"]],
            "open_defects": [d["id"] for d in st["evaluation"]["defects"] if d["status"] in ("open", "persisting", "needs_human", "in_rework")],
            "latest_build": (st["build"].get("prototype") or {}).get("entry"),   # where to open it (backlog N-07)
            "latest_release": _latest_release(project),
            # blocking defects gate by gate: the trend a human needs to fund another cycle (backlog N-02)
            "gate_trend": [{"build": g["build_version"], "outcome": g["outcome"], "blocking": len(g["blocking_defects"])}
                           for g in st["evaluation"].get("gates", [])],
            "ledger_events": sum(1 for _ in ledger_obj._lines()) if ledger_obj else 0,
            "budget_resets": budget_resets(ledger_obj) if ledger_obj else {},
            "delegations": live_delegations(st["history"].get("delegations", []), dt.datetime.now(dt.timezone.utc),
                                            _project_humans(Path(project))),
            "human_only_actions": list(HUMAN_ONLY_ACTIONS),
            "checkpoints": [(c["seq"], c["event"], c["node"]) for c in st["history"]["checkpoints"]],
            "human_actions": risk_waits + gate_waits + escalation_waits,
            "changed_acceptances": [w for w in risk_waits if "changed after" in w["message"]],
            "transcribed_actions": transcribed}
    if evaluation:
        out["evaluation"] = _evaluation_view(st)
    return out


def _project_humans(project: Path) -> list[str] | None:
    """The project's named humans, as the engine reads them (the workflow's and pdg.project.yaml's), or None if unreadable."""
    import yaml
    from .graph import DEFAULT_WORKFLOW, load_workflow
    try:
        cfg = yaml.safe_load((project / "pdg.project.yaml").read_text()) or {}
        wf = Path(cfg.get("workflow") or DEFAULT_WORKFLOW)
        wf = wf if wf.is_absolute() or not cfg.get("workflow") else project / wf
        return sorted(set(load_workflow(wf).policies.human_actors) | set(cfg.get("humans") or []))
    except Exception:  # noqa: BLE001 - status must never fail on what it can only show
        return None


def _retry_budgets(project: Path) -> dict[str, int]:
    """Each node's retry budget, from the project's workflow (the package's unless the project names its own)."""
    import yaml
    from .graph import DEFAULT_WORKFLOW, load_workflow
    try:
        cfg = yaml.safe_load((project / "pdg.project.yaml").read_text()) or {}
        wf = Path(cfg.get("workflow") or DEFAULT_WORKFLOW)
        wf = wf if wf.is_absolute() or not cfg.get("workflow") else project / wf
        return {n.id: n.retry.max_attempts for n in load_workflow(wf).nodes}
    except Exception:  # noqa: BLE001 - status must never fail on a budget it can only show
        return {}


def cmd_status(a) -> int:
    s = read_status(a.project, getattr(a, "evaluation", False))
    if a.json:
        _print(s)
    else:
        print(_summary(s))
        for n, r in s["nodes"].items():
            # a node the run passed without needing (the rework after a gate that passed) is not a node still to run (W62)
            state = "not needed" if n in s.get("not_needed", []) else r["status"]
            print(f"  {n:<30} {state:<14} {r['outcome'] or '':<18} attempt {r['attempt']} · {r['failed']} failed · "
                  f"{r['left']} left")
        if a.checkpoints:
            for seq, ev, node in s["checkpoints"]:
                print(f"  checkpoint {seq:>4} {ev:<16} {node or 'run'}")
    return _exit_for(s)


def cmd_waiting(a) -> int:
    from .engine_common import renew_command
    rows = []
    for project in a.projects:
        s = read_status(project)
        for w in s.get("human_actions", []):
            rows.append([s["project"], w["action"], w["command"], w["actor"], w["unblocks"], w.get("message", "")])
        for d in s.get("delegations", []) or []:
            if d.get("left_s") is not None and d["left_s"] < 86400 and not d.get("renewed"):
                rows.append([s["project"], "renew delegation", renew_command(d, s["project_root"]), d.get("by", ""),
                             "delegate authority", "expires within 24 h" if d["left_s"] > 0 else "expired"])
        st = read_json(Path(project) / ".pdg" / "state.json")
        for fb in st["evaluation"].get("feedback", []):
            if fb.get("human") and fb.get("status") == "open":
                rows.append([s["project"], "feedback", "—", fb["actor"], "feedback diagnosis", fb["status"]])
        for cr in st["history"].get("change_requests", []):
            if cr.get("status") == "open":
                actor = (_project_humans(Path(project)) or ["human"])[0]
                rows.append([s["project"], "change-request", f"pdg decide-change-request {shlex.quote(str(project))} "
                             f"{cr['id']} --approve --actor {shlex.quote(actor)}", actor, cr.get("writer", ""),
                             cr["status"]])
    print("| Project | Action | Command | Actor | Unblocks | Since / state |")
    print("|---|---|---|---|---|---|")
    for row in rows:
        print("| " + " | ".join(str(c).replace("|", "/") for c in row) + " |")
    if not rows:
        print("| — | none | — | — | — | — |")
    return 0


def _latest_release(project: str) -> str | None:
    from .release_shelf import latest_release_path
    try:
        path = latest_release_path(Path(project))
    except ValueError:
        return None
    return str(path) if path else None


def cmd_tasks(a) -> int:
    s = read_status(a.project)
    tasks = Path(a.project) / ".pdg" / "tasks"
    st = read_json(Path(a.project) / ".pdg" / "state.json")
    if not s["waiting_agent"]:
        print("no open task packets")
    for n in s["waiting_agent"]:
        rt = st["runtime"]["nodes"][n]
        packet = tasks / f"{n}-a{rt['attempt']}.md"
        print(f"{n} (attempt {rt['attempt']}, token {rt['token']}): {packet}")
    return 0


def cmd_submit(a) -> int:
    from .engine import EngineError
    from .check_node import check_node
    outputs = {}
    for kv in a.output or []:
        k, _, v = kv.partition("=")
        if not k or not v:
            print(f"refused (nothing changed): --output {kv!r} needs the form key=path")
            return 4
        outputs[k] = v
    if not a.dry_run and (not a.token or not a.actor):
        print("refused (nothing changed): submit needs --token and --actor unless --dry-run")
        return 4
    try:
        if a.dry_run:
            state = Path(a.project) / ".pdg" / "state.json"
            from .util import sha256_file
            with _locked(a.project, "submit --dry-run"):
                eng, before = _engine(a.project), sha256_file(state)
            rep = check_node(eng, a.node, outputs)
            with _locked(a.project, "submit --dry-run"):
                if sha256_file(state) != before:
                    print("the run changed while it was checked; run it again")
                    return 4
            _print_check_node(rep)
            return _check_node_exit(rep)
        with _locked(a.project, "submit"):
            eng = _engine(a.project)
            res = eng.submit(a.node, outputs, a.token, a.actor)
            status = eng.run()
    except EngineError as exc:
        print(f"refused: {exc}")
        return 4
    if res.get("parked"):
        print(f"{a.node}: not judged, and no attempt was used: the run is blocked. The submission is parked. Once the "
              "block is resolved, run the same command again. If resolving it withdraws this node, a review's findings "
              "are recorded as feedback and any other output is listed in the node's next packet.")
        for f in res["failures"]:
            print("  -", f)
    elif res["failures"]:
        print(f"{a.node} attempt failed ({res['attempts_left']} attempt(s) left):")
        for f in res["failures"]:
            print("  -", f)
    for n in res.get("notices", []):
        print("note:", n)
    print(_summary(status))
    return _exit_for(status)


def _print_check_node(rep: dict[str, Any]) -> None:
    for key, path in sorted(rep["resolved"].items()):
        print(f"output {key}: {path}")
    for line in rep["refused"]:
        print("refused:", line)
    for line in rep["failures"]:
        print("would block:", line)
    print(f"submit command: {rep['command']}")
    print(f"would block {len(rep['failures'])} · advisory {len(rep['advisory'])} · deferred {len(rep['deferred'])}")


def _check_node_exit(rep: dict[str, Any]) -> int:
    return 4 if rep["refused"] else 1 if rep["failures"] else 3 if rep["advisory"] else 0


def cmd_check_node(a) -> int:
    from .engine import EngineError
    from .check_node import check_node
    outputs = {}
    for kv in a.output or []:
        k, _, v = kv.partition("=")
        if not k or not v:
            print(f"refused (nothing changed): --output {kv!r} needs the form key=path")
            return 4
        outputs[k] = v
    try:
        state = Path(a.project) / ".pdg" / "state.json"
        from .util import sha256_file
        with _locked(a.project, "check-node"):
            eng, before = _engine(a.project), sha256_file(state)
        rep = check_node(eng, a.node, outputs)
        with _locked(a.project, "check-node"):
            if sha256_file(state) != before:
                print("the run changed while it was checked; run it again")
                return 4
    except EngineError as exc:
        print(f"refused: {exc}")
        return 4
    _print_check_node(rep)
    return _check_node_exit(rep)


def cmd_draft_interpretation(a) -> int:
    from .engine import EngineError
    from .interpretation import write_draft
    try:
        with _locked(a.project, "draft-interpretation"):
            eng = _engine(a.project)
            out = Path(a.out) if a.out else eng.project.root / "work" / "n16_feedback_diagnosis" / "draft-interpretation.json"
            path = write_draft(eng, out if out.is_absolute() else eng.project.root / out)
    except EngineError as exc:
        print(f"refused: {exc}")
        return 4
    print(f"draft interpretation: {path}")
    print(f"finding sidecar: {path.with_suffix('.findings.json')}")
    return 0


def cmd_revise_brief(a) -> int:
    from .engine import EngineError
    try:
        with _locked(a.project, "revise-brief"):
            eng = _engine(a.project)
            touched = eng.revise_brief(Path(a.from_file), a.actor, a.reason, a.on_behalf_of)
            status = eng.run()
    except EngineError as exc:
        print(f"refused: {exc}")
        return 4
    print("re-opened: " + ", ".join(touched))
    print(_summary(status))
    return _exit_for(status)


def cmd_approve(a) -> int:
    from .engine import EngineError
    decision = a.decision or ("rejected" if a.reject else "approved")
    try:
        reason = _reason(a)
    except EngineError as exc:
        print(f"refused: {exc}")
        return 4
    try:
        with _locked(a.project, "approve"):
            eng = _engine(a.project)
            node = eng.node(a.node)
            if a.reject and "changes_requested" in node.human_review.outcomes:
                decision = "changes_requested"
            eng.decide(a.node, decision, a.actor, reason, a.feedback, on_behalf_of=a.on_behalf_of,
                       recorded_by=a.recorded_by, source=a.source, interprets=a.interprets)
            status = eng.run()
    except EngineError as exc:
        print(f"refused: {exc}")
        return 4
    for n in eng.notices:
        print("note:", n)
    print(_summary(status))
    return _exit_for(status)


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _human_args(p) -> None:
    p.add_argument("--recorded-by", help="who typed the human action (defaults to --actor/--by)")
    p.add_argument("--source", default="", help="verbatim source words when an agent transcribed the action")
    p.add_argument("--interprets", action="store_true", help="the transcription goes beyond the source words and needs ratification")


def _reason(a, attr: str = "reason") -> str:
    from .engine import EngineError
    value = getattr(a, attr, None)
    if value is None:
        if sys.stdin.isatty() and sys.stdout.isatty():
            print(f"{attr.replace('_', ' ')}: ", end="", flush=True)
            ready, _, _ = select.select([sys.stdin], [], [], 30)
            if not ready:
                raise EngineError(f"--{attr.replace('_', '-')} was not provided and no input arrived at the prompt")
            value = sys.stdin.readline().rstrip("\n")
        else:
            raise EngineError(f"--{attr.replace('_', '-')} is required when no terminal is attached")
    if not str(value).strip():
        raise EngineError(f"{attr.replace('_', ' ')} is required")
    if PLACEHOLDER_RE.fullmatch(str(value).strip()):
        raise EngineError(f"--{attr.replace('_', '-')} is still a template placeholder; type your own words")
    return value


def _simple(a, fn) -> int:
    from .engine import EngineError
    needs_reason = {"defer", "decide-deferred", "correct-check", "change-request", "decide-change-request",
                    "invalidate", "accept-risk", "ratify"}
    try:
        command = getattr(a, "command", "")
        if command in needs_reason and getattr(a, "reason", None) is None:
            a.reason = _reason(a)
        if command == "unblock" and getattr(a, "note", None) is None:
            a.note = _reason(a, "note")
        with _locked(a.project, a.command):
            eng = _engine(a.project)
            out = fn(eng)
            status = eng.run() if a.command not in ("rollback",) else eng.status()
    except EngineError as exc:
        print(f"refused: {exc}")
        return 4
    if out is not None:
        _print(out if not hasattr(out, "model_dump") else out.model_dump())
    for n in eng.notices:
        print("note:", n)
    print(_summary(status))
    return _exit_for(status)


def cmd_ledger_verify(a) -> int:
    """The hash chain, and whether the ledger still reaches the last event the state recorded (a cut-off or replaced
    ledger has a valid chain but lost its end)."""
    from .engine import ledger_health
    state = Path(a.project) / ".pdg" / "state.json"
    runtime = read_json(state).get("runtime", {}) if state.exists() else None
    ok, n, msg = ledger_health(Path(a.project) / ".pdg" / "ledger.jsonl", runtime)
    print(f"ledger {'ok' if ok else 'BROKEN'}: {n} events — {msg}")
    return 0 if ok else 1


def cmd_accept_ledger_break(a) -> int:
    from .engine import Engine
    with _locked(a.project, "accept-ledger-break"):
        eng = Engine(a.project, accept_ledger_break=(a.actor, a.reason))
    brk = eng.state.runtime.ledger_breaks[-1]
    print(f"ledger break accepted by {brk.actor}: {brk.describe()}; the ledger continues at event {brk.resumes_at_seq}. "
          "`pdg ledger-verify`, the report and the release summary list the break.")
    return 0


def cmd_lineage(a) -> int:
    st = read_json(Path(a.project) / ".pdg" / "state.json")
    arts = st["artifacts"]
    seen, stack, out = set(), [a.artifact], []
    while stack:
        x = stack.pop()
        if x in seen or x not in arts:
            continue
        seen.add(x)
        out.append({"id": x, "node": arts[x]["node"], "sha256": arts[x]["sha256"][:16], "current": arts[x]["current"]})
        stack.extend(arts[x]["inputs"])
    _print(out)
    return 0 if out else 4


def cmd_report(a) -> int:
    from .report import write_report
    path = write_report(Path(a.project), Path(a.out) if a.out else None)
    print(f"report: {path}")
    return 0


def cmd_memory(a) -> int:
    from .lock import rules_lock
    from .memory import DEFAULT_RULES, MemoryRefusal, RuleBase
    rules_path = Path(a.rules) if a.rules else DEFAULT_RULES
    try:
        if a.action == "status":
            rb = RuleBase(rules_path)
            s = rb.summary()
            print(f"rule base v{s['version']}: {s['rules']} rules")
            for state, ids in s["by_state"].items():
                print(f"  {state:<10} {len(ids):>3}  {' '.join(ids)}")
            print(f"awaiting a named human's approval (validated, advisory): {len(s['awaiting_human_approval'])}")
            print(f"seed approvals awaiting Wei's confirmation (`pdg memory confirm <rule> --by Wei`): "
                  f"{len(s['seed_approvals_awaiting_confirmation'])}")
            pending = s["amendments_awaiting_confirmation"]
            print(f"agent amendments awaiting Wei's confirmation (`pdg memory confirm {','.join(pending) or '<rules>'} "
                  f"--by Wei`): {len(pending)}")
            return 0
        with rules_lock(rules_path, f"memory {a.action}"):
            rb = RuleBase(rules_path)
            if a.action == "confirm":
                ids = rb.seed_approvals() if a.all_seed else [x.strip() for x in (a.rule or "").split(",") if x.strip()]
                done = rb.confirm_many(ids, a.by, human=True, reason=_reason(a) if a.reason is not None else "",
                                       evidence=a.evidence or [], recorded_by=a.recorded_by, source=a.source,
                                       interprets=a.interprets)
                print(f"confirmed {len(done)} rule(s) as Wei's decision")
            elif a.action == "promote":
                check = {k: v for k, v in (("fn", a.check_fn), ("dimensions", a.check_dimension or []),
                                           ("test", a.check_test)) if v}
                _check_exists(check)
                rb.transition(a.rule, a.to, a.by, human=a.human, evidence=a.evidence or [],
                              reason=_reason(a) if a.reason is not None else "",
                              adopted_in=a.adopted_in or "", statement=a.statement, check=check or None,
                              recorded_by=a.recorded_by, source=a.source, interprets=a.interprets)
            elif a.action == "apply":
                try:
                    proposal = read_json(a.proposal)
                except ValueError as exc:
                    raise MemoryRefusal(f"{a.proposal} is not valid JSON ({exc}); nothing applied") from None
                if not isinstance(proposal, dict) or not isinstance(proposal.get("candidates", []), list) \
                        or not isinstance(proposal.get("observations", []), list):
                    raise MemoryRefusal(f"{a.proposal} is not a learning proposal (expected candidates and observations lists)")
                try:
                    out = rb.apply_proposal(proposal, a.approved_by, human=True, recorded_by=a.recorded_by,
                                            source=a.source, interprets=a.interprets)
                except (KeyError, TypeError, ValueError) as exc:
                    raise MemoryRefusal(f"{a.proposal} is malformed ({exc.__class__.__name__}: {exc}); nothing applied") from None
                _print(out)
            print(f"rule base now v{rb.version}")
    except MemoryRefusal as exc:
        print(f"refused by memory governance: {exc}")
        return 3
    return 0


def _check_exists(check: dict) -> None:
    """A rule's check must be real: the tool resolves, each rubric dimension exists, and the test file is in the package."""
    from .evaluation import dimension_index, load_rubrics
    from .graph import resolve_tool
    from .memory import MemoryRefusal
    if check.get("fn"):
        try:
            resolve_tool(check["fn"])
        except (ImportError, AttributeError, ValueError):
            raise MemoryRefusal(f"check {check['fn']} does not resolve to a tool in pdg/tools") from None
    unknown = [d for d in check.get("dimensions", []) if d not in dimension_index(load_rubrics())]
    if unknown:
        raise MemoryRefusal(f"rubric dimension(s) {', '.join(unknown)} do not exist")
    if check.get("test") and not (PKG_ROOT / check["test"].split("::")[0]).is_file():
        raise MemoryRefusal(f"test {check['test']} is not a file in the package")


def cmd_dry_run(a) -> int:
    from .dryrun import run
    out = run(Path(a.out) if a.out else None, keep=not a.no_keep)
    return 0 if out["passed"] else 1


def _project_above(path: Path) -> Path | None:
    """The project a prototype sits in (its drafts/ or work/): the nearest folder above it holding pdg.project.yaml."""
    for p in ([path] if path.is_dir() else []) + list(path.parents):
        if (p / "pdg.project.yaml").is_file():
            return p
    return None


def _project_for_check(project: Path) -> dict[str, Any]:
    """What the gate reads from a project, read here without the lock and without writing: the accepted thresholds,
    the design system's colours and pdg.project.yaml (its reference build) (field run 2, R2-28)."""
    import yaml
    from .controls import accepted_path, front_matter
    from .engine import _deep_merge
    from .models import ProjectState
    from .tools.browser import documented_state_fills, status_colours
    th = yaml.safe_load((PKG_ROOT / "config" / "defaults.yaml").read_text())["thresholds"]
    config = yaml.safe_load((project / "pdg.project.yaml").read_text()) or {}
    sp = project / ".pdg" / "state.json"
    state = ProjectState.model_validate(read_json(sp)) if sp.is_file() else None
    rec = state.controls.get("evaluation") if state else None
    ev = (accepted_path(project, rec) if rec else None) or project / "controls" / "evaluation.md"
    if ev.is_file():
        th = _deep_merge(th, front_matter(ev.read_text()).get("thresholds") or {})
    system = state.design.system if state else None
    return {"thresholds": th, "config": config, "tokens": {c.name: c.value for c in system.colors} if system else {},
            "status": status_colours(system.colors) if system else {},
            "documented": documented_state_fills(system.colors) if system else {}}


def findings_by_screen(findings: list[dict], cap: int = 12) -> list[str]:
    """A dimension's findings, one per line under their screen, at most `cap` a screen: 22 findings on one line could not
    be triaged (field run 2). A message that opens with its screen's name does not repeat it."""
    by_screen: dict[str, list[str]] = {}
    for f in findings:
        scr = f.get("location") or "(page)"
        msg = f["message"]
        by_screen.setdefault(scr, []).append(msg[len(scr) + 2:] if msg.startswith(f"{scr}: ") else msg)
    return [line for scr, msgs in by_screen.items()
            for line in [f"  {scr} ({len(msgs)}):", *(f"    - {m}" for m in msgs[:cap])]
            + ([f"    … and {len(msgs) - cap} more"] if len(msgs) > cap else [])]


CHECK_INPUTS = {"plan": ("N10's plan", "work/n10_prototype_planning/a<N>/plan.json", "scenarios"),
                "experience": ("N07's experience artifact", "work/n07_experience_architecture/a<N>/experience.json", "screens")}


def _check_input(path: str, what: str) -> tuple[dict | None, str]:
    """A `check-prototype` input as the JSON artifact it must be, or a one-line refusal naming the file it wants: given
    the control document (`controls/experience.md`) it died with a JSONDecodeError traceback (field run W64)."""
    name, where, key = CHECK_INPUTS[what]
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        return None, f"refused (nothing checked): --{what} {path} cannot be read ({exc.strerror or exc})"
    except ValueError:
        return None, (f"refused (nothing checked): --{what} {path} is not JSON; it wants {name}, {where}"
                      + (", not the control document" if path.endswith(".md") else ""))
    if not isinstance(doc, dict):
        return None, f"refused (nothing checked): --{what} {path} is not a JSON object; it wants {name}, {where}"
    # the shapes the suite reads, so a wrongly shaped file is refused here, not a traceback later (batch 18 review I3)
    if what == "experience":
        screens = doc.get(key)
        bad = ("no `screens` list" if not isinstance(screens, list) else
               "a screen that is not an object with a string `id`"
               if any(not isinstance(s, dict) or not isinstance(s.get("id"), str) for s in screens) else "")
    else:
        bad = next((f"`{k}` is not a {kind.__name__}" for k, kind in (("scenarios", list), ("states", list),
                    ("viewports", list), ("samples", dict)) if k in doc and not isinstance(doc[k], kind)), "") or (
            "a `samples` entry that is not a list of routes" if isinstance(doc.get("samples"), dict)
            and any(not isinstance(v, list) for v in doc["samples"].values()) else "")
    if bad:
        return None, f"refused (nothing checked): --{what} {path} is not {name} ({bad}); it wants {where}"
    return doc, ""


def cmd_recheck_release(a) -> int:
    """Re-run a passed run's tool checks, the browser suite included, on what it released, read-only (W65). The project
    lock is held only to read the run and to record the re-check: a person may file feedback while the suite runs.
    `--decline` records a person's decision not to re-open the release on what the last re-check found."""
    import datetime as dt
    from .engine import EngineError
    from .util import sha256_file
    if a.decline:
        if not a.actor:
            print("refused (nothing changed): --decline needs --actor")
            return 4
        reason = a.reason if a.reason is not None else _reason(a)
        return _simple(a, lambda e: e.decline_recheck(a.actor, reason, a.on_behalf_of,
                                                      a.recorded_by, a.source, a.interprets))
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(a.out).resolve() if a.out else (Path(a.project).resolve() / ".pdg" / "release-recheck" / stamp)
    state = Path(a.project) / ".pdg" / "state.json"
    try:
        with _locked(a.project, "recheck-release"):
            eng, before = _engine(a.project), sha256_file(state)
        rep = eng.recheck_release(out)
    except EngineError as exc:
        print(f"refused (nothing checked): {exc}")
        return 4
    with _locked(a.project, "recheck-release"):
        changed_meanwhile = sha256_file(state) != before
        if not changed_meanwhile:
            eng.record_recheck(rep)
    if changed_meanwhile:   # the run moved on: what was re-checked may no longer be what is released
        print("the run changed while it was re-checked: this report is not recorded and proposes nothing; re-run once the run is quiet")
    judged = "; ".join((f"code {j['code'][:12]} and configuration {j['config'][:12]}" if j["code"]
                        else "checks not recorded (passed before pdg recorded them)") + f" ({len(j['nodes'])} nodes)"
                       for j in rep["judged_by"]) or "nothing recorded"
    now_ = rep["checked_with"]
    print(f"release v{rep['build_version']}: judged by {judged}; re-checked with code {now_['code'][:12]} and "
          f"configuration {now_['config'][:12]}")
    blocking = [r for r in rep["failures"] if r["blocks"]]
    for r in rep["failures"]:
        print(f"  {r['node']} {r['dim']} ({'would block' if r['blocks'] else 'advisory'}): {r['evidence'][:300]}")
    for r in rep["not_run"]:
        print(f"  not checked: {r['node']} {r['check']}: {r['why'][:300]}")
    print(f"{len(rep['failures'])} failing, {len(blocking)} would block, {len(rep['not_run'])} check(s) not run, across "
          f"{len(rep['checked'])} node(s)" + ("" if blocking or rep["not_run"] else "; nothing to re-open"))
    if blocking and not changed_meanwhile:   # the decision is a person's: each command is ready once they agree
        print("To re-open the release on one, a person runs its feedback command:")
        for r in blocking:
            text = f"{r['dim']} fails on the released v{rep['build_version']} (pdg recheck-release): {r['evidence'][:240]}"
            print(f"  pdg feedback {shlex.quote(a.project)} --actor NAME --text {shlex.quote(text)}")
    print(f"report: {(out / 'recheck-release.json').resolve()}")
    return 5 if changed_meanwhile else 1 if blocking else 3 if rep["not_run"] else 0


def cmd_check_prototype(a) -> int:
    import yaml
    from .context import CheckResult
    from .tools.browser import findings_from, note_reference, reference_for, reference_hint_for, run_suite, suite_screens
    plan, refusal = _check_input(a.plan, "plan")
    experience, refused = _check_input(a.experience, "experience") if a.experience else (None, "")
    if refusal or refused:
        print(refusal or refused)
        return 4
    root = Path(a.prototype)
    if a.project and not (Path(a.project) / "pdg.project.yaml").is_file():
        print(f"refused (nothing checked): {a.project} has no pdg.project.yaml")
        return 4
    # a prototype checked before submission sits in its project: the reference, the design system and the accepted
    # thresholds the gate will use are read here too, so REF-PARITY is not a silent pass (field run 2, R2-28)
    project = Path(a.project).resolve() if a.project else _project_above(root.resolve())
    proj = _project_for_check(project) if project else None
    t = (proj["thresholds"] if proj else yaml.safe_load((PKG_ROOT / "config" / "defaults.yaml").read_text())["thresholds"])["browser"]
    if (root / "build-manifest.json").is_file():
        entry = root / json.loads((root / "build-manifest.json").read_text())["entry"]
    else:
        entry = root / "index.html" if root.is_dir() else root
    if not entry.is_file():
        print(f"refused (nothing checked): no prototype entry at {entry}")
        return 4
    reference = error = None
    if project:
        try:
            reference = reference_for(project, proj["config"])
        except (OSError, KeyError, TypeError, ValueError) as exc:   # a misdeclared reference fails REF-PARITY, not the suite
            error = str(exc)
    screens = (suite_screens(experience["screens"], plan.get("samples") or {}) if experience is not None
               else [{"id": "entry", "route": None}])   # without the experience spec, sweep the entry page itself
    out = Path(a.out or "prototype-check")
    try:
        rep = run_suite(entry, plan.get("scenarios", []), plan.get("states", []), screens,
                        plan.get("viewports") or t["viewports"], t, out, forbidden=plan.get("forbidden_text") or None,
                        tokens=proj["tokens"] if proj else None, reference=reference,
                        status=proj["status"] if proj else None, documented=proj["documented"] if proj else None)
    except Exception as exc:  # noqa: BLE001 - a suite that cannot run is reported, never a pass
        print(f"check-prototype: the browser suite could not run ({exc.__class__.__name__}: {exc})")
        return 4
    if project:
        note_reference(rep, out, error, None if reference or error else reference_hint_for(project))
    res = CheckResult()
    findings_from(rep, t, res)
    if not plan.get("scenarios"):
        res.dim("FUNC-SCENARIOS", False, "the plan has no scenarios, so no task was checked")
    print(f"project: {project}{'' if a.project else ' (found above the prototype; --project names another)'}" if project
          else "note: no --project and no pdg.project.yaml above the prototype, so the reference build, the design "
               "system's colours and the project's thresholds were not used")
    for dim, o in res.dimensions.items():
        print(f"{'PASS' if o.passed else 'FAIL'} {dim}: {o.evidence}")
        print("".join(f"{line}\n" for line in findings_by_screen(o.findings)), end="")
    print(f"report: {out / 'browser-report.json'} · screenshots: {out / 'screenshots'}")
    would_block, advisory = _prototype_verdict_counts(project, res)
    deferred = _deferred_count(project)
    print(f"would block {would_block} · advisory {advisory} · deferred {deferred}")
    return 1 if would_block else 3 if advisory else 0


def _prototype_verdict_counts(project: Path | None, res) -> tuple[int, int]:
    from .evaluation import can_fail, load_rubrics
    rule_states = _rule_states_for_check(project)
    dims = {d["id"]: d for rub in load_rubrics().values() for d in rub.get("dimensions", [])}
    failed = [dim for dim, out in res.dimensions.items() if not out.passed]
    blocking = [dim for dim in failed if dim not in dims or can_fail(dims[dim], rule_states)]
    advisory = [dim for dim in failed if dim not in blocking]
    return len(blocking), len(advisory)


def _rule_states_for_check(project: Path | None) -> dict[str, str]:
    import yaml
    from .memory import RuleBase
    from .memory import DEFAULT_RULES
    if project:
        try:
            cfg = yaml.safe_load((project / "pdg.project.yaml").read_text()) or {}
            rp = cfg.get("rules")
            rules = (project / rp).resolve() if rp and not Path(rp).is_absolute() else Path(rp or DEFAULT_RULES)
            return RuleBase(rules).states()
        except (OSError, ValueError, KeyError):
            return RuleBase(DEFAULT_RULES).states()
    return RuleBase(DEFAULT_RULES).states()


def _deferred_count(project: Path | None) -> int:
    if not project:
        return 0
    try:
        st = read_json(Path(project) / ".pdg" / "state.json")
    except (OSError, ValueError):
        return 0
    return sum(1 for d in st.get("evaluation", {}).get("defects", [])
               if d.get("deferred") and d.get("status") in ("open", "persisting", "needs_human"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pdg", description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("validate", help="validate the graph")
    p.add_argument("--workflow")
    p.set_defaults(fn=cmd_validate)
    p = sub.add_parser("docs", help="generate catalogs, schemas, graph.mmd/svg, principles")
    p.add_argument("--check", action="store_true")
    p.set_defaults(fn=cmd_docs)
    p = sub.add_parser("init", help="create a project")
    p.add_argument("project")
    p.add_argument("--name", required=True)
    p.set_defaults(fn=cmd_init)
    for name, fn in (("run", cmd_run), ("status", cmd_status), ("tasks", cmd_tasks), ("ledger-verify", cmd_ledger_verify),
                     ("report", cmd_report)):
        p = sub.add_parser(name)
        p.add_argument("project")
        if name == "run":
            p.add_argument("--max-steps", type=int, default=500)
        if name == "status":
            p.add_argument("--json", action="store_true")
            p.add_argument("--evaluation", action="store_true")
            p.add_argument("--checkpoints", action="store_true")
        if name == "report":
            p.add_argument("--out")
        p.set_defaults(fn=fn)
    p = sub.add_parser("waiting", help="show every pending human-only action across projects")
    p.add_argument("projects", nargs="+")
    p.set_defaults(fn=cmd_waiting)
    p = sub.add_parser("check-build", help="run N11's checks on a build folder before submitting it (read-only)")
    p.add_argument("build"); p.add_argument("--project", help="the project, for its screens, design system and thresholds")
    p.set_defaults(fn=cmd_check_build)
    p = sub.add_parser("archive", help="list, or move out, a run's earlier attempt folders (records and hashes stay)")
    p.add_argument("project"); p.add_argument("--apply", action="store_true"); p.add_argument("--actor")
    p.add_argument("--keep", action="append", default=[], help="repeatable project-relative path to keep in place")
    p.add_argument("--to", default="~/Downloads/Archive")
    _human_args(p)
    p.set_defaults(fn=cmd_archive)
    p = sub.add_parser("release-shelf", help="rebuild the stable release shelf from the ledger and packages")
    p.add_argument("project")
    p.set_defaults(fn=cmd_release_shelf)
    p = sub.add_parser("review", help="write the D15 end-review packet and board, or record Wei's reply")
    p.add_argument("project"); p.add_argument("--date"); p.add_argument("--record")
    p.add_argument("--score-tool", help=argparse.SUPPRESS)
    p.set_defaults(fn=cmd_review)
    p = sub.add_parser("check-output", help="check a file against a node's declared output, before submitting it")
    p.add_argument("node"); p.add_argument("key"); p.add_argument("file")
    p.add_argument("--workflow", default=None, help="a workflow file other than the package's")
    p.add_argument("--project", help="project context for checks that need current findings or feedback")
    p.set_defaults(fn=cmd_check_output)
    p = sub.add_parser("check-node", help="dry-run a node submission without using an attempt")
    p.add_argument("project"); p.add_argument("node")
    p.add_argument("--output", action="append", help="key=path (relative to the packet's work dir)")
    p.set_defaults(fn=cmd_check_node)
    p = sub.add_parser("draft-interpretation", help="write an N16 interpretation skeleton from current reviews")
    p.add_argument("project"); p.add_argument("--out")
    p.set_defaults(fn=cmd_draft_interpretation)
    p = sub.add_parser("revise-brief", help="replace sources/brief.md, refresh input hashes and re-open N02 onward")
    p.add_argument("project"); p.add_argument("--from", dest="from_file", required=True)
    p.add_argument("--actor", required=True); p.add_argument("--reason", required=True)
    p.add_argument("--on-behalf-of")
    p.set_defaults(fn=cmd_revise_brief)
    p = sub.add_parser("submit", help="an agent submits a node's outputs")
    p.add_argument("project"); p.add_argument("node")
    p.add_argument("--token"); p.add_argument("--actor")
    p.add_argument("--output", action="append", help="key=path (relative to the packet's work dir)")
    p.add_argument("--dry-run", action="store_true", help="run the submission checks without using an attempt")
    p.set_defaults(fn=cmd_submit)
    p = sub.add_parser("approve", help="a named human decides a gate")
    p.add_argument("project"); p.add_argument("node")
    p.add_argument("--actor", required=True); p.add_argument("--reason")
    p.add_argument("--reject", action="store_true"); p.add_argument("--decision")
    p.add_argument("--feedback", action="append")
    p.add_argument("--on-behalf-of")
    _human_args(p)
    p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("feedback", help="record feedback on the current version (re-opens diagnosis)")
    p.add_argument("project"); p.add_argument("--actor", required=True); p.add_argument("--text", required=True)
    p.add_argument("--at", default=""); p.add_argument("--severity", default="")
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.add_feedback(a.text, a.actor, a.at, a.severity,
                                                                    recorded_by=a.recorded_by, source=a.source,
                                                                    interprets=a.interprets)))
    p = sub.add_parser("defer", help="park a defect for a human decision; the gate neither routes nor resolves it")
    p.add_argument("project"); p.add_argument("defect"); p.add_argument("--reason")
    p.add_argument("--trigger", required=True, help="what brings it back: the decision or event that ends the wait")
    p.add_argument("--actor", required=True); p.add_argument("--on-behalf-of")
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.defer(a.defect, _reason(a), a.trigger, a.actor, a.on_behalf_of,
                                                            a.recorded_by, a.source, a.interprets)))
    p = sub.add_parser("decide-deferred", help="a named human ends a deferral: fix it, close it, keep it for the next build, "
                                                     "or mark it resolved once a review said it no longer holds")
    p.add_argument("project"); p.add_argument("defect")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--fix", action="store_const", const="fix", dest="decision")
    g.add_argument("--close", action="store_const", const="close", dest="decision")
    g.add_argument("--keep", action="store_const", const="keep", dest="decision")
    g.add_argument("--resolved", action="store_const", const="resolved", dest="decision",
                   help="a review said it no longer holds, and you checked: it is resolved, and its reviews re-check it stays so")
    p.add_argument("--reason"); p.add_argument("--actor", required=True); p.add_argument("--on-behalf-of")
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.decide_deferred(a.defect, a.decision, _reason(a), a.actor,
                                                                      a.on_behalf_of)))
    p = sub.add_parser("correct-check", help="correct an open defect's acceptance check, with a reason, before the reviews")
    p.add_argument("project"); p.add_argument("defect"); p.add_argument("--check", required=True)
    p.add_argument("--reason"); p.add_argument("--actor", required=True); p.add_argument("--on-behalf-of")
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.correct_check(a.defect, a.check, _reason(a), a.actor, a.on_behalf_of)))
    p = sub.add_parser("change-request", help="a named human unlocks an approved control document for one writer")
    p.add_argument("project"); p.add_argument("--doc", required=True)
    p.add_argument("--reason", help="the stakeholder's words, quoted, then the outcome they ask for, "
                                                   "paraphrased; not the components the build has (R2-32)")
    p.add_argument("--actor", required=True); p.add_argument("--writer")
    p.add_argument("--on-behalf-of")
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.change_request(a.doc, _reason(a), a.actor, a.writer, a.on_behalf_of,
                                                                      a.recorded_by, a.source, a.interprets)))
    p = sub.add_parser("decide-change-request", help="a named human approves or declines an agent's open change request")
    p.add_argument("project"); p.add_argument("change_request")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--approve", action="store_true"); g.add_argument("--decline", action="store_true")
    p.add_argument("--reason"); p.add_argument("--actor", required=True); p.add_argument("--on-behalf-of")
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.decide_change_request(a.change_request, a.approve, a.actor,
                                                                            _reason(a), a.on_behalf_of, a.recorded_by,
                                                                            a.source, a.interprets)))
    p = sub.add_parser("unblock", help="a named human resolves an escalation")
    p.add_argument("project"); p.add_argument("node"); p.add_argument("--actor", required=True)
    p.add_argument("--note"); p.add_argument("--reset-budget", action="store_true")
    p.add_argument("--waive", action="append")
    p.add_argument("--restore-controls", action="store_true", help="restore hand-edited control documents to their accepted versions")
    p.add_argument("--on-behalf-of")
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.unblock(a.node, a.actor, a.note, a.reset_budget, a.waive,
                                                              a.restore_controls, a.on_behalf_of, a.recorded_by, a.source,
                                                              a.interprets)))
    p = sub.add_parser("accept-config", help="a named human accepts a mid-run workflow/rules/rubric change")
    p.add_argument("project"); p.add_argument("--actor"); p.add_argument("--reason")
    p.add_argument("--on-behalf-of")
    p.add_argument("--dry-run", action="store_true", help="show what accepting would re-judge and withdraw; change nothing")
    p.add_argument("--discard-in-flight", action="store_true", help="accept even though work out with agents is withdrawn")
    _human_args(p)
    p.set_defaults(fn=cmd_accept_config)
    p = sub.add_parser("invalidate", help="a named human forces nodes to re-run")
    p.add_argument("project"); p.add_argument("nodes", nargs="+"); p.add_argument("--actor", required=True)
    p.add_argument("--reason")
    p.add_argument("--on-behalf-of")
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.invalidate_nodes(a.nodes, _reason(a), a.actor, a.on_behalf_of,
                                                                        a.recorded_by, a.source, a.interprets)))
    p = sub.add_parser("delegate", help="a named human grants a scoped, time-limited delegation to an agent")
    p.add_argument("project"); p.add_argument("--by", required=True); p.add_argument("--agent", required=True)
    p.add_argument("--instruction", required=True, nargs="?"); p.add_argument("--scope", required=True)
    p.add_argument("--nodes", default="", help="gates the grant may decide (decide only)")
    p.add_argument("--except-nodes", default="", help="nodes no action in this grant covers, e.g. the release")
    p.add_argument("--expires", required=True, nargs="?")
    p.add_argument("--recorded-by", required=True, nargs="?",
                   help="who is typing this grant: the human themself, or the agent:<role> transcribing their words")
    p.add_argument("--source", default="", help="where the human's words came from (a chat message and its time)")
    p.add_argument("--budget-resets", type=int, default=None,
                   help="how many rework-budget resets an unblock under this grant may make (default: not limited)")
    p.add_argument("--include-release", action="store_true",
                   help="allow a decide grant to cover n18_final_verification")
    p.set_defaults(fn=cmd_delegate)
    p = sub.add_parser("revoke-delegation", help="a named human revokes a scoped delegation")
    p.add_argument("project"); p.add_argument("delegation"); p.add_argument("--by", required=True)
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.revoke_delegation(a.delegation, a.by, a.recorded_by, a.source,
                                                                        a.interprets)))
    p = sub.add_parser("accept-risk", help="a named human accepts building past an unvalidated assumption (N10's gate)")
    p.add_argument("project"); p.add_argument("assumption"); p.add_argument("--actor", required=True)
    p.add_argument("--reason")
    p.add_argument("--on-behalf-of")
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.accept_risk(a.assumption, a.actor, _reason(a), a.on_behalf_of,
                                                                   a.recorded_by, a.source, a.interprets)))
    p = sub.add_parser("accept-ledger-break", help="a named human accepts that ledger events were lost (no backup exists)")
    p.add_argument("project"); p.add_argument("--actor", required=True); p.add_argument("--reason", required=True)
    p.set_defaults(fn=cmd_accept_ledger_break)
    p = sub.add_parser("rollback", help="a named human restores a checkpoint")
    p.add_argument("project"); p.add_argument("--checkpoint", type=int, required=True); p.add_argument("--actor", required=True)
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.rollback(a.checkpoint, a.actor, a.recorded_by, a.source, a.interprets)))
    p = sub.add_parser("ratify", help="a named human confirms or reverses a delegated/transcribed action")
    p.add_argument("project"); p.add_argument("target")
    p.add_argument("--actor", required=True); p.add_argument("--reason"); p.add_argument("--reverse", action="store_true")
    _human_args(p)
    p.set_defaults(fn=lambda a: _simple(a, lambda e: e.ratify(a.target, a.actor, _reason(a), a.reverse,
                                                               a.recorded_by, a.source, a.interprets)))
    p = sub.add_parser("lineage")
    p.add_argument("project"); p.add_argument("artifact")
    p.set_defaults(fn=cmd_lineage)
    p = sub.add_parser("memory", help="the governed rule base")
    p.add_argument("action", choices=["status", "confirm", "promote", "apply"])
    p.add_argument("rule", nargs="?"); p.add_argument("--to"); p.add_argument("--by"); p.add_argument("--human", action="store_true")
    p.add_argument("--evidence", action="append"); p.add_argument("--reason"); p.add_argument("--adopted-in")
    p.add_argument("--statement"); p.add_argument("--proposal"); p.add_argument("--approved-by"); p.add_argument("--rules")
    _human_args(p)
    p.add_argument("--all-seed", action="store_true", help="confirm: every rule still enforced on a seed approval alone")
    p.add_argument("--check-fn", help="promote --to validated: the tool check that enforces the rule (module:fn)")
    p.add_argument("--check-dimension", action="append", help="promote --to validated: a rubric dimension id (repeatable)")
    p.add_argument("--check-test", help="promote --to validated: a test id that exercises the rule")
    p.set_defaults(fn=cmd_memory)
    p = sub.add_parser("dry-run", help="run the fictional example end to end and verify it")
    p.add_argument("--out"); p.add_argument("--no-keep", action="store_true")
    p.set_defaults(fn=cmd_dry_run)
    p = sub.add_parser("recheck-release", help="a passed run: re-run its checks, the browser suite included, on what it "
                                               "released, read-only, after a check upgrade (W65)")
    p.add_argument("project"); p.add_argument("--out", help="a new folder for the report and screenshots "
                                                           "(default: <project>/.pdg/release-recheck/<UTC time>)")
    p.add_argument("--decline", action="store_true", help="a named human decides not to re-open the release on what the "
                                                          "last re-check found; needs --actor and --reason")
    p.add_argument("--actor"); p.add_argument("--reason"); p.add_argument("--on-behalf-of")
    _human_args(p)
    p.set_defaults(fn=cmd_recheck_release)
    p = sub.add_parser("check-prototype", help="run the browser suite on any built prototype")
    p.add_argument("prototype")
    p.add_argument("--plan", required=True, help="N10's plan artifact, work/n10_prototype_planning/a<N>/plan.json")
    p.add_argument("--experience", help="N07's experience artifact, work/n07_experience_architecture/a<N>/experience.json "
                                        "(not controls/experience.md): the screens to sweep; without it, the entry page only")
    p.add_argument("--out")
    p.add_argument("--project", help="the project, for its reference build, design system and thresholds (default: the "
                                     "nearest folder above the prototype holding pdg.project.yaml)")
    p.set_defaults(fn=cmd_check_prototype)
    a = ap.parse_args(argv)
    from .engine import EngineError
    from .lock import Locked
    from .memory import MemoryRefusal
    import yaml
    from pydantic import ValidationError

    from .provenance import LedgerBehind, LedgerCorrupt
    from .util import ConcurrentChange, NotRegularFile
    try:
        return a.fn(a)
    except MemoryRefusal as exc:
        print(f"refused by memory governance (nothing written): {exc}")
        return 3
    except LedgerBehind as exc:   # the human action WAS saved; don't repeat it
        print(f"saved, but the ledger is behind: {exc}")
        return 4
    except (EngineError, Locked, FileNotFoundError) as exc:
        print(f"refused (nothing changed): {exc}")
        _notes(exc)
        return 4
    except (ConcurrentChange, NotRegularFile, LedgerCorrupt) as exc:
        print(f"refused: {exc}")
        _notes(exc)
        return 4
    except OSError as exc:   # a project file could not be read or written; a human action then recorded nothing
        what = f"{exc.filename}: {exc.strerror}" if getattr(exc, "filename", None) and exc.strerror else str(exc)
        print(f"refused (nothing changed): could not read or write {what}")
        _notes(exc)
        return 4
    except (ValidationError, yaml.YAMLError) as exc:   # an invalid graph, config or artifact file: say where, not a traceback
        print(f"refused (nothing changed): invalid input — {str(exc).splitlines()[0]}")
        for line in str(exc).splitlines()[1:6]:
            print(f"  {line}")
        return 4


def _notes(exc: BaseException) -> None:
    for note in getattr(exc, "__notes__", []):
        print(f"  note: {note}")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
