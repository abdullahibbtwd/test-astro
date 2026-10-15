#!/usr/bin/env python3
"""calibrate_bands.py — ACG spec 08 §4 calibration report.

For N charts × the full gazetteer, reports the share of each band per goal against
the targets (strongly_supportive 2–8%, no_emphasis 40–75%). It never changes any
constant: the gate is Radul's, and per the spec only the band thresholds may move.

    python Astrocartography/calibrate_bands.py                   # 20 synthetic charts
    python Astrocartography/calibrate_bands.py --charts charts.json
        charts.json: [{"year":..,"month":..,"day":..,"hour":..,"minute":..,
                       "latitude":..,"longitude":..}, ...]   (real charts; stays local)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, os.path.join(_ROOT, "d_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import acg_constants as C  # noqa: E402
import acg_geodata as geo  # noqa: E402
import acg_goals as ag  # noqa: E402
import compute_acg as ca  # noqa: E402
import compute_parans as cp  # noqa: E402

TARGET_STRONG = (0.02, 0.08)
TARGET_NONE = (0.40, 0.75)
BIRTHPLACES = [(41.0082, 28.9784), (39.9334, 32.8597), (38.4237, 27.1428),
               (37.0, 35.3213), (40.1885, 29.061), (52.52, 13.405)]


def synthetic_charts(n: int, seed: int = 20260925) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        lat, lon = rng.choice(BIRTHPLACES)
        out.append({"year": rng.randint(1960, 2005), "month": rng.randint(1, 12),
                    "day": rng.randint(1, 28), "hour": rng.randint(0, 23),
                    "minute": rng.randint(0, 59), "latitude": lat, "longitude": lon})
    return out


def band_shares(charts: list[dict], thresholds: dict | None = None,
                with_parans: bool = True) -> dict:
    from compute_chart import BirthData, compute_chart
    aff = ag.load_affinity()
    cities = geo.load_cities()
    counts = {g: Counter() for g in ag.GOAL_ORDER}
    saved = {k: getattr(C, k) for k in thresholds or {}}
    try:
        for k, v in (thresholds or {}).items():
            setattr(ag, k, v)
        for ch in charts:
            natal = compute_chart(BirthData(time_precision="exact", **ch))
            acg = ca.compute_acg(natal)
            parans = cp.compute_parans(acg) if with_parans else None
            scan = ag.goal_scan(acg, aff, cities, None, parans)
            for gi, g in enumerate(ag.GOAL_ORDER):
                codes = ag.band_codes_np(scan["city_P"][:, gi].astype(float),
                                         scan["city_N"][:, gi].astype(float))
                counts[g].update(ag._BAND_CODES[c] for c in codes)
    finally:
        for k, v in saved.items():
            setattr(ag, k, v)
    total = len(charts) * len(cities)
    return {g: {b: counts[g][b] / total for b in C.BANDS} for g in ag.GOAL_ORDER}


def report(shares: dict, n_charts: int, source: str) -> str:
    lines = [f"# ACG band calibration ({source}, {n_charts} charts × {len(geo.load_cities())} cities, "
             f"lines + parans, W_PARAN={C.W_PARAN})",
             "", f"Thresholds: no_emphasis P+N < {C.BAND_NO_EMPHASIS_PN}; mixed max ≥ "
             f"{C.BAND_MIXED_MIN} & min ≥ {C.BAND_MIXED_RATIO}·max; strongly S ≥ {C.BAND_STRONG}; "
             f"supportive/challenging |S| ≥ {C.BAND_SUPPORTIVE}.",
             f"Targets: strongly_supportive {TARGET_STRONG[0]:.0%}–{TARGET_STRONG[1]:.0%}, "
             f"no_emphasis {TARGET_NONE[0]:.0%}–{TARGET_NONE[1]:.0%}.", "",
             "| goal | strongly | supportive | mixed | challenging | no_emphasis | on target |",
             "|---|---:|---:|---:|---:|---:|---|"]
    for g, s in shares.items():
        ok_s = TARGET_STRONG[0] <= s["strongly_supportive"] <= TARGET_STRONG[1]
        ok_n = TARGET_NONE[0] <= s["no_emphasis"] <= TARGET_NONE[1]
        lines.append(f"| {g} | {s['strongly_supportive']:.1%} | {s['supportive']:.1%} | "
                     f"{s['mixed']:.1%} | {s['challenging']:.1%} | {s['no_emphasis']:.1%} | "
                     f"{'yes' if ok_s and ok_n else ('strong ✗' if not ok_s else '') + (' none ✗' if not ok_n else '')} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="ACG band calibration report (08 §4).")
    ap.add_argument("--charts", help="JSON list of real charts (kept local)")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--out", default=os.path.join(_HERE, "calibration_report.md"))
    args = ap.parse_args()
    if args.charts:
        with open(args.charts, encoding="utf-8") as fh:
            charts, source = json.load(fh), "real charts"
    else:
        charts, source = synthetic_charts(args.n), "synthetic charts"
    text = report(band_shares(charts), len(charts), source)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
