"""pa_cards.py - AskCard and link builders (PA_01 §6), in the exact FE_09 §4.3 shapes.

Cards are built deterministically from evidence; the model only picks among candidates (D12).
Link routes use the FE app's route forms (Phase 0 X7, Radul 2026-10-05); the app's validating
mapper (FX4.6) sends anything unknown to the tab.
"""

from __future__ import annotations

from typing import Optional

import _paths  # noqa: F401
import pa_catalogue as C  # noqa: E402

# --- link table (label TR / EN, route template) ------------------------------------------------------------
LINKS = {
    "chart":          (("Haritam", "My chart"), "/chart"),
    "chart_section":  ((None, None), "/chart/section/{key}"),            # label = the section title
    "day":            (("Günün yorumu", "This day"), "/ahead?view=day&date={date}"),
    "month":          ((None, None), "/forecast/month/{month}"),          # label = the month name
    "calendar":       (("Takvim", "Calendar"), "/ahead?view=calendar"),
    "calendar_item":  (("Takvim", "Calendar"), "/calendar/item/{id}"),
    "best_days":      (("En İyi Günler", "Best Days"), "/best-days/{activity}"),
    "place":          ((None, None), "/map?place={place_id}"),            # label = the place name
    "recommend":      (("Nereye Gitmeliyim?", "Where Should I Go?"), "/map/recommend?goal={goal}&scope={scope}"),
    "compatibility":  (("Uyum", "Compatibility"), "/match/{id}"),
    "compatibility_new": (("Uyum", "Compatibility"), "/match/new?b={profile_id}&type={type}"),
    "add_person":     (("Kişi ekle", "Add a person"), "/profile/charts/new"),
}


def link(kind: str, lang: str, label: Optional[str] = None, **slots) -> dict:
    (tr, en), tmpl = LINKS[kind]
    lab = label or (tr if lang == "tr" else en)
    return {"label": lab, "route": tmpl.format(**slots)}


def section_link(key: str, lang: str) -> dict:
    return link("chart_section", lang, C.SECTION_TITLE[lang][key], key=key)


def month_link(month: str, lang: str) -> dict:
    y, m = (int(x) for x in month.split("-"))
    return link("month", lang, f"{C.MONTHS[lang][m - 1]} {y}", month=month)


# --- cards -------------------------------------------------------------------------------------------------------
def _key(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def chart_fact_card(chart: dict, body: str) -> Optional[dict]:
    """FE_02 §7.2 mapping: degree_in_sign at full precision, Placidus house."""
    for p in chart["points"]:
        if _key(p["name"]) == body:
            return {"type": "chart_fact", "body": body, "sign": p["sign"].lower(),
                    "degree_in_sign": p["degree_in_sign"], "house": (p.get("sector") or {}).get("placidus"),
                    "retrograde": bool(p.get("retrograde"))}
    return None


def best_days_card(activity: str, days: list[dict]) -> dict:
    return {"type": "best_days", "activity": activity,
            "days": [{"date": d["local_date"], "grade": d["grade"]} for d in days]}


def place_card(place_id: str, name: str, country_code: str, goals: list[tuple[str, str]], lang: str) -> dict:
    return {"type": "place", "place_id": place_id, "name": name, "country_code": country_code,
            "cards": [{"goal": g, "band": b, "band_label": C.PLACE_BAND[lang][b]} for g, b in goals]}


def period_ref(p: dict, lang: str, has_text: bool) -> dict:
    """periods.json entry -> FE_02 §7.4 PeriodRef."""
    return {"id": p["id"], "goal": p["goal"], "goal_label": C.GOAL[lang][p["goal"]], "kind": p["kind"],
            "label": f"{C.GOAL[lang][p['goal']]}: {C.PERIOD_KIND[lang][p['kind']]}",
            "start": p["start_local"], "end": p["end_local"], "peak": p["peak_local"],
            "strength": p["strength"], "importance": p["importance"], "has_text": has_text}


def phase_on(ev: dict, ds: str) -> str:
    """FE_02 §6.3: building before the first exact, easing after the last, else peak."""
    ex = ev.get("exacts_local") or []
    if not ex:
        return "peak" if ev["start_local"] <= ds <= ev["end_local"] else ("building" if ds < ev["start_local"] else "easing")
    if ds < min(ex):
        return "building"
    if ds > max(ex):
        return "easing"
    return "peak"


def transit_episode(ev: dict, ds: str, lang: str, has_text: bool) -> dict:
    """personal_events transit -> FE_02 §7.3 TransitEpisode, phase relative to ``ds``."""
    ph = phase_on(ev, ds)
    natal = ev["n_point"].upper() if ev["n_point"] in ("asc", "mc") else ev["n_point"]
    return {"id": ev["id"], "label": C.transit_item_label(ev["t_body"], ev["aspect"], ev["n_point"], lang),
            "importance": ev["importance"], "transiting": ev["t_body"], "aspect": ev["aspect"], "natal": natal,
            "start": ev["start_local"], "end": ev["end_local"], "exact_dates": list(ev.get("exacts_local") or []),
            "phase": ph, "phase_label": C.PHASE[lang][ph], "has_text": has_text}


def compatibility_card(compatibility_id: str, labels: tuple[str, str], compat_type: str) -> dict:
    return {"type": "compatibility", "compatibility_id": compatibility_id, "labels": list(labels),
            "compat_type": compat_type}


def forecast_card(horizon: str, lang: str, date: Optional[str] = None, month: Optional[str] = None) -> dict:
    if horizon == "day":
        title = "Günlük yorum" if lang == "tr" else "Daily forecast"
    elif horizon == "month":
        y, m = (int(x) for x in month.split("-"))
        title = f"{C.MONTHS[lang][m - 1]} {y}"
    else:
        title = "Yıllık yorum" if lang == "tr" else "Year ahead"
    card = {"type": "forecast", "horizon": horizon, "title": title}
    if date:
        card["date"] = date
    if month:
        card["month"] = month
    return card
