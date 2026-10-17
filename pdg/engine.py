"""The graph engine: readiness, conflict-free parallel batches, fingerprints and memo-skips, completion checks, routing,
targeted invalidation, checkpoints and resume. Configuration drift, human actions (gates, change requests, rollback,
archive) and task packets live in the engine_config, engine_human and engine_packets mixins.

Execution follows a bulk-synchronous rhythm: every ready node in a batch executes in parallel (threads; agents are
external and answer through task packets), then results are judged and committed one by one in graph order, so the
shared state is never written concurrently. The engine — not an agent's sense of completion — decides when work is done:
a node passes only when its completion checks recompute from disk, and the run passes only when END is reached.
"""

from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import json
import secrets
import shlex
import shutil
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

import yaml
from pydantic import ValidationError

from .artifacts import ARTIFACT_MODELS, Interpretation, Source, ValidationDoc, output_problems
from .context import CheckResult, NodeContext, NodeResult
from .controls import split_sections, ControlStore, front_matter
from .evaluation import (dimension_index, evaluate_tool_dims, load_rubrics, merge_review, missing_review_dims, node_dimensions,
                         unreported_tool_dims)
from .executors import Executor, FixtureError, ScriptedExecutor, TaskPacketExecutor
from .graph import DEFAULT_WORKFLOW, GraphIndex, control_reads, load_workflow, outcome_matches, resolve_tool, structural_errors
from .memory import DEFAULT_RULES, RuleBase, is_human
from .models import (ArtifactRecord, CheckpointRef, Delegation, EdgeKind, Escalation, FindingRecord, KnowledgeState, LedgerBreak,
                     NodeDef, NodeKind, NodeRuntime, NodeStatus, PassedChecks, ProjectInfo, ProjectState, PrototypeRef, REDUCER_PATHS,
                     Revision, RunStatus, TestResult, ValidationFinding)
from .provenance import Ledger, LedgerBehind, LedgerCorrupt
from .util import (BRIEF_PLACEHOLDER, PKG_ROOT, ConcurrentChange, file_identity, get_path, glob_files, now, read_json, read_text,
                   rel, set_path, sha256_bytes, sha256_file, sha256_json, write_json_atomic)
from .engine_common import (ACTIVE, DEFECT_ACTIVE, DELEGABLE_ACTIONS, OS_NOISE, RUNNABLE,  # noqa: F401 - re-exported
                            SIMULATED_LABEL, WAITING, EngineError, StaleSubmission, _deep_merge, checks_fingerprint,
                            ignored_tree_noise, package_git_state, release_checks, tree_sha, renew_command,
                            latest_reviews_by_node, validation_findings)
from .engine_config import ConfigMixin
from .engine_human import HumanActionsMixin
from .engine_packets import PacketMixin


def ledger_health(ledger_path: Path, runtime: dict[str, Any] | None) -> tuple[bool, int, str]:
    """(ok, events, why) for a run's ledger: the hash chain is whole AND it still reaches the last event the state
    recorded. Events a human action committed with the state but could not write yet count as present (the next command
    that changes the run writes them). Breaks a named human accepted are listed, never hidden."""
    ledger = Ledger(ledger_path, read_only=True)
    ok, n, msg = ledger.verify()
    rt = runtime or {}
    if ok:
        tail, pending = rt.get("ledger_tail"), rt.get("pending_ledger") or []
        lost = ledger.reaches(tail)
        if lost and ledger.pending_fill(tail, pending):
            msg = (f"ok; {len(pending)} event(s) are pending in the state and will be written by the next command that "
                   "changes the run")
        elif lost:
            ok, msg = False, lost
    for brk in rt.get("ledger_breaks") or []:
        b = LedgerBreak.model_validate(brk)
        msg += f"; break accepted by {b.actor} ({b.at[:10]}): {b.describe()} ({b.reason})"
    return ok, n, msg


class Project:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        cfg = self.root / "pdg.project.yaml"
        self.config: dict[str, Any] = (yaml.safe_load(cfg.read_text()) or {}) if cfg.exists() else {}

    @property
    def state_path(self) -> Path:
        return self.root / ".pdg" / "state.json"

    @property
    def dry_run(self) -> bool:
        return bool(self.config.get("dry_run", False))

    @property
    def fixtures(self) -> Path:
        return self.root / self.config.get("fixtures", "fixtures")

    KEYS = {"id", "name", "dry_run", "fixtures", "humans", "reference", "release_shelf", "rules", "workflow"}

    def unknown_keys(self) -> list[str]:
        """Keys pdg does not read. A mistyped key (`dry-run:`) would otherwise be silently ignored."""
        return sorted(set(self.config) - self.KEYS)


class Engine(ConfigMixin, HumanActionsMixin, PacketMixin):
    """One run of the graph. Methods for configuration, human actions and task packets come from the mixins in
    engine_config.py, engine_human.py and engine_packets.py."""

    def __init__(self, project_dir: str | Path, executor: Executor | None = None, workflow_path: str | Path | None = None,
                 rules_path: str | Path | None = None, accept_ledger_break: tuple[str, str] | None = None):
        """Open (or create) a run. Callers that change the run hold the project lock (pdg.lock). `accept_ledger_break`
        is (named human, reason): the only way to continue a run whose ledger lost events (`pdg accept-ledger-break`)."""
        self._in_action = False   # inside a human action, saves are deferred to its single commit
        self._undo: list[Callable[[], None]] = []   # disk side effects of the current human action, undone if it fails
        self._state_identity: tuple[int, int, int] | None = None   # state.json as this engine last read or wrote it
        self.recovered_ledger = 0   # pending events written on open (a human action whose ledger write did not land)
        self.notices: list[str] = []   # what the submitting agent must be told (edits the engine did not apply), per submit
        self.project = Project(project_dir)
        if not self.project.root.is_dir():
            raise EngineError(f"project directory {self.project.root} does not exist (run `pdg init` first)")
        if self.project.unknown_keys():
            raise EngineError(f"pdg.project.yaml has key(s) pdg does not read: {', '.join(self.project.unknown_keys())} "
                              f"(known: {', '.join(sorted(Project.KEYS))}); remove or fix them")
        self.pdg_dir = self.project.root / ".pdg"
        self.pdg_dir.mkdir(parents=True, exist_ok=True)
        wf_cfg = self.project.config.get("workflow")
        self.workflow_path = Path(workflow_path or wf_cfg or DEFAULT_WORKFLOW)
        if not workflow_path and wf_cfg and not self.workflow_path.is_absolute():   # like `rules:`, relative to the project
            self.workflow_path = self.project.root / self.workflow_path
        self.wf = load_workflow(self.workflow_path)
        errs = structural_errors(self.wf)
        if errs:
            raise EngineError("the graph fails validation — refusing to run: " + "; ".join(errs[:6]))
        self.idx = GraphIndex(self.wf)
        self.rubrics = load_rubrics()
        self.dims = dimension_index(self.rubrics)
        self.humans = sorted(set(self.wf.policies.human_actors) | set(self.project.config.get("humans") or []))
        rp = rules_path or self.project.config.get("rules")
        self.rules_path = (self.project.root / rp).resolve() if rp and not Path(rp).is_absolute() else Path(rp or DEFAULT_RULES)
        self.rules = RuleBase(self.rules_path, humans=self.humans)
        self.rule_states = self.rules.states()
        self.ledger = Ledger(self.pdg_dir / "ledger.jsonl")
        self.controls = ControlStore(self)
        self._hash_cache: dict[str, tuple[tuple[int, int, int, int], str]] = {}
        if self.project.state_path.exists():
            self._state_identity = file_identity(self.project.state_path)
            self.state = ProjectState.model_validate(read_json(self.project.state_path))
            rechain: list[str] = []
            if self.state.runtime.pending_ledger:   # a human action committed but its ledger write did not land
                try:
                    self.recovered_ledger = self.ledger.recover(self.state.runtime.pending_ledger)
                except LedgerCorrupt as exc:   # the ledger also lost events, so these no longer continue it
                    if not accept_ledger_break:
                        raise EngineError(
                            f"{exc}: the ledger lost events, and the last human action's "
                            f"{len(self.state.runtime.pending_ledger)} event(s) cannot be written after them. Nothing was "
                            "written. Restore .pdg/ledger.jsonl from a backup, or a named human accepts the loss: "
                            f"`pdg accept-ledger-break {shlex.quote(str(self.project.root))} --actor <name> --reason \"…\"`") from None
                    rechain = list(self.state.runtime.pending_ledger)   # written again after the accepted break
                self.state.runtime.pending_ledger = []
            self._check_ledger_anchor(accept_ledger_break, rechain)   # before anything new is written to a damaged ledger
            self._restore_interrupted_commit()
            self._resume_fixups()
        else:
            if accept_ledger_break:
                raise EngineError(f"{self.project.root} has no run yet, so there is no ledger break to accept")
            brief = self.project.root / "sources" / "brief.md"
            if not brief.is_file() or BRIEF_PLACEHOLDER in read_text(brief) or not read_text(brief).strip():
                raise EngineError(f"write the requester's brief into {rel(brief, self.project.root)} first "
                                  "(verbatim; a run never starts from the template)")
            self.state = self._new_state()
            self.controls.ensure()
            self.ledger.append("run_created", project=self.state.project.id, workflow=self.wf.id,
                               version=self.wf.version, config_sha256=self.state.runtime.config_sha256,
                               rules_version=self.rules.version, dry_run=self.project.dry_run)
            self._checkpoint("created", None)
        self.executor = executor or self._default_executor()

    # ------------------------------------------------------------------------------------------------ construction
    def _default_executor(self) -> Executor:
        if self.project.dry_run:
            return ScriptedExecutor(self.project.fixtures)
        return TaskPacketExecutor()

    def _new_state(self) -> ProjectState:
        cfg = self.project.config
        brief = self.project.root / "sources" / "brief.md"
        st = ProjectState(schema_version=self.wf.policies.schema_version,
                          project=ProjectInfo(id=cfg.get("id") or self.project.root.name,
                                              name=cfg.get("name") or self.project.root.name, created=now(),
                                              workflow_id=self.wf.id, workflow_version=self.wf.version))
        st.inputs.brief = brief.read_text() if brief.exists() else ""
        st.runtime.nodes = {n.id: NodeRuntime() for n in self.wf.nodes}
        st.runtime.config_sha256 = self._config_fingerprint()
        st.runtime.config_parts = self._config_files()
        st.runtime.dry_run = self.project.dry_run
        st.knowledge = self._knowledge_ref()
        return st

    def _knowledge_ref(self) -> KnowledgeState:
        states = self.rules.states()
        prev = getattr(self, "state", None)
        return KnowledgeState(rules_path=rel(self.rules_path, PKG_ROOT), rules_version=self.rules.version,
                              rules_sha256=self.rules.sha256(),
                              enforced=sorted(r for r, s in states.items() if s in ("adopted", "monitored")),
                              advisory=sorted(r for r, s in states.items() if s in ("validated", "approved")),
                              lessons=prev.knowledge.lessons if prev else [],
                              proposal=prev.knowledge.proposal if prev else None)

    def _reopen_inputs_if_unfrozen(self) -> None:
        """The freeze is N02's verdict: it holds only while N02 stands passed. Once N02 is re-opened (a new source
        through N01, an intake loop), the inputs are open again until N02 passes and re-freezes them. Before this, N01's
        re-registration of the sources tripped the frozen-input check, which escalated before N02 could ever run
        (field run W48)."""
        fz = self.idx.freeze_node
        if self.state.inputs.frozen and fz and self.rt(fz).status != NodeStatus.PASSED:
            self.ledger.append("inputs_reopened", node=fz, status=self.rt(fz).status.value,
                               sha256=self.state.inputs.inputs_sha256, sources=len(self.state.inputs.sources))
            self.state.inputs.frozen = False

    def _repair_duplicate_defect_ids(self) -> None:
        """A run from before W46's fix can hold two defects with one id. The later one takes the next free id, its
        history says so, and the ledger records it; records written before that may mean either (field run W46)."""
        from .gating import _next_defect_id
        seen: set[str] = set()
        for d in self.state.evaluation.defects:
            if d.id not in seen:
                seen.add(d.id)
                continue
            old, d.id = d.id, _next_defect_id(self.state.evaluation.defects)
            seen.add(d.id)
            d.history.append(f"{now()} renumbered {old} → {d.id}: another defect already had {old} (field run W46); records "
                             f"before this that say {old} may mean either")
            self.ledger.append("defect_renumbered", old=old, new=d.id, signature=d.signature)

    def _migrate_defect_signatures(self) -> bool:
        """Normalize attempt-folder locations in older states when they are loaded."""
        from .gating import canonical_signature
        seen: dict[str, Any] = {}
        merged = []
        changed = False
        for d in self.state.evaluation.defects:
            old = d.signature
            d.signature = canonical_signature(d.signature)
            d.aliases = sorted({canonical_signature(a) for a in d.aliases if canonical_signature(a) != d.signature})
            if old != d.signature:
                d.history.append(f"{now()} migrated signature {old} → {d.signature} (attempt folder removed)")
                changed = True
            twin = seen.get(d.signature)
            if twin:
                active = {"open", "persisting", "needs_human", "in_rework"}
                keep, drop = (d, twin) if d.status in active and twin.status not in active else (twin, d)
                keep.aliases = sorted(set(keep.aliases) | {old, drop.signature, *d.aliases, *drop.aliases} - {keep.signature})
                keep.failures += drop.failures
                if keep.status == "resolved" and drop.status in active:
                    keep.status, keep.resolved_at_version = drop.status, None
                    keep.history.append(f"{now()} re-opened by merged active duplicate {drop.id}")
                keep.history += [f"{now()} merged duplicate defect {drop.id} ({old}) into {keep.id}", *drop.history]
                drop.status = "dismissed"
                drop.history.append(f"{now()} merged into {keep.id}: same canonical signature")
                seen[d.signature] = keep
                merged.append((drop.id, keep.id, old))
                changed = True
            else:
                seen[d.signature] = d
        for old_id, new_id, sig in merged:
            self.ledger.append("defect_merged", old=old_id, new=new_id, signature=sig)
        return changed

    def _journal_path(self) -> Path:
        return self.pdg_dir / "commit-journal.json"

    def _restore_interrupted_commit(self) -> None:
        """A commit saves state more than once (control installs, feedback). If the process died mid-commit, the journal
        holds the state from before it: restore that, and put the control files back to the versions it accepted."""
        j = self._journal_path()
        if not j.exists():
            return
        data = read_json(j)
        breaks = self.state.runtime.ledger_breaks   # an accepted ledger break is never rolled back
        self.state = ProjectState.model_validate(data["state"])
        self.state.runtime.ledger_breaks = breaks
        restored = self.controls.restore_accepted("interrupted-commit")
        self.ledger.append("commit_rolled_back", node=data["node"], attempt=data["attempt"], controls_restored=restored)
        self._write_state()
        j.unlink()

    def _check_ledger_anchor(self, accept: tuple[str, str] | None, rechain: list[str] | None = None) -> None:
        """The ledger must still contain the last event the state recorded. Otherwise events were deleted, cut off or the
        ledger was replaced, and appending now would hide that under a new, valid-looking end. Only a named human may
        accept the loss (`pdg accept-ledger-break`); the break is then ledgered, kept in the state and shown at release."""
        tail = self.state.runtime.ledger_tail
        lost = self.ledger.reaches(tail)
        if not lost:
            if accept:
                raise EngineError("the ledger reaches the last event the state recorded; there is no break to accept")
            return
        ok, _, why = self.ledger.verify()
        if not ok:   # a lost tail can be accepted; a damaged chain cannot be repaired by accepting anything
            raise EngineError(f"the ledger's own chain is broken ({why}). Nothing was written. Accepting lost events cannot "
                              "repair it, and N18 would never release: restore .pdg/ledger.jsonl from a backup")
        if not accept:
            raise EngineError(f"{lost}. Nothing was written. If no backup exists, a named human may accept the loss: "
                              f"`pdg accept-ledger-break {shlex.quote(str(self.project.root))} --actor <name> --reason \"…\"`")
        actor, reason = accept
        if not self.is_human(actor):
            raise EngineError(f"only a named human ({', '.join(self.humans)}) accepts a ledger break; '{actor}' is not one")
        if not reason.strip():
            raise EngineError("accepting a ledger break needs the human's reason (--reason)")
        recorded, end = int(tail[0]), self.ledger._last[0]
        rewritten = any(e["seq"] == recorded for e in self.ledger.events())   # the event is there, with another hash
        brk = LedgerBreak(actor=actor, reason=reason.strip(), at=now(), lost_after_seq=0 if rewritten else end,
                          recorded_seq=recorded, lost_hash=str(tail[1])[:16], problem=lost, resumes_at_seq=end + 1,
                          rechained=len(rechain or []))
        self.state.runtime.ledger_breaks.append(brk)
        self.ledger.append("ledger_break_accepted", **brk.model_dump())
        moved: dict[int, int] = {}
        for line in rechain or []:   # the last human action's events: committed with the state, re-chained after the break
            ev = json.loads(line)
            moved[ev["seq"]] = self.ledger.append(ev["type"], **ev["data"], rechained_from_seq=ev["seq"])["seq"]
        for d in self.state.history.decisions:   # a decision cites its ledger event: point it at the re-chained copy
            d.evidence = [f"ledger:{moved[int(x[7:])]}" if x.startswith("ledger:") and x[7:].isdigit() and int(x[7:]) in moved
                          else x for x in d.evidence]
        self._write_state()

    def _resume_fixups(self) -> None:
        """Recover from a process that died mid-step. Loading a healthy run changes nothing and writes nothing, so
        read-only commands (status, tasks, lineage) and refused commands leave the state and the ledger untouched."""
        fixed = self.controls.settle_after_crash()
        if fixed:
            self.ledger.append("controls_settled", docs=fixed)
        reset = []
        for nid, rt in self.state.runtime.nodes.items():
            if rt.status not in ACTIVE:
                continue
            reset.append(nid)
            node = self.node(nid)
            was = rt.status.value
            reverted = self._revert_interrupted_controls(nid, rt)
            rt.interruptions += 1
            msg = (f"The previous attempt (a{rt.attempt}) was interrupted: the process ended while the node was {was}. "
                   f"It does not count against the retry budget.")
            if reverted:
                msg += f" Its unaccepted edits to {', '.join(reverted)} were undone."
            rt.failures = [msg]
            self.state.history.revisions.append(Revision(node=nid, attempt=rt.attempt, reason="resume", detail=msg, at=now()))
            self.ledger.append("resume_reset", node=nid, attempt=rt.attempt, was=was, interruptions=rt.interruptions)
            if rt.interruptions >= node.retry.max_attempts:
                self._escalate(node, f"interrupted {rt.interruptions} times in a row", [msg])
            else:
                rt.status = NodeStatus.READY
        if not (fixed or reset):
            return
        if self.state.runtime.status not in (RunStatus.BLOCKED, RunStatus.RUN_PASS):
            self.state.runtime.status = RunStatus.RUNNING
        self.ledger.append("resumed", status=self.state.runtime.status.value, reset=reset, settled=fixed)
        self.save("resumed")

    def _revert_interrupted_controls(self, nid: str, rt: NodeRuntime) -> list[str]:
        """Undo control documents an interrupted attempt installed before it could pass."""
        out = []
        for doc, rec in self.state.controls.items():
            if len(rec.history) < 2 or rec.history[-1].node != nid:
                continue
            last = rec.history[-1]
            # by attempt when recorded: timestamps have 1-second resolution, and a node re-dispatched within the second
            # it last installed must not lose that (accepted) version
            mine = last.attempt == rt.attempt if last.attempt else bool(rt.started_at) and last.at >= rt.started_at
            if not mine:
                continue
            bad = rec.history.pop()
            prev = rec.history[-1]
            live = self.controls.path(doc)
            if live.exists():
                shutil.copyfile(live, self.controls.archive / f"{doc}.interrupted-{nid}-a{rt.attempt}.md")
            shutil.copyfile(self.project.root / prev.archived, live)
            rec.version, rec.accepted_sha256 = prev.version, prev.sha256
            self.ledger.append("interrupted_edit_undone", doc=doc, node=nid, discarded_version=bad.version)
            out.append(doc)
        return out

    # ------------------------------------------------------------------------------------------------ accessors
    def node(self, node_id: str) -> NodeDef:
        try:
            return self.idx.nodes[node_id]
        except KeyError:
            raise EngineError(f"unknown node {node_id}") from None

    def rt(self, node_id: str) -> NodeRuntime:
        return self.state.runtime.nodes[node_id]

    def current(self, key: str) -> list[ArtifactRecord]:
        return sorted((a for a in self.state.artifacts.values() if a.key == key and a.current), key=lambda a: a.created)

    def thresholds(self) -> dict[str, Any]:
        base = yaml.safe_load((PKG_ROOT / "config" / "defaults.yaml").read_text())["thresholds"]
        over = front_matter(self.controls.accepted_text("evaluation")).get("thresholds") or {}
        return _deep_merge(base, over)

    def is_human(self, actor: str) -> bool:
        return is_human(actor, self.humans, True)

    def _parse_time(self, value: str, what: str) -> dt.datetime:
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise EngineError(f"{what} must be an ISO datetime") from None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)

    def _authority(self, actor: str, action: str, node: str | None = None,
                   on_behalf_of: str | None = None) -> tuple[bool, str | None, str | None]:
        if self.is_human(actor):
            return True, None, None
        if action not in DELEGABLE_ACTIONS:
            raise EngineError(f"{action} is not delegable; only a named human ({', '.join(self.humans)}) may do it")
        if not on_behalf_of:
            raise EngineError(f"no delegation: {actor} is not a named human and --on-behalf-of was not provided")
        matches = [d for d in self.state.history.delegations if d.by == on_behalf_of and d.agent == actor]
        if not matches:
            raise EngineError(f"no active delegation for {actor} on behalf of {on_behalf_of}")
        if not self.is_human(on_behalf_of):   # the grantor left the project's humans list: their grants lapse with them
            raise EngineError(f"{on_behalf_of} is not a named human ({', '.join(self.humans)}), so nothing is done on "
                              "their behalf")
        now_utc = dt.datetime.now(dt.timezone.utc)
        revoked = [d for d in matches if d.revoked_at]
        unrevoked = [d for d in matches if not d.revoked_at]
        if not unrevoked and revoked:
            raise EngineError(f"delegation {revoked[-1].id} was revoked")
        unexpired = [d for d in unrevoked if self._parse_time(d.expires, f"delegation {d.id} expiry") > now_utc]

        def covers(d: Delegation) -> bool:
            return action in d.scope and (not d.nodes if node is None
                                          else (not d.nodes or node in d.nodes) and node not in d.except_nodes)
        lapsed = [d for d in unrevoked if d not in unexpired and covers(d)]
        if lapsed and not any(covers(d) for d in unexpired):   # the grant that would have covered it, and how it is
            d = lapsed[-1]                                     # renewed: a lapsed grant stopped a stakeholder's change (R2-30)
            raise EngineError(f"delegation {d.id} expired at {d.expires}; ask {d.by} to renew it "
                              f"(`{renew_command(d.model_dump(mode='json'))}`), or {d.by} takes the action directly")
        if not unexpired and unrevoked:
            raise EngineError(f"delegation {unrevoked[-1].id} expired at {unrevoked[-1].expires}, and none covered {action}")
        scoped = [d for d in unexpired if action in d.scope]
        if not scoped:
            raise EngineError(f"delegation for {actor} on behalf of {on_behalf_of} is out of scope for {action}")
        # a node list limits a grant to those gates: an action that names no node (a deferral, a risk, the config) is
        # covered only by a grant without one (independent audit #2: an N10-only grant could close a blocking defect)
        node_scoped = [d for d in scoped if (not d.nodes if node is None
                                             else (not d.nodes or node in d.nodes) and node not in d.except_nodes)]
        if not node_scoped:
            raise EngineError(f"delegation for {actor} on behalf of {on_behalf_of} is out of scope for {node}")
        chosen = node_scoped[-1]
        if action == "decide" and node == "n18_final_verification" and not getattr(chosen, "include_release", False):
            raise EngineError(f"delegation {chosen.id} does not include the release gate; {chosen.by} must decide N18")
        return False, chosen.by, chosen.id

    # ------------------------------------------------------------------------------------------------ readiness
    def _edge_satisfied(self, e) -> bool:
        if e.source == self.wf.start:
            return True
        rt = self.state.runtime.nodes.get(e.source)
        return bool(rt and rt.status == NodeStatus.PASSED and outcome_matches(e.when, rt.outcome))

    def ready_nodes(self) -> list[str]:
        out = []
        for nid in self.idx.order(set(self.idx.nodes)):
            rt = self.rt(nid)
            if rt.status not in RUNNABLE:
                continue
            ins = self.idx.flow_in(nid)
            if ins and all(self._edge_satisfied(e) for e in ins):
                out.append(nid)
        return out

    def _inflight(self) -> list[str]:
        return [n for n, rt in self.state.runtime.nodes.items() if rt.status in ACTIVE | {NodeStatus.WAITING_AGENT}]

    def conflict_keys(self, node: NodeDef) -> tuple[set[str], set[str], set[str]]:
        writes = (set(node.state_write) - REDUCER_PATHS) | {f"control:{d}" for d in node.controls.write}
        reads = {f"control:{d}" for d in control_reads(node)}
        return writes, reads, set(node.resources) & set(self.wf.policies.single_flight_resources)

    @staticmethod
    def _overlap(a: set[str], b: set[str]) -> bool:
        return any(x == y or x.startswith(y + ".") or y.startswith(x + ".") for x in a for y in b)

    def _conflicts(self, a: NodeDef, b: NodeDef) -> bool:
        wa, ra, sa = self.conflict_keys(a)
        wb, rb, sb = self.conflict_keys(b)
        return self._overlap(wa, wb) or bool(wa & rb) or bool(wb & ra) or bool(sa & sb)

    def select_batch(self, ready: list[str]) -> list[str]:
        """Up to parallel_limit ready nodes that neither write the same state or control document, nor read a document
        another writes, nor share a single-flight resource — with each other or with nodes still in flight."""
        busy = [self.node(n) for n in self._inflight()]
        batch: list[NodeDef] = []
        for nid in ready:
            n = self.node(nid)
            if any(self._conflicts(n, o) for o in busy + batch):
                continue
            batch.append(n)
            if len(batch) >= self.wf.policies.parallel_limit:
                break
        return [n.id for n in batch]

    # ------------------------------------------------------------------------------------------------ fingerprints
    def _file_sha(self, p: Path) -> str:
        """sha256 of a file, cached on its identity. ctime is part of the key: resetting a file's modification time
        after an edit (`touch -r`) changes its ctime, so the edit is still re-hashed."""
        st = p.stat()
        key = (st.st_mtime_ns, st.st_size, st.st_ino, st.st_ctime_ns)
        hit = self._hash_cache.get(str(p))
        if hit and hit[0] == key:
            return hit[1]
        sha = sha256_file(p)
        self._hash_cache[str(p)] = (key, sha)
        return sha

    def _tree_sha(self, path: Path) -> str:
        """tree_sha(path)[0], reusing cached file hashes: a directory artifact (the prototype build) is re-checked
        before every step, so an edit to one of its files after registration is caught like an edit to a file artifact."""
        return sha256_json([[str(p.relative_to(path)), self._file_sha(p)]
                            for p in sorted(x for x in path.rglob("*") if x.is_file() and not ignored_tree_noise(x))])

    def _input_hash(self, node: NodeDef, ref: str) -> Any:
        kind, _, arg = ref.partition(":")
        if kind == "state":
            return sha256_json(get_path(self.state, arg))
        if kind == "artifact":  # content, not ids: an identical re-run upstream must not force a re-run here
            mine = self.idx.descendants(node.id) | {node.id}
            return sorted(a.sha256 for a in self.current(arg) if a.node not in mine)
        if kind == "control":
            return self._control_hash(node, arg)
        if kind == "files":
            return [(rel(p, self.project.root), self._file_sha(p)) for p in glob_files(self.project.root, arg)]
        if kind == "defects":
            return sorted((d.id, d.status) for d in self.state.evaluation.defects
                          if d.traced_node == node.id and d.status in DEFECT_ACTIVE | {"in_rework"})
        if kind == "feedback":
            return sorted(f.id for f in self.state.evaluation.feedback if f.status == "open")
        if kind == "rework":
            return sorted(self.rt(node.id).rework)
        return None

    def _control_hash(self, node: NodeDef, doc: str) -> Any:
        """Hash of the parts of a control document written upstream of `node`. Sections owned by the node itself or
        by its descendants are feedback: feedback reaches a node only through a declared loop edge (which forces a
        re-run), so leaving it out keeps a downstream write from silently invalidating every upstream reader's memo."""
        rec = self.state.controls.get(doc)
        if rec is None:
            return None
        mine = self.idx.descendants(node.id) | {node.id}
        owners = self.idx.section_owners(doc)
        if "*" in owners:
            return "written-downstream" if owners["*"] in mine else rec.accepted_sha256
        skip = {sec for sec, owner in owners.items() if owner in mine}
        if not skip:
            return rec.accepted_sha256
        pre, secs = split_sections(self.controls.accepted_text(doc))
        kept = ([] if "_preamble" in skip else [pre.strip()]) + [body.strip() for title, body in secs if title not in skip]
        return sha256_json(kept)

    def judging_hash(self, node: NodeDef, leave_out: frozenset[str] = frozenset()) -> str:
        """How a node is judged: its rubric entries, the states of their rules, and the threshold sections its tools and
        rubrics read. Accepting a configuration re-judges every node whose hash moved (backlog B-03, vpg #59). `leave_out`:
        dimension ids to judge as if absent."""
        dims = [d for d in node_dimensions(node, self.rubrics) if d["id"] not in leave_out]
        th = self.thresholds()
        names = {d.get("check", {}).get("fn", "").split(":")[0] for d in dims} | set(node.evaluation)
        names |= {n.replace("-", "_") for n in names} | {n.rsplit("-", 1)[-1] for n in names}
        if node.run and node.run.tool:
            names.add(node.run.tool.split(":")[0])
        if node.kind == NodeKind.REVIEW:
            names.add("review")
        # what decides a verdict, not the prose around it: rewording an example must not re-ask a gate (audit #7)
        judged = [{k: d.get(k) for k in ("id", "level", "check")}
                  | ({"threshold": d.get("threshold")} if d.get("check", {}).get("type") == "review" else {}) for d in dims]
        return sha256_json({"dims": judged, "rules": {d["id"]: self.rule_states.get(d.get("rule", ""), "candidate") for d in dims},
                            "thresholds": {k: th[k] for k in sorted(names) if k in th}})

    def fingerprint(self, node: NodeDef, stable: bool = False) -> str:
        """Content fingerprint of everything a node's output depends on. `stable` leaves out the transient rework
        context (its own defect ids): a rework target is always forced to re-run, so the context only matters then."""
        prompt = PKG_ROOT / node.prompt
        refs = [r for r in node.inputs if not (stable and r.split(":", 1)[0] in ("rework", "defects"))]
        return sha256_json({
            "node": node.model_dump(mode="json", by_alias=True),
            "prompt": sha256_file(prompt) if prompt.is_file() else None,
            "inputs": {ref: self._input_hash(node, ref) for ref in refs},
            "controls": {d: self._control_hash(node, d) for d in control_reads(node)},
        })

    # ------------------------------------------------------------------------------------------------ the step
    def step(self) -> list[str]:
        rs = self.state.runtime
        if rs.status in (RunStatus.RUN_PASS, RunStatus.BLOCKED):
            return []
        self._note_code_change()
        self._repair_duplicate_defect_ids()
        migrated = self._migrate_defect_signatures()
        self._reopen_inputs_if_unfrozen()
        problems = self._integrity_problems()
        if problems:
            self._escalate_run("integrity", problems)
            return []
        changed_state = False
        if not self.state.inputs.frozen:  # until N02 freezes the inputs, the brief is whatever the file says now
            brief = self.project.root / "sources" / "brief.md"
            text = brief.read_text() if brief.is_file() else ""
            if text != self.state.inputs.brief:
                self.state.inputs.brief = text
                self.ledger.append("brief_updated", sha256=sha256_json(text))
                changed_state = True
        batch = self.select_batch(self.ready_nodes())
        if not batch:
            self._update_status()
            if changed_state or migrated:
                self.save("step")
            return []
        rs.batches += 1
        self.ledger.append("batch", n=rs.batches, nodes=batch)
        ctxs = [c for c in (self._prepare(nid) for nid in batch) if c is not None]
        self.save("dispatch")
        results = self._execute_all(ctxs)
        for ctx, res, err in results:
            if self.rt(ctx.node.id).status != NodeStatus.RUNNING:
                continue
            if err is not None:
                self._fail(ctx.node, self.rt(ctx.node.id), [err], ctx)
            elif res.pending:
                self.rt(ctx.node.id).status = NodeStatus.WAITING_AGENT
                self.ledger.append("task_issued", node=ctx.node.id, attempt=ctx.attempt, agent=ctx.node.agent)
            else:
                self._complete(ctx, res)
        self._update_status()
        self.save("step")
        return batch

    def run(self, max_steps: int = 500) -> dict[str, Any]:
        for _ in range(max_steps):
            if not self.step():
                break
        return self.status()

    def _prepare(self, nid: str) -> NodeContext | None:
        node, rt = self.node(nid), self.rt(nid)
        fp = self.fingerprint(node)
        if rt.status == NodeStatus.STALE and not rt.force_rerun and rt.passed_fingerprint == self.fingerprint(node, stable=True):
            rt.status = NodeStatus.PASSED
            rt.memo_hits += 1
            rt.rerun_reason = ""
            if not node.human_review.required or rt.outcome == "approved":
                self.controls.close_unlocks_for(nid, sorted(node.controls.lock_on_approval))
            self.ledger.append("memo_hit", node=nid, outcome=rt.outcome, fingerprint=fp[:16])
            return None
        rt.attempt += 1
        rt.status = NodeStatus.RUNNING
        rt.issued_judging, rt.issued_dims = self.judging_hash(node), self._dim_signatures(node)
        rt.token = secrets.token_hex(8)
        rt.fingerprint = fp
        rt.executed = False
        rt.started_at = now()
        work = self.project.root / "work" / nid / f"a{rt.attempt}"
        if work.exists():
            keep = [p for p in work.iterdir()]
            if keep:
                pre = work / ".pre-dispatch"
                pre.mkdir(exist_ok=True)
                moved = []
                for p in keep:
                    if p == pre:
                        continue
                    dest = pre / p.name
                    if dest.exists():
                        dest = pre / f"{p.name}.{secrets.token_hex(4)}"
                    shutil.move(str(p), dest)
                    moved.append(rel(dest, self.project.root))
                self.ledger.append("pre_dispatch_preserved", node=nid, attempt=rt.attempt, paths=moved)
                self.notices.append(f"{nid} a{rt.attempt}: moved pre-dispatch files to " + ", ".join(moved))
            else:
                shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)
        self.ledger.append("node_dispatched", node=nid, attempt=rt.attempt, fingerprint=fp[:16],
                           rework=rt.rework, retry_context=bool(rt.failures))
        return NodeContext(self, node, rt.attempt, work, rt.token, fp)

    def _execute_one(self, ctx: NodeContext) -> NodeResult:
        node = ctx.node
        t0 = time.monotonic()
        try:
            if node.kind == NodeKind.REVIEW and node.run and node.run.tool:
                ctx.precheck = self._call_tool(node.run.tool, ctx)
                self._save_precheck(ctx)
            if node.kind == NodeKind.TOOL:
                ctx.precheck = self._call_tool(node.run.tool, ctx)
                self._save_precheck(ctx)
                return NodeResult(outputs=dict(ctx.precheck.outputs), actor=f"tool:{node.run.tool}")
            return self.executor.execute(ctx)
        finally:
            ctx.work.joinpath(".duration").write_text(f"{time.monotonic() - t0:.3f}")

    def _execute_all(self, ctxs: list[NodeContext]) -> list[tuple[NodeContext, NodeResult | None, str | None]]:
        if not ctxs:
            return []
        out: dict[str, tuple[NodeContext, NodeResult | None, str | None]] = {}
        with cf.ThreadPoolExecutor(max_workers=min(len(ctxs), self.wf.policies.parallel_limit)) as pool:
            futs = {pool.submit(self._execute_one, c): c for c in ctxs}
            for fut in cf.as_completed(futs):
                c = futs[fut]
                try:
                    out[c.node.id] = (c, fut.result(), None)
                except FixtureError as exc:
                    out[c.node.id] = (c, None, str(exc))
                except Exception as exc:  # noqa: BLE001 - recorded as the attempt's failure, with a traceback on disk
                    (c.work / "error.log").write_text(traceback.format_exc())
                    out[c.node.id] = (c, None, f"{exc.__class__.__name__}: {exc} (see {rel(c.work / 'error.log', self.project.root)})")
        return [out[c.node.id] for c in ctxs]

    def _call_tool(self, fn: str, ctx: NodeContext) -> CheckResult:
        try:
            res = resolve_tool(fn)(ctx)
        except Exception as exc:  # noqa: BLE001
            (ctx.work / f"tool-error-{fn.replace(':', '-')}.log").write_text(traceback.format_exc())
            return CheckResult(errors=[f"{fn} raised {exc.__class__.__name__}: {exc}"])
        if not isinstance(res, CheckResult):
            return CheckResult(errors=[f"{fn} returned {type(res).__name__}, not a CheckResult"])
        return res

    def _precheck_path(self, ctx: NodeContext) -> Path:
        return self.pdg_dir / "prechecks" / ctx.node.id / f"a{ctx.attempt}.json"

    def _save_precheck(self, ctx: NodeContext) -> None:
        """The engine's copy (with the hash of every output the tool wrote) is the only one ever read back. The copy in
        the work folder is for the reviewer agent to read; editing it changes nothing."""
        data = ctx.precheck.to_dict()
        data["output_sha256"] = {k: tree_sha(Path(v))[0] for k, v in ctx.precheck.outputs.items() if Path(v).exists()}
        write_json_atomic(self._precheck_path(ctx), data)
        write_json_atomic(ctx.work / "precheck.json", ctx.precheck.to_dict())

    def _load_precheck(self, ctx: NodeContext) -> list[str]:
        """Load the engine's pre-check; return the tool outputs that changed after the tool ran."""
        p = self._precheck_path(ctx)
        if not p.exists():
            return []
        data = read_json(p)
        hashes = data.pop("output_sha256", {})
        ctx.precheck = CheckResult.from_dict(data)
        return [f"{k} ({rel(Path(v), self.project.root)})" for k, v in ctx.precheck.outputs.items()
                if not Path(v).exists() or tree_sha(Path(v))[0] != hashes.get(k)]

    # ------------------------------------------------------------------------------------------------ judging an attempt
    def _complete(self, ctx: NodeContext, res: NodeResult) -> None:
        rt = self.rt(ctx.node.id)
        rt.executed = True
        rt.status = NodeStatus.VALIDATING
        self.save("validating")
        snapshot = self.state.model_copy(deep=True)
        write_json_atomic(self._journal_path(), {"node": ctx.node.id, "attempt": ctx.attempt, "at": now(),
                                                 "state": snapshot.model_dump(mode="json")})
        self._judge_and_commit(ctx, res, snapshot)
        self.save("committed")
        self._journal_path().unlink(missing_ok=True)

    def _judge_and_commit(self, ctx: NodeContext, res: NodeResult, snapshot: ProjectState) -> None:
        node = ctx.node
        failures: list[str] = list(ctx.integrity)
        outputs = {**(ctx.precheck.outputs if ctx.precheck else {}), **res.outputs}
        regs, errs = self._register_outputs(ctx, outputs)
        failures += errs
        ctx.submitted = {k: self.project.root / r.path for k, r in regs.items()}
        if not failures:
            for o in node.outputs:
                if o.kind == "control" and o.key in ctx.submitted:
                    failures += self.controls.check_install(node.id, node.controls.write, o.doc, ctx.submitted[o.key])
        results: dict[str, CheckResult] = {}
        if ctx.precheck is not None and node.run and node.run.tool:
            results[node.run.tool] = ctx.precheck
            failures += ctx.precheck.errors
            if ctx.precheck.data.get("blocked"):
                self.state = snapshot
                self._escalate(node, f"tool cannot run: {ctx.precheck.data['blocked']}", ctx.precheck.errors or [])
                return
        review = None
        if not failures:
            for chk in node.completion:
                failures += self._run_check(chk, ctx, results)
        if not failures:
            failures += unreported_tool_dims(node, results, self.rubrics, self.rule_states)
        hook: CheckResult | None = None
        if not failures:
            if node.kind == NodeKind.REVIEW:
                own = set().union(*(r.own for r in results.values())) if results else set()
                _, _, blocking = evaluate_tool_dims(node, results, self.rubrics, self.rule_states, only=own)
                failures += blocking       # the reviewer's own artifact is wrong: it retries, nothing is routed (W35)
                if not failures:
                    review = self._review_record(ctx, results)
            else:
                _, _, blocking = evaluate_tool_dims(node, results, self.rubrics, self.rule_states)
                failures += blocking
        if not failures and node.kind == NodeKind.GATE and node.run and node.run.tool:
            hook = self._call_tool(node.run.tool, ctx)
            failures += hook.errors
            if not failures:
                hregs, herrs = self._register_outputs(ctx, hook.outputs, only=set(hook.outputs))
                failures += herrs
                regs.update(hregs)
                results[node.run.tool] = hook
                failures += unreported_tool_dims(node, {node.run.tool: hook}, self.rubrics, self.rule_states)
                _, _, blocking = evaluate_tool_dims(node, {node.run.tool: hook}, self.rubrics, self.rule_states)
                failures += blocking
        outcome = (hook.outcome if hook else None) or (ctx.precheck.outcome if node.kind == NodeKind.TOOL and ctx.precheck else None) or "pass"
        if not failures and not node.human_review.required and outcome not in node.outcomes:
            failures.append(f"outcome '{outcome}' is not one of {node.outcomes}")
        if not failures:
            try:
                self._commit(ctx, regs, review, hook or ctx.precheck, res)
            except (ValidationError, EngineError, ValueError, KeyError) as exc:
                failures.append(f"state update refused: {exc}")
        if failures:
            self.state = snapshot
            self._record_failed_artifacts(regs)
            self._fail(node, self.rt(node.id), failures, ctx)
            return
        rt = self.rt(node.id)
        data = dict((hook or ctx.precheck).data) if (hook or ctx.precheck) else {}
        if node.human_review.required:
            tool_records = []
            if results:
                records, _, _ = evaluate_tool_dims(node, results, self.rubrics, self.rule_states)
                tool_records = [f"{r.id}: {r.detail or r.evidence}" for r in records if r.check == "tool"]
            if hook and node.run and node.run.tool:
                records, _, _ = evaluate_tool_dims(node, {node.run.tool: hook}, self.rubrics, self.rule_states)
                tool_records += [f"{r.id}: {r.detail or r.evidence}" for r in records if r.check == "tool"]
            rt.tool_details = list(dict.fromkeys(x for x in tool_records if x.strip()))
            self.notices += [f"tool detail: {x}" for x in rt.tool_details]
        if node.human_review.required:
            self._await_human(node, rt, res, data)
        else:
            self._pass(node, rt, outcome, data)

    def _register_outputs(self, ctx: NodeContext, outputs: dict[str, str],
                          only: set[str] | None = None) -> tuple[dict[str, ArtifactRecord], list[str]]:
        node = ctx.node
        declared = {o.key: o for o in node.outputs}
        regs: dict[str, ArtifactRecord] = {}
        errs: list[str] = []
        for key in outputs:
            if key not in declared:
                errs.append(f"undeclared output '{key}' (declared: {', '.join(declared)})")
        lineage = sorted({a.id for ref in node.inputs if ref.startswith("artifact:")
                          for a in self.current(ref.split(':', 1)[1]) if a.node != node.id})
        for o in node.outputs:
            if only is not None and o.key not in only:
                continue
            if o.key not in outputs:
                if o.required and only is None and not self._produced_by_hook(node, o.key):
                    errs.append(f"missing required output '{o.key}'")
                continue
            src = Path(outputs[o.key])
            src = src if src.is_absolute() else ctx.work / src
            src = src.resolve()
            if not src.exists():
                errs.append(f"output '{o.key}' does not exist: {src}")
                continue
            try:
                src.relative_to(self.project.root)
            except ValueError:
                errs.append(f"output '{o.key}' lies outside the project: {src}")
                continue
            links = [rel(p, src) for p in (src.rglob("*") if src.is_dir() else []) if p.is_symlink()]
            if links:   # a link can lead outside the project, directly or through a linked directory: submit real files
                errs.append(f"output '{o.key}' contains symbolic links, which can point outside the project: {links[:5]}")
                continue
            dst = src
            try:
                src.relative_to(ctx.work.resolve())
            except ValueError:
                dst = ctx.work / (o.key + ("" if src.is_dir() else src.suffix))
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
                else:
                    shutil.copyfile(src, dst)
            if o.kind == "dir" and not dst.is_dir():
                errs.append(f"output '{o.key}' must be a directory")
                continue
            if o.kind != "dir" and not dst.is_file():
                errs.append(f"output '{o.key}' must be a file")
                continue
            if o.kind == "json" or o.schema_name:
                try:
                    data = json.loads(dst.read_text())
                    if o.schema_name:
                        ARTIFACT_MODELS[o.schema_name].model_validate(data)
                except (ValueError, ValidationError) as exc:
                    errs.append(f"output '{o.key}' fails schema '{o.schema_name or 'json'}': {str(exc)[:600]}")
                    continue
            sha, size = tree_sha(dst)
            rid = f"{node.id}/{o.key}/a{ctx.attempt}"
            regs[o.key] = ArtifactRecord(id=rid, key=o.key, node=node.id, attempt=ctx.attempt, kind=o.kind,
                                         path=rel(dst, self.project.root), sha256=sha, bytes=size, created=now(),
                                         inputs=lineage, build_version=self.state.build.version, current=False)
        return regs, errs

    def _produced_by_hook(self, node: NodeDef, key: str) -> bool:
        """Outputs written by a gate node's deterministic hook are registered after the agent's submission."""
        return node.kind == NodeKind.GATE and key in {"gaps", "gate_report", "learning_proposal"}

    def _record_failed_artifacts(self, regs: dict[str, ArtifactRecord]) -> None:
        for r in regs.values():
            r.current = False
            r.superseded_by = "failed-attempt"
            self.state.artifacts[r.id] = r

    def _run_check(self, chk, ctx: NodeContext, results: dict[str, CheckResult]) -> list[str]:
        if chk.type == "artifact":
            return [] if ctx.output(chk.key) is not None else [f"{chk.description} — artifact '{chk.key}' missing"]
        if chk.type == "tool":
            if chk.fn not in results:
                results[chk.fn] = self._call_tool(chk.fn, ctx)
            return list(results[chk.fn].errors)
        if chk.type == "state":
            val = get_path(self.state, chk.args.get("path", ""))
            return [] if val else [f"{chk.description} — state {chk.args.get('path')} is empty"]
        if chk.type == "review_complete":
            p = ctx.output(chk.key)
            if p is None:
                return [f"review '{chk.key}' missing"]
            missing = missing_review_dims(ctx.node, self.rubrics, json.loads(p.read_text()))
            return [f"MUST review dimension {m} left unscored" for m in missing]
        if chk.type == "interpretation_complete":
            return self._interpretation_gaps(ctx)
        return [f"unknown check type {chk.type}"]

    def _interpretation_gaps(self, ctx: NodeContext) -> list[str]:
        p = ctx.output("interpretation")
        if p is None:
            return ["interpretation missing"]
        interp = Interpretation.model_validate(json.loads(p.read_text()))
        errs = []
        mapped = {m.feedback_id for m in interp.feedback if m.defect_ids or m.dismissed_reason}
        mapped |= {fid for d in interp.defects for fid in d.from_feedback}
        for f in self.state.evaluation.feedback:
            if f.status == "open" and f.id not in mapped:
                errs.append(f"feedback {f.id} ('{f.text[:60]}') is neither mapped to a defect nor dismissed")
        covered = {x for d in interp.defects for x in d.from_findings} | {d.signature for d in interp.defects}
        current = {f"{f.node}:{f.signature}": f for f in self._current_findings()}
        for a in interp.answered_findings:   # an answer replaces a defect only for a review finding, with evidence (W22)
            f = current.get(a.finding)
            if f is None:
                errs.append(f"answer to {a.finding}: no current finding has that node:signature")
            elif f.by == "tool":
                errs.append(f"answer to {a.finding}: a tool finding cannot be answered away; fix the build or the tool")
            elif not (a.evidence.strip() and a.checked_by.strip() and a.reason.strip()):
                errs.append(f"answer to {a.finding} needs its reason, its evidence and who checked")
            else:
                covered.add(a.finding)
        for f in self._current_findings():
            if f.blocking and f.by != "tool" and f"{f.node}:{f.signature}" not in covered and f.signature not in covered:
                errs.append(f"blocking {f.by} finding {f.node}:{f.signature} has no defect")
        for d in interp.defects:
            if d.traced_node not in self.idx.nodes:
                errs.append(f"defect {d.id} traces to unknown node {d.traced_node}")
            if not d.smallest_fix.strip() or not d.acceptance_check.strip():
                errs.append(f"defect {d.id} needs a smallest fix and an acceptance check")
        return errs

    def _current_findings(self) -> list[FindingRecord]:
        out = []
        for r in self.idx.reviewer_nodes():
            rv = self.latest_review(r)
            if rv and rv.build_version == self.state.build.version:
                out += rv.findings
        return out

    def latest_review(self, node_id: str):
        return latest_reviews_by_node(self.state.evaluation.reviews, {node_id}).get(node_id)

    def _review_record(self, ctx: NodeContext, results: dict[str, CheckResult]):
        node = ctx.node
        rkey = next((c.key for c in node.completion if c.type == "review_complete"), None)
        agent_review = json.loads(ctx.output(rkey).read_text()) if rkey and ctx.output(rkey) else None
        extra = []
        vp = ctx.output("validation")
        if vp is not None:
            agent_review, extra = validation_findings(ValidationDoc.model_validate(json.loads(vp.read_text())),
                                                      agent_review)
        return merge_review(node, ctx.attempt, self.state.build.version, results, agent_review, self.rubrics,
                            self.rule_states, float(self.thresholds()["review"]["score_threshold"]), extra)

    # ------------------------------------------------------------------------------------------------ committing
    def _commit(self, ctx: NodeContext, regs: dict[str, ArtifactRecord], review, result: CheckResult | None,
                res: NodeResult) -> None:
        node = ctx.node
        kinds = {o.key: o.kind for o in node.outputs}
        for key, rec in regs.items():
            for old in self.current(key):
                if kinds.get(key) == "control" and old.node != node.id:
                    continue   # two nodes' copies of one shared document are two records, both current (FR-11)
                old.current = False
                old.superseded_by = rec.id
            rec.current = True
            self.state.artifacts[rec.id] = rec
        writes = []
        for o in node.outputs:
            if o.key in regs and o.state_fields:
                doc = json.loads((self.project.root / regs[o.key].path).read_text())
                for field, path in o.state_fields.items():
                    value = doc if field == "." else doc.get(field)
                    if value is not None:
                        writes.append((path, value))
        if writes:  # typed writes: apply to a plain copy, then re-validate the whole state against the model
            data = self.state.model_dump(mode="json", by_alias=True)
            for path, value in writes:
                if isinstance(get_path(data, path), list) and not isinstance(value, list):
                    value = [value]
                set_path(data, path, value)
            self.state = ProjectState.model_validate(data)
        self._engine_managed_outputs(node, regs)
        if review is not None:
            self.state.evaluation.reviews.append(review)
        if "validation" in regs:
            self._validation_feedback(ctx, regs["validation"])
        if result is not None:
            for t in result.data.get("test_results", []):
                self.state.evaluation.test_results.append(TestResult(node=node.id, build_version=self.state.build.version,
                                                                     at=now(), **t))
            self._gate_side_effects(node, result)
        self.state = ProjectState.model_validate(self.state.model_dump(mode="json", by_alias=True))
        for o in node.outputs:
            if o.kind == "control" and o.key in regs:
                self.controls.install(node.id, o.doc, self.project.root / regs[o.key].path)

    def _engine_managed_outputs(self, node: NodeDef, regs: dict[str, ArtifactRecord]) -> None:
        if "prototype_build" in regs:
            self.state.build.code_artifacts.append(regs["prototype_build"].id)
        if "content" in regs:
            self.state.build.content_artifacts.append(regs["content"].id)
        if "prototype" in regs:
            rec = regs["prototype"]
            root = self.project.root / rec.path
            manifest = root / "build-manifest.json"
            entry = json.loads(manifest.read_text())["entry"] if manifest.exists() else "index.html"
            stack = json.loads(manifest.read_text()).get("stack", []) if manifest.exists() else []
            b = self.state.build
            prev = self.state.artifacts.get(b.prototype.artifact) if b.prototype else None
            if prev is not None and prev.sha256 == rec.sha256:
                # A rebuild that changed nothing is not a new version, and the build of record stays the one that was
                # reviewed: `build.prototype` is unchanged, so the reviewers' inputs are too and their memo holds, and
                # the release packages exactly the folder they saw. The new record (same bytes) is kept for lineage.
                rec.build_version = b.version
                self.ledger.append("build_unchanged", version=b.version, artifact=rec.id, sha256=rec.sha256,
                                   build_of_record=prev.id)
                return
            b.version += 1
            rec.build_version = b.version
            entry_path = root / entry
            b.prototype = PrototypeRef(version=b.version, artifact=rec.id, entry=rel(entry_path, self.project.root),
                                       sha256=sha256_file(entry_path) if entry_path.is_file() else rec.sha256, stack=stack)
            self.state.history.versions.append({"version": b.version, "node": node.id, "attempt": rec.attempt,
                                                "sha256": rec.sha256, "at": now()})
            self.ledger.append("build_version", version=b.version, artifact=rec.id, sha256=rec.sha256)

    def _validation_feedback(self, ctx: NodeContext, rec: ArtifactRecord) -> None:
        """Record the round in research.validation_findings (simulated unless a real session took part), and each
        participant's own words as feedback, flagged simulated when their session was."""
        from .tools.validation import metrics
        doc = ValidationDoc.model_validate(json.loads((self.project.root / rec.path).read_text()))
        m = metrics(doc)
        self.state.research.validation_findings.append(ValidationFinding(
            at_version=self.state.build.version, participants=len(doc.sessions),
            simulated=not m["real_sessions"], task_success_rate=float(m["success_rate"]),
            mean_seq=m["mean_seq"], summary=doc.summary))
        simulated = {s.participant: s.simulated for s in doc.sessions}
        for f in doc.findings:
            if f.by != "human":
                continue
            sim = simulated.get(f.participant, True)
            self.add_feedback(f.message, actor=f"participant:{f.participant or 'unknown'}", at=f.location,
                              severity=f.severity, simulated=sim, human=not sim, reopen=False)

    def _gate_side_effects(self, node: NodeDef, result: CheckResult) -> None:
        d = result.data
        if node.gate == "freeze_inputs" and result.outcome == "pass":
            if d.get("sources") is not None:
                self.state.inputs.sources = [Source.model_validate(s) for s in d["sources"]]
            self.state.inputs.frozen = True
            self.state.inputs.inputs_sha256 = self._inputs_sha()
            self.ledger.append("inputs_frozen", sha256=self.state.inputs.inputs_sha256, sources=len(self.state.inputs.sources))
        if node.gate == "regeneration_plan" and d.get("targets"):
            gates = len(self.state.evaluation.gates)
            if self.state.runtime.planned_gate != gates:   # a plan re-run for the same gate (after an unblock) is the same cycle
                self.state.runtime.rework_cycles += 1
                self.state.runtime.planned_gate = gates
            ids = {x for v in d.get("defects_by_target", {}).values() for x in v}
            from .gating import fix_marker
            for df in self.state.evaluation.defects:
                if df.id in ids:
                    df.status = "in_rework"
                    df.rework_version = self.state.build.version
                    df.attempts_at_start = fix_marker(self, df)   # the correction starts now
                    df.history.append(f"{now()} in rework (cycle {self.state.runtime.rework_cycles})")
            self.ledger.append("regeneration_plan", cycle=self.state.runtime.rework_cycles, targets=d["targets"],
                               defects=sorted(ids))
        if node.gate == "learning" and d.get("proposal"):
            self.state.knowledge.proposal = d["proposal"]

    def _inputs_sha(self) -> str:
        items = []
        for s in self.state.inputs.sources:
            if s.path:
                p = self.project.root / s.path
                items.append([s.id, s.path, sha256_file(p) if p.is_file() else None])
            else:
                items.append([s.id, s.url, None])
        return sha256_json({"brief": self.state.inputs.brief, "sources": items})

    # ------------------------------------------------------------------------------------------------ human gates
    def _gate_outputs(self, node: NodeDef) -> dict[str, str]:
        """Output key → sha256 of what an approver of `node` sees now; a control output counts as its whole accepted
        document, so another writer's change to a shared document counts as a change too."""
        out: dict[str, str] = {}
        for o in node.outputs:
            if o.kind == "control" and o.doc in self.state.controls:
                if self.state.controls[o.doc].accepted_sha256:
                    out[o.key] = self.state.controls[o.doc].accepted_sha256
                continue
            mine = [a for a in self.current(o.key) if a.node == node.id]
            if mine:
                out[o.key] = mine[-1].sha256
        return out

    def _await_human(self, node: NodeDef, rt: NodeRuntime, res: NodeResult, data: dict[str, Any]) -> None:
        rt.passed_judging = self.judging_hash(node)   # judged now, even before the human decides (audit #8)
        rt.judged_checks = self._checks_record(node)   # its checks ran now, not when a person approves (review 3, I1)
        rt.status = NodeStatus.WAITING_HUMAN
        rt.outcome = None
        rt.failures, rt.streak = [], 0   # this attempt passed its checks; a rejection sets its own retry context (W16)
        prev = next((a for a in reversed(self.state.history.approvals) if a.node == node.id and a.decision == "approved"
                     and a.outputs), None)
        unchanged, changed = None, None
        rt.gate_note = ""
        if prev is not None:   # asked again: say what changed since the approval, so a re-ask is one informed step
            current = self._gate_outputs(node)
            changed = sorted(k for k in set(prev.outputs) | set(current) if prev.outputs.get(k) != current.get(k))
            who = f"{prev.actor}{f' on behalf of {prev.on_behalf_of} ({prev.delegation})' if prev.on_behalf_of else ''}"
            if changed:
                rt.gate_note = f"asked again; since {who} approved it at {prev.at[:19]}, these outputs changed: {', '.join(changed)}"
            else:
                unchanged = {"at": prev.at, "actor": prev.actor, "on_behalf_of": prev.on_behalf_of,
                             "delegation": prev.delegation}
                rt.gate_note = f"asked again with outputs byte-identical to the version {who} approved at {prev.at[:19]}"
            if rt.rerun_reason:
                rt.gate_note += f"; it re-ran because {rt.rerun_reason[:240]}"
            fixes = self._cycle_fixes(node)
            if fixes:   # the approver checks what the cycle changes against what this node's work asserts (N-19)
                rt.gate_note += (f"; this rework cycle fixes {', '.join(d['id'] for d in fixes)}: check that nothing "
                                 "approved here still asserts what those fixes change (the task packet lists them)")
        self.ledger.append("awaiting_human", node=node.id, decision=node.human_review.decision,
                           approver=node.human_review.approver, outcomes=node.human_review.outcomes,
                           unchanged_since=unchanged, changed_outputs=changed, rerun_reason=rt.rerun_reason or None)
        self._checkpoint("awaiting_human", node.id)
        if self.project.dry_run:
            scripted = res.decision or {}
            decision = scripted.get("decision", node.human_review.dry_run_decision)
            reason = scripted.get("reason", "dry run: scripted decision by the dry-run actor (not a human approval)")
            self.decide(node.id, decision, self.wf.policies.dry_run_actor, reason, scripted.get("feedback"), _auto=True)

    # ------------------------------------------------------------------------------------------------ passing & routing
    def _checks_record(self, node: NodeDef) -> PassedChecks:
        """Which code and configuration a node's tool checks ran with: a later change to either is a check upgrade its
        verdict never saw (W65). Taken when the checks run: a node a person approves later keeps it, even if an upgrade
        landed while it waited. Not changed when accept-config lets a verdict stand: its checks did not run again."""
        tools = any(d.get("check", {}).get("type") == "tool" for d in node_dimensions(node, self.rubrics))
        return PassedChecks(**checks_fingerprint(self.state.runtime.code_parts, self.state.runtime.config_parts),
                            git_state=package_git_state(PKG_ROOT),
                            recheckable=tools and node.kind != NodeKind.GATE)

    def _pass(self, node: NodeDef, rt: NodeRuntime, outcome: str, data: dict[str, Any]) -> None:
        approved = rt.status == NodeStatus.WAITING_HUMAN   # its checks ran when it began to wait: keep that record
        rt.status = NodeStatus.PASSED
        rt.force_rerun = False   # cleared on passing, not on dispatch: an invalidation mid-attempt must not memo-skip it
        rt.outcome = outcome
        rt.passed_fingerprint = self.fingerprint(node, stable=True)   # after its own writes: what a memo check will see
        rt.passed_judging = self.judging_hash(node)
        rt.passed_dims, rt.rejudge = self._dim_signatures(node), None
        # approved: the record its checks made when it began to wait (a memo hit keeps the last pass's; review 4)
        rt.passed_checks = rt.judged_checks if approved else self._checks_record(node)
        rt.judged_checks = None
        rt.streak = 0
        rt.interruptions = 0
        rt.failures = []
        rt.rework = []
        rt.rerun_reason, rt.gate_note = "", ""
        rt.passed_attempt = rt.attempt
        rt.passed_controls = {d: self.state.controls[d].version for d in sorted(set(control_reads(node)) | set(node.controls.write))
                              if d in self.state.controls}
        rt.finished_at = now()
        dur = self.project.root / "work" / node.id / f"a{rt.attempt}" / ".duration"
        rt.duration_s = float(dur.read_text()) if dur.exists() else None
        self.ledger.append("node_passed", node=node.id, attempt=rt.attempt, outcome=outcome)
        self._checkpoint("pass", node.id)
        targets = data.get("targets") or []
        loop_targets: list[str] = []
        fired: list[str] = []
        for e in self.idx.outgoing[node.id]:
            if e.kind == EdgeKind.FLOW or not outcome_matches(e.when, outcome, targets):
                continue
            if e.kind == EdgeKind.ESCALATE:
                self._escalate(node, f"{e.id}: outcome '{outcome}'", data.get("report") or [f"outcome {outcome}"], edge=e.id)
                return
            n = self.state.runtime.loop_traversals.get(e.id, 0) + 1
            if n > (e.max_traversals or 0):
                self._escalate(node, f"loop {e.id} ({node.id} → {e.target}) exhausted its {e.max_traversals} traversals",
                               data.get("report") or [f"outcome {outcome}"], edge=e.id)
                return
            self.state.runtime.loop_traversals[e.id] = n
            loop_targets.append(e.target)
            fired.append(e.id)
        if loop_targets:
            rt.passed_fingerprint = None   # an outcome that loops back was judged wrong: never memo-restore it
            self.ledger.append("loop_fired", edges=fired, source=node.id, outcome=outcome, targets=loop_targets)
            self.invalidate(loop_targets, f"{', '.join(fired)} from {node.id} ({outcome})",
                            defects_by_target=data.get("defects_by_target"), force=True, context=data.get("context"))
        elif not node.human_review.required or outcome == "approved":
            self.controls.close_unlocks_for(node.id, sorted(node.controls.lock_on_approval))

    def invalidate(self, targets: list[str], reason: str, defects_by_target: dict[str, list[str]] | None = None,
                   force: bool = True, context: list[str] | None = None) -> list[str]:
        tset = set(targets)
        desc: set[str] = set()
        for t in tset:
            desc |= self.idx.descendants(t)
        desc -= tset
        touched = []
        self._resolve_parked([n for n in self.idx.order(tset | desc) if self.rt(n).parked], f"invalidated: {reason}")
        for t in self.idx.order(tset):
            rt = self.rt(t)
            rt.status = NodeStatus.STALE
            rt.force_rerun = force
            rt.token = None
            rt.rerun_reason = reason
            if defects_by_target is not None:
                rt.rework = list(defects_by_target.get(t, []))
            if context:
                rt.failures = list(context)
            self.state.history.revisions.append(Revision(node=t, attempt=rt.attempt, reason="rework" if defects_by_target
                                                         else "loop", detail=reason, at=now()))
            touched.append(t)
        for d in self.idx.order(desc):
            rt = self.rt(d)
            if rt.status in (NodeStatus.PLANNED,):
                continue
            rt.status = NodeStatus.STALE
            rt.token = None
            ups = sorted(t for t in tset if d in self.idx.descendants(t))   # only the targets it depends on (W15)
            rt.rerun_reason = f"upstream {', '.join(ups)} re-opened: {reason}"
            touched.append(d)
        self.ledger.append("invalidated", targets=sorted(tset), descendants=sorted(desc), reason=reason)
        return touched

    def _fail(self, node: NodeDef, rt: NodeRuntime, failures: list[str], ctx: NodeContext | None = None) -> None:
        rt.streak += 1
        rt.failures = failures[:25]
        rt.status = NodeStatus.ITERATE
        rt.finished_at = now()
        self.state.history.revisions.append(Revision(node=node.id, attempt=rt.attempt, reason="retry",
                                                     detail="; ".join(failures[:3])[:500], at=now()))
        self.ledger.append("node_failed", node=node.id, attempt=rt.attempt, streak=rt.streak, failures=failures[:8])
        self._checkpoint("fail", node.id)
        if rt.streak >= node.retry.max_attempts:
            self._escalate(node, f"{rt.streak} consecutive failed attempts (retry budget {node.retry.max_attempts})", failures)

    def _escalate(self, node: NodeDef, reason: str, report: list[str], edge: str | None = None) -> None:
        rt = self.rt(node.id)
        rt.status = NodeStatus.BLOCKED
        n = sum(1 for e in self.state.runtime.escalations if e.node == node.id) + 1
        path = self.pdg_dir / "escalations" / f"{node.id}-{n}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        open_defects = [d for d in self.state.evaluation.defects if d.status in DEFECT_ACTIVE | {"in_rework"}]
        lines = [f"# Escalation — {node.id} ({node.name})", "",
                 f"> **TL;DR:** {reason}. The run is BLOCKED until {node.escalation.to} acts.", "",
                 f"- **When:** {now()}", f"- **Edge:** {edge or '—'}", f"- **Attempts:** {rt.attempt} (streak {rt.streak})",
                 f"- **Escalate to:** {node.escalation.to} — {node.escalation.report}", "", "## What failed", ""]
        lines += [f"- {r}" for r in report[:30]] or ["- (no detail)"]
        lines += ["", "## Rework history", ""]
        gates = self.state.evaluation.gates
        if gates:   # the trend decides whether another cycle is worth funding (backlog N-02)
            lines += ["Blocking defects by gate: " + " → ".join(f"{len(g.blocking_defects)} (v{g.build_version})"
                                                               for g in gates), ""]
        lines += [f"- cycle {g.cycle} · v{g.build_version} · {g.outcome}: {'; '.join(g.reasons)[:300]}"
                  for g in gates] or ["- none"]
        lines += ["", "## Open defects", ""]
        lines += [f"- {d.id} `{d.signature}` {d.severity} {d.status} → {d.traced_node} (failed corrections: {d.failures})"
                  for d in open_defects] or ["- none"]
        lines += ["", "## What unblocks it", "", self._unblock_advice(node, edge), "",
                  f"```bash\npython -m pdg unblock {shlex.quote(str(self.project.root))} {node.id} --actor <human> "
                  "\n```", ""]
        path.write_text("\n".join(lines))
        self.state.runtime.escalations.append(Escalation(id=f"{node.id}-{n}", node=node.id, reason=reason,
                                                         report=rel(path, self.project.root), at=now()))
        self.state.runtime.status = RunStatus.BLOCKED
        self.ledger.append("escalated", node=node.id, reason=reason, report=rel(path, self.project.root))
        self._checkpoint("escalated", node.id)

    def _unblock_advice(self, node: NodeDef, edge: str | None) -> str:
        if node.gate == "freeze_inputs":
            return "Register the missing source (then unblock), or waive a resolvable gap by name: `--waive <gap>`."
        if node.gate == "review_gate":
            return ("Resolve what needs a human: approve a change request for a locked document "
                    "(`pdg change-request … --doc <doc> --writer <node>`), re-trace an unroutable defect, or reset the budget "
                    "(`--reset-budget`) after deciding another cycle is worth it. The reset covers the rework cycles, each "
                    "defect's failed corrections and the rework edges' traversals.")
        if edge and edge.startswith("E") and self.idx.nodes[node.id].human_review.required:
            return "The approver rejected this node repeatedly: agree the direction with Wei, then unblock to re-open it."
        return "Fix the cause named above (or supply what the node lacked), then unblock to give the node a fresh retry budget."

    def _escalate_run(self, what: str, problems: list[str]) -> None:
        if any(e.open and e.node == "run" and e.reason.startswith(what) for e in self.state.runtime.escalations):
            self.state.runtime.status = RunStatus.BLOCKED
            return
        n = sum(1 for e in self.state.runtime.escalations if e.node == "run") + 1
        path = self.pdg_dir / "escalations" / f"run-{n}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        q = shlex.quote(str(self.project.root))
        path.write_text("\n".join([f"# Run escalation — {what}", "", f"> **TL;DR:** the run cannot continue: {what}.", ""]
                                  + [f"- {p}" for p in problems] + ["", "A named human resolves it with one of these, "
                                  "after checking the cause:", "", "```bash", "# a configuration change you reviewed",
                                  f"python -m pdg accept-config {q} --actor <human> --reason \"…\"",
                                  "# a hand-edited control document, back to its accepted version",
                                  f"python -m pdg unblock {q} run --actor <human> --restore-controls",
                                  "# any other cause, once fixed", f"python -m pdg unblock {q} run --actor <human>",
                                  "```", ""]))
        self.state.runtime.escalations.append(Escalation(id=f"run-{n}", node="run", reason=f"{what}: {problems[0][:200]}",
                                                         report=rel(path, self.project.root), at=now()))
        self.state.runtime.status = RunStatus.BLOCKED
        self.ledger.append("escalated", node="run", reason=what, problems=problems[:10])
        self.save("escalated")

    def _end_reached(self) -> bool:
        ins = [e for e in self.idx.incoming[self.wf.end] if e.kind == EdgeKind.FLOW]
        return bool(ins) and all(self._edge_satisfied(e) for e in ins)

    def _update_status(self) -> None:
        rs = self.state.runtime
        if any(e.open for e in rs.escalations):
            rs.status = RunStatus.BLOCKED
            return
        if self._end_reached():
            if rs.status != RunStatus.RUN_PASS:
                rs.status = RunStatus.RUN_PASS
                self.ledger.append("run_pass", build_version=self.state.build.version, cycles=rs.rework_cycles,
                                   judged_by=release_checks(self.state))
            return
        statuses = {rt.status for rt in rs.nodes.values()}
        if self.ready_nodes() and self.select_batch(self.ready_nodes()):
            rs.status = RunStatus.RUNNING
        elif NodeStatus.WAITING_HUMAN in statuses:
            rs.status = RunStatus.WAITING_HUMAN
        elif NodeStatus.WAITING_AGENT in statuses:
            rs.status = RunStatus.WAITING_AGENT
        elif statuses & ACTIVE:
            rs.status = RunStatus.RUNNING
        else:
            waiting = [f"{n}: {self.rt(n).status.value}" for n in self.idx.nodes if self.rt(n).status in RUNNABLE]
            self._escalate_run("no-progress", ["nothing is ready or in flight and END is not reached"] + waiting[:10])

    def _integrity_problems(self, ignore_docs: set[str] | None = None) -> list[str]:
        out = []
        if self._config_fingerprint() != self.state.runtime.config_sha256:
            out.append(f"configuration drift: {self._config_drift()[1]}. The workflow, rules, rubrics, defaults or project "
                       "config changed since the run started (a named human reviews the change and runs `pdg accept-config`)")
        if self.state.inputs.frozen and self._inputs_sha() != self.state.inputs.inputs_sha256:
            out.append("a frozen input (the brief or a registered source) changed after N02 froze it")
        out += self.controls.drift(ignore=ignore_docs)
        for a in self.state.artifacts.values():
            if not a.current:
                continue
            p = self.project.root / a.path
            if not p.exists():
                out.append(f"artifact {a.id} is missing from disk")
            elif (self._file_sha(p) if p.is_file() else self._tree_sha(p)) != a.sha256:
                out.append(f"artifact {a.id} was modified after registration")
        return out

    # ------------------------------------------------------------------------------------------------ commands
    def submit(self, node_id: str, outputs: dict[str, str], token: str, actor: str) -> dict[str, Any]:
        node, rt = self.node(node_id), self.rt(node_id)
        self.notices = []
        self._note_code_change()   # the ledger names the code before it records a verdict made with it (review S4)
        self._repair_duplicate_defect_ids()
        self._reopen_inputs_if_unfrozen()
        if rt.status != NodeStatus.WAITING_AGENT:
            raise EngineError(f"{node_id} is {rt.status.value}, not waiting for a submission")
        if token != rt.token:
            raise StaleSubmission(f"token {token!r} is not the current dispatch token for {node_id} a{rt.attempt} "
                                  "(a newer packet superseded it; read `pdg tasks`)")
        declared = {o.key for o in node.outputs}
        unknown = sorted(set(outputs) - declared)
        if unknown:
            raise EngineError(f"unknown output key(s) {unknown}; {node_id} declares {sorted(declared)}")
        if self._migrate_defect_signatures():
            self.save("defect_migration")
        work = self.project.root / "work" / node_id / f"a{rt.attempt}"
        ctx = NodeContext(self, node, rt.attempt, work, rt.token, rt.fingerprint or "")
        changed = self._load_precheck(ctx)
        tool_keys = sorted(set(outputs) & set(ctx.precheck.outputs)) if ctx.precheck else []
        if tool_keys:
            raise EngineError(f"{', '.join(tool_keys)}: written by the engine's own check; submit only your outputs")
        resolved = self._resolve_submission(outputs, work)            # refuses a missing or outside path, changing nothing
        malformed = self._schema_refusals(node, resolved) or self._wrong_build(node, resolved)
        if malformed:
            raise EngineError("not accepted, and no attempt was used: " + "; ".join(malformed) +
                              f" (check a file first with `pdg check-output {node_id} <key> <file>`)")
        human_preconditions = self._human_precondition_refusals(node, resolved)
        if human_preconditions:
            raise EngineError("not accepted, and no attempt was used: " + "; ".join(human_preconditions))
        live = self._live_control_outputs(node, resolved)
        problems = self._integrity_problems(ignore_docs=set(live.values()))
        if problems:   # the node keeps its packet and token; resubmit after a named human resolves the escalation
            # parked, not dropped: if resolving the block withdraws this node (a re-judge), a reviewer's findings are
            # still recorded; no attempt is used (field run W42)
            rt.parked = {"outputs": resolved, "actor": actor, "at": now(), "token": token,
                         "build_version": self.state.build.version,   # an edit after parking is caught (review S1)
                         "sha256": {k: self._path_sha(Path(v)) for k, v in resolved.items()}}
            self.ledger.append("submission_parked", node=node_id, attempt=rt.attempt, actor=actor, outputs=sorted(resolved))
            self._escalate_run("integrity", problems)
            self.save("parked")
            return {"node": node_id, "status": self.state.runtime.status.value, "outcome": None, "parked": True,
                    "failures": ["not accepted — the run is blocked: " + p for p in problems],
                    "attempts_left": max(0, node.retry.max_attempts - rt.streak)}
        lock_only = self._lock_only_refusals(node, resolved)
        if lock_only:
            raise EngineError("not accepted, and no attempt was used: " + "; ".join(lock_only))
        resolved = self._adopt_live_control_edits(node, resolved, live, work)   # nothing can refuse the submission now
        if changed:
            ctx.integrity = [f"tool outputs changed after the engine's check ran: {', '.join(changed)} "
                             "(a submission cannot change a tool verdict; the next attempt re-runs the check)"]
        rt.status = NodeStatus.RUNNING
        rt.parked = rt.carried = None
        self.ledger.append("node_submitted", node=node_id, attempt=rt.attempt, actor=actor, outputs=sorted(resolved))
        self._complete(ctx, NodeResult(outputs=resolved, actor=actor))
        self._update_status()
        self.save("submit")
        rt = self.rt(node_id)
        return {"node": node_id, "status": rt.status.value, "outcome": rt.outcome, "failures": rt.failures,
                "attempts_left": max(0, node.retry.max_attempts - rt.streak), "notices": list(self.notices)}

    def _human_precondition_refusals(self, node: NodeDef, resolved: dict[str, str]) -> list[str]:
        if not any(d["id"] == "PLN-FIDELITY-GATE" for d in node_dimensions(node, self.rubrics)):
            return []
        plan_key = next((o.key for o in node.outputs if o.schema_name == "plan" and o.key in resolved), None)
        if plan_key is None:
            return []
        from .artifacts import PrototypePlan
        from .tools.plan import _human_acceptance
        doc = PrototypePlan.model_validate(json.loads(Path(resolved[plan_key]).read_text()))
        if doc.fidelity not in ("mid", "high"):
            return []
        refusals = []
        statuses = {a.assumption_id: a.status for a in doc.riskiest_assumptions}
        for a in self.state.research.assumptions:
            if not a.riskiest or statuses.get(a.id) != "accepted_risk":
                continue
            who = _human_acceptance(self.state, a.id, self.humans)
            if who is None or "re-accept" in who:
                actor = (self.humans[0] if self.humans else "Wei")
                refusals.append(f"{a.id} needs human-only accept-risk for N10 fidelity gate: "
                                f"`pdg accept-risk {shlex.quote(str(self.project.root))} {a.id} --actor {actor}`")
        return refusals

    def _schema_refusals(self, node: NodeDef, resolved: dict[str, str]) -> list[str]:
        """Schema errors in the submitted files. A malformed file is a slip, not a quality failure, so `submit` refuses
        it and the node keeps its attempt (field run 2, R2-02)."""
        out = []
        for o in node.outputs:
            if o.key in resolved:
                out += output_problems(o, Path(resolved[o.key]))
        return out

    def _wrong_build(self, node: NodeDef, resolved: dict[str, str]) -> list[str]:
        """A review that names a build other than the one under review judged something else: the first project's
        reviewers could only write "on build v5" in free text (backlog N-06). Refused, like any slip."""
        proto = self.state.build.prototype
        out = []
        for o in node.outputs:
            if o.schema_name == "review" and o.key in resolved and proto is not None:
                named = str(json.loads(Path(resolved[o.key]).read_text()).get("build") or "").strip().lower()
                if named and (len(named) < 12 or not proto.sha256.lower().startswith(named)):
                    out.append(f"output '{o.key}' reviews build {named[:16]}, but the build under review is "
                               f"v{proto.version} ({proto.sha256[:16]}): review that build, or leave `build` out")
        return out

    def _resolve_submission(self, outputs: dict[str, str], work: Path) -> dict[str, str]:
        resolved = {}
        for k, v in outputs.items():
            p = Path(v)
            p = (p if p.is_absolute() else work / p).resolve()
            if not p.exists():
                raise EngineError(f"output {k}: {p} does not exist")
            try:
                p.relative_to(self.project.root.resolve())
            except ValueError:
                raise EngineError(f"output {k}: {p} is outside the project") from None
            resolved[k] = str(p)
        return resolved

    def _live_control_outputs(self, node: NodeDef, resolved: dict[str, str]) -> dict[str, str]:
        """Output key → document, for control outputs submitted as the live `controls/<doc>.md` itself."""
        return {o.key: o.doc for o in node.outputs if o.kind == "control" and o.key in resolved
                and o.doc in node.controls.write and Path(resolved[o.key]) == self.controls.path(o.doc).resolve()}

    def _lock_only_refusals(self, node: NodeDef, resolved: dict[str, str]) -> list[str]:
        problems = []
        for o in node.outputs:
            if o.kind != "control" or o.key not in resolved:
                continue
            rec = self.state.controls[o.doc]
            if (Path(resolved[o.key]) == self.controls.path(o.doc).resolve() and rec.status == "locked"
                    and rec.locked_node != node.id and rec.unlocked_for != node.id
                    and node.id not in rec.unlocked_for_nodes):
                text, _ = self.controls.merge(node.id, o.doc, Path(resolved[o.key]))
                if sha256_bytes(text.encode()) != rec.accepted_sha256:
                    problems.append(f"{o.doc}.md is locked ({rec.locked_by}); a named human must approve a change request first "
                                    f"(`pdg change-request <project> --doc {o.doc} --actor <human>`)")
                    continue
            checks = self.controls.check_install(node.id, node.controls.write, o.doc, Path(resolved[o.key]))
            if checks and all(" is locked " in c for c in checks):
                problems += checks
        return problems

    def _adopt_live_control_edits(self, node: NodeDef, resolved: dict[str, str], live: dict[str, str],
                                  work: Path) -> dict[str, str]:
        """An agent that edited `controls/<doc>.md` in place and submitted that path: its text becomes the submission (a
        new copy in its work folder, never overwriting an earlier one) and the live file goes back to the accepted
        version, so the usual install checks (ownership, locks, append-only) decide what lands. Called only after every
        refusal check has passed, so a refused command never changes a file."""
        out = dict(resolved)
        for key, doc in live.items():
            copy = work / f"{doc}.submitted-{now().replace(':', '')}.md"
            shutil.copyfile(self.controls.path(doc), copy)
            self.controls.path(doc).write_text(self.controls.accepted_text(doc))
            out[key] = str(copy)
        if live:
            self.ledger.append("live_control_edit_submitted", node=node.id, docs=sorted(live.values()))
        return out

    # ------------------------------------------------------------------------------------------------ persistence
    def save(self, event: str = "") -> None:
        if self._in_action:
            return   # a human action commits once, when it completes
        self._write_state()

    def _write_state(self) -> None:
        """Save state.json only if it is exactly as this engine last read or wrote it (see util.ConcurrentChange), and
        record the ledger's last event, so a ledger that later lacks it is known to have lost events."""
        if file_identity(self.project.state_path) != self._state_identity:
            raise ConcurrentChange(f"{self.project.state_path} changed since this command opened the run (another pdg "
                                   "process or a hand edit); nothing was written. Retry the command")
        self.state.runtime.ledger_tail = list(self.ledger._last)
        write_json_atomic(self.project.state_path, self.state)
        self._state_identity = file_identity(self.project.state_path)

    @contextmanager
    def _action(self, event: str, stamp: dict[str, Any] | None = None) -> Iterator[None]:
        """One human action is one durable unit. Its state changes stay in memory and its ledger events are buffered;
        the state is saved once at the end (carrying the events, write-ahead), and only then are the events written. If
        anything fails first, nothing is saved and the in-memory state is put back, so a retry never records the same
        decision twice and a crash never leaves half a decision (a gate passed but its loop not fired)."""
        if self._in_action:
            yield
            return
        snapshot = self.state.model_copy(deep=True)
        self._in_action, self._undo = True, []
        old_stamp = dict(self.ledger.stamp)
        if stamp:
            self.ledger.stamp = {**self.ledger.stamp, **stamp}
        try:
            with self.ledger.deferred() as lines:
                yield
                self._in_action = False
                self.state.runtime.pending_ledger = list(lines)
                self._write_state()
        except BaseException as exc:
            self.state = snapshot
            failed = []
            for undo in reversed(self._undo):   # e.g. a rollback's restored documents go back; each one runs regardless
                try:
                    undo()
                except Exception as err:
                    failed.append(f"{type(err).__name__}: {err}")
            if failed:
                exc.add_note("could not undo part of this action (check these files by hand): " + "; ".join(failed))
            raise
        finally:
            self.ledger.stamp = old_stamp
            self._in_action, self._undo = False, []
        committed = self.state.runtime.pending_ledger
        try:
            self.ledger.write_lines(committed)
        except Exception as exc:
            raise LedgerBehind(f"the {event} was saved, but its {len(committed)} ledger event(s) could not be written "
                               f"({exc}). They are kept in the state and written by the next command that changes the run "
                               "(for example `pdg run`); don't repeat the action") from exc
        self.state.runtime.pending_ledger = []   # persisted with the next save

    def _checkpoint(self, event: str, node_id: str | None) -> None:
        seq = len(self.state.history.checkpoints) + 1
        path = self.pdg_dir / "checkpoints" / f"{seq:05d}-{event}-{node_id or 'run'}.json"
        self.state.history.checkpoints.append(CheckpointRef(seq=seq, event=event, node=node_id,
                                                            path=rel(path, self.project.root), at=now()))
        write_json_atomic(path, self.state)
        self.save(event)
