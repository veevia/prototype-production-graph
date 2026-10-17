"""Configuration and code provenance: drift, accept-config, re-judging and parked submissions (field run W42, W43; backlog
B-03).

A mixin of `Engine` (pdg/engine.py): it reads and writes the engine's own state through `self`, so it is not used
on its own."""

from __future__ import annotations

import json
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from .context import NodeContext
from .engine_common import (EngineAttrs, EngineError, checks_now, config_files, package_code_parts, package_git_state,
                            release_checks)
from .evaluation import can_fail, evaluate_tool_dims, node_dimensions
from .human_recording import recording, stamp, validate_human_words
from .memory import RuleBase
from .models import NodeDef, NodeKind, NodeStatus, RunStatus
from .util import PKG_ROOT, now, rel, sha256_file, sha256_json, write_json_atomic


class ConfigMixin(EngineAttrs):
    def _config_fingerprint(self) -> str:
        parts = {"workflow": sha256_file(self.workflow_path), "rules": sha256_file(self.rules_path),
                 "defaults": sha256_file(PKG_ROOT / "config" / "defaults.yaml"),
                 "rubrics": {p.name: sha256_file(p) for p in sorted((PKG_ROOT / "rubrics").glob("*.yaml"))}}
        cfg = self.project.root / "pdg.project.yaml"
        if cfg.exists():
            parts["project"] = sha256_file(cfg)
        return sha256_json(parts)

    def _config_files(self) -> dict[str, str]:
        """The files behind the fingerprint, by path, so a drift can say which one changed."""
        return config_files(self.project.root, self.workflow_path, self.rules_path)

    def _config_drift(self) -> tuple[list[str], str]:
        """(changed paths, a sentence naming them) between the accepted configuration and the files on disk."""
        was, now_ = self.state.runtime.config_parts, self._config_files()
        if not was:
            return [], "which file is unknown: this run started before pdg recorded per-file hashes"
        changed = sorted(k for k in was.keys() & now_.keys() if was[k] != now_[k])
        added, removed = sorted(now_.keys() - was.keys()), sorted(was.keys() - now_.keys())
        parts = [f"{verb} {', '.join(paths)}" for verb, paths in (("changed", changed), ("added", added),
                                                                   ("removed", removed)) if paths]
        return changed + added + removed, "; ".join(parts) or "no file differs, only how the fingerprint is computed"

    def _note_code_change(self) -> None:
        """Record in the ledger when the package's code changed under the run. Unlike the configuration it does not
        block: a fix to a check can change a verdict, and the ledger then says which code judged which attempt."""
        parts = package_code_parts(PKG_ROOT)
        rs = self.state.runtime
        if parts == rs.code_parts:
            return
        git_state = package_git_state(PKG_ROOT)
        if rs.code_parts:
            changed = sorted(k for k in parts.keys() | rs.code_parts.keys() if parts.get(k) != rs.code_parts.get(k))
            self.ledger.append("code_updated", changed=changed, sha256=sha256_json(parts), git_state=git_state)
        else:   # the first time this run sees pdg's code: which code judges from here on (batch 7 review S4)
            self.ledger.append("code_recorded", files=len(parts), sha256=sha256_json(parts), git_state=git_state)
        rs.code_parts = parts

    def config_impact(self) -> dict[str, Any]:
        """What accepting the configuration on disk would do, changing nothing: the files that changed, the nodes it
        re-judges, every node it withdraws (those and their descendants), and which of those are out with an agent or
        hold a parked submission (`pdg accept-config --dry-run`; field run W42)."""
        changed = self._config_drift()[0]
        saved = self.rule_states
        self.rule_states = RuleBase(self.rules_path, humans=self.humans).states()
        try:
            rejudge = self._rejudge_after_config(changed)
        finally:
            self.rule_states = saved
        touched = self.idx.order(set(rejudge) | {d for n in rejudge for d in self.idx.descendants(n)
                                                 if self.rt(d).status != NodeStatus.PLANNED})
        return {"changed": changed, "rejudge": rejudge, "withdrawn": touched,
                "in_flight": [n for n in touched if self.rt(n).status == NodeStatus.WAITING_AGENT and not self.rt(n).parked],
                "parked": [n for n in self.idx.order([x.id for x in self.wf.nodes]) if self.rt(n).parked],
                "parked_fate": {n: (self.parked_fate(n) if n in touched else "kept: resubmit the same command after the accept")
                                for n in self.idx.order([x.id for x in self.wf.nodes]) if self.rt(n).parked}}

    def accept_config(self, actor: str, reason: str, on_behalf_of: str | None = None,
                      discard_in_flight: bool = False, recorded_by: str | None = None,
                      source: str = "", interprets: bool = False) -> dict[str, Any]:
        reason = validate_human_words(reason, "configuration acceptance reason")
        rec = recording(actor, recorded_by, source)
        human, behalf, delegation = self._authority(actor, "accept_config", None, on_behalf_of)
        impact = self.config_impact()
        if impact["in_flight"] and not discard_in_flight:
            raise EngineError(f"accepting would withdraw work still out with an agent: {', '.join(impact['in_flight'])}. "
                              "Have each submit first: while the run is blocked a submission is parked, and on accept a "
                              "review's findings are recorded as feedback and any other output is handed to the node's "
                              "next attempt. Or pass --discard-in-flight")
        with self._action("config_accepted", stamp(rec, interprets)):
            old = self.state.runtime.config_sha256
            changed = impact["changed"]
            self.rules = RuleBase(self.rules_path, humans=self.humans)
            self.rule_states = self.rules.states()
            self.state.runtime.config_sha256 = self._config_fingerprint()
            self.state.runtime.config_parts = self._config_files()
            self.state.knowledge = self._knowledge_ref()
            for e in self.state.runtime.escalations:
                if e.open and e.node == "run" and e.reason.startswith("integrity"):
                    e.open, e.resolved_by, e.resolved_at = False, actor, now()
            rejudge = self._rejudge_after_config(changed)
            for n in self.wf.nodes:   # the rest stands under the accepted configuration: record it, so the next accept is exact
                if n.id not in rejudge and self.rt(n.id).status in (NodeStatus.PASSED, NodeStatus.WAITING_HUMAN):
                    self.rt(n.id).passed_judging = self.judging_hash(n)
                    self.rt(n.id).passed_dims = self._dim_signatures(n)
            recorded = self._resolve_parked(impact["withdrawn"], "configuration accepted")
            for n in rejudge:      # its packet says what changed and what its last passed output now fails (W43)
                self.rt(n).rejudge = self._rejudge_context(self.node(n), changed)
            if rejudge:   # a verdict made under the old rubric, threshold or rule state no longer stands (backlog B-03)
                self.invalidate(rejudge, f"configuration accepted: {', '.join(changed) or 'the judging'} changed how it "
                                         "is judged", force=True)
            self.ledger.append("config_accepted", actor=actor, human=human, on_behalf_of=behalf, delegation=delegation,
                               reason=reason, old=old, new=self.state.runtime.config_sha256, changed=changed,
                               rejudged=rejudge, discarded=impact["in_flight"] if discard_in_flight else [],
                               parked_findings=recorded, **rec, interprets=interprets)
            self.state.runtime.status = RunStatus.RUNNING
            self._update_status()
            self.save("config_accepted")
        return {"config_sha256": self.state.runtime.config_sha256, "rejudged": rejudge, "parked_findings": recorded}

    def _dim_signatures(self, node: NodeDef) -> list[str]:
        return sorted(f"{d['id']}|{d['level']}|{d.get('check', {}).get('type')}|{d.get('threshold', '')}"
                      for d in node_dimensions(node, self.rubrics))

    def _path_sha(self, p: Path) -> str | None:
        return self._file_sha(p) if p.is_file() else self._tree_sha(p) if p.is_dir() else None

    def parked_fate(self, nid: str) -> str:
        """What resolving a parked submission would do with it, before its node is withdrawn (W42; review I1)."""
        p = self.rt(nid).parked or {}
        edited = [k for k, h in (p.get("sha256") or {}).items() if self._path_sha(Path(p["outputs"][k])) != h]
        if edited:
            return f"edited after parking ({', '.join(sorted(edited))}): discarded, resubmit"
        if nid in self.idx.reviewer_nodes() and p.get("build_version") == self.state.build.version:
            return "findings recorded as feedback"
        return "outputs handed to its next attempt"

    def _resolve_parked(self, nids: list[str], why: str) -> dict[str, list[str]]:
        """Before a node with a parked submission is withdrawn (a re-judge, an invalidation), nothing it did is lost
        silently (W42; review I1, I2). A review of the current build is evidence about the build, so each agent finding
        becomes feedback on record; any other output is handed to the node's next attempt, whose packet lists it; an
        output edited after parking is neither. The ledger says which."""
        out: dict[str, list[str]] = {}
        for nid in nids:
            rt = self.rt(nid)
            if not rt.parked:
                continue
            node, fate = self.node(nid), self.parked_fate(nid)
            if fate == "findings recorded as feedback":
                ids = []
                for f, simulated in self._parked_findings(node, rt.parked["outputs"]):
                    loc = f.get("location", "") + (f"#{f['element']}" if f.get("element") else "")
                    text = (f"[parked review by {nid} a{rt.attempt}, build v{self.state.build.version}] "
                            f"{f.get('dimension')}@{loc}: {f.get('message', '')} (severity {f.get('severity', '?')}"
                            + (f"; fix: {f['smallest_fix']}" if f.get("smallest_fix") else "")
                            + (f"; fixed when: {f['acceptance_check']}" if f.get("acceptance_check") else "") + ")")
                    ids.append(self.add_feedback(text, f"agent:{node.agent}", loc, f.get("severity", ""),
                                                 simulated=simulated, human=False, reopen=False).id)
                out[nid] = ids
            elif fate == "outputs handed to its next attempt":
                rt.carried = {"attempt": rt.attempt, "at": rt.parked["at"], "why": why,
                              "outputs": {k: rel(Path(v), self.project.root) for k, v in rt.parked["outputs"].items()}}
            self.ledger.append("parked_resolved", node=nid, reason=why, fate=fate, recorded_as_feedback=out.get(nid, []),
                               carried=fate == "outputs handed to its next attempt", discarded=fate.startswith("edited"))
            rt.parked = None
        return out

    def _parked_findings(self, node: NodeDef, outputs: dict[str, str]) -> list[tuple[dict[str, Any], bool]]:
        found: list[tuple[dict[str, Any], bool]] = []
        for o in node.outputs:
            p = Path(outputs.get(o.key, ""))
            if o.schema_name not in ("review", "validation") or not p.is_file():
                continue
            try:
                doc = json.loads(p.read_text())
            except ValueError:
                continue
            simulated = {s.get("participant") for s in doc.get("sessions", []) if s.get("simulated")}
            found += [(f, f.get("participant") in simulated) for f in doc.get("findings", [])
                      if isinstance(f, dict) and f.get("by", "agent") != "tool"]
        seen, out = set(), []
        for f, sim in found:   # a finding in both of N14's outputs is recorded once (W33)
            key = (f.get("dimension"), f.get("location", ""), f.get("element", ""))
            if key not in seen:
                seen.add(key)
                out.append((f, sim))
        return out

    def _rejudge_context(self, node: NodeDef, changed: list[str]) -> dict[str, Any]:
        """For a node re-judged by accept-config: the dimensions new or changed since it passed, and what its last
        passed output now fails on the tool checks that can be re-run here (the browser suite runs after it submits)."""
        rt = self.rt(node.id)
        now_dims = self._dim_signatures(node)
        was = set(rt.passed_dims)
        dims = [s for s in now_dims if s not in was] if was else [
            s for s in now_dims if any(f"rubrics/{r}.yaml" in changed for r in node.evaluation)]
        return {"changed": changed, "dims": [s.replace("|", " · ") for s in dims], "last_pass": self._recheck_last_pass(node),
                "passed_attempt": rt.passed_attempt, "rechecked": self._recheck_fns(node)}

    def _recheck_fns(self, node: NodeDef, browser: bool = False) -> list[str]:
        """The tool checks that can be re-run on a node's last passed output: no browser suite unless asked (a static
        check may still render a few routes, as BLD-SCREENS does for screens its text scan misses), and never a gate's
        hook, which decides on the live state (resolves defects, records a gate) instead of checking an output (review C1)."""
        if node.kind == NodeKind.GATE or not self.rt(node.id).passed_attempt:
            return []
        return sorted({d["check"]["fn"] for d in node_dimensions(node, self.rubrics)
                       if d.get("check", {}).get("type") == "tool"
                       and (browser or not d["check"].get("fn", "").startswith("browser:"))})

    def _recheck_last_pass(self, node: NodeDef, browser: bool = False, work: Path | None = None) -> list[dict[str, Any]]:
        """What a node's last passed output fails on its tool checks now, changing nothing in the run. `work` keeps what
        the checks write (a browser report, its screenshots)."""
        rt = self.rt(node.id)
        mine = {a.key: self.project.root / a.path for a in self.state.artifacts.values()
                if a.node == node.id and a.attempt == rt.passed_attempt and a.superseded_by != "failed-attempt"}
        fns = self._recheck_fns(node, browser)
        if not mine or not fns:
            return []
        out: list[dict[str, Any]] = []
        saved = self.state.model_copy(deep=True)
        if work is not None:
            work.mkdir(parents=True, exist_ok=True)
        try:
            with (nullcontext(str(work)) if work is not None else tempfile.TemporaryDirectory(prefix="pdg-rejudge-")) as tmp:
                ctx = NodeContext(self, node, rt.passed_attempt, Path(tmp), "", "")
                ctx.submitted = mine
                results = {fn: self._call_tool(fn, ctx) for fn in fns}
        finally:
            self.state = saved   # a check that writes to the run's state changes nothing here
        for fn, res in results.items():
            # a check that could not run gives no verdict: a missing browser (`blocked`) or one that raised (`_call_tool`)
            out += [{"dim": fn, "passed": False, "evidence": e, "not_run": bool(res.data.get("blocked"))
                     or e.startswith((f"{fn} raised ", f"{fn} returned "))} for e in res.errors]
        records, _, _ = evaluate_tool_dims(node, results, self.rubrics, self.rule_states)
        out += [{"dim": r.id, "passed": False, "evidence": r.evidence, "level": r.level} for r in records
                if r.status in ("fail", "advisory_fail")]
        return out

    def recheck_release(self, out: Path) -> dict[str, Any]:
        """Re-run every passed node's tool checks, the browser suite included, on its released outputs, with the code and
        configuration on disk, changing nothing in the run. A check upgrade that lands after a release never sees it
        otherwise: a hand-run found that the first field run's released v15 hid a decision-driving score at every width
        up to 1210 px, which 16 review rounds had missed (W65). A failure, a rubric dimension's or a check's own error,
        says whether it would block; a check that could not run at all (a missing browser, or one that raised) is listed
        apart. Filing a failure as feedback, which re-opens the release, stays a person's action."""
        rs = self.state.runtime
        if rs.status != RunStatus.RUN_PASS:
            raise EngineError(f"nothing released to re-check: the run is {rs.status.value}")
        out = out.resolve()
        allowed_project_out = out == self.pdg_dir / "release-recheck" or self.pdg_dir / "release-recheck" in out.parents
        if (out == self.project.root or self.project.root in out.parents) and not allowed_project_out:
            raise EngineError(f"--out {out} is inside the project; choose .pdg/release-recheck or a folder outside it")
        if out.exists() and any(out.iterdir()):
            raise EngineError(f"--out {out} already holds files; choose a new folder")
        out.mkdir(parents=True, exist_ok=True)
        dims = {d["id"]: d for n in self.wf.nodes for d in node_dimensions(n, self.rubrics)}
        started, judged = checks_now(self.project.root), release_checks(self.state)
        rows, not_run, checked = [], [], []
        for node in self.wf.nodes:
            fns = self._recheck_fns(node, browser=True)
            if not fns or self.rt(node.id).status != NodeStatus.PASSED:   # a stale node is not in the release
                continue
            checked.append({"node": node.id, "checks": fns})
            for r in self._recheck_last_pass(node, browser=True, work=out / node.id):
                d = dims.get(r["dim"])
                if r.get("not_run"):
                    not_run.append({"node": node.id, "check": r["dim"], "why": r["evidence"]})
                else:   # a check's own error fails an attempt, as it does at submission (engine: errors are failures)
                    rows.append({"node": node.id, **r, "blocks": can_fail(d, self.rule_states) if d else True})
        report = {"build_version": self.state.build.version, "checked_with": started, "judged_by": judged,
                  "checked": checked, "failures": rows, "not_run": not_run, "at": now()}
        (out / "recheck-release.json").write_text(json.dumps(report, indent=1))
        return report

    def record_recheck(self, report: dict[str, Any]) -> None:
        """What `pdg status` reads to settle or sharpen its re-check hint; not the run's state, not its ledger (W65)."""
        write_json_atomic(self.pdg_dir / "release-recheck.json", {
            "build_version": report["build_version"], "checked_with": report["checked_with"], "at": report["at"],
            "failing": len(report["failures"]), "blocking": sum(1 for r in report["failures"] if r["blocks"]),
            "not_run": len(report["not_run"])})

    def decline_recheck(self, actor: str, reason: str, on_behalf_of: str | None = None,
                        recorded_by: str | None = None, source: str = "", interprets: bool = False) -> dict[str, Any]:
        """A person decides not to re-open the release on what the last re-check found: a decision on record, so the
        status hint stops asking (batch 19 review 2)."""
        from .engine_common import recheck_record
        record = recheck_record(self.pdg_dir)
        if not record or record.get("checked_with") != checks_now(self.project.root) \
                or record.get("build_version") != self.state.build.version:
            raise EngineError("no re-check with the current checks on this build to decline: run `pdg recheck-release` first")
        if not reason.strip():
            raise EngineError("declining needs a reason")
        reason = validate_human_words(reason, "recheck decline reason")
        rec = recording(actor, recorded_by, source)
        if record.get("not_run"):   # the W65 case itself: a suite that never ran on the release is no finding to decline
            raise EngineError(f"{record['not_run']} check(s) did not run on the release: make them run and re-check; a "
                              "decline covers findings, not checks never made")
        # a person's decision, never delegated: a grant to approve gates does not cover it (batch 19 review 3, I2)
        human, _, _ = self._authority(actor, "decline_recheck", None, on_behalf_of)
        declined = {"by": actor, "reason": reason.strip(), "at": now()}
        with self._action("recheck_declined", stamp(rec, interprets)):
            self.ledger.append("recheck_declined", build_version=record["build_version"], blocking=record["blocking"],
                               not_run=record["not_run"], reason=reason, actor=actor, human=human,
                               **rec, interprets=interprets)
            self.save("recheck_declined")
        # only once the decision is committed: a failed save leaves the hint asking (batch 19 review 3, I3)
        write_json_atomic(self.pdg_dir / "release-recheck.json", {**record, "declined": declined})
        return {"declined": declined}

    def _rejudge_after_config(self, changed: list[str]) -> list[str]:
        """Nodes whose verdict the accepted configuration changes. A node judged since pdg recorded it compares its
        judging hash; one judged before falls back to its rubric files. A node out with an agent has a packet built on
        the old dimensions, so it is re-issued when what judges it changed since its last pass (a review threshold, a rule
        state, a dimension that can fail it): tool checks run at submission anyway. The first run's N13 was out with its
        reviewer when a batch added two SHOULD tool dimensions, and re-issuing it would have cost a review round."""
        out = []
        for n in self.wf.nodes:
            rt = self.rt(n.id)
            rubric_changed = any(f"rubrics/{r}.yaml" in changed for r in n.evaluation)
            # a node out with an agent: against the judging its packet was issued under (older packets: its last pass)
            issued = rt.status == NodeStatus.WAITING_AGENT and rt.issued_judging
            base, dims = (rt.issued_judging, rt.issued_dims) if issued else (rt.passed_judging, rt.passed_dims)
            if rt.status in (NodeStatus.PASSED, NodeStatus.WAITING_HUMAN, NodeStatus.WAITING_AGENT) and base:
                # a dimension added since then that cannot fail it (SHOULD, or its rule not enforced) leaves the verdict
                # standing: a configuration batch that adds one would otherwise withdraw the node and all it fed, a
                # rebuild for an advisory line (config batch 5 dry run: N09, N10 and N13 and their descendants)
                had = {sig.split("|", 1)[0] for sig in dims}
                cannot_fail = frozenset(d["id"] for d in node_dimensions(n, self.rubrics) if had and d["id"] not in had
                                        and not can_fail(d, self.rule_states))
                if base != self.judging_hash(n, cannot_fail):
                    out.append(n.id)
            elif rt.status in (NodeStatus.PASSED, NodeStatus.WAITING_HUMAN, NodeStatus.WAITING_AGENT) and rubric_changed:
                out.append(n.id)
        return out
