"""Regression tests for verified audit findings in deterministic quality tools."""

from __future__ import annotations

import json

import pytest
from types import SimpleNamespace

from pdg.models import ProjectState
from pdg.tools import _node, content, evidence, experience, product, prototype, validation

from .conftest import FakeCtx, PKG

FIX = PKG / "examples" / "coa-review" / "fixtures"


def _fx(node: str, name: str, attempt: int = 1):
    return json.loads((FIX / node / f"attempt-{attempt}" / name).read_text())


def _state(**sections):
    data = {"schema_version": "t", "project": {"id": "t", "name": "t", "created": "now", "workflow_id": "w",
                                                "workflow_version": "1"}}
    data.update(sections)
    return ProjectState.model_validate(data)


def test_f04_node_unit_requires_exit_zero_and_last_summary(tmp_path, monkeypatch):
    test_file = tmp_path / "misleading.test.js"
    test_file.write_text("test body is not executed by this parser regression")
    out = "\n".join([
        "# pass 3",
        "# fail 0",
        "not ok 1 - actually fails",
        "1..1",
        "# tests 4",
        "# pass 3",
        "# fail 1",
    ])
    monkeypatch.setattr(_node, "node_bin", lambda: "node")
    monkeypatch.setattr(_node.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=out, stderr="", returncode=1))

    passed, failed, tail = _node.unit(test_file, tmp_path)

    assert passed == 3
    assert failed == 1
    assert "fail 1" in tail


def test_f05_external_refs_cover_common_network_forms_without_local_false_positives():
    html = """
    <img src=https://cdn.example/a.png>
    <img srcset="/local.png 1x, https://cdn.example/b.png 2x">
    <script>import("https://cdn.example/module.js"); fetch('/api/local');</script>
    <style>
      @import url("https://cdn.example/site.css");
      .remote { background-image: url(//cdn.example/bg.png); }
      .data { background-image: url(data:image/png;base64,AAAA); }
      .relative { background-image: url(./local.png); }
    </style>
    """

    refs = prototype.external_refs(html)

    assert len(refs) == 5
    assert not any("data:" in ref or "./local" in ref or "/api/local" in ref for ref in refs)


def test_f05_off_token_colours_scan_inline_styles_and_modern_css_colours():
    html = """
    <style>
      :root { --token: #123456; --alpha: #ff000080; }
      .ok { color: var(--token); }
      .bad { border-color: #777; background: rgb(12 34 56 / 80%); outline-color: hsl(210 50% 40%); }
    </style>
    <div style="color:#777777; background-color: rgba(1, 2, 3, .4); border-color:#abcd">x</div>
    """

    off = prototype.off_token_colours(html)

    assert "#777777" in off
    assert "#AABBCCDD" in off
    assert "rgba(1, 2, 3, .4)" in off
    assert "rgb(12 34 56 / 80%)" in off
    assert "hsl(210 50% 40%)" in off
    assert "#FF000080" not in off


def test_f06_content_scans_dataset_placeholders_and_requires_visible_body_label(tmp_path):
    root = tmp_path / "prototype"
    root.mkdir()
    (root / "index.html").write_text(
        "<html><head><title>Synthetic data — for design review only</title></head>"
        "<body><main><h1>Queue</h1><p>Fictional lot review.</p></main></body></html>"
    )
    (root / "lots.json").write_text(json.dumps([{"supplier": "Lorem ipsum GmbH", "status": "TBD"}]))
    (root / "build-manifest.json").write_text(json.dumps({"entry": "index.html"}))
    doc = {"datasets": [{"path": "lots.json", "records": 1, "provenance": "synthetic",
                         "label_shown_in_ui": True}], "copy_deck": "copy.md", "edge_cases": ["TBD"]}
    ctx = FakeCtx({"content": doc}, thresholds={"content": {"min_records": 1}}, work=tmp_path)
    ctx.output = lambda key: root if key == "prototype" else None

    res = content.check(ctx)

    assert not res.dimensions["CNT-PLACEHOLDER"].passed
    assert not res.dimensions["CNT-PROVENANCE"].passed
    assert "visible label present: False" in res.dimensions["CNT-PROVENANCE"].evidence


def test_f07_list_data_screen_requires_empty_and_error_states():
    interactions = _fx("n08_interaction_design", "interactions.json")
    interactions["screens"][0]["states"].pop("empty")
    state = _state(design={"screens": _fx("n07_experience_architecture", "experience.json")["screens"]})

    res = experience.check_interactions(FakeCtx({"interactions": interactions}, state=state))

    assert not res.dimensions["EXP-STATES"].passed
    assert "without an empty state" in res.dimensions["EXP-STATES"].evidence


def test_f09_validation_parses_plan_percentage_thresholds():
    plan = _fx("n10_prototype_planning", "plan.json")
    plan["test_criteria"][0]["threshold"] = "≥ 90%"
    tasks = [{"scenario_id": "S-01", "success": i < 17, "seq": 6} for i in range(20)]
    doc = {"sessions": [{"participant": "P1", "role": "reviewer", "simulated": False, "tasks": tasks}],
           "summary": "Real moderated sessions."}
    state = _state(build={"plan": plan})

    res = validation.check(FakeCtx({"validation": doc}, state=state))

    assert not res.dimensions["VAL-TASK-SUCCESS"].passed
    assert "≥ 90%" in res.dimensions["VAL-TASK-SUCCESS"].evidence


def test_f09_validation_fails_loudly_on_unparseable_plan_threshold():
    plan = _fx("n10_prototype_planning", "plan.json")
    plan["test_criteria"][0]["threshold"] = "nine out of ten"
    doc = {"sessions": [{"participant": "P1", "role": "reviewer", "simulated": False,
                         "tasks": [{"scenario_id": "S-01", "success": True, "seq": 6}]}],
           "summary": "Real moderated sessions."}
    state = _state(build={"plan": plan})

    res = validation.check(FakeCtx({"validation": doc}, state=state))

    assert not res.dimensions["VAL-TASK-SUCCESS"].passed
    assert "could not parse" in res.dimensions["VAL-TASK-SUCCESS"].evidence


def test_f16_evidence_missing_fails_when_open_questions_are_not_declared_missing():
    doc = _fx("n02_evidence_review", "evidence.json")
    doc["missing"] = []
    state = _state(inputs={"sources": _fx("n01_context_intake", "sources.json")["sources"]})

    res = evidence.check_tags(FakeCtx({"evidence": doc}, state=state))

    assert not res.dimensions["EVD-MISSING"].passed
    assert "Q-01" in res.dimensions["EVD-MISSING"].evidence


def _agent_finding(location: str, **kw) -> dict:
    return {"dimension": "VAL-INSIGHT", "severity": "P3", "message": "the lot status reads as final", "evidence": "",
            "location": location, "by": "agent", **kw}


def test_a_simulated_sessions_finding_passes_without_the_word_and_the_engine_labels_it():
    """Field run W34: the check searched each simulated finding's evidence for the word "simulated", a rule the rubric
    and the task never state, and failed an honestly flagged run. Being simulated is structural (the session says
    so), so the check no longer reads prose, and the engine labels the stored finding itself (F16's goal holds)."""
    from pdg.artifacts import ValidationDoc
    from pdg.engine import SIMULATED_LABEL, validation_findings
    plan = _fx("n10_prototype_planning", "plan.json")
    doc = _fx("n14_validation", "validation.json")
    simulated = next(s["participant"] for s in doc["sessions"] if s["simulated"])
    doc["findings"] = [_agent_finding("lot:1280", participant=simulated, evidence="session notes, build v1")]
    res = validation.check(FakeCtx({"validation": doc}, state=_state(build={"plan": plan})))
    assert res.dimensions["VAL-SIMULATED-FLAGGED"].passed
    _, extra = validation_findings(ValidationDoc.model_validate(doc), None)
    assert extra[0]["evidence"].startswith(SIMULATED_LABEL)


def test_a_finding_from_an_unrecorded_participant_fails_the_simulated_flag():
    """What the structural check still catches: a finding whose participant has no recorded session."""
    plan = _fx("n10_prototype_planning", "plan.json")
    doc = _fx("n14_validation", "validation.json")
    doc["findings"][0]["participant"] = "P-GHOST"
    res = validation.check(FakeCtx({"validation": doc}, state=_state(build={"plan": plan})))
    assert not res.dimensions["VAL-SIMULATED-FLAGGED"].passed
    assert "P-GHOST" in res.dimensions["VAL-SIMULATED-FLAGGED"].evidence


def test_n14s_findings_are_stored_once_when_both_of_its_outputs_hold_them():
    """Field run W33: N14's contract asks for findings in the validation doc and in its review, and the engine added the
    validation doc's findings to the review's own without de-duplicating, so every stored N14 review held them twice."""
    from pdg.artifacts import ValidationDoc
    from pdg.engine import validation_findings
    doc = _fx("n14_validation", "validation.json")
    doc["findings"] = [_agent_finding("lot:1280"), _agent_finding("queue:390")]
    review = {"dimensions": [], "findings": [dict(doc["findings"][0])], "summary": "s"}
    _, extra = validation_findings(ValidationDoc.model_validate(doc), review)
    assert [f["location"] for f in extra] == ["queue:390"]


def test_f16_rollback_trigger_requires_measurable_condition_not_length():
    scope = _fx("n05_scope_success", "scope.json")
    scope["rollback_triggers"] = ["Roll back if reviewers are unhappy with the new workflow"]

    res = product.check_scope(FakeCtx({"scope": scope}))

    assert not res.dimensions["SCP-ROLLBACK"].passed

    scope["rollback_triggers"] = ["Roll back on a P1 incident in the release guard audit"]
    assert product.check_scope(FakeCtx({"scope": scope})).dimensions["SCP-ROLLBACK"].passed


# ------------------------------------------------------------------------------------------------ F08: the fidelity gate
def _plan_state(extra_history=None, extra_feedback=None):
    import json as _json

    from pdg.models import ProjectState
    from .conftest import EXAMPLE as _EX
    ev = _json.loads((_EX / "fixtures" / "n02_evidence_review" / "attempt-2" / "evidence.json").read_text())
    for a in ev["assumptions"]:
        if a.get("riskiest"):
            a["validation"], a["accepted_by"] = "accepted_risk", "Wei"          # what an agent can write
    return ProjectState.model_validate({
        "schema_version": "t", "project": {"id": "t", "name": "t", "created": "n", "workflow_id": "w", "workflow_version": "1"},
        "research": {"assumptions": ev["assumptions"], "evidence": ev["evidence"]},
        "history": {"approvals": extra_history or []}, "evaluation": {"feedback": extra_feedback or []}})


def _plan(status="accepted_risk", evidence=None):
    import json as _json

    from .conftest import EXAMPLE as _EX
    p = _json.loads((_EX / "fixtures" / "n10_prototype_planning" / "attempt-2" / "plan.json").read_text())
    for ac in p["riskiest_assumptions"]:
        ac["status"], ac["evidence_ids"] = status, (evidence if evidence is not None else ac["evidence_ids"])
    return p


def test_f08_an_agent_written_acceptance_is_not_a_human_one():
    from pdg.tools import plan
    from .conftest import FakeCtx
    res = plan.check(FakeCtx({"plan": _plan()}, state=_plan_state()))
    assert not res.dimensions["PLN-FIDELITY-GATE"].passed                   # `accepted_by: Wei`, written by an agent
    assert "no named human accepted it" in res.dimensions["PLN-FIDELITY-GATE"].evidence


def test_f08_only_a_named_humans_recorded_acceptance_counts():
    """A risk counts as accepted only through `pdg accept-risk` by a named human. Words that merely mention the id do
    not count, and neither do scripted (dry-run) records."""
    from pdg.artifacts import PrototypePlan
    from pdg.tools import plan
    from .conftest import FakeCtx
    aid = PrototypePlan.model_validate(_plan()).riskiest_assumptions[0].assumption_id
    refusal = [{"node": "n05_scope_success", "decision": "approved", "actor": "Wei", "human": True, "at": "t",
                "reason": f"{aid} is NOT accepted as a risk: validate it before any mid or high fidelity build",
                "build_version": 0}]
    res = plan.check(FakeCtx({"plan": _plan()}, state=_plan_state(extra_history=refusal)))
    assert not res.dimensions["PLN-FIDELITY-GATE"].passed                   # a mention (here a refusal) is not acceptance
    st = _plan_state()
    st.history.risk_acceptances.append(__import__("pdg.models", fromlist=["RiskAcceptance"]).RiskAcceptance(
        assumption=aid, actor="Wei", reason="the paper test covers it for this round", at="2026-09-26T21:00:00+00:00"))
    res = plan.check(FakeCtx({"plan": _plan()}, state=st))
    assert res.dimensions["PLN-FIDELITY-GATE"].passed and f"{aid} by Wei" in res.dimensions["PLN-FIDELITY-GATE"].evidence
    st.history.risk_acceptances[0].actor = "dry-run-auto"
    assert not plan.check(FakeCtx({"plan": _plan()}, state=st)).dimensions["PLN-FIDELITY-GATE"].passed


def test_risk_acceptance_is_bound_to_the_statement_hash():
    from pdg.models import RiskAcceptance
    from pdg.artifacts import PrototypePlan
    from pdg.tools import plan
    from pdg.util import sha256_json
    from .conftest import FakeCtx
    st = _plan_state()
    aid = PrototypePlan.model_validate(_plan()).riskiest_assumptions[0].assumption_id
    assumption = next(a for a in st.research.assumptions if a.id == aid)
    st.history.risk_acceptances.append(RiskAcceptance(
        assumption=aid, actor="Wei", reason="the paper test covers it for this round",
        at="2026-09-26T21:00:00+00:00", statement_sha256=sha256_json(assumption.statement)))
    assert plan.check(FakeCtx({"plan": _plan()}, state=st)).dimensions["PLN-FIDELITY-GATE"].passed
    assumption.statement += " Changed."
    res = plan.check(FakeCtx({"plan": _plan()}, state=st))
    assert not res.dimensions["PLN-FIDELITY-GATE"].passed
    assert f"{aid} changed after Wei accepted it on 2026-09-26: re-accept" in res.dimensions["PLN-FIDELITY-GATE"].evidence


def test_f08_validated_assumptions_must_cite_evidence_that_exists():
    from pdg.tools import plan
    from .conftest import FakeCtx
    res = plan.check(FakeCtx({"plan": _plan("validated", ["E-DOES-NOT-EXIST"])}, state=_plan_state()))
    assert not res.dimensions["PLN-FIDELITY-GATE"].passed
    assert "E-DOES-NOT-EXIST" in res.dimensions["PLN-FIDELITY-GATE"].evidence


def test_f07_a_record_screen_that_loads_needs_no_empty_state():
    """A record screen (one lot) can have a loading state, and its purpose can mention data; neither makes it a list.
    Only a screen named or routed as a collection (queue, list, log…) or one that declares an empty state must have
    one."""
    interactions = _fx("n08_interaction_design", "interactions.json")
    lot = next(s for s in interactions["screens"] if s["screen"] == "lot")
    lot["states"]["loading"] = "Skeleton rows while the lot's certificate data loads"
    screens = _fx("n07_experience_architecture", "experience.json")["screens"]
    for s in screens:
        if s["id"] == "lot":
            s["purpose"] += " Shows the certificate data beside the specification."
    res = experience.check_interactions(FakeCtx({"interactions": interactions}, state=_state(design={"screens": screens})))
    assert res.dimensions["EXP-STATES"].passed, res.dimensions["EXP-STATES"].evidence


def test_f16_rollback_triggers_are_judged_without_any_products_vocabulary():
    """The check must work for any product: a quantified event passes in words the example never uses, and a vague
    trigger fails even when it contains a word from the example's domain."""
    scope = _fx("n05_scope_success", "scope.json")
    for trigger, ok in [("If any session publishes a wrong supplier notice, pause the pilot", True),
                        ("If more than two reviewers skip the rationale field, revisit the form", True),
                        ("Roll back if the release goes badly", False),
                        ("Stop if the lot review time feels too long", False),
                        ("Roll back if reviewers need more time than today", False),
                        ("Roll back if any problems appear", False)]:
        scope["rollback_triggers"] = [trigger]
        assert product.check_scope(FakeCtx({"scope": scope})).dimensions["SCP-ROLLBACK"].passed is ok, trigger


def _success(threshold: str, rate: float):
    plan = _fx("n10_prototype_planning", "plan.json")
    plan["test_criteria"][0]["threshold"] = threshold
    tasks = [{"scenario_id": "S-01", "success": i < round(rate * 20), "seq": 6} for i in range(20)]
    doc = {"sessions": [{"participant": "P1", "role": "reviewer", "simulated": False, "tasks": tasks}],
           "summary": "Real moderated sessions."}
    return validation.check(FakeCtx({"validation": doc}, state=_state(build={"plan": plan}))).dimensions["VAL-TASK-SUCCESS"]


def test_f09_a_success_threshold_is_read_as_a_rate_never_as_an_id():
    """'4 of 5' is 80% (not 4%), and a scenario id such as S-01 in the threshold is never read as the number."""
    assert not _success("≥ 4 of 5 participants", 0.6).passed
    assert _success("≥ 4 of 5 participants", 0.85).passed
    assert _success("S-01..S-04 ≥ 80%", 0.85).passed and not _success("S-01..S-04 ≥ 80%", 0.7).passed
    assert not _success("most tasks on S-01", 0.95).passed                # no rate stated: fail loudly, never a default


def test_f06_the_synthetic_label_must_be_visible_to_a_sighted_user(tmp_path):
    """<title>, <noscript> and screen-reader-only text are not a visible label; a container class such as
    overflow-hidden hides nothing, and a hidden input does not hide the text after it."""
    def provenance(body: str, name: str) -> bool:
        root = tmp_path / name
        root.mkdir()
        (root / "index.html").write_text(f"<html><head><title>Lots</title><style>{SR_ONLY}</style></head>"
                                         f"<body><main><h1>Queue</h1>{body}</main></body></html>")
        (root / "lots.json").write_text(json.dumps([{"supplier": "Northwind Metals", "status": "ready"}]))
        (root / "build-manifest.json").write_text(json.dumps({"entry": "index.html"}))
        doc = {"datasets": [{"path": "lots.json", "records": 1, "provenance": "synthetic", "label_shown_in_ui": True}],
               "copy_deck": "copy.md", "edge_cases": ["none"]}
        ctx = FakeCtx({"content": doc}, thresholds={"content": {"min_records": 1}}, work=tmp_path)
        ctx.output = lambda key: root if key == "prototype" else None
        return content.check(ctx).dimensions["CNT-PROVENANCE"].passed
    assert not provenance("<noscript>Synthetic data</noscript>", "a")
    assert not provenance("<span class='sr-only'>Synthetic data</span>", "b")
    assert provenance("<div class='overflow-hidden rounded'><p>Synthetic data: demo only</p></div>", "c")
    assert provenance("<form><input type='hidden' name='lot'><p>Synthetic data: demo only</p></form>", "d")
    assert provenance("<div id='b'></div><script>document.getElementById('b').textContent = "
                      "'Synthetic data \u2014 for design review only'</script>", "e")          # drawn by a script (R3-1)


SR_ONLY = (".sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;"
           "clip:rect(0,0,0,0);white-space:nowrap;border:0}")


def test_f06_without_a_browser_the_static_scan_still_reads_script_drawn_labels(tmp_path, monkeypatch):
    """No Chromium: the static fallback keeps script text (a script-drawn label is not refused), still ignores <title>
    and sr-only text, and says it did not verify the rendered page."""
    import pdg.tools.browser as b
    monkeypatch.setattr(b, "visible_text_with", lambda entry, word, timeout_ms=3000: None)

    def provenance(body: str, name: str):
        root = tmp_path / name
        root.mkdir()
        (root / "index.html").write_text(f"<html><head><title>Synthetic</title></head><body>{body}</body></html>")
        (root / "lots.json").write_text(json.dumps([{"supplier": "Northwind Metals", "status": "ready"}]))
        (root / "build-manifest.json").write_text(json.dumps({"entry": "index.html"}))
        doc = {"datasets": [{"path": "lots.json", "records": 1, "provenance": "synthetic", "label_shown_in_ui": True}],
               "copy_deck": "copy.md", "edge_cases": ["none"]}
        ctx = FakeCtx({"content": doc}, thresholds={"content": {"min_records": 1}}, work=tmp_path)
        ctx.output = lambda key: root if key == "prototype" else None
        return content.check(ctx).dimensions["CNT-PROVENANCE"]
    drawn = provenance("<div id='b'></div><script>b.textContent='Synthetic data'</script>", "a")
    assert drawn.passed and "static scan" in drawn.evidence
    assert not provenance("<main><h1>Queue</h1></main>", "b").passed               # the <title> alone is not a label
    assert not provenance("<span class='sr-only'>Synthetic data</span>", "c").passed


def test_f07_a_declared_screen_kind_decides_whether_it_needs_an_empty_state():
    """A list screen whose name gives no hint ("Lots") is caught by its declared kind, and a declared record screen
    whose name looks like a list is not held to a list's states."""
    interactions = _fx("n08_interaction_design", "interactions.json")
    screens = _fx("n07_experience_architecture", "experience.json")["screens"]
    for s in screens:
        if s["id"] == "queue":
            s["name"], s["route"], s["kind"] = "Lots", "#/lots", "list"
    queue = next(s for s in interactions["screens"] if s["screen"] == "queue")
    queue["states"].pop("empty")
    res = experience.check_interactions(FakeCtx({"interactions": interactions}, state=_state(design={"screens": screens})))
    assert not res.dimensions["EXP-STATES"].passed and "queue" in res.dimensions["EXP-STATES"].evidence
    for s in screens:
        if s["id"] == "queue":
            s["name"], s["kind"] = "Queue item review", "record"             # a record screen, named like a list
    res = experience.check_interactions(FakeCtx({"interactions": interactions}, state=_state(design={"screens": screens})))
    assert res.dimensions["EXP-STATES"].passed, res.dimensions["EXP-STATES"].evidence


def test_f07_every_screen_must_declare_its_kind_at_n07():
    exp = _fx("n07_experience_architecture", "experience.json")
    reqs = _fx("n04_requirements", "requirements.json")
    state = _state(product={"requirements": reqs["requirements"]})
    assert experience.check_flows(FakeCtx({"experience": exp}, state=state)).dimensions["EXP-SCREENS"].passed
    del exp["screens"][0]["kind"]
    res = experience.check_flows(FakeCtx({"experience": exp}, state=state)).dimensions["EXP-SCREENS"]
    assert not res.passed and "without a kind" in res.evidence


def test_f09_a_count_is_not_a_rate():
    """'≥ 4 participants' and 'at least 4 users' are counts, and a bare '90' could be 90% or 90 tasks: each fails loudly
    instead of becoming a 4% (or guessed) target."""
    for threshold in ("≥ 4 participants", "at least 4 users", "90"):
        dim = _success(threshold, 0.95)
        assert not dim.passed and "could not parse" in dim.evidence, threshold
    assert _success("≥ 0.8", 0.85).passed


def test_f05_static_module_imports_and_xhr_are_network_references():
    html = ("<script type=module>import { a } from 'https://cdn.example.com/a.js'; import 'https://cdn.example.com/b.js';"
            "const x = new XMLHttpRequest(); x.open('GET', 'https://api.example.com/lots');"
            "import { local } from './local.js';</script>")
    refs = prototype.external_refs(html)
    assert len(refs) == 3 and not any("local.js" in r for r in refs)


def test_tec_devdoc_needs_real_headings_not_lines_inside_a_code_block():
    from pdg.tools.feasibility import devdoc_missing
    dev = "# Development\n\n## Architecture\nx\n\n```md\n## Testing\n```\n"
    assert devdoc_missing(dev, ["Architecture", "Testing"]) == ["Testing"]
    assert devdoc_missing(dev + "\n## Testing (node --test)\nrun it\n", ["Architecture", "Testing"]) == []


def test_f04_a_non_zero_exit_fails_even_when_the_last_summary_says_all_passed(tmp_path, monkeypatch):
    """The threshold is "node --test exits 0": a run whose summary reads '# fail 0' but that exits 1 (an error after the
    tests, a failing hook) is a failure, not 5 passes."""
    out = "\n".join(["# tests 5", "# pass 5", "# fail 0", "Error: unhandled rejection after the last test"])
    monkeypatch.setattr(_node, "node_bin", lambda: "node")
    monkeypatch.setattr(_node.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=out, stderr="", returncode=1))
    passed, failed, _ = _node.unit(tmp_path / "t.test.js", tmp_path)
    assert (passed, failed) == (5, 1)


@pytest.mark.parametrize("html,found", [
    ("<p>Lot 7</p><script>const todo = open.map(x => x)</script>", []),
    ("<script>el.textContent = \"TODO: write the copy\"</script>", ["TODO"]),
    ("<p>Lorem ipsum</p>", ["Lorem", "ipsum"]),
    ("<!-- TODO later --><p>ok</p><style>.todo{}</style>", []),
])
def test_the_placeholder_scan_reads_what_a_user_can_read_not_script_identifiers(html, found):
    """Field run W41: BLD-PLACEHOLDER failed a build on `const todo = …` in the inline script. It reads the page's text and
    the strings its scripts render, never identifiers, comments or styles."""
    from pdg.tools.prototype import placeholders
    assert placeholders(html) == found


def test_f06_the_rendered_page_decides_when_a_browser_is_available(tmp_path):
    """Batch 8 (found reading pyflakes output): since the configuration batch, `visible_text_with` returned right after
    its import, so CNT-PROVENANCE always fell back to the static scan and never looked at the rendered page. A label
    hidden by a stylesheet rule is invisible only in the rendered page."""
    import pytest
    from pdg.tools.browser import visible_text_with
    root = tmp_path / "p"
    root.mkdir()
    (root / "index.html").write_text("<html><head><title>Lots</title><style>.gone{display:none}</style></head><body><main>"
                                     "<h1>Queue</h1><p class='gone'>Synthetic data</p></main></body></html>")
    try:   # whether a browser exists is asked of Playwright itself: a broken helper also returns None
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            pw.chromium.launch().close()
    except Exception:  # noqa: BLE001
        pytest.skip("Chromium is not installed (python -m playwright install chromium)")
    assert visible_text_with(root / "index.html", "synthetic") == (False, "")
    (root / "lots.json").write_text(json.dumps([{"supplier": "Northwind Metals", "status": "ready"}]))
    (root / "build-manifest.json").write_text(json.dumps({"entry": "index.html"}))
    doc = {"datasets": [{"path": "lots.json", "records": 1, "provenance": "synthetic", "label_shown_in_ui": True}],
           "copy_deck": "copy.md", "edge_cases": ["none"]}
    ctx = FakeCtx({"content": doc}, thresholds={"content": {"min_records": 1}}, work=tmp_path)
    ctx.output = lambda key: root if key == "prototype" else None
    o = content.check(ctx).dimensions["CNT-PROVENANCE"]
    assert not o.passed and "(rendered page)" in o.evidence, o.evidence


def test_w49_a_screen_is_reached_by_its_route_its_backticked_id_or_its_parent_never_by_a_word_in_a_label():
    """Field run 1, W49: EXP-SCREENS looked for a screen id anywhere in the navigation text, so `signal` passed on
    "Regulatory signals" and failed once the label changed, with no change to how the screen is reached."""
    reqs = _fx("n04_requirements", "requirements.json")
    state = _state(product={"requirements": reqs["requirements"]})

    def orphans(navigation, extra):
        exp = _fx("n07_experience_architecture", "experience.json")
        exp["navigation"] = navigation
        exp["screens"] += extra
        dim = experience.check_flows(FakeCtx({"experience": exp}, state=state)).dimensions["EXP-SCREENS"]
        return dim.evidence.split("orphan screens ")[1].split(" (")[0] if "orphan screens" in dim.evidence else "none"
    signal = {"id": "signal", "name": "Signal record", "purpose": "Read one signal", "route": "#/signal", "kind": "record"}
    feed = {"id": "feed", "name": "Feed", "purpose": "All signals", "route": "#/feed", "kind": "list"}
    base = ["Lot queue (#/queue)", "Decision log (#/audit)"]
    assert orphans(base + ["Signal Feed › Regulatory signals (#/feed/regulatory)"], [signal, feed]) == "['signal', 'feed']"
    assert orphans(base + ["Signals (#/signal)"], [signal]) == "none"                      # the route, as a whole route
    assert orphans(base + ["Signals (#/signal)."], [{**signal, "route": "/signal"}]) == "none"   # written without its #
    assert orphans(base + ["Signals (#/signals)"], [signal]) == "['signal']"                # another route is not it
    assert orphans(base + ["Record `signal`"], [signal]) == "none"                          # the id in backticks
    assert orphans(base + ["signal"], [signal]) == "none"                                   # the id as a whole entry
    child = {"id": "drawer", "name": "Related", "purpose": "Related records", "route": "#/signal/related",
             "parent": "signal", "kind": "list"}
    assert orphans(base + ["Signals (#/signal)"], [signal, child]) == "none"                # a nested route under it
    assert orphans(base, [signal, child]) == "['signal', 'drawer']"                         # an orphan's child is one too
    # the review's edge cases: written forms of a whole route, and what is not one
    assert orphans(base + ["Feed (#/feed/signal)"], [signal]) == "['signal']"               # the end of another route
    assert orphans(base + ["Signals (#/signal/)"], [signal]) == "none"                      # a trailing slash
    assert orphans(base + ["Signals (/signal)"], [signal]) == "none"                        # written without its #
    assert orphans(base + ["Signals (index.html#/signal)"], [signal]) == "none"             # after the entry file
    assert orphans(base + ["Signals (?fail=1#/signal)"], [signal]) == "none"                # after a query
    assert orphans(base + ["Failing (?fail=1#/signal)"], [{**signal, "route": "?fail=1#/signal"}]) == "none"  # a query route
    assert orphans(base + ["#/signal: one record"], [signal]) == "none"                     # a colon in prose
    assert orphans(base + ["Signals (#/signal:x)"], [signal]) == "['signal']"
    assert orphans(base + ["Café (#/café)"], [{**signal, "route": "#/caf%C3%A9"}]) == "none"  # percent-encoded
    home = {"id": "home", "name": "Home", "purpose": "Start", "route": "#/", "kind": "dashboard"}
    assert orphans(base + ["Cases / Lots (#/cases)"], [home]) == "['home']"                # a slash is not the root
    assert orphans(base + ["Home (#/)"], [home]) == "none"
    assert orphans(base + ["C# notes / #"], [{**home, "route": "#"}]) == "['home']"          # a bare # is the root
    assert orphans(base + ["C# notes / #"], [{**home, "route": ""}]) == "['home']"
    assert orphans(base + ["Lot queue (#/lots)"], [{**signal, "id": "q", "route": "queue"}]) == "['q']"
    assert orphans(base + ["Lot queue (#queue)"], [{**signal, "id": "q", "route": "queue"}]) == "none"
    # a parent passes reachability only down to a record, a form or a nested route (W49 review, I1)
    record = {"id": "rec", "name": "Record", "purpose": "One signal", "route": "#/r/1", "parent": "signal", "kind": "record"}
    settings = {"id": "settings", "name": "Settings", "purpose": "Preferences", "route": "#/settings", "parent": "signal",
                "kind": "dashboard"}
    assert orphans(base + ["Signals (#/signal)"], [signal, record, settings]) == "['settings']"
    exp = _fx("n07_experience_architecture", "experience.json")
    exp["navigation"], exp["screens"] = base + ["Signals (#/signal)"], exp["screens"] + [signal, record]
    dim = experience.check_flows(FakeCtx({"experience": exp}, state=state)).dimensions["EXP-SCREENS"]
    assert dim.passed and "reached only through its parent: rec ← signal" in dim.evidence, dim.evidence


def test_w51_a_mixed_dataset_names_what_was_verified_and_against_which_known_source(tmp_path, monkeypatch):
    """Field run 1, W51: provenance was real, synthetic or invented, so a dataset verified field by field against a
    source, with synthetic statuses, could not say which fields a reviewer should hold to the source."""
    from pydantic import ValidationError
    import pdg.tools.browser as b
    from pdg.artifacts import Dataset
    base = {"path": "d.json", "records": 1, "label_shown_in_ui": True}
    with pytest.raises(ValidationError, match="names its verified_fields"):
        Dataset.model_validate({**base, "provenance": "mixed", "verified_fields": ["title"]})
    with pytest.raises(ValidationError, match="apply to a mixed dataset"):
        Dataset.model_validate({**base, "provenance": "synthetic", "verified_fields": ["title"], "source_ids": ["S-01"]})
    with pytest.raises(ValidationError, match="a blank entry names nothing"):
        Dataset.model_validate({**base, "provenance": "mixed", "verified_fields": [" "], "source_ids": ["S-01"]})
    assert Dataset.model_validate({**base, "provenance": "mixed", "verified_fields": ["title "],
                                   "source_ids": [" S-01"]}).source_ids == ["S-01"]
    monkeypatch.setattr(b, "visible_text_with", lambda entry, word, timeout_ms=3000: None)
    root = tmp_path / "proto"
    root.mkdir()
    (root / "index.html").write_text("<html><body><main><p>Synthetic data: demo only</p></main></body></html>")
    (root / "d.json").write_text(json.dumps([{"title": "A study", "status": "open"}]))
    (root / "build-manifest.json").write_text(json.dumps({"entry": "index.html"}))
    state = _state(inputs={"sources": [{"id": "S-01", "kind": "data", "title": "Demo set", "evidence": "observed"}]},
                   research={"evidence": [{"id": "E-01", "claim": "Titles match", "source_ids": ["S-01"], "tag": "observed"}]})

    def dim(source_ids, label=True, fields=("title",)):
        ds = {**base, "provenance": "mixed", "verified_fields": list(fields), "source_ids": source_ids,
              "label_shown_in_ui": label}
        ctx = FakeCtx({"content": {"datasets": [ds], "copy_deck": "c.md", "edge_cases": ["none"]}}, state=state,
                      thresholds={"content": {"min_records": 1}}, work=tmp_path)
        ctx.output = lambda key: root if key == "prototype" else None
        return content.check(ctx).dimensions["CNT-PROVENANCE"]
    ok = dim(["S-01", "E-01"])                                          # a source or an evidence id
    assert ok.passed and "d.json: title against S-01, E-01" in ok.evidence, ok.evidence
    unknown = dim(["S-01", "S-99"])
    assert not unknown.passed and "does not know: d.json: ['S-99']" in unknown.evidence, unknown.evidence
    assert not dim(["S-01"], label=False).passed                        # partly synthetic data is still labelled
    typo = dim(["S-01"], fields=("title", "titel"))                     # a field no record holds checks nothing
    assert not typo.passed and "no record holds: d.json: ['titel']" in typo.evidence, typo.evidence
    (root / "d.json").write_text(json.dumps([{"study": {"title": "A study"}, "status": "open"}]))
    assert dim(["S-01"], fields=("study.title",)).passed                # a dotted path into the record


def test_n29_a_contrast_ratio_design_md_states_must_be_the_one_the_tokens_give(tmp_path):
    """Field run 1, v10 round: N09 a6 stated card on red-ink as 6.60:1 in design.md's table; the tokens give 6.91:1.
    VIS-CONTRAST computed only the JSON pairs, so the approver's table was wrong and a delegate caught it by hand. Only
    the column headed as the measured ratio is read; a stated ratio may be cut or rounded to its decimals, never rounded
    up across a WCAG step; a CSS custom property or var() names its token (review I1, S1)."""
    from pdg.tools import design_system
    ds = {"colors": [{"name": "ink", "value": "#1A1A1A", "role": "text", "provenance": "brand"},
                     {"name": "card", "value": "#FFFFFF", "role": "surface", "provenance": "brand"},
                     {"name": "hint", "value": "#777777", "role": "text", "provenance": "brand"},
                     {"name": "veil", "value": "rgba(0,0,0,.4)", "role": "scrim", "provenance": "brand"}],
          "type_scale": [{"name": "body", "size_px": 16, "weight": 400, "line_height": 1.5}], "spacing_px": [8],
          "radii_px": [4], "contrast_pairs": [{"fg": "ink", "bg": "card", "use": "body"}], "components": [],
          "breakpoints_px": [640], "motion": [], "prohibited": ["gradients"], "accessibility": []}
    template = "| Foreground | Background | Ratio | Minimum | Use |"

    def vis(*rows, head=template, after="", rule="|---|---|---|---|---|"):
        md = tmp_path / "design.md"
        md.write_text("## Contrast\n\n" + head + "\n" + rule + "\n" + "\n".join(rows) + "\n" + after)
        ctx = FakeCtx({"design_system": ds})
        ctx.output = lambda key: md if key == "design_md" else None
        dims = design_system.check(ctx).dimensions
        assert dims["VIS-CONTRAST"].passed, dims["VIS-CONTRAST"].evidence   # a table typo is not a contrast failure (L-07)
        return dims["VIS-RATIO-STATED"]
    assert f"{design_system.contrast('#1A1A1A', '#FFFFFF'):.3f}" == "17.404"
    assert f"{design_system.contrast('#777777', '#FFFFFF'):.3f}" == "4.478"
    ok = vis("| ink | card | 17.40:1 | 4.5:1 | body |")
    assert ok.passed and "design.md: 1 stated ratio checked" in ok.evidence, ok.evidence
    assert vis("| `--ink` | `var(--card)` | 17.4:1 | 4.5:1 | body |").passed    # CSS names, one decimal
    assert vis("| ink | card | 17:1 | 4.5:1 | body |").passed               # cut to a whole number
    assert vis("| ink | card | **17.40:1** | 4.5:1 | body |").passed         # emphasis is not part of the ratio
    assert vis("| hint | card | 4.48:1 | 4.5:1 | a hint, not a declared pair |", "| hint | card | 4.4:1 | 4.5:1 | cut |").passed
    assert vis("| Ink | Card | 3.00:1 | 4.5:1 | a row that names no token |").passed
    assert vis("| veil | card | 9.99:1 | 3:1 | a translucent scrim has no single ratio |").passed
    for decorated in ("17.40:1 ✓", "17,40:1", "≈17.4:1", "17.40:1 (AAA)"):         # skipped, never read as the 4.5:1 beside it
        assert vis(f"| ink | card | {decorated} | 4.5:1 | body |").passed, decorated
    bad = vis("| ink | card | 16.60:1 | 4.5:1 | body |")
    assert not bad.passed and "ink/card stated 16.60:1, measures 17.40:1" in bad.evidence, bad.evidence
    assert not vis("| ink | card | **16.60:1** | 4.5:1 | body |").passed
    assert not vis("| ink | card | 17.2:1 | 4.5:1 | body |").passed           # one decimal, 0.2 off
    assert not vis("| ink | card | 18:1 | 4.5:1 | body |").passed             # rounded up by more than half
    assert not vis("| `--ink` | `--card` | 16.60:1 | 4.5:1 | body |").passed
    assert not vis("| var(--ink) | card | 16:1 | 4.5:1 | body |").passed
    up = vis("| hint | card | 4.5:1 | 4.5:1 | a hint |")                      # 4.478 is not 4.5:1
    assert not up.passed and "hint/card stated 4.5:1, rounds up across 4.5:1 (measures 4.48:1)" in up.evidence, up.evidence
    required_first = "| Foreground | Background | Required contrast | Measured contrast | Use |"
    assert vis("| ink | card | 4.5:1 | 17.40:1 | body |", head=required_first).passed
    assert not vis("| ink | card | 4.5:1 | 16.60:1 | body |", head=required_first).passed
    alias = "\n## Aliases\n\n| Token | Alias | Note | Use |\n|---|---|---|---|\n| ink | card | 16:1 | outline |\n"
    assert vis("| ink | card | 17.40:1 | 4.5:1 | body |", after=alias).passed    # a table without a ratio column
    unread = vis("| ink | card | 16.60:1 | 4.5:1 | body |", head="| Token | Alias | Width | Note | Use |")
    assert unread.passed and "design.md: 0 stated ratios checked" in unread.evidence, unread.evidence   # it says so
    # the review's headers and rules that left a table unread (S1, S2) and a ratio in backticks
    for head in ("| Foreground | Background | Luminance contrast | Minimum | Use |",
                 "| Foreground | Background | Contrast (WCAG AA) | Minimum | Use |"):
        assert not vis("| ink | card | 16.60:1 | 4.5:1 | body |", head=head).passed, head
    assert not vis("| ink | card | 16.60:1 | 4.5:1 | body |", rule="|:--|:--|--:|-|-|").passed
    assert not vis("| ink | card | `16.60:1` | 4.5:1 | body |").passed


def test_w53_a_plan_samples_only_screens_the_design_has():
    from pdg.artifacts import Screen
    from pdg.tools import plan
    from .conftest import FakeCtx
    st = _plan_state()
    st.design.screens = [Screen(id="lot", name="Lot", purpose="One lot", route="#/lot/L-1", kind="record")]
    p = _plan()
    assert not [e for e in plan.check(FakeCtx({"plan": p}, state=st)).errors if "samples" in e]
    p["samples"] = {"lot": ["#/lot/L-9"], "nope": ["#/x"]}
    errs = [e for e in plan.check(FakeCtx({"plan": p}, state=st)).errors if "samples" in e]
    assert errs == ["`samples` names screens the design does not have: ['nope']"], errs
    p["samples"] = {"lot": ["#/lot/L-1", " "]}                              # its own route, a blank: not more records
    errs = [e for e in plan.check(FakeCtx({"plan": p}, state=st)).errors if "samples" in e]
    assert errs == ["`samples` must be more records of their screen, not a design screen's route or blank: [' ', '#/lot/L-1']"], errs
    # PLN-SAMPLES (SHOULD, L-07): a record screen names two or more worst-case records for the width checks
    p["samples"] = {"lot": ["#/lot/L-9"]}
    dim = plan.check(FakeCtx({"plan": p}, state=st)).dimensions["PLN-SAMPLES"]
    assert not dim.passed and dim.evidence == "1 record screen(s); fewer than 2 samples: lot (1)", dim.evidence
    p["samples"] = {"lot": ["#/lot/L-7", "#/lot/L-9"]}
    dim = plan.check(FakeCtx({"plan": p}, state=st)).dimensions["PLN-SAMPLES"]
    assert dim.passed and dim.evidence == "1 record screen(s): each names its worst-case records in `samples`", dim.evidence


def test_r2_26_a_documented_state_fill_is_a_status_colour_design_md_names(tmp_path):
    """Batch 18 review S8: `state_fill_of` exempts a component's state from VIS-STATE-FILLS, so it is checked where N09
    writes it: on a status colour only, and for a class design.md mentions (a generic "btn" would exempt every button)."""
    from pdg.tools import design_system
    ds = {"colors": [{"name": "ink", "value": "#1A1A1A", "role": "text", "provenance": "brand"},
                     {"name": "card", "value": "#FFFFFF", "role": "surface", "provenance": "brand", "state_fill_of": []},
                     {"name": "red-dim", "value": "#FDE8E1", "role": "alert: held pills; the active filter too",
                      "provenance": "brand", "state_fill_of": ["sf-btn"]}],
          "type_scale": [{"name": "body", "size_px": 16, "weight": 400, "line_height": 1.5}], "spacing_px": [8],
          "radii_px": [4], "contrast_pairs": [{"fg": "ink", "bg": "card", "use": "body"}], "components": [],
          "breakpoints_px": [640], "motion": [], "prohibited": ["gradients"], "accessibility": []}
    md = tmp_path / "design.md"

    def errors(text, colours=None):
        md.write_text(text)
        ctx = FakeCtx({"design_system": {**ds, "colors": colours or ds["colors"]}})
        ctx.output = lambda key: md if key == "design_md" else None
        return design_system.check(ctx).errors
    assert errors("The filter button `sf-btn` fills red-dim when active.") == []
    assert errors("The filter button fills red-dim when active.") == [
        "red-dim's `state_fill_of` names ['sf-btn'], which design.md does not mention: say there which state of which "
        "component it fills"]
    assert errors("The `sf-btn-group` wraps the filters.") != []                 # a longer class is not the class
    card = {**ds["colors"][1], "state_fill_of": ["sf-btn"]}
    assert errors("The `sf-btn` is the filter button.", [ds["colors"][0], card, ds["colors"][2]]) == [
        "card lists `state_fill_of` but is no status colour (by name or role): nothing to exempt"]
