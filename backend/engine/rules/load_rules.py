"""
Load data-driven interpretation rule packs.

Empty / missing sections fall back to safe math-only defaults. Never invent
astrological content — callers must treat empty lists as "no rules yet".
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

_HERE = Path(__file__).resolve().parent

# Safe defaults when a file or section is empty / missing.
SOLAR_RETURN_DEFAULTS: dict[str, Any] = {
    "reading_sequence": {"steps": []},
    "placement_hierarchy": {"order": []},
    "return_to_natal_aspects": {"aspects": []},
    "inclusions": {"items": []},
    "exclusions": {"items": []},
    "house_focus": {"houses": []},
    "reading_framework": {"sections": []},
    "excluded_themes": {"themes": []},
}

FAMILY_DEFAULTS: dict[str, Any] = {
    "reading_sequence": {"steps": []},
    "placement_hierarchy": {"order": []},
    "return_to_natal_aspects": {"aspects": []},
    "inclusions": {"items": []},
    "exclusions": {"items": []},
    "relationship_type_aspect_weights": {
        # null selection = keep full modern set (today's Match / romantic).
        "romantic": {"selection": None, "weights": {}},
        # Empty selection = no rules yet → return [] (current engine behavior).
        "parent_child": {"selection": [], "weights": {}},
        "sibling": {"selection": [], "weights": {}},
    },
    "house_focus": {"houses": []},
    "reading_framework": {"sections": []},
    "excluded_themes": {"themes": []},
}

_CACHE: dict[str, dict[str, Any]] = {}


def rules_dir() -> Path:
    override = os.environ.get("ASTRO_RULES_DIR")
    return Path(override) if override else _HERE


def _deep_merge(defaults: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(defaults)
    for key, value in loaded.items():
        if key.startswith("_"):
            out[key] = value
            continue
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
        ):
            merged = deepcopy(out[key])
            for sk, sv in value.items():
                if sk.startswith("_"):
                    merged[sk] = sv
                elif (
                    sk in merged
                    and isinstance(merged[sk], dict)
                    and isinstance(sv, dict)
                ):
                    nested = deepcopy(merged[sk])
                    nested.update(sv)
                    merged[sk] = nested
                else:
                    merged[sk] = sv
            out[key] = merged
        else:
            out[key] = value
    return out


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Rules file must be a JSON object: {path}")
    return data


def load_solar_return_rules(*, force_reload: bool = False) -> dict[str, Any]:
    key = "solar_return"
    if not force_reload and key in _CACHE:
        return deepcopy(_CACHE[key])
    path = rules_dir() / "solar_return_rules.json"
    merged = _deep_merge(SOLAR_RETURN_DEFAULTS, _read_json(path))
    _CACHE[key] = merged
    return deepcopy(merged)


def load_family_rules(*, force_reload: bool = False) -> dict[str, Any]:
    key = "family"
    if not force_reload and key in _CACHE:
        return deepcopy(_CACHE[key])
    path = rules_dir() / "family_rules.json"
    merged = _deep_merge(FAMILY_DEFAULTS, _read_json(path))
    _CACHE[key] = merged
    return deepcopy(merged)


def clear_rules_cache() -> None:
    _CACHE.clear()


def family_aspect_selection(
    relationship_type: str,
    rules: Optional[dict[str, Any]] = None,
) -> Optional[frozenset[tuple[str, str, str]]]:
    """
    Return membership filter for synastry aspects.

    None  → keep all modern hits (romantic default)
    empty frozenset → no rules yet → caller returns []
    non-empty frozenset → keep only listed (a_point, b_point, type) triples
    """
    pack = rules if rules is not None else load_family_rules()
    block = (pack.get("relationship_type_aspect_weights") or {}).get(
        relationship_type
    )
    if not isinstance(block, dict):
        if relationship_type == "romantic":
            return None
        return frozenset()
    selection = block.get("selection", [] if relationship_type != "romantic" else None)
    if selection is None:
        return None
    if not selection:
        return frozenset()
    triples: set[tuple[str, str, str]] = set()
    for row in selection:
        if isinstance(row, (list, tuple)) and len(row) == 3:
            triples.add((str(row[0]), str(row[1]), str(row[2])))
        elif isinstance(row, dict):
            triples.add(
                (
                    str(row["a_point"]),
                    str(row["b_point"]),
                    str(row["type"]),
                )
            )
    return frozenset(triples)


def has_interpretation_framework(rules: dict[str, Any]) -> bool:
    """True only when the astrologer has supplied reading framework sections."""
    sections = (rules.get("reading_framework") or {}).get("sections") or []
    return bool(sections)
