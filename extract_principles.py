#!/usr/bin/env python3
"""
Phase 1 - Principle extraction for the astrology knowledge base.

Reads chapter .txt files from chapters/traditional and chapters/modern,
runs the extraction prompt on each via the Anthropic API, and writes one
JSON file per chapter into extracted/. Finally merges everything into
all_principles.json, ready for the consolidation step.

Setup:
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."     # (Windows: set ANTHROPIC_API_KEY=...)

Run:
    python extract_principles.py

It is resumable: chapters that already have output in extracted/ are skipped.
Delete a file in extracted/ to re-run just that chapter.
"""

import os
import re
import sys
import json
import time
import pathlib

import anthropic

# ----------------------------------------------------------------------------
# Config - edit these if needed
# ----------------------------------------------------------------------------
MODEL = "claude-sonnet-5"   # solid quality/cost for a batch job.
                              # Use "claude-opus-4-8" for highest quality.
MAX_TOKENS = 16000            # generous, so dense chapters don't get truncated
CHAPTERS_DIR = "chapters"
OUTPUT_DIR = "extracted"
COMBINED_FILE = "all_principles.json"

# Soft guard: a chapter much larger than this many characters extracts poorly
# in one pass. Split it into smaller .txt files if you hit the warning.
SIZE_WARN_CHARS = 120_000     # ~30k tokens

# ----------------------------------------------------------------------------
# The extraction prompt. {source} and {chapter} are filled per file.
# Edit the wording here if you refine the prompt later.
# ----------------------------------------------------------------------------
EXTRACTION_PROMPT = """You are an extraction engine for a traditional astrology knowledge base. Your job is to read one chapter of source material and output a structured specification of the ASTROLOGICAL TECHNIQUES AND RULES it contains - not a summary, not a rewrite, and not a paraphrase of the text.

CRITICAL CONSTRAINTS - read carefully:
1. Extract only the underlying techniques, conditions, and judgments (the methods of the tradition). These are facts/procedures, not anyone's property.
2. NEVER reproduce or closely paraphrase the source's sentences, phrasing, or wording. Restate every rule in your own neutral, technical language. If a phrase in your output could be matched back to a sentence in the source, rewrite it further.
3. Do NOT preserve the source's structure, ordering, section headings, or selection of topics. Reorganize freely by technique. Your output's organization must owe nothing to the source's organization.
4. Convert worked examples into the GENERAL RULE they demonstrate. Do not copy the example charts, names, dates, or scenarios - state only the principle.
5. Exclude the translator's or author's ORIGINAL commentary - historical analysis, biography, opinions, footnoted scholarship, introductions. Capture only the astrological techniques themselves. If a footnote states a technique, capture the technique; if it states the author's own analysis, skip it.
6. If the chapter contains no extractable technique (e.g. it is purely biographical or introductory), return an empty "principles" array and note why.

For each distinct technique, output one object with these fields:
- "principle_id": a short kebab-case slug, e.g. "horary-lost-object-house-lord"
- "domain": one of ["basics","natal","horary","electional","mundane","predictive","lots","dignities","timing"]
- "topic_tags": array of retrieval tags - the chart factors this rule keys off, e.g. ["7th house","house lord","significator","lost objects"]
- "rule": the technique, in your own neutral technical wording - the core content
- "conditions": the inputs/significators the rule depends on (which planet, house, lot, dignity, sect, aspect, etc.)
- "judgment": what conclusion or prediction the rule yields
- "attribution_in_text": if the passage credits an earlier authority (e.g. Dorotheus, Masha'allah, the Persians, al-Andarzaghar), name it here; else null. This flags principles to later cross-check against public-domain sources.
- "notes": ambiguities, variant readings, or conflicts with other rules; else null

Then a final self-check: before returning, scan your output and confirm no field reproduces source phrasing. If any does, rewrite it.

Output VALID JSON ONLY - a single object: {{"source": "{source}", "principles": [ ... ]}}. No markdown fences, no commentary before or after.

SOURCE_NAME: {source}
CHAPTER TEXT:
{chapter}
"""

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment


def parse_json_safe(text):
    """Parse model output as JSON, tolerating accidental code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return json.loads(text)


def extract_chapter(path, tradition, retries=3):
    """Run the extraction prompt on one chapter file; return the parsed dict."""
    source_name = path.stem
    chapter_text = path.read_text(encoding="utf-8", errors="replace")

    if len(chapter_text) > SIZE_WARN_CHARS:
        print(f"  ! {source_name} is large ({len(chapter_text):,} chars). "
              f"Consider splitting it into smaller .txt files.")

    prompt = EXTRACTION_PROMPT.format(source=source_name, chapter=chapter_text)

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = "".join(b.text for b in msg.content if b.type == "text")
            data = parse_json_safe(raw)

            # Enforce the tradition tag in code, regardless of model output.
            for p in data.get("principles", []):
                p["tradition"] = tradition
            data["source"] = source_name
            data["tradition"] = tradition
            return data

        except json.JSONDecodeError as e:
            last_err = f"bad JSON ({e})"
        except anthropic.APIError as e:
            last_err = f"API error ({e})"
        if attempt < retries:
            wait = 2 ** attempt
            print(f"  retry {attempt}/{retries} after {last_err}; waiting {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"failed on {source_name}: {last_err}")


def main():
    base = pathlib.Path(CHAPTERS_DIR)
    out = pathlib.Path(OUTPUT_DIR)
    out.mkdir(exist_ok=True)

    if not base.exists():
        sys.exit(f"No '{CHAPTERS_DIR}/' folder found. Create it with "
                 f"'traditional/' and 'modern/' subfolders of .txt files.")

    jobs = []
    for tradition in ("traditional", "modern"):
        folder = base / tradition
        if folder.exists():
            jobs += [(p, tradition) for p in sorted(folder.glob("*.txt"))]

    if not jobs:
        sys.exit("No .txt chapters found under chapters/traditional or chapters/modern.")

    print(f"Found {len(jobs)} chapter(s). Model: {MODEL}\n")

    done = failed = skipped = 0
    for path, tradition in jobs:
        target = out / f"{tradition}__{path.stem}.json"
        if target.exists():
            skipped += 1
            print(f"= skip (already done): {target.name}")
            continue

        print(f"> extracting [{tradition}] {path.name} ...")
        try:
            data = extract_chapter(path, tradition)
            target.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                              encoding="utf-8")
            n = len(data.get("principles", []))
            print(f"  ok: {n} principle(s) -> {target.name}")
            done += 1
        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    # Merge every chapter's principles into one array for consolidation.
    combined = []
    for f in sorted(out.glob("*.json")):
        chapter = json.loads(f.read_text(encoding="utf-8"))
        combined.extend(chapter.get("principles", []))
    pathlib.Path(COMBINED_FILE).write_text(
        json.dumps(combined, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nDone. extracted={done} skipped={skipped} failed={failed}")
    print(f"{len(combined)} total principles -> {COMBINED_FILE}")
    if failed:
        print("Re-run the script to retry the failed chapters.")


if __name__ == "__main__":
    main()
