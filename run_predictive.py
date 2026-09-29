#!/usr/bin/env python3
"""run_predictive.py — top-level orchestrator of the predictive pipeline
(PREDICTIVE_ORCHESTRATION_SPEC.md).

Turns one request into a persisted run: resolve input -> natal chart -> forecast
-> grounding -> reading(s), owning the run folder and the run manifest. Mirrors
the natal run.py contract: compute stays pure, the orchestrator owns all I/O and
sequencing and never interprets or computes astrology itself.

The profile/horizon asymmetry (spec §1) drives batching:
  * profile is a READ-TIME lens — stages 1-3 are profile-agnostic, so a
    multi-profile request runs 1-3 once and loops stage 4 over profiles.
  * horizon changes the event window — stages 2-3 are horizon-specific, so a
    multi-horizon request re-runs 2-3 per horizon (stage 1 natal stays shared).

Stages 0-3 and 5 are deterministic; stage 4 (reading) is an LLM call and needs
ANTHROPIC_API_KEY. `--dry-run` executes the deterministic spine and stops before
any reading.

    python run_predictive.py                       # interactive: prompts for inputs
    python run_predictive.py --location "Istanbul, TR" --date 1990-06-15 \
        --time 14:30 --precision exact --target today --horizon month --profile personal
    python run_predictive.py ... --horizon month --profiles general,personal,professional
    python run_predictive.py --request request.json [--dry-run]

With no --request and no --location/--date, it asks for and collects inputs
interactively (birth date / time / place, then target / horizon / profile) —
the same flow as the natal (run.py) and synastry (synastry_run.py) orchestrators.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import string
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Each layer computes paths relative to its own __file__ and imports siblings by
# bare name; put every stage's dir on sys.path before importing them.
for _d in ("d_layer", "principles_grounding", "Forecast_compute", "prediction_reading"):
    _p = os.path.join(REPO_ROOT, _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Reuse the natal orchestrator's building blocks (identical contracts): the JSON
# writer, the validated birth-data prompt, the raw prompt helper, and the
# birth-date filename-suffix rule.
import run  # noqa: E402
from run import (  # noqa: E402
    _write_json, collect_input, suffixed, render_chart_wheels, WheelError,
)

# The merged corpus the predictive grounding runs against (spec §6). Named with a
# dot, not the underscore the manifest example uses — this is the real file.
CORPUS_PATH = os.path.join(REPO_ROOT, "principles_grounding",
                           "all_principles_grounded.with_predictive.json")
# Predictive runs get their own folder (like synastry_run/), one subfolder per run.
PRED_RUNS_DIR = os.path.join(REPO_ROOT, "prediction_run")
GEOCODE_CACHE = os.path.join(REPO_ROOT, ".cache", "geocode.json")

HORIZONS = ("day", "month", "year")
PROFILES = ("general", "personal", "professional")
# How much astrological reasoning the reading text names (see pr_prompts / read_forecast).
ASTRO_DETAILS = ("plain", "modern", "technical")
DEFAULT_ASTRO_DETAIL = "modern"

# Grounding params (spec §6 params.grounding). Stage-2 embeddings are not wired
# (no retriever), so grounding is structural-only for now.
GROUND_CAP = 6
GROUND_SIM_FLOOR = 0.35
GROUND_STAGE2 = False

# Degradation: a run whose grounded material is thin is marked degraded rather
# than shipping a starved reading as if the period were genuinely quiet (spec §5).
# "events_with_zero_matches above a threshold" -> fraction of the event set with
# no grounded principle at all.
ZERO_MATCH_DEGRADE_RATIO = 0.5


# ===========================================================================
# Result type
# ===========================================================================

@dataclass
class RunResult:
    run_id: str
    run_dir: str
    status: str                       # "ok" | "degraded" | "failed"
    manifest: dict = field(default_factory=dict)
    readings: list[str] = field(default_factory=list)   # shipped reading paths
    errors: list[str] = field(default_factory=list)


class StageError(RuntimeError):
    """A deterministic stage failed; carries the stage name for the manifest."""
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


# ===========================================================================
# Stage 0 — resolve input (geocode + validate + target date)
# ===========================================================================

def _load_geocode_cache() -> dict:
    try:
        with open(GEOCODE_CACHE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_geocode_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(GEOCODE_CACHE), exist_ok=True)
    with open(GEOCODE_CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, ensure_ascii=False, indent=2)


def geocode(location: str) -> dict:
    """location string -> {latitude, longitude, display_name}. Non-interactive
    (this is a batch/CLI orchestrator). Cached by location string, since it is a
    network call and not deterministic (spec §2). Raises StageError on no match —
    never proceeds coordinate-less."""
    key = location.strip().lower()
    cache = _load_geocode_cache()
    if key in cache:
        return cache[key]

    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderServiceError, GeocoderTimedOut
    geolocator = Nominatim(user_agent=run.GEOCODER_USER_AGENT, timeout=15)
    try:
        loc = geolocator.geocode(location, addressdetails=False)
    except (GeocoderServiceError, GeocoderTimedOut) as err:
        raise StageError("resolve", f"geocoding service error for {location!r}: {err}")
    if loc is None:
        raise StageError("resolve", f"no location found for {location!r}")

    resolved = {"latitude": round(float(loc.latitude), 4),
                "longitude": round(float(loc.longitude), 4),
                "display_name": loc.address}
    cache[key] = resolved
    _save_geocode_cache(cache)
    return resolved


def resolve_input(request: dict) -> dict:
    """Validate the request, geocode the birth location, and normalize horizons /
    profiles into lists. Returns the resolved request (coords included) that is
    persisted verbatim as input.json."""
    birth = request.get("birth") or {}
    for f in ("year", "month", "day"):
        if not isinstance(birth.get(f), int):
            raise StageError("resolve", f"birth.{f} missing or not an int")
    precision = birth.get("time_precision", "exact")
    if precision not in ("exact", "approximate", "unknown"):
        raise StageError("resolve", f"bad time_precision {precision!r}")
    if precision == "exact":
        for f in ("hour", "minute"):
            if not isinstance(birth.get(f), int):
                raise StageError("resolve", f"birth.{f} required for exact precision")
    location = birth.get("location")
    if not location or not str(location).strip():
        raise StageError("resolve", "birth.location is required")

    horizons = request.get("horizons") or ([request["horizon"]] if request.get("horizon")
                                            else ["month"])
    profiles = request.get("profiles") or ([request["profile"]] if request.get("profile")
                                           else ["general"])
    for h in horizons:
        if h not in HORIZONS:
            raise StageError("resolve", f"bad horizon {h!r}; expected one of {HORIZONS}")
    for p in profiles:
        if p not in PROFILES:
            raise StageError("resolve", f"bad profile {p!r}; expected one of {PROFILES}")

    geo = geocode(str(location))
    # CAL_00 §6 / D1: optional current location. It anchors the DAY/MONTH/YEAR window
    # in that tz; the natal chart (houses) stays on the birth coordinates.
    cur = request.get("current_location")
    cur_geo = ({"query": cur, "provider": "nominatim", **geocode(str(cur))}
               if cur and str(cur).strip() else None)
    config = request.get("config") or {}
    astro_detail = config.get("astro_detail", DEFAULT_ASTRO_DETAIL)
    if astro_detail not in ASTRO_DETAILS:
        raise StageError("resolve",
                         f"bad astro_detail {astro_detail!r}; expected one of {ASTRO_DETAILS}")
    return {
        "birth": {
            "year": birth["year"], "month": birth["month"], "day": birth["day"],
            "hour": birth.get("hour", 12), "minute": birth.get("minute", 0),
            "location": location, "time_precision": precision,
        },
        "geocode": {"provider": "nominatim", **geo},
        "current_location": cur_geo,
        "target_date": request.get("target_date"),      # may be null -> resolved at stage 1
        "horizons": list(horizons),
        "profiles": list(profiles),
        "config": {
            "enable_profections": bool(config.get("enable_profections", False)),
            "enable_lots_targets": bool(config.get("enable_lots_targets", False)),
            "surface_planets": bool(config.get("surface_planets", True)),
            "astro_detail": astro_detail,
            "calendar": bool(config.get("calendar", True)),
        },
    }


# ===========================================================================
# Corpus + hashing helpers
# ===========================================================================

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _load_corpus() -> tuple[list[dict], dict]:
    with open(CORPUS_PATH, encoding="utf-8") as fh:
        raw = json.load(fh)
    records = raw if isinstance(raw, list) else next(
        v for v in raw.values() if isinstance(v, list))
    version = {"file": os.path.basename(CORPUS_PATH),
               "record_count": len(records), "hash": _sha256_file(CORPUS_PATH)}
    return records, version


def _mint_run_id(now_utc: datetime) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=3))
    return now_utc.strftime("%Y%m%d-%H%M%S") + "_" + suffix


def _resolve_target(raw, tzname: str) -> str:
    """null / "today" -> today's date in the birth-location timezone (spec §2)."""
    if raw and str(raw).lower() != "today":
        return str(raw)
    return datetime.now(ZoneInfo(tzname)).date().isoformat()


# ===========================================================================
# Readable text + English translation of a reading
#
# The predictive reading layer authors Turkish only (no text_tr/text_en split,
# no renderer) — unlike the natal/synastry layers. So the orchestrator renders
# the reading JSON to a .txt and produces the English version itself.
# ===========================================================================

def _heading(key: str) -> str:
    from pr_events import SEGMENT_LABEL
    base = {"reading": "The day ahead", "overview": "Overview",
            "focus": "Focus"}.get(key) or SEGMENT_LABEL.get(key, key)
    return base.upper()


def _render_reading_text(reading: dict) -> str:
    """Flatten a reading dict (keyed by the horizon's section keys) into readable
    text with headings, in the reading's own section order."""
    from pr_events import HORIZON_KEYS
    horizon = (reading.get("meta") or {}).get("horizon", "")
    lines: list[str] = []
    for key in HORIZON_KEYS.get(horizon, []):
        body = (reading.get(key) or "").strip()
        if not body:
            continue
        lines += [_heading(key), "", body, ""]
    return "\n".join(lines).strip() + "\n"


def _lenient_json(text: str) -> dict:
    import re
    text = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        a, b = text.find("{"), text.rfind("}")
        if a != -1 and b > a:
            return json.loads(text[a:b + 1], strict=False)
        raise


def translate_reading(reading: dict, model: str,
                      fallback_model: str | None = None) -> dict:
    """Faithful English translation of a Turkish reading (one model call).
    Returns an English reading dict with the same section keys. Raises on any
    failure — the caller treats English as best-effort and keeps the Turkish.
    ``model`` is normally the cheap translation model; if it is unavailable
    (no credits, exhausted retries) the call is retried once on ``fallback_model``."""
    from pr_events import HORIZON_KEYS
    import llm_client

    horizon = (reading.get("meta") or {}).get("horizon", "")
    keys = [k for k in HORIZON_KEYS.get(horizon, []) if (reading.get(k) or "").strip()]
    if not keys:
        raise ValueError("reading has no section text to translate")
    src = {k: reading[k] for k in keys}

    system = (
        "You are a professional translator. Translate the given Turkish "
        "astrological forecast sections into natural, warm English. Translate "
        "faithfully — do not add, drop, or reinterpret content, keep the same "
        "sections. Return JSON ONLY (no prose, no code fences) with exactly the "
        "same keys as the input, each mapping to its English translation."
    )
    try:
        resp = llm_client.complete(
            model, system, json.dumps(src, ensure_ascii=False),
            max_tokens=8192, timeout_s=120.0, label="translate")
    except (llm_client.ProviderQuotaError, RuntimeError) as err:
        if not fallback_model or fallback_model == model:
            raise
        print(f"    translation failed on {model} ({type(err).__name__}); "
              f"falling back to {fallback_model}")
        resp = llm_client.complete(
            fallback_model, system, json.dumps(src, ensure_ascii=False),
            max_tokens=8192, timeout_s=120.0, label="translate/fallback")
    text = resp.text
    data = _lenient_json(text)
    en_sections = {k: (data.get(k) or "").strip() for k in keys}
    return {**en_sections,
            "meta": {**(reading.get("meta") or {}), "language": "en"}}


# ===========================================================================
# The orchestrator
# ===========================================================================

def run_predictive(request: dict, *, dry_run: bool = False,
                   model: str | None = None,
                   synthesis_model: str | None = None,
                   translation_model: str | None = None,
                   **gen_kwargs) -> RunResult:
    """Resolve -> natal -> (forecast -> grounding)×horizon -> reading×(horizon,profile)
    -> manifest. Owns the run folder and every artifact. On a deterministic stage
    raising, records the failure, keeps completed artifacts, and stops (no reading
    ships)."""
    now_utc = datetime.now(timezone.utc)
    run_id = _mint_run_id(now_utc)
    run_dir = os.path.join(PRED_RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    # Every artifact is suffixed with the birth date (same rule as run.py /
    # synastry_run.py), so a file pulled out of its folder is never confused with
    # another person's. Computed from the raw request so even an early-failure
    # manifest is named correctly.
    _b = request.get("birth") or {}
    try:
        suffix = f"{int(_b['year']):04d}-{int(_b['month']):02d}-{int(_b['day']):02d}"
    except (KeyError, TypeError, ValueError):
        suffix = "unknown"

    stages: list[dict] = []
    outputs = {"horizons": [], "profiles": [], "readings": []}
    params: dict = {
        "grounding": {"cap": GROUND_CAP, "similarity_floor": GROUND_SIM_FLOOR,
                      "stage2_enabled": GROUND_STAGE2,
                      "zero_match_degrade_ratio": ZERO_MATCH_DEGRADE_RATIO},
        "reading": {},
        "config": {},
    }
    manifest: dict = {
        "run_id": run_id, "status": "failed",
        "created_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "request_hash": None, "natal_ref": None, "corpus_version": None,
        "stages": stages, "params": params, "outputs": outputs,
    }
    result = RunResult(run_id=run_id, run_dir=run_dir, status="failed",
                       manifest=manifest)

    def record(name, status, artifact=None, dt=None, error=None):
        stages.append({"name": name, "status": status, "artifact": artifact,
                       "duration_ms": None if dt is None else round(dt * 1000, 1),
                       "error": error})

    def finish(status: str) -> RunResult:
        manifest["status"] = status
        result.status = status
        _write_json(os.path.join(run_dir, suffixed("run_manifest.json", suffix)), manifest)
        return result

    degraded = False

    try:
        # --- Stage 0: resolve input -> input.json ---
        t0 = time.monotonic()
        resolved = resolve_input(request)
        params["config"] = dict(resolved["config"])
        input_name = suffixed("input.json", suffix)
        _write_json(os.path.join(run_dir, input_name), resolved)
        manifest["request_hash"] = "sha256:" + hashlib.sha256(
            json.dumps(resolved, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:16]
        record("resolve", "ok", input_name, time.monotonic() - t0)
        outputs["horizons"] = list(resolved["horizons"])
        outputs["profiles"] = list(resolved["profiles"])
        print(f"run_id = {run_id}  ->  {run_dir}")
        print(f"[0] resolved: {resolved['geocode']['display_name']} "
              f"({resolved['geocode']['latitude']}, {resolved['geocode']['longitude']})")

        lat = resolved["geocode"]["latitude"]
        lon = resolved["geocode"]["longitude"]
        cfg = resolved["config"]

        # --- Stage 1: natal chart (once, shared) -> natal_chart.json ---
        from compute_chart import compute_chart, BirthData
        t0 = time.monotonic()
        try:
            natal = compute_chart(BirthData(
                year=resolved["birth"]["year"], month=resolved["birth"]["month"],
                day=resolved["birth"]["day"], hour=resolved["birth"]["hour"],
                minute=resolved["birth"]["minute"], latitude=lat, longitude=lon,
                time_precision=resolved["birth"]["time_precision"]))
        except Exception as err:  # noqa: BLE001 — surface any compute failure as a stage error
            raise StageError("natal", str(err))
        natal_name = suffixed("natal_chart.json", suffix)
        _write_json(os.path.join(run_dir, natal_name), natal)
        record("natal", "ok", natal_name, time.monotonic() - t0)
        tzname = (natal.get("meta") or {}).get("timezone") or "UTC"
        cur_geo = resolved.get("current_location")
        if cur_geo:
            from compute_chart import resolve_timezone
            tzname = resolve_timezone(cur_geo["latitude"], cur_geo["longitude"])
            resolved["current_location"]["timezone"] = tzname
            lat_day, lon_day = cur_geo["latitude"], cur_geo["longitude"]
        else:
            lat_day, lon_day = lat, lon
        target = _resolve_target(resolved["target_date"], tzname)
        resolved["target_date"] = target                    # persist the resolved date
        _write_json(os.path.join(run_dir, input_name), resolved)
        from compute_forecast import _natal_ref
        manifest["natal_ref"] = _natal_ref(natal)           # == forecast.meta.natal_ref
        print(f"[1] natal computed (tz={tzname}); target_date={target}")

        # --- Stage 1b: natal chart wheel SVGs (deterministic; offline) ---
        t0 = time.monotonic()
        try:
            wheels = render_chart_wheels(os.path.join(run_dir, natal_name),
                                         run_dir, suffix)
        except WheelError as err:
            raise StageError("wheel", str(err))
        for wp in wheels:
            record("wheel", "ok", os.path.basename(wp), time.monotonic() - t0)
        print(f"[1b] wheels -> {', '.join(os.path.basename(w) for w in wheels)}")

        # --- corpus (loaded once; hashed for the manifest) ---
        records, corpus_version = _load_corpus()
        manifest["corpus_version"] = corpus_version

        from compute_forecast import compute_forecast, ForecastConfig
        from ground_forecast import ground_forecast
        fconfig = ForecastConfig(enable_profections=cfg["enable_profections"],
                                 enable_lots_targets=cfg["enable_lots_targets"])

        # Inject deterministic now/run_id into compute_forecast so the forecast is
        # a pure function of the resolved request (spec §8 / invariant 8: two runs
        # of one request produce byte-identical stage 1-3 artifacts). The module
        # documents these as its only non-deterministic fields; target is explicit
        # so `now` never touches the event window. Real wall-clock provenance lives
        # in the manifest's created_at, and the folder run_id stays unique per run.
        det_now = datetime.fromisoformat(target).replace(tzinfo=timezone.utc)
        forecast_run_id = manifest["request_hash"].replace("sha256:", "req-")

        # --- Stages 2-3: forecast + grounding, once per horizon ---
        grounded_by_horizon: dict[str, dict] = {}
        for horizon in resolved["horizons"]:
            t0 = time.monotonic()
            try:
                forecast = compute_forecast(natal, target, horizon,
                                            latitude=lat_day, longitude=lon_day,
                                            config=fconfig, now=det_now,
                                            run_id=forecast_run_id,
                                            window_tz=tzname)
            except Exception as err:  # noqa: BLE001
                raise StageError(f"forecast:{horizon}", str(err))
            fc_name = suffixed(f"forecast_{horizon}.json", suffix)
            _write_json(os.path.join(run_dir, fc_name), forecast)
            record(f"forecast:{horizon}", "ok", fc_name, time.monotonic() - t0)

            t0 = time.monotonic()
            try:
                gr = ground_forecast(forecast, natal, records,
                                     cap=GROUND_CAP, sim_floor=GROUND_SIM_FLOOR)
            except Exception as err:  # noqa: BLE001
                raise StageError(f"grounding:{horizon}", str(err))
            g_name = suffixed(f"forecast_grounded_{horizon}.json", suffix)
            r_name = suffixed(f"grounding_report_{horizon}.json", suffix)
            report = gr.report()
            _write_json(os.path.join(run_dir, g_name), gr.forecast)
            _write_json(os.path.join(run_dir, r_name), report)
            record(f"grounding:{horizon}", "ok", g_name, time.monotonic() - t0)
            grounded_by_horizon[horizon] = gr.forecast

            # degradation signals (spec §5): forecast degraded, or recall-thin.
            events_total = report["events_total"] or 1
            zero_ratio = len(report["events_with_zero_matches"]) / events_total
            if forecast["meta"].get("degraded"):
                degraded = True
            if zero_ratio >= ZERO_MATCH_DEGRADE_RATIO:
                degraded = True
            print(f"[2-3] {horizon}: {events_total} events, "
                  f"{report['events_with_matches']} matched, "
                  f"{len(report['events_with_zero_matches'])} zero "
                  f"(ratio {zero_ratio:.2f}), kept {report['kept_total']}")

        # --- Stage 3b: calendar context (the same calendar the app shows; see
        # prediction_reading/pr_calendar.py). Built once for 12 months from the target,
        # then sliced per horizon window and beat.
        calendar_by_horizon: dict[str, dict] = {}
        if cfg.get("calendar", True):
            t0 = time.monotonic()
            try:
                import pr_calendar
                cal = pr_calendar.build(natal, tzname, datetime.fromisoformat(target).date())
                for horizon in resolved["horizons"]:
                    ctx = pr_calendar.for_forecast(cal, grounded_by_horizon[horizon])
                    calendar_by_horizon[horizon] = ctx
                    c_name = suffixed(f"calendar_context_{horizon}.json", suffix)
                    _write_json(os.path.join(run_dir, c_name), ctx)
                    record(f"calendar:{horizon}", "ok", c_name, time.monotonic() - t0)
                print(f"[3b] calendar context for {', '.join(calendar_by_horizon)}")
            except Exception as err:  # noqa: BLE001 — the reading still works without it
                record("calendar", "failed", error=str(err))
                print(f"[3b] calendar context unavailable ({err}); reading without it")

        # --- dry run stops before the reading (spec §9) ---
        if dry_run:
            print("[dry-run] deterministic spine complete; no reading.")
            return finish("degraded" if degraded else "ok")

        # --- Stage 4: reading, once per (horizon, profile) ---
        from read_forecast import run_reading
        from pr_generate import DEFAULT_MODEL, DEFAULT_TEMPERATURE
        resolved_model = model or DEFAULT_MODEL
        import llm_client
        # English translation runs on the cheap model by default (falls back to
        # the reading model if that provider is unavailable).
        resolved_translation = (resolved_model if translation_model == "same"
                                else translation_model or llm_client.DEFAULT_CHEAP_MODEL)
        _missing = llm_client.missing_key_message(
            [resolved_model, synthesis_model or resolved_model, resolved_translation],
            "the reading stage (use --dry-run to skip)")
        if _missing:
            raise StageError("reading", _missing)
        # temperature is only sent to models that still accept it (Sonnet 5 / Opus 4.7+
        # reject it); recorded here for provenance regardless.
        params["reading"] = {"model": resolved_model, "temperature": DEFAULT_TEMPERATURE,
                             "translation_model": resolved_translation,
                             "surface_planets": cfg["surface_planets"],
                             "astro_detail": cfg["astro_detail"]}

        any_shipped = False
        any_rejected = False
        for horizon in resolved["horizons"]:
            grounded = grounded_by_horizon[horizon]
            for profile in resolved["profiles"]:
                t0 = time.monotonic()
                print(f"[4] reading {horizon}/{profile} (model call)...")
                try:
                    reading, errors, rep = run_reading(
                        grounded, reading_type=profile, model=resolved_model,
                        synthesis_model=synthesis_model,
                        surface_planets=cfg["surface_planets"],
                        astro_detail=cfg["astro_detail"],
                        calendar=calendar_by_horizon.get(horizon), **gen_kwargs)
                except Exception as err:  # noqa: BLE001
                    raise StageError(f"reading:{horizon}/{profile}", str(err))

                base = f"reading_{horizon}_{profile}_{target}"
                if rep.get("build_blocking"):
                    # §5: could not pass validation after re-ask — do NOT ship.
                    rej = suffixed(f"{base}.rejected.json", suffix)
                    _write_json(os.path.join(run_dir, rej),
                                {"reading": reading, "errors": errors, "report": rep})
                    record(f"reading:{horizon}/{profile}", "failed", rej,
                           time.monotonic() - t0, error="; ".join(errors[:8]))
                    any_rejected = True
                    result.errors.extend(errors)
                    print(f"    REJECTED ({len(errors)} contract error(s)) -> {rej}")
                    continue

                out = suffixed(f"{base}.json", suffix)
                _write_json(os.path.join(run_dir, out), reading)
                record(f"reading:{horizon}/{profile}", "ok", out, time.monotonic() - t0)
                outputs["readings"].append(out)
                result.readings.append(os.path.join(run_dir, out))
                any_shipped = True
                if (reading.get("meta") or {}).get("sparse"):
                    degraded = True
                if errors:                                  # non-blocking caveats
                    result.errors.extend(errors)

                # Readable Turkish text (the reading is authored in Turkish).
                tr_txt = suffixed(f"{base}.tr.txt", suffix)
                with open(os.path.join(run_dir, tr_txt), "w", encoding="utf-8") as fh:
                    fh.write(_render_reading_text(reading))
                outputs["readings"].append(tr_txt)

                # English version (best-effort: the reading layer authors Turkish
                # only, so the orchestrator translates. A failure never sinks the
                # run — the Turkish reading has already shipped).
                en_note = ""
                try:
                    en_reading = translate_reading(reading, resolved_translation,
                                                   fallback_model=resolved_model)
                    en_json = suffixed(f"{base}.en.json", suffix)
                    en_txt = suffixed(f"{base}.en.txt", suffix)
                    _write_json(os.path.join(run_dir, en_json), en_reading)
                    with open(os.path.join(run_dir, en_txt), "w", encoding="utf-8") as fh:
                        fh.write(_render_reading_text(en_reading))
                    outputs["readings"] += [en_json, en_txt]
                    en_note = f", {en_txt}"
                except Exception as err:  # noqa: BLE001 — English is best-effort
                    print(f"    (english translation skipped: {err})", file=sys.stderr)

                print(f"    shipped -> {out}, {tr_txt}{en_note}"
                      + ("  [sparse]" if (reading.get('meta') or {}).get('sparse') else ""))

        # A reading that failed validation is a run failure (spec §5). Shipped
        # readings from other profiles remain on disk and are listed in outputs.
        if any_rejected:
            return finish("failed")
        if not any_shipped:
            return finish("failed")
        return finish("degraded" if degraded else "ok")

    except StageError as err:
        record(err.stage, "failed", None, None, error=str(err))
        result.errors.append(f"{err.stage}: {err}")
        print(f"\n[FAILED] stage {err.stage}: {err}", file=sys.stderr)
        return finish("failed")


# ===========================================================================
# CLI
# ===========================================================================

def _prompt_target() -> str | None:
    """Forecast target date (blank = today in the birth-location tz)."""
    while True:
        raw = run._prompt("Forecast target date (YYYY-MM-DD, blank = today): ")
        if not raw:
            return None
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except ValueError:
            print("  Invalid date. Use YYYY-MM-DD, or leave blank for today.")


def _prompt_choice(title: str, options: list[tuple[str, str]], default: str) -> str:
    """Numbered menu (mirrors synastry_run's reading-type prompt). options is a
    list of (value, description); returns the chosen value, default on blank."""
    print(title)
    for i, (val, desc) in enumerate(options, 1):
        star = "  (default)" if val == default else ""
        print(f"  [{i}] {val:<13}— {desc}{star}")
    mapping = {str(i): val for i, (val, _) in enumerate(options, 1)}
    mapping[""] = default
    n = len(options)
    while True:
        choice = run._prompt(f"Choose [1-{n}] (default {default}): ").strip()
        if choice in mapping:
            return mapping[choice]
        print(f"  Enter 1-{n}, or leave blank for {default}.")


def _collect_request_interactive(args) -> dict:
    """Ask for and collect inputs interactively, like the natal / synastry
    orchestrators. Reuses run.collect_input for the validated birth date / time /
    place, then prompts the predictive-specific target / horizon / profile."""
    print("=== Predictive reading ===")
    inp = collect_input()                       # birth_date / birth_time_local / place_query (+ y/m/d/h/m)
    target = _prompt_target()
    horizon = _prompt_choice(
        "\nForecast horizon?",
        [("day", "the day ahead"), ("month", "the month ahead"),
         ("year", "the year ahead")], "month")
    profile = _prompt_choice(
        "\nReading focus?",
        [("general", "life as a whole"), ("personal", "romantic / personal life"),
         ("professional", "work / career")], "general")
    astro_detail = _prompt_choice(
        "\nAstrological detail in the text?",
        [("plain", "plain psychological language, no astrology jargon"),
         ("modern", "name planets, aspects, signs, transits, moon phases"),
         ("technical", "full detail incl. house numbers & classical terms")],
        DEFAULT_ASTRO_DETAIL)

    req: dict = {
        "birth": {"year": inp["year"], "month": inp["month"], "day": inp["day"],
                  "hour": inp["hour"], "minute": inp["minute"],
                  "location": inp["place_query"], "time_precision": "exact"},
        "target_date": target,
        "horizon": horizon,
        "profile": profile,
        # config flags stay on CLI (advanced); interactive asks only for astro detail.
        "config": {"enable_profections": args.enable_profections,
                   "enable_lots_targets": args.enable_lots_targets,
                   "surface_planets": not args.no_surface_planets,
                   "astro_detail": astro_detail},
    }
    return req


def _build_request_from_args(args) -> dict:
    if args.request:
        with open(args.request, encoding="utf-8") as fh:
            return json.load(fh)
    if args.date is None or args.location is None:
        raise SystemExit("need --location and --date (or --request request.json)")
    y, m, d = (int(x) for x in args.date.split("-"))
    hour = minute = None
    if args.time:
        hour, minute = (int(x) for x in args.time.split(":"))
    req: dict = {
        "birth": {"year": y, "month": m, "day": d, "location": args.location,
                  "time_precision": args.precision},
        "target_date": None if (args.target in (None, "today")) else args.target,
        "config": {"enable_profections": args.enable_profections,
                   "enable_lots_targets": args.enable_lots_targets,
                   "surface_planets": not args.no_surface_planets,
                   "astro_detail": args.astro_detail,
                   "calendar": not getattr(args, "no_calendar", False)},
    }
    if hour is not None:
        req["birth"]["hour"], req["birth"]["minute"] = hour, minute
    if getattr(args, "current_location", None):
        req["current_location"] = args.current_location
    if args.horizons:
        req["horizons"] = [h.strip() for h in args.horizons.split(",") if h.strip()]
    else:
        req["horizon"] = args.horizon
    if args.profiles:
        req["profiles"] = [p.strip() for p in args.profiles.split(",") if p.strip()]
    else:
        req["profile"] = args.profile
    return req


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Predictive pipeline orchestrator (spec).")
    ap.add_argument("--request", help="path to a full request.json (spec §2)")
    ap.add_argument("--location", help="birth location string (geocoded)")
    ap.add_argument("--date", help="birth date YYYY-MM-DD")
    ap.add_argument("--time", help="birth time HH:MM (24h); omit for non-exact")
    ap.add_argument("--precision", choices=["exact", "approximate", "unknown"],
                    default="exact")
    ap.add_argument("--target", default="today", help="forecast target date YYYY-MM-DD or 'today'")
    ap.add_argument("--no-calendar", action="store_true",
                    help="write the reading without the personal-calendar context")
    ap.add_argument("--current-location", default=None,
                    help="where the user is now: anchors the day/month/year window in its tz "
                         "(default: the birth location)")
    ap.add_argument("--horizon", choices=list(HORIZONS), default="month")
    ap.add_argument("--horizons", help="comma list for multi-horizon batching")
    ap.add_argument("--profile", choices=list(PROFILES), default="general")
    ap.add_argument("--profiles", help="comma list for multi-profile batching")
    ap.add_argument("--enable-profections", action="store_true")
    ap.add_argument("--enable-lots-targets", action="store_true")
    ap.add_argument("--no-surface-planets", action="store_true")
    ap.add_argument("--astro-detail", choices=list(ASTRO_DETAILS),
                    default=DEFAULT_ASTRO_DETAIL,
                    help="astrological detail in the reading text: plain | modern (default) | "
                         "technical")
    ap.add_argument("--model", default=None, help="reading model override")
    ap.add_argument("--synthesis-model", default=None)
    ap.add_argument("--translation-model", default=None,
                    help="English translation model (default: the cheap model, gpt-6-luna; "
                         "'same' = the reading model)")
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="stages 0-3 only; no reading, zero model calls")
    args = ap.parse_args(argv)

    if not os.path.exists(CORPUS_PATH):
        print(f"Missing predictive corpus: {CORPUS_PATH}", file=sys.stderr)
        return 1

    # Interactive when no request file and no birth flags were supplied — same as
    # the natal / synastry orchestrators. CLI flags remain for scripted/batch use.
    if args.request or (args.location and args.date):
        request = _build_request_from_args(args)
    else:
        request = _collect_request_interactive(args)
    gen_kwargs = {}
    if args.max_tokens is not None:
        gen_kwargs["max_tokens"] = args.max_tokens

    res = run_predictive(request, dry_run=args.dry_run, model=args.model,
                         synthesis_model=args.synthesis_model,
                         translation_model=args.translation_model, **gen_kwargs)

    print("\n" + "=" * 70)
    print(f"RUN {res.status.upper()} — {res.run_dir}")
    if res.readings:
        print("Readings shipped:")
        for p in res.readings:
            print(f"  - {os.path.basename(p)}")
    if res.errors:
        print(f"Errors/caveats: {len(res.errors)}")
    print(f"Manifest: run_manifest.json  (status={res.status})")
    print("=" * 70)
    return {"ok": 0, "degraded": 0, "failed": 1}[res.status]


if __name__ == "__main__":
    raise SystemExit(main())
