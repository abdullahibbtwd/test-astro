#!/usr/bin/env python3
"""run_calendar.py - the personal calendar + Best Days orchestrator (CAL_05).

    python run_calendar.py --date 1979-03-30 --time 06:30 --location Sofia \
        --current-location Istanbul --mode all

Modes (CAL_05 §2):
    collective   1                   the global sky-event cache
    events       1-3                 + natal + personal_events.json (12 months)
    calendar     1-4, 6, 8 (+7)      + day_scores/periods, notifications, month views,
                                       texts for the first month
    month YYYY-MM                     calendar for one month (+ its texts)
    day YYYY-MM-DD                    one day view + day note + its major events' texts
    best-days    1-3, 5, 7           best_days.json (90 days) + top-day texts
    all          everything

Everything is deterministic except stage 7 (texts), which calls the model only for
uncached, grounded units. ``--dry-run`` makes zero model calls and writes the prompts.
Houses are natal Placidus. ``--current-location`` only sets the tz (CAL_00 D1, D7).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ENGINE_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(ENGINE_ROOT))  # repo root (Chart_wheel, run caches)
# Layer packages live under backend/engine; keep ENGINE as the import root.
_ENGINE = ENGINE_ROOT
for _p in ("Calendar", "calendar_reading", "d_layer", "Astrocartography"):
    _full = os.path.join(ENGINE_ROOT, _p)
    if _full not in sys.path:
        sys.path.insert(0, _full)
if ENGINE_ROOT not in sys.path:
    sys.path.insert(0, ENGINE_ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import best_days as BD  # noqa: E402
import build_transit_affinity as BA  # noqa: E402
import cal_astro as A  # noqa: E402
import cal_constants as K  # noqa: E402
import cal_corpus  # noqa: E402
import cal_scoring as S  # noqa: E402
import collective_events as C  # noqa: E402
import cr_generate as G  # noqa: E402
import cr_prompts as PR  # noqa: E402
import cr_render as R  # noqa: E402
import cr_sections as CS  # noqa: E402
import personal_events as P  # noqa: E402
from acg_constants import GOAL_ORDER, GOALS  # noqa: E402
from compute_chart import BirthData, compute_chart, resolve_timezone  # noqa: E402

CAL_RUN = os.path.join(REPO_ROOT, "cal_run")
CACHE_ROOT = os.path.join(CAL_RUN, "_cache")
MODES = ("collective", "events", "calendar", "month", "day", "best-days", "all")
STAGES_BY_MODE = {
    "collective": {1},
    "events": {1, 2, 3, 7},
    "calendar": {1, 2, 3, 4, 6, 7, 8},
    "month": {1, 2, 3, 4, 6, 7, 8},
    "day": {1, 2, 3, 4, 7, 8},
    "best-days": {1, 2, 3, 5, 7},
    "all": {1, 2, 3, 4, 5, 6, 7, 8},
}


# --- small helpers ---------------------------------------------------------------------------
def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _file_sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _write(path: str, obj, dumps=None) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(obj) if dumps else json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    os.replace(tmp, path)
    return path


def _read(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _tz_slug(tz: str) -> str:
    return tz.replace("/", "_")


class Manifest:
    def __init__(self, run_id: str, params: dict):
        self.data = {"run_id": run_id, "status": "running",
                     "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "params": params, "stages": [], "outputs": {}}

    def stage(self, name: str, status: str, **kw) -> None:
        self.data["stages"].append({"stage": name, "status": status, **kw})
        print(f"[{name}] {status}" + (f" {kw}" if kw else ""), flush=True)


# --- the run ---------------------------------------------------------------------------------
def run_calendar(birth: dict, *, current_location: str | None, mode: str, mode_arg: str | None = None,
                 start: date | None = None, activity: str | None = None, dry_run: bool = False,
                 model: str | None = None, translation_model: str | None = None,
                 geocoder=None, now_utc: datetime | None = None) -> dict:
    import run as RUN                          # suffixed(), mint_run_id() (repo run-id scheme)
    import run_predictive as RP                # geocode() with its cache
    geocoder = geocoder or RP.geocode
    now_utc = now_utc or datetime.now(timezone.utc)
    stages = STAGES_BY_MODE[mode]

    bgeo = geocoder(birth["location"])
    warnings = []
    if current_location:
        cgeo = geocoder(current_location)
    else:
        cgeo = bgeo
        warnings.append("no --current-location: using the birth location's tz (CAL_05 §1)")
    tz = resolve_timezone(cgeo["latitude"], cgeo["longitude"])
    start = start or datetime.now(ZoneInfo(tz)).date()
    if mode == "month" and mode_arg:
        y, m = (int(x) for x in mode_arg.split("-"))
        start = min(start, date(y, m, 1)) if date(y, m, 1) >= start else date(y, m, 1)
    if mode == "day" and mode_arg:
        d = date.fromisoformat(mode_arg)
        start = d if d < start else start

    bdate = f"{birth['year']:04d}-{birth['month']:02d}-{birth['day']:02d}"
    run_id = RUN.mint_run_id(now_utc, bdate)
    run_dir = os.path.join(CAL_RUN, run_id)
    sfx = bdate
    man = Manifest(run_id, {"birth": {**birth, "latitude": bgeo["latitude"], "longitude": bgeo["longitude"]},
                            "current_location": current_location, "tz": tz, "mode": mode,
                            "mode_arg": mode_arg, "from": start.isoformat(), "activity": activity,
                            "dry_run": dry_run})
    man.data["warnings"] = warnings

    def out(name: str, obj, dumps=None) -> str:
        p = _write(os.path.join(run_dir, RUN.suffixed(name, sfx)), obj, dumps)
        man.data["outputs"][name] = os.path.basename(p)
        return p

    # 1 collective ---------------------------------------------------------------------------
    first, last, jd0, jd1 = P.horizon(start, tz)
    years = sorted({A.jd_to_utc(jd0 - 2).year, A.jd_to_utc(jd1 + 2).year} |
                   set(range(A.jd_to_utc(jd0).year, A.jd_to_utc(jd1).year + 1)))
    hit = all(os.path.exists(C.path_for(y)) for y in years)
    coll_all = [e for y in years for e in C.ensure_year(y)["events"]]
    coll_by_id = {e["id"]: e for e in coll_all}
    man.stage("1 collective", "cache_hit" if hit else "built", years=years)
    as_text = lambda s_: s_  # noqa: E731  (out() writes a ready string as-is)
    if stages == {1}:
        for lang in ("tr", "en"):
            out(f"sky_events.{lang}.md", collective_text(coll_all, first, last, tz, lang), as_text)
        return _finish(man, run_dir, out)

    # 2 natal ----------------------------------------------------------------------------------
    natal = compute_chart(BirthData(year=birth["year"], month=birth["month"], day=birth["day"],
                                    hour=birth.get("hour", 12), minute=birth.get("minute", 0),
                                    latitude=bgeo["latitude"], longitude=bgeo["longitude"],
                                    time_precision=birth.get("time_precision", "exact")))
    out("natal_chart.json", natal)
    ck = P.chart_key(natal)
    man.data["chart_key"] = ck
    man.stage("2 natal", "ok", chart_key=ck)

    corpus_sha = cal_corpus.corpus_sha()

    # 3 events ---------------------------------------------------------------------------------
    events, ev_key, st = ensure_events(natal, tz, start)
    man.stage("3 events", st, **({} if st == "cache_hit" else {"n": len(events["events"])}))
    out("personal_events.json", events, P.dumps)

    # 4 scores + periods -------------------------------------------------------------------------
    scores = periods = None
    if 4 in stages:
        scores, periods, st = ensure_scores(natal, tz, events, ev_key)
        man.stage("4 scores", st, **({} if st == "cache_hit" else {"periods": len(periods["periods"])}))
        out("day_scores.json", scores, S.dumps)
        out("periods.json", periods, S.dumps)

    # 5 best days --------------------------------------------------------------------------------
    best = None
    if 5 in stages or 6 in stages and mode == "all":
        best, st = ensure_best_days(natal, tz, start)
        man.stage("5 best_days", st)
        if activity:
            best = {**best, "activities": {activity: best["activities"][activity]}}

    # 6 notifications ------------------------------------------------------------------------------
    if 6 in stages and periods is not None:
        wins = BD.all_windows(best) if best else []
        notif = S.notifications(periods, events, coll_all, S.load_templates(), windows=wins)
        out("notifications.json", notif, S.dumps)
        for lang in ("tr", "en"):
            out(f"notifications.{lang}.md", notifications_text(notif, lang), as_text)
        man.stage("6 notifications", "ok", n=len(notif["candidates"]))

    # 7 texts --------------------------------------------------------------------------------------
    index, modern = cal_corpus.load()
    with open(BA.TAGS, encoding="utf-8") as fh:
        tags = json.load(fh)
    units: dict = {}
    if periods is not None or mode in ("events",):
        units = CS.plan_units(events, periods or {"periods": []}, events["collective_refs"], coll_by_id,
                              index, modern, tags)
    bd_units = CS.best_day_units(best, index, modern) if best else {}
    want: list[dict] = []
    if 7 in stages:
        if mode in ("calendar", "all", "events"):
            # the whole 12-month horizon (texts are cached, so this is paid once per chart)
            want += [u for u in units.values() if u["text"] and CS.overlaps(u["span"], first, last)]
        if mode == "month":
            y, m = (int(x) for x in mode_arg.split("-"))
            mf = date(y, m, 1)
            want += [u for u in units.values() if u["text"] and CS.overlaps(u["span"], mf, P.add_months(mf, 1) - timedelta(days=1))]
        if mode == "day":
            d = date.fromisoformat(mode_arg)
            want += [u for u in units.values() if u["text"] and u.get("importance") == "major"
                     and CS.overlaps(u["span"], d, d)]
            day = next(x for x in scores["days"] if x["local_date"] == d.isoformat())
            dn = CS.day_note_unit(day, events, units, index, modern)
            units[dn["unit_id"]] = dn
            if dn["text"]:
                want.append(dn)
        if mode in ("best-days", "all"):
            want += [u for u in bd_units.values() if u["text"]]
        want = list({u["unit_id"]: u for u in want}.values())
        store = G.TextStore(os.path.join(C.COLLECTIVE_DIR, "texts.json"),
                            os.path.join(CACHE_ROOT, ck, "texts.json"))
        if dry_run:
            todo = [u for u in want if not store.get(u["scope"], G.cache_key(
                u, corpus_sha, None if u["scope"] == "collective" else ck))]
            prompts = [dict(zip(("system", "user"), PR.build_draft_prompt(todo[i:i + G.BATCH])))
                       for i in range(0, len(todo), G.BATCH)]
            out("prompts.json", {"model_calls": 0, "units": [u["unit_id"] for u in todo], "prompts": prompts})
            man.stage("7 texts", "dry_run", units=len(todo), prompts=len(prompts))
        else:
            kw = {k: v for k, v in (("model", model), ("translation_model", translation_model)) if v}
            gen = G.make_generator(**kw) if want else None
            stats = G.ensure_texts(want, store, gen, corpus_sha, ck) if want else \
                {"cached": 0, "generated": 0, "refused": {}, "batches": 0}
            man.data["texts"] = {**stats, "usage": gen.usage if gen else None}
            man.stage("7 texts", "ok", generated=stats["generated"], cached=stats["cached"],
                      refused=len(stats["refused"]))
        all_units = {**units, **bd_units}
        for lang in ("tr", "en"):
            out(f"texts_{lang}.json", G.texts_for(all_units, store, corpus_sha, ck, lang))
        man.data["gaps"] = G.gaps(all_units)
        if best:
            texts_tr = G.texts_for(bd_units, store, corpus_sha, ck, "tr")
            texts_en = G.texts_for(bd_units, store, corpus_sha, ck, "en")
            for act, a in best["activities"].items():
                a["texts"] = {ld: {"text_tr": texts_tr.get(f"b:{act}:{ld}", {}).get("text"),
                                   "text_en": texts_en.get(f"b:{act}:{ld}", {}).get("text")}
                              for ld in a["top_days"]}
    if best:
        out("best_days.json", BD.public(best), BD.dumps)
        for lang in ("tr", "en"):
            out(f"best_days.{lang}.md", best_days_text(best, lang), as_text)
    if 7 in stages and mode in ("events", "calendar", "all"):
        store = G.TextStore(os.path.join(C.COLLECTIVE_DIR, "texts.json"), os.path.join(CACHE_ROOT, ck, "texts.json"))
        for lang in ("tr", "en"):
            out(f"year_overview.{lang}.md", events_text(events, units, store, corpus_sha, ck, lang), as_text)

    # 8 views ----------------------------------------------------------------------------------------
    if 8 in stages and scores is not None:
        store = G.TextStore(os.path.join(C.COLLECTIVE_DIR, "texts.json"), os.path.join(CACHE_ROOT, ck, "texts.json"))
        months = []
        if mode == "month":
            months = [mode_arg]
        elif mode in ("calendar", "all"):
            m = date(start.year, start.month, 1)
            while m <= last:
                months.append(f"{m.year:04d}-{m.month:02d}")
                m = P.add_months(m, 1)
        for ym in months:
            mv = month_view(ym, events, scores, periods, coll_all, units, store, corpus_sha, ck, tz)
            out(f"calendar_{ym}.json", mv)
            for lang in ("tr", "en"):
                out(f"calendar_{ym}.{lang}.md",
                    month_text(mv, events, periods, units, store, corpus_sha, ck, lang), as_text)
        if mode == "day":
            dv = day_view(mode_arg, events, scores, periods, coll_all, units, store, corpus_sha, ck, tz)
            out(f"day_{mode_arg}.json", dv)
            for lang in ("tr", "en"):
                out(f"day_{mode_arg}.{lang}.md", day_text(dv, periods, units, store, corpus_sha, ck, lang), as_text)
        man.stage("8 views", "ok", months=len(months))
    return _finish(man, run_dir, out)


# --- cached calendar stages (shared with the Personal Astrologist, PA Phase 0 G5) ------------------
def _cache_dir(natal: dict, tz: str) -> str:
    return os.path.join(CACHE_ROOT, P.chart_key(natal), _tz_slug(tz))


def ensure_events(natal: dict, tz: str, start: date) -> tuple[dict, str, str]:
    """personal_events for 12 months from ``start`` -> (doc, ev_key, 'cache_hit' | 'built')."""
    ev_key = _sha({"from": start.isoformat(), "tz": tz, "corpus": cal_corpus.corpus_sha(),
                   "schema": K.SCHEMA_EVENTS, "orbs": K.TRANSIT_ORB})[:16]
    path = os.path.join(_cache_dir(natal, tz), f"personal_events_{ev_key}.json")
    if os.path.exists(path):
        return _read(path), ev_key, "cache_hit"
    events = P.build_personal_events(natal, tz, start)
    _write(path, events, P.dumps)
    return events, ev_key, "built"


def ensure_scores(natal: dict, tz: str, events: dict, ev_key: str) -> tuple[dict, dict, str]:
    """day scores + periods for an events doc -> (scores, periods, status)."""
    sc_key = _sha({"ev": ev_key, "aff": _file_sha(BA.OUT), "bands": K.BAND})[:16]
    path = os.path.join(_cache_dir(natal, tz), f"scores_{sc_key}.json")
    if os.path.exists(path):
        cached = _read(path)
        return cached["scores"], cached["periods"], "cache_hit"
    full = S.day_scores(events, natal, BA.load())
    periods = S.periods(full, events)
    scores = S.public_scores(full)
    _write(path, {"scores": scores, "periods": periods})
    return scores, periods, "built"


def ensure_best_days(natal: dict, tz: str, start: date) -> tuple[dict, str]:
    """Best Days (90 days from ``start``, every activity, with the internal ``_parts``) -> (doc, status)."""
    cat = BD.load_catalogue()
    bd_key = _sha({"from": start.isoformat(), "tz": tz, "cat": cat["version"], "grounding": _sha(cat),
                   "th": BD.GRADE_TH, "corpus": cal_corpus.corpus_sha()})[:16]
    path = os.path.join(_cache_dir(natal, tz), f"best_days_{bd_key}.json")
    if os.path.exists(path):
        return _read(path), "cache_hit"
    best = BD.build_best_days(natal, tz, start, cat=cat)
    _write(path, best)
    return best, "built"


def ensure_calendar(natal: dict, tz: str, start: date, *, best_days: bool = True) -> dict:
    """Every cached calendar product for (chart, tz, start): {events, scores, periods, best, status}."""
    events, ev_key, s1 = ensure_events(natal, tz, start)
    scores, periods, s2 = ensure_scores(natal, tz, events, ev_key)
    best, s3 = ensure_best_days(natal, tz, start) if best_days else (None, "skipped")
    return {"events": events, "scores": scores, "periods": periods, "best": best,
            "status": {"events": s1, "scores": s2, "best_days": s3}}


def _finish(man: Manifest, run_dir: str, out) -> dict:
    man.data["status"] = "ok"
    man.stage("9 manifest", "ok")
    out("run_manifest.json", man.data)
    return {"run_dir": run_dir, "manifest": man.data}


# --- views (CAL_05 §3) --------------------------------------------------------------------------------
_LUN = ("new_moon", "full_moon", "solar_eclipse", "lunar_eclipse")


def _voc_local(coll: list[dict], d: date, tz: str) -> list[list[str]]:
    zi = ZoneInfo(tz)
    d0 = datetime(d.year, d.month, d.day, tzinfo=zi)
    d1 = d0 + timedelta(days=1)
    out = []
    for e in coll:
        if e["kind"] != "voc_moon":
            continue
        s = A.parse_iso_utc(e["start_utc"]).astimezone(zi)
        t = A.parse_iso_utc(e["end_utc"]).astimezone(zi)
        if t <= d0 or s >= d1:
            continue
        a, b = max(s, d0), min(t, d1)
        out.append([a.strftime("%H:%M"), "24:00" if b == d1 else b.strftime("%H:%M")])
    return out


def _moon_phase(d: date, tz: str, lun_dates: dict) -> str:
    if d.isoformat() in lun_dates:
        return lun_dates[d.isoformat()]
    e = A.elongation(A.local_time_jd(d, 12, 0, tz))
    if e < 90:
        return "waxing_crescent"
    if e < 180:
        return "waxing_gibbous"
    if e < 270:
        return "waning_gibbous"
    return "waning_crescent"


def _day_entry(d: date, day: dict, events: dict, periods: dict, coll: list[dict], units: dict,
               tz: str, lun_dates: dict) -> dict:
    ds = d.isoformat()
    jd = A.local_time_jd(d, 12, 0, tz)
    retro = sorted(b for b in K.STATION_BODIES if A.lon_speed(jd, b)[1] < 0)
    evs = []
    for e in events["events"]:
        on = (ds in e.get("exacts_local", []) if e["kind"] == "transit" and e["exacts_local"]
              else e.get("local_date") == ds if "local_date" in e
              else e["kind"] == "transit" and A.local_date_of_iso(e["closest_utc"], tz) == ds)
        if on and e["importance"] != "minor":
            u = units.get({"transit": "t:", "station_on_point": "s:"}.get(e["kind"], "l:") + e["id"], {})
            evs.append({"id": e["id"], "label_tr": u.get("label_tr"), "label_en": u.get("label_en"),
                        "importance": e["importance"], "has_text": bool(u.get("text"))})
    # a station already shown as "turns retrograde on your X" is not repeated as a bare station
    shown = {e.get("ref") for e in events["events"] if e["kind"] == "station_on_point"
             and e.get("local_date") == ds and e["importance"] != "minor"}
    for c in events["collective_refs"]:
        if c["id"] in shown:
            continue
        if c.get("local_date") == ds and c["kind"] in ("ingress", "station_retrograde", "station_direct"):
            tr, en = CS.collective_label({"id": c["id"], **_coll_lookup(coll, c["id"])})
            evs.append({"id": c["id"], "label_tr": tr, "label_en": en, "importance": "collective",
                        "has_text": False})
    active = [{"id": p["id"], "goal": p["goal"], "kind": p["kind"]} for p in periods["periods"]
              if p["start_local"] <= ds <= p["end_local"]]
    return {"local_date": ds, "tone": day["tone"],
            "moon": {"sign": A.sign_key(A.lon(jd, "moon")), "phase": _moon_phase(d, tz, lun_dates),
                     "voc_local": _voc_local(coll, d, tz)},
            "retrograde": retro, "events": evs, "active_periods": active,
            "goals": {g: day["goals"][g]["band"] for g in GOAL_ORDER}}


_COLL_INDEX: dict = {}


def _coll_lookup(coll: list[dict], cid: str) -> dict:
    if id(coll) not in _COLL_INDEX:
        _COLL_INDEX.clear()
        _COLL_INDEX[id(coll)] = {e["id"]: e for e in coll}
    return _COLL_INDEX[id(coll)][cid]


def _lun_dates(events: dict) -> dict:
    out = {}
    for e in events["events"]:
        if e["kind"] in _LUN:
            out[e["local_date"]] = {"new_moon": "new", "full_moon": "full",
                                    "solar_eclipse": "new", "lunar_eclipse": "full"}[e["kind"]]
    return out


def month_view(ym: str, events, scores, periods, coll, units, store, corpus_sha, ck, tz) -> dict:
    y, m = (int(x) for x in ym.split("-"))
    mf = date(y, m, 1)
    ml = P.add_months(mf, 1) - timedelta(days=1)
    lun = _lun_dates(events)
    days = [_day_entry(date.fromisoformat(d["local_date"]), d, events, periods, coll, units, tz, lun)
            for d in scores["days"] if mf.isoformat() <= d["local_date"] <= ml.isoformat()]
    a, b = mf.isoformat(), ml.isoformat()
    in_m = lambda s, e: s <= b and e >= a  # noqa: E731
    return {"schema_version": "cal-month-1", "month": ym, "tz": tz, "chart_key": ck, "days": days,
            "lunations": [e["id"] for e in events["events"] if e["kind"] in ("new_moon", "full_moon") and a <= e["local_date"] <= b],
            "eclipses": [e["id"] for e in events["events"] if e["kind"].endswith("_eclipse") and a <= e["local_date"] <= b],
            "retrograde_periods": [c["id"] for c in events["collective_refs"] if c["kind"] == "retrograde_period"
                                   and in_m(c["start_local"], c["end_local"])],
            "major_transits": [e["id"] for e in events["events"] if e["kind"] == "transit" and e["importance"] == "major"
                               and in_m(e["start_local"], e["end_local"])],
            "periods": [p["id"] for p in periods["periods"] if in_m(p["start_local"], p["end_local"])]}


def day_view(ds: str, events, scores, periods, coll, units, store, corpus_sha, ck, tz) -> dict:
    d = date.fromisoformat(ds)
    day = next(x for x in scores["days"] if x["local_date"] == ds)
    entry = _day_entry(d, day, events, periods, coll, units, tz, _lun_dates(events))

    def text(uid):
        u = units.get(uid)
        if not u or not u["text"]:
            return None
        e = store.get(u["scope"], G.cache_key(u, corpus_sha, None if u["scope"] == "collective" else ck))
        return {"text_tr": e["tr"], "text_en": e["en"], "trace": e["trace"]} if e else None
    entry["day_note"] = text(f"d:{ds}")
    entry["event_texts"] = {ev["id"]: text(("t:" if ev["id"].startswith("tr:") else "l:") + ev["id"])
                            for ev in entry["events"] if ev["importance"] == "major"}
    return {"schema_version": "cal-day-1", "tz": tz, "chart_key": ck, **entry}


# --- readable month / day documents -------------------------------------------------------------------------
_MONTHS = {"tr": ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
                  "Ekim", "Kasım", "Aralık"],
           "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                  "October", "November", "December"]}
_H = {"tr": {"sky": "Ayın gökyüzü", "transits": "Önemli transitler", "periods": "Dönemler",
             "days": "Gün gün", "retro": "Retro dönemleri", "note": "Günün notu", "events": "Günün olayları",
             "active": "Etkin dönemler",
             "areas": "yaşam alanları",
             "band": {"supportive": "destekleyici", "strongly_supportive": "çok destekleyici",
                      "challenging": "zorlayıcı", "strongly_challenging": "çok zorlayıcı",
                      "mixed": "karışık"}, "tone": {"favorable": "destekleyici", "challenging": "zorlayıcı",
                                                   "mixed": "karışık", "quiet": "sakin"}, "until": "–"},
      "en": {"sky": "Sky this month", "transits": "Key transits", "periods": "Periods",
             "days": "Day by day", "retro": "Retrograde periods", "note": "Note for the day",
             "events": "Events today", "active": "Active periods",
             "areas": "life areas",
             "band": {"supportive": "supportive", "strongly_supportive": "very supportive",
                      "challenging": "demanding", "strongly_challenging": "very demanding",
                      "mixed": "mixed"},
             "tone": {"favorable": "favorable", "challenging": "challenging", "mixed": "mixed",
                      "quiet": "quiet"}, "until": "–"}}


def _fmt(ds: str, lang: str) -> str:
    d = date.fromisoformat(ds)
    return f"{d.day} {_MONTHS[lang][d.month - 1]}" + ("" if d.year == date.today().year else f" {d.year}")


def _span(a: str, b: str, lang: str) -> str:
    return _fmt(a, lang) if a == b else f"{_fmt(a, lang)} {_H[lang]['until']} {_fmt(b, lang)}"


def _unit_text(uid: str, units: dict, store, corpus_sha: str, ck: str, lang: str):
    u = units.get(uid)
    if not u or not u["text"]:
        return None
    e = store.get(u["scope"], G.cache_key(u, corpus_sha, None if u["scope"] == "collective" else ck))
    return e[lang] if e else None


def month_text(mv: dict, events: dict, periods: dict, units: dict, store, corpus_sha, ck, lang: str) -> str:
    h = _H[lang]
    y, m = (int(x) for x in mv["month"].split("-"))
    ev = {e["id"]: e for e in events["events"]}
    lab = f"label_{lang}"
    L = [f"# {_MONTHS[lang][m - 1]} {y}", ""]

    L += [f"## {h['sky']}", ""]
    for eid in mv["lunations"] + mv["eclipses"]:
        e = ev[eid]
        u = units.get(f"l:{eid}", {})
        L.append(f"**{u.get(lab, eid)}** · {_fmt(e['local_date'], lang)}")
        t = _unit_text(f"l:{eid}", units, store, corpus_sha, ck, lang)
        L += ([t, ""] if t else [""])
    refs = {c["id"]: c for c in events["collective_refs"]}
    if mv["retrograde_periods"]:
        L += [f"**{h['retro']}**", ""]
        for rid in mv["retrograde_periods"]:
            c = refs[rid]
            u = units.get(f"c:{rid}", {})
            L.append(f"- {u.get(lab, rid)}: {_span(c['start_local'], c['end_local'], lang)}")
        L.append("")

    a, b = f"{mv['month']}-01", f"{mv['month']}-31"
    tr = [e for e in events["events"] if e["kind"] == "transit" and e["importance"] != "minor"
          and e["start_local"] <= b and e["end_local"] >= a]
    tr.sort(key=lambda e: ({"major": 0, "moderate": 1}[e["importance"]], e["start_local"]))
    if tr:
        L += [f"## {h['transits']}", ""]
        for e in tr:
            u = units.get(f"t:{e['id']}", {})
            L.append(f"### {u.get(lab, e['id'])}")
            L.append(f"*{_span(e['start_local'], e['end_local'], lang)}*")
            t = _unit_text(f"t:{e['id']}", units, store, corpus_sha, ck, lang)
            L += (["", t, ""] if t else [""])

    ps = [p for p in periods["periods"] if p["id"] in set(mv["periods"])]
    if ps:
        L += [f"## {h['periods']}", ""]
        for p in ps:
            u = units.get(f"p:{p['id']}", {})
            L.append(f"### {u.get(lab, p['id'])}")
            L.append(f"*{_span(p['start_local'], p['end_local'], lang)}*")
            t = _unit_text(f"p:{p['id']}", units, store, corpus_sha, ck, lang)
            L += (["", t, ""] if t else [""])

    L += [f"## {h['days']}", ""]
    rows = []                       # [first_date, last_date, names, areas]
    for d in mv["days"]:
        names = [x[lab] for x in d["events"] if x.get(lab)]
        areas = [f"{GOALS[g][0 if lang == 'tr' else 1]} {h['band'][b]}"
                 for g, b in d["goals"].items() if b != "quiet"]
        if not names and not areas:
            continue
        prev = rows[-1] if rows else None
        # consecutive event-free days with the same life-area picture become one line
        if prev and not names and not prev[2] and prev[3] == areas and                 date.fromisoformat(d["local_date"]) - date.fromisoformat(prev[1]) == timedelta(days=1):
            prev[1] = d["local_date"]
            continue
        rows.append([d["local_date"], d["local_date"], names, areas])
    for a, b, names, areas in rows:
        line = f"- **{_span(a, b, lang)}**"
        if names:
            line += ": " + "; ".join(names)
        if areas:
            line += f" · *{h['areas']}: " + ", ".join(areas) + "*"
        L.append(line)
    return "\n".join(L).rstrip() + "\n"


def day_text(dv: dict, periods: dict, units: dict, store, corpus_sha, ck, lang: str) -> str:
    h = _H[lang]
    lab = f"label_{lang}"
    L = [f"# {_fmt(dv['local_date'], lang)} · {h['tone'][dv['tone']]}", ""]
    if dv.get("day_note"):
        L += [f"## {h['note']}", "", dv["day_note"][f"text_{lang}"], ""]
    if dv["events"]:
        L += [f"## {h['events']}", ""]
        for e in dv["events"]:
            L.append(f"### {e.get(lab) or e['id']}")
            t = (dv.get("event_texts") or {}).get(e["id"])
            L += (["", t[f"text_{lang}"], ""] if t else [""])
    per = {p["id"]: p for p in periods["periods"]}
    if dv["active_periods"]:
        L += [f"## {h['active']}", ""]
        for p in dv["active_periods"]:
            u = units.get(f"p:{p['id']}", {})
            q = per[p["id"]]
            L.append(f"- {u.get(lab, p['id'])} ({_span(q['start_local'], q['end_local'], lang)})")
    return "\n".join(L).rstrip() + "\n"


_H2 = {"tr": {"sky_title": "Gökyüzü olayları", "year_title": "Yılın", "major": "Büyük transitler",
              "moderate": "Orta etkili transitler", "lunations": "Haritanda yeni ay, dolunay ve tutulmalar",
              "stations": "Haritandaki noktalarda yön değiştiren gezegenler",
              "minor_note": "{n} küçük transit yalnızca takvimde etiket olarak gösterilir.",
              "best_title": "En iyi günler", "top": "En iyi günler", "why": "Neden",
              "caveat": "Dikkat", "windows": "Destekleyici aralıklar", "avoid": "Kaçınılması iyi olan günler",
              "none": "yok", "notif_title": "Bildirim önerileri", "grade": {"excellent": "mükemmel", "good": "iyi"},
              "prio": "öncelik"},
       "en": {"sky_title": "Sky events", "year_title": "Your year", "major": "Major transits",
              "moderate": "Moderate transits", "lunations": "New moons, full moons and eclipses in your chart",
              "stations": "Planets turning on points of your chart",
              "minor_note": "{n} minor transits appear in the calendar as labels only.",
              "best_title": "Best days", "top": "Top days", "why": "Why", "caveat": "Watch",
              "windows": "Supportive windows", "avoid": "Days to avoid", "none": "none",
              "notif_title": "Notification suggestions", "grade": {"excellent": "excellent", "good": "good"},
              "prio": "priority"}}


def _group_by_month(items: list[tuple[str, str]], lang: str) -> list[str]:
    """items: [(local_date, line)] -> markdown grouped under month headings."""
    L, cur = [], None
    for ds, line in sorted(items):
        ym = ds[:7]
        if ym != cur:
            y, m = (int(x) for x in ym.split("-"))
            L += ["", f"## {_MONTHS[lang][m - 1]} {y}", ""]
            cur = ym
        L.append(line)
    return L


def collective_text(coll: list[dict], first: date, last: date, tz: str, lang: str) -> str:
    a, b = first.isoformat(), last.isoformat()
    lab = 0 if lang == "tr" else 1
    items = []
    for e in coll:
        k = e["kind"]
        if k in ("new_moon", "full_moon", "solar_eclipse", "lunar_eclipse", "station_retrograde",
                 "station_direct") or (k == "ingress" and e["body"] != "moon"):
            ds = A.local_date_of_iso(e["t_utc"], tz)
            if a <= ds <= b:
                items.append((ds, f"- **{_fmt(ds, lang)}**: {CS.collective_label(e)[lab]}"))
        elif k == "retrograde_period":
            s_, t_ = A.local_date_of_iso(e["start_utc"], tz), A.local_date_of_iso(e["end_utc"], tz)
            if s_ <= b and t_ >= a:
                items.append((max(s_, a), f"- **{_span(s_, t_, lang)}**: {CS.collective_label(e)[lab]}"))
    L = [f"# {_H2[lang]['sky_title']} · {_span(a, b, lang)}"] + _group_by_month(items, lang)
    return "\n".join(L).rstrip() + "\n"


def events_text(events: dict, units: dict, store, corpus_sha, ck, lang: str) -> str:
    h = _H2[lang]
    lab = f"label_{lang}"
    hz = events["horizon"]
    L = [f"# {h['year_title']} · {_span(hz['from_local'], hz['to_local'], lang)}", ""]

    def block(title, evs, prefix):
        if not evs:
            return
        L.extend([f"## {title}", ""])
        for e in evs:
            u = units.get(prefix + e["id"], {})
            when = _span(e["start_local"], e["end_local"], lang) if "start_local" in e else _fmt(e["local_date"], lang)
            L.append(f"### {u.get(lab) or e['id']}")
            L.append(f"*{when}*")
            t = _unit_text(prefix + e["id"], units, store, corpus_sha, ck, lang)
            L.extend(["", t, ""] if t else [""])

    tr = [e for e in events["events"] if e["kind"] == "transit"]
    block(h["major"], [e for e in tr if e["importance"] == "major"], "t:")
    block(h["moderate"], [e for e in tr if e["importance"] == "moderate"], "t:")
    block(h["lunations"], [e for e in events["events"] if e["kind"] in _LUN and e["importance"] != "minor"], "l:")
    st = [e for e in events["events"] if e["kind"] == "station_on_point" and e["importance"] != "minor"]
    if st:
        L.extend([f"## {h['stations']}", ""])
        for e in st:
            L.append(f"- **{_fmt(e['local_date'], lang)}**: {units.get('s:' + e['id'], {}).get(lab) or e['id']}")
        L.append("")
    n_minor = sum(1 for e in tr if e["importance"] == "minor")
    L.append(h["minor_note"].format(n=n_minor))
    return "\n".join(L).rstrip() + "\n"


def _collapse_dates(dates: list[str], lang: str) -> str:
    runs: list[list[str]] = []
    for ds in sorted(dates):
        if runs and date.fromisoformat(ds) - date.fromisoformat(runs[-1][1]) == timedelta(days=1):
            runs[-1][1] = ds
        else:
            runs.append([ds, ds])
    return ", ".join(_span(a, b, lang) for a, b in runs)


def best_days_text(best: dict, lang: str) -> str:
    h = _H2[lang]
    hz = best["horizon"]
    L = [f"# {h['best_title']} · {_span(hz['from_local'], hz['to_local'], lang)}", ""]
    grades = {}
    for act, a in best["activities"].items():
        grades = {d["local_date"]: d["grade"] for d in a["days"]}
        name = BD.ACTIVITIES[act][0 if lang == "tr" else 1]
        L += [f"## {name}", "", f"### {h['top']}", ""]
        if not a["top_days"]:
            L += [f"- {h['none']}", ""]
        for ds in a["top_days"]:
            r = a["reasons"].get(ds, {})
            L.append(f"**{_fmt(ds, lang)}** ({h['grade'].get(grades[ds], grades[ds])})")
            pos = [x[f"label_{lang}"] for x in r.get("positive", [])]
            neg = [x[f"label_{lang}"] for x in r.get("negative", [])]
            if pos:
                L.append(f"- {h['why']}: " + "; ".join(pos))
            if neg:
                L.append(f"- {h['caveat']}: " + "; ".join(neg))
            t = (a.get("texts") or {}).get(ds, {}).get(f"text_{lang}")
            L += (["", t, ""] if t else [""])
        L += [f"### {h['windows']}", "",
              "- " + (", ".join(_span(w["start"], w["end"], lang) for w in a["windows"]) or h["none"]), "",
              f"### {h['avoid']}", "",
              "- " + (_collapse_dates([x["local_date"] for x in a["avoid_days"]], lang) or h["none"]), ""]
    return "\n".join(L).rstrip() + "\n"


def notifications_text(notif: dict, lang: str) -> str:
    h = _H2[lang]
    L = [f"# {h['notif_title']}", ""]
    for c in notif["candidates"]:
        L.append(f"- **{_fmt(c['trigger_local_date'], lang)}** ({h['prio']} {c['priority']}): {c[f'text_{lang}']}")
    return "\n".join(L).rstrip() + "\n"


# --- CLI -------------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Personal calendar + Best Days (CAL_05).")
    ap.add_argument("--date", required=True, help="birth date YYYY-MM-DD")
    ap.add_argument("--time", help="birth time HH:MM (24h); omit for unknown")
    ap.add_argument("--location", required=True, help="birth location (geocoded)")
    ap.add_argument("--current-location", help="where the user is now (sets the tz)")
    ap.add_argument("--mode", nargs="+", default=["calendar"],
                    help="collective | events | calendar | month YYYY-MM | day YYYY-MM-DD | best-days | all")
    ap.add_argument("--from", dest="start", help="horizon start YYYY-MM-DD (default: today in the current tz)")
    ap.add_argument("--activity", choices=BD.ACTIVITY_ORDER)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--translation-model")
    args = ap.parse_args(argv)
    mode, mode_arg = args.mode[0], (args.mode[1] if len(args.mode) > 1 else None)
    if mode not in MODES or (mode in ("month", "day") and not mode_arg):
        ap.error(f"bad --mode {args.mode}")
    y, m, d = (int(x) for x in args.date.split("-"))
    birth = {"year": y, "month": m, "day": d, "location": args.location,
             "time_precision": "exact" if args.time else "unknown"}
    if args.time:
        birth["hour"], birth["minute"] = (int(x) for x in args.time.split(":"))
    res = run_calendar(birth, current_location=args.current_location, mode=mode, mode_arg=mode_arg,
                       start=date.fromisoformat(args.start) if args.start else None,
                       activity=args.activity, dry_run=args.dry_run, model=args.model,
                       translation_model=args.translation_model)
    print(f"run folder: {res['run_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
