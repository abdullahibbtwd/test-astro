#!/usr/bin/env python3
"""
s3_sections.py — the section model for S3 (SYNASTRY_READING_SPEC.md §3).

Eight sections: a short per-person opener (``what_each_brings``, "movement 0")
plus the seven shared relationship axes. Their keys are a locked render contract
— once written they are the foreign keys the app renders against.

This module also carries the point taxonomy (significators vs. outer planets, used
by the noise floor §4.1) and the ``RoutedRecord`` carrier a section call receives.
Routing itself lives in ``s3_routing.py``; this file is the single source of truth
for the section list, order, themes, and the point classes.

Domain values ("Venus", "Aries", "square", …) are never renamed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# The eight sections, in canonical render order (§3).
# ---------------------------------------------------------------------------

WHAT_EACH_BRINGS = "what_each_brings"   # movement 0 — per-person opener
ATTRACTION = "attraction"               # 1
EMOTIONAL = "emotional"                 # 2
COMMUNICATION = "communication"         # 3
FRICTION = "friction"                   # 4
VALUES = "values"                       # 5
COMMITMENT = "commitment"               # 6
PURPOSE = "purpose"                     # 7

SECTION_ORDER: list[str] = [
    WHAT_EACH_BRINGS,
    ATTRACTION,
    EMOTIONAL,
    COMMUNICATION,
    FRICTION,
    VALUES,
    COMMITMENT,
    PURPOSE,
]

# The seven axes only (what_each_brings is the opener, not an axis). Used where a
# routine must iterate the compatibility axes without the opener.
AXIS_ORDER: list[str] = SECTION_ORDER[1:]

MOVEMENT: dict[str, int] = {
    WHAT_EACH_BRINGS: 0,
    ATTRACTION: 1,
    EMOTIONAL: 2,
    COMMUNICATION: 3,
    FRICTION: 4,
    VALUES: 5,
    COMMITMENT: 6,
    PURPOSE: 7,
}

# Theme handed to each section call (§3, §4). English: instruction to the model,
# never reader-facing.
SECTION_THEME: dict[str, str] = {
    WHAT_EACH_BRINGS: (
        "The standing ground each person walks in with: their own natal capacity "
        "to partner — how each one loves, needs, and bonds — BEFORE the two charts "
        "are compared. One short paragraph per person. This is NOT a compatibility "
        "claim about the pair; it is each individual's relational nature."
    ),
    ATTRACTION: (
        "Attraction and chemistry: the spark, physical and romantic pull, desire, "
        "the magnetic draw between the two."
    ),
    EMOTIONAL: (
        "Emotional needs and security: how safe, held, and understood each feels "
        "with the other; nurturing, moods, the felt sense of home together."
    ),
    COMMUNICATION: (
        "Communication and the meeting of minds: how they talk, think together, "
        "trade ideas, and understand (or miss) each other in words."
    ),
    FRICTION: (
        "Friction and challenge: where the two grind, clash, or frustrate each "
        "other; the hard edges and the work the relationship asks."
    ),
    VALUES: (
        "Values, money, and shared life: what they treasure, how they handle "
        "resources and the practical building of a life, shared tastes and pace."
    ),
    COMMITMENT: (
        "Commitment and long-term viability: staying power, loyalty, the capacity "
        "to build something durable and to keep choosing each other."
    ),
    PURPOSE: (
        "Shared purpose and growth: where the relationship stretches them, the "
        "larger direction, meaning, and how they grow through each other."
    ),
}

# ---------------------------------------------------------------------------
# Point taxonomy. Significators drive the salience floor (§4.1): a cross-aspect
# with NO significator endpoint (outer-planet-only) is below the floor and drops.
# ---------------------------------------------------------------------------

LUMINARIES = {"Sun", "Moon"}
PERSONAL_PLANETS = {"Mercury", "Venus", "Mars"}
SOCIAL_PLANETS = {"Jupiter", "Saturn"}
OUTER_PLANETS = {"Uranus", "Neptune", "Pluto"}
NODES = {"North Node", "South Node"}
# Angles as they appear in the data: Ascendant/Descendant and Midheaven/Nadir.
ANGLES = {"Ascendant", "Descendant", "Midheaven", "Nadir", "MC", "IC"}

# Everything that carries relational weight in synastry. Outer planets are NOT
# significators — a contact between two of them is generational backdrop (§4.1).
SIGNIFICATORS = LUMINARIES | PERSONAL_PLANETS | SOCIAL_PLANETS | NODES | ANGLES

# The classical malefics, for the friction routing "malefic-receiver receptions".
MALEFICS = {"Mars", "Saturn"}

# Angular houses, for overlay salience weighting (§4.3).
ANGULAR_HOUSES = {1, 4, 7, 10}


def is_significator(point: Optional[str]) -> bool:
    return bool(point) and point in SIGNIFICATORS


# ---------------------------------------------------------------------------
# Routed-record carrier (what a section call receives per record, §5).
# ---------------------------------------------------------------------------

@dataclass
class RoutedRecord:
    """One grounded synastry (or person) record placed into one section.

    Carries the traceability anchor (``record_id`` — a per-fact unique uid, since
    ``principle_id`` is a template shared across several grounded facts), the
    template ``principle_id`` for provenance, the person-substituted
    ``bound_statement`` (S3's ONLY source of claims — never ``rule``), the
    ``bound`` role block (correct person attribution), the routing ``weight``
    used for ordering/capping, and provenance (``reasons``). ``person`` is set
    for opener records so the opener call knows whose paragraph they feed.
    """

    record_id: str
    interaction: str
    bound_statement: str
    bound: dict
    topic_tags: list[str]
    principle_id: str = ""
    weight: float = 0.0
    person: Optional[str] = None          # "A"/"B" for opener records, else None
    reasons: list[str] = field(default_factory=list)

    def as_prompt_dict(self) -> dict:
        """Compact view passed to a section call (§5). Note: ``bound`` is passed
        so the call gets person attribution right; ``rule`` is deliberately NOT
        included (§7 hard rule — attribution comes only from ``bound``)."""
        d = {
            "record_id": self.record_id,
            "bound_statement": self.bound_statement,
            "bound": self.bound,
        }
        if self.person:
            d["person"] = self.person
        return d

    def as_report_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "principle_id": self.principle_id,
            "interaction": self.interaction,
            "weight": round(self.weight, 3),
            "reasons": self.reasons,
        }
