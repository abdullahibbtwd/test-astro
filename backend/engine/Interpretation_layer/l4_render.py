#!/usr/bin/env python3
"""
l4_render.py — turn an l4_output.json into human-readable text.

The app renders `text_tr` (and `text_en`) directly; this module is for humans
reading the result — it drops the `principle_ids` QA trace and lays the
sections out with headings, in canonical order, in either language.

Part two is one section per Placidus house, headed "N. Ev — <name>" / "House N —
<name>". The two luminary notes in Part one are headed with the actual house
("Güneş 9. Evde" / "Sun in the 9th House") read from the section's `house` field.

Run:
    python l4_render.py                       # writes l4_reading.tr.txt + .en.txt
    python l4_render.py --in l4_output.json --lang tr
"""

from __future__ import annotations

import argparse
import json
import os

from l4_sections import (
    LUMINARY_OF_SECTION, MOVEMENT, SECTION_HOUSE, SECTION_ORDER,
)

# Human-readable section headings (display only — the structural keys stay locked).
SECTION_TITLES: dict[str, dict[str, str]] = {
    # Movement 1
    "core_identity":           {"tr": "Çekirdek Kimlik",   "en": "Core Identity"},
    "sun_house":               {"tr": "Güneş'in Evi",      "en": "The Sun's House"},
    "moon_house":              {"tr": "Ay'ın Evi",         "en": "The Moon's House"},
    "inner_drives":            {"tr": "İç Dürtüler",       "en": "Inner Drives"},
    "chart_shape":             {"tr": "Haritanın Genel Şekli", "en": "Chart Shape"},
    # Movement 2 — one per house
    "identity":                {"tr": "Kimlik",
                                "en": "Identity"},
    "values_money":            {"tr": "Değerler ve Para",
                                "en": "Values and Money"},
    "communication_learning":  {"tr": "İletişim, Öğrenim ve Kardeşler",
                                "en": "Communication, Studying, Siblings"},
    "family_home":             {"tr": "Aile ve Yuva",
                                "en": "Family and Home"},
    "joy_creativity_children": {"tr": "Neşe, Sanatsal Yetenekler ve Çocuklar",
                                "en": "Joy, Artistic Talents and Kids"},
    "health_routine_pets":     {"tr": "Sağlık, Rutin ve Evcil Hayvanlar",
                                "en": "Health, Routine, Pets"},
    "partnerships":            {"tr": "Ortaklıklar",
                                "en": "Partnerships"},
    "transformation_intimacy": {"tr": "Dönüşüm ve Yakınlık",
                                "en": "Transformation and Intimacy"},
    "travel_philosophy":       {"tr": "Uzak Seyahatler ve Felsefe",
                                "en": "Distant Travels and Philosophy"},
    "status_vocation":         {"tr": "Toplumsal Statü ve Meslek",
                                "en": "Social Status and Vocation"},
    "friendships_future":      {"tr": "Arkadaşlıklar ve Gelecek",
                                "en": "Friendships and the Future"},
    "subconscious_solitude":   {"tr": "Bilinçaltı ve Yalnızlık",
                                "en": "Subconscious and Solitary"},
}

MOVEMENT_TITLES: dict[str, dict[int, str]] = {
    "tr": {1: "BİRİNCİ BÖLÜM — Kim Olduğun",
           2: "İKİNCİ BÖLÜM — Evler: Hayatına Nasıl Yansıdığı"},
    "en": {1: "PART ONE — Who You Are",
           2: "PART TWO — The Houses: Where It Lands"},
}

_DOC_TITLE = {"tr": "DOĞUM HARİTASI YORUMU", "en": "NATAL CHART READING"}
_LUMINARY_NAME = {"Sun": {"tr": "Güneş", "en": "Sun"}, "Moon": {"tr": "Ay", "en": "Moon"}}


def _ordinal_en(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def section_title(key: str, lang: str, house: int | None = None) -> str:
    """Display heading for one section. House sections carry their house
    number; luminary notes name the actual house when the output provides it."""
    base = SECTION_TITLES.get(key, {}).get(lang, key)
    if key in SECTION_HOUSE:
        n = SECTION_HOUSE[key]
        return f"{n}. Ev — {base}" if lang == "tr" else f"House {n} — {base}"
    lum = LUMINARY_OF_SECTION.get(key)
    if lum and house:
        name = _LUMINARY_NAME[lum][lang]
        return (f"{name} {house}. Evde" if lang == "tr"
                else f"{name} in the {_ordinal_en(house)} House")
    return base


def render(output: dict, lang: str) -> str:
    """Readable text for one language ('tr' uses text_tr, 'en' uses text_en)."""
    field = "text_tr" if lang == "tr" else "text_en"
    by_key = {s.get("key"): s for s in output.get("sections", [])}
    lines: list[str] = [_DOC_TITLE[lang], "=" * len(_DOC_TITLE[lang]), ""]
    current_movement: int | None = None
    for key in SECTION_ORDER:
        sec = by_key.get(key)
        if not sec:
            continue
        mv = MOVEMENT[key]
        if mv != current_movement:
            current_movement = mv
            lines += ["", MOVEMENT_TITLES[lang][mv], "-" * 60, ""]
        title = section_title(key, lang, sec.get("house"))
        body = (sec.get(field) or "").strip() or "(metin yok)"
        lines += [title, "", body, ""]
    return "\n".join(lines).strip() + "\n"


def write_readable(output: dict, out_dir: str, stem: str = "l4_reading") -> list[str]:
    """Write both languages (skips a language with no text) and return paths."""
    written = []
    for lang in ("tr", "en"):
        has_text = any(
            (s.get("text_tr" if lang == "tr" else "text_en") or "").strip()
            for s in output.get("sections", [])
        )
        if not has_text:
            continue
        path = os.path.join(out_dir, f"{stem}.{lang}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render(output, lang))
        written.append(path)
    return written


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Render l4_output.json to readable text.")
    ap.add_argument("--in", dest="inp", default=os.path.join(here, "l4_output.json"))
    ap.add_argument("--lang", choices=["tr", "en", "both"], default="both")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as fh:
        output = json.load(fh)

    if args.lang == "both":
        paths = write_readable(output, os.path.dirname(os.path.abspath(args.inp)))
        for p in paths:
            print(f"wrote {p}")
        if not paths:
            print("no text found to render")
    else:
        print(render(output, args.lang))


if __name__ == "__main__":
    main()
