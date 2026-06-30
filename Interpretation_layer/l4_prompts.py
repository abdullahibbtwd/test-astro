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

from l4_sections import MOVEMENT, SECTION_THEME, RoutedPrinciple

# Tokens that must never appear in reader-facing text (§7.3). Kept here so the
# prompt's prohibition and the validator's check share one list.
FORBIDDEN_READER_TOKENS = [
    "modern", "classical", "traditional",
    "klasik", "geleneksel",
]

_CONTRACT = f"""\
You are the interpretation layer of an astrology application, writing in Turkish.
You turn grounded astrological principles into a warm, layered natal reading.

NON-NEGOTIABLE RULES (the no-hallucination contract):
1. Every interpretive statement you write MUST rest on at least one of the
   principles given to you, cited by its principle_id. You may use the chart
   object for factual cross-reference (positions, rulerships) but you must NEVER
   invent an interpretive claim that no given principle supports.
2. The reading is psychological-primary. Classical heritage (dignities, whole-
   sign houses, lord placements, sect) is TEXTURE — cultural and historical
   color woven in lightly. It may enrich but must never carry a section's
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
    sector_rulers table, and the duplicate whole_sign-scheme aspects) 13× per run.

    Kept: each point's sign / degree / placidus house / retrograde / sign-ruler /
    essential dignities held; the angles; the chart ruler; sect; Fortune & Spirit;
    the placidus house rulers; and the degree-based (modern) aspects with orbs.
    All of it is fact, never interpretation — nothing is re-derived here."""
    rulers_src = (chart.get("sector_rulers") or {}).get("placidus") or {}

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

    return {
        "ascendant": _axis(axes.get("ascendant")),
        "mc": _axis(axes.get("mc")),
        "chart_ruler": (rulers_src.get("1") or {}).get("ruler"),
        "is_diurnal": chart.get("is_diurnal"),
        "points": points,
        "house_rulers_placidus": {
            h: {"sign_on_cusp": b.get("sign_on_cusp"), "ruler": b.get("ruler"),
                "ruler_sign": b.get("ruler_sign"), "ruler_house": b.get("ruler_sector")}
            for h, b in rulers_src.items()
        },
        "fortune": _axis(dp.get("fortune")),
        "spirit": _axis(dp.get("spirit")),
        "aspects": aspects,
    }


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
   keep the full treatment in its Movement-2 domain section ("where it lands")
   and trim the other to a one-line callback that points to it. Never silently
   delete the fact; never repeat the full treatment in both.
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

BILINGUAL OUTPUT: for each surviving section, produce the final reading in BOTH
Turkish (`text_tr`) and English (`text_en`). They are two renderings of the SAME
synthesized content — the English must match the Turkish exactly in meaning,
tone, and warmth: nothing added, dropped, softened, or reinterpreted in either.
Every contract rule (psychological-primary, classical-as-texture, NO tradition
labels, no fatalism) applies to BOTH languages. Keep astrological proper nouns in
standard English (Sun, Moon, Ascendant, Venus, Libra, …).
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
       "text_tr": "<the synthesized Turkish reading>",
       "text_en": "<faithful English rendering of the same content>" }}
  ]
}}

- Keep the sections that survive synthesis. Do not invent a section that was not
  in the drafts.
- Both text_tr and text_en are required and must be non-empty for every section.
"""
    return system, user
