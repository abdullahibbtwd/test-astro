"""calibrate_scoring.py - CAL_02 §7 calibration gate.

10 real charts (distinct birth dates from runs/*/chart_<date>.json) x 12 months from
2026-09-28, each in its own birth-location tz. The script reports per goal the share
of days per band and the periods per quarter. Only thresholds are tuned: one scale
factor lam multiplies every spec threshold (quiet, mixed_min, normal, strong;
mixed_ratio is a ratio and stays). The spec structure is kept and only the scale moves
to match |A| <= 0.067.

Targets: favorable days 10-25%, challenging 10-25%, quiet >= 40%, ~1-4 periods per
goal per quarter.

    python Calendar/calibrate_scoring.py            # writes Calendar/CAL_CALIBRATION.md
"""

from __future__ import annotations

import glob
import json
import os
import pickle
import re
import sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import build_transit_affinity as BA  # noqa: E402
import cal_constants as K  # noqa: E402
import cal_scoring as S  # noqa: E402
import personal_events as P  # noqa: E402
from acg_constants import GOAL_ORDER  # noqa: E402

FROM = date(2026, 9, 28)
CACHE = os.path.join(ROOT, "cal_run", "_calibration", "scores.pkl")
REPORT = os.path.join(HERE, "CAL_CALIBRATION.md")
LAMBDAS = [round(0.02 * i, 2) for i in range(1, 31)]      # 0.02 .. 0.60


def charts(n: int = 10) -> list[tuple[str, dict]]:
    seen, out = set(), []
    for p in sorted(glob.glob(os.path.join(ROOT, "runs", "*", "chart_*.json"))):
        m = re.search(r"chart_(\d{4}-\d{2}-\d{2})\.json$", p)
        if not m or m.group(1) in seen:
            continue
        with open(p, encoding="utf-8") as fh:
            c = json.load(fh)
        if c.get("confidence") == "unknown":
            continue
        seen.add(m.group(1))
        out.append((m.group(1), c))
        if len(out) == n:
            break
    return out


def compute_all() -> list[dict]:
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    table = BA.load()
    res = []
    for bd, natal in charts():
        tz = natal["meta"]["timezone"]
        ev = P.build_personal_events(natal, tz, FROM)
        sc = S.day_scores(ev, natal, table)
        res.append({"birth": bd, "tz": tz, "events": ev, "scores": sc})
        print(f"  {bd} {tz}: {len(ev['events'])} events", flush=True)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "wb") as fh:
        pickle.dump(res, fh)
    return res


def rebanded(sc: dict, th: dict) -> dict:
    out = {"chart_key": sc["chart_key"], "tz": sc["tz"], "horizon": sc["horizon"], "days": []}
    for d in sc["days"]:
        goals = {g: {**v, "band": S.band(v["P"], v["N"], th)} for g, v in d["goals"].items()}
        out["days"].append({**d, "goals": goals})
    return out


def stats(res: list[dict], th: dict) -> dict:
    band_n = {g: Counter() for g in GOAL_ORDER}
    per_n = {g: 0 for g in GOAL_ORDER}
    ndays = 0
    for r in res:
        sc = rebanded(r["scores"], th)
        ndays += len(sc["days"])
        for d in sc["days"]:
            for g in GOAL_ORDER:
                band_n[g][d["goals"][g]["band"]] += 1
        for p in S.periods(sc, r["events"])["periods"]:
            per_n[p["goal"]] += 1
    out = {}
    for g in GOAL_ORDER:
        b = band_n[g]
        out[g] = {"favorable": (b["supportive"] + b["strongly_supportive"]) / ndays,
                  "challenging": (b["challenging"] + b["strongly_challenging"]) / ndays,
                  "mixed": b["mixed"] / ndays, "quiet": b["quiet"] / ndays,
                  "strong": (b["strongly_supportive"] + b["strongly_challenging"]) / ndays,
                  "periods_per_quarter": per_n[g] / (len(res) * 4)}
    return out


def loss(st: dict) -> float:
    """Distance from the targets, summed over goals (0 = all inside)."""
    def outside(x: float, lo: float, hi: float) -> float:
        return max(0.0, lo - x) + max(0.0, x - hi)
    tot = 0.0
    for v in st.values():
        tot += outside(v["favorable"], 0.10, 0.25) + outside(v["challenging"], 0.10, 0.25)
        tot += outside(v["quiet"], 0.40, 1.0)
        tot += 0.05 * outside(v["periods_per_quarter"], 1.0, 4.0)
    return tot


def scaled(lam: float) -> dict:
    b = K.BAND_SPEC
    return {"quiet": round(b["quiet"] * lam, 6), "mixed_min": round(b["mixed_min"] * lam, 6),
            "mixed_ratio": b["mixed_ratio"], "strong": round(b["strong"] * lam, 6),
            "normal": round(b["normal"] * lam, 6)}


def table_md(st: dict) -> list[str]:
    rows = ["| goal | favorable | challenging | mixed | quiet | strong | periods/quarter | in target |",
            "|---|---|---|---|---|---|---|---|"]
    for g, v in st.items():
        ok = (0.10 <= v["favorable"] <= 0.25 and 0.10 <= v["challenging"] <= 0.25 and v["quiet"] >= 0.40
              and 1.0 <= v["periods_per_quarter"] <= 4.0)
        rows.append(f"| {g} | {v['favorable']:.1%} | {v['challenging']:.1%} | {v['mixed']:.1%} | "
                    f"{v['quiet']:.1%} | {v['strong']:.1%} | {v['periods_per_quarter']:.1f} | {'✅' if ok else '❌'} |")
    return rows


def main() -> None:
    res = compute_all()
    spec_st = stats(res, K.BAND_SPEC)
    sweep = [(loss(stats(res, scaled(lam))), lam) for lam in LAMBDAS]
    best_loss, best = min(sweep)
    best_st = stats(res, scaled(best))
    lines = ["# CAL_02 §7 calibration", "",
             f"*{len(res)} real charts (runs/, distinct birth dates) × 12 months from {FROM}, each in its birth tz. "
             "Only thresholds are tuned: one factor λ scales every spec threshold.*", "",
             "Charts: " + ", ".join(f"{r['birth']} ({r['tz']})" for r in res), "",
             "## Spec thresholds (λ = 1)", "", f"`{K.BAND_SPEC}`", "", *table_md(spec_st), "",
             f"## Proposed: λ = {best}", "", f"`{scaled(best)}`  (loss {best_loss:.3f})", "", *table_md(best_st), "",
             "## Sweep", "", "| λ | loss |", "|---|---|", *[f"| {lam} | {l:.3f} |" for l, lam in sweep], "",
             "Targets: favorable 10–25%, challenging 10–25%, quiet ≥ 40%, 1–4 periods per goal per quarter.",
             "Goals that stay outside the targets at the best λ are sparse in the corpus. "
             "Fix that in tagging or corpus, not in per-goal thresholds (the spec allows one threshold set)."]
    with open(REPORT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"best lambda {best} loss {best_loss:.3f} -> {REPORT}")


if __name__ == "__main__":
    main()
