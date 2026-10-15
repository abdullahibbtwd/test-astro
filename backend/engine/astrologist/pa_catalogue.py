"""pa_catalogue.py - the TR/EN label catalogue the chat uses (Phase 0 §10).

There is no single backend catalogue yet. This module **imports** the labels from the layers
that own them, so the chat says exactly what the app shows, and adds only the four tables
that existed as enums alone (grades, day bands, tones, transit phases) plus the 17 natal
section titles. New TR strings go to native review with the templates.
"""

from __future__ import annotations

import hashlib
import json
import os

import _paths  # noqa: F401
from acg_constants import BANDS as ACG_BANDS  # noqa: E402
from acg_constants import GOALS  # noqa: E402
from ar_sections import TIER_WORDING  # noqa: E402
from best_days import ACTIVITIES  # noqa: E402
from cr_sections import (PLANET_TR, POINT_EN, POINT_TR_COM, POINT_TR_DAT, SIGN_TR,  # noqa: E402
                         transit_label)

CATALOGUE_VERSION = "pa-cat-1"
_TEMPLATES = os.path.join(_paths.ROOT, "calendar_reading", "notification_templates.json")
with open(_TEMPLATES, encoding="utf-8") as _fh:
    _AREA = json.load(_fh)["slot_forms"]["area"]          # {"tr": {"1": ...}, "en": {...}}

BODIES = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune",
          "pluto", "north_node", "south_node"]
SIGNS = list(SIGN_TR)
ASPECTS = ["conjunction", "sextile", "square", "trine", "opposition"]

BODY = {"tr": {**PLANET_TR, "north_node": "Kuzey Ay Düğümü", "south_node": "Güney Ay Düğümü"},
        "en": {**{k: v for k, v in POINT_EN.items() if k in PLANET_TR},
               "north_node": "North Node", "south_node": "South Node"}}
ANGLE = {"tr": {"asc": "Yükselen", "mc": "Tepe Noktası", "dsc": "Alçalan", "ic": "Dip Noktası"},
         "en": {"asc": "Ascendant", "mc": "Midheaven", "dsc": "Descendant", "ic": "IC"}}
SIGN = {"tr": dict(SIGN_TR), "en": {s: s.title() for s in SIGN_TR}}
ASPECT = {"tr": {"conjunction": "kavuşum", "sextile": "altmışlık", "square": "kare",
                 "trine": "üçgen", "opposition": "karşıt"},
          "en": {a: a for a in ASPECTS}}
AREA = {"tr": {int(k): v for k, v in _AREA["tr"].items()}, "en": {int(k): v for k, v in _AREA["en"].items()}}
GOAL = {"tr": {g: v[0] for g, v in GOALS.items()}, "en": {g: v[1] for g, v in GOALS.items()}}
ACTIVITY = {"tr": {a: v[0] for a, v in ACTIVITIES.items()}, "en": {a: v[1] for a, v in ACTIVITIES.items()}}

# --- the tables that existed as enums only (new; TR to native review) -------------------------------
GRADE = {"tr": {"excellent": "mükemmel", "good": "iyi", "neutral": "nötr", "avoid": "kaçınılması iyi"},
         "en": {"excellent": "excellent", "good": "good", "neutral": "neutral", "avoid": "best avoided"}}
DAY_BAND = {"tr": {"strongly_supportive": "çok destekleyici", "supportive": "destekleyici", "quiet": "sakin",
                   "mixed": "karışık", "challenging": "zorlayıcı", "strongly_challenging": "çok zorlayıcı"},
            "en": {"strongly_supportive": "strongly supportive", "supportive": "supportive", "quiet": "quiet",
                   "mixed": "mixed", "challenging": "demanding", "strongly_challenging": "very demanding"}}
TONE = {"tr": {"favorable": "destekleyici", "mixed": "karışık", "quiet": "sakin", "challenging": "zorlayıcı"},
        "en": {"favorable": "favourable", "mixed": "mixed", "quiet": "quiet", "challenging": "challenging"}}
PHASE = {"tr": {"building": "güçleniyor", "peak": "en güçlü noktasında", "easing": "etkisini yitiriyor"},
         "en": {"building": "building", "peak": "at its peak", "easing": "easing"}}
PLACE_BAND = {"tr": {k: v[0] for k, v in ACG_BANDS.items()}, "en": {k: v[1] for k, v in ACG_BANDS.items()}}
TIER = {"tr": {k: v[0] for k, v in TIER_WORDING.items()}, "en": {k: v[1] for k, v in TIER_WORDING.items()}}
PERIOD_KIND = {"tr": {"favorable": "destekleyici dönem", "challenging": "daha dikkat isteyen dönem"},
               "en": {"favorable": "supportive period", "challenging": "more demanding period"}}

SECTION_KEYS = ["core_identity", "sun_house", "moon_house", "inner_drives", "chart_shape", "identity",
                "values_money", "communication_learning", "family_home", "joy_creativity_children",
                "health_routine_pets", "partnerships", "transformation_intimacy", "travel_philosophy",
                "status_vocation", "friendships_future", "subconscious_solitude"]
HOUSE_OF_SECTION = {k: i + 1 for i, k in enumerate(SECTION_KEYS[5:])}
SECTION_OF_HOUSE = {v: k for k, v in HOUSE_OF_SECTION.items()}
SECTION_TITLE = {
    "tr": {"core_identity": "Temel Kimlik", "sun_house": "Güneş'inin Alanı", "moon_house": "Ay'ının Alanı",
           "inner_drives": "İç Dürtüler", "chart_shape": "Haritanın Genel Yapısı",
           **{k: AREA["tr"][h] for k, h in HOUSE_OF_SECTION.items()}},
    "en": {"core_identity": "Core Identity", "sun_house": "Your Sun's Area", "moon_house": "Your Moon's Area",
           "inner_drives": "Inner Drives", "chart_shape": "Overall Chart Shape",
           **{k: AREA["en"][h] for k, h in HOUSE_OF_SECTION.items()}},
}
MONTHS = {"tr": ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
                 "Ekim", "Kasım", "Aralık"],
          "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                 "October", "November", "December"]}


def body(b: str, lang: str) -> str:
    return BODY[lang].get(b) or ANGLE[lang].get(b) or b


def fmt_date(iso: str, lang: str) -> str:
    """'12 Ekim 2026' / '12 October 2026' (dates are the only digits labels carry, PA_01 §3.2)."""
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{d} {MONTHS[lang][m - 1]} {y}"


def placement_label(b: str, sign: str, house: int | None, retro: bool, lang: str) -> str:
    if lang == "tr":
        s = f"{body(b, 'tr')}: {SIGN['tr'][sign]} burcunda"
        if house:
            s += f", {AREA['tr'][house]} alanında"
        return s + (", retro hareketli" if retro else "")
    s = f"{body(b, 'en')} in {SIGN['en'][sign]}"
    if house:
        s += f", in your {AREA['en'][house]} area"
    return s + (", retrograde" if retro else "")


def angle_label(a: str, sign: str, lang: str) -> str:
    return f"{ANGLE[lang][a]}: {SIGN[lang][sign]}" if lang == "tr" else f"{ANGLE['en'][a]} in {SIGN['en'][sign]}"


def house_label(h: int, sign: str, rulers: list[str], lang: str) -> str:
    rs = [body(r, lang) for r in rulers]
    if lang == "tr":
        return f"{AREA['tr'][h]} alanı: {SIGN['tr'][sign]} burcunda başlıyor, yöneticisi {' ve '.join(rs)}"
    return f"{AREA['en'][h]} area: begins in {SIGN['en'][sign]}, ruled by {' and '.join(rs)}"


def aspect_label(a: str, b: str, typ: str, lang: str) -> str:
    if lang == "tr":
        return f"{body(a, 'tr')} ile {body(b, 'tr')} arasında {ASPECT['tr'][typ]}"
    return f"{body(a, 'en')} {typ} {body(b, 'en')}"


def transit_item_label(t: str, a: str, n: str, lang: str) -> str:
    """The calendar's own label (CAL_03 §2) - identical to what the calendar screen shows."""
    tr, en = transit_label(t, a, n)
    return tr if lang == "tr" else en


def catalogue_sha() -> str:
    blob = json.dumps([CATALOGUE_VERSION, BODY, ANGLE, SIGN, ASPECT, AREA, GOAL, ACTIVITY, GRADE, DAY_BAND, TONE,
                       PHASE, PLACE_BAND, TIER, SECTION_TITLE], ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


__all__ = ["BODIES", "SIGNS", "ASPECTS", "BODY", "ANGLE", "SIGN", "ASPECT", "AREA", "GOAL", "ACTIVITY", "GRADE",
           "DAY_BAND", "TONE", "PHASE", "PLACE_BAND", "TIER", "PERIOD_KIND", "SECTION_KEYS", "SECTION_TITLE",
           "HOUSE_OF_SECTION", "SECTION_OF_HOUSE", "MONTHS", "body", "fmt_date", "placement_label", "angle_label",
           "house_label", "aspect_label", "transit_item_label", "catalogue_sha", "POINT_TR_DAT", "POINT_TR_COM"]
