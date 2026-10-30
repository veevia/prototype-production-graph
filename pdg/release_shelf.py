"""Stable release shelf rebuilt from a run's ledger and release package artifacts."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import Approval, ArtifactRecord, Defect, ProjectState
from .util import rel


@dataclass(frozen=True)
class ShelfRelease:
    version: int
    date: str
    decider: str
    typed_by: str
    delegation: str
    package: ArtifactRecord
    summary: ArtifactRecord | None
    advisories: list[str]
    archived: bool = False


def shelf_root(project: Path) -> Path:
    try:
        cfg = yaml.safe_load((project / "pdg.project.yaml").read_text()) if (project / "pdg.project.yaml").is_file() else {}
    except (OSError, yaml.YAMLError):
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    raw = (cfg or {}).get("release_shelf") or "releases"
    if Path(raw).is_absolute():
        raise ValueError("release_shelf must be project-relative")
    root = (project / raw).resolve()
    project_root, hub = project.resolve(), project.resolve().parent
    in_project = _is_relative_to(root, project_root)
    in_hub_child = root.parent == hub and root != hub and root != project_root
    if not in_project and not in_hub_child:
        raise ValueError("release_shelf must stay inside the project or its parent hub folder")
    if in_hub_child and ((root / ".pdg").exists() or (root / "pdg.project.yaml").exists()):
        raise ValueError("release_shelf in a parent hub must not point at a pdg project")
    return root


def export(project: Path, state: ProjectState) -> list[ShelfRelease]:
    releases = release_rows(state)
    root = shelf_root(project)
    scoped = _scope(root, project, state)
    versions = scoped["versions"]
    _check_write_target(root)
    _check_write_target(versions)
    root.mkdir(parents=True, exist_ok=True)
    versions.mkdir(parents=True, exist_ok=True)
    if scoped["shared"]:
        _claim_namespace(versions, state)
    records = scoped["records"]
    _check_write_target(records)
    records.mkdir(exist_ok=True)
    for row in releases:
        dst = versions / f"v{row.version}"
        _check_write_target(dst)
        if dst.exists():
            continue
        src = project / row.package.path
        if not src.exists():
            continue
        tmp = versions / f".v{row.version}.tmp"
        _check_write_target(tmp)
        if tmp.exists():
            shutil.rmtree(tmp)
        shutil.copytree(src, tmp, symlinks=False)
        os.replace(tmp, dst)
        if row.summary and (project / row.summary.path).is_file():
            target = records / f"{scoped['prefix']}v{row.version}-release-summary.md"
            _check_write_target(target)
            shutil.copyfile(project / row.summary.path, target)
    _check_write_target(scoped["latest"])
    _write_latest(scoped["latest"], versions, releases)
    text = releases_markdown(project, root, state, releases)
    _check_write_target(project / "RELEASES.md")
    (project / "RELEASES.md").write_text(text, encoding="utf-8")
    _check_write_target(scoped["index"])
    scoped["index"].write_text(text, encoding="utf-8")
    return releases


def release_rows(state: ProjectState) -> list[ShelfRelease]:
    artifacts = list(state.artifacts.values())
    rows: dict[int, ShelfRelease] = {}
    for approval in state.history.approvals:
        if approval.node != "n18_final_verification" or approval.decision != "approved":
            continue
        package = _artifact_for(artifacts, "package", approval)
        if package is None:
            continue
        summary = _artifact_for(artifacts, "release_summary", approval)
        rows[approval.build_version] = ShelfRelease(version=approval.build_version, date=approval.at[:10],
                                                    decider=approval.on_behalf_of or approval.actor,
                                                    typed_by=approval.actor if approval.on_behalf_of else "",
                                                    delegation=approval.delegation or "", package=package,
                                                    summary=summary,
                                                    advisories=_advisories(state.evaluation.defects,
                                                                          approval.build_version))
    return sorted(rows.values(), key=lambda r: (r.version, r.date))


def latest_release_path(project: Path) -> Path | None:
    try:
        state = ProjectState.model_validate(json.loads((project / ".pdg" / "state.json").read_text()))
    except (OSError, ValueError):
        return None
    rows = release_rows(state)
    if not rows:
        return None
    root = shelf_root(project)
    latest = _scope(root, project, state)["latest"]
    return latest if latest.is_file() else None


def releases_markdown(project: Path, root: Path, state: ProjectState, releases: list[ShelfRelease]) -> str:
    shared = not _is_relative_to(root, project.resolve())
    lines = ["# Releases", "", "Rebuilt by `pdg release-shelf` from approved release records and release packages.", ""]
    if not releases:
        return "\n".join(lines + ["No approved N18 releases found.", ""])
    lines += ["| Version | Date | Decider | Typed by | Delegation | Open advisories | Link |",
              "|---|---|---|---|---|---:|---|"]
    for row in sorted(releases, key=lambda r: r.version, reverse=True):
        scope = _scope(root, project, state) if shared else {"versions": root}
        link = rel(scope["versions"] / f"v{row.version}", project)
        typed = row.typed_by or "—"
        delegation = row.delegation or "—"
        missing = not (project / row.package.path).exists()
        status = "archived; restore source package" if missing and not ((scope["versions"] / f"v{row.version}").exists()) else f"[{link}]({link})"
        lines.append(f"| v{row.version} | {row.date} | {row.decider} | {typed} | {delegation} | "
                     f"{len(row.advisories)} | {status} |")
    latest = latest_release_path(project)
    if latest:
        lines += ["", f"Latest: [{rel(latest, project)}]({rel(latest, project)}).", ""]
    return "\n".join(lines)


def _artifact_for(artifacts: list[ArtifactRecord], key: str, approval: Approval) -> ArtifactRecord | None:
    expected = approval.outputs.get(key)
    matches = [a for a in artifacts if a.node == approval.node and a.key == key
               and (not expected or a.sha256 == expected)]
    if not matches:
        return None
    return sorted(matches, key=lambda a: (a.attempt, a.created))[-1]


def _advisories(defects: list[Defect], version: int) -> list[str]:
    return [d.id for d in defects if d.opened_at_version <= version and d.status in ("open", "persisting")
            and d.severity in ("P3", "P4") and not d.deferred]


def _write_latest(latest: Path, versions: Path, releases: list[ShelfRelease]) -> None:
    if not releases:
        latest.write_text("<!doctype html><title>No releases</title><p>No releases found.</p>\n", encoding="utf-8")
        return
    existing = [r for r in releases if (versions / f"v{r.version}").is_dir()]
    if not existing:
        latest.write_text("<!doctype html><title>Release archived</title><p>No release copy is on the shelf. "
                          "Restore the archived package and run pdg release-shelf.</p>\n", encoding="utf-8")
        return
    target = os.path.relpath(versions / f"v{existing[-1].version}" / _entry(versions / f"v{existing[-1].version}"),
                             latest.parent)
    latest.write_text("<!doctype html><meta charset=\"utf-8\">"
                      f"<meta http-equiv=\"refresh\" content=\"0; url={html.escape(target, quote=True)}\">"
                      f"<title>Latest release</title><p><a href=\"{html.escape(target, quote=True)}\">"
                      "Open latest release</a></p>\n", encoding="utf-8")


def _entry(package: Path) -> str:
    manifest = package / "manifest.json"
    if manifest.is_file():
        try:
            files: dict[str, Any] = json.loads(manifest.read_text()).get("files", {})
            htmls = sorted(k for k in files if k.endswith(".html"))
            dist = [h for h in htmls if "/dist/" in h or h.startswith("dist/")]
            if dist:
                return dist[0]
            if htmls:
                return htmls[0]
        except ValueError:
            pass
    htmls = sorted(p.relative_to(package).as_posix() for p in package.rglob("*.html"))
    return htmls[0] if htmls else "."


def _scope(root: Path, project: Path, state: ProjectState) -> dict[str, Path | str]:
    if _is_relative_to(root, project.resolve()):
        return {"versions": root, "records": root / "records", "latest": root / "latest.html",
                "index": project / "RELEASES.md", "prefix": "", "shared": False}
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", state.project.id).strip(".-") or project.name
    _refuse_casefold_slug_collision(root, slug)
    return {"versions": root / slug, "records": root / "records", "latest": root / f"{slug}-latest.html",
            "index": root / f"RELEASES-{slug}.md", "prefix": f"{slug}-", "shared": True}


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _check_write_target(path: Path) -> None:
    try:
        if path.lstat().st_mode and path.is_symlink():
            raise ValueError(f"release shelf write target is a symlink: {path}")
    except FileNotFoundError:
        return


def _claim_namespace(versions: Path, state: ProjectState) -> None:
    marker = versions / ".pdg-release-owner.json"
    owner = {"project_id": state.project.id, "created": state.project.created}
    if marker.exists():
        _check_write_target(marker)
        try:
            existing = json.loads(marker.read_text())
        except ValueError as exc:
            raise ValueError(f"release shelf owner marker is unreadable: {marker}") from exc
        if existing != owner:
            raise ValueError(f"release shelf namespace {versions} is owned by another project")
    else:
        _check_write_target(marker)
        marker.write_text(json.dumps(owner, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _refuse_casefold_slug_collision(root: Path, slug: str) -> None:
    if not root.is_dir():
        return
    wanted = slug.casefold()
    for child in root.iterdir():
        if child.name.casefold() == wanted and child.name != slug:
            raise ValueError(f"release shelf namespace {slug} collides with existing {child.name}")
