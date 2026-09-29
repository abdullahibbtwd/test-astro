#!/usr/bin/env python3
"""ar_prompts.py — prompts for the ACG place reading (spec 04 §4 + 07 §6).

Every writing call returns the same JSON shape:

    {"units": [{"unit_id": "...", "sentences": [{"text": "...", "ids": ["<principle_id>", ...]}]}]}

so each sentence carries the ids it rests on and the validator can check every trace
against the unit's routed pool (the model never sees ids it may not use). The card
band label is NOT written by the model — ar_generate prepends the exact label, so a
card can never assert a band other than the computed one (AV9 by construction).
"""

from __future__ import annotations

import json

from ar_sections import SECTIONS

UNITS_SCHEMA = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string"},
                    "sentences": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "ids": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["text", "ids"],
                        },
                    },
                },
                "required": ["unit_id", "sentences"],
            },
        }
    },
    "required": ["units"],
}

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string"},
                    "sentences": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["unit_id", "sentences"],
            },
        }
    },
    "required": ["units"],
}

CONTRACT = """\
You write one part of an astrocartography reading in Turkish: how a particular PLACE
brings certain themes of a person's birth chart forward. Warm, plain, second person
("sen" is avoided; use the polite plural "siz" consistently), psychological and
experiential, never technical.

NON-NEGOTIABLE RULES
1. Use ONLY the principles given to you. Every sentence lists in "ids" the
   principle id(s) it rests on — ids from the list you were given, nothing else. Never
   invent a claim, a place fact, a history or an event that no given principle supports.
2. Never write numbers of any kind, distances, kilometres, miles, degrees, coordinates,
   house numbers ("10. ev", "10th house"), or angle abbreviations (ASC, DSC, MC, IC),
   and never the words "boylam", "enlem", "orb", "yükselen çizgi", "tepe noktası".
   Describe WHERE a theme shows up with the plain words you are given.
3. Use the given intensity wording ("belirgin biçimde", "hissedilir biçimde",
   "hafif ve arka planda") at most ONCE per paragraph, and don't invent stronger or
   weaker ones. The "where it shows up" words describe a life area: say it once, then
   refer to it naturally (e.g. "bu alanda", "ilişkilerinizde") — never repeat the same
   phrase sentence after sentence. Vary sentence openings; read like a person, not a list.
4. Always keep ambivalence: themes come in easier and more demanding forms. There are
   no good or bad planets or places.
5. NEVER advise moving, staying, visiting or avoiding a place. No guarantees, no
   certainty, no yes/no verdicts ("evet", "hayır", "kesinlikle", "garanti",
   "uygun değil", "taşınmalı..."). No fatalism.
6. Principles marked sensitivity "high" may only be rendered as inner or experiential
   themes (intensity, pressure, risk-taking, feeling unanchored, deep change) — NEVER
   as events that will happen (death, accident, attack, illness, crime, addiction). If
   such a principle cannot be rendered that way, leave it out.
7. Never label anything "modern", "classical", "traditional", "klasik", "geleneksel";
   never mention house systems.
8. Name planets in Turkish (Güneş, Ay, Merkür, Venüs, Mars, Jüpiter, Satürn, Uranüs,
   Neptün, Plüton) and ONLY the planets you are told about for this part.
"""

_OUTPUT = """
Return ONLY a JSON object of this shape (no prose, no code fences):
{"units": [{"unit_id": "<unit id as given>", "sentences": [{"text": "<one Turkish sentence>", "ids": ["<principle id>"]}]}]}
"""


def _words(section: str) -> str:
    lo, hi = SECTIONS[section][2]
    return f"{lo}–{hi} Turkish words"


def build_lines_prompt(plan_section: dict, place: dict) -> tuple[str, str]:
    units = []
    for s in plan_section["slots"]:
        units.append({"unit_id": s["slot_id"], "planet": s["planet_tr"],
                      "where_it_shows_up": s["where_tr"], "intensity_wording": s["wording_tr"],
                      "principles": s["records"]})
    user = f"""PART: "Buradaki Gezegen Çizgileri" (planetary lines at {place['name_tr']}).
Write ONE paragraph per unit ({_words('lines_here')} each) explaining what this planet's
line IS for the person here: the planet's theme (its synopsis principles), where it
shows up (the given plain words; the angle-frame principle), and how strongly (the
intensity wording). Planet-in-house principles, if present, describe the planet's
expression: present them as what this place emphasises, NEVER as "your planet is in
house N". Do not list pros and cons here — other parts cover them.

UNITS:
{json.dumps(units, ensure_ascii=False, indent=1)}
{_OUTPUT}"""
    return CONTRACT, user


def build_background_prompt(plan_section: dict, place: dict) -> tuple[str, str]:
    units = [{"unit_id": s["slot_id"], "planets": s["planets_tr"], "principles": s["records"]}
             for s in plan_section["slots"]]
    user = f"""PART: "Arka Plan Etkileri" (background influences at {place['name_tr']}).
For each unit write ONE short paragraph ({_words('background_influences')} each) about the
COMBINED, BACKGROUND influence of the two given planets that runs through this whole
east-west band of the world where {place['name_tr']} lies. It is softer and more diffuse
than a planetary line: say so in plain words. Use ONLY the unit's principles. Name only
the unit's two planets. Never write numbers, latitudes, "paran", "enlem", "kesişim" or
angle names.

UNITS:
{json.dumps(units, ensure_ascii=False, indent=1)}
{_OUTPUT}"""
    return CONTRACT, user


def build_polarity_prompt(section: str, plan_section: dict, place: dict) -> tuple[str, str]:
    slot = plan_section["slots"][0]
    if section == "positives":
        brief = ("the POSITIVE influences this place can bring forward (supportive "
                 "principles, and the easier side of mixed ones)")
    else:
        brief = ("the POTENTIAL CHALLENGES this place can bring forward (challenging "
                 "principles, and the demanding side of mixed ones), with respect and "
                 "without fatalism; sensitivity rule 6 applies strictly")
    user = f"""PART: "{SECTIONS[section][0]}" at {place['name_tr']}.
Write {_words(section)} as one flowing paragraph about {brief}.
EACH SENTENCE rests on EXACTLY ONE principle: "ids" holds exactly one id.
You may name the planet each principle belongs to (given) and where it shows up.

UNIT id: "{slot['slot_id']}"
PRINCIPLES:
{json.dumps(slot['records'], ensure_ascii=False, indent=1)}
{_OUTPUT}"""
    return CONTRACT, user


def build_life_areas_prompt(plan_section: dict, place: dict) -> tuple[str, str]:
    slot = plan_section["slots"][0]
    user = f"""PART: "Burada Öne Çıkan Yaşam Alanları" at {place['name_tr']}.
In this place some planets move into different life areas of the person's chart.
Write {_words('life_areas_here')} as one paragraph describing which life areas come
forward here and how, using ONLY the principles below. Name the life areas with the
given names (never house numbers) and the planets as given.

UNIT id: "{slot['slot_id']}"
PRINCIPLES (each with its planet and life area):
{json.dumps(slot['records'], ensure_ascii=False, indent=1)}
{_OUTPUT}"""
    return CONTRACT, user


def build_cards_prompt(cards: list[dict], place: dict) -> tuple[str, str]:
    units = [{"unit_id": c["card"], "goal": c["title_tr"], "goal_definition": c["goal_definition"],
              "computed_band": c["band_label_tr"], "principles": c["records"]} for c in cards]
    user = f"""PART: "Bu Yer Ne İçin Uygun?" at {place['name_tr']}.
For each unit (one life goal), write 2–3 sentences (25–45 Turkish words in total)
explaining WHY this place has the computed assessment for that goal, using ONLY that
unit's principles. The computed assessment is fixed and will be printed before your
text — do NOT restate it, do NOT contradict it, do NOT write yes/no or "uygun"/"uygun
değil". If the assessment is mixed ("Karışık") or demanding ("Zorlayıcı"), one sentence
must name the demanding side. Do not name the place in the cards.

UNITS:
{json.dumps(units, ensure_ascii=False, indent=1)}
{_OUTPUT}"""
    return CONTRACT, user


def build_overview_prompt(plan_section: dict, drafts: dict, place: dict,
                          focus: dict | None, no_lines: bool) -> tuple[str, str]:
    slot = plan_section["slots"][0]
    gist = {k: " ".join(s["text"] for s in v) for k, v in drafts.items()}
    focus_line = ""
    if focus:
        focus_line = (f"\nThe person is especially interested in \"{focus['label_tr']}\": give "
                      f"that theme one sentence of emphasis, drawn from the other parts.")
    none_line = ("\nNo planetary line is close to this place: say so plainly and explain, "
                 "from the principles, what that means." if no_lines else "")
    user = f"""PART: "Bu Yere Genel Bakış" — the overview of {place['name_tr']}.
Write {_words('place_overview')} as one paragraph. It MUST name the place as
"{place['name_tr']}". Give a one-line gist of each other part (below, already written),
and carry the framing principles: themes come in easier and more demanding forms; how
the person meets them depends on the whole birth chart; they show up at the scale of an
ordinary life, not as dramatic events.{focus_line}{none_line}
"ids": framing principles from the list below, or ids already used in the other parts.

UNIT id: "{slot['slot_id']}"
FRAMING PRINCIPLES:
{json.dumps(slot['records'], ensure_ascii=False, indent=1)}

OTHER PARTS (already written, for the gist only):
{json.dumps(gist, ensure_ascii=False, indent=1)}
{_OUTPUT}"""
    return CONTRACT, user


def build_translation_prompt(units: list[dict], place: dict,
                             card_labels_en: dict | None = None) -> tuple[str, str]:
    system = CONTRACT + """
You are now the FAITHFUL TRANSLATION pass: render Turkish sentences into warm, natural
English, sentence by sentence — EXACTLY the same number of sentences per unit, same
order, same meaning; nothing added, dropped or softened. Planet names in English (Sun,
Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto). Every rule above
applies to the English too (no numbers, no angle abbreviations, no directives, no
event predictions, no tradition labels). Use "you".
"""
    payload = [{"unit_id": u["unit_id"], "sentences": [s["text"] for s in u["sentences"]]}
               for u in units]
    user = f"""Place: Turkish name "{place['name_tr']}", English name "{place['name']}" (use the
English name in English text).

UNITS TO TRANSLATE:
{json.dumps(payload, ensure_ascii=False, indent=1)}

Return ONLY: {{"units": [{{"unit_id": "...", "sentences": ["<English sentence>", ...]}}]}}"""
    return system, user


def build_detox_prompt(unit: dict, lang: str, problems: list[str]) -> tuple[str, str]:
    lang_name = "Turkish" if lang == "tr" else "English"
    system = CONTRACT + f"""
You are now the REWRITE pass for ONE unit of {lang_name} text that broke a rule. Rewrite
ONLY what is needed to remove the problems listed, keeping meaning, tone and the same
number of sentences in the same order. Remove numbers/distances/jargon, directives
("you should move", "taşınmalısınız"...), certainty words ("kesinlikle", "garanti",
"definitely"), yes/no verdicts, and turn any predicted event (death, accident, illness,
crime, addiction, attack) into an inner or experiential theme — or drop that clause.
Keep the text in {lang_name}.
"""
    user = f"""PROBLEMS: {json.dumps(problems, ensure_ascii=False)}

UNIT:
{json.dumps({"unit_id": unit["unit_id"], "sentences": [s["text"] for s in unit["sentences"]]}, ensure_ascii=False, indent=1)}

Return ONLY: {{"units": [{{"unit_id": "{unit['unit_id']}", "sentences": ["...", "..."]}}]}}
with exactly {len(unit['sentences'])} sentences."""
    return system, user


def build_length_reask(section: str, unit: dict, lo: int, hi: int, got: int,
                       pool: list[dict]) -> tuple[str, str]:
    user = f"""The following unit of the part "{SECTIONS[section][0]}" has {got} Turkish words;
it must have between {lo} and {hi}. Rewrite it to fit, using only these principles
(same rules, same JSON shape, each sentence with its ids):

PRINCIPLES: {json.dumps(pool, ensure_ascii=False, indent=1)}
CURRENT: {json.dumps(unit, ensure_ascii=False, indent=1)}
{_OUTPUT}"""
    return CONTRACT, user
