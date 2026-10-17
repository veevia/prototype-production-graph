"""What a named human (or a delegate) does to a run: delegations, gate decisions, feedback, deferrals, check corrections,
change requests, unblocks, waivers, risk acceptance, invalidation, rollback and archiving.

A mixin of `Engine` (pdg/engine.py): it reads and writes the engine's own state through `self`, so it is not used
on its own."""

from __future__ import annotations

import datetime as dt
import json
import re
import shlex
import shutil
from pathlib import Path
from typing import Any

from .engine_common import ACTIVE, DEFECT_ACTIVE, DELEGABLE_ACTIONS, EngineAttrs, EngineError
from .engine_common import budget_resets as count_resets
from .gating import fix_marker
from .human_recording import recording, stamp, validate_human_words
from .models import (Approval, ChangeRequest, Decision, Delegation, EdgeKind, Feedback, GapWaiver, NodeStatus,
                     ProjectState, Ratification, RiskAcceptance, RunStatus)
from .util import now, read_json, rel, sha256_file, sha256_json, write_json_atomic


class HumanActionsMixin(EngineAttrs):
    def delegate(self, by: str, agent: str, instruction: str, scope: list[str], nodes: list[str] | None,
                 expires: str, recorded_by: str | None = None, source: str = "",
                 except_nodes: list[str] | None = None, budget_resets: int | None = None,
                 include_release: bool = False) -> Delegation:
        if not self.is_human(by):
            raise EngineError(f"only a named human ({', '.join(self.humans)}) can delegate; '{by}' is not one")
        if recorded_by is not None and recorded_by != by and not recorded_by.startswith("agent:"):
            raise EngineError(f"recorded_by is whoever typed the grant: {by} themself, or the agent transcribing their "
                              f"words (agent:<role>); '{recorded_by}' is neither")
        instruction = validate_human_words(instruction, "delegation instruction")
        if not agent.startswith("agent:"):
            raise EngineError("delegation agent must start with 'agent:'")
        if not scope:
            raise EngineError("delegation scope must list at least one action")
        bad = [s for s in scope if s not in DELEGABLE_ACTIONS]
        if bad:
            raise EngineError(f"delegation scope contains unknown action(s): {', '.join(bad)}")
        node_ids = list(nodes or [])
        for nid in node_ids:
            node = self.node(nid)
            if not node.human_review.required:
                raise EngineError(f"{nid} is not a human gate")
        # a node list can name only gates, and only `decide` acts on a gate: an unblock names the escalated node (n16,
        # n17), a change request its writer. So a node-scoped unblock could never apply (field run 2, R2-01)
        unbound = [s for s in scope if s != "decide"]
        if node_ids and unbound:
            raise EngineError(f"--nodes scopes `decide` only, but the scope also lists {', '.join(unbound)}, which act on "
                              "nodes that are not gates. Grant those in a second delegation without --nodes, or limit this "
                              "one with --except-nodes (for example --except-nodes n18_final_verification)")
        except_ids = list(except_nodes or [])
        for nid in except_ids:
            self.node(nid)
        if node_ids and except_ids:
            raise EngineError("use --nodes or --except-nodes, not both")
        if budget_resets is not None and (budget_resets < 0 or "unblock" not in scope):
            raise EngineError("--budget-resets is a count (0 or more) of the resets an `unblock` under this grant may make, "
                              "so the scope must include unblock")
        release = "n18_final_verification"
        covers_release = "decide" in scope and (release in node_ids or (not node_ids and release not in except_ids))
        if covers_release and not include_release:
            raise EngineError("a delegation whose decide scope covers n18_final_verification needs --include-release")
        if include_release and recorded_by and recorded_by.startswith("agent:"):
            raise EngineError("--include-release grants must be typed by the named human, not transcribed by an agent")
        if self._parse_time(expires, "delegation expiry") <= dt.datetime.now(dt.timezone.utc):
            raise EngineError("delegation expiry must be in the future")
        rec = recording(by, recorded_by, source)
        with self._action("delegation_granted", stamp(rec)):
            delegation = Delegation(id=f"DL-{len(self.state.history.delegations) + 1:03d}", by=by,
                                    instruction=instruction, scope=list(scope), nodes=node_ids,
                                    except_nodes=except_ids, agent=agent,
                                    created=now(), expires=expires, **rec,
                                    budget_resets=budget_resets, include_release=include_release)
            self.state.history.delegations.append(delegation)
            self.ledger.append("delegation_granted", **delegation.model_dump(mode="json"))
            self.save("delegation_granted")
        return delegation

    def revoke_delegation(self, id: str, by: str, recorded_by: str | None = None,
                          source: str = "", interprets: bool = False) -> Delegation:
        if not self.is_human(by):
            raise EngineError(f"only a named human ({', '.join(self.humans)}) can revoke delegation; '{by}' is not one")
        delegation = next((d for d in self.state.history.delegations if d.id == id), None)
        if delegation is None:
            raise EngineError(f"unknown delegation {id}")
        if delegation.revoked_at:
            raise EngineError(f"{id} was already revoked")
        rec = recording(by, recorded_by, source)
        with self._action("delegation_revoked", stamp(rec, interprets)):
            delegation.revoked_at = now()
            delegation.revoked_by = by
            self.ledger.append("delegation_revoked", id=id, by=by, revoked_at=delegation.revoked_at,
                               granted_by=delegation.by, agent=delegation.agent, **rec, interprets=interprets)
            self.save("delegation_revoked")
        return delegation

    def decide(self, node_id: str, decision: str, actor: str, reason: str = "", feedback: list[str] | None = None,
               on_behalf_of: str | None = None, _auto: bool = False, recorded_by: str | None = None,
               source: str = "", interprets: bool = False) -> dict[str, Any]:
        node, rt = self.node(node_id), self.rt(node_id)
        if rt.status != NodeStatus.WAITING_HUMAN:
            raise EngineError(f"{node_id} is {rt.status.value}, not waiting for a human decision")
        if decision not in node.human_review.outcomes:
            raise EngineError(f"'{decision}' is not a decision at {node_id} (choose: {', '.join(node.human_review.outcomes)})")
        if _auto and actor == self.wf.policies.dry_run_actor and self.project.dry_run:
            human, behalf, delegation = False, None, None
        else:
            human, behalf, delegation = self._authority(actor, "decide", node_id, on_behalf_of)
        if not human and not delegation and not (_auto and actor == self.wf.policies.dry_run_actor and self.project.dry_run):
            raise EngineError(f"only a named human ({', '.join(self.humans)}) decides at {node_id}; '{actor}' is not one")
        if not _auto:
            if not reason.strip():
                raise EngineError("a decision needs a reason (the approver's words)")
            reason = validate_human_words(reason, "decision reason")
        rec = recording(actor, recorded_by, source)
        with self._action("decision", stamp(rec, interprets)):
            locked: list[str] = []
            if decision == "approved":
                locked = self.controls.lock(sorted(node.controls.lock_on_approval), node_id, actor)
                relock = [d for d, r in self.state.controls.items() if r.unlocked_for == node_id and d not in locked]
                locked += self.controls.relock(relock, node_id, actor)
            fb_ids = [self.add_feedback(t, actor, at=node_id, human=human, reopen=False).id for t in (feedback or [])]
            ev = self.ledger.append("decision", node=node_id, decision=decision, actor=actor, human=human,
                                    on_behalf_of=behalf, delegation=delegation, reason=reason, locked=locked,
                                    feedback=fb_ids, **rec, interprets=interprets)
            ap = Approval(node=node_id, decision=decision, actor=actor, human=human, on_behalf_of=behalf,
                          delegation=delegation, reason=reason, at=now(), build_version=self.state.build.version,
                          locked=locked, outputs=self._gate_outputs(node), **rec, interprets=interprets)
            self.state.history.approvals.append(ap)
            light = "green" if decision == "approved" else "red"
            self.state.history.decisions.append(Decision(
                id=f"D-{len(self.state.history.decisions) + 1:03d}", node=node_id, what=node.human_review.decision,
                light=light, owner=actor, rationale=reason, evidence=[f"ledger:{ev['seq']}"], at=now()))
            context = None
            if decision != "approved":
                context = [f"{actor} {decision} at {node_id}: {reason}"] + [f"feedback: {t}" for t in (feedback or [])]
            self._pass(node, rt, decision, {"decision": decision, "actor": actor, "human": human, "context": context})
            self._update_status()
            self.save("decision")
        if node_id == "n18_final_verification" and decision == "approved":
            try:
                self.release_shelf()
            except (OSError, ValueError, shutil.Error) as exc:
                self.notices.insert(0, f"release shelf rebuild failed after approval ({exc}); run `pdg release-shelf "
                                       f"{shlex.quote(str(self.project.root))}` after restoring any archived packages")
        return {"node": node_id, "decision": decision, "actor": actor, "human": human, "on_behalf_of": behalf,
                "delegation": delegation, "locked": locked}

    def add_feedback(self, text: str, actor: str, at: str = "", severity: str = "", simulated: bool = False,
                     human: bool | None = None, reopen: bool = True, recorded_by: str | None = None,
                     source: str = "", interprets: bool = False) -> Feedback:
        if not text.strip():
            raise EngineError("feedback text is empty")
        human = self.is_human(actor) if human is None else human
        rec = {} if self._in_action and recorded_by is None and not source and not interprets else recording(actor, recorded_by, source)
        with self._action("feedback", stamp(rec, interprets)):
            fb = Feedback(id=f"FB-{len(self.state.evaluation.feedback) + 1:03d}", actor=actor, human=human,
                          simulated=simulated, text=text, at=at, severity=severity, created=now(),
                          build_version=self.state.build.version, **rec, interprets=interprets)
            self.state.evaluation.feedback.append(fb)
            self.ledger.append("feedback", id=fb.id, actor=actor, human=human, simulated=simulated, at=at,
                               text=text[:300], **rec, interprets=interprets)
            gate = self.idx.gate_node
            if reopen and gate and self.rt(gate).status in (NodeStatus.PASSED, NodeStatus.STALE) and \
                    self.state.runtime.status != RunStatus.BLOCKED:
                self.invalidate([gate], f"new feedback {fb.id}", force=True)
                self.state.runtime.status = RunStatus.RUNNING
            self.save("feedback")
        return fb

    def _open_defect(self, defect_id: str):
        d = next((x for x in self.state.evaluation.defects if x.id == defect_id), None)
        if d is None:
            raise EngineError(f"unknown defect {defect_id}")
        if d.status not in DEFECT_ACTIVE | {"in_rework"}:
            raise EngineError(f"{defect_id} is {d.status}, not open")
        return d

    def defer(self, defect_id: str, reason: str, trigger: str, actor: str, on_behalf_of: str | None = None,
              recorded_by: str | None = None, source: str = "", interprets: bool = False) -> dict[str, Any]:
        """Park a defect for a human decision: the gate stops routing it and never resolves it on a re-run for other
        reasons, which is what happened to every deferred defect the interpreter forgot to re-file (field run W39). An agent
        may defer an advisory defect, since that lists it for Wei; a blocking one takes a named human or a delegation."""
        d = self._open_defect(defect_id)
        if d.deferred:
            raise EngineError(f"{defect_id} is already deferred: {d.deferred}")
        if not reason.strip() or not trigger.strip():
            raise EngineError("a deferral needs the reason and the trigger that brings the defect back")
        rec = recording(actor, recorded_by, source)
        human, behalf, delegation = False, None, None
        if d.severity in self.wf.policies.blocking_severities or self.is_human(actor) or on_behalf_of:
            human, behalf, delegation = self._authority(actor, "decide", None, on_behalf_of)
        with self._action("defect_deferred", stamp(rec, interprets)):
            who = actor + (f" on behalf of {behalf} ({delegation})" if behalf else "")
            d.deferred, d.deferred_by, d.deferred_trigger = reason.strip(), who, trigger.strip()
            d.claimed_fixed = None   # a new deferral: no review has said this one no longer holds (review of W61)
            d.history.append(f"{now()} deferred by {who}: {d.deferred} (comes back when: {d.deferred_trigger})")
            self.ledger.append("defect_deferred", defect=defect_id, reason=d.deferred, trigger=d.deferred_trigger,
                               actor=actor, human=human, on_behalf_of=behalf, delegation=delegation,
                               **rec, interprets=interprets)
            self.save("defect_deferred")
        return {"defect": defect_id, "deferred": d.deferred}

    def decide_deferred(self, defect_id: str, decision: str, reason: str, actor: str,
                        on_behalf_of: str | None = None) -> dict[str, Any]:
        """End a deferral with a decision on record: `fix` returns it to the open defects, `close` dismisses it as
        won't-do, `keep` carries it to the next build with the reason, and `resolved`, once a review said it no longer
        holds, records it fixed, so its reviews re-check that it stays so (W61)."""
        d = self._open_defect(defect_id)
        if not d.deferred:
            raise EngineError(f"{defect_id} is not deferred")
        if decision not in ("fix", "close", "keep", "resolved"):
            raise EngineError("decision must be fix, close, keep or resolved")
        if decision == "resolved" and d.claimed_fixed is None:
            raise EngineError(f"no review has said {defect_id} no longer holds: `--close` ends it as won't-do, `--keep` "
                              "carries it to the next build, `--fix` returns it to the open defects")
        if not reason.strip():
            raise EngineError("a decision on a deferred defect needs a reason")
        human, behalf, delegation = self._authority(actor, "decide", None, on_behalf_of)
        with self._action("deferred_decided"):
            who = actor + (f" on behalf of {behalf} ({delegation})" if behalf else "")
            d.history.append(f"{now()} deferral decided by {who}: {decision} ({reason.strip()})")
            if decision == "fix":
                d.deferred = d.deferred_by = d.deferred_trigger = ""
                d.status = "open"
            elif decision == "close":
                d.deferred = d.deferred_by = d.deferred_trigger = ""
                d.status = "dismissed"
            elif decision == "resolved":   # its reviews re-check it stays fixed, and it re-opens with its history (W36)
                d.deferred = d.deferred_by = d.deferred_trigger = ""
                d.status, d.resolved_at_version = "resolved", self.state.build.version
            else:   # kept: only a review after this decision can say again that it no longer holds
                d.attempts_at_start = fix_marker(self, d)
            d.claimed_fixed = None
            self.ledger.append("deferred_decided", defect=defect_id, decision=decision, reason=reason.strip(), actor=actor,
                               human=human, on_behalf_of=behalf, delegation=delegation)
            self.save("deferred_decided")
        return {"defect": defect_id, "decision": decision, "status": d.status}

    def correct_check(self, defect_id: str, check: str, reason: str, actor: str,
                      on_behalf_of: str | None = None) -> dict[str, Any]:
        """Correct an open defect's acceptance check between the gate and the reviews, with a reason on record: a check
        that can never pass (a width the layout cannot reach) would otherwise be judged as written (field run W37). The
        next reviewers' packets carry the corrected check. A change to a recorded criterion, so `change_request` scope."""
        d = next((x for x in self.state.evaluation.defects if x.id == defect_id), None)
        if d is None:
            raise EngineError(f"unknown defect {defect_id}")
        if d.status not in DEFECT_ACTIVE | {"in_rework"}:
            raise EngineError(f"{defect_id} is {d.status}: only an open defect's check can be corrected")
        check, reason = check.strip(), reason.strip()
        if not check or not reason:
            raise EngineError("a corrected check needs the new check and the reason")
        human, behalf, delegation = self._authority(actor, "change_request", d.traced_node, on_behalf_of)
        with self._action("acceptance_check_corrected"):
            old = d.acceptance_check
            d.acceptance_check = check
            who = actor + (f" on behalf of {behalf} ({delegation})" if behalf else "")
            d.history.append(f"{now()} acceptance check corrected by {who}: {reason} (was: {old})")
            self.ledger.append("acceptance_check_corrected", defect=defect_id, was=old, now=check, reason=reason,
                               actor=actor, human=human, on_behalf_of=behalf, delegation=delegation)
            self.save("acceptance_check_corrected")
        return {"defect": defect_id, "was": old, "now": check}

    def change_request(self, doc: str, reason: str, by: str, writer: str | None = None,
                       on_behalf_of: str | None = None, recorded_by: str | None = None,
                       source: str = "", interprets: bool = False) -> ChangeRequest:
        reason = validate_human_words(reason, "change-request reason")
        rec = recording(by, recorded_by, source)
        if doc not in self.state.controls:
            raise EngineError(f"unknown control document {doc}")
        writers = [n.id for n in self.wf.nodes if doc in n.controls.write]
        if writer is None:
            needing = [d.traced_node for d in self.state.evaluation.defects
                       if d.status == "needs_human" and d.traced_node in writers]
            writer = needing[0] if needing else writers[-1]
        if writer not in writers:
            raise EngineError(f"{writer} does not write {doc} (writers: {', '.join(writers)})")
        if self.is_human(by) or on_behalf_of:
            human, behalf, delegation = self._authority(by, "change_request", writer, on_behalf_of)
        else:
            human, behalf, delegation = False, None, None
        reruns = self.idx.order(self.idx.descendants(writer) | {writer})
        gates = [n for n in reruns if self.node(n).human_review.required]
        with self._action("change_request", stamp(rec, interprets)):
            cr = ChangeRequest(id=f"CR-{len(self.state.history.change_requests) + 1:03d}", doc=doc, reason=reason, by=by,
                               human=human, on_behalf_of=behalf, delegation=delegation,
                               status="approved" if human or delegation else "open", writer=writer, at=now(),
                               reruns=reruns, gates=gates, **rec, interprets=interprets)
            self.state.history.change_requests.append(cr)
            self.ledger.append("change_request", id=cr.id, doc=doc, by=by, human=human, on_behalf_of=behalf,
                               delegation=delegation, writer=writer, reason=reason, reruns=reruns, gates=gates,
                               **rec, interprets=interprets)
            if human or delegation:
                self._apply_change_request(cr, by, human, behalf, delegation)
            self.save("change_request")
        return cr

    def revise_brief(self, src: Path, actor: str, reason: str, on_behalf_of: str | None = None) -> list[str]:
        if not src.is_file():
            raise EngineError(f"brief source does not exist: {src}")
        if not reason.strip():
            raise EngineError("a brief revision needs a reason")
        text = src.read_text()
        human, behalf, delegation = self._authority(actor, "change_request", self.idx.freeze_node, on_behalf_of)
        with self._action("revise_brief"):
            brief = self.project.root / "sources" / "brief.md"
            before = brief.read_bytes() if brief.exists() else b""
            archive = self.pdg_dir / "brief-revisions" / f"{now().replace(':', '')}-brief.md"
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_bytes(before)
            tmp = brief.with_suffix(".md.tmp")
            tmp.write_text(text)
            tmp.replace(brief)
            self._undo.append(lambda: brief.write_bytes(before))
            self.state.inputs.brief = text
            self.state.inputs.inputs_sha256 = self._inputs_sha()
            self.state.inputs.frozen = True
            touched = self.invalidate([self.idx.freeze_node], f"brief revised by {actor}: {reason}", force=True,
                                      context=[f"Brief revision by {actor}: {reason}"])
            self.ledger.append("brief_revised", actor=actor, human=human, on_behalf_of=behalf, delegation=delegation,
                               reason=reason, sha256=sha256_file(brief), archived=rel(archive, self.project.root),
                               touched=touched)
            self._update_status()
            self.save("revise_brief")
        return touched

    def _apply_change_request(self, cr: ChangeRequest, by: str, human: bool, behalf: str | None,
                              delegation: str | None) -> None:
        unlocked: dict[str, list[str]] = {}
        for doc in sorted({d for nid in cr.reruns for d in self.node(nid).controls.write
                           if d in self.state.controls and self.state.controls[d].status == "locked"}):
            locked_by = self.state.controls[doc].locked_node
            writers = [nid for nid in cr.reruns if doc in self.node(nid).controls.write and nid != locked_by]
            if not writers:
                continue
            self.controls.unlock_for_many(doc, writers)
            unlocked[doc] = writers
        for d in self.state.evaluation.defects:
            if d.status == "needs_human" and d.traced_node == cr.writer:
                d.status = "open"
                d.history.append(f"{now()} routable again after {cr.id}")
        self.invalidate([cr.writer], f"change request {cr.id} on {cr.doc}.md: {cr.reason}", force=True,
                        context=[f"Change request {cr.id} by {cr.by}: {cr.reason}"])
        self.ledger.append("change_request_approved", id=cr.id, doc=cr.doc, writer=cr.writer, by=by, human=human,
                           on_behalf_of=behalf, delegation=delegation, unlocked=unlocked)
        self._update_status()

    def decide_change_request(self, cr_id: str, approve: bool, actor: str, reason: str,
                              on_behalf_of: str | None = None, recorded_by: str | None = None,
                              source: str = "", interprets: bool = False) -> ChangeRequest:
        """Approve or decline a change request an agent filed without authority: it stayed open for good, with no
        command to decide it (backlog N-04). The request shows its cost, the re-runs and re-asked gates (N-05)."""
        cr = next((c for c in self.state.history.change_requests if c.id == cr_id), None)
        if cr is None:
            raise EngineError(f"unknown change request {cr_id}")
        if cr.status != "open":
            raise EngineError(f"{cr_id} is {cr.status}, not open")
        reason = validate_human_words(reason, "change-request decision reason")
        rec = recording(actor, recorded_by, source)
        human, behalf, delegation = self._authority(actor, "change_request", cr.writer, on_behalf_of)
        with self._action("change_request_decided", stamp(rec, interprets)):
            cr.decided_by, cr.decision_reason = actor, reason.strip()
            if approve:
                cr.status = "approved"
                self._apply_change_request(cr, actor, human, behalf, delegation)
            else:
                cr.status = "declined"
                self.ledger.append("change_request_declined", id=cr.id, doc=cr.doc, writer=cr.writer, by=actor,
                                   human=human, on_behalf_of=behalf, delegation=delegation, reason=cr.decision_reason,
                                   **rec, interprets=interprets)
            self.save("change_request_decided")
        return cr

    def unblock(self, node_id: str, actor: str, note: str = "", reset_budget: bool = False,
                waive: list[str] | None = None, restore_controls: bool = False,
                on_behalf_of: str | None = None, recorded_by: str | None = None,
                source: str = "", interprets: bool = False) -> dict[str, Any]:
        if note:
            note = validate_human_words(note, "unblock note")
        rec = recording(actor, recorded_by, source)
        human, behalf, delegation = self._authority(actor, "unblock", node_id if node_id != "run" else None, on_behalf_of)
        esc = [e for e in self.state.runtime.escalations if e.open and e.node == node_id]
        if not esc:
            raise EngineError(f"{node_id} has no open escalation")
        if reset_budget and delegation is not None:
            # a grant that says how many budget resets it covers holds an agent to that number; a further reset is a
            # named human's (field run W59). A grant that says nothing is not limited: that default is Wei's call (D12)
            grant = next(d for d in self.state.history.delegations if d.id == delegation)
            counted = self.budget_resets() if grant.budget_resets is not None else {}
            if counted is None:
                raise EngineError(f"{delegation} covers {grant.budget_resets} rework-budget reset(s), and the ledger is "
                                  f"damaged, so the resets it made cannot be counted: a named human resets the budget")
            used = counted.get(delegation, 0)
            if grant.budget_resets is not None and used >= grant.budget_resets:
                raise EngineError(f"{delegation} covers {grant.budget_resets} rework-budget reset(s) and has used {used}: "
                                  f"a further reset needs a named human (`pdg unblock … --reset-budget --actor "
                                  f"{grant.by}`), or a grant that covers more")
        if waive:
            self._waive(node_id, waive, actor, note, record=False)   # refuse a bad waiver before anything changes
        with self._action("unblocked", stamp(rec, interprets)):
            esc = [e for e in self.state.runtime.escalations if e.open and e.node == node_id]
            if restore_controls:  # a hand edit: put the accepted versions back; the displaced text stays in the archive
                live = {d: self.controls.path(d).read_bytes() for d in self.state.controls if self.controls.path(d).is_file()}
                self._undo.append(lambda: [self.controls.path(d).write_bytes(b) for d, b in live.items()])
                restored = self.controls.restore_accepted("hand-edit")
                self.ledger.append("controls_restored", docs=restored, actor=actor, human=human,
                                   on_behalf_of=behalf, delegation=delegation, **rec, interprets=interprets)
            if waive:
                self._waive(node_id, waive, actor, note, behalf=behalf, delegation=delegation)
            for e in esc:
                e.open, e.resolved_by, e.resolved_at = False, actor, now()
            if node_id != "run":
                rt = self.rt(node_id)
                rt.streak = 0
                rt.interruptions = 0
                for e in self.idx.outgoing[node_id]:
                    if e.kind == EdgeKind.LOOP and self.state.runtime.loop_traversals.get(e.id, 0) >= (e.max_traversals or 0):
                        self.state.runtime.loop_traversals[e.id] = 0
                self.invalidate([node_id], f"unblocked by {actor}: {note}", force=True,
                                context=[f"Unblocked by {actor}: {note}"] if note else None)
            edges_reset: list[str] = []
            if reset_budget:
                self.state.runtime.rework_cycles = 0
                for d in self.state.evaluation.defects:
                    if d.status in DEFECT_ACTIVE | {"in_rework"}:   # a defect mid-rework too (independent audit #6)
                        d.failures = 0
                # the rework edges are the same budget as the cycles (field run W23), so a reset restores them too;
                # otherwise a gate blocked on a spent edge could never be lifted (backlog B-01)
                for e in self.idx.outgoing.get(self.idx.regen_node, []) if self.idx.regen_node else []:
                    if e.kind == EdgeKind.LOOP and self.state.runtime.loop_traversals.get(e.id, 0):
                        self.state.runtime.loop_traversals[e.id] = 0
                        edges_reset.append(e.id)
            self.ledger.append("unblocked", node=node_id, actor=actor, human=human, on_behalf_of=behalf,
                               delegation=delegation, note=note, reset_budget=reset_budget, waived=waive or [],
                               edges_reset=edges_reset, **rec, interprets=interprets)
            self.state.runtime.status = RunStatus.RUNNING
            self._update_status()
            self.save("unblocked")
        return {"node": node_id, "status": self.state.runtime.status.value}

    def budget_resets(self) -> dict[str, int] | None:
        """Rework-budget resets so far, by who made them: a delegation id, or the named human (field run W59)."""
        return count_resets(self.ledger)

    def _waive(self, node_id: str, gaps: list[str], actor: str, reason: str, record: bool = True,
               behalf: str | None = None, delegation: str | None = None) -> None:
        """Waive resolvable intake gaps. `record=False` only checks, so a refused waiver changes nothing."""
        node = self.node(node_id)
        if node.gate != "freeze_inputs":
            raise EngineError("only intake gaps (at the freeze_inputs node) can be waived")
        if self.state.inputs.frozen:
            raise EngineError("the inputs are frozen; a waiver must come before the freeze")
        report = self.current("gaps")
        known = {g["id"]: g for g in (json.loads((self.project.root / report[-1].path).read_text())["gaps"] if report else [])}
        for g in gaps:
            if g not in known:
                raise EngineError(f"gap {g} is not in the latest gap report")
            if known[g]["severity"] == "blocking":
                raise EngineError(f"gap {g} is blocking: answer it, don't waive it")
            if not reason.strip():
                raise EngineError("a waiver needs a note (why the product can proceed without the source)")
        for g in gaps if record else []:
            self.state.inputs.waivers.append(GapWaiver(gap=g, by=actor, reason=reason, at=now()))
            self.ledger.append("gap_waived", gap=g, by=actor, on_behalf_of=behalf, delegation=delegation, reason=reason)

    def accept_risk(self, assumption: str, actor: str, reason: str, on_behalf_of: str | None = None,
                    recorded_by: str | None = None, source: str = "", interprets: bool = False) -> dict[str, Any]:
        """A named human accepts building past an unvalidated assumption. The fidelity gate (N10) counts this record,
        never an `accepted_by` field an agent wrote or a mention of the id in someone's words."""
        if not self.is_human(actor) and not on_behalf_of:
            raise EngineError(f"only a named human ({', '.join(self.humans)}) accepts a risk; '{actor}' is not one")
        human, behalf, delegation = self._authority(actor, "accept_risk", None, on_behalf_of)
        reason = validate_human_words(reason, "risk acceptance reason")
        rec = recording(actor, recorded_by, source)
        known = {a.id: a for a in self.state.research.assumptions}
        if assumption not in known:
            raise EngineError(f"assumption {assumption} is not in the research state (known: {', '.join(sorted(known)) or 'none'})")
        with self._action("risk_accepted", stamp(rec, interprets)):
            statement_sha = sha256_json(known[assumption].statement)
            ra = RiskAcceptance(assumption=assumption, actor=actor, on_behalf_of=behalf, delegation=delegation,
                                reason=reason, at=now(), build_version=self.state.build.version,
                                statement_sha256=statement_sha, **rec, interprets=interprets)
            self.state.history.risk_acceptances.append(ra)
            self.ledger.append("risk_accepted", assumption=assumption, actor=actor, human=human,
                               on_behalf_of=behalf, delegation=delegation, reason=ra.reason,
                               riskiest=known[assumption].riskiest, statement_sha256=statement_sha,
                               **rec, interprets=interprets)
            self.save("risk_accepted")
        return ra.model_dump()

    def invalidate_nodes(self, targets: list[str], reason: str, actor: str, on_behalf_of: str | None = None,
                         recorded_by: str | None = None, source: str = "", interprets: bool = False) -> list[str]:
        reason = validate_human_words(reason, "invalidation reason")
        rec = recording(actor, recorded_by, source)
        for t in targets:
            self.node(t)
        human, behalf, delegation = self._authority(actor, "invalidate", None, on_behalf_of)
        for t in targets:                                  # an --except-nodes grant covers none of its listed nodes
            self._authority(actor, "invalidate", t, on_behalf_of)
        with self._action("invalidate", stamp(rec, interprets)):
            touched = self.invalidate(targets, f"invalidated by {actor}: {reason}", force=True)
            self.ledger.append("human_invalidated", targets=targets, actor=actor, human=human, on_behalf_of=behalf,
                               delegation=delegation, reason=reason, touched=touched, **rec, interprets=interprets)
            self._update_status()
            self.save("invalidate")
        return touched

    def rollback(self, seq: int, actor: str, recorded_by: str | None = None, source: str = "",
                 interprets: bool = False) -> dict[str, Any]:
        if not self.is_human(actor):
            raise EngineError("only a named human rolls back")
        rec = recording(actor, recorded_by, source)
        cp = next((c for c in self.state.history.checkpoints if c.seq == seq), None)
        if cp is None:
            raise EngineError(f"no checkpoint {seq} (see `pdg status --checkpoints`)")
        if not (self.project.root / cp.path).is_file():
            where = self._checkpoint_archives(cp.path)
            raise EngineError(f"checkpoint {seq} was archived"
                              + (f"; restore the archive first (`bash restore.sh` in {', '.join(where)})" if where else ""))
        cur = self.state
        old = ProjectState.model_validate(read_json(self.project.root / cp.path))
        gone = sorted({a.path for a in old.artifacts.values() if a.current and not (self.project.root / a.path).exists()})
        if gone:   # an archived earlier attempt: put it back before rolling back to it (N-17)
            folders = {"/".join(Path(g).parts[:3]) for g in gone}
            where = sorted({e["data"]["dest"] for e in self.ledger.events("archived")
                            if folders & set(self._archived_folders(Path(e["data"]["dest"])))})
            raise EngineError(f"checkpoint {seq} needs files no longer in the project: {gone[:5]}"
                              + (f"; restore the archive first (`bash restore.sh` in {', '.join(where)})" if where else ""))
        for k, v in cur.runtime.loop_traversals.items():        # budgets never go backwards
            old.runtime.loop_traversals[k] = max(v, old.runtime.loop_traversals.get(k, 0))
        old.runtime.rework_cycles = max(cur.runtime.rework_cycles, old.runtime.rework_cycles)
        fails = {d.id: d.failures for d in cur.evaluation.defects}
        for d in old.evaluation.defects:
            d.failures = max(d.failures, fails.get(d.id, 0))
        seen = {e.id for e in old.runtime.escalations}
        old.runtime.escalations += [e for e in cur.runtime.escalations if e.open and e.id not in seen]
        old.history.checkpoints = cur.history.checkpoints
        old.runtime.config_sha256 = cur.runtime.config_sha256
        old.runtime.ledger_breaks = cur.runtime.ledger_breaks   # an accepted ledger break is never rolled back
        old.runtime.pending_ledger = []
        for nid, rt in old.runtime.nodes.items():
            if rt.status in ACTIVE or rt.status == NodeStatus.WAITING_AGENT:
                rt.status = NodeStatus.READY
                rt.token = None
            rt.attempt = max(rt.attempt, cur.runtime.nodes[nid].attempt)
        carried = {}
        for nid, crt in cur.runtime.nodes.items():   # nothing an agent submitted disappears with the state (review I2)
            if crt.parked and not self.parked_fate(nid).startswith("edited"):
                carried[nid] = {"attempt": crt.attempt, "at": crt.parked["at"], "why": f"rolled back to checkpoint {seq}",
                                "outputs": {k: rel(Path(v), self.project.root) for k, v in crt.parked["outputs"].items()}}
            elif crt.carried:
                carried[nid] = crt.carried
            if nid in old.runtime.nodes and nid in carried:
                old.runtime.nodes[nid].carried = carried[nid]
        parked = {nid: self.parked_fate(nid) for nid, crt in cur.runtime.nodes.items() if crt.parked}
        with self._action("rollback", stamp(rec, interprets)):
            live = {doc: self.controls.path(doc).read_bytes() for doc in cur.controls if self.controls.path(doc).is_file()}
            self._undo.append(lambda: [self.controls.path(d).write_bytes(b) for d, b in live.items()])
            for nid, fate in parked.items():
                self.ledger.append("parked_resolved", node=nid, reason=f"rolled back to checkpoint {seq}",
                                   fate="edited after parking: discarded" if fate.startswith("edited")
                                   else "outputs handed to its next attempt",
                                   recorded_as_feedback=[], carried=not fate.startswith("edited"),
                                   discarded=fate.startswith("edited"))
            self.state = old
            restored = self.controls.restore_accepted("before-rollback")
            self.ledger.append("rollback", to_checkpoint=seq, actor=actor, controls_restored=restored,
                               **rec, interprets=interprets)
            self._update_status()
            self.save("rollback")
        return {"restored_checkpoint": seq, "controls_restored": restored, "status": self.state.runtime.status.value}

    def release_shelf(self) -> list[dict[str, Any]]:
        from .release_shelf import export
        with self._action("release_shelf_rebuilt"):
            rows = export(self.project.root, self.state)
            self.ledger.append("release_shelf_rebuilt", releases=len(rows), latest=rows[-1].version if rows else 0)
            self.save("release_shelf_rebuilt")
        return [r.__dict__ for r in rows]

    @staticmethod
    def _archived_folders(dest: Path) -> list[str]:
        try:
            return [m["path"] for m in read_json(dest / "manifest.json").get("moved", [])]
        except (OSError, ValueError, AttributeError, KeyError, TypeError):
            return []

    def _checkpoint_archives(self, checkpoint_path: str) -> list[str]:
        out = []
        for e in self.ledger.events("archived"):
            dest = e["data"].get("dest")
            if not dest:
                continue
            try:
                moved = read_json(Path(dest) / "manifest.json").get("moved_checkpoints", [])
            except (OSError, ValueError, AttributeError):
                continue
            if checkpoint_path in [m.get("path") for m in moved]:
                out.append(dest)
        return sorted(out)

    def archive_candidates(self) -> list[tuple[str, int]]:
        """Attempt folders (`work/<node>/a<n>`) that no current artifact, current attempt or last pass uses: earlier
        attempts and their screenshot rounds. Their records and hashes stay in the state and the ledger (backlog N-17)."""
        keep: set[str] = set()
        for a in self.state.artifacts.values():
            if a.current:
                keep.add("/".join(Path(a.path).parts[:3]))
        for nid, rt in self.state.runtime.nodes.items():
            keep |= {f"work/{nid}/a{rt.attempt}", f"work/{nid}/a{rt.passed_attempt}"}
            if rt.carried:   # a parked submission its next packet points to
                keep.add(f"work/{nid}/a{rt.carried['attempt']}")
        out = []
        for d in sorted((self.project.root / "work").glob("*/a*")):
            r = rel(d, self.project.root)
            # only attempt folders: `app-src` or `assets` under a node's folder is not an earlier attempt (review I3)
            if d.is_dir() and re.fullmatch(r"a\d+", d.name) and r not in keep:
                out.append((r, sum(f.stat().st_size for f in d.rglob("*") if f.is_file())))
        return out

    def archive_plan(self, keep: list[str] | None = None):
        from .archive import plan
        return plan(self.project.root, self.archive_candidates(), self.state.history.checkpoints, keep or [])

    def archive(self, dest_root: Path, actor: str, keep: list[str] | None = None,
                recorded_by: str | None = None, source: str = "", interprets: bool = False) -> dict[str, Any]:
        """Move superseded attempt folders out of the project, with a manifest, an UNDO.md and a restore.sh. A named
        human's call (backlog D5 decides what a run commits); a rollback that needs a moved folder refuses and names it."""
        from .archive import dangling_symlinks
        if not self.is_human(actor):
            raise EngineError("only a named human archives a run's earlier attempts")
        rec = recording(actor, recorded_by, source)
        plan = self.archive_plan(keep)
        if plan.unmatched_keep:
            raise EngineError("--keep did not match an archive candidate: " + ", ".join(plan.unmatched_keep))
        cands = plan.move
        if not cands:
            return {"moved": 0, "bytes": 0, "dest": None}
        dangling = dangling_symlinks(self.project.root, [r for r, _ in cands])
        if dangling:
            raise EngineError("archive would leave dangling symlink(s) inside the run: " + ", ".join(dangling[:8]))
        safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", self.state.project.id).lstrip(".-") or "project"   # review S5
        base = Path(dest_root).expanduser().resolve() / f"{dt.datetime.now(dt.timezone.utc):%Y%m%d}-pdg-{safe_id}"
        dest, n = base, 1
        while dest.exists():   # a second archive the same day keeps the first one's restore script
            n += 1
            dest = base.with_name(f"{base.name}-{n}")
        dest.mkdir(parents=True)
        root_q, dest_q = shlex.quote(str(self.project.root)), shlex.quote(str(dest))
        # written before anything moves and each line guarded, so it is safe to run twice or after a crash
        # a folder already back in the project is never overwritten or nested into (review S6)
        restore_attempts = "".join(f"if [ -e {dest_q}/{shlex.quote(r)} ]; then if [ -e {root_q}/{shlex.quote(r)} ]; "
                                                  f"then echo 'already in the project, left as it is: {r}' >&2; exit 1; fi; "
                                                  f"mkdir -p {root_q}/{shlex.quote(str(Path(r).parent))} && "
                                                  f"mv {dest_q}/{shlex.quote(r)} {root_q}/{shlex.quote(r)}; fi\n"
                                                  for r, _ in cands)
        restore_checkpoints = "".join(f"if [ -e {dest_q}/{shlex.quote(c.path)} ]; then if [ -e {root_q}/{shlex.quote(c.path)} ]; "
                                      f"then echo 'already in the project, left as it is: {c.path}' >&2; exit 1; fi; "
                                      f"mkdir -p {root_q}/{shlex.quote(str(Path(c.path).parent))} && "
                                      f"mv {dest_q}/{shlex.quote(c.path)} {root_q}/{shlex.quote(c.path)}; fi\n"
                                      for c in plan.checkpoints)
        (dest / "restore.sh").write_text("#!/bin/bash\n# put every archived attempt folder back into the project\nset -e\n"
                                        + restore_attempts + restore_checkpoints)
        (dest / "restore.sh").chmod(0o755)
        moved, moved_checkpoints = [], []
        with self._action("archived", stamp(rec, interprets)):   # all or nothing: a failed move puts every folder moved so far back
            for r, size in cands:
                src, target = self.project.root / r, dest / r
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(target))
                self._undo.append(lambda s=src, t=target: shutil.move(str(t), str(s)))
                moved.append({"path": r, "bytes": size})
            for cp in plan.checkpoints:
                src, target = self.project.root / cp.path, dest / cp.path
                if src.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(target))
                    self._undo.append(lambda s=src, t=target: shutil.move(str(t), str(s)))
                    moved_checkpoints.append({"seq": cp.seq, "path": cp.path})
            write_json_atomic(dest / "manifest.json", {"project": str(self.project.root), "moved": moved,
                                                       "moved_checkpoints": moved_checkpoints, "kept": plan.keep,
                                                       "at": now(), "by": actor})
            (dest / "UNDO.md").write_text(f"# Archived attempts of {self.state.project.id}\n\n{len(moved)} earlier attempt "
                                          f"folders and {len(moved_checkpoints)} checkpoint(s) moved by {actor} at {now()} "
                                          f"from `{self.project.root}`. Their records and hashes stay in the run's state "
                                          "and ledger. To put them back: `bash restore.sh`.\n")
            self.ledger.append("archived", dest=str(dest), folders=len(moved), bytes=sum(m["bytes"] for m in moved),
                               checkpoints=len(moved_checkpoints), actor=actor, **rec, interprets=interprets)
            self.save("archived")
        return {"moved": len(moved), "bytes": sum(m["bytes"] for m in moved), "dest": str(dest)}

    def ratify(self, target: str, actor: str, reason: str, reverse: bool = False,
               recorded_by: str | None = None, source: str = "", interprets: bool = False) -> dict[str, Any]:
        if not self.is_human(actor):
            raise EngineError(f"only a named human ({', '.join(self.humans)}) ratifies an action; '{actor}' is not one")
        reason = validate_human_words(reason, "ratification reason")
        targets = {str(e["seq"]) for e in self.ledger.events()}
        targets |= {str(e["data"].get("id")) for e in self.ledger.events() if e["data"].get("id")}
        targets |= {a.node for a in self.state.history.approvals}
        if target not in targets:
            raise EngineError(f"cannot ratify unknown action {target}")
        rec = recording(actor, recorded_by, source)
        with self._action("ratified", stamp(rec, interprets)):
            rat = Ratification(target=target, actor=actor, reason=reason, at=now(), reverse=reverse)
            self.state.history.ratifications.append(rat)
            self.ledger.append("ratified", target=target, actor=actor, reason=reason, reverse=reverse,
                               **rec, interprets=interprets)
            self.save("ratified")
        return rat.model_dump()
