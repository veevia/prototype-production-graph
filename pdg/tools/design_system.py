"""N09: the visual system — WCAG contrast of every declared pair, type scale, radii, spacing, provenance."""

from __future__ import annotations

import re

from ..artifacts import DesignSystemDoc
from ..context import CheckResult, NodeContext
from ._common import canonical_colour, contrast, parse_colour

RATIO_CELL = re.compile(r"(\d+(?:\.(\d+))?)\s*:\s*1")
TOKEN_CELL = re.compile(r"^var\((.+)\)$")
RULE_ROW = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
MEASURED = re.compile(r"ratio|contrast|measured", re.I)
REQUIRED = re.compile(r"\b(min(imum)?|need(ed)?|requir\w*|target|threshold)\b", re.I)
WCAG_STEPS = (3.0, 4.5, 7.0)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def stated_ratios(md: str, names: set[str]) -> list[tuple[str, str, str]]:
    """(fg, bg, stated) for each row of a design.md table whose header names the measured ratio ("Ratio", "Contrast")
    and whose first two cells name colour tokens. The approver reads this table, so it must say what the tokens give
    (N-29). Only that column is read: a decorated ratio is skipped, never replaced by the "Minimum" beside it."""
    rows, lines = [], md.splitlines()
    for k in range(1, len(lines)):
        if not RULE_ROW.match(lines[k].strip()) or not lines[k - 1].lstrip().startswith("|"):
            continue
        head = _cells(lines[k - 1])
        col = next((n for n, h in enumerate(head) if n >= 2 and MEASURED.search(h) and not REQUIRED.search(h)), None)
        if col is None:
            continue
        for line in lines[k + 1:]:
            if not line.lstrip().startswith("|"):
                break
            cells = _cells(line)
            if len(cells) <= col:
                continue
            fg, bg = (TOKEN_CELL.sub(r"\1", c.strip("`").strip()).removeprefix("--") for c in cells[:2])   # `--ink`, var(--ink)
            stated = cells[col].strip("*_` ")
            if fg in names and bg in names and RATIO_CELL.fullmatch(stated):
                rows.append((fg, bg, stated))
    return rows


def misstated(stated: str, actual: float) -> str | None:
    """Why a stated ratio is not what the tokens give, or None. It may be cut or rounded to its decimals, never rounded
    up across a WCAG step (4.499 is not 4.5:1)."""
    m = RATIO_CELL.fullmatch(stated)
    value, unit = float(m.group(1)), 10 ** -len(m.group(2) or "")
    step = next((w for w in WCAG_STEPS if value >= w > actual + 1e-9), None)
    if step is not None:
        return f"rounds up across {step:g}:1"
    if not -unit - 1e-9 < value - actual <= unit / 2 + 1e-9:
        return f"measures {actual:.2f}:1"
    return None


def check(ctx: NodeContext) -> CheckResult:
    res = CheckResult()
    doc = DesignSystemDoc.model_validate(ctx.json("design_system"))
    t = ctx.thresholds["design_system"]
    colors = {c.name: c for c in doc.colors}
    # a translucent token (a shadow, a scrim) is declared too, so the build's token block can be checked against the
    # system (field run 2, R2-08); a contrast pair still needs two opaque colours
    bad_hex = [c.name for c in doc.colors if parse_colour(c.value) is None]
    if bad_hex:
        res.errors.append(f"colour tokens must be CSS colours (#rrggbb, #rrggbbaa, rgb()/rgba() or hsl()/hsla()): {bad_hex}")
        return res
    see_through = sorted({n for p in doc.contrast_pairs for n in (p.fg, p.bg) if n in colors
                          and canonical_colour(colors[n].value).startswith("rgba(")})
    if see_through:
        res.errors.append(f"contrast pairs need opaque #rrggbb colours; translucent: {see_through}")
        return res
    failing, rows = [], []
    for p in doc.contrast_pairs:
        if p.fg not in colors or p.bg not in colors:
            failing.append(f"{p.fg}/{p.bg}: unknown token")
            continue
        ratio = contrast(canonical_colour(colors[p.fg].value), canonical_colour(colors[p.bg].value))
        need = t["min_contrast_non_text"] if p.non_text else (t["min_contrast_large"] if p.large_text else t["min_contrast_text"])
        rows.append(f"{p.fg}/{p.bg} {ratio:.2f}:1 (≥{need})")
        if ratio + 1e-9 < need:
            failing.append(f"{p.fg} on {p.bg} = {ratio:.2f}:1 < {need}:1 ({p.use})")
    # a stated ratio may be rounded or cut to its decimals; anything further off is not what the tokens give
    md_path = ctx.output("design_md")
    md = md_path.read_text() if md_path is not None and md_path.is_file() else ""
    # a colour exempts a component's state from VIS-STATE-FILLS only if it is a status colour, and only for a component
    # design.md names: a generic class ("btn") would otherwise exempt every button unseen (batch 18 review S8)
    from .browser import status_colours
    status = status_colours(doc.colors)
    for c in doc.colors:
        if c.state_fill_of and c.name not in status:
            res.errors.append(f"{c.name} lists `state_fill_of` but is no status colour (by name or role): nothing to exempt")
        unnamed = [k for k in c.state_fill_of if not re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", md)]
        if c.state_fill_of and unnamed:
            res.errors.append(f"{c.name}'s `state_fill_of` names {unnamed}, which design.md does not mention: say there which "
                              "state of which component it fills")
    wrong, checked = [], 0
    for fg, bg, stated in stated_ratios(md, set(colors)):
        if canonical_colour(colors[fg].value).startswith("rgba(") or canonical_colour(colors[bg].value).startswith("rgba("):
            continue
        checked += 1
        actual = contrast(canonical_colour(colors[fg].value), canonical_colour(colors[bg].value))
        why = misstated(stated, actual)
        if why:
            wrong.append(f"{fg}/{bg} stated {stated}, {why}" + (f" (measures {actual:.2f}:1)" if why.startswith("rounds") else ""))
    res.dim("VIS-CONTRAST", not failing and bool(doc.contrast_pairs), f"{len(doc.contrast_pairs)} pairs"
            + (f"; failing: {failing}" if failing else ": all pass"))
    # a ratio design.md states that the tokens do not give is a documentation defect, not a contrast failure: its own
    # dimension, so a typo in the table does not count against the accessibility rule (N-29; batch 10 review S2)
    res.dim("VIS-RATIO-STATED", not wrong, (f"design.md: {checked} stated ratio{'s' if checked != 1 else ''} checked"
                                            if md else "no design.md read")   # 0: no table read
            + (f"; design.md states a ratio the tokens do not give: {wrong}" if wrong else ""))
    res.data["contrast"] = rows
    sizes = sorted({tt.size_px for tt in doc.type_scale})
    res.dim("VIS-TYPE", len(sizes) <= t["max_type_sizes"] and (not sizes or min(sizes) >= t["min_type_px"]),
            f"{len(sizes)} sizes {sizes} (max {t['max_type_sizes']}, min {t['min_type_px']} px)")
    res.dim("VIS-RADII", len(set(doc.radii_px)) <= t["max_radii"], f"{len(set(doc.radii_px))} radii {sorted(set(doc.radii_px))}")
    off = [s for s in doc.spacing_px if s % t["spacing_grid_px"]]
    res.dim("VIS-SPACING", not off, f"spacing {doc.spacing_px}" + (f"; off-grid {off}" if off else ""))
    noprov = [c.name for c in doc.colors if not c.provenance.strip()]
    res.dim("VIS-PROVENANCE", not noprov, f"tokens without provenance: {noprov or 'none'}")
    res.dim("VIS-PROHIBITED", bool(doc.prohibited), f"{len(doc.prohibited)} prohibited patterns")
    alert = [c for c in doc.colors if "alert" in c.role.lower() or "danger" in c.role.lower() or "error" in c.role.lower()]
    reserved = {canonical_colour(a.value) for a in alert}   # any spelling of an alert colour (batch 7 review S3)
    shared = [c.name for c in doc.colors if c not in alert and canonical_colour(c.value) in reserved]
    res.dim("VIS-ALERT-RESERVED", not shared, f"alert colour reused by non-alert tokens: {shared or 'none'}")
    return res
