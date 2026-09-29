#!/usr/bin/env python3
"""
l4_routing.py — principle -> section routing (L4_INTERPRETATION_SPEC.md §3).

Deterministic. Each grounded principle is assigned to one or more sections off
its ``about`` block plus chart-derived occupancy/rulership. Overlap ACROSS
sections is allowed and intended (§3) — it is reconciled later in synthesis
(§5), never deduped here. The only collapsing done here is WITHIN a single
section: the same principle reaching one section by two paths is merged into one
carrier (passing an identical principle twice to a section call is pointless),
and the strongest texture wins (a primary path overrides a classical one).

House policy (§3.0, locked): every house in the reading is **Placidus**. The
grounding gate has already verified each house claim against the Placidus
placement, so a record's declared ``house_system`` is provenance only — the
router never branches on it and no record is "classical texture" merely for
coming from a whole-sign book. ``texture: classical`` remains for dignities and
house-lord-relative material (classical apparatus by construction).
Occupancy/rulership cross-routing uses the ``placidus`` sector and BOTH the
traditional ruler and the modern co-ruler of each cusp (§3.0).

Movement 2 is one section per house. The two luminaries additionally feed a
short dedicated "by house" note each (``sun_house`` / ``moon_house``).

``route(kept, chart)`` returns a ``RoutingResult``: the per-section carriers in
canonical order, plus a drop log for records the rules cannot home (§3.2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from l4_sections import (
    CHART_SHAPE,
    CORE_IDENTITY,
    HOUSE_DOMAIN,
    IDENTITY,
    INNER_DRIVES,
    LUMINARY_HOUSE_SECTION,
    PLANETS,
    POINT_HOME,
    SECTION_HOUSE,
    SECTION_ORDER,
    STATUS_VOCATION,
    RoutedPrinciple,
)

# factor_types that are classical apparatus by construction (§3.1.4, §3.1.10,
# §4): dignities and house-lord-relative read as texture wherever they land.
_INHERENTLY_CLASSICAL = {"dignity", "house_lord_relative"}

# Personal planets — for the aspect "both endpoints personal -> inner_drives"
# rule (§3.1.6).
_PERSONAL = {"Sun", "Moon", "Mercury", "Venus", "Mars"}

# --- §3.1.11 general sub-routing tag vocabularies (lower-case, exact-tag match
# unless noted). The ladder is first-match-wins; default is chart_shape. ---
_TAG_CHART_RULER = {"ascendant ruler", "chart ruler", "ruling planet"}
_TAG_MC = {"midheaven", "mc", "mc ruler", "midheaven ruler"}
# Any of the ten planets named as a tag (outer planets included: modern
# astrology reads Uranus / Neptune / Pluto as personal factors by house).
_TAG_PLANETS = {p.lower(): p for p in PLANETS}
_LORD_OF_HOUSE_RE = re.compile(r"lord of\s+(\d+)\s*(?:st|nd|rd|th)?\s+house")


# ---------------------------------------------------------------------------
# Chart access helpers (§3.0). points is a LIST keyed by name (chart_types.py).
# ---------------------------------------------------------------------------

def _point_index(chart: dict) -> dict[str, dict]:
    return {p["name"]: p for p in chart.get("points", [])}


def chart_ruler(chart: dict) -> Optional[str]:
    """The Ascendant ruler = the placidus 1st-house (traditional) ruler (§3.0).
    Resolved from ``sector_rulers``; the locked placidus rule governs the spine."""
    rulers = (chart.get("sector_rulers") or {}).get("placidus") or {}
    block = rulers.get("1")
    return block.get("ruler") if block else None


def chart_rulers(chart: dict) -> set[str]:
    """Every chart ruler: the traditional 1st-house ruler plus its modern
    co-ruler when the rising sign has one (Pluto / Uranus / Neptune)."""
    rulers = (chart.get("sector_rulers") or {}).get("placidus") or {}
    block = rulers.get("1") or {}
    return {r for r in (block.get("ruler"), block.get("modern_ruler")) if r}


def house_of(point: str, pts: dict[str, dict]) -> Optional[int]:
    """Placidus sector a point occupies (§3.0)."""
    p = pts.get(point)
    if not p:
        return None
    return (p.get("sector") or {}).get("placidus")


def houses_ruled(point: str, chart: dict) -> list[int]:
    """Houses this point rules under placidus (§3.0) — as traditional ruler OR
    as the modern co-ruler of the cusp sign."""
    rulers = (chart.get("sector_rulers") or {}).get("placidus") or {}
    out: list[int] = []
    for h_str, block in rulers.items():
        if point in (block.get("ruler"), block.get("modern_ruler")):
            try:
                out.append(int(h_str))
            except (TypeError, ValueError):
                continue
    return sorted(out)


def section_for_point(point: str, chart: dict) -> set[str]:
    """Movement-1 home(s) of a point (§3.0). A point can have more than one
    home: a chart ruler (traditional ruler or modern co-ruler of the Ascendant)
    belongs to BOTH ``core_identity`` (spine) and its own planet home."""
    homes: set[str] = set()
    base = POINT_HOME.get(point)
    if base:
        homes.add(base)
    if point and point in chart_rulers(chart):
        homes.add(CORE_IDENTITY)
    return homes


def domain_section_for_house(house: Optional[int]) -> Optional[str]:
    """Movement-2 home of a house number (§3.0): one section per house."""
    if house is None:
        return None
    return HOUSE_DOMAIN.get(int(house))


def section_houses(chart: dict) -> dict[str, int]:
    """House number carried by each section in the output (§6 ``house``): the
    house sections' own number, and the luminary notes' actual Placidus house."""
    pts = _point_index(chart)
    out: dict[str, int] = dict(SECTION_HOUSE)
    for point, sec in LUMINARY_HOUSE_SECTION.items():
        h = house_of(point, pts)
        if h is not None:
            out[sec] = int(h)
    return out


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class RoutingResult:
    sections: dict[str, list[RoutedPrinciple]]
    drops: list[dict] = field(default_factory=list)

    def non_empty(self) -> dict[str, list[RoutedPrinciple]]:
        """Sections with at least one principle, in canonical order. Empty
        sections are omitted entirely (§2 note, §7.4)."""
        return {
            k: self.sections[k]
            for k in SECTION_ORDER
            if self.sections.get(k)
        }

    def low_salience_ids(self) -> set[str]:
        """principle_ids flagged low-salience anywhere they were routed (§5.5:
        synthesis prunes these from chart_shape first)."""
        out: set[str] = set()
        for routed in self.sections.values():
            for rp in routed:
                if rp.is_low_salience:
                    out.add(rp.principle_id)
        return out

    def report(self) -> dict:
        return {
            "section_counts": {
                k: len(self.sections.get(k, [])) for k in SECTION_ORDER
            },
            "low_salience": sorted(self.low_salience_ids()),
            "dropped": len(self.drops),
            "drop_log": self.drops,
        }


# ---------------------------------------------------------------------------
# Routing accumulator
# ---------------------------------------------------------------------------

class _Router:
    def __init__(self, chart: dict):
        self.chart = chart
        self.pts = _point_index(chart)
        # section -> principle_id -> RoutedPrinciple (within-section merge).
        self._sections: dict[str, dict[str, RoutedPrinciple]] = {
            k: {} for k in SECTION_ORDER
        }
        self.drops: list[dict] = []

    def emit(self, section: Optional[str], rec: dict, *,
             classical: bool, reason: str, low_salience: bool = False) -> None:
        """Place ``rec`` into ``section`` (or no-op if section is None). Merges
        on principle_id; a primary (non-classical) path clears a prior classical
        texture, and a normal-salience path clears a prior low-salience flag
        (here we keep the strongest carrier; §5 conflict precedence is downstream)."""
        if section is None or section not in self._sections:
            return
        ft = (rec.get("about") or {}).get("factor_type")
        classical = classical or ft in _INHERENTLY_CLASSICAL
        pid = rec.get("principle_id", "<no-id>")
        bucket = self._sections[section]
        existing = bucket.get(pid)
        if existing is None:
            bucket[pid] = RoutedPrinciple(
                principle_id=pid,
                tradition=rec.get("tradition"),
                rule=rec.get("rule"),
                topic_tags=list(rec.get("topic_tags") or []),
                about=rec.get("about") or {},
                requires=list(rec.get("requires") or []),
                texture="classical" if classical else None,
                salience="low" if low_salience else None,
                reasons=[reason],
            )
        else:
            existing.reasons.append(reason)
            if not classical:
                existing.texture = None  # primary path wins over texture
            if not low_salience:
                existing.salience = None  # normal path wins over low-salience

    def drop(self, rec: dict, reason: str) -> None:
        self.drops.append({
            "principle_id": rec.get("principle_id", "<no-id>"),
            "reason": reason,
            "about": rec.get("about") or {},
        })

    def result(self) -> RoutingResult:
        sections = {
            k: list(self._sections[k].values()) for k in SECTION_ORDER
        }
        return RoutingResult(sections=sections, drops=self.drops)


# ---------------------------------------------------------------------------
# Subject points of a record (drive occupancy/rulership cross-routing, §3.0)
# ---------------------------------------------------------------------------

def _subject_points(about: dict) -> list[str]:
    ft = about.get("factor_type")
    if ft == "aspect":
        a = about.get("aspect") or {}
        return [p for p in (a.get("source"), a.get("target")) if p]
    if ft in ("planet_in_sign", "planet_in_house", "planet_in_sign_and_house",
              "dignity", "node", "house_ruler"):
        p = about.get("point")
        return [p] if p else []
    if ft == "house_domain" and about.get("point") is not None:
        return [about["point"]]
    return []


# ---------------------------------------------------------------------------
# §3.1 factor_type routing
# ---------------------------------------------------------------------------

def _route_by_factor_type(r: _Router, rec: dict) -> bool:
    """Apply §3.1 rules 1-11. Returns True if the record was routed by a typed
    rule, False if it falls through to the §3.2 fallback."""
    about = rec.get("about") or {}
    ft = about.get("factor_type")
    chart = r.chart

    def point_homes(point: str, reason: str, *, classical: bool = False) -> None:
        for sec in section_for_point(point, chart):
            r.emit(sec, rec, classical=classical, reason=reason)

    # 1. planet_in_sign -> section_for_point(point)
    if ft == "planet_in_sign":
        point_homes(about.get("point"), "planet_in_sign -> point home")
        return True

    # 2 & 3. planet_in_house / planet_in_sign_and_house -> point home AND domain.
    #    A luminary's house record feeds its short "by house" note instead of
    #    core_identity (which reads the luminaries by sign).
    if ft in ("planet_in_house", "planet_in_sign_and_house"):
        point = about.get("point")
        lum = LUMINARY_HOUSE_SECTION.get(point)
        if lum:
            r.emit(lum, rec, classical=False,
                   reason=f"{ft} -> {lum} (luminary by house)")
        if not lum or ft == "planet_in_sign_and_house":
            point_homes(point, f"{ft} -> point home")
        dom = domain_section_for_house(about.get("house"))
        r.emit(dom, rec, classical=False,
               reason=f"{ft} -> domain h{about.get('house')}")
        return True

    # 4. dignity -> section_for_point(point), classical
    if ft == "dignity":
        point_homes(about.get("point"), "dignity -> point home", classical=True)
        return True

    # 5. node -> section_for_point(point) AND domain if house present
    if ft == "node":
        point_homes(about.get("point"), "node -> point home")
        if "house" in about:
            dom = domain_section_for_house(about.get("house"))
            r.emit(dom, rec, classical=False,
                   reason=f"node -> domain h{about.get('house')}")
        return True

    # 6. aspect -> for each endpoint: point home AND its placidus-house domain;
    #    if both endpoints personal also inner_drives; informs chart_shape.
    if ft == "aspect":
        a = about.get("aspect") or {}
        endpoints = [a.get("source"), a.get("target")]
        for ep in endpoints:
            if not ep:
                continue
            point_homes(ep, f"aspect endpoint {ep} -> point home")
            dom = domain_section_for_house(house_of(ep, r.pts))
            r.emit(dom, rec, classical=False,
                   reason=f"aspect endpoint {ep} -> occupied domain")
        if all(ep in _PERSONAL for ep in endpoints if ep):
            r.emit(INNER_DRIVES, rec, classical=False,
                   reason="aspect both endpoints personal -> inner_drives")
        r.emit(CHART_SHAPE, rec, classical=False,
               reason="aspect -> configuration (chart_shape)")
        return True

    # 7. ascendant -> core_identity AND identity_body (H1)
    if ft == "ascendant":
        r.emit(CORE_IDENTITY, rec, classical=False,
               reason="ascendant -> core_identity")
        r.emit(IDENTITY, rec, classical=False,
               reason="ascendant -> identity (H1)")
        return True

    # 8. house_ruler -> domain AND point home
    if ft == "house_ruler":
        dom = domain_section_for_house(about.get("house"))
        r.emit(dom, rec, classical=False,
               reason=f"house_ruler -> domain h{about.get('house')}")
        point_homes(about.get("point"), "house_ruler -> point home")
        return True

    # 9. house_domain — polymorphic (§3.1.9)
    if ft == "house_domain":
        if about.get("point") is not None:
            # element-of-sign character: Movement 1, the point's home.
            point_homes(about.get("point"),
                        "house_domain(point) -> point home")
            return True
        if "house" in about:
            h = about.get("house")
            dom = domain_section_for_house(h)
            r.emit(dom, rec, classical=False,
                   reason=f"house_domain(house) -> domain h{h}")
            # The house's meaning also grounds the short note of any luminary
            # sitting in it (§3.1.9).
            for lum_point, lum_sec in LUMINARY_HOUSE_SECTION.items():
                if house_of(lum_point, r.pts) == h:
                    r.emit(lum_sec, rec, classical=False,
                           reason=f"house_domain(house) -> {lum_sec} "
                                  f"({lum_point} occupies h{h})")
            return True
        return False  # neither key present -> fallback

    # 10. house_lord_relative -> ruled (subject_house) domain, classical
    if ft == "house_lord_relative":
        dom = domain_section_for_house(about.get("subject_house"))
        r.emit(dom, rec, classical=True,
               reason=f"house_lord_relative -> subject_house "
                      f"{about.get('subject_house')} domain")
        return True

    # 11. general -> sub-route by topic_tags (§3.1.11), first match wins.
    if ft == "general":
        _route_general(r, rec)
        return True

    return False


def _route_general(r: _Router, rec: dict) -> None:
    """§3.1.11 priority ladder for the heterogeneous `general` slice. First match
    wins; default is chart_shape. A kept general record is NEVER dropped."""
    about = rec.get("about") or {}
    tags = {str(t).lower() for t in (rec.get("topic_tags") or [])}
    conf = about.get("extraction_confidence")
    chart = r.chart

    # rung 1 — chart-ruler / ascendant-ruler material -> core_identity
    if tags & _TAG_CHART_RULER:
        r.emit(CORE_IDENTITY, rec, classical=False,
               reason="general(tags: chart ruler) -> core_identity")
        return

    # rung 2 — Midheaven / MC material -> vocation_public
    if tags & _TAG_MC:
        r.emit(STATUS_VOCATION, rec, classical=False,
               reason="general(tags: MC) -> status_vocation (H10)")
        return

    # rung 3 — a specific house lord ("lord of Nth house") -> that domain
    lord_houses = sorted({
        int(m.group(1))
        for t in tags
        for m in [_LORD_OF_HOUSE_RE.search(t)]
        if m and 1 <= int(m.group(1)) <= 12
    })
    if lord_houses:
        for h in lord_houses:
            r.emit(domain_section_for_house(h), rec, classical=False,
                   reason=f"general(tags: lord of {h}) -> domain h{h}")
        return

    # rung 4 — one or two specific planets named (any of the ten; the outer
    # planets are personal factors in the modern reading, never mere backdrop)
    # -> each planet's Movement-1 home AND the house it occupies / rules, so
    # e.g. "Pluto" material lands in the section of the house Pluto sits in.
    # Naming three or more planets signals class-level methodology, which falls
    # through to the default bucket.
    named = sorted({_TAG_PLANETS[t] for t in tags if t in _TAG_PLANETS})
    if 1 <= len(named) <= 2:
        for p in named:
            for sec in section_for_point(p, chart):
                r.emit(sec, rec, classical=False,
                       reason=f"general(tags: {p}) -> point home")
            _emit_point_domains(r, rec, p, classical=False,
                                tag=f"general(tags: {p})")
        return

    # default — interpretive methodology / whole-chart weighting -> chart_shape.
    # Low-confidence defaults are low-salience so synthesis prunes them first.
    r.emit(CHART_SHAPE, rec, classical=False,
           low_salience=(conf == "low"),
           reason="general(default) -> chart_shape")


def _emit_point_domains(r: _Router, rec: dict, point: str, *,
                        classical: bool, tag: str) -> None:
    """Route ``rec`` to the section of the house ``point`` occupies (placidus)
    and of every house it rules (traditional ruler or modern co-ruler)."""
    occ = domain_section_for_house(house_of(point, r.pts))
    r.emit(occ, rec, classical=classical,
           reason=f"{tag} occupancy: {point} occupies domain")
    for h in houses_ruled(point, r.chart):
        r.emit(domain_section_for_house(h), rec, classical=classical,
               reason=f"{tag} rulership: {point} rules h{h} domain")


def _route_occupancy(r: _Router, rec: dict) -> None:
    """§3.0 point-occupancy & rulership: for each subject point of the record,
    also route it to the section of the house it occupies (placidus) and to the
    section of every house it rules. Inherently-classical records stay classical;
    everything else is primary."""
    about = rec.get("about") or {}
    ft = about.get("factor_type")
    classical = ft in _INHERENTLY_CLASSICAL
    for p in _subject_points(about):
        _emit_point_domains(r, rec, p, classical=classical, tag="chart")


# ---------------------------------------------------------------------------
# §3.2 fallback
# ---------------------------------------------------------------------------

def _route_fallback(r: _Router, rec: dict) -> None:
    about = rec.get("about") or {}
    ft = about.get("factor_type")
    conf = about.get("extraction_confidence")
    if ft == "unclassified":
        if conf in ("high", "medium"):
            r.emit(CHART_SHAPE, rec, classical=False, low_salience=True,
                   reason=f"unclassified ({conf}) -> chart_shape (low-salience)")
        else:
            r.drop(rec, f"unclassified low-confidence ({conf}) dropped (§3.2)")
        return
    r.drop(rec, f"no routing rule matched factor_type={ft!r} (§3.2)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def route(kept: list[dict], chart: dict) -> RoutingResult:
    """Route this chart's kept grounded principles into sections (§3)."""
    r = _Router(chart)
    for rec in kept:
        routed = _route_by_factor_type(r, rec)
        if routed:
            _route_occupancy(r, rec)
        else:
            _route_fallback(r, rec)
    return r.result()
