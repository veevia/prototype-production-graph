#!/usr/bin/env python3
"""Build a filtered public checkout; never copy private history or publish automatically."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ".pdg-public-export.json"
PATTERNS = (
    "pdg/*.py", "pdg/tools/*.py", "agents/*.yaml", "prompts/*.md",
    "graph/*.yaml", "config/*.yaml", "rubrics/*.yaml", "schemas/*.json",
    "schemas/artifacts/*.json", "templates/control/*.md", "examples/coa-review/**/*",
    "tests/*.py", "tests/kernel-sync.json", "vendor/axe-core/*",
    "loop/replay_verdicts.py", "knowledge/public/privacy.json", "scripts/export_public.py",
)
DOCS = (
    "architecture", "graph-spec", "state-model", "control-documents", "control-access",
    "orchestration", "evaluation-and-gates", "self-improvement", "node-catalog",
    "edge-catalog", "agent-catalog", "rubric-catalog", "previous-iterations",
)
NOISE = {".DS_Store", "__pycache__", ".pytest_cache", "node_modules", ".pdg", "_runs"}
SECRET = re.compile(
    rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|"
    rb"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{32,}|"
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
)
# Folders that exist only in the author's workspace. Exported text names what a standalone checkout has instead
# (PUBLIC_PATHS); only the files that describe the workspace itself, the tests that look for it and the shared kernel's
# provenance notes (pinned byte for byte by tests/kernel-sync.json) still name them.
WORKSPACE_ONLY = re.compile(r"\b(?:00_README|02_Workflows|04_MCP|05_Library)\b")
DESCRIBES_WORKSPACE = frozenset({"CONTRIBUTING.md", "scripts/export_public.py", "pdg/lock.py", "pdg/provenance.py",
                                 "pdg/util.py"})
PUBLIC_PATHS = (   # whole phrases first, then the general prefixes
    ("(the case study in knowledge/case-studies/) and Wei's canonical frameworks (00_README/_frameworks/)",
     "and Wei's canonical frameworks (neither is distributed)"),
    ("(for example `05_Library/DESIGN-SYSTEM-AI-INSTRUCTIONS.md` copied into `sources/`)",
     "(for example your design system's AI instructions, as `templates/artifacts/DESIGN-SYSTEM-AI-INSTRUCTIONS.md` "
     "describes, copied into `sources/`)"),
    ("05_Library/_starters/ for a production foundation", "Your own production starter, if any, for a production foundation"),
    ("the design system (05_Library) or brand guide", "the design system or brand guide"),
    ("from the workspace starter's installed dependencies\n  (`05_Library/_starters/next-tailwind/node_modules/axe-core/`).",
     "from an installed copy of the package."),
    ("adapter in `04_MCP/markitdown/`", "an MCP adapter in the author's workspace"),
    ("`04_MCP/workiq/`; workspace skill `workiq-grounding`", "in the author's workspace, with its skill `workiq-grounding`"),
    ("| `knowledge/case-studies/hub-programmes-2026/*_TENANT*` | the evidence behind the rules | the builder script "
     "(identifiers stay in `_TENANT` files) |",
     "| `knowledge/public/evidence.json` | the public evidence records behind the rules (the private case studies are "
     "not distributed) | the author's public export |"),
    ("05_Library/DESIGN-SYSTEM-AI-INSTRUCTIONS.md", "templates/artifacts/DESIGN-SYSTEM-AI-INSTRUCTIONS.md"),
    ("00_README/_templates/", "templates/artifacts/"),
    ("`02_Workflows/prototype-design/", "pdg's `"),
)


def public_paths(text: str) -> str:
    for old, new in PUBLIC_PATHS:
        text = text.replace(old, new)
    return text


def names_workspace(name: str) -> bool:
    """Whether an exported file may name workspace-only folders."""
    return name in DESCRIBES_WORKSPACE or name.startswith("tests/")


def png_metadata(data: bytes) -> list[str]:
    """A PNG's text, EXIF and content-credential chunks: a public image carries pixels only."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ["not a PNG"]
    found, i = [], 8
    while i + 8 <= len(data):
        length, kind = int.from_bytes(data[i:i + 4], "big"), data[i + 4:i + 8].decode("latin-1")
        if kind in ("tEXt", "zTXt", "iTXt", "eXIf", "caBX"):
            found.append(kind)
        i += 12 + length
    return found


def gif_metadata(data: bytes) -> list[str]:
    """A GIF's comment, plain-text and application blocks other than the looping one (XMP rides in these)."""
    if data[:6] not in (b"GIF87a", b"GIF89a") or len(data) < 13:
        return ["not a GIF"]
    found, i = [], 13 + (3 << ((data[10] & 7) + 1) if data[10] & 0x80 else 0)
    while i < len(data) and data[i] != 0x3B:
        if data[i] == 0x21:
            label, j = data[i + 1], i + 2
            name = data[j + 1:j + 12] if label == 0xFF else b""
            if label == 0xFE or label == 0x01 or (label == 0xFF and name != b"NETSCAPE2.0"):
                found.append({0xFE: "comment", 0x01: "plain text"}.get(label) or "application " + name.decode("latin-1"))
        elif data[i] == 0x2C:
            j = i + 10 + (3 << ((data[i + 9] & 7) + 1) if data[i + 9] & 0x80 else 0) + 1
        else:
            return found + ["malformed"]
        while j < len(data) and data[j]:   # data sub-blocks up to their terminator
            j += data[j] + 1
        i = j + 1
    return found


def image_metadata(name: str, data: bytes) -> list[str]:
    return png_metadata(data) if name.endswith(".png") else gif_metadata(data) if name.endswith(".gif") else []


def standalone(name: str, data: bytes) -> bytes:
    """A copied tool must run without the package it was written in: refuse one that imports vpg."""
    if re.search(rb"^[ \t]*(?:from|import)[ \t]+vpg\b", data, re.M):
        raise ValueError(f"{name} imports the vpg package, which the public checkout does not have; "
                         "export its standalone implementation")
    return data


def encoded(data: object) -> bytes:
    return (json.dumps(data, indent=1, ensure_ascii=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular_bytes(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected a regular, non-symlink source: {path}")
    return path.read_bytes()


def public_rules(root: Path) -> tuple[bytes, bytes]:
    data = json.loads(regular_bytes(root / "knowledge/rules.json"))
    records = []
    data["note"] = "Public author-maintained rule profile; private evidence and project approvals are not distributed."
    for rule in data["rules"]:
        eid = "PUBLIC-" + rule["id"]
        records.append({"id": eid, "type": "standard", "text": rule["statement"],
                        "evidence_class": "recommendation", "citations": ["public-rule:" + rule["id"]]})
        rule["evidence"] = [eid]
        rule["evidence_class"] = "recommendation"
        rule["note"] = ""
        rule["observations"] = []
        rule["previous_versions"] = []
        for event in rule["lifecycle"]["history"]:
            event["evidence"] = [eid]
            event["reason"] = "Author rule lifecycle; original private evidence is not distributed."
            for key in set(event) - {"state", "at", "by", "human", "basis", "evidence", "reason", "awaits_confirmation"}:
                del event[key]
    evidence = {"distribution": "public", "fields": [], "records": records}
    return encoded(data), encoded(evidence)


def inventory(root: Path = ROOT) -> dict[str, bytes]:
    workspace = root.parents[1]
    if not (workspace / "02_Workflows/video-production/scoring/vpg_score.py").is_file():
        raise ValueError("export requires the Wei_workspace authoring checkout, including video-production/scoring")
    files: dict[str, bytes] = {}
    for pattern in PATTERNS:
        for path in sorted(root.glob(pattern)):
            if path.is_dir():
                continue
            rel = path.relative_to(root)
            if set(rel.parts) & NOISE or "_TENANT" in path.name:
                continue
            if any(parent.is_symlink() for parent in path.parents if parent != root.parent):
                raise ValueError(f"symlink source directory: {path}")
            files[rel.as_posix()] = regular_bytes(path)
    for name in ("requirements.txt", "constraints.txt", "pytest.ini"):
        files[name] = regular_bytes(root / name)
    for name in DOCS:
        files[f"docs/{name}.md"] = regular_bytes(root / f"docs/{name}.md")
    files["docs/research/graph-engineering-and-tools.md"] = regular_bytes(
        root / "docs/research/graph-engineering-and-tools.md")
    for source, target in {
        "README.md": "README.md", "CONTRIBUTING.md": "CONTRIBUTING.md",
        "LICENSE": "LICENSE", "THIRD_PARTY_NOTICES.md": "THIRD_PARTY_NOTICES.md",
        "gitignore": ".gitignore", "test.yml": ".github/workflows/test.yml",
        "pdg-overview.gif": "docs/images/pdg-overview.gif",
    }.items():
        files[target] = regular_bytes(root / "community" / source)
    # The scorer is copied, never imported from a sibling checkout. VPG v1.8 moved its implementation into the vpg
    # package and left scoring/vpg_score.py as a shim over it, which cannot run in the public checkout.
    files["scoring/vpg_score.py"] = standalone(
        "scoring/vpg_score.py", regular_bytes(workspace / "02_Workflows/video-production/vpg/scoring.py"))
    files["scoring/test_vpg_score.py"] = regular_bytes(
        workspace / "02_Workflows/video-production/scoring/test_vpg_score.py")
    # Artifact templates retain their headings and placeholders, not private workspace navigation.
    refs = sorted({ref for path in (root / "templates/control").glob("*.md")
                   for ref in re.findall(r"(?:00_README/_templates|05_Library)/[\w.-]+\.md", path.read_text())})
    for ref in refs:
        source = workspace / ref
        name = source.name
        if ref.startswith("05_Library/"):
            files[f"templates/artifacts/{name}"] = (
                "# Design-system authority\n\n**TL;DR:** Register your own authorized design system before generating UI.\n\n"
                "Name the component library, tokens, typography, spacing, icons, accessibility rules and source owner. "
                "Copy its authorized guidance into your project's sources and cite its source ID in design decisions. "
                "No customer brand assets or proprietary libraries are supplied.\n"
            ).encode()
        else:
            text = regular_bytes(source).decode()
            text = re.sub(r"(?m)^source:.*$", "source: Author artifact template; private programme examples omitted", text)
            text = re.sub(r"(<FILL:[^>\n]*?), e\.g\.,[^>\n]*>", r"\1>", text)
            text = re.sub(r'AI: replace "[^"]+" with the system-of-record named in the source\.',
                          "AI: use the system-of-record named in your authorized sources.", text)
            text = re.sub(r"\[([^\]]+)\]\((?!https?://|#)[^)]+\)", r"\1", text)
            files[f"templates/artifacts/{name}"] = text.encode()
    files["knowledge/rules.json"], files["knowledge/public/evidence.json"] = public_rules(root)
    files["knowledge/rules-changelog.jsonl"] = b""
    forks = regular_bytes(root / "scoring/forks.yaml").decode()
    forks = forks.replace("../video-production/scoring/vpg_score.py", "scoring/vpg_score.py")
    forks = forks.replace("../../.venv/bin/python", "python")
    forks = forks.replace('run_from: "02_Workflows/prototype-design"', 'run_from: "."')
    forks = forks.replace("02_Workflows/video-production/scoring/README.md", "docs/dependencies.md")
    files["scoring/forks.yaml"] = forks.encode()
    for name, content in list(files.items()):
        if name.startswith("templates/control/"):
            text = content.decode()
            for ref in refs:
                text = text.replace(ref, "templates/artifacts/" + Path(ref).name)
            files[name] = text.encode()
    skills = sorted({skill for node in _workflow(root)["nodes"] for skill in node["skills"]})
    rows = "\n".join(f"- `{skill}`" for skill in skills)
    files["docs/dependencies.md"] = (
        "# Dependency inventory\n\n**TL;DR:** The engine needs Python, Node and Chromium; host skills and enterprise integrations are optional.\n\n"
        "## Runtime and tests\n\n"
        "Python 3.11+, pydantic, PyYAML, jsonschema and Playwright; pytest for tests. "
        "Minimum versions are in `requirements.txt`; `constraints.txt` pins the exact versions CI verifies, "
        "because a new Playwright brings a new Chromium that can change browser verdicts. Node.js 22+ runs prototype unit tests. "
        "Chromium is installed with `python -m playwright install chromium`. axe-core and its license are bundled. "
        "The candidate scorer and its tests are copied, not imported from a sibling checkout.\n\n"
        "## Source closure\n\n"
        "Graph, defaults, rubrics, schemas, role cards, node prompts, eight control templates, "
        "their referenced artifact templates, public rule profile, fictional example and regression tests are included. "
        "No runtime Python import reaches into Wei_workspace. Kernel comparisons with the author's video workflow "
        "and private provenance checks explicitly skip when those optional sources are absent.\n\n"
        "## Optional host capabilities\n\n"
        f"The graph names {len(skills)} skill labels below. These are agent guidance, not installed Python dependencies. "
        "Use each packet's instructions and rubrics manually or map these labels to your assistant's own skills. "
        "The role cards' runtime bindings are examples, not agents launched by the engine. "
        "WorkIQ/M365 grounding, wiki retrieval, document conversion, Figma and other MCP integrations "
        "are optional source-acquisition tools. They require their own authorization and are not bundled.\n\n"
        + rows + "\n\n## Publication boundary\n\n"
        "Excluded: customer case studies, private citations and quotations, prior rule snapshots, "
        "personal preference decisions/models, run directories, workspace SOPs containing standing grants, "
        "the historical build-loop reviewer and private Git history. "
        "Public evidence entries are rule recommendations, not customer evidence. "
        "Published rules retain author confirmation status, not approval by a new project's principal.\n"
    ).encode()
    # References to omitted workspace-only guides lead to the standalone guide instead.
    replacements = {
        "adr/0001-standalone-engine.md": "../CONTRIBUTING.md",
        "../../SOPs/prototype-design/SOP.md": "../README.md",
        "../knowledge/seed/build_rules.py": "../knowledge/public/evidence.json",
        "../../../video-production/docs/research/graph-engineering-and-tools.md":
            "https://docs.langchain.com/oss/python/langgraph/overview",
    }
    for name, content in list(files.items()):
        if name.startswith("docs/") and name.endswith(".md"):
            text = content.decode()
            for old, new in replacements.items():
                text = text.replace(old, new)
            if name == "docs/research/graph-engineering-and-tools.md":
                text = text.replace("its research doc", "upstream graph reference")
            if name == "docs/self-improvement.md":
                text = re.sub(r"The seed rule base was distilled.*?became three enforced rules:",
                              "The public profile recommends checks such as these; private feedback and source records "
                              "are not distributed, and author defaults do not approve your project's decisions:", text,
                              flags=re.S)
            files[name] = text.encode()
    for name, content in list(files.items()):
        if names_workspace(name):
            continue
        try:
            text = content.decode()
        except UnicodeDecodeError:
            continue
        files[name] = public_paths(text).encode()
    return files


def _workflow(root: Path) -> dict:
    import yaml
    return yaml.safe_load((root / "graph/workflow.yaml").read_text())


def scan(files: dict[str, bytes], root: Path = ROOT) -> None:
    private = root / "knowledge/case-studies/hub-programmes-2026/deidentify_TENANT.json"
    path = private if private.exists() else root / "knowledge/public/privacy.json"
    policy = json.loads(regular_bytes(path))
    if not isinstance(policy.get("banned"), list) or not policy["banned"]:
        raise ValueError(f"privacy policy must declare blocked identifiers: {path}")
    errors = []
    for name, content in files.items():
        if "_TENANT" in Path(name).name or set(Path(name).parts) & NOISE:
            errors.append(f"{name}: excluded path")
        if len(content) >= 100 * 1024 * 1024:
            errors.append(f"{name}: exceeds GitHub ordinary-file limit")
        if SECRET.search(content):
            errors.append(f"{name}: credential-shaped content")
        if not names_workspace(name) and WORKSPACE_ONLY.search(content.decode("utf-8", "replace")):
            errors.append(f"{name}: workspace-only path (add its public counterpart to PUBLIC_PATHS)")
        if image_metadata(name, content):
            errors.append(f"{name}: image metadata ({', '.join(image_metadata(name, content))}); strip it before export")
        if name.startswith("vendor/") or name.endswith((".png", ".gif")):   # minified or binary: no text to read
            continue
        text = content.decode("utf-8")
        if re.search(r"/(?:Users|home)/[^/\s]+/|https://[^/\s]+\.sharepoint\.com", text):
            errors.append(f"{name}: personal path or tenant URL")
        if any(word.lower() in text.lower() for word in policy["banned"]):
            errors.append(f"{name}: private identifier")
        if any(re.search(rf"\b{re.escape(word)}\b", text, re.I) for word in policy.get("whole_words", [])):
            errors.append(f"{name}: private whole-word identifier")
    if errors:
        raise ValueError("public export refused:\n" + "\n".join(sorted(set(errors))))


def build(root: Path = ROOT) -> dict[str, bytes]:
    files = inventory(root)
    snapshot = dict(files)
    with tempfile.TemporaryDirectory(prefix="pdg-public-build-") as folder:
        stage = Path(folder)
        for name, content in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        env.pop("PYTHONPATH", None)
        subprocess.run([sys.executable, "-B", "-m", "pdg", "docs"], cwd=stage, env=env,
                       check=True, capture_output=True, text=True)
        files = {p.relative_to(stage).as_posix(): p.read_bytes()
                 for p in stage.rglob("*") if p.is_file()}
    scan(files, root)
    if inventory(root) != snapshot:
        raise ValueError("source changed during export; retry from a stable authoring snapshot")
    return files


def safe_target(dest: Path, name: str) -> Path:
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts or rel.parts[0] == ".git":
        raise ValueError(f"unsafe export path: {name}")
    path = dest / rel
    for p in (dest, path, *path.parents):
        if p.is_symlink():
            raise ValueError(f"symlink destination refused: {p}")
    if path.exists() and not path.is_file():
        raise ValueError(f"destination is not a regular file: {path}")
    return path


def sync(dest: Path, files: dict[str, bytes], *, apply: bool = False) -> list[str]:
    if dest.is_symlink():
        raise ValueError("destination must not be a symlink")
    dest = dest.absolute()
    safe_target(dest, RECEIPT)
    dest = dest.resolve()
    workspace = ROOT.parents[1]
    if dest == workspace or dest in workspace.parents or workspace in dest.parents:
        raise ValueError("destination must be outside the source workspace")
    receipt = safe_target(dest, RECEIPT)
    old = json.loads(receipt.read_text())["files"] if receipt.exists() else {}
    changed = []
    # Preflight the whole batch before any writes, including removals.
    for name in sorted(set(old) | set(files)):
        path = safe_target(dest, name)
        present = sha(path.read_bytes()) if path.exists() else None
        wanted = sha(files[name]) if name in files else None
        if present == wanted:
            continue
        if name in old and present is None and wanted is not None:
            raise ValueError(f"destination has a deleted managed file: {name}; reconcile it into the source first")
        if present is not None and (name not in old or present != old[name]):
            raise ValueError(f"destination has an unowned or edited file: {name}; reconcile it into the source first")
        changed.append(name)
    if apply:
        dest.mkdir(parents=True, exist_ok=True)
        for name in changed:
            path = safe_target(dest, name)
            if name in files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(files[name])
            else:
                path.unlink(missing_ok=True)
        receipt.write_bytes(encoded({"schema": "pdg-public-export/v1",
                                     "files": {name: sha(content) for name, content in sorted(files.items())}}))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        files = build()
        changed = sync(args.dest, files, apply=args.apply)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"export failed: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr or exc.stdout or "", file=sys.stderr)
        return 2
    print(f"{len(files)} public files; {len(changed)} {'updated' if args.apply else 'different'}")
    for name in changed:
        print(f"  {name}")
    return 1 if changed and args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
