#!/usr/bin/env python3
"""
ground_forecast.py — the forecast analogue of ``ground.py`` (FORECAST_GROUNDING_SPEC.md).

Where ``ground.py`` keeps a principle iff its subject is true of a **static chart**, this
keeps a principle iff its subject is true of a **transient forecast event**. It takes the
deterministic forecast (``compute_forecast()`` events) plus the natal chart the forecast was
built on, and attaches to each event the predictive principles verifiably about it — the
``matched_principles`` array the reading layer already consumes.

**Deterministic-first, no runtime LLM.** Stage 1 is exact structured matching against the
predictive corpus's ``about`` blocks (an index lookup per event). Stage 2 is an OPTIONAL
semantic residual that reuses the existing L2 retrieval infra to reach the
``general``/``unclassified``/angle records the structured index cannot — it is gated behind
a flag and an injected retriever, so with none wired the module ships Stage 1 alone (which
grounds the aspect + ingress spine, i.e. most events).

Reused verbatim from ``ground.py`` where the logic is subject-agnostic (§0): Gate A
(``_gate_a``), Gate C (``_gate_c`` / ``_requirement_satisfiable``), ``_point_index``, the
``DropLog`` shape, and ``grounding_schema.invariant_violation``. Only Gate B's reconciliation
target changes — from the chart to each event.

Run
---
    python ground_forecast.py --forecast <forecast.json> --chart <chart.json>
    # writes the forecast back out with matched_principles + a coverage report
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional, Protocol

# Reuse the subject-agnostic machinery from the natal gate (§0).
from ground import DropLog, _gate_a, _gate_c, _point_index
from grounding_schema import invariant_violation

# Gate A domain set for the predictive reading (§0: add the reading key).
PREDICTIVE_DOMAINS = {"predictive", "timing"}

# Tradition gate: predictive grounding is modern-only (same rule as CAL D3). The
# predictive+timing slice does carry traditional general/unclassified records, so this
# is enforced, not assumed. A record with no tradition field is not eligible.
PREDICTIVE_TRADITIONS = {"modern"}

# The four chart angles are aspect targets with no planet-pair record; they route to
# Stage 2 (+ ascendant-tagged records for the Ascendant only), never Stage 1 (§3).
ANGLE_TARGETS = {"Ascendant", "MC", "IC", "Descendant"}

DEFAULT_CAP = 6                 # §1 cap N per event
DEFAULT_SIM_FLOOR = 0.35        # §4 embedding similarity floor (validate empirically)

# Per-family structural floor: below this many structural matches, Stage 2 is invited to
# fill the gap (§4). Families with no structured record type start at 0 (always residual).
STRUCTURAL_FLOOR = {
    "transit_aspect": 1, "ingress_house": 1,
    "ingress_sign": 0, "lunation": 0, "eclipse": 0, "profection": 0,
}


# ===========================================================================
# Stage 1 — deterministic exact-match indices (§2)
# ===========================================================================
@dataclass
class MatchIndices:
    """Built once per run from the predictive-domain slice of the merged corpus."""
    aspect: dict[tuple, list[dict]] = field(default_factory=dict)        # (source, target, type)
    house_point: dict[tuple, list[dict]] = field(default_factory=dict)   # (point, house, hs)
    house_domain: dict[tuple, list[dict]] = field(default_factory=dict)  # (house, hs)
    sign_point: dict[tuple, list[dict]] = field(default_factory=dict)    # (point, sign)
    corpus_ids: set[str] = field(default_factory=set)


def build_indices(records: list[dict]) -> MatchIndices:
    """Index only the modern predictive/timing slice (Gate A + tradition applied up front,
    §2). general and unclassified records carry no subject and are deliberately NOT
    indexed — they are reachable only via Stage 2 (§3), so per-event grounding cannot
    flood on them."""
    idx = MatchIndices()
    for rec in records:
        if rec.get("domain") not in PREDICTIVE_DOMAINS:
            continue
        if _gate_tradition(rec):
            continue
        idx.corpus_ids.add(rec.get("principle_id"))
        about = rec.get("about") or {}
        ft = about.get("factor_type")
        if ft == "aspect":
            a = about.get("aspect") or {}
            s, t, typ = a.get("source"), a.get("target"), a.get("type")
            # Directed: corpus aspect records are source = transiting, target = natal.
            if s and t and typ:
                idx.aspect.setdefault((s, t, typ), []).append(rec)
        elif ft == "planet_in_house":
            key = (about.get("point"), about.get("house"),
                   about.get("house_system") or "placidus")
            idx.house_point.setdefault(key, []).append(rec)
        elif ft == "house_domain":
            idx.house_domain.setdefault(
                (about.get("house"), about.get("house_system") or "placidus"), []
            ).append(rec)
        elif ft == "planet_in_sign":
            idx.sign_point.setdefault((about.get("point"), about.get("sign")), []).append(rec)
        # general / unclassified / house_lord_relative / dignity / etc. -> not indexed.
    return idx


# ===========================================================================
# Stage 1 — Gate B dispatch by event family (§2 table, §3 overrides)
# ===========================================================================
def _structural_candidates(event: dict, idx: MatchIndices) -> list[dict]:
    fam = event.get("family")
    bodies = event.get("bodies") or {}
    trans, natal = bodies.get("transiting"), bodies.get("natal")

    if fam == "transit_aspect":
        # Angle-target contacts have no planet-pair record -> Stage 2 only (§3).
        if natal in ANGLE_TARGETS or natal is None or trans is None:
            return []
        # Directed match (§2 direction discipline): transiting -> record source, natal ->
        # record target. "tr Sun □ natal Saturn" must not pull "tr Saturn □ natal Sun".
        return list(idx.aspect.get((trans, natal, event.get("aspect")), []))

    if fam == "ingress_house":
        hp = event.get("house_placidus")
        out = list(idx.house_point.get((trans, hp, "placidus"), []))
        out += idx.house_domain.get((hp, "placidus"), [])
        return out

    if fam == "ingress_sign":
        return list(idx.sign_point.get((trans, event.get("sign")), []))

    if fam in ("lunation", "eclipse"):
        hp = event.get("house_placidus")
        if hp is not None:
            return list(idx.house_domain.get((hp, "placidus"), []))
        return []

    return []


# ===========================================================================
# Stage 2 — embedding residual interface (§4). Optional, injectable, deterministic.
# ===========================================================================
class EmbeddingRetriever(Protocol):
    """The existing L2 semantic-retrieval infra, adapted. Given a query and k, returns
    (record, similarity) pairs from the predictive candidate pool, best first. Reuse the
    SAME embedding index/model natal retrieval uses (§4) — do not stand up a second space."""
    def query(self, text: str, k: int) -> list[tuple[dict, float]]: ...


class NullRetriever:
    """Stand-in when no embedding infra is wired yet (§4 fallback). Returns nothing, so
    general/unclassified/angle coverage stays thin but the structural spine still grounds."""
    def query(self, text: str, k: int) -> list[tuple[dict, float]]:
        return []


def _event_query(event: dict) -> str:
    """Build the Stage-2 query from the event's topic_tags + a compact plain gloss of the
    configuration the compute layer already produced (§4.1)."""
    g = event.get("grounding") or {}
    tags = list(g.get("topic_tags") or [])
    bodies = event.get("bodies") or {}
    bits = [event.get("family", ""), bodies.get("transiting") or "",
            bodies.get("natal") or "", event.get("aspect") or "",
            event.get("phase") or "", event.get("sign") or ""]
    return " ".join(t for t in (tags + bits) if t).strip()


# ===========================================================================
# Result container (§1 primary + secondary outputs)
# ===========================================================================
@dataclass
class ForecastGroundingResult:
    forecast: dict                       # the injected forecast (events + matched_principles)
    drops: list[DropLog]
    per_event: dict[str, dict]           # event_id -> {kept, structural, embedding}
    zero_match_events: list[str]
    stage2_enabled: bool
    cap: int

    def report(self) -> dict:
        stage_split = Counter()
        for ev in self.forecast.get("events", []):
            for m in ev.get("matched_principles", []):
                stage_split[m.get("source_stage")] += 1
        return {
            "reading": "forecast",
            "horizon": (self.forecast.get("meta") or {}).get("horizon"),
            "events_total": len(self.forecast.get("events", [])),
            "events_with_matches":
                len(self.forecast.get("events", [])) - len(self.zero_match_events),
            "events_with_zero_matches": self.zero_match_events,   # §6.7 explicit
            "kept_total": sum(v["kept"] for v in self.per_event.values()),
            "source_stage_split": dict(stage_split),
            "drops_by_gate": dict(Counter(d.gate for d in self.drops)),
            "stage2_enabled": self.stage2_enabled,
            "cap_n": self.cap,
            "per_event": self.per_event,
            "drop_log": [d.as_dict() for d in self.drops],
        }


# ===========================================================================
# The gate
# ===========================================================================
def _gate_tradition(rec: dict) -> Optional[str]:
    trad = rec.get("tradition")
    if trad not in PREDICTIVE_TRADITIONS:
        return f"tradition {trad!r} not in allowed {sorted(PREDICTIVE_TRADITIONS)}"
    return None


def _matched_entry(rec: dict, source_stage: str, similarity: Optional[float]) -> dict:
    return {
        "principle_id": rec.get("principle_id"),
        "judgment": rec.get("judgment", ""),
        "topic_tags": rec.get("topic_tags", []),
        "tradition": rec.get("tradition"),   # always "modern" — tradition gate (§1)
        "source_stage": source_stage,
        "similarity": similarity,
    }


def ground_forecast(forecast: dict, chart: dict, records: list[dict], *,
                    cap: int = DEFAULT_CAP,
                    retriever: Optional[EmbeddingRetriever] = None,
                    sim_floor: float = DEFAULT_SIM_FLOOR) -> ForecastGroundingResult:
    """Attach ``matched_principles`` to every forecast event. Stage 1 (structural) always
    runs; Stage 2 (embedding residual) runs only when a ``retriever`` is provided (§4).
    Mutates a deep copy of ``forecast`` and returns it inside the result (input untouched)."""
    forecast = copy.deepcopy(forecast)
    idx = build_indices(records)
    pts = _point_index(chart)
    stage2 = retriever is not None and not isinstance(retriever, NullRetriever)

    drops: list[DropLog] = []
    per_event: dict[str, dict] = {}
    zero: list[str] = []

    for event in forecast.get("events", []):
        eid = event.get("event_id", "<no-id>")

        # --- Stage 1: structural candidates, then Gate A/C wrap (§2) ---
        kept: list[dict] = []
        seen: set[str] = set()
        for rec in _structural_candidates(event, idx):
            pid = rec.get("principle_id")
            about = rec.get("about") or {}
            # Gate A (redundant with the index pre-filter, but asserts invariant 1).
            reason = _gate_a(rec, PREDICTIVE_DOMAINS)
            if reason:
                drops.append(DropLog(pid, "A", reason, about, {"event_id": eid}))
                continue
            # Tradition gate (likewise redundant with the index pre-filter).
            reason = _gate_tradition(rec)
            if reason:
                drops.append(DropLog(pid, "TRADITION", reason, about, {"event_id": eid}))
                continue
            # invariant precondition (never compare against a null required field).
            viol = invariant_violation(about)
            if viol:
                drops.append(DropLog(pid, "INVARIANT_VIOLATION", viol, about, {"event_id": eid}))
                continue
            # Gate C — satisfiable in the NATAL chart (reused unchanged, §2).
            ok, creason = _gate_c(rec, chart, pts)
            if not ok:
                drops.append(DropLog(pid, "C", creason, about, {"event_id": eid}))
                continue
            if pid not in seen:
                seen.add(pid)
                kept.append(rec)

        # structural ranked deterministically by principle_id (§5)
        structural = sorted(kept, key=lambda r: r.get("principle_id") or "")
        matched = [_matched_entry(r, "structural", None) for r in structural]
        n_structural = len(matched)

        # --- Stage 2: embedding residual to fill gaps (§4) ---
        n_embedding = 0
        below_floor = n_structural < STRUCTURAL_FLOOR.get(event.get("family"), 0)
        wants_residual = (below_floor or n_structural < cap
                          or (event.get("bodies") or {}).get("natal") in ANGLE_TARGETS
                          or event.get("family") in ("ingress_sign", "lunation", "eclipse"))
        if stage2 and wants_residual and len(matched) < cap:
            hits = retriever.query(_event_query(event), cap * 2)
            # deterministic order: similarity desc, then principle_id (§5)
            hits = sorted(
                ((r, s) for r, s in hits
                 if r.get("domain") in PREDICTIVE_DOMAINS and s >= sim_floor),
                key=lambda rs: (-rs[1], rs[0].get("principle_id") or ""))
            for rec, sim in hits:
                pid = rec.get("principle_id")
                if pid in seen:
                    continue
                treason = _gate_tradition(rec)
                if treason:
                    drops.append(DropLog(pid, "TRADITION", treason, rec.get("about") or {},
                                         {"event_id": eid}))
                    continue
                ok, creason = _gate_c(rec, chart, pts)
                if not ok:
                    drops.append(DropLog(pid, "C", creason, rec.get("about") or {},
                                         {"event_id": eid}))
                    continue
                seen.add(pid)
                matched.append(_matched_entry(rec, "embedding", round(float(sim), 4)))
                n_embedding += 1
                if len(matched) >= cap:
                    break

        # cap N, structural already ahead of embedding by append order (§1, §8)
        matched = matched[:cap]
        event["matched_principles"] = matched
        per_event[eid] = {"kept": len(matched), "structural": n_structural,
                          "embedding": n_embedding}
        if not matched:
            zero.append(eid)

    return ForecastGroundingResult(
        forecast=forecast, drops=drops, per_event=per_event,
        zero_match_events=zero, stage2_enabled=stage2, cap=cap)


# ===========================================================================
# CLI
# ===========================================================================
def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Forecast grounding gate — attaches matched_principles to each event.")
    ap.add_argument("--forecast", required=True, help="compute_forecast() output JSON")
    ap.add_argument("--chart", required=True,
                    help="the natal chart the forecast was built on")
    ap.add_argument("--corpus",
                    default=os.path.join(here, "all_principles_grounded.with_predictive.json"),
                    help="MERGED grounded corpus (predictive slice; never the pre-merge file)")
    ap.add_argument("--out", default=None,
                    help="output forecast+matched_principles (default: alongside --forecast)")
    ap.add_argument("--report", default=None,
                    help="coverage report path (default: alongside --out)")
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP,
                    help=f"max matched principles per event (default {DEFAULT_CAP})")
    ap.add_argument("--enable-embeddings", action="store_true",
                    help="run Stage 2 residual (needs L2 retrieval infra wired; else no-op)")
    ap.add_argument("--sim-floor", type=float, default=DEFAULT_SIM_FLOOR)
    args = ap.parse_args()

    with open(args.forecast, encoding="utf-8") as fh:
        forecast = json.load(fh)
    with open(args.chart, encoding="utf-8") as fh:
        chart = json.load(fh)
    with open(args.corpus, encoding="utf-8") as fh:
        corpus = json.load(fh)
    records = corpus if isinstance(corpus, list) else next(
        v for v in corpus.values() if isinstance(v, list))

    retriever: Optional[EmbeddingRetriever] = None
    if args.enable_embeddings:
        # No L2 retrieval infra is wired in this repo yet (§4 fallback): warn and run
        # Stage 1 only rather than silently pretending Stage 2 ran.
        print("[ground_forecast] --enable-embeddings set but no retriever is wired; "
              "running Stage 1 only (see §4).")

    result = ground_forecast(forecast, chart, records, cap=args.cap,
                             retriever=retriever, sim_floor=args.sim_floor)

    out = args.out or os.path.join(
        os.path.dirname(os.path.abspath(args.forecast)),
        os.path.splitext(os.path.basename(args.forecast))[0] + ".grounded.json")
    report_path = args.report or (os.path.splitext(out)[0] + ".coverage.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result.forecast, fh, ensure_ascii=False, indent=1)
    with open(report_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result.report(), fh, ensure_ascii=False, indent=2)

    rep = result.report()
    print(f"grounded {rep['events_total']} events: {rep['kept_total']} matches "
          f"({rep['source_stage_split']}), "
          f"{len(rep['events_with_zero_matches'])} with zero matches, "
          f"{sum(rep['drops_by_gate'].values())} drops {rep['drops_by_gate']}")
    print(f"-> {out}\n-> {report_path}")


if __name__ == "__main__":
    main()
