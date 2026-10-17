"""Running node for syntax checks and the prototype's unit tests (Node 22's built-in test runner)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def node_bin() -> str | None:
    return shutil.which("node")


_ENV_KEEP = ("PATH", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "SYSTEMROOT", "COMSPEC")


def _env(home: Path | None = None) -> dict[str, str]:
    """A minimal environment for agent-written prototype tests: only locale, temp and search-path variables are kept;
    HOME and USERPROFILE are pointed at the test working directory. This does not isolate network access."""
    env = {k: v for k, v in os.environ.items() if k in _ENV_KEEP}
    if home is not None:
        env["HOME"] = str(home)
        env["USERPROFILE"] = str(home)
    env["NODE_ENV"] = "test"
    return env


def syntax(files: list[Path], timeout: float = 60) -> list[str]:
    node = node_bin()
    bad = []
    for f in files:
        p = subprocess.run([node, "--check", str(f)], capture_output=True, text=True, timeout=timeout, env=_env())
        if p.returncode != 0:
            bad.append(f"{f.name}: {(p.stderr or p.stdout).strip().splitlines()[-1] if (p.stderr or p.stdout).strip() else 'syntax error'}")
    return bad


def unit(test_file: Path, cwd: Path, timeout: float = 60) -> tuple[int, int, str]:
    """(passed, failed, tail of the output)."""
    p = subprocess.run([node_bin(), "--test", str(test_file)], capture_output=True, text=True, timeout=timeout, cwd=cwd,
                       env=_env(cwd))
    out = (p.stdout or "") + (p.stderr or "")
    passes = re.findall(r"^# pass (\d+)", out, re.M)
    failures = re.findall(r"^# fail (\d+)", out, re.M)
    passed = int(passes[-1]) if passes else 0
    failed = int(failures[-1]) if failures else 0
    if p.returncode != 0:
        failed = max(failed, 1)
    return passed, failed, "\n".join(out.strip().splitlines()[-12:])


def unit_in_scratch(test_file: Path, root: Path, timeout: float = 60) -> tuple[int, int, str]:
    """Run node --test against a disposable copy so tests cannot mutate the registered artifact directory."""
    rel = test_file.relative_to(root)
    with tempfile.TemporaryDirectory(prefix="pdg-node-") as tmp:
        scratch = Path(tmp) / "build"
        shutil.copytree(root, scratch)
        return unit(scratch / rel, scratch, timeout)
