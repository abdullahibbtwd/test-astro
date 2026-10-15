#!/usr/bin/env python3
"""
read_forecast.py — the predictive reading orchestrator (PREDICTIVE_READING_SPEC).

Pipeline (the ONLY LLM stage in the predictive pipeline):

    grounded forecast object  (compute_forecast events + matched principle texts)
      -> profile emphasis + segment split          (deterministic — pr_events)
      -> per-beat calls in parallel + 1 synthesis   (§2 call graph — pr_generate)
      -> bounded per-section word-count re-ask       (§8)
      -> Tier-A/B mask + structure lint              (§11 — pr_validate); never ship a leak
      -> persist reading_{horizon}_{profile}_{target}.json into the forecast's run folder (§10)

Input contract: a "grounded forecast" is a ``compute_forecast()`` object whose every event
also carries ``matched_principles: [{principle_id, judgment, ...}]`` (attached by the
forecast-grounding step, which is a separate module). See pr_events.py for the full contract.

Run
---
    python read_forecast.py --input <grounded_forecast.json> --profile personal
    python read_forecast.py --input <grounded_forecast.json> --dry-run   # blocks, no model
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from pr_events import (
    BEAT_SEGMENTS, HORIZON_KEYS, SEGMENT_LABEL, WORD_TARGETS,
    events_block, grounded_event_count, is_sparse,
)
from pr_generate import DEFAULT_MODEL, make_generator
import pr_calendar
from pr_profiles import DEFAULT_READING_TYPE, READING_TYPES, get_profile
from pr_prompts import (
    build_beat_user, build_day_user, build_reask_user, build_synthesis_user,
    build_system_block,
)
from pr_validate import ValidationContext, bounds, is_build_blocking, validate, word_count

_HERE = os.path.dirname(os.path.abspath(__file__))
# Canonical planet names that may legitimately be surfaced (§5) when contacted.
_PLANET_NAMES = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter",
                 "Saturn", "Uranus", "Neptune", "Pluto"}


def _load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _words(horizon: str, key: str) -> str:
    lo, hi = WORD_TARGETS[horizon][key]
    return f"{lo}–{hi}"          # en-dash, matching the spec's "50–80" style


# ---------------------------------------------------------------------------
# Validation context derived from the forecast payload (§11.5 allow-lists).
# ---------------------------------------------------------------------------
def _build_ctx(forecast: dict, profile, horizon: str, *, surface_planets: bool,
               sparse: bool, astro_detail: str, calendar: dict | None = None) -> ValidationContext:
    allowed_planets: set[str] = set()
    if calendar:
        for sl in [calendar["window"], *calendar["segments"].values()]:
            allowed_planets |= pr_calendar.planets(sl)
    has_luminary_event = False
    for e in forecast.get("events", []):
        b = e.get("bodies") or {}
        for who in (b.get("transiting"), b.get("natal")):
            if who in _PLANET_NAMES:
                allowed_planets.add(who)
        if e.get("family") in ("lunation", "eclipse"):
            has_luminary_event = True
    if has_luminary_event:
        # New/full moon + eclipse are allowed sky hooks (§5), so their luminaries are fair.
        allowed_planets |= {"Moon", "Sun"}

    years: set[int] = set()
    for k in ("start", "end"):
        v = (forecast.get("window") or {}).get(k, "")
        if len(v) >= 4 and v[:4].isdigit():
            years.add(int(v[:4]))
    td = (forecast.get("meta") or {}).get("target_date", "")
    if len(td) >= 4 and td[:4].isdigit():
        years.add(int(td[:4]))

    return ValidationContext(
        horizon=horizon, profile=profile, surface_planets=surface_planets,
        sparse=sparse, astro_detail=astro_detail,
        allowed_planets=allowed_planets, allowed_years=years)


# ---------------------------------------------------------------------------
# The call graph (§2) — returns the assembled section dict (no meta yet).
# ---------------------------------------------------------------------------
def _generate_sections(gen, forecast: dict, profile, horizon: str, *,
                       sparse: bool, astro_detail: str, calendar: dict | None = None) -> dict:
    events = forecast["events"]

    if horizon == "day":
        # DAY is space-tight (§3): cap the block so off-domain events drop for space.
        block = events_block(events, profile, limit=8, astro_detail=astro_detail)
        block += pr_calendar.block(calendar, None, astro_detail)
        user = build_day_user(profile, block, sparse=sparse)
        return {"reading": gen.day(user)["reading"]}

    # month / year: parallel beats, then one synthesis.
    segs = BEAT_SEGMENTS[horizon]
    jobs = []
    for seg in segs:
        block = events_block(events, profile, segment=seg, astro_detail=astro_detail)
        block += pr_calendar.block(calendar, seg, astro_detail)
        jobs.append((seg, build_beat_user(
            profile, SEGMENT_LABEL[seg], block,
            words=_words(horizon, seg), sparse=sparse)))
    beats = gen.beats(jobs)

    full_block = events_block(events, profile, astro_detail=astro_detail)
    full_block += pr_calendar.block(calendar, None, astro_detail)
    synth = gen.synthesize(build_synthesis_user(
        profile, full_block, beats,
        words=_words(horizon, "overview"), sparse=sparse))

    sections = {"overview": synth.get("overview", "")}
    for seg in segs:
        sections[seg] = beats.get(seg, "")
    sections["focus"] = synth.get("focus", "")
    return sections


# ---------------------------------------------------------------------------
# §8 bounded word-count re-ask: rewrite ONLY offending sections, once each.
# ---------------------------------------------------------------------------
def _reask_out_of_range(gen, sections: dict, forecast: dict, profile, horizon: str, *,
                        sparse: bool, astro_detail: str, calendar: dict | None = None) -> list[str]:
    events = forecast["events"]
    reasked = []
    for key in HORIZON_KEYS[horizon]:
        text = sections.get(key, "")
        lo, hi = bounds(horizon, key, sparse=sparse)
        if lo <= word_count(text) <= hi:
            continue
        # context: the section's own segment for beats, else the full list
        seg = key if key in BEAT_SEGMENTS.get(horizon, []) else None
        block = events_block(events, profile, segment=seg, astro_detail=astro_detail)
        block += pr_calendar.block(calendar, seg, astro_detail)
        new_text = gen.reask(
            build_reask_user(profile, key, text, lo, hi, block), key)
        if new_text.strip():
            sections[key] = new_text
            reasked.append(key)
    return reasked


# ---------------------------------------------------------------------------
# Driver (importable; tests inject `generator`)
# ---------------------------------------------------------------------------
def run_reading(forecast: dict, *, reading_type: str = DEFAULT_READING_TYPE,
                generator=None, model: str = DEFAULT_MODEL,
                synthesis_model: str | None = None,
                surface_planets: bool = True, astro_detail: str = "modern",
                calendar: dict | None = None, **gen_kwargs):
    """Run the predictive reading for one profile over the forecast's own horizon.
    `astro_detail` ("plain"|"modern"|"technical") sets how much astrological reasoning the
    text may name (plain = hide all machinery; modern = everyday astro vocabulary;
    technical = full reasoning incl. houses/classical terms). Returns (reading, errors,
    report)."""
    horizon = forecast["meta"]["horizon"]
    if horizon not in HORIZON_KEYS:
        raise ValueError(f"unsupported horizon {horizon!r}")
    profile = get_profile(reading_type)

    sparse = is_sparse(forecast["events"], profile, horizon)
    gcount = grounded_event_count(forecast["events"], profile)

    system_block = build_system_block(surface_planets=surface_planets,
                                      astro_detail=astro_detail)
    gen = generator or make_generator(
        system_block, model=model, synthesis_model=synthesis_model, **gen_kwargs)

    sections = _generate_sections(gen, forecast, profile, horizon,
                                  sparse=sparse, astro_detail=astro_detail, calendar=calendar)
    reasked = _reask_out_of_range(gen, sections, forecast, profile, horizon,
                                  sparse=sparse, astro_detail=astro_detail, calendar=calendar)

    reading = {
        **{k: sections.get(k, "") for k in HORIZON_KEYS[horizon]},
        "meta": {
            "horizon": horizon,
            "profile": reading_type,
            "target_date": forecast["meta"].get("target_date"),
            "natal_ref": forecast["meta"].get("natal_ref"),
            "run_id": forecast["meta"].get("run_id"),
            "model": model,
            "grounded_event_count": gcount,
            "sparse": sparse,
            "surface_planets": surface_planets,
            "astro_detail": astro_detail,
            "calendar_context": bool(calendar),
        },
    }

    ctx = _build_ctx(forecast, profile, horizon,
                     surface_planets=surface_planets, sparse=sparse,
                     astro_detail=astro_detail, calendar=calendar)
    errors = validate(reading, ctx)

    report = {
        "horizon": horizon, "profile": reading_type, "sparse": sparse,
        "grounded_event_count": gcount, "reasked_sections": reasked,
        "astro_detail": astro_detail, "backend": type(gen).__name__,
        "build_blocking": is_build_blocking(errors),
    }
    if getattr(gen, "usage", None):
        report["token_usage"] = gen.usage
    return reading, errors, report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _dry_run(forecast: dict, reading_type: str, astro_detail: str = "modern") -> dict:
    profile = get_profile(reading_type)
    horizon = forecast["meta"]["horizon"]
    events = forecast["events"]
    preview = {"horizon": horizon, "profile": reading_type, "astro_detail": astro_detail,
               "grounded_event_count": grounded_event_count(events, profile),
               "sparse": is_sparse(events, profile, horizon), "blocks": {}}
    if horizon == "day":
        preview["blocks"]["reading"] = events_block(
            events, profile, limit=8, astro_detail=astro_detail)
    else:
        for seg in BEAT_SEGMENTS[horizon]:
            preview["blocks"][seg] = events_block(
                events, profile, segment=seg, astro_detail=astro_detail)
        preview["blocks"]["_full"] = events_block(events, profile, astro_detail=astro_detail)
    return preview


def main() -> None:
    ap = argparse.ArgumentParser(description="Predictive reading generation (L4-analogue).")
    ap.add_argument("--input", required=True,
                    help="grounded forecast JSON (compute_forecast + matched_principles)")
    ap.add_argument("--profile", choices=list(READING_TYPES),
                    default=DEFAULT_READING_TYPE,
                    help="reframe lens: general (default) | personal | professional")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"beat/day model (default {DEFAULT_MODEL})")
    ap.add_argument("--synthesis-model", default=None,
                    help="synthesis model (default: same as --model)")
    ap.add_argument("--no-surface-planets", action="store_true",
                    help="turn OFF plain planet/sky-event names in the output (§5 toggle)")
    ap.add_argument("--astro-detail", choices=["plain", "modern", "technical"],
                    default="modern",
                    help="how much astrological reasoning to name: plain (hide all), "
                         "modern (default: planets/aspects/signs/transits), technical "
                         "(full incl. house numbers & classical terms)")
    ap.add_argument("--out-dir", default=None,
                    help="where to write the reading (default: the forecast's folder, §10)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build the event blocks and print them; no model calls")
    args = ap.parse_args()

    forecast = _load_json(args.input)
    horizon = forecast["meta"]["horizon"]
    target = forecast["meta"].get("target_date", "na")
    out_dir = args.out_dir or os.path.dirname(os.path.abspath(args.input))
    os.makedirs(out_dir, exist_ok=True)

    if args.dry_run:
        preview = _dry_run(forecast, args.profile, args.astro_detail)
        path = os.path.join(out_dir, f"reading_{horizon}_{args.profile}_{target}.dryrun.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(preview, fh, ensure_ascii=False, indent=2)
        print(f"grounded_event_count={preview['grounded_event_count']} "
              f"sparse={preview['sparse']}  dry run -> {path}")
        return

    try:
        reading, errors, report = run_reading(
            forecast, reading_type=args.profile, model=args.model,
            synthesis_model=args.synthesis_model,
            surface_planets=not args.no_surface_planets,
            astro_detail=args.astro_detail)
    except RuntimeError as err:
        print(f"\n{err}", file=sys.stderr)
        sys.exit(2)

    print(f"backend={report['backend']} horizon={horizon} profile={args.profile} "
          f"grounded={report['grounded_event_count']} sparse={report['sparse']} "
          f"reasked={report['reasked_sections']}")
    if report.get("token_usage"):
        u = report["token_usage"]
        print(f"tokens: input={u['input_tokens']:,} output={u['output_tokens']:,} "
              f"cache_read={u['cache_read_input_tokens']:,} over {u['calls']} calls")

    base = f"reading_{horizon}_{args.profile}_{target}"
    if errors:
        rejected = os.path.join(out_dir, base + ".rejected.json")
        with open(rejected, "w", encoding="utf-8") as fh:
            json.dump({"errors": errors, "reading": reading}, fh,
                      ensure_ascii=False, indent=2)
        tag = "TIER-A build-blocking " if report["build_blocking"] else ""
        print(f"\n{tag}CONTRACT VIOLATION - {len(errors)} error(s), NOT writing reading "
              f"(rejected -> {rejected}):", file=sys.stderr)
        for e in errors[:40]:
            print("  -", e, file=sys.stderr)
        sys.exit(1)

    out_path = os.path.join(out_dir, base + ".json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(reading, fh, ensure_ascii=False, indent=2)
    print(f"validated OK -> {out_path}")


if __name__ == "__main__":
    main()
