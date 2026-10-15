#!/usr/bin/env python3
"""
pr_events.py — deterministic event serialization + profile emphasis
(PREDICTIVE_READING_SPEC §5, §7.2, §9).

Turns grounded forecast events into the plain one-line-per-event block the prompts
consume, and owns every deterministic decision the reading LLM must NOT make:

  - which events are material (only grounded ones — those the upstream grounding step
    attached ≥1 matched principle to; §4 grounding discipline);
  - segment membership (taken from the compute layer's `segment` field, never recomputed, §2);
  - profile emphasis ORDER (lead events first, then texture, by raw strength; §3);
  - the plain-language translation of every technical fact into feeling-words (§5, §7.2).

Input contract — a "grounded forecast" is a `compute_forecast()` object whose every event
additionally carries:

    event["matched_principles"] : list of { "principle_id": str, "judgment": str, ... }

attached by the forecast-grounding step. `judgment` is the already-plain, tradition-masked
gloss the reading interprets from (§4). Events with no matched principle are not material
and are dropped from the reading (the model interprets ONLY from given texts).

No LLM, no I/O.
"""

from __future__ import annotations

from typing import Optional

from pr_profiles import Profile

# ---------------------------------------------------------------------------
# Horizon shape (§1) — section keys and per-section word targets (min, max).
# ---------------------------------------------------------------------------
HORIZON_KEYS = {
    "day": ["reading"],
    "month": ["overview", "early", "mid", "late", "focus"],
    "year": ["overview", "q1", "q2", "q3", "q4", "focus"],
}
WORD_TARGETS = {
    "day": {"reading": (120, 180)},
    "month": {"overview": (80, 120), "early": (50, 80), "mid": (50, 80),
              "late": (50, 80), "focus": (80, 120)},
    "year": {"overview": (100, 140), "q1": (60, 90), "q2": (60, 90),
             "q3": (60, 90), "q4": (60, 90), "focus": (100, 140)},
}
# Which segment labels are the parallel beat calls for each horizon (§2).
BEAT_SEGMENTS = {"month": ["early", "mid", "late"], "year": ["q1", "q2", "q3", "q4"]}
# Human labels for the beat prompts.
SEGMENT_LABEL = {
    "early": "beginning of the month", "mid": "middle of the month",
    "late": "end of the month",
    "q1": "first quarter", "q2": "second quarter",
    "q3": "third quarter", "q4": "fourth quarter",
}
# Sparse thresholds on grounded_event_count, per horizon (§9).
SPARSE_THRESHOLD = {"day": 1, "month": 3, "year": 6}


# ---------------------------------------------------------------------------
# Plain life-area language (§5, §7.2). House domain -> everyday words. Placidus only.
# ---------------------------------------------------------------------------
_HOUSE_AREA = {
    1: "self and vitality", 2: "money and resources", 3: "mind and communication",
    4: "home and family", 5: "creativity and romance", 6: "health and daily work",
    7: "close relationships", 8: "shared depths and change", 9: "meaning and horizons",
    10: "work and standing", 11: "friends and hopes", 12: "inner life and rest",
}
# Fallback when no house is known (degraded precision, or a pure-sky event without a
# located house): read the plain theme off the natal target instead.
_PLANET_THEME = {
    "Sun": "self and vitality", "Moon": "feeling-life and home",
    "Mercury": "mind and communication", "Venus": "love and pleasure",
    "Mars": "drive and action", "Jupiter": "growth and opportunity",
    "Saturn": "responsibility and structure", "Uranus": "change and freedom",
    "Neptune": "dreams and letting go", "Pluto": "depth and transformation",
    "Ascendant": "self and how you meet the world", "MC": "work and standing",
    "IC": "home and roots", "Descendant": "close relationships",
}


def plain_area(event: dict) -> str:
    hp = event.get("house_placidus")
    if hp in _HOUSE_AREA:
        return _HOUSE_AREA[hp]
    natal = (event.get("bodies") or {}).get("natal")
    if natal in _PLANET_THEME:
        return _PLANET_THEME[natal]
    # sky events (lunation/eclipse) with no located house
    return "your inner rhythm"


# ---------------------------------------------------------------------------
# Motion words (§5 translation guide, §7.2). Valence (aspect) x motion (phase),
# NEVER the mechanism name.
# ---------------------------------------------------------------------------
_TENSION = {"square", "opposition"}
_FLOW = {"trine", "sextile"}
# phase -> motion verb
_PHASE_MOTION = {"applying": "building", "perfecting": "coming to a head now",
                 "separating": "settling"}


def motion_word(event: dict) -> str:
    fam = event.get("family")
    if fam in ("lunation", "eclipse"):
        # §7.2: lunations/eclipses render as culmination / fresh cycle.
        # full moon / lunar eclipse -> culmination; new moon / solar eclipse -> fresh cycle.
        tags = (event.get("grounding") or {}).get("topic_tags") or []
        joined = " ".join(tags).lower()
        if "full moon" in joined or "lunar" in joined:
            return "a culmination"
        return "a fresh cycle"
    if fam in ("ingress_sign", "ingress_house"):
        return "a new emphasis"
    # transit_aspect: valence x phase
    asp = event.get("aspect")
    phase = event.get("phase")
    pm = _PHASE_MOTION.get(phase, "moving")
    if asp == "conjunction":
        base = "a fresh start"
    elif asp in _TENSION:
        base = "pressure"
    elif asp in _FLOW:
        base = "support"
    else:
        base = "a theme"
    # e.g. "pressure building", "support coming to a head now", "a fresh start settling"
    return f"{base} {pm}"


# ---------------------------------------------------------------------------
# Dignity word (§6). strong | mixed | vulnerable | — . Read primarily off the natal
# target (the factor being pressed); fall back to the transiting body.
# ---------------------------------------------------------------------------
def _dignity_state(d: Optional[dict]) -> Optional[str]:
    if not d:
        return None
    if d.get("in_domicile") or d.get("in_exaltation"):
        return "strong"
    if d.get("in_detriment") or d.get("in_fall"):
        return "vulnerable"
    return None


def dignity_word(event: dict) -> str:
    dig = event.get("dignity") or {}
    natal = _dignity_state(dig.get("natal"))
    trans = _dignity_state(dig.get("transiting"))
    states = {s for s in (natal, trans) if s}
    if states == {"strong"}:
        return "strong"
    if states == {"vulnerable"}:
        return "vulnerable"
    if states == {"strong", "vulnerable"}:
        return "mixed"
    return "—"


# ---------------------------------------------------------------------------
# Principle gloss (§7.2): the matched principle's judgment, <=25 words, already plain.
# ---------------------------------------------------------------------------
def principle_gloss(event: dict, max_words: int = 25) -> str:
    matched = event.get("matched_principles") or []
    for m in matched:
        j = (m.get("judgment") or "").strip()
        if j:
            words = j.split()
            return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")
    return ""


def is_grounded(event: dict) -> bool:
    """A material event: the grounding step attached at least one principle judgment."""
    return bool(principle_gloss(event))


# ---------------------------------------------------------------------------
# Strength ordering (§3): general leads by objective strength; all profiles order
# within the lead / texture groups by it. Angle contact > slower body > perfecting-now
# > standing background.
# ---------------------------------------------------------------------------
_SPEED_RANK = {"slow": 2, "fast": 1}
_PHASE_RANK = {"perfecting": 3, "applying": 2, "separating": 1}


def strength(event: dict) -> tuple:
    natal = (event.get("bodies") or {}).get("natal")
    angle = 1 if natal in ("Ascendant", "MC", "IC", "Descendant") else 0
    fam_key = 1 if event.get("family") in ("eclipse",) else 0  # eclipses punch above weight
    spd = _SPEED_RANK.get(event.get("speed_class"), 0)
    ph = _PHASE_RANK.get(event.get("phase"), 0)
    standing = 0 if event.get("standing") else 1
    return (angle, fam_key, spd, ph, standing)


# ---------------------------------------------------------------------------
# Astrological descriptor (for astro_detail = "modern" / "technical")
# ---------------------------------------------------------------------------
# The plain reading hides all machinery; when the audience is astrology-literate we hand the
# model the actual configuration in [brackets] so it can NAME the driver accurately (and only
# name what is real — the §11.5 lint still forbids planets not present in the event list).
def astro_descriptor(event: dict, astro_detail: str) -> str:
    if astro_detail not in ("modern", "technical"):
        return ""
    fam = event.get("family")
    b = event.get("bodies") or {}
    trans, natal = b.get("transiting"), b.get("natal")
    sign = event.get("sign")
    tech = astro_detail == "technical"

    if fam == "transit_aspect":
        # The event sign belongs to the moving body, never to the natal target.
        mover = f"transiting {trans}" + (f" in {sign}" if sign else "")
        parts = [f"{mover} {event.get('aspect')} natal {natal}"]
        if tech:
            hp = event.get("house_placidus")
            if hp is not None:
                parts.append(f"house {hp}")
            if event.get("phase"):
                parts.append(event["phase"])
            if event.get("cycle_stage") is not None:
                parts.append(f"stage {event['cycle_stage']}")
        desc = " ".join(parts)
    elif fam == "ingress_sign":
        desc = f"{trans} enters {sign}"
    elif fam == "ingress_house":
        hp = event.get("house_placidus")
        desc = (f"{trans} enters house {hp}" if (tech and hp is not None)
                else f"{trans} enters a new area")
    elif fam in ("lunation", "eclipse"):
        tags = " ".join((event.get("grounding") or {}).get("topic_tags") or []).lower()
        moon = "full moon" if ("full moon" in tags or "lunar" in tags) else "new moon"
        if "eclipse" in tags:
            moon += " eclipse"
        desc = f"{moon}" + (f" in {sign}" if sign else "")
    else:
        return ""
    return f"[{desc}] "


# ---------------------------------------------------------------------------
# Serialization (§7.2)
# ---------------------------------------------------------------------------
def serialize_event(event: dict, segment_hint: Optional[str] = None,
                    astro_detail: str = "plain") -> str:
    seg = segment_hint if segment_hint is not None else (event.get("segment") or "—")
    return (f"- ({seg}) {astro_descriptor(event, astro_detail)}"
            f"{motion_word(event)} — {plain_area(event)} "
            f"| strength: {dignity_word(event)} "
            f"| meaning: {principle_gloss(event)}")


def material_events(events: list[dict]) -> list[dict]:
    """Only grounded events feed the reading (§4)."""
    return [e for e in events if is_grounded(e)]


def order_for_profile(events: list[dict], profile: Profile) -> list[dict]:
    """Lead events first (profile emphasis §3), then texture; each group by strength."""
    lead, texture = [], []
    for e in events:
        (lead if profile.is_lead(e) else texture).append(e)
    lead.sort(key=strength, reverse=True)
    texture.sort(key=strength, reverse=True)
    return lead + texture


def events_block(events: list[dict], profile: Profile, *,
                 segment: Optional[str] = None, limit: Optional[int] = None,
                 astro_detail: str = "plain") -> str:
    """Build the serialized block for a call. When `segment` is given, include only that
    segment's events (beat calls); otherwise the full material list (synthesis / day).
    Ordered by profile emphasis. `limit` truncates for the space-tight DAY horizon.
    `astro_detail` ("plain"|"modern"|"technical") controls whether each line carries the
    bracketed astrological driver the model may name."""
    mats = material_events(events)
    if segment is not None:
        mats = [e for e in mats if e.get("segment") == segment]
    ordered = order_for_profile(mats, profile)
    if limit is not None:
        ordered = ordered[:limit]
    if not ordered:
        return "(no notable movement in this stretch)"
    return "\n".join(serialize_event(e, astro_detail=astro_detail) for e in ordered)


def grounded_event_count(events: list[dict], profile: Profile) -> int:
    """Material grounded events (after profile emphasis — emphasis reorders but does not
    drop, so the count is simply the material set). Drives the §9 sparse decision."""
    return len(material_events(events))


def is_sparse(events: list[dict], profile: Profile, horizon: str) -> bool:
    return grounded_event_count(events, profile) < SPARSE_THRESHOLD[horizon]
