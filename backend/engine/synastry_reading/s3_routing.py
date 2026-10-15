#!/usr/bin/env python3
"""
s3_routing.py — S3 input prep: noise floor + routing + ordering + cap
(SYNASTRY_READING_SPEC.md §4).

There is no separate ranking artifact — S3 prepares its own inputs here:

  1. Noise floor (§4.1): drop face-grade receptions and sub-salience aspects
     (outer-planet-only contacts) from user-facing content. Dropped records are
     logged to the routing report, never deleted upstream.
  2. Route by content, not by bucket (§4.2): each surviving synastry record goes
     to one or more of the seven axes by its ``bound`` points/houses/topic_tags.
     Overlap is allowed and intended (a Venus-Mars square feeds both Attraction
     and Friction); dedup happens later in synthesis.
  3. Order and cap (§4.3): within each axis, order by weight (aspect salience;
     reception grade weight; mutual bonus) and cap at ~8 records; overflow drops
     to the report, not the reading.

The per-person opener (``what_each_brings``) is fed straight from ``person_a`` /
``person_b`` — not floored or routed by content, but capped so its two paragraphs
stay lean.

Attribution note (§7): routing reads ``bound`` (resolved persons/points), never
the pre-binding ``rule`` / ``person_a_point`` labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from s3_sections import (
    ATTRACTION,
    AXIS_ORDER,
    COMMITMENT,
    COMMUNICATION,
    EMOTIONAL,
    FRICTION,
    LUMINARIES,
    MALEFICS,
    OUTER_PLANETS,
    PERSONAL_PLANETS,
    PURPOSE,
    VALUES,
    WHAT_EACH_BRINGS,
    ANGULAR_HOUSES,
    RoutedRecord,
    is_significator,
)

# §4.3 — cap each section's input so section prompts stay lean.
SECTION_CAP = 8
# The opener gets a paragraph per person; cap the records feeding each person.
OPENER_CAP_PER_PERSON = 10

# Aspect-type base salience (before orb tightening). Hard aspects and the
# conjunction carry more relational charge than the wide sextile.
_ASPECT_BASE = {
    "conjunction": 1.0,
    "opposition": 0.9,
    "square": 0.85,
    "trine": 0.8,
    "sextile": 0.6,
    "quincunx": 0.5,
}
_HARD_ASPECTS = {"square", "opposition"}
# Orb beyond which an aspect contributes no tightness bonus.
_ORB_CEIL = 8.0


# ---------------------------------------------------------------------------
# Small typed accessors over the record's synastry / bound blocks.
# ---------------------------------------------------------------------------

def _syn(rec: dict) -> dict:
    return rec.get("synastry") or {}


def _interaction(rec: dict) -> str:
    return _syn(rec).get("interaction", "")


def _bound(rec: dict) -> dict:
    return rec.get("bound") or {}


def _aspect_points(rec: dict) -> set[str]:
    b = _bound(rec)
    return {p for p in (b.get("p1_point"), b.get("p2_point")) if p}


def _reception_points(rec: dict) -> set[str]:
    b = _bound(rec)
    return {p for p in (b.get("receiver_point"), b.get("received_point")) if p}


def _matched0(rec: dict) -> dict:
    m = rec.get("matched")
    return m[0] if isinstance(m, list) and m else {}


def fact_uid(rec: dict) -> str:
    """A stable, per-fact unique id. ``principle_id`` alone is NOT unique — a
    reception template like ``syn-reception-mars-receives`` grounds several
    distinct facts (Mars receives Sun at domicile, Mars receives Mercury at face,
    …). We disambiguate by signing the ``bound`` block so every grounded fact has
    its own traceable id (needed for S4 resonance scoring, §10.6). Global
    uniqueness is finalised in ``route`` with a counter suffix on any collision."""
    pid = rec.get("principle_id", "x")
    b = _bound(rec)
    it = _interaction(rec)
    if it == "aspect":
        sig = f"{b.get('p1_point')}_{b.get('aspect')}_{b.get('p2_point')}"
    elif it == "house_overlay":
        sig = f"{b.get('mover_point')}_h{b.get('home_house')}"
    elif it == "reception":
        sig = (f"{b.get('receiver_point')}-recv-{b.get('received_point')}"
               f"_{b.get('grade')}")
    elif it == "compatibility":
        sig = "-".join(str(x) for x in (b.get("factors") or []))
    else:
        sig = str(b.get("point") or b.get("factor_type") or "")
    return f"{pid}::{sig}" if sig and sig != "None_None_None" else pid


# ---------------------------------------------------------------------------
# Noise floor (§4.1)
# ---------------------------------------------------------------------------

def below_floor(rec: dict) -> Optional[str]:
    """Return a drop reason if this synastry record is below the noise floor
    (§4.1), else None. Applied at S3 read time; nothing is deleted upstream."""
    interaction = _interaction(rec)

    # Reception grade: face -> too weak to state (weight 0.2).
    if interaction == "reception":
        if _bound(rec).get("grade") == "face":
            return "reception_face_grade"
        return None

    # Cross-aspects below salience: outer-planet-only contacts. With no
    # sig_importance in the grounded data, "sub-floor" == neither endpoint is a
    # significator (both endpoints are outer planets / ungraded generational
    # points). A contact touching any significator survives.
    if interaction == "aspect":
        pts = _aspect_points(rec)
        if pts and not any(is_significator(p) for p in pts):
            return "aspect_outer_planet_only"
        return None

    return None


# ---------------------------------------------------------------------------
# Weight (§4.3) — used for ordering and cap only, never surfaced to the reader.
# ---------------------------------------------------------------------------

def weight_of(rec: dict) -> float:
    interaction = _interaction(rec)
    b = _bound(rec)

    if interaction == "aspect":
        base = _ASPECT_BASE.get(b.get("aspect"), 0.6)
        orb = _matched0(rec).get("orb")
        tightness = 0.0
        if isinstance(orb, (int, float)):
            tightness = max(0.0, 1.0 - min(float(orb), _ORB_CEIL) / _ORB_CEIL)
        w = 0.6 * base + 0.4 * tightness
        # Luminary/personal-planet contacts are the load-bearing chemistry.
        if _aspect_points(rec) & (LUMINARIES | PERSONAL_PLANETS):
            w += 0.15
        return round(w, 4)

    if interaction == "reception":
        # matched weight already encodes grade (domicile 1.0 -> face 0.2) and the
        # mutual +0.2 (capped 1.0); fall back to a grade table if absent.
        w = _matched0(rec).get("weight")
        if not isinstance(w, (int, float)):
            w = {"domicile": 1.0, "exaltation": 0.9, "triplicity": 0.6,
                 "bound": 0.4, "face": 0.2}.get(b.get("grade"), 0.4)
        if b.get("mutual"):
            w = min(1.0, float(w) + 0.05)   # small tiebreak beyond matched's cap
        return round(float(w), 4)

    if interaction == "house_overlay":
        w = 0.7
        if b.get("home_house") in ANGULAR_HOUSES:
            w += 0.15
        if b.get("mover_point") in (LUMINARIES | PERSONAL_PLANETS):
            w += 0.1
        return round(w, 4)

    if interaction == "compatibility":
        return 0.45

    return 0.4


# ---------------------------------------------------------------------------
# Content routing (§4.2) — a record may serve more than one axis.
# ---------------------------------------------------------------------------

def _compatibility_factors(rec: dict) -> set[str]:
    return {str(f).lower() for f in (_bound(rec).get("factors") or [])}


def route_sections(rec: dict) -> list[tuple[str, str]]:
    """Axes this synastry record routes to, with a reason each (§4.2). Reads only
    ``bound`` + ``topic_tags`` — never ``rule``. Returns (section, reason) pairs;
    duplicates across sections are intended."""
    interaction = _interaction(rec)
    b = _bound(rec)
    out: list[tuple[str, str]] = []

    def add(sec: str, reason: str) -> None:
        out.append((sec, reason))

    # ---- ASPECT ----------------------------------------------------------
    if interaction == "aspect":
        pts = _aspect_points(rec)
        atype = b.get("aspect")
        # 1 Attraction: Venus/Mars/Sun/Moon aspects; Asc/Desc contacts.
        if pts & {"Venus", "Mars", "Sun", "Moon"}:
            add(ATTRACTION, f"aspect touches {sorted(pts & {'Venus','Mars','Sun','Moon'})}")
        if pts & {"Ascendant", "Descendant"}:
            add(ATTRACTION, "aspect touches Ascendant/Descendant")
        # 2 Emotional: Moon aspects (incl. Moon-Saturn, Moon-Venus).
        if "Moon" in pts:
            add(EMOTIONAL, "aspect touches Moon")
        if "Nadir" in pts or "IC" in pts:
            add(EMOTIONAL, "aspect touches IC")
        # 3 Communication: Mercury aspects.
        if "Mercury" in pts:
            add(COMMUNICATION, "aspect touches Mercury")
        # 4 Friction: hard aspects on any significators; Mars-Saturn.
        if atype in _HARD_ASPECTS and any(is_significator(p) for p in pts):
            add(FRICTION, f"{atype} on significator(s)")
        if {"Mars", "Saturn"} <= pts:
            add(FRICTION, "Mars-Saturn contact")
        # 5 Values/life: Venus/Jupiter/Saturn.
        if pts & {"Venus", "Jupiter", "Saturn"}:
            add(VALUES, f"aspect touches {sorted(pts & {'Venus','Jupiter','Saturn'})}")
        # 6 Commitment: Saturn contacts; Sun-Moon.
        if "Saturn" in pts:
            add(COMMITMENT, "Saturn contact")
        if {"Sun", "Moon"} <= pts:
            add(COMMITMENT, "Sun-Moon contact")
        # 7 Purpose: Jupiter/Nodes; MC contacts.
        if pts & {"Jupiter", "North Node", "South Node"}:
            add(PURPOSE, "aspect touches Jupiter/Nodes")
        if "Midheaven" in pts or "MC" in pts:
            add(PURPOSE, "aspect touches Midheaven")

    # ---- HOUSE OVERLAY ---------------------------------------------------
    elif interaction == "house_overlay":
        h = b.get("home_house")
        mover = b.get("mover_point")
        # House 1 is the self/body/first-impression house — an overlay there
        # colors physical presence and initial draw, like an Ascendant contact.
        if h in (1, 5, 8):
            add(ATTRACTION, f"overlay into house {h}")
        if h == 4:
            add(EMOTIONAL, "overlay into house 4")
        if mover == "Moon":
            add(EMOTIONAL, "Moon overlay")
        if h in (3, 9):
            add(COMMUNICATION, f"overlay into house {h}")
        if mover == "Mercury":
            add(COMMUNICATION, "Mercury overlay")
        if h in (2, 6, 10):
            add(VALUES, f"overlay into house {h}")
        if h == 7:
            add(COMMITMENT, "overlay into house 7")
        if h in (9, 11, 12):
            add(PURPOSE, f"overlay into house {h}")
        if mover in OUTER_PLANETS:
            add(PURPOSE, f"{mover} (outer) overlay into personal house")

    # ---- RECEPTION -------------------------------------------------------
    elif interaction == "reception":
        pts = _reception_points(rec)
        receiver = b.get("receiver_point")
        received = b.get("received_point")
        syn = _syn(rec)
        # 1 Attraction: Venus<->Mars receptions.
        if pts & {"Venus", "Mars"}:
            add(ATTRACTION, "Venus/Mars reception")
        # 2 Emotional: Moon receptions.
        if "Moon" in pts:
            add(EMOTIONAL, "Moon reception")
        # 3 Communication: Mercury receptions.
        if "Mercury" in pts:
            add(COMMUNICATION, "Mercury reception")
        # 4 Friction: malefic-receiver; debilitated-receiver.
        if receiver in MALEFICS or syn.get("receiver_class") == "malefic":
            add(FRICTION, "malefic-receiver reception")
        if syn.get("receiver_debilitated") or b.get("receiver_debilitated"):
            add(FRICTION, "debilitated-receiver reception")
        # 5 Values/life: Venus/Jupiter/Saturn as either party.
        if pts & {"Venus", "Jupiter", "Saturn"}:
            add(VALUES, "Venus/Jupiter/Saturn reception")
        # 6 Commitment: Saturn; mutual receptions.
        if "Saturn" in pts:
            add(COMMITMENT, "Saturn reception")
        if b.get("mutual"):
            add(COMMITMENT, "mutual reception")
        # 7 Purpose: Jupiter reception.
        if "Jupiter" in pts:
            add(PURPOSE, "Jupiter reception")
        # Fallback so no surviving reception is left homeless: luminary receptions
        # about safety land in Emotional; anything else lands in Commitment (the
        # reception home per the routing table's "mutual receptions" emphasis).
        if not out:
            if pts & LUMINARIES:
                add(EMOTIONAL, "luminary reception (fallback)")
            else:
                add(COMMITMENT, "reception (fallback)")

    # ---- COMPATIBILITY ---------------------------------------------------
    elif interaction == "compatibility":
        factors = _compatibility_factors(rec)
        if "air" in factors:
            add(COMMUNICATION, "air compatibility")
        # earth / modality / sign compatibility -> shared-life values. Route any
        # non-air factor here so every surviving compatibility record has a home.
        if factors - {"air"}:
            add(VALUES, f"compatibility factors {sorted(factors - {'air'})}")
        if not out:
            add(VALUES, "compatibility (fallback)")

    return out


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class RoutingResult:
    sections: dict[str, list[RoutedRecord]]
    section_order: list[str]                 # profile's [opener] + axes, in order
    reading_type: str = "general"
    floor_drops: list[dict] = field(default_factory=list)
    context_drops: list[dict] = field(default_factory=list)
    overflow_drops: list[dict] = field(default_factory=list)
    unrouted: list[dict] = field(default_factory=list)
    houses_valid: bool = True
    record_index: dict[str, dict] = field(default_factory=dict)

    def non_empty(self) -> dict[str, list[RoutedRecord]]:
        """Sections with ≥1 record, in the profile's canonical order. Empty axes
        are omitted (§4.3: never padded)."""
        return {k: self.sections[k]
                for k in self.section_order if self.sections.get(k)}

    def routed_ids(self) -> dict[str, set[str]]:
        return {
            k: {r.record_id for r in recs}
            for k, recs in self.sections.items() if recs
        }

    def report(self) -> dict:
        return {
            "reading_type": self.reading_type,
            "houses_valid": self.houses_valid,
            "section_counts": {
                k: len(self.sections.get(k, [])) for k in self.section_order
            },
            "sections": {
                k: [r.as_report_dict() for r in self.sections.get(k, [])]
                for k in self.section_order if self.sections.get(k)
            },
            "context_drops": self.context_drops,
            "floor_drops": self.floor_drops,
            "overflow_drops": self.overflow_drops,
            "unrouted": self.unrouted,
            "record_index": self.record_index,
        }


# ---------------------------------------------------------------------------
# Opener selection (§3 section 0) — per-person natal partnering material.
# ---------------------------------------------------------------------------

# Relationship-load-bearing points, to prioritise which person records feed the
# opener when there are more than the cap.
_OPENER_PRIORITY_POINTS = {"Venus", "Moon", "Mars", "Sun", "Descendant"}


def _opener_weight(rec: dict) -> float:
    """Light priority for opener records: relational significators and role/dignity
    lines lead; generic methodology trails."""
    b = _bound(rec)
    syn = _syn(rec)
    w = 0.3
    if b.get("point") in _OPENER_PRIORITY_POINTS:
        w += 0.4
    if syn.get("relational_role"):
        w += 0.2
    if b.get("factor_type") == "dignity" or syn.get("factor_type") == "dignity":
        w += 0.1
    if b.get("factor_type") in ("planet_in_sign", "planet_in_house"):
        w += 0.1
    return w


def _select_opener(person_recs: list[dict], person: str,
                   admit=None) -> list[RoutedRecord]:
    pool = [r for r in person_recs if admit is None or admit(r)]
    ranked = sorted(pool, key=_opener_weight, reverse=True)
    out: list[RoutedRecord] = []
    for rec in ranked[:OPENER_CAP_PER_PERSON]:
        pid = rec.get("principle_id", "<no-id>")
        out.append(RoutedRecord(
            # Person prefix guarantees opener uids never collide with a synastry
            # uid and stay distinct across the two people.
            record_id=f"{person}:{pid}",
            principle_id=pid,
            interaction=_interaction(rec) or "natal_relational",
            bound_statement=rec.get("bound_statement") or rec.get("rule") or "",
            bound=_bound(rec),
            topic_tags=list(rec.get("topic_tags") or []),
            weight=_opener_weight(rec),
            person=person,
            reasons=[f"opener:{person}"],
        ))
    return out


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _carrier(rec: dict, reasons: list[str], uid: str) -> RoutedRecord:
    return RoutedRecord(
        record_id=uid,
        principle_id=rec.get("principle_id", "<no-id>"),
        interaction=_interaction(rec),
        bound_statement=rec.get("bound_statement") or "",
        bound=_bound(rec),
        topic_tags=list(rec.get("topic_tags") or []),
        weight=weight_of(rec),
        reasons=reasons,
    )


def route(payload: dict, profile=None, *,
          houses_valid: Optional[bool] = None) -> RoutingResult:
    """Filter by context (§2), apply the floor (§4.1), route the survivors to the
    profile's axes (§4.2), order (profile emphasis, §4) and cap each (§4.3), and
    build the opener from person material.

    ``profile`` is an ``s3_profiles.Profile``; if omitted the GENERAL profile is
    used (base-spec behaviour). ``payload`` is the parsed grounded file. If
    ``houses_valid`` is not given it is inferred from whether any house_overlay
    record survived grounding (they are absent when birth times are not exact)."""
    if profile is None:                       # lazy import avoids an import cycle
        from s3_profiles import GENERAL
        profile = GENERAL

    synastry = payload.get("synastry") or []
    person_a = payload.get("person_a") or []
    person_b = payload.get("person_b") or []

    if houses_valid is None:
        houses_valid = any(_interaction(r) == "house_overlay" for r in synastry)

    admit_set = profile.admitted_contexts

    def admit(rec: dict) -> bool:
        ctx = set((_syn(rec).get("contexts")) or ["universal"])
        return bool(ctx & admit_set)

    sections: dict[str, list[RoutedRecord]] = {k: [] for k in profile.axis_keys}
    floor_drops: list[dict] = []
    context_drops: list[dict] = []
    overflow_drops: list[dict] = []
    unrouted: list[dict] = []
    record_index: dict[str, dict] = {}
    seen_uids: set[str] = set()

    def unique_uid(rec: dict) -> str:
        uid = fact_uid(rec)
        if uid in seen_uids:
            n = 2
            while f"{uid}#{n}" in seen_uids:
                n += 1
            uid = f"{uid}#{n}"
        seen_uids.add(uid)
        return uid

    for rec in synastry:
        uid = unique_uid(rec)
        record_index[uid] = {
            "principle_id": rec.get("principle_id", "<no-id>"),
            "interaction": _interaction(rec),
            "contexts": _syn(rec).get("contexts"),
            "bound": _bound(rec),
        }
        # 1) context eligibility filter (§2) — before the noise floor.
        if not admit(rec):
            context_drops.append({
                "record_id": uid,
                "interaction": _interaction(rec),
                "contexts": _syn(rec).get("contexts"),
                "reason": "context_ineligible",
            })
            continue
        # 2) noise floor (§4.1).
        reason = below_floor(rec)
        if reason:
            floor_drops.append({
                "record_id": uid,
                "principle_id": rec.get("principle_id", "<no-id>"),
                "interaction": _interaction(rec),
                "reason": reason,
            })
            continue
        # 3) route to the profile's axes (§4.2).
        placements = profile.route(rec)
        if not placements:
            unrouted.append({
                "record_id": uid,
                "interaction": _interaction(rec),
                "bound": _bound(rec),
            })
            continue
        emph = profile.emphasis_delta(rec)
        per_section: dict[str, list[str]] = {}
        for sec, why in placements:
            per_section.setdefault(sec, []).append(why)
        for sec, reasons in per_section.items():
            if sec not in sections:            # guard against a stray key
                continue
            carrier = _carrier(rec, reasons, uid)
            carrier.weight = round(carrier.weight + emph, 4)
            sections[sec].append(carrier)

    # Order by weight (strongest first) and cap; overflow -> report (§4.3).
    for sec in profile.axis_keys:
        recs = sorted(sections[sec], key=lambda r: r.weight, reverse=True)
        kept, overflow = recs[:SECTION_CAP], recs[SECTION_CAP:]
        sections[sec] = kept
        for r in overflow:
            overflow_drops.append({
                "record_id": r.record_id, "section": sec,
                "weight": round(r.weight, 3), "reason": "section_cap",
            })

    # Opener (context-filtered, not floored/routed by content; capped per person).
    opener = (_select_opener(person_a, "A", admit)
              + _select_opener(person_b, "B", admit))
    sections[profile.opener_key] = opener

    return RoutingResult(
        sections=sections,
        section_order=profile.section_order,
        reading_type=profile.reading_type,
        floor_drops=floor_drops,
        context_drops=context_drops,
        overflow_drops=overflow_drops,
        unrouted=unrouted,
        houses_valid=houses_valid,
        record_index=record_index,
    )
