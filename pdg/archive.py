"""Archive planning: references, explicit keeps, symlink safety and checkpoints."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .models import CheckpointRef
from .util import read_json, rel


@dataclass
class ArchivePlan:
    move: list[tuple[str, int]]
    keep: dict[str, list[str]] = field(default_factory=dict)
    checkpoints: list[CheckpointRef] = field(default_factory=list)
    unmatched_keep: list[str] = field(default_factory=list)


def plan(root: Path, candidates: list[tuple[str, int]], checkpoints: list[CheckpointRef],
         keep_paths: list[str]) -> ArchivePlan:
    explicit = {rel((root / p).resolve() if not Path(p).is_absolute() else Path(p).resolve(), root)
                if (Path(p).is_absolute() or (root / p).exists()) else p.rstrip("/") for p in keep_paths}
    sizes = dict(candidates)
    kept: dict[str, list[str]] = {}
    unmatched = set(explicit)
    changed = True
    while changed:
        changed = False
        remaining = [r for r, _ in candidates if r not in kept]
        refs = references(root, remaining, list(kept))
        for r in remaining:
            reasons = []
            matching_keep = sorted(k for k in explicit if r == k or k.startswith(r.rstrip("/") + "/")
                                   or r.startswith(k.rstrip("/") + "/"))
            if matching_keep:
                reasons += [f"--keep {k}" for k in matching_keep]
                unmatched -= set(matching_keep)
            reasons += refs.get(r, [])
            if reasons:
                kept[r] = reasons
                changed = True
    move = [(r, sizes[r]) for r, _ in candidates if r not in kept]
    return ArchivePlan(move=move, keep=kept, checkpoints=checkpoint_moves(root, [r for r, _ in move], checkpoints),
                       unmatched_keep=sorted(unmatched))


def references(root: Path, candidates: list[str], kept_attempts: list[str] | None = None) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {c: [] for c in candidates}
    moved = [(c, root / c) for c in candidates]
    for f in _scan_files(root, candidates, kept_attempts or []):
        try:
            if f.is_symlink():
                target = (f.parent / os.readlink(f)).resolve()
                for c, p in moved:
                    if _inside(target, p):
                        out[c].append(f"symlink {rel(f, root)}")
                continue
            if not _textish(f):
                continue
            text = f.read_text(errors="ignore")
        except OSError:
            continue
        for c, _ in moved:
            count = text.count(c)
            if count:
                out[c].append(f"{rel(f, root)} ({count})")
    return {k: v for k, v in out.items() if v}


def checkpoint_moves(root: Path, moved: list[str], checkpoints: list[CheckpointRef]) -> list[CheckpointRef]:
    keep_seq = {1}
    if checkpoints:
        keep_seq.add(max(c.seq for c in checkpoints))
    keep_seq |= {c.seq for c in checkpoints if c.node == "n18_final_verification"}
    out = []
    prefixes = tuple(p.rstrip("/") + "/" for p in moved)
    for cp in checkpoints:
        if cp.seq in keep_seq:
            continue
        path = root / cp.path
        try:
            data = read_json(path)
        except (OSError, ValueError):
            continue
        paths = [a.get("path", "") for a in data.get("artifacts", {}).values() if a.get("current")]
        if any(str(p).startswith(prefixes) for p in paths):
            out.append(cp)
    return out


def dangling_symlinks(root: Path, moving: list[str]) -> list[str]:
    moved = [root / p for p in moving]
    bad = []
    for f in root.rglob("*"):
        if ".pdg" in f.parts or any(_path_inside(f, m) for m in moved):
            continue
        try:
            if f.is_symlink() and any(_inside((f.parent / os.readlink(f)).resolve(), m) for m in moved):
                bad.append(f.relative_to(root).as_posix())
        except OSError:
            continue
    return bad


def _scan_files(root: Path, candidates: list[str], extra_kept: list[str]) -> list[Path]:
    keep_roots = [root / p for p in _kept_attempts(root, candidates)] + [root / p for p in extra_kept]
    files = []
    for f in root.rglob("*"):
        if not f.is_file() and not f.is_symlink():
            continue
        parts = set(f.relative_to(root).parts)
        if ".pdg" in parts:
            continue
        rel_parts = f.relative_to(root).parts
        under_work = bool(rel_parts) and rel_parts[0] == "work"
        if under_work and not any(_inside(f, k) for k in keep_roots):
            continue
        files.append(f)
    return files


def _kept_attempts(root: Path, candidates: list[str]) -> list[str]:
    cand = set(candidates)
    return [rel(p, root) for p in (root / "work").glob("*/a*") if p.is_dir() and rel(p, root) not in cand]


def _textish(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".html", ".htm", ".json", ".js", ".ts", ".tsx", ".jsx", ".py", ".css",
                                   ".yaml", ".yml", ".txt", ".sh"}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _path_inside(path: Path, root: Path) -> bool:
    try:
        path.absolute().relative_to(root.absolute())
        return True
    except ValueError:
        return False
