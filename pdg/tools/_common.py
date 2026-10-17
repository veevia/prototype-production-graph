"""Shared helpers for the deterministic tools."""

from __future__ import annotations

import math
import re
from typing import Any

PLACEHOLDER = re.compile(r"\b(lorem|ipsum|TODO|TBD|FIXME|xxx+|placeholder text|sample text)\b", re.I)
HEX = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")


def sentences(text: str) -> int:
    parts = [p for p in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9“\"'])", text.strip()) if p.strip()]
    return len(parts)


def words(text: str) -> int:
    return len(text.split())


def finding(dim: str, message: str, severity: str = "P3", location: str = "", traced_node: str | None = None,
            smallest_fix: str = "", acceptance_check: str = "", evidence: str = "") -> dict[str, Any]:
    return {"dimension": dim, "message": message, "severity": severity, "location": location, "traced_node": traced_node,
            "smallest_fix": smallest_fix, "acceptance_check": acceptance_check, "evidence": evidence, "by": "tool"}


def hex_to_rgb(value: str) -> tuple[float, float, float]:
    v = value.lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return tuple(int(v[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(rgb: tuple[float, float, float]) -> float:
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    """WCAG 2.x contrast ratio of two #rrggbb colours."""
    a, b = luminance(hex_to_rgb(fg)), luminance(hex_to_rgb(bg))
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def strip_attr_placeholders(html: str) -> str:
    """Remove placeholder="…" and aria/title attributes before scanning visible text for placeholder words."""
    return re.sub(r'\s(placeholder|aria-[a-z]+|title|data-[a-z-]+)="[^"]*"', "", html)


_COLOUR_FN = re.compile(r"^\s*(rgba?|hsla?)\s*\((.*)\)\s*$", re.I)
_HUE_UNIT = {"deg": 1.0, "grad": 0.9, "rad": 180 / math.pi, "turn": 360.0, "": 1.0}


def _half_up(x: float) -> int:
    """CSS rounds a channel half up (76.5 → 77); Python's round() rounds half to even."""
    return int(math.floor(x + 0.5 + 1e-9))


def _alpha8(a: float) -> int:
    return _half_up(max(0.0, min(1.0, a)) * 255)


def parse_colour(value: str) -> tuple[int, int, int, float] | None:
    """(r, g, b, alpha) as a browser computes them, for a CSS colour written as hex (#rgb, #rgba, #rrggbb, #rrggbbaa),
    rgb()/rgba() or hsl()/hsla(): commas or spaces, a `/` alpha, percentages, hue units, `none`. None for anything
    else (a name, a var())."""
    v = value.strip().lower()
    if v == "transparent":
        return 0, 0, 0, 0.0
    if v.startswith("#"):
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        if len(h) not in (6, 8) or any(ch not in "0123456789abcdef" for ch in h):
            return None
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a
    m = _COLOUR_FN.match(v)
    if not m:
        return None
    args = [x for x in re.split(r"[\s,/]+", m.group(2).strip()) if x]
    if len(args) not in (3, 4):
        return None

    def num(tok: str, percent_of: float) -> float:   # `none` is 0; a percentage is a share of percent_of
        return 0.0 if tok == "none" else float(tok[:-1]) * percent_of / 100 if tok.endswith("%") else float(tok)
    try:
        alpha = num(args[3], 1) if len(args) == 4 else 1.0
        if m.group(1).startswith("rgb"):
            r, g, b = (num(x, 255) for x in args[:3])
        else:
            unit = re.search(r"[a-z]*$", args[0]).group(0)
            hue = (0.0 if args[0] == "none" else float(args[0][:len(args[0]) - len(unit)]) * _HUE_UNIT[unit]) % 360
            # saturation and lightness: `50%` or, in CSS Color 4's space syntax, the bare number `50`
            sat, light = (max(0.0, min(1.0, num(x if x.endswith("%") or x == "none" else x + "%", 1))) for x in args[1:3])
            k_a = sat * min(light, 1 - light)

            def f(n: int) -> float:   # CSS Color 4's hslToRgb
                k = (n + hue / 30) % 12
                return light - k_a * max(-1.0, min(k - 3, 9 - k, 1.0))
            r, g, b = (f(n) * 255 for n in (0, 8, 4))
    except (ValueError, KeyError):
        return None
    clamp = lambda x: max(0, min(255, _half_up(x)))  # noqa: E731
    return clamp(r), clamp(g), clamp(b), max(0.0, min(1.0, alpha))


def canonical_colour(value: str) -> str:
    """One spelling per colour, as a browser computes it: opaque as #RRGGBB, translucent as rgba(r,g,b,a) with the 8-bit
    alpha written in the fewest decimals that round-trip, as CSS serialises it (field run 2, R2-16:
    `rgb(255 255 255 / 40%)`, `rgba(255,255,255,.4)` and `#FFFFFF66` are one colour; `#00000080` is `rgba(0,0,0,0.5)`)."""
    c = parse_colour(value)
    if c is None:
        return re.sub(r"\s+", " ", value.strip().lower())
    r, g, b, a = c
    a8 = _alpha8(a)
    if a8 == 255:
        return f"#{r:02X}{g:02X}{b:02X}"
    short = round(a8 / 255, 2)
    alpha = short if _alpha8(short) == a8 else round(a8 / 255, 3)
    return f"rgba({r},{g},{b},{alpha:g})"

