"""Unit tests for data-driven rule loaders (no astrological invention)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from load_rules import (  # noqa: E402
    clear_rules_cache,
    family_aspect_selection,
    has_interpretation_framework,
    load_family_rules,
    load_solar_return_rules,
)


@pytest.fixture(autouse=True)
def _clear():
    clear_rules_cache()
    yield
    clear_rules_cache()


def test_solar_return_rules_load_with_empty_sections():
    rules = load_solar_return_rules(force_reload=True)
    assert rules["reading_sequence"]["steps"] == []
    assert rules["placement_hierarchy"]["order"] == []
    assert rules["return_to_natal_aspects"]["aspects"] == []
    assert rules["inclusions"]["items"] == []
    assert rules["exclusions"]["items"] == []
    assert rules["house_focus"]["houses"] == []
    assert rules["reading_framework"]["sections"] == []
    assert rules["excluded_themes"]["themes"] == []
    assert not has_interpretation_framework(rules)
    assert rules["_meta"]["status"] == "AWAITING_ASTROLOGER"


def test_family_rules_default_selections():
    rules = load_family_rules(force_reload=True)
    assert family_aspect_selection("romantic", rules) is None
    assert family_aspect_selection("parent_child", rules) == frozenset()
    assert family_aspect_selection("sibling", rules) == frozenset()
    assert rules["relationship_type_aspect_weights"]["romantic"]["weights"] == {}


def test_missing_file_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRO_RULES_DIR", str(tmp_path))
    clear_rules_cache()
    solar = load_solar_return_rules(force_reload=True)
    family = load_family_rules(force_reload=True)
    assert solar["reading_sequence"]["steps"] == []
    assert family_aspect_selection("romantic", family) is None
    assert family_aspect_selection("sibling", family) == frozenset()


def test_partial_override_merges(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRO_RULES_DIR", str(tmp_path))
    (tmp_path / "family_rules.json").write_text(
        json.dumps(
            {
                "relationship_type_aspect_weights": {
                    "sibling": {
                        "selection": [
                            {"a_point": "Sun", "b_point": "Moon", "type": "trine"}
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    clear_rules_cache()
    rules = load_family_rules(force_reload=True)
    assert family_aspect_selection("sibling", rules) == frozenset(
        {("Sun", "Moon", "trine")}
    )
    # Unspecified romantic still defaults to full set.
    assert family_aspect_selection("romantic", rules) is None
