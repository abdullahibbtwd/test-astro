#!/usr/bin/env python3
"""
extract_houses.py — corpus delta: modern natal PLANETS-IN-HOUSES principles.

Source: ``TXT/Planets_in_houses.txt`` (a planets-in-houses text organised by
house: Chapter One = first house … Chapter Twelve = twelfth house; inside each
chapter every planet has a "<Nth> House Sequence: <Planet>" part followed by a
"<Nth> House Aspects: <Planet>" part — both describe the SAME placement through
the other life areas, so together they are one planet-in-house unit).

For each of the 120 (house, planet) units this script asks the model for a
handful of atomic, technique-only principles (no source wording, no book
structure) and forces the record shape the corpus pipeline expects:

    principle_id  = "{planet}-{N}{st|nd|rd|th}-{slug}"   -> backfill Tier-1 id parse
    conditions    = {"planet": P, "house": N}             -> Tier-1 corroboration
    topic_tags    ⊇ {P, "{Nth} house"}
    domain natal, tradition modern (forced in code, never trusted to the model)

Output (resumable; one JSON per unit under TXT/extracted_houses/, then the
combined ``houses_delta.raw.json`` here). Next steps: ``merge_houses_delta.py``
(Step 3 normalise/dedupe/append to the clean corpus) then ``finish_delta.py``
(Step 4 backfill + gate + append to the grounded corpus).

Run (needs GEMINI_API_KEY; the model comes from llm_client.DEFAULT_MODEL):
    python principles_grounding/extract_houses.py
    python principles_grounding/extract_houses.py --limit 3     # smoke test
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import llm_client  # noqa: E402

SOURCE = os.path.join(ROOT, "TXT", "Planets_in_houses.txt")
UNIT_DIR = os.path.join(ROOT, "TXT", "extracted_houses")
RAW_OUT = os.path.join(HERE, "houses_delta.raw.json")

PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
           "Uranus", "Neptune", "Pluto")
ORDINAL_WORDS = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
                 "Nine", "Ten", "Eleven", "Twelve"]
HOUSE_WORDS = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh",
               "eighth", "ninth", "tenth", "eleventh", "twelfth"]


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ---------------------------------------------------------------------------
# Text segmentation
# ---------------------------------------------------------------------------

_CHAPTER_RE = re.compile(r"^\s*Chapter\s+(" + "|".join(ORDINAL_WORDS) + r")\s*$")
# The planet is optional on the heading line: OCR occasionally breaks the heading
# so the planet name sits alone a few lines below ("Ninth House Sequence:" / "Mercury").
_SEQ_RE = re.compile(r"^\s*.*?House\s+Sequence:\s*(" + "|".join(PLANETS) + r")?\s*$")
_PLANET_LINE_RE = re.compile(r"^\s*(" + "|".join(PLANETS) + r")\s*$")
# Each chapter ends with a "<Nth> House Polarities" part (Sun-house x Moon-house
# combinations). That is a compound factor the corpus schema cannot verify yet, so
# the last planet's unit is cut where it starts. (Follow-up candidate.)
_POLARITIES_RE = re.compile(r"^\s*.*?House\s+Polarities\s*$")
_NOISE_RE = re.compile(
    r"^\s*(\d{1,3}|Planets in Houses.*|Introduction|(" + "|".join(w.capitalize() for w in HOUSE_WORDS)
    + r")\s+House|[^A-Za-z0-9]{1,8})\s*$")


def _clean(lines: list[str]) -> str:
    out: list[str] = []
    for ln in lines:
        if _NOISE_RE.match(ln):
            continue
        out.append(ln.rstrip())
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def segment(path: str = SOURCE) -> dict[tuple[int, str], str]:
    """Return {(house, planet): unit_text} for all 120 units; raise if the
    layout is not exactly 12 chapters x 10 planets."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    chapter_starts: list[tuple[int, int]] = []          # (line_idx, house)
    for i, ln in enumerate(lines):
        m = _CHAPTER_RE.match(ln)
        if m:
            chapter_starts.append((i, ORDINAL_WORDS.index(m.group(1)) + 1))
    if [h for _, h in chapter_starts] != list(range(1, 13)):
        raise SystemExit(f"expected chapters 1..12 in order, found {chapter_starts}")

    units: dict[tuple[int, str], str] = {}
    for ci, (start, house) in enumerate(chapter_starts):
        end = chapter_starts[ci + 1][0] if ci + 1 < len(chapter_starts) else len(lines)
        heads: list[tuple[int, int, str]] = []       # (heading line, body-start line, planet)
        for i in range(start, end):
            m = _SEQ_RE.match(lines[i])
            if not m:
                continue
            planet, body_from = m.group(1), i + 1
            if not planet:
                for k in range(i + 1, min(i + 8, end)):   # planet name alone, a few lines down
                    pm = _PLANET_LINE_RE.match(lines[k])
                    if pm:
                        planet, body_from = pm.group(1), k + 1
                        break
            if planet:
                heads.append((i, body_from, planet))
        planets_seen = [p for _, _, p in heads]
        if sorted(planets_seen) != sorted(PLANETS):
            raise SystemExit(f"chapter {house}: expected the 10 planets once each, "
                             f"found {planets_seen}")
        for hi, (hstart, body_from, planet) in enumerate(heads):
            hend = heads[hi + 1][0] if hi + 1 < len(heads) else end
            for k in range(body_from, hend):          # trim the chapter's polarities tail
                if _POLARITIES_RE.match(lines[k]):
                    hend = k
                    break
            body = _clean(lines[body_from:hend])
            if not 1500 <= len(body) <= 14000:
                raise SystemExit(f"unit h{house} {planet} has an implausible size "
                                 f"({len(body)} chars) — check the segmentation")
            units[(house, planet)] = body
    return units


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

SYSTEM = """You are an extraction engine for an astrology knowledge base (modern, \
psychological natal astrology). You read one unit of source text — everything a \
book says about ONE planet placed in ONE natal house — and output a structured \
set of the interpretive PRINCIPLES it contains: not a summary, not a rewrite, \
not a paraphrase.

CRITICAL CONSTRAINTS:
1. Extract the underlying interpretive claims (placement -> meaning). Treat each \
"factor -> significance" statement as a rule whose condition is the placement and \
whose judgment is the assigned meaning.
2. NEVER reproduce or closely paraphrase the source's sentences, phrasing or \
imagery. Restate every rule in your own neutral, technical language. If a phrase \
of yours could be matched back to a source sentence, rewrite it further.
3. Do NOT preserve the source's structure. The source walks through the placement \
one life area at a time and uses house-to-house numbering ("2nd to the 12th", \
"Trine: 5,9", "Cross: 4, 7, 10"). Ignore that scaffolding completely: never \
mention derivative houses, house numbers other than the placement's own house, or \
aspect names between houses. Reorganise the content by THEME.
4. Write about "the native" in the third person, present tense, as standing \
significations of the placement (e.g. "Venus in the 7th house inclines the native \
to ..."). Never address the reader as "you".
5. Keep it psychological and behavioural: motivations, needs, strengths, \
characteristic challenges and their constructive resolution. Drop any fatalistic \
or moralising remarks, any autobiographical or anecdotal material, and any advice \
about how to read charts.
6. Prefer 4 to 7 principles per unit: ONE core principle stating the overall \
meaning of the placement, then the strongest distinct themes (each merging what \
the source says about that theme across its sections). Each principle must be \
atomic (one theme), self-contained, and 2-4 sentences long.

Output fields for each principle:
- "principle_id": kebab-case slug of 2-4 words naming the THEME only (e.g. \
"recognition-drive", "shared-resources-caution"). Do NOT include the planet or the \
house in it — the pipeline prefixes them.
- "topic_tags": 3-6 lower-case retrieval tags for the theme (life areas, traits). \
Do NOT include the planet or house tag — the pipeline adds them.
- "rule": the principle in your own neutral technical wording (the core content).
- "judgment": the conclusion in one sentence: what this means for the native.
- "notes": ambiguities or tensions with other principles, else an empty string.

Self-check before returning: no field reproduces source phrasing; no house \
numbers other than the placement's own; no second person. Return ONLY the JSON."""

USER_TMPL = """PLACEMENT: {planet} in the {ord} house (natal, modern psychological astrology).

SOURCE UNIT (everything the book says about this placement):
\"\"\"
{body}
\"\"\"

Return a JSON object {{"principles": [ ... ]}} with 4 to 7 principles for {planet} in the {ord} house, as specified."""

SCHEMA = {
    "type": "object",
    "properties": {
        "principles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "principle_id": {"type": "string"},
                    "topic_tags": {"type": "array", "items": {"type": "string"}},
                    "rule": {"type": "string"},
                    "judgment": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["principle_id", "topic_tags", "rule", "judgment", "notes"],
            },
        }
    },
    "required": ["principles"],
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_PLANET_OR_ORD_RE = re.compile(
    r"^(?:(?:sun|moon|mercury|venus|mars|jupiter|saturn|uranus|neptune|pluto)-)?"
    r"(?:(?:\d{1,2}(?:st|nd|rd|th)|" + "|".join(HOUSE_WORDS) + r")-house-|"
    r"(?:\d{1,2}(?:st|nd|rd|th)|" + "|".join(HOUSE_WORDS) + r")-)?")


def _slug(s: str) -> str:
    s = _SLUG_RE.sub("-", (s or "").lower()).strip("-")
    s = _PLANET_OR_ORD_RE.sub("", s)          # strip a planet/house prefix if the model added one
    return s or "placement-meaning"


def shape_records(house: int, planet: str, data: dict) -> list[dict]:
    """Force the corpus record shape + the deterministic id/conditions/tags the
    backfill Tier-1 parser keys on. Nothing here is trusted to the model."""
    ord_ = ordinal(house)
    out: list[dict] = []
    seen: set[str] = set()
    for item in data.get("principles") or []:
        rule = (item.get("rule") or "").strip()
        if len(rule) < 40:
            continue
        base = f"{planet.lower()}-{ord_}-{_slug(item.get('principle_id'))}"
        pid, n = base, 2
        while pid in seen:
            pid, n = f"{base}-{n}", n + 1
        seen.add(pid)
        tags = [t.strip() for t in (item.get("topic_tags") or []) if isinstance(t, str) and t.strip()]
        tags = [t for t in tags if t.lower() not in {planet.lower(), f"{ord_} house"}]
        tags = [planet, f"{ord_} house"] + tags[:6]
        notes = (item.get("notes") or "").strip() or None
        out.append({
            "principle_id": pid,
            "domain": "natal",
            "topic_tags": tags,
            "rule": rule,
            "conditions": {"planet": planet, "house": house},
            "judgment": (item.get("judgment") or "").strip() or None,
            "attribution_in_text": None,
            "notes": notes,
            "tradition": "modern",
        })
    return out


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _unit_path(house: int, planet: str) -> str:
    return os.path.join(UNIT_DIR, f"h{house:02d}_{planet.lower()}.json")


def extract_unit(house: int, planet: str, body: str, model: str) -> dict:
    user = USER_TMPL.format(planet=planet, ord=ordinal(house), body=body)
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = llm_client.complete(model, SYSTEM, user, max_tokens=8192,
                                       temperature=0.2, schema=SCHEMA, timeout_s=180.0,
                                       label=f"h{house}/{planet}")
            if resp.stop_reason == "max_tokens":
                raise RuntimeError("output truncated")
            data = json.loads(resp.text)
            recs = shape_records(house, planet, data)
            if len(recs) < 3:
                raise RuntimeError(f"only {len(recs)} usable principles")
            return {"house": house, "planet": planet, "model": model,
                    "usage": resp.usage, "principles": recs}
        except (json.JSONDecodeError, RuntimeError) as exc:
            last = exc
            time.sleep(2 * attempt)
        except llm_client.transient_errors(model) as exc:
            last = exc
            time.sleep(5 * attempt)
    raise RuntimeError(f"h{house} {planet}: failed after 3 attempts: {last}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract planets-in-houses principles (delta).")
    ap.add_argument("--model", default=llm_client.DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="only the first N units (smoke test)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true", help="segment only; print unit sizes")
    args = ap.parse_args()

    units = segment()
    print(f"segmented {len(units)} units from {os.path.basename(SOURCE)}")
    if args.dry_run:
        for (h, p), body in sorted(units.items()):
            print(f"  h{h:02d} {p:8s} {len(body):6d} chars")
        return

    llm_client.require_api_key(args.model, "planets-in-houses extraction")
    os.makedirs(UNIT_DIR, exist_ok=True)
    todo = [(k, v) for k, v in sorted(units.items()) if not os.path.exists(_unit_path(*k))]
    already = len(units) - len(todo)
    if args.limit:
        todo = todo[:args.limit]
    print(f"{already} unit(s) already extracted; {len(todo)} to run now "
          f"with {args.model} ({args.workers} workers)")

    t0 = time.time()
    failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(extract_unit, h, p, body, args.model): (h, p)
                for (h, p), body in todo}
        for fut in as_completed(futs):
            h, p = futs[fut]
            try:
                res = fut.result()
            except Exception as exc:          # noqa: BLE001 — report and continue
                failed += 1
                print(f"  FAILED h{h:02d} {p}: {exc}", flush=True)
                continue
            with open(_unit_path(h, p), "w", encoding="utf-8") as fh:
                json.dump(res, fh, ensure_ascii=False, indent=2)
            print(f"  ok h{h:02d} {p:8s} {len(res['principles'])} principles "
                  f"(out={res['usage']['output_tokens']} tok)", flush=True)

    # combine every unit present on disk
    combined: list[dict] = []
    usage = {"input_tokens": 0, "output_tokens": 0}
    n_units = 0
    for (h, p) in sorted(units):
        path = _unit_path(h, p)
        if not os.path.exists(path):
            continue
        res = json.load(open(path, encoding="utf-8"))
        combined.extend(res["principles"])
        for k in usage:
            usage[k] += (res.get("usage") or {}).get(k, 0)
        n_units += 1
    with open(RAW_OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(combined, fh, ensure_ascii=False, indent=2)
    print(f"\ndone in {time.time() - t0:.0f}s: {n_units}/{len(units)} units on disk, "
          f"{len(combined)} principles -> {os.path.relpath(RAW_OUT, ROOT)}")
    print(f"tokens this session: in={usage['input_tokens']:,} out={usage['output_tokens']:,}")
    if failed:
        print(f"{failed} unit(s) failed — re-run to retry them (resumable).")
        sys.exit(1)


if __name__ == "__main__":
    main()
