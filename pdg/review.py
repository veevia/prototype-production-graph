"""End-review packet generation and reply recording for D15."""

from __future__ import annotations

import html
import json
import random
import re
import shlex
import subprocess
import sys
import tempfile
from hashlib import sha256
from pathlib import Path
from typing import Any, NamedTuple
from urllib.parse import quote

from .util import PKG_ROOT
from .privacy import privacy_path

RANK = re.compile(r"^(F-\d+)\s*:\s*([^#\n]+?)(?:\s+why:\s*(.*))?$", re.I)
ORDINAL_RUNS = {
    "first-run", "second-run", "third-run", "fourth-run", "fifth-run", "sixth-run", "seventh-run", "eighth-run",
    "ninth-run", "tenth-run", "eleventh-run", "twelfth-run", "thirteenth-run", "fourteenth-run", "fifteenth-run",
    "sixteenth-run", "seventeenth-run", "eighteenth-run", "nineteenth-run", "twentieth-run",
}


class ParsedReply(NamedTuple):
    fork_id: str
    rank: str
    ratings: list[str]
    why: str
    fork: dict[str, Any]


def build(project: Path, date: str) -> dict[str, Path]:
    review = project / "review"
    review.mkdir(exist_ok=True)
    forks = _forks(review / "forks")
    order = _blind_order(forks)
    _write_blind_copies(project, forks, order)
    (review / "blind-order.json").write_text(json.dumps(order, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (review / f"blind-order-{date}.json").write_text(json.dumps(order, indent=2, ensure_ascii=False) + "\n",
                                                     encoding="utf-8")
    md = review / f"end-review-{date}.md"
    board = review / f"end-review-{date}.html"
    md.write_text(_markdown(project, forks, order), encoding="utf-8")
    board.write_text(_html(project, forks, order), encoding="utf-8")
    return {"packet": md, "board": board}


def record(project: Path, reply: Path, score_tool: Path | None = None) -> list[str]:
    text = reply.read_text(encoding="utf-8")
    _preference_words()
    aliases = _aliases()
    parsed = _parse_reply(project, text, aliases)
    done = _recorded(project)
    source = _source(text)
    commands: list[str] = []
    for fork_id, rank, ratings, why, fork_doc in parsed:
        if fork_id in done:
            commands.append(f"# skipped {fork_id}: already recorded")
            continue
        key = _record_key(fork_id, fork_doc.get("version"), rank, ratings, why)
        if key in done:
            commands.append(f"# skipped {fork_id}: already recorded")
            continue
        canonical = _write_canonical_fork(fork_doc, fork_id)
        cmd = [sys.executable, str(score_tool or _default_score_tool()), "--data", "knowledge/preferences/wei",
               "record", str(canonical), "--rank", rank]
        for rate in ratings:
            cmd += ["--rate", rate]
        if why:
            cmd += ["--why", why.strip()]
        if source:
            cmd += ["--source", source]
        try:
            subprocess.run(cmd, cwd=PKG_ROOT, check=True)
        finally:
            canonical.unlink(missing_ok=True)
        _mark_recorded(project, key)
        commands.append(" ".join(shlex.quote(x) for x in cmd))
    return commands + _next_commands(project, text)


def _forks(folder: Path) -> list[dict[str, Any]]:
    return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []


def _markdown(project: Path, forks: list[dict[str, Any]], order: dict[str, dict[str, str]]) -> str:
    lines = ["# End review", "", "## 1. Blind choices", ""]
    for fork in forks:
        fork_id = str(fork.get("fork_id", "fork"))
        lines += [f"### {fork_id}", ""]
        for label, c in _blind(fork, order.get(fork_id, {})):
            build = _blind_url(project, fork_id, label)
            lines.append(f"- **{label}**: [open option]({build})")
    lines += ["", "## 2. Reveal", ""]
    for fork in forks:
        lines.append(f"### {fork.get('fork_id', 'fork')}")
        pred = fork.get("predicted") or {}
        if pred:
            lines.append("- Prediction: " + ", ".join(f"{k} {v}" for k, v in pred.items()))
        for c in fork.get("candidates", []):
            lines.append(f"- {c.get('id')}: scores {c.get('scores', {})}; rationale: {c.get('rationale', '')}")
    lines += ["", "## 3. Provisional decisions", ""]
    decisions = project / "review" / "decisions.md"
    lines.append(decisions.read_text(encoding="utf-8") if decisions.is_file() else "- none")
    lines += ["", "## 4. Queued human-only actions", "", "- release: `pdg approve <project> n18_final_verification ...`",
              "- feedback: `pdg feedback <project> --actor Wei --text ...`",
              "- reversals: use each decision card's Undo line", "", "## Reply form", "",
              "```text", "F-001: B > A > C  why: ...", "confirm: all", "release: B", "```", ""]
    return "\n".join(lines)


def _html(project: Path, forks: list[dict[str, Any]], order: dict[str, dict[str, str]]) -> str:
    parts = ["<!doctype html><meta charset='utf-8'><title>End review</title>",
             "<style>body{font-family:system-ui;margin:24px;max-width:1100px}.card{border:1px solid #ccc;"
             "border-radius:10px;padding:14px;margin:12px 0} iframe{width:100%;height:520px;border:1px solid #ddd}</style>",
             "<h1>End review</h1><h2>Blind first</h2>"]
    for fork in forks:
        fork_id = str(fork.get('fork_id', 'fork'))
        parts.append(f"<h3>{html.escape(fork_id)}</h3>")
        for label, c in _blind(fork, order.get(fork_id, {})):
            build = html.escape(_blind_url(project, fork_id, label), quote=True)
            parts.append(f"<div class='card'><h4>{html.escape(label)}</h4><p><a href='{build}'>Open option</a></p>"
                         f"<iframe src='{build}'></iframe></div>")
    parts.append("<h2>Reveal</h2>")
    for fork in forks:
        parts.append(f"<details><summary>{html.escape(str(fork.get('fork_id', 'fork')))} scores and rationale</summary><pre>"
                     f"{html.escape(json.dumps(fork, indent=2))}</pre></details>")
    parts.append("<h2>Reply form</h2><textarea rows='8' style='width:100%'>F-001: Option 1 > Option 2  Option 1:DES-TASTE=5 why: ...\nconfirm: all\nrelease: Option 1</textarea>")
    return "\n".join(parts)


def _blind_order(forks: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for fork in forks:
        candidates = list(fork.get("candidates", []))
        rng = random.Random(str(fork.get("fork_id", "")) + ":" + str(fork.get("version", "")))
        rng.shuffle(candidates)
        out[str(fork.get("fork_id", "fork"))] = {f"Option {i + 1}": str(c.get("id")) for i, c in enumerate(candidates)}
    return out


def _blind(fork: dict[str, Any], order: dict[str, str]) -> list[tuple[str, dict[str, Any]]]:
    by_id = {str(c.get("id")): c for c in fork.get("candidates", [])}
    if order:
        return [(label, by_id[cid]) for label, cid in order.items() if cid in by_id]
    candidates = list(fork.get("candidates", []))
    rng = random.Random(str(fork.get("fork_id", "")) + ":" + str(fork.get("version", "")))
    rng.shuffle(candidates)
    labels = [f"Option {i + 1}" for i in range(len(candidates))]
    return list(zip(labels, candidates))


def _parse_reply(project: Path, text: str, aliases: dict[str, str] | None = None) -> list[ParsedReply]:
    order = json.loads((project / "review" / "blind-order.json").read_text())
    aliases = aliases if aliases is not None else _aliases()
    source = _source(text)
    if source:
        _validate_source(source)
        _refuse_preference_identifier(source, "source")
    parsed: list[ParsedReply] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if re.match(r"^F-\d+\s*:", line, re.I) and not RANK.match(line):
            raise ValueError(f"could not parse review reply line: {raw}")
        match = RANK.match(line)
        if not match:
            continue
        fork_id, ranking_text, why = match.groups()
        labels = order.get(fork_id)
        if not labels:
            raise ValueError(f"{fork_id} has no blind-order map; run `pdg review` before `--record`")
        rank_tokens, rating_pairs = _rank_and_ratings(ranking_text)
        if len(rank_tokens) != len(set(rank_tokens)):
            raise ValueError(f"{fork_id} ranks the same option more than once")
        unknown = [t for t in rank_tokens if t not in labels]
        unknown += [label for label, _, _ in rating_pairs if label not in labels]
        if unknown:
            raise ValueError(f"{fork_id} unknown blind option label(s): {', '.join(unknown)}")
        if why:
            _refuse_preference_identifier(why, "why")
        fork = project / "review" / "forks" / f"{fork_id}.json"
        if not fork.is_file():
            raise FileNotFoundError(f"{fork} does not exist")
        fork_doc = _canonical_fork_data(fork, aliases)
        _refuse_preference_identifiers(fork_doc, "fork")
        rank = ",".join(labels.get(t, t) for t in rank_tokens)
        ratings = [f"{labels[label]}:{dim}={value}" for label, dim, value in rating_pairs]
        parsed.append(ParsedReply(fork_id, rank, ratings, why or "", fork_doc))
    return parsed


def _rank_and_ratings(text: str) -> tuple[list[str], list[tuple[str, str, str]]]:
    ratings = re.findall(r"(Option\s+\d+|[A-Za-z0-9_-]+):([A-Za-z0-9_-]+)=([1-5])", text)
    cleaned = re.sub(r"(Option\s+\d+|[A-Za-z0-9_-]+):[A-Za-z0-9_-]+=[1-5]", "", text)
    rank = [x.strip() for x in re.split(r">|,", cleaned) if x.strip()]
    return rank, ratings


def _candidate_url(project: Path, fork_id: str, candidate: dict[str, Any]) -> str:
    raw = candidate.get("build") or candidate.get("path")
    path = (project / raw).resolve() if raw else _default_candidate_path(project, fork_id, str(candidate.get("id")))
    return "file://" + quote(str(path))


def _blind_url(project: Path, fork_id: str, label: str) -> str:
    return "file://" + quote(str((project / "review" / "blind" / fork_id / _label_slug(label) / "index.html").resolve()))


def _write_blind_copies(project: Path, forks: list[dict[str, Any]], order: dict[str, dict[str, str]]) -> None:
    for fork in forks:
        fork_id = str(fork.get("fork_id", "fork"))
        for label, candidate in _blind(fork, order.get(fork_id, {})):
            target = project / "review" / "blind" / fork_id / _label_slug(label) / "index.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            url = _candidate_url(project, fork_id, candidate)
            target.write_text("<!doctype html><meta charset=\"utf-8\">"
                              f"<meta http-equiv=\"refresh\" content=\"0; url={html.escape(url, quote=True)}\">"
                              f"<title>{html.escape(label)}</title><p><a href=\"{html.escape(url, quote=True)}\">"
                              "Open option</a></p>\n", encoding="utf-8")


def _label_slug(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip()).strip("-").lower() or "option"


def _default_candidate_path(project: Path, fork_id: str, candidate_id: str) -> Path:
    base = project / "candidates" / fork_id / candidate_id
    htmls = sorted(base.rglob("*.html")) if base.exists() else []
    return htmls[0].resolve() if htmls else base.resolve()


def _aliases() -> dict[str, str]:
    path = PKG_ROOT / "knowledge" / "preferences" / "wei" / "aliases.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def _canonical_fork_data(fork: Path, aliases: dict[str, str]) -> dict[str, Any]:
    data = json.loads(fork.read_text())
    run = data.get("run")
    if run in aliases:
        data["run"] = aliases[run]
    elif run in _run_aliases():
        data["run"] = _run_aliases()[run]
    if data.get("run") is not None and str(data["run"]) not in ORDINAL_RUNS:
        raise ValueError("fork run label must be an ordinal label like first-run")
    if data.get("run") is not None:
        _refuse_preference_identifier(str(data["run"]), "run")
    return data


def _write_canonical_fork(data: dict[str, Any], fork_id: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", suffix=f"-{fork_id}.json", delete=False, encoding="utf-8")
    tmp = Path(handle.name)
    handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    handle.close()
    return tmp


def _canonical_fork(fork: Path, aliases: dict[str, str]) -> Path:
    return _write_canonical_fork(_canonical_fork_data(fork, aliases), fork.stem)


def _default_score_tool() -> Path:
    bundled = PKG_ROOT / "scoring" / "vpg_score.py"
    if bundled.is_file():
        return bundled
    return PKG_ROOT.parent / "video-production" / "scoring" / "vpg_score.py"


def _source(text: str) -> str:
    for line in text.splitlines():
        if line.lower().startswith("source:"):
            return line.split(":", 1)[1].strip()
    return ""


def _validate_source(source: str) -> None:
    if not re.fullmatch(r"Wei, [a-z -]+, \d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z", source):
        raise ValueError("source must be date and channel only, e.g. `Wei, run chat, 2026-10-03T22:26Z`")


def _refuse_preference_identifier(text: str, field: str) -> None:
    banned = _preference_words()
    low = _identifier_key(text)
    hit = next((w for w in banned if w and w in low), None)
    if hit:
        raise ValueError(f"{field} contains a product/customer identifier; keep verbatim words in the review file")


def _preference_words() -> list[str]:
    path = privacy_path(PKG_ROOT)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot load preference product-word list from {path}") from exc
    words = [_identifier_key(str(w)) for w in data.get("preference_product_words", [])]
    words += [_identifier_key(str(w)) for w in data.get("banned", [])]
    words += [_identifier_key(str(w)) for w in data.get("whole_words", [])]
    if not words:
        raise ValueError(f"cannot load preference product-word list from {path}")
    return words


def _identifier_key(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _refuse_preference_identifiers(value: Any, field: str) -> None:
    if isinstance(value, str):
        _refuse_preference_identifier(value, field)
    elif isinstance(value, dict):
        for k, v in value.items():
            _refuse_preference_identifiers(str(k), field)
            _refuse_preference_identifiers(v, field)
    elif isinstance(value, list):
        for item in value:
            _refuse_preference_identifiers(item, field)


def _run_aliases() -> dict[str, str]:
    path = privacy_path(PKG_ROOT)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.get("preference_run_aliases", {}).items()}


def _recorded(project: Path) -> set[str]:
    path = project / "review" / "recorded-replies.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return set()
    return {str(x) for x in data.get("forks", [])}


def _mark_recorded(project: Path, fork_id: str) -> None:
    path = project / "review" / "recorded-replies.json"
    done = sorted(_recorded(project) | {fork_id})
    path.write_text(json.dumps({"forks": done}, indent=2) + "\n", encoding="utf-8")


def _record_key(fork_id: str, version: object, rank: str, ratings: list[str], why: str) -> str:
    body = json.dumps({"rank": rank, "ratings": ratings, "why": why}, sort_keys=True)
    return f"{fork_id}@{version or 0}:{sha256(body.encode()).hexdigest()[:16]}"


def _next_commands(project: Path, text: str) -> list[str]:
    q = shlex.quote(str(project))
    out = [f"pdg feedback {q} --actor Wei --text '<change words>'"]
    for line in text.splitlines():
        if line.lower().startswith("release:"):
            choice = line.split(":", 1)[1].strip()
            out.insert(0, f"# release choice recorded in reply: {choice}")
            if not choice.lower().startswith("none"):
                out.insert(1, f"pdg approve {q} n18_final_verification --actor Wei --reason '<release words>'")
    return out
