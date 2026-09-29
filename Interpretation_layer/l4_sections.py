#!/usr/bin/env python3
"""
l4_sections.py — the section model (L4_INTERPRETATION_SPEC.md §2).

The section keys are a locked render contract (§0, §7.6). This module is the
single source of truth for them: their canonical render order, which movement
each belongs to, the theme description handed to the section call, and the
structural maps (point -> Movement-1 home, house -> Movement-2 section) the
router in ``l4_routing.py`` builds on.

Basis (since 2026-09-21): modern astrology. Houses are **Placidus only** (the
grounding gate verifies every house claim against the Placidus placement, see
ground.py). All ten planets are full participants — Uranus, Neptune and Pluto
included — plus the lunar nodes. Movement 2 is one section per house, in house
order, under the reader-facing names chosen for the app.

Domain values ("Sun", "Aries", …) are never renamed here; only structural keys
live in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# The sections, in canonical render order (§2).
# ---------------------------------------------------------------------------

# Movement 1 — structural portrait ("who you are").
CORE_IDENTITY = "core_identity"
SUN_HOUSE = "sun_house"          # short note: the Sun's Placidus house
MOON_HOUSE = "moon_house"        # short note: the Moon's Placidus house
INNER_DRIVES = "inner_drives"
CHART_SHAPE = "chart_shape"

# Movement 2 — one section per Placidus house ("where it lands").
IDENTITY = "identity"                              # H1
VALUES_MONEY = "values_money"                      # H2
COMMUNICATION_LEARNING = "communication_learning"  # H3
FAMILY_HOME = "family_home"                        # H4
JOY_CREATIVITY_CHILDREN = "joy_creativity_children"  # H5
HEALTH_ROUTINE_PETS = "health_routine_pets"        # H6
PARTNERSHIPS = "partnerships"                      # H7
TRANSFORMATION_INTIMACY = "transformation_intimacy"  # H8
TRAVEL_PHILOSOPHY = "travel_philosophy"            # H9
STATUS_VOCATION = "status_vocation"                # H10
FRIENDSHIPS_FUTURE = "friendships_future"          # H11
SUBCONSCIOUS_SOLITUDE = "subconscious_solitude"    # H12

MOVEMENT_1: list[str] = [CORE_IDENTITY, SUN_HOUSE, MOON_HOUSE, INNER_DRIVES, CHART_SHAPE]
MOVEMENT_2: list[str] = [
    IDENTITY, VALUES_MONEY, COMMUNICATION_LEARNING, FAMILY_HOME,
    JOY_CREATIVITY_CHILDREN, HEALTH_ROUTINE_PETS, PARTNERSHIPS,
    TRANSFORMATION_INTIMACY, TRAVEL_PHILOSOPHY, STATUS_VOCATION,
    FRIENDSHIPS_FUTURE, SUBCONSCIOUS_SOLITUDE,
]
SECTION_ORDER: list[str] = MOVEMENT_1 + MOVEMENT_2

MOVEMENT: dict[str, int] = {**{k: 1 for k in MOVEMENT_1}, **{k: 2 for k in MOVEMENT_2}}

# Movement-2 home of a house number (§2 map): one section per house.
HOUSE_DOMAIN: dict[int, str] = {i + 1: key for i, key in enumerate(MOVEMENT_2)}
# Inverse: house section -> its house number.
SECTION_HOUSE: dict[str, int] = {key: h for h, key in HOUSE_DOMAIN.items()}

# The two luminaries get a short dedicated "by house" note in Movement 1.
LUMINARY_HOUSE_SECTION: dict[str, str] = {"Sun": SUN_HOUSE, "Moon": MOON_HOUSE}
LUMINARY_OF_SECTION: dict[str, str] = {v: k for k, v in LUMINARY_HOUSE_SECTION.items()}

# The ten planets of modern astrology (all full participants) and the nodes.
PLANETS: tuple[str, ...] = ("Sun", "Moon", "Mercury", "Venus", "Mars",
                            "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")
OUTER_PLANETS: tuple[str, ...] = ("Uranus", "Neptune", "Pluto")
NODES: tuple[str, ...] = ("North Node", "South Node")

# Theme handed to each section call (§2, §4). English: this is instruction to
# the model, not reader-facing text.
SECTION_THEME: dict[str, str] = {
    CORE_IDENTITY: (
        "The spine of the chart: the Sun and the Moon by sign, the Ascendant, and "
        "the chart ruler(s) — the ruler of the 1st house, with its modern co-ruler "
        "when the rising sign has one. The luminaries plus the chart ruler as the "
        "core of who the native is. (The luminaries' HOUSE placements have their "
        "own short sections; do not treat them fully here.)"
    ),
    SUN_HOUSE: (
        "A short dedicated note: the Sun's house placement (Placidus). What it "
        "means that the person's identity, vitality and sense of purpose are "
        "focused in this life area."
    ),
    MOON_HOUSE: (
        "A short dedicated note: the Moon's house placement (Placidus). What it "
        "means that the person's emotional needs, instincts and sense of safety "
        "are focused in this life area."
    ),
    INNER_DRIVES: (
        "Mercury, Venus, Mars — the mind, what one values and is drawn to, and "
        "the will to act. By sign, with a pointer to the house sections where "
        "each lands."
    ),
    CHART_SHAPE: (
        "Chart-level aggregate — dominant element and modality, the day/night "
        "(sect) condition, hemisphere emphasis, the tightest aspect patterns / "
        "configurations — AND the wider planets read as full personal factors in "
        "the modern manner: Jupiter, Saturn, Uranus, Neptune, Pluto and the lunar "
        "nodes, each by sign and house."
    ),
    IDENTITY: (
        "House 1 — identity: the self one presents, vitality, the body, first "
        "impressions, the way one meets life. The Ascendant sign and its ruler(s)."
    ),
    VALUES_MONEY: (
        "House 2 — values and money: what one values, income and possessions, "
        "self-worth, how one earns, spends and holds resources."
    ),
    COMMUNICATION_LEARNING: (
        "House 3 — communication, studying, siblings: the everyday mind, learning "
        "style, speech and writing, siblings and neighbours, short journeys."
    ),
    FAMILY_HOME: (
        "House 4 — family and home: origins, parents and ancestry, the home base, "
        "roots, the private inner life."
    ),
    JOY_CREATIVITY_CHILDREN: (
        "House 5 — joy, artistic talents and kids: creativity and self-expression, "
        "play, pleasure, romance, children."
    ),
    HEALTH_ROUTINE_PETS: (
        "House 6 — health, routine, pets: daily work and habits, service, care of "
        "the body and health, small animals."
    ),
    PARTNERSHIPS: (
        "House 7 — partnerships: marriage and committed partnership, the "
        "significant other, one-to-one bonds and contracts, what one seeks in a "
        "partner."
    ),
    TRANSFORMATION_INTIMACY: (
        "House 8 — transformation and intimacy: deep bonds and sexuality, shared "
        "resources, crisis, loss and regeneration, psychological depth."
    ),
    TRAVEL_PHILOSOPHY: (
        "House 9 — distant travels and philosophy: the far mind, higher learning, "
        "belief and worldview, long journeys and foreign cultures."
    ),
    STATUS_VOCATION: (
        "House 10 — social status and vocation: career and calling, public role, "
        "reputation and achievement, the Midheaven and its ruler(s)."
    ),
    FRIENDSHIPS_FUTURE: (
        "House 11 — friendships and the future: friends, groups and community, "
        "hopes, wishes and long-term goals."
    ),
    SUBCONSCIOUS_SOLITUDE: (
        "House 12 — subconscious and solitude: the hidden and the dreamlike, "
        "retreat and solitude, what dissolves the ego, spiritual life."
    ),
}

# ---------------------------------------------------------------------------
# Structural maps (§3.0 helpers).
# ---------------------------------------------------------------------------

# Movement-1 home of a point, by name. The chart ruler(s) are resolved per-chart
# in the router and ALSO map to core_identity (handled there, not here).
POINT_HOME: dict[str, str] = {
    "Sun": CORE_IDENTITY,
    "Moon": CORE_IDENTITY,
    "Mercury": INNER_DRIVES,
    "Venus": INNER_DRIVES,
    "Mars": INNER_DRIVES,
    "Jupiter": CHART_SHAPE,
    "Saturn": CHART_SHAPE,
    "Uranus": CHART_SHAPE,
    "Neptune": CHART_SHAPE,
    "Pluto": CHART_SHAPE,
    "North Node": CHART_SHAPE,
    "South Node": CHART_SHAPE,
}

# Provenance-only keys stripped from the prompt view of ``about``: every house
# in the reading is Placidus (grounding verified it), so the source book's
# declared system must not reach the model as if it mattered.
_HOUSE_SYSTEM_KEYS = ("house_system", "subject_house_system", "placement_house_system")


# ---------------------------------------------------------------------------
# Routed-principle carrier (what a section call receives per principle, §4).
# ---------------------------------------------------------------------------

@dataclass
class RoutedPrinciple:
    """One principle as placed into one section. Carries the traceability anchor
    (``principle_id``), the fields a section call needs, and the ``texture`` flag
    (``"classical"`` where §3/§4 set it, else ``None``). ``reasons`` records why
    the router placed it here — provenance only, never rendered."""

    principle_id: str
    tradition: Optional[str]
    rule: Optional[str]
    topic_tags: list[str]
    about: dict
    requires: list[dict]
    texture: Optional[str] = None
    # "low" marks low-confidence general-methodology material that synthesis
    # prunes first if chart_shape runs long (§3.1.11, §5.5). None = normal.
    salience: Optional[str] = None
    reasons: list[str] = field(default_factory=list)

    @property
    def is_classical(self) -> bool:
        return self.texture == "classical"

    @property
    def is_low_salience(self) -> bool:
        return self.salience == "low"

    def as_prompt_dict(self) -> dict:
        """Compact view passed to the section call (§4). Tradition is included
        for the conflict / texture rules but must never surface in output text.
        House-system provenance is dropped: houses are Placidus by policy."""
        about = {k: v for k, v in (self.about or {}).items()
                 if k not in _HOUSE_SYSTEM_KEYS}
        d = {
            "principle_id": self.principle_id,
            "tradition": self.tradition,
            "rule": self.rule,
            "topic_tags": self.topic_tags,
            "about": about,
        }
        if self.texture:
            d["texture"] = self.texture
        if self.salience:
            d["salience"] = self.salience
        return d

    def as_report_dict(self) -> dict:
        return {
            "principle_id": self.principle_id,
            "texture": self.texture,
            "salience": self.salience,
            "reasons": self.reasons,
        }
