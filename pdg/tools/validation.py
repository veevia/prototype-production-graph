"""N14: the moderator guide (pre-check) and validation metrics that never count simulated sessions as evidence."""

from __future__ import annotations

import re
from statistics import mean

from ..artifacts import ValidationDoc
from ..context import CheckResult, NodeContext


def prepare(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    plan = ctx.state.build.plan
    lines = ["# Moderator guide", "", "> Read each task aloud. Do not demonstrate. After each task ask the Single Ease Question:",
             "> *“Overall, how difficult or easy was the task to complete?”* (1 = very difficult … 7 = very easy).", "",
             "Record every session honestly: participant role and an anonymised id, whether it was simulated, and per task "
             "success, time and SEQ. A simulated session is never user evidence.", ""]
    for s in (plan.scenarios if plan else []):
        lines += [f"## {s.id} — {s.name}", "", f"- **Flow:** {s.flow_id}", f"- **Success looks like:** {s.success}",
                  f"- **Expected path (moderator only):** {len(s.steps)} steps", ""]
    path = ctx.out("moderator-guide.md")
    path.write_text("\n".join(lines))
    res.outputs["moderator_guide"] = str(path)
    return res


def metrics(doc: ValidationDoc) -> dict:
    real = [s for s in doc.sessions if not s.simulated]
    use = real or doc.sessions
    tasks = [t for s in use for t in s.tasks]
    rate = (sum(t.success for t in tasks) / len(tasks)) if tasks else 0.0
    seqs = [t.seq for t in tasks if t.seq is not None]
    return {"real_sessions": len(real), "simulated_sessions": len(doc.sessions) - len(real), "tasks": len(tasks),
            "success_rate": round(rate, 3), "mean_seq": round(mean(seqs), 2) if seqs else None,
            "basis": "real sessions" if real else "SIMULATED sessions only — not user evidence"}


def _parse_success_threshold(raw: str) -> float | None:
    """A task-success threshold as a fraction: "80%", "4 of 5", "4/5", "≥ 0.8" or a bare "0.8". None when it states no
    rate unambiguously (an id such as S-01 is never read as a number): the caller then fails loudly."""
    pct = re.search(r"(\d+(?:\.\d+)?)\s*%", raw)
    if pct:
        return float(pct.group(1)) / 100
    ratio = re.search(r"(?<![\w-])(\d+)\s*(?:of|/|out\s+of)\s*(\d+)\b", raw)
    if ratio and int(ratio.group(2)) > 0:
        return int(ratio.group(1)) / int(ratio.group(2))
    num = re.search(r"(?:≥|>=|>|at\s+least|minimum|min\.?)\s*(\d+(?:\.\d+)?)\b", raw, re.I) \
        or re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*", raw)
    if not num:
        return None
    value = float(num.group(1))
    return value if value <= 1 else None   # "≥ 4 participants" is a count, and "90" could be 90% or 90 tasks: ask


def check(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = ValidationDoc.model_validate(ctx.json("validation"))
    plan = ctx.state.build.plan
    known = {s.id for s in (plan.scenarios if plan else [])}
    unknown = sorted({t.scenario_id for s in doc.sessions for t in s.tasks if t.scenario_id not in known})
    if unknown:
        res.errors.append(f"tasks on unknown scenarios: {unknown}")
    if not doc.sessions:
        res.errors.append("no sessions recorded (record real sessions, or simulated ones flagged as simulated)")
        return res
    m = metrics(doc)
    t = ctx.thresholds["validation"]
    target = t["min_task_success"]
    target_source = "default 0.8"
    unparseable: str | None = None
    for c in (plan.test_criteria if plan else []):
        if "success" in c.metric.lower():
            parsed = _parse_success_threshold(c.threshold)
            if parsed is None:
                unparseable = c.threshold
            else:
                target, target_source = parsed, c.threshold
            break
    if unparseable:
        res.dim("VAL-TASK-SUCCESS", False,
                f"could not parse task success threshold {unparseable!r}; success {m['success_rate']:.0%} ({m['basis']})")
    else:
        res.dim("VAL-TASK-SUCCESS", m["success_rate"] >= target,
                f"success {m['success_rate']:.0%} ≥ {target:.0%}? ({m['basis']}; threshold {target_source})")
    res.dim("VAL-SEQ", m["mean_seq"] is not None and m["mean_seq"] >= t["min_mean_seq"],
            f"mean SEQ {m['mean_seq']} (target {t['min_mean_seq']}; {m['basis']})")
    # structural, not a word search (field run W34): each session states `simulated`, the metrics exclude simulated
    # sessions by construction, and the engine labels a simulated session's findings itself when it stores them. What
    # can still go wrong is a finding whose participant has no recorded session: nobody can tell if it was simulated.
    recorded = {s.participant for s in doc.sessions}
    unknown = sorted({f.participant for f in doc.findings if f.participant and f.participant not in recorded})
    evidence = (f"{m['real_sessions']} real, {m['simulated_sessions']} simulated sessions; metrics use {m['basis']}; "
                "the engine labels simulated sessions' findings")
    if unknown:
        evidence += f"; findings name participants with no recorded session, so whether they were simulated is unknown: {unknown}"
    res.dim("VAL-SIMULATED-FLAGGED", not unknown, evidence, own=True)
    res.data["metrics"] = m
    return res
