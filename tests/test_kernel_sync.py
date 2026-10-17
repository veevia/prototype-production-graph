"""The shared kernel is copied, not shared: util, provenance and lock exist in both the video production engine (vpg)
and this one (ADR 0001; Wei chose to keep two copies with a drift check on 2026-09-26). Two tripwires guard them:

- the pin: both copies as last compared. When either changes, it fails and says what to do, so a fix in one copy cannot
  silently miss the other;
- the logic check: the copies run the same code. Their syntax trees are compared with every string masked (messages
  and docstrings name vpg or pdg) and without pdg's declared extra constants (`pdg_only` in kernel-sync.json).

    python tests/test_kernel_sync.py --update     # after comparing the copies and porting what applies
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
VPG = PKG.parent / "video-production" / "vpg"
PIN = Path(__file__).with_name("kernel-sync.json")
SIDES = {"vpg": VPG, "pdg": PKG / "pdg"}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def changed_since_pin(pin: dict, sides: dict[str, Path] = SIDES) -> list[str]:
    return [f"{side}/{name}" for name, shas in pin["files"].items() for side, root in sides.items()
            if _sha(root / name) != shas[side]]


def changed_kernel_message(pin: dict, changed: list[str]) -> str:
    return (f"the shared kernel changed since it was last compared ({pin['compared']}): {', '.join(changed)}. Fix: review "
            "each changed file in the other copy, then port the change, or record the intentional difference in "
            "tests/kernel-sync.json, as its own commit before a batch. Then run `python -B tests/test_kernel_sync.py --update`.")


class _MaskStrings(ast.NodeTransformer):
    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        return ast.copy_location(ast.Constant(value="<str>"), node) if isinstance(node.value, str) else node


def logic(path: Path, extra: set[str] = frozenset()) -> str:
    """The module's code with its docstring, every string and the named top-level constants taken out."""
    tree = ast.parse(path.read_text())
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    tree.body = [n for n in body if not (isinstance(n, ast.Assign)
                                         and any(isinstance(t, ast.Name) and t.id in extra for t in n.targets))]
    return ast.dump(_MaskStrings().visit(tree))


def logic_differences(pin: dict, sides: dict[str, Path] = SIDES) -> list[str]:
    extra = pin.get("pdg_only", {})
    return [name for name in pin["files"]
            if logic(sides["vpg"] / name) != logic(sides["pdg"] / name, set(extra.get(name, [])))]


def test_the_shared_kernel_copies_have_not_changed_since_they_were_last_compared():
    import pytest
    if not VPG.is_dir():
        pytest.skip("the video production workflow is not in this checkout")
    pin = json.loads(PIN.read_text())
    changed = changed_since_pin(pin)
    assert not changed, changed_kernel_message(pin, changed)
    assert pin["known_differences"], "record how the copies differ, even when the answer is 'none'"


def test_the_two_kernel_copies_run_the_same_logic():
    import pytest
    if not VPG.is_dir():
        pytest.skip("the video production workflow is not in this checkout")
    differ = logic_differences(json.loads(PIN.read_text()))
    assert not differ, (f"{differ}: the vpg and pdg copies no longer run the same code. Port the change to the other copy "
                        "(with a test), or declare a pdg-only constant under `pdg_only` in tests/kernel-sync.json.")


def test_the_kernel_change_message_names_files_and_the_fix():
    msg = changed_kernel_message({"compared": "DATE"}, ["vpg/provenance.py", "pdg/lock.py"])
    assert "vpg/provenance.py" in msg and "pdg/lock.py" in msg
    assert "review each changed file in the other copy" in msg
    assert "tests/kernel-sync.json, as its own commit before a batch" in msg


def test_the_tripwire_notices_a_change_in_either_copy(tmp_path):
    import shutil

    import pytest
    if not VPG.is_dir():
        pytest.skip("the video production workflow is not in this checkout")
    pin = json.loads(PIN.read_text())
    sides = {}
    for side, root in SIDES.items():
        (tmp_path / side).mkdir()
        for name in pin["files"]:
            shutil.copy(root / name, tmp_path / side / name)
        sides[side] = tmp_path / side
    assert changed_since_pin(pin, sides) == [] and logic_differences(pin, sides) == []
    fixed = sides["vpg"] / "provenance.py"
    fixed.write_text(fixed.read_text() + "\n# a fix made in one copy only\n")
    assert changed_since_pin(pin, sides) == ["vpg/provenance.py"]
    message = changed_kernel_message({"compared": "DATE"}, changed_since_pin(pin, sides))
    assert "vpg/provenance.py" in message and "as its own commit before a batch" in message
    assert logic_differences(pin, sides) == []                            # a comment is not logic …
    reworded = sides["pdg"] / "lock.py"
    reworded.write_text(reworded.read_text().replace("another pdg process", "some other pdg process"))
    assert logic_differences(pin, sides) == []                            # … nor is a message
    fixed.write_text(fixed.read_text() + "GENESIS_LEN = 64\n")
    assert logic_differences(pin, sides) == ["provenance.py"]             # a new statement is


if __name__ == "__main__" and "--update" in sys.argv:
    pin = json.loads(PIN.read_text())
    pin["files"] = {name: {side: _sha(root / name) for side, root in SIDES.items()} for name in pin["files"]}
    pin["compared"] = date.today().isoformat()
    PIN.write_text(json.dumps(pin, indent=1, ensure_ascii=False) + "\n")
    print(f"pinned {len(pin['files'])} kernel files ({pin['compared']})")
