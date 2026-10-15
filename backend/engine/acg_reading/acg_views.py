#!/usr/bin/env python3
"""acg_views.py — the model side of the country / region view (ACG 07 §6.3) and the
"Where Should I Go?" recommender (ACG 09 §2, §4), plus their run-stage wiring for
run_acg.py.

The numbers, bands, rankings and orderings all come from Astrocartography/
acg_recommend.py (deterministic). The model only explains them, one unit per item,
using only that item's contributing records; band labels are prepended in code;
item order and membership are never touched by the model (RV3 by construction).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "Astrocartography"),
           os.path.join(_ROOT, "principles_grounding")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ar_prompts as P  # noqa: E402
from ar_routing import _slim  # noqa: E402
from ar_sections import ANGLE_PLAIN, FOOTER, PLANET_NAMES  # noqa: E402
from ar_validate import planets_named, text_problems, unit_text, word_count  # noqa: E402
from acg_constants import BANDS, GOALS, GOAL_ORDER  # noqa: E402

METHOD_INTRO = ("acg-method-ambivalence", "acg-method-natal-modifies-response",
                "acg-method-orb-distance")
NO_INFLUENCE = "acg-method-no-influence"
TOL = 0.20
LENGTHS = {"intro": (50, 80), "city": (40, 70), "region": (30, 50), "country": (40, 70),
           "turkey_intro": (30, 50), "area_overview": (90, 140)}
RV4_TR = ["en iyi yer kesinlikle", "garantili"]
RV4_EN = ["the best place for sure", "guaranteed"]


def _bounds(kind: str) -> tuple[int, int]:
    lo, hi = LENGTHS[kind]
    return int(lo * (1 - TOL)), int(round(hi * (1 + TOL)))


# ---------------------------------------------------------------------------
# corpus access + requires filter (the ground_acg evaluator, natal only)
# ---------------------------------------------------------------------------

class Corpus:
    def __init__(self, natal: dict):
        import ground_acg as ga
        self.ga = ga
        self.natal = natal
        self.by_id = {r["principle_id"]: r for r in ga.load_json(ga.ACG_CORPUS_PATH)}

    def ok(self, rid: str) -> bool:
        r = self.by_id.get(rid)
        if r is None:
            return False
        ok, _, _ = self.ga.eval_requires(r, self.natal, None)
        return ok

    def slim(self, rid: str) -> dict:
        return _slim(self.by_id[rid])

    def frame(self, angle: str) -> Optional[str]:
        rid = f"acg-angle-{angle.lower()}"
        return rid if rid in self.by_id else None

    def general(self, body: str) -> list[str]:
        name = PLANET_NAMES[body][1]
        return sorted(rid for rid, r in self.by_id.items()
                      if r.get("acg_scope") == "planet_general"
                      and (r.get("about") or {}).get("planet") == name and self.ok(rid))


# ---------------------------------------------------------------------------
# generic unit writing: draft -> translate -> detox -> validate
# ---------------------------------------------------------------------------

UNIT_BRIEF = """You write short explanations for an astrocartography result screen. Each unit
explains ONE item using ONLY that unit's principles (cite their ids per sentence). The
computed assessment (band) is fixed and printed before your text: never restate or
contradict it. Explain WHY through the planet's theme and where it shows up (plain words
given), e.g. "Jüpiter'in teması burada görünürlük ve mesleki büyüme alanını öne çıkarır".
If "has_tradeoff" is true, ONE sentence must name the demanding side and cite a principle
marked challenging or mixed. Name places exactly as given (Turkish name)."""


def _write_units(gen, units: list[dict], place_ctx: dict) -> tuple[dict, dict]:
    """units: [{unit_id, kind, brief, principles, ...}] -> (tr units, en units)."""
    if not units:
        return {}, {}
    payload = [{k: v for k, v in u.items() if k not in ("kind",)} for u in units]
    lens = {u["unit_id"]: LENGTHS[u["kind"]] for u in units}
    user = f"""{UNIT_BRIEF}

Word counts (Turkish): {json.dumps(lens)}  (each unit: that many words in total).

UNITS:
{json.dumps(payload, ensure_ascii=False, indent=1)}

Return ONLY: {{"units": [{{"unit_id": "...", "sentences": [{{"text": "...", "ids": ["..."]}}]}}]}}"""
    tr = gen.draft("views", P.CONTRACT, user)
    en = gen.translate_units("views", tr, place_ctx) if tr else {}
    for lang, secs in (("tr", tr), ("en", en)):
        for uid, u in list(secs.items()):
            probs = text_problems(unit_text(u), lang) + _rv4(unit_text(u), lang)
            if probs:
                secs[uid] = gen.detox_unit(u, lang, probs)
    return tr, en


def _rv4(text: str, lang: str) -> list[str]:
    terms = RV4_TR if lang == "tr" else RV4_EN
    low = (text or "").casefold()
    return [f"RV4 certainty superlative {t!r}" for t in terms if t in low]


def validate_units(units: list[dict], tr: dict, en: dict, polarity: dict) -> list[str]:
    """RV1–RV4 + AV1/2/8/10 + lengths + planets ⊆ the item's lines."""
    errors = []
    for u in units:
        uid = u["unit_id"]
        pool = {p["id"] for p in u["principles"]}
        for lang, secs in (("tr", tr), ("en", en)):
            unit = secs.get(uid)
            if not unit or not unit_text(unit):
                errors.append(f"[{lang}] unit {uid} missing or empty")
                continue
            text = unit_text(unit)
            errors += [f"{p} in [{lang}] {uid}" for p in text_problems(text, lang)]
            errors += [f"{p} in [{lang}] {uid}" for p in _rv4(text, lang)]
            extra = planets_named(text, lang) - set(u.get("allowed_planets", []))
            if extra:
                errors.append(f"[{lang}] {uid} names planet(s) {sorted(extra)} not in its lines")
            if u.get("must_name") and lang == "tr" and u["must_name"].casefold() not in \
                    text.casefold():
                errors.append(f"[tr] {uid} does not name {u['must_name']!r}")
        unit = tr.get(uid) or {"sentences": []}
        ids = [i for s in unit["sentences"] for i in s.get("ids", [])]
        if not ids:
            errors.append(f"RV1 {uid} has no trace")
        for i in ids:
            if i not in pool:
                errors.append(f"RV1 {uid} traces {i!r} outside its contributors/frame")
        if u.get("has_tradeoff") and not any(polarity.get(i) in ("challenging", "mixed")
                                             for i in ids):
            errors.append(f"RV2 {uid} has a tradeoff but traces no challenging/mixed record")
        lo, hi = _bounds(u["kind"])
        n = word_count(unit_text(unit))
        if not (lo <= n <= hi):
            errors.append(f"length {uid}: {n} words (allowed {lo}–{hi})")
    return errors


def _labelled(band: Optional[str], tr_u: dict, en_u: dict) -> dict:
    if band is None:
        return {"tr": unit_text(tr_u or {}), "en": unit_text(en_u or {})}
    lt, le = BANDS[band]
    return {"tr": f"{lt}. {unit_text(tr_u or {})}".strip(),
            "en": f"{le}. {unit_text(en_u or {})}".strip()}


def _trace(u: dict) -> list[str]:
    return sorted({i for s in (u or {}).get("sentences", []) for i in s.get("ids", [])})


# ---------------------------------------------------------------------------
# item -> unit
# ---------------------------------------------------------------------------

def _line_ctx(line: Optional[dict]) -> Optional[dict]:
    if not line:
        return None
    if line.get("kind") == "paran":
        return {"planets": [PLANET_NAMES[b][0] for b in line["bodies"]],
                "kind": "a softer background band where both planets combine"}
    return {"planet": PLANET_NAMES[line["body"]][0],
            "where_it_shows_up": ANGLE_PLAIN[line["angle"]][0]}


def _bodies_of(ln: dict) -> list[str]:
    return list(ln["bodies"]) if ln.get("kind") == "paran" else [ln["body"]]


def item_unit(item: dict, kind: str, goal: str, corpus: Corpus, uid: str) -> dict:
    ids = [c for c in item["contributors"] if corpus.ok(c)]
    dom = item.get("dominant_line")
    frame = corpus.frame(dom["angle"]) if dom and dom.get("kind") != "paran" else None
    if frame:
        ids.append(frame)
    lines = item.get("supporting_lines", []) + item.get("challenging_lines", [])
    unit = {"unit_id": uid, "kind": kind, "place": item["name_tr"],
            "goal": GOALS[goal][0], "goal_definition": GOALS[goal][2],
            "computed_band": BANDS[item["band"]][0], "has_tradeoff": item["has_tradeoff"],
            "dominant_line": _line_ctx(dom),
            "other_lines": [_line_ctx(ln) for ln in lines if ln is not dom][:3],
            "principles": [corpus.slim(i) for i in dict.fromkeys(ids)],
            "allowed_planets": sorted({b for ln in lines for b in _bodies_of(ln)}),
            "must_name": item["name_tr"]}
    if kind == "country" and item.get("best_region"):
        unit["mention_best_region"] = item["best_region"]["name_tr"]
    if kind == "country" and item.get("best_cities"):
        unit["mention_best_city"] = item["best_cities"][0]["name_tr"]
    return unit


def _polarity(corpus: Corpus) -> dict:
    return {rid: r.get("polarity") for rid, r in corpus.by_id.items()}


# ---------------------------------------------------------------------------
# free text -> goal (09 §2)
# ---------------------------------------------------------------------------

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {"goal": {"type": ["string", "null"], "enum": list(GOAL_ORDER) + [None]},
                   "confidence": {"type": "number"}},
    "required": ["goal", "confidence"],
}


def classify_goal(text: str, gen) -> dict:
    table = "\n".join(f"- {g}: {tr} / {en} — {d}" for g, (tr, en, d) in GOALS.items())
    system = ("You map a user's question about WHERE to live, travel or go to exactly one "
              "life goal from a closed list, or null if it fits none or is not about "
              "choosing a place for a life goal. Return JSON only.")
    user = f"""GOALS:
{table}

QUESTION: {json.dumps(text, ensure_ascii=False)}

Return {{"goal": "<one goal key>" or null, "confidence": <0..1>}}."""
    data = gen._call_cheap(system, user, max_tokens=256, label="acg-classify",
                           schema=CLASSIFY_SCHEMA)
    goal, conf = data.get("goal"), float(data.get("confidence") or 0.0)
    if goal not in GOALS or conf < 0.6:
        return {"status": "needs_goal", "goal": None, "confidence": conf,
                "options": [{"goal": g, "label_tr": v[0], "label_en": v[1]}
                            for g, v in GOALS.items()]}
    return {"status": "ok", "goal": goal, "confidence": conf}


# ---------------------------------------------------------------------------
# recommend (09)
# ---------------------------------------------------------------------------

def recommendation_units(ranking: dict, corpus: Corpus) -> list[dict]:
    goal = ranking["goal"]
    units = [{"unit_id": "intro", "kind": "intro", "goal": GOALS[goal][0],
              "goal_definition": GOALS[goal][2],
              "brief_extra": "Introduce the result list: how to read it, ambivalence, "
                             "that the whole birth chart shapes the response, and that "
                             "places closer to a line are felt more.",
              "has_tradeoff": False, "allowed_planets": [],
              "principles": [corpus.slim(i) for i in METHOD_INTRO if i in corpus.by_id]}]
    for kind, key in (("city", "cities"), ("region", "regions"), ("country", "countries")):
        for n, item in enumerate(ranking.get(key, [])):
            units.append(item_unit(item, kind, goal, corpus, f"{key}:{n}"))
    tr = ranking.get("turkey")
    if tr is not None:
        for n, item in enumerate(tr["cities"]):
            units.append(item_unit(item, "city", goal, corpus, f"turkey.cities:{n}"))
        for n, item in enumerate(tr["regions"]):
            units.append(item_unit(item, "region", goal, corpus, f"turkey.regions:{n}"))
        if tr["none_eligible"]:
            best = tr.get("best_available")
            pids = [NO_INFLUENCE] + ([c for c in best["contributors"] if corpus.ok(c)]
                                     if best else [])
            units.append({"unit_id": "turkey.intro", "kind": "turkey_intro",
                          "goal": GOALS[goal][0],
                          "brief_extra": "Say plainly that no place in Turkey stands out for "
                                         "this goal in this chart"
                                         + (f"; then describe the closest option, "
                                            f"{best['name_tr']}, honestly as it is."
                                            if best else "."),
                          "has_tradeoff": bool(best and best["has_tradeoff"]),
                          "allowed_planets": sorted({b for ln in
                                                     (best or {}).get("supporting_lines", [])
                                                     + (best or {}).get("challenging_lines", [])
                                                     for b in _bodies_of(ln)}),
                          "principles": [corpus.slim(i) for i in dict.fromkeys(pids)
                                         if i in corpus.by_id]})
        else:
            units.append({"unit_id": "turkey.intro", "kind": "turkey_intro",
                          "goal": GOALS[goal][0],
                          "brief_extra": "Introduce the places in Turkey listed below.",
                          "has_tradeoff": False, "allowed_planets": [],
                          "principles": [corpus.slim(i) for i in METHOD_INTRO
                                         if i in corpus.by_id]})
    return units


def _rounded(km: float):
    return "<10" if km < 10 else int(km / 10 + 0.5) * 10


def _public_line(dom: dict) -> dict:
    if dom.get("kind") == "paran":
        return {"kind": "paran", "bodies": dom["bodies"], "pair": dom["pair"],
                "distance_km_rounded": _rounded(dom["dlat_km"])}
    return {"kind": "line", "body": dom["body"], "angle": dom["angle"],
            "distance_km_rounded": _rounded(dom["distance_km"])}


def _public(item: dict, texts: dict, trace: list[str]) -> dict:
    dom = item.get("dominant_line")
    out = {"id": item.get("id"), "name": item["name"], "name_tr": item["name_tr"],
           "country": item.get("country"), "band": item["band"],
           "band_label_tr": BANDS[item["band"]][0], "band_label_en": BANDS[item["band"]][1],
           "S": item["S"], "P": item["P"], "N": item["N"],
           "dominant_line": None if not dom else _public_line(dom),
           "supporting_lines": item["supporting_lines"],
           "challenging_lines": item["challenging_lines"],
           "has_tradeoff": item["has_tradeoff"], "contributors": item["contributors"],
           "text_tr": texts.get("tr", ""), "text_en": texts.get("en", ""), "trace": trace}
    for k in ("best_cities", "best_region"):
        if k in item:
            out[k] = item[k]
    return out


def assemble_recommendation(ranking: dict, tr: dict, en: dict) -> dict:
    goal = ranking["goal"]
    status = "thin_result" if ranking["thin_result"] else "ok"

    def items(key, prefix=None):
        prefix = prefix or key
        return [_public(it, _labelled(it["band"], tr.get(f"{prefix}:{n}"), en.get(f"{prefix}:{n}")),
                        _trace(tr.get(f"{prefix}:{n}")))
                for n, it in enumerate(ranking.get(key, []) if "." not in prefix
                                       else ranking["turkey"][key])]
    out = {"schema_version": "acg-recommend-1", "goal": goal,
           "goal_label_tr": GOALS[goal][0], "goal_label_en": GOALS[goal][1],
           "scope": ranking["scope"], "status": status,
           "intro": {**_labelled(None, tr.get("intro"), en.get("intro")),
                     "trace": _trace(tr.get("intro"))},
           "cities": items("cities"), "regions": items("regions"),
           "countries": items("countries"),
           "footer": FOOTER}
    if "turkey" in ranking:
        t = ranking["turkey"]
        out["turkey"] = {"intro": {**_labelled(None, tr.get("turkey.intro"), en.get("turkey.intro")),
                                   "trace": _trace(tr.get("turkey.intro"))},
                         "cities": items("cities", "turkey.cities"),
                         "regions": items("regions", "turkey.regions"),
                         "none_eligible": t["none_eligible"]}
        if t.get("best_available"):
            b = t["best_available"]
            out["turkey"]["best_available"] = _public(b, _labelled(b["band"], None, None), [])
    return out


# ---------------------------------------------------------------------------
# area overview (07 §6.3)
# ---------------------------------------------------------------------------

def area_units(view: dict, corpus: Corpus) -> list[dict]:
    ids = ["acg-method-ambivalence", "acg-method-natal-modifies-response",
           "acg-method-degree-of-expression"]
    ids.append("acg-method-orb-distance" if view["top_cover_lines"] else NO_INFLUENCE)
    planets = []
    lines_ctx = []
    for ln in view["top_cover_lines"]:
        planets.append(ln["body"])
        lines_ctx.append(_line_ctx(ln))
        fr = corpus.frame(ln["angle"])
        if fr:
            ids.append(fr)
        ids += corpus.general(ln["body"])
    bands = {GOALS[g][0]: BANDS[b["band"]][0] for g, b in view["bands"].items()}
    extra = ("Summarise which themes the planetary lines over this area bring forward "
             "and what that means, with ambivalence.")
    if view.get("varies_by_region"):
        hl = "; ".join(f"{GOALS[h['goal']][0]}: {h['name_tr']}" for h in view["varies_highlight"])
        extra += (f" IMPORTANT: say that the picture varies by region, and name the best "
                  f"region for these goals: {hl}.")
    return [{"unit_id": "place_overview", "kind": "area_overview", "place": view["name_tr"],
             "lines_over_area": lines_ctx, "goal_assessments": bands, "brief_extra": extra,
             "has_tradeoff": False, "allowed_planets": sorted(set(planets)),
             "must_name": view["name_tr"],
             "principles": [corpus.slim(i) for i in dict.fromkeys(ids) if i in corpus.by_id]}]


# ---------------------------------------------------------------------------
# run-stage wiring (called by run_acg.py)
# ---------------------------------------------------------------------------

def _place_ctx(name_tr: str, name: str) -> dict:
    return {"name_tr": name_tr, "name": name}


def _write_and_validate(units, gen, place_ctx, corpus):
    tr, en = _write_units(gen, units, place_ctx)
    errors = validate_units(units, tr, en, _polarity(corpus))
    return tr, en, errors


def run_area(mode, request, acg, aff, prod, stages, manifest, write, finish, *,
             dry_run, models, make_generator: Callable):
    import acg_recommend as rec
    rec.set_parans(prod.get("parans"))
    code = request["country"].upper() if mode == "country" else request["region"]
    t0 = time.monotonic()
    view = rec.area_view(mode, code, acg, prod["goal_scan"], aff)
    stages.record("aggregate", view["status"] if view["status"] == "ok"
                  else f"absent:{view['absence']['reason']}", None, t0)
    name = f"{mode}_{code}.json"
    if view["status"] != "ok":
        write(name, view)
        return finish("absent")
    manifest["place"] = {"name": view["name"], "name_tr": view["name_tr"], "kind": mode,
                         "code": code}
    corpus = Corpus(prod["natal"])
    units = area_units(view, corpus)
    if dry_run:
        view["dry_run_units"] = units
        write(name, view)
        stages.record("reading", "dry_run", name)
        return finish("ok")
    gen = make_generator(models)
    t0 = time.monotonic()
    tr, en, errors = _write_and_validate(units, gen, _place_ctx(view["name_tr"], view["name"]),
                                         corpus)
    view["place_overview"] = {"tr": unit_text(tr.get("place_overview", {})),
                              "en": unit_text(en.get("place_overview", {})),
                              "trace": _trace(tr.get("place_overview"))}
    view["footer"] = FOOTER
    view["validation"] = {"errors": errors, "passed": not errors, "usage": gen.usage}
    if errors:
        write(f"{mode}_{code}.rejected.json", view)
        stages.record("reading", "failed", None, t0, error="; ".join(errors[:6]))
        return finish("failed")
    write(name, view)
    stages.record("reading", "ok", name, t0)
    return finish("ok")


def run_recommend(request, acg, aff, prod, stages, manifest, write, finish, *,
                  dry_run, models, make_generator: Callable):
    import acg_recommend as rec
    goal = request.get("recommend")
    scope = (request.get("scope") or "world")
    scope = scope if scope == "world" else scope.upper()
    if not goal and request.get("query_text"):
        if dry_run:
            stages.record("classify", "dry_run", None)
            write("recommend_needs_goal.json", {"status": "needs_goal", "dry_run": True})
            return finish("ok")
        cls = classify_goal(request["query_text"], make_generator(models))
        stages.record("classify", cls["status"], None)
        if cls["status"] != "ok":
            write("recommend_needs_goal.json", {"schema_version": "acg-recommend-1", **cls,
                                                "query_text": request["query_text"]})
            return finish("ok")
        goal = cls["goal"]
    if goal == "overall":
        import ar_overall
        return ar_overall.run(request, acg, aff, prod, stages, manifest, write, finish,
                              dry_run=dry_run, models=models, make_generator=make_generator,
                              scope=scope)
    manifest["goal"], manifest["scope"] = goal, scope
    # v4 (spec 11): line-first over reviewed, viable destinations when the data exists
    if os.path.exists(os.path.join(_ROOT, "Astrocartography", "destinations.json")):
        import ar_recommend
        return ar_recommend.run(request, acg, aff, prod, stages, manifest, write, finish,
                                dry_run=dry_run, models=models, make_generator=make_generator,
                                goal=goal, scope=scope)
    rec.set_parans(prod.get("parans"))
    t0 = time.monotonic()
    ranking = rec.rank(goal, scope, acg, prod["goal_scan"], aff)
    stages.record("recommend", "ok", None, t0)
    corpus = Corpus(prod["natal"])
    units = recommendation_units(ranking, corpus)
    name = f"recommend_{goal}_{scope}.json"
    if dry_run:
        out = assemble_recommendation(ranking, {}, {})
        out["dry_run_units"] = units
        write(name, out)
        stages.record("reading", "dry_run", name)
        return finish("ok")
    gen = make_generator(models)
    t0 = time.monotonic()
    tr, en, errors = _write_and_validate(units, gen, _place_ctx("", ""), corpus)
    out = assemble_recommendation(ranking, tr, en)
    out["validation"] = {"errors": errors, "passed": not errors, "usage": gen.usage}
    if errors:
        write(f"recommend_{goal}_{scope}.rejected.json", out)
        stages.record("reading", "failed", None, t0, error="; ".join(errors[:6]))
        return finish("failed")
    write(name, out)
    stages.record("reading", "ok", name, t0)
    return finish("ok")
