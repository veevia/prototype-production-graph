#!/usr/bin/env python3
"""Generate deterministic, domain-free records for technical workflow checks."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def build(seed: int, subset: list[str] | None = None) -> dict:
    rng = random.Random(seed)
    parameters = [
        {"id": "field_a", "name": "Field A", "unit": "", "min": 0, "max": 10},
        {"id": "field_b", "name": "Field B", "unit": "", "min": 0, "max": 10},
        {"id": "field_c", "name": "Field C", "unit": "", "min": 0, "max": 10},
        {"id": "field_d", "name": "Field D", "unit": "", "min": 0, "max": 10},
        {"id": "field_e", "name": "Field E", "unit": "", "min": 0, "max": 10},
    ]
    records = []
    for i in range(1, 17):
        ident = f"R-{i:03}"
        values = {p["id"]: round(rng.uniform(3, 7), 2) for p in parameters}
        edge = "within"
        if i in (2, 9):
            values["field_a"], edge = 12, "out-of-range"
        elif i == 3:
            values["field_a"], edge = None, "missing-value"
        elif i in (5, 8, 13):
            values["field_a"], edge = 9.5, "borderline"
        elif i == 15:
            values["field_a"], values["field_b"], edge = 12, None, "out-of-range+missing-value"
        if subset is None or ident in subset:
            records.append({
                "id": ident, "group": "TEST", "source": "SOURCE",
                "received": "2000-01-01", "due": "2000-01-02",
                "ref": f"REF-{i:03}", "input": f"INPUT-{i:03}",
                "edge_case": edge, "results": values, "notes": {},
            })
    return {
        "generated": {"generator": "data/generate.py", "seed": seed, "provenance": "synthetic",
                      "note": "Generated technical records, not project data or user evidence."},
        "specs": {"TEST": {"group": "Test group", "parameters": parameters}},
        "sources": [{"id": "SOURCE", "name": "Test source", "contact": "test@example.invalid"}],
        "records": records,
        "history": [{"record": f"H-{i:03}", "group": "TEST", "decision": "hold", "verdict": "hold",
                     "verdictLabel": "Hold", "rationale": "Generated historical test event.",
                     "by": "Test actor", "at": f"2000-01-01T00:0{i}:00"} for i in range(1, 4)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    dataset = out / "records.json"
    dataset.write_text(json.dumps(build(args.seed), indent=1) + "\n")
    content = {
        "datasets": [{"path": "data/records.json", "records": 16, "provenance": "synthetic",
                      "label_shown_in_ui": True, "primary": "records"}],
        "copy_deck": "content/copy-deck.md",
        "edge_cases": ["within", "borderline", "out-of-range", "missing-value", "out-of-range+missing-value"],
    }
    (out / "content.json").write_text(json.dumps(content, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
