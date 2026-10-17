"""Second-pass regression tests for deterministic audit findings."""

from __future__ import annotations

import json

from pdg.engine import tree_sha
from pdg.tools import _node, feasibility, prototype
from pdg.util import sha256_file

from .conftest import FakeCtx


def _manifest(root, unit_tests="domain.test.js"):
    files = {}
    for p in root.rglob("*"):
        if p.is_file() and p.name != "build-manifest.json":
            files[str(p.relative_to(root))] = sha256_file(p)
    (root / "build-manifest.json").write_text(json.dumps({
        "entry": "index.html",
        "stack": ["html", "js"],
        "files": files,
        "screens": {},
        "unit_tests": unit_tests,
    }))


def _mutating_build(root):
    root.mkdir()
    (root / "index.html").write_text("<main>Prototype</main>")
    (root / "domain.test.js").write_text(
        "import test from 'node:test';\n"
        "import assert from 'node:assert/strict';\n"
        "import { writeFileSync } from 'node:fs';\n"
        "test('writes during test', () => { writeFileSync('mutation.txt', 'changed'); assert.equal(1, 1); });\n"
    )
    _manifest(root)


def test_n2_token_value_literals_are_still_off_token_colours():
    html = """
    <style>
      :root { --text-muted: #777777; --surface: #fff; }
      .meta { color: #777; background: var(--surface); }
      .card { border-color: #FFF; }
    </style>
    """

    assert prototype.off_token_colours(html) == ["#777777", "#FFFFFF"]


def test_c5_external_refs_cover_template_and_realtime_network_calls():
    html = """
    <script>
      fetch(`https://api.example.test/lots`);
      new WebSocket("wss://stream.example.test/lots");
      new WebSocket('ws://stream.example.test/local');
      new EventSource("https://events.example.test/feed");
      navigator.sendBeacon("https://beacon.example.test/audit", "{}");
      fetch(`./local.json`);
      fetch("data:application/json,{}");
    </script>
    """

    refs = prototype.external_refs(html)

    assert len(refs) == 5
    assert any("wss://stream.example.test" in ref for ref in refs)
    assert any("ws://stream.example.test" in ref for ref in refs)
    assert not any("data:" in ref or "./local" in ref for ref in refs)


def test_n3_prototype_unit_tests_run_in_scratch_copy_without_mutating_artifact(tmp_path):
    root = tmp_path / "artifact"
    _mutating_build(root)
    before = tree_sha(root)[0]
    ctx = FakeCtx({}, work=tmp_path)
    ctx.output = lambda key: root if key == "prototype_build" else None
    ctx.artifact = lambda key: root if key == "prototype_build" else None

    res = prototype.check_unit(ctx)

    assert res.dimensions["BLD-UNIT"].passed, res.data["test_results"]
    assert tree_sha(root)[0] == before
    assert not (root / "mutation.txt").exists()


def test_n3_feasibility_unit_tests_run_in_scratch_copy_without_mutating_artifact(tmp_path):
    root = tmp_path / "artifact"
    _mutating_build(root)
    before = tree_sha(root)[0]
    ctx = FakeCtx({}, work=tmp_path)
    ctx.artifact = lambda key: root if key == "prototype" else None
    ctx.control_text = lambda doc: "\n".join(f"## {s}" for s in ctx.thresholds["feasibility"]["devdoc_sections"])

    res = feasibility.check(ctx)

    assert res.dimensions["TEC-UNIT"].passed, res.data["test_results"]
    assert tree_sha(root)[0] == before
    assert not (root / "mutation.txt").exists()


def test_r3_13_tree_sha_ignores_python_bytecode_caches(tmp_path):
    root = tmp_path / "artifact"
    root.mkdir()
    (root / "index.html").write_text("<main>Prototype</main>")
    before = tree_sha(root)[0]

    cache = root / "tests" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "probe.cpython-311.pyc").write_bytes(b"bytecode")
    (cache / "notes.txt").write_text("cache folder noise")
    (root / "module.pyc").write_bytes(b"bytecode")

    assert tree_sha(root)[0] == before


def test_n4_agent_tests_get_home_and_userprofile_inside_their_working_directory(tmp_path, monkeypatch):
    if not _node.node_bin():
        return
    monkeypatch.setenv("HOME", "/Users/weiwei")
    test_file = tmp_path / "home.test.js"
    test_file.write_text(
        "import test from 'node:test';\n"
        "import assert from 'node:assert/strict';\n"
        "test('home is isolated', () => {\n"
        "  assert.equal(process.env.HOME, process.cwd());\n"
        "  assert.equal(process.env.USERPROFILE, process.cwd());\n"
        "});\n"
    )

    passed, failed, tail = _node.unit(test_file, tmp_path)

    assert (passed, failed) == (1, 0), tail
