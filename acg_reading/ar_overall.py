#!/usr/bin/env python3
"""ar_overall.py — explanations and output for the "overall improvement" recommendation
(Astrocartography/acg_overall.py ranks; the model only explains).

Each place gets a deterministic label ("Supportive for 5 goals · challenging for 1") that
is printed before the text, and a 35–60 word explanation grounded ONLY in the records
behind its top supported goals (and its challenged goals, whose demanding side must be
named). Validation: RV1–RV4 + the text rules (acg_views.validate_units), with two
targeted repair rounds (ar_recommend.write_and_validate).

Outputs: recommend_overall_<scope>.json / .md (TR+EN) / .en.md / .tr.md
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Callable

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "Astrocartography")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import acg_views as V  # noqa: E402
import ar_recommend as R  # noqa: E402
from ar_sections import ANGLE_PLAIN, FOOTER, PLANET_NAMES  # noqa: E402
from ar_validate import unit_text  # noqa: E402
from acg_constants import GOALS, GOAL_ORDER  # noqa: E402

V.LENGTHS.update({"overall_place": (35, 60)})
TITLE = {"tr": "Genel Gelişim İçin Nereye Gitmeliyim?",
         "en": "Where Should I Go for Overall Growth?"}


def place_label(p: dict, lang: str) -> str:
    k, m = p["breadth"], p["strain"]
    if lang == "tr":
        s = f"{k} hedefte destekleyici"
        return s + (f" · {m} hedefte zorlayıcı" if m else "")
    s = f"Supportive for {k} goal{'s' if k != 1 else ''}"
    return s + (f" · challenging for {m}" if m else "")


def _goal_names(goals: list[str], lang: str) -> list[str]:
    i = 0 if lang == "tr" else 1
    return [GOALS[g][i] for g in goals]


def build_units(result: dict, corpus: "V.Corpus") -> list[dict]:
    units = [{"unit_id": "intro", "kind": "intro", "goal": "Genel gelişim (11 hedefin tamamı)",
              "brief_extra": "Introduce a list of places that support the person across many "
                             "life areas at once (not one single goal); ambivalence; the whole "
                             "birth chart shapes the response; places nearer a line feel it more.",
              "has_tradeoff": False, "allowed_planets": [],
              "principles": [corpus.slim(i) for i in V.METHOD_INTRO if i in corpus.by_id]}]

    def unit(p, uid):
        ids = [c for c in p["contributors"] if corpus.ok(c)]
        dom = p.get("dominant_line")
        if dom and dom.get("kind") == "line":
            fr = corpus.frame(dom["angle"])
            if fr:
                ids.append(fr)
        bodies = sorted({b for ln in p["lines"] for b in V._bodies_of(ln)})
        return {"unit_id": uid, "kind": "overall_place", "place": p["name_tr"],
                "computed_assessment": place_label(p, "tr"),
                "supported_goals": _goal_names(p["supported"][:4], "tr"),
                "challenged_goals": _goal_names(p["challenged"][:2], "tr"),
                "main_line": V._line_ctx(dom),
                "brief_extra": "Explain which life areas this place supports most (name 2–3 of "
                               "the supported goals) and through which planet themes; if any "
                               "goal is challenged, one sentence names that demanding side.",
                "has_tradeoff": p["has_tradeoff"], "allowed_planets": bodies,
                "must_name": p["name_tr"],
                "principles": [corpus.slim(i) for i in dict.fromkeys(ids)]}
    for n, p in enumerate(result["places"]):
        units.append(unit(p, f"places:{n}"))
    for n, p in enumerate((result.get("turkey") or {}).get("places", [])):
        units.append(unit(p, f"turkey.places:{n}"))
    return units


def _public(p: dict, tr: dict, en: dict, uid: str) -> dict:
    lt, le = place_label(p, "tr"), place_label(p, "en")
    dom = p.get("dominant_line")
    return {"id": p["id"], "name": p["name"], "name_tr": p["name_tr"], "country": p["country"],
            "size": p.get("size"), "overall": p["overall"], "breadth": p["breadth"],
            "strain": p["strain"], "label_tr": lt, "label_en": le,
            "supported_goals": p["supported"], "challenged_goals": p["challenged"],
            "mixed_goals": p["mixed"], "goals": p["goals"],
            "dominant_line": None if not dom else V._public_line(dom),
            "has_tradeoff": p["has_tradeoff"], "contributors": p["contributors"],
            "text_tr": f"{lt}. {unit_text(tr.get(uid) or {})}".strip(),
            "text_en": f"{le}. {unit_text(en.get(uid) or {})}".strip(),
            "trace": V._trace(tr.get(uid))}


def assemble(result: dict, tr: dict, en: dict) -> dict:
    out = {"schema_version": "acg-recommend-overall-1", "goal": "overall",
           "goal_label_tr": "Genel gelişim", "goal_label_en": "Overall growth",
           "scope": result["scope"], "status": "thin_result" if result["thin_result"] else "ok",
           "method": result["method"], "filters_applied": result["filters_applied"],
           "include_unreviewed": result["include_unreviewed"],
           "intro": {"tr": unit_text(tr.get("intro") or {}), "en": unit_text(en.get("intro") or {}),
                     "trace": V._trace(tr.get("intro"))},
           "places": [_public(p, tr, en, f"places:{n}") for n, p in enumerate(result["places"])],
           "footer": FOOTER}
    if result.get("turkey") is not None:
        out["turkey"] = {"places": [_public(p, tr, en, f"turkey.places:{n}")
                                    for n, p in enumerate(result["turkey"]["places"])]}
    return out


def render_markdown(out: dict, langs=("tr", "en")) -> str:
    L: list[str] = []
    for lang in langs:
        tr = lang == "tr"
        L += [f"# {TITLE[lang]}", "",
              ("Filtreler" if tr else "Filters") + f": {json.dumps(out['filters_applied'], ensure_ascii=False)}",
              ""]
        if out.get("include_unreviewed"):
            L += ["> " + ("GELİŞTİRME: gözden geçirilmemiş yerler dahil." if tr else
                          "DEV: unreviewed destinations included."), ""]
        if out["intro"].get(lang):
            L += [out["intro"][lang], ""]
        for n, p in enumerate(out["places"], 1):
            name = p["name_tr"] if tr else p["name"]
            sup = ", ".join(_goal_names(p["supported_goals"], lang))
            L += [f"## {n}. {name} ({p['country']})", "",
                  f"- {'Destekledikleri' if tr else 'Supports'}: {sup}"]
            if p["challenged_goals"]:
                L += [f"- {'Zorladıkları' if tr else 'Challenges'}: "
                      f"{', '.join(_goal_names(p['challenged_goals'], lang))}"]
            L += ["", p[f"text_{lang}"], ""]
        t = out.get("turkey")
        if t is not None:
            L += ["## " + ("Türkiye" if tr else "Turkey"), ""]
            if not t["places"]:
                L += [("Türkiye'de birden çok hedefi birlikte destekleyen bir yer öne çıkmıyor."
                       if tr else "No place in Turkey stands out for several goals at once."), ""]
            for p in t["places"]:
                name = p["name_tr"] if tr else p["name"]
                sup = ", ".join(_goal_names(p["supported_goals"], lang))
                L += [f"- **{name}** — {sup}. {p[f'text_{lang}']}"]
            L += [""]
        L += [f"*{out['footer'][lang]}*", "", "---", ""]
    return "\n".join(L).rstrip("-\n ") + "\n"


def run(request, acg, aff, prod, stages, manifest, write, finish, *, dry_run, models,
        make_generator: Callable, scope: str):
    import acg_destinations as dst
    import acg_overall as ov
    import acg_recommend as rec
    rec.set_parans(prod.get("parans"))
    b = request["birth"]
    home = request.get("home_latlon") or (b["latitude"], b["longitude"])
    f = request.get("filters") or {}
    # "love" has the living + travel default purpose, which is what overall needs
    filters = dst.resolve_filters("love", regions=f.get("regions"), city_size=f.get("city_size"),
                                  max_distance_km=f.get("max_distance_km"), home_latlon=home,
                                  climate=f.get("climate"), purpose=f.get("purpose") or "both")
    t0 = time.monotonic()
    result = ov.recommend_overall(acg, aff, filters, scope,
                                  include_unreviewed=bool(request.get("include_unreviewed")))
    stages.record("recommend", "ok", None, t0)
    manifest["goal"], manifest["scope"] = "overall", result["scope"]
    manifest["filters_applied"] = result["filters_applied"]
    corpus = V.Corpus(prod["natal"])
    units = build_units(result, corpus)
    name = f"recommend_overall_{result['scope']}.json"
    if dry_run:
        out = assemble(result, {}, {})
        out["dry_run_units"] = units
        write(name, out)
        stages.record("reading", "dry_run", name)
        return finish("ok")
    gen = make_generator(models)
    t0 = time.monotonic()
    try:
        tr, en, errors = R.write_and_validate(units, gen, corpus)
    except Exception as err:  # noqa: BLE001 — a model failure is a failed stage, not a crash
        stages.record("reading", "failed", None, t0, error=f"{type(err).__name__}: {err}"[:500])
        return finish("failed")
    out = assemble(result, tr, en)
    out["validation"] = {"errors": errors, "passed": not errors, "usage": gen.usage,
                         "units": len(units)}
    if errors:
        write(f"recommend_overall_{result['scope']}.rejected.json", out)
        stages.record("reading", "failed", None, t0, error="; ".join(errors[:6]))
        return finish("failed")
    write(name, out)
    write(name.replace(".json", ".md"), None, raw=render_markdown(out))
    write(name.replace(".json", ".en.md"), None, raw=render_markdown(out, ("en",)))
    write(name.replace(".json", ".tr.md"), None, raw=render_markdown(out, ("tr",)))
    stages.record("reading", "ok", name, t0)
    return finish("ok")
