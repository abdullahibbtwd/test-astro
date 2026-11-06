"""Python-side benchmark harness — skips until benchmarks/*.json exist."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent / "fixtures"
_CASES = _ROOT / "benchmarks"
_SCHEMA = _ROOT / "benchmark.schema.json"


def _case_files() -> list[Path]:
    if not _CASES.is_dir():
        return []
    return sorted(p for p in _CASES.glob("*.json"))


def test_benchmark_schema_documents_expected_fields():
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert schema["title"] == "AstrologyBenchmarkCase"
    props = schema["properties"]
    for key in (
        "birth",
        "target_year",
        "expected",
        "sample_reading",
        "mapping",
    ):
        assert key in props
    expected = props["expected"]["properties"]
    assert "return_utc" in expected
    assert "ascendant" in expected
    assert "key_placements" in expected


def test_benchmark_cases_skip_when_empty():
    files = _case_files()
    if not files:
        pytest.skip(
            "No files in backend/tests/fixtures/benchmarks/*.json yet — "
            "awaiting astrologer benchmark cases"
        )
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("id"), path
        assert data.get("kind") in {"solar_return", "family"}
        assert "birth" in data and "expected" in data
        if data["kind"] == "solar_return":
            assert "target_year" in data
            assert data["expected"].get("return_utc")
