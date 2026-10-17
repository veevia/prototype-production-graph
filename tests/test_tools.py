"""Deterministic tools on good and bad inputs."""

from __future__ import annotations

import json

from pdg.tools import concepts, design_system, plan, product
from pdg.tools._common import contrast, sentences
from pdg.tools.prototype import external_refs, off_token_colours, placeholders

from .conftest import PKG, FakeCtx

FIX = PKG / "examples" / "coa-review" / "fixtures"


def _fx(node: str, name: str, attempt: int = 1):
    return json.loads((FIX / node / f"attempt-{attempt}" / name).read_text())


def test_wcag_contrast_matches_known_values():
    assert round(contrast("#000000", "#FFFFFF"), 1) == 21.0
    assert round(contrast("#767676", "#FFFFFF"), 2) == 4.54
    assert contrast("#6B7280", "#EEF0F3") < 4.5 < contrast("#4A5361", "#EEF0F3")


def test_sentence_counter():
    assert sentences("One sentence, with a comma.") == 1
    assert sentences("Two sentences. Here is the second.") == 2


def test_static_scanners():
    assert external_refs('<img src="https://cdn.example/x.png"><a href="#/queue">') == ['src="https://']
    assert external_refs('<svg xmlns="http://www.w3.org/2000/svg"></svg>') == []
    css = "<style>:root{--a:#123456} .x{color:var(--a)} .y{color:#FF0000}</style>"
    assert off_token_colours(css) == ["#FF0000"]
    assert placeholders('<input placeholder="Search"> Lorem ipsum') == ["Lorem", "ipsum"]


def test_design_system_check_fails_an_undeclared_low_contrast_pair():
    ds = _fx("n09_visual_system", "design-system.json")
    ok = design_system.check(FakeCtx({"design_system": ds}))
    assert ok.dimensions["VIS-CONTRAST"].passed and ok.dimensions["VIS-TYPE"].passed
    ds["contrast_pairs"].append({"fg": "color-text-subtle", "bg": "color-surface-alt", "use": "chips"})
    bad = design_system.check(FakeCtx({"design_system": ds}))
    assert not bad.dimensions["VIS-CONTRAST"].passed
    assert "color-text-subtle on color-surface-alt" in bad.dimensions["VIS-CONTRAST"].evidence


def test_scope_quality_bars():
    scope = _fx("n05_scope_success", "scope.json")
    assert all(d.passed for d in product.check_scope(FakeCtx({"scope": scope})).dimensions.values())
    scope["rollback_triggers"] = ["if things go bad"]
    scope["scope"]["non_goals"] = []
    scope["success_criteria"][0]["target"] = "much faster"
    res = product.check_scope(FakeCtx({"scope": scope}))
    assert not res.dimensions["SCP-ROLLBACK"].passed
    assert not res.dimensions["SCP-NONGOALS"].passed
    assert not res.dimensions["SCP-NUMBERS"].passed


def test_concepts_override_needs_a_rationale():
    from pdg.models import ProjectState
    doc = _fx("n06_concept_ideation", "concepts.json")
    reqs = _fx("n04_requirements", "requirements.json")
    st = ProjectState.model_validate({"schema_version": "t", "project": {"id": "t", "name": "t", "created": "n", "workflow_id": "w",
                                      "workflow_version": "1"}, "product": {"requirements": reqs["requirements"]}})
    assert concepts.check(FakeCtx({"concepts": doc}, state=st)).dimensions["CON-MATRIX"].passed
    doc["selected"], doc["rationale"] = "K-3", "gut feel"
    assert not concepts.check(FakeCtx({"concepts": doc}, state=st)).dimensions["CON-MATRIX"].passed


def test_fidelity_gate_refuses_mid_fidelity_on_an_unvalidated_riskiest_assumption():
    from pdg.models import ProjectState
    ev = _fx("n02_evidence_review", "evidence.json", 2)
    p = _fx("n10_prototype_planning", "plan.json")
    st = ProjectState.model_validate({"schema_version": "t", "project": {"id": "t", "name": "t", "created": "n", "workflow_id": "w",
                                      "workflow_version": "1"}, "research": {"assumptions": ev["assumptions"],
                                                                              "evidence": ev["evidence"]}})
    assert plan.check(FakeCtx({"plan": p}, state=st)).dimensions["PLN-FIDELITY-GATE"].passed
    p["riskiest_assumptions"][0]["status"] = "unvalidated"
    res = plan.check(FakeCtx({"plan": p}, state=st))
    assert not res.dimensions["PLN-FIDELITY-GATE"].passed
    p["fidelity"] = "low"  # lowering the fidelity is a valid fix
    assert plan.check(FakeCtx({"plan": p}, state=st)).dimensions["PLN-FIDELITY-GATE"].passed


def test_a_lesson_resting_only_on_simulated_feedback_cannot_be_classed_verified():
    from types import SimpleNamespace

    from pdg.models import Defect, Feedback
    from pdg.tools.learning import check_lessons

    ctx = FakeCtx({})
    ctx.engine.rules = SimpleNamespace(rules=[{"id": "R-A11Y-001"}])
    ev = ctx.state.evaluation
    ev.feedback.append(Feedback(id="FB-001", actor="participant:P4", human=False, simulated=True, text="layout", created="now"))
    base = dict(dimension="X", severity="P2", message="m", evidence="e", trace_reason="r", smallest_fix="f", acceptance_check="a")
    ev.defects.append(Defect(id="D-001", signature="LAYOUT@lot", traced_node="n08_interaction_design", feedback_ids=["FB-001"], **base))
    ev.defects.append(Defect(id="D-002", signature="A11Y-AXE@queue", traced_node="n11_prototype_development", **base))

    def verdict(evidence_class, evidence):
        ctx._docs = {"lessons": {"summary": "s", "lessons": [{"id": "L-01", "statement": "s", "scope": "reusable",
                                                               "evidence_class": evidence_class, "evidence": evidence}]}}
        return check_lessons(ctx).dimensions["LRN-HONEST"].passed

    assert not verdict("verified", ["D-001", "FB-001", "comparison:cycle-1"])   # simulated support only
    assert verdict("inferred", ["D-001", "FB-001"])
    assert verdict("verified", ["D-002", "comparison:cycle-1"])                # a measured (tool) finding


def test_the_token_block_may_declare_only_design_system_colours():
    """Field run 2, R2-08: a build moved every literal into 75 generated `:root` variables, so the token rule passed with
    38 colours the design system never had. The block's colours are checked against the approved system."""
    from pdg.artifacts import DesignSystemDoc
    from pdg.tools.prototype import token_block_extras
    ds = DesignSystemDoc.model_validate(_fx("n09_visual_system", "design-system.json"))
    first = ds.colors[0].value
    ok = f"<style>:root{{--a:{first}; --shadow: rgba(27, 31, 36, 0.08)}}</style>"
    assert token_block_extras(ok, ds) == []
    bad = f"<style>:root{{--n11-color-1:{first}; --n11-color-2:#123456}} [data-theme=dark]{{--x:hsl(0 0% 10%)}}</style>"
    assert token_block_extras(bad, ds) == ["#123456", "#1A1A1A"]
    assert token_block_extras(bad, None) is None


def test_a_design_system_can_declare_a_translucent_token_but_not_pair_it_for_contrast():
    """R2-08: shadows and scrims could not be declared (only #rrggbb), so the build's token block could not match."""
    ds = _fx("n09_visual_system", "design-system.json")
    ds["colors"].append({"name": "scrim", "value": "rgba(0, 0, 0, 0.4)", "role": "dialog scrim", "provenance": "t"})
    assert not design_system.check(FakeCtx({"design_system": ds})).errors
    ds["contrast_pairs"].append({"fg": "scrim", "bg": ds["colors"][0]["name"], "use": "overlay"})
    assert any("translucent" in e for e in design_system.check(FakeCtx({"design_system": ds})).errors)



def test_one_colour_matches_however_it_is_spelled():
    """R2-08 in the field: the first run's build wrote `rgba(0,0,0,.15)`; a design system writing `rgba(0, 0, 0, 0.15)`
    must match it, or declaring the colour could never clear the finding."""
    from pdg.artifacts import DesignSystemDoc
    from pdg.tools.prototype import token_block_extras
    ds = _fx("n09_visual_system", "design-system.json")
    ds["colors"].append({"name": "scrim", "value": "rgba(0, 0, 0, 0.15)", "role": "scrim", "provenance": "t"})
    assert token_block_extras("<style>:root{--s: rgba(0,0,0,.15)}</style>", DesignSystemDoc.model_validate(ds)) == []



def test_every_spelling_of_a_colour_is_one_colour_on_both_sides():
    """Field run 2, R2-16: `rgb(255 255 255 / 40%)` could be neither declared in N09 nor matched by BLD-TOKENS. Both
    sides use one canonical form, so any CSS spelling of the same colour matches."""
    from pdg.artifacts import DesignSystemDoc
    from pdg.tools._common import canonical_colour
    from pdg.tools.prototype import token_block_extras
    same = ["rgb(255 255 255 / 40%)", "rgba(255,255,255,.4)", "#ffffff66", "hsla(0, 0%, 100%, 0.4)"]
    assert {canonical_colour(v) for v in same} == {"rgba(255,255,255,0.4)"}
    assert {canonical_colour(v) for v in ("#1a1a1a", "rgb(26,26,26)", "rgb(26 26 26 / 100%)", "#1A1A1AFF")} == {"#1A1A1A"}
    ds = _fx("n09_visual_system", "design-system.json")
    ds["colors"].append({"name": "scrim", "value": "rgb(255 255 255 / 40%)", "role": "scrim", "provenance": "t"})
    assert not design_system.check(FakeCtx({"design_system": ds})).errors
    assert token_block_extras("<style>:root{--s: rgba(255,255,255,.4)}</style>", DesignSystemDoc.model_validate(ds)) == []


def test_a_screen_marked_only_in_a_compiled_bundle_counts_as_implemented(tmp_path):
    """Field run 2, R2-17: a compiled React build writes `"data-screen": "hub"` in its scripts, never the markup
    attribute, so BLD-SCREENS failed with every screen implemented."""
    from pdg.tools.prototype import screen_markers
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text('_jsx("section",{"data-screen":"hub",children:x});'
                                                'React.createElement("main",{"data-screen": "case"});'
                                                "el.setAttribute('data-screen','audit'); el.dataset.screen = 'lot';")
    html = '<div id="root"></div><section data-screen="queue"></section><script src="assets/app.js"></script>'
    assert screen_markers(tmp_path, html) == {"hub", "case", "audit", "lot", "queue"}


def test_a_lookup_is_not_a_marker_and_one_huge_bundle_does_not_end_the_scan(tmp_path):
    """Batch 7 review I5: `querySelector('[data-screen="settings"]')` counted as building the screen, and one file over
    the 30 MB budget, sorted first, stopped the whole scan, so a vendor bundle failed BLD-SCREENS."""
    from pdg.tools.prototype import screen_markers
    (tmp_path / "a-vendor.js").write_text(" " * 31_000_000)
    (tmp_path / "b-app.js").write_text("""document.querySelector('[data-screen="settings"]');"""
                                       """el.closest("[data-screen='audit']"); root.innerHTML = '<main data-screen=\\"tpl\\">';"""
                                       """_jsx("section", {"data-screen": "hub"});""")
    (tmp_path / "node_modules" / "lib").mkdir(parents=True)
    (tmp_path / "node_modules" / "lib" / "x.js").write_text('_jsx("div", {"data-screen": "vendored"})')
    html = '<style>[data-screen="css"] { display: grid }</style><div id="root"></div>'
    assert screen_markers(tmp_path, html) == {"hub", "tpl"}


def test_an_alert_colour_is_reserved_in_every_spelling():
    """Batch 7 review S3: VIS-ALERT-RESERVED compared raw spellings, so once rgb() and hsl() tokens were accepted,
    `rgb(220 38 38)` reused the alert red `#DC2626` unnoticed."""
    ds = _fx("n09_visual_system", "design-system.json")
    ds["colors"] = [c for c in ds["colors"] if not any(w in c["role"].lower() for w in ("alert", "danger", "error"))]
    ds["colors"] += [{"name": "danger", "value": "#DC2626", "role": "danger alert", "provenance": "t"},
                     {"name": "brand-accent", "value": "rgb(220 38 38)", "role": "accent", "provenance": "t"}]
    res = design_system.check(FakeCtx({"design_system": ds}))
    assert not res.errors
    row = res.dimensions["VIS-ALERT-RESERVED"]
    assert not row.passed and "brand-accent" in row.evidence
