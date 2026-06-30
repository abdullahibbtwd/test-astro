#!/usr/bin/env python3
"""
l4_render.py — turn an l4_output.json into human-readable text.

The app renders `text_tr` (and now `text_en`) directly; this module is for
humans reading the result — it drops the `principle_ids` QA trace and lays the
sections out with headings, in canonical order, in either language.

Run:
    python l4_render.py                       # writes l4_reading.tr.txt + .en.txt
    python l4_render.py --in l4_output.json --lang tr
"""

from __future__ import annotations

import argparse
import json
import os

from l4_sections import MOVEMENT, SECTION_ORDER

# Human-readable section headings (display only — the structural keys stay locked).
SECTION_TITLES: dict[str, dict[str, str]] = {
    "core_identity":       {"tr": "Çekirdek Kimlik",            "en": "Core Identity"},
    "inner_drives":        {"tr": "İç Dürtüler",                "en": "Inner Drives"},
    "chart_shape":         {"tr": "Haritanın Genel Şekli",      "en": "Chart Shape"},
    "identity_body":       {"tr": "Kimlik ve Beden",            "en": "Identity & Body"},
    "resources_values":    {"tr": "Kaynaklar ve Değerler",      "en": "Resources & Values"},
    "mind_communication":  {"tr": "Zihin ve İletişim",          "en": "Mind & Communication"},
    "home_roots":          {"tr": "Yuva ve Kökler",             "en": "Home & Roots"},
    "creativity_pleasure": {"tr": "Yaratıcılık ve Haz",         "en": "Creativity & Pleasure"},
    "daily_work":          {"tr": "Günlük İş ve Sağlık",        "en": "Daily Work & Health"},
    "relationships":       {"tr": "İlişkiler",                  "en": "Relationships"},
    "vocation_public":     {"tr": "Meslek ve Toplumsal Rol",    "en": "Vocation & Public Role"},
    "community_meaning":   {"tr": "Topluluk ve Anlam",          "en": "Community & Meaning"},
}

MOVEMENT_TITLES: dict[str, dict[int, str]] = {
    "tr": {1: "BİRİNCİ BÖLÜM — Kim Olduğun",
           2: "İKİNCİ BÖLÜM — Hayatına Nasıl Yansıdığı"},
    "en": {1: "PART ONE — Who You Are",
           2: "PART TWO — Where It Lands"},
}

_DOC_TITLE = {"tr": "DOĞUM HARİTASI YORUMU", "en": "NATAL CHART READING"}


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
        title = SECTION_TITLES[key][lang]
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
