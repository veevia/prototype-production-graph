#!/usr/bin/env python3
"""Seeded synthetic data for the Lot Release Workbench (fictional companies, materials and certificates).

    python3 data/generate.py --out <dir> [--seed 20260926] [--seed-subset <path>]

Writes <dir>/lots.json and <dir>/content.json (the content document N12 submits). The scenario lots are fixed so the
browser scenarios are stable; every other value is drawn from the seed. Edge cases: out-of-spec, missing-value and
borderline results, and one lot with both (the missing value escalates; it never lowers the tier).
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

SPECS = {
    "MAT-SUC": {"material": "Liquid sucrose 67 °Bx", "parameters": [
        {"id": "brix", "name": "Brix", "unit": "°Bx", "min": 66.5, "max": 67.5, "dp": 1},
        {"id": "color", "name": "Colour", "unit": "ICUMSA", "max": 35, "dp": 0},
        {"id": "ph", "name": "pH", "unit": "", "min": 6.0, "max": 7.5, "dp": 2},
        {"id": "turbidity", "name": "Turbidity", "unit": "NTU", "max": 5, "dp": 1},
        {"id": "yeast", "name": "Yeast and mould", "unit": "CFU/10 g", "max": 10, "dp": 0}]},
    "MAT-CIT": {"material": "Citric acid, anhydrous", "parameters": [
        {"id": "assay", "name": "Assay", "unit": "%", "min": 99.5, "max": 100.5, "dp": 2},
        {"id": "moisture", "name": "Moisture", "unit": "%", "max": 0.5, "dp": 2},
        {"id": "sulfate", "name": "Sulfate", "unit": "mg/kg", "max": 150, "dp": 0},
        {"id": "lead", "name": "Lead", "unit": "mg/kg", "max": 0.5, "dp": 2}]},
    "MAT-LEM": {"material": "Natural lemon flavour", "parameters": [
        {"id": "sg", "name": "Specific gravity (20 °C)", "unit": "", "min": 0.850, "max": 0.870, "dp": 3},
        {"id": "ri", "name": "Refractive index (20 °C)", "unit": "", "min": 1.470, "max": 1.480, "dp": 4},
        {"id": "ethanol", "name": "Ethanol", "unit": "% v/v", "min": 30, "max": 40, "dp": 1}]},
    "MAT-ASC": {"material": "Ascorbic acid", "parameters": [
        {"id": "assay", "name": "Assay", "unit": "%", "min": 99.0, "max": 100.5, "dp": 2},
        {"id": "lod", "name": "Loss on drying", "unit": "%", "max": 0.4, "dp": 2},
        {"id": "ph", "name": "pH (5 % solution)", "unit": "", "min": 2.1, "max": 2.6, "dp": 2}]},
    "MAT-CO2": {"material": "Carbon dioxide, beverage grade", "parameters": [
        {"id": "purity", "name": "Purity", "unit": "% v/v", "min": 99.9, "borderline_margin": 0.02, "dp": 2},
        {"id": "moisture", "name": "Moisture", "unit": "ppm v/v", "max": 20, "dp": 0},
        {"id": "acetaldehyde", "name": "Acetaldehyde", "unit": "ppm v/v", "max": 0.2, "dp": 2},
        {"id": "sulfur", "name": "Total sulfur", "unit": "ppm v/v", "max": 0.1, "dp": 2}]},
    "MAT-ORC": {"material": "Orange juice concentrate 65 °Bx", "parameters": [
        {"id": "brix", "name": "Brix", "unit": "°Bx", "min": 64.5, "max": 65.5, "dp": 1},
        {"id": "acidity", "name": "Acidity (as citric)", "unit": "%", "min": 3.0, "max": 4.0, "dp": 2},
        {"id": "pulp", "name": "Sinking pulp", "unit": "%", "max": 12, "dp": 1}]},
}
SUPPLIERS = [
    {"id": "SUP-NWS", "name": "Northwind Sweeteners", "contact": "quality@northwind-sweeteners.example"},
    {"id": "SUP-CTC", "name": "Contoso Citrus", "contact": "coa-desk@contoso-citrus.example"},
    {"id": "SUP-ADF", "name": "Adatum Flavors", "contact": "qa@adatum-flavors.example"},
    {"id": "SUP-TSG", "name": "Tailspin Gases", "contact": "quality@tailspin-gases.example"},
    {"id": "SUP-LWC", "name": "Litware Chemicals", "contact": "coa@litware-chemicals.example"},
]
SUPPLIER_OF = {"MAT-SUC": "SUP-NWS", "MAT-CIT": "SUP-LWC", "MAT-LEM": "SUP-ADF", "MAT-ASC": "SUP-LWC",
               "MAT-CO2": "SUP-TSG", "MAT-ORC": "SUP-CTC"}
# lot id, material, edge case, overrides {param: value | None}, received offset (days from 2026-09-18)
PLAN = [
    ("L-2418", "MAT-SUC", "within", {"brix": 67.0, "color": 22, "ph": 6.8, "turbidity": 2.1, "yeast": 3}, 3),
    ("L-2421", "MAT-CIT", "within", {}, 0),
    ("L-2424", "MAT-LEM", "borderline", {"ethanol": 39.4}, 1),
    ("L-2426", "MAT-CO2", "within", {}, 1),
    ("L-2429", "MAT-ASC", "within", {}, 2),
    ("L-2431", "MAT-SUC", "out-of-spec", {"brix": 67.9}, 4),
    ("L-2433", "MAT-ORC", "borderline", {"brix": 65.42}, 4),
    ("L-2435", "MAT-CIT", "out-of-spec", {"lead": 0.71}, 5),
    ("L-2437", "MAT-LEM", "missing-value", {"sg": None}, 5),
    ("L-2439", "MAT-CO2", "within", {}, 5),
    ("L-2440", "MAT-SUC", "within", {}, 6),
    ("L-2442", "MAT-ORC", "within", {}, 6),
    ("L-2444", "MAT-ASC", "borderline", {"lod": 0.38}, 6),
    ("L-2446", "MAT-CIT", "within", {}, 7),
    ("L-2448", "MAT-SUC", "out-of-spec+missing-value", {"brix": 68.1, "color": None}, 7),
    ("L-2450", "MAT-LEM", "within", {}, 7),
]
# Decisions recorded on the previous shift (lots no longer in the queue), so the decision log is never empty on arrival.
HISTORY = [
    {"lot": "L-2396", "material": "MAT-SUC", "decision": "release", "verdict": "ready", "verdictLabel": "Ready to release",
     "rationale": "", "by": "Sam Rivera", "at": "2026-09-17T14:22:00"},
    {"lot": "L-2402", "material": "MAT-CIT", "decision": "hold", "verdict": "hold", "verdictLabel": "Hold",
     "rationale": "Lead at 0.62 mg/kg against a 0.5 mg/kg maximum. Held for a retest from Litware; the QA lead sent the notice to "
                  "their certificate desk. Keep it out of the citrus line until the retest clears.",
     "by": "Morgan Lee", "at": "2026-09-17T16:05:00"},
    {"lot": "L-2405", "material": "MAT-LEM", "decision": "reject", "verdict": "escalate", "verdictLabel": "Escalate to QA lead",
     "rationale": "Second certificate in a row with an unreadable specific gravity; supplier asked to re-issue and retest.",
     "by": "Sam Rivera", "at": "2026-09-17T17:40:00"},
]
NOTES = {("L-2437", "sg"): "Value unreadable on the supplier's scanned certificate",
         ("L-2448", "color"): "Colour field left blank on the certificate"}


def within_value(rng: random.Random, p: dict) -> float:
    lo, hi = p.get("min"), p.get("max")
    if lo is not None and hi is not None:
        span = hi - lo
        v = rng.uniform(lo + 0.25 * span, hi - 0.25 * span)
    elif hi is not None:
        v = rng.uniform(0.2 * hi, 0.6 * hi)
    else:
        v = lo + rng.uniform(0.03, 0.06)
    return round(v, p["dp"])


def build(seed: int, subset: list[str] | None = None) -> dict:
    rng = random.Random(seed)
    lots = []
    for n, (lid, mat, edge, over, offset) in enumerate(PLAN):
        spec = SPECS[mat]
        results = {p["id"]: within_value(rng, p) for p in spec["parameters"]}
        results.update(over)
        received = date(2026, 9, 18) + timedelta(days=offset)
        lot = {"id": lid, "material": mat, "supplier": SUPPLIER_OF[mat], "received": received.isoformat(),
               "due": (received + timedelta(days=1)).isoformat(), "po": f"PO-{771200 + 7 * n}", "coa": f"CoA-{5500 + 3 * n}",
               "edge_case": edge, "results": results,
               "notes": {k[1]: v for k, v in NOTES.items() if k[0] == lid}}
        if subset is None or lid in subset:
            lots.append(lot)
    specs = {k: {"material": v["material"], "parameters": [{kk: vv for kk, vv in p.items() if kk != "dp"} for p in v["parameters"]]}
             for k, v in SPECS.items()}
    return {"generated": {"generator": "data/generate.py", "seed": seed, "provenance": "synthetic",
                          "note": "Fictional companies, materials and certificates for design review only."},
            "specs": specs, "suppliers": SUPPLIERS, "lots": lots, "history": HISTORY}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20260926)
    ap.add_argument("--seed-subset", help="write only the three scenario lots to this path (the build's seed data)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if a.seed_subset:
        Path(a.seed_subset).write_text(json.dumps(build(a.seed, ["L-2418", "L-2431", "L-2437"]), indent=1, ensure_ascii=False) + "\n")
    data = build(a.seed)
    (out / "lots.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    content = {"datasets": [{"path": "data/lots.json", "records": len(data["lots"]), "provenance": "synthetic",
                             "generator": "data/generate.py", "seed": a.seed, "label_shown_in_ui": True}],
               "copy_deck": "content/copy-deck.md",
               "edge_cases": ["out-of-spec", "missing-value", "borderline", "out-of-spec+missing-value"]}
    (out / "content.json").write_text(json.dumps(content, indent=1) + "\n")
    print(f"wrote {len(data['lots'])} lots (seed {a.seed}) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
