"""The evidence base behind the rules: every rule traces to recorded evidence, every citation resolves, rubrics and
rules agree, and nothing outside a *_TENANT file identifies the customer the case study came from."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from pdg.memory import HUMAN_GUARDED, STATES
from pdg.docs import evidence_records
from pdg.privacy import privacy_path

from .conftest import PKG

WORKSPACE = PKG.parents[1]
CASE = PKG / "knowledge" / "case-studies" / "hub-programmes-2026"
RULES = json.loads((PKG / "knowledge" / "rules.json").read_text())
HISTORY = evidence_records()
DEID = json.loads(privacy_path().read_text())
RECORD_IDS = {r["id"] for r in HISTORY["records"]}
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".jsonl", ".js", ".css", ".html", ".mmd", ".svg", ".txt", ".csv"}
CITATION = re.compile(r"^(~?[^\s:()]+\.[A-Za-z0-9]+)(?::(\d+)(?:-(\d+))?)?(?:\s.*)?$")


def _recorded_lines(rel: str) -> int | None:
    """Line count of a cited workspace file as it was when the case study was last recorded (the last commit that
    touched the history file). Another project may move or delete a cited file later; the citation stays valid
    provenance because the content it cites is still in history. None when git or the file at that commit is absent."""
    try:
        history = str((CASE / "iteration-history_TENANT.json").relative_to(WORKSPACE))
        sha = subprocess.run(["git", "-C", str(WORKSPACE), "log", "-1", "--format=%H", "--", history],
                             capture_output=True, text=True, timeout=20).stdout.strip()
        if not sha:
            return None
        shown = subprocess.run(["git", "-C", str(WORKSPACE), "show", f"{sha}:{rel}"], capture_output=True, timeout=20)
        return len(shown.stdout.splitlines()) if shown.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _dimensions():
    for p in sorted((PKG / "rubrics").glob("*.yaml")):
        for d in yaml.safe_load(p.read_text())["dimensions"]:
            yield p.stem, d


@pytest.mark.skipif(not (CASE / "iteration-history_TENANT.json").is_file(),
                    reason="private source records are intentionally not distributed")
def test_every_iteration_record_has_the_seven_fields_and_says_missing_rather_than_guessing():
    iterations = [r for r in HISTORY["records"] if r["type"] == "iteration"]
    assert len(iterations) >= 20
    assert HISTORY["fields"] == ["iteration", "decision", "output", "feedback", "revision", "result", "reusable_lesson"]
    for r in iterations:
        for f in HISTORY["fields"]:
            assert isinstance(r.get(f), str) and r[f].strip(), (r["id"], f)
        assert r["citations"], r["id"]
    assert any(r["feedback"] == "MISSING" for r in iterations)       # gaps are stated, never filled in
    for r in HISTORY["records"]:
        assert r["citations"], r["id"]
        assert r.get("evidence_class", r.get("lesson_class")) in ("verified", "inferred", "recommendation", "missing"), r["id"]


def test_every_citation_resolves_to_a_file_and_line_range_that_exist():
    hub_files = [c.split(":")[0] for r in HISTORY["records"] for c in r["citations"] if c.startswith("01_Project-Hubs/")]
    if not any((WORKSPACE / f).is_file() for f in hub_files):
        pytest.skip("the source project hub is not in this checkout")
    broken = []
    for r in HISTORY["records"]:
        for c in r["citations"]:
            m = CITATION.match(c)
            if not m:
                assert c.startswith(("session:", "brief ", "https://")), (r["id"], c)
                continue
            p = Path(m.group(1)).expanduser()
            p = p if p.is_absolute() else WORKSPACE / p
            if p.is_file():
                lines = sum(1 for _ in p.open(errors="ignore"))
            elif not Path(m.group(1)).is_absolute() and (lines := _recorded_lines(m.group(1))) is not None:
                pass                                            # moved or deleted since; the recorded content still resolves
            else:
                broken.append(f"{r['id']}: {c} (missing)")
                continue
            if m.group(2) and int(m.group(3) or m.group(2)) > lines:
                broken.append(f"{r['id']}: {c} (the file has {lines} lines)")
    assert not broken, broken


def test_every_rule_traces_to_evidence_and_has_an_executable_check():
    cats = set(RULES["categories"])
    for rule in RULES["rules"]:
        assert rule["statement"].strip() and rule["category"] in cats, rule["id"]
        assert rule["evidence"] and set(rule["evidence"]) <= RECORD_IDS, (rule["id"], rule["evidence"])
        chk, state = rule["check"], rule["lifecycle"]["state"]
        assert state in STATES and rule["lifecycle"]["history"], rule["id"]
        if state != "candidate":                                        # validation needs an executable check
            assert chk.get("fn") or chk.get("dimensions") or chk.get("test"), rule["id"]
        else:
            assert chk.get("type") in ("reference", "tool", "review", "test"), rule["id"]
    assert {r["category"] for r in RULES["rules"]} == cats              # every category has rules


def test_the_seed_lifecycle_follows_the_basis_and_claims_no_human_decision():
    for rule in RULES["rules"]:
        state, basis = rule["lifecycle"]["state"], rule["basis"]
        if state in HUMAN_GUARDED and not rule["confirmed_by_wei"]:
            assert basis in ("canonical-framework", "stated-requirement", "graduated-skill"), rule["id"]
            assert rule["scope"] == "stable", rule["id"]
        if basis == "recommendation":
            assert state == "candidate", rule["id"]
        if rule["scope"] == "project_specific":
            assert state not in HUMAN_GUARDED, rule["id"]               # never a default for other projects
        assert not any(h["human"] for h in rule["lifecycle"]["history"]) or rule["confirmed_by_wei"], rule["id"]


def test_rubrics_and_rules_agree():
    rules = {r["id"]: r for r in RULES["rules"]}
    seen = set()
    for rubric, d in _dimensions():
        assert d["rule"] in rules, (rubric, d["id"], d["rule"])
        chk = rules[d["rule"]]["check"]
        assert d["id"] in chk.get("dimensions", []), (d["id"], d["rule"])
        fn = d["check"].get("fn")
        if fn:
            fns = chk.get("fn") if isinstance(chk.get("fn"), list) else [chk.get("fn")]
            assert fn in fns, (d["id"], fn, fns)
        seen.add(d["id"])
    for r in rules.values():
        assert set(r["check"].get("dimensions", [])) <= seen, r["id"]


def test_rule_tests_exist():
    for rule in RULES["rules"]:
        ref = rule["check"].get("test")
        if not ref:
            continue
        path, _, name = ref.partition("::")
        tree = ast.parse((PKG / path).read_text())
        assert name in {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}, ref


def _scanned_files():
    roots = [PKG, WORKSPACE / "02_Workflows" / "SOPs" / "prototype-design",
             WORKSPACE / "02_Workflows" / "prompts" / "prototype-design.prompt.md"]
    for root in roots:
        files = [root] if root.is_file() else sorted(root.rglob("*")) if root.is_dir() else []
        for p in files:
            parts = set(p.relative_to(WORKSPACE).parts)
            if (not p.is_file() or p.suffix not in TEXT_SUFFIXES or "_TENANT" in p.name
                    or p == privacy_path() or "vendor" in parts
                    or parts & {".pdg", "work", "__pycache__", ".pytest_cache", "node_modules", "_runs"}):
                continue
            yield p


def test_no_customer_identifier_outside_tenant_files():
    banned = [b.lower() for b in DEID["banned"]]
    whole = [re.compile(rf"\b{re.escape(w)}\b") for w in DEID["whole_words"]]
    hits = []
    for p in _scanned_files():
        text = p.read_text(errors="ignore")
        low = text.lower()
        hits += [f"{p.relative_to(WORKSPACE)}: '{b}'" for b in banned if b in low]
        hits += [f"{p.relative_to(WORKSPACE)}: '{w.pattern}'" for w in whole if w.search(text)]
    assert not hits, hits[:20]


def test_preference_store_uses_deidentified_run_labels_sources_and_reasons():
    prefs = PKG / "knowledge" / "preferences"
    product_words = [b.lower() for b in DEID.get("preference_product_words", [])]
    source = re.compile(r"^Wei, [a-z -]+, \d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z$")
    hits = []
    for p in sorted(prefs.rglob("*")):
        if not p.is_file() or p.suffix not in TEXT_SUFFIXES:
            continue
        text = p.read_text(errors="ignore")
        low = text.lower()
        hits += [f"{p.relative_to(PKG)}: '{w}'" for w in product_words if w in low]
    decisions = prefs / "wei" / "decisions.jsonl"
    lines = decisions.read_text().splitlines() if decisions.exists() else []
    for n, line in enumerate(lines, 1):
        row = json.loads(line)
        if row.get("run") not in {"first-run", "second-run", "third-run"}:
            hits.append(f"decisions.jsonl:{n}: run {row.get('run')!r}")
        if row.get("source") and not source.match(row["source"]):
            hits.append(f"decisions.jsonl:{n}: source {row['source']!r}")
    assert not hits, hits[:20]


def test_the_previous_iterations_doc_is_complete():
    doc = (PKG / "docs" / "previous-iterations.md").read_text()
    for r in HISTORY["records"]:
        if r["type"] == "iteration":
            assert r["id"] in doc, r["id"]
    assert "MISSING" in doc
