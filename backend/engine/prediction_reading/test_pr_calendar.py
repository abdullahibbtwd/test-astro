"""Calendar context in the predictive reading (pr_calendar.py). Offline: fake generator, no model.
Run: python -m pytest prediction_reading/test_pr_calendar.py -q"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "d_layer"))

import pr_calendar as PC  # noqa: E402
from compute_chart import BirthData, compute_chart  # noqa: E402
from pr_profiles import get_profile  # noqa: E402
from read_forecast import _build_ctx, run_reading  # noqa: E402
from test_forecast_reading import FakeGenerator, _forecast, _month_forecast  # noqa: E402

START = date(2026, 10, 12)


@pytest.fixture(scope="module")
def cal():
    natal = compute_chart(BirthData(year=1979, month=3, day=30, hour=6, minute=30,
                                    latitude=42.6977, longitude=23.3219))
    return PC.build(natal, "Europe/Sofia", START)


def _fc(horizon: str, days: int) -> dict:
    end = START + timedelta(days=days)
    return _forecast(horizon, [], target=START.isoformat(),
                     start=f"{START.isoformat()}T00:00:00+03:00", end=f"{end.isoformat()}T00:00:00+02:00")


def test_segments_tile_the_window():
    for horizon, days, segs in (("month", 31, ["early", "mid", "late"]), ("year", 365, ["q1", "q2", "q3", "q4"])):
        fc = _fc(horizon, days)
        a, b = PC.window_dates(fc)
        ranges = [PC.segment_dates(fc, s) for s in segs]
        assert ranges[0][0] == a and ranges[-1][1] == b
        for (_, hi), (lo, _) in zip(ranges, ranges[1:]):
            assert lo == hi + timedelta(days=1)


def test_contexts_per_horizon(cal):
    day = PC.for_forecast(cal, _fc("day", 1))
    assert day["window"]["range"][0] == day["window"]["range"][1] == START.isoformat()
    assert not day["segments"]
    month = PC.for_forecast(cal, _fc("month", 31))
    assert set(month["segments"]) == {"early", "mid", "late"}
    year = PC.for_forecast(cal, _fc("year", 365))
    txt = PC.render(year["window"], "modern", "year")
    # a year reading keeps the slow / major picture: no fast moderate transits, no repeats
    assert "[moderate] Mars" not in txt and "[moderate] Venus" not in txt
    lines = [ln for ln in txt.splitlines() if ln.startswith("- [")]
    assert len(lines) <= PC.MAX_TRANSIT_LINES and len(lines) == len(set(lines))
    assert "[major] Saturn conjunct your Sun" in txt
    # periods grouped by life area + kind
    per = [ln for ln in txt.splitlines() if ln.startswith("- life area")]
    assert len(per) == len({ln.split(":")[0] + ln.split(":")[1].split("(")[0] for ln in per})


def test_plain_mode_names_no_planets(cal):
    ctx = PC.for_forecast(cal, _fc("month", 31))
    txt = PC.render(ctx["window"], "plain", "month")
    for p in ("Saturn", "Mars", "Jupiter", "Uranus", "Neptune", "Pluto", "Venus"):
        assert p not in txt


class RecordingGen(FakeGenerator):
    def __init__(self):
        self.users: list[str] = []

    def day(self, user):
        self.users.append(user)
        return super().day(user)

    def beats(self, jobs):
        self.users += [u for _, u in jobs]
        return super().beats(jobs)

    def synthesize(self, user):
        self.users.append(user)
        return super().synthesize(user)


def test_prompts_carry_the_calendar(cal):
    fc = _month_forecast()
    fc["window"] = _fc("month", 31)["window"]
    ctx = PC.for_forecast(cal, fc)
    gen = RecordingGen()
    reading, errors, rep = run_reading(fc, generator=gen, calendar=ctx)
    assert gen.users and all("CALENDAR CONTEXT" in u for u in gen.users)
    assert reading["meta"]["calendar_context"] is True
    gen2 = RecordingGen()
    run_reading(fc, generator=gen2)                      # default: unchanged behaviour
    assert not any("CALENDAR CONTEXT" in u for u in gen2.users)


def test_validator_allows_calendar_planets(cal):
    fc = _month_forecast()
    fc["window"] = _fc("month", 31)["window"]          # a window inside the calendar data
    ctx = PC.for_forecast(cal, fc)
    with_cal = _build_ctx(fc, get_profile("general"), "month", surface_planets=True, sparse=False,
                          astro_detail="modern", calendar=ctx)
    without = _build_ctx(fc, get_profile("general"), "month", surface_planets=True, sparse=False,
                         astro_detail="modern")
    extra = PC.planets(ctx["window"])
    assert extra and extra <= with_cal.allowed_planets
    assert with_cal.allowed_planets >= without.allowed_planets
