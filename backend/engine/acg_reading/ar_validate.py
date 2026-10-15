#!/usr/bin/env python3
"""ar_validate.py — the ACG reading validator (spec 04 §5 AV1–AV8 + 07 §6.4 AV9–AV12).

It refuses to ship any contract violation. It works on the unit form the generator
produces (``{unit_id: {"sentences": [{"text", "ids"}]}}`` per section and language) and
on the final reading JSON, and returns a list of error strings (empty = pass).

Text-level checks (``text_problems``) are also what the generator's detox rewrite
targets, so the rewrite clears exactly what the validator would flag.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_L4 = os.path.join(_ROOT, "Interpretation_layer")
if _L4 not in sys.path:
    sys.path.insert(0, _L4)

from ar_sections import BANDS, SECTIONS, length_bounds  # noqa: E402

try:                                            # share the natal reader-token list
    from l4_prompts import FORBIDDEN_READER_TOKENS  # noqa: E402
except Exception:  # pragma: no cover
    FORBIDDEN_READER_TOKENS = ["modern", "classical", "traditional", "klasik", "geleneksel",
                               "placidus", "whole sign", "whole-sign", "tam burç"]

_W = r"[\wçğıöşüâîûÇĞİÖŞÜ]"


def _words_re(terms: list[str]) -> re.Pattern:
    return re.compile(r"(?<!" + _W + r")(" + "|".join(re.escape(t) for t in terms) + r")(?!"
                      + _W + r")", re.IGNORECASE)


def tr_fold(text: str) -> str:
    """Turkish-aware casefold: İ->i, I->ı before lower()."""
    return (text or "").replace("İ", "i").replace("I", "ı").lower()


# AV1 — technical leakage
_AV1_NUM_UNIT = re.compile(r"\d[\d.,]*\s*(km\b|°|derece|kilometre|mil\b|miles?\b|kilometers?\b|degrees?\b)",
                           re.IGNORECASE)
_AV1_WORDS = _words_re(["boylam", "enlem", "longitude", "latitude", "orb", "yükselen çizgi",
                        "tepe noktası", "hour angle", "paran", "parans"])
_AV1_ABBR = re.compile(r"\b(ASC|MC|DSC|IC)\b")                     # case-sensitive
_AV1_HOUSE = re.compile(r"\b\d{1,2}\.\s?ev|\b\d{1,2}(st|nd|rd|th) house", re.IGNORECASE)

# AV2 — directive / fatalistic (also the detox list)
AV2_TR = ["taşınmalısın", "taşınmalısınız", "taşının", "kaçının", "uzak durun", "kesinlikle",
          "garanti", "asla yaşama"]
AV2_EN = ["you should move", "must move", "avoid living", "stay away", "guarantee",
          "definitely will"]
# AV8 — event prediction for sensitive themes
AV8_TR = ["ölüm", "öleceksin", "kaza geçir", "saldırıya uğra", "hastalanacak", "suça karış",
          "suç işle", "bağımlı ol"]
AV8_EN = ["death", "die", "accident", "attacked", "will fall ill", "crime", "addiction"]
# AV10 — yes/no verdicts
AV10_TR = ["evet", "hayır", "kesinlikle uygun", "uygun değil", "taşınmalı"]
AV10_EN_RE = re.compile(r"(?<![\w])(yes,|no,)|\b(definitely suitable|not suitable|you should)\b",
                        re.IGNORECASE)

_TR_PREFIX = lambda terms: re.compile(  # noqa: E731 — prefix match for agglutinative TR
    r"(?<!" + _W + r")(" + "|".join(re.escape(tr_fold(t)) for t in terms) + r")")
_AV2_TR_RE = _TR_PREFIX(AV2_TR)
_AV8_TR_RE = _TR_PREFIX(AV8_TR)
_AV10_TR_RE = re.compile(r"(?<!" + _W + r")(evet|hayır)(?!" + _W + r")|"
                         + r"(kesinlikle uygun|uygun değil|taşınmalı)")
_AV2_EN_RE = _words_re(AV2_EN)
_AV8_EN_RE = re.compile(r"\b(death|deaths|die|dies|dying|accidents?|attacked|will fall ill|"
                        r"crimes?|criminal|addictions?)\b", re.IGNORECASE)
_FORBIDDEN_RE = _words_re(FORBIDDEN_READER_TOKENS)

# planet names (AV3 / AV12). TR "Ay" (Moon) is matched case-sensitively; the
# lowercase month/"ay" never matches.
PLANET_PATTERNS = {
    "sun": (r"\bGüneş", r"\bSun\b"), "moon": (r"\bAy\b", r"\bMoon\b"),
    "mercury": (r"\bMerkür", r"\bMercury\b"), "venus": (r"\bVenüs", r"\bVenus\b"),
    "mars": (r"\bMars", r"\bMars\b"), "jupiter": (r"\bJüpiter", r"\bJupiter\b"),
    "saturn": (r"\bSatürn", r"\bSaturn\b"), "uranus": (r"\bUranüs", r"\bUranus\b"),
    "neptune": (r"\bNeptün", r"\bNeptune\b"), "pluto": (r"\bPlüton", r"\bPluto\b"),
}


def planets_named(text: str, lang: str) -> set[str]:
    i = 0 if lang == "tr" else 1
    return {p for p, pats in PLANET_PATTERNS.items() if re.search(pats[i], text or "")}


# Corrupted model output (seen live: "iliřkiler", "bi%cimde", "Nept%un"): letters from
# Latin Extended-A/B that neither Turkish nor the gazetteer's place names use, or a
# percent sign glued to a letter.
_TURKISH_EXT = set("ğĞıİşŞ")
_ENC_PCT = re.compile(r"%[A-Za-z]")


def encoding_problems(text: str) -> list[str]:
    bad = sorted({c for c in (text or "") if 0x100 <= ord(c) <= 0x24F and c not in _TURKISH_EXT})
    probs = [f"ENC corrupted character(s) {''.join(bad)!r}"] if bad else []
    if _ENC_PCT.search(text or ""):
        probs.append(f"ENC corrupted sequence {_ENC_PCT.search(text).group(0)!r}")
    return probs


def text_problems(text: str, lang: str) -> list[str]:
    """AV1, AV2, AV8, AV10, the forbidden reader tokens and encoding corruption."""
    t = text or ""
    probs: list[str] = encoding_problems(t)
    for m in _AV1_NUM_UNIT.finditer(t):
        probs.append(f"AV1 number+unit {m.group(0)!r}")
    for m in _AV1_WORDS.finditer(t):
        probs.append(f"AV1 technical word {m.group(0)!r}")
    for m in _AV1_ABBR.finditer(t):
        probs.append(f"AV1 angle abbreviation {m.group(0)!r}")
    for m in _AV1_HOUSE.finditer(t):
        probs.append(f"AV1 house number {m.group(0)!r}")
    for m in _FORBIDDEN_RE.finditer(t):
        probs.append(f"forbidden reader token {m.group(0)!r}")
    if lang == "tr":
        f = tr_fold(t)
        probs += [f"AV2 directive {m.group(0)!r}" for m in _AV2_TR_RE.finditer(f)]
        probs += [f"AV8 event word {m.group(0)!r}" for m in _AV8_TR_RE.finditer(f)]
        probs += [f"AV10 verdict {m.group(0)!r}" for m in _AV10_TR_RE.finditer(f)]
    else:
        probs += [f"AV2 directive {m.group(0)!r}" for m in _AV2_EN_RE.finditer(t)]
        probs += [f"AV8 event word {m.group(0)!r}" for m in _AV8_EN_RE.finditer(t)]
        probs += [f"AV10 verdict {m.group(0)!r}" for m in AV10_EN_RE.finditer(t)]
    return probs


def word_count(text: str) -> int:
    return len((text or "").split())


def unit_text(unit: dict) -> str:
    return " ".join(s["text"].strip() for s in unit.get("sentences", []) if s["text"].strip())


# ---------------------------------------------------------------------------
# Full validation
# ---------------------------------------------------------------------------

def validate(reading: dict, plan: dict, pools: dict, polarity_of: dict,
             allowed_ids: set[str]) -> list[str]:
    """``reading``: {"tr": {section: {unit_id: unit}}, "en": {...}, "cards": [...]}
    (the generator's internal form). ``pools``: unit_id -> the ids it may trace.
    ``polarity_of``: id -> polarity. ``allowed_ids``: every id in acg_principles.json."""
    errors: list[str] = []
    place = plan["place"]
    planned = {s["key"] for s in plan["sections"]}
    for lang in ("tr", "en"):
        secs = reading.get(lang, {})
        # AV7: omitted sections are absent, never empty
        for key in secs:
            if key not in planned:
                errors.append(f"AV7 [{lang}] unexpected section {key!r}")
        for key in planned:
            if key == "suitability":
                continue
            if key not in secs or not secs[key]:
                errors.append(f"AV7 [{lang}] planned section {key!r} missing or empty")
        for key, units in secs.items():
            for uid, unit in units.items():
                text = unit_text(unit)
                if not text:
                    errors.append(f"AV7 [{lang}] {key}/{uid} is empty")
                    continue
                errors += [f"{p} in [{lang}] {key}/{uid}" for p in text_problems(text, lang)]
                # AV4 trace
                ids = [i for s in unit["sentences"] for i in s.get("ids", [])]
                if lang == "tr":
                    if not ids:
                        errors.append(f"AV4 [{lang}] {key}/{uid} has no trace")
                    for s in unit["sentences"]:
                        if not s.get("ids"):
                            errors.append(f"AV4 [{lang}] {key}/{uid} sentence without ids: "
                                          f"{s['text'][:60]!r}")
                    for i in ids:
                        if i not in allowed_ids:
                            errors.append(f"AV4 [{lang}] {key}/{uid} traces unknown id {i!r}")
                        elif i not in pools.get(uid, set()):
                            errors.append(f"AV4 [{lang}] {key}/{uid} traces {i!r} outside its pool")
                    # AV6 lengths (TR)
                    lo, hi = length_bounds(key)
                    n = word_count(text)
                    if not (lo <= n <= hi):
                        errors.append(f"AV6 [{lang}] {key}/{uid} has {n} words (allowed {lo}–{hi})")
                    # AV11 polarity (one id per sentence)
                    if key in ("positives", "challenges"):
                        ok_pol = ("supportive", "mixed") if key == "positives" else \
                            ("challenging", "mixed")
                        for s in unit["sentences"]:
                            if len(s.get("ids", [])) != 1:
                                errors.append(f"AV11 [{lang}] {key}: sentence must trace exactly "
                                              f"one record: {s['text'][:60]!r}")
                            for i in s.get("ids", []):
                                if polarity_of.get(i) not in ok_pol:
                                    errors.append(f"AV11 [{lang}] {key} traces {i!r} with polarity "
                                                  f"{polarity_of.get(i)!r}")
                # AV3 / AV12 planet coverage
                named = planets_named(text, lang)
                if key == "lines_here":
                    extra = named - set(plan["line_bodies"])
                    if extra:
                        errors.append(f"AV3 [{lang}] lines_here/{uid} names unselected "
                                      f"planet(s) {sorted(extra)}")
                if key == "background_influences":
                    extra = named - set(plan.get("paran_bodies", []))
                    if extra:
                        errors.append(f"AV12 [{lang}] background_influences/{uid} names "
                                      f"planet(s) {sorted(extra)} not in the near parans")
                if key in ("positives", "challenges"):
                    extra = named - set(plan["line_bodies"])
                    if extra:
                        errors.append(f"AV12 [{lang}] {key} names planet(s) {sorted(extra)} not "
                                      f"on a selected line")
        # AV3 coverage: every selected line's planet named in lines_here
        if "lines_here" in secs:
            named_all = set()
            for unit in secs["lines_here"].values():
                named_all |= planets_named(unit_text(unit), lang)
            missing = set(plan["line_bodies"]) - named_all
            if missing:
                errors.append(f"AV3 [{lang}] lines_here never names {sorted(missing)}")
        # AV5 overview names the place
        ov = secs.get("place_overview", {})
        want = place["name_tr"] if lang == "tr" else place["name"]
        ov_text = " ".join(unit_text(u) for u in ov.values())
        if want and want.casefold() not in ov_text.casefold():
            errors.append(f"AV5 [{lang}] place_overview does not name {want!r}")

    # AV9 cards
    for card in reading.get("cards", []):
        for lang in ("tr", "en"):
            label = BANDS[card["band"]][0 if lang == "tr" else 1]
            text = card.get(f"text_{lang}", "")
            if not text.startswith(label):
                errors.append(f"AV9 card {card['card']} [{lang}] does not start with {label!r}")
            errors += [f"{p} in card {card['card']} [{lang}]"
                       for p in text_problems(text[len(label):] if text.startswith(label) else text,
                                              lang)]
        allowed = set(card.get("contributors", [])) | {plan["no_emphasis_id"],
                                                       "acg-method-orb-distance"}
        if not card.get("trace"):
            errors.append(f"AV4 card {card['card']} has no trace")
        for i in card.get("trace", []):
            if i not in allowed:
                errors.append(f"AV9 card {card['card']} traces {i!r} outside its contributors")
        if not card.get("template"):
            n = word_count(card.get("text_tr", ""))
            lo, hi = length_bounds("suitability")
            if not (lo <= n <= hi):
                errors.append(f"AV6 card {card['card']} has {n} words (allowed {lo}–{hi})")
    return errors


def is_blocking(errors: list[str]) -> bool:
    return bool(errors)
