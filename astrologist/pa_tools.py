"""pa_tools.py - the 11 deterministic tools that turn a plan into evidence packs (PA_01 §3-5).

No model calls anywhere (T9). Every tool reuses an existing layer's loaders and grounding
selectors through ``TurnContext``; it never selects records by its own rules.

A pack holds a **model view** (facts / records / items / prose / candidates as labels; dates
are the only digits) and an ``_internal`` block (record claims, raw items, card bodies) that
the validator uses and the model never sees.
"""

from __future__ import annotations

import copy
import re
import difflib
import json
from datetime import date, timedelta
from typing import Callable, Optional

import _paths  # noqa: F401
import pa_cards as CARDS  # noqa: E402
import pa_catalogue as C  # noqa: E402
import pa_constants as K  # noqa: E402
import pa_dossier as D  # noqa: E402
from pa_context import TurnContext  # noqa: E402

TOOLS = ["chart_facts", "natal_topics", "natal_section", "day", "span", "best_days", "calendar_item",
         "place", "recommend", "compatibility", "astro_basics"]
SOURCE_KIND = {"chart_facts": ["chart"], "natal_topics": ["chart"], "natal_section": ["natal_reading"],
               "day": ["calendar"], "span": ["calendar"], "best_days": ["best_days"],
               "calendar_item": ["calendar"], "place": ["acg"], "recommend": ["acg"],
               "compatibility": ["compatibility"], "astro_basics": []}
ACG_METHOD_IDS = ["acg-method-ambivalence", "acg-method-natal-modifies-response", "acg-method-degree-of-expression"]


# --- pack scaffolding -------------------------------------------------------------------------------
def new_pack(call_id: str, tool: str, args: dict, forced: bool = False) -> dict:
    return {"call_id": call_id, "tool": tool, "args": copy.deepcopy(args), "forced": forced, "status": "ok",
            "absence": None, "clamped": None, "source_kinds": list(SOURCE_KIND[tool]), "facts": [],
            "records": [], "items": [], "prose": [], "card_candidates": [], "link_candidates": [],
            "needs_input": None, "resolved_by": None,
            "_internal": {"facts": {}, "records": {}, "items": {}}}


def add_fact(p: dict, fid: str, label: str, fact: Optional[dict] = None) -> None:
    if fid not in p["_internal"]["facts"]:
        p["facts"].append({"id": fid, "label": label})
        p["_internal"]["facts"][fid] = fact or {}


_SENT = re.compile(r"(?<=[.!?])\s+")
_HOUSE_WORD = re.compile(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)"
                         r"[- ]house\b", re.IGNORECASE)


def clean_render(text: str) -> str:
    """PA_01 §3.2: no digits (degrees, ages, house numbers) and no house-number wording reach the model.
    Sentences that carry them are dropped, deterministically; the rest of the record stays."""
    keep = [s for s in _SENT.split((text or "").strip()) if s and not re.search(r"\d", s)
            and not _HOUSE_WORD.search(s)]
    return " ".join(keep)


def add_record(p: dict, rid: str, render: str, *, polarity=None, sensitivity=None, claims=None) -> None:
    render = clean_render(render)
    if rid in p["_internal"]["records"] or not render:
        return
    p["records"].append({"id": rid, "render": render, "polarity": polarity,
                         "sensitivity": sensitivity or "normal"})
    p["_internal"]["records"][rid] = {"claims": claims or {"sign": [], "house": [], "aspect": []},
                                       "polarity": polarity}


def add_item(p: dict, iid: str, label: str, dates: list[str], *, band=None, grade=None, band_label=None,
             raw: Optional[dict] = None) -> None:
    if iid in p["_internal"]["items"]:
        return
    p["items"].append({"id": iid, "label": label, "dates": sorted(set(dates)), "band": band, "grade": grade,
                       "band_label": band_label})
    p["_internal"]["items"][iid] = raw or {}


def add_prose(p: dict, pid: str, text: Optional[str]) -> None:
    """Already-validated texts, cut to 250 words; sentences with digits or house numbers (older
    readings can carry "12. ev") are dropped like in records (PA_01 §3.2)."""
    text = clean_render(text or "")
    if text and pid not in {x["id"] for x in p["prose"]}:
        p["prose"].append({"id": pid, "text": cut_words(text, K.CAP_PROSE_WORDS)})


def add_card(p: dict, card: Optional[dict], desc: str) -> None:
    if card:
        i = len(p["card_candidates"])
        p["card_candidates"].append({"id": f"k:{p['call_id']}:{i}", "card": card, "desc": desc})


def add_link(p: dict, lk: dict) -> None:
    if lk["route"] not in {x["route"] for x in p["link_candidates"]}:
        i = len(p["link_candidates"])
        p["link_candidates"].append({"id": f"l:{p['call_id']}:{i}", **lk})


def absent(p: dict, reason: str, **extra) -> dict:
    p["status"] = "absent"
    p["absence"] = {"reason": reason, **extra}
    return p


def cut_words(text: str, n: int) -> str:
    words = text.split()
    if len(words) <= n:
        return text.strip()
    cut = " ".join(words[:n])
    for end in (". ", "! ", "? "):
        i = cut.rfind(end.strip())
        if i > len(cut) // 2:
            return cut[:i + 1]
    return cut


def model_view(p: dict) -> dict:
    """The pack as the composer sees it: no internal fields, candidates as one-line descriptions."""
    v = {k: val for k, val in p.items() if not k.startswith("_")}
    v["card_candidates"] = [{"id": c["id"], "desc": c["desc"]} for c in p["card_candidates"]]
    v["link_candidates"] = [{"id": lk["id"], "label": lk["label"]} for lk in p["link_candidates"]]
    return v


# --- natal tools (PA_01 §4.1-4.3) -------------------------------------------------------------------
def _natal_record(p: dict, dossier: dict, rid: str) -> None:
    r = dossier["records"][rid]
    add_record(p, rid, r["render"], polarity=r.get("polarity"), sensitivity=r.get("sensitivity"),
               claims=r.get("_claims"))


def _fact(p: dict, dossier: dict, fid: str, lang: str) -> None:
    f = dossier["facts"].get(fid)
    if f:
        add_fact(p, fid, D.fact_label(f, lang), f)


def chart_facts(ctx: TurnContext, p: dict, bodies=None, angles=None, big_three=None) -> dict:
    dz, lang = ctx.dossier(), ctx.lang
    if not bodies and not angles:
        bodies, angles = ["sun", "moon"], ["asc"]
    for b in (bodies or [])[:4]:
        _fact(p, dz, f"f:natal:{b}", lang)
    for a in angles or []:
        _fact(p, dz, f"f:natal:{a}", lang)
    asp = sorted((f for f in dz["facts"].values() if f["kind"] == "aspect" and
                  (f["a"] in (bodies or []) or f["b"] in (bodies or []))), key=lambda f: f["rank"])[:4]
    for f in asp:
        _fact(p, dz, f"f:natal:aspect:{f['a']}|{f['b']}|{f['type']}", lang)
    for b in (bodies or [])[:3]:
        add_card(p, CARDS.chart_fact_card(ctx.natal(), b), f"chart fact card: {C.body(b, 'en')}")
    add_link(p, CARDS.link("chart", lang))
    return p


def natal_topics(ctx: TurnContext, p: dict, topics=None, goals=None, bodies=None, depth: str = "normal") -> dict:
    dz, lang = ctx.dossier(), ctx.lang
    tps = list(topics or [])
    for g in goals or []:
        for t in D.GOAL_TOPICS.get(g, []):
            if t not in tps:
                tps.append(t)
    bodies = list(bodies or [])
    cap = K.NATAL_CAP_MORE if depth == "more" else None
    sel = D.select_natal(dz, tps, bodies, cap)
    if not sel:
        return absent(p, "no_grounding")
    for rid in sel:
        _natal_record(p, dz, rid)
    seen_bodies = []
    for rid in sel:
        for b in dz["records"][rid]["_bodies"]:
            if b not in seen_bodies:
                seen_bodies.append(b)
    for b in seen_bodies:
        _fact(p, dz, f"f:natal:{b}", lang)
    for t in tps:
        if t in C.HOUSE_OF_SECTION:
            _fact(p, dz, f"f:natal:house:{C.HOUSE_OF_SECTION[t]}", lang)
    if tps:
        pr = dz["prose"].get(f"p:natal_section:{tps[0]}")
        if pr:
            add_prose(p, f"p:natal_section:{tps[0]}", pr[f"text_{lang}"])
            p["source_kinds"].append("natal_reading")
    for b in [b for b in seen_bodies if b in C.BODIES][:2]:
        add_card(p, CARDS.chart_fact_card(ctx.natal(), b), f"chart fact card: {C.body(b, 'en')}")
    add_link(p, CARDS.section_link(tps[0], lang) if tps else CARDS.link("chart", lang))
    return p


def natal_section(ctx: TurnContext, p: dict, section_key: str) -> dict:
    dz, lang = ctx.dossier(), ctx.lang
    pr = dz["prose"].get(f"p:natal_section:{section_key}")
    if not pr:
        natal_topics(ctx, p, topics=[section_key])
        p["status"], p["absence"] = "absent", {"reason": "not_generated"}
        p["source_kinds"] = ["chart"]
        return p
    add_prose(p, f"p:natal_section:{section_key}", pr[f"text_{lang}"])
    for rid in pr["trace"][:12]:
        _natal_record(p, dz, rid)
    add_link(p, CARDS.section_link(section_key, lang))
    return p


# --- calendar helpers ----------------------------------------------------------------------------------------
def _cal_records(ctx: TurnContext, p: dict, unit_id: str, cap: int, goal: Optional[str] = None) -> None:
    """The CAL_03 unit's allowed records (its ``pool``), modern only by construction."""
    import cal_corpus
    u = ctx.units().get(unit_id)
    if not u:
        return
    _, modern = ctx.corpus()
    for r in u["pool"][:cap]:
        rec = modern.get(r["id"]) or {}
        k = cal_corpus.transit_key_of(rec) if rec else None
        claims = {"sign": [], "house": [], "aspect": [[k[0], k[2], k[1]]] if k else []}
        add_record(p, f"r:cal:{r['id']}", r["text"], polarity=r.get("polarity"), claims=claims)


def _transit_item(ctx: TurnContext, p: dict, ev: dict, ref_day: str) -> None:
    lang = ctx.lang
    ph = CARDS.phase_on(ev, ref_day)
    lab = f"{C.transit_item_label(ev['t_body'], ev['aspect'], ev['n_point'], lang)} ({C.PHASE[lang][ph]})"
    add_item(p, f"i:transit:{ev['id']}", lab, [ev["start_local"], ev["end_local"], *ev.get("exacts_local", [])],
             raw={"kind": "transit", "t": ev["t_body"], "a": ev["aspect"], "n": ev["n_point"],
                  "importance": ev["importance"]})


def _lunation_item(ctx: TurnContext, p: dict, ev: dict) -> None:
    lang = ctx.lang
    u = ctx.units().get(f"l:{ev['id']}", {})
    lab = u.get(f"label_{lang}") or ev["kind"]
    if ev.get("natal_house"):
        area = C.AREA[lang][ev["natal_house"]]
        lab += f", {area} alanında" if lang == "tr" else f", in your {area} area"
    add_item(p, f"i:lunation:{ev['id']}", lab, [ev["local_date"]],
             raw={"kind": ev["kind"], "sign": ev.get("sign"), "house": ev.get("natal_house"),
                  "body": "moon" if ev["kind"] in ("full_moon", "lunar_eclipse") else "sun"})


def _period_item(ctx: TurnContext, p: dict, per: dict) -> None:
    lang = ctx.lang
    lab = f"{C.GOAL[lang][per['goal']]}: {C.PERIOD_KIND[lang][per['kind']]}"
    add_item(p, f"i:period:{per['id']}", lab, [per["start_local"], per["end_local"], per["peak_local"]],
             band=per["kind"], band_label=C.PERIOD_KIND[lang][per["kind"]], raw={"kind": "period", **per})


def _in_cal(ctx: TurnContext, d: date) -> bool:
    a, b = ctx.cal_range()
    return a <= d <= b


def _has_text(ctx: TurnContext, unit_id: str) -> bool:
    return bool(ctx.cached_text(unit_id))


# --- day (PA_01 §4.4) ---------------------------------------------------------------------------------------------
def day(ctx: TurnContext, p: dict, date_: str, lens: str = "general") -> dict:
    lang = ctx.lang
    d = date.fromisoformat(date_)
    if not _in_cal(ctx, d) or d < ctx.today - timedelta(days=K.DAY_PAST_DAYS):
        a, b = ctx.cal_range()
        p["status"] = "out_of_range"
        p["absence"] = {"reason": "out_of_range", "allowed": {"from": a.isoformat(), "to": b.isoformat()}}
        return p
    cal = ctx.calendar()
    ds = d.isoformat()
    day_row = next((x for x in cal["scores"]["days"] if x["local_date"] == ds), None)
    if day_row:
        import cal_astro as A
        jd = A.local_time_jd(d, 12, 0, ctx.tz)
        moon_sign = A.sign_key(A.lon(jd, "moon"))
        retro = [b for b in ("mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto")
                 if A.lon_speed(jd, b)[1] < 0]
        bands = [f"{C.GOAL[lang][g]} {C.DAY_BAND[lang][v['band']]}" for g, v in day_row["goals"].items()
                 if v["band"] != "quiet"]
        moon = (f"Ay {C.SIGN['tr'][moon_sign]} burcunda" if lang == "tr" else f"Moon in {C.SIGN['en'][moon_sign]}")
        lab = (f"{C.fmt_date(ds, lang)}: " + (f"genel ton {C.TONE['tr'][day_row['tone']]}" if lang == "tr" else
                                               f"overall tone {C.TONE['en'][day_row['tone']]}"))
        if bands:
            lab += "; " + ", ".join(bands)
        lab += f"; {moon}"
        if retro:
            lab += "; " + ("retro: " if lang == "tr" else "retrograde: ") + ", ".join(C.body(b, lang) for b in retro)
        add_item(p, f"i:day:{ds}", lab, [ds], band=day_row["tone"], band_label=C.TONE[lang][day_row["tone"]],
                 raw={"kind": "day", "moon_sign": moon_sign, "bands": {g: v["band"] for g, v in day_row["goals"].items()}})
    eps = [e for e in cal["events"]["events"] if e["kind"] == "transit" and e["importance"] in ("major", "moderate")
           and e["start_local"] <= ds <= e["end_local"]]
    eps.sort(key=lambda e: (e["importance"] != "major",
                            min([abs((date.fromisoformat(x) - d).days) for x in e.get("exacts_local") or []] or [999]),
                            e["id"]))
    for e in eps[:4]:
        _transit_item(ctx, p, e, ds)
        _cal_records(ctx, p, f"t:{e['id']}", 4)
        add_card(p, {"type": "transit", "transit": CARDS.transit_episode(e, ds, lang, _has_text(ctx, f"t:{e['id']}"))},
                 f"transit card: {C.transit_item_label(e['t_body'], e['aspect'], e['n_point'], 'en')}") \
            if len(p["card_candidates"]) < 2 else None
    for e in cal["events"]["events"]:
        if e["kind"] in ("new_moon", "full_moon", "solar_eclipse", "lunar_eclipse") and e["local_date"] == ds:
            _lunation_item(ctx, p, e)
            _cal_records(ctx, p, f"l:{e['id']}", 3)
    try:
        best = ctx.best()
        for act, a in best["activities"].items():
            row = next((x for x in a["days"] if x["local_date"] == ds), None)
            if row and row["grade"] in ("excellent", "good"):
                add_item(p, f"i:bestday:{act}:{ds}", f"{C.ACTIVITY[lang][act]}: {C.GRADE[lang][row['grade']]}", [ds],
                         grade=row["grade"], band_label=C.GRADE[lang][row["grade"]], raw={"kind": "bestday"})
    except Exception:  # noqa: BLE001 - Best Days covers 90 days from today; a past day has none
        pass
    pr = ctx.predictive_reading("day", ds, lens)
    if pr and pr.get(lang):
        add_prose(p, f"p:forecast:day:{ds}:{lens}", pr[lang].get("reading", ""))
        p["source_kinds"].append("forecast")
    add_prose(p, f"p:caltext:d:{ds}", ctx.cached_text(f"d:{ds}"))
    for e in eps[:2]:
        add_prose(p, f"p:caltext:t:{e['id']}", ctx.cached_text(f"t:{e['id']}"))
    add_card(p, CARDS.forecast_card("day", lang, date=ds), "daily forecast card")
    add_link(p, CARDS.link("day", lang, date=ds))
    if not p["items"]:
        return absent(p, "no_data")
    return p


# --- span (PA_01 §4.5) ------------------------------------------------------------------------------------------
def span(ctx: TurnContext, p: dict, from_: str, to: str, goal: Optional[str] = None, lens: str = "general",
         include: Optional[list] = None) -> dict:
    lang = ctx.lang
    a0, b0 = date.fromisoformat(from_), date.fromisoformat(to)
    lo, hi = ctx.cal_range()
    a, b = max(a0, lo), min(b0, hi)
    if a > b:
        p["status"] = "out_of_range"
        p["absence"] = {"reason": "out_of_range", "allowed": {"from": lo.isoformat(), "to": hi.isoformat()}}
        return p
    if (a, b) != (a0, b0):
        p["clamped"] = {"asked": {"from": from_, "to": to}, "used": {"from": a.isoformat(), "to": b.isoformat()}}
    A_, B_ = a.isoformat(), b.isoformat()
    n_days = (b - a).days + 1
    inc = set(include or ["periods", "transits", "lunations", "eclipses", "retrogrades", "favorable_days"])
    cal = ctx.calendar()
    ref_day = max(A_, ctx.today.isoformat()) if A_ <= ctx.today.isoformat() <= B_ else A_
    overl = lambda s, e: s <= B_ and e >= A_  # noqa: E731
    if "periods" in inc:
        pers = [x for x in cal["periods"]["periods"] if overl(x["start_local"], x["end_local"])
                and (goal is None or x["goal"] == goal)]
        for x in pers:
            _period_item(ctx, p, x)
        rich = [x for x in pers if x["importance"] == "major" or x["strength"] == "strong"][:3]
        for x in rich:
            _cal_records(ctx, p, f"p:{x['id']}", 4)
        for x in rich[:2]:
            add_card(p, {"type": "period", "period": CARDS.period_ref(x, lang, _has_text(ctx, f"p:{x['id']}"))},
                     f"period card: {C.GOAL['en'][x['goal']]} {x['kind']}")
            add_prose(p, f"p:caltext:p:{x['id']}", ctx.cached_text(f"p:{x['id']}"))
    if "transits" in inc:
        trs = [e for e in cal["events"]["events"] if e["kind"] == "transit" and overl(e["start_local"], e["end_local"])
               and (e["importance"] == "major" or (e["importance"] == "moderate" and n_days <= 31))]
        trs.sort(key=lambda e: (e["importance"] != "major", e["start_local"], e["id"]))
        for e in trs:
            _transit_item(ctx, p, e, ref_day)
        majors = [e for e in trs if e["importance"] == "major"][:3]
        for e in majors:
            _cal_records(ctx, p, f"t:{e['id']}", 3)
        if majors:
            e = majors[0]
            add_card(p, {"type": "transit", "transit": CARDS.transit_episode(e, ref_day, lang, _has_text(ctx, f"t:{e['id']}"))},
                     f"transit card: {C.transit_item_label(e['t_body'], e['aspect'], e['n_point'], 'en')}")
    if inc & {"lunations", "eclipses"}:
        luns = [e for e in cal["events"]["events"] if e["kind"] in ("new_moon", "full_moon", "solar_eclipse", "lunar_eclipse")
                and A_ <= e["local_date"] <= B_
                and (("eclipses" in inc and e["kind"].endswith("eclipse")) or ("lunations" in inc and e["kind"].endswith("moon")))]
        for e in luns:
            _lunation_item(ctx, p, e)
        for e in [e for e in luns if e["importance"] != "minor"][:2]:
            _cal_records(ctx, p, f"l:{e['id']}", 2)
    if "retrogrades" in inc:
        coll = ctx.collective()
        for c in cal["events"]["collective_refs"]:
            if c["kind"] == "retrograde_period" and overl(c["start_local"], c["end_local"]):
                import cr_sections as CS
                tr, en = CS.collective_label(coll[c["id"]])
                add_item(p, f"i:retro:{c['id']}", tr if lang == "tr" else en, [c["start_local"], c["end_local"]],
                         raw={"kind": "retro"})
    if "favorable_days" in inc and n_days <= 62:
        for row in cal["scores"]["days"]:
            if A_ <= row["local_date"] <= B_ and row["tone"] in ("favorable", "challenging"):
                if goal and row["goals"][goal]["band"] == "quiet":
                    continue
                add_item(p, f"i:day:{row['local_date']}", f"{C.fmt_date(row['local_date'], lang)}: {C.TONE[lang][row['tone']]}",
                         [row["local_date"]], band=row["tone"], band_label=C.TONE[lang][row["tone"]], raw={"kind": "day"})
    # prose: a month reading when the range is exactly a calendar month
    month = None
    if a.day == 1 and (b + timedelta(days=1)).day == 1 and a.month == b.month:
        month = A_[:7]
        pr = ctx.predictive_reading("month", A_, lens)
        if pr and pr.get(lang):
            r = pr[lang]
            add_prose(p, f"p:forecast:month:{month}:{lens}", f"{r.get('overview', '')} {r.get('focus', '')}")
            add_card(p, CARDS.forecast_card("month", lang, month=month), "month forecast card")
            p["source_kinds"].append("forecast")
    add_link(p, CARDS.month_link(A_[:7], lang) if A_[:7] == B_[:7] else CARDS.link("calendar", lang))
    if not p["items"]:
        return absent(p, "no_data")
    return p


# --- best days (PA_01 §4.6) ---------------------------------------------------------------------------------------
def best_days(ctx: TurnContext, p: dict, activities: list[str], from_: Optional[str] = None,
              to: Optional[str] = None) -> dict:
    import best_days as BD
    lang = ctx.lang
    lo, hi = ctx.today, ctx.today + timedelta(days=K.BEST_DAYS_DAYS - 1)
    a0 = date.fromisoformat(from_) if from_ else lo
    b0 = date.fromisoformat(to) if to else lo + timedelta(days=K.BEST_DAYS_DEFAULT_DAYS - 1)
    a, b = max(a0, lo), min(b0, hi)
    if a > b:
        p["status"] = "out_of_range"
        p["absence"] = {"reason": "out_of_range", "allowed": {"from": lo.isoformat(), "to": hi.isoformat()}}
        return p
    if (a, b) != (a0, b0) and (from_ or to):
        p["clamped"] = {"asked": {"from": a0.isoformat(), "to": b0.isoformat()},
                        "used": {"from": a.isoformat(), "to": b.isoformat()}}
    A_, B_ = a.isoformat(), b.isoformat()
    best = ctx.best()
    index, modern = ctx.corpus()
    for act in activities[:2]:
        a_doc = best["activities"][act]
        rows = [r for r in a_doc["days"] if A_ <= r["local_date"] <= B_]
        good = [r for r in rows if r["grade"] in ("excellent", "good")]
        name = C.ACTIVITY[lang][act]
        for r in good:
            add_item(p, f"i:bestday:{act}:{r['local_date']}", f"{name}: {C.GRADE[lang][r['grade']]}", [r["local_date"]],
                     grade=r["grade"], band_label=C.GRADE[lang][r["grade"]], raw={"kind": "bestday", "activity": act})
        if not good:
            add_item(p, f"i:bestday_none:{act}", (f"{name}: bu aralıkta iyi ya da mükemmel gün yok" if lang == "tr"
                                                 else f"{name}: no good or excellent day in this range"), [A_, B_],
                     raw={"kind": "bestday_none"})
        for r in rows:
            if r["grade"] == "avoid":
                add_item(p, f"i:avoidday:{act}:{r['local_date']}", f"{name}: {C.GRADE[lang]['avoid']}", [r["local_date"]],
                         grade="avoid", band_label=C.GRADE[lang]["avoid"], raw={"kind": "avoid"})
        for w in a_doc["windows"]:
            if w["start"] <= B_ and w["end"] >= A_:
                add_item(p, f"i:window:{act}:{w['start']}", (f"{name}: destekleyici aralık" if lang == "tr"
                                                            else f"{name}: supportive window"), [w["start"], w["end"]],
                         raw={"kind": "window"})
        top = sorted(good, key=lambda r: (-r["R"], r["local_date"]))[:3]
        for r in sorted(top, key=lambda r: r["local_date"]):
            ds = r["local_date"]
            parts = sorted((x for x in r.get("_parts", []) if x["contribution"] > 0), key=lambda x: -x["contribution"])
            negs = sorted((x for x in r.get("_parts", []) if x["contribution"] < 0), key=lambda x: x["contribution"])
            reasons = BD.reasons(r.get("_parts", []))
            labs = [clean_render(x[f"label_{lang}"]) for x in reasons["positive"]]
            labs = [lab for lab in labs if lab]
            add_item(p, f"i:bestday_why:{act}:{ds}", f"{name} {C.fmt_date(ds, lang)}: " + "; ".join(labs), [ds],
                     raw={"kind": "why", "parts": parts[:3] + negs[:2]})
            n = 0
            for part in parts:
                for pid in BD.part_records(part, index):
                    rec = modern.get(pid)
                    if rec and n < 3:
                        import cal_corpus
                        k = cal_corpus.transit_key_of(rec)
                        add_record(p, f"r:bd:{pid}", " ".join(x for x in (rec.get("rule"), rec.get("judgment")) if x),
                                   claims={"sign": [], "house": [], "aspect": [[k[0], k[2], k[1]]] if k else []})
                        n += 1
            add_prose(p, f"p:caltext:b:{act}:{ds}", ctx.cached_text(f"b:{act}:{ds}"))
        add_card(p, CARDS.best_days_card(act, good[:7]), f"best days card: {C.ACTIVITY['en'][act]}")
        add_link(p, CARDS.link("best_days", lang, activity=act))
    return p


# --- calendar item (PA_01 §4.7) -----------------------------------------------------------------------------------
def calendar_item(ctx: TurnContext, p: dict, item_id: str) -> dict:
    lang = ctx.lang
    cal = ctx.calendar()
    today = ctx.today.isoformat()
    ev = next((e for e in cal["events"]["events"] if e["id"] == item_id), None)
    if ev and ev["kind"] == "transit":
        _transit_item(ctx, p, ev, today)
        _cal_records(ctx, p, f"t:{item_id}", 4)
        add_prose(p, f"p:caltext:t:{item_id}", ctx.cached_text(f"t:{item_id}"))
        add_card(p, {"type": "transit", "transit": CARDS.transit_episode(ev, today, lang, _has_text(ctx, f"t:{item_id}"))},
                 "transit card")
    elif ev and ev["kind"] in ("new_moon", "full_moon", "solar_eclipse", "lunar_eclipse"):
        _lunation_item(ctx, p, ev)
        _cal_records(ctx, p, f"l:{item_id}", 3)
        add_prose(p, f"p:caltext:l:{item_id}", ctx.cached_text(f"l:{item_id}"))
    elif ev:
        u = ctx.units().get(f"s:{item_id}", {})
        add_item(p, f"i:event:{item_id}", u.get(f"label_{lang}") or item_id, [ev.get("local_date") or ev.get("t_utc", "")[:10]],
                 raw={"kind": ev["kind"]})
    else:
        per = next((x for x in cal["periods"]["periods"] if x["id"] == item_id), None)
        if not per:
            return absent(p, "item_not_found")
        _period_item(ctx, p, per)
        _cal_records(ctx, p, f"p:{item_id}", 4)
        add_prose(p, f"p:caltext:p:{item_id}", ctx.cached_text(f"p:{item_id}"))
        add_card(p, {"type": "period", "period": CARDS.period_ref(per, lang, _has_text(ctx, f"p:{item_id}"))}, "period card")
    add_link(p, CARDS.link("calendar_item", lang, id=item_id))
    return p


# --- places (PA_01 §4.8) ------------------------------------------------------------------------------------------
def search_places(text: str) -> dict:
    """Deterministic gazetteer search, TR + EN names and aliases, misspelling-tolerant (Phase 0 G2).
    -> {"status": "ok" | "ambiguous" | "not_found", "place": row?, "options": [row]}. Never geocodes."""
    import acg_locate as al
    gaz = al.load_gazetteer()
    q = (text or "").split(",")[0].strip()
    hit = al.gazetteer_lookup(q, gaz)
    if hit:
        row = next((r for r in gaz if r["id"] == hit["id"]), None) if isinstance(hit, dict) and "id" in hit else None
        return {"status": "ok", "place": row or hit, "options": []}
    fq = al._fold(q)
    scored: dict = {}
    for r in gaz:
        for nm in {r["name"], r.get("name_tr") or r["name"], *(r.get("aliases") or [])}:
            s = difflib.SequenceMatcher(None, fq, al._fold(nm)).ratio()
            if s > scored.get(r["id"], (0, None))[0]:
                scored[r["id"]] = (s, r)
    cand = sorted((v for v in scored.values() if v[0] >= 0.82), key=lambda v: (-v[0], -(v[1].get("population") or 0)))
    if not cand:
        return {"status": "not_found", "place": None, "options": []}
    best_s = cand[0][0]
    close = [r for s, r in cand if s >= best_s - 0.04][:4]
    if len(close) == 1 or best_s >= 0.9 and (len(cand) == 1 or cand[1][0] < best_s - 0.04):
        return {"status": "ok", "place": cand[0][1], "options": []}
    return {"status": "ambiguous", "place": None, "options": close}


def _place_by_id(place_id: str) -> Optional[dict]:
    import acg_locate as al
    for r in al.load_gazetteer():
        if r["id"] == place_id:
            return r
    try:
        import acg_destinations as dst
        d = dst.destination(place_id)
        if d:
            return {"id": d["id"], "name": d["name"], "name_tr": d.get("name_tr") or d["name"],
                    "country_code": d.get("country"), "lat": d["lat"], "lon": d["lon"]}
    except Exception:  # noqa: BLE001
        pass
    return None


SUITABILITY_GOALS = ["travel", "relocation", "career", "business", "love", "family"]   # ACG_07 §6.2 (X8)


def _acg_record(p: dict, r: dict, extra_claims: Optional[dict] = None) -> None:
    add_record(p, f"r:acg:{r['principle_id']}", " ".join(x for x in (r.get("rule"), r.get("judgment")) if x),
               polarity=r.get("polarity"), sensitivity=r.get("sensitivity") or "normal",
               claims=extra_claims or {"sign": [], "house": [], "aspect": []})


def place(ctx: TurnContext, p: dict, place_id: Optional[str] = None, place_text: Optional[str] = None,
          goals: Optional[list] = None) -> dict:
    import acg_locate as al
    import ground_acg as ga
    lang = ctx.lang
    row = _place_by_id(place_id) if place_id else None
    if not row and place_text:
        res = search_places(place_text)
        if res["status"] == "ambiguous":
            p["status"] = "needs_input"
            p["needs_input"] = {"kind": "place_ambiguous",
                                "options": [{"place_id": r["id"], "name": r["name_tr"] if lang == "tr" else r["name"],
                                             "country": r.get("country_code")} for r in res["options"]]}
            return p
        if res["status"] == "not_found":
            p["status"] = "needs_input"
            p["needs_input"] = {"kind": "place_not_found", "options": []}
            return p
        row = res["place"]
    if not row:
        p["status"] = "needs_input"
        p["needs_input"] = {"kind": "place_not_found", "options": []}
        return p
    prod = ctx.acg()
    if prod["acg"].get("status") != "ok":
        return absent(p, (prod["acg"].get("absence") or {}).get("reason", "acg_absent"))
    plc = {"query": row["name"], "name": row["name"], "name_tr": row.get("name_tr") or row["name"],
           "lat": row["lat"], "lon": row["lon"], "country_code": row.get("country_code"), "source": "gazetteer"}
    b = ctx.subject["birth"]["place"]
    loc, reloc = al.build_locate(prod["acg"], ctx.natal(), plc, natal_latlon=(b["lat"], b["lon"]),
                                 parans=prod.get("parans"))
    ok, _ = ga.corpus_ok()
    if not ok:
        return absent(p, "acg_corpus_missing")
    payload, _drops = ga.ground_acg(ctx.natal(), reloc, loc, ga.load_json(ga.ACG_CORPUS_PATH),
                                    ga.load_json(ga.MAIN_CORPUS_PATH), acg=prod["acg"], affinity=prod["aff"],
                                    parans=prod.get("parans"))
    name = plc["name_tr"] if lang == "tr" else plc["name"]
    p["_internal"]["place"] = {"place_id": row["id"], "name": name, "country": plc["country_code"]}
    for ln in payload.get("lines_display", []):
        lab = (f"{ln['planet_tr']} – {ln['angle_label_tr']}, {C.TIER['tr'][ln['tier']]}" if lang == "tr"
               else f"{ln['planet_en']} – {ln['angle_label_en']}, {C.TIER['en'][ln['tier']]}")
        add_item(p, f"i:line:{row['id']}:{ln['body']}:{ln['angle']}", lab, [], raw={"kind": "line", **ln})
    gc = payload.get("goal_contributors") or {}
    for g in C.GOAL["en"]:
        if g in gc:
            bd = gc[g]["band"]
            add_item(p, f"i:place:{row['id']}:{g}", f"{name} – {C.GOAL[lang][g]}: {C.PLACE_BAND[lang][bd]}", [],
                     band=bd, band_label=C.PLACE_BAND[lang][bd], raw={"kind": "place_goal", "goal": g})
    rel = (loc.get("relocation") or {}).get("status")
    if rel and rel != "ok":
        add_item(p, f"i:relocation:{row['id']}", ("yerel ev konumları hesaplanamadı" if lang == "tr"
                                                 else "local house positions not available"), [], raw={"kind": "relocation"})
    records = {r["principle_id"]: r for bundle in payload.get("bundles", []) for r in bundle["records"]}
    records.update({r["principle_id"]: r for r in (payload.get("goal_records") or [])})
    frames = [r for bundle in payload.get("bundles", []) for r in bundle["records"] if r.get("acg_scope") == "angle_frame"]
    if goals:
        for g in goals[:2]:
            for pid in (gc.get(g) or {}).get("contributors", [])[:8]:
                if pid in records:
                    _acg_record(p, records[pid])
    else:
        for bundle in payload.get("bundles", [])[:4]:
            for r in [r for r in bundle["records"] if r.get("acg_scope") == "line"][:4]:
                _acg_record(p, r)
    for r in frames[:1]:
        _acg_record(p, r)
    for pid in ACG_METHOD_IDS:
        if pid in records:
            _acg_record(p, records[pid])
        else:
            mr = _acg_corpus().get(pid)
            if mr:
                _acg_record(p, mr)
    shown = list(goals or []) + [g for g in SUITABILITY_GOALS if g not in (goals or [])]
    add_card(p, CARDS.place_card(row["id"], name, plc["country_code"] or "",
                                 [(g, gc[g]["band"]) for g in shown[:6] if g in gc], lang), f"place card: {plc['name']}")
    add_link(p, CARDS.link("place", lang, label=name, place_id=row["id"]))
    return p


_ACG_CORPUS: dict = {}


def _acg_corpus() -> dict:
    if not _ACG_CORPUS:
        import ground_acg as ga
        ok, _ = ga.corpus_ok()
        if ok:
            _ACG_CORPUS.update({r["principle_id"]: r for r in ga.load_json(ga.ACG_CORPUS_PATH)})
    return _ACG_CORPUS


# --- recommend (PA_01 §4.9) ---------------------------------------------------------------------------------------
def recommend(ctx: TurnContext, p: dict, goal: str, scope: str = "world") -> dict:
    import acg_destinations as dst
    import acg_line_first as lf
    import acg_recommend as rec
    lang = ctx.lang
    prod = ctx.acg()
    if prod["acg"].get("status") != "ok" or prod.get("goal_scan") is None:
        return absent(p, "acg_absent")
    rec.set_parans(prod.get("parans"))
    b = ctx.subject["birth"]["place"]
    flt = dst.resolve_filters(goal, regions=None, city_size=None, max_distance_km=None, home_latlon=(b["lat"], b["lon"]),
                              climate=None, purpose=None)
    rk = lf.rank_line_first(goal, scope, prod["acg"], prod["goal_scan"], prod["aff"], flt)
    corpus = _acg_corpus()
    top = rk["cities"][:5]
    tk = (rk.get("turkey") or {}).get("cities", [])[:3] if scope == "world" else []

    def item(c, pre):
        nm = c["name_tr"] if lang == "tr" else c["name"]
        dl = c.get("dominant_line") or {}
        line = (f"{C.body(dl.get('body', ''), lang)} – {dl.get('angle', '')}" if dl.get("body") else "")
        lab = f"{nm}: {C.PLACE_BAND[lang][c['band']]}" + (f" ({line})" if line else "")
        if c.get("has_tradeoff"):
            lab += "; " + ("bazı zorlayıcı yönleri de var" if lang == "tr" else "also has demanding sides")
        add_item(p, f"i:{pre}:{c['id']}", lab, [], band=c["band"], band_label=C.PLACE_BAND[lang][c["band"]],
                 raw={"kind": "recommend", "id": c["id"]})
    for c in top:
        item(c, "rec")
    for c in tk:
        item(c, "rec_tr")
    if rk.get("thin_result"):
        add_item(p, "i:thin_result", "kısa liste" if lang == "tr" else "short list", [], raw={"kind": "thin_result"})
        p["_internal"]["thin_result"] = True
    for c in top[:3] + tk[:1]:
        for pid in (c.get("contributors") or [])[:4]:
            if pid in corpus:
                _acg_record(p, corpus[pid])
    for pid in ACG_METHOD_IDS:
        if pid in corpus:
            _acg_record(p, corpus[pid])
    for c in top[:3]:
        add_card(p, CARDS.place_card(c["id"], c["name_tr"] if lang == "tr" else c["name"], c.get("country") or "",
                                     [(goal if goal != "overall" else "relocation", c["band"])], lang),
                 f"place card: {c['name']}")
    add_link(p, CARDS.link("recommend", lang, goal=goal, scope=scope))
    if not top:
        return absent(p, "no_data")
    return p


# --- compatibility (PA_01 §4.10) ------------------------------------------------------------------------------------
REL_TYPE = {"partner": "love", "colleague": "work", "business_partner": "work", "parent": "family",
            "child": "family", "family": "family", "friend": "general", "other": "general", "self": "general"}
TYPE_LENS = {"love": "personal", "work": "professional", "family": "general", "general": "general"}


def _big_three(chart: dict) -> dict:
    out = {}
    for pt in chart["points"]:
        if pt["name"] in ("Sun", "Moon"):
            out[pt["name"].lower()] = pt["sign"].lower()
    if chart.get("axes"):
        out["asc"] = chart["axes"]["ascendant"]["sign"].lower()
    return out


def compatibility(ctx: TurnContext, p: dict, other: Optional[str] = None, compatibility_id: Optional[str] = None,
                  type: Optional[str] = None) -> dict:  # noqa: A002 - the spec's argument name
    import ground_relationship as gr
    import s3_profiles
    import s3_routing
    lang = ctx.lang
    comp = None
    if compatibility_id:
        comp = next((c for c in ctx.compatibilities if c["compatibility_id"] == compatibility_id), None)
        if comp:
            other_pid = comp["profile_b_id"] if comp["profile_a_id"] == ctx.subject.get("profile_id") else comp["profile_a_id"]
            other = next((h for h, pr in ctx.people.items() if pr.get("profile_id") == other_pid), other)
            type = type or comp["type"]
    if not other or other not in ctx.people:
        p["status"] = "needs_input"
        p["needs_input"] = {"kind": "person_unknown", "options": [{"handle": h, "label": pr["label"]}
                                                                for h, pr in ctx.people.items()]}
        return p
    prof = ctx.people[other]
    ctype = type or REL_TYPE.get(prof.get("relation", "other"), "general")
    lens = TYPE_LENS[ctype]
    a, bch = ctx.natal(), ctx.person_chart(other)
    with open(gr.__file__.replace("ground_relationship.py", "combined_relationship_principles_tagged.json"),
              encoding="utf-8") as fh:
        recs = json.load(fh)
    pl = gr.ground_relationship(recs, a, bch).payload()
    routed = s3_routing.route(pl, s3_profiles.get_profile(lens),
                              houses_valid=bool(a.get("axes")) and bool(bch.get("axes")))
    by_id = {}
    for part in ("synastry", "person_a", "person_b", "framing"):
        for r in pl.get(part) or []:
            by_id.setdefault(r["principle_id"], r)
    order = []
    for key in routed.section_order:
        for it in routed.sections.get(key, []):
            pid = it.get("principle_id") if isinstance(it, dict) else getattr(it, "principle_id", None)
            if pid and pid not in order:
                order.append(pid)
    for pid in order[:30]:
        r = by_id.get(pid)
        if r:
            add_record(p, f"r:syn:{pid}", (r.get("bound_statement") or r.get("rule") or "").strip(),
                       polarity=r.get("polarity"), sensitivity=r.get("sensitivity"))
    lab = prof["label"]
    for who, ch, fid in (("self", a, "f:natal"), (other, bch, f"f:other:{other}")):
        for k, sign in _big_three(ch).items():
            body = C.body(k, lang)
            name = "" if who == "self" else f"{lab}: "
            add_fact(p, f"{fid}:{k}", f"{name}{body}: {C.SIGN[lang][sign]}" if lang == "tr"
                     else f"{name}{body} in {C.SIGN['en'][sign]}", {"kind": "big_three", "body": k, "sign": sign,
                                                                   "who": who})
    p["_internal"]["other_label"] = lab
    p["_internal"]["lens"] = lens
    existing = comp or next((c for c in ctx.compatibilities if c.get("type") == ctype and
                             prof.get("profile_id") in (c["profile_a_id"], c["profile_b_id"])), None)
    if existing and ctype in ("love", "work", "family"):
        add_card(p, CARDS.compatibility_card(existing["compatibility_id"], (ctx.subject["label"], lab), ctype),
                 f"compatibility card with {lab}")
        add_link(p, CARDS.link("compatibility", lang, id=existing["compatibility_id"]))
    else:
        add_link(p, CARDS.link("compatibility_new", lang, profile_id=prof.get("profile_id", ""),
                               type=ctype if ctype in ("love", "work", "family") else "love"))
    if not p["records"]:
        return absent(p, "no_grounding")
    return p


# --- astro basics (PA_01 §4.11) -------------------------------------------------------------------------------------
BASICS_KINDS = ["planet", "life_area", "aspect_cycle", "lunation", "eclipse", "retrograde", "acg_line"]


def astro_basics(ctx: TurnContext, p: dict, kind: str, key: str) -> dict:
    import cal_corpus
    index, modern = cal_corpus.load()
    ids: list[str] = []
    if kind == "planet":
        k = key.title()
        ids = [i for i, r in sorted(modern.items()) if r.get("domain") == "basics"
               and (r.get("about") or {}).get("point") == k][:6]
    elif kind == "life_area":
        h = C.HOUSE_OF_SECTION.get(key) or (int(key) if str(key).isdigit() else None)
        ids = (index["house_domain"].get(h, []) if h else [])[:6]
    elif kind == "aspect_cycle":
        ids = [i for i in (f"transit-aspect-summary-{key}", "separating-vs-approaching-aspect-distinction") if i in modern]
    elif kind in ("lunation", "eclipse"):
        ids = index["generic"][kind][:6]
    elif kind == "retrograde":
        ids = [i for i, r in sorted(modern.items()) if "retrograde" in " ".join(r.get("topic_tags") or []).lower()
               and r.get("domain") in ("basics", "predictive")][:6]
    elif kind == "acg_line":
        corp = _acg_corpus()
        ids = [i for i in (f"acg-angle-{key.lower()}",) if i in corp]
        for i in ids:
            _acg_record(p, corp[i])
        if not p["records"]:
            return absent(p, "no_grounding")
        return p
    for i in ids:
        r = modern[i]
        add_record(p, f"r:basics:{i}", " ".join(x for x in (r.get("rule"), r.get("judgment")) if x),
                   claims={"sign": [], "house": [], "aspect": []})
    if not p["records"]:
        return absent(p, "no_grounding")
    p["_internal"]["general"] = True
    return p


# --- context -> forced calls (PA_01 §5) ------------------------------------------------------------------------------
def forced_calls(context: Optional[dict], ctx: TurnContext, lens: str = "general") -> list[tuple[str, dict]]:
    """FE context ids -> the calls that run first. ``activity`` + ``date`` (a Best Days day) is one
    best_days call for that day; ``compatibility_id`` + ``other_profile_id`` (a compatibility report)
    is one compatibility call."""
    import calendar as _cal
    c = context or {}
    out: list[tuple[str, dict]] = []
    if c.get("section_key"):
        out.append(("natal_section", {"section_key": c["section_key"]}))
    if c.get("activity"):
        a = {"activities": [c["activity"]]}
        if c.get("date"):
            a.update({"from": c["date"], "to": c["date"]})
        out.append(("best_days", a))
    elif c.get("date"):
        out.append(("day", {"date": c["date"], "lens": lens}))
    if c.get("month"):
        y, m = (int(x) for x in c["month"].split("-"))
        out.append(("span", {"from": f"{y:04d}-{m:02d}-01", "to": f"{y:04d}-{m:02d}-{_cal.monthrange(y, m)[1]:02d}",
                             "lens": lens}))
    if c.get("place_id"):
        out.append(("place", {"place_id": c["place_id"]}))
    if c.get("compatibility_id"):
        out.append(("compatibility", {"compatibility_id": c["compatibility_id"]}))
    elif c.get("other_profile_id"):
        h = next((h for h, pr in ctx.people.items() if pr.get("profile_id") == c["other_profile_id"]), None)
        out.append(("compatibility", {"other": h}))
    if c.get("item_id"):
        out.append(("calendar_item", {"item_id": c["item_id"]}))
    return out[:K.MAX_CALLS]


# --- dispatch + caps ------------------------------------------------------------------------------------------------
_IMPL: dict[str, Callable] = {
    "chart_facts": lambda ctx, p, a: chart_facts(ctx, p, a.get("bodies"), a.get("angles"), a.get("big_three")),
    "natal_topics": lambda ctx, p, a: natal_topics(ctx, p, a.get("topics"), a.get("goals"), a.get("bodies"),
                                                   a.get("depth", "normal")),
    "natal_section": lambda ctx, p, a: natal_section(ctx, p, a["section_key"]),
    "day": lambda ctx, p, a: day(ctx, p, a["date"], a.get("lens", "general")),
    "span": lambda ctx, p, a: span(ctx, p, a["from"], a["to"], a.get("goal"), a.get("lens", "general"), a.get("include")),
    "best_days": lambda ctx, p, a: best_days(ctx, p, a["activities"], a.get("from"), a.get("to")),
    "calendar_item": lambda ctx, p, a: calendar_item(ctx, p, a["item_id"]),
    "place": lambda ctx, p, a: place(ctx, p, a.get("place_id"), a.get("place_text"), a.get("goals")),
    "recommend": lambda ctx, p, a: recommend(ctx, p, a["goal"], a.get("scope", "world")),
    "compatibility": lambda ctx, p, a: compatibility(ctx, p, a.get("other"), a.get("compatibility_id"), a.get("type")),
    "astro_basics": lambda ctx, p, a: astro_basics(ctx, p, a["kind"], a["key"]),
}


def run_tool(ctx: TurnContext, call_id: str, tool: str, args: dict, forced: bool = False) -> dict:
    p = new_pack(call_id, tool, args, forced)
    try:
        return _IMPL[tool](ctx, p, args)
    except KeyError as err:                    # a malformed call is a missing item, never a crash
        return absent(p, "item_not_found", detail=str(err))


def apply_caps(packs: list[dict]) -> list[dict]:
    """PA_01 §3.4: per turn <= 40 records, <= 3 prose, <= 30 items; trim from the end of each call's
    list proportionally, keeping >= 4 records per call that has any. Deterministic."""
    def trim(field: str, cap: int, keep_min: int) -> None:
        total = sum(len(p[field]) for p in packs)
        if total <= cap:
            return
        sizes = [len(p[field]) for p in packs]
        quota = [min(s, max(keep_min if s else 0, (s * cap) // total)) for s in sizes]
        spare = cap - sum(quota)
        for i in sorted(range(len(packs)), key=lambda i: -sizes[i]):
            if spare <= 0:
                break
            add = min(spare, sizes[i] - quota[i])
            quota[i] += add
            spare -= add
        for p, q in zip(packs, quota):
            p[field] = p[field][:q]
    trim("records", K.CAP_RECORDS, K.MIN_RECORDS_PER_CALL)
    trim("items", K.CAP_ITEMS, 1)
    trim("prose", K.CAP_PROSE, 0)
    return packs
