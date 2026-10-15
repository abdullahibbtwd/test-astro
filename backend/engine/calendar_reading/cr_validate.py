"""cr_validate.py - calendar text validator (CAL_03 §4, CV1-CV5).

The text-level rules reuse the ACG validator (``ar_validate.text_problems``: AV1
technical leakage, AV2 directives, AV8 event-prediction words, AV10 verdicts,
forbidden reader tokens, encoding corruption). On top of those:

  CV1  trace ⊆ the unit's pool, and every sentence traced
  CV2  no numbers in prose: digits, month names, number-word house references,
       astro jargon (the predictive layer's MODERN/TECH hard lists)
  CV3  AV2 + AV8 unchanged (inside text_problems)
  CV4  a challenging period traces >= 1 mixed/supportive record for its goal
  CV5  TR length within ±20% of the unit's range

A unit is ``{"unit_id", "sentences": [{"text", "ids"}]}``.
"""

from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, os.path.join(_ROOT, "acg_reading"), os.path.join(_ROOT, "prediction_reading")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ar_validate import tr_fold, unit_text, word_count  # noqa: E402
from ar_validate import text_problems as _acg_text_problems  # noqa: E402
from pr_prompts import MODERN_HARD, TECH_HARD  # noqa: E402

from cr_sections import TOLERANCE  # noqa: E402

_W = r"[\wçğıöşüâîûÇĞİÖŞÜ]"
_DIGIT = re.compile(r"\d")
_MONTHS_EN = ["january", "february", "march", "april", "june", "july", "august", "september",
              "october", "november", "december"]           # "may" is also a verb: skipped
_MONTHS_TR = ["ocak", "şubat", "nisan", "mayıs", "haziran", "temmuz", "ağustos", "eylül",
              "ekim", "kasım", "aralık"]                  # "mart" skipped: ambiguous with Mars forms
_ORD_HOUSE = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)\s+house\b|"
    r"(birinci|ikinci|üçüncü|dördüncü|beşinci|altıncı|yedinci|sekizinci|dokuzuncu|onuncu|"
    r"on birinci|onbirinci|on ikinci|onikinci)\s+ev", re.IGNORECASE)
_JARGON = sorted(set(MODERN_HARD) | set(TECH_HARD) | {"derece", "degree", "degrees"})


def _words_re(terms: list[str]) -> re.Pattern:
    return re.compile(r"(?<!" + _W + r")(" + "|".join(re.escape(t) for t in terms) + r")(?!" + _W + r")",
                      re.IGNORECASE)


_MONTH_EN_RE = _words_re(_MONTHS_EN)
_MONTH_TR_RE = re.compile(r"(?<!" + _W + r")(" + "|".join(_MONTHS_TR) + r")")   # prefix: ekim'de
_JARGON_RE = _words_re(_JARGON)
# TR aspect words are also everyday words ("kare" = a square shape), so they count as
# jargon only next to "açı" (angle/aspect) or "açısı", "açı yap...".
_TR_ASPECT_RE = re.compile(r"(?<!" + _W + r")(kare|üçgen|karşıt|karşıtlık|altmışlık|kavuşum)\s+açı")


def cv2_problems(text: str, lang: str) -> list[str]:
    t = text or ""
    probs = []
    if _DIGIT.search(t):
        probs.append(f"CV2 digit in prose {_DIGIT.search(t).group(0)!r}")
    m = (_MONTH_TR_RE.search(tr_fold(t)) if lang == "tr" else _MONTH_EN_RE.search(t))
    if m:
        probs.append(f"CV2 date word {m.group(0)!r}")
    if _ORD_HOUSE.search(t):
        probs.append(f"CV2 house number {_ORD_HOUSE.search(t).group(0)!r}")
    for j in _JARGON_RE.finditer(t):
        probs.append(f"CV2 technical term {j.group(0)!r}")
    for j in _TR_ASPECT_RE.finditer(tr_fold(t)):
        probs.append(f"CV2 technical term {j.group(0)!r}")
    return probs


# CV3 extension (AV8 spirit, CAL_03 §3): no body parts / medical terms / mishaps.
# Medical collocations only: "kalbin olduğu yön" / "gözden geçirmek" are everyday idioms.
_BODY_TR = ["kalp sağlı", "kalp ve dolaşım", "kalp ile dolaşım", "kalp hastal", "kalbini yor",
            "göz çevres", "gözlerin", "göz sağlı", "dolaşım sistem", "kan basıncı", "tansiyon",
            "ameliyat", "cerrahi", "mide", "sindirim", "böbrek", "karaciğer", "akciğer", "sakarl",
            "kardiyovasküler"]
_BODY_EN = re.compile(r"\b(heart|cardiac|cardiovascular|eyes?|circulat\w*|blood pressure|surgery|"
                      r"surgical|stomach|digestion|kidneys?|liver|lungs?|clumsi\w*|injur\w*)\b", re.IGNORECASE)
_BODY_TR_RE = re.compile(r"(?<!" + _W + r")(" + "|".join(_BODY_TR) + r")")
# Prose is 2nd person singular ("sen"); formal verb endings / "siz" pronoun slip in.
# (Possessive "-iniz" is not matched: labels legitimately use it.)
_FORMAL_TR = re.compile(r"(?<!" + _W + r")(siz|sizin|size|sizi|sizde|sizden)(?!" + _W + r")|"
                        r"[\wçğıöşü]+(siniz|sınız|sunuz|sünüz)(?!" + _W + r")")
_EN_PLANETS_IN_TR = re.compile(r"\b(Sun|Moon|Mercury|Venus|Jupiter|Saturn|Uranus|Neptune|Pluto|"
                               r"Ascendant|Midheaven)\b")


def cv3_problems(text: str, lang: str) -> list[str]:
    t = text or ""
    probs = []
    if lang == "tr":
        f = tr_fold(t)
        for m in _BODY_TR_RE.finditer(f):
            probs.append(f"CV3 body/medical word {m.group(0)!r}")
        for m in _EN_PLANETS_IN_TR.finditer(t):
            probs.append(f"CV3 English planet name in Turkish {m.group(0)!r}")
        for m in _FORMAL_TR.finditer(f):
            probs.append(f"CV3 formal 'siz' register {m.group(0)!r} (write in 'sen')")
    else:
        for m in _BODY_EN.finditer(t):
            if m.group(0).lower() == "heart":
                continue                          # "your heart" is figurative in EN prose
            probs.append(f"CV3 body/medical word {m.group(0)!r}")
    return probs


def text_problems(text: str, lang: str) -> list[str]:
    """Everything a detox rewrite can fix: ACG AV1/AV2/AV8/AV10 + tokens + encoding + CV2 + CV3."""
    return _acg_text_problems(text, lang) + cv2_problems(text, lang) + cv3_problems(text, lang)


def bounds(words: tuple[int, int]) -> tuple[int, int]:
    lo, hi = words
    return int(lo * (1 - TOLERANCE)), int(round(hi * (1 + TOLERANCE)))


def validate_unit(unit_plan: dict, tr: dict, en: dict) -> list[str]:
    uid = unit_plan["unit_id"]
    errs: list[str] = []
    pool = {r["id"]: r for r in unit_plan["pool"]}
    for lang, u in (("tr", tr), ("en", en)):
        text = unit_text(u or {})
        if not text:
            errs.append(f"CV5 [{lang}] {uid} is empty")
            continue
        errs += [f"{p} in [{lang}] {uid}" for p in text_problems(text, lang)]
    # CV1 trace (sentence ids are shared by TR and EN)
    for s in (tr or {}).get("sentences", []):
        if not s.get("ids"):
            errs.append(f"CV1 {uid} sentence without ids: {s['text'][:60]!r}")
        for i in s.get("ids", []):
            if i not in pool:
                errs.append(f"CV1 {uid} traces {i!r} outside its pool")
    if tr and en and len(tr.get("sentences", [])) != len(en.get("sentences", [])):
        errs.append(f"CV1 {uid} EN sentence count differs from TR")
    # CV4
    if unit_plan["unit_type"] == "period" and unit_plan["context"]["kind"] == "challenging":
        traced = {i for s in (tr or {}).get("sentences", []) for i in s.get("ids", [])}
        if not any(pool.get(i, {}).get("polarity") in ("mixed", "supportive") for i in traced):
            errs.append(f"CV4 {uid} traces no mixed/supportive record for its goal")
    # CV5
    lo, hi = bounds(unit_plan["words"])
    n = word_count(unit_text(tr or {}))
    if not (lo <= n <= hi):
        errs.append(f"CV5 [tr] {uid} has {n} words (allowed {lo}-{hi})")
    return errs
