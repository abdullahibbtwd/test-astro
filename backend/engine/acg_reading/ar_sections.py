#!/usr/bin/env python3
"""ar_sections.py — the ACG city-reading section model (ACG 07 §6.1–6.2, supersedes
spec 04 §2) and the fixed reader-facing vocab the routing hands to the prompts."""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ACG = os.path.join(_ROOT, "Astrocartography")
if _ACG not in sys.path:
    sys.path.insert(0, _ACG)

from acg_constants import BANDS, GOALS  # noqa: E402,F401

SCHEMA_VERSION = "acg-reading-3"

# key -> (TR title, EN title, (min, max) TR words, per-slot?)
SECTIONS: dict[str, tuple[str, str, tuple[int, int], bool]] = {
    "place_overview": ("Bu Yere Genel Bakış", "This Place at a Glance", (90, 140), False),
    "lines_here": ("Buradaki Gezegen Çizgileri", "Planetary Lines Here", (40, 70), True),
    "background_influences": ("Arka Plan Etkileri", "Background Influences", (30, 60), True),
    "positives": ("Olumlu Etkiler", "Positive Influences", (80, 160), False),
    "challenges": ("Olası Zorluklar", "Potential Challenges", (60, 140), False),
    "life_areas_here": ("Burada Öne Çıkan Yaşam Alanları", "Life Areas That Shift Here",
                        (80, 160), False),
    "suitability": ("Bu Yer Ne İçin Uygun?", "What Is This Place Suited For?", (25, 50), True),
}
SECTION_ORDER: tuple[str, ...] = tuple(SECTIONS)
LENGTH_TOLERANCE = 0.20                          # AV6: ±20%

# card key -> (TR title, EN title, goal)   (07 §6.2, fixed order)
CARDS: dict[str, tuple[str, str, str]] = {
    "travel": ("Seyahat için", "For travel", "travel"),
    "living": ("Kalıcı yaşam için", "For permanent living", "relocation"),
    "work": ("Çalışma için", "For work", "career"),
    "business": ("İş kurmak için", "For business", "business"),
    "love": ("Aşk için", "For love", "love"),
    "family": ("Aile için", "For family", "family"),
}
CARD_ORDER: tuple[str, ...] = tuple(CARDS)
GOAL_TO_CARD = {g: k for k, (_, _, g) in CARDS.items()}

NO_EMPHASIS_ID = "acg-method-no-influence"
NO_EMPHASIS_TEXT = {
    "tr": "Bu hedef açısından bu yer doğum haritanızdaki mevcut eğilimlere belirgin bir "
          "vurgu eklemiyor.",
    "en": "For this goal, the place adds no particular emphasis to what your birth chart "
          "already shows.",
}

FOOTER = {
    "tr": "Bu okuma sembolik bir yansımadır; nerede yaşayacağınıza dair bir tavsiye değildir.",
    "en": "This reading is a symbolic reflection, not advice on where to live.",
}

# spec 04 §3: tier -> wording label (never a number)
TIER_WORDING = {
    "tight": ("belirgin biçimde", "strongly"),
    "strong": ("hissedilir biçimde", "noticeably"),
    "wide": ("hafif ve arka planda", "faintly, in the background"),
}

# where each angle shows up — plain words handed to the prompt instead of jargon
ANGLE_PLAIN = {
    "ASC": ("kişisel ifade, beden ve ilk izlenim", "self-expression, body and first impressions"),
    "DSC": ("ilişkiler, ortaklıklar ve karşınızdaki insanlar",
            "relationships, partnerships and the people you meet"),
    "MC": ("meslek, toplumsal görünürlük ve hedefler",
           "career, public visibility and aims"),
    "IC": ("ev, kökler ve iç dünya", "home, roots and inner life"),
}

PLANET_NAMES = {
    "sun": ("Güneş", "Sun"), "moon": ("Ay", "Moon"), "mercury": ("Merkür", "Mercury"),
    "venus": ("Venüs", "Venus"), "mars": ("Mars", "Mars"), "jupiter": ("Jüpiter", "Jupiter"),
    "saturn": ("Satürn", "Saturn"), "uranus": ("Uranüs", "Uranus"),
    "neptune": ("Neptün", "Neptune"), "pluto": ("Plüton", "Pluto"),
}

# PROJECT_OVERVIEW §3 reader-facing house names (numbers never reach the prompt)
LIFE_AREAS = {
    1: ("Kimlik", "Identity"), 2: ("Değerler ve Para", "Values and Money"),
    3: ("İletişim, Öğrenim ve Kardeşler", "Communication, Studying, Siblings"),
    4: ("Aile ve Yuva", "Family and Home"),
    5: ("Neşe, Sanatsal Yetenekler ve Çocuklar", "Joy, Artistic Talents and Kids"),
    6: ("Sağlık, Rutin ve Evcil Hayvanlar", "Health, Routine, Pets"),
    7: ("Ortaklıklar", "Partnerships"),
    8: ("Dönüşüm ve Yakınlık", "Transformation and Intimacy"),
    9: ("Uzak Seyahatler ve Felsefe", "Distant Travels and Philosophy"),
    10: ("Toplumsal Statü ve Meslek", "Social Status and Vocation"),
    11: ("Arkadaşlıklar ve Gelecek", "Friendships and the Future"),
    12: ("Bilinçaltı ve Yalnızlık", "Subconscious and Solitary"),
}


def length_bounds(section: str, n_slots: int = 1) -> tuple[int, int]:
    """TR word range with the AV6 ±20% tolerance applied."""
    lo, hi = SECTIONS[section][2]
    return int(lo * (1 - LENGTH_TOLERANCE)), int(round(hi * (1 + LENGTH_TOLERANCE)))
