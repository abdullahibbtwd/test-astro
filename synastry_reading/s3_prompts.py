#!/usr/bin/env python3
"""
s3_prompts.py — prompt construction for S3 (SYNASTRY_READING_SPEC.md §5, §8).

Three call kinds:
  - section  (§5): the seven axes + the per-person opener. Each gets only its
    routed ``bound_statement``s (+ ``bound`` for attribution) and writes Turkish
    prose. It never sees raw chart positions (§2) — grounding is the bound facts.
  - synthesis (§5): weaves the eight drafts into one voice, resolves cross-section
    repetition, writes an honest qualitative overall (no score, §6), and emits
    BOTH Turkish and a faithful English (§5).
  - statements (§11): breaks the final reading into atomic self-scorable
    statements, each tagged with the grounded record id(s) it rests on (for S4).

The shared block (contract + framing stance + person labels) is built once and
marked cacheable in ``s3_generate.py`` (§5 prompt caching).

The mask (§8) is encoded in the contract AND enforced downstream by
``s3_validate.py`` — the prompt's prohibition and the validator's ban list share
the vocabulary below.
"""

from __future__ import annotations

import json
from typing import Iterable, Optional

from s3_sections import MOVEMENT, SECTION_THEME, RoutedRecord

# ---------------------------------------------------------------------------
# The tradition mask (§8). Two tiers so the validator does not false-positive on
# ordinary romantic English.
# ---------------------------------------------------------------------------

# HARD-BANNED: unambiguous classical machinery + tradition names. These have no
# ordinary-language collision, so a hit is always a mask leak (§10.3).
HARD_BANNED_TERMS = [
    # reception machinery
    "reception", "receptions",
    # essential dignities / debilities
    "domicile", "exaltation", "exalted", "triplicity", "peregrine",
    "debility", "detriment",
    "decan", "decans",
    # technical apparatus
    "overlay", "overlays", "significator", "significators",
    "dignity", "dignities",
    "house cusp", "house cusps",
    "diurnal", "nocturnal",
    "ptolemaic", "hellenistic",
    # tradition labels (mirrors the natal L4 ban)
    "classical", "traditional", "klasik", "geleneksel",
]

# CONTEXT-BANNED: technical only in these phrasings. Bare "fall"/"face"/"bound"/
# "receive" are ordinary romantic words ("fall in love", "face a challenge",
# "bound together", "receive affection") and must NOT be blanket-banned. We catch
# only the astrological usage via regex bigrams and the "Nth house" leak.
CONTEXT_BANNED_PATTERNS = [
    r"\bin\s+detriment\b",
    r"\bin\s+fall\b",
    r"\breceives?\s+by\b",
    r"\breceiving\s+planet\b",
    r"\breceived\s+planet\b",
    r"\bby\s+(?:domicile|exaltation|triplicity|bound|face|term)\b",
    r"\bapplying\s+aspect\b",
    r"\bseparating\s+aspect\b",
    r"\bmutual\s+reception\b",
    # "your 10th house" / "the 7th house" style leaks (English)
    r"\b\d+(?:st|nd|rd|th)\s+house\b",
    # Turkish ordinal-house leak: "10. ev" / "7. evinde"
    r"\b\d+\.\s*ev(?:i|in|inde|ine|inden)?\b",
]

# What the model is TOLD not to write (superset, human-readable).
_MASK_VOCAB_FOR_PROMPT = (
    "reception / receive / receiving / received (in the technical sense), "
    "domicile, exaltation, exalted, triplicity, bound(s)/term, face/decan, "
    "overlay, house cusp, orb, applying, separating, significator, dignity, "
    "debility, detriment, fall (as a placement), peregrine, sect, "
    "diurnal / nocturnal, and any tradition names (classical, traditional, "
    "Hellenistic, Arabic, modern, Ptolemaic) — in Turkish or English"
)


def _labels_line(label_a: str, label_b: str) -> str:
    return (
        f"PERSON LABELS. In every bound_statement, \"A\" means {label_a!r} and "
        f"\"B\" means {label_b!r}. Render the people with these labels naturally; "
        f"never write the bare letters \"A\"/\"B\" or \"person A\"/\"person B\"."
    )


def build_contract(framing: Optional[Iterable[dict]] = None,
                   *, label_a: str = "sen", label_b: str = "partnerin") -> str:
    """The shared, cacheable contract block (§5). Encodes the mask, the
    attribution rule, the qualitative-only rule, the interpretive stance drawn
    from ``framing`` (stance only — never content), and the person labels."""
    stance_lines = ""
    if framing:
        items = []
        for f in framing:
            j = (f.get("judgment") or f.get("rule") or "").strip()
            if j:
                items.append(f"- {j}")
        if items:
            stance_lines = (
                "\n\nINTERPRETIVE STANCE (shapes HOW you write — it is NOT content, "
                "and none of it becomes a statement about this couple):\n"
                + "\n".join(items)
            )

    return f"""\
You are the relationship-reading layer of an astrology application, writing in
Turkish. You turn grounded facts about how two people's charts interact into ONE
coherent, warm, romance-first reading for the couple. You present a single modern
voice; the classical machinery underneath is invisible.

NON-NEGOTIABLE RULES:

1. TRACEABILITY. Every claim you write MUST rest on one of the bound_statements
   handed to you. Do NOT assert any placement, aspect, or dynamic that is not in
   your given material. Invent nothing — no positions, no facts.

2. ATTRIBUTION comes ONLY from each record's `bound` block, which already encodes
   the correct direction (who acts on whom). Never infer who is who from anything
   else. {_labels_line(label_a, label_b)}

3. THE MASK. The reading is one modern, plain-language voice. The following
   vocabulary must NEVER appear in what you write: {_MASK_VOCAB_FOR_PROMPT}.
   Some bound_statements still contain this scaffolding (e.g. "the receiving
   planet", "in the received planet's affairs"). TRANSLATE the meaning into
   ordinary relational language — welcome, accommodation, drawing-out, holding,
   protecting — never echo the technical phrasing. House meanings become
   life-areas in plain words (career, home, intimacy, money), never "the 10th
   house".

4. NO SCORE. Never emit or imply a compatibility percentage, number, or letter
   grade. If you characterize an axis, use plain words (strong, easy, effortful,
   volatile), never a scalar.

5. ASYMMETRY. Where a dynamic runs mainly one way (the bound block makes the
   direction explicit), state it plainly ("this asks more patience of {label_b}
   than of {label_a}"). Do not flatten genuine one-sidedness into false mutuality.

6. VOICE. Warm, grounded, second person, plain modern Turkish. Romance-first:
   write to a couple about their bond. No jargon, no lists of factors, no
   fatalism — a classically "hard" contact is rendered as real, workable texture,
   never a verdict of doom.{stance_lines}
"""


# ---------------------------------------------------------------------------
# Section call (§5)
# ---------------------------------------------------------------------------

def _records_block(routed: Iterable[RoutedRecord]) -> str:
    return json.dumps([r.as_prompt_dict() for r in routed],
                      ensure_ascii=False, indent=2)


def build_section_user(section_key: str, routed: list[RoutedRecord],
                       *, houses_valid: bool = True,
                       label_a: str = "sen", label_b: str = "partnerin") -> str:
    """User message for one axis call (§5). The opener has its own builder."""
    degrade = ""
    if not houses_valid and section_key in {"emotional", "values", "purpose"}:
        degrade = (
            "\n\nNOTE: this couple's birth times are not both exact, so life-area "
            "detail that depends on home/house placements is unavailable. Write "
            "from the contact material you DO have, and where a house-based nuance "
            "would normally go, say plainly that some of this detail cannot be "
            "confirmed without exact birth times. Do not invent it."
        )
    return f"""\
SECTION: {section_key}  (axis {MOVEMENT[section_key]})
THEME: {SECTION_THEME[section_key]}

GROUNDED FACTS routed to this section (your ONLY allowed source of claims). Read
`bound_statement` for the content and `bound` for who-acts-on-whom:
{_records_block(routed)}

Write the Turkish reading for THIS section only. Weave the facts into flowing
romance-first prose addressed to the couple — do not list them. Every statement
must rest on one of the facts above. Honor every rule of the contract, especially
the mask (no technical vocabulary) and attribution (only from `bound`).{degrade}

Return ONLY a JSON object of this exact shape, no prose around it:

{{ "key": "{section_key}", "text_tr": "<the Turkish reading for this section>" }}
"""


def build_opener_user(routed: list[RoutedRecord], *,
                      label_a: str = "sen", label_b: str = "partnerin") -> str:
    """User message for the per-person opener (§3 section 0). One short paragraph
    per person describing their own capacity to partner — not a claim about the
    pair."""
    a_recs = [r for r in routed if r.person == "A"]
    b_recs = [r for r in routed if r.person == "B"]
    return f"""\
SECTION: what_each_brings  (the opener)
THEME: {SECTION_THEME['what_each_brings']}

Write TWO short paragraphs, one per person, describing the relational nature each
brings on their own — how they love, need, and bond — as standing ground, NOT a
compatibility claim about the two together.

{label_a.upper()}'S material (write {label_a}'s paragraph from these):
{_records_block(a_recs)}

{label_b.upper()}'S material (write {label_b}'s paragraph from these):
{_records_block(b_recs)}

Ground every statement in the facts above. Honor the mask (no technical
vocabulary) and every contract rule. Warm, plain Turkish.

Return ONLY a JSON object of this exact shape:

{{ "key": "what_each_brings", "text_tr": "<{label_a}'s paragraph>\\n\\n<{label_b}'s paragraph>" }}
"""


# ---------------------------------------------------------------------------
# Synthesis call (§5, §6)
# ---------------------------------------------------------------------------

def build_synthesis_system(contract: str) -> str:
    return contract + """\

You are now performing the SINGLE synthesis pass over all section drafts at once.
This is a rewrite/weave pass over the drafts' text. You may rewrite, merge, trim,
reorder, and rephrase freely. You may NEVER introduce a claim absent from the
drafts — the drafts are your only source.

Do these jobs:
1. ONE VOICE: rewrite every section into one consistent warm, romance-first,
   second-person Turkish voice.
2. DEDUP ACROSS SECTIONS: when the same contact was treated in two sections (e.g.
   a Venus-Mars square in both Attraction and Friction), keep the full treatment
   in the section where it lands most naturally and trim the other to a short
   callback. Never silently drop the fact; never repeat it in full twice.
3. NAME REAL TENSION: where two sections reflect a genuine tension in the bond,
   name it as productive tension, not blandness — and do not invent a bridging
   claim.
4. HONEST OVERALL (qualitative, NO score): the synthesis may give each axis a
   plain-language texture and an honest overall sense of the bond. NEVER a
   number, percentage, or grade. If you write a summary line, it names the axes'
   texture, not a scalar.

BILINGUAL OUTPUT: for each surviving section, produce the final reading in BOTH
Turkish (`text_tr`) and English (`text_en`). They are two renderings of the SAME
content — the English must match the Turkish 1:1 in every claim, tone, and
warmth: nothing added, dropped, softened, or reinterpreted. Every contract rule
(the mask, no-score, no-fatalism, attribution) applies to BOTH languages. Keep
astrological proper nouns in standard English (Sun, Moon, Venus, Libra, …) — but
the banned technical vocabulary stays banned in English too.
"""


def build_synthesis_user(drafts: list[dict]) -> str:
    """``drafts`` is the list of section-call outputs (key + text_tr), including
    the opener."""
    return f"""\
SECTION DRAFTS (each: key, text_tr):
{json.dumps(drafts, ensure_ascii=False, indent=2)}

Return ONLY a JSON object of this exact shape:

{{
  "sections": [
    {{ "key": "<one of the draft keys>",
       "text_tr": "<the synthesized Turkish reading>",
       "text_en": "<faithful English rendering of the same content>" }}
  ]
}}

- Keep the sections that survive synthesis, in the given order. Do not invent a
  section that was not in the drafts.
- Both text_tr and text_en are required and non-empty for every section.
"""


# ---------------------------------------------------------------------------
# Statements call (§11) — atomic self-scorable statements with source ids.
# ---------------------------------------------------------------------------

def build_statements_system(contract: str) -> str:
    return contract + """\

You are now extracting ATOMIC, SELF-CONTAINED statements from the FINAL reading,
for an evaluation harness. Each statement is one checkable claim about the couple,
readable on its own, in both Turkish and English, and tagged with the id(s) of the
grounded record(s) it rests on.

Rules:
- Every statement must be traceable to one or more of the ALLOWED record ids given
  for its section. Use ONLY ids from that section's allowed list.
- Do not invent claims the reading does not make. Do not include the opener's
  scene-setting fluff — only substantive relational claims.
- Statements inherit the mask and no-score rules: no technical vocabulary, no
  numbers/grades.
- Keep each statement to one idea. Prefer 3-8 statements per section.
"""


def build_statements_user(final_sections: list[dict],
                          allowed_ids_by_section: dict[str, list[str]]) -> str:
    """``final_sections`` = the synthesized sections (key, text_tr, text_en).
    ``allowed_ids_by_section`` = the routed record ids available per section."""
    payload = {
        "sections": [
            {
                "key": s.get("key"),
                "text_tr": s.get("text_tr", ""),
                "text_en": s.get("text_en", ""),
                "allowed_record_ids": allowed_ids_by_section.get(s.get("key"), []),
            }
            for s in final_sections
        ]
    }
    return f"""\
FINAL READING (per section: key, text_tr, text_en, allowed_record_ids):
{json.dumps(payload, ensure_ascii=False, indent=2)}

Return ONLY a JSON object of this exact shape:

{{
  "statements": [
    {{ "section": "<section key>",
       "text_tr": "<atomic claim in Turkish>",
       "text_en": "<same claim in English>",
       "source_ids": ["<record id from that section's allowed list>", "..."] }}
  ]
}}

- Every source_ids entry MUST come from that section's allowed_record_ids.
- Every statement needs at least one source_id.
"""
