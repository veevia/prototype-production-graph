"""The eight control documents: who may write each one, approval locks, change requests and append-only sections.

A control document is installed only through a node's declared `kind: control` output, and only when that node passes:
  - the node must list the document in `controls.write`;
  - a locked document (approved at a human gate) changes only after a named human approves a change request, which
    unlocks it for one writer node; identical content is not a change;
  - sections marked `<!-- append-only -->` keep every line of the accepted version (evidence is never silently rewritten);
  - every accepted version is archived by number and hash under `.pdg/controls/`, so rollback and resume can restore it.
A hand edit to `controls/<doc>.md` outside this path is detected as an integrity problem that blocks the run.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .models import CONTROL_DOCS, ControlRecord, ControlVersion
from .util import PKG_ROOT, now, rel, sha256_bytes, sha256_file

if TYPE_CHECKING:  # pragma: no cover
    from .engine import Engine

TEMPLATES = PKG_ROOT / "templates" / "control"
APPEND_ONLY = "<!-- append-only -->"
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _structural(lines: list[str]) -> list[bool]:
    """For each line, whether it can be a heading: not inside the YAML front matter or a fenced code block. A `## `
    line in a code sample or a `#` comment in the front matter is text, never a section boundary."""
    return _scan(lines)[0]


def _lines(text: str) -> list[str]:
    """Lines split on "\n" only, as split_sections splits them. str.splitlines() also breaks on form feeds and
    U+2028, so a fence "closed" after one would pass a check yet stay open in the merge."""
    return [ln.rstrip("\r") for ln in text.split("\n")]


def unclosed_fence(text: str) -> int | None:
    """The 1-based line of a code fence that is never closed (it would swallow every later section), or None."""
    return _scan(_lines(text))[1]


def duplicate_headings(text: str) -> list[str]:
    """Level-2 section titles that appear more than once (a merge would keep only one copy)."""
    titles = [t for t, _ in split_sections(text)[1]]
    return sorted({t for t in titles if titles.count(t) > 1})


def _scan(lines: list[str]) -> tuple[list[bool], int | None]:
    ok = [True] * len(lines)
    start = 0
    if lines and lines[0].strip() == "---":
        end = next((j for j in range(1, len(lines)) if lines[j].strip() == "---"), None)
        if end is not None:   # front matter only when it closes (as front_matter() reads it)
            ok[:end + 1] = [False] * (end + 1)
            start = end + 1
    fence, opened = "", None
    for i in range(start, len(lines)):
        m = _FENCE.match(lines[i])
        if fence:
            ok[i] = False
            mark = lines[i].strip()
            if m and mark == mark[0] * len(mark) and mark[0] == fence[0] and len(mark) >= len(fence):
                fence, opened = "", None
        elif m:
            fence, ok[i], opened = m.group(1), False, i + 1
    return ok, opened


def front_matter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def append_only_sections(text: str) -> dict[str, list[str]]:
    """Heading → the non-empty lines of each section whose first line after the heading is the append-only marker."""
    out: dict[str, list[str]] = {}
    lines = _lines(text)
    ok = _structural(lines)
    i = 0
    while i < len(lines):
        m = _HEADING.match(lines[i]) if ok[i] else None
        if m and i + 1 < len(lines) and lines[i + 1].strip() == APPEND_ONLY:
            level, title = len(m.group(1)), m.group(2).strip()
            body: list[str] = []
            j = i + 2
            while j < len(lines):
                n = _HEADING.match(lines[j]) if ok[j] else None
                if n and len(n.group(1)) <= level:
                    break
                if lines[j].strip():
                    body.append(lines[j].rstrip())
                j += 1
            out[title] = body
            i = j
            continue
        i += 1
    return out


def append_only_violations(old: str, new: str) -> list[str]:
    errs = []
    new_sections = append_only_sections(new)
    for title, lines in append_only_sections(old).items():
        if title not in new_sections:
            errs.append(f"append-only section '{title}' was removed")
            continue
        kept = set(new_sections[title])
        lost = [ln for ln in lines if ln not in kept]
        if lost:
            errs.append(f"append-only section '{title}' lost {len(lost)} line(s), e.g. {lost[0][:80]!r}")
    return errs


def split_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """(preamble, [(section title, full section text)]) for level-2 headings outside front matter and code fences."""
    lines = [ln for ln in re.split(r"(?<=\n)", text) if ln]
    ok = _structural([ln.rstrip("\r\n") for ln in lines])
    starts = [i for i, ln in enumerate(lines) if ok[i] and ln.startswith("## ")]
    if not starts:
        return text, []
    secs = []
    for k, s in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(lines)
        secs.append((lines[s][3:].strip(), "".join(lines[s:end])))
    return "".join(lines[:starts[0]]), secs


def merge_sections(accepted: str, submitted: str, owned: list[str]) -> tuple[str, list[str]]:
    """Take the owned sections (and the preamble, if owned) from `submitted`; keep everything else as accepted.
    An owned section the submission leaves out keeps its accepted text, so a writer may submit only its sections.
    Returns (merged text, non-owned sections the submission changed — ignored, and reported by the caller)."""
    own = set(owned)
    pa, sa = split_sections(accepted)
    ps, ss = split_sections(submitted)
    sub = dict(ss)
    ignored: list[str] = []
    if "_preamble" in own and ps.strip():
        out = [ps]
    else:
        out = [pa]
        if ps.strip() and ps.strip() != pa.strip():
            ignored.append("_preamble")
    present = set()
    for title, body in sa:
        present.add(title)
        if title in own and title in sub:
            out.append(sub[title])
        else:
            if title in sub and sub[title].strip() != body.strip():
                ignored.append(title)
            out.append(body)
    for title, body in ss:
        if title not in present:
            (out.append(body) if title in own else ignored.append(title))
    return "\n".join(x.rstrip() + "\n" for x in out if x.strip()), ignored


def accepted_path(root: Path, rec: ControlRecord) -> Path | None:
    """The archived copy of a document's accepted version, or None before one is recorded (the file is then the text)."""
    h = next((v for v in reversed(rec.history) if v.sha256 == rec.accepted_sha256), None)
    return root / h.archived if h else None


class ControlStore:
    def __init__(self, engine: "Engine"):
        self.engine = engine
        self.dir = engine.project.root / "controls"
        self.archive = engine.project.root / ".pdg" / "controls"

    def path(self, doc: str) -> Path:
        return self.dir / f"{doc}.md"

    @property
    def records(self) -> dict[str, ControlRecord]:
        return self.engine.state.controls

    def ensure(self) -> None:
        """Create a registry entry for every document; seed a missing file from its template (version 0)."""
        self.dir.mkdir(parents=True, exist_ok=True)
        self.archive.mkdir(parents=True, exist_ok=True)
        for doc in CONTROL_DOCS:
            p = self.path(doc)
            if not p.exists():
                shutil.copyfile(TEMPLATES / f"{doc}.md", p)
            if doc not in self.records:
                rec = ControlRecord(doc=doc)
                self._archive(rec, p, node="init")
                self.records[doc] = rec

    def _archive(self, rec: ControlRecord, src: Path, node: str, attempt: int = 0) -> None:
        sha = sha256_file(src)
        dst = self.archive / f"{rec.doc}.v{rec.version}.md"
        shutil.copyfile(src, dst)
        rec.accepted_sha256 = sha
        rec.history.append(ControlVersion(version=rec.version, sha256=sha, node=node, at=now(), attempt=attempt,
                                          archived=rel(dst, self.engine.project.root)))

    def text(self, doc: str) -> str:
        p = self.path(doc)
        return p.read_text() if p.exists() else ""

    def accepted_text(self, doc: str) -> str:
        p = accepted_path(self.engine.project.root, self.records[doc])
        return p.read_text() if p else self.text(doc)

    def merge(self, node_id: str, doc: str, src: Path) -> tuple[str, list[str]]:
        """(the text installing `src` would produce, non-owned sections it tried to change). A shared document takes
        only the writer's owned sections; a single-writer document takes the whole submission."""
        node = self.engine.idx.nodes.get(node_id)
        owned = node.controls.sections.get(doc) if node else None
        new = src.read_text()
        return merge_sections(self.accepted_text(doc), new, owned) if owned else (new, [])

    def merged(self, node_id: str, doc: str, src: Path) -> str:
        return self.merge(node_id, doc, src)[0]

    def check_install(self, node_id: str, writes: list[str], doc: str, src: Path) -> list[str]:
        """Why installing `src` as `doc` for `node_id` would be refused (empty = allowed)."""
        if doc not in writes:
            return [f"{node_id} may not write control document {doc}"]
        rec = self.records[doc]
        if src.stat().st_size == 0 or not src.read_text().strip():
            return [f"{doc}.md submitted empty"]
        submitted = src.read_text()
        opened = unclosed_fence(submitted)
        if opened is not None:
            return [f"{doc}.md: the code fence opened at line {opened} is never closed; close it (an open fence swallows "
                    "every later section, other writers' included)"]
        dups = duplicate_headings(submitted)
        if dups:
            return [f"{doc}.md: section heading(s) {', '.join(dups)} appear more than once; merge each into one section"]
        live = self.path(doc)
        if live.exists() and sha256_file(live) != rec.accepted_sha256:
            return [f"controls/{doc}.md was edited outside the workflow; a named human restores it first "
                    "(`pdg unblock <project> run --restore-controls`)"]
        new = self.merged(node_id, doc, src)
        if sha256_bytes(new.encode()) == rec.accepted_sha256:
            return []
        if (rec.status == "locked" and rec.unlocked_for != node_id and node_id not in rec.unlocked_for_nodes
                and rec.locked_node != node_id):
            return [f"{doc}.md is locked ({rec.locked_by}); a named human must approve a change request first "
                    f"(`pdg change-request <project> --doc {doc} --actor <human>`)"]
        return append_only_violations(self.accepted_text(doc), new)

    def install(self, node_id: str, doc: str, src: Path) -> bool:
        """Install an already-checked document (merged by section ownership). Returns True if the content changed.
        Crash-safe order: archive, record, then the live file (resume restores the live file from the archive)."""
        rec = self.records[doc]
        text, ignored = self.merge(node_id, doc, src)
        if ignored:  # never silent: ledgered, and the submitting agent is told in the submit output
            self.engine.ledger.append("control_edits_ignored", doc=doc, node=node_id, sections=ignored)
            owners = {s: n.id for n in self.engine.wf.nodes if n.id != node_id for s in n.controls.sections.get(doc, [])}
            named = ", ".join(f"{s.replace('_preamble', 'preamble')} ({owners.get(s, 'another writer')})" for s in ignored)
            self.engine.notices.append(
                f"{doc}.md: not applied, because other writers own these sections: {named}. Only your own sections were "
                "installed. If you did not mean to change them, your copy was out of date and nothing is lost.")
        if sha256_bytes(text.encode()) == rec.accepted_sha256:
            return False
        staged = self.archive / f"{doc}.staged-{node_id}.md"
        staged.write_text(text)
        rec.version += 1
        if rec.status != "locked":
            rec.status = "accepted"
        nodes = self.engine.state.runtime.nodes
        self._archive(rec, staged, node=node_id, attempt=nodes[node_id].attempt if node_id in nodes else 0)
        staged.unlink()
        self.engine.save("control_installed")
        tmp = self.path(doc).with_suffix(".md.tmp")
        tmp.write_text(text)
        tmp.replace(self.path(doc))
        self.engine.ledger.append("control_installed", doc=doc, node=node_id, version=rec.version,
                                  sha256=rec.accepted_sha256)
        return True

    def lock(self, docs: list[str], node_id: str, actor: str) -> list[str]:
        locked = []
        for doc in docs:
            rec = self.records[doc]
            rec.status = "locked"
            rec.locked_by = f"{node_id} by {actor}"
            rec.locked_node = node_id
            rec.unlocked_for = None
            rec.unlocked_for_nodes = []
            locked.append(doc)
            self.engine.ledger.append("control_locked", doc=doc, node=node_id, actor=actor, sha256=rec.accepted_sha256)
        return locked

    def relock(self, docs: list[str], node_id: str, actor: str) -> list[str]:
        """Close a change request's unlock. The lock keeps its original owner (the gate that signed the document)."""
        for doc in docs:
            rec = self.records[doc]
            rec.unlocked_for = None
            rec.unlocked_for_nodes = [n for n in rec.unlocked_for_nodes if n != node_id]
            self.engine.ledger.append("control_relocked", doc=doc, node=node_id, actor=actor, owner=rec.locked_node)
        return list(docs)

    def needs_change_request(self, node_id: str, writes: list[str]) -> list[str]:
        """Documents this node writes that are locked by another node's gate and not unlocked for it."""
        return [d for d in writes if self.records[d].status == "locked" and self.records[d].locked_node != node_id
                and self.records[d].unlocked_for != node_id and node_id not in self.records[d].unlocked_for_nodes]

    def unlock_for(self, doc: str, writer: str) -> None:
        rec = self.records[doc]
        rec.unlocked_for = writer
        self.engine.ledger.append("control_unlocked", doc=doc, writer=writer)

    def unlock_for_many(self, doc: str, writers: list[str]) -> None:
        rec = self.records[doc]
        rec.unlocked_for_nodes = sorted(set(rec.unlocked_for_nodes) | set(writers))
        rec.unlocked_for = writers[0] if len(writers) == 1 else rec.unlocked_for
        self.engine.ledger.append("control_unlocked", doc=doc, writers=writers)

    def close_unlocks_for(self, node_id: str, locking_docs: list[str] | None = None) -> None:
        locking = set(locking_docs or [])
        for doc, rec in self.records.items():
            if rec.unlocked_for == node_id:
                rec.unlocked_for = None
                self.engine.ledger.append("control_relocked", doc=doc, node=node_id, owner=rec.locked_node)
            if doc in locking and rec.unlocked_for_nodes:
                rec.unlocked_for_nodes = []
                self.engine.ledger.append("control_relocked", doc=doc, node=node_id, owner=rec.locked_node)
            elif node_id in rec.unlocked_for_nodes:
                rec.unlocked_for_nodes = [n for n in rec.unlocked_for_nodes if n != node_id]
                self.engine.ledger.append("control_relocked", doc=doc, node=node_id, owner=rec.locked_node)

    def drift(self, ignore: set[str] | None = None) -> list[str]:
        """Documents whose live file no longer matches the accepted version (a hand edit)."""
        out = []
        for doc, rec in self.records.items():
            if ignore and doc in ignore:
                continue
            p = self.path(doc)
            if not p.exists():
                out.append(f"controls/{doc}.md is missing")
            elif sha256_file(p) != rec.accepted_sha256:
                out.append(f"controls/{doc}.md was edited outside the workflow (sha256 differs from accepted v{rec.version})")
        return out

    def restore_accepted(self, reason: str) -> list[str]:
        """Put every live file back to its accepted version, keeping the displaced text beside the archive."""
        restored = []
        for doc, rec in self.records.items():
            p = self.path(doc)
            if p.exists() and sha256_file(p) == rec.accepted_sha256:
                continue
            h = next((v for v in reversed(rec.history) if v.sha256 == rec.accepted_sha256), None)
            if h is None:
                continue
            if p.exists():
                shutil.copyfile(p, self.archive / f"{doc}.{reason}-{now().replace(':', '')}.md")
            shutil.copyfile(self.engine.project.root / h.archived, p)
            restored.append(doc)
        return restored

    def settle_after_crash(self) -> list[str]:
        """On resume: a live file that matches an older accepted version (the crash landed between recording and writing)
        is rolled forward to the accepted version. A file matching no version is left for `drift()` to report."""
        fixed = []
        for doc, rec in self.records.items():
            p = self.path(doc)
            if not p.exists():
                continue
            cur = sha256_file(p)
            if cur == rec.accepted_sha256:
                continue
            if any(v.sha256 == cur for v in rec.history):
                h = next(v for v in reversed(rec.history) if v.sha256 == rec.accepted_sha256)
                shutil.copyfile(self.engine.project.root / h.archived, p)
                fixed.append(doc)
        return fixed
