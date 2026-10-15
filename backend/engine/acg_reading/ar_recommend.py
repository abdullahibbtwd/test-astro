#!/usr/bin/env python3
"""ar_recommend.py — explanations for the v4 line-first "Where Should I Go?" result
(ACG 11 §6–§7, on top of 09 §4). The ranking is deterministic
(Astrocartography/acg_line_first.py); the model only explains it.

Units (TR words):
    intro                 50–80   acg-method-ambivalence / -natal-modifies-response / -orb-distance
    line group            60–90   the line's affinity-cell contributors for the goal + its angle
                                  frame (A3); for a paran: the pair's paran records or fallback
                                  contributors + acg-method-crossings
    destination           20–40   the place's own contributors (its other lines / parans), and
                                  the demanding side when has_tradeoff
    region / country      as 09 §4
    lines_without_dest.   fixed template, no model call, traced to acg-method-orb-distance

Units are written in parallel chunks, translated sentence-aligned, detoxed, validated
(RV1–RV4 + the text rules); failing units get ONE redraft with the validator's
messages, then anything still failing is refused.
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "Astrocartography")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import acg_views as V  # noqa: E402
import ar_prompts as P  # noqa: E402
from ar_sections import ANGLE_PLAIN, FOOTER, PLANET_NAMES  # noqa: E402
from ar_validate import text_problems, unit_text  # noqa: E402
from acg_constants import BANDS, GOALS  # noqa: E402

V.LENGTHS.update({"line_group": (60, 90), "destination": (20, 40)})
CHUNK = 12
REPAIR_ROUNDS = 2             # targeted redrafts of failing units before refusing
TEMPLATE_ID = "acg-method-orb-distance"
CROSSINGS_ID = "acg-method-crossings"


# ---------------------------------------------------------------------------
# units
# ---------------------------------------------------------------------------

def _group_unit(group: dict, goal: str, corpus: "V.Corpus", aff: dict, uid: str) -> dict:
    import acg_goals as ag
    ln = group["line"]
    if ln["kind"] == "paran":
        ids = [c for c in ag.paran_contributors(aff, ln["pair"], goal) if corpus.ok(c)]
        if CROSSINGS_ID in corpus.by_id:
            ids.append(CROSSINGS_ID)
        bodies = list(ln["bodies"])
        ctx = {"planets": [PLANET_NAMES[b][0] for b in bodies],
               "kind": "a softer background band where both planets combine"}
    else:
        ids = [c for c in ag.cell_contributors(aff, ln["body"], ln["angle"], goal) if corpus.ok(c)]
        fr = corpus.frame(ln["angle"])
        if fr:
            ids.append(fr)
        bodies = [ln["body"]]
        ctx = {"planet": PLANET_NAMES[ln["body"]][0],
               "where_it_shows_up": ANGLE_PLAIN[ln["angle"]][0]}
    return {"unit_id": uid, "kind": "line_group", "goal": GOALS[goal][0],
            "goal_definition": GOALS[goal][2], "line": ctx,
            "places_on_this_line": [d["name_tr"] for d in group["destinations"]],
            "brief_extra": "Explain why this line/band of the person's chart supports this goal "
                           "and where it shows up; you may mention the listed places by name.",
            "has_tradeoff": False, "allowed_planets": sorted(bodies),
            "principles": [corpus.slim(i) for i in dict.fromkeys(ids)]}


def _dest_unit(d: dict, goal: str, corpus: "V.Corpus", uid: str) -> dict:
    u = V.item_unit(d, "destination", goal, corpus, uid)
    u["brief_extra"] = ("One or two sentences on what is specific to this place for the goal "
                        "(its other lines or bands, if any); name the demanding side when "
                        "has_tradeoff is true.")
    return u


def build_units(ranking: dict, corpus: "V.Corpus", aff: dict) -> list[dict]:
    goal = ranking["goal"]
    units = [V.recommendation_units({"goal": goal}, corpus)[0]]            # intro
    blocks = [("", ranking)]
    if ranking.get("turkey") is not None:
        blocks.append(("turkey.", ranking["turkey"]))
    for prefix, blk in blocks:
        for gi, g in enumerate(blk.get("by_line", [])):
            units.append(_group_unit(g, goal, corpus, aff, f"{prefix}by_line:{gi}"))
            for di, d in enumerate(g["destinations"]):
                units.append(_dest_unit(d, goal, corpus, f"{prefix}by_line:{gi}:dest:{di}"))
    for n, item in enumerate(ranking.get("regions", [])):
        units.append(V.item_unit(item, "region", goal, corpus, f"regions:{n}"))
    for n, item in enumerate(ranking.get("countries", [])):
        units.append(V.item_unit(item, "country", goal, corpus, f"countries:{n}"))
    tr = ranking.get("turkey")
    if tr is not None:
        for n, item in enumerate(tr.get("regions", [])):
            units.append(V.item_unit(item, "region", goal, corpus, f"turkey.regions:{n}"))
        # the Turkey intro (09 §3.4 / §4) comes from the v3 builder
        tu = [u for u in V.recommendation_units({"goal": goal, "turkey": {
            "cities": tr.get("cities", []), "regions": [], "none_eligible": tr["none_eligible"],
            "best_available": tr.get("best_available")}}, corpus)
            if u["unit_id"] == "turkey.intro"]
        units += tu
    return units


def template_texts(ranking: dict) -> None:
    """Fixed sentences for lines without destinations (no model call)."""
    def fill(rows):
        for r in rows:
            ln = r["line"]
            p_tr, p_en = PLANET_NAMES[ln["body"]]
            w_tr, w_en = ANGLE_PLAIN[ln["angle"]]
            r["text_tr"] = (f"{p_tr} temasını {w_tr} alanında öne çıkaran güçlü çizginiz bu "
                            f"hedef için belirgin; ancak şu anki seçimlerinize uyan yerleşim "
                            f"yerlerinden geçmiyor.")
            r["text_en"] = (f"Your strong line bringing {p_en} themes forward in {w_en} "
                            f"matters for this goal, but it does not pass through places that "
                            f"fit your current choices.")
            r["trace"] = [TEMPLATE_ID]
    fill(ranking.get("lines_without_destinations", []))
    if ranking.get("turkey"):
        fill(ranking["turkey"].get("lines_without_destinations", []))


# ---------------------------------------------------------------------------
# writing: chunked, parallel, one repair round
# ---------------------------------------------------------------------------

def _write(gen, units: list[dict], feedback: Optional[dict] = None) -> tuple[dict, dict]:
    chunks = [units[i:i + CHUNK] for i in range(0, len(units), CHUNK)]

    def one(chunk):
        if feedback:
            chunk = [dict(u, fix_these_problems=feedback.get(u["unit_id"], [])) for u in chunk]
        return V._write_units(gen, chunk, {"name_tr": "", "name": ""})
    tr, en = {}, {}
    with ThreadPoolExecutor(max_workers=gen.max_workers) as pool:
        for t, e in pool.map(one, chunks):
            tr.update(t)
            en.update(e)
    return tr, en


def _errors_by_unit(errors: list[str], units: list[dict]) -> dict:
    out: dict = {}
    ids = sorted((u["unit_id"] for u in units), key=len, reverse=True)
    for e in errors:
        uid = next((i for i in ids if i in e), None)
        if uid:
            out.setdefault(uid, []).append(e)
    return out


def write_and_validate(units, gen, corpus) -> tuple[dict, dict, list[str]]:
    tr, en = _write(gen, units)
    pol = V._polarity(corpus)
    errors = V.validate_units(units, tr, en, pol)
    for _round in range(REPAIR_ROUNDS):
        if not errors:
            break
        bad = _errors_by_unit(errors, units)
        redo = [u for u in units if u["unit_id"] in bad]
        if not redo:
            break
        t2, e2 = _write(gen, redo, feedback=bad)
        tr.update(t2)
        en.update(e2)
        errors = V.validate_units(units, tr, en, pol)
    return tr, en, errors


# ---------------------------------------------------------------------------
# assembly (spec 11 §7 + the compatible 09 §5 fields)
# ---------------------------------------------------------------------------

def _dest_public(d: dict, tr: dict, en: dict, uid: str) -> dict:
    out = V._public(d, V._labelled(d["band"], tr.get(uid), en.get(uid)), V._trace(tr.get(uid)))
    km = d["group_distance_km"]
    out.update({"size": d.get("size"), "kind": d.get("dest_kind"), "purposes": d.get("purposes"),
                "reviewed": d.get("reviewed"),
                "distance_km_rounded": "<10" if km < 10 else int(km / 10 + 0.5) * 10})
    return out


def _groups_public(groups, tr, en, prefix):
    out = []
    for gi, g in enumerate(groups):
        uid = f"{prefix}by_line:{gi}"
        out.append({"line": g["line"], "kind": g["kind"], "affinity": g["affinity"],
                    "text_tr": unit_text(tr.get(uid) or {}), "text_en": unit_text(en.get(uid) or {}),
                    "trace": V._trace(tr.get(uid)),
                    "destinations": [_dest_public(d, tr, en, f"{uid}:dest:{di}")
                                     for di, d in enumerate(g["destinations"])]})
    return out


def assemble(ranking: dict, tr: dict, en: dict) -> dict:
    goal = ranking["goal"]
    by_line = _groups_public(ranking["by_line"], tr, en, "")
    dest_text = {d["id"]: d for g in by_line for d in g["destinations"]}
    out = {"schema_version": "acg-recommend-2", "goal": goal,
           "goal_label_tr": GOALS[goal][0], "goal_label_en": GOALS[goal][1],
           "scope": ranking["scope"],
           "status": "thin_result" if ranking["thin_result"] else "ok",
           "filters_applied": ranking["filters_applied"],
           "include_unreviewed": ranking["include_unreviewed"],
           "intro": {"tr": unit_text(tr.get("intro") or {}), "en": unit_text(en.get("intro") or {}),
                     "trace": V._trace(tr.get("intro"))},
           "by_line": by_line,
           "lines_without_destinations": ranking["lines_without_destinations"],
           "by_purpose": ranking["by_purpose"],
           "cities": [dest_text[c["id"]] for c in ranking["cities"]],
           "regions": [V._public(it, V._labelled(it["band"], tr.get(f"regions:{n}"),
                                                 en.get(f"regions:{n}")),
                                 V._trace(tr.get(f"regions:{n}")))
                       for n, it in enumerate(ranking["regions"])],
           "countries": [V._public(it, V._labelled(it["band"], tr.get(f"countries:{n}"),
                                                   en.get(f"countries:{n}")),
                                   V._trace(tr.get(f"countries:{n}")))
                         for n, it in enumerate(ranking["countries"])],
           "footer": FOOTER}
    t = ranking.get("turkey")
    if t is not None:
        tby = _groups_public(t["by_line"], tr, en, "turkey.")
        tdest = {d["id"]: d for g in tby for d in g["destinations"]}
        out["turkey"] = {
            "intro": {"tr": unit_text(tr.get("turkey.intro") or {}),
                      "en": unit_text(en.get("turkey.intro") or {}),
                      "trace": V._trace(tr.get("turkey.intro"))},
            "by_line": tby, "lines_without_destinations": t["lines_without_destinations"],
            "cities": [tdest[c["id"]] for c in t["cities"]],
            "regions": [V._public(it, V._labelled(it["band"], tr.get(f"turkey.regions:{n}"),
                                                  en.get(f"turkey.regions:{n}")),
                                  V._trace(tr.get(f"turkey.regions:{n}")))
                        for n, it in enumerate(t["regions"])],
            "none_eligible": t["none_eligible"]}
        if t.get("best_available"):
            b = t["best_available"]
            out["turkey"]["best_available"] = V._public(b, V._labelled(b["band"], None, None), [])
    return out


# ---------------------------------------------------------------------------
# readable output: recommend_<goal>_<scope>.md (TR then EN)
# ---------------------------------------------------------------------------

_ANGLE_UI = {"ASC": ("Yükselen çizgi", "Rising line"), "DSC": ("Alçalan çizgi", "Setting line"),
             "MC": ("Zirve çizgisi", "Culminating line"), "IC": ("Kök çizgisi", "Root line")}


def _line_title(line: dict, lang: str) -> str:
    i = 0 if lang == "tr" else 1
    if line["kind"] == "paran":
        names = " + ".join(PLANET_NAMES[b][i] for b in line["bodies"])
        return f"{names} — " + ("Enlem kesişimi" if lang == "tr" else "Latitude crossing")
    return f"{PLANET_NAMES[line['body']][i]} — {_ANGLE_UI[line['angle']][i]}"


def _dist(d) -> str:
    v = d.get("distance_km_rounded")
    return "" if v is None else (f" · ~{v} km" if v != "<10" else " · <10 km")


def render_markdown(out: dict, langs: tuple[str, ...] = ("tr", "en")) -> str:
    L: list[str] = []
    for lang in langs:
        tr = lang == "tr"
        goal = out["goal_label_tr"] if tr else out["goal_label_en"]
        L += [f"# {'Nereye Gitmeliyim?' if tr else 'Where Should I Go?'} — {goal}", ""]
        f = out["filters_applied"]
        L += [("Filtreler" if tr else "Filters") + f": {json.dumps(f, ensure_ascii=False)}", ""]
        if out.get("include_unreviewed"):
            L += ["> " + ("GELİŞTİRME: gözden geçirilmemiş yerler dahil." if tr else
                          "DEV: unreviewed destinations included."), ""]
        if out["intro"].get(lang):
            L += [out["intro"][lang], ""]
        for g in out["by_line"]:
            L += [f"## {_line_title(g['line'], lang)}", ""]
            if g.get(f"text_{lang}"):
                L += [g[f"text_{lang}"], ""]
            for d in g["destinations"]:
                name = d["name_tr"] if tr else d["name"]
                L += [f"- **{name}** ({d['country']}{_dist(d)}) — {d.get(f'text_{lang}') or ''}"]
            L += [""]
        if out["lines_without_destinations"]:
            L += ["## " + ("Uygun yer bulunmayan güçlü çizgiler" if tr else
                           "Strong lines without suitable places"), ""]
            for x in out["lines_without_destinations"]:
                L += [f"- {_line_title(x['line'], lang)}: {x.get(f'text_{lang}', '')}"]
            L += [""]
        for key, title in (("regions", ("Bölgeler", "Regions")),
                           ("countries", ("Ülkeler", "Countries"))):
            if out.get(key):
                L += [f"## {title[0 if tr else 1]}", ""]
                for it in out[key]:
                    name = it["name_tr"] if tr else it["name"]
                    L += [f"- **{name}** — {it.get(f'text_{lang}') or ''}"]
                L += [""]
        t = out.get("turkey")
        if t:
            L += ["## " + ("Türkiye" if tr else "Turkey"), ""]
            if t["intro"].get(lang):
                L += [t["intro"][lang], ""]
            for g in t["by_line"]:
                L += [f"### {_line_title(g['line'], lang)}", ""]
                for d in g["destinations"]:
                    name = d["name_tr"] if tr else d["name"]
                    L += [f"- **{name}**{_dist(d)} — {d.get(f'text_{lang}') or ''}"]
                L += [""]
            if t.get("best_available"):
                b = t["best_available"]
                L += [f"- {b['name_tr'] if tr else b['name']}: "
                      f"{b['band_label_tr'] if tr else b['band_label_en']}", ""]
        L += [f"*{out['footer'][lang]}*", "", "---", ""]
    return "\n".join(L).rstrip("-\n ") + "\n"


# ---------------------------------------------------------------------------
# run stage (called by acg_views.run_recommend)
# ---------------------------------------------------------------------------

def run(request, acg, aff, prod, stages, manifest, write, finish, *, dry_run, models,
        make_generator: Callable, goal: str, scope: str):
    import acg_destinations as dst
    import acg_line_first as lf
    import acg_recommend as rec
    rec.set_parans(prod.get("parans"))
    b = request["birth"]
    home = request.get("home_latlon") or (b["latitude"], b["longitude"])
    f = request.get("filters") or {}
    filters = dst.resolve_filters(goal, regions=f.get("regions"), city_size=f.get("city_size"),
                                  max_distance_km=f.get("max_distance_km"), home_latlon=home,
                                  climate=f.get("climate"), purpose=f.get("purpose"))
    t0 = time.monotonic()
    ranking = lf.rank_line_first(goal, scope, acg, prod["goal_scan"], aff, filters,
                                 include_unreviewed=bool(request.get("include_unreviewed")))
    template_texts(ranking)
    stages.record("recommend", "ok", None, t0)
    manifest["filters_applied"] = ranking["filters_applied"]
    manifest["include_unreviewed"] = ranking["include_unreviewed"]
    corpus = V.Corpus(prod["natal"])
    units = build_units(ranking, corpus, aff)
    name = f"recommend_{goal}_{scope}.json"
    if dry_run:
        out = assemble(ranking, {}, {})
        out["dry_run_units"] = units
        write(name, out)
        stages.record("reading", "dry_run", name)
        return finish("ok")
    gen = make_generator(models)
    t0 = time.monotonic()
    try:
        tr, en, errors = write_and_validate(units, gen, corpus)
    except Exception as err:  # noqa: BLE001 — a model failure is a failed stage, not a crash
        stages.record("reading", "failed", None, t0, error=f"{type(err).__name__}: {err}"[:500])
        return finish("failed")
    out = assemble(ranking, tr, en)
    out["validation"] = {"errors": errors, "passed": not errors, "usage": gen.usage,
                         "units": len(units)}
    if errors:
        write(f"recommend_{goal}_{scope}.rejected.json", out)
        stages.record("reading", "failed", None, t0, error="; ".join(errors[:6]))
        return finish("failed")
    write(name, out)
    write(name.replace(".json", ".md"), None, raw=render_markdown(out))
    write(name.replace(".json", ".en.md"), None, raw=render_markdown(out, ("en",)))
    write(name.replace(".json", ".tr.md"), None, raw=render_markdown(out, ("tr",)))
    stages.record("reading", "ok", name, t0)
    return finish("ok")
