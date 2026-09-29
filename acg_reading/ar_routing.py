#!/usr/bin/env python3
"""ar_routing.py — deterministic routing: acg_principles.json -> section plan.

No LLM. The plan fixes, for every unit the model will write, exactly which records
it may use (the trace pool) and the reader-facing labels it receives (tier wording,
life-area names, band labels) — numbers, degrees and angle abbreviations never reach
a prompt. Same payload + same focus goal -> the same plan (spec 04 AR1).

Units:
  place_overview   1 slot: method records (+ the other drafts as context, later)
  lines_here       1 slot per selected line: A3 frame + A2 synopsis + A4 fallback
  positives        1 slot: selected lines' A1/A2 with polarity supportive|mixed
  challenges       1 slot: selected lines' A1/A2 with polarity challenging|mixed
  life_areas_here  1 slot: house-shift bundles
  suitability      6 cards (+ a 7th for a focus goal outside the six)

``focus_goal`` (07 §6.5) reorders lines and cards and adds one emphasis instruction;
it never filters records.
"""

from __future__ import annotations

import re
from typing import Optional

from ar_sections import (
    ANGLE_PLAIN, BANDS, CARD_ORDER, CARDS, GOAL_TO_CARD, GOALS, LIFE_AREAS,
    NO_EMPHASIS_ID, PLANET_NAMES, SECTIONS, TIER_WORDING,
)

POS_POLARITIES = ("supportive", "mixed")
NEG_POLARITIES = ("challenging", "mixed")


_ABBR_PLAIN = [
    (re.compile(r"\bthe ASC\b|\bASC\b|\bAscendant\b"), "the rising point"),
    (re.compile(r"\bthe DSC\b|\bDSC\b|\bDescendant\b"), "the setting point"),
    (re.compile(r"\bthe MC\b|\bMC\b|\bMidheaven\b"), "the culmination point"),
    (re.compile(r"\bthe IC\b|\bIC\b|\bImum Coeli\b"), "the root point"),
]


def _plain(text):
    """Swap angle abbreviations in record text for plain words before it reaches a
    prompt, so the model has nothing to echo that AV1 forbids. Meaning is unchanged."""
    if not text:
        return text
    for pat, rep in _ABBR_PLAIN:
        text = pat.sub(rep, text)
    return text


def _slim(r: dict) -> dict:
    """What a prompt sees of a record: meaning only, no provenance or numbers."""
    return {"id": r["principle_id"], "rule": _plain(r.get("rule")),
            "judgment": _plain(r.get("judgment")),
            "polarity": r.get("polarity"), "sensitivity": r.get("sensitivity", "normal")}


def _line_bundles(payload: dict) -> list[dict]:
    return [b for b in payload.get("bundles", []) if b["factor"].startswith("line:")]


def _body_angle(factor: str) -> tuple[str, str]:
    body, angle = factor.split(":", 1)[1].split("|")
    return body, angle


def _goal_contribution(payload: dict, goal: str, body: str, angle: str) -> float:
    for c in (payload.get("goal_contributors", {}).get(goal) or {}).get("contributions", []):
        if c["body"] == body and c["angle"] == angle:
            return abs(float(c["contribution"]))
    return 0.0


def build_plan(payload: dict, *, focus_goal: Optional[str] = None,
               with_cards: bool = True) -> dict:
    if focus_goal is not None and focus_goal not in GOALS:
        raise ValueError(f"unknown focus goal {focus_goal!r}")
    place = payload.get("place") or {}
    records: dict[str, dict] = {}
    for b in payload.get("bundles", []):
        for r in b["records"]:
            records[r["principle_id"]] = r
    for r in payload.get("goal_records", []):
        records.setdefault(r["principle_id"], r)

    lines = _line_bundles(payload)
    if focus_goal:
        lines = sorted(lines, key=lambda b: (-_goal_contribution(payload, focus_goal,
                                                                  *_body_angle(b["factor"])),
                                             b.get("distance_km", 0.0)))
    sections: list[dict] = []

    # --- lines_here: what each line IS (A3 + A2, A4 fallback) ---------------
    line_slots = []
    pos_pool, neg_pool = [], []
    selected_bodies = []
    for b in lines:
        body, angle = _body_angle(b["factor"])
        selected_bodies.append(body)
        what = [r for r in b["records"] if r["acg_evidence"].get("source") in ("A3", "A2", "A4")]
        line_slots.append({
            "slot_id": b["factor"], "body": body, "angle": angle,
            "planet_tr": PLANET_NAMES[body][0], "planet_en": PLANET_NAMES[body][1],
            "where_tr": ANGLE_PLAIN[angle][0], "where_en": ANGLE_PLAIN[angle][1],
            "tier": b["tier"], "wording_tr": TIER_WORDING[b["tier"]][0],
            "wording_en": TIER_WORDING[b["tier"]][1],
            "records": [_slim(r) for r in what],
        })
        for r in b["records"]:
            if r["acg_evidence"].get("source") not in ("A1", "A2"):
                continue
            tagged = dict(_slim(r), planet_tr=PLANET_NAMES[body][0],
                          planet_en=PLANET_NAMES[body][1], where_tr=ANGLE_PLAIN[angle][0],
                          wording_tr=TIER_WORDING[b["tier"]][0])
            if r.get("polarity") in POS_POLARITIES and r["principle_id"] not in \
                    {x["id"] for x in pos_pool}:
                pos_pool.append(tagged)
            if r.get("polarity") in NEG_POLARITIES and r["principle_id"] not in \
                    {x["id"] for x in neg_pool}:
                neg_pool.append(tagged)
    if line_slots:
        sections.append({"key": "lines_here", "slots": line_slots})

    # --- background_influences: near parans (spec 10 §7) ------------------
    paran_slots = []
    paran_bodies: set[str] = set()
    for b in payload.get("bundles", []):
        if not b["factor"].startswith("paran:"):
            continue
        a, c = b["bodies"]
        paran_bodies |= {a, c}
        paran_slots.append({"slot_id": b["factor"], "bodies": [a, c],
                            "planets_tr": [PLANET_NAMES[a][0], PLANET_NAMES[c][0]],
                            "planets_en": [PLANET_NAMES[a][1], PLANET_NAMES[c][1]],
                            "records": [_slim(r) for r in b["records"]]})
    if paran_slots:
        sections.append({"key": "background_influences", "slots": paran_slots})
    if pos_pool:
        sections.append({"key": "positives", "slots": [{"slot_id": "positives",
                                                         "records": pos_pool}]})
    if neg_pool:
        sections.append({"key": "challenges", "slots": [{"slot_id": "challenges",
                                                          "records": neg_pool}]})

    # --- life_areas_here -----------------------------------------------------
    house = [b for b in payload.get("bundles", []) if b["factor"].startswith("house:")]
    if house:
        recs = []
        for b in house:
            body = b["factor"][6:].split("|")[0]
            area_tr, area_en = LIFE_AREAS[b["relocated_house"]]
            for r in b["records"]:
                recs.append(dict(_slim(r), planet_tr=PLANET_NAMES[body][0],
                                 planet_en=PLANET_NAMES[body][1], life_area_tr=area_tr,
                                 life_area_en=area_en))
        sections.append({"key": "life_areas_here", "slots": [{"slot_id": "life_areas_here",
                                                               "records": recs}]})

    # --- suitability cards (07 §6.2) ----------------------------------------
    cards = []
    if with_cards:
        order = list(CARD_ORDER)
        extra_goal = None
        if focus_goal:
            if focus_goal in GOAL_TO_CARD:
                order.remove(GOAL_TO_CARD[focus_goal])
                order.insert(0, GOAL_TO_CARD[focus_goal])
            else:
                extra_goal = focus_goal
        specs = [(k, CARDS[k][0], CARDS[k][1], CARDS[k][2]) for k in order]
        if extra_goal:
            specs.append((extra_goal, GOALS[extra_goal][0], GOALS[extra_goal][1], extra_goal))
        gc = payload.get("goal_contributors") or {}
        for key, t_tr, t_en, goal in specs:
            blk = gc.get(goal) or {"band": "no_emphasis", "contributors": []}
            band = blk["band"]
            contributors = [c for c in blk.get("contributors", []) if c in records]
            cards.append({
                "card": key, "goal": goal, "title_tr": t_tr, "title_en": t_en,
                "band": band, "band_label_tr": BANDS[band][0], "band_label_en": BANDS[band][1],
                "goal_definition": GOALS[goal][2],
                "template": band == "no_emphasis" or not contributors,
                "contributors": contributors,
                "records": [_slim(records[c]) for c in contributors],
            })
        sections.append({"key": "suitability", "slots": [], "cards": cards})

    # --- place_overview (always, drafted last) ------------------------------
    method = next((b for b in payload.get("bundles", []) if b["factor"] == "method"),
                  {"records": []})
    overview = {"key": "place_overview", "slots": [{
        "slot_id": "place_overview", "records": [_slim(r) for r in method["records"]]}]}
    if focus_goal:
        overview["focus_goal"] = {"goal": focus_goal, "label_tr": GOALS[focus_goal][0],
                                  "label_en": GOALS[focus_goal][1]}

    ordered = [overview] + sorted(sections, key=lambda s: list(SECTIONS).index(s["key"]))
    allowed_bodies = sorted(set(selected_bodies), key=list(PLANET_NAMES).index)
    return {
        "place": {"name": place.get("name"), "name_tr": place.get("name_tr")},
        "focus_goal": focus_goal,
        "selection_rule": (payload.get("selection") or {}).get("rule"),
        "no_lines": not line_slots,
        "line_bodies": allowed_bodies,
        "house_bodies": sorted({b["factor"][6:].split("|")[0] for b in house},
                               key=list(PLANET_NAMES).index),
        "paran_bodies": sorted(paran_bodies, key=list(PLANET_NAMES).index),
        "parans_display": payload.get("parans_display", []),
        "sections": ordered,
        "goal_scores": {g: {k: v for k, v in blk.items()
                            if k in ("score", "P", "N", "band")}
                        | {"band_label_tr": BANDS[blk["band"]][0],
                           "band_label_en": BANDS[blk["band"]][1]}
                        for g, blk in (payload.get("goal_contributors") or {}).items()},
        "lines_display": payload.get("lines_display", []),
        "sensitivity_high_ids": payload.get("sensitivity_high_ids", []),
        "known_ids": sorted(records),
        "no_emphasis_id": NO_EMPHASIS_ID,
    }


def traced_ids(plan: dict) -> set[str]:
    """Every id any unit of the plan may trace (the grounded pool)."""
    out = set(plan["known_ids"])
    out.add(NO_EMPHASIS_ID)
    return out
