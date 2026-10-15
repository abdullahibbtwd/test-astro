#!/usr/bin/env python3
"""
backfill.py — populate ``about`` + ``requires`` on every principle record via the
confidence-tiered cascade of PRINCIPLE_GROUNDING_SPEC.md §2.

    Tier 1  strict ID parse, corroborated by conditions/tags   -> id_parse / high
    Tier 2  conditions/tags cross-check (resolved fact)         -> conditions_crosscheck / medium|high
    Tier 3  schema-constrained extraction (LLM, pluggable)      -> llm / <=medium
    fallback                                                    -> unclassified / low

For each record the cascade stops at the first tier that yields a confident
subject. Every record is processed (all domains) so the corpus is internally
consistent; only ``natal`` survives the gate's domain pre-filter at read time.

``requires`` is the normalized projection of the poly-typed ``conditions`` field
(list / str / dict) into dependency tokens for gate C. The original ``conditions``
is preserved verbatim for provenance (spec §1, §8).

The Tier-3 extractor is pluggable (the ``Extractor`` protocol), mirroring the
embedder pattern in ``retrival_contract/retrieval.py``. ``make_default_extractor()``
returns an Anthropic-backed extractor when ``ANTHROPIC_API_KEY`` and the SDK are
present, otherwise a deterministic, fully-offline heuristic extractor. Either way
Tier-3 output is schema-validated against ``grounding_schema`` and capped at
``medium`` — off-vocabulary output is rejected, never silently accepted.

Run
---
    python backfill.py                       # all_principles.clean.json -> all_principles.grounded.json
    python backfill.py --in X --out Y --report report.json
    python backfill.py --no-llm              # Tier 1/2 only; rest -> unclassified
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from typing import Any, Optional, Protocol

from grounding_schema import invariant_violation, validate_about, validate_requires
from grounding_vocab import (
    DIGNITIES,
    HOUSE_WORDS,
    POINTS,
    RECONCILABLE_FACTOR_TYPES,
    SIGNS,
    canon_aspect,
    canon_point,
    canon_sign,
)

# ---------------------------------------------------------------------------
# conditions -> normalized text helpers (the field is list / str / dict)
# ---------------------------------------------------------------------------

def _conditions_strings(conditions: Any) -> list[str]:
    """Flatten the poly-typed conditions field into a list of strings."""
    if conditions is None:
        return []
    if isinstance(conditions, str):
        return [conditions]
    if isinstance(conditions, dict):
        # e.g. {"planet": "Mars", "house": 2} -> ["planet: Mars", "house: 2"]
        return [f"{k}: {v}" for k, v in conditions.items()]
    if isinstance(conditions, list):
        out: list[str] = []
        for item in conditions:
            out.extend(_conditions_strings(item))
        return out
    return [str(conditions)]


def _conditions_blob(record: dict) -> str:
    parts = _conditions_strings(record.get("conditions"))
    return " ; ".join(parts).lower()


# ---------------------------------------------------------------------------
# requires — normalize conditions into dependency tokens (gate C input)
# ---------------------------------------------------------------------------

_GENDER_RE = re.compile(r"\b(sex of (the )?native|gender|male|female|men|women)\b")
_TIME_RE = re.compile(r"\b(birth time|time of birth|exact time|planetary hour|diurnal or nocturnal|sect)\b")
_ASPECT_RE = re.compile(r"\baspect")
_DIGNITY_RE = re.compile(r"\b(domicile|detriment|exalt|fall|triplicit|bound|term|face|dignit)")
_ELEMENT_RE = re.compile(r"\belement\b")
_ASC_RE = re.compile(r"\b(ascendant|rising|asc\b)")
_RULER_RE = re.compile(r"\b(ruler of|lord of|house ruler|sign ruler|lord)\b")
_HOUSE_RE = re.compile(r"\bhouse\b|\bcusp\b")
_SIGN_DEP_RE = re.compile(r"\bsign\b")


def _points_mentioned(text: str) -> list[str]:
    found = []
    for p in POINTS:
        if p.lower() in text:
            found.append(p)
    return found


def extract_requires(record: dict) -> list[dict]:
    """Project conditions into deduped dependency tokens for gate C."""
    blob = _conditions_blob(record)
    reqs: list[dict] = []
    seen: set[tuple] = set()

    def add(kind: str, point: str | None = None) -> None:
        key = (kind, point)
        if key not in seen:
            seen.add(key)
            req: dict = {"kind": kind}
            if point:
                req["point"] = point
            reqs.append(req)

    if not blob:
        return reqs

    pts = _points_mentioned(blob)

    if _GENDER_RE.search(blob):
        add("native_gender")
    if _TIME_RE.search(blob):
        add("birth_time")
    if _ASC_RE.search(blob):
        add("ascendant")
    if _RULER_RE.search(blob):
        add("house_ruler")
    if _ELEMENT_RE.search(blob):
        # element of a named point's sign, else generic sign_element
        if pts:
            for p in pts:
                add("sign_element", p)
        else:
            add("sign_element")
    if _ASPECT_RE.search(blob):
        if pts:
            for p in pts:
                add("point_aspects", p)
        else:
            add("point_aspects")
    if _DIGNITY_RE.search(blob):
        for p in pts:
            add("point_dignity", p)
    if _HOUSE_RE.search(blob):
        for p in pts:
            add("point_house", p)
    if _SIGN_DEP_RE.search(blob) and "element" not in blob:
        for p in pts:
            add("point_sign", p)

    if not reqs:
        add("other")
    return reqs


# ---------------------------------------------------------------------------
# Tier 1 — strict ID parse, corroborated by conditions
# ---------------------------------------------------------------------------

# planet-sign-SIGN-...  (e.g. mars-sign-aries-delineation)
_ID_SIGN_RE = re.compile(
    r"^(sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto)"
    r"-sign-(aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|"
    r"sagittarius|capricorn|aquarius|pisces)\b"
)
# {planet|point}-{ordinal}-...  (e.g. mars-2nd-poverty, south-node-2nd-...)
_ID_HOUSE_RE = re.compile(
    r"^(north-node|south-node|sun|moon|mercury|venus|mars|jupiter|saturn|"
    r"uranus|neptune|pluto)-(\d{1,2})(?:st|nd|rd|th)?-"
)
# own-dignity, e.g. venus-in-own-domicile-natal, saturn-in-own-bound...
_ID_OWN_DIGNITY_RE = re.compile(
    r"^(sun|moon|mercury|venus|mars|jupiter|saturn)-in-own-"
    r"(domicile|detriment|exaltation|fall|triplicity|bound|term|face)"
)

_TERM_TO_DIGNITY = {"term": "bound"}


def _corroborates_sign(record: dict, point: str, sign: str) -> bool:
    blob = _conditions_blob(record)
    return f"{point.lower()} in {sign.lower()}" in blob


def _corroborates_house(record: dict, point: str, house: int) -> bool:
    cond = record.get("conditions")
    # dict form: {"planet"/"point": X, "house": N}
    if isinstance(cond, dict):
        cp = canon_point(str(cond.get("planet") or cond.get("point") or ""))
        ch = cond.get("house")
        if cp == point and _coerce_house(ch) == house:
            return True
    blob = _conditions_blob(record)
    # prose form: "X in the Nth house" / "house: N"
    if f"house: {house}" in blob:
        return True
    ordinals = [w for w, n in HOUSE_WORDS.items() if n == house]
    return any(f"{o} house" in blob for o in ordinals) and point.lower() in blob


def _coerce_house(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v if 1 <= v <= 12 else None
    if isinstance(v, str):
        s = v.strip().lower()
        if s.isdigit():
            n = int(s)
            return n if 1 <= n <= 12 else None
        if s in HOUSE_WORDS:
            return HOUSE_WORDS[s]
    return None


def _house_system_default(record: dict) -> tuple[str, str]:
    """(house_system, confidence_note) per spec §3 tradition-based default."""
    if record.get("tradition") == "traditional":
        return "whole_sign", "medium"
    return "placidus", "medium"


def tier1_id_parse(record: dict) -> Optional[dict]:
    pid = (record.get("principle_id") or "").lower()

    m = _ID_SIGN_RE.match(pid)
    if m:
        point = canon_point(m.group(1))
        sign = canon_sign(m.group(2))
        if point and sign and _corroborates_sign(record, point, sign):
            return {
                "factor_type": "planet_in_sign",
                "point": point,
                "sign": sign,
                "extraction_confidence": "high",
                "extraction_source": "id_parse",
            }

    m = _ID_HOUSE_RE.match(pid)
    if m:
        raw_point = m.group(1).replace("-", " ")
        point = canon_point(raw_point)
        house = _coerce_house(m.group(2))
        if point and house and _corroborates_house(record, point, house):
            hs, _ = _house_system_default(record)
            ft = "node" if point in ("North Node", "South Node") else "planet_in_house"
            return {
                "factor_type": ft,
                "point": point,
                "house": house,
                "house_system": hs,
                "extraction_confidence": "high",
                "extraction_source": "id_parse",
            }

    m = _ID_OWN_DIGNITY_RE.match(pid)
    if m:
        point = canon_point(m.group(1))
        dig = _TERM_TO_DIGNITY.get(m.group(2), m.group(2))
        if point and dig in DIGNITIES and "own" in _conditions_blob(record):
            return {
                "factor_type": "dignity",
                "point": point,
                "dignity": dig,
                "extraction_confidence": "high",
                "extraction_source": "id_parse",
            }
    return None


# ---------------------------------------------------------------------------
# Tier 2 — conditions/tags cross-check (resolved fact, ID not required)
# ---------------------------------------------------------------------------

_PROSE_SIGN_RE = re.compile(
    r"\b(sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto|"
    r"north node|south node)\s+in\s+"
    r"(aries|taurus|gemini|cancer|leo|virgo|libra|scorpio|"
    r"sagittarius|capricorn|aquarius|pisces)\b"
)


def tier2_conditions(record: dict) -> Optional[dict]:
    cond = record.get("conditions")

    # dict form is the cleanest resolved fact: {planet/point, house}
    if isinstance(cond, dict):
        point = canon_point(str(cond.get("planet") or cond.get("point") or ""))
        house = _coerce_house(cond.get("house"))
        sign = canon_sign(str(cond.get("sign") or ""))
        if point and house and sign:
            hs, _ = _house_system_default(record)
            return {
                "factor_type": "planet_in_sign_and_house",
                "point": point, "sign": sign, "house": house,
                "house_system": hs,
                "extraction_confidence": "high",
                "extraction_source": "conditions_crosscheck",
            }
        if point and house:
            hs, _ = _house_system_default(record)
            ft = "node" if point in ("North Node", "South Node") else "planet_in_house"
            return {
                "factor_type": ft, "point": point, "house": house,
                "house_system": hs,
                "extraction_confidence": "high",
                "extraction_source": "conditions_crosscheck",
            }
        if point and sign:
            return {
                "factor_type": "planet_in_sign", "point": point, "sign": sign,
                "extraction_confidence": "high",
                "extraction_source": "conditions_crosscheck",
            }

    # list/str prose: look for "{Point} in {Sign}" resolved facts.
    blob = _conditions_blob(record)
    matches = _PROSE_SIGN_RE.findall(blob)
    uniq = {(canon_point(p), canon_sign(s)) for p, s in matches}
    uniq = {(p, s) for p, s in uniq if p and s}
    if len(uniq) == 1:
        point, sign = next(iter(uniq))
        ft = "node" if point in ("North Node", "South Node") else "planet_in_sign"
        return {
            "factor_type": ft, "point": point, "sign": sign,
            "extraction_confidence": "high",
            "extraction_source": "conditions_crosscheck",
        }
    if len(uniq) > 1:
        # multiple candidate subjects -> medium, pick none decisively; defer.
        return None
    return None


# ---------------------------------------------------------------------------
# Tier 2b — structural types (rev 2): house_domain & house_lord_relative.
# Deterministic ID/conditions patterns that the v1 model mis-typed (Patterns 1-2
# of the spec revision). Runs before the LLM so these never fall to unclassified.
# ---------------------------------------------------------------------------

_OUTER_PLANETS = {"Uranus", "Neptune", "Pluto"}
_ORD_WORDS = "|".join(w for w in HOUSE_WORDS if not w[0].isdigit())  # first..twelfth

# {planet}-house-...-domain  -> house_domain keyed on the point (Pattern 1)
_ID_DOMAIN_PLANET = re.compile(
    r"^(sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto)"
    r"-house-.*-domain$"
)
# {ordinal-word}-house-significations  -> house_domain keyed on the house
_ID_HOUSE_SIG = re.compile(rf"^({_ORD_WORDS})-house-significations$")
# lord-asc-in-{N}{ord}-...  -> house_lord_relative subject=1 placement=N (Pattern 2)
_ID_LORD_ASC_IN = re.compile(r"^lord-asc-in-(\d{1,2})(?:st|nd|rd|th)\b")
# lord-{M}{ord}-in-{N}{ord}-... (non-template, single placement)
_ID_LORD_M_IN_N = re.compile(
    r"^lord-(\d{1,2})(?:st|nd|rd|th)-in-(\d{1,2})(?:st|nd|rd|th)\b")
# lord-{M}{ord}-in-twelve-...  -> 12-way enumeration template, not single subject
_ID_LORD_IN_TWELVE = re.compile(r"^lord-(\d{1,2})(?:st|nd|rd|th)-in-twelve\b")


def tier2b_structural(record: dict) -> Optional[dict]:
    pid = (record.get("principle_id") or "").lower()
    blob = _conditions_blob(record)

    # --- house_lord_relative: "lord of the Xth in the Yth" -------------------
    m = _ID_LORD_ASC_IN.match(pid)
    if m and "lord" in blob and ("ascendant" in blob or "asc" in blob):
        placement = _coerce_house(m.group(1))
        if placement:
            hs, _ = _house_system_default(record)
            return {
                "factor_type": "house_lord_relative",
                "subject_house": 1, "subject_house_system": hs,
                "placement_house": placement, "placement_house_system": hs,
                "extraction_confidence": "high",
                "extraction_source": "id_parse",
            }
    m = _ID_LORD_M_IN_N.match(pid)
    if m:
        subj, placement = _coerce_house(m.group(1)), _coerce_house(m.group(2))
        if subj and placement and "lord" in blob:
            hs, _ = _house_system_default(record)
            return {
                "factor_type": "house_lord_relative",
                "subject_house": subj, "subject_house_system": hs,
                "placement_house": placement, "placement_house_system": hs,
                "extraction_confidence": "high",
                "extraction_source": "id_parse",
            }

    # --- house_domain (point or house, no occupancy) -------------------------
    m = _ID_DOMAIN_PLANET.match(pid)
    if m:
        point = canon_point(m.group(1))
        if point:
            about = {
                "factor_type": "house_domain", "point": point,
                "extraction_confidence": "high", "extraction_source": "id_parse",
            }
            if point in _OUTER_PLANETS:
                about["generational"] = True
            return about
    m = _ID_HOUSE_SIG.match(pid)
    if m:
        house = HOUSE_WORDS.get(m.group(1))
        if house:
            hs, _ = _house_system_default(record)
            return {
                "factor_type": "house_domain", "house": house, "house_system": hs,
                "extraction_confidence": "high", "extraction_source": "id_parse",
            }
    return None


# --- Tier-1 element template detector: "{planet}-element-*" / "element of {planet}"
# `element` is a RETIRED factor_type. This emits a TRANSIENT marker
# (factor_type "element", no value) used only to flag the record for the
# reclassify post-pass, which re-types it to house_domain (single planet) or
# general (relational). The marker NEVER survives to the output: ground_record
# allows it through unvalidated, reclassify converts it, and the final invariant
# check blocks the build if any `element` record remains. Detection lives here so
# routing logic stays single-sourced in reclassify._route_element_violation.
_ID_ELEMENT_PLANET = re.compile(
    r"\b(sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto|"
    r"north-node|south-node)\b")
_RULE_ELEMENT_OF = re.compile(
    r"element of (?:the )?(sun|moon|mercury|venus|mars|jupiter|saturn|uranus|"
    r"neptune|pluto|north node|south node)('s)?\b", re.I)


def tier1_element(record: dict) -> Optional[dict]:
    pid = (record.get("principle_id") or "").lower()
    if "-element-" not in pid and "element" not in pid:
        if not _RULE_ELEMENT_OF.search(record.get("rule") or ""):
            return None
    # need an unambiguous single subject point
    point = None
    m = _ID_ELEMENT_PLANET.search(pid)
    if m:
        point = canon_point(m.group(1).replace("-", " "))
    if point is None:
        m = _RULE_ELEMENT_OF.search(record.get("rule") or "")
        if m:
            point = canon_point(m.group(1))
    if point is None:
        return None
    about = {
        "factor_type": "element", "point": point,
        "extraction_confidence": "high", "extraction_source": "deterministic",
    }
    if point in _OUTER_PLANETS:
        about["generational"] = True
    return about


# --- Tier-1 dignity capture: essential dignity & reception-in-other's-domicile -
_CLASSICAL = "sun|moon|mercury|venus|mars|jupiter|saturn"
_DIGNITY_KEYWORDS = {
    "domicile": "domicile", "exaltation": "exaltation", "detriment": "detriment",
    "fall": "fall", "bound": "bound", "bounds": "bound", "term": "bound",
    "terms": "bound", "triplicity": "triplicity", "face": "face",
}
# {planet}-in-(own|{other})-{dignity}-natal  (the dense classical reception set)
_ID_DIGNITY = re.compile(
    rf"^({_CLASSICAL})-in-(own-|({_CLASSICAL})-)?"
    r"(domicile|detriment|exaltation|fall|bounds?|terms?|triplicity|face)s?\b")


def tier1_dignity(record: dict) -> Optional[dict]:
    pid = (record.get("principle_id") or "").lower()
    if "house" in pid or "lord" in pid:
        return None
    m = _ID_DIGNITY.match(pid)
    if not m:
        return None
    point = canon_point(m.group(1))
    dignity = _DIGNITY_KEYWORDS.get(m.group(4))
    ruler = canon_point(m.group(3)) if m.group(3) else None
    if not point or not dignity:
        return None
    about = {
        "factor_type": "dignity", "point": point, "dignity": dignity,
        "extraction_confidence": "high", "extraction_source": "deterministic",
    }
    # "{planet}-in-{other}-domicile" = subject sits in a sign the OTHER rules
    # (reception); reconciled via classifications.<ruler-field> == dignity_ruler.
    if ruler and ruler != point:
        about["dignity_ruler"] = ruler
    return about


# ---------------------------------------------------------------------------
# Tier 1 — deterministic capture (mandatory, exhaustive, LOCKED). Runs all the
# deterministic signals in precedence order and stamps source=deterministic. A
# record captured here is frozen: the LLM and `unclassified` may not touch it.
# ---------------------------------------------------------------------------

def tier1_deterministic(record: dict) -> Optional[dict]:
    pid = (record.get("principle_id") or "").lower()
    # An id that explicitly carries the element signal is an element principle
    # first, even when it also names a house (e.g. north-node-4th-element-sign):
    # its subject is the point's sign-element, not the placement.
    element_first = tier1_element(record) if "element" in pid else None
    about = (
        element_first
        or tier1_id_parse(record)     # planet-sign / planet-house / own-dignity
        or tier2_conditions(record)   # resolved fact in conditions
        or tier2b_structural(record)  # house_domain / house_lord_relative
        or tier1_dignity(record)      # essential dignity & reception
        or tier1_element(record)      # point-element templates
    )
    if about is None:
        return None
    about = dict(about)
    about["extraction_source"] = "deterministic"   # normalize legacy labels
    about.setdefault("extraction_confidence", "high")
    return about


# ---------------------------------------------------------------------------
# Tier 3 — schema-constrained extraction (pluggable)
# ---------------------------------------------------------------------------

class Extractor(Protocol):
    """Reads a record, returns an `about` subject dict (the value fields only;
    the orchestrator stamps source/confidence) or None for 'cannot determine'."""

    def extract(self, record: dict) -> Optional[dict]: ...


# Prompt shared by any real-LLM extractor: the closed vocabularies + framing.
EXTRACTION_SYSTEM_PROMPT = f"""\
You extract the SUBJECT of an astrology principle against a fixed schema. This is
EXTRACTION, NOT generation: read the principle's id, rule and judgment and report
ONLY what chart configuration it interprets, by calling the `emit_about` tool.
Never invent a subject the text does not support. If you cannot determine a
single concrete subject (the text is a general teaching, a multi-house template,
or genuinely ambiguous), call the tool with factor_type "unclassified".

The id may be a LABEL, not a subject: e.g. `asc-scorpio-mars-primary-ruler` is
about the ASCENDANT and its ruler — the token "scorpio" there is the rising sign
the rule discusses, so factor_type is `ascendant` with ascendant_sign Scorpio,
NOT planet_in_sign. Read the rule/judgment to decide; do not pattern-match the id.

Value fields are foreign keys and MUST use this exact vocabulary/casing:
  signs:    {", ".join(SIGNS)}
  points:   {", ".join(POINTS)}
  aspects:  conjunction, sextile, square, trine, opposition
  dignities: {", ".join(DIGNITIES)}
  house_system: placidus | whole_sign   (mandatory whenever house is present;
    if the source is classical and unmarked use whole_sign, if modern use placidus)
  factor_type: planet_in_sign | planet_in_house | planet_in_sign_and_house |
    aspect | dignity | node | ascendant | house_ruler | general | unclassified
  (there is NO `element` type: a point's sign-element is not chart-reconcilable —
   single-planet element significations are house_domain, relational ones general)

Emit only the fields the chosen factor_type uses.
"""


def _extraction_tool_schema() -> dict:
    """The emit_about tool's input_schema: ABOUT_SCHEMA minus the orchestrator-
    owned stamping fields (the model reports the subject; we stamp source/conf).
    Forcing tool use with this schema is what constrains output to the FK enums."""
    from grounding_schema import ABOUT_SCHEMA

    schema = json.loads(json.dumps(ABOUT_SCHEMA))  # deep copy
    # strip orchestrator-owned and human-review-only fields from the LLM surface.
    for owned in ("extraction_confidence", "extraction_source",
                  "reviewer", "reviewed_at"):
        schema["properties"].pop(owned, None)
    schema["required"] = ["factor_type"]
    schema.pop("$schema", None)
    schema.pop("$id", None)
    # Drop the conditional house_system rule: the Anthropic tool schema only
    # enforces a subset of JSON Schema, so we keep input_schema to the enums it
    # does enforce and rely on local validate_about() for the conditional.
    schema.pop("allOf", None)
    return schema


EXTRACTION_TOOL = {
    "name": "emit_about",
    "description": "Report the subject of the principle as a structured `about` "
                   "object. Call exactly once.",
    "input_schema": _extraction_tool_schema(),
}


class HeuristicExtractor:
    """Deterministic, fully-offline Tier-3 fallback. Scans the id + rule + judgment
    for an unambiguous subject the strict tiers missed (label-style ids, prose).
    Conservative by design — returns None ('cannot determine') rather than guess,
    because the grounding gate, not this extractor, is the safeguard."""

    _ASC_SIGN_RE = re.compile(
        r"\b(ascendant|rising|asc)\b[^.]*?\b(aries|taurus|gemini|cancer|leo|"
        r"virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces)\b"
    )
    _ASPECT_RE = re.compile(
        r"\b(sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto|"
        r"north node|south node)\b[^.]{0,40}?"
        r"\b(conjunction|conjunct|sextile|square|trine|opposition|opposed?)\b"
        r"[^.]{0,40}?"
        r"\b(sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto|"
        r"north node|south node)\b"
    )
    _ASPECT_WORD = {
        "conjunct": "conjunction", "conjunction": "conjunction",
        "sextile": "sextile", "square": "square", "trine": "trine",
        "opposition": "opposition", "opposed": "opposition", "oppose": "opposition",
    }

    def extract(self, record: dict) -> Optional[dict]:
        text = " ".join(
            str(record.get(k) or "")
            for k in ("principle_id", "rule", "judgment")
        ).lower().replace("-", " ")

        # ascendant + sign
        m = self._ASC_SIGN_RE.search(text)
        if m:
            sign = canon_sign(m.group(2))
            if sign:
                return {"factor_type": "ascendant", "ascendant_sign": sign}

        # explicit point-in-sign in prose
        m = _PROSE_SIGN_RE.search(text)
        if m:
            point, sign = canon_point(m.group(1)), canon_sign(m.group(2))
            if point and sign:
                ft = "node" if point in ("North Node", "South Node") else "planet_in_sign"
                return {"factor_type": ft, "point": point, "sign": sign}

        # binary aspect between two points
        m = self._ASPECT_RE.search(text)
        if m:
            src = canon_point(m.group(1))
            typ = self._ASPECT_WORD.get(m.group(2))
            tgt = canon_point(m.group(3))
            if src and tgt and typ and src != tgt:
                return {
                    "factor_type": "aspect",
                    "aspect": {"source": src, "target": tgt, "type": typ},
                }
        return None


class AnthropicExtractor:
    """Real schema-constrained LLM extraction (spec §2.1).

    Uses FORCED tool use: the model must call `emit_about`, whose `input_schema`
    is the FK-enum-constrained about schema, so off-vocabulary values are blocked
    at the API boundary. The returned tool input is re-validated locally against
    ``grounding_schema`` and, on any residual violation, the error is fed back and
    the call retried (reject-and-retry, capped at ``max_retries``). The
    orchestrator (``tier3_extract``) stamps source=llm and caps confidence at
    ``medium`` — this class never assigns confidence.

    Network/transient errors are retried with exponential backoff. Persistent
    failure returns None, so the record falls through to ``unclassified`` rather
    than corrupting the corpus.
    """

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        max_retries: int = 2,
        max_tokens: int = 512,
    ) -> None:
        import anthropic  # import-time check that the SDK is installed
        self._anthropic = anthropic
        self._client = anthropic.Anthropic()
        self._model = model
        self._max_retries = max_retries
        self._max_tokens = max_tokens

    def _call(self, messages: list[dict]):
        import time
        last_exc: Exception | None = None
        for attempt in range(4):
            try:
                return self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=EXTRACTION_SYSTEM_PROMPT,
                    tools=[EXTRACTION_TOOL],
                    tool_choice={"type": "tool", "name": "emit_about"},
                    messages=messages,
                )
            except (self._anthropic.APIStatusError,
                    self._anthropic.APIConnectionError) as exc:
                last_exc = exc
                # 4xx other than rate-limit/overloaded won't fix on retry.
                status = getattr(exc, "status_code", None)
                if status and status not in (408, 409, 429, 500, 502, 503, 529):
                    raise
                time.sleep(min(2 ** attempt, 8))
        if last_exc:
            raise last_exc
        raise RuntimeError("unreachable")

    @staticmethod
    def _tool_input(msg) -> Optional[dict]:
        for block in msg.content:
            if getattr(block, "type", "") == "tool_use" and block.name == "emit_about":
                return dict(block.input)
        return None

    def extract(self, record: dict) -> Optional[dict]:
        user = json.dumps({
            "principle_id": record.get("principle_id"),
            "rule": record.get("rule"),
            "judgment": record.get("judgment"),
        }, ensure_ascii=False)
        messages: list[dict] = [{"role": "user", "content": user}]

        try:
            for attempt in range(self._max_retries + 1):
                msg = self._call(messages)
                subject = self._tool_input(msg)
                if subject is None:
                    return None
                if subject.get("factor_type") == "unclassified":
                    return None
                subject.pop("extraction_confidence", None)
                subject.pop("extraction_source", None)

                # local re-validation (the real safeguard on top of the API schema)
                probe = dict(subject, extraction_source="llm",
                             extraction_confidence="medium")
                ok, errs = validate_about(probe)
                if ok:
                    return subject
                if attempt >= self._max_retries:
                    return None
                # reject-and-retry: feed the validation errors back.
                messages += [
                    {"role": "assistant", "content": msg.content},
                    {"role": "user", "content": (
                        "The emit_about call was rejected by schema validation:\n"
                        + "\n".join(f"- {e}" for e in errs)
                        + "\nCall emit_about again with corrected, in-vocabulary "
                          "values, or factor_type \"unclassified\" if you cannot.")},
                ]
            return None
        except Exception:
            return None


class _NullExtractor:
    """Tier-3 disabled: everything unresolved by Tiers 1-2 -> unclassified."""

    def extract(self, record: dict) -> Optional[dict]:
        return None


def load_api_key(api_key_file: str | None = None) -> bool:
    """Ensure ANTHROPIC_API_KEY is in os.environ. Order: existing env var, then
    an explicit --api-key-file, then ``~/.anthropic_key``. Returns True if a key
    is now available. The key value is never printed. Keep the key file OUTSIDE
    any synced folder (Drive/Dropbox); ``~/.anthropic_key`` is the safe default."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    candidates = []
    if api_key_file:
        candidates.append(api_key_file)
    candidates.append(os.path.join(os.path.expanduser("~"), ".anthropic_key"))
    for path in candidates:
        try:
            with open(path, encoding="utf-8") as fh:
                key = fh.read().strip()
            if key:
                os.environ["ANTHROPIC_API_KEY"] = key
                print(f"[backfill] loaded API key from {path}")
                return True
        except OSError:
            continue
    return False


def make_default_extractor(verbose: bool = True) -> Extractor:
    """Anthropic-backed extraction when a key + SDK are available, else the
    offline heuristic. Pass ``verbose`` to log which backend was selected."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            ext = AnthropicExtractor()
            if verbose:
                print("[backfill] Tier-3: AnthropicExtractor (live LLM pass)")
            return ext
        except Exception as exc:  # SDK missing / client init failure
            if verbose:
                print(f"[backfill] Tier-3: Anthropic unavailable ({exc}); "
                      "falling back to heuristic")
    elif verbose:
        print("[backfill] Tier-3: ANTHROPIC_API_KEY not set; using offline "
              "HeuristicExtractor. Set the key to run the live LLM pass.")
    return HeuristicExtractor()


def _id_partial_subject(record: dict) -> Optional[dict]:
    """A weak, UNCORROBORATED subject read from the principle_id alone — the
    'partial signal' of spec §2.1. Records reaching Tier 3 failed Tiers 1-2 (so
    no corroborated subject exists), but the id may still parse to a candidate
    that the LLM output can be checked against. Used only for the self-consistency
    comparison, never to assign a subject."""
    pid = (record.get("principle_id") or "").lower()
    m = _ID_SIGN_RE.match(pid)
    if m:
        point, sign = canon_point(m.group(1)), canon_sign(m.group(2))
        if point and sign:
            return {"point": point, "sign": sign}
    m = _ID_HOUSE_RE.match(pid)
    if m:
        point = canon_point(m.group(1).replace("-", " "))
        house = _coerce_house(m.group(2))
        if point and house:
            return {"point": point, "house": house}
    return None


def tier3_extract(record: dict, extractor: Extractor) -> Optional[dict]:
    """Run the extractor, schema-validate, cap confidence at medium. Returns a
    stamped, validated about dict or None (-> unclassified)."""
    subject = extractor.extract(record)
    if not subject:
        return None
    # records carrying a house need a system; backfill default if LLM omitted it.
    hs_default, _ = _house_system_default(record)
    if "house" in subject and "house_system" not in subject:
        subject["house_system"] = hs_default
    for hf, hsf in (("subject_house", "subject_house_system"),
                    ("placement_house", "placement_house_system")):
        if hf in subject and hsf not in subject:
            subject[hsf] = hs_default
    about = dict(subject)
    about["extraction_source"] = "llm"
    if about.get("factor_type") == "unclassified":
        # rev 3 §2.1: an LLM unclassified verdict is EARNED — it must carry a
        # reason. Default to no_subject_in_text if the model omitted one.
        about["extraction_confidence"] = "low"
        about.setdefault("unclassified_reason", "no_subject_in_text")
    else:
        about["extraction_confidence"] = "medium"   # spec §2: capped at medium
        # self-consistency vs the uncorroborated id signal (§2.1): downgrade on
        # disagreement (kept as confidence signal; routed to review in §2.5).
        partial = _id_partial_subject(record)
        if partial:
            for k in ("point", "sign", "house"):
                if k in partial and k in about and partial[k] != about[k]:
                    about["extraction_confidence"] = "low"
                    break

    ok, _errs = validate_about(about)
    if not ok:
        return None  # off-vocabulary / invalid -> reject (never silently kept)
    return about


# ---------------------------------------------------------------------------
# Orchestration — Tier 1 (deterministic, LOCKED) -> Tier 2 (LLM residual) ->
# earned unclassified. No `manual` discard channel (rev 3 §2).
# ---------------------------------------------------------------------------

def _unclassified(reason: str) -> dict:
    return {
        "factor_type": "unclassified",
        "unclassified_reason": reason,
        "extraction_confidence": "low",
        "extraction_source": "llm",
    }


_GENDER_REQ = re.compile(r"native_gender")


def _residual_verdict(record: dict) -> dict:
    """For a record the LLM could not classify (or when the LLM is absent): an
    EARNED unclassified with a valid reason, or `general` for non-configurational
    framing material. Never `manual` (that is human-review-only)."""
    # non-configurational basics framing -> general (deterministic decision)
    if record.get("domain") == "basics":
        return {
            "factor_type": "general",
            "extraction_confidence": "low",
            "extraction_source": "deterministic",
        }
    # dependency the chart cannot carry (gender) -> earned unclassified
    blob = _conditions_blob(record)
    if _GENDER_RE.search(blob):
        return _unclassified("dependency_unsatisfiable")
    return _unclassified("no_subject_in_text")


# ---------------------------------------------------------------------------
# Tier 0 — the ACG corpus (docs/acg/ACG_06_CORPUS_DELTA_SPEC.md §8). Only records whose
# principle_id starts with "acg-" take this branch; every other record is
# untouched (no main-corpus id starts with "acg-"). The ACG factor types are
# validated by the ACG-local vocab below and are deliberately NOT added to
# grounding_vocab.FACTOR_TYPES (the main schema stays byte-identical). 100%
# deterministic: an ACG record never reaches the LLM tier.
# ---------------------------------------------------------------------------

ACG_PLANETS: tuple[str, ...] = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter",
                                "Saturn", "Uranus", "Neptune", "Pluto")
ACG_ANGLES: tuple[str, ...] = ("ASC", "DSC", "MC", "IC")
ACG_FACTOR_TYPES: dict[str, tuple[str, ...]] = {
    "planet_on_angle": ("planet", "angle"),
    "acg_angle_frame": ("angle",),
    "acg_planet_general": ("planet",),
    "acg_method": ("slug",),
    "acg_paran": ("planets",),
    "acg_mundane": (),
}
ACG_SCOPE_FACTOR: dict[str, tuple[str, ...]] = {
    # acg_scope -> the factor types it may carry. The fixed method id
    # acg-method-crossings has scope "paran" but no planets: it is an acg_method.
    "line": ("planet_on_angle",), "angle_frame": ("acg_angle_frame",),
    "planet_general": ("acg_planet_general",), "method": ("acg_method",),
    "ccg": ("acg_method",), "zenith": ("acg_method",),
    "paran": ("acg_paran", "acg_method"), "mundane": ("acg_mundane",),
}
ACG_REQUIRE_KINDS: dict[str, tuple[str, ...]] = {
    # kind -> required fields (value-bearing; evaluated by ground_acg, spec 03 gate 3)
    "natal_point_sign": ("point", "sign"),
    "natal_point_aspect": ("point", "other"),          # + optional "aspect"
    "natal_point_retrograde": ("point",),
    "natal_point_dignity": ("point", "dignity"),
    "relocated_point_house": ("point", "house"),
    "relocated_point_angular": ("point",),
    "unsupported": ("text",),                          # -> requires_unsupported_kind
}
_ACG_DIGNITIES = ("domicile", "detriment", "exaltation", "fall")
_ACG_ASPECTS = ("conjunction", "sextile", "square", "trine", "opposition")
_ACG_P = "sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto"
_ACG_A = "asc|dsc|mc|ic"
_ACG_ID_RES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(rf"^acg-angle-({_ACG_A})$"), "acg_angle_frame"),
    (re.compile(rf"^acg-general-({_ACG_P})-\d{{2}}$"), "acg_planet_general"),
    (re.compile(rf"^acg-paran-({_ACG_P})-({_ACG_P})-\d{{2}}$"), "acg_paran"),
    (re.compile(r"^acg-mundane-\d{2}$"), "acg_mundane"),
    (re.compile(r"^acg-method-([a-z0-9]+(?:-[a-z0-9]+)*)$"), "acg_method"),
    (re.compile(r"^acg-((?:zenith|ccg)-\d{2})$"), "acg_method"),
    (re.compile(rf"^acg-({_ACG_P})-({_ACG_A})-\d{{2}}$"), "planet_on_angle"),
)


def tier0_acg(record: dict) -> dict:
    """``about`` for an ``acg-*`` record, derived from the id alone. Raises
    ValueError on an id that matches no ACG pattern (a build bug, never guessed)."""
    pid = str(record.get("principle_id") or "")
    for rx, ft in _ACG_ID_RES:
        m = rx.match(pid)
        if not m:
            continue
        about: dict[str, Any] = {"factor_type": ft}
        if ft == "planet_on_angle":
            about.update(planet=m.group(1).capitalize(), angle=m.group(2).upper())
        elif ft == "acg_angle_frame":
            about["angle"] = m.group(1).upper()
        elif ft == "acg_planet_general":
            about["planet"] = m.group(1).capitalize()
        elif ft == "acg_method":
            about["slug"] = m.group(1)
        elif ft == "acg_paran":
            about["planets"] = sorted([m.group(1).capitalize(), m.group(2).capitalize()])
        about["extraction_confidence"] = "high"
        about["extraction_source"] = "deterministic"
        return about
    raise ValueError(f"ACG id matches no ACG pattern: {pid!r}")


def _acg_unsupported(cond: Any) -> dict:
    if isinstance(cond, dict) and set(cond) == {"text"}:
        text = str(cond["text"])
    else:
        text = json.dumps(cond, ensure_ascii=False, sort_keys=True)
    return {"kind": "unsupported", "text": text}


def acg_requires(record: dict) -> list[dict]:
    """Value-bearing ``requires`` (exploration report §13 C6) from the record's
    structured ``conditions`` list. No condition -> []. A stated condition that
    cannot be mapped becomes {"kind": "unsupported", "text": ...}, so grounding
    drops the record as requires_unsupported_kind rather than guessing."""
    conds = record.get("conditions") or []
    if isinstance(conds, dict):
        conds = [conds]
    if not isinstance(conds, list):
        conds = [{"text": str(conds)}]
    out: list[dict] = []
    for c in conds:
        req: Optional[dict] = None
        if isinstance(c, dict) and len(c) == 1:
            (kind, v), = c.items()
            v = v if isinstance(v, dict) else {}
            pt, other = v.get("point"), v.get("other")
            pt_ok = pt in ACG_PLANETS
            if kind == "natal_sign" and pt_ok and v.get("sign") in SIGNS:
                req = {"kind": "natal_point_sign", "point": pt, "sign": v["sign"]}
            elif kind == "natal_aspect" and pt_ok and other in ACG_PLANETS and other != pt:
                req = {"kind": "natal_point_aspect", "point": pt, "other": other}
                if v.get("aspect") in _ACG_ASPECTS:
                    req["aspect"] = v["aspect"]
                elif v.get("aspect"):
                    req = None                       # an off-vocab aspect is not guessed
            elif kind == "natal_retrograde" and pt_ok:
                req = {"kind": "natal_point_retrograde", "point": pt}
            elif kind == "natal_dignity" and pt_ok and v.get("dignity") in _ACG_DIGNITIES:
                req = {"kind": "natal_point_dignity", "point": pt, "dignity": v["dignity"]}
            elif kind == "relocated_house" and pt_ok and isinstance(v.get("house"), int) \
                    and 1 <= v["house"] <= 12:
                req = {"kind": "relocated_point_house", "point": pt, "house": v["house"]}
            elif kind == "relocated_angular" and pt_ok:
                req = {"kind": "relocated_point_angular", "point": pt}
        out.append(req if req is not None else _acg_unsupported(c))
    return out


def validate_acg_about(about: Any, scope: Any = None) -> tuple[bool, list[str]]:
    errs: list[str] = []
    if not isinstance(about, dict):
        return False, ["about must be an object"]
    ft = about.get("factor_type")
    if ft not in ACG_FACTOR_TYPES:
        return False, [f"factor_type off-vocabulary: {ft!r}"]
    allowed = set(ACG_FACTOR_TYPES[ft]) | {"factor_type", "extraction_confidence",
                                           "extraction_source"}
    for k in about:
        if k not in allowed:
            errs.append(f"unknown field: {k}")
    for k in ACG_FACTOR_TYPES[ft]:
        if about.get(k) in (None, "", []):
            errs.append(f"missing {k}")
    if "planet" in about and about["planet"] not in ACG_PLANETS:
        errs.append(f"planet off-vocabulary: {about['planet']!r}")
    if "angle" in about and about["angle"] not in ACG_ANGLES:
        errs.append(f"angle off-vocabulary: {about['angle']!r}")
    if "planets" in about:
        ps = about["planets"]
        if not (isinstance(ps, list) and len(ps) == 2 and all(p in ACG_PLANETS for p in ps)
                and ps == sorted(ps) and ps[0] != ps[1]):
            errs.append(f"planets must be 2 distinct sorted planets: {ps!r}")
    if about.get("extraction_source") != "deterministic" or \
            about.get("extraction_confidence") != "high":
        errs.append("ACG about must be deterministic/high")
    if scope is not None and ft not in ACG_SCOPE_FACTOR.get(scope, ()):
        errs.append(f"acg_scope {scope!r} inconsistent with factor_type {ft!r}")
    return (not errs, errs)


def validate_acg_requires(reqs: Any) -> tuple[bool, list[str]]:
    errs: list[str] = []
    if not isinstance(reqs, list):
        return False, ["requires must be a list"]
    for i, r in enumerate(reqs):
        if not isinstance(r, dict) or r.get("kind") not in ACG_REQUIRE_KINDS:
            errs.append(f"requires[{i}] kind off-vocabulary: {r!r}")
            continue
        need = ACG_REQUIRE_KINDS[r["kind"]]
        extra = {"aspect"} if r["kind"] == "natal_point_aspect" else set()
        for k in r:
            if k != "kind" and k not in need and k not in extra:
                errs.append(f"requires[{i}] unknown field: {k}")
        for k in need:
            if r.get(k) in (None, ""):
                errs.append(f"requires[{i}] missing {k}")
        for k in ("point", "other"):
            if k in r and r[k] not in ACG_PLANETS:
                errs.append(f"requires[{i}].{k} off-vocabulary: {r[k]!r}")
    return (not errs, errs)


def _ground_acg_record(record: dict) -> dict:
    about = tier0_acg(record)
    ok, errs = validate_acg_about(about, record.get("acg_scope"))
    if not ok:
        raise ValueError(f"{record.get('principle_id')}: invalid ACG about: {errs}")
    requires = acg_requires(record)
    rok, rerrs = validate_acg_requires(requires)
    if not rok:
        raise ValueError(f"{record.get('principle_id')}: invalid ACG requires: {rerrs}")
    out = dict(record)
    out["about"] = about
    out["requires"] = requires
    return out


def ground_record(record: dict, extractor: Extractor) -> dict:
    """Return a copy of the record with `about` + `requires` added. Original
    fields (incl. `conditions`) are untouched. Tier-1 capture is LOCKED — if it
    fires, neither the LLM nor an unclassified verdict can override it."""
    if str(record.get("principle_id") or "").startswith("acg-"):
        return _ground_acg_record(record)            # Tier 0 — ACG corpus only
    locked = tier1_deterministic(record)            # Tier 1 — mandatory, frozen
    if locked is not None:
        about = locked
    else:
        about = tier3_extract(record, extractor)    # Tier 2 — LLM residual only
        if about is None:
            about = _residual_verdict(record)       # earned unclassified/general

    ok, errs = validate_about(about)
    if not ok:
        # A value-less `element` template is a KNOWN transient: backfill types it
        # `element` (so the reclassify rule "factor_type==element and element
        # absent" can re-type it to house_domain/general with audit). It is left
        # as-is here; the reclassify post-pass fixes it, and the final invariant
        # check blocks the build if any survives. All other invalid abouts are a
        # bug to surface, so they are downgraded to unclassified.
        is_element_template = (
            about.get("factor_type") == "element"
            and about.get("element") is None
            and about.get("point")
        )
        if not is_element_template:
            about = _unclassified("no_subject_in_text")

    requires = extract_requires(record)
    rok, _ = validate_requires(requires)
    if not rok:
        requires = [{"kind": "other"}]

    out = dict(record)
    out["about"] = about
    out["requires"] = requires
    return out


def backfill(
    records: list[dict],
    extractor: Extractor | None = None,
    progress_every: int = 0,
) -> list[dict]:
    """Backfill all records. ``progress_every`` > 0 prints a heartbeat every N
    records (useful for the live LLM pass, which is rate-limited and slow)."""
    extractor = extractor or make_default_extractor()
    out: list[dict] = []
    total = len(records)
    for i, r in enumerate(records, 1):
        out.append(ground_record(r, extractor))
        if progress_every and (i % progress_every == 0 or i == total):
            llm = sum(1 for g in out if g["about"]["extraction_source"] == "llm")
            print(f"[backfill] {i}/{total} processed ({llm} via LLM)", flush=True)
    return out


def validate_invariants(grounded: list[dict]) -> dict:
    """Spec §2.3 / §2.4: deterministic post-backfill validation. Every record's
    factor_type required fields must be non-null. A reconcilable type with a
    missing required field is a BUILD-BLOCKING violation. Returns a report; the
    build is only acceptable when ``reconcilable_with_null_field == 0``."""
    violations: list[dict] = []
    schema_errors: list[dict] = []
    for r in grounded:
        about = r.get("about") or {}
        viol = invariant_violation(about)
        if viol:
            violations.append({"principle_id": r.get("principle_id"),
                               "domain": r.get("domain"),
                               "factor_type": about.get("factor_type"),
                               "reason": viol, "about": about})
        ok, errs = validate_about(about)
        if not ok:
            schema_errors.append({"principle_id": r.get("principle_id"),
                                  "errors": errs, "about": about})
    natal_viol = [v for v in violations if v["domain"] == "natal"]

    # rev 3 §2: no auto-`manual` discard channel; every manual record needs a
    # reviewer + reviewed_at. And every unclassified needs an enum reason.
    manual_dump, unclassified_no_reason = [], []
    for r in grounded:
        about = r.get("about") or {}
        if about.get("extraction_source") == "manual" and not (
                about.get("reviewer") and about.get("reviewed_at")):
            manual_dump.append(r.get("principle_id"))
        if about.get("factor_type") == "unclassified" and not about.get(
                "unclassified_reason"):
            unclassified_no_reason.append(r.get("principle_id"))

    # rev 3 §2.2: per-category natal build floors.
    natal = [r for r in grounded if r.get("domain") == "natal"]
    natal_factor = Counter(r["about"]["factor_type"] for r in natal)
    floors_status = {
        cat: {"floor": floor, "have": natal_factor.get(cat, 0),
              "met": natal_factor.get(cat, 0) >= floor}
        for cat, floor in BUILD_FLOORS.items()
    }
    floors_met = all(s["met"] for s in floors_status.values())
    unclassified_natal = natal_factor.get("unclassified", 0)

    # RECLASSIFY_SPEC §7: the hard count ceiling is replaced by a STRUCTURAL check
    # — every remaining `unclassified` has a valid reason and matches no route
    # signal that would have moved it. The count is reported, not asserted.
    from reclassify import structural_residual_check
    structural = structural_residual_check(grounded)

    build_blocking = (
        len(violations) + len(schema_errors) + len(manual_dump)
        + len(unclassified_no_reason)
        + (0 if floors_met else 1) + (0 if structural["passes"] else 1)
    )
    return {
        "total_records": len(grounded),
        "reconcilable_with_null_field": len(violations),
        "reconcilable_with_null_field_natal": len(natal_viol),
        "schema_invalid": len(schema_errors),
        "manual_without_reviewer": manual_dump,
        "unclassified_without_reason": unclassified_no_reason,
        "natal_floors": floors_status,
        "floors_met": floors_met,
        "natal_unclassified": unclassified_natal,
        "structural_residual_check": structural,
        "build_blocking": build_blocking,
        "passes": build_blocking == 0,
        "violations": violations,
        "schema_errors": schema_errors,
    }


# rev 3 §2.2 — floors equal the Tier-1 DETERMINISTIC counts (so they are always
# achievable without the LLM, and the LLM can only add). Values below are this
# implementation's measured deterministic natal counts; the spec's published
# numbers are noted where they differ.
#   element: RETIRED factor_type (element-of-sign is not chart-reconcilable), so
#   there is no element floor. Such records are house_domain (single planet) or
#   general (relational); the layer is retained under those types.
BUILD_FLOORS: dict[str, int] = {
    "planet_in_sign": 84, "dignity": 55, "house_domain": 22,
    "house_lord_relative": 12,
}
UNCLASSIFIED_CEILING = 50    # natal


def diff_factor_types(prev: list[dict], curr: list[dict]) -> dict:
    """rev 3 §2.4 — LLM non-determinism guard. Diff factor_type per principle_id
    against the last accepted artifact. Net movement INTO unclassified, or any
    floor breach, is a build-blocking event listed here for justification."""
    prev_ft = {r["principle_id"]: (r.get("about") or {}).get("factor_type")
               for r in prev}
    changes, into_unclassified, out_of_unclassified = [], 0, 0
    for r in curr:
        pid = r["principle_id"]
        old = prev_ft.get(pid)
        new = (r.get("about") or {}).get("factor_type")
        if old is not None and old != new:
            changes.append({"principle_id": pid, "from": old, "to": new})
            if new == "unclassified":
                into_unclassified += 1
            elif old == "unclassified":
                out_of_unclassified += 1
    net_into_unclassified = into_unclassified - out_of_unclassified
    return {
        "changed": len(changes),
        "into_unclassified": into_unclassified,
        "out_of_unclassified": out_of_unclassified,
        "net_into_unclassified": net_into_unclassified,
        "build_blocking_event": net_into_unclassified > 0,
        "changes": changes,
    }


def build_report(grounded: list[dict]) -> dict:
    by_source = Counter(r["about"]["extraction_source"] for r in grounded)
    by_conf = Counter(r["about"]["extraction_confidence"] for r in grounded)
    by_factor = Counter(r["about"]["factor_type"] for r in grounded)
    natal = [r for r in grounded if r.get("domain") == "natal"]
    natal_factor = Counter(r["about"]["factor_type"] for r in natal)
    unclassified_natal = sum(
        1 for r in natal if r["about"]["factor_type"] == "unclassified"
    )
    return {
        "total_records": len(grounded),
        "by_extraction_source": dict(by_source),
        "by_extraction_confidence": dict(by_conf),
        "by_factor_type": dict(by_factor),
        "natal_total": len(natal),
        "natal_by_factor_type": dict(natal_factor),
        "natal_unclassified": unclassified_natal,
        # sampling-review targets (spec §2.2): all low + all disagreements.
        "review_pool_low": by_conf.get("low", 0),
    }


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Backfill about/requires (spec §2).")
    ap.add_argument("--in", dest="inp",
                    default=os.path.join(here, "all_principles.clean.json"))
    ap.add_argument("--out", dest="out",
                    default=os.path.join(here, "all_principles.grounded.json"))
    ap.add_argument("--report", dest="report",
                    default=os.path.join(here, "backfill_report.json"))
    ap.add_argument("--validation-report", dest="validation",
                    default=os.path.join(here, "validation_report.json"))
    ap.add_argument("--no-llm", action="store_true",
                    help="skip Tier-3 extraction entirely (rest -> unclassified)")
    ap.add_argument("--heuristic", action="store_true",
                    help="force the offline heuristic Tier-3 (ignore any API key)")
    ap.add_argument("--model", default="claude-opus-4-8",
                    help="Anthropic model id for the live extraction pass")
    ap.add_argument("--api-key-file", default=None,
                    help="read ANTHROPIC_API_KEY from this file if the env var is "
                         "unset (keep it outside synced folders)")
    ap.add_argument("--limit", type=int, default=0,
                    help="process only the first N records (smoke-test the LLM pass)")
    ap.add_argument("--progress-every", type=int, default=50,
                    help="print a heartbeat every N records")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as fh:
        records = json.load(fh)
    if args.limit:
        records = records[:args.limit]

    if not (args.no_llm or args.heuristic):
        load_api_key(args.api_key_file)

    if args.no_llm:
        extractor: Extractor = _NullExtractor()
        print("[backfill] Tier-3 disabled (--no-llm)")
    elif args.heuristic:
        extractor = HeuristicExtractor()
        print("[backfill] Tier-3: HeuristicExtractor (forced offline)")
    elif os.environ.get("ANTHROPIC_API_KEY"):
        try:
            extractor = AnthropicExtractor(model=args.model)
            print(f"[backfill] Tier-3: AnthropicExtractor (live, model={args.model})")
        except Exception as exc:
            extractor = HeuristicExtractor()
            print(f"[backfill] Anthropic unavailable ({exc}); using heuristic")
    else:
        extractor = HeuristicExtractor()
        print("[backfill] ANTHROPIC_API_KEY not set; using offline HeuristicExtractor.\n"
              "           Set it (and optionally --model) to run the live LLM pass.")

    # §2.4 re-run stability: diff against the last accepted artifact (if any),
    # BEFORE overwriting it.
    prev_accepted = None
    if os.path.exists(args.out):
        try:
            with open(args.out, encoding="utf-8") as fh:
                prev_accepted = json.load(fh)
        except (OSError, json.JSONDecodeError):
            prev_accepted = None

    grounded = backfill(records, extractor, progress_every=args.progress_every)

    # RECLASSIFY_SPEC: deterministic post-pass over the `unclassified` pile, run
    # AFTER backfill and BEFORE the build gates. No LLM, count-free, idempotent.
    from collections import Counter as _Counter
    from reclassify import load_rules, reclassify
    grounded, reclass_log = reclassify(grounded, load_rules())
    by_route = dict(_Counter(x["route"] for x in reclass_log))
    with open(os.path.join(here, "reclassify_report.json"), "w", encoding="utf-8") as fh:
        json.dump({"routed": len(reclass_log), "by_route": by_route,
                   "routing": reclass_log}, fh, ensure_ascii=False, indent=2)
    print(f"[reclassify] routed {len(reclass_log)} records {by_route}")

    report = build_report(grounded)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    # §2.2/§2.3 full build gate — floors, ceiling, invariants, no manual dump.
    validation = validate_invariants(grounded)
    if prev_accepted is not None:
        validation["rerun_diff"] = diff_factor_types(prev_accepted, grounded)
    with open(args.validation, "w", encoding="utf-8") as fh:
        json.dump(validation, fh, ensure_ascii=False, indent=2)

    print(f"backfilled {len(grounded)} records")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    floors = validation["natal_floors"]
    print("\n[build gate 2.2/2.3]")
    for cat, s in floors.items():
        print(f"  floor {cat:<20} have {s['have']:>3} >= {s['floor']:<3} "
              f"{'OK' if s['met'] else 'MISS'}")
    sc = validation["structural_residual_check"]
    print(f"  residual unclassified natal: {validation['natal_unclassified']} "
          f"(structural check {'PASS' if sc['passes'] else 'FAIL'}: "
          f"no-reason={len(sc['unclassified_without_reason'])}, "
          f"still-routable={len(sc['unclassified_still_route_matchable'])})")
    print(f"  reconcilable-with-null: {validation['reconcilable_with_null_field']}, "
          f"schema-invalid: {validation['schema_invalid']}, "
          f"manual-without-reviewer: {len(validation['manual_without_reviewer'])}, "
          f"unclassified-without-reason: {len(validation['unclassified_without_reason'])}")
    if "rerun_diff" in validation:
        rd = validation["rerun_diff"]
        print(f"  rerun diff: {rd['changed']} changed, "
              f"net into unclassified {rd['net_into_unclassified']} "
              f"{'(BLOCKING)' if rd['build_blocking_event'] else ''}")

    accepted = validation["passes"] and not (
        validation.get("rerun_diff", {}).get("build_blocking_event"))
    if accepted:
        import hashlib
        payload = json.dumps(grounded, ensure_ascii=False, indent=1)
        # newline="\n": disable Windows \n->\r\n translation so the on-disk bytes
        # equal the hashed bytes (and the artifact is byte-stable cross-platform).
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(payload)
        # Freshness fingerprint sidecar: lets any downstream consumer confirm it
        # is reading THIS post-reclass artifact and not a stale Drive sync fork
        # (this tree lives in Google Drive, which forks conflict copies on
        # mid-sync overwrites). Mismatch => the consumer has the wrong/old file.
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with open(args.out + ".sha256", "w", encoding="utf-8") as fh:
            fh.write(f"{digest}  {os.path.basename(args.out)}\n"
                     f"out_of_scope={sum(1 for r in grounded if r.get('out_of_scope'))} "
                     f"invariant_violations={validation['reconcilable_with_null_field']} "
                     f"records={len(grounded)}\n")
        print(f"\n-> BUILD ACCEPTED, written to {args.out}")
        print(f"   sha256 {digest}")
        print(f"   (consumers: verify against {os.path.basename(args.out)}.sha256 "
              f"to rule out a stale Drive fork)")
    else:
        # Do not overwrite the last accepted artifact with a failing build.
        fail_path = args.out.replace(".json", ".rejected.json")
        with open(fail_path, "w", encoding="utf-8") as fh:
            json.dump(grounded, fh, ensure_ascii=False, indent=1)
        print(f"\n-> BUILD REJECTED (see validation_report.json). "
              f"Output written to {fail_path}, accepted artifact untouched.")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
