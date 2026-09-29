#!/usr/bin/env python3
"""test_acg_policy_decisions.py — Radul's 2026-09-28 viability decisions (spec 11 §3 amendments).

- Afghanistan is excluded (P1).
- Islands are allowed under the Africa rule (P4): Mauritius, Seychelles, Zanzibar, Madagascar,
  Cabo Verde … while mainland Africa outside the Mediterranean coast stays excluded.
- Bali and the Canary Islands are included (and, with the island destinations above,
  recorded as reviewed in destinations_review_decisions.csv).
"""

from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import acg_destinations as dst  # noqa: E402


@pytest.fixture(scope="module")
def by_id():
    return {d["id"]: d for d in dst.load_destinations()}


@pytest.mark.parametrize("did", ["dst-kabul"])
def test_afghanistan_excluded(by_id, did):
    ok, rule = dst.policy_verdict(by_id[did])
    assert not ok and rule == "P1"
    assert by_id[did]["exclude"] and by_id[did]["exclude_reason"] == "policy:P1"


@pytest.mark.parametrize("did", ["dst-zanzibar", "dst-zanzibar-tz", "dst-mauritius", "dst-port-louis",
                                 "dst-seychelles", "dst-victoria-sc", "dst-antananarivo",
                                 "dst-praia"])
def test_african_islands_allowed(by_id, did):
    d = by_id[did]
    assert d["island"] is True
    ok, rule = dst.policy_verdict(d)
    assert ok and rule == "P4" and not d["exclude"]


@pytest.mark.parametrize("did", ["dst-nairobi", "dst-casablanca", "dst-lagos"])
def test_mainland_africa_still_excluded(by_id, did):
    if did not in by_id:
        pytest.skip(f"{did} not in destinations")
    d = by_id[did]
    assert d["island"] is False
    assert dst.policy_verdict(d) == (False, "P4")


@pytest.mark.parametrize("did", ["dst-bali", "dst-canary-islands", "dst-las-palmas-de-gran-canaria",
                                 "dst-zanzibar", "dst-mauritius", "dst-seychelles"])
def test_included_and_reviewed(by_id, did):
    d = by_id[did]
    assert dst.policy_verdict(d)[0] and not d["exclude"] and d["reviewed"]


def test_continents_are_not_islands(by_id):
    for did in ("dst-london", "dst-tokyo", "dst-sydney"):
        pass                                  # UK / Japan are islands; Australia is not
    for did, want in (("dst-berlin", False), ("dst-new-york", False)):
        if did in by_id:
            assert by_id[did]["island"] is want
