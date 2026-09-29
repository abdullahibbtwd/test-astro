#!/usr/bin/env python3
"""
pr_prompts.py — the literal prompt blocks for the predictive reading
(PREDICTIVE_READING_SPEC §5, §7). The spec ships the actual strings; this module holds
them verbatim with `{token}` fills, plus the two-tier banned vocabulary the mask (§5)
rests on — shared with ``pr_validate.py`` so the prompt's prohibition and the lint's
ban list can never drift.

Prompts are English scaffolding with Turkish-output directives (§7). The shared system
block is built once and marked cacheable by ``pr_generate.py`` (§2 prompt caching).
"""

from __future__ import annotations

from pr_profiles import Profile

# ===========================================================================
# TRADITION MASK + MACHINERY-HIDING VOCAB (§5, §11.2)
# Two tiers. HARD entries are unambiguous leaks (always banned). CONTEXT entries are
# words that are ordinary in plain prose and are caught only in their technical phrasing,
# so the lint does not false-positive on everyday Turkish/English.
# ===========================================================================

# The three vocabulary buckets and which astro_detail level UN-bans each:
#   - TIER_A  (classical / tradition machinery): hidden in plain & modern; shown in technical.
#   - MODERN  (modern astrology vocabulary — aspect names, retrograde, transit-as-driver):
#             hidden ONLY in plain; shown in modern & technical (the everyday language of a
#             modern astrology audience).
#   - TECH    (technique machinery — house numbers, phase words, house systems, orb, ingress):
#             hidden in plain & modern; shown in technical.
ASTRO_DETAILS = ("plain", "modern", "technical")

# --- TIER A: classical vocabulary (a hit is build-blocking below the technical level, §11.2) -
TIER_A_HARD = [
    "part of fortune", "part of spirit", "lot of fortune", "lot of spirit",
    "hilaj", "hīlāj", "hyleg", "alcocoden", "alcochoden", "almuten",
    "triplicity", "triplicities", "firdaria", "firdar",
    "profection", "profections", "profected",
    "lord of the year", "zodiacal releasing", "decan", "decans", "decanate",
    "sect",  # whole-word; no ordinary collision in this prose
]
# Ambiguous single words banned ONLY in their technical usage.
TIER_A_CONTEXT = [
    r"\bthe\s+lot\b", r"\blots?\s+of\s+(?:fortune|spirit)\b",
    r"\bby\s+(?:bound|term|terms|face|triplicity)\b",
    r"\bbound\s+ruler\b", r"\bterm\s+ruler\b",
    r"\bin\s+sect\b", r"\bout\s+of\s+sect\b",
]

# --- MODERN: everyday astrology words (allowed at modern+; a leak only in plain) ------------
MODERN_HARD = [
    "conjunction", "opposition", "sextile", "trine", "quincunx",
    "kavuşum", "karşıtlık", "sekstil", "trigon", "altmışlık", "üçgenlik",
    "retrograde", "retrograd",
]
MODERN_CONTEXT = [
    r"\b(?:square|trine|sextile|opposition)\s+(?:aspect|to\s+(?:your|natal))",
    r"\btransit(?:ing|s)?\s+(?:planet|to\s+(?:your|natal))",
]

# --- TECH: technique machinery (allowed only at the technical level) ------------------------
TECH_HARD = [
    "applying", "separating", "perfecting", "cycle stage",
    "placidus", "whole-sign", "whole sign", "wholesign", "ingress", "orb",
]
TECH_CONTEXT = [
    r"\b\d+(?:st|nd|rd|th)\s+house\b",            # "10th house"
    r"\b\d+\.\s*ev(?:i|in|inde|ine|inden)?\b",    # "10. ev"
    r"\bhouse\s+\d+\b",                            # "house 10"
]


# ===========================================================================
# §7.1 SHARED SYSTEM BLOCK (cached prefix for every call in a horizon)
# The header, rules 1/2/4/5 are fixed; rule 3 (what may/must be named) varies by
# astro_detail so an astrology-literate audience gets the reasoning, not just the mood.
# ===========================================================================
_HEADER = """\
You are an astrologer writing for a Turkish-speaking audience in warm, grounded, modern
psychological language. You write about lived experience — mood, timing, where to lean in
and where to be patient.

ABSOLUTE RULES:
1. Interpret ONLY the events given to you below. Do not invent planets, dates, themes, or
   movement that is not in the event list. If the list is short, write a shorter, calmer
   piece. Never pad.
2. Base each interpretation on the "meaning" text attached to each event. Do not overrule it
   with your own astrological ideas. If two meanings clash, prefer the psychological one.
"""

_FOOTER = """\
4. When a strength is noted for a factor, write pressure on it as consolidation and
   endurance, NOT as depletion. Only genuine weakness reads as real strain.
5. Output MUST be valid JSON with exactly the keys requested. Turkish prose only inside the
   values. No commentary outside the JSON."""

# rule 3 — plain: hide ALL machinery, translate to feeling-language (the original behaviour).
_RULE3_PLAIN_ON = (
    "You MAY name planets and common sky moments (full moon, new moon, eclipse) as everyday "
    "hooks, but never the mechanics around them.")
_RULE3_PLAIN_OFF = (
    "Do not name planets or sky events at all; speak purely in terms of lived themes.")

_TRANSLATION_GUIDE = (
    "     - tension (a hard angle) → friction, a push-pull, pressure to work through\n"
    "     - flow (an easy angle) → ease, support, momentum, an opening\n"
    "     - a beginning → a fresh start, an intensifying\n"
    "     - building → approaching; peaking → coming to a head now; winding down → releasing\n"
    "     - life areas in plain words: self, relationships, home, work, money, health.")


def _rule3(astro_detail: str, surface_planets: bool) -> str:
    if astro_detail == "modern":
        return (
            "3. Name the astrological driver of each theme in everyday astrology language, "
            "THEN say what it means. You SHOULD name: the planets involved, the aspect between "
            "them (conjunction, square, trine, sextile, opposition), the signs, transits, "
            "retrogrades, and new/full moons or eclipses — but ONLY those shown in the event "
            "list (each event line prints its driver in [brackets]). NEVER invent a planet, "
            "aspect, sign, or moon-phase that is not listed. After naming the driver, translate "
            "what it MEANS into plain psychological Turkish:\n"
            + _TRANSLATION_GUIDE + "\n"
            "   Do NOT use: house NUMBERS (refer to houses only as plain life areas); the words "
            "applying / separating / perfecting; cycle-stage labels; Placidus / whole-sign; "
            "orb; and NEVER any classical/tradition term (lot, Part of Fortune, Spirit, sect, "
            "profection, lord of the year, triplicity, bound, term, decan, releasing, almuten) "
            "— in Turkish or English.")
    if astro_detail == "technical":
        return (
            "3. Write for an astrology-literate reader: give the full astrological reasoning "
            "behind each theme — the planets, the aspect, the signs, the house (by number when "
            "the event line lists one), whether it is building or exact, new/full moons and "
            "eclipses, and any traditional factor the event's meaning text actually supports. "
            "Name ONLY what appears in the event list (drivers are printed in [brackets]); "
            "never invent a factor. ALWAYS follow the technical detail with its plain, lived "
            "meaning, so the piece stays a reading and not a chart print-out:\n"
            + _TRANSLATION_GUIDE)
    # plain
    clause = _RULE3_PLAIN_ON if surface_planets else _RULE3_PLAIN_OFF
    return (
        "3. NEVER use technical vocabulary in your output. Forbidden: house numbers; the "
        "geometry words square, trine, sextile, opposition, conjunction; applying / separating "
        "/ perfecting; transit, ingress, orb, retrograde-as-jargon, cycle stage; Placidus / "
        "whole-sign; and ANY classical term (lot, Part of Fortune, Spirit, sect, profection, "
        "lord of the year, triplicity, bound, term, firdaria, releasing, almuten) — Turkish or "
        "English. Translate every technical fact into plain feeling-language:\n"
        + _TRANSLATION_GUIDE + "\n   " + clause)


# Back-compat names some callers/tests still import.
PLANET_SURFACE_ON = _RULE3_PLAIN_ON
PLANET_SURFACE_OFF = _RULE3_PLAIN_OFF


def build_system_block(*, surface_planets: bool = True,
                       astro_detail: str = "modern") -> str:
    if astro_detail not in ASTRO_DETAILS:
        raise ValueError(f"bad astro_detail {astro_detail!r}; expected {ASTRO_DETAILS}")
    return _HEADER + _rule3(astro_detail, surface_planets) + "\n" + _FOOTER


# ===========================================================================
# §9 SPARSE CLAUSE (appended to the task when meta.sparse)
# ===========================================================================
SPARSE_CLAUSE = (
    "\n\nNOTE: this is a genuinely quiet stretch — few notable movements. Say so honestly "
    "in a calm, brief way. A shorter piece is expected and correct here; do NOT invent "
    "themes or movement to fill space. A quiet forecast is a valid forecast.")


# ===========================================================================
# PROFILE HEADER LINE (§7.3/§7.4/§7.5 — "PROFILE: {profile} — {lens_line}")
# ===========================================================================
def _profile_header(profile: Profile) -> str:
    return f"PROFILE: {profile.name}  — {profile.lens_line}"


# ===========================================================================
# §7.3 DAY block prompt
# ===========================================================================
def build_day_user(profile: Profile, events_block: str, *, sparse: bool) -> str:
    task = (
        f"TASK: Write ONE flowing paragraph of 120–180 words in Turkish for this day, seen "
        f"through the {profile.name} lens: lead with what matters most for "
        f"{profile.domain_phrase}, and cast every theme in that register. If the day is "
        f"quiet, say so honestly and keep it brief. Return JSON: {{\"reading\": \"...\"}}.")
    if sparse:
        task += SPARSE_CLAUSE
    return (f"{_profile_header(profile)}\n\n"
            f"EVENTS FOR THIS DAY:\n{events_block}\n\n{task}")


# ===========================================================================
# §7.4 / §7.6 BEAT prompt (month: early/mid/late 50–80w; year: q1..q4 60–90w)
# ===========================================================================
def build_beat_user(profile: Profile, segment_label: str, events_block: str, *,
                    words: str, sparse: bool) -> str:
    task = (
        f"TASK: Write {words} words in Turkish covering the {segment_label} through the "
        f"{profile.name} lens. Concrete and grounded; no preamble. "
        f"Return JSON: {{\"beat\": \"...\"}}.")
    if sparse:
        task += SPARSE_CLAUSE
    return (f"{_profile_header(profile)}\n\n"
            f"EVENTS IN THIS PART ({segment_label}):\n{events_block}\n\n{task}")


# ===========================================================================
# §7.5 / §7.6 SYNTHESIS prompt (month overview/focus 80–120w; year 100–140w)
# ===========================================================================
def build_synthesis_user(profile: Profile, events_block_full: str,
                         beats: dict[str, str], *, words: str, sparse: bool) -> str:
    beat_lines = "\n".join(f"{k}: {v}" for k, v in beats.items())
    if profile.name == "general":
        focus_line = (f'2. "focus": {words} words on the single strongest theme of the '
                      f"period, area-neutral.")
    else:
        focus_line = (f'2. "focus": {words} words specifically on {profile.domain_phrase} — '
                      f"the profile's home ground.")
    task = (
        f"TASK (Turkish, JSON):\n"
        f'1. "overview": {words} words naming the period\'s dominant thread through the '
        f"{profile.name} lens and how it moves across the parts.\n"
        f"{focus_line}\n"
        f'Return {{"overview": "...", "focus": "..."}}.')
    if sparse:
        task += SPARSE_CLAUSE
    return (f"{_profile_header(profile)}\n\n"
            f"ALL EVENTS THIS PERIOD:\n{events_block_full}\n\n"
            f"THE PARTS ALREADY WRITTEN:\n{beat_lines}\n\n{task}")


# ===========================================================================
# §8 bounded re-ask for a single out-of-range section
# ===========================================================================
def build_reask_user(profile: Profile, key: str, current_text: str,
                     lo: int, hi: int, events_block: str) -> str:
    return (
        f"{_profile_header(profile)}\n\n"
        f"EVENTS:\n{events_block}\n\n"
        f"The following section is the wrong length. Rewrite ONLY it in Turkish so it lands "
        f"between {lo} and {hi} words, keeping the same meaning, voice and the {profile.name} "
        f"lens, adding no new themes and removing none of the grounded ones. "
        f"Current text:\n\"\"\"{current_text}\"\"\"\n\n"
        f"Return JSON: {{\"{key}\": \"...\"}}.")
