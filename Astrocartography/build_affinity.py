#!/usr/bin/env python3
"""
build_affinity.py — the goal-affinity table (spec ``ACG/ACG_08_GOAL_SCORING_SPEC.md`` §2).

Input: ``principles_grounding/acg_principles.grounded.json`` with ``goal_effects`` from
``principles_grounding/tag_goals_acg.py`` (07 §5). No LLM; deterministic.

For every planet p (sun..pluto) × angle a (MC, IC, ASC, DSC) × goal g (08 §1):

    s = Σ w_r·cit_r over records with goal_effects[g] == "supportive"
    c = Σ w_r·cit_r over records with goal_effects[g] == "challenging"
    m = Σ w_r·cit_r over records with goal_effects[g] == "mixed"
        records: A1 ``line`` records for (p, a)      w = AFFINITY_W_LINE    (1.0)
                 A2 ``planet_general`` records for p w = AFFINITY_W_GENERAL (0.5)
        cit_r = max(1, citation_count)
    s' = s + m/2 ; c' = c + m/2 ; volume = s' + c'
    net = (s' − c') / (volume + K) ; A = net · min(1, volume / V0)
    low_evidence = volume < AFFINITY_LOW_EVIDENCE

A3 angle frames and A4 planet-in-house fallbacks never enter the table.

Paran affinity (``ACG/ACG_10_PARANS_SPEC.md`` §6), top-level block ``parans``, key
``"<p1>-<p2>"`` (lowercase, alphabetical; the 45 unordered pairs of the 10 planets):

    s, c, m, volume from the ``paran`` records whose about.planets == {p1, p2}
        (w = PARAN_W_RECORD = 1.0, cit = max(1, citation_count))
    volume >= PARAN_MIN_VOLUME -> A by the cell formula above,      source "paran",
                                  contributors = those paran records
    else                       -> A = 1/2·(Ā(p1,g) + Ā(p2,g)),      source "fallback",
                                  Ā(p,g) = mean of the 4 stored line-cell A(p,a,g);
                                  contributors = union of both planets' 4 cells' contributors
                                  (s/c/m/volume still report the thin paran evidence)
    low_evidence = volume < AFFINITY_LOW_EVIDENCE (on the paran evidence)

The ``cells`` block is independent of the paran records.

Outputs (``principles_grounding/``):
  * ``acg_goal_affinity.json`` (+ ``.sha256``) — schema ``acg-affinity-1``
  * ``acg_goal_affinity_review.md`` — the 40 × 11 grid + the 08 §2 sanity expectations
    (evaluated and reported, never enforced: a failure is fixed in tagging or corpus,
    never by overriding A)

    python Astrocartography/build_affinity.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from acg_constants import (AFFINITY_K, AFFINITY_LOW_EVIDENCE, AFFINITY_V0,  # noqa: E402
                           AFFINITY_W_GENERAL, AFFINITY_W_LINE, ANGLES, BODY_ORDER,
                           GOAL_ORDER, GOALS, READ_IN_V1)

SCHEMA_VERSION = "acg-affinity-1"
PG = os.path.join(ROOT, "principles_grounding")
CORPUS = os.path.join(PG, "acg_principles.grounded.json")
OUT = os.path.join(PG, "acg_goal_affinity.json")
REVIEW = os.path.join(PG, "acg_goal_affinity_review.md")

PLANETS: tuple[str, ...] = tuple(b for b in BODY_ORDER if READ_IN_V1[b])   # sun..pluto
ROW_ANGLES: tuple[str, ...] = ("ASC", "DSC", "MC", "IC")
DIGITS = 12                      # stable float formatting (well below the 1e-9 tolerance)
MIXED_RATIO = 0.5                # "mixed" in the sanity checks: min(s',c') >= ratio·max(s',c')
# paran affinity (spec 10 §6); kept here, not in acg_constants
PARAN_MIN_VOLUME = 2.0           # paran-specific evidence needed to use it instead of the fallback
PARAN_W_RECORD = 1.0             # weight of one paran record
PAIRS: tuple[str, ...] = tuple(f"{a}-{b}" for i, a in enumerate(sorted(PLANETS))
                               for b in sorted(PLANETS)[i + 1:])        # 45, alphabetical


def _num(x: float) -> float:
    r = round(float(x), DIGITS)
    return 0.0 if r == 0 else r          # no "-0.0"


def cell_value(s: float, c: float, m: float) -> dict:
    sp, cp = s + 0.5 * m, c + 0.5 * m
    volume = sp + cp
    net = (sp - cp) / (volume + AFFINITY_K)
    A = net * min(1.0, volume / AFFINITY_V0)
    return {"A": _num(A), "s": _num(s), "c": _num(c), "m": _num(m), "volume": _num(volume),
            "low_evidence": volume < AFFINITY_LOW_EVIDENCE}


def _planet(about: dict) -> str:
    return str(about.get("planet") or "").lower()


def paran_pair(r: dict) -> str | None:
    """'<p1>-<p2>' for a paran planet-pair record, None otherwise (e.g. the acg_method
    record ``acg-method-crossings`` filed under scope paran)."""
    about = r.get("about") or {}
    if r.get("acg_scope") != "paran" or about.get("factor_type") != "acg_paran":
        return None
    pl = sorted(str(x).lower() for x in (about.get("planets") or []))
    if len(pl) != 2 or pl[0] == pl[1] or not set(pl) <= set(PLANETS):
        return None
    return f"{pl[0]}-{pl[1]}"


def fallback_A(cells: dict, pair: str, g: str) -> float:
    """1/2·(Ā(p1,g) + Ā(p2,g)), Ā = mean of the 4 stored line-cell A values (spec 10 §6)."""
    means = [sum(cells[f"{p}|{a}"][g]["A"] for a in ANGLES) / len(ANGLES)
             for p in pair.split("-")]
    return 0.5 * (means[0] + means[1])


def build_parans(records: list[dict], cells: dict) -> dict:
    """The 45 × 11 ``parans`` block (spec 10 §6) from the paran records + the line cells."""
    by_pair: dict = {}
    for r in records:
        k = paran_pair(r)
        if k is not None:
            by_pair.setdefault(k, []).append(r)
    out: dict = {}
    for pair in PAIRS:
        blk = {}
        for g in GOAL_ORDER:
            acc = {"supportive": 0.0, "challenging": 0.0, "mixed": 0.0}
            contributors = []
            for r in by_pair.get(pair, []):
                pol = (r.get("goal_effects") or {}).get(g)
                if pol in acc:
                    acc[pol] += PARAN_W_RECORD * max(1, int(r.get("citation_count") or 0))
                    contributors.append(r["principle_id"])
            v = cell_value(acc["supportive"], acc["challenging"], acc["mixed"])
            if v["volume"] >= PARAN_MIN_VOLUME:
                v["source"] = "paran"
            else:
                v["A"] = _num(fallback_A(cells, pair, g))
                v["source"] = "fallback"
                contributors = [c for p in pair.split("-") for a in ANGLES
                                for c in cells[f"{p}|{a}"][g]["contributors"]]
            v["contributors"] = sorted(set(contributors))
            blk[g] = v
        out[pair] = blk
    return out


def build(records: list[dict], corpus_sha256: str) -> dict:
    """Corpus records -> the affinity document (pure; no IO)."""
    line: dict = {}       # (planet, ANGLE) -> [records]
    general: dict = {}    # planet -> [records]
    for r in records:
        about = r.get("about") or {}
        if r.get("acg_scope") == "line" and about.get("factor_type") == "planet_on_angle":
            line.setdefault((_planet(about), str(about.get("angle")).upper()), []).append(r)
        elif (r.get("acg_scope") == "planet_general"
              and about.get("factor_type") == "acg_planet_general"):
            general.setdefault(_planet(about), []).append(r)

    cells: dict = {}
    for p in PLANETS:
        for a in ANGLES:
            weighted = ([(AFFINITY_W_LINE, r) for r in line.get((p, a), [])]
                        + [(AFFINITY_W_GENERAL, r) for r in general.get(p, [])])
            cell = {}
            for g in GOAL_ORDER:
                acc = {"supportive": 0.0, "challenging": 0.0, "mixed": 0.0}
                contributors = []
                for w, r in weighted:
                    pol = (r.get("goal_effects") or {}).get(g)
                    if pol in acc:
                        acc[pol] += w * max(1, int(r.get("citation_count") or 0))
                        contributors.append(r["principle_id"])
                v = cell_value(acc["supportive"], acc["challenging"], acc["mixed"])
                v["contributors"] = sorted(set(contributors))
                cell[g] = v
            cells[f"{p}|{a}"] = cell
    return {
        "schema_version": SCHEMA_VERSION,
        "corpus_sha256": corpus_sha256,
        "constants": {"K": AFFINITY_K, "V0": AFFINITY_V0, "W_LINE": AFFINITY_W_LINE,
                      "W_GENERAL": AFFINITY_W_GENERAL, "LOW_EVIDENCE": AFFINITY_LOW_EVIDENCE,
                      "PARAN_MIN_VOLUME": PARAN_MIN_VOLUME, "W_PARAN_RECORD": PARAN_W_RECORD,
                      "planets": list(PLANETS), "angles": list(ANGLES),
                      "goals": list(GOAL_ORDER)},
        "cells": cells,
        "parans": build_parans(records, cells),
    }


def dumps(doc: dict) -> str:
    return json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def file_sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------------------------------------------------------------------------
# Review sheet
# ---------------------------------------------------------------------------

def _sc(cell: dict) -> tuple[float, float]:
    return cell["s"] + 0.5 * cell["m"], cell["c"] + 0.5 * cell["m"]


def is_mixed(cell: dict) -> bool:
    sp, cp = _sc(cell)
    return sp > 0 and cp > 0 and min(sp, cp) >= MIXED_RATIO * max(sp, cp)


def _goal_terms(g: str) -> list[str]:
    """Word stems from the goal's normative definition (08 §1), for the failure hint."""
    words = re.findall(r"[a-z]{4,}", GOALS[g][2].lower())
    return sorted({w[:6] for w in words} - {"making", "place"})


def _diagnose(records: list[dict], p: str, a: str, g: str) -> str:
    """A hint for a failed expectation: corpus (no record speaks to the goal) or tagging
    (records speak to it but carry no / the opposite tag). Radul decides."""
    pool = [r for r in records
            if (r.get("acg_scope") == "line" and _planet(r.get("about") or {}) == p
                and str((r.get("about") or {}).get("angle")).upper() == a)
            or (r.get("acg_scope") == "planet_general" and _planet(r.get("about") or {}) == p)]
    n_line = sum(1 for r in pool if r["acg_scope"] == "line")
    rx = re.compile(r"\b(" + "|".join(_goal_terms(g)) + r")", re.I)
    mention = [r["principle_id"] for r in pool
               if rx.search(" ".join(filter(None, (r.get("rule"), r.get("judgment"),
                                                   json.dumps(r.get("conditions") or [])))))]
    tagged = {r["principle_id"]: r["goal_effects"][g] for r in pool
              if g in (r.get("goal_effects") or {})}
    if n_line < 2:
        return f"likely CORPUS: only {n_line} line record(s) for {p}|{a}"
    if not tagged and not mention:
        return (f"likely CORPUS: none of the {n_line} line + {len(pool) - n_line} "
                f"planet_general records for {p}|{a} uses `{g}` definition terms; nothing to tag")
    if not tagged:
        return (f"CHECK: none tagged `{g}`, but keyword hits on `{g}` definition terms (a "
                f"crude hint; may be false positives) in {mention} - TAGGING if those records "
                f"really concern {g}, otherwise CORPUS")
    return f"tagged `{g}`: {tagged}; records mentioning `{g}` terms: {mention}"


EXPECTATIONS = [
    # (planet, angle, goal, test, label)
    ("venus", "DSC", "love", "pos", "Venus DSC positive for love"),
    ("venus", "ASC", "love", "pos", "Venus ASC positive for love"),
    ("jupiter", "MC", "career", "pos", "Jupiter MC positive for career"),
    ("jupiter", "MC", "business", "pos", "Jupiter MC positive for business"),
    ("saturn", "MC", "career", "mixed_or_pos", "Saturn MC mixed or positive for career"),
    ("saturn", "MC", "rest", "neg", "Saturn MC negative for rest"),
    ("mars", "ASC", "rest", "neg", "Mars ASC negative for rest"),
    *[("neptune", a, g, "pos", f"Neptune {a} positive for {g}")
      for g in ("spirituality", "creativity") for a in ROW_ANGLES],
    *[("neptune", a, "money", "neg_or_mixed", f"Neptune {a} negative or mixed for money")
      for a in ROW_ANGLES],
]


def evaluate(doc: dict, records: list[dict]) -> list[dict]:
    out = []
    for p, a, g, test, label in EXPECTATIONS:
        cell = doc["cells"][f"{p}|{a}"][g]
        A = cell["A"]
        ok = {"pos": A > 0, "neg": A < 0,
              "mixed_or_pos": A > 0 or is_mixed(cell),
              "neg_or_mixed": A < 0 or is_mixed(cell)}[test]
        out.append({"label": label, "cell": f"{p}|{a}", "goal": g, "pass": ok, "A": A,
                    "s": cell["s"], "c": cell["c"], "m": cell["m"], "volume": cell["volume"],
                    "low_evidence": cell["low_evidence"], "mixed": is_mixed(cell),
                    "diagnosis": None if ok else _diagnose(records, p, a, g)})
    return out


def review_md(doc: dict, records: list[dict]) -> str:
    L = ["# ACG goal-affinity table: review sheet (08 §2)", "",
         f"Corpus `acg_principles.grounded.json` sha256 `{doc['corpus_sha256']}`. "
         f"Constants: K={AFFINITY_K}, V0={AFFINITY_V0}, w(line)={AFFINITY_W_LINE}, "
         f"w(planet_general)={AFFINITY_W_GENERAL}; `·` marks a low-evidence cell "
         f"(volume < {AFFINITY_LOW_EVIDENCE}).", "",
         "Generated by `Astrocartography/build_affinity.py`; do not edit by hand. A failed "
         "sanity expectation is fixed in tagging or the corpus, never by overriding A.", "",
         "## Grid (A, 2 dp)", ""]
    L.append("| line | " + " | ".join(GOAL_ORDER) + " |")
    L.append("|---|" + "---:|" * len(GOAL_ORDER))
    n_low = 0
    for p in PLANETS:
        for a in ROW_ANGLES:
            cell = doc["cells"][f"{p}|{a}"]
            vals = []
            for g in GOAL_ORDER:
                v = cell[g]
                n_low += v["low_evidence"]
                vals.append(f"{v['A']:+.2f}{'·' if v['low_evidence'] else ''}")
            L.append(f"| {p} {a} | " + " | ".join(vals) + " |")
    total = len(PLANETS) * len(ANGLES) * len(GOAL_ORDER)
    L += ["", f"Low-evidence cells: {n_low} of {total}.", "", "## Sanity expectations", "",
          f"Not hard-coded; evaluated here. `mixed` = both s' and c' present with "
          f"min(s', c') ≥ {MIXED_RATIO}·max(s', c').", "",
          "| expectation | result | A | s | c | m | volume | low evidence |",
          "|---|---|---:|---:|---:|---:|---:|---|"]
    res = evaluate(doc, records)
    for e in res:
        L.append(f"| {e['label']} | {'PASS' if e['pass'] else '**FAIL**'} | {e['A']:+.3f} | "
                 f"{e['s']:g} | {e['c']:g} | {e['m']:g} | {e['volume']:g} | "
                 f"{'yes' if e['low_evidence'] else 'no'} |")
    fails = [e for e in res if not e["pass"]]
    L += ["", f"{len(res) - len(fails)} of {len(res)} expectations pass.", ""]
    if fails:
        L += ["### Failures: diagnosis", ""]
        for e in fails:
            L.append(f"- **{e['label']}** (A {e['A']:+.3f}): {e['diagnosis']}")
        L.append("")
    L += parans_md(doc)
    return "\n".join(L)


def parans_md(doc: dict) -> list[str]:
    """The review sheet's parans section (spec 10 §6)."""
    par = doc.get("parans") or {}
    entries = [(k, g, par[k][g]) for k in sorted(par) for g in GOAL_ORDER]
    own = [(k, g, v) for k, g, v in entries if v["source"] == "paran"]
    thin = sorted({k for k, g, v in entries if 0 < v["volume"] < PARAN_MIN_VOLUME})
    L = ["## Parans (spec 10 §6)", "",
         f"{len(par)} pairs × {len(GOAL_ORDER)} goals = {len(entries)} entries: "
         f"**{len(own)}** from paran records (volume ≥ {PARAN_MIN_VOLUME:g}), "
         f"{len(entries) - len(own)} fallback (A = ½·(Ā(p1,g) + Ā(p2,g)), Ā = mean of the "
         f"planet's 4 line cells). Pairs with some paran evidence below the threshold "
         f"(fallback used): {len(thin)}.", ""]
    if own:
        L += ["| pair | goal | A | s | c | m | volume | fallback A would be | contributors |",
              "|---|---|---:|---:|---:|---:|---:|---:|---|"]
        for k, g, v in own:
            L.append(f"| {k} | {g} | {v['A']:+.3f} | {v['s']:g} | {v['c']:g} | {v['m']:g} | "
                     f"{v['volume']:g} | {fallback_A(doc['cells'], k, g):+.3f} | "
                     f"{', '.join(v['contributors'])} |")
        L.append("")
    return L


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the ACG goal-affinity table (08 §2).")
    ap.add_argument("--corpus", default=CORPUS)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--review", default=REVIEW)
    args = ap.parse_args()

    records = json.load(open(args.corpus, encoding="utf-8"))
    missing = [r["principle_id"] for r in records
               if (r.get("acg_scope") in ("line", "planet_general") or paran_pair(r))
               and "goal_effects" not in r]
    if missing:
        sys.exit(f"{len(missing)} line/planet_general/paran records have no goal_effects "
                 f"(run principles_grounding/tag_goals_acg.py first): {missing[:5]}")
    doc = build(records, file_sha256(args.corpus))
    payload = dumps(doc)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    n_low = sum(v["low_evidence"] for c in doc["cells"].values() for v in c.values())
    n_par = sum(v["source"] == "paran" for c in doc["parans"].values() for v in c.values())
    with open(args.out + ".sha256", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{digest}  {os.path.basename(args.out)}\n"
                 f"cells={len(doc['cells'])} goals={len(GOAL_ORDER)} low_evidence={n_low} "
                 f"paran_pairs={len(doc['parans'])} paran_sourced={n_par} "
                 f"corpus_sha256={doc['corpus_sha256']}\n")
    md = review_md(doc, records)
    with open(args.review, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(md)
    res = evaluate(doc, records)
    print(f"wrote {os.path.basename(args.out)} (+ .sha256 {digest[:16]}…), "
          f"{os.path.basename(args.review)}; low-evidence cells {n_low}; paran entries "
          f"from paran records {n_par} of {len(doc['parans']) * len(GOAL_ORDER)}")
    for e in res:
        print(f"  {'PASS' if e['pass'] else 'FAIL'}  {e['label']}: A={e['A']:+.3f} "
              f"s={e['s']:g} c={e['c']:g} m={e['m']:g} vol={e['volume']:g}"
              + (f"  [{e['diagnosis']}]" if e["diagnosis"] else ""))


if __name__ == "__main__":
    main()
