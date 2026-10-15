"""cr_prompts.py - prompts for the calendar texts (CAL_03 §3).

TR drafts (several units per call, each sentence traced to principle ids) -> EN
translation (sentence-aligned, so the ids carry over) -> detox rewrite of any unit that
trips a text rule -> one length re-ask.
"""

from __future__ import annotations

import json

UNITS_SCHEMA = {
    "type": "object",
    "properties": {"units": {"type": "array", "items": {
        "type": "object",
        "properties": {"unit_id": {"type": "string"},
                       "sentences": {"type": "array", "items": {
                           "type": "object",
                           "properties": {"text": {"type": "string"},
                                          "ids": {"type": "array", "items": {"type": "string"}}},
                           "required": ["text", "ids"]}}},
        "required": ["unit_id", "sentences"]}}},
    "required": ["units"],
}

TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {"units": {"type": "array", "items": {
        "type": "object",
        "properties": {"unit_id": {"type": "string"},
                       "sentences": {"type": "array", "items": {"type": "string"}}},
        "required": ["unit_id", "sentences"]}}},
    "required": ["units"],
}

CONTRACT = """\
You write short texts for a personal astrological calendar app, in Turkish, for one reader.

VOICE: second person singular ("sen"), warm and reflective, present or near-future tense.
Describe tendencies, themes and inner experience - never certain outcomes.

HARD RULES (a validator rejects any text that breaks them):
1. Use ONLY the principles given for that unit. Every sentence lists in "ids" the principle
   id(s) it is based on, chosen from that unit's principles. Never invent astrological content.
2. No numbers of any kind: no digits, dates, month names, degrees, percentages, ages, house
   numbers. The app shows dates separately.
3. No technical jargon: do not write aspect names (conjunction, square, trine, sextile,
   opposition, kavuşum, kare, üçgen, karşıtlık...), and not "orb", "applying", "separating",
   "ingress", "retrograde", "Placidus", "degree". Planet names are allowed.
4. No directives or guarantees: no "yapmalısın", "kesinlikle", "garanti", "asla", "you must".
   Offer possibilities ("...için uygun bir zaman olabilir").
5. No fatalism and no predicted events. Health, accidents, loss, death, crime, addiction:
   only as inner, experiential themes (tension, the need for care, rest), never as events
   that will happen. Never name body parts, organs or medical conditions (heart, eyes,
   circulation, surgery...) and never suggest clumsiness or mishaps: say "energy", "the need
   to rest", "taking care of yourself" instead. If a principle predicts such an event, soften
   it to a theme or omit it.
6. Stay inside the word range given for each unit.
7. Planet names in Turkish only: Güneş, Ay, Merkür, Venüs, Mars, Jüpiter, Satürn, Uranüs,
   Neptün, Plüton; Yükselen, Tepe Noktası. Never the English names in Turkish text.
8. The context's "phase_arc" is background. Mention the arc in at most one short, natural
   clause; never narrate it step by step or count peaks.
"""

_UNIT_HINTS = {
    "personal_transit": ("Describe what this period tends to bring. Frame it by its arc (building, "
                         "at its peak, easing) using the phase_arc words, never dates."),
    "personal_lunation": ("Describe the new/full moon or eclipse as a focus on the given life area; "
                          "if it touches birth-chart points, say those themes are highlighted."),
    "period": ("Name the life area and say whether this stretch is supportive or more demanding for it. "
               "For a demanding period, include one constructive angle from a mixed or supportive principle."),
    "collective_event": "Describe the collective sky event and its general tone for everyone.",
    "day_note": "A short note for today, weaving together the day's main influences.",
    "best_day": ("Say why this day suits the activity, weaving the listed influences together; "
                 "mention the activity by name. Supportive, never a guarantee."),
}


def _unit_payload(u: dict) -> dict:
    lo, hi = u["words"]
    p = {"unit_id": u["unit_id"], "kind": u["unit_type"], "title": u["label_en"],
         "instructions": _UNIT_HINTS[u["unit_type"]], "turkish_words": f"{lo}-{hi}",
         "context": u["context"],
         "principles": [{k: r[k] for k in ("id", "text", "polarity") if k in r} for r in u["pool"]]}
    return p


_OUTPUT = """Return ONLY JSON: {"units": [{"unit_id": "...", "sentences": [{"text": "<Turkish sentence>", "ids": ["<principle id>"]}]}]}
One entry per unit, unit_id copied exactly."""


def build_draft_prompt(units: list[dict]) -> tuple[str, str]:
    user = ("Write the Turkish text for each unit below.\n\nUNITS:\n"
            + json.dumps([_unit_payload(u) for u in units], ensure_ascii=False, indent=1)
            + "\n\n" + _OUTPUT)
    return CONTRACT, user


def with_feedback(prompt: tuple[str, str], errors: list[str]) -> tuple[str, str]:
    system, user = prompt
    fb = "\n".join(f"- {e}" for e in errors[:16])
    return system, user + "\n\nA PREVIOUS ATTEMPT FAILED THESE CHECKS; fix every one (keep all other rules):\n" + fb


def build_translation_prompt(units: list[dict]) -> tuple[str, str]:
    system = """You translate short Turkish astrological calendar texts into natural English.
Translate sentence by sentence: the same number of sentences in the same order (each sentence
is traced separately). Second person ("you"), warm, reflective. Keep the same rules: no numbers,
no dates, no technical jargon (aspect names, orb, degrees), no directives or guarantees,
no predicted events."""
    payload = [{"unit_id": u["unit_id"], "sentences": [s["text"] for s in u["sentences"]]} for u in units]
    user = ("UNITS TO TRANSLATE:\n" + json.dumps(payload, ensure_ascii=False, indent=1)
            + '\n\nReturn ONLY: {"units": [{"unit_id": "...", "sentences": ["<English sentence>", ...]}]}')
    return system, user


def build_detox_prompt(unit: dict, lang: str, problems: list[str]) -> tuple[str, str]:
    lang_name = "Turkish" if lang == "tr" else "English"
    system = CONTRACT + f"""
You are now the REWRITE pass for ONE unit of {lang_name} text that broke a rule. Rewrite ONLY what
is needed to remove the listed problems, keeping meaning, tone and the same number of sentences in
the same order. Remove numbers, dates, month names, jargon, directives and certainty words; turn any
predicted event into an inner theme or drop that clause. Keep the text in {lang_name}."""
    user = (f"PROBLEMS: {json.dumps(problems, ensure_ascii=False)}\n\nUNIT:\n"
            + json.dumps({"unit_id": unit["unit_id"], "sentences": [s["text"] for s in unit["sentences"]]},
                         ensure_ascii=False, indent=1)
            + f'\n\nReturn ONLY: {{"units": [{{"unit_id": "{unit["unit_id"]}", "sentences": ["..."]}}]}} '
              f"with exactly {len(unit['sentences'])} sentences.")
    return system, user


def build_length_reask(u: dict, current: dict, got: int) -> tuple[str, str]:
    lo, hi = u["words"]
    user = (f"This unit has {got} Turkish words; it must have between {lo} and {hi}. Rewrite it to fit, "
            "using only its principles (same rules, each sentence with its ids).\n\nUNIT:\n"
            + json.dumps(_unit_payload(u), ensure_ascii=False, indent=1)
            + "\n\nCURRENT:\n" + json.dumps(current, ensure_ascii=False, indent=1) + "\n\n" + _OUTPUT)
    return CONTRACT, user
