"""Task packets: everything an agent needs for one attempt of one node, and the status summary.

A mixin of `Engine` (pdg/engine.py): it reads and writes the engine's own state through `self`, so it is not used
on its own."""

from __future__ import annotations

import datetime as dt
import difflib
import shlex
from typing import Any

from .context import NodeContext
from .engine_common import (DEFECT_ACTIVE, HUMAN_ONLY_ACTIONS, EngineAttrs, live_delegations, not_needed, recheck_due,
                            recheck_record, uncommitted_check_files)
from .evaluation import node_dimensions
from .executors import schema_path
from .gating import advisory_remedy, open_advisories, rechecking_reviewers
from .graph import control_reads
from .models import NodeDef, NodeKind, NodeRuntime, NodeStatus
from .util import PKG_ROOT
from .util import sha256_json


class PacketMixin(EngineAttrs):
    def lineage(self, artifact_id: str) -> list[dict[str, Any]]:
        out, seen, stack = [], set(), [artifact_id]
        while stack:
            aid = stack.pop()
            if aid in seen or aid not in self.state.artifacts:
                continue
            seen.add(aid)
            a = self.state.artifacts[aid]
            out.append({"id": a.id, "node": a.node, "sha256": a.sha256[:16], "current": a.current, "inputs": a.inputs})
            stack.extend(a.inputs)
        return out

    def status(self) -> dict[str, Any]:
        rs = self.state.runtime
        accepted = {r.assumption: r for r in self.state.history.risk_acceptances}
        risk_waits = []
        for a in self.state.research.assumptions:
            if not a.riskiest:
                continue
            ra = accepted.get(a.id)
            cur = sha256_json(a.statement)
            changed = bool(ra and ra.statement_sha256 and ra.statement_sha256 != cur)
            if not changed:
                continue
            actor = (ra.on_behalf_of or ra.actor) if ra else (self.humans[0] if self.humans else "Wei")
            risk_waits.append({"action": "accept-risk", "actor": actor, "unblocks": "N10 fidelity gate",
                               "command": f"pdg accept-risk {shlex.quote(str(self.project.root))} {a.id} "
                                          f"--actor {shlex.quote(actor)}",
                               "message": f"{a.id} changed after {actor} accepted it on {ra.at[:10]}: re-accept"})
        human = self.humans[0] if self.humans else "human"
        gate_waits = [{"action": "approve", "actor": human, "unblocks": n,
                       "command": f"pdg approve {shlex.quote(str(self.project.root))} {shlex.quote(n)} --actor "
                                  f"{shlex.quote(human)}",
                       "message": r.gate_note}
                      for n, r in rs.nodes.items() if r.status == NodeStatus.WAITING_HUMAN]
        escalation_waits = [{"action": "unblock", "actor": human, "unblocks": e.node,
                             "command": f"pdg unblock {shlex.quote(str(self.project.root))} {shlex.quote(e.node)} --actor "
                                        f"{shlex.quote(human)}",
                             "message": e.reason} for e in rs.escalations if e.open]
        from .gating import transcribed_action
        ratified = {r.target: r for r in self.state.history.ratifications}
        transcribed = []
        for e in self.ledger.events():
            data = e["data"]
            actor = data.get("actor") or data.get("by")
            rb = data.get("recorded_by")
            if transcribed_action(e["type"], data, self.humans):
                rat = ratified.get(str(e["seq"])) or ratified.get(str(data.get("id", "")))
                transcribed.append({"event": str(e["seq"]), "action": e["type"], "actor": actor, "recorded_by": rb,
                                    "source": data.get("source", ""), "interprets": data.get("interprets", False),
                                    "ratified": bool(rat and not rat.reverse), "reversed": bool(rat and rat.reverse)})
        return {
            "project": self.state.project.id, "project_root": str(self.project.root), "status": rs.status.value,
            "batches": rs.batches,
            "build_version": self.state.build.version, "rework_cycles": rs.rework_cycles,
            "budget_resets": self.budget_resets(),
            "human_only_actions": list(HUMAN_ONLY_ACTIONS),
            "delegations": live_delegations([d.model_dump(mode="json") for d in self.state.history.delegations],
                                            dt.datetime.now(dt.timezone.utc), self.humans),
            "nodes": {n: {"status": r.status.value, "outcome": r.outcome, "attempt": r.attempt, "memo_hits": r.memo_hits}
                      for n, r in rs.nodes.items()},
            "waiting_agent": [n for n, r in rs.nodes.items() if r.status == NodeStatus.WAITING_AGENT],
            "waiting_agent_details": [],
            "learning_pending": self.rt("n18_final_verification").status == NodeStatus.PASSED
            and self.rt("n19_learning_memory").status != NodeStatus.PASSED
            if "n18_final_verification" in self.idx.nodes and "n19_learning_memory" in self.idx.nodes else False,
            "not_needed": not_needed(rs.status.value, {n: r.status.value for n, r in rs.nodes.items()}),
            # the code and configuration on disk, as `pdg status` reads them: one helper, so the two never drift (W65)
            "recheck_due": recheck_due(rs.model_dump(mode="json"), self.state.build.version, self.project.root,
                                       recheck_record(self.pdg_dir)),
            "uncommitted_check_files": uncommitted_check_files(rs.model_dump(mode="json")),
            "waiting_human": [n for n, r in rs.nodes.items() if r.status == NodeStatus.WAITING_HUMAN],
            "gate_notes": {n: r.gate_note for n, r in rs.nodes.items() if r.status == NodeStatus.WAITING_HUMAN},
            "escalations": [e.model_dump() for e in rs.escalations if e.open],
            "open_defects": [d.id for d in self.state.evaluation.defects if d.status in DEFECT_ACTIVE | {"in_rework"}],
            "human_actions": risk_waits + gate_waits + escalation_waits,
            "changed_acceptances": [w for w in risk_waits if "changed after" in w["message"]],
            "transcribed_actions": transcribed,
            "ledger_events": self.ledger._last[0],
        }

    def task_packet(self, ctx: NodeContext) -> dict[str, Any]:
        node, rt = ctx.node, self.rt(ctx.node.id)
        inputs: dict[str, str] = {}
        for ref in node.inputs:
            kind, _, arg = ref.partition(":")
            if kind == "artifact":
                cur = [a for a in self.current(arg) if a.node != node.id]
                inputs[ref] = ", ".join(a.path for a in cur) or "(none yet)"
            elif kind == "control":
                inputs[ref] = f"controls/{arg}.md (v{self.state.controls[arg].version})"
            elif kind == "state":
                inputs[ref] = "see .pdg/state.json → " + arg
            else:
                inputs[ref] = ref
        rework = [d.model_dump() for d in self.state.evaluation.defects if d.id in rt.rework]
        # advisory defects traced here are never routed, so this run is the chance to fix them: listed apart, optional,
        # and never put into rework, where a failed correction would count towards escalation (field run W17)
        advisory = [d.model_dump() for d in self.state.evaluation.defects
                    if d.traced_node == node.id and d.id not in rt.rework and d.status in ("open", "persisting")
                    and d.severity not in self.wf.policies.blocking_severities]
        # at the gate: every open advisory, and whose node it waits on. The gate routes only blocking defects, so an
        # advisory whose node does not re-run in the cycle stays open (field run W54): raise it or invalidate its node
        advisories = [{**d.model_dump(include={"id", "signature", "dimension", "severity", "traced_node", "message",
                                               "smallest_fix", "acceptance_check"}),
                       "remedy": advisory_remedy(self, d, self.state.runtime.rework_cycles)}
                      for d in open_advisories(self)] if node.id == self.idx.gate_node else []
        # defects traced here still in rework, which no gate has judged yet: whatever re-opened the node, keep them
        # fixed (a pass clears the rework list, and an invalidation does not refill it; field run W21)
        in_rework = [d.model_dump() for d in self.state.evaluation.defects
                     if d.traced_node == node.id and d.status == "in_rework" and d.id not in rt.rework]
        # a reviewer re-verifies the open defects it reported: each resolves only when no current review reports its
        # signature, so it must be re-filed under that signature or not at all (field run W18)
        reverify = [{k: d.model_dump()[k] for k in ("id", "signature", "dimension", "severity", "message",
                                                    "acceptance_check", "status", "deferred", "deferred_trigger")}
                    for d in self.state.evaluation.defects
                    if d.status in ("open", "in_rework", "persisting", "needs_human") and node.id in rechecking_reviewers(self, d)] \
            if node.id in self.idx.reviewer_nodes() else []
        blocking_findings = [{"key": f"{f.node}:{f.signature}", "severity": f.severity,
                              "dimension": f.dimension, "message": f.message}
                             for f in self._current_findings()
                             if f.blocking and f.by != "tool"] if node.id == self.idx.gate_node else []
        # the regression list: a later fix can undo an earlier one, and the gate judges only open defects, so a reviewer
        # re-checks the resolved defects it found; one that fails again re-opens with its history (field run W36)
        still_fixed = [{k: d.model_dump()[k] for k in ("id", "signature", "dimension", "acceptance_check",
                                                       "resolved_at_version")}
                       for d in self.state.evaluation.defects if d.status == "resolved" and node.id in rechecking_reviewers(self, d)] \
            if node.id in self.idx.reviewer_nodes() else []
        dims = [{"id": d["id"], "name": d["name"], "level": d["level"], "check": d["check"]["type"],
                 "threshold": d.get("threshold", ""), "mode": self._mode(d)} for d in node_dimensions(node, self.rubrics)]
        outs = [{"key": o.key, "kind": o.kind, "required": o.required, "description": o.description,
                 "schema": schema_path(o.schema_name), "doc": o.doc} for o in node.outputs if not self._produced_by_hook(node, o.key)
                and not (ctx.precheck and o.key in ctx.precheck.outputs)]
        submit = (f"python -B -m pdg submit {shlex.quote(str(self.project.root))} {node.id} --token {ctx.token} "
                  f"--actor agent:{node.agent} "
                  + " ".join(f"--output {o['key']}=<path>" for o in outs if o["required"]))
        return {"node": node.id, "name": node.name, "attempt": ctx.attempt, "agent": node.agent,
                "support_agents": node.support_agents, "purpose": node.purpose, "instructions": node.instructions,
                "prompt": (PKG_ROOT / node.prompt).read_text(), "context": node.context, "skills": node.skills,
                "tools": node.tools, "inputs": inputs, "outputs": outs, "dimensions": dims,
                "controls": {"read": control_reads(node), "write": node.controls.write, "sections": node.controls.sections},
                "previous_failures": rt.failures, "rework": rework, "in_rework": in_rework, "advisory": advisory,
                "blocking_traced_here": self._blocking_traced_here(node),
                "rerun_changes": self._rerun_changes(node, rt),
                "control_locks": self._control_locks(node),
                "convergence": self._convergence_packet(node),
                "open_advisories": advisories,
                "blocking_findings": blocking_findings,
                "reverify": reverify, "still_fixed": still_fixed, "rerun": self._rerun_context(node, rt),
                "under_review": ({"version": self.state.build.version, "sha256": self.state.build.prototype.sha256,
                                  "entry": self.state.build.prototype.entry}
                                 if node.id in self.idx.reviewer_nodes() and self.state.build.prototype else None),
                "open_feedback": self._open_feedback(node), "cycle_fixes": self._cycle_fixes(node),
                "rejudge": rt.rejudge, "carried": rt.carried,
                "fidelity_gate": self._fidelity_gate_brief(node),
                "acceptance": self._acceptance_brief(node), "acceptance_owed": self._acceptance_owed(node),
                "work_dir": str(ctx.work), "token": ctx.token,
                "precheck": ctx.precheck.to_dict() if ctx.precheck else None, "submit": submit}

    def _open_feedback(self, node: NodeDef) -> list[dict[str, Any]]:
        """Every open feedback item, for a node that reads `feedback:open`: the packet alone is enough to map them all,
        where the re-run reason names only the first item that re-opened it (field run W31)."""
        if "feedback:open" not in node.inputs:
            return []
        return [{"id": f.id, "actor": f.actor, "human": f.human, "simulated": f.simulated, "at": f.at,
                 "severity": f.severity, "text": f.text} for f in self.state.evaluation.feedback if f.status == "open"]

    def _blocking_traced_here(self, node: NodeDef) -> list[dict[str, Any]]:
        return [{k: d.model_dump()[k] for k in ("id", "signature", "dimension", "severity", "message",
                                                "smallest_fix", "acceptance_check", "status")}
                for d in self.state.evaluation.defects
                if d.traced_node == node.id and d.status in DEFECT_ACTIVE | {"in_rework"}
                and d.severity in self.wf.policies.blocking_severities]

    def _rerun_changes(self, node: NodeDef, rt: NodeRuntime) -> list[dict[str, Any]]:
        if not rt.passed_attempt:
            return []
        passed = max((e["seq"] for e in self.ledger.events("node_passed")
                      if e["data"].get("node") == node.id and e["data"].get("attempt") == rt.passed_attempt), default=0)
        changes: list[dict[str, Any]] = []
        approved_cr = {cr.id for cr in self.state.history.change_requests if cr.status in ("approved", "applied")}
        for e in self.ledger.events():
            if e["seq"] <= passed:
                continue
            data = e["data"]
            if (e["type"] == "change_request" and data.get("id") in approved_cr
                    and node.id in data.get("reruns", [])):
                doc = data.get("doc", "")
                changes.append({"id": data.get("id", f"ledger:{e['seq']}"), "kind": "change_request",
                                "reason": data.get("reason", ""), "doc": doc, "seq": e["seq"],
                                "unapplied_to_own_document": doc in node.controls.write})
            elif e["type"] == "human_invalidated" and node.id in data.get("touched", data.get("targets", [])):
                changes.append({"id": f"ledger:{e['seq']}", "kind": "invalidation",
                                "reason": data.get("reason", ""), "doc": "", "seq": e["seq"],
                                "unapplied_to_own_document": False})
        return sorted(changes, key=lambda c: c["seq"])

    def _control_locks(self, node: NodeDef) -> list[dict[str, str]]:
        docs = self.controls.needs_change_request(node.id, node.controls.write)
        return [{"doc": d, "locked_by": self.state.controls[d].locked_by or "",
                 "command": f"pdg change-request {shlex.quote(str(self.project.root))} --doc {d} --writer {node.id} "
                            "--actor <human> --reason \"…\""} for d in docs]

    def _convergence_packet(self, node: NodeDef) -> dict[str, Any] | None:
        if node.id != self.idx.gate_node:
            return None
        trend = [len(g.blocking_defects) for g in self.state.evaluation.gates]
        groups: dict[str, list[str]] = {}
        for d in self.state.evaluation.defects:
            if d.status not in DEFECT_ACTIVE | {"in_rework"}:
                continue
            loc = d.signature.split("@", 1)[1].split("#", 1)[0] if "@" in d.signature else d.signature
            component = loc.split(":", 1)[0]
            if component and len(d.history) > 1:
                groups.setdefault(component, []).append(d.id)
        recurring = [{"component": k, "defects": sorted(v)} for k, v in sorted(groups.items())]
        return {"trend": trend, "recurring": recurring}

    def _fidelity_gate_brief(self, node: NodeDef) -> list[dict[str, Any]] | None:
        """For the node judged by PLN-FIDELITY-GATE: each riskiest assumption and who, if anyone, accepted it as a risk.
        At mid or high fidelity an unvalidated one needs a named human's `accept-risk` first, and an agent should learn
        that before it spends an attempt (field run 2, R2-03)."""
        if not any(d["id"] == "PLN-FIDELITY-GATE" for d in node_dimensions(node, self.rubrics)):
            return None
        from .tools.plan import _human_acceptance
        return [{"id": a.id, "statement": a.statement, "accepted_by": _human_acceptance(self.state, a.id, self.humans)}
                for a in self.state.research.assumptions if a.riskiest]

    def _acceptance_brief(self, node: NodeDef) -> dict[str, Any] | None:
        """For the node judged by PLN-ACCEPTANCE: every P0 and P1 acceptance line, verbatim, and the checks `covered_by`
        may name, so the plan can trace them without reading N04's output (batch 8b review C1)."""
        if not any(d["id"] == "PLN-ACCEPTANCE" for d in node_dimensions(node, self.rubrics)):
            return None
        from .tools.plan import acceptance_checks, acceptance_lines
        return {"lines": acceptance_lines(self.state.product.requirements),
                "checks": acceptance_checks(self.idx, self.rubrics, node.id)}

    def _acceptance_owed(self, node: NodeDef) -> list[dict[str, str]]:
        """For a node whose check the plan named as covering an acceptance line: those lines, so a reviewer scores its
        dimension with them in mind; the trace is otherwise a claim nobody reads (batch 8b review I2)."""
        plan = self.state.build.plan
        mine = {d["id"] for d in node_dimensions(node, self.rubrics)}
        return [{"requirement": t.requirement, "acceptance": t.acceptance, "check": t.covered_by}
                for t in (plan.acceptance_trace if plan else []) if t.covered_by in mine]

    def _cycle_fixes(self, node: NodeDef) -> list[dict[str, Any]]:
        """The current rework cycle's defects, for a node that re-runs inside the cycle without being one of its targets.
        Their fixes can change what this node's own work asserts: the plan's scenarios bind copy and states, so a fix
        that renames a label makes an expectation stale, and a failing scenario is blamed on the build (backlog N-19)."""
        gates = self.state.evaluation.gates
        if (not gates or gates[-1].outcome != "rework" or node.id in gates[-1].targets
                or node.kind in (NodeKind.REVIEW, NodeKind.GATE) or not self.rt(node.id).passed_attempt):
            return []
        return [{k: d.model_dump()[k] for k in ("id", "signature", "traced_node", "severity", "message", "smallest_fix",
                                                "acceptance_check")}
                for d in self.state.evaluation.defects if d.id in gates[-1].blocking_defects and d.status == "in_rework"]

    def _rerun_context(self, node: NodeDef, rt: NodeRuntime) -> dict[str, Any] | None:
        """For a node that passed before and runs again: why, which of its inputs changed since that pass (a control
        document with its diff), and what it submitted then, so the agent can tell whether its own work must change."""
        mine = [a for a in self.state.artifacts.values() if a.node == node.id]
        # the passing attempt's records: `current` is not enough, since two nodes' copies of a shared control document
        # share an output key and the later one un-marks the earlier (states from before passed_attempt fall back to it)
        last = sorted((a for a in mine if (a.attempt == rt.passed_attempt if rt.passed_attempt else a.current)),
                      key=lambda a: a.key)
        if not last:
            return None
        read: dict[str, set[str]] = {}
        for aid in {i for a in last for i in a.inputs}:
            if aid in self.state.artifacts:
                read.setdefault(self.state.artifacts[aid].key, set()).add(aid)
        changed: list[dict[str, Any]] = []
        for ref in node.inputs:
            kind, _, key = ref.partition(":")
            if kind != "artifact" or key not in read:
                continue
            was = [self.state.artifacts[i] for i in sorted(read[key])]
            now_ = [a for a in self.current(key) if a.node != node.id]
            if {a.sha256 for a in was} != {a.sha256 for a in now_}:
                changed.append({"input": ref, "was": ", ".join(a.path for a in was),
                                "now": ", ".join(a.path for a in now_) or "(none)"})
        for doc, version in sorted((rt.passed_controls or self._legacy_passed_controls(node)).items()):
            rec = self.state.controls.get(doc)
            if rec is not None and rec.version != version:
                changed.append({"input": f"control:{doc}", "was": f"v{version}", "now": f"v{rec.version}",
                                "diff": self._control_diff(doc, version)})
        return {"reason": rt.rerun_reason, "changed_inputs": changed,
                "last_passed": {"attempt": max(a.attempt for a in last), "outputs": {a.key: a.path for a in last}}}

    def _legacy_passed_controls(self, node: NodeDef) -> dict[str, int]:
        """For a pass saved before pdg recorded `passed_controls`: the control versions installed before the node's last
        `node_passed` event. The ledger orders both exactly, where one-second timestamps could not (field run W15)."""
        passed = [e["seq"] for e in self.ledger.events("node_passed") if e["data"].get("node") == node.id]
        if not passed:
            return {}
        docs = set(control_reads(node)) | set(node.controls.write)
        seen: dict[str, int] = {}
        for e in self.ledger.events("control_installed"):
            if e["seq"] < passed[-1] and e["data"].get("doc") in docs:
                seen[e["data"]["doc"]] = int(e["data"]["version"])
        return seen

    def _control_diff(self, doc: str, version: int, limit: int = 80) -> list[str]:
        rec = self.state.controls[doc]
        old = next((v for v in rec.history if v.version == version), None)
        if old is None or not (self.project.root / old.archived).is_file():
            return []
        diff = list(difflib.unified_diff((self.project.root / old.archived).read_text().splitlines(),
                                         self.controls.accepted_text(doc).splitlines(),
                                         f"{doc}.md v{version}", f"{doc}.md v{rec.version}", n=1, lineterm=""))
        return diff[:limit] + ([f"… {len(diff) - limit} more diff lines"] if len(diff) > limit else [])

    def _mode(self, dim: dict[str, Any]) -> str:
        from .evaluation import mode_for
        return mode_for(dim, self.rule_states)
