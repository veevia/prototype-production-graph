"""N11: the prototype build — reproducibility, offline, screens implemented, tokens only, no placeholders, code quality."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..artifacts import BuildManifest
from ..context import CheckResult, NodeContext
from ..util import sha256_file
from . import _node
from ._common import PLACEHOLDER, canonical_colour, finding, strip_attr_placeholders

ATTR_REF = re.compile(r"""\b(?:src|href|action|poster)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.I)
SRCSET_REF = re.compile(r"""\bsrcset\s*=\s*(?:"([^"]*)"|'([^']*)'|([^>]+))""", re.I)
CALL_REF = re.compile(r"""\b(?:fetch|import|EventSource|sendBeacon)\(\s*(?:"([^"`']+)"|'([^'`"]+)'|`([^`"']+)`)""", re.I)
SOCKET_REF = re.compile(r"""\bWebSocket\(\s*(?:"([^"`']+)"|'([^'`"]+)'|`([^`"']+)`)""", re.I)
# static ES-module imports (`import x from "…"`, `import "…"`) and XMLHttpRequest.open("GET", "…")
MODULE_REF = re.compile(r"""\bimport\s+(?:[\w*{}\s,$]+\s+from\s*)?(?:"([^"]+)"|'([^']+)')""")
XHR_REF = re.compile(r"""\.open\(\s*["'][A-Za-z]+["']\s*,\s*(?:"([^"`']+)"|'([^'`"]+)'|`([^`"']+)`)""")
CSS_URL_REF = re.compile(r"""url\(\s*["']?([^"')\s]+)""", re.I)
CSS_IMPORT_REF = re.compile(r"""@import\s+(?:url\(\s*)?["']?([^"')\s;]+)""", re.I)
STYLE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
INLINE_STYLE = re.compile(r"""\sstyle\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
ROOT_BLOCK = re.compile(r":root\s*\{[^}]*\}", re.S)
THEME_BLOCK = re.compile(r"\[data-theme[^\]]*\]\s*\{[^}]*\}", re.S)
HEX_COLOUR = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
CSS_COLOUR_FN = re.compile(r"\b(?:rgb|rgba|hsl|hsla)\(\s*[^)]*?\)", re.I)


def _external(value: str) -> bool:
    value = value.strip().strip("\"'")
    return not value.lower().startswith("data:") and (value.startswith(("http://", "https://", "ws://", "wss://", "//")))


def _snippet(kind: str, value: str) -> str:
    return f"{kind}={value.strip()}"[:80]


def external_refs(html: str) -> list[str]:
    refs: list[str] = []
    for m in ATTR_REF.finditer(html):
        value = next(g for g in m.groups() if g is not None)
        if _external(value):
            refs.append(re.match(r"""[^\s=]+\s*=\s*["']?(?:https?:)?//""", m.group(0), re.I).group(0))
    for m in SRCSET_REF.finditer(html):
        value = next(g for g in m.groups() if g is not None)
        for candidate in (part.strip().split()[0] for part in value.split(",") if part.strip()):
            if _external(candidate):
                refs.append(_snippet("srcset", candidate))
    for pattern in (CALL_REF, SOCKET_REF, MODULE_REF, XHR_REF):
        for m in pattern.finditer(html):
            value = next(g for g in m.groups() if g is not None)
            if _external(value):
                refs.append(_snippet("call", value))
    for m in CSS_IMPORT_REF.finditer(html):
        if _external(m.group(1)):
            refs.append(_snippet("@import", m.group(1)))
    css_without_imports = re.sub(r"@import[^;]+;", "", html, flags=re.I)
    for m in CSS_URL_REF.finditer(css_without_imports):
        if _external(m.group(1)):
            refs.append(_snippet("url", m.group(1)))
    return refs


def root_colours(html: str) -> list[str]:
    """The colour values the build's token blocks (`:root`, `[data-theme]`) declare."""
    css = "\n".join(STYLE.findall(html))
    blocks = "\n".join(m.group(0) for rx in (ROOT_BLOCK, THEME_BLOCK) for m in rx.finditer(css))
    return sorted({_normalise_colour(m.group(0)) for rx in (HEX_COLOUR, CSS_COLOUR_FN) for m in rx.finditer(blocks)})


# a marker the build writes, not a lookup: `[data-screen="x"]` in a selector or a CSS rule proves nothing is built
_MARKER = re.compile(r"""(?<![\[\w-])data-screen\s*=\s*\\?["']([^"'\\]+)\\?["']"""
                     r"""|["']data-screen["']\s*[:,]\s*["']([^"']+)["']"""
                     r"""|dataset\.screen\s*=\s*["']([^"']+)["']""")


def screen_markers(root: Path, html: str) -> set[str]:
    """Screen ids the build marks, in its markup or in its own scripts: a compiled React build writes
    `"data-screen": "hub"` or `createElement("section", {"data-screen": "hub"})`, never the markup attribute
    (field run 2, R2-17). Scripts are read up to 30 MB in all; a file that would pass the budget is skipped, not the
    rest (batch 7 review I5)."""
    texts, budget = [html], 30_000_000
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x != "node_modules")
        for name in sorted(files):
            f = Path(d) / name
            if f.suffix not in (".js", ".mjs", ".cjs") or not f.is_file():
                continue
            size = f.stat().st_size
            if size > budget:
                continue
            budget -= size
            texts.append(f.read_text(errors="ignore"))
    return {g for text in texts for m in _MARKER.finditer(text) for g in m.groups() if g}


def token_block_extras(html: str, system) -> list[str] | None:
    """Colours the build's token block declares that the approved design system does not: moving every literal into
    generated `:root` variables satisfied the token rule with 38 such colours (field run 2, R2-08). None: no system."""
    if system is None:
        return None
    allowed = {_normalise_colour(c.value) for c in system.colors}
    return [c for c in root_colours(html) if c not in allowed]


def _normalise_colour(value: str) -> str:
    return canonical_colour(value)


def _normalise_hex(value: str) -> str:
    raw = value.lstrip("#")
    if len(raw) in (3, 4):
        raw = "".join(c * 2 for c in raw)
    return f"#{raw.upper()}"


def off_token_colours(html: str) -> list[str]:
    css = "\n".join(STYLE.findall(html))
    css = THEME_BLOCK.sub("", ROOT_BLOCK.sub("", css))
    inline_css = "\n".join(next(g for g in m.groups() if g is not None) for m in INLINE_STYLE.finditer(html))
    scan = "\n".join([css, inline_css])
    colours = {_normalise_hex(m.group(0)) for m in HEX_COLOUR.finditer(scan)}
    colours.update(m.group(0) for m in CSS_COLOUR_FN.finditer(scan))
    return sorted(colours)


_SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.S | re.I)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_JS_STRING = re.compile(r"'(?:\\.|[^'\\\n])*'|\"(?:\\.|[^\"\\\n])*\"|`(?:\\.|[^`\\])*`", re.S)
_JS_MARKER = re.compile(r"\b(TODO|TBD|FIXME|XXX+)\b")                      # the placeholder convention, in capitals
_JS_PROSE = re.compile(r"\b(lorem|ipsum|placeholder text|sample text)\b", re.I)


def placeholders(html: str) -> list[str]:
    """Placeholder words a user could read: the page's text and visible attributes, and the strings its scripts render.
    A script's identifiers, comments and styles are not read: `const todo = …` failed a build (field run W41)."""
    scripts = _SCRIPT.findall(html)
    page = _COMMENT.sub(" ", _STYLE.sub(" ", _SCRIPT.sub(" ", html)))
    found = {m.group(0) for m in PLACEHOLDER.finditer(strip_attr_placeholders(page))}
    for lit in (x for src in scripts for x in _JS_STRING.findall(src)):
        found |= {m.group(0) for rx in (_JS_MARKER, _JS_PROSE) for m in rx.finditer(lit)}
    return sorted(found)


def _manifest(ctx: NodeContext, root: Path) -> BuildManifest:
    data = ctx.json("build_manifest") if ctx.output("build_manifest") else json.loads((root / "build-manifest.json").read_text())
    return BuildManifest.model_validate(data)


def check_static(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    root = ctx.output("prototype_build") or ctx.artifact("prototype_build")
    man = _manifest(ctx, root)
    entry = root / man.entry
    if not entry.is_file():
        res.errors.append(f"entry {man.entry} does not exist in the build")
        return res
    html = entry.read_text()
    mism = [f for f, h in man.files.items() if not (root / f).is_file() or sha256_file(root / f) != h]
    res.dim("BLD-REPRO", not mism, f"{len(man.files)} files hashed" + (f"; mismatched {mism[:5]}" if mism else ": all match"))
    ext = external_refs(html)
    res.dim("BLD-OFFLINE", not ext, "no network references" if not ext else f"{len(ext)} network references, e.g. {ext[:3]}",
            [finding("BLD-OFFLINE", f"network reference {e}", "P2", man.entry, "n11_prototype_development",
                     "inline the asset or remove the reference", "0 http(s) references in the build") for e in ext[:5]])
    screens = [s.id for s in ctx.state.design.screens]
    marked = screen_markers(root, html)
    missing = [s for s in screens if s not in marked]
    how = ""
    if missing:
        # a marker written from data (`data-screen="feed-${id}"`) is invisible to the text scan: render the route (W52)
        from .browser import rendered_screens
        routes = {s.id: s.route for s in ctx.state.design.screens}
        seen = rendered_screens(entry, {s: routes[s] for s in missing}, {s: r for s, r in routes.items() if s not in missing})
        if seen is None:
            how = "; no browser, so the rest were not rendered (text scan only)"
        else:
            shown = [s for s in missing if s in seen["shown"]]
            missing = [s for s in missing if s not in seen["shown"]]
            why = {"everywhere": "its marker shows on every route loaded (a navigation link, or screens stacked on one "
                                 "page?)", "hidden": "its marker is on the page but not visible at 1280 px",
                   "linked": "its marker is only on a link or navigation entry, which names the screen but is not it",
                   "unloaded": "its route did not finish loading", "unchecked": "not rendered: the 30 s budget ran out"}
            reasons = [f"{s}: {why[k]}" for s in missing for k in why if s in seen[k]]
            how = (f"; {len(shown)} found by rendering their routes: {shown}" if shown else "") + (
                f"; {'; '.join(reasons)}" if reasons else "")
    res.dim("BLD-SCREENS", not missing, f"{len(screens) - len(missing)}/{len(screens)} screens implemented" + how
            + (f"; missing {missing}: mark each with data-screen=\"<id>\" (or 'data-screen': '<id>', or "
               f"dataset.screen = '<id>'), or make its route render [data-screen=\"<id>\"]" if missing else ""))
    off = off_token_colours(html)
    # moving every literal into generated `:root` variables satisfied "literals only in the token block" with 38 colours
    # the design system never had (field run 2, R2-08): the block's values must be the system's colours
    extra = token_block_extras(html, ctx.state.design.system)
    res.dim("BLD-TOKENS", not off and not extra,
            ("colours come from tokens only" if not off else f"off-system colour literals: {off[:8]}")
            + (f"; the token block declares {len(extra)} colour(s) the design system does not have: {extra[:8]}" if extra
               else "; every token-block colour is a design-system colour" if extra is not None else ""))
    ph = placeholders(html)
    res.dim("BLD-PLACEHOLDER", not ph, "no placeholder text" if not ph else f"placeholder text found: {ph}")
    return res


def check_unit(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    if not _node.node_bin():
        res.errors.append("node is not on PATH; the unit and syntax checks cannot run")
        res.data["blocked"] = "node unavailable"
        return res
    root = ctx.output("prototype_build") or ctx.artifact("prototype_build")
    man = _manifest(ctx, root)
    js = sorted(p for p in root.rglob("*.js") if "node_modules" not in p.parts)
    bad = _node.syntax(js, ctx.thresholds["feasibility"]["node_timeout_s"])
    res.dim("BLD-SYNTAX", not bad, f"{len(js)} scripts parse" if not bad else f"syntax errors: {bad}")
    if not man.unit_tests or not (root / man.unit_tests).is_file():
        res.dim("BLD-UNIT", False, "no unit-test file in the manifest")
        return res
    passed, failed, tail = _node.unit_in_scratch(root / man.unit_tests, root, ctx.thresholds["feasibility"]["node_timeout_s"])
    res.dim("BLD-UNIT", passed >= 1 and failed == 0, f"node --test: {passed} passed, {failed} failed")
    res.data["test_results"] = [{"suite": f"node --test {man.unit_tests}", "passed": passed, "failed": failed, "details": tail}]
    return res
