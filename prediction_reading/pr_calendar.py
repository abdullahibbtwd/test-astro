"""pr_calendar.py - the personal calendar as context for the predictive reading.

The day / month / year readings and the app's calendar (run_calendar.py, CAL_01-02) look
at the same sky. Without this module the reading ranks events by its own simpler rules
and can disagree with the calendar the user sees. This module slices the calendar to a
reading's window (and to each beat's part of it) and renders a short CALENDAR CONTEXT
block for the prompts:

  * major / moderate transit episodes active in the range, with where they stand in it
    (building / at its peak / easing / between peaks). A transit is one long influence,
    not only the exact hits that fall inside a one-month window.
  * the supportive / demanding periods per life area (derived from the same grounded
    transit records via goal tags)
  * DAY: that day's life-area picture

Only corpus-backed items go in. Retrogrades and the void Moon have no modern grounding,
so the calendar shows them as labels only and they are left out here too.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in ("Calendar", "Astrocartography"):
    if os.path.join(_ROOT, _p) not in sys.path:
        sys.path.insert(0, os.path.join(_ROOT, _p))

import build_transit_affinity as BA  # noqa: E402
import cal_scoring as S  # noqa: E402
import personal_events as P  # noqa: E402
from acg_constants import GOALS  # noqa: E402

from pr_events import _PLANET_THEME  # noqa: E402

_POINT = {"sun": "Sun", "moon": "Moon", "mercury": "Mercury", "venus": "Venus", "mars": "Mars",
          "jupiter": "Jupiter", "saturn": "Saturn", "uranus": "Uranus", "neptune": "Neptune",
          "pluto": "Pluto", "asc": "Ascendant", "mc": "MC"}
_ASPECT = {"conjunction": "conjunct", "sextile": "sextile", "square": "square",
           "trine": "trine", "opposition": "opposite"}
_TONE = {"conjunction": "a new-chapter influence", "sextile": "a supportive influence",
         "trine": "a supportive influence", "square": "a pressuring influence",
         "opposition": "a pressuring influence"}
_BAND = {"supportive": "supportive", "strongly_supportive": "strongly supportive",
         "challenging": "demanding", "strongly_challenging": "strongly demanding", "mixed": "mixed"}


def build(natal: dict, tz: str, start: date, months: int = 12) -> dict:
    """The calendar data for [start, start + months): events, day scores, periods."""
    events = P.build_personal_events(natal, tz, start, months)
    full = S.day_scores(events, natal, BA.load())
    return {"events": events, "scores": S.public_scores(full), "periods": S.periods(full, events)}


def _local(iso: str) -> date:
    return datetime.fromisoformat(iso).date()


def window_dates(forecast: dict) -> tuple[date, date]:
    """Inclusive local dates of the forecast window (its end is exclusive)."""
    w = forecast["window"]
    return _local(w["start"]), _local(w["end"]) - timedelta(days=1)


def segment_dates(forecast: dict, seg: str) -> tuple[date, date]:
    """Local date range of a beat segment (thirds for month, quarters for year, as compute_forecast)."""
    a, b = window_dates(forecast)
    n = (b - a).days + 1
    parts = ["early", "mid", "late"] if seg in ("early", "mid", "late") else ["q1", "q2", "q3", "q4"]
    i, k = parts.index(seg), len(parts)
    lo = a + timedelta(days=int(n * i / k))
    hi = a + timedelta(days=int(n * (i + 1) / k) - 1)
    return lo, hi


def slice_for(cal: dict, first: date, last: date) -> dict:
    a, b = first.isoformat(), last.isoformat()
    tr = [e for e in cal["events"]["events"] if e["kind"] == "transit" and e["importance"] != "minor"
          and e["start_local"] <= b and e["end_local"] >= a]
    tr.sort(key=lambda e: ({"major": 0, "moderate": 1}[e["importance"]], -e["I"], e["id"]))
    per = [p for p in cal["periods"]["periods"] if p["start_local"] <= b and p["end_local"] >= a]
    day = None
    if a == b:
        d = next((x for x in cal["scores"]["days"] if x["local_date"] == a), None)
        if d:
            day = {g: v["band"] for g, v in d["goals"].items() if v["band"] != "quiet"}
    return {"range": [a, b], "transits": tr, "periods": per, "day": day}


def _stage(e: dict, a: str, b: str) -> str:
    pivots = e["exacts_local"] or []
    if any(a <= p <= b for p in pivots):
        return "at its peak"
    if not pivots:
        return "present (never quite exact)"
    if b < pivots[0]:
        return "building"
    if a > pivots[-1]:
        return "easing"
    return "between peaks (it will return)"


def _span_words(e: dict, a: str, b: str) -> str:
    if e["start_local"] < a and e["end_local"] > b:
        return "runs through this whole stretch"
    if e["start_local"] >= a and e["end_local"] <= b:
        return "begins and ends inside this stretch"
    return "starts in this stretch" if e["start_local"] >= a else "fades out in this stretch"


_FAST = {"sun", "mercury", "venus", "mars"}
MAX_TRANSIT_LINES = 10


def _keep(sl: dict, horizon: str) -> tuple[list[dict], list[dict]]:
    """Size the context to the horizon: a year reading keeps the slow, major picture."""
    tr, per = sl["transits"], sl["periods"]
    if horizon == "year":
        tr = [e for e in tr if e["importance"] == "major" or e["t_body"] not in _FAST]
        per = [p for p in per if p["importance"] == "major" or p["strength"] == "strong"]
    return tr, per


def render(sl: dict, astro_detail: str = "modern", horizon: str = "month") -> str:
    """The CALENDAR CONTEXT block (English, like the rest of the prompt scaffolding)."""
    a, b = sl["range"]
    lines = ["CALENDAR CONTEXT (the app's calendar shows the user these same items for this stretch; "
             "keep the reading consistent with them and give [major] items priority. "
             "Never state dates.):"]
    tr, per = _keep(sl, horizon)
    seen: dict[str, int] = {}
    rows: list[list] = []
    for e in tr:
        if astro_detail == "plain":
            what = f"{_TONE[e['aspect']]} on {_PLANET_THEME.get(_POINT[e['n_point']], 'your life')}"
        else:
            what = f"{_POINT[e['t_body']]} {_ASPECT[e['aspect']]} your {_POINT[e['n_point']]}"
        if what in seen:                                   # the same transit recurring in the range
            rows[seen[what]][2] += 1
            continue
        seen[what] = len(rows)
        rows.append([e, what, 1])
    for e, what, n in rows[:MAX_TRANSIT_LINES]:
        again = f" (recurs {n} times in this stretch)" if n > 1 else ""
        lines.append(f"- [{e['importance']}] {what}: {_stage(e, a, b)}; {_span_words(e, a, b)}{again}")
    groups: dict[tuple, list] = {}
    for p in per:
        groups.setdefault((p["goal"], p["kind"]), []).append(p)
    for (goal, kind), ps in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        word = "supportive" if kind == "favorable" else "demanding"
        strong = sum(1 for p in ps if p["strength"] == "strong")
        detail = (f"{len(ps)} stretches" if len(ps) > 1 else "one stretch") + \
            (f", {strong} strong" if strong else "")
        lines.append(f"- life area {GOALS[goal][1]}: {word} ({detail})")
    if sl.get("day"):
        lines.append("- life areas today: " + ", ".join(f"{GOALS[g][1]} {_BAND[v]}" for g, v in sl["day"].items()))
    if len(lines) == 1:
        lines.append("- nothing major on the calendar for this stretch")
    return "\n".join(lines)


def planets(sl: dict) -> set[str]:
    """Planet names the context introduces (for the reading validator's allow-list)."""
    out = set()
    for e in sl["transits"]:            # superset of what render() keeps: allow-list stays safe
        out.add(_POINT[e["t_body"]])
        if e["n_point"] not in ("asc", "mc"):
            out.add(_POINT[e["n_point"]])
    return out


def for_forecast(cal: dict, forecast: dict) -> dict:
    """Everything the reading needs for one forecast: the whole-window slice and one per beat."""
    horizon = forecast["meta"]["horizon"]
    a, b = window_dates(forecast)
    out = {"horizon": horizon, "window": slice_for(cal, a, b), "segments": {}}
    segs = {"month": ["early", "mid", "late"], "year": ["q1", "q2", "q3", "q4"]}.get(horizon, [])
    for s in segs:
        out["segments"][s] = slice_for(cal, *segment_dates(forecast, s))
    return out


def block(ctx: Optional[dict], segment: Optional[str], astro_detail: str) -> str:
    if not ctx:
        return ""
    sl = ctx["segments"].get(segment) if segment else ctx["window"]
    return "\n\n" + render(sl or ctx["window"], astro_detail, ctx["horizon"])
