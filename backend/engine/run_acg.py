#!/usr/bin/env python3
"""run_acg.py — the astrocartography orchestrator (ACG spec 05 + change order 07 §8).

Modes (07 §8):
    map        no place                    lines, city scan, goal scan, 11 heat layers
    city       --city TEXT | --lat --lon   + locate, relocate, grounding, place reading
    country    --country ISO               + country aggregate + overview reading
    region     --region ADMIN1_ID          + region aggregate + overview reading
    recommend  --recommend GOAL [--scope world|TR|ISO] [--query-text TEXT]
                                           + "Where Should I Go?" ranking + explanations

Stages (spec 05 §1): input-resolve -> compute_chart -> compute_acg -> city_scan ->
goal_scan -> (locate -> relocate -> ground_acg -> reading) | aggregate | recommend ->
manifest. An absence at any stage is written and recorded; later stages degrade as
their specs say; it is never an exception exit.

Per-chart cache (07 §8): acg.json, acg.geojson, city_scan.json, goal_scan.npz and the
heat layers depend only on the birth instant + corpus + affinity table, so they live in
``acg_run/_cache/<chart key>/`` and are reused across runs. Readings are cached by
(chart key, place id, focus goal). Run folders ``acg_run/YYYYMMDD-HHMMSS_<3>/`` hold the
per-run artifacts, every file suffixed with the birth date (repo convention).

    python run_acg.py                                            # interactive
    python run_acg.py --date 1985-03-14 --time 11:30 --location Istanbul --city İzmir
    python run_acg.py ... --country TR
    python run_acg.py ... --recommend career --scope world
    python run_acg.py ... --city Berlin --dry-run                # no model calls
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from typing import Optional

ENGINE_ROOT = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(ENGINE_ROOT))  # repo root (Chart_wheel, run caches)
# Layer packages live under backend/engine; keep ENGINE as the import root.
_ENGINE = ENGINE_ROOT
for _d in ("d_layer", "principles_grounding", "Astrocartography", "acg_reading",
           "Interpretation_layer"):
    _p = os.path.join(ENGINE_ROOT, _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)
if ENGINE_ROOT not in sys.path:
    sys.path.insert(0, ENGINE_ROOT)

import run  # noqa: E402
from run import _write_json, suffixed  # noqa: E402

ACG_RUNS_DIR = os.path.join(REPO_ROOT, "acg_run")
CACHE_DIR = os.path.join(ACG_RUNS_DIR, "_cache")
MODES = ("map", "city", "country", "region", "recommend")


# ===========================================================================
# helpers
# ===========================================================================

def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def _read_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _mint_run_id(now_utc: datetime) -> str:
    import run_predictive
    return run_predictive._mint_run_id(now_utc)


class Stages:
    """Stage bookkeeping for the manifest (status, artifact, cache hit, duration)."""

    def __init__(self):
        self.rows: list[dict] = []
        self.status: dict[str, str] = {}

    def record(self, name: str, status: str, artifact=None, t0: Optional[float] = None,
               cache_hit: Optional[bool] = None, error: Optional[str] = None) -> None:
        self.rows.append({"name": name, "status": status, "artifact": artifact,
                          "cache_hit": cache_hit, "error": error,
                          "duration_ms": None if t0 is None else
                          round((time.monotonic() - t0) * 1000, 1)})
        self.status[name] = status


# ===========================================================================
# the per-chart cache (07 §8)
# ===========================================================================

def _file_sha(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def chart_cache_key(acg_meta: dict, corpus_sha: Optional[str], affinity_sha: Optional[str]) -> str:
    """07 §8 key (jd_ut, flags, corpus, affinity) + the gazetteer and grid the scans read."""
    acg_dir = os.path.join(ENGINE_ROOT, "Astrocartography")
    return _sha({"jd_ut": acg_meta.get("jd_ut"), "flags": acg_meta.get("flags"),
                 "node_type": acg_meta.get("node_type"), "corpus": corpus_sha,
                 "affinity": affinity_sha,
                 "gazetteer": _file_sha(os.path.join(acg_dir, "gazetteer.json")),
                 "grid": _file_sha(os.path.join(acg_dir, "geo_grid.npz")),
                 # the compute code itself: a geometry or scoring change rebuilds the cache
                 "code": [_file_sha(os.path.join(acg_dir, f)) for f in
                          ("compute_acg.py", "compute_parans.py", "acg_goals.py",
                           "acg_constants.py", "acg_locate.py")]})[:24]


def build_chart_products(natal: dict, cache_root: str = CACHE_DIR, *, stages: Stages,
                         with_goal_scan: bool = True) -> dict:
    """compute_acg + city_scan + goal_scan + heat layers, cached per chart."""
    import compute_acg as ca
    import acg_locate as al
    import acg_goals as ag
    import ground_acg as ga

    t0 = time.monotonic()
    acg = ca.compute_acg(natal)
    _, corpus_sha = ga.corpus_ok()
    aff_sha = ag.affinity_sha256()
    key = chart_cache_key(acg["meta"], corpus_sha, aff_sha)
    cdir = os.path.join(cache_root, key)
    os.makedirs(cdir, exist_ok=True)
    paths = {"acg": os.path.join(cdir, "acg.json"),
             "geojson": os.path.join(cdir, "acg.geojson"),
             "parans": os.path.join(cdir, "parans.json"),
             "parans_geojson": os.path.join(cdir, "acg_parans.geojson"),
             "city_scan": os.path.join(cdir, "city_scan.json"),
             "goal_scan": os.path.join(cdir, "goal_scan.npz")}

    hit = os.path.exists(paths["acg"])
    if not hit:
        ca.write_acg(acg, paths["acg"], paths["geojson"])
    stages.record("compute_acg", "ok" if acg["status"] == "ok"
                  else f"absent:{acg['absence']['reason']}", "acg.json", t0, cache_hit=hit)

    # parans (spec 10 §3): cached next to acg.json
    import compute_parans as cpar
    t0 = time.monotonic()
    hit = os.path.exists(paths["parans"])
    if hit:
        parans = _read_json(paths["parans"])
    else:
        parans = cpar.compute_parans(acg)
        with open(paths["parans"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(cpar.dumps(parans))
        with open(paths["parans_geojson"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(cpar.to_geojson(parans), separators=(",", ":")) + "\n")
    stages.record("compute_parans", parans.get("status", "ok"), "parans.json", t0,
                  cache_hit=hit)

    t0 = time.monotonic()
    hit = os.path.exists(paths["city_scan"])
    if hit:
        scan = _read_json(paths["city_scan"])
    else:
        scan = al.city_scan(acg)
        with open(paths["city_scan"], "w", encoding="utf-8", newline="\n") as fh:
            fh.write(ca.dumps(scan))
    stages.record("city_scan", scan.get("status", "ok"), "city_scan.json", t0, cache_hit=hit)

    goal = None
    if with_goal_scan and acg["status"] == "ok" and aff_sha is not None:
        t0 = time.monotonic()
        hit = os.path.exists(paths["goal_scan"])
        if hit:
            goal = ag.load_scan(paths["goal_scan"])
        else:
            grid = _load_grid()
            goal = ag.goal_scan(acg, ag.load_affinity(), al.load_gazetteer(), grid, parans)
            ag.save_scan(goal, paths["goal_scan"])
            for g in ag.GOAL_ORDER:
                with open(os.path.join(cdir, f"goal_heat_{g}.geojson"), "w",
                          encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(ag.heat_geojson(goal, g), separators=(",", ":")) + "\n")
        stages.record("goal_scan", "ok", "goal_scan.npz", t0, cache_hit=hit)
    elif with_goal_scan:
        stages.record("goal_scan", "absent:" + ("acg_absent" if acg["status"] != "ok"
                                                else "affinity_missing"), None)
    return {"acg": acg, "parans": parans, "city_scan": scan, "goal_scan": goal, "key": key,
            "dir": cdir,
            "paths": paths, "corpus_sha256": corpus_sha, "affinity_sha256": aff_sha}


def _load_grid() -> Optional[dict]:
    try:
        import acg_geodata
        return acg_geodata.load_grid()
    except Exception:  # noqa: BLE001 — geo index not built: cities only
        return None


# ===========================================================================
# model settings
# ===========================================================================

def resolve_models(args) -> dict:
    import llm_client
    from ar_generate import DEFAULT_MODEL, DEFAULT_TRANSLATION_MODEL
    model = args.model or DEFAULT_MODEL
    synth = args.synthesis_model or model
    trans = synth if args.translation_model == "same" else (args.translation_model
                                                            or DEFAULT_TRANSLATION_MODEL)
    return {"model": model, "synthesis": synth, "translation": trans,
            "missing": llm_client.missing_key_message([model, synth, trans], "the ACG reading")}


def make_generator(models: dict):
    from ar_generate import ACGGenerator
    return ACGGenerator(model=models["model"], synthesis_model=models["synthesis"],
                        translation_model=models["translation"])


# ===========================================================================
# the run
# ===========================================================================

def run_acg(request: dict, *, dry_run: bool = False, scan_only: bool = False,
            models: Optional[dict] = None, runs_dir: str = ACG_RUNS_DIR,
            cache_root: str = CACHE_DIR, now_utc: Optional[datetime] = None) -> dict:
    """``request``: {birth: {year, month, day, hour, minute, latitude, longitude,
    time_precision, location?}, city?, lat?, lon?, country?, region?, recommend?,
    scope?, query_text?, focus_goal?}. Returns the manifest."""
    from compute_chart import BirthData, compute_chart
    import acg_locate as al
    import acg_goals as ag
    import ground_acg as ga

    now_utc = now_utc or datetime.now(timezone.utc)
    run_id = _mint_run_id(now_utc)
    run_dir = os.path.join(runs_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)
    b = request["birth"]
    suffix = f"{int(b['year']):04d}-{int(b['month']):02d}-{int(b['day']):02d}"
    stages = Stages()
    artifacts: list[str] = []

    def write(name: str, obj, raw: Optional[str] = None) -> str:
        fname = suffixed(name, suffix)
        path = os.path.join(run_dir, fname)
        if raw is not None:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(raw)
        else:
            _write_json(path, obj)
        artifacts.append(fname)
        return fname

    def copy_cached(src: str, name: str) -> str:
        fname = suffixed(name, suffix)
        shutil.copyfile(src, os.path.join(run_dir, fname))
        artifacts.append(fname)
        return fname

    mode = ("recommend" if request.get("recommend") or request.get("query_text") else
            "country" if request.get("country") else
            "region" if request.get("region") else
            "city" if (request.get("city") or request.get("lat") is not None) else "map")
    if scan_only:
        mode = "map"
    manifest: dict = {
        "run_id": run_id, "layer": "acg", "mode": mode,
        "created_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "focus_goal": request.get("focus_goal"), "goal": request.get("recommend"),
        "scope": request.get("scope") if mode == "recommend" else None,
        "place": None, "stages": stages.rows, "stage_status": stages.status,
        "counts": {}, "models": {}, "gaps": [], "dry_run": dry_run,
        "acg_corpus_sha256": None, "affinity_sha256": None, "chart_cache_key": None,
        "artifacts": artifacts, "status": "failed",
    }

    def finish(status: str) -> dict:
        manifest["status"] = status
        _write_json(os.path.join(run_dir, suffixed("run_manifest.json", suffix)), manifest)
        manifest["run_dir"] = run_dir
        return manifest

    # --- stage 2: natal chart ------------------------------------------------
    t0 = time.monotonic()
    natal = compute_chart(BirthData(
        year=b["year"], month=b["month"], day=b["day"], hour=b.get("hour", 12),
        minute=b.get("minute", 0), latitude=b["latitude"], longitude=b["longitude"],
        time_precision=b.get("time_precision", "exact"),
        approx_bucket=b.get("approx_bucket")))
    stages.record("compute_chart", "ok", write("chart.json", natal), t0)

    # --- stages 3–4b: per-chart products (cached) ---------------------------
    prod = build_chart_products(natal, cache_root, stages=stages)
    prod["natal"] = natal
    acg = prod["acg"]
    manifest.update(acg_corpus_sha256=prod["corpus_sha256"],
                    affinity_sha256=prod["affinity_sha256"], chart_cache_key=prod["key"])
    copy_cached(prod["paths"]["acg"], "acg.json")
    copy_cached(prod["paths"]["geojson"], "acg.geojson")
    copy_cached(prod["paths"]["city_scan"], "city_scan.json")
    if os.path.exists(prod["paths"]["parans"]):
        copy_cached(prod["paths"]["parans"], "parans.json")
    if os.path.exists(prod["paths"]["parans_geojson"]):
        copy_cached(prod["paths"]["parans_geojson"], "acg_parans.geojson")
    if prod["goal_scan"] is not None:
        copy_cached(prod["paths"]["goal_scan"], "goal_scan.npz")
        for g in ag.GOAL_ORDER:
            src = os.path.join(prod["dir"], f"goal_heat_{g}.geojson")
            if os.path.exists(src):
                copy_cached(src, f"goal_heat_{g}.geojson")

    if acg["status"] != "ok":
        reason = acg["absence"]["reason"]
        for later in ("locate", "relocate", "ground_acg", "reading", "aggregate", "recommend"):
            stages.record(later, f"skipped:{reason}", None)
        manifest["gaps"].append(f"acg_absent:{reason}")
        return finish("absent")
    if mode == "map":
        return finish("ok")

    aff = ag.load_affinity() if prod["affinity_sha256"] else None
    if models is None and not dry_run:
        raise ValueError("models are required for a live reading")
    if models:
        manifest["models"] = {k: v for k, v in models.items() if k != "missing"}

    if mode == "city":
        return _city(request, natal, acg, aff, prod, stages, manifest, write, finish,
                     dry_run=dry_run, models=models, cache_root=cache_root)
    if mode in ("country", "region"):
        import acg_views
        return acg_views.run_area(mode, request, acg, aff, prod, stages, manifest, write,
                                  finish, dry_run=dry_run, models=models,
                                  make_generator=make_generator)
    import acg_views
    return acg_views.run_recommend(request, acg, aff, prod, stages, manifest, write, finish,
                                   dry_run=dry_run, models=models,
                                   make_generator=make_generator)


def _city(request, natal, acg, aff, prod, stages, manifest, write, finish, *,
          dry_run, models, cache_root):
    import acg_locate as al
    import ground_acg as ga
    import ar_routing
    import ar_generate
    import ar_render

    # --- stage 5: locate ------------------------------------------------------
    t0 = time.monotonic()
    place, absence = al.resolve_place(request.get("city"), request.get("lat"),
                                      request.get("lon"))
    b = request["birth"]
    if place is None:
        loc, reloc = al.absent_locate({"query": request.get("city")}, absence["reason"],
                                      absence.get("detail")), None
    else:
        loc, reloc = al.build_locate(acg, natal, place,
                                     natal_latlon=(b["latitude"], b["longitude"]),
                                     chart_filename=f"chart_relocated_{_date(b)}.json",
                                     parans=prod.get("parans"))
    manifest["place"] = (None if place is None else
                         {"name": place["name"], "name_tr": place["name_tr"],
                          "source": place["source"], "lat": place["lat"], "lon": place["lon"]})
    stages.record("locate", "ok" if loc["status"] == "ok"
                  else f"absent:{loc['absence']['reason']}", None, t0)
    if loc["status"] != "ok":
        for later in ("relocate", "ground_acg", "reading"):
            stages.record(later, f"skipped:{loc['absence']['reason']}", None)
        write("locate.json", loc)
        return finish("absent")

    # --- stage 6: relocate ----------------------------------------------------
    rs = loc["relocation"]
    if reloc is not None:
        write("chart_relocated.json", reloc)
        stages.record("relocate", "ok", f"chart_relocated_{_date(b)}.json")
    else:
        stages.record("relocate", f"absent:{rs['absence']['reason']}", None)
        manifest["gaps"].append(f"relocation_absent:{rs['absence']['reason']}")

    # --- stage 7: grounding ---------------------------------------------------
    t0 = time.monotonic()
    ok, _ = ga.corpus_ok()
    payload, drop_report = ga.ground_acg(
        natal, reloc, loc, ga.load_json(ga.ACG_CORPUS_PATH) if ok else None,
        ga.load_json(ga.MAIN_CORPUS_PATH), acg=acg, affinity=aff, parans=prod.get("parans"))
    loc["lines_display"] = payload.get("lines_display", [])
    write("locate.json", loc)
    write("acg_principles.json", payload)
    write("acg_drop_report.json", drop_report)
    stages.record("ground_acg", payload["status"] if payload["status"] == "ok"
                  else f"absent:{payload['absence']['reason']}", None, t0)
    manifest["counts"] = {"lines_near_read": sum(1 for ln in loc["lines_near"]
                                                 if ln["read_in_v1"]),
                          "selection_rule": payload["selection"]["rule"], **payload["counts"]}
    manifest["gaps"] += [g for g in payload.get("gaps", []) if g not in manifest["gaps"]]
    if payload["status"] != "ok":
        stages.record("reading", f"skipped:{payload['absence']['reason']}", None)
        return finish("absent")

    # --- stage 8: reading -----------------------------------------------------
    plan = ar_routing.build_plan(payload, focus_goal=request.get("focus_goal"))
    if dry_run:
        write("dry_run_prompts.json", ar_generate.dry_run_prompts(plan))
        stages.record("reading", "dry_run", None)
        return finish("ok")

    place_id = place.get("query") or f"{place['lat']:.4f},{place['lon']:.4f}"
    rkey = _sha({"chart": prod["key"], "place": [place["name"], place["lat"], place["lon"]],
                 "focus": request.get("focus_goal"), "models": manifest["models"],
                 "plan": _sha(plan), "code": _reading_code_version()})[:24]
    rdir = os.path.join(cache_root, prod["key"], "readings", rkey)
    t0 = time.monotonic()
    if os.path.exists(os.path.join(rdir, "reading_tr.json")):
        tr_doc = _read_json(os.path.join(rdir, "reading_tr.json"))
        en_doc = _read_json(os.path.join(rdir, "reading_en.json"))
        report = _read_json(os.path.join(rdir, "validation_report.json"))
        hit = True
    else:
        hit = False
        gen = make_generator(models)
        allowed = {r["principle_id"] for r in ga.load_json(ga.ACG_CORPUS_PATH)}
        allowed |= set(ar_routing.traced_ids(plan))
        try:
            reading, errors = ar_generate.generate(plan, gen, allowed)
        except Exception as err:  # noqa: BLE001 — a model failure is a failed stage
            stages.record("reading", "failed", None, t0, error=str(err)[:500])
            return finish("failed")
        report = {"errors": errors, "passed": not errors, "usage": gen.usage,
                  "fallbacks": gen.fallbacks, "place_id": place_id}
        tr_doc = ar_render.reading_json(reading, plan, "tr")
        en_doc = ar_render.reading_json(reading, plan, "en")
        if errors:
            write("reading.rejected.json", {"tr": tr_doc, "en": en_doc, "errors": errors})
            write("validation_report.json", report)
            stages.record("reading", "failed", None, t0, cache_hit=False,
                          error="; ".join(errors[:6]))
            return finish("failed")
        os.makedirs(rdir, exist_ok=True)
        for n, obj in (("reading_tr.json", tr_doc), ("reading_en.json", en_doc),
                       ("validation_report.json", report)):
            _write_json(os.path.join(rdir, n), obj)
    write("reading_tr.json", tr_doc)
    write("reading_en.json", en_doc)
    write("reading.md", None, raw=ar_render.reading_markdown(tr_doc, en_doc))
    write("validation_report.json", report)
    stages.record("reading", "ok", "reading_tr.json", t0, cache_hit=hit)
    return finish("ok")


def _reading_code_version() -> str:
    """Hash of the reading layer's source: a prompt or validator change invalidates
    cached readings."""
    h = hashlib.sha256()
    rdir = os.path.join(ENGINE_ROOT, "acg_reading")
    for name in sorted(os.listdir(rdir)):
        if name.startswith("ar_") and name.endswith(".py"):
            with open(os.path.join(rdir, name), "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()[:16]


def _date(b: dict) -> str:
    return f"{int(b['year']):04d}-{int(b['month']):02d}-{int(b['day']):02d}"


# ===========================================================================
# CLI
# ===========================================================================

def _birth_from_args(args) -> dict:
    import run_predictive
    if args.date and args.location:
        y, m, d = (int(x) for x in args.date.split("-"))
        hh, mm = (int(x) for x in (args.time or "12:00").split(":"))
        geo = run_predictive.geocode(args.location)
        return {"year": y, "month": m, "day": d, "hour": hh, "minute": mm,
                "latitude": geo["latitude"], "longitude": geo["longitude"],
                "location": args.location,
                "time_precision": "exact" if args.time else args.precision,
                "approx_bucket": args.approx_bucket}
    inp = run.collect_input()
    geo = run.geocode(inp["place_query"])
    return {"year": inp["year"], "month": inp["month"], "day": inp["day"],
            "hour": inp["hour"], "minute": inp["minute"], "latitude": geo["latitude"],
            "longitude": geo["longitude"], "location": inp["place_query"],
            "time_precision": "exact"}


def main(argv: Optional[list[str]] = None) -> int:
    import acg_constants as C
    ap = argparse.ArgumentParser(description="Astrocartography pipeline (ACG specs 05, 07–09).")
    ap.add_argument("--date", help="birth date YYYY-MM-DD")
    ap.add_argument("--time", help="birth time HH:MM (24h, local)")
    ap.add_argument("--location", help="birth place (geocoded)")
    ap.add_argument("--precision", choices=["exact", "approximate", "unknown"], default="exact")
    ap.add_argument("--approx-bucket", help="bucket for --precision approximate (compute_chart)")
    ap.add_argument("--city", help="place to read (gazetteer, then geocoder)")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--country", help="ISO-2 country code (country view)")
    ap.add_argument("--region", help="Natural Earth admin-1 id (region view)")
    ap.add_argument("--recommend", choices=list(C.GOAL_ORDER) + ["overall"],
                    help="Where Should I Go? goal, or 'overall' (all 11 goals together)")
    ap.add_argument("--scope", default="world", help="world | TR | <ISO-2>")
    ap.add_argument("--query-text", help="free text for the recommender (mapped to a goal)")
    ap.add_argument("--focus-goal", choices=list(C.GOAL_ORDER))
    # spec 11 §8: recommender filters (omitted = the defaults of spec 11 §4)
    ap.add_argument("--regions", help="comma list, e.g. europe,turkey (default: all)")
    ap.add_argument("--city-size", help="comma list of big,mid,small (default: big,mid)")
    ap.add_argument("--max-distance-km", type=float, help="max distance from --home-city")
    ap.add_argument("--home-city", help="current home (default: the birthplace)")
    ap.add_argument("--climate", help="comma list of warm,mild,cold (default: not applied)")
    ap.add_argument("--purpose", choices=["living", "travel", "both"],
                    help="default: derived from the goal")
    ap.add_argument("--include-unreviewed", action="store_true",
                    help="DEV ONLY: also recommend destinations not yet reviewed "
                         "(flagged in the output)")
    ap.add_argument("--scan-only", action="store_true", help="map mode even with a place")
    ap.add_argument("--dry-run", action="store_true", help="no model calls")
    ap.add_argument("--model")
    ap.add_argument("--synthesis-model")
    ap.add_argument("--translation-model")
    args = ap.parse_args(argv)
    if (args.lat is None) != (args.lon is None):
        ap.error("--lat and --lon go together")

    birth = _birth_from_args(args)
    city = args.city
    if not any([args.city, args.lat is not None, args.country, args.region, args.recommend,
                args.query_text]) and not (args.date and args.location):
        city = run._prompt("Şehir (boş bırak = yalnızca harita) / City (blank = map only): ") or None
    split = lambda v: [x.strip() for x in v.split(",") if x.strip()] if v else None  # noqa: E731
    home_latlon = None
    if args.home_city:
        import acg_locate as al
        hp, ab = al.resolve_place(args.home_city)
        if hp is None:
            print(f"Home city not found: {args.home_city} ({ab})", file=sys.stderr)
            return 1
        home_latlon = (hp["lat"], hp["lon"])
    request = {"birth": birth, "city": city, "lat": args.lat, "lon": args.lon,
               "country": args.country, "region": args.region, "recommend": args.recommend,
               "scope": args.scope, "query_text": args.query_text,
               "focus_goal": args.focus_goal, "home_latlon": home_latlon,
               "include_unreviewed": args.include_unreviewed,
               "filters": {"regions": split(args.regions), "city_size": split(args.city_size),
                           "max_distance_km": args.max_distance_km,
                           "climate": split(args.climate), "purpose": args.purpose}}
    needs_model = not (args.dry_run or args.scan_only) and any(
        [city, args.lat is not None, args.country, args.region, args.recommend, args.query_text])
    models = None
    if needs_model:
        models = resolve_models(args)
        if models["missing"]:
            print(models["missing"], file=sys.stderr)
            return 1
    m = run_acg(request, dry_run=args.dry_run, scan_only=args.scan_only, models=models)
    print("\n" + "=" * 70)
    print(f"ACG {m['mode']} run {m['status'].upper()} — {m['run_dir']}")
    for s in m["stages"]:
        hit = " (cache)" if s.get("cache_hit") else ""
        err = f"  {s['error'][:160]}" if s.get("error") else ""
        print(f"  {s['name']:<14} {s['status']}{hit}{err}")
    print("=" * 70)
    return 0 if m["status"] in ("ok", "absent") else 1


if __name__ == "__main__":
    raise SystemExit(main())
