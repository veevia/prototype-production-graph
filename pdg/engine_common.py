"""Names the engine and its mixins share: its errors, the node-status groups and small helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .artifacts import ValidationDoc
from .models import NodeStatus
from .util import PKG_ROOT, rel, sha256_file, sha256_json

if TYPE_CHECKING:
    from .controls import ControlStore
    from .engine import Project
    from .graph import GraphIndex
    from .memory import RuleBase
    from .models import ProjectState, Workflow
    from .provenance import Ledger

ACTIVE = {NodeStatus.RUNNING, NodeStatus.VALIDATING}
WAITING = {NodeStatus.WAITING_AGENT, NodeStatus.WAITING_HUMAN}
RUNNABLE = {NodeStatus.PLANNED, NodeStatus.READY, NodeStatus.ITERATE, NodeStatus.STALE}
DEFECT_ACTIVE = {"open", "persisting", "needs_human"}
DELEGABLE_ACTIONS = {"decide", "change_request", "unblock", "accept_config", "invalidate", "accept_risk"}
HUMAN_ONLY_ACTIONS = (
    "approve or reject the release gate (N18)",
    "rollback to a checkpoint",
    "archive earlier attempts with `archive --apply`",
    "delegate release approval with `delegate --include-release`",
    "confirm memory rules",
    "promote memory rules with `--human`",
    "apply memory proposals",
    "accept a ledger break",
    "decline a release re-check",
    "ratify or reverse a transcribed interpretation",
    "reset a rework budget beyond a delegation's grant",
)
SIMULATED_LABEL = "Simulated session, not user evidence."
OS_NOISE = {".DS_Store", "Thumbs.db"}   # written by file managers, never by a node
PYTHON_CACHE_DIRS = {"__pycache__"}
PYTHON_CACHE_SUFFIXES = {".pyc"}


def validation_findings(vdoc: ValidationDoc, review: dict[str, Any] | None) -> tuple[dict[str, Any] | None, list[dict]]:
    """N14's review and the validation doc's findings to add to it. The engine labels every finding a simulated session
    raised, so no agent has to remember a word (field run W34). A validation finding the review already holds at the same
    dimension, location and element is not added again (W33: N14's contract asks for findings in both files)."""
    simulated = {s.participant for s in vdoc.sessions if s.simulated}

    def label(f: dict[str, Any]) -> dict[str, Any]:
        if f.get("participant") in simulated and "simulated" not in (f.get("evidence") or "").lower():
            f = {**f, "evidence": f"{SIMULATED_LABEL} {f.get('evidence') or ''}".strip()}
        return f

    if review is not None:
        review = {**review, "findings": [label(f) for f in review.get("findings", [])]}
    held = {(f.get("dimension"), f.get("location", ""), f.get("element", "")) for f in (review or {}).get("findings", [])}
    extra = []
    for f in vdoc.findings:
        key = (f.dimension, f.location, f.element)
        if f.by == "human" or key in held:
            continue
        held.add(key)
        extra.append(label(f.model_dump()))
    return review, extra


def latest_reviews_by_node(reviews, reviewers: list[str] | set[str] | None = None) -> dict[str, Any]:
    """Latest review record per reviewer, using the same ordering everywhere N16 reads current findings."""
    wanted = set(reviewers or [])
    out: dict[str, Any] = {}
    for r in reviews:
        if wanted and r.node not in wanted:
            continue
        cur = out.get(r.node)
        if cur is None or (r.build_version, r.attempt) > (cur.build_version, cur.attempt):
            out[r.node] = r
    return out


class EngineError(Exception):
    """A refused command. Nothing changed; the message says why (CLI exit code 4)."""


class StaleSubmission(EngineError):
    pass


def tree_sha(path: Path) -> tuple[str, int]:
    """Content hash of a file, or of a directory tree (sorted relative paths + file hashes)."""
    if path.is_file():
        return sha256_file(path), path.stat().st_size
    items, total = [], 0
    for p in sorted(x for x in path.rglob("*") if x.is_file() and not ignored_tree_noise(x)):
        items.append([str(p.relative_to(path)), sha256_file(p)])
        total += p.stat().st_size
    return sha256_json(items), total


def ignored_tree_noise(path: Path) -> bool:
    """Files that must never affect artifact integrity: OS noise and Python interpreter bytecode caches."""
    return path.name in OS_NOISE or path.suffix in PYTHON_CACHE_SUFFIXES or bool(PYTHON_CACHE_DIRS & set(path.parts))


def _deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def package_code_parts(pkg_root: Path) -> dict[str, str]:
    """The package's source files by path → sha256: which code judges a run."""
    return {rel(p, pkg_root): sha256_file(p) for p in sorted((pkg_root / "pdg").rglob("*.py")) if "__pycache__" not in p.parts}


def package_git_state(pkg_root: Path) -> dict[str, Any] | None:
    """The git commit and local package diff that judged a run. Git is provenance only: never fail a command over it."""
    def git(*args: str, timeout: int = 5) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(pkg_root), "--no-optional-locks", *args], check=False,
                              text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=timeout)

    try:
        inside = git("rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return None
        head = git("rev-parse", "HEAD")
        if head.returncode != 0:
            return None
        prefix = git("rev-parse", "--show-prefix").stdout.strip()
        changed = git("status", "--porcelain", "--untracked-files=all", "-z", "--", "pdg")
        if changed.returncode != 0:
            return {"commit": head.stdout.strip(), "uncommitted_files": [], "diff_sha256": None}
        statuses = _git_status_paths(changed.stdout, prefix)
        files = sorted({path for _, path in statuses if _package_state_file(path)})
        if not files:
            return {"commit": head.stdout.strip(), "uncommitted_files": [], "diff_sha256": None}
        diff = git("diff", "--", *files, timeout=10)
        diff_text = diff.stdout if diff.returncode == 0 else ""
        staged = git("diff", "--cached", "--", *files, timeout=10)
        if staged.returncode == 0:
            diff_text += staged.stdout
        for status, path in statuses:
            if path in files and status == "??":
                p = pkg_root / path
                if p.is_file():
                    diff_text += f"\nUNTRACKED {path} {sha256_file(p)}\n"
        return {"commit": head.stdout.strip(), "uncommitted_files": files, "diff_sha256": sha256_json(diff_text)}
    except (OSError, ValueError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return None


def _strip_git_prefix(path: str, prefix: str) -> str:
    return path[len(prefix):] if prefix and path.startswith(prefix) else path


def _git_status_paths(output: str, prefix: str) -> list[tuple[str, str]]:
    rows, parts, i = [], output.split("\0"), 0
    while i < len(parts):
        row = parts[i]
        i += 1
        if not row:
            continue
        status, path = row[:2], row[3:]
        if status[0] in {"R", "C"} and i < len(parts):
            i += 1   # old path
        rows.append((status, _strip_git_prefix(path, prefix)))
    return rows


def _package_state_file(path: str) -> bool:
    p = Path(path)
    return bool(p.parts) and p.parts[0] == "pdg" and not ignored_tree_noise(p)


def checks_fingerprint(code_parts: dict[str, str], config_parts: dict[str, str]) -> dict[str, str]:
    """The code and the configuration a verdict was reached with, each as one hash."""
    return {"code": sha256_json(code_parts), "config": sha256_json(config_parts)}


def config_files(project_root: Path, workflow_path: Path, rules_path: Path) -> dict[str, str]:
    """The files that judge a run, by path → sha256: its workflow, rules, defaults, rubrics and project file."""
    pkg = PKG_ROOT
    files = {rel(workflow_path, pkg): sha256_file(workflow_path), rel(rules_path, pkg): sha256_file(rules_path),
             "config/defaults.yaml": sha256_file(pkg / "config" / "defaults.yaml")}
    files.update({f"rubrics/{p.name}": sha256_file(p) for p in sorted((pkg / "rubrics").glob("*.yaml"))})
    cfg = project_root / "pdg.project.yaml"
    if cfg.exists():
        files["pdg.project.yaml"] = sha256_file(cfg)
    return files


def project_paths(project_root: Path) -> tuple[Path, Path]:
    """The workflow and rules a project runs with, resolved as the engine resolves them."""
    import yaml
    from .graph import DEFAULT_WORKFLOW
    from .memory import DEFAULT_RULES
    cfg_file = project_root / "pdg.project.yaml"
    cfg = (yaml.safe_load(cfg_file.read_text()) or {}) if cfg_file.is_file() else {}
    if not isinstance(cfg, dict):
        raise ValueError("pdg.project.yaml is not a mapping")
    wf = Path(cfg.get("workflow") or DEFAULT_WORKFLOW)
    wf = project_root / wf if cfg.get("workflow") and not wf.is_absolute() else wf
    rp = cfg.get("rules")
    rules = (project_root / rp).resolve() if rp and not Path(rp).is_absolute() else Path(rp or DEFAULT_RULES)
    return wf, rules


def checks_now(project_root: Path) -> dict[str, str]:
    """The code and configuration on disk now: what a re-check of the release would judge it with. The root is resolved
    as the engine resolves it, so both status paths name the same files (batch 19 review 2, I4)."""
    root = Path(project_root).resolve()
    return checks_fingerprint(package_code_parts(PKG_ROOT), config_files(root, *project_paths(root)))


def judged_with(rt: dict[str, Any]) -> dict[str, dict[str, str] | None]:
    """Each passed node the re-check can run → the code and configuration its checks ran with, or None for a node that
    passed before pdg recorded them: never taken as current until a re-check (batch 19 review 2, I3)."""
    return {n: ({"code": r["passed_checks"]["code"], "config": r["passed_checks"]["config"],
                 "git_state": r["passed_checks"].get("git_state")} if r.get("passed_checks") else None)
            for n, r in rt["nodes"].items()
            if r["status"] == "PASSED" and (not r.get("passed_checks") or r["passed_checks"].get("recheckable", True))}


def recheck_due(rt: dict[str, Any], build_version: int, project_root: Path, record: dict[str, Any] | None) -> dict[str, Any]:
    """For a passed run, what a check upgrade left unchecked (W65): {"changed": [...], "nodes": [...], "unrecorded":
    [...]} when a passed node was judged by other code or configuration than is on disk, or by checks never recorded;
    {"rechecked": record} when a re-check with the current checks left something open that no person declined; else {}.
    A clean re-check with the current checks, on this build, settles it. Read only for a passed run."""
    if rt["status"] != "RUN_PASS":
        return {}
    import yaml
    try:
        now_ = checks_now(project_root)
    except (OSError, ValueError, yaml.YAMLError) as exc:   # a malformed project file, say: status must still answer
        return {"unreadable": f"{exc.__class__.__name__}: {str(exc).splitlines()[0][:120] if str(exc) else ''}"}
    judged = judged_with(rt)
    unrecorded = sorted(n for n, j in judged.items() if j is None)
    stale = sorted(n for n, j in judged.items() if j is not None and (j["code"], j["config"]) != (now_["code"], now_["config"]))
    if not unrecorded and not stale:
        return {}
    if record and record.get("checked_with") == now_ and record.get("build_version") == build_version:
        return {"rechecked": record} if (record.get("blocking") or record.get("not_run")) and not record.get("declined") else {}
    changed = [what for what, key in (("the code", "code"), ("the configuration", "config"))
               if any(judged[n][key] != now_[key] for n in stale)]
    return {"changed": changed, "nodes": stale, "unrecorded": unrecorded}


def release_checks(state: Any) -> list[dict[str, Any]]:
    """The distinct code and configuration the passed nodes' tool checks ran with, with the nodes each judged."""
    groups: dict[tuple[str | None, str | None], list[str]] = {}
    git_states: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
    for n, j in judged_with(state.runtime.model_dump(mode="json")).items():
        key = (j["code"], j["config"]) if j else (None, None)
        groups.setdefault(key, []).append(n)
        if j and isinstance(j.get("git_state"), dict):
            git_states.setdefault(key, []).append(j["git_state"])
    return [{"code": c, "config": g, "git_state": _merge_git_states(git_states.get((c, g), [])), "nodes": sorted(ns)}
            for (c, g), ns in sorted(groups.items(), key=lambda x: -len(x[1]))]


def _merge_git_states(states: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not states:
        return None
    commits = sorted({s["commit"] for s in states if s.get("commit")})
    files = sorted({f for s in states for f in (s.get("uncommitted_files") or [])})
    diffs = sorted({s["diff_sha256"] for s in states if s.get("diff_sha256")})
    return {"commits": commits, "uncommitted_files": files, "diff_sha256": sha256_json(diffs) if diffs else None}


def uncommitted_check_files(rt: dict[str, Any]) -> list[str]:
    """Files from the package working tree that any passed check recorded as uncommitted."""
    files: set[str] = set()
    for row in judged_with(rt).values():
        if row and isinstance(row.get("git_state"), dict):
            files.update(row["git_state"].get("uncommitted_files") or [])
    return sorted(files)


def recheck_record(pdg_dir: Path) -> dict[str, Any] | None:
    import json
    p = pdg_dir / "release-recheck.json"
    try:
        return json.loads(p.read_text()) if p.is_file() else None
    except ValueError:
        return None


def not_needed(run_status: str, nodes: dict[str, str]) -> list[str]:
    """The nodes a passed run left stale (the rework after a gate that passed): not nodes still to run (field run W62)."""
    return [n for n, s in nodes.items() if run_status == "RUN_PASS" and s == "STALE"]


def budget_resets(ledger: Any) -> dict[str, int] | None:
    """Rework-budget resets so far, from the ledger's `unblocked` events, by who made them: a delegation id, or the
    named human (field run W59). None when the ledger is damaged: they cannot be counted, and a status must still print
    (review I4)."""
    from .provenance import LedgerCorrupt
    try:
        unblocked = ledger.events("unblocked")
    except LedgerCorrupt:
        return None
    out: dict[str, int] = {}
    for ev in unblocked:
        if ev["data"].get("reset_budget"):
            who = ev["data"].get("delegation") or ev["data"].get("actor", "?")
            out[who] = out.get(who, 0) + 1
    return out


def live_delegations(delegations: list[dict[str, Any]], at: Any, humans: list[str] | None = None) -> list[dict[str, Any]]:
    """Each grant not revoked, with its time left in seconds (negative once expired), the ones that expired within the last
    day included: a grant that lapses mid-change refused a stakeholder's request 22 minutes after it arrived, and nothing
    had said it would (field run 2, R2-30). A lapsed grant a later live one from the same grantor to the same agent covers
    is left out; a grant whose grantor is no longer a named human says so (review S1, S2)."""
    import datetime as dt
    out = []
    for d in delegations:
        if d.get("revoked_at"):
            continue
        row = {k: d.get(k) for k in ("id", "by", "agent", "scope", "nodes", "except_nodes", "budget_resets", "expires",
                                     "instruction")}
        try:
            end = dt.datetime.fromisoformat(str(d["expires"]).replace("Z", "+00:00"))
            row["left_s"] = int(((end if end.tzinfo else end.replace(tzinfo=dt.timezone.utc)) - at).total_seconds())
        except ValueError:
            row["left_s"] = None                           # unreadable: every action under it is refused (review N3)
        if humans is not None and d["by"] not in humans:
            row["lapsed_grantor"] = True
        if row["left_s"] is None or row["left_s"] > -86400:
            out.append(row)
    live = [r for r in out if r["left_s"] is not None and r["left_s"] > 0 and not r.get("lapsed_grantor")]

    def covers(x: dict[str, Any], r: dict[str, Any]) -> bool:
        """x authorizes at least what r did: its scope, its gates, its excluded gates and its reset cap (review S-C)."""
        return (x["id"] != r["id"] and x["by"] == r["by"] and x["agent"] == r["agent"] and set(r["scope"]) <= set(x["scope"])
                and (not x.get("nodes") or bool(r.get("nodes")) and set(r["nodes"]) <= set(x["nodes"]))
                and set(x.get("except_nodes") or []) <= set(r.get("except_nodes") or [])
                and (x.get("budget_resets") is None or r.get("budget_resets") is not None
                     and x["budget_resets"] >= r["budget_resets"]))
    for r in out:   # a grant another live one already renews needs no renewing (review N-a)
        if r["left_s"] is not None and r["left_s"] > 0 and any(covers(x, r) and x["left_s"] > r["left_s"] for x in live):
            r["renewed"] = True
    return [r for r in out if not (r["left_s"] is not None and r["left_s"] <= 0 and any(covers(x, r) for x in live))]


def delegation_text(d: dict[str, Any], project: str | None = None) -> str:
    """'DL-002 for agent:x (unblock, decide except n18) expires in 3 h 12 min', and how to renew it in its last 24 hours
    or once expired."""
    left = d["left_s"]
    span = lambda s: f"{s // 3600} h {s % 3600 // 60} min" if s >= 3600 else f"{max(1, s // 60)} min"   # noqa: E731
    limits = ", ".join(d["scope"]) + (f" on {', '.join(d['nodes'])}" if d.get("nodes") else "") + (
        f" except {', '.join(d['except_nodes'])}" if d.get("except_nodes") else "") + (
        f", {d['budget_resets']} budget reset(s)" if d.get("budget_resets") is not None else "")
    if d.get("lapsed_grantor"):
        return f"{d['id']} for {d['agent']} ({limits}) authorizes nothing: {d['by']} is no longer a named human"
    if left is None:
        return f"{d['id']} for {d['agent']} ({limits}): its expiry {d['expires']!r} cannot be read, so it authorizes nothing"
    when = f"expires in {span(left)}" if left > 0 else "expires now" if left == 0 else f"expired {span(-left)} ago"
    renew = f": ask {d['by']} to renew it (`{renew_command(d, project)}`)" if left < 86400 and not d.get("renewed") else ""
    return f"{d['id']} for {d['agent']} ({limits}) {when}{renew}"


def renew_command(d: dict[str, Any], project: str | None = None) -> str:
    """The grant again, with every limit it had: a renewal that drops `--except-nodes` hands the agent the release gate
    (config batch 5, part 2 review C1). Typed by the grantor, or by an agent transcribing their words."""
    import shlex
    q = shlex.quote
    parts = ["pdg delegate", q(project or "<project>"), f"--by {q(d['by'])}", f"--agent {q(d['agent'])}",
             f"--scope {q(','.join(d['scope']))}"]
    parts += [f"--nodes {q(','.join(d['nodes']))}"] if d.get("nodes") else []
    parts += [f"--except-nodes {q(','.join(d['except_nodes']))}"] if d.get("except_nodes") else []
    parts += [f"--budget-resets {int(d['budget_resets'])}"] if d.get("budget_resets") is not None else []
    return " ".join(parts + ["--expires", "--instruction", "--recorded-by"])


def resets_text(resets: dict[str, int] | None) -> str:
    """'3 budget reset(s) (2 by DL-001, 1 by Wei)', or '' before the first; unknown when the ledger is damaged."""
    if resets is None:
        return "budget resets unknown (the ledger is damaged)"
    return (f"{sum(resets.values())} budget reset(s) (" + ", ".join(f"{n} by {who}" for who, n in sorted(resets.items()))
            + ")") if resets else ""


class EngineAttrs:
    """The state `Engine.__init__` sets, declared once so the mixins' `self.` lookups type-check. Annotations only:
    nothing here creates an attribute or changes behaviour."""
    project: Project
    pdg_dir: Path
    workflow_path: Path
    wf: Workflow
    idx: GraphIndex
    rubrics: dict[str, dict[str, Any]]
    humans: list[str]
    rules_path: Path
    rules: RuleBase
    rule_states: dict[str, str]
    ledger: Ledger
    controls: ControlStore
    state: ProjectState
    notices: list[str]
    _undo: list[Callable[[], None]]
