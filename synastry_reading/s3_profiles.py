#!/usr/bin/env python3
"""
s3_profiles.py — the reading-type fork (SYNASTRY_READING_PROFILES.md).

Supersedes base-spec §3 (section structure) and §4 (routing/floor) and
parameterizes them by ``reading_type ∈ {general, personal, professional}``. A
``Profile`` bundles everything that differs by type: which contexts it admits
(§2), its section keys/order/themes/titles, the interpretive stance and
per-section lens that reframe universal records (§3), the significator emphasis
that reweights ordering (§4), and its routing function.

Everything else — generation architecture, no-score, attribution, mask,
precision, invariants, artifacts — is unchanged from the base spec and lives in
the other modules, driven by the active ``Profile``.

Imports the low-level record accessors from ``s3_routing`` one-directionally
(``s3_routing`` never imports this module — ``route()`` there duck-types the
profile), so there is no import cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from s3_routing import (
    _HARD_ASPECTS,
    _aspect_points,
    _bound,
    _compatibility_factors,
    _interaction,
    _reception_points,
    _syn,
    route_sections,  # the personal/general content router (base-spec §4.2)
)
from s3_sections import (
    MALEFICS,
    OUTER_PLANETS,
    WHAT_EACH_BRINGS,
    is_significator,
)

READING_TYPES = ("general", "personal", "professional")
DEFAULT_READING_TYPE = "general"

# Context admission per type (§2). general admits everything.
_ADMITS = {
    "general": {"universal", "personal", "professional"},
    "personal": {"universal", "personal"},
    "professional": {"universal", "professional"},
}


def admits(profile_admits: set[str], rec: dict) -> bool:
    """True if this record's contexts intersect the profile's admitted set (§2).
    A record with no contexts tag is treated as universal (fail-open, so an
    untagged record is never silently lost)."""
    ctx = set((_syn(rec).get("contexts")) or ["universal"])
    return bool(ctx & profile_admits)


# ---------------------------------------------------------------------------
# Profile container
# ---------------------------------------------------------------------------

@dataclass
class Profile:
    reading_type: str
    axis_keys: list[str]                     # the 7 axes, in order
    themes: dict[str, str]                   # key -> model-facing theme
    titles: dict[str, dict[str, str]]        # key -> {tr, en} render title
    doc_title: dict[str, str]                # {tr, en}
    stance: str                              # injected into the _CONTRACT (§3)
    lens: dict[str, str]                     # key -> per-section lens instruction
    emphasis_points: dict[str, float] = field(default_factory=dict)
    emphasis_houses: dict[int, float] = field(default_factory=dict)
    house_dependent_axes: set[str] = field(default_factory=set)
    route_fn: Callable[[dict], list] = route_sections
    admitted_contexts: set[str] = field(default_factory=lambda: set(_ADMITS["general"]))
    opener_key: str = WHAT_EACH_BRINGS

    @property
    def section_order(self) -> list[str]:
        return [self.opener_key] + self.axis_keys

    @property
    def movement(self) -> dict[str, int]:
        m = {self.opener_key: 0}
        for i, k in enumerate(self.axis_keys, 1):
            m[k] = i
        return m

    def route(self, rec: dict) -> list:
        return self.route_fn(rec)

    def emphasis_delta(self, rec: dict) -> float:
        """Ordering nudge (§4): emphasized points/houses lead, de-emphasized sink.
        Never drops a record (the base floor already did that) — only reorders
        within a section."""
        d = 0.0
        it = _interaction(rec)
        b = _bound(rec)
        pts: set[str] = set()
        houses: set[int] = set()
        if it == "aspect":
            pts = _aspect_points(rec)
        elif it == "reception":
            pts = _reception_points(rec)
        elif it == "house_overlay":
            if b.get("mover_point"):
                pts = {b["mover_point"]}
            if b.get("home_house"):
                houses = {b["home_house"]}
        for p in pts:
            d += self.emphasis_points.get(p, 0.0)
        for h in houses:
            d += self.emphasis_houses.get(h, 0.0)
        return d


# ===========================================================================
# GENERAL (§4.1) — no emphasis, holistic. Routing == personal, relabeled.
# ===========================================================================

_GEN_KEYS = ["rapport", "emotional_dynamics", "communication",
             "friction", "values", "support_trust", "direction"]

# personal-router key -> general key
_PERSONAL_TO_GENERAL = {
    "attraction": "rapport",
    "emotional": "emotional_dynamics",
    "communication": "communication",
    "friction": "friction",
    "values": "values",
    "commitment": "support_trust",
    "purpose": "direction",
}


def _route_general(rec: dict) -> list:
    out = []
    for sec, why in route_sections(rec):
        out.append((_PERSONAL_TO_GENERAL[sec], why))
    return out


GENERAL = Profile(
    reading_type="general",
    axis_keys=_GEN_KEYS,
    themes={
        WHAT_EACH_BRINGS:
            "The standing ground each person walks in with: their own natal "
            "capacity to connect — how each one relates, needs, and bonds — BEFORE "
            "the two charts are compared. One short paragraph per person; NOT a "
            "compatibility claim about the pair.",
        "rapport": "Overall rapport and how the two meet — the shape of the "
                   "connection as a whole, sphere-agnostic.",
        "emotional_dynamics": "Emotional dynamics: how feeling and mood move "
                              "between them.",
        "communication": "Communication and the meeting of minds.",
        "friction": "Friction and tension: where the two grind or challenge each "
                    "other.",
        "values": "Values and shared ground: what they hold in common.",
        "support_trust": "Support, reliability and trust: whether they can lean "
                         "on each other.",
        "direction": "Shared direction: where the connection points them over "
                     "time.",
    },
    titles={
        WHAT_EACH_BRINGS: {"tr": "Her Biri Ne Getiriyor", "en": "What Each Brings"},
        "rapport": {"tr": "Genel Uyum ve Buluşma", "en": "Overall Rapport"},
        "emotional_dynamics": {"tr": "Duygusal Dinamikler", "en": "Emotional Dynamics"},
        "communication": {"tr": "İletişim ve Zihin", "en": "Communication & Mind"},
        "friction": {"tr": "Sürtüşme ve Gerilim", "en": "Friction & Tension"},
        "values": {"tr": "Değerler ve Ortak Zemin", "en": "Values & Shared Ground"},
        "support_trust": {"tr": "Destek, Güven ve İstikrar",
                          "en": "Support, Reliability & Trust"},
        "direction": {"tr": "Ortak Yön", "en": "Shared Direction"},
    },
    doc_title={"tr": "İLİŞKİ YORUMU", "en": "RELATIONSHIP READING"},
    stance=(
        "READING TYPE: GENERAL — the connection as a whole. Interpret each "
        "contact at face value for the bond between these two people; assume "
        "NEITHER romance NOR business. Do not push a contact toward desire, nor "
        "toward work and contracts. Read it as the plain human connection it is."
    ),
    lens={},   # face-value: no per-section reframing
    house_dependent_axes={"emotional_dynamics", "values", "direction"},
    admitted_contexts=set(_ADMITS["general"]),
    route_fn=_route_general,
)


# ===========================================================================
# PERSONAL (§4.2) — the base-spec §3 sections. Routing == base route_sections.
# ===========================================================================

_PER_KEYS = ["attraction", "emotional", "communication",
             "friction", "values", "commitment", "purpose"]

_PERSONAL_LENS_COMMON = (
    "Read this universal contact through a ROMANTIC / life-partnership lens: what "
    "it means for closeness, desire, safety, and long-term bonding between the two."
)

PERSONAL = Profile(
    reading_type="personal",
    axis_keys=_PER_KEYS,
    themes={
        WHAT_EACH_BRINGS:
            "The standing ground each person walks in with: their own natal "
            "capacity to partner — how each one loves, needs, and bonds — BEFORE "
            "the two charts are compared. One short paragraph per person; NOT a "
            "compatibility claim about the pair.",
        "attraction": "Attraction and chemistry: the spark, physical and romantic "
                      "pull, desire, the magnetic draw.",
        "emotional": "Emotional needs and security: how safe, held, and understood "
                     "each feels with the other.",
        "communication": "Communication and the meeting of minds.",
        "friction": "Friction and challenge: where the two grind, clash, or "
                    "frustrate each other.",
        "values": "Values, money, and shared life: what they treasure and how they "
                  "build a life.",
        "commitment": "Commitment and long-term viability: staying power, loyalty, "
                      "building something durable.",
        "purpose": "Shared purpose and growth: where the relationship stretches "
                   "them and how they grow through each other.",
    },
    titles={
        WHAT_EACH_BRINGS: {"tr": "Her Biri Ne Getiriyor",
                           "en": "What Each Brings to a Partnership"},
        "attraction": {"tr": "Çekim ve Kimya", "en": "Attraction & Chemistry"},
        "emotional": {"tr": "Duygusal İhtiyaçlar ve Güven",
                      "en": "Emotional Needs & Security"},
        "communication": {"tr": "İletişim ve Zihinlerin Buluşması",
                          "en": "Communication & the Meeting of Minds"},
        "friction": {"tr": "Sürtüşme ve Zorluk", "en": "Friction & Challenge"},
        "values": {"tr": "Değerler, Para ve Ortak Hayat",
                   "en": "Values, Money & Shared Life"},
        "commitment": {"tr": "Bağlılık ve Uzun Vade",
                       "en": "Commitment & Long-Term Viability"},
        "purpose": {"tr": "Ortak Amaç ve Büyüme", "en": "Shared Purpose & Growth"},
    },
    doc_title={"tr": "İLİŞKİ YORUMU — ROMANTİK", "en": "RELATIONSHIP READING — PERSONAL"},
    stance=(
        "READING TYPE: PERSONAL FOCUS — the two as intimate life partners. "
        "Romantic-first. Reframe every universal contact toward closeness, desire, "
        "emotional security, and long-term bonding. A structuring contact reads as "
        "commitment and staying power; a resource contact reads as building a "
        "shared life together."
    ),
    lens={k: _PERSONAL_LENS_COMMON for k in _PER_KEYS},
    emphasis_points={"Venus": 0.2, "Mars": 0.2, "Moon": 0.2, "Sun": 0.15},
    emphasis_houses={5: 0.2, 7: 0.2, 8: 0.2, 4: 0.15, 6: -0.15, 10: -0.15},
    house_dependent_axes={"emotional", "values", "purpose"},
    admitted_contexts=set(_ADMITS["personal"]),
    route_fn=route_sections,
)


# ===========================================================================
# PROFESSIONAL (§4.3) — bespoke section set + routing.
# ===========================================================================

_PRO_KEYS = ["working_rapport", "roles_leadership", "decision_making",
             "reliability", "money_resources", "conflict_style", "shared_goals"]


def _route_professional(rec: dict) -> list:
    """Route a synastry record to the professional axes (§4.3). Business set:
    Mars, Saturn, Mercury, Venus, Moon; houses 10, 6, 2, 11, 7. 7th and reception
    carry across per §5, reframed by lens."""
    it = _interaction(rec)
    b = _bound(rec)
    out: list[tuple[str, str]] = []

    def add(sec: str, why: str) -> None:
        out.append((sec, why))

    if it == "aspect":
        pts = _aspect_points(rec)
        atype = b.get("aspect")
        # 1 Working rapport: how they meet; personal chemistry noted (minor).
        if pts & {"Sun", "Moon", "Ascendant", "Descendant"}:
            add("working_rapport", "rapport contact (Sun/Moon/Asc/Desc)")
        if pts & {"Venus", "Mars"}:
            add("working_rapport", "personal chemistry (noted, minor)")
        # 2 Roles, leadership, division of labour: authority/drive.
        if pts & {"Sun", "Saturn", "Mars"}:
            add("roles_leadership", "authority/drive contact")
        if pts & {"Midheaven", "MC"}:
            add("roles_leadership", "Midheaven (standing) contact")
        # 3 Communication & decision-making.
        if "Mercury" in pts:
            add("decision_making", "Mercury contact")
        if "Moon" in pts:
            add("decision_making", "Moon (instinct in decisions)")
        # 4 Reliability & follow-through.
        if "Saturn" in pts:
            add("reliability", "Saturn (follow-through)")
        # 5 Money, resources & shared value.
        if pts & {"Venus", "Jupiter"}:
            add("money_resources", "Venus/Jupiter (value) contact")
        # 6 Conflict & friction style.
        if atype in _HARD_ASPECTS and any(is_significator(p) for p in pts):
            add("conflict_style", f"{atype} on significator(s)")
        if {"Mars", "Saturn"} <= pts:
            add("conflict_style", "Mars-Saturn contact")
        # 7 Shared goals & venture longevity.
        if pts & {"Jupiter", "North Node", "South Node"}:
            add("shared_goals", "Jupiter/Nodes (direction)")
        if pts & {"Midheaven", "MC"}:
            add("shared_goals", "Midheaven (goal/standing)")

    elif it == "house_overlay":
        h = b.get("home_house")
        mover = b.get("mover_point")
        if h in (1, 7):
            add("working_rapport", f"overlay into house {h}")
        if h == 10:
            add("roles_leadership", "overlay into house 10 (vocation)")
        if h in (3, 9):
            add("decision_making", f"overlay into house {h}")
        if mover == "Mercury":
            add("decision_making", "Mercury overlay")
        if h == 6:
            add("reliability", "overlay into house 6 (work/service)")
        if h in (2, 8):
            add("money_resources", f"overlay into house {h} (resources)")
        if h in (10, 11, 12):
            # 12th = the hidden, behind-the-scenes undercurrents of the venture.
            add("shared_goals", f"overlay into house {h}")
        if h == 7:
            add("shared_goals", "overlay into house 7 (partnership/contract)")
        if mover in OUTER_PLANETS:
            add("shared_goals", f"{mover} (outer) overlay")
        if not out:
            add("shared_goals", "overlay (fallback)")

    elif it == "reception":
        pts = _reception_points(rec)
        receiver = b.get("receiver_point")
        syn = _syn(rec)
        if "Saturn" in pts:
            add("reliability", "Saturn reception (dependable structure)")
        if pts & {"Venus", "Jupiter"}:
            add("money_resources", "Venus/Jupiter reception (value)")
        if "Mercury" in pts:
            add("decision_making", "Mercury reception")
        if pts & {"Moon"}:
            add("working_rapport", "Moon reception (instinctive rapport)")
        if receiver in MALEFICS or syn.get("receiver_class") == "malefic":
            add("conflict_style", "malefic-receiver reception")
        if syn.get("receiver_debilitated") or b.get("receiver_debilitated"):
            add("conflict_style", "debilitated-receiver reception")
        if b.get("mutual"):
            add("shared_goals", "mutual reception (durable partnership)")
        if not out:
            add("shared_goals", "reception (fallback)")

    elif it == "compatibility":
        factors = _compatibility_factors(rec)
        if "air" in factors:
            add("decision_making", "air compatibility")
        if "earth" in factors:
            add("reliability", "earth compatibility (dependable)")
            add("money_resources", "earth compatibility (material)")
        rest = factors - {"air", "earth"}
        if rest:
            add("money_resources", f"compatibility factors {sorted(rest)}")
        if not out:
            add("money_resources", "compatibility (fallback)")

    return out


_PRO_LENS_COMMON = (
    "Read this universal contact through a PROFESSIONAL / working-partnership "
    "lens: competence, dependability, authority, decision-making, and the "
    "durability of a shared venture. Personal chemistry, if it appears, is noted "
    "ONLY as something that may support or complicate the work — never the point. "
    "No romance, desire, or intimacy claims."
)

PROFESSIONAL = Profile(
    reading_type="professional",
    axis_keys=_PRO_KEYS,
    themes={
        WHAT_EACH_BRINGS:
            "The working capacity each person brings on their own — how each one "
            "operates, takes responsibility, and collaborates — BEFORE the two "
            "charts are compared. One short paragraph per person; NOT a "
            "compatibility claim about the pair. (This slice is lean by design.)",
        "working_rapport": "Working rapport and trust: how the two meet and "
                           "whether an easy working footing forms.",
        "roles_leadership": "Roles, leadership and division of labour: who leads, "
                            "who defers, how authority and load split.",
        "decision_making": "Communication and decision-making: how they exchange "
                           "information and reach calls together.",
        "reliability": "Reliability and follow-through: dependability, keeping "
                       "commitments, steady execution.",
        "money_resources": "Money, resources and shared value: financial "
                           "compatibility, shared assets, material judgment.",
        "conflict_style": "Conflict and friction style: how disputes arise and "
                          "how they get handled.",
        "shared_goals": "Shared goals and venture longevity: aligned aims and "
                        "whether the partnership endures.",
    },
    titles={
        WHAT_EACH_BRINGS: {"tr": "Her Biri Ne Getiriyor",
                           "en": "What Each Brings to a Working Partnership"},
        "working_rapport": {"tr": "Çalışma Uyumu ve Güven",
                            "en": "Working Rapport & Trust"},
        "roles_leadership": {"tr": "Roller, Liderlik ve İş Bölümü",
                             "en": "Roles, Leadership & Division of Labour"},
        "decision_making": {"tr": "İletişim ve Karar Alma",
                            "en": "Communication & Decision-Making"},
        "reliability": {"tr": "Güvenilirlik ve Takip",
                        "en": "Reliability & Follow-Through"},
        "money_resources": {"tr": "Para, Kaynaklar ve Ortak Değer",
                            "en": "Money, Resources & Shared Value"},
        "conflict_style": {"tr": "Çatışma ve Sürtüşme Tarzı",
                           "en": "Conflict & Friction Style"},
        "shared_goals": {"tr": "Ortak Hedefler ve Ortaklığın Ömrü",
                         "en": "Shared Goals & Venture Longevity"},
    },
    doc_title={"tr": "İLİŞKİ YORUMU — PROFESYONEL",
               "en": "RELATIONSHIP READING — PROFESSIONAL"},
    stance=(
        "READING TYPE: PROFESSIONAL FOCUS — the two as collaborators, co-founders, "
        "or colleagues. Reframe every universal contact toward competence, "
        "dependability, authority, decision-making, and venture durability. A "
        "structuring contact reads as accountability and dependable seniority, not "
        "romantic strain; a resource contact reads as joint finances and shared "
        "investment. Personal chemistry is noted only as something that may help or "
        "complicate the work. Contain NO romance, desire, or intimacy claims."
    ),
    lens={k: _PRO_LENS_COMMON for k in _PRO_KEYS},
    emphasis_points={"Mars": 0.2, "Saturn": 0.2, "Mercury": 0.15,
                     "Venus": 0.1, "Moon": 0.1},
    emphasis_houses={10: 0.2, 6: 0.2, 2: 0.15, 11: 0.15, 7: 0.1,
                     5: -0.2, 8: -0.1},
    house_dependent_axes={"roles_leadership", "reliability",
                          "money_resources", "shared_goals"},
    admitted_contexts=set(_ADMITS["professional"]),
    route_fn=_route_professional,
)


PROFILES: dict[str, Profile] = {
    "general": GENERAL,
    "personal": PERSONAL,
    "professional": PROFESSIONAL,
}


def get_profile(reading_type: str) -> Profile:
    if reading_type not in PROFILES:
        raise ValueError(
            f"reading_type must be one of {READING_TYPES}, got {reading_type!r}")
    return PROFILES[reading_type]
