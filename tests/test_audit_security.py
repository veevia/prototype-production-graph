"""Security audit findings (checked directly after the security auditor's report was blocked by a content filter):
agent-written code never sees the caller's secrets (S1), and the shareable run report never renders state as markup (S2)."""

from __future__ import annotations

import json

import pytest

from pdg.engine import Engine

PROBE = "<i data-pdg-probe>"


def test_agent_written_tests_never_see_the_callers_secrets(tmp_path, monkeypatch):
    from pdg.tools import _node
    if not _node.node_bin():
        pytest.skip("node is not installed")
    monkeypatch.setenv("PDG_PROBE_API_KEY", "not-for-agents")
    probe = tmp_path / "probe.test.mjs"
    probe.write_text("import test from 'node:test';\nimport assert from 'node:assert';\n"
                     "test('no caller secrets', () => { assert.strictEqual(process.env.PDG_PROBE_API_KEY, undefined); });\n")
    passed, failed, tail = _node.unit(probe, tmp_path)
    assert (passed, failed) == (1, 0), tail
    env = _node._env()
    assert "PDG_PROBE_API_KEY" not in env and "PATH" in env


def test_the_run_report_escapes_every_value_it_reads_from_state(project, fast_browser):
    from pdg.report import write_report
    eng = Engine(project)
    for _ in range(4):
        eng.step()
    state = project / ".pdg" / "state.json"
    st = json.loads(state.read_text())
    st["runtime"]["batches"] = PROBE                                        # hand-edited state: markup where a number was
    st["runtime"]["nodes"]["n01_context_intake"]["status"] = PROBE
    state.write_text(json.dumps(st))
    html = write_report(project).read_text()
    assert PROBE not in html
    assert "&lt;i data-pdg-probe&gt;" in html
