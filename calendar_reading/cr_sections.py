"""cr_sections.py - calendar text units, deterministic labels and grounding pools (CAL_03 §1-2).

A *unit* is one piece of text the calendar may show:

  collective_event   c:<collective id>      global; shared by every user
  personal_transit   t:<event id>           major 70-110 / moderate 30-50 / minor -> label only
  personal_lunation  l:<event id>           lunation or eclipse, importance >= moderate
  period             p:<period id>          importance major or strength strong
  day_note           d:<YYYY-MM-DD>         the "today" card, on request

Every unit always has a deterministic TR/EN label (no model). A unit gets prose only if
its pool of eligible modern records is non-empty ("no grounding, no text"). Otherwise it
is label-only and listed in ``gaps``.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "Calendar"), os.path.join(_ROOT, "Astrocartography")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from acg_constants import GOALS  # noqa: E402

PROMPT_VERSION = "cr-2"
TOLERANCE = 0.20                                   # CV5: ±20%
LENGTHS = {"best_day": (30, 50), "collective_event": (50, 80), "personal_transit:major": (70, 110),
           "personal_transit:moderate": (30, 50), "personal_lunation": (40, 70),
           "period": (40, 80), "day_note": (40, 60)}

# --- label vocabulary ---------------------------------------------------------------------
PLANET_TR = {"sun": "Güneş", "moon": "Ay", "mercury": "Merkür", "venus": "Venüs", "mars": "Mars",
             "jupiter": "Jüpiter", "saturn": "Satürn", "uranus": "Uranüs", "neptune": "Neptün",
             "pluto": "Plüton"}
PLANET_EN = {k: k.title() for k in PLANET_TR}
POINT_EN = {**{k: v for k, v in PLANET_EN.items()}, "asc": "Ascendant", "mc": "Midheaven",
            "dsc": "Descendant", "ic": "IC"}
# natal point with 2nd-person-plural possessive, dative (-e/-a) and comitative (-le/-la)
POINT_TR_DAT = {"sun": "Güneş'inize", "moon": "Ay'ınıza", "mercury": "Merkür'ünüze",
                "venus": "Venüs'ünüze", "mars": "Mars'ınıza", "jupiter": "Jüpiter'inize",
                "saturn": "Satürn'ünüze", "uranus": "Uranüs'ünüze", "neptune": "Neptün'ünüze",
                "pluto": "Plüton'unuza", "asc": "Yükselen'inize", "mc": "Tepe Noktanıza",
                "dsc": "Alçalan'ınıza", "ic": "Dip Noktanıza"}
POINT_TR_COM = {"sun": "Güneş'inizle", "moon": "Ay'ınızla", "mercury": "Merkür'ünüzle",
                "venus": "Venüs'ünüzle", "mars": "Mars'ınızla", "jupiter": "Jüpiter'inizle",
                "saturn": "Satürn'ünüzle", "uranus": "Uranüs'ünüzle", "neptune": "Neptün'ünüzle",
                "pluto": "Plüton'unuzla", "asc": "Yükselen'inizle", "mc": "Tepe Noktanızla",
                "dsc": "Alçalan'ınızla", "ic": "Dip Noktanızla"}
POINT_TR_NOM = {"sun": "Güneş'iniz", "moon": "Ay'ınız", "mercury": "Merkür'ünüz",
                "venus": "Venüs'ünüz", "mars": "Mars'ınız", "jupiter": "Jüpiter'iniz",
                "saturn": "Satürn'ünüz", "uranus": "Uranüs'ünüz", "neptune": "Neptün'ünüz",
                "pluto": "Plüton'unuz", "asc": "Yükselen'iniz", "mc": "Tepe Noktanız",
                "dsc": "Alçalan'ınız", "ic": "Dip Noktanız"}
ASPECT_TR = {"sextile": "altmışlık", "square": "kare", "trine": "üçgen", "opposition": "karşıt"}
ASPECT_EN = {"conjunction": "conjunct", "sextile": "sextile", "square": "square",
             "trine": "trine", "opposition": "opposite"}
SIGN_TR = {"aries": "Koç", "taurus": "Boğa", "gemini": "İkizler", "cancer": "Yengeç", "leo": "Aslan",
           "virgo": "Başak", "libra": "Terazi", "scorpio": "Akrep", "sagittarius": "Yay",
           "capricorn": "Oğlak", "aquarius": "Kova", "pisces": "Balık"}
# PROJECT_OVERVIEW §3 reader-facing house areas (numbers never reach the prose, CV2)
HOUSE_AREA_EN = {1: "Identity", 2: "Values and Money", 3: "Communication, Studying, Siblings",
                 4: "Family and Home", 5: "Joy, Artistic Talents and Kids", 6: "Health, Routine, Pets",
                 7: "Partnerships", 8: "Transformation and Intimacy", 9: "Distant Travels and Philosophy",
                 10: "Social Status and Vocation", 11: "Friendships and the Future",
                 12: "Subconscious and Solitary"}
ECL_KIND_TR = {"total": "Tam", "annular": "Halkalı", "hybrid": "Hibrit", "partial": "Parçalı",
               "penumbral": "Yarı gölgeli"}


def transit_label(t: str, a: str, n: str) -> tuple[str, str]:
    if a == "conjunction":
        tr = f"{PLANET_TR[t]}, {POINT_TR_COM[n]} kavuşumda"
    else:
        tr = f"{PLANET_TR[t]}, {POINT_TR_DAT[n]} {ASPECT_TR[a]}"
    return tr, f"{PLANET_EN[t]} {ASPECT_EN[a]} your {POINT_EN[n]}"


def lunation_label(kind: str, sign: str, eclipse_kind: Optional[str] = None) -> tuple[str, str]:
    s_tr, s_en = SIGN_TR[sign], sign.title()
    if kind == "new_moon":
        return f"Yeni Ay – {s_tr}", f"New Moon in {s_en}"
    if kind == "full_moon":
        return f"Dolunay – {s_tr}", f"Full Moon in {s_en}"
    body_tr = "güneş tutulması" if kind == "solar_eclipse" else "ay tutulması"
    body_en = "solar eclipse" if kind == "solar_eclipse" else "lunar eclipse"
    k = eclipse_kind or "partial"
    return f"{ECL_KIND_TR[k]} {body_tr} – {s_tr}", f"{k.title()} {body_en} in {s_en}"


def collective_label(ev: dict) -> tuple[str, str]:
    k = ev["kind"]
    if k in ("new_moon", "full_moon", "solar_eclipse", "lunar_eclipse"):
        return lunation_label(k, ev["sign"], ev.get("eclipse_kind"))
    if k == "retrograde_period":
        return f"{PLANET_TR[ev['body']]} retrosu", f"{PLANET_EN[ev['body']]} retrograde"
    if k == "ingress":
        return (f"{PLANET_TR[ev['body']]} {SIGN_TR[ev['sign']]} burcuna giriyor",
                f"{PLANET_EN[ev['body']]} enters {ev['sign'].title()}")
    if k in ("station_retrograde", "station_direct"):
        d_tr = "geri harekete başlıyor" if k == "station_retrograde" else "düz harekete geçiyor"
        d_en = "turns retrograde" if k == "station_retrograde" else "turns direct"
        return f"{PLANET_TR[ev['body']]} {d_tr}", f"{PLANET_EN[ev['body']]} {d_en}"
    return k, k


def station_label(ev: dict) -> tuple[str, str]:
    d_tr = "geri harekete başlıyor" if ev["direction"] == "R" else "düz harekete geçiyor"
    d_en = "turns retrograde" if ev["direction"] == "R" else "turns direct"
    if ev["aspect"] == "conjunction":
        where_tr, where_en = f"{POINT_TR_NOM[ev['n_point']]} üzerinde", f"on your {POINT_EN[ev['n_point']]}"
    else:
        where_tr = f"{POINT_TR_DAT[ev['n_point']]} {ASPECT_TR[ev['aspect']]} konumda"
        where_en = f"{ASPECT_EN[ev['aspect']]} your {POINT_EN[ev['n_point']]}"
    return f"{PLANET_TR[ev['body']]}, {where_tr} {d_tr}", f"{PLANET_EN[ev['body']]} {d_en} {where_en}"


def period_label(goal: str, kind: str) -> tuple[str, str]:
    g_tr, g_en = GOALS[goal][0], GOALS[goal][1]
    if kind == "favorable":
        return f"{g_tr}: destekleyici dönem", f"{g_en}: supportive period"
    return f"{g_tr}: daha dikkat isteyen dönem", f"{g_en}: more demanding period"


def event_label(ev: dict) -> tuple[str, str]:
    if ev["kind"] == "transit":
        return transit_label(ev["t_body"], ev["aspect"], ev["n_point"])
    if ev["kind"] in ("new_moon", "full_moon", "solar_eclipse", "lunar_eclipse"):
        return lunation_label(ev["kind"], ev["sign"], ev.get("eclipse_kind"))
    if ev["kind"] == "station_on_point":
        return station_label(ev)
    return ev["kind"], ev["kind"]


# --- grounding pools --------------------------------------------------------------------------
def _rec(modern: dict, pid: str, polarity: Optional[str] = None) -> dict:
    r = modern[pid]
    text = " ".join(x for x in (r.get("rule"), r.get("judgment")) if x)
    out = {"id": pid, "text": text}
    if polarity:
        out["polarity"] = polarity
    return out


def transit_pool(index: dict, modern: dict, t: str, a: str, n: str) -> list[dict]:
    return [_rec(modern, i) for i in index["transits"].get((t, a, n), [])]


def lunation_pool(index: dict, modern: dict, ev: dict) -> list[dict]:
    ids: list[str] = []
    if ev["hits"]:
        kind = "eclipse" if ev["kind"].endswith("_eclipse") else "lunation"
        ids += index["generic"][kind]
    if ev.get("natal_house"):
        ids += index["house_domain"].get(ev["natal_house"], [])
    return [_rec(modern, i) for i in dict.fromkeys(ids)]


# Collective events have no modern grounding in the current corpus (Phase 0 audit §3 b-d).
# The table stays here so a corpus delta (CAL_06) can fill it without code changes:
# {collective kind: [principle ids]}.
COLLECTIVE_GROUNDING: dict[str, list[str]] = {}


def collective_pool(modern: dict, ev: dict, grounding: Optional[dict] = None) -> list[dict]:
    g = COLLECTIVE_GROUNDING if grounding is None else grounding
    return [_rec(modern, i) for i in g.get(ev["kind"], []) if i in modern]


def phase_arc(ev: dict) -> str:
    """The episode's phase arc as words (CAL_03 §3: phase labels, never dates)."""
    n = len(ev.get("exacts_utc", []))
    if n == 0:
        return "a slow build-up that comes close to full strength, then fades"
    if n == 1:
        return "builds, is strongest in the middle, then fades"
    return "a long influence that returns in waves as the planet turns back and forth, then fades"


def period_pool(index: dict, modern: dict, tags: dict, per: dict, ev_by_id: dict,
                max_drivers: int = 3) -> list[dict]:
    g = per["goal"]
    out: list[dict] = []
    for d in per["drivers"][:max_drivers]:
        e = ev_by_id.get(d)
        if not e or e["kind"] != "transit":
            continue
        for i in index["transits"].get((e["t_body"], e["aspect"], e["n_point"]), []):
            pol = tags.get(i, {}).get(g)
            if pol:
                out.append(_rec(modern, i, pol))
    return list({r["id"]: r for r in out}.values())


# --- unit planning ---------------------------------------------------------------------------
def _span_local(ev: dict) -> tuple[str, str]:
    if "start_local" in ev:
        return ev["start_local"], ev["end_local"]
    return ev["local_date"], ev["local_date"]


def plan_units(events_doc: dict, periods_doc: dict, collective_refs: list[dict],
               collective_by_id: dict, index: dict, modern: dict, tags: dict,
               collective_grounding: Optional[dict] = None) -> dict[str, dict]:
    """unit_id -> unit {unit_id, unit_type, ref, scope, label_tr, label_en, words, pool,
    context, span, text: bool, gap: reason|None}."""
    units: dict[str, dict] = {}
    ev_by_id = {e["id"]: e for e in events_doc["events"]}

    def add(u: dict) -> None:
        u.setdefault("gap", None)
        if u["words"] is None:
            u["text"] = False
        elif not u["pool"]:
            u["text"] = False
            u["gap"] = u.get("gap") or "no_grounding"
        else:
            u["text"] = u.get("text", True)
        units[u["unit_id"]] = u

    for ref in collective_refs:
        ev = collective_by_id.get(ref["id"])
        if not ev or ev["kind"] not in ("new_moon", "full_moon", "solar_eclipse", "lunar_eclipse",
                                        "retrograde_period", "ingress"):
            continue
        if ev["kind"] == "ingress" and ev["body"] not in ("jupiter", "saturn", "uranus", "neptune", "pluto"):
            continue
        tr, en = collective_label(ev)
        span = (ref.get("local_date") or ref.get("start_local"),
                ref.get("local_date") or ref.get("end_local"))
        add({"unit_id": f"c:{ev['id']}", "unit_type": "collective_event", "ref": ev["id"],
             "scope": "collective", "label_tr": tr, "label_en": en, "span": span,
             "words": LENGTHS["collective_event"],
             "pool": collective_pool(modern, ev, collective_grounding),
             "context": {"event": en}})

    for ev in events_doc["events"]:
        tr, en = event_label(ev)
        span = _span_local(ev)
        base = {"ref": ev["id"], "scope": "personal", "label_tr": tr, "label_en": en, "span": span,
                "importance": ev["importance"]}
        if ev["kind"] == "transit":
            words = None if ev["importance"] == "minor" else LENGTHS[f"personal_transit:{ev['importance']}"]
            add({**base, "unit_id": f"t:{ev['id']}", "unit_type": "personal_transit", "words": words,
                 "pool": transit_pool(index, modern, ev["t_body"], ev["aspect"], ev["n_point"]),
                 "context": {"transit": en, "phase_arc": phase_arc(ev),
                             "transiting_planet": ev["t_body"], "natal_point": ev["n_point"]}})
        elif ev["kind"] in ("new_moon", "full_moon", "solar_eclipse", "lunar_eclipse"):
            words = LENGTHS["personal_lunation"] if ev["importance"] in ("major", "moderate") else None
            add({**base, "unit_id": f"l:{ev['id']}", "unit_type": "personal_lunation", "words": words,
                 "pool": lunation_pool(index, modern, ev),
                 "context": {"event": en, "life_area": HOUSE_AREA_EN.get(ev.get("natal_house")),
                             "touches": [POINT_EN[h["point"]] for h in ev["hits"]]}})
        elif ev["kind"] == "station_on_point":
            add({**base, "unit_id": f"s:{ev['id']}", "unit_type": "station_on_point", "words": None,
                 "pool": [], "context": {}})

    for per in periods_doc["periods"]:
        tr, en = period_label(per["goal"], per["kind"])
        eligible = per["importance"] == "major" or per["strength"] == "strong"
        pool = period_pool(index, modern, tags, per, ev_by_id) if eligible else []
        gap = None
        if eligible and per["kind"] == "challenging" and pool and \
                not any(r.get("polarity") in ("mixed", "supportive") for r in pool):
            gap = "no_constructive_record"          # CV4: label only
        u = {"unit_id": f"p:{per['id']}", "unit_type": "period", "ref": per["id"], "scope": "personal",
             "label_tr": tr, "label_en": en, "span": (per["start_local"], per["end_local"]),
             "importance": per["importance"], "words": LENGTHS["period"] if eligible else None,
             "pool": pool, "gap": gap,
             "context": {"goal": per["goal"], "goal_definition": GOALS[per["goal"]][2],
                         "kind": per["kind"], "strength": per["strength"]}}
        if gap:
            u["text"] = False
        add(u)
    return units


def day_note_unit(day: dict, events_doc: dict, units: dict, index: dict, modern: dict) -> dict:
    """The on-request 'today' card: the day's top drivers (<= 3) across goals."""
    counts: dict[str, int] = {}
    for g, ids in day["drivers"].items():
        for i in ids:
            counts[i] = counts.get(i, 0) + 1
    top = sorted(counts, key=lambda i: (-counts[i], i))[:3]
    ev_by_id = {e["id"]: e for e in events_doc["events"]}
    pool: list[dict] = []
    for i in top:
        e = ev_by_id[i]
        pool += transit_pool(index, modern, e["t_body"], e["aspect"], e["n_point"])
    d = day["local_date"]
    u = {"unit_id": f"d:{d}", "unit_type": "day_note", "ref": d, "scope": "personal",
         "label_tr": d, "label_en": d, "span": (d, d), "words": LENGTHS["day_note"],
         "pool": list({r["id"]: r for r in pool}.values()), "gap": None,
         "context": {"transits": [units[f"t:{i}"]["label_en"] for i in top if f"t:{i}" in units],
                     "tone": day["tone"]}}
    u["text"] = bool(u["pool"])
    if not u["pool"]:
        u["gap"] = "no_grounding"
    return u


def overlaps(span: tuple[str, str], first: date, last: date) -> bool:
    a, b = span
    return a is not None and b is not None and a <= last.isoformat() and b >= first.isoformat()


def window(today: date, days: int) -> tuple[date, date]:
    return today, today + timedelta(days=days - 1)


# --- Best Days top-day texts (CAL_04 §5) ---------------------------------------------------------
def best_day_units(bd_doc: dict, index: dict, modern: dict) -> dict[str, dict]:
    """One unit per (activity, top day): 30-50 words grounded in the records of that day's
    top contributions (the same parts the deterministic reasons name)."""
    import best_days as B          # Calendar/ (on sys.path above)
    units: dict[str, dict] = {}
    for act, a in bd_doc["activities"].items():
        tr_name, en_name = B.ACTIVITIES[act][0], B.ACTIVITIES[act][1]
        for d in a["days"]:
            ld = d["local_date"]
            if ld not in a["top_days"]:
                continue
            parts = d.get("_parts", [])
            pos = sorted((p for p in parts if p["contribution"] > 0), key=lambda p: -p["contribution"])[:3]
            neg = sorted((p for p in parts if p["contribution"] < 0), key=lambda p: p["contribution"])[:2]
            ids: list[str] = []
            for p in pos + neg:
                ids += B.part_records(p, index)
            pool = [_rec(modern, i) for i in dict.fromkeys(ids) if i in modern]
            r = a["reasons"][ld]
            u = {"unit_id": f"b:{act}:{ld}", "unit_type": "best_day", "ref": f"{act}:{ld}",
                 "scope": "personal", "label_tr": f"{tr_name} – {ld}", "label_en": f"{en_name} – {ld}",
                 "span": (ld, ld), "words": LENGTHS["best_day"], "pool": pool, "gap": None,
                 "context": {"activity": en_name,
                             "supportive_influences": [x["label_en"] for x in r["positive"]],
                             "caveats": [x["label_en"] for x in r["negative"]]}}
            u["text"] = bool(pool)
            if not pool:
                u["gap"] = "no_grounding"
            units[u["unit_id"]] = u
    return units
