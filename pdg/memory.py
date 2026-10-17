"""Governed memory: the reusable rule base and its evidence-gated lifecycle.

    candidate → validated → approved → adopted → monitored → revised | retired
                     ▲                                          │
                     └────────── (a revised rule re-validates) ─┘

Gates (a refused transition raises MemoryRefusal — CLI exit code 3):
  validated  needs a check (tool fn, rubric dimension, or test id) and ≥ 1 evidence ref plus validation evidence
  approved   needs a named human (agents and dry-run actors are refused)
  adopted    needs an approved rule and `adopted_in` (the rubric or config it now lives in)
  monitored  needs ≥ 1 observation from a run after adoption
  revised    needs a reason and evidence; a named human when the rule is approved, adopted or monitored; the previous
             statement is kept in `previous_versions`, and the rule goes back through validation
  retired    needs a reason and evidence; a named human when the rule is approved, adopted or monitored
Every write bumps the rule-base version, archives the previous file under knowledge/history/, and appends one line to
knowledge/rules-changelog.jsonl. Protected scopes (product truth, requirements, evidence, approved design principles)
are never changed by a learning proposal.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .util import PKG_ROOT, is_human_name, now, read_json, sha256_file, write_json_atomic
from .human_recording import recording, validate_human_words

DEFAULT_RULES = PKG_ROOT / "knowledge" / "rules.json"
STATES = ["candidate", "validated", "approved", "adopted", "monitored", "revised", "retired"]
HUMAN_GUARDED = {"approved", "adopted", "monitored"}
ALLOWED = {
    "candidate": {"validated", "retired"},
    "validated": {"approved", "revised", "retired"},
    "approved": {"adopted", "revised", "retired"},
    "adopted": {"monitored", "revised", "retired"},
    "monitored": {"revised", "retired"},
    "revised": {"validated", "retired"},
    "retired": set(),
}


class MemoryRefusal(Exception):
    """A governance rule refused the change. Nothing was written."""


def is_human(actor: str, humans: list[str], human_flag: bool) -> bool:
    """A named human on the project's list, never an agent or dry-run actor in any spelling (`Agent:x`, `DRY-RUN`)."""
    if not human_flag or not actor or not is_human_name(actor):
        return False
    return actor in humans


class RuleBase:
    def __init__(self, path: str | Path = DEFAULT_RULES, humans: list[str] | None = None):
        self.path = Path(path)
        self.data: dict[str, Any] = read_json(self.path)
        self.humans = humans or ["Wei"]

    # ------------------------------------------------------------------------------------------------ read side
    @property
    def rules(self) -> list[dict[str, Any]]:
        return self.data["rules"]

    @property
    def version(self) -> str:
        return self.data["version"]

    def sha256(self) -> str:
        return sha256_file(self.path)

    def get(self, rule_id: str) -> dict[str, Any]:
        for r in self.rules:
            if r["id"] == rule_id:
                return r
        raise MemoryRefusal(f"unknown rule {rule_id}")

    def states(self) -> dict[str, str]:
        return {r["id"]: r["lifecycle"]["state"] for r in self.rules}

    def summary(self) -> dict[str, Any]:
        by_state: dict[str, list[str]] = {s: [] for s in STATES}
        for r in self.rules:
            by_state[r["lifecycle"]["state"]].append(r["id"])
        awaiting = [r["id"] for r in self.rules if r["lifecycle"]["state"] == "validated"]
        unconfirmed = [r["id"] for r in self.rules
                       if r["lifecycle"]["state"] in HUMAN_GUARDED and not r.get("confirmed_by_wei", False)]
        return {"version": self.version, "rules": len(self.rules), "by_state": {k: v for k, v in by_state.items() if v},
                "awaiting_human_approval": awaiting, "seed_approvals_awaiting_confirmation": unconfirmed,
                "amendments_awaiting_confirmation": self.pending_amendments()}

    def pending_amendments(self) -> list[str]:
        """Rules an agent amended since the last human decision on them, with the amendment marked as awaiting Wei's
        confirmation (backlog D8). The amendment is enforced; confirming it records that it is Wei's decision."""
        out = []
        for r in self.rules:
            if r["lifecycle"]["state"] not in HUMAN_GUARDED:   # a rule not yet approved: approving it covers its check
                continue
            h = r["lifecycle"]["history"]
            last_human = max((i for i, e in enumerate(h) if e.get("human")), default=-1)
            if any(e.get("awaits_confirmation") for e in h[last_human + 1:]):
                out.append(r["id"])
        return out

    # ------------------------------------------------------------------------------------------------ write side
    def _write(self, change: dict[str, Any]) -> None:
        hist = self.path.parent / "history"
        hist.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.path, hist / f"rules-v{self.version}.json")
        major, minor, patch = (int(x) for x in self.version.split("."))
        self.data["version"] = f"{major}.{minor}.{patch + 1}"
        self.data["updated"] = now()
        write_json_atomic(self.path, self.data)
        line = {"at": now(), "version": self.data["version"], **change}
        with (self.path.parent / "rules-changelog.jsonl").open("a") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    def transition(self, rule_id: str, to: str, by: str, human: bool = False, evidence: list[str] | None = None,
                   reason: str = "", adopted_in: str = "", statement: str | None = None,
                   check: dict[str, Any] | None = None, recorded_by: str | None = None,
                   source: str = "", interprets: bool = False) -> dict[str, Any]:
        """`check` (validation only) names the executable check a rule gains: `{"fn": …, "dimensions": […]}` or
        `{"test": …}`. A candidate from a learning proposal has none until it is validated."""
        rule = self.get(rule_id)
        cur = rule["lifecycle"]["state"]
        if check and to != "validated":
            raise MemoryRefusal(f"{rule_id}: a check is attached only when the rule is validated")
        if to not in STATES:
            raise MemoryRefusal(f"unknown state {to}")
        if to not in ALLOWED[cur]:
            raise MemoryRefusal(f"{rule_id}: {cur} → {to} is not a lifecycle transition (allowed: {sorted(ALLOWED[cur])})")
        evidence = list(evidence or [])
        rec = recording(by, recorded_by, source) if human else {"recorded_by": recorded_by or by, "source": source}
        if reason:
            reason = validate_human_words(reason, "rule transition reason")
        named = is_human(by, self.humans, human)
        if to == "validated":
            chk = {**(rule.get("check") or {}), **{k: v for k, v in (check or {}).items() if v}}
            if not (chk.get("fn") or chk.get("dimensions") or chk.get("test")):
                raise MemoryRefusal(f"{rule_id}: validation needs a check (tool fn, rubric dimension or test id)")
            if not rule.get("evidence"):
                raise MemoryRefusal(f"{rule_id}: validation needs ≥ 1 evidence ref")
            if not evidence:
                raise MemoryRefusal(f"{rule_id}: validation needs validation evidence (a test id or a run)")
        if to == "approved" and not named:
            raise MemoryRefusal(f"{rule_id}: approval needs a named human ({', '.join(self.humans)}); '{by}' is not one")
        if to == "adopted" and not (adopted_in or rule.get("adopted_in")):
            raise MemoryRefusal(f"{rule_id}: adoption needs adopted_in (the rubric or config the rule lives in)")
        if to == "monitored":
            adopted_at = next((h.get("at", "") for h in reversed(rule["lifecycle"]["history"])
                               if h.get("state") == "adopted"), "")
            post_adoption = [o for o in rule.get("observations", []) if o.get("at", "") > adopted_at]
            if not post_adoption:
                raise MemoryRefusal(f"{rule_id}: monitoring needs ≥ 1 observation from a run after adoption")
        if to in ("revised", "retired"):
            if not reason or not evidence:
                raise MemoryRefusal(f"{rule_id}: {to} needs a reason and evidence")
            if cur in HUMAN_GUARDED and not named:
                raise MemoryRefusal(f"{rule_id}: a {cur} rule is {to} only by a named human")
        if to == "revised":
            if not statement:
                raise MemoryRefusal(f"{rule_id}: a revision needs the new statement")
            rule.setdefault("previous_versions", []).append({"statement": rule["statement"], "state": cur, "at": now()})
            rule["statement"] = statement
        if to == "adopted" and adopted_in:
            rule["adopted_in"] = adopted_in
        if to == "validated" and check:
            rule["check"] = chk
        rule["lifecycle"]["state"] = to
        rule["lifecycle"]["history"].append({"state": to, "at": now(), "by": by, "human": named,
                                             "evidence": evidence, "reason": reason, **rec, "interprets": interprets})
        if to == "approved" and named:
            rule["confirmed_by_wei"] = True
        self._write({"change": "transition", "rule": rule_id, "from": cur, "to": to, "by": by, "human": named,
                     "reason": reason, "evidence": evidence, **rec, "interprets": interprets})
        return rule

    def seed_approvals(self) -> list[str]:
        """Rules that are enforced on a seed approval alone: approved, adopted or monitored, not yet confirmed by Wei."""
        return [r["id"] for r in self.rules
                if r["lifecycle"]["state"] in HUMAN_GUARDED and not r.get("confirmed_by_wei", False)]

    def confirm_many(self, rule_ids: list[str], by: str, human: bool, reason: str = "",
                     evidence: list[str] | None = None, recorded_by: str | None = None,
                     source: str = "", interprets: bool = False) -> list[dict[str, Any]]:
        """Wei confirms seed approvals, as one decision and one version. Every rule is checked before anything is
        written, so one invalid id refuses the whole batch."""
        if not is_human(by, self.humans, human):
            raise MemoryRefusal(f"confirmation needs a named human ({', '.join(self.humans)})")
        rec = recording(by, recorded_by, source)
        if reason:
            reason = validate_human_words(reason, "rule confirmation reason")
        if not rule_ids:
            raise MemoryRefusal("nothing to confirm")
        rules = [self.get(rid) for rid in rule_ids]
        amended = set(self.pending_amendments())
        for r in rules:
            if r["lifecycle"]["state"] not in HUMAN_GUARDED:
                raise MemoryRefusal(f"{r['id']} is {r['lifecycle']['state']}; only approved rules can be confirmed")
            if r.get("confirmed_by_wei") and r["id"] not in amended:
                raise MemoryRefusal(f"{r['id']} is already confirmed by Wei")
        for r in rules:
            what = "the amendment" if r.get("confirmed_by_wei") else "the seed approval"
            r["confirmed_by_wei"] = True
            r["lifecycle"]["history"].append({"state": r["lifecycle"]["state"], "at": now(), "by": by, "human": True,
                                              "evidence": list(evidence or []),
                                              "reason": reason or f"Wei confirmed {what}: now a human decision",
                                              **rec, "interprets": interprets})
        self._write({"change": "confirm", "rules": list(rule_ids), "by": by, "reason": reason,
                     "evidence": list(evidence or []), **rec, "interprets": interprets})
        return rules

    def confirm(self, rule_id: str, by: str, human: bool) -> dict[str, Any]:
        """Wei confirms a seed approval that was derived from his own recorded words."""
        return self.confirm_many([rule_id], by, human)[0]

    def apply_proposal(self, proposal: dict[str, Any], approved_by: str, human: bool,
                       recorded_by: str | None = None, source: str = "", interprets: bool = False) -> dict[str, Any]:
        """Apply a learning proposal (N19). Observations are recorded on existing rules; new candidates are added as
        `candidate`. A proposal item that targets a protected scope is refused, and so is any non-human applier."""
        if not is_human(approved_by, self.humans, human):
            raise MemoryRefusal(f"a learning proposal is applied only by a named human ({', '.join(self.humans)})")
        rec = recording(approved_by, recorded_by, source)
        protected = set(self.data.get("protected_scopes", []))
        for item in proposal.get("candidates", []) + proposal.get("observations", []):
            target_scope = item.get("target_scope") or item.get("category")
            if target_scope in protected:
                raise MemoryRefusal(f"proposal item targets protected scope '{target_scope}': refused")
        applied = {"observations": 0, "candidates": 0, "skipped": []}
        ids = {r["id"] for r in self.rules}
        for ob in proposal.get("observations", []):
            if ob.get("rule") not in ids:
                applied["skipped"].append(ob.get("rule"))
                continue
            rule = self.get(ob["rule"])
            # dated by the run that made it (the proposal's time), not by when it was applied: monitoring needs an
            # observation from a run after adoption
            rule.setdefault("observations", []).append({"run": proposal.get("run", ""),
                                                        "at": str(proposal.get("created") or now()), "applied_at": now(),
                                                        "fired": ob.get("fired", False), "helped": ob.get("helped"),
                                                        "evidence": ob.get("evidence", []),
                                                        **{k: ob[k] for k in ("defects", "resolved", "open", "lesson_helped")
                                                           if k in ob}})
            applied["observations"] += 1
        for c in proposal.get("candidates", []):
            if c.get("id") in ids:
                applied["skipped"].append(c["id"])
                continue
            self.rules.append({
                "id": c["id"], "statement": c["statement"], "category": c.get("category", "evidence_and_process"),
                "target_scope": c.get("target_scope") or c.get("category", "evidence_and_process"),
                "scope": c.get("scope", "stable"), "basis": "observed-pattern", "origin": c.get("origin", "learning proposal"),
                "evidence": c.get("evidence", []), "evidence_class": c.get("evidence_class", "inferred"),
                "check": c.get("check", {}), "threshold": c.get("threshold", ""), "calibration_pending": True,
                "lifecycle": {"state": "candidate", "history": [{"state": "candidate", "at": now(), "by": approved_by,
                                                                 "human": True, "evidence": c.get("evidence", []),
                                                                 "reason": "added from a learning proposal",
                                                                 **rec, "interprets": interprets}]},
                "adopted_in": "", "observations": [], "previous_versions": [], "confirmed_by_wei": False,
            })
            ids.add(c["id"])
            applied["candidates"] += 1
        self._write({"change": "apply_proposal", "run": proposal.get("run", ""), "by": approved_by, **applied,
                     **rec, "interprets": interprets})
        return applied
