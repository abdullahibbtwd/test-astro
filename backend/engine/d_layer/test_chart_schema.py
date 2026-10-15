#!/usr/bin/env python3
"""
test_chart_schema.py — proves chart_types.py, chart_schema.json, and the actual
output of compute_chart() all agree.

Generates four fixture charts:
  * exact          (Istanbul, known clock time)
  * approximate    (Istanbul, a named time bucket)
  * unknown        (Istanbul, no birth time)
  * circumpolar    (Svalbard, exact time — Placidus undefined, must degrade)

and validates each against chart_schema.json (JSON Schema Draft 2020-12) with the
`jsonschema` package. It also asserts the structural absent-vs-null contract that
the schema cannot fully express on its own (e.g. that an unknown chart's points
carry no `sector` key at all).

Run directly (`python test_chart_schema.py`) or under pytest.
"""

from __future__ import annotations

import json
import os

from jsonschema import Draft202012Validator

from compute_chart import BirthData, compute_chart

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCHEMA_PATH = os.path.join(_HERE, "chart_schema.json")

# Istanbul
_IST = dict(year=1990, month=6, day=15, latitude=41.0082, longitude=28.9784)
# Svalbard — above the polar circle, so Placidus is undefined there.
_SVB = dict(year=1990, month=6, day=15, latitude=78.2232, longitude=15.6267)


def _load_validator() -> Draft202012Validator:
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _fixtures() -> dict[str, dict]:
    return {
        "exact": compute_chart(BirthData(
            time_precision="exact", hour=14, minute=30, **_IST)),
        "approximate": compute_chart(BirthData(
            time_precision="approximate", approx_bucket="morning", **_IST)),
        "unknown": compute_chart(BirthData(
            time_precision="unknown", **_IST)),
        "circumpolar": compute_chart(BirthData(
            time_precision="exact", hour=14, minute=30, **_SVB)),
    }


def test_all_fixtures_validate() -> None:
    validator = _load_validator()
    for kind, chart in _fixtures().items():
        errors = sorted(validator.iter_errors(chart), key=lambda e: e.path)
        assert not errors, (
            f"[{kind}] failed schema validation:\n"
            + "\n".join(f"  - {e.json_path}: {e.message}" for e in errors)
        )


def test_absent_vs_null_contract() -> None:
    """Guards the distinctions the schema enforces, checked explicitly."""
    charts = _fixtures()

    # Unknown tier: structural keys ABSENT (not present-but-null), and points
    # carry no `sector` key.
    unk = charts["unknown"]
    for absent in ("axes", "sectors", "is_diurnal", "derived_points",
                   "planetary_day", "planetary_hour"):
        assert absent not in unk, f"unknown chart should omit {absent!r}"
    assert all("sector" not in p for p in unk["points"])
    # Moon emits a daily range in the unknown tier.
    moon = next(p for p in unk["points"] if p["name"] == "Moon")
    assert "range" in moon

    # Circumpolar exact: Placidus is NULL (concept exists, undefined here);
    # whole-sign stays populated.
    cp = charts["circumpolar"]
    assert cp["sectors"]["placidus_cusps"] is None
    assert isinstance(cp["sectors"]["whole_sign_cusps"], list)
    assert all(p["sector"]["placidus"] is None for p in cp["points"])
    assert all(isinstance(p["sector"]["whole_sign"], int) for p in cp["points"])

    # classifications: null for non-classical points, present for classical 7.
    ex = charts["exact"]
    pluto = next(p for p in ex["points"] if p["name"] == "Pluto")
    assert pluto["classifications"] is None
    sun = next(p for p in ex["points"] if p["name"] == "Sun")
    assert sun["classifications"] is not None

    # is_diurnal is a boolean in timed tiers.
    assert isinstance(ex["is_diurnal"], bool)

    # Approximate tier carries unstable_fields.
    assert "unstable_fields" in charts["approximate"]


if __name__ == "__main__":
    validator = _load_validator()
    ok = True
    for kind, chart in _fixtures().items():
        errors = sorted(validator.iter_errors(chart), key=lambda e: e.path)
        if errors:
            ok = False
            print(f"FAIL [{kind}]:")
            for e in errors:
                print(f"  - {e.json_path}: {e.message}")
        else:
            print(f"OK   [{kind}] validates against chart_schema.json")
    test_absent_vs_null_contract()
    print("OK   absent-vs-null contract holds")
    if not ok:
        raise SystemExit(1)
    print("\nAll fixtures validate and the absent-vs-null contract holds.")
