"""build_transit_affinity.py - transit x goal affinity table (CAL_02 §3).

Key: directed (T, a, N) - transiting body, aspect, natal point (Phase 0: the Hand
records are per exact aspect, not per family). Formula = ACG_08 §2:

    s, c, m = Σ w_r over records r of the cell tagged supportive / challenging / mixed for g
    s' = s + 0.5 m      c' = c + 0.5 m
    net = (s' - c') / (s' + c' + K)          K = 2
    A   = net · min(1, (s' + c') / V0)       V0 = 5

Record weight (decision Q2): w_r = 1 / n_cell, so the two extractions of Hand's book
count as one source per cell. No record carries citation_count (Phase 0 F10).

    python Calendar/build_transit_affinity.py
      -> principles_grounding/cal_transit_affinity.json
      -> principles_grounding/cal_transit_affinity_review.md
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, os.path.join(ROOT, "Astrocartography")):
    if p not in sys.path:
        sys.path.insert(0, p)

import cal_constants as K  # noqa: E402
import cal_corpus  # noqa: E402
from acg_constants import GOAL_ORDER  # noqa: E402

PG = os.path.join(ROOT, "principles_grounding")
TAGS = os.path.join(PG, "transit_goal_tags.json")
OUT = os.path.join(PG, "cal_transit_affinity.json")
REVIEW = os.path.join(PG, "cal_transit_affinity_review.md")
SCHEMA = "cal-affinity-1"
KK = 2.0
V0 = 5.0


def cell_value(s: float, c: float, m: float) -> dict:
    sp, cp = s + 0.5 * m, c + 0.5 * m
    vol = sp + cp
    net = (sp - cp) / (sp + cp + KK)
    return {"A": round(net * min(1.0, vol / V0), 6), "s": round(s, 6), "c": round(c, 6),
            "m": round(m, 6), "volume": round(vol, 6)}


def cell_key(t: str, a: str, n: str) -> str:
    return f"{t}|{a}|{n}"


def build(index: dict, tags: dict) -> dict:
    cells: dict = {}
    for (t, a, n), ids in index["transits"].items():
        if t == "moon":
            continue            # the Moon is not a calendar transit (CAL_01 §1)
        w = 1.0 / len(ids)
        per_goal = {}
        for g in GOAL_ORDER:
            s = c = m = 0.0
            contrib = []
            for i in ids:
                pol = tags.get(i, {}).get(g)
                if pol is None:
                    continue
                contrib.append(i)
                if pol == "supportive":
                    s += w
                elif pol == "challenging":
                    c += w
                else:
                    m += w
            if contrib:
                per_goal[g] = {**cell_value(s, c, m), "contributors": sorted(contrib)}
        cells[cell_key(t, a, n)] = {"records": sorted(ids), "goals": per_goal}
    return cells


def lookup(table: dict, t: str, a: str, n: str, g: str) -> float:
    cell = table["cells"].get(cell_key(t, a, n))
    if not cell:
        return 0.0
    return cell["goals"].get(g, {}).get("A", 0.0)


def load(path: str = OUT) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# --- review ------------------------------------------------------------------------------
EXPECT = [  # (T, a, N, goal, sign) - CAL_02 §3 examples + obvious ones
    ("jupiter", "trine", "sun", "career", +1), ("jupiter", "trine", "sun", "money", +1),
    ("saturn", "square", "moon", "family", -1), ("saturn", "square", "moon", "rest", -1),
    ("venus", "conjunction", "venus", "love", +1), ("saturn", "opposition", "venus", "love", -1),
    ("jupiter", "conjunction", "mc", "career", +1), ("saturn", "square", "mc", "career", -1),
    ("neptune", "square", "sun", "rest", -1), ("jupiter", "trine", "moon", "family", +1),
]


def review_md(table: dict) -> str:
    cells = table["cells"]
    lines = ["# CAL transit affinity: review (CAL_02 §3 gate)", "",
             f"*schema {SCHEMA}; corpus sha {table['corpus_sha256'][:12]}; tags sha {table['tags_sha256'][:12]}.*",
             "", "A ∈ [−1, 1] per (transiting T, aspect, natal N, goal). Record weight = 1/n per cell, so the book counts once.",
             f"With one source book, volume ≤ 1 < V0 = {V0}, so **|A| ≤ 0.067 by construction**. The day-score band "
             "thresholds are calibrated to that scale (CAL_02 §7); only the sign and relative size matter.", "",
             "## 1. Expectation checks", "", "| T | aspect | N | goal | expected | A | contributors | ok |", "|---|---|---|---|---|---|---|---|"]
    bad = 0
    for t, a, n, g, sg in EXPECT:
        v = lookup(table, t, a, n, g)
        contrib = cells.get(cell_key(t, a, n), {}).get("goals", {}).get(g, {}).get("contributors", [])
        ok = (v > 0) if sg > 0 else (v < 0)
        bad += not ok
        lines.append(f"| {t} | {a} | {n} | {g} | {'+' if sg > 0 else '−'} | {v:+.4f} | {', '.join(contrib) or '—'} | {'✅' if ok else '❌'} |")
    lines += ["", f"{len(EXPECT) - bad}/{len(EXPECT)} expectations hold. A failure is fixed in the tagging, never the numbers.", ""]
    n_cells = len(cells)
    empty = sorted(k for k, v in cells.items() if not v["goals"])
    lines += ["## 2. Coverage", "", f"- cells: {n_cells} (T = Sun…Pluto × 5 aspects × 12 natal points = 540 possible)",
              f"- cells with no goal at all: {len(empty)}" + (f" ({', '.join(empty[:20])}{' …' if len(empty) > 20 else ''})" if empty else ""),
              ""]
    lines += ["| goal | cells + | cells − | cells mixed/0 |", "|---|---|---|---|"]
    for g in GOAL_ORDER:
        vals = [v["goals"][g]["A"] for v in cells.values() if g in v["goals"]]
        lines.append(f"| {g} | {sum(1 for x in vals if x > 0)} | {sum(1 for x in vals if x < 0)} | {sum(1 for x in vals if x == 0)} |")
    lines += ["", "## 3. Strongest cells per goal", ""]
    for g in GOAL_ORDER:
        ranked = sorted(((v["goals"][g]["A"], k) for k, v in cells.items() if g in v["goals"]), reverse=True)
        top = [f"{k.replace('|', ' ')} {a:+.3f}" for a, k in ranked[:6] if a > 0]
        low = [f"{k.replace('|', ' ')} {a:+.3f}" for a, k in ranked[::-1][:6] if a < 0]
        lines += [f"**{g}**: most supportive: {'; '.join(top) or '—'}", "",
                  f"most challenging: {'; '.join(low) or '—'}", ""]
    return "\n".join(lines) + "\n"


def main() -> None:
    idx, _ = cal_corpus.load()
    with open(TAGS, encoding="utf-8") as fh:
        tags_raw = fh.read()
    tags = json.loads(tags_raw)
    table = {"schema_version": SCHEMA,
             "corpus_sha256": cal_corpus.corpus_sha(),
             "tags_sha256": hashlib.sha256(tags_raw.encode("utf-8")).hexdigest(),
             "constants": {"K": KK, "V0": V0, "record_weight": "1/n_cell"},
             "cells": build(idx, tags)}
    payload = json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
    with open(REVIEW, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(review_md(table))
    print(f"{len(table['cells'])} cells -> {OUT}\nreview -> {REVIEW}")


if __name__ == "__main__":
    main()
