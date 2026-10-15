#!/usr/bin/env python3
"""
pr_profiles.py — the reframe-lens for the predictive reading (PREDICTIVE_READING_SPEC §3, §7.7).

A profile does three things, in order (§3): **select emphasis**, **reframe valence**,
and **own the `focus` paragraph**. It never changes which events exist — grounding ran
once upstream; the profile reinterprets the same events through its lens.

Domain routing uses the **Placidus** house on each event (`house_placidus`) and the natal
target planet. Whole-sign is internal texture only and is never routed or surfaced on (§3).

This module is pure data + tiny predicates: no LLM, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field

READING_TYPES = ("general", "personal", "professional")
DEFAULT_READING_TYPE = "general"


@dataclass(frozen=True)
class Profile:
    name: str
    # Lead sets (§3 table). Empty for "general" — it leads with whatever is objectively
    # strongest, regardless of area.
    lead_houses: frozenset[int]
    lead_planets: frozenset[str]          # natal TARGET planet names
    lead_angles: frozenset[str]           # natal angle targets that count as lead
    # The line injected into every prompt telling the model how to slant the voice (§7.7).
    lens_line: str
    # What the `focus` paragraph is about (§7.7 {profile_domain}).
    domain_phrase: str
    # Plain-language keywords used by the §11.4 focus-domain spot-check heuristic. Turkish
    # + English so the lint works whichever language the model leans on.
    domain_keywords: tuple[str, ...] = field(default_factory=tuple)

    # -- emphasis predicate: is this event in the profile's lead set? -----------
    def is_lead(self, event: dict) -> bool:
        """True when the event sits in this profile's foreground (§3 emphasis). General
        has no lead set, so nothing is 'lead' and ordering falls back to raw strength."""
        if not (self.lead_houses or self.lead_planets or self.lead_angles):
            return False
        hp = event.get("house_placidus")
        if hp is not None and hp in self.lead_houses:
            return True
        natal = (event.get("bodies") or {}).get("natal")
        if natal in self.lead_planets:
            return True
        if natal in self.lead_angles:
            return True
        return False


GENERAL = Profile(
    name="general",
    lead_houses=frozenset(),
    lead_planets=frozenset(),
    lead_angles=frozenset(),
    lens_line=(
        "Lead with the period's strongest movement whatever life-area it touches; "
        "keep the voice balanced across life as a whole."),
    domain_phrase="life as a whole",
    domain_keywords=(),
)

PERSONAL = Profile(
    name="personal",
    lead_houses=frozenset({1, 3, 4, 5, 7}),
    lead_planets=frozenset({"Moon", "Venus", "Mars"}),
    lead_angles=frozenset({"Ascendant", "IC"}),
    lens_line=(
        "Foreground close relationships, home, body and feeling-life; read every theme "
        "for what it means to the heart and private life."),
    domain_phrase="close relationships and inner life",
    domain_keywords=(
        "ilişki", "sevgi", "aşk", "ev", "aile", "yürek", "kalp", "duygu", "beden",
        "yakın", "gönül", "içsel",
        "relationship", "love", "home", "family", "heart", "feeling", "body", "close",
        "intimacy", "private",
    ),
)

PROFESSIONAL = Profile(
    name="professional",
    lead_houses=frozenset({2, 6, 10, 11}),
    lead_planets=frozenset({"Sun", "Mercury", "Saturn", "Jupiter"}),
    lead_angles=frozenset({"MC"}),
    lens_line=(
        "Foreground work, money, standing and responsibility; read every theme for what "
        "it means to effort, ambition and structure."),
    domain_phrase="work, money and standing",
    domain_keywords=(
        "iş", "para", "kariyer", "sorumluluk", "hedef", "emek", "başarı", "itibar",
        "çalışma", "maddi", "kazanç", "yapı", "disiplin",
        "work", "money", "career", "responsibility", "goal", "effort", "standing",
        "ambition", "structure", "finance", "professional",
    ),
)

_BY_NAME = {p.name: p for p in (GENERAL, PERSONAL, PROFESSIONAL)}


def get_profile(name: str) -> Profile:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise ValueError(
            f"unknown profile {name!r}; expected one of {READING_TYPES}") from None
