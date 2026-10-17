#!/usr/bin/env python3
"""Authoring script for the dry-run fixtures (the scripted agent outputs of the FICTIONAL example).

    python3 fixtures/_author.py      # from examples/coa-review/

Each fixture is what an agent would submit for one node attempt: JSON artifacts, control documents, and optionally
commands to run first (the prototype build). The story the fixtures tell:
  - N01 attempt 1 misses a design authority → N02 reports a resolvable gap → the intake loop (E03) → N01 attempt 2.
  - N11 attempt 1 is a first draft with an overlay: status chips use an undeclared token pairing (a real contrast
    failure that axe measures) and the decision panel sits above the comparison.
  - N14 attempt 1 records a SIMULATED QA-lead concern about the layout (labelled simulated — not user evidence).
  - N16 attempt 1 traces the concern to N08 (redesign) and the tool's contrast findings to N11 (redevelopment).
  - Attempt 2 of N08/N10/N11 fixes both; N16 attempt 2 finds nothing blocking; the run passes.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE.parents[2] / "templates" / "control"


def w(node: str, attempt: int, name: str, content) -> None:
    d = HERE / node / f"attempt-{attempt}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, (dict, list)):
        p.write_text(json.dumps(content, indent=1, ensure_ascii=False) + "\n")
    else:
        p.write_text(content if content.endswith("\n") else content + "\n")


def fixture(node: str, attempt: int, outputs: dict, run: list | None = None, extra: str = "") -> None:
    lines = [f"# {node} attempt {attempt} — scripted agent output for the fictional example (dry run)"]
    if run:
        lines.append("run:")
        for cmd in run:
            lines.append("  - [" + ", ".join(json.dumps(a) for a in cmd) + "]")
    lines.append("outputs:")
    for k, v in outputs.items():
        lines.append(f"  {k}: {json.dumps(v)}")
    if extra:
        lines.append(extra)
    w(node, attempt, "fixture.yaml", "\n".join(lines))


def fm(doc: str, extra: str = "") -> str:
    return f"---\ndoc: {doc}\nstatus: filled\nproject: Lot Release Workbench (fictional example)\n{extra}---\n\n"


# ------------------------------------------------------------------------------------------------ N01 intake
SOURCES = [
    {"id": "S-01", "kind": "brief", "title": "Brief (fictional)", "path": "sources/brief.md", "evidence": "reported",
     "notes": "The requester's words, verbatim"},
    {"id": "S-02", "kind": "interview", "title": "Reviewer interviews — synthesis", "path": "sources/research/reviewer-interviews.md",
     "evidence": "observed", "notes": "Fictional research: 5 reviewers + the QA lead"},
    {"id": "S-03", "kind": "analytics", "title": "Time study, 40 lots", "path": "sources/research/time-study.csv",
     "evidence": "observed", "notes": "Fictional research"},
    {"id": "S-04", "kind": "research", "title": "Paper-prototype test", "path": "sources/research/paper-prototype-test.md",
     "evidence": "observed", "notes": "Fictional research: 5 reviewers, 3 paper lots"},
    {"id": "S-05", "kind": "spec", "title": "Lot release SOP (excerpt)", "path": "sources/process/lot-release-sop.md",
     "evidence": "reported"},
    {"id": "S-06", "kind": "spec", "title": "Ingredient specifications", "path": "sources/specs/ingredient-specs.json",
     "evidence": "observed"},
]
DESIGN_SOURCE = {"id": "S-07", "kind": "design-system", "title": "Fabrikam Quality UI guide (excerpt)",
                 "path": "sources/design/fabrikam-quality-ui.md", "evidence": "reported"}
Q1 = {"id": "Q-01", "question": "Can the plant's LIMS export certificate values as structured data?", "blocking": False,
      "owner": "LIMS owner (fictional)", "light": "yellow", "trigger": "The LIMS owner confirms the export format",
      "expiry": "2026-10-31"}
fixture("n01_context_intake", 1, {"sources": "sources.json", "intake_notes": "intake-notes.md"})
w("n01_context_intake", 1, "sources.json", {"sources": SOURCES, "open_questions": [Q1]})
w("n01_context_intake", 1, "intake-notes.md", "# Intake notes\n\nSix sources registered. MISSING: a design-system or brand authority "
  "for the plant's tools — asked the requester.")
fixture("n01_context_intake", 2, {"sources": "sources.json", "intake_notes": "intake-notes.md"})
w("n01_context_intake", 2, "sources.json", {"sources": SOURCES + [DESIGN_SOURCE], "open_questions": [Q1]})
w("n01_context_intake", 2, "intake-notes.md", "# Intake notes (loop 1)\n\nResolved gap G-DESIGN-AUTHORITY: registered the "
  "Fabrikam Quality UI guide (S-07).")

# ------------------------------------------------------------------------------------------------ N02 evidence
EVIDENCE = [
    ("E-01", "4 of 5 reviewers re-key certificate values from the PDF into a spreadsheet before comparing them with the specification", ["S-02"], "observed", "I type every number twice"),
    ("E-02", "The median review takes 11 minutes per lot (n = 40); re-keying is about 6 of them", ["S-03"], "observed", ""),
    ("E-03", "3 of 4 out-of-spec lots were missed on first review (37 of 40 lots correct first time)", ["S-03"], "observed", ""),
    ("E-04", "Reviewers want each value next to its limit before deciding", ["S-02"], "observed", "I need to see the number next to the limit, not scroll between them"),
    ("E-05", "The SOP requires a written rationale for every hold or reject, attributable to a named reviewer with a time", ["S-05"], "reported", ""),
    ("E-06", "Unreadable values are escalated by phone to the QA lead, with no record", ["S-02"], "observed", "I only hear about unreadable certificates when someone calls me"),
    ("E-07", "In the paper test, 4 of 5 reviewers released a compliant lot from the derived verdict without re-keying", ["S-04"], "observed", ""),
    ("E-08", "Supplier notices are drafted by the reviewer and sent by the supplier-quality manager", ["S-02", "S-05"], "reported", ""),
    ("E-09", "The QA lead agreed the lot-release flow and that the tool never releases a lot itself", ["S-04"], "observed", ""),
    ("E-10", "Plant tablets have no internet access; tools must run offline", ["S-05"], "reported", ""),
    ("E-11", "Reviewers handle 15–20 lots a shift", ["S-03", "S-01"], "observed", ""),
]
E12 = ("E-12", "Status is shown as icon + text + colour; red is reserved for failures", ["S-07"], "reported", "")
INSIGHTS = [
    {"id": "I-01", "statement": "Re-keying is both the time sink and the error source", "evidence_ids": ["E-01", "E-02", "E-03"], "confidence": "high"},
    {"id": "I-02", "statement": "Reviewers trust a derived verdict when they can see the value next to its limit", "evidence_ids": ["E-04", "E-07"], "confidence": "medium"},
    {"id": "I-03", "statement": "Escalations for unreadable values are invisible today", "evidence_ids": ["E-06"], "confidence": "medium"},
    {"id": "I-04", "statement": "Every decision must be attributable and explained; sending stays with supplier quality", "evidence_ids": ["E-05", "E-08"], "confidence": "high"},
]
ASSUMPTIONS = [
    {"id": "A-01", "statement": "Reviewers will release from a derived verdict without re-keying values", "importance": "high", "certainty": "medium",
     "riskiest": True, "validation": "validated", "evidence_ids": ["E-07"]},
    {"id": "A-02", "statement": "Showing the derivation next to each result is enough to catch a misread", "importance": "medium", "certainty": "medium"},
    {"id": "A-03", "statement": "The supplier-quality manager will reuse the reviewer's notice draft", "importance": "medium", "certainty": "low"},
    {"id": "A-04", "statement": "Sixteen lots represent a realistic shift queue", "importance": "low", "certainty": "medium"},
]
MISSING = ["Structured certificate exports from the LIMS (none provided)", "Usage analytics of the current spreadsheet",
           "The supplier-quality manager's view of notice drafts"]


def evidence_doc(with_e12: bool) -> dict:
    ev = EVIDENCE + ([E12] if with_e12 else [])
    return {"evidence": [{"id": i, "claim": c, "source_ids": s, "tag": t, "quote": q} for i, c, s, t, q in ev],
            "insights": INSIGHTS, "assumptions": ASSUMPTIONS, "open_questions": [Q1], "missing": MISSING}


def research_md(with_e12: bool, validation: list[str]) -> str:
    ev = EVIDENCE + ([E12] if with_e12 else [])
    t = fm("research")
    t += "# Research — Lot Release Workbench (fictional example)\n\n> **TL;DR:** Re-keying certificate values is the time sink " \
         "and the error source (I-01: E-01, E-02, E-03); a paper test says a derived verdict can replace it (E-07).\n\n" \
         "Tags: `observed` · `reported` · `assumed`. The two logs are append-only.\n\n## Evidence log\n<!-- append-only -->\n"
    t += "".join(f"- {i} · {t_} · {c} · {', '.join(s)}\n" for i, c, s, t_, _ in ev)
    t += "\n## Insights\n\n| ID | Insight | Evidence | Confidence |\n|---|---|---|---|\n"
    t += "".join(f"| {x['id']} | {x['statement']} | {', '.join(x['evidence_ids'])} | {x['confidence']} |\n" for x in INSIGHTS)
    t += "\n## Assumptions\n\n| ID | Assumption | Importance | Certainty | Riskiest | Validation |\n|---|---|---|---|---|---|\n"
    t += "".join(f"| {a['id']} | {a['statement']} | {a['importance']} | {a['certainty']} | {'yes' if a.get('riskiest') else 'no'} | "
                 f"{a.get('validation', 'unvalidated')} {', '.join(a.get('evidence_ids', []))} |\n" for a in ASSUMPTIONS)
    t += "\n## Open questions\n\n| ID | Question | Blocking | Light | Trigger | Expiry | Owner |\n|---|---|---|---|---|---|---|\n"
    t += f"| Q-01 | {Q1['question']} | no | 🟡 | {Q1['trigger']} | {Q1['expiry']} | {Q1['owner']} |\n"
    t += "\n## Missing information\n\n" + "".join(f"- MISSING: {m}\n" for m in MISSING)
    t += "\n## Validation findings\n<!-- append-only -->\n" + "".join(f"{v}\n" for v in validation)
    return t


fixture("n02_evidence_review", 1, {"evidence": "evidence.json", "research_md": "research.md"})
w("n02_evidence_review", 1, "evidence.json", evidence_doc(False))
w("n02_evidence_review", 1, "research.md", research_md(False, []))
fixture("n02_evidence_review", 2, {"evidence": "evidence.json", "research_md": "research.md"})
w("n02_evidence_review", 2, "evidence.json", evidence_doc(True))
w("n02_evidence_review", 2, "research.md", research_md(True, []))

# ------------------------------------------------------------------------------------------------ N03–N05 product
PROBLEM = {
    "problem_statement": "Reviewers re-key certificate values to compare them with the specification, which is slow and still misses out-of-spec values.",
    "job": "When a lot arrives with its supplier certificate, confirm every result against our specification so compliant lots are released the same shift and the rest are held with a clear reason.",
    "primary_persona": "A plant QA reviewer who checks 15–20 incoming ingredient lots a shift against supplier certificates.",
    "top_pain": {"statement": "Re-keying certificate values into a spreadsheet takes a median 11 minutes per lot and still lets out-of-spec values past the first review.",
                 "evidence_ids": ["E-01", "E-02", "E-03"]},
    "opportunity": "Show every certificate value next to its limit with a derived, explained verdict, so the reviewer decides on one screen without re-keying.",
    "pov": {"user": "A plant QA reviewer", "need": "to confirm a certificate against the specification without re-keying it",
            "insight": "reviewers trust a derived verdict when they can see each value next to its limit (I-02)"},
    "against": ["Auto-release with no human decision", "A generic document inbox that hides the numbers"],
    "how_might_we": ["How might we show every value next to its limit so nothing is re-keyed?",
                     "How might we make the verdict's reasoning visible at a glance?",
                     "How might we make unreadable values an explicit escalation instead of a phone call?",
                     "How might we give supplier quality a ready-to-send draft without the tool ever sending it?"],
    "decisions_to_enable": ["Release, hold or reject a lot", "Escalate an unreadable certificate", "Prepare a supplier notice"],
}
REQS = [
    ("R-01", "user", "Show every certificate result next to its specification limit, with its result", "P0", ["E-01", "E-04"], [], ["Each parameter row shows the specification, the certificate value and the result", "No value has to be re-keyed"]),
    ("R-02", "user", "Derive a verdict (ready, hold, escalate) and show how it was derived", "P0", ["E-07"], ["A-01"], ["The verdict names the results that drive it", "Each row shows its derivation"]),
    ("R-03", "business", "Allow release only when every result is within specification", "P0", ["E-03", "E-05"], [], ["Release is disabled with an 'unlocks when' reason otherwise"]),
    ("R-04", "business", "Require a rationale of at least 20 characters for hold and reject", "P0", ["E-05"], [], ["A shorter rationale is refused with a message, and focus moves to the field"]),
    ("R-05", "user", "Escalate lots with a missing or unreadable result to the QA lead, never lowering the tier", "P0", ["E-06"], [], ["An unreadable value makes the verdict 'Escalate to QA lead'"]),
    ("R-06", "business", "Record every decision with the reviewer, the time, the rationale and the verdict at that moment", "P0", ["E-05"], [], ["The decision log lists every decision, newest first"]),
    ("R-07", "user", "Draft the supplier notice from the results that need action, and never send it from the tool", "P1", ["E-08"], ["A-03"], ["The draft lists every result that needs action", "No send control exists"]),
    ("R-08", "technical", "Run offline in a browser from one file on the plant tablets", "P0", ["E-10"], [], ["Opens from file:// with zero network requests"]),
    ("R-09", "user", "Filter the queue by status and search it, with a way back from an empty result", "P1", ["E-11"], ["A-04"], ["An empty result offers 'Reset filters'"]),
]
CONSTRAINTS = [
    {"id": "C-01", "type": "technical", "statement": "No internet on plant tablets", "source": "S-05 SOP §6 (E-10)"},
    {"id": "C-02", "type": "regulatory", "statement": "Decisions must be attributable to a named reviewer with a time", "source": "S-05 SOP §3"},
    {"id": "C-03", "type": "time", "statement": "Pilot-ready prototype in six weeks", "source": "S-01 brief"},
    {"id": "C-04", "type": "design", "statement": "Use the Fabrikam Quality UI guide", "source": "S-07"},
]
SCOPE = {
    "objective": "Cut the median lot review from 11 to 4 minutes without releasing a single out-of-spec lot.",
    "value_proposition": "Reviewers see every certificate result against its limit, with a derived and explained verdict, and decide on one screen.",
    "scope": {"in_scope": ["Lot queue with derived verdicts", "Lot review: comparison, verdict, guarded decision with rationale",
                           "Draft supplier notice", "Decision log", "Loading, empty, error and not-found states"],
              "out_of_scope": ["Sending supplier notices", "LIMS or ERP integration", "Editing specifications", "Sign-in and multi-user sync"],
              "non_goals": ["Auto-releasing lots without a human decision", "Replacing the QA lead's judgement on escalations", "Supplier scorecards"]},
    "success_criteria": [
        {"id": "M-01", "name": "Median review time per lot", "kind": "north_star", "baseline": "11 min (time study, n = 40)", "target": "≤ 4 min", "unit": "minutes", "method": "Timed moderated sessions, 5 reviewers per round"},
        {"id": "M-02", "name": "Out-of-spec values caught on first review", "kind": "supporting", "baseline": "1 of 4 (time study)", "target": "4 of 4 (100%)", "unit": "lots", "method": "Seeded out-of-spec lots in the session set"},
        {"id": "M-03", "name": "Wrong releases", "kind": "guardrail", "baseline": "0", "target": "0", "unit": "lots", "method": "Every release checked against the specification in the session log"},
        {"id": "M-04", "name": "Reviewers who try to bypass the release guard", "kind": "supporting", "baseline": "not measured (new)", "target": "≤ 1 of 5", "unit": "reviewers", "method": "Session observation"}],
    "rollback_triggers": ["If fewer than 4 of 5 reviewers complete S-01 unaided in round one, stop and revisit the comparison layout",
                          "If any session releases an out-of-spec lot, stop the pilot and fix the guard before round two"],
    "open_questions": [Q1], "light": "green",
}


def _problem_users() -> str:
    t = "## Problem\n\n"
    t += (f"- **Problem statement:** {PROBLEM['problem_statement']}\n- **Job (one sentence):** {PROBLEM['job']}\n"
          f"- **Primary persona (one sentence):** {PROBLEM['primary_persona']}\n"
          f"- **Top pain (one sentence, with evidence):** {PROBLEM['top_pain']['statement']} — {', '.join(PROBLEM['top_pain']['evidence_ids'])}\n"
          f"- **Opportunity:** {PROBLEM['opportunity']}\n- **POV:** {PROBLEM['pov']['user']} needs {PROBLEM['pov']['need']} because "
          f"{PROBLEM['pov']['insight']}.\n- **We design against:** {'; '.join(PROBLEM['against'])}\n\n")
    return t + "## Users\n\nPrimary: plant QA reviewers (E-01, E-11). Secondary: the QA lead (escalations, E-06) and supplier quality (notices, E-08).\n\n"


def _requirements_constraints() -> str:
    t = "## Requirements\n\n| ID | Type | Priority | Requirement | Evidence / assumption | Acceptance |\n|---|---|---|---|---|---|\n"
    t += "".join(f"| {i} | {ty} | {p} | {s} | {', '.join(e + a)} | {'; '.join(acc)} |\n" for i, ty, s, p, e, a, acc in REQS)
    t += "\n## Constraints\n\n| ID | Type | Constraint | Source |\n|---|---|---|---|\n"
    return t + "".join(f"| {c['id']} | {c['type']} | {c['statement']} | {c['source']} |\n" for c in CONSTRAINTS) + "\n"


def product_md(stage: int) -> str:
    """product.md is shared by section: N03 owns Problem and Users, N04 Requirements and Constraints, N05 the preamble
    and the rest. N03 and N04 submit only their sections; N05 submits the whole document (its copy of the other
    sections is identical to what N03 and N04 installed, so nothing is ignored)."""
    if stage == 1:
        return _problem_users()
    if stage == 2:
        return _requirements_constraints()
    sc = SCOPE["scope"]
    t = fm("product") + "# Product — Lot Release Workbench (fictional example)\n\n"
    t += f"> **TL;DR:** {SCOPE['objective']}\n\n" + _problem_users()
    t += f"## Value proposition\n\n{SCOPE['value_proposition']}\n\n" + _requirements_constraints()
    t += ("## Scope\n\n- **In scope:** " + "; ".join(sc["in_scope"]) + "\n- **Out of scope:** " + "; ".join(sc["out_of_scope"]) +
          "\n- **Non-goals:** " + "; ".join(sc["non_goals"]) + "\n\n## Success criteria\n\n| ID | Kind | Metric | Baseline | Target | Method |\n|---|---|---|---|---|---|\n")
    t += "".join(f"| {m['id']} | {m['kind']} | {m['name']} | {m['baseline']} | {m['target']} | {m['method']} |\n" for m in SCOPE["success_criteria"])
    t += "\n## Rollback triggers\n\n" + "".join(f"- {r}\n" for r in SCOPE["rollback_triggers"])
    t += f"\n## Open questions\n\n| ID | Question | Light | Trigger | Expiry | Owner |\n|---|---|---|---|---|---|\n| Q-01 | {Q1['question']} | 🟡 | {Q1['trigger']} | {Q1['expiry']} | {Q1['owner']} |\n"
    return t


fixture("n03_problem_definition", 1, {"problem": "problem.json", "product_md": "product.md"})
w("n03_problem_definition", 1, "problem.json", PROBLEM)
w("n03_problem_definition", 1, "product.md", product_md(1))
fixture("n04_requirements", 1, {"requirements": "requirements.json", "product_md": "product.md"})
w("n04_requirements", 1, "requirements.json", {"requirements": [{"id": i, "type": ty, "statement": s, "priority": p, "evidence_ids": e,
                                                               "assumption_ids": a, "acceptance": acc} for i, ty, s, p, e, a, acc in REQS],
                                             "constraints": CONSTRAINTS})
w("n04_requirements", 1, "product.md", product_md(2))
fixture("n05_scope_success", 1, {"scope": "scope.json", "product_md": "product.md", "evaluation_md": "evaluation.md"})
w("n05_scope_success", 1, "scope.json", SCOPE)
w("n05_scope_success", 1, "product.md", product_md(3))
w("n05_scope_success", 1, "evaluation.md", fm("evaluation", "thresholds: {validation: {min_task_success: 0.8}}\n") +
  "# Evaluation — Lot Release Workbench (fictional example)\n\n> **TL;DR:** A version reaches Wei only when S-01–S-04 pass at 390, 768 "
  "and 1440 px with zero axe violations, and no blocking defect is open.\n\n## Product quality gates\n\nEvery P0 requirement "
  "(R-01–R-06, R-08) is covered by a passing scenario; the guardrail M-03 (wrong releases) stays at 0.\n\n## Design quality gates\n\n"
  "Hierarchy, specificity, consistency and semantic colour score ≥ 4 of 5 (design-quality rubric).\n\n## Accessibility gates\n\n"
  "0 axe violations (WCAG 2.2 A/AA); visible focus; targets ≥ 24 px (44 px on tablets); text ≥ 12 px.\n\n## Usability gates\n\n"
  "Task success ≥ 80% on S-01–S-04 (T-01); median release time ≤ 4 min (M-01).\n\n## Functional gates\n\nNo console errors; "
  "every planned state renders; the release guard and the rationale rule hold.\n\n## Technical gates\n\nOffline single file; "
  "domain unit tests pass; bundle ≤ 1.5 MB; development.md complete.")

# ------------------------------------------------------------------------------------------------ N06 concepts
CONCEPTS = {
    "criteria": [{"id": "C1", "name": "Speed to a correct decision", "weight": 0.4, "requirement_ids": ["R-01", "R-02"]},
                 {"id": "C2", "name": "Errors caught before release", "weight": 0.35, "requirement_ids": ["R-03", "R-05"]},
                 {"id": "C3", "name": "Audit readiness", "weight": 0.25, "requirement_ids": ["R-04", "R-06"]}],
    "concepts": [
        {"id": "K-1", "name": "Side-by-side review workbench", "summary": "A queue of lots, then one review screen with every value next to its limit, a derived verdict and a guarded decision.",
         "before": "Re-key values into a spreadsheet and compare them by eye", "after": "See each value next to its limit with an explained verdict and decide on one screen",
         "riskiest_assumption": "Reviewers release from the derived verdict without re-keying (A-01)", "scores": {"C1": 5, "C2": 5, "C3": 4}},
        {"id": "K-2", "name": "Exception-only inbox", "summary": "Compliant lots are accepted automatically; reviewers see only exceptions.",
         "before": "Review every lot", "after": "Review only exceptions",
         "riskiest_assumption": "QA accepts releases no person looked at (conflicts with the SOP, E-05)", "scores": {"C1": 5, "C2": 3, "C3": 2}},
        {"id": "K-3", "name": "Guided checklist", "summary": "A step-by-step checklist, one parameter per step.",
         "before": "Scan a PDF", "after": "Tick each parameter in turn",
         "riskiest_assumption": "A checklist is faster than a table for five or more parameters", "scores": {"C1": 2, "C2": 4, "C3": 5}}],
    "selected": "K-1", "rationale": "Highest weighted score (4.75 vs 3.55 and 3.45) and keeps a human decision on every lot, as the SOP requires (E-05).",
    "light": "green", "disagreement": [],
}
fixture("n06_concept_ideation", 1, {"concepts": "concepts.json"})
w("n06_concept_ideation", 1, "concepts.json", CONCEPTS)

# ------------------------------------------------------------------------------------------------ N07 experience
SCREENS = [
    {"id": "queue", "name": "Lot queue", "purpose": "See incoming lots with their derived verdict; find the next lot to review", "route": "#/queue", "kind": "list"},
    {"id": "lot", "name": "Lot review", "purpose": "Compare every result with its limit, read the verdict, record the decision", "route": "#/lot/L-2418", "parent": "queue", "kind": "record"},
    {"id": "notice", "name": "Supplier notice draft", "purpose": "Prepare the supplier notice for a held lot (never sent from here)", "route": "#/lot/L-2431/notice", "parent": "lot", "kind": "form"},
    {"id": "audit", "name": "Decision log", "purpose": "See every decision, who made it, when, and the verdict at the time", "route": "#/audit", "kind": "list"},
]
FLOWS = [
    {"id": "F-01", "name": "Release a compliant lot", "requirement_ids": ["R-01", "R-02", "R-03", "R-06"], "entry": "queue", "exit": "audit",
     "steps": [{"screen": "queue", "action": "Filter to Needs review and open the lot", "outcome": "The lot review opens with focus on its heading"},
               {"screen": "lot", "action": "Read results next to limits and the derived verdict", "outcome": "Ready to release, with the derivation per row"},
               {"screen": "lot", "action": "Choose Release, add a rationale, record", "outcome": "Status Released; decision announced"},
               {"screen": "audit", "action": "Open the decision log", "outcome": "The release is the newest entry"}]},
    {"id": "F-02", "name": "Hold an out-of-spec lot and draft the notice", "requirement_ids": ["R-01", "R-02", "R-03", "R-04", "R-07"], "entry": "lot", "exit": "notice",
     "steps": [{"screen": "lot", "action": "See the out-of-spec result and the Hold verdict", "outcome": "Release is locked and says what unlocks it"},
               {"screen": "lot", "action": "Choose Hold with a rationale of at least 20 characters", "outcome": "Status On hold"},
               {"screen": "notice", "action": "Draft the supplier notice and save it", "outcome": "Draft saved — not sent"}]},
    {"id": "F-03", "name": "Escalate an unreadable certificate", "requirement_ids": ["R-05", "R-04"], "entry": "lot", "exit": "lot",
     "steps": [{"screen": "lot", "action": "See the missing result and the Escalate verdict", "outcome": "Release is locked"},
               {"screen": "lot", "action": "Try a hold with a short rationale", "outcome": "Refused with a message; focus on the rationale"}]},
    {"id": "F-04", "name": "Find a lot and recover", "requirement_ids": ["R-09", "R-08"], "entry": "queue", "exit": "queue",
     "steps": [{"screen": "queue", "action": "The first load fails; retry", "outcome": "The queue loads (offline, from the file)"},
               {"screen": "queue", "action": "Search with no match, then reset", "outcome": "Empty state with Reset filters; back to all lots"}]},
]
JOURNEY = {"id": "J-01", "persona": "QA lot reviewer", "job": PROBLEM["job"], "stages": [
    {"name": "Receive", "doing": "A lot and its certificate arrive", "pain": "Certificates are PDFs", "opportunity": "Queue lots with a derived verdict"},
    {"name": "Review", "doing": "Compare each value with the specification", "pain": "Re-keying, 6 of 11 minutes (E-02)", "opportunity": "Values next to limits"},
    {"name": "Decide", "doing": "Release, hold or reject", "pain": "Missed out-of-spec values (E-03)", "opportunity": "A guarded, explained decision"},
    {"name": "Notify", "doing": "Tell the supplier", "pain": "Drafts written from scratch", "opportunity": "A generated draft, sent by supplier quality"},
    {"name": "Audit", "doing": "Show who decided what", "pain": "Phone escalations leave no trace (E-06)", "opportunity": "A decision log"}]}
EXPERIENCE = {"journeys": [JOURNEY], "screens": SCREENS, "navigation": ["Lot queue (#/queue)", "Decision log (#/audit)"], "flows": FLOWS,
              "system_behavior": ["The verdict is derived: any out-of-spec result → Hold; any missing or unreadable result → Escalate (never lower); otherwise Ready",
                                  "Release is guarded: allowed only when the verdict is Ready", "Decisions persist in the browser and appear in the log",
                                  "Notices are drafts; nothing is ever sent"]}


def spec_screens(layout_v2: bool) -> list:
    lot_layout = ("The comparison table comes first; the derived verdict opens the decision panel, which follows the table and sits "
                  "beside it (sticky) at ≥ 1024 px: evidence, then verdict, then decision"
                  if layout_v2 else "The decision panel sits first, above the comparison table, so the action is always visible")
    return [
        {"screen": "queue", "states": {"loading": "Skeleton rows while the lots load", "empty": "No lots match — Reset filters",
                                       "error": "The lot list did not load — Try again", "success": "Lots with verdict and status, needs-review first"},
         "interactions": [{"id": "filter", "trigger": "A status filter", "response": "The table shows that status", "feedback": "The count is announced", "keyboard": "Tab to the filter; Enter or Space toggles it"},
                          {"id": "search", "trigger": "Typing in Search", "response": "Rows filter as you type", "feedback": "An empty result shows Reset filters", "keyboard": "Type; Escape clears"},
                          {"id": "open", "trigger": "A lot link", "response": "The lot review opens", "feedback": "Focus moves to the lot heading", "keyboard": "Enter on the link"}]},
        {"screen": "lot", "states": {"success": lot_layout, "error": "Lot not found — back to the queue", "ready": "Verdict Ready to release",
                                     "hold": "Verdict Hold", "escalate": "Verdict Escalate to QA lead"},
         "interactions": [{"id": "choose", "trigger": "A decision option", "response": "Release is disabled unless the verdict is Ready; the reason 'Release unlocks when every result is within specification.' is shown",
                           "feedback": "The locked option explains what unlocks it", "keyboard": "Arrow keys move between options"},
                          {"id": "record", "trigger": "Record decision", "response": "Validates the rationale (≥ 20 characters for hold and reject)",
                           "feedback": "On error the message shows and focus moves to the rationale; on success the status is announced", "keyboard": "Enter submits the form"},
                          {"id": "notice", "trigger": "Draft supplier notice", "response": "Opens the draft", "feedback": "Focus moves to the draft heading", "keyboard": "Enter on the link"}],
         "validation": ["Rationale of at least 20 characters for hold and reject", "Release only when the verdict is Ready"]},
        {"screen": "notice", "states": {"success": "Issues list and editable draft; Save draft", "error": "Lot not found",
                                        "not-needed": "No notice needed for a Ready lot"},
         "interactions": [{"id": "save", "trigger": "Save draft", "response": "Stores the draft locally", "feedback": "'Draft saved — not sent' is announced", "keyboard": "Enter on the button"}]},
        {"screen": "audit", "states": {"empty": "No decisions recorded yet — go to the queue", "error": "Decisions can't be saved in this browser (storage unavailable)",
                                       "success": "Decisions newest first"},
         "interactions": [{"id": "open", "trigger": "A lot link", "response": "The lot review opens", "feedback": "Focus moves to the lot heading", "keyboard": "Enter on the link"}]},
    ]


FOCUS = ["On navigation, focus moves to the new screen's h1", "Every control shows a 2 px focus ring", "An error moves focus to the invalid field"]
FEEDBACK = ["Status changes are announced in a polite live region", "Status is never colour alone: icon + text + colour"]


def experience_md(with_interactions: bool, layout_v2: bool) -> str:
    t = fm("experience") + "# Experience — Lot Release Workbench (fictional example)\n\n> **TL;DR:** A reviewer opens a lot from the queue, " \
        "sees every value next to its limit with an explained verdict, and records a guarded decision.\n\n## Journeys\n\n"
    t += "".join(f"- **{s['name']}** — {s['doing']}. Pain: {s['pain']}. Opportunity: {s['opportunity']}.\n" for s in JOURNEY["stages"])
    t += "\n## Tasks\n\nRelease a compliant lot · hold an out-of-spec lot and draft the notice · escalate an unreadable certificate · find a lot.\n"
    t += "\n## Information architecture\n\n| Screen id | Name | Route | Purpose | Parent |\n|---|---|---|---|---|\n"
    t += "".join(f"| {s['id']} | {s['name']} | `{s['route']}` | {s['purpose']} | {s.get('parent', '—')} |\n" for s in SCREENS)
    t += "\n**Navigation:** Lot queue · Decision log.\n\n## User flows\n\n"
    for f in FLOWS:
        t += f"- **{f['id']} {f['name']}** ({', '.join(f['requirement_ids'])}): " + " → ".join(f"{s['screen']}: {s['action']}" for s in f["steps"]) + "\n"
    if with_interactions:  # N08 owns this section; N07 leaves it to N08 (the template text stays until then)
        t += "\n## Interactions and states\n\n"
        for s in spec_screens(layout_v2):
            t += f"### {s['screen']}\n\n" + "".join(f"- **{k}:** {v}\n" for k, v in s["states"].items())
            t += "".join(f"- *{i['trigger']}* → {i['response']}; {i['feedback']} (keyboard: {i['keyboard']})\n" for i in s["interactions"]) + "\n"
        t += "**Focus:** " + "; ".join(FOCUS) + ".  \n**Feedback:** " + "; ".join(FEEDBACK) + ".\n"
        if layout_v2:
            t += "\n*Revision (rework cycle 1, D-001):* the comparison now precedes the decision panel (stakeholder feedback FB-001, simulated).\n"
    t += "\n## System behavior\n\n" + "".join(f"- {b}\n" for b in EXPERIENCE["system_behavior"])
    return t


fixture("n07_experience_architecture", 1, {"experience": "experience.json", "experience_md": "experience.md"})
w("n07_experience_architecture", 1, "experience.json", EXPERIENCE)
w("n07_experience_architecture", 1, "experience.md", experience_md(False, False))
for att, v2 in ((1, False), (2, True)):
    fixture("n08_interaction_design", att, {"interactions": "interactions.json", "experience_md": "experience.md"})
    w("n08_interaction_design", att, "interactions.json", {"screens": spec_screens(v2), "focus_rules": FOCUS, "feedback_rules": FEEDBACK})
    w("n08_interaction_design", att, "experience.md", experience_md(True, v2))

# ------------------------------------------------------------------------------------------------ N09 visual system
G = "Fabrikam Quality UI guide (S-07)"
COLORS = [("color-canvas", "#F6F7F9", "page canvas", G), ("color-surface", "#FFFFFF", "panels and tables", G),
          ("color-surface-alt", "#EEF0F3", "table headers, quiet surfaces", "derived: 4% ink on canvas"),
          ("color-border", "#CDD2D9", "dividers", "derived from ink"), ("color-border-strong", "#8A93A0", "control borders (≥ 3:1)", "derived from ink"),
          ("color-text", "#1B1F24", "ink", G), ("color-text-secondary", "#4A5361", "secondary text", "derived: ink 75%"),
          ("color-text-subtle", "#6B7280", "captions on white only", "derived: ink 60%"), ("color-accent", "#0B5CAD", "actions and links", G),
          ("color-accent-strong", "#084A8C", "hover", "derived: accent −15%"), ("color-accent-tint", "#E7F0FA", "information banners", "derived: accent 10%"),
          ("color-on-accent", "#FFFFFF", "text on accent", G), ("color-success", "#1D6B37", "pass: text and icons", G),
          ("color-success-tint", "#E7F4EC", "pass: backgrounds", G), ("color-warning", "#7A4F00", "attention: text and icons", G),
          ("color-warning-tint", "#FFF3D6", "attention: backgrounds", G), ("color-alert", "#B3261E", "alert: failures and holds only", G),
          ("color-alert-tint", "#FDECEB", "alert backgrounds: failures and holds only", G), ("color-focus", "#0B5CAD", "focus ring", G)]
PAIRS = [("color-text", "color-surface", "body text"), ("color-text", "color-canvas", "page text"), ("color-text-secondary", "color-surface", "secondary text"),
         ("color-text-secondary", "color-surface-alt", "table headers, status chips"), ("color-text-secondary", "color-success-tint", "verdict rule text"),
         ("color-text-secondary", "color-alert-tint", "verdict rule text"), ("color-text-secondary", "color-warning-tint", "verdict rule text"),
         ("color-text-subtle", "color-surface", "captions"), ("color-accent", "color-surface", "links"), ("color-on-accent", "color-accent", "primary buttons"),
         ("color-success", "color-success-tint", "pass chips"), ("color-warning", "color-warning-tint", "attention chips"),
         ("color-alert", "color-alert-tint", "failure chips"), ("color-alert", "color-surface", "error titles"), ("color-text", "color-accent-tint", "banners")]
DS = {"colors": [{"name": n, "value": v, "role": r, "provenance": p} for n, v, r, p in COLORS],
      "type_scale": [{"name": "xs", "size_px": 12, "weight": 600, "line_height": 1.4}, {"name": "sm", "size_px": 14, "weight": 400, "line_height": 1.5},
                     {"name": "md", "size_px": 16, "weight": 400, "line_height": 1.5}, {"name": "lg", "size_px": 18, "weight": 600, "line_height": 1.35},
                     {"name": "xl", "size_px": 20, "weight": 600, "line_height": 1.3}, {"name": "2xl", "size_px": 24, "weight": 600, "line_height": 1.25}],
      "spacing_px": [4, 8, 12, 16, 24, 32], "radii_px": [4, 8, 999],
      "contrast_pairs": [{"fg": f, "bg": b, "use": u} for f, b, u in PAIRS] +
                        [{"fg": "color-border-strong", "bg": "color-surface", "use": "control borders", "non_text": True},
                         {"fg": "color-focus", "bg": "color-surface", "use": "focus ring", "non_text": True},
                         {"fg": "color-focus", "bg": "color-canvas", "use": "focus ring on canvas", "non_text": True}],
      "components": [{"name": "Button", "variants": ["primary", "secondary", "quiet"], "states": ["default", "hover", "focus", "disabled"]},
                     {"name": "Filter chip", "variants": ["pressed", "unpressed"], "states": ["default", "focus"]},
                     {"name": "Status chip", "variants": ["ready/within", "attention", "failure", "neutral status"], "states": ["default"]},
                     {"name": "Data table", "variants": ["queue", "comparison", "log"], "states": ["default", "stacked (< 640 px)"]},
                     {"name": "Decision option", "variants": ["release", "hold", "reject"], "states": ["default", "checked", "focus", "locked"]},
                     {"name": "Text area", "variants": ["rationale", "notice"], "states": ["default", "focus", "invalid"]},
                     {"name": "State panel", "variants": ["loading", "empty", "error", "not needed"], "states": ["default"]}],
      "breakpoints_px": [640, 1024],
      "motion": ["No animation", "Transitions ≤ 0.1 s", "Nothing moves under prefers-reduced-motion"],
      "prohibited": ["Gradients", "Status by colour alone", "Alert red outside failures and holds", "Left-accent highlight borders",
                     "Decorative cards for row-by-row comparison", "Web fonts or any network asset", "Text below 12 px"],
      "accessibility": ["WCAG 2.2 AA", "44 px touch targets on tablets", "A visible 2 px focus ring", "One h1 per screen; headings in order"]}
DS["colors"].append({"name": "shadow-elevation", "value": "rgba(27, 31, 36, 0.08)", "role": "shadow under raised panels",
                     "provenance": "translucent token: the build's panel shadow, declared so the token block matches the system"})


def design_md() -> str:
    t = fm("design") + "# Design — Lot Release Workbench (fictional example)\n\n> **TL;DR:** Calm, dense and tabular: the numbers " \
        "lead, status is icon + text + colour, and red means a failure.\n\n## Visual language\n\nQuiet neutrals, one accent for actions, " \
        "status colours only for status. Tables for comparison and audit.\n\n## Layout\n\nQueue: one table. Lot review: the comparison " \
        "table leads; the derived verdict opens the decision panel beside it (≥ 1024 px) or after it — evidence, then verdict, then decision.\n\n## Typography\n\n| Token | Size (px) | Weight | Line height | Use |\n|---|---|---|---|---|\n"
    t += "".join(f"| {x['name']} | {x['size_px']} | {x['weight']} | {x['line_height']} | — |\n" for x in DS["type_scale"])
    t += "\n## Color\n\n| Token | Value | Role | Provenance |\n|---|---|---|---|\n" + "".join(f"| {n} | {v} | {r} | {p} |\n" for n, v, r, p in COLORS)
    t += "\n**Declared pairs:** " + "; ".join(f"{p['fg']} on {p['bg']} ({p['use']})" for p in DS["contrast_pairs"]) + ". Ratios are recomputed by `design_system:check`.\n"
    t += "\n## Components\n\n" + "".join(f"- **{c['name']}:** {', '.join(c['variants'])} — states {', '.join(c['states'])}\n" for c in DS["components"])
    t += "\n## Motion\n\n" + "; ".join(DS["motion"]) + ".\n\n## Responsive behavior\n\nBreakpoints 640 and 1024 px; tables restack as labelled rows below 640 px.\n"
    t += "\n## Accessibility\n\n" + "; ".join(DS["accessibility"]) + ".\n\n## Prohibited patterns\n\n" + "".join(f"- {p}\n" for p in DS["prohibited"])
    return t


fixture("n09_visual_system", 1, {"design_system": "design-system.json", "design_md": "design.md"})
w("n09_visual_system", 1, "design-system.json", DS)
w("n09_visual_system", 1, "design.md", design_md())

# ------------------------------------------------------------------------------------------------ N10 plan
PLAN = json.loads((HERE / "n10_prototype_planning" / "attempt-1" / "plan.json").read_text())
PLAN["states"] = [s for s in PLAN["states"] if not (s["screen"] == "audit" and s["state"] == "error")] + \
    [{"screen": "audit", "state": "error", "route": "?storage=off#/audit", "marker": '[data-state="error"]'}]
for _s in PLAN["states"]:   # the log shows the previous shift's decisions; ?log=empty is the first-day plant
    if _s["screen"] == "audit" and _s["state"] == "empty":
        _s["route"] = "?log=empty#/audit"
# the width checks load the lots most likely to break the lot screen: the out-of-spec one (a notice action and failing
# pills) and the one with an unreadable value (a note and a missing field), not only the route's in-spec lot (R-A11Y-004)
PLAN["samples"] = {"lot": ["#/lot/L-2431", "#/lot/L-2437"]}


def prototype_md(plan: dict, rev: str = "") -> str:
    t = fm("prototype") + "# Prototype plan — Lot Release Workbench (fictional example)\n\n> **TL;DR:** A mid-fidelity, functional, offline " \
        "build that tests the release guard, the rationale rule and the notice draft; the riskiest assumption (A-01) is already " \
        "validated on paper (E-07).\n\n## Goals\n\n" + "".join(f"- {g}\n" for g in plan["goals"])
    t += f"\n## Fidelity\n\n**{plan['fidelity']}** — {plan['fidelity_rationale']}\n\n## Scenarios\n\n"
    t += "".join(f"- **{s['id']}** ({s['flow_id']}) {s['name']} — {len(s['steps'])} steps; success: {s['success']}\n" for s in plan["scenarios"])
    t += "\n## Required interactions\n\nFilter and search; open a lot; choose and record a decision; draft and save a notice.\n"
    t += "\n## Content\n\n" + "".join(f"- {c}\n" for c in plan["content_needs"])
    t += "\n## States\n\n| Screen | State | Route | Marker |\n|---|---|---|---|\n" + "".join(
        f"| {s['screen']} | {s['state']} | `{s['route']}` | `{s['marker']}` |\n" for s in plan["states"])
    if plan.get("samples"):
        t += "\n## Worst-case records\n\n" + "".join(f"- `{k}`: " + ", ".join(f"`{r}`" for r in v) + "\n"
                                                    for k, v in plan["samples"].items())
    t += "\n## Test criteria\n\n| ID | Metric | Threshold |\n|---|---|---|\n" + "".join(f"| {c['id']} | {c['metric']} | {c['threshold']} |\n" for c in plan["test_criteria"])
    t += "\n## Out of scope\n\n" + "".join(f"- {o}\n" for o in plan["out_of_scope"]) + (f"\n{rev}\n" if rev else "")
    return t


fixture("n10_prototype_planning", 1, {"plan": "plan.json", "prototype_md": "prototype.md"})
w("n10_prototype_planning", 1, "plan.json", PLAN)
w("n10_prototype_planning", 1, "prototype.md", prototype_md(PLAN))
PLAN2 = json.loads(json.dumps(PLAN))
s01 = PLAN2["scenarios"][0]["steps"]
_at = next(i for i, x in enumerate(s01) if x.get("expect_count")) + 1   # after the comparison's column check
s01.insert(_at, {"expect_in_viewport": '[data-testid="comparison-table"] tbody tr:first-child'})
for _t in (*PLAN2.get("focus_trace", []), *PLAN2.get("acceptance_trace", [])):   # 1-based: later steps move down one
    if _t.get("scenario") == "S-01" and _t.get("step", 0) > _at:
        _t["step"] += 1
fixture("n10_prototype_planning", 2, {"plan": "plan.json", "prototype_md": "prototype.md"})
w("n10_prototype_planning", 2, "plan.json", PLAN2)
w("n10_prototype_planning", 2, "prototype.md", prototype_md(PLAN2, "*Revision (rework cycle 1):* S-01 now checks that the comparison "
  "table's first row is visible on arrival at every viewport — the acceptance check of D-001."))

# ------------------------------------------------------------------------------------------------ N11 build, N12 content
DEV = fm("development") + """# Development — Lot Release Workbench (fictional example)

> **TL;DR:** A dependency-free, single-file offline build proves the interaction and the rules; production needs the LIMS
> certificate feed, sign-in and a server-side decision log.

## Architecture

Static single-page app. `src/domain.js` holds the pure rules (derivation, verdict, guard, rationale, notice draft) and runs
unchanged in the browser and under `node --test`. `src/app.js` renders four hash-routed screens from inlined data and keeps
decisions in `localStorage`. `build.py` inlines CSS, JS and data into `dist/prototype.html` and writes a hashed manifest.

## Technology

HTML5, CSS custom properties (the design tokens), vanilla ES5 JavaScript, Python 3 for the build, Node 22's built-in test
runner. No framework and no network dependency, because plant tablets are offline (C-01).

## Components

Shell (header, navigation, synthetic-data banner, footer) · filter chips · search · data table (stacks below 640 px) · status
chip · verdict panel · decision form (options, rationale, errors) · notice draft · state panels (loading, empty, error, not needed).

## Data and APIs

`data/lots.json`: specifications, suppliers and lots (seeded, synthetic). Mocked seams, and what production needs for each:
- Certificates: inlined JSON → the LIMS export API (open question Q-01).
- Decisions: `localStorage` → a server-side, attributable decision log with sign-in (C-02).
- Notices: saved drafts → hand-off to supplier quality's mailbox (sending stays outside the tool, E-08).

## Folder structure

`src/` (index.html, styles.css, domain.js, app.js, data/seed.json) · `data/` (generate.py, lots.json) · `content/` (copy deck) ·
`tests/` (domain.test.js) · `dist/` (built) · `build-manifest.json`.

## Standards

Tokens only (no colour literal outside `:root`); every screen marked `data-screen`; every state marked `data-state`;
WCAG 2.2 AA; 44 px targets; one h1 per screen; focus moves to the heading on navigation.

## Testing

`node --test tests/domain.test.js` for the rules; the pdg browser suite (Playwright + axe) for scenarios S-01–S-04, states,
responsive behaviour and accessibility at 390, 768 and 1440 px.
"""
for att, overlay in ((1, True), (2, False)):
    run = [["{python}", "{project}/prototype/build.py", "--src", "{project}/prototype", "--out", "{work}/prototype_build"] +
           (["--overlay", "{fixture}/overlay"] if overlay else [])]
    fixture("n11_prototype_development", att, {"prototype_build": "{work}/prototype_build",
                                                "build_manifest": "{work}/prototype_build/build-manifest.json",
                                                "development_md": "development.md"}, run=run)
    w("n11_prototype_development", att, "development.md", DEV if att == 1 else DEV + "\n*Revision (rework cycle 1, D-002/D-003):* status "
      "chips use their declared tint pairs; the comparison precedes the decision panel (D-001).\n")
w("n11_prototype_development", 1, "overlay/overlay.css", """/* First draft (scripted fixture): the decision panel leads the lot review, and status chips use the subtle
   text token on the alt surface — an undeclared pairing. Both are on-system tokens, so the static checks pass;
   the browser review measures the contrast. */
.lot-layout { display: flex; flex-direction: column; }
.lot-layout .decision-col { order: -1; position: static; }
.chip { color: var(--color-text-subtle); background: var(--color-surface-alt); }""")
fixture("n12_content_data", 1, {"prototype": "{work}/prototype", "content": "{work}/generated/content.json"},
        run=[["{python}", "{artifact:prototype_build}/data/generate.py", "--out", "{work}/generated", "--seed", "20260926"],
             ["{python}", "{artifact:prototype_build}/build.py", "--src", "{artifact:prototype_build}", "--out", "{work}/prototype",
              "--data", "{work}/generated/lots.json"]])

# ------------------------------------------------------------------------------------------------ N13–N15 reviews
REVIEW13 = {"dimensions": [
    {"id": "DES-HIERARCHY", "score": 4, "evidence": "lot-1440.png: the verdict and the comparison lead; one primary action"},
    {"id": "DES-SPECIFICITY", "score": 5, "evidence": "queue-1440.png: lot, certificate, material, supplier and limits in the domain's words"},
    {"id": "DES-CONSISTENCY", "score": 4, "evidence": "One table style, one chip style, one radius set across the four screens"},
    {"id": "DES-DENSITY", "score": 4, "evidence": "Tables for comparison and audit; no decorative cards"},
    {"id": "DES-SEMANTIC-COLOR", "score": 4, "evidence": "Green pass, amber attention, red failure; icon + text on every chip"},
    {"id": "DES-DERIVATION", "score": 5, "evidence": "Every row shows how its result was derived"},
    {"id": "DES-SCOPE-VISIBLE", "score": 5, "evidence": "notice: 'Draft only — sending happens outside this prototype'"},
    {"id": "DES-DOMAIN", "score": 4, "evidence": "Reviewer workflow only; no merged flows"},
    {"id": "A11Y-SEMANTICS", "score": 4, "evidence": "One h1 per screen, captions on tables, labelled controls, live status"},
    {"id": "A11Y-MANUAL", "score": 4, "evidence": "Keyboard-only walk of S-01 to S-04 at 1440 and 390: focus follows the reading order, "
     "returns to the lot row after the decision dialog closes, and the status region announces each recorded decision"},
    {"id": "RESP-LAYOUT", "score": 4, "evidence": "lot-390.png: rows restack as labelled fields"}],
    "findings": [], "summary": "Scripted review (dry run): the design dimensions meet the bar; the tool findings stand on their own."}
for att in (1, 2):
    fixture("n13_quality_review", att, {"quality_review": "review.json"})
    w("n13_quality_review", att, "review.json", REVIEW13)


def sessions(version: int, concern: bool) -> dict:
    ss = []
    for i, role in enumerate(["lot reviewer", "lot reviewer", "lot reviewer", "QA lead", "lot reviewer"], 1):
        tasks = [{"scenario_id": sid, "success": True, "time_s": t, "seq": q} for sid, t, q in
                 (("S-01", 150 + 10 * i, 6), ("S-02", 210 + 5 * i, 6), ("S-03", 95 + 5 * i, 5), ("S-04", 80 + 4 * i, 6))]
        ss.append({"participant": f"P{i}", "role": role, "simulated": True, "tasks": tasks, "quotes": []})
    findings = []
    if concern:
        findings.append({"dimension": "STAKEHOLDER-FEEDBACK", "severity": "P2", "by": "human", "participant": "P4", "location": "lot:1280",
                         "message": "On my laptop the decision panel comes first; I have to scroll down to the results and back up to decide.",
                         "evidence": "simulated session P4 (QA lead), build v1"})
    return {"sessions": ss, "findings": findings,
            "summary": f"SIMULATED sessions for the fictional example (build v{version}); not user evidence. Real validation is Wei's human dimension."}


VALREV = {"dimensions": [{"id": "VAL-INSIGHT", "score": 4, "evidence": "Each finding names the screen and the flow it implicates"}],
          "findings": [], "summary": "Scripted validation review (dry run)."}
V1 = "- v1 · SIMULATED (not evidence) · 5 sessions · task success 100% · 1 stakeholder concern (FB-001: decision panel before the comparison on a laptop)"
V2 = "- v2 · SIMULATED (not evidence) · 5 sessions · task success 100% · no concerns; the comparison now leads (D-001 verified)"
for att, concern, lines in ((1, True, [V1]), (2, False, [V1, V2])):
    fixture("n14_validation", att, {"validation": "validation.json", "validation_review": "review.json", "research_md": "research.md"})
    w("n14_validation", att, "validation.json", sessions(att, concern))
    w("n14_validation", att, "review.json", VALREV)
    w("n14_validation", att, "research.md", research_md(True, lines))
FEAS = {"dimensions": [{"id": "TEC-FEASIBLE", "score": 4, "evidence": "development.md names the LIMS, decision-log and notice seams and what each needs"},
                       {"id": "TEC-QUALITY", "score": 4, "evidence": "Pure domain module with unit tests; renderers small and escaped"}],
        "findings": [], "summary": "Scripted feasibility review (dry run)."}
for att in (1, 2):
    fixture("n15_feasibility_review", att, {"feasibility_review": "review.json"})
    w("n15_feasibility_review", att, "review.json", FEAS)

# ------------------------------------------------------------------------------------------------ N16 diagnosis, N19 learning
fixture("n16_feedback_diagnosis", 1, {"interpretation": "interpretation.json"})  # tool findings map themselves
w("n16_feedback_diagnosis", 1, "interpretation.json", {
    "defects": [{"id": "D-001", "signature": "LAYOUT-COMPARISON-FIRST@lot", "dimension": "STAKEHOLDER-FEEDBACK", "severity": "P2",
                 "message": "The decision panel precedes the comparison, so on a laptop the reviewer scrolls between the results and the decision",
                 "evidence": "FB-001 (simulated QA-lead session P4, build v1)", "traced_node": "n08_interaction_design",
                 "trace_reason": "The interaction spec (N08) put the decision panel first; the build implemented the spec faithfully",
                 "smallest_fix": "Specify the comparison table first and the decision panel after it (beside it, sticky, at ≥ 1024 px)",
                 "acceptance_check": "On arrival at #/lot/L-2418 the comparison table's first row is in the viewport at 390, 768 and 1440 px (S-01)",
                 "from_feedback": ["FB-001"]}],
    "feedback": [{"feedback_id": "FB-001", "defect_ids": ["D-001"]}],
    "summary": "One simulated stakeholder concern traced to the interaction spec; the tool's contrast findings are mapped from their own trace."})
fixture("n16_feedback_diagnosis", 2, {"interpretation": "interpretation.json"})
w("n16_feedback_diagnosis", 2, "interpretation.json", {"defects": [], "feedback": [],
                                                      "summary": "No new blocking finding or feedback at build v2."})
fixture("n19_learning_memory", 1, {"lessons": "lessons.json", "memory_md": "memory.md"})
LESSONS = {"lessons": [
    {"id": "L-01", "statement": "On a review screen, put the evidence being compared before the decision control; on wide screens keep the decision beside it",
     "scope": "reusable", "evidence_class": "inferred", "evidence": ["D-001", "FB-001", "comparison:cycle-1"], "rule_id": None,
     "category": "ux_interaction"},
    {"id": "L-02", "statement": "Every foreground/background pairing a build uses must be a declared pair: on-system tokens in an undeclared pairing still failed contrast",
     "scope": "reusable", "evidence_class": "verified", "evidence": ["D-002", "D-003", "D-004", "comparison:cycle-1"], "rule_id": "R-A11Y-001", "helped": True},
    {"id": "L-03", "statement": "Riverside tablets are offline: the single-file build is the delivery format",
     "scope": "project_specific", "evidence_class": "verified", "evidence": ["E-10", "C-01"], "rule_id": None}],
    "summary": "Two reusable lessons (one new candidate) and one project-specific note."}
w("n19_learning_memory", 1, "lessons.json", LESSONS)
w("n19_learning_memory", 1, "memory.md", fm("memory") + """# Memory — Lot Release Workbench (fictional example)

> **TL;DR:** Evidence before the decision control, and only declared colour pairs — both caught by review, fixed in one cycle.

## Reusable principles in force

Rule base v1.0.0 (see the run's knowledge refs). Rules that fired: R-A11Y-001 (axe gate) — helped.

## Successful patterns

- The browser suite caught an on-token contrast failure the static checks could not see (D-002–D-004, three screens).
- One targeted cycle re-opened N08 and N11 only; N01–N07 and N09 were not re-run.

## Recurring failures

- None recurring yet (first run).

## Verified improvements

- v1 → v2: 4 defects resolved (D-001 layout; D-002–D-004 contrast); comparison verdict *improved*.

## Lessons log
<!-- append-only -->
- L-01 (reusable, candidate): evidence before the decision control
- L-02 (reusable): only declared colour pairs
- L-03 (project-specific): offline single-file delivery
""")
print("fixtures written")
