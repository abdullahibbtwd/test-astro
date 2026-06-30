"""score_report.py — L5 readback: filled scoresheet -> tuning report.

Standalone, run by hand AFTER a human fills the `score` column of
``scoresheet.csv`` (EVAL_HARNESS_SPEC.md §6, §8). This cannot be a stage of
``run.py`` because the scores don't exist at run time.

    python score_report.py runs/<id>/scoresheet.csv [--json report.json] [--n 10]

It prints, and optionally dumps as JSON:

  * overall mean + count (comparable to the earlier 7.42 baseline);
  * per-category mean, worst first;
  * the lowest-N statements, with category / frequency / sources / principle_ids;
  * CORRELATED MISSES — statements with frequency >= 2 AND score <= 4, the prime
    suspects for a single mis-grounded principle reinjected across sections. This
    flag is the readout the whole harness exists to produce.

Scores are SELF-RATED truthfulness (resonance) — a tuning signal, not
ground-truth accuracy. The report wording keeps that caveat in view.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys

# frequency >= 2 AND score <= 4 => correlated miss (§6.3). Both thresholds named
# here so the failure-mode definition lives in one place.
_CORRELATED_FREQ = 2
_CORRELATED_MAX_SCORE = 4


def _read_rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _parse_score(raw: str):
    """Return an int 0–10, or None if the cell is blank / unparseable."""
    if raw is None:
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        v = int(float(s))   # tolerate "8" or "8.0"
    except ValueError:
        return None
    return v


def _mean(xs: list[int]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def analyse(rows: list[dict], *, lowest_n: int = 10) -> dict:
    scored: list[dict] = []
    skipped = 0
    for r in rows:
        score = _parse_score(r.get("score", ""))
        if score is None:
            skipped += 1
            continue
        try:
            freq = int(float((r.get("frequency") or "1").strip() or 1))
        except ValueError:
            freq = 1
        scored.append({
            "id": (r.get("id") or "").strip(),
            "statement": (r.get("statement") or "").strip(),
            "category": (r.get("category") or "other").strip(),
            "source_sections": (r.get("source_sections") or "").strip(),
            "frequency": freq,
            "score": score,
            "comment": (r.get("comment") or "").strip(),
        })

    all_scores = [s["score"] for s in scored]

    # per-category means, sorted ascending (worst first)
    by_cat: dict[str, list[int]] = {}
    for s in scored:
        by_cat.setdefault(s["category"], []).append(s["score"])
    cat_means = sorted(
        ((cat, _mean(v), len(v)) for cat, v in by_cat.items()),
        key=lambda t: t[1],
    )

    # lowest-N statements (worst score first; frequency as tiebreak — a repeated
    # low claim is the more interesting miss).
    lowest = sorted(scored, key=lambda s: (s["score"], -s["frequency"]))[:lowest_n]

    # correlated misses: low AND repeated across sections.
    correlated = sorted(
        (s for s in scored
         if s["frequency"] >= _CORRELATED_FREQ and s["score"] <= _CORRELATED_MAX_SCORE),
        key=lambda s: (s["score"], -s["frequency"]),
    )

    return {
        "scored_count": len(scored),
        "skipped_count": skipped,
        "overall_mean": _mean(all_scores),
        "category_means": [
            {"category": c, "mean": m, "count": n} for c, m, n in cat_means
        ],
        "lowest": lowest,
        "correlated_misses": correlated,
        "lowest_n": lowest_n,
    }


def _fmt_stmt(s: dict) -> str:
    return (f"  [{s['score']:>2}] {s['id']}  ({s['category']}, "
            f"freq {s['frequency']}, src {s['source_sections'] or '-'})\n"
            f"       {s['statement']}")


def print_report(rep: dict) -> None:
    out = sys.stdout
    p = lambda *a: print(*a, file=out)

    p("=" * 72)
    p("L5 SCORE READBACK — self-rated truthfulness (resonance), a tuning signal,")
    p("not ground-truth accuracy.")
    p("=" * 72)
    p(f"Scored: {rep['scored_count']}   Skipped (blank score): {rep['skipped_count']}")
    if rep["scored_count"] == 0:
        p("\nNo scored rows — fill the `score` column (0–10) and re-run.")
        return

    p(f"\nOVERALL MEAN: {rep['overall_mean']:.2f}  (n={rep['scored_count']})   "
      f"[baseline reference: 7.42]")

    p("\nPER-CATEGORY MEAN (worst first):")
    for c in rep["category_means"]:
        p(f"  {c['mean']:>5.2f}  {c['category']:<16} (n={c['count']})")

    p(f"\nLOWEST {rep['lowest_n']} STATEMENTS:")
    for s in rep["lowest"]:
        p(_fmt_stmt(s))

    p("\n" + "-" * 72)
    p("CORRELATED MISSES  (frequency >= 2 AND score <= 4)")
    p("Low-rated claims the reading repeated across sections — the prime suspects")
    p("for a single mis-grounded principle reinjected everywhere. This is the")
    p("signal the harness exists to surface.")
    p("-" * 72)
    if not rep["correlated_misses"]:
        p("  none — no low score recurred across multiple sections.")
    else:
        for s in rep["correlated_misses"]:
            p(_fmt_stmt(s))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Read back a filled scoresheet.csv into a tuning report (L5 §6)."
    )
    ap.add_argument("scoresheet", help="path to the filled scoresheet.csv")
    ap.add_argument("--n", type=int, default=10,
                    help="how many lowest-scored statements to list (default 10)")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="also write the report as JSON to this path")
    args = ap.parse_args(argv)

    rows = _read_rows(args.scoresheet)
    rep = analyse(rows, lowest_n=args.n)
    print_report(rep)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(rep, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"\nWrote JSON report: {args.json_out}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
