"""Guarantee tests from the 2026-09-26 test-strategy audit. Each test names the documented guarantee it proves and fails
when that guarantee is broken by a one-line change in pdg/ that the rest of the suite let through (checked by
mutation). Most tests share one finished run of the fictional example (browser stubbed) and change a private copy of
it; the others drive a short real (non-dry-run) project through task packets and named-human decisions."""

from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path

import pytest
import yaml

import pdg.lock as lock
import pdg.tools.browser as browser
from pdg.cli import main
from pdg.context import CheckResult, NodeContext, NodeResult
from pdg.engine import Engine, EngineError
from pdg.evaluation import load_rubrics, merge_review
from pdg.executors import ScriptedExecutor
from pdg.gating import release_verify, review_gate
from pdg.graph import load_workflow
from pdg.models import Defect, NodeStatus
from pdg.provenance import Ledger
from pdg.tools._common import finding

from .conftest import EXAMPLE, copy_example, fake_browser

INTAKE, PROBLEM, REQS, GATE = "n01_context_intake", "n03_problem_definition", "n04_requirements", "n16_feedback_diagnosis"
EVIDENCE = "n02_evidence_review"
FIXTURES = EXAMPLE / "fixtures"
TYPED = ("inputs", "product", "research", "design", "build", "evaluation", "knowledge", "controls")


@pytest.fixture(scope="module")
def finished(tmp_path_factory) -> Path:
    """One finished run of the example: the intake loop, one rework cycle, RUN_PASS on build v2."""
    project = copy_example(tmp_path_factory.mktemp("finished") / "proj")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(browser, "check", fake_browser)
        eng = Engine(project)
        eng.run(max_steps=400)
    assert eng.state.runtime.status.value == "RUN_PASS" and eng.state.build.version == 2
    return project


@pytest.fixture
def done(finished, tmp_path, fast_browser) -> Engine:
    """A private copy of the finished run, opened by a new engine."""
    copy = tmp_path / "done"
    shutil.copytree(finished, copy, symlinks=True)
    return Engine(copy)


def _real(tmp_path: Path, scripted: bool = False) -> Engine:
    """A real (non-dry-run) project: agents get task packets (or scripted fixtures) and only named humans decide gates."""
    project = copy_example(tmp_path / "real", dry_run=False)
    return Engine(project, executor=ScriptedExecutor(project / "fixtures") if scripted else None)


def _write(eng: Engine, node: str, name: str, doc) -> str:
    """Write an agent's output into the node's current work folder; return the name to submit."""
    work = eng.project.root / "work" / node / f"a{eng.rt(node).attempt}"
    (work / name).write_text(doc if isinstance(doc, str) else json.dumps(doc))
    return name


def _typed_on_disk(eng: Engine) -> dict:
    saved = json.loads(eng.project.state_path.read_text())
    return {k: saved[k] for k in TYPED}


def _last_seq(eng: Engine) -> int:
    return max(e["seq"] for e in eng.ledger.events())


def _saved(project: Path) -> tuple[bytes, bytes]:
    """The run's saved state and ledger, byte for byte: a refused command leaves both alone."""
    return (project / ".pdg" / "state.json").read_bytes(), (project / ".pdg" / "ledger.jsonl").read_bytes()


def _at_problem_gate(tmp_path: Path) -> Engine:
    """A real project whose scripted agents ran up to N03, which now waits for a named human."""
    eng = _real(tmp_path, scripted=True)
    eng.run(max_steps=100)
    assert eng.rt(PROBLEM).status == NodeStatus.WAITING_HUMAN
    return eng


def _fixture(fixtures: Path, node: str, attempt: int) -> tuple[Path, dict[str, str]]:
    """A node's scripted fixture folder (its latest attempt up to `attempt`) and its outputs (key → file name)."""
    fx = next(fixtures / node / f"attempt-{n}" for n in range(attempt, 0, -1) if (fixtures / node / f"attempt-{n}").is_dir())
    return fx, yaml.safe_load((fx / "fixture.yaml").read_text())["outputs"]


def _submit_fixture(eng: Engine, node: str, replace: dict | None = None) -> dict:
    """Play the node's agent: write its fixture outputs (some files replaced) into its work folder and submit them."""
    fx, outputs = _fixture(FIXTURES, node, eng.rt(node).attempt)
    written = {key: _write(eng, node, name, (replace or {}).get(name, (fx / name).read_text()))
               for key, name in outputs.items()}
    return eng.submit(node, written, eng.rt(node).token, f"agent:{eng.node(node).agent}")


class _PendingFor(ScriptedExecutor):
    """Scripted agents, except that the named nodes wait for a real submission on their first dispatch."""

    def __init__(self, fixtures: Path, nodes: set[str]):
        super().__init__(fixtures)
        self.nodes, self.seen = nodes, set()

    def execute(self, ctx):
        if ctx.node.id in self.nodes and ctx.node.id not in self.seen:
            self.seen.add(ctx.node.id)
            return NodeResult(pending=True)
        return super().execute(ctx)


# ------------------------------------------------------------------------------------------------ schema validation
BAD_SOURCES = {
    "unknown-key": lambda good: {**good, "reviewer_note": "a key the sources schema does not define"},
    "evidence-tag-outside-the-enum": lambda good: {**good, "sources": [{**good["sources"][0], "evidence": "rumour"},
                                                                       *good["sources"][1:]]},
    "sources-not-a-list": lambda good: {"sources": "S-01, S-02"},
}


@pytest.mark.parametrize("case", sorted(BAD_SOURCES))
def test_a_schema_invalid_submission_is_refused_and_the_node_keeps_its_attempt(tmp_path, case):
    """state-model.md, "How state changes": a malformed agent output never reaches the state. A malformed file is a
    slip, not a quality failure, so `submit` refuses it by name, changing nothing, and the same packet can submit the
    corrected file (field run 2, R2-02: one schema slip cost N07 one of its three attempts)."""
    eng = _real(tmp_path)
    eng.run()
    rt = eng.rt(INTAKE)
    assert rt.status == NodeStatus.WAITING_AGENT
    attempt, token = rt.attempt, rt.token
    good = json.loads((FIXTURES / INTAKE / "attempt-2" / "sources.json").read_text())
    name = _write(eng, INTAKE, "sources.json", BAD_SOURCES[case](good))
    saved = _saved(eng.project.root)
    with pytest.raises(EngineError, match=r"(?s)no attempt was used: output 'sources' fails schema 'sources'.*check-output"):
        eng.submit(INTAKE, {"sources": name}, token, "agent:context-research")
    assert _saved(eng.project.root) == saved and not eng.current("sources")
    assert (eng.rt(INTAKE).status, eng.rt(INTAKE).attempt, eng.rt(INTAKE).token) == (NodeStatus.WAITING_AGENT, attempt, token)
    _write(eng, INTAKE, "sources.json", good)
    res = eng.submit(INTAKE, {"sources": name}, token, "agent:context-research")
    assert not any("fails schema" in f for f in res["failures"] or [])


def test_check_output_runs_the_submit_schema_check_before_anything_is_submitted(tmp_path, capsys):
    """Backlog N-09: an agent checks a file against its node's declared output first, with no project and no token."""
    good = json.loads((FIXTURES / INTAKE / "attempt-2" / "sources.json").read_text())
    ok, bad = tmp_path / "ok.json", tmp_path / "bad.json"
    ok.write_text(json.dumps(good))
    bad.write_text(json.dumps(BAD_SOURCES["sources-not-a-list"](good)))
    assert main(["check-output", INTAKE, "sources", str(ok)]) == 0
    assert main(["check-output", INTAKE, "sources", str(bad)]) == 4
    assert "fails schema 'sources'" in capsys.readouterr().err
    assert main(["check-output", INTAKE, "no-such-key", str(ok)]) == 4


# ------------------------------------------------------------------------------------------------ the review gate
def _gate(eng: Engine, tmp_path: Path, defects: list[dict] | None = None):
    """Run N16's review gate on the current state with an interpretation holding these defects."""
    work = tmp_path / f"gate-{len(eng.state.evaluation.gates)}"
    work.mkdir()
    interpretation = work / "interpretation.json"
    interpretation.write_text(json.dumps({"defects": defects or [], "feedback": [], "summary": "audit coverage"}))
    ctx = NodeContext(eng, eng.node(GATE), 90, work, "t", "")
    ctx.submitted = {"interpretation": interpretation}
    res = review_gate(ctx)
    return res, eng.state.evaluation.gates[-1]


def _defect(traced_node: str) -> dict:
    return {"id": "D-901", "signature": "AUDIT-HOLD-REASON@queue", "dimension": "STAKEHOLDER-FEEDBACK", "severity": "P2",
            "message": "The queue hides why a lot is on hold", "evidence": "an audit fixture", "traced_node": traced_node,
            "trace_reason": "the spec leaves the hold reason out", "smallest_fix": "show the hold reason in the row",
            "acceptance_check": "every held lot shows its reason in the queue"}


@pytest.mark.parametrize("reason", ["a stale review", "a defect that needs a human", "the rework budget spent"],
                         ids=["stale-review", "needs-a-human", "budget-spent"])
def test_the_review_gate_blocks_for_each_reason_and_says_which(done, tmp_path, reason):
    """evaluation-and-gates.md, the gate's outcomes: `blocked` when a review is missing or stale, when a defect needs a
    human (its fix would change a locked document), or when max_rework_cycles is spent. Nothing is routed then."""
    eng, pol, version = done, done.wf.policies, done.state.build.version
    ev = eng.state.evaluation
    defects = []
    if reason == "a stale review":
        ev.reviews = [r for r in ev.reviews if not (r.node == "n15_feasibility_review" and r.build_version == version)]
        expected = f"reviews missing or stale for build v{version}: n15_feasibility_review"
    elif reason == "a defect that needs a human":
        defects = [_defect(REQS)]                                           # product.md was signed at N05
        expected = f"fixing it changes locked product.md (approve a change request with --writer {REQS})"
    else:
        eng.state.runtime.rework_cycles = pol.max_rework_cycles
        defects = [_defect("n08_interaction_design")]
        expected = f"rework budget spent ({pol.max_rework_cycles}/{pol.max_rework_cycles} cycles)"
    res, gate = _gate(eng, tmp_path, defects)
    assert res.outcome == gate.outcome == "blocked"
    assert len(gate.reasons) == 1 and expected in gate.reasons[0], gate.reasons
    assert gate.targets == [] and res.data["targets"] == []
    if reason == "a defect that needs a human":
        assert next(d for d in ev.defects if d.id == "D-901").status == "needs_human"


def test_the_review_gate_passes_a_clean_build_and_routes_a_defect_while_the_budget_lasts(done, tmp_path):
    """The contrast for the test above: the same state passes, and the same defect is routed to its traced node one
    cycle before the budget is spent."""
    eng, pol = done, done.wf.policies
    res, gate = _gate(eng, tmp_path)
    assert res.outcome == gate.outcome == "pass"
    eng.state.runtime.rework_cycles = pol.max_rework_cycles - 1
    res, gate = _gate(eng, tmp_path, [_defect("n08_interaction_design")])
    assert res.outcome == gate.outcome == "rework" and gate.targets == ["n08_interaction_design"]
    assert res.data["defects_by_target"] == {"n08_interaction_design": ["D-901"]}


def test_a_rework_cycle_that_opens_more_blocking_defects_than_it_resolves_is_recorded_as_regressed(project, monkeypatch):
    """evaluation-and-gates.md, "Comparison": after each rework cycle the gate records a verdict, `regressed` when more
    new blocking defects appeared than were resolved. Here the corrected build fixes the four defects found on build v1
    but loses the focus ring on five tab stops."""
    def regressing(ctx):
        res = fake_browser(ctx)
        if not json.loads((ctx.artifact("prototype") / "build-manifest.json").read_text()).get("overlays"):
            res.dim("A11Y-FOCUS", False, "5 tab stops without a visible focus ring", [finding(
                "A11Y-FOCUS", f"no visible focus on tab stop {i}", "P2", f"queue:tab-{i}", "n11_prototype_development",
                "give it a :focus-visible outline", f"tab stop {i} shows a focus ring") for i in range(1, 6)])
        return res

    monkeypatch.setattr(browser, "check", regressing)
    eng = Engine(project)
    for _ in range(300):
        if len(eng.state.evaluation.gates) == 2 or not eng.step():
            break
    ev = eng.state.evaluation
    assert [(g.outcome, g.build_version) for g in ev.gates] == [("rework", 1), ("rework", 2)]
    assert [(c.cycle, len(c.resolved), len(c.new), c.verdict) for c in ev.comparisons] == [(1, 4, 5, "regressed")]


def test_a_loop_that_spends_its_traversal_budget_escalates_instead_of_looping_again(tmp_path):
    """orchestration.md, "Loops and targeted rework": every loop has a budget that ends in an escalation to a named
    human, never an endless loop. Wei rejects the problem frame once more than E07 allows."""
    eng = _real(tmp_path, scripted=True)
    eng.run(max_steps=100)
    budget = next(e for e in eng.wf.edges if e.id == "E07").max_traversals
    for n in range(1, budget + 1):
        assert eng.rt(PROBLEM).status == NodeStatus.WAITING_HUMAN
        eng.decide(PROBLEM, "rejected", "Wei", f"Not the job the reviewers described (round {n}).")
        assert eng.state.runtime.loop_traversals["E07"] == n
        eng.run(max_steps=100)
    assert eng.rt(PROBLEM).status == NodeStatus.WAITING_HUMAN and eng.rt(PROBLEM).attempt == budget + 1
    eng.decide(PROBLEM, "rejected", "Wei", "Still not the job.")
    eng.run(max_steps=100)
    st = eng.state
    assert st.runtime.status.value == "BLOCKED" and eng.rt(PROBLEM).status == NodeStatus.BLOCKED
    esc = [e for e in st.runtime.escalations if e.open]
    assert [e.node for e in esc] == [PROBLEM]
    assert f"loop E07 ({PROBLEM} → {PROBLEM}) exhausted its {budget} traversals" in esc[0].reason
    assert st.runtime.loop_traversals["E07"] == budget and eng.rt(PROBLEM).attempt == budget + 1   # not dispatched again


# ------------------------------------------------------------------------------------------------ release verification
def _release(eng: Engine, tmp_path: Path, name: str) -> CheckResult:
    work = tmp_path / name
    work.mkdir()
    return release_verify(NodeContext(eng, eng.node("n18_final_verification"), 90, work, "t", ""))


@pytest.mark.parametrize("condition", ["no blocking defect open", "every review current", "prototype hashes verify"],
                         ids=["open-defect", "stale-review", "tampered-prototype"])
def test_the_release_check_fails_on_each_broken_condition_and_only_on_it(done, tmp_path, condition):
    """evaluation-and-gates.md, "Release verification": N18 recomputes its conditions from disk rather than trusting
    state. One broken condition fails the check on its own, by name, and nothing is packaged."""
    eng, st = done, done.state
    assert not _release(eng, tmp_path, "intact").errors
    if condition == "no blocking defect open":
        st.evaluation.defects.append(Defect(id="D-950", signature="AUDIT@queue", dimension="A11Y-AXE", severity="P2",
                                            message="found after the gate", evidence="an audit fixture",
                                            traced_node="n11_prototype_development", trace_reason="the build",
                                            smallest_fix="fix the contrast", acceptance_check="0 axe violations",
                                            opened_at_version=st.build.version))
    elif condition == "every review current":
        st.evaluation.reviews = [r for r in st.evaluation.reviews
                                 if not (r.node == "n15_feasibility_review" and r.build_version == st.build.version)]
    else:
        built = eng.project.root / st.artifacts[st.build.prototype.artifact].path
        page = next(p for p in sorted(built.rglob("*.html")))
        page.write_text(page.read_text() + "<!-- edited after the gate passed -->")
    res = _release(eng, tmp_path, "broken")
    assert len(res.errors) == 1 and res.errors[0].startswith(f"release condition failed: {condition} ("), res.errors
    assert not res.dimensions["REL-CONDITIONS"].passed and not (tmp_path / "broken" / "package").exists()


# ------------------------------------------------------------------------------------------------ feedback mapping
def test_feedback_the_interpreter_leaves_unmapped_fails_diagnosis_and_names_the_item(done):
    """evaluation-and-gates.md, "Defects": the interpreter must map every open feedback item (interpretation_complete).
    An unmapped item fails N16 by its id on every attempt, stays open, and the gate never decides without it."""
    eng = done
    gates, seq = len(eng.state.evaluation.gates), _last_seq(eng)
    fb = eng.add_feedback("The notice draft should name the lot's PO in the subject line.", "Wei", at="notice")
    eng.run(max_steps=100)
    fails = [f for e in eng.ledger.events("node_failed") if e["seq"] > seq and e["data"]["node"] == GATE
             for f in e["data"]["failures"]]
    unmapped = [f for f in fails if f.startswith(f"feedback {fb.id} (") and
                f.endswith("is neither mapped to a defect nor dismissed")]
    assert fails and unmapped == fails and len(fails) == eng.node(GATE).retry.max_attempts, fails
    assert eng.state.runtime.status.value == "BLOCKED" and eng.rt(GATE).status == NodeStatus.BLOCKED
    assert next(f for f in eng.state.evaluation.feedback if f.id == fb.id).status == "open"
    assert len(eng.state.evaluation.gates) == gates


# ------------------------------------------------------------------------------------------------ control documents
def test_a_control_install_is_refused_for_a_non_writer_and_for_an_empty_document(done, tmp_path):
    """control-documents.md, "How a change is installed": refused when the node does not list the document in
    controls.write, or when the submission is empty."""
    c = done.controls
    draft = tmp_path / "experience.md"
    draft.write_text(c.text("experience").replace("## Journeys\n", "## Journeys\n\nJ-9 A reviewer re-checks a lot.\n", 1))
    assert c.check_install("n07_experience_architecture", ["experience"], "experience", draft) == []   # its writer may
    assert c.check_install("n05_scope_success", done.node("n05_scope_success").controls.write, "experience", draft) == [
        "n05_scope_success may not write control document experience"]
    empty = tmp_path / "design.md"
    for blank in ("", "  \n\n"):
        empty.write_text(blank)
        assert c.check_install("n09_visual_system", ["design"], "design", empty) == ["design.md submitted empty"]


def test_a_change_request_unlocks_a_signed_document_for_the_rerun_writer_set(done, tmp_path):
    """B23: a named human's request unlocks a signed document for every rerun writer that writes it, except the
    signing gate; otherwise a cascade hits one lock per writer."""
    c = done.controls
    product = c.text("product")
    reworded = tmp_path / "product-n03.md"
    reworded.write_text(product.replace("## Problem\n", "## Problem\n\nReworded after the pilot.\n", 1))
    widened = tmp_path / "product-n04.md"
    widened.write_text(product.replace("## Constraints\n", "## Constraints\n\nC-9 Works offline for a whole shift.\n", 1))
    assert "is locked" in c.check_install(PROBLEM, ["product"], "product", reworded)[0]    # signed at N05
    done.change_request("product", "Reword the problem after the pilot", "Wei", writer=PROBLEM)
    assert c.check_install(PROBLEM, ["product"], "product", reworded) == []
    assert c.check_install(REQS, ["product"], "product", widened) == []
    assert done.state.controls["product"].locked_node == "n05_scope_success"


def test_an_approved_change_request_reopens_the_defects_waiting_on_it(done, tmp_path):
    """control-documents.md, "Locks and change requests": a named human's change request unlocks the document for its
    writer and re-opens the defects that were waiting on it, so the next gate routes them. An agent's request stays
    open and changes nothing."""
    eng = done

    def status() -> str:
        return next(d.status for d in eng.state.evaluation.defects if d.id == "D-901")

    _, gate = _gate(eng, tmp_path, [_defect(REQS)])
    assert gate.outcome == "blocked" and status() == "needs_human"          # fixing it would change a signed product.md
    asked = eng.change_request("product", "Let N04 add the hold-reason requirement", "agent:product-strategist", writer=REQS)
    assert asked.status == "open" and status() == "needs_human"
    approved = eng.change_request("product", "Let N04 add the hold-reason requirement", "Wei", writer=REQS)
    assert status() == "open"
    assert next(d for d in eng.state.evaluation.defects if d.id == "D-901").history[-1].endswith(
        f"routable again after {approved.id}")
    _, gate = _gate(eng, tmp_path)
    assert gate.outcome == "rework" and gate.targets == [REQS]


def test_an_edit_to_a_section_the_writer_does_not_own_is_ignored_and_ledgered(project, fast_browser):
    """control-documents.md, "Shared documents": an edit to a section the writer does not own is ignored and reported
    (control_edits_ignored on the ledger), so it is never silent; the writer's own sections still land."""
    eng = Engine(project, executor=_PendingFor(project / "fixtures", {REQS}))
    eng.run(max_steps=100)
    rt = eng.rt(REQS)
    assert rt.status == NodeStatus.WAITING_AGENT
    fx = FIXTURES / REQS / "attempt-1"
    submitted = (fx / "product.md").read_text() + "\n## Scope\n\nN04 widens the scope to every lot type.\n"
    outputs = {"requirements": _write(eng, REQS, "requirements.json", (fx / "requirements.json").read_text()),
               "product_md": _write(eng, REQS, "product.md", submitted)}
    res = eng.submit(REQS, outputs, rt.token, "agent:product-strategist")
    assert not res["failures"], res["failures"]
    live = eng.controls.text("product")
    assert "| R-01 |" in live and "widens the scope" not in live
    ignored = [(e["data"]["doc"], e["data"]["node"], e["data"]["sections"])
               for e in eng.ledger.events("control_edits_ignored")]
    assert ignored == [("product", REQS, ["Scope"])]


def test_reopening_after_a_crash_rolls_a_stale_control_file_forward_and_leaves_a_hand_edit_alone(done):
    """control-documents.md, "How a change is installed": an install archives and records the new version before it
    writes the live file, so on resume a live file that matches an older accepted version is rolled forward. A file that
    matches no version is a hand edit, left for the integrity check to report."""
    project = done.project.root
    rec, live = done.state.controls["product"], done.controls.path("product")
    accepted = live.read_text()
    live.write_text((project / rec.history[-2].archived).read_text())   # recorded the newest version, then crashed
    reopened = Engine(project)
    assert live.read_text() == accepted and not reopened.controls.drift()
    assert [e["data"]["docs"] for e in reopened.ledger.events("controls_settled")] == [["product"]]
    live.write_text(accepted + "\nA note typed straight into the file.\n")
    again = Engine(project)
    assert "typed straight into the file" in live.read_text() and again.controls.drift()


# ------------------------------------------------------------------------------------------------ scoring
def test_a_reviewer_cannot_pass_what_the_tool_failed_or_never_measured_and_human_dimensions_stay_pending():
    """evaluation-and-gates.md, "Scoring a node": a reviewer cannot pass a dimension a tool MUST failed; a tool dimension
    the check ran without reporting is not_scored, never a pass; human dimensions stay pending for a named human; and
    an enforced MUST's finding is raised to at least P3, so it blocks."""
    node = next(n for n in load_workflow().nodes if n.id == "n13_quality_review")
    rubrics = load_rubrics()
    dims = [d for r in node.evaluation for d in rubrics[r]["dimensions"]]
    enforced = {d["rule"]: "adopted" for d in dims if d.get("rule")}
    tool = CheckResult()
    for d in dims:
        if d["check"]["type"] == "tool" and d["id"] not in ("A11Y-AXE", "PERF-LOAD"):    # PERF-LOAD: never reported
            tool.dim(d["id"], True, "measured")
    tool.dim("A11Y-AXE", False, "1 color-contrast violation", [finding(
        "A11Y-AXE", "axe color-contrast on the queue", "P4", "queue:color-contrast", "n11_prototype_development",
        "use the declared tint pair", "0 color-contrast violations on the queue")])
    review = {"summary": "It all looks fine to me.",
              "dimensions": [{"id": d["id"], "score": 5, "passed": True, "evidence": "fine"} for d in dims]}
    rec = merge_review(node, 1, 2, {"browser:check": tool}, review, rubrics, enforced, 4.0)
    status = {r.id: r.status for r in rec.dimensions}
    assert status["A11Y-AXE"] == "fail" and rec.overridden == ["A11Y-AXE"] and not rec.passed
    assert [(f.by, f.blocking, f.severity) for f in rec.findings if f.dimension == "A11Y-AXE"] == [("tool", True, "P3")]
    assert status["PERF-LOAD"] == "not_scored"
    assert status["DES-TASTE"] == "pending_human"
    assert all(status[d["id"]] == "pass" for d in dims if d["check"]["type"] == "review")   # the reviewer's own count


def test_a_finished_run_leaves_every_human_dimension_pending_and_lists_them_for_wei(done):
    """evaluation-and-gates.md, "Scoring a node": human dimensions stay pending and are listed in the run report."""
    st, version = done.state, done.state.build.version
    human = {(r.node, d.id, d.status) for r in st.evaluation.reviews if r.build_version == version
             for d in r.dimensions if d.check == "human"}
    assert human == {("n13_quality_review", "DES-TASTE", "pending_human"),
                     ("n14_validation", "VAL-REAL-USERS", "pending_human")}
    summary = next(done.project.root.glob("work/n18_final_verification/a*/release-summary.md")).read_text()
    pending = summary.split("## Human dimensions still pending", 1)[1].split("\n## ", 1)[0]
    assert "- n13_quality_review: DES-TASTE" in pending and "- n14_validation: VAL-REAL-USERS" in pending


# ------------------------------------------------------------------------------------------------ retry budget and unblocking
MISSING_SOURCE = {"sources": [{"id": "S-01", "kind": "brief", "title": "Brief", "path": "sources/missing.md",
                               "evidence": "reported"}]}                    # schema-valid; the registry check fails it


def test_a_node_escalates_exactly_when_its_retry_budget_is_spent(tmp_path):
    """orchestration.md, "Retry and escalation": after retry.max_attempts consecutive failures, and not before or
    after, the node escalates and the run is BLOCKED."""
    eng = _real(tmp_path)
    budget = eng.node(INTAKE).retry.max_attempts
    for attempt in range(1, budget + 1):
        eng.run()
        rt = eng.rt(INTAKE)
        assert rt.status == NodeStatus.WAITING_AGENT and rt.attempt == attempt       # re-dispatched, not escalated early
        assert eng.state.runtime.status.value != "BLOCKED"
        res = eng.submit(INTAKE, {"sources": _write(eng, INTAKE, "sources.json", MISSING_SOURCE)}, rt.token,
                         "agent:context-research")
        assert res["attempts_left"] == budget - attempt
        assert res["status"] == ("BLOCKED" if attempt == budget else "ITERATE")
    esc = [e for e in eng.state.runtime.escalations if e.open]
    assert [e.node for e in esc] == [INTAKE]
    assert f"{budget} consecutive failed attempts (retry budget {budget})" in esc[0].reason
    eng.run()
    assert eng.rt(INTAKE).attempt == budget and not (eng.pdg_dir / "tasks" / f"{INTAKE}-a{budget + 1}.json").exists()


def test_unblocking_a_node_gives_it_a_fresh_retry_budget(tmp_path):
    """orchestration.md, "Retry and escalation": `pdg unblock <project> <node> --actor Wei --note …` gives the node a
    fresh budget and re-runs it, so it may fail max_attempts more times before it escalates again."""
    eng = _real(tmp_path)
    budget = eng.node(INTAKE).retry.max_attempts

    def fail_once() -> dict:
        eng.run()
        return eng.submit(INTAKE, {"sources": _write(eng, INTAKE, "sources.json", MISSING_SOURCE)}, eng.rt(INTAKE).token,
                          "agent:context-research")

    assert [fail_once()["status"] for _ in range(budget)][-1] == "BLOCKED"
    eng.unblock(INTAKE, "Wei", note="the brief's path is fixed; try again")
    assert eng.rt(INTAKE).streak == 0 and eng.state.runtime.status.value != "BLOCKED"
    again = [fail_once() for _ in range(budget)]
    assert [r["attempts_left"] for r in again] == list(range(budget - 1, -1, -1))
    assert [r["status"] for r in again] == ["ITERATE"] * (budget - 1) + ["BLOCKED"]
    assert eng.rt(INTAKE).attempt == 2 * budget


def test_waiting_unblock_command_refuses_without_terminal_and_note(tmp_path, capsys):
    eng = _real(tmp_path)
    budget = eng.node(INTAKE).retry.max_attempts
    for _ in range(budget):
        eng.run()
        eng.submit(INTAKE, {"sources": _write(eng, INTAKE, "sources.json", MISSING_SOURCE)}, eng.rt(INTAKE).token,
                   "agent:context-research")
    assert [(e.node, e.open) for e in eng.state.runtime.escalations if e.open] == [(INTAKE, True)]
    assert main(["waiting", str(eng.project.root)]) == 0
    out = capsys.readouterr().out
    command = next(line.split("|")[3].strip() for line in out.splitlines()
                   if f"pdg unblock {eng.project.root}" in line)
    assert "--note" not in command
    assert main(shlex.split(command)[1:]) == 4
    assert "--note is required when no terminal is attached" in capsys.readouterr().out


def test_waiving_a_blocking_intake_gap_is_refused_and_changes_nothing(project, capsys):
    """orchestration.md, "Retry and escalation": `--waive <gap>` covers intake gaps a named human decides the product can
    proceed without. A blocking gap must be answered, so waiving it is refused and changes nothing; a resolvable gap in
    the same report can be waived."""
    eng = Engine(project, executor=_PendingFor(project / "fixtures", {EVIDENCE}))
    eng.run(max_steps=100)
    evidence = json.loads((FIXTURES / EVIDENCE / "attempt-1" / "evidence.json").read_text())
    evidence["open_questions"][0]["blocking"] = True                        # Q-01 now blocks the intake
    assert _submit_fixture(eng, EVIDENCE, {"evidence.json": evidence})["status"] == "BLOCKED"
    assert [(e.node, e.reason) for e in eng.state.runtime.escalations if e.open] == [(EVIDENCE, "E05: outcome 'gaps_blocking'")]
    report = json.loads((project / eng.current("gaps")[-1].path).read_text())
    assert {g["id"]: g["severity"] for g in report["gaps"]} == {"G-DESIGN-AUTHORITY": "resolvable", "G-Q-Q-01": "blocking"}
    before = _saved(project)
    assert main(["unblock", str(project), EVIDENCE, "--actor", "Wei", "--note", "proceed without the LIMS answer",
                 "--waive", "G-Q-Q-01"]) == 4
    assert "gap G-Q-Q-01 is blocking: answer it, don't waive it" in capsys.readouterr().out and _saved(project) == before
    eng.unblock(EVIDENCE, "Wei", note="the brand guide arrives with the pilot", waive=["G-DESIGN-AUTHORITY"])
    assert [(w.gap, w.by) for w in eng.state.inputs.waivers] == [("G-DESIGN-AUTHORITY", "Wei")]
    assert not [e for e in eng.state.runtime.escalations if e.open]


# ------------------------------------------------------------------------------------------------ concurrency
def test_a_second_writer_is_refused_the_project_lock_and_the_cli_changes_nothing_while_it_is_held(tmp_path, monkeypatch,
                                                                                                   capsys):
    """orchestration.md, "Durability": every mutating command takes .pdg/lock, so a project has one writer at a time."""
    eng = _real(tmp_path, scripted=True)
    eng.run(max_steps=100)
    assert eng.rt(PROBLEM).status == NodeStatus.WAITING_HUMAN
    project = eng.project.root
    hold = lock.project_lock
    monkeypatch.setattr(lock, "project_lock", lambda p, command, timeout=900.0: hold(p, command, timeout=0.2))

    def saved() -> tuple[bytes, bytes]:
        return (project / ".pdg" / "state.json").read_bytes(), (project / ".pdg" / "ledger.jsonl").read_bytes()

    approve = ["approve", str(project), PROBLEM, "--actor", "Wei", "--reason", "The job and the pain are right."]
    with hold(project, "run"):
        with pytest.raises(lock.Locked, match=r"is held by pid \d+ \(`pdg run`"):
            with lock.project_lock(project, "submit"):
                pass
        before = saved()
        assert main(approve) == 4
        assert "is held by" in capsys.readouterr().out and saved() == before
    assert main(approve) == 0                                               # the same command, once the lock is free
    decisions = Ledger(project / ".pdg" / "ledger.jsonl", read_only=True).events("decision")
    assert [(e["data"]["node"], e["data"]["actor"]) for e in decisions] == [(PROBLEM, "Wei")]


def test_select_batch_respects_the_parallel_limit_and_nodes_still_in_flight(project):
    """orchestration.md, "Scheduling": up to parallel_limit ready nodes, skipping any that conflict with a node already
    chosen or still in flight (here: another writer of product.md whose task packet is out)."""
    eng = Engine(project)
    fan = ["n13_quality_review", "n14_validation", "n15_feasibility_review"]
    assert eng.select_batch(fan) == fan
    eng.wf.policies.parallel_limit = 2
    assert eng.select_batch(fan) == fan[:2]
    eng.wf.policies.parallel_limit = 4
    offered = [REQS, "n13_quality_review"]
    eng.rt(PROBLEM).status = NodeStatus.WAITING_AGENT
    assert eng.select_batch(offered) == ["n13_quality_review"]
    eng.rt(PROBLEM).status = NodeStatus.PASSED
    assert eng.select_batch(offered) == offered


# ------------------------------------------------------------------------------------------------ refusals change nothing
def test_a_submission_to_a_node_that_is_not_waiting_is_refused_and_changes_nothing(tmp_path):
    """orchestration.md, "Executors": a submission is refused, with nothing written, when the node is not waiting, even
    a valid one: N01 has passed, and N03 waits for a human's decision, not for its agent."""
    eng = _at_problem_gate(tmp_path)
    before = _saved(eng.project.root)
    for node in (INTAKE, PROBLEM):
        rt = eng.rt(node)
        fx, outputs = _fixture(eng.project.root / "fixtures", node, rt.attempt)   # paths inside the project
        with pytest.raises(EngineError, match=f"{node} is {rt.status.value}, not waiting for a submission"):
            eng.submit(node, {k: str(fx / name) for k, name in outputs.items()}, rt.token, f"agent:{eng.node(node).agent}")
    assert _saved(eng.project.root) == before
    assert (eng.rt(INTAKE).status, eng.rt(PROBLEM).status) == (NodeStatus.PASSED, NodeStatus.WAITING_HUMAN)


def test_a_decision_with_a_blank_reason_is_refused_and_changes_nothing(tmp_path):
    """A gate decision records the approver's own words as its rationale (`pdg approve … --reason`), so a blank reason
    is refused and changes nothing; the same decision with a reason goes through."""
    eng = _at_problem_gate(tmp_path)
    before = _saved(eng.project.root)
    for blank in ("", "  \n\t"):
        with pytest.raises(EngineError, match="a decision needs a reason"):
            eng.decide(PROBLEM, "approved", "Wei", blank)
    assert _saved(eng.project.root) == before
    assert eng.rt(PROBLEM).status == NodeStatus.WAITING_HUMAN and not eng.state.history.approvals
    eng.decide(PROBLEM, "approved", "Wei", "The job and the pain are right.")
    assert [(a.node, a.reason) for a in eng.state.history.approvals] == [(PROBLEM, "The job and the pain are right.")]


# ------------------------------------------------------------------------------------------------ memoisation
def test_a_validation_finding_appended_by_n14_does_not_make_n03_run_again(done):
    """control-documents.md, "Shared documents": a reader's fingerprint covers only the sections written upstream of it,
    so a validation finding appended by N14 does not force N03 to re-run. Wei re-runs N02 unchanged, which leaves N03
    stale but not forced, and N03 is memo-restored."""
    eng = done
    assert eng.state.controls["research"].history[-1].node == "n14_validation"   # N14 wrote research.md after N03 passed
    seq, attempts = _last_seq(eng), {n: eng.rt(n).attempt for n in eng.idx.nodes}
    eng.invalidate_nodes([EVIDENCE], "re-check the evidence", "Wei")
    eng.run(max_steps=400)
    assert eng.state.runtime.status.value == "RUN_PASS" and eng.rt(EVIDENCE).attempt == attempts[EVIDENCE] + 1
    assert eng.rt(PROBLEM).attempt == attempts[PROBLEM]
    assert PROBLEM in {e["data"]["node"] for e in eng.ledger.events("memo_hit") if e["seq"] > seq}


# ------------------------------------------------------------------------------------------------ build versions
def test_an_identical_rebuild_keeps_its_build_version(done):
    """state-model.md, "How state changes": build versions increase only when the prototype's content changes; a rebuild
    that produces identical bytes keeps its version and says so (build_unchanged on the ledger)."""
    eng = done
    st = eng.state
    version, versions, first, seq = st.build.version, len(st.history.versions), st.build.prototype.artifact, _last_seq(eng)
    eng.invalidate_nodes(["n12_content_data"], "rebuild the content; nothing changed", "Wei")
    eng.run(max_steps=400)
    st = eng.state
    assert st.runtime.status.value == "RUN_PASS"
    rebuilt = eng.current("prototype")[-1].id
    assert rebuilt != first and st.artifacts[rebuilt].sha256 == st.artifacts[first].sha256    # a new record, same bytes
    assert st.build.prototype.artifact == first                             # the reviewed build stays the build of record
    assert st.build.version == version and len(st.history.versions) == versions
    builds = [(e["type"], e["data"]["version"], e["data"]["artifact"]) for e in eng.ledger.events()
              if e["seq"] > seq and e["type"] in ("build_unchanged", "build_version")]
    assert builds == [("build_unchanged", version, rebuilt)]
    assert (st.evaluation.gates[-1].outcome, st.evaluation.gates[-1].build_version) == ("pass", version)


def test_an_identical_rebuild_does_not_re_review_the_same_bytes(done):   # audit finding F35
    """architecture.md: identical inputs are memo-restored. state-model.md: a rebuild with identical bytes keeps its
    version, "so the reviews of that content still hold"."""
    eng = done
    before = {r: eng.rt(r).attempt for r in eng.idx.reviewer_nodes()}
    eng.invalidate_nodes(["n12_content_data"], "rebuild the content; nothing changed", "Wei")
    eng.run(max_steps=400)
    assert eng.state.runtime.status.value == "RUN_PASS"
    assert {r: eng.rt(r).attempt for r in before} == before


def test_a_reviewers_own_artifact_failure_fails_its_attempt_instead_of_becoming_an_unroutable_defect(tmp_path,
                                                                                                    fast_browser):
    """Field run W35: VAL-SIMULATED-FLAGGED judges N14's own validation doc, not the prototype. It failed, yet N14
    passed and the failure became a blocking finding traced nowhere (N17 cannot route back to N14), so the gate would
    have escalated over a one-line relabel. An own-artifact MUST now fails the reviewer's attempt, which it retries."""
    validation = "n14_validation"
    project = copy_example(tmp_path / "p")
    eng = Engine(project, executor=_PendingFor(project / "fixtures", {validation}))
    eng.run(max_steps=400)
    rt = eng.rt(validation)
    assert rt.status == NodeStatus.WAITING_AGENT
    fx, _ = _fixture(FIXTURES, validation, rt.attempt)
    doc = json.loads((fx / "validation.json").read_text())
    doc["findings"].append({"dimension": "VAL-INSIGHT", "severity": "P3", "message": "the lot status reads as final",
                            "location": "lot:1280", "by": "agent", "participant": "P-GHOST"})
    reviews = len(eng.state.evaluation.reviews)
    res = _submit_fixture(eng, validation, replace={"validation.json": json.dumps(doc)})
    assert any("VAL-SIMULATED-FLAGGED" in f and "P-GHOST" in f for f in res["failures"]), res["failures"]
    assert eng.rt(validation).status != NodeStatus.PASSED and res["attempts_left"] < eng.node(validation).retry.max_attempts
    assert len(eng.state.evaluation.reviews) == reviews                  # nothing was recorded against the build


def test_a_review_that_names_another_build_is_refused_and_keeps_its_attempt(tmp_path, fast_browser):
    """Backlog N-06: a review was not bound to the build it judged, so the first project's reviewers wrote "on build v5"
    into free text. The packet states the build's sha256, and a review naming another build is refused, as a slip."""
    reviewer = "n15_feasibility_review"
    project = copy_example(tmp_path / "p")
    eng = Engine(project, executor=_PendingFor(project / "fixtures", {reviewer}))
    eng.run(max_steps=400)
    rt = eng.rt(reviewer)
    assert rt.status == NodeStatus.WAITING_AGENT
    sha = eng.state.build.prototype.sha256
    fx, outputs = _fixture(FIXTURES, reviewer, rt.attempt)
    review_file = outputs["feasibility_review"]
    review = json.loads((fx / review_file).read_text())
    attempt = rt.attempt
    with pytest.raises(EngineError, match="reviews build 0000000000000000, but the build under review"):
        _submit_fixture(eng, reviewer, replace={review_file: json.dumps({**review, "build": "0" * 16})})
    assert eng.rt(reviewer).attempt == attempt and eng.rt(reviewer).status == NodeStatus.WAITING_AGENT
    res = _submit_fixture(eng, reviewer, replace={review_file: json.dumps({**review, "build": sha[:16]})})
    assert not any("reviews build" in f for f in res["failures"] or [])


def test_the_example_fixtures_are_what_their_author_script_writes(tmp_path):
    """The README says to regenerate every fixture with `python _author.py`. Hand edits to the fixtures had drifted from
    it (screen kinds, a shadow token, a manual accessibility score, a moved step and its references), so running it would
    have quietly undone them. It now writes exactly the committed fixtures."""
    import subprocess
    import sys
    copy = tmp_path / "coa-review"
    shutil.copytree(EXAMPLE, copy, ignore=shutil.ignore_patterns("__pycache__", "_runs"))
    inputs = {"_author.py", "README.md", "n10_prototype_planning/attempt-1/plan.json"}   # what the script reads, or keeps
    for f in [f for f in (copy / "fixtures").rglob("*") if f.is_file()]:
        rel_path = f.relative_to(copy / "fixtures")
        if rel_path.as_posix() not in inputs and "overlay" not in rel_path.parts:
            f.unlink()                                     # so every other file is one the script wrote
    subprocess.run([sys.executable, "-B", "_author.py"], cwd=copy / "fixtures", check=True, capture_output=True)
    files = lambda root: {p.relative_to(root): p.read_bytes() for p in root.rglob("*")
                          if p.is_file() and not p.name.startswith(".")}   # not a Finder .DS_Store
    written, committed = files(copy / "fixtures"), files(FIXTURES)
    committed = {k: v for k, v in committed.items() if "__pycache__" not in k.parts}
    assert sorted(written) == sorted(committed)
    assert [str(k) for k in committed if written[k] != committed[k]] == []
