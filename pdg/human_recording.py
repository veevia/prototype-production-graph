"""Shared guardrails for human-recorded commands."""

from __future__ import annotations

import re
from typing import Any

from .engine_common import EngineError

PLACEHOLDER_RE = re.compile(r"^\s*(?:['\"]?\s*(?:<[^>]+>|…|\\.\\.\\.|Wei's words)[^'\"]*['\"]?)\s*$", re.I)


def validate_human_words(value: str, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise EngineError(f"{field} is required")
    if PLACEHOLDER_RE.fullmatch(text):
        raise EngineError(f"{field} is still a template placeholder; type your own words")
    return text


def recording(actor: str, recorded_by: str | None, source: str = "") -> dict[str, Any]:
    by = (recorded_by or "").strip()
    src = (source or "").strip()
    if recorded_by is not None and by.startswith("agent:") and not src:
        raise EngineError("--source is required when --recorded-by is an agent")
    if source and PLACEHOLDER_RE.fullmatch(src):
        raise EngineError("--source is still a template placeholder; quote the human's actual words")
    return {"recorded_by": by, "source": src}


def stamp(rec: dict[str, Any], interprets: bool = False) -> dict[str, Any]:
    return {**rec, "interprets": interprets}
