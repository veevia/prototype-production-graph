#!/usr/bin/env python3
"""Assemble the Lot Release Workbench into one self-contained, offline HTML file.

    python3 build.py --src <prototype root or earlier build> --out <dir> [--overlay <dir>] [--data <lots.json>]

The output directory is itself a prototype root (src/, tests/, data/, content/, build.py) plus dist/prototype.html and
build-manifest.json, so a later step (content integration, rework) can rebuild from it. The build is deterministic:
same inputs, same bytes (no timestamps), so the manifest's hashes prove reproducibility.
--overlay applies a draft's CSS changes (overlay.css is appended to src/styles.css and recorded in the manifest).
--data embeds that dataset (copied to data/lots.json); otherwise data/lots.json, else src/data/seed.json, is embedded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

COPY = ["src", "tests", "data", "content", "build.py"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--overlay")
    ap.add_argument("--data")
    a = ap.parse_args()
    src, out = Path(a.src).resolve(), Path(a.out).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in COPY:
        p = src / name
        if p.is_dir():
            shutil.copytree(p, out / name, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
        elif p.is_file():
            shutil.copyfile(p, out / name)
    overlays = []
    if a.overlay:
        ov = Path(a.overlay)
        css = ov / "overlay.css"
        if css.is_file():
            with (out / "src" / "styles.css").open("a") as f:
                f.write("\n/* overlay: " + ov.name + " */\n" + css.read_text())
            overlays.append(f"{ov.name}/overlay.css")
    # the manifest lists every overlay present in the sources, including ones inherited from an earlier build
    overlays = sorted(set(overlays) | {m + "/overlay.css" for m in re.findall(r"/\* overlay: ([^ ]+) \*/", (out / "src" / "styles.css").read_text())})
    if a.data:
        (out / "data").mkdir(exist_ok=True)
        shutil.copyfile(a.data, out / "data" / "lots.json")
    dataset = out / "data" / "lots.json" if (out / "data" / "lots.json").is_file() else out / "src" / "data" / "seed.json"
    data = json.loads(dataset.read_text())
    s = out / "src"
    fingerprint = hashlib.sha256(b"".join((s / n).read_bytes() for n in ("index.html", "styles.css", "domain.js", "app.js"))
                                 + dataset.read_bytes()).hexdigest()[:10]
    data["build"] = fingerprint
    html = (s / "index.html").read_text()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    for marker, text in (("/*INLINE:styles.css*/", (s / "styles.css").read_text()),
                         ("/*INLINE:domain.js*/", (s / "domain.js").read_text()),
                         ("/*INLINE:app.js*/", (s / "app.js").read_text()),
                         ("/*INLINE:data*/", blob)):
        if marker not in html:
            raise SystemExit(f"index.html lacks the {marker} marker")
        html = html.replace(marker, text)
    dist = out / "dist"
    dist.mkdir()
    (dist / "prototype.html").write_text(html)
    screens = sorted(set(re.findall(r'data-screen="([a-z0-9-]+)"', (s / "app.js").read_text())))
    manifest = {
        "entry": "dist/prototype.html",
        "stack": ["HTML5", "CSS custom properties (design tokens)", "vanilla JavaScript (ES5, no dependencies)",
                  "Python build script", "node:test unit tests"],
        "files": {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file()},
        "screens": {sid: f'[data-screen="{sid}"]' for sid in screens},
        "commands": {"build": "python3 build.py --src . --out <dir> [--data data/lots.json]",
                     "test": "node --test tests/domain.test.js",
                     "open": "open dist/prototype.html (file://, no server)"},
        "unit_tests": "tests/domain.test.js",
    }
    (out / "build-manifest.json").write_text(json.dumps({**manifest, "dataset": str(dataset.relative_to(out)),
                                                         "overlays": overlays, "build": fingerprint}, indent=1) + "\n")
    print(f"built {out / 'dist' / 'prototype.html'} ({len(html) // 1024} KB, {len(data['lots'])} lots, build {fingerprint})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
