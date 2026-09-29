#!/usr/bin/env python3
"""
ground_acg.py — ACG spec 03 (+ v3 change order 07 §7): which principles are true of
THIS person in THIS place.

Deterministic. No LLM. Reuses ground.py's gate functions (``_point_index``,
``_gate_b``, ``_gate_c``, ``_requirement_satisfiable``, ``_relation_exists``, the
``DropLog`` record and the drop-report shape) — it never forks them.

Inputs: natal chart, relocated chart (may be None), locate.json, the ACG corpus
(``acg_principles.grounded.json``, primary source) and the main corpus (fallback A4
and stream B only). Only ACG scopes line / angle_frame / planet_general / method are
eligible; paran / zenith / ccg / mundane are never loaded in v1.

Line selection (spec 03 §3): every tight/strong line of a read body, up to the 4
closest; if none, the single nearest wide line; else none (acg-method-no-influence).

Evidence streams (spec 03 §4):
  A  line evidence: A3 angle frame, A1 planet-on-angle records, A2 planet synopsis,
     A4 fallback (main-corpus modern natal planet_in_house for the angle's house,
     only when A1 kept < 3; fills A1 + A4 up to 3).
     >>> A4 is the ONE sanctioned exception to the Placidus-only house policy: the
     line claim replaces the house claim, so the record's house is NOT verified
     against the chart. Its other dependencies still go through ground._gate_c. <<<
  B  relocated-house evidence: main-corpus modern natal planet_in_house records for
     planets whose Placidus house changes, run through the standard ground.py gates
     against the relocated chart.
  C  method framing records (fixed ids).

``requires`` on ACG records carries value conditions (exploration report C6):
natal_point_sign / _aspect / _retrograde / _dignity are checked against the NATAL
chart; relocated_point_house / _angular against the RELOCATED chart. The main
corpus's existence tokens go through ground._requirement_satisfiable unchanged.
Anything else is dropped as ``requires_unsupported_kind`` — never guessed.

v3 (07 §7): the payload also carries ``goal_contributors`` — per goal, the score,
band and contributing record ids from ACG spec 08 §3 for this place. Contributor
records from lines not selected for prose (e.g. wide lines) are loaded into
``goal_records`` with ``acg_evidence.tier`` set to the line's tier.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from collections import Counter
from typing import Any, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, os.path.join(_ROOT, "Astrocartography")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ground import (  # noqa: E402  — reused, not forked
    DropLog, _gate_b, _gate_c, _point_index, _relation_exists, _requirement_satisfiable,
    ground,
)
from grounding_vocab import DIGNITY_TO_CLASSIFICATION  # noqa: E402

from acg_constants import (  # noqa: E402
    A4_FILL_TO, ACG_MAX_HOUSE_SHIFTS, ACG_MAX_LINES_READ, ANGLE_HOUSE, BODY_DISPLAY,
    BODY_ORDER, DISPLAY_TO_BODY, GOAL_ORDER, PERSONAL_BODIES, TIER_LABELS, ANGLE_LABELS,
    PLANET_TR,
)

SCHEMA_VERSION = "acg-ground-2"
ACG_CORPUS_PATH = os.path.join(_HERE, "acg_principles.grounded.json")
MAIN_CORPUS_PATH = os.path.join(_HERE, "all_principles.grounded.json")

V1_SCOPES = ("line", "angle_frame", "planet_general", "method", "paran")   # paran: spec 10 §5
DROP_REASONS = (
    "tier_wide_not_selected", "body_out_of_scope", "line_budget_exceeded", "scope_not_v1",
    "fallback_not_needed", "covered_by_line", "house_budget_exceeded",
    "requires_unsatisfied_natal", "requires_unsatisfied_relocated",
    "requires_needs_relocated_chart", "requires_unsupported_kind",
)
METHOD_ALWAYS = ("acg-method-ambivalence", "acg-method-natal-modifies-response",
                 "acg-method-degree-of-expression")
ANGULAR = (1, 4, 7, 10)


# ---------------------------------------------------------------------------
# Corpus helpers
# ---------------------------------------------------------------------------

def load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def corpus_ok(path: str = ACG_CORPUS_PATH) -> tuple[bool, Optional[str]]:
    """Preflight (spec 05 stage 7): the corpus exists and matches its .sha256 sidecar."""
    if not os.path.exists(path):
        return False, None
    digest = sha256_file(path)
    side = path + ".sha256"
    if os.path.exists(side):
        with open(side, encoding="utf-8") as fh:
            recorded = fh.read().split()[0].strip() if fh.readable() else ""
        if recorded and recorded != digest:
            return False, digest
    return True, digest


class _Index:
    """Lookup tables over the two corpora, built once per call."""

    def __init__(self, acg_corpus: list[dict], main_corpus: list[dict]):
        self.by_id: dict[str, dict] = {}
        self.line: dict[tuple[str, str], list[dict]] = {}
        self.general: dict[str, list[dict]] = {}
        self.frame: dict[str, dict] = {}
        self.method: dict[str, dict] = {}
        self.paran: dict[str, list[dict]] = {}          # "<a>-<b>" (alphabetical) -> records
        self.out_of_scope: list[dict] = []
        for r in acg_corpus:
            self.by_id[r["principle_id"]] = r
            scope, about = r.get("acg_scope"), r.get("about") or {}
            if scope not in V1_SCOPES:
                self.out_of_scope.append(r)
                continue
            if scope == "line":
                key = (DISPLAY_TO_BODY.get(about.get("planet"), ""), about.get("angle"))
                self.line.setdefault(key, []).append(r)
            elif scope == "planet_general":
                self.general.setdefault(DISPLAY_TO_BODY.get(about.get("planet"), ""), []).append(r)
            elif scope == "angle_frame":
                self.frame[about.get("angle")] = r
            elif scope == "method":
                self.method[r["principle_id"]] = r
            elif scope == "paran":
                if about.get("factor_type") == "acg_paran":
                    key = "-".join(sorted(DISPLAY_TO_BODY.get(p, p.lower())
                                          for p in about.get("planets", [])))
                    self.paran.setdefault(key, []).append(r)
                else:                                   # acg-method-crossings (about acg_method)
                    self.method[r["principle_id"]] = r
        for recs in self.line.values():
            recs.sort(key=lambda r: (-int(r.get("citation_count") or 0), r["principle_id"]))
        for recs in self.general.values():
            recs.sort(key=lambda r: r["principle_id"])
        for recs in self.paran.values():
            recs.sort(key=lambda r: (-int(r.get("citation_count") or 0), r["principle_id"]))
        # main corpus: modern natal planet_in_house pool (exploration report C8)
        self.pih: dict[tuple[str, int], list[dict]] = {}
        for r in main_corpus:
            about = r.get("about") or {}
            if (about.get("factor_type") == "planet_in_house" and r.get("domain") == "natal"
                    and r.get("tradition") == "modern"):
                self.pih.setdefault((about.get("point"), about.get("house")), []).append(r)
                self.by_id.setdefault(r["principle_id"], r)
        for recs in self.pih.values():
            recs.sort(key=lambda r: r["principle_id"])


# ---------------------------------------------------------------------------
# requires evaluation (gate 3)
# ---------------------------------------------------------------------------

_NATAL_KINDS = {"natal_point_sign", "natal_point_aspect", "natal_point_retrograde",
                "natal_point_dignity"}
_RELOC_KINDS = {"relocated_point_house", "relocated_point_angular"}
_EXISTENCE_KINDS = {"native_gender", "birth_time", "ascendant", "house_ruler", "point_sign",
                    "point_aspects", "point_house", "point_dignity", "sign_element", "other"}


def eval_requires(record: dict, natal: dict, relocated: Optional[dict],
                  skip_house_of: Optional[str] = None) -> tuple[bool, Optional[str], Any]:
    """-> (ok, drop_reason, fact). ``skip_house_of`` drops the A4 house condition."""
    npts = _point_index(natal)
    rpts = _point_index(relocated) if relocated else {}
    for req in record.get("requires") or []:
        kind = req.get("kind")
        point = req.get("point")
        if kind in _NATAL_KINDS:
            p = npts.get(point)
            if p is None:
                return False, "requires_unsatisfied_natal", {"req": req, "point": None}
            if kind == "natal_point_sign":
                ok = p.get("sign") == req.get("sign")
                fact = {"req": req, "sign": p.get("sign")}
            elif kind == "natal_point_aspect":
                other, asp = req.get("other"), req.get("aspect")
                types = [asp] if asp else ["conjunction", "sextile", "square", "trine",
                                           "opposition"]
                ok = any(_relation_exists(natal, point, other, t, "modern") for t in types)
                fact = {"req": req}
            elif kind == "natal_point_retrograde":
                ok = bool(p.get("retrograde"))
                fact = {"req": req, "retrograde": p.get("retrograde")}
            else:  # natal_point_dignity
                key = DIGNITY_TO_CLASSIFICATION.get(req.get("dignity"))
                cls = p.get("classifications") or {}
                ok = bool(key) and cls.get(key) is True
                fact = {"req": req}
            if not ok:
                return False, "requires_unsatisfied_natal", fact
        elif kind in _RELOC_KINDS:
            if relocated is None:
                return False, "requires_needs_relocated_chart", {"req": req}
            p = rpts.get(point)
            house = ((p or {}).get("sector") or {}).get("placidus")
            ok = (house == req.get("house")) if kind == "relocated_point_house" else (house in ANGULAR)
            if not ok:
                return False, "requires_unsatisfied_relocated", {"req": req, "house": house}
        elif kind in _EXISTENCE_KINDS:
            if kind == "point_house" and skip_house_of and point == skip_house_of:
                continue
            ok, reason = _requirement_satisfiable(req, natal, npts)
            if not ok:
                return False, "requires_unsatisfied_natal", {"req": req, "reason": reason}
        else:
            return False, "requires_unsupported_kind", {"req": req}
    return True, None, None


# ---------------------------------------------------------------------------
# Line selection (spec 03 §3)
# ---------------------------------------------------------------------------

def select_lines(lines_near: list[dict]) -> tuple[str, list[dict], list[tuple[dict, str]]]:
    """-> (rule, selected lines, [(line, drop_reason)])."""
    drops: list[tuple[dict, str]] = []
    read = []
    for ln in lines_near:
        if not ln.get("read_in_v1"):
            drops.append((ln, "body_out_of_scope"))
        else:
            read.append(ln)
    ts = [ln for ln in read if ln["tier"] in ("tight", "strong")]
    wide = [ln for ln in read if ln["tier"] == "wide"]
    if ts:
        chosen = ts[:ACG_MAX_LINES_READ]
        drops += [(ln, "line_budget_exceeded") for ln in ts[ACG_MAX_LINES_READ:]]
        drops += [(ln, "tier_wide_not_selected") for ln in wide]
        return "tight_strong", chosen, drops
    if wide:
        drops += [(ln, "tier_wide_not_selected") for ln in wide[1:]]
        return "nearest_wide", wide[:1], drops
    return "none", [], drops


def line_key(ln: dict) -> str:
    return f"{ln['body']}|{ln['angle']}"


def lines_display(locate: dict, selected_keys: set[str]) -> list[dict]:
    """07 §4: every read line within 1,000 km, as UI data (distances rounded to 10 km)."""
    out = []
    for ln in locate.get("lines_near", []):
        if not ln.get("read_in_v1"):
            continue
        d = float(ln["distance_km"])
        rounded: Any = "<10" if d < 10.0 else int((d / 10.0) + 0.5) * 10
        a_tr, a_en = ANGLE_LABELS[ln["angle"]]
        t_tr, t_en = TIER_LABELS[ln["tier"]]
        out.append({"body": ln["body"], "angle": ln["angle"],
                    "planet_tr": PLANET_TR[ln["body"]], "planet_en": BODY_DISPLAY[ln["body"]],
                    "angle_label_tr": a_tr, "angle_label_en": a_en,
                    "distance_km_rounded": rounded, "tier": ln["tier"],
                    "tier_label_tr": t_tr, "tier_label_en": t_en,
                    "read_in_prose": line_key(ln) in selected_keys})
    return out


# ---------------------------------------------------------------------------
# The grounding
# ---------------------------------------------------------------------------

def _with_evidence(record: dict, evidence: dict) -> dict:
    r = copy.deepcopy(record)
    r["acg_evidence"] = evidence
    return r


def _absent(locate: Optional[dict], reason: str, detail: Optional[str] = None) -> dict:
    place = (locate or {}).get("place") or {}
    return {"schema_version": SCHEMA_VERSION, "status": "absent",
            "absence": {"reason": reason, "detail": detail},
            "place": {"name": place.get("name"), "name_tr": place.get("name_tr")},
            "selection": {"rule": "none", "lines": []}, "bundles": [], "gaps": [],
            "counts": {}, "sensitivity_high_ids": [], "goal_contributors": {},
            "goal_records": [], "lines_display": []}


def ground_acg(natal: dict, relocated: Optional[dict], locate: dict,
               acg_corpus: Optional[list[dict]], main_corpus: list[dict], *,
               acg: Optional[dict] = None, affinity: Optional[dict] = None,
               parans: Optional[dict] = None) -> tuple[dict, dict]:
    """-> (acg_principles.json payload, acg_drop_report.json). ``acg`` and ``affinity``
    enable the v3 goal block (07 §7); without them it is left empty."""
    drops: list[DropLog] = []

    def drop(pid: str, reason: str, about: Optional[dict] = None, fact: Any = None) -> None:
        assert reason in DROP_REASONS, reason
        drops.append(DropLog(pid, "ACG", reason, about or {}, fact))

    def report(payload: dict) -> dict:
        return {"reading": "acg", "house_policy": "placidus",
                "kept": payload["counts"].get("records_kept", 0), "dropped": len(drops),
                "drops_by_reason": dict(Counter(d.reason for d in drops)),
                "drop_log": [d.as_dict() for d in drops]}

    if locate.get("status") != "ok":
        ab = locate.get("absence") or {}
        p = _absent(locate, ab.get("reason", "locate_absent"), ab.get("detail"))
        return p, report(p)
    if acg_corpus is None:
        p = _absent(locate, "acg_corpus_missing")
        return p, report(p)

    idx = _Index(acg_corpus, main_corpus)
    for r in idx.out_of_scope:
        drop(r["principle_id"], "scope_not_v1", r.get("about"), {"acg_scope": r.get("acg_scope")})

    rule, selected, line_drops = select_lines(locate.get("lines_near", []))
    for ln, reason in line_drops:
        drop(f"line:{line_key(ln)}", reason, {"body": ln["body"], "angle": ln["angle"]},
             {"tier": ln["tier"], "distance_km": ln["distance_km"]})

    gaps = ["rising_sign_records_absent"]
    reloc = locate.get("relocation") or {}
    if relocated is None:
        gaps.append(f"relocation_absent:{((reloc.get('absence') or {}).get('reason')) or 'unknown'}")

    bundles: list[dict] = []
    counts = Counter()
    line_bodies: set[str] = set()

    # ---- stream A --------------------------------------------------------
    for ln in selected:
        body, angle = ln["body"], ln["angle"]
        line_bodies.add(body)
        ev = {"kind": "line", "body": body, "angle": angle, "tier": ln["tier"],
              "distance_km": ln["distance_km"]}
        recs: list[dict] = []
        frame = idx.frame.get(angle)
        if frame is not None:
            recs.append(_with_evidence(frame, {**ev, "source": "A3"}))
        a1_kept = []
        for r in idx.line.get((body, angle), []):
            ok, reason, fact = eval_requires(r, natal, relocated)
            if ok:
                a1_kept.append(_with_evidence(r, {**ev, "source": "A1"}))
            else:
                drop(r["principle_id"], reason, r.get("about"), fact)
        recs += a1_kept
        a2_kept = []
        for r in idx.general.get(body, []):
            ok, reason, fact = eval_requires(r, natal, relocated)
            if ok:
                a2_kept.append(_with_evidence(r, {**ev, "source": "A2"}))
            else:
                drop(r["principle_id"], reason, r.get("about"), fact)
        recs += a2_kept
        display = BODY_DISPLAY[body]
        a4_pool = idx.pih.get((display, ANGLE_HOUSE[angle]), [])
        a4_kept = []
        slots = max(0, A4_FILL_TO - len(a1_kept))
        for r in a4_pool:
            if len(a4_kept) >= slots:
                drop(r["principle_id"], "fallback_not_needed", r.get("about"),
                     {"a1_kept": len(a1_kept), "line": f"{body}|{angle}"})
                continue
            ok, reason, fact = eval_requires(r, natal, relocated, skip_house_of=display)
            if ok:
                a4_kept.append(_with_evidence(r, {**ev, "source": "A4"}))
            else:
                drop(r["principle_id"], reason, r.get("about"), fact)
        recs += a4_kept
        counts["a1"] += len(a1_kept)
        counts["a2"] += len(a2_kept)
        counts["a4"] += len(a4_kept)
        bundles.append({"factor": f"line:{body}|{angle}", "tier": ln["tier"],
                        "distance_km": ln["distance_km"], "records": recs})
    counts["lines_kept"] = len(selected)

    # ---- stream B --------------------------------------------------------
    house_bundles: list[dict] = []
    if relocated is not None:
        order = {b: i for i, b in enumerate(BODY_ORDER)}
        shifts = []
        for d in locate.get("house_diff", []):
            if d["body"] in line_bodies:
                drop(f"house:{d['body']}|{d['relocated_house']}", "covered_by_line",
                     {"body": d["body"]}, d)
                continue
            shifts.append(d)
        shifts.sort(key=lambda d: (not d["angular_after"], d["body"] not in PERSONAL_BODIES,
                                   order[d["body"]]))
        for d in shifts[ACG_MAX_HOUSE_SHIFTS:]:
            drop(f"house:{d['body']}|{d['relocated_house']}", "house_budget_exceeded",
                 {"body": d["body"]}, d)
        for d in shifts[:ACG_MAX_HOUSE_SHIFTS]:
            display = BODY_DISPLAY[d["body"]]
            cands = idx.pih.get((display, d["relocated_house"]), [])
            res = ground(cands, relocated, reading="natal", house_policy="placidus")
            for dl in res.drops:
                drop(dl.principle_id, "requires_unsatisfied_relocated", dl.about,
                     dl.relevant_chart_fact)
            ev = {"kind": "house_shift", "body": d["body"], "natal_house": d["natal_house"],
                  "relocated_house": d["relocated_house"]}
            recs = [_with_evidence(r, ev) for r in res.kept]
            if recs:
                house_bundles.append({"factor": f"house:{d['body']}|{d['relocated_house']}",
                                      "natal_house": d["natal_house"],
                                      "relocated_house": d["relocated_house"],
                                      "angular_after": d["angular_after"], "records": recs})
    bundles += house_bundles
    counts["house_shifts_kept"] = len(house_bundles)

    # ---- stream P: near parans (spec 10 §7) ------------------------------
    paran_bundles: list[dict] = []
    for pn in locate.get("parans_near", []):
        a, b = pn["a"]["body"], pn["b"]["body"]
        ev = {"kind": "paran", "id": pn["id"], "pair": pn["pair"], "bodies": [a, b],
              "dlat_km": pn["dlat_km"]}
        recs = []
        for r in idx.paran.get(pn["pair"], []):
            ok, reason, fact = eval_requires(r, natal, relocated)
            if ok:
                recs.append(_with_evidence(r, {**ev, "source": "P1"}))
            else:
                drop(r["principle_id"], reason, r.get("about"), fact)
        if not recs:                        # fallback: both synopses + the crossings method
            for body in (a, b):
                for r in idx.general.get(body, []):
                    ok, _, _ = eval_requires(r, natal, relocated)
                    if ok:
                        recs.append(_with_evidence(r, {**ev, "source": "P2"}))
            if "acg-method-crossings" in idx.method:
                recs.append(_with_evidence(idx.method["acg-method-crossings"],
                                           {**ev, "source": "P3"}))
        paran_bundles.append({"factor": f"paran:{pn['id']}", "pair": pn["pair"],
                              "bodies": [a, b], "records": recs})
    bundles += paran_bundles
    counts["parans_kept"] = len(paran_bundles)

    # ---- stream C --------------------------------------------------------
    method_ids = list(METHOD_ALWAYS)
    method_ids.append("acg-method-orb-distance" if selected else "acg-method-no-influence")
    if house_bundles:
        method_ids.append("acg-method-relocated-chart")
    method_recs = [_with_evidence(idx.method[m], {"kind": "method"})
                   for m in method_ids if m in idx.method]
    bundles.append({"factor": "method", "records": method_recs})

    # ---- v3: goal contributors (07 §7) -----------------------------------
    goal_contributors: dict = {}
    goal_records: list[dict] = []
    if acg is not None and affinity is not None and acg.get("status") == "ok":
        import acg_goals  # noqa: WPS433
        place = locate["place"]
        scores = acg_goals.score_point(acg, place["lat"], place["lon"], affinity, parans)
        in_bundles = {r["principle_id"] for b in bundles for r in b["records"]}
        tier_of = {line_key(ln): ln for ln in locate.get("lines_near", [])}
        loaded: set[str] = set()
        for goal in GOAL_ORDER:
            sc = scores[goal]
            kept_ids, dropped_ids = [], []
            for rid in sc["contributors"]:
                rec = idx.by_id.get(rid)
                if rec is None:
                    dropped_ids.append(rid)
                    continue
                ok, reason, fact = eval_requires(rec, natal, relocated)
                if not ok:
                    dropped_ids.append(rid)
                    continue
                kept_ids.append(rid)
                if rid not in in_bundles and rid not in loaded:
                    # which line brought it in: the strongest contributing line of this cell
                    src = next((c for c in sc["contributions"]
                                if abs(c["contribution"]) >= 0.05 and rid in
                                acg_goals.cell_contributors(affinity, c["body"], c["angle"], goal)),
                               None)
                    ln = tier_of.get(f"{src['body']}|{src['angle']}") if src else None
                    psrc = None if src else next(
                        (c for c in sc.get("paran_contributions", [])
                         if abs(c["contribution"]) >= 0.05 and rid in
                         acg_goals.paran_contributors(affinity, c["pair"], goal)), None)
                    goal_records.append(_with_evidence(rec, {
                        "kind": "goal", "body": src["body"] if src else None,
                        "angle": src["angle"] if src else None,
                        "tier": ln["tier"] if ln else ("paran" if psrc else None),
                        "distance_km": ln["distance_km"] if ln else None,
                        "paran": psrc["id"] if psrc else None}))
                    loaded.add(rid)
            goal_contributors[goal] = {
                "score": round(sc["S"], 6), "P": round(sc["P"], 6), "N": round(sc["N"], 6),
                "band": sc["band"], "contributors": kept_ids,
                "contributors_dropped_by_requires": dropped_ids,
                "contributions": [{"body": c["body"], "angle": c["angle"],
                                   "contribution": round(c["contribution"], 6),
                                   "distance_km": round(c["distance_km"], 1)}
                                  for c in sc["contributions"] if c["contribution"] != 0.0],
                "paran_contributions": [{"id": c["id"], "pair": c["pair"],
                                         "contribution": round(c["contribution"], 6),
                                         "dlat_km": c["dlat_km"]}
                                        for c in sc.get("paran_contributions", [])
                                        if c["contribution"] != 0.0],
            }

    all_kept = [r for b in bundles for r in b["records"]]
    counts["records_kept"] = len(all_kept)
    sens = sorted({r["principle_id"] for r in all_kept + goal_records
                   if r.get("sensitivity") == "high"})
    place = locate.get("place") or {}
    selected_keys = {line_key(ln) for ln in selected}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "ok",
        "absence": None,
        "place": {"name": place.get("name"), "name_tr": place.get("name_tr")},
        "selection": {"rule": rule, "lines": [line_key(ln) for ln in selected]},
        "bundles": bundles,
        "gaps": gaps,
        "counts": dict(counts),
        "sensitivity_high_ids": sens,
        "goal_contributors": goal_contributors,
        "goal_records": goal_records,
        "lines_display": lines_display(locate, selected_keys),
        "parans_display": locate.get("parans_display", []),
    }
    return payload, report(payload)


def main() -> None:
    ap = argparse.ArgumentParser(description="ACG grounding (spec 03).")
    ap.add_argument("--chart", required=True)
    ap.add_argument("--relocated", default=None)
    ap.add_argument("--locate", required=True)
    ap.add_argument("--acg", default=None, help="acg.json (enables the goal block)")
    ap.add_argument("--out", default="acg_principles.json")
    ap.add_argument("--drop-report", default="acg_drop_report.json")
    args = ap.parse_args()
    natal = load_json(args.chart)
    relocated = load_json(args.relocated) if args.relocated else None
    locate = load_json(args.locate)
    acg = load_json(args.acg) if args.acg else None
    aff = None
    if acg is not None:
        import acg_goals
        aff = acg_goals.load_affinity() if os.path.exists(acg_goals.AFFINITY_PATH) else None
    ok, _ = corpus_ok()
    payload, rep = ground_acg(natal, relocated, locate,
                              load_json(ACG_CORPUS_PATH) if ok else None,
                              load_json(MAIN_CORPUS_PATH), acg=acg, affinity=aff)
    for path, obj in ((args.out, payload), (args.drop_report, rep)):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
    print(f"status={payload['status']} rule={payload['selection']['rule']} "
          f"kept={payload['counts'].get('records_kept', 0)} dropped={len(rep['drop_log'])}")


if __name__ == "__main__":
    main()
