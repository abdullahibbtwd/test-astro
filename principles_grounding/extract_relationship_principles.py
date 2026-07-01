#!/usr/bin/env python3
"""
extract_relationship_principles.py

Phase-1 extraction for the RELATIONSHIP (synastry) knowledge base — the parallel
of ``extract_principles.py`` for two-chart comparison material.

Reads the chunked ``Analyzing Human Relationships`` text produced by
``split_relationships.py`` (``relationships_chunks/chunks.jsonl``), runs a
synastry-aware extraction prompt on each chunk via the Anthropic API, and emits
principles in the **same base format as ``all_principles.clean.json``** (the nine
clean fields) PLUS an additive structured ``synastry`` block — the two-chart
analog of ``about`` that the downstream grounding step needs to reconcile a
principle against a *pair* of charts.

Output record shape:
    {
      "principle_id": "syn-sun-conjunct-moon",
      "domain": "relationship",
      "topic_tags": ["synastry","Sun","Moon","conjunction"],
      "rule": "...", "conditions": [...], "judgment": "...",
      "attribution_in_text": null, "notes": null,
      "tradition": "modern",
      "synastry": {                         # additive; two-chart subject
        "interaction": "aspect",            # aspect|house_overlay|planet_role|compatibility|general
        "person_a_point": "Sun",
        "person_b_point": "Moon",
        "aspect": "conjunction",
        "polarity": "dynamic"
      }
    }

Pipeline position:
    split_relationships.py -> relationships_chunks/chunks.jsonl
      -> THIS SCRIPT -> relationship_principles.clean.json
        -> (grounding) -> relationship_principles.grounded.json
          -> (two-chart gate) -> personal_relationship_principles.json -> reading

Setup:
    pip install anthropic
    # key: env var, or a file OUTSIDE synced folders (this tree is in Drive):
    setx ANTHROPIC_API_KEY "sk-ant-..."   (or) put it in %USERPROFILE%\\.anthropic_key

Run:
    python extract_relationship_principles.py                 # all 88 chunks
    python extract_relationship_principles.py --limit 3       # smoke-test 3 chunks
    python extract_relationship_principles.py --model claude-opus-4-8

Resumable: a chunk whose per-chunk output already exists in --outdir is skipped.
Delete that file to re-extract just that chunk.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_MODEL = "claude-sonnet-4-6"   # matches extract_principles.py
MAX_TOKENS = 16000
DOMAIN = "relationship"
TRADITION = "modern"                  # Sakoian & Acker is a modern text

# Closed FK vocabularies the `synastry` block must use (verbatim casing).
POINTS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
          "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven",
          "North Node", "South Node")
ASPECTS = ("conjunction", "sextile", "square", "trine", "opposition")
INTERACTIONS = ("aspect", "house_overlay", "planet_role", "compatibility", "general")
POLARITIES = ("harmonious", "dynamic", "neutral")

# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------
EXTRACTION_PROMPT = """You extract SYNASTRY (two-chart comparison) techniques from one chunk of a horoscopic-comparison text and output a structured specification of the astrological RULES it contains — not a summary, not a paraphrase.

The material compares two people's natal charts. Person A ("the {a_planet} individual", the acting party in this chunk) and Person B (the other). An entry like "A's Sun Conjunct B's Moon" means: person A's Sun forms a conjunction to person B's Moon. A house entry like "First House" (under a planet chapter) means: person A's {a_planet} falls in person B's first house.

CRITICAL CONSTRAINTS:
1. Extract only the underlying techniques and their judgments (the tradition's methods), as facts/procedures.
2. NEVER reproduce or closely paraphrase the source's sentences or wording. Restate every rule in your own neutral, technical language. If a phrase could be matched back to a source sentence, rewrite it further.
3. Do NOT preserve the source's ordering or phrasing. Reorganize by technique.
4. Convert any worked example into the general rule it demonstrates. No names, no charts.
5. One principle per atomic entry: each "A's X <aspect> B's Y" line is one principle; each "Nth House" line under a planet chapter is one principle (A's {a_planet} in B's Nth house). A section's opening prose (no specific pairing) is one general principle for that planet's comparative role. Basic-concept chunks (elements, quadruplicities, sign roles, house influences, rules of comparison) each yield one or more compatibility/methodology principles.
6. If the chunk contains no extractable technique, return an empty "principles" array.

For each principle output one object with these fields (the base nine, matching the natal dataset, plus `synastry`):
- "principle_id": short kebab-case slug prefixed "syn-", e.g. "syn-sun-conjunct-moon", "syn-sun-in-3rd-house", "syn-fire-water-element-compatibility"
- "domain": always "relationship"
- "topic_tags": retrieval tags — the chart factors this rule keys off, e.g. ["synastry","Sun","Moon","conjunction"] or ["synastry","house overlay","Sun","3rd house"]
- "rule": the technique in your own neutral technical wording (the core content)
- "conditions": array of the two-chart inputs the rule depends on, e.g. ["Person A's Sun position","Person B's Moon position","conjunction between A's Sun and B's Moon"]
- "judgment": the relational conclusion the rule yields (the effect on the relationship)
- "attribution_in_text": an earlier authority credited in the passage, else null
- "notes": ambiguities/variant readings/dependencies on the rest of the comparison, else null
- "tradition": always "modern"
- "synastry": the structured two-chart subject. Emit ONLY the fields the interaction uses:
    - "interaction": one of "aspect" | "house_overlay" | "planet_role" | "compatibility" | "general"
    - for "aspect":        "person_a_point", "person_b_point" (from {points}), "aspect" (from {aspects}), and "polarity" ("harmonious" for sextile/trine, "dynamic" for square/opposition, "neutral"/either for conjunction)
    - for "house_overlay": "person_a_point" (from {points}) and "overlay_house" (integer 1-12) — person A's point in person B's house
    - for "planet_role":   "person_a_point" only — a planet's general comparative role
    - for "compatibility": "factors" (array of the sign/element/quadruplicity tokens involved, e.g. ["fire","water"] or ["cardinal","cardinal"])
    - for "general":        methodology rule of comparison; no subject fields needed

FK DISCIPLINE: point names, aspect names, and interaction/polarity values MUST use the exact vocabulary/casing above. Do not invent values.

Anchors for THIS chunk (use them, but read the text to decide each principle):
  person A's planet (chapter): {a_planet}
  section: {section}          (this tells you the aspect type or that it is house placements / an intro)

Output VALID JSON ONLY — a single object: {{"source": "{source}", "principles": [ ... ]}}. No markdown fences, no commentary.

CHUNK:
{chunk}
"""


# ---------------------------------------------------------------------------
# API-key loading (env var, or a file kept OUTSIDE synced folders)
# ---------------------------------------------------------------------------
def load_api_key(api_key_file: str | None) -> bool:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    for path in filter(None, [api_key_file,
                              os.path.join(os.path.expanduser("~"), ".anthropic_key")]):
        try:
            with open(path, encoding="utf-8") as fh:
                key = fh.read().strip()
            if key:
                os.environ["ANTHROPIC_API_KEY"] = key
                print(f"[extract] loaded API key from {path}")
                return True
        except OSError:
            continue
    return False


def parse_json_safe(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Normalization / validation of one extracted record
# ---------------------------------------------------------------------------
def _clean_synastry(syn: dict) -> dict:
    """Keep only recognized fields with in-vocabulary values (drop the rest)."""
    if not isinstance(syn, dict):
        return {"interaction": "general"}
    out: dict = {}
    inter = syn.get("interaction")
    out["interaction"] = inter if inter in INTERACTIONS else "general"
    for k in ("person_a_point", "person_b_point"):
        v = syn.get(k)
        if v in POINTS:
            out[k] = v
    if syn.get("aspect") in ASPECTS:
        out["aspect"] = syn["aspect"]
    oh = syn.get("overlay_house")
    if isinstance(oh, int) and not isinstance(oh, bool) and 1 <= oh <= 12:
        out["overlay_house"] = oh
    if syn.get("polarity") in POLARITIES:
        out["polarity"] = syn["polarity"]
    if isinstance(syn.get("factors"), list):
        out["factors"] = [str(x) for x in syn["factors"]]
    return out


def normalize_record(p: dict) -> dict:
    """Enforce the fixed fields and the clean field order; sanitize synastry."""
    pid = str(p.get("principle_id") or "").strip() or "syn-unnamed"
    if not pid.startswith("syn-"):
        pid = "syn-" + pid.lstrip("-")
    return {
        "principle_id": pid,
        "domain": DOMAIN,
        "topic_tags": p.get("topic_tags") or [],
        "rule": p.get("rule") or "",
        "conditions": p.get("conditions") or [],
        "judgment": p.get("judgment") or "",
        "attribution_in_text": p.get("attribution_in_text"),
        "notes": p.get("notes"),
        "tradition": TRADITION,
        "synastry": _clean_synastry(p.get("synastry") or {}),
    }


# ---------------------------------------------------------------------------
# Per-chunk extraction
# ---------------------------------------------------------------------------
def extract_chunk(client, model: str, chunk: dict, retries: int = 3) -> list[dict]:
    prompt = EXTRACTION_PROMPT.format(
        source=chunk.get("file", chunk.get("id", "?")),
        a_planet=chunk.get("chapter", "?"),
        section=chunk.get("section", "?"),
        points=", ".join(POINTS),
        aspects=", ".join(ASPECTS),
        chunk=chunk["text"],
    )
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            msg = client.messages.create(
                model=model, max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            data = parse_json_safe(raw)
            return [normalize_record(p) for p in data.get("principles", [])]
        except json.JSONDecodeError as e:
            last_err = f"bad JSON ({e})"
        except anthropic.APIError as e:
            last_err = f"API error ({e})"
        if attempt < retries:
            wait = 2 ** attempt
            print(f"    retry {attempt}/{retries} after {last_err}; waiting {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"failed on chunk {chunk.get('id')}: {last_err}")


def load_chunks(path: Path) -> list[dict]:
    chunks = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Extract synastry principles (clean "
                                             "format + synastry block).")
    ap.add_argument("--chunks", type=Path,
                    default=here / "relationships_chunks" / "chunks.jsonl")
    ap.add_argument("--outdir", type=Path, default=here / "relationship_extracted",
                    help="per-chunk JSON outputs (resumable)")
    ap.add_argument("--out", type=Path,
                    default=here / "relationship_principles.clean.json",
                    help="merged output — the grounding pipeline's input")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="process only first N chunks")
    ap.add_argument("--api-key-file", default=None)
    args = ap.parse_args()

    if not load_api_key(args.api_key_file):
        sys.exit("ERROR: no ANTHROPIC_API_KEY (env var or ~/.anthropic_key file). "
                 "Set it, then re-run.")
    if not args.chunks.exists():
        sys.exit(f"ERROR: chunks not found: {args.chunks}\n"
                 f"Run split_relationships.py first.")

    client = anthropic.Anthropic()
    chunks = load_chunks(args.chunks)
    if args.limit:
        chunks = chunks[:args.limit]
    args.outdir.mkdir(parents=True, exist_ok=True)

    print(f"Extracting {len(chunks)} chunk(s). Model: {args.model}\n")
    done = skipped = failed = 0
    for c in chunks:
        target = args.outdir / f"{c['id']}.json"
        if target.exists():
            skipped += 1
            print(f"= skip (done): {target.name}")
            continue
        label = f"{c.get('chapter')}/{c.get('section')}"
        print(f"> [{c['id']}] {label} ...")
        try:
            principles = extract_chunk(client, args.model, c)
            target.write_text(json.dumps(
                {"source": c["file"], "chapter": c.get("chapter"),
                 "section": c.get("section"), "principles": principles},
                ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"    ok: {len(principles)} principle(s)")
            done += 1
        except Exception as e:
            print(f"    FAILED: {e}")
            failed += 1

    # Merge every per-chunk file into one clean array (the pipeline input).
    combined: list[dict] = []
    for f in sorted(args.outdir.glob("*.json")):
        combined.extend(json.loads(f.read_text(encoding="utf-8")).get("principles", []))
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(combined, fh, ensure_ascii=False, indent=1)

    print(f"\nDone. extracted={done} skipped={skipped} failed={failed}")
    print(f"{len(combined)} relationship principles -> {args.out}")
    if failed:
        print("Re-run to retry the failed chunks (completed ones are skipped).")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
