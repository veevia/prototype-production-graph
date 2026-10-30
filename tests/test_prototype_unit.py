"""The example prototype's domain rules under Node's own test runner: verdicts, tolerance edges, escalation."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from .conftest import EXAMPLE


def test_domain_rules_pass_under_node():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    r = subprocess.run([node, "--test", str(EXAMPLE / "prototype" / "tests" / "domain.test.js")],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "# fail 0" in r.stdout and "# pass " in r.stdout


def test_the_build_is_reproducible(tmp_path):
    import sys
    outs = []
    for name in ("a", "b"):
        out = tmp_path / name
        subprocess.run([sys.executable, str(EXAMPLE / "prototype" / "build.py"), "--src", str(EXAMPLE / "prototype"),
                        "--out", str(out)], check=True, capture_output=True, text=True)
        outs.append((out / "dist" / "prototype.html").read_bytes())
    assert outs[0] == outs[1] and b"http://" not in outs[0].replace(b"http://www.w3.org", b"")
