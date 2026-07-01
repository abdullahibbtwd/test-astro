#!/usr/bin/env python3
"""
s3_render.py — turn an S3 output object into human-readable text
(SYNASTRY_READING_SPEC.md §11: relationship_reading.tr.txt / .en.txt).

The app renders ``text_tr`` / ``text_en`` directly; this module lays the sections
out with headings, in canonical order, in either language, dropping the
``source_ids`` QA trace.
"""

from __future__ import annotations

import argparse
import json
import os

from s3_sections import SECTION_ORDER

SECTION_TITLES: dict[str, dict[str, str]] = {
    "what_each_brings": {"tr": "Her Biri Ne Getiriyor",     "en": "What Each Brings"},
    "attraction":       {"tr": "Çekim ve Kimya",            "en": "Attraction & Chemistry"},
    "emotional":        {"tr": "Duygusal İhtiyaçlar ve Güven", "en": "Emotional Needs & Security"},
    "communication":    {"tr": "İletişim ve Zihinlerin Buluşması", "en": "Communication & the Meeting of Minds"},
    "friction":         {"tr": "Sürtüşme ve Zorluk",        "en": "Friction & Challenge"},
    "values":           {"tr": "Değerler, Para ve Ortak Hayat", "en": "Values, Money & Shared Life"},
    "commitment":       {"tr": "Bağlılık ve Uzun Vade",     "en": "Commitment & Long-Term Viability"},
    "purpose":          {"tr": "Ortak Amaç ve Büyüme",      "en": "Shared Purpose & Growth"},
}

_DOC_TITLE = {"tr": "İLİŞKİ YORUMU", "en": "RELATIONSHIP READING"}


def render(output: dict, lang: str) -> str:
    field = "text_tr" if lang == "tr" else "text_en"
    by_key = {s.get("key"): s for s in output.get("sections", [])}
    title = _DOC_TITLE[lang]
    lines: list[str] = [title, "=" * len(title), ""]
    for key in SECTION_ORDER:
        sec = by_key.get(key)
        if not sec:
            continue
        body = (sec.get(field) or "").strip()
        if not body:
            continue
        lines += [SECTION_TITLES[key][lang], "", body, ""]
    return "\n".join(lines).strip() + "\n"


def write_readable(output: dict, out_dir: str,
                   stem: str = "relationship_reading") -> list[str]:
    written = []
    for lang in ("tr", "en"):
        field = "text_tr" if lang == "tr" else "text_en"
        if not any((s.get(field) or "").strip() for s in output.get("sections", [])):
            continue
        path = os.path.join(out_dir, f"{stem}.{lang}.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render(output, lang))
        written.append(path)
    return written


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="Render S3 output to readable text.")
    ap.add_argument("--in", dest="inp",
                    default=os.path.join(here, "relationship_reading.json"))
    ap.add_argument("--lang", choices=["tr", "en", "both"], default="both")
    args = ap.parse_args()
    with open(args.inp, encoding="utf-8") as fh:
        output = json.load(fh)
    if args.lang == "both":
        for p in write_readable(output, os.path.dirname(os.path.abspath(args.inp))):
            print(f"wrote {p}")
    else:
        print(render(output, args.lang))


if __name__ == "__main__":
    main()
