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

from s3_profiles import get_profile


def render(output: dict, lang: str) -> str:
    """Readable text for one language. Titles + order come from the reading's
    profile (stamped in the output as ``reading_type``)."""
    profile = get_profile(output.get("reading_type", "general"))
    field = "text_tr" if lang == "tr" else "text_en"
    by_key = {s.get("key"): s for s in output.get("sections", [])}
    title = profile.doc_title[lang]
    lines: list[str] = [title, "=" * len(title), ""]
    for key in profile.section_order:
        sec = by_key.get(key)
        if not sec:
            continue
        body = (sec.get(field) or "").strip()
        if not body:
            continue
        titles = profile.titles.get(key, {"tr": key, "en": key})
        lines += [titles[lang], "", body, ""]
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
