"""Shared fixtures for the PA tests: the three fixture charts, a turn context, a temp dossier cache."""

from __future__ import annotations

import os
import sys
from datetime import date

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, "fixtures")):
    if p not in sys.path:
        sys.path.insert(0, p)

import _paths  # noqa: E402,F401
import subjects as S  # noqa: E402
from pa_context import TurnContext, chart_of  # noqa: E402


@pytest.fixture(scope="session")
def charts():
    return {"self": chart_of(S.SUBJECT["birth"]), "partner": chart_of(S.PARTNER["birth"]),
            "colleague": chart_of(S.COLLEAGUE["birth"])}


@pytest.fixture(scope="session")
def pa_cache(tmp_path_factory):
    return str(tmp_path_factory.mktemp("pa_cache"))


def make_ctx(lang="tr", cache_root=None, today=S.FIXTURE_TODAY):
    return TurnContext(S.SUBJECT, profiles=S.PROFILES, compatibilities=S.COMPATIBILITIES, lang=lang,
                       today=date.fromisoformat(today), cache_root=cache_root)


@pytest.fixture(scope="session")
def ctx(pa_cache):
    return make_ctx("tr", pa_cache)


@pytest.fixture(scope="session")
def ctx_en(pa_cache):
    return make_ctx("en", pa_cache)
