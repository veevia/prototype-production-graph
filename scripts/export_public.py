#!/usr/bin/env python3
"""Export an allowlisted starter tree without Git history or private project inputs."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOP_LEVEL = {
    ".gitignore", "README.md", "CONTRIBUTING.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "requirements.txt", "constraints.txt", "pytest.ini",
}
DIRECTORIES = {
    ".github/workflows", "agents", "config", "docs", "graph", "knowledge/public",
    "pdg", "prompts", "rubrics", "schemas", "scoring", "scripts", "templates", "tests", "vendor/axe-core", "loop",
}
KNOWLEDGE = {"knowledge/rules.json", "knowledge/rules-changelog.jsonl",
             "knowledge/design-principles.md", "knowledge/seed-rule-review.md"}
EXCLUDED = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".pdg", "_runs",
            "sources", "work", "releases", "preferences", "history"}
SECRET = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|"
    rb"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)


def allowed(name: str) -> bool:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or set(path.parts) & EXCLUDED:
        return False
    if name.startswith("templates/testing/") and path.suffix in {".json", ".jsonl", ".csv"}:
        return False
    return name in TOP_LEVEL | KNOWLEDGE or any(name.startswith(p + "/") for p in DIRECTORIES)


def inventory(root: Path = ROOT) -> dict[str, bytes]:
    result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others",
                             "--exclude-standard", "-z"], check=True, capture_output=True)
    files = {}
    for name in sorted(set(result.stdout.decode().split("\0")) - {""}):
        path = root / name
        if not path.exists():
            continue
        if not allowed(name):
            raise ValueError(f"unapproved publication path: {name}")
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root.parent):
            raise ValueError(f"symlink source is not publishable: {name}")
        files[name] = path.read_bytes()
    scan(files)
    return files


def scan(files: dict[str, bytes]) -> None:
    errors = []
    for name, content in files.items():
        if not allowed(name):
            errors.append(f"{name}: unapproved publication path")
        if SECRET.search(content):
            errors.append(f"{name}: credential-shaped content")
        if name.startswith("vendor/") or name.endswith((".png", ".gif")):
            continue
        text = content.decode("utf-8")
        if re.search(r"/(?:Users|home)/[^/\s]+/|https://[^/\s]+\.sharepoint\.com", text):
            errors.append(f"{name}: personal path or tenant URL")
    if "knowledge/rules.json" in files:
        rules = json.loads(files["knowledge/rules.json"])["rules"]
        for rule in rules:
            if (rule["scope"] != "stable" or rule.get("observations") or rule.get("previous_versions")
                    or rule.get("confirmed_by_human")
                    or any(h.get("human") for h in rule["lifecycle"]["history"])):
                errors.append(f"knowledge/rules.json: project history or approval in {rule['id']}")
    if errors:
        raise ValueError("publication refused:\n" + "\n".join(errors))


def export(dest: Path, files: dict[str, bytes]) -> None:
    dest = dest.resolve()
    if dest == ROOT or ROOT in dest.parents:
        raise ValueError("export destination must be outside the starter repository")
    if dest.exists() and any(dest.iterdir()):
        raise ValueError("export destination must be empty; existing files are never overwritten")
    scan(files)
    dest.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        files = inventory()
        if args.out:
            export(args.out, files)
        print(f"verified {len(files)} allowlisted starter files")
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
