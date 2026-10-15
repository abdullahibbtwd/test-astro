#!/usr/bin/env python3
"""ar_render.py — the ACG reading artifacts: reading_tr.json, reading_en.json, reading.md.

Deterministic. Each language's JSON has the sections in the fixed order (omitted
sections are absent, never blank), per-paragraph text with its trace, the six (or
seven) suitability cards, ``goal_scores`` for all 11 goals, ``lines_display`` (UI data,
07 §4), ``place`` and the fixed ``footer`` (spec 04 §6).
"""

from __future__ import annotations

from ar_sections import FOOTER, SCHEMA_VERSION, SECTION_ORDER, SECTIONS
from ar_validate import unit_text


def _slot_order(plan: dict, key: str) -> list[str]:
    sec = next((s for s in plan["sections"] if s["key"] == key), None)
    return [s["slot_id"] for s in (sec or {}).get("slots", [])]


def reading_json(reading: dict, plan: dict, lang: str) -> dict:
    secs_in = reading[lang]
    sections = []
    for key in SECTION_ORDER:
        if key == "suitability":
            cards = [{"card": c["card"], "goal": c["goal"],
                      "title": c["title_tr"] if lang == "tr" else c["title_en"],
                      "band": c["band"],
                      "band_label_tr": c["band_label_tr"], "band_label_en": c["band_label_en"],
                      "text": c[f"text_{lang}"], "trace": c["trace"]}
                     for c in reading.get("cards", [])]
            if cards:
                sections.append({"key": key, "title": SECTIONS[key][0 if lang == "tr" else 1],
                                 "cards": cards})
            continue
        units = secs_in.get(key)
        if not units:
            continue
        paras = []
        for uid in _slot_order(plan, key) or list(units):
            u = units.get(uid)
            if not u:
                continue
            paras.append({"slot_id": uid, "text": unit_text(u),
                          "trace": sorted({i for s in u["sentences"] for i in s["ids"]}),
                          "sentences": u["sentences"]})
        sections.append({"key": key, "title": SECTIONS[key][0 if lang == "tr" else 1],
                         "text": "\n\n".join(p["text"] for p in paras), "paragraphs": paras})
    return {
        "schema_version": SCHEMA_VERSION,
        "language": lang,
        "place": plan["place"],
        "focus_goal": plan.get("focus_goal"),
        "sections": sections,
        "goal_scores": plan.get("goal_scores", {}),
        "lines_display": plan.get("lines_display", []),
        "parans_display": plan.get("parans_display", []),
        "footer": FOOTER[lang],
    }


def _lines_table(display: list[dict], lang: str) -> list[str]:
    if not display:
        return []
    i = 0 if lang == "tr" else 1
    head = ("| Gezegen | Çizgi | Yaklaşık uzaklık | Yakınlık |" if lang == "tr"
            else "| Planet | Line | Approx. distance | Proximity |")
    out = [head, "|---|---|---|---|"]
    for d in display:
        planet = d["planet_tr"] if lang == "tr" else d.get("planet_en", d["body"].title())
        angle = d["angle_label_tr"] if lang == "tr" else d["angle_label_en"]
        tier = d["tier_label_tr"] if lang == "tr" else d["tier_label_en"]
        dist = d["distance_km_rounded"]
        dist = f"~{dist} km" if dist != "<10" else "<10 km"
        out.append(f"| {planet} | {angle} | {dist} | {tier} |")
    return out + [""]


def reading_markdown(tr: dict, en: dict) -> str:
    lines: list[str] = []
    for doc in (tr, en):
        lang = doc["language"]
        name = doc["place"]["name_tr"] if lang == "tr" else doc["place"]["name"]
        lines += [f"# {name}", ""]
        lines += _lines_table(doc["lines_display"], lang)
        for p in doc.get("parans_display", []):
            names = " + ".join(p["planets_tr"] if lang == "tr" else p["planets_en"])
            label = p["label_tr"] if lang == "tr" else p["label_en"]
            dist = p["distance_km_rounded"]
            lines.append(f"- {label}: {names} (~{dist} km)")
        if doc.get("parans_display"):
            lines.append("")
        for sec in doc["sections"]:
            lines += [f"## {sec['title']}", ""]
            if "cards" in sec:
                for c in sec["cards"]:
                    lines += [f"**{c['title']}** — {c['text']}", ""]
            else:
                for p in sec["paragraphs"]:
                    lines += [p["text"], ""]
        lines += [f"*{doc['footer']}*", "", "---", ""]
    return "\n".join(lines).rstrip("-\n ") + "\n"
