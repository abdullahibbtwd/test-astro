#!/usr/bin/env python3
"""run.py — the single interactive orchestrator (ORCHESTRATOR_SPEC.md).

One entry point that runs the whole pipeline end to end and writes every artifact
of one run into its own id'd folder under ``runs/``. It replaces the manual
three-step dance (edit compute_chart.py -> ground.py -> l4_interpret.py).

It calls the Python layer functions (L1/L2-L3/L4/L5) IN PROCESS and shells out to
the Node chart-wheel engine (a separate JS module, no Python entry point).
``run.py`` owns all file writing into the run folder; the layer functions are
pure computation.

Pipeline (integral stages, all part of one run):
    L1  chart           compute_chart.compute_chart
    wheel               Chart_wheel/cli.js  (deterministic SVG of chart.json; no LLM)
    L2/L3 grounding     ground.ground
    L4  interpretation  l4_interpret.interpret + l4_render.write_readable
    L5  distillation    distill.distill  (mandatory — a run is incomplete without it)

The chart wheel depends only on chart.json (L1), so it is rendered right after L1
— before the costly L4 call — so a missing Node / render failure aborts cheaply
and every completed run ships its wheel SVGs.

The only thing outside this script is the score *readback* (score_report.py),
deferred because it consumes scores a human fills into scoresheet.csv after the
run. run.py ends by printing the exact command to run once the sheet is filled.

    python run.py
    python run.py --model claude-opus-4-8 --synthesis-model claude-opus-4-8
"""

from __future__ import annotations

import argparse
import json
import os
import random
import string
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# Insert each layer's directory onto sys.path BEFORE importing it: every layer
# module computes paths relative to its own __file__ and imports sibling modules
# (ground imports grounding_schema; l4_interpret imports l4_generate/l4_routing/...).
_LAYER_DIRS = ("d_layer", "principles_grounding", "Interpretation_layer", "Eval_harness")
for _d in _LAYER_DIRS:
    _p = os.path.join(REPO_ROOT, _d)
    if _p not in sys.path:
        sys.path.insert(0, _p)

CORPUS_PATH = os.path.join(REPO_ROOT, "principles_grounding",
                           "all_principles.grounded.json")
RUNS_DIR = os.path.join(REPO_ROOT, "runs")
GEOCODER_USER_AGENT = "astrology-app-orchestrator/1.0 (natal chart pipeline)"

# Chart wheel (CHART_WHEEL_SPEC.md): a deterministic SVG render of chart.json,
# implemented as a standalone Node module. run.py shells out to its CLI once per
# theme, with --check so the §8 invariant gate runs as part of the render.
CHART_WHEEL_CLI = os.path.join(REPO_ROOT, "Chart_wheel", "cli.js")
WHEEL_THEMES = ("light", "dark")


def suffixed(filename: str, suffix: str) -> str:
    """Insert ``_<suffix>`` after the base name (before the first dot) so every
    artifact in a run folder carries the birth date and can never collide with a
    same-named file from another run. Idempotent.

        chart.json            -> chart_1990-07-13.json
        l4_reading.en.txt     -> l4_reading_1990-07-13.en.txt
        chart_wheel.light.svg -> chart_wheel_1990-07-13.light.svg
    """
    base, dot, rest = filename.partition(".")
    tag = f"_{suffix}"
    if base.endswith(tag):
        return filename
    return f"{base}{tag}{dot}{rest}"


# ===========================================================================
# §1  Interactive input
# ===========================================================================

def _prompt(text: str) -> str:
    try:
        return input(text).strip()
    except EOFError:
        print("\nNo input available — aborting.", file=sys.stderr)
        sys.exit(1)


def collect_input() -> dict:
    """Prompt for birth date, time, and place. Re-prompt on invalid input rather
    than crashing. time_precision is fixed to 'exact' for now (§8)."""
    # 1. Birth date — YYYY-MM-DD, must be a real date.
    while True:
        raw = _prompt("Birth date (YYYY-MM-DD): ")
        try:
            d = datetime.strptime(raw, "%Y-%m-%d")
            year, month, day = d.year, d.month, d.day
            break
        except ValueError:
            print("  Invalid date. Use YYYY-MM-DD, e.g. 1979-03-30.")

    # 2. Birth time — HH:MM (24h), LOCAL wall-clock at the birth place. Passed
    #    straight to compute_chart, which converts local->UT itself. No tz math here.
    while True:
        raw = _prompt("Birth time (HH:MM, 24h, local time at birth place): ")
        try:
            t = datetime.strptime(raw, "%H:%M")
            hour, minute = t.hour, t.minute
            break
        except ValueError:
            print("  Invalid time. Use HH:MM in 24h, e.g. 06:30.")

    # 3. Birth place — free-text city string.
    while True:
        place_query = _prompt("Birth place (e.g. Istanbul, Turkey): ")
        if place_query:
            break
        print("  Place cannot be empty.")

    return {
        "year": year, "month": month, "day": day,
        "hour": hour, "minute": minute,
        "birth_date": f"{year:04d}-{month:02d}-{day:02d}",
        "birth_time_local": f"{hour:02d}:{minute:02d}",
        "place_query": place_query,
    }


# ===========================================================================
# §2  Geocoding (the only online step)
# ===========================================================================

def geocode(place_query: str) -> dict:
    """City string -> (latitude, longitude, resolved_display_name) via Nominatim.

    On zero results: print the failure and re-prompt for the place string (never
    fall back to a default, never proceed coordinate-less). On a hit, echo the
    resolved display name back for confirmation — a wrong city silently corrupts
    the entire chart. Timezone is NOT resolved here; compute_chart derives it from
    lat/lon internally.
    """
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderServiceError, GeocoderTimedOut

    geolocator = Nominatim(user_agent=GEOCODER_USER_AGENT, timeout=15)

    query = place_query
    while True:
        try:
            location = geolocator.geocode(query, addressdetails=False)
        except (GeocoderServiceError, GeocoderTimedOut) as err:
            print(f"  Geocoding service error: {err}")
            query = _prompt("  Re-enter birth place: ") or query
            continue

        if location is None:
            print(f"  No location found for {query!r}.")
            query = _prompt("  Re-enter birth place: ") or query
            continue

        display_name = location.address
        lat = round(float(location.latitude), 4)
        lon = round(float(location.longitude), 4)

        ans = _prompt(
            f"  Resolved to: {display_name} ({lat}, {lon}) — correct? [Y/n] "
        ).lower()
        if ans in ("", "y", "yes"):
            return {
                "provider": "nominatim",
                "display_name": display_name,
                "latitude": lat,
                "longitude": lon,
                "place_query": query,
            }
        # Rejected — re-prompt for a better string.
        query = _prompt("  Re-enter birth place: ") or query


# ===========================================================================
# §5  Run id & directory
# ===========================================================================

def mint_run_id(now_utc: datetime, birth_date: str) -> str:
    """YYYYMMDD-HHMMSS_<3 random lowercase alnum>_<birthdate> — sortable,
    collision-safe, and self-identifying. The trailing birthdate (YYYY-MM-DD)
    makes every run folder name say whose chart it is at a glance, so two runs
    are never indistinguishable by title."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=3))
    return now_utc.strftime("%Y%m%d-%H%M%S") + "_" + suffix + "_" + birth_date


# ===========================================================================
# Chart wheel (deterministic SVG; Node module — the one sanctioned shell-out)
# ===========================================================================

class WheelError(RuntimeError):
    """The chart-wheel render failed (Node missing, gate violation, or crash)."""


def render_chart_wheels(chart_path: str, run_dir: str, suffix: str,
                        stem: str = "chart_wheel") -> list[str]:
    """Render the chart wheel for each theme into run_dir, gated by §8 invariants.

    Pure function of chart.json (no LLM, no network). Returns the written SVG
    paths. ``stem`` names the output file (e.g. "chart_wheel_a" for a synastry
    person). Raises WheelError on a missing Node runtime, an invariant-gate
    violation, or any renderer crash — fail loud, like any other stage.
    """
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        raise WheelError(
            "Node.js runtime not found on PATH — the chart wheel (Chart_wheel/) "
            "is a Node module. Install Node 18+ and retry."
        )
    if not os.path.exists(CHART_WHEEL_CLI):
        raise WheelError(f"chart-wheel CLI missing: {CHART_WHEEL_CLI}")

    # cli.js resolves the chart path against its own cwd, so pass it absolute
    # (run.py owns all paths). cli.js resolves its JS imports via import.meta,
    # independent of cwd, so we don't override cwd.
    chart_path = os.path.abspath(chart_path)

    written: list[str] = []
    for theme in WHEEL_THEMES:
        out_path = os.path.join(run_dir, suffixed(f"{stem}.{theme}.svg", suffix))
        # --check runs the §8 invariant gate and writes the SVG only if it passes;
        # exit 1 on any violation.
        proc = subprocess.run(
            [node, CHART_WHEEL_CLI, chart_path,
             "--theme", theme, "--check", "--out", out_path],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not os.path.exists(out_path):
            raise WheelError(
                f"chart-wheel render/gate failed for theme {theme!r} "
                f"(exit {proc.returncode}):\n{proc.stderr.strip()}"
            )
        written.append(out_path)
    return written


# ===========================================================================
# Orchestration
# ===========================================================================

def _write_json(path: str, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser(description="Interactive natal-chart pipeline (L1->L5).")
    # §7-optional: thread model/token knobs through to L4 if the user sets them.
    ap.add_argument("--model", default=None, help="L4 section-call model")
    ap.add_argument("--synthesis-model", default=None, help="L4 synthesis-call model")
    ap.add_argument("--max-tokens", type=int, default=None, help="L4 per-section budget")
    ap.add_argument("--synthesis-max-tokens", type=int, default=None,
                    help="L4 synthesis output budget")
    ap.add_argument("--distill-model", default=None, help="L5 distiller model")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set — L4 interpretation and L5 distillation "
              "make real Anthropic calls and need it. Export it and retry.",
              file=sys.stderr)
        return 1
    if not os.path.exists(CORPUS_PATH):
        print(f"Missing grounded corpus: {CORPUS_PATH}", file=sys.stderr)
        return 1

    # --- 1. collect input (§1) ---
    inp = collect_input()
    # Every artifact in this run is suffixed with the birth date (§5), so a file
    # pulled out of its run folder is never confused with another run's.
    suffix = inp["birth_date"]

    # --- 2. geocode (§2) ---
    geo = geocode(inp["place_query"])

    # --- 3. mint run_id, create runs/<run_id>/ (§5). No file under the run dir is
    #        written before this point (invariant 1). ---
    now_utc = datetime.now(timezone.utc)
    run_id = mint_run_id(now_utc, inp["birth_date"])
    run_dir = os.path.join(RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)
    print(f"\nrun_id = {run_id}\nrun_dir = {run_dir}\n")

    artifacts: list[str] = []

    def artifact(*names: str) -> None:
        for n in names:
            if n not in artifacts:
                artifacts.append(n)

    def write_meta(status: str, models: dict | None = None,
                   resolved_tz: str | None = None) -> None:
        meta = {
            "run_id": run_id,
            "created_utc": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "input": {
                "birth_date": inp["birth_date"],
                "birth_time_local": inp["birth_time_local"],
                "place_query": inp["place_query"],
            },
            "geocode": {
                "provider": geo["provider"],
                "display_name": geo["display_name"],
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
            },
            "resolved_timezone": resolved_tz,
            "time_precision": "exact",
            "models": models or {},
            "artifacts": list(artifacts),
        }
        _write_json(os.path.join(run_dir, suffixed("run_meta.json", suffix)), meta)

    # --- 4. L1 chart -> chart.json ---
    from compute_chart import compute_chart, BirthData

    bd = BirthData(
        year=inp["year"], month=inp["month"], day=inp["day"],
        hour=inp["hour"], minute=inp["minute"],
        latitude=geo["latitude"], longitude=geo["longitude"],
        time_precision="exact",
    )
    chart = compute_chart(bd)
    chart_path = os.path.join(run_dir, suffixed("chart.json", suffix))
    _write_json(chart_path, chart)
    artifact(os.path.basename(chart_path))
    resolved_tz = (chart.get("meta") or {}).get("timezone")
    print(f"[L1] chart computed (timezone={resolved_tz})")

    # --- 4b. Chart wheel -> chart_wheel.{light,dark}.svg ---
    # Deterministic SVG of chart.json; depends on nothing downstream. Rendered
    # here (before the costly L4 call) so a Node/render failure aborts cheaply.
    print("[wheel] rendering chart wheel (light + dark)...")
    try:
        wheel_paths = render_chart_wheels(chart_path, run_dir, suffix)
    except WheelError as err:
        print(f"\n[wheel] render failed: {err}", file=sys.stderr)
        write_meta("wheel_render_error", resolved_tz=resolved_tz)
        return 1
    for p in wheel_paths:
        artifact(os.path.basename(p))
    print(f"[wheel] wrote {', '.join(os.path.basename(p) for p in wheel_paths)}")

    # --- 5. L2/L3 grounding -> personal_principles.json ---
    from ground import ground

    with open(CORPUS_PATH, encoding="utf-8") as fh:
        corpus = json.load(fh)
    result = ground(corpus, chart, reading="natal")
    personal_payload = result.kept_payload()
    # Invariant 2: assert the kept-count contract on write.
    assert personal_payload["kept_count"] == len(result.kept), \
        "kept_count != len(result.kept)"
    pp_name = suffixed("personal_principles.json", suffix)
    _write_json(os.path.join(run_dir, pp_name), personal_payload)
    artifact(pp_name)
    print(f"[L2/L3] grounded {len(result.kept)} personal principles "
          f"({len(result.drops)} dropped)")

    # --- 6. L4 interpretation ---
    # Pass result.kept to interpret() in memory; the written file is a record only.
    from l4_interpret import interpret
    from l4_render import write_readable

    gen_kwargs: dict = {}
    if args.max_tokens is not None:
        gen_kwargs["max_tokens"] = args.max_tokens
    if args.synthesis_max_tokens is not None:
        gen_kwargs["synthesis_max_tokens"] = args.synthesis_max_tokens
    interpret_kwargs: dict = dict(gen_kwargs)
    if args.model is not None:
        interpret_kwargs["model"] = args.model
    if args.synthesis_model is not None:
        interpret_kwargs["synthesis_model"] = args.synthesis_model

    print("[L4] interpreting (real Anthropic calls — this can take a while)...")
    try:
        output, report, errors = interpret(chart, result.kept, **interpret_kwargs)
    except RuntimeError as err:
        # generation backend failure (e.g. token cap) — fail loud, fail clean.
        print(f"\n[L4] generation failed: {err}", file=sys.stderr)
        write_meta("l4_generation_error")
        return 2

    # The routing report doesn't carry model names; record what we resolved/used.
    from l4_generate import DEFAULT_MODEL
    section_model = args.model or DEFAULT_MODEL
    models = {
        "section": section_model,
        "synthesis": args.synthesis_model or section_model,
    }

    if errors:
        # §6: L4 contract violation. Do NOT write l4_output.json or run the
        # distiller. Keep chart.json / personal_principles.json for debugging.
        print(f"\n[L4] CONTRACT VIOLATION — {len(errors)} error(s); "
              "not writing l4_output.json:", file=sys.stderr)
        for e in errors[:40]:
            print("  -", e, file=sys.stderr)
        write_meta("l4_contract_violation", models=models, resolved_tz=resolved_tz)
        return 1

    # errors == [] : now (and only now) write l4_output.json (invariant 3).
    l4_name = suffixed("l4_output.json", suffix)
    report_name = suffixed("l4_routing_report.json", suffix)
    _write_json(os.path.join(run_dir, l4_name), output)
    _write_json(os.path.join(run_dir, report_name), report)
    artifact(l4_name, report_name)
    reading_paths = write_readable(output, run_dir, stem=suffixed("l4_reading", suffix))
    for p in reading_paths:
        artifact(os.path.basename(p))
    print(f"[L4] {len(output['sections'])} sections; "
          f"readable -> {', '.join(os.path.basename(p) for p in reading_paths)}")

    # --- 7. L5 distillation (mandatory) ---
    from distill import distill, DEFAULT_MODEL as DISTILL_DEFAULT

    print("[L5] distilling reading into ratable statements...")
    try:
        distill_paths = distill(
            output, run_dir,
            model=args.distill_model or DISTILL_DEFAULT,
            suffix=suffix,
        )
    except (RuntimeError, ValueError) as err:
        # A distiller failure is a run failure — treated like any other stage error.
        print(f"\n[L5] distillation failed: {err}", file=sys.stderr)
        write_meta("l5_distill_error", models=models, resolved_tz=resolved_tz)
        return 1
    for p in distill_paths:
        artifact(os.path.basename(p))
    print(f"[L5] wrote {', '.join(os.path.basename(p) for p in distill_paths)}")

    # --- 8. manifest + summary + the next human step ---
    # List run_meta.json among the artifacts before writing, so the manifest
    # records itself.
    artifact(suffixed("run_meta.json", suffix))
    write_meta("complete", models=models, resolved_tz=resolved_tz)

    scoresheet = os.path.join("runs", run_id, suffixed("scoresheet.csv", suffix))
    print("\n" + "=" * 70)
    print(f"RUN COMPLETE — {run_dir}")
    print("Artifacts:")
    for a in artifacts:
        print(f"  - {a}")
    print("\nNext human step: fill the `score` column (0-10) in scoresheet.csv, then:")
    print(f"  python Eval_harness/score_report.py {scoresheet}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
