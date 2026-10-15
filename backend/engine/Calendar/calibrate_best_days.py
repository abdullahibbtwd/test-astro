"""calibrate_best_days.py - CAL_04 §6 calibration gate.

10 real charts (the same set as calibrate_scoring.py) x 90 days x 10 activities.
The script reports each grade's share per activity. Only the grade thresholds are tuned
(weights need Radul's sign-off). Targets: excellent 3-10%, good 10-25%, avoid 10-25%.

    python Calendar/calibrate_best_days.py        # writes Calendar/CAL_BEST_DAYS_CALIBRATION.md
"""

from __future__ import annotations

import itertools
import os
import pickle
import sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import best_days as B  # noqa: E402
from calibrate_scoring import charts  # noqa: E402

FROM = date(2026, 9, 28)
CACHE = os.path.join(ROOT, "cal_run", "_calibration", "best_days.pkl")
REPORT = os.path.join(HERE, "CAL_BEST_DAYS_CALIBRATION.md")


def collect() -> list[dict]:
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    rows = []
    for bd, natal in charts():
        doc = B.build_best_days(natal, natal["meta"]["timezone"], FROM)
        for act, v in doc["activities"].items():
            for d in v["days"]:
                gates = []   # all gates are on disabled C-factors in v1
                rows.append({"chart": bd, "act": act, "R": d["R"], "gates": gates})
        print(f"  {bd}", flush=True)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "wb") as fh:
        pickle.dump(rows, fh)
    return rows


def shares(rows: list[dict], th: dict) -> dict:
    out = {}
    for act in B.ACTIVITY_ORDER:
        rs = [r for r in rows if r["act"] == act]
        c = Counter(B.grade(r["R"], r["gates"], th) for r in rs)
        out[act] = {g: c[g] / len(rs) for g in ("excellent", "good", "neutral", "avoid")}
    return out


def loss(sh: dict) -> float:
    def outside(x, lo, hi):
        return max(0.0, lo - x) + max(0.0, x - hi)
    return sum(outside(v["excellent"], 0.03, 0.10) + outside(v["good"], 0.10, 0.25)
               + outside(v["avoid"], 0.10, 0.25) for v in sh.values())


def table(sh: dict) -> list[str]:
    rows = ["| activity | excellent | good | neutral | avoid | in target |", "|---|---|---|---|---|---|"]
    for a, v in sh.items():
        ok = 0.03 <= v["excellent"] <= 0.10 and 0.10 <= v["good"] <= 0.25 and 0.10 <= v["avoid"] <= 0.25
        rows.append(f"| {a} | {v['excellent']:.1%} | {v['good']:.1%} | {v['neutral']:.1%} | {v['avoid']:.1%} | {'✅' if ok else '❌'} |")
    return rows


def main() -> None:
    rows = collect()
    spec = shares(rows, B.GRADE_TH)
    grid = [x / 20 for x in range(1, 61)]                   # 0.05 .. 3.0
    best = None
    for g, e, a in itertools.product(grid, grid, [-x for x in grid]):
        if e <= g:
            continue
        th = {"excellent": e, "good": g, "avoid": a}
        l_ = loss(shares(rows, th)) if best is None or True else 0
        if best is None or l_ < best[0] - 1e-12:
            best = (l_, th)
    l_, th = best
    sh = shares(rows, th)
    lines = ["# CAL_04 §6 Best Days calibration", "",
             f"*10 real charts × 90 days from {FROM} × 10 activities; C-factors disabled (Q4), so no hard gates. "
             "Only grade thresholds tuned; weights unchanged.*", "",
             "## Spec thresholds", "", f"`{B.GRADE_TH}`", "", *table(spec), "",
             f"## Proposed thresholds (loss {l_:.3f})", "", f"`{th}`", "", *table(sh), "",
             "Targets: excellent 3–10%, good 10–25%, avoid 10–25%."]
    with open(REPORT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(th, round(l_, 3))


if __name__ == "__main__":
    main()
