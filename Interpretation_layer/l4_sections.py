#!/usr/bin/env python3
"""
l4_sections.py — the section model (L4_INTERPRETATION_SPEC.md §2).

The twelve section keys are a locked render contract (§0, §7.6). This module is
the single source of truth for them: their canonical render order, which
movement each belongs to, the theme description handed to the section call, and
the two structural maps (point -> Movement-1 home, house -> Movement-2 domain)
the router in ``l4_routing.py`` builds on.

Domain values ("Sun", "Aries", …) are never renamed here; only structural keys
live in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# The twelve sections, in canonical render order (§2).
# ---------------------------------------------------------------------------

# Movement 1 — structural portrait ("who you are").
CORE_IDENTITY = "core_identity"
INNER_DRIVES = "inner_drives"
CHART_SHAPE = "chart_shape"

# Movement 2 — life-domain translation ("where it lands").
IDENTITY_BODY = "identity_body"
RESOURCES_VALUES = "resources_values"
MIND_COMMUNICATION = "mind_communication"
HOME_ROOTS = "home_roots"
CREATIVITY_PLEASURE = "creativity_pleasure"
DAILY_WORK = "daily_work"
RELATIONSHIPS = "relationships"
VOCATION_PUBLIC = "vocation_public"
COMMUNITY_MEANING = "community_meaning"

SECTION_ORDER: list[str] = [
    CORE_IDENTITY,
    INNER_DRIVES,
    CHART_SHAPE,
    IDENTITY_BODY,
    RESOURCES_VALUES,
    MIND_COMMUNICATION,
    HOME_ROOTS,
    CREATIVITY_PLEASURE,
    DAILY_WORK,
    RELATIONSHIPS,
    VOCATION_PUBLIC,
    COMMUNITY_MEANING,
]

MOVEMENT: dict[str, int] = {
    CORE_IDENTITY: 1,
    INNER_DRIVES: 1,
    CHART_SHAPE: 1,
    IDENTITY_BODY: 2,
    RESOURCES_VALUES: 2,
    MIND_COMMUNICATION: 2,
    HOME_ROOTS: 2,
    CREATIVITY_PLEASURE: 2,
    DAILY_WORK: 2,
    RELATIONSHIPS: 2,
    VOCATION_PUBLIC: 2,
    COMMUNITY_MEANING: 2,
}

# Theme handed to each section call (§2, §4). English: this is instruction to
# the model, not reader-facing text.
SECTION_THEME: dict[str, str] = {
    CORE_IDENTITY: (
        "The spine of the chart: the Sun, the Moon, and the chart ruler "
        "(the Ascendant's ruler). The luminaries plus the chart ruler as the "
        "core of who the native is."
    ),
    INNER_DRIVES: (
        "Mercury, Venus, Mars — the mind, what one values and is drawn to, and "
        "the will to act."
    ),
    CHART_SHAPE: (
        "Chart-level aggregate: dominant element and modality, the day/night "
        "(sect) condition, hemisphere emphasis, the outer planets and nodes, "
        "and the tightest aspect patterns / configurations."
    ),
    IDENTITY_BODY: "House 1 — self, vitality, physical presentation.",
    RESOURCES_VALUES: (
        "Houses 2 and 8 read as one domain — one's own resources and shared "
        "resources, debt, and depth."
    ),
    MIND_COMMUNICATION: (
        "Houses 3 and 9 read as one domain — the near mind and the far mind, "
        "learning, and belief."
    ),
    HOME_ROOTS: "House 4 — origins, family, foundation, the private base.",
    CREATIVITY_PLEASURE: "House 5 — creativity, romance, children, play.",
    DAILY_WORK: "House 6 — daily work, service, health, routine.",
    RELATIONSHIPS: "House 7 — partnership and the other.",
    VOCATION_PUBLIC: "House 10 — vocation, public role, calling, reputation.",
    COMMUNITY_MEANING: (
        "Houses 11 and 12 read as one domain — hopes and community, and the "
        "retreat, the hidden, and transcendence."
    ),
}

# ---------------------------------------------------------------------------
# Structural maps (§3.0 helpers).
# ---------------------------------------------------------------------------

# Movement-1 home of a point, by name. The chart ruler is resolved per-chart in
# the router and ALSO maps to core_identity (handled there, not here).
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

# Movement-2 home of a house number (§2 map). Paired houses share a section.
HOUSE_DOMAIN: dict[int, str] = {
    1: IDENTITY_BODY,
    2: RESOURCES_VALUES,
    8: RESOURCES_VALUES,
    3: MIND_COMMUNICATION,
    9: MIND_COMMUNICATION,
    4: HOME_ROOTS,
    5: CREATIVITY_PLEASURE,
    6: DAILY_WORK,
    7: RELATIONSHIPS,
    10: VOCATION_PUBLIC,
    11: COMMUNITY_MEANING,
    12: COMMUNITY_MEANING,
}


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
    # "low" marks generational backdrop / low-confidence general-methodology
    # material that synthesis prunes first if chart_shape runs long (§3.1.11,
    # §5.5). None = normal salience.
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
        for the conflict / texture rules but must never surface in output text."""
        d = {
            "principle_id": self.principle_id,
            "tradition": self.tradition,
            "rule": self.rule,
            "topic_tags": self.topic_tags,
            "about": self.about,
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
