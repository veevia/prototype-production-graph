from __future__ import annotations

import json
from pathlib import Path

from loop import replay_verdicts as rv


def test_parse_verdicts_counts_findings():
    rows = rv.parse_verdicts("""project: /p
PASS FUNC-SCENARIOS: ok
FAIL A11Y-FOCUS: 2 focus stops
  home (2):
    - button missing ring
    - tab missing ring
PASS A11Y-FOCUS-POINTER: ok
""")
    assert rows["FUNC-SCENARIOS"] == rv.Verdict(True, 0, "ok")
    assert rows["A11Y-FOCUS"] == rv.Verdict(False, 2, "2 focus stops", ("button missing ring", "tab missing ring"))


def test_compare_labels_stricter_and_more_lenient_flips():
    before = {"run": {"A": rv.Verdict(True, 0), "B": rv.Verdict(False, 2), "C": rv.Verdict(True, 1)}}
    after = {"run": {"A": rv.Verdict(False, 1), "B": rv.Verdict(True, 0), "C": rv.Verdict(True, 0)}}
    flips = rv.compare(before, after)
    assert [(f["dimension"], f["direction"], f["stricter"]) for f in flips] == [
        ("A", "stricter", True),
        ("B", "more lenient", False),
        ("C", "more lenient", False),
    ]


def test_compare_ignores_evidence_only_changes():
    assert rv.compare({"run": {"PERF-LOAD": rv.Verdict(True, 0, "812 ms")}},
                      {"run": {"PERF-LOAD": rv.Verdict(True, 0, "940 ms")}}) == []


def test_compare_finding_messages_not_only_pass_fail():
    flips = rv.compare({"run": {"A11Y-FOCUS": rv.Verdict(False, 2, "bad", ("one", "two"))}},
                       {"run": {"A11Y-FOCUS": rv.Verdict(False, 2, "bad", ("one", "three"))}})
    assert [(f["dimension"], f["direction"], f["stricter"]) for f in flips] == [
        ("A11Y-FOCUS", "findings changed", False)
    ]


def test_main_uses_injected_runner_for_pin_and_against(tmp_path, monkeypatch, capsys):
    files = {}
    for name in ("build.html", "plan.json", "experience.json", "project"):
        p = tmp_path / name
        if name == "project":
            p.mkdir()
        else:
            p.write_text("{}")
        files[name] = p
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps([{"label": "one", "build": str(files["build.html"]), "plan": str(files["plan.json"]),
                                   "experience": str(files["experience.json"]), "project": str(files["project"])}]))
    monkeypatch.setenv("PDG_REPLAY_CORPUS", str(corpus))

    def runner(package: Path, entry: dict[str, str], out: Path):
        return {"A11Y-FOCUS": rv.Verdict(package.name == "pkg", 0)}

    pin = tmp_path / "pin.json"
    monkeypatch.setattr(rv, "__file__", str(tmp_path / "pkg" / "loop" / "replay_verdicts.py"))
    assert rv.main(["--pin", str(pin)], runner=runner) == 0
    pinned = json.loads(pin.read_text())
    assert pinned["one"]["A11Y-FOCUS"]["passed"] is True

    pin.write_text(json.dumps({"one": {"A11Y-FOCUS": {"passed": False, "finding_count": 1}}}))
    assert rv.main(["--against", str(pin)], runner=runner) == 0
    assert "more lenient" in capsys.readouterr().out
