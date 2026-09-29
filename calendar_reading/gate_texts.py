"""gate_texts.py - CAL_03 gate run: 1 real chart x 3 months of texts.

    python calendar_reading/gate_texts.py [--from 2026-09-28] [--months 3]
Writes cal_run/_gate/texts_{tr,en}.json + gate_report.json.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, os.path.join(ROOT, "Calendar"), os.path.join(ROOT, "d_layer")):
    sys.path.insert(0, p)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import build_transit_affinity as BA  # noqa: E402
import cal_corpus  # noqa: E402
import cal_scoring as S  # noqa: E402
import collective_events as C  # noqa: E402
import cr_generate as G  # noqa: E402
import cr_render as R  # noqa: E402
import cr_sections as CS  # noqa: E402
import personal_events as P  # noqa: E402
from compute_chart import BirthData, compute_chart  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2026-09-28")
    ap.add_argument("--months", type=int, default=3)
    args = ap.parse_args()
    start = date.fromisoformat(args.start)
    end = P.add_months(start, args.months)
    idx, modern = cal_corpus.load()
    with open(BA.TAGS, encoding="utf-8") as fh:
        tags = json.load(fh)
    natal = compute_chart(BirthData(year=1979, month=3, day=30, hour=6, minute=30,
                                    latitude=42.6977, longitude=23.3219))
    ev = P.build_personal_events(natal, "Europe/Sofia", start)
    per = S.periods(S.day_scores(ev, natal, BA.load()), ev)
    first, last, jd0, jd1 = P.horizon(start, "Europe/Sofia")
    coll = {c["id"]: c for c in C.load_range(jd0, jd1)}
    units = CS.plan_units(ev, per, ev["collective_refs"], coll, idx, modern, tags)
    sel = {u["unit_id"]: u for u in units.values()
           if CS.overlaps(u["span"], start, end - __import__("datetime").timedelta(days=1))}
    store = G.TextStore(os.path.join(C.COLLECTIVE_DIR, "texts.json"),
                        os.path.join(ROOT, "cal_run", "_cache", ev["chart_key"], "texts.json"))
    gen = G.make_generator()
    sha = cal_corpus.corpus_sha()
    stats = G.ensure_texts(list(sel.values()), store, gen, sha, ev["chart_key"])
    out = os.path.join(ROOT, "cal_run", "_gate")
    R.write_texts(out, sel, store, sha, ev["chart_key"])
    rep = {"window": [start.isoformat(), end.isoformat()], "units": len(sel),
           "with_text": sum(1 for u in sel.values() if u["text"]), "stats": stats,
           "gaps": G.gaps(sel), "usage": gen.usage}
    with open(os.path.join(out, "gate_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print(json.dumps({k: rep[k] for k in ("units", "with_text", "stats", "usage")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
