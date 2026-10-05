#!/usr/bin/env python3
"""
l4_prompts.py — prompt construction for the section calls (§4) and the single
synthesis pass (§5).

These prompts encode the no-hallucination contract directly: every interpretive
claim must trace to a routed ``principle_id``; tradition names never reach the
reader; classical material is texture, never the verdict; the reading is warm,
second-person, psychological-primary Turkish.

The model is asked to return strict JSON so the orchestrator can validate the
``claims[]`` trace (§6, §7) without parsing prose.
"""

from __future__ import annotations

import json
from typing import Iterable

from l4_sections import (
    CHART_SHAPE, CORE_IDENTITY, INNER_DRIVES, LUMINARY_OF_SECTION, MOVEMENT,
    SECTION_HOUSE, SECTION_THEME, RoutedPrinciple,
)

# Tokens that must never appear in reader-facing text (§7.3). Kept here so the
# prompt's prohibition and the validator's check share one list. House-system
# names are included: the reading is Placidus by policy and never discusses it.
FORBIDDEN_READER_TOKENS = [
    "modern", "classical", "traditional",
    "klasik", "geleneksel",
    "placidus", "whole sign", "whole-sign", "tam burç",
]

_CONTRACT = f"""\
You are the interpretation layer of an astrology application, writing in Turkish.
You turn grounded astrological principles into a warm, layered natal reading.

NON-NEGOTIABLE RULES (the no-hallucination contract):
1. Every interpretive statement you write MUST rest on at least one of the
   principles given to you, cited by its principle_id. You may use the chart
   object for factual cross-reference (positions, rulerships) but you must NEVER
   invent an interpretive claim that no given principle supports.
2. The reading is psychological-primary. Classical heritage (dignities, lord
   placements, sect) is TEXTURE — cultural and historical color woven in lightly. It may enrich but must never carry a section's
   verdict alone. Principles marked "texture": "classical" are this material.
3. When a principle's tradition is "modern" and another is "traditional" and
   they disagree, the modern reading governs the verdict; the other may add
   texture only.
4. A classically negative principle is NEVER delivered as a hard verdict or
   fatalistic prediction. Render it as perspective/heritage; the psychological
   reframe governs.
5. Arabic-Islamic / Ottoman material is framed as cultural-historical heritage,
   never as religious endorsement.
6. NEVER label anything for the reader as "modern", "classical", or
   "traditional" (or Turkish equivalents like "klasik" / "geleneksel"). Tradition
   names and these words must not appear in the Turkish text at all.
7. Voice: second person ("sen"/"sende"), warm, plain Turkish. No jargon dumps.
8. Framework: modern astrology. Houses are Placidus and are the ONLY houses in
   this reading — never name or discuss any house system. All ten planets (Sun
   through Pluto) plus the lunar nodes are full participants: read Uranus,
   Neptune and Pluto by house (and by sign as background) as real personal
   factors whenever the principles support it — never dismiss them as merely
   generational. Rulership follows the modern scheme with the traditional ruler
   kept alongside: Pluto with Mars for Scorpio, Uranus with Saturn for Aquarius,
   Neptune with Jupiter for Pisces; the chart lists both for every house cusp.
"""


# Essential-dignity classification flags -> the dignity label the model reads.
_ESSENTIAL_DIGNITIES = [
    ("in_domicile", "domicile"), ("in_detriment", "detriment"),
    ("in_exaltation", "exaltation"), ("in_fall", "fall"),
    ("in_triplicity", "triplicity"), ("in_own_bound", "bound"),
    ("in_own_face", "face"),
]


def _r(x, n: int = 1):
    return round(x, n) if isinstance(x, (int, float)) else x


def compact_chart(chart: dict) -> dict:
    """A lossless-for-interpretation projection of the chart for the PROMPT only
    (§4 cross-reference). Routing/resolution still read the full chart object —
    this just stops shipping precision the model never needs (4-decimal
    longitudes, cusp arrays, ephemeris meta, sign_index/speed, the whole_sign
    sector_rulers table, and the duplicate whole_sign-scheme aspects) per call.

    Kept: each point's sign / degree / house / retrograde / sign-ruler / essential
    dignities held; the angles; the chart ruler(s); sect; Fortune & Spirit; the
    house rulers with the modern co-ruler where the cusp sign has one; and the
    degree-based (modern) aspects with orbs. Houses are Placidus throughout (the
    only house system in the reading). All of it is fact, never interpretation —
    nothing is re-derived here."""
    rulers_src = (chart.get("sector_rulers") or {}).get("placidus") or {}

    def _ruler_entry(b: dict) -> dict:
        e = {"sign_on_cusp": b.get("sign_on_cusp"), "ruler": b.get("ruler"),
             "ruler_sign": b.get("ruler_sign"), "ruler_house": b.get("ruler_sector")}
        m = b.get("modern_ruler")
        if m and m != b.get("ruler"):
            e["co_ruler"] = m
            e["co_ruler_sign"] = b.get("modern_ruler_sign")
            e["co_ruler_house"] = b.get("modern_ruler_sector")
        return e

    points = []
    for p in chart.get("points", []):
        entry = {
            "name": p.get("name"),
            "sign": p.get("sign"),
            "deg": _r(p.get("degree_in_sign")),
            "house": (p.get("sector") or {}).get("placidus"),
        }
        if p.get("retrograde"):
            entry["retrograde"] = True
        cls = p.get("classifications") or {}
        if cls:
            entry["sign_ruler"] = cls.get("sign_ruler")
            held = [label for key, label in _ESSENTIAL_DIGNITIES if cls.get(key)]
            if held:
                entry["dignities"] = held
        points.append(entry)

    def _axis(a: dict | None) -> dict:
        a = a or {}
        return {"sign": a.get("sign"), "deg": _r(a.get("degree_in_sign"))}

    axes = chart.get("axes") or {}
    dp = chart.get("derived_points") or {}

    aspects = [
        {"source": r["source"], "target": r["target"], "type": r["type"],
         **({"orb": _r(r["orb"], 2)} if "orb" in r else {})}
        for r in chart.get("relations", [])
        if r.get("scheme") == "modern"
    ]

    first = rulers_src.get("1") or {}
    out = {
        "ascendant": _axis(axes.get("ascendant")),
        "mc": _axis(axes.get("mc")),
        "chart_ruler": first.get("ruler"),
    }
    if first.get("modern_ruler") and first.get("modern_ruler") != first.get("ruler"):
        out["chart_co_ruler"] = first["modern_ruler"]
    out.update({
        "is_diurnal": chart.get("is_diurnal"),
        "points": points,
        "house_rulers": {h: _ruler_entry(b) for h, b in rulers_src.items()},
        "fortune": _axis(dp.get("fortune")),
        "spirit": _axis(dp.get("spirit")),
        "aspects": aspects,
    })
    return out


# ---------------------------------------------------------------------------
# Per-section brief (§4): what THIS section is for, with the chart facts it
# needs named explicitly (the luminary's house, the house's occupants and
# ruler(s)). Facts only — the claims must still rest on the routed principles.
# ---------------------------------------------------------------------------

_LUMINARY_FOCUS = {
    "Sun": "identity, vitality and sense of purpose",
    "Moon": "emotional needs, instincts and sense of safety",
}


def _placidus_house(chart: dict, point: str):
    for p in chart.get("points", []):
        if p.get("name") == point:
            return (p.get("sector") or {}).get("placidus")
    return None


def section_brief(section_key: str, chart: dict) -> str:
    """Section-specific instruction appended to the theme (§4)."""
    lum = LUMINARY_OF_SECTION.get(section_key)
    if lum:
        h = _placidus_house(chart, lum)
        return (
            f"SHORT NOTE. The {lum} is in house {h}. Write ONE paragraph of 3-5 "
            f"sentences on what it means that this person's {_LUMINARY_FOCUS[lum]} "
            f"are focused in the affairs of house {h} — grounded in the principles "
            f"given (the house's significations and the {lum}-in-house principle). "
            f"Do not discuss the {lum}'s SIGN here (core_identity covers it) and do "
            f"not cover the whole house (its own section in Part two does). The note "
            f"must stand on its own; it is never a mere cross-reference."
        )
    house = SECTION_HOUSE.get(section_key)
    if house:
        occupants = [p.get("name") for p in chart.get("points", [])
                     if (p.get("sector") or {}).get("placidus") == house]
        rb = ((chart.get("sector_rulers") or {}).get("placidus") or {}).get(str(house)) or {}
        ruler, co = rb.get("ruler"), rb.get("modern_ruler")
        ruler_txt = (f"{ruler} (placed in {rb.get('ruler_sign')}, house "
                     f"{rb.get('ruler_sector')})")
        if co and co != ruler:
            ruler_txt += (f"; modern co-ruler {co} (placed in "
                          f"{rb.get('modern_ruler_sign')}, house "
                          f"{rb.get('modern_ruler_sector')})")
        occ_txt = ", ".join(occupants) if occupants else "none"
        return (
            f"HOUSE {house}. Sign on the cusp: {rb.get('sign_on_cusp')}. Ruler: "
            f"{ruler_txt}. Planets in this house: {occ_txt}. Cover, grounded in the "
            f"principles: (a) what this house means for this person; (b) EVERY "
            f"planet listed in it — Uranus, Neptune and Pluto included — and what it "
            f"brings to this area of life; (c) the cusp sign and the ruler(s) and "
            f"where they sit. If the house holds no planet, read it through its cusp "
            f"sign and ruler(s). Do not restate the Part-one sign portraits."
        )
    if section_key == CHART_SHAPE:
        return (
            "Beyond the aggregate portrait, read Jupiter, Saturn, Uranus, Neptune, "
            "Pluto and the nodes individually by sign and house, as personal factors "
            "in the modern manner. Their house treatment is fuller in Part two — "
            "summarize here and point forward."
        )
    if section_key == CORE_IDENTITY:
        return (
            "Read the Sun and the Moon by SIGN, the Ascendant, and the chart ruler(s) "
            "(traditional ruler and modern co-ruler when there is one). The luminaries' "
            "houses have their own short notes right after this section — mention "
            "them in one clause at most."
        )
    if section_key == INNER_DRIVES:
        return (
            "Read Mercury, Venus and Mars by sign and condition; their house "
            "placements are treated fully in Part two — point forward in one clause "
            "each."
        )
    return ""


def _principles_block(routed: Iterable[RoutedPrinciple]) -> str:
    return json.dumps(
        [rp.as_prompt_dict() for rp in routed],
        ensure_ascii=False,
        indent=2,
    )


def build_section_prompt(section_key: str,
                         routed: list[RoutedPrinciple],
                         chart: dict) -> tuple[str, str]:
    """(system, user) for one section call (§4). The section's grounding is
    structural — it is built ONLY from the principles handed to it, and the
    per-section principle_id trace is attached deterministically downstream from
    routing — so the call returns prose only, no per-sentence claim trace."""
    system = _CONTRACT
    user = f"""\
SECTION: {section_key}  (movement {MOVEMENT[section_key]})
THEME: {SECTION_THEME[section_key]}
BRIEF: {section_brief(section_key, chart)}

GROUNDED PRINCIPLES routed to this section (your ONLY allowed source of claims):
{_principles_block(routed)}

CHART (compact — factual cross-reference only; do not derive new claims from it):
{json.dumps(compact_chart(chart), ensure_ascii=False)}

Write the Turkish reading for THIS section only. Every interpretive statement
must rest on one of the principles above — do not introduce any claim they do not
support. Weave them into flowing prose; do not list them. Honor every rule of the
contract.

Return ONLY a JSON object of this exact shape, no prose around it:

{{ "key": "{section_key}", "text_tr": "<the Turkish reading for this section>" }}

- text_tr is the reading a person will read. Turkish only, non-empty.
"""
    return system, user


def build_synthesis_prompt(drafts: list[dict], chart: dict,
                           low_salience_ids: list[str] | None = None
                           ) -> tuple[str, str]:
    """(system, user) for the single global synthesis pass (§5).

    ``drafts`` is the list of section-call outputs (each a dict with key and
    text_tr). ``low_salience_ids`` are principle_ids flagged as
    generational backdrop / low-confidence methodology, which the pass prunes
    first from chart_shape if it runs long (§5.5). The pass unifies voice, dedups
    across sections, balances texture, prunes chart_shape, and names genuine
    tensions — but adds NO new claim."""
    system = _CONTRACT + """\

You are now performing the SINGLE synthesis pass over all section drafts at once.
This is a rewrite/prune pass over the drafts' text. You may rewrite, merge, trim,
or remove material and rephrase freely. You may NEVER introduce interpretive
content that is absent from the drafts — the drafts are your only source.

Do four jobs, in this priority order:
1. VOICE: rewrite every section into one consistent warm second-person Turkish
   voice, psychological-primary.
2. CROSS-SECTION DEDUP: when the same chart fact is treated in two sections,
   keep the full treatment in its Movement-2 house section ("where it lands")
   and trim the other to a one-line callback that points to it. Never silently
   delete the fact; never repeat the full treatment in both. EXCEPTION: the
   sections sun_house and moon_house are deliberately short dedicated notes on
   the luminary's house — keep their content intact (3-5 sentences); never reduce
   them to a callback.
3. TEXTURE BALANCING: ensure no section leans too heavily on classical texture;
   re-weight toward the psychological body. Classical stays texture, never
   labeled, never dominant.
4. CONTRADICTION: when two sections reflect a genuine chart tension, name it as
   productive tension rather than leaving them silently disagreeing. Do not
   resolve it into blandness and do not invent a bridging claim.
5. CHART_SHAPE SALIENCE PRUNING: chart_shape collects the general-default and
   generational material and can over-accumulate. If it runs long, prune in this
   order: first the low-salience generational backdrop, then low-confidence
   general-methodology material, keeping the highest-confidence structural points
   (sect, dominant element/modality, tightest configuration). Pruning REMOVES
   material (allowed); it never adds. Aim for a tight structural portrait, not a
   methodology dump. The principle_ids listed as LOW-SALIENCE below mark the
   material to drop first.

OUTPUT: for each surviving section, produce the final synthesized reading in
Turkish (`text_tr`) only. English is produced by a separate faithful translation
pass, so do NOT write any English here.
"""
    low_block = json.dumps(sorted(low_salience_ids or []), ensure_ascii=False)
    user = f"""\
SECTION DRAFTS (each: key, text_tr):
{json.dumps(drafts, ensure_ascii=False, indent=2)}

LOW-SALIENCE principle_ids (prune material resting on these from chart_shape
first if it runs long):
{low_block}

CHART (compact — factual cross-reference only):
{json.dumps(compact_chart(chart), ensure_ascii=False)}

Return ONLY a JSON object of this exact shape:

{{
  "sections": [
    {{ "key": "<one of the draft keys>",
       "text_tr": "<the synthesized Turkish reading>" }}
  ]
}}

- Keep the sections that survive synthesis. Do not invent a section that was not
  in the drafts.
- text_tr is required and must be non-empty for every surviving section.
"""
    return system, user


def build_section_synthesis_prompt(section_key: str, own_text_tr: str,
                                   all_drafts: list[dict], chart: dict,
                                   low_salience_ids: list[str] | None = None
                                   ) -> tuple[str, str]:
    """(system, user) for synthesizing ONE section (§5), given every other
    section's draft as read-only context. This replaces the single global call:
    each section's synthesis output is bounded to one section, so it can never
    hit the model's output ceiling no matter how large the whole reading is. The
    other drafts are context so cross-section dedup and contradiction still work.

    Turkish only — English is a separate faithful translation pass."""
    system = _CONTRACT + """\

You are finalizing ONE section of the reading. You are given THIS section's draft
to synthesize, plus every OTHER section's draft as READ-ONLY CONTEXT (so you can
coordinate across the whole reading). Rewrite/trim/merge only THIS section's text.
You may NEVER introduce interpretive content absent from the drafts — the drafts
are your only source. Output only THIS section.

Do these jobs, scoped to THIS section:
1. VOICE: warm, consistent, second-person Turkish, psychological-primary.
2. CROSS-SECTION DEDUP: when a chart fact in THIS section is also treated in
   another section, the fuller treatment belongs in its Movement-2 house section
   ("where it lands"). If THIS section is that Movement-2 home, keep the full
   treatment. If it is NOT, trim the fact here to a one-line callback pointing to
   the section that owns it. Never silently delete a fact; never repeat a full
   treatment that its home section already carries. Use the context drafts to see
   where each fact's home is. EXCEPTION: if THIS section is sun_house or
   moon_house it is a deliberately short dedicated note on the luminary's house —
   keep it self-contained (3-5 sentences, one paragraph); never reduce it to a
   callback, and never expand it into the full house treatment.
3. TEXTURE BALANCING: do not lean too heavily on classical texture; keep the
   psychological body dominant. Classical stays texture, never labeled.
4. CONTRADICTION: if THIS section reflects a genuine chart tension with another
   section (visible in context), name it as productive tension — do not invent a
   bridging claim, do not flatten it into blandness.
5. CHART_SHAPE SALIENCE PRUNING (only if THIS section is chart_shape): it collects
   general-default and generational material and can over-accumulate. If it runs
   long, prune in order: first the low-salience generational backdrop, then
   low-confidence general-methodology material, keeping the highest-confidence
   structural points (sect, dominant element/modality, tightest configuration).
   Pruning REMOVES material; it never adds. The LOW-SALIENCE principle_ids below
   mark what to drop first.

Output Turkish only; English is produced by a separate faithful pass.
"""
    context = [d for d in all_drafts if d.get("key") != section_key]
    low_block = json.dumps(sorted(low_salience_ids or []), ensure_ascii=False)
    user = f"""\
SECTION TO SYNTHESIZE: {section_key}  (movement {MOVEMENT[section_key]})
THEME: {SECTION_THEME[section_key]}
BRIEF: {section_brief(section_key, chart)}

THIS SECTION'S DRAFT (synthesize this — it is your only editable text):
{json.dumps(own_text_tr, ensure_ascii=False)}

OTHER SECTIONS' DRAFTS (READ-ONLY context for dedup / callbacks / contradiction —
do NOT output these, do NOT copy their full treatments in):
{json.dumps(context, ensure_ascii=False)}

LOW-SALIENCE principle_ids (prune material resting on these from chart_shape
first if it runs long):
{low_block}

CHART (compact — factual cross-reference only):
{json.dumps(compact_chart(chart), ensure_ascii=False)}

Return ONLY a JSON object of this exact shape:

{{ "key": "{section_key}", "text_tr": "<the synthesized Turkish reading for THIS section>" }}

- text_tr is required and must be non-empty.
"""
    return system, user


def build_translation_prompt(section_key: str, text_tr: str) -> tuple[str, str]:
    """(system, user) for one section's Turkish→English translation pass. The
    English is a faithful rendering of the ALREADY-synthesized Turkish — no new
    content, no re-interpretation. Split out of synthesis so each call emits one
    section in one language and can never hit the output ceiling."""
    system = _CONTRACT + """\

You are now the FAITHFUL TRANSLATION pass. You are given the final Turkish reading
for ONE section. Render it in warm, natural English that matches the Turkish
EXACTLY in meaning, tone, and warmth: nothing added, dropped, softened, or
reinterpreted. Every contract rule (psychological-primary, classical-as-texture,
NO tradition labels, no fatalism) applies to the English too. Keep astrological
proper nouns in standard English (Sun, Moon, Ascendant, Venus, Libra, …). Do NOT
invent content the Turkish does not contain.

IMPORTANT: if the Turkish contains a tradition-label word (a word naming a school
of astrology — e.g. "geleneksel", "klasik", "modern"), do NOT translate it
literally into "traditional"/"classical"/"modern". Rephrase to convey the same
sense WITHOUT naming a tradition (rule 6), e.g. "an older, inherited way of seeing
this".
"""
    user = f"""\
SECTION: {section_key}

FINAL TURKISH READING (translate this faithfully, in full):
{json.dumps(text_tr, ensure_ascii=False)}

Return ONLY a JSON object of this exact shape, no prose around it:

{{ "key": "{section_key}", "text_en": "<faithful English rendering>" }}

- text_en is required and must be non-empty.
"""
    return system, user


_LANG_NAME = {"tr": "Turkish", "en": "English"}


def build_detox_prompt(section_key: str, text: str, lang: str,
                       tokens: list[str]) -> tuple[str, str]:
    """(system, user) for removing leaked tradition-label words from one section's
    reader-facing text (§7.3). A targeted rewrite: strip the forbidden words while
    keeping meaning, tone, and every other word essentially identical."""
    lang_name = _LANG_NAME.get(lang, lang)
    system = _CONTRACT + f"""\

You are given ONE section's finished {lang_name} reading that accidentally
contains one or more FORBIDDEN tradition-label words. These words name a school of
astrology and must NEVER reach the reader (rule 6 / §7.3).

Rewrite the text so those exact words no longer appear, while keeping the meaning,
tone, warmth, and every other part essentially identical. Do NOT add new content
and do NOT drop any real content. Where the text was labeling material as a
tradition, rephrase to describe it WITHOUT naming a school — e.g. frame it as "an
older, inherited way of seeing this" / "daha eski, köklü bir bakış". Keep the
output in {lang_name}. Keep astrological proper nouns (Sun, Moon, Venus, …) as-is.
"""
    user = f"""\
SECTION: {section_key}   LANGUAGE: {lang_name}
FORBIDDEN WORDS THAT MUST NOT APPEAR IN THE OUTPUT: {json.dumps(tokens, ensure_ascii=False)}

TEXT TO CLEAN:
{json.dumps(text, ensure_ascii=False)}

Return ONLY a JSON object of this exact shape, no prose around it:

{{ "text": "<the cleaned {lang_name} text, none of the forbidden words present>" }}
"""
    return system, user


def build_progressive_finalize_prompt(section_key: str, draft: str,
                                      written: list[dict], own: list[str],
                                      elsewhere: list[dict], chart: dict,
                                      low_salience_ids: list[str] | None = None
                                      ) -> tuple[str, str]:
    """ONB_01: finalize only this draft, with immutable earlier text as context."""
    # Reuse the batch jobs verbatim except for their all-drafts ownership policy.
    batch_system, _ = build_section_synthesis_prompt(section_key, draft, [], chart, low_salience_ids)
    texture_jobs = batch_system[batch_system.index('3. TEXTURE BALANCING:'):]
    exception_start = batch_system.index('EXCEPTION:')
    exception_end = batch_system.index('3. TEXTURE BALANCING:')
    system = _CONTRACT + """
You are finalizing ONE section that will be read in order. Rewrite only THIS
SECTION'S DRAFT. Its draft is the ONLY source of interpretive content. CHART is
for factual cross-reference; context and ownership are not additional sources.
WRITTEN SO FAR contains finalized sections already read: keep the same voice,
do not re-teach what they covered, and name genuine tensions as productive tension.
Backward callbacks are allowed only when their subject is visible in that context.
OWN principles get full treatment.
OWNED ELSEWHERE lists principles whose portrait belongs to another section. Use
these only for THIS section's area of life, never repeat their home portrait.
If needed, refer to the owner by its display title in one clause, without claiming
that a later section has already been read. Do not include a person's name.
1. VOICE: warm, consistent, second-person Turkish, psychological-primary.
2. CROSS-SECTION DEDUP: apply the supplied primary-reason ownership map.
""" + batch_system[exception_start:exception_end] + texture_jobs
    payload = {
        'SECTION': section_key, 'THEME': SECTION_THEME[section_key],
        'BRIEF': section_brief(section_key, chart), "THIS SECTION'S DRAFT": draft,
        'WRITTEN SO FAR': written, 'OWN': own, 'OWNED ELSEWHERE': elsewhere,
        'LOW-SALIENCE ids': sorted(low_salience_ids or []), 'CHART': compact_chart(chart),
    }
    return system, json.dumps(payload, ensure_ascii=False) + '\nReturn only {"key": "' + section_key + '", "text_tr": "..."}.'
