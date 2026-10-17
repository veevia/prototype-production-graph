"""N12: content and data realism — placeholders, provenance labels, volume, edge cases."""

from __future__ import annotations

import json
import re

from ..artifacts import ContentDoc
from ..context import CheckResult, NodeContext
from ._common import PLACEHOLDER
from .prototype import placeholders

# Static approximation of what a sighted user sees (N13's browser review sees the rendered page): comments, <head>,
# <title>, scripts, styles, <noscript>, <template>, and elements hidden by the `hidden` attribute, aria-hidden,
# display:none / visibility:hidden, or a whole class token hidden / sr-only / visually-hidden. A class such as
# `overflow-hidden` does not hide anything. Void elements (<input type=hidden>) have no content to remove.
_HIDING = (r"\shidden(?=[\s>/=])|aria-hidden\s*=\s*['\"]?true|display\s*:\s*none|visibility\s*:\s*hidden"
           r"|class\s*=\s*['\"][^'\"]*(?<![\w-])(?:hidden|sr-only|visually-hidden)(?![\w-])[^'\"]*['\"]")
NON_VISIBLE = re.compile(
    r"<!--.*?-->|<(head|title|style|noscript|template)\b[^>]*>.*?</\1\s*>|"
    rf"<(?!input\b|img\b|meta\b|link\b|br\b|hr\b)(\w+)\b(?=[^>]*(?:{_HIDING}))[^>]*>.*?</\2\s*>",
    re.S | re.I,
)


def _visible_text(html: str) -> str:
    visible = NON_VISIBLE.sub(" ", html)
    return re.sub(r"<[^>]+>", " ", visible)


PRIMARY = re.compile(r"^(?P<key>[\w-]+)(?:\[(?P<field>[\w-]+)=(?P<value>[^\]]+)\])?$")


def _records(data, primary: str = "") -> tuple[list, str]:
    """(records, what was counted). `primary` names a top-level list, optionally one type of it (`key[field=value]`);
    without it the longest top-level list counts, and the evidence says which, so a reader can tell it was the right one."""
    if isinstance(data, list):
        return data, "the top-level list"
    if not isinstance(data, dict):
        return [], "no list"
    if primary:
        m = PRIMARY.match(primary.strip())
        rows = data.get(m.group("key")) if m else None
        if not isinstance(rows, list):
            return [], f"{primary} (no such list)"
        if m.group("field"):
            rows = [r for r in rows if isinstance(r, dict) and str(r.get(m.group("field"))) == m.group("value")]
        return rows, primary
    lists = {k: v for k, v in data.items() if isinstance(v, list)}
    if not lists:
        return [], "no list"
    key = max(lists, key=lambda k: len(lists[k]))
    return lists[key], f"{key}, the longest of {len(lists)} list{'s' if len(lists) != 1 else ''}"


def _has_field(row, path: str) -> bool:
    """`title` or a dotted `study.title`: the record holds it."""
    for part in path.split("."):
        if not isinstance(row, dict) or part not in row:
            return False
        row = row[part]
    return True


def check(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    root = ctx.output("prototype")
    doc = ContentDoc.model_validate(ctx.json("content"))
    man = json.loads((root / "build-manifest.json").read_text())
    html = (root / man["entry"]).read_text()
    unlabelled = [d.path for d in doc.datasets if d.provenance != "real" and not d.label_shown_in_ui]
    # The rendered page decides (a label a script draws counts; one in <title> or an sr-only span does not). Without a
    # browser, the static scan keeps script text, so a script-drawn label is not refused; the evidence says which.
    from .browser import visible_text_with
    rendered = visible_text_with(root / man["entry"], "synthetic")
    shown = rendered[0] if rendered is not None else bool(re.search(r"synthetic", _visible_text(html), re.I))
    how = "rendered page" if rendered is not None else "static scan (no browser; not verified as rendered)"
    needs_label = any(d.provenance != "real" for d in doc.datasets)
    # a dataset verified against a source names it; an id the run does not know is a claim no reviewer can check (W51)
    known = {s.id for s in ctx.state.inputs.sources} | {e.id for e in ctx.state.research.evidence}
    unknown_src = [f"{d.path}: {sorted(set(d.source_ids) - known)}" for d in doc.datasets if set(d.source_ids) - known]
    t = ctx.thresholds["content"]
    small, missing_files, blob, counted, unverifiable = [], [], "", [], []
    for d in doc.datasets:
        p = root / d.path
        if not p.is_file():
            missing_files.append(d.path)
            continue
        raw = p.read_text()
        blob += raw
        rows, what = _records(json.loads(raw), d.primary)
        n = len(rows)
        absent_fields = [f for f in d.verified_fields if not any(_has_field(r, f) for r in rows)]
        if absent_fields:   # a field said to be checked against the source that no record holds checks nothing (W51)
            unverifiable.append(f"{d.path}: {absent_fields}")
        counted.append(f"{d.path} → {what}: {n} records")
        if n < t["min_records"] or n != d.records:
            small.append(f"{d.path} → {what}: {n} records (declared {d.records}, min {t['min_records']})")
    dataset_ph = sorted({m.group(0) for m in PLACEHOLDER.finditer(blob)})
    ph = sorted(set(placeholders(html)) | set(dataset_ph))
    res.dim("CNT-PLACEHOLDER", not ph, "no placeholder text" if not ph else f"placeholder text: {ph}")
    labelled = not unlabelled and (shown or not needs_label)
    verified = [f"{d.path}: {', '.join(d.verified_fields)} against {', '.join(d.source_ids)}" for d in doc.datasets
                if d.provenance == "mixed"]
    res.dim("CNT-PROVENANCE", labelled and not unknown_src and not unverifiable,
            (f"synthetic data is labelled in the UI ({how})" if labelled
             else f"unlabelled datasets {unlabelled}; visible label present: {shown} ({how})")
            + (f"; verified fields: {'; '.join(verified)}" if verified else "")
            + (f"; source ids the run does not know: {'; '.join(unknown_src)}" if unknown_src else "")
            + (f"; verified fields no record holds: {'; '.join(unverifiable)}" if unverifiable else ""))
    if missing_files:
        res.errors.append(f"datasets missing from the build: {missing_files}")
    res.dim("CNT-VOLUME", not small, f"{len(doc.datasets)} datasets" + (f"; {small}" if small
                                                                        else f": volume ok ({'; '.join(counted)})"))
    absent = [e for e in doc.edge_cases if e not in blob]
    res.dim("CNT-EDGE", bool(doc.edge_cases) and not absent, f"edge cases {doc.edge_cases}" + (f"; absent from data {absent}" if absent else ""))
    return res
