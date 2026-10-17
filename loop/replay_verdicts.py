"""Replay browser-check verdicts on a private field-run corpus before landing check changes."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


PASS_LINE = re.compile(r"^(PASS|FAIL) ([A-Z0-9-]+): (.*)$")
FINDING_LINE = re.compile(r"^\s+- (.*)$")


@dataclass(frozen=True)
class Verdict:
    passed: bool
    finding_count: int = 0
    evidence: str = ""
    findings: tuple[str, ...] = ()


CorpusEntry = dict[str, str]
Runner = Callable[[Path, CorpusEntry, Path], dict[str, Verdict]]


def load_corpus(path: Path | None = None) -> list[CorpusEntry]:
    src = path or Path(os.environ["PDG_REPLAY_CORPUS"])
    rows = json.loads(src.read_text())
    if not isinstance(rows, list):
        raise ValueError(f"{src} must hold a list")
    for i, row in enumerate(rows):
        missing = [k for k in ("label", "build", "plan", "experience", "project") if not row.get(k)]
        if missing:
            raise ValueError(f"{src} entry {i} is missing {', '.join(missing)}")
        for key in ("build", "plan", "experience", "project"):
            if not Path(row[key]).exists():
                raise FileNotFoundError(f"{row['label']}: {key} path does not exist: {row[key]}")
    return rows


def subprocess_runner(package: Path, entry: CorpusEntry, out: Path) -> dict[str, Verdict]:
    cmd = [sys.executable, "-B", "-m", "pdg", "check-prototype", entry["build"], "--plan", entry["plan"],
           "--experience", entry["experience"], "--project", entry["project"], "--out", str(out)]
    proc = subprocess.run(cmd, cwd=package, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"{entry['label']} under {package} exited {proc.returncode}\n{proc.stdout}")
    return parse_verdicts(proc.stdout)


def parse_verdicts(text: str) -> dict[str, Verdict]:
    rows: dict[str, Verdict] = {}
    current: str | None = None
    for line in text.splitlines():
        if m := PASS_LINE.match(line):
            current = m.group(2)
            rows[current] = Verdict(m.group(1) == "PASS", 0, m.group(3))
        elif current and (m := FINDING_LINE.match(line)):
            old = rows[current]
            rows[current] = Verdict(old.passed, old.finding_count + 1, old.evidence, old.findings + (m.group(1),))
    return rows


def verdict_json(verdicts: dict[str, dict[str, Verdict]]) -> dict[str, dict[str, dict[str, object]]]:
    return {label: {dim: {"passed": v.passed, "finding_count": v.finding_count, "evidence": v.evidence,
                          "findings": list(v.findings)}
                    for dim, v in sorted(dims.items())}
            for label, dims in sorted(verdicts.items())}


def load_pinned(path: Path) -> dict[str, dict[str, Verdict]]:
    raw = json.loads(path.read_text())
    return {label: {dim: Verdict(bool(v["passed"]), int(v.get("finding_count", 0)), str(v.get("evidence", "")),
                                   tuple(str(f) for f in v.get("findings", [])))
                    for dim, v in dims.items()}
            for label, dims in raw.items()}


def run_tree(package: Path, corpus: Sequence[CorpusEntry], runner: Runner = subprocess_runner, max_workers: int = 6,
             tag: str = "current") -> dict[str, dict[str, Verdict]]:
    out: dict[str, dict[str, Verdict]] = {}
    with tempfile.TemporaryDirectory(prefix=f"pdg-replay-{tag}-") as tmp, ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(runner, package, entry, Path(tmp) / entry["label"]): entry["label"] for entry in corpus}
        for fut in as_completed(futures):
            out[futures[fut]] = fut.result()
    return out


def compare(before: dict[str, dict[str, Verdict]], after: dict[str, dict[str, Verdict]]) -> list[dict[str, object]]:
    flips = []
    for label in sorted(set(before) | set(after)):
        dims = sorted(set(before.get(label, {})) | set(after.get(label, {})))
        for dim in dims:
            b = before.get(label, {}).get(dim)
            a = after.get(label, {}).get(dim)
            if b is not None and a is not None and (b.passed, _finding_key(b)) == (a.passed, _finding_key(a)):
                continue
            if b is None or a is None:
                direction = "added" if a is not None else "removed"
                stricter = a is not None and not a.passed
            elif b.passed != a.passed:
                direction = "stricter" if b.passed and not a.passed else "more lenient"
                stricter = direction == "stricter"
            elif len(_finding_key(a)) != len(_finding_key(b)):
                direction = "stricter" if len(_finding_key(a)) > len(_finding_key(b)) else "more lenient"
                stricter = direction == "stricter"
            elif _finding_key(a) != _finding_key(b):
                direction = "findings changed"
                stricter = False
            flips.append({"label": label, "dimension": dim, "from": b, "to": a,
                          "direction": direction, "stricter": stricter})
    return flips


def _finding_key(v: Verdict) -> tuple[str, ...]:
    return v.findings or tuple(f"finding-{i}" for i in range(v.finding_count))


def print_flips(flips: Iterable[dict[str, object]]) -> None:
    print("| entry | dimension | direction | before | after |")
    print("|---|---|---|---|---|")
    any_row = False
    for f in flips:
        any_row = True
        b, a = f["from"], f["to"]
        print(f"| {f['label']} | {f['dimension']} | {f['direction']} | {_cell(b)} | {_cell(a)} |")
    if not any_row:
        print("| none | - | - | - | - |")


def _cell(v: object) -> str:
    if v is None:
        return "missing"
    assert isinstance(v, Verdict)
    return f"{'PASS' if v.passed else 'FAIL'} / {v.finding_count}"


def main(argv: list[str] | None = None, runner: Runner = subprocess_runner) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--baseline", type=Path, help="package tree to compare against")
    ap.add_argument("--pin", type=Path, help="write pinned current verdicts")
    ap.add_argument("--against", type=Path, help="compare current verdicts against pinned verdicts")
    ap.add_argument("--allow-stricter", action="store_true")
    ap.add_argument("--max-workers", type=int, default=6)
    ns = ap.parse_args(argv)
    if not ns.baseline and not ns.against and not ns.pin:
        ap.error("provide --baseline, --against or --pin")
    corpus = load_corpus()
    here = Path(__file__).resolve().parents[1]
    current = run_tree(here, corpus, runner, max(1, min(6, ns.max_workers)), "current")
    if ns.pin:
        ns.pin.write_text(json.dumps(verdict_json(current), indent=2, ensure_ascii=False) + "\n")
    if ns.against:
        before = load_pinned(ns.against)
    elif ns.baseline:
        before = run_tree(ns.baseline.resolve(), corpus, runner, max(1, min(6, ns.max_workers)), "baseline")
    else:
        return 0
    flips = compare(before, current)
    print_flips(flips)
    return 1 if any(f["stricter"] for f in flips) and not ns.allow_stricter else 0


if __name__ == "__main__":
    raise SystemExit(main())
