"""cal_corpus.py - the calendar's local view of the corpus (Phase 0 report, decision Q3).

The shared corpus file is read, never modified. Modern records only (CAL_00 D3).
The index is deterministic and keyed for CAL:

  transits[(T, a, N)]   directed: T = transiting body (Sun..Pluto, Moon), a = aspect,
                        N = natal point (10 planets + asc + mc). Both Hand copies:
                        the structured ``about.aspect`` records, plus the unclassified
                        records whose ``principle_id`` parses as T-a-N (this recovers every
                        transit to ASC/MC).
  moon_in_house[h]      transiting Moon through natal house h (CAL_04 P3)
  generic[kind]         lunation / eclipse / station records (few; general statements)
  house_domain[h]       modern natal house-meaning records (CAL_03 personal_lunation)

    python Calendar/cal_corpus.py        # prints the coverage summary
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from functools import lru_cache

import cal_constants as K

ENGINE_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO_ROOT = os.path.normpath(os.path.join(ENGINE_ROOT, "..", ".."))  # astrology-app root
CORPUS_PATH = os.path.join(ENGINE_ROOT, "principles_grounding",
                           "all_principles_grounded.with_predictive.json")

_PL = "sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto"
_ID_RX = re.compile(
    rf"^(?:transit(?:ing)?-)?({_PL})-(conjunct|conjunction|sextile|square|trine|opposition|opposite)"
    rf"-(?:natal-)?({_PL}|midheaven|ascendant|mc|asc)(?:-|$)")
_NORM = {"conjunct": "conjunction", "opposite": "opposition",
         "midheaven": "mc", "ascendant": "asc"}
_TARGETS = set(K.NATAL_PLANETS) | {"asc", "mc"}
_TRANSITING = set(K.TRANSIT_BODIES) | {"moon"}

# Generic timing records found in the Phase 0 audit (§3 b-d); modern, predictive.
GENERIC_IDS = {
    "lunation": ["lunation-eclipse-activates-natal-planet", "lunation-activates-natal-planet",
                 "transiting-moon-new-full-extended"],
    "eclipse": ["eclipse-natal-activation", "eclipse-natal-planet-duration",
                "eclipse-activation-natal-planet", "eclipse-delayed-trigger",
                "lunation-eclipse-activates-natal-planet"],
    "station": ["stationary-transit-intensification", "stationary-transit-intensification-2"],
    "moon_house_general": ["moon-house-transit-focus-area"],
    "electional_moon": ["avoid-social-occasions-moon-affliction", "moon-affliction-electional-caution"],
}


_RETURN_RX = re.compile(rf"^({_PL})-return(?:-|$)")


def _key_from_id(pid: str):
    r = _RETURN_RX.match(pid)          # "saturn-return-first" = Saturn conjunct natal Saturn
    if r and r.group(1) in K.TRANSIT_BODIES:
        return r.group(1), "conjunction", r.group(1)
    m = _ID_RX.match(pid)
    if not m:
        return None
    t, typ, n = m.group(1), _NORM.get(m.group(2), m.group(2)), _NORM.get(m.group(3), m.group(3))
    return (t, typ, n) if (t != n or t in K.TRANSIT_BODIES) else None


def transit_key_of(rec: dict):
    """(T, a, N) for a modern transit record, or None. Direction: T is the transiting body.

    When the principle_id parses as T-a-N it wins over ``about``. In the audit, all 11
    disagreements were angle transits whose ``about.aspect.target`` was mis-set (mostly to Sun)."""
    a = rec.get("about") or {}
    if a.get("factor_type") in ("aspect", "unclassified", "general"):
        k = _key_from_id(rec["principle_id"])
        if k:
            return k
    if a.get("factor_type") == "aspect":
        asp = a.get("aspect") or {}
        t = str(asp.get("source", "")).lower()
        n = str(asp.get("target", "")).lower()
        n = _NORM.get(n, n)
        typ = asp.get("type")
        if t in _TRANSITING and n in _TARGETS and typ in K.ASPECTS:
            return t, typ, n
        return None
    if a.get("factor_type") == "unclassified":
        m = _ID_RX.match(rec["principle_id"])
        if m:
            t, typ, n = m.group(1), _NORM.get(m.group(2), m.group(2)), _NORM.get(m.group(3), m.group(3))
            if t != n or t in K.TRANSIT_BODIES:
                return t, typ, n
    return None


def _moon_house_of(rec: dict):
    a = rec.get("about") or {}
    if a.get("factor_type") == "planet_in_house" and a.get("point") == "Moon":
        return a.get("house")
    return None


def build_index(records: list[dict]) -> dict:
    modern = [r for r in records if r.get("tradition") == "modern"]
    byid = {r["principle_id"]: r for r in modern}
    transits: dict = defaultdict(list)
    moon_in_house: dict = defaultdict(list)
    house_domain: dict = defaultdict(list)
    for r in modern:
        if r.get("domain") == "predictive":
            k = transit_key_of(r)
            if k:
                transits[k].append(r["principle_id"])
            h = _moon_house_of(r)
            if h:
                moon_in_house[int(h)].append(r["principle_id"])
        a = r.get("about") or {}
        if a.get("factor_type") == "house_domain" and a.get("house"):
            house_domain[int(a["house"])].append(r["principle_id"])
    generic = {k: [i for i in ids if i in byid] for k, ids in GENERIC_IDS.items()}
    return {"transits": {k: sorted(v) for k, v in sorted(transits.items())},
            "moon_in_house": {k: sorted(v) for k, v in sorted(moon_in_house.items())},
            "house_domain": {k: sorted(v) for k, v in sorted(house_domain.items())},
            "generic": generic}


def corpus_sha(path: str = CORPUS_PATH) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


@lru_cache(maxsize=2)
def load(path: str = CORPUS_PATH) -> tuple[dict, dict]:
    """-> (index, {principle_id: record} for modern records)."""
    with open(path, encoding="utf-8") as fh:
        records = json.load(fh)
    modern = {r["principle_id"]: r for r in records if r.get("tradition") == "modern"}
    return build_index(records), modern


def tag_scope_ids(index: dict) -> list[str]:
    """Records to goal-tag (CAL_02 §2): every transit record + the generic timing records."""
    ids = {i for v in index["transits"].values() for i in v}
    for k in ("lunation", "eclipse", "station"):
        ids.update(index["generic"][k])
    return sorted(ids)


def main() -> None:
    idx, _ = load()
    tr = idx["transits"]
    cells = {(t, a, n) for (t, a, n) in tr if t != "moon"}
    want = {(t, a, n) for t in K.TRANSIT_BODIES for a in K.ASPECT_ORDER
            for n in K.NATAL_PLANETS + ["asc", "mc"]}
    print(f"transit cells (T!=Moon): {len(cells & want)}/{len(want)}; "
          f"records {sum(len(v) for k, v in tr.items() if k[0] != 'moon')}")
    print(f"moon transit cells: {sum(1 for k in tr if k[0] == 'moon')}")
    print(f"missing: {sorted(want - cells)}")
    print(f"moon_in_house houses: {sorted(idx['moon_in_house'])}; "
          f"house_domain houses: {sorted(idx['house_domain'])}")
    print(f"generic: { {k: len(v) for k, v in idx['generic'].items()} }")
    print(f"tag scope: {len(tag_scope_ids(idx))} records")


if __name__ == "__main__":
    main()
