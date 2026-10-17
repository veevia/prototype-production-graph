"""Structural health of the package's own code, checked without extra tools.

A block moved by a bad edit left `visible_text_with` returning right after its import, and its real body sat, unreachable,
after another function's `return` (found in batch 8; the rendered-page check behind CNT-PROVENANCE had not run since the
configuration batch). Every statement after a `return`, `raise`, `break` or `continue` in the same block is dead code."""

from __future__ import annotations

import ast
import re

from .conftest import PKG

TERMINAL = (ast.Return, ast.Raise, ast.Break, ast.Continue)


def _dead_code(tree: ast.AST) -> list[int]:
    lines = []
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if not isinstance(block, list):
                continue
            for i, stmt in enumerate(block[:-1]):
                if isinstance(stmt, TERMINAL):
                    lines.append(block[i + 1].lineno)
    return lines


def test_no_statement_follows_a_return_raise_break_or_continue():
    dead = {str(p.relative_to(PKG)): lines for p in sorted((PKG / "pdg").rglob("*.py"))
            if (lines := _dead_code(ast.parse(p.read_text())))}
    assert not dead, dead


def test_the_check_finds_the_defect_it_guards_against():
    src = "def a():\n    return 1\n    x = 2\n"
    assert _dead_code(ast.parse(src)) == [3]


def test_printed_commands_and_docs_do_not_include_bare_reason_or_note_flags():
    pat = re.compile(r"--(?:reason|note)(?=$|\s*(?:`|\n|--[A-Za-z]|…))")
    roots = [PKG / "pdg", PKG / "docs"]
    offenders = {}
    for root in roots:
        for p in sorted(root.rglob("*")):
            if p.suffix not in {".py", ".md"}:
                continue
            rel = str(p.relative_to(PKG))
            hits = [f"{i}: {line.strip()}" for i, line in enumerate(p.read_text().splitlines(), 1) if pat.search(line)]
            if hits:
                offenders[rel] = hits
    assert not offenders, offenders
