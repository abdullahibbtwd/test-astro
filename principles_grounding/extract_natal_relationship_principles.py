#!/usr/bin/env python3
"""
extract_natal_relationship_principles.py

Pull the RELATIONSHIP-relevant principles out of the natal/general corpus and
re-emit them in the SAME format as ``extract_relationship_principles.py`` (the
nine clean fields + a ``synastry`` block), so they can join the synastry
principles in one combined relationship corpus.

These are SINGLE-CHART principles (e.g. "Venus in the 7th house → seeks
partnership"). In a two-chart reading they apply to EACH partner's own chart, so
their ``synastry`` block uses ``interaction: "natal_relational"`` and carries the
single-chart subject (mirrored from the record's already-grounded ``about``).

Identification is HYBRID (per the owner decision):
  1. deterministic pre-filter — broad relational signal (house 5/7/8, Descendant/
     7th-lord, Venus/Mars significators, partner/marriage/love/social keywords,
     Venus/Mars sign & element delineations);
  2. LLM classify — for each candidate, keep/drop + assign a relational_role and
     polarity. Only candidates reach the model (cheap), and the subject is reused
     from ``about`` (no re-extraction).

Input:  all_principles.grounded.json   (clean fields + validated `about`)
Output: relationship_natal_principles.clean.json   (clean 9 fields + synastry)

Combine with the synastry set for the grounding step:
    python extract_natal_relationship_principles.py
    python -c "import json;a=json.load(open('relationship_principles.clean.json'));\
b=json.load(open('relationship_natal_principles.clean.json'));\
json.dump(a+b,open('combined_relationship_principles.clean.json','w'),ensure_ascii=False,indent=1)"

Setup / key: same as extract_relationship_principles.py (env var or ~/.anthropic_key).

Run:
    python extract_natal_relationship_principles.py --limit 40      # smoke test
    python extract_natal_relationship_principles.py                 # full pass
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

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000
BATCH = 20                       # candidates per LLM classification call
DOMAIN = "relationship"

RELATIONAL_ROLES = ("partnership", "romance", "intimacy", "attraction",
                    "desire", "affection", "social", "friendship",
                    "marriage", "companionship", "general")
POLARITIES = ("harmonious", "dynamic", "neutral")

# Subject fields copied verbatim from `about` into the natal_relational block.
_SUBJECT_FIELDS = ("factor_type", "point", "sign", "house", "house_system",
                   "dignity", "dignity_ruler", "aspect", "ascendant_sign",
                   "subject_house", "subject_house_system",
                   "placement_house", "placement_house_system", "generational")

# ---------------------------------------------------------------------------
# Deterministic pre-filter (BROAD relational nature)
# ---------------------------------------------------------------------------
_REL_KEYWORDS = re.compile(
    r"\b(marri|spouse|partner|husband|wife|romance|romantic|\blove\b|lover|"
    r"companionship|friendship|\bsocial\b|relationship|descendant|"
    r"seventh house|7th house|eighth house|8th house|fifth house|5th house|"
    r"attraction|sexual|intimac|desire|affection|union|betroth|divorce)\b",
    re.I)


def is_candidate(rec: dict) -> bool:
    """Broad relational pre-filter over an already-grounded record."""
    about = rec.get("about") or {}
    # Venus / Mars as significators (broad scope keeps their delineations)
    if about.get("point") in ("Venus", "Mars"):
        return True
    # relationship houses in any house-bearing subject
    for hk in ("house", "subject_house", "placement_house"):
        if about.get(hk) in (5, 7, 8):
            return True
    # keyword signal in id / rule / judgment / tags
    blob = " ".join([
        rec.get("principle_id", ""), str(rec.get("topic_tags") or ""),
        rec.get("rule") or "", rec.get("judgment") or "",
    ])
    return bool(_REL_KEYWORDS.search(blob))


# ---------------------------------------------------------------------------
# API key + JSON helpers (shared style with the other extractor)
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


def parse_json_safe(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# LLM classification (batched)
# ---------------------------------------------------------------------------
CLASSIFY_PROMPT = """You are filtering an astrology principle dataset for RELATIONSHIP relevance, BROAD sense: partnership, marriage, romance, intimacy, sexual/affectionate nature, attraction, desire, and social/relational disposition — including how a person loves or desires (Venus/Mars sign & element style) and their social nature. EXCLUDE principles that merely mention Venus/Mars or a house in a non-relational way (e.g. Venus for money/art only, Mars for injury/work, 8th house for death/inheritance with no relational content).

For each principle object below, decide keep/drop and, if kept, assign a relational_role and polarity.

relational_role ∈ {roles}
polarity ∈ harmonious | dynamic | neutral   (the relational tone the rule implies; neutral if none)

Return VALID JSON ONLY: a JSON array, one object per input principle, in the same order:
[{{"principle_id": "...", "keep": true, "relational_role": "partnership", "polarity": "harmonious"}}, ...]
For dropped ones: {{"principle_id":"...","keep":false}}. No commentary, no fences.

PRINCIPLES:
{items}
"""


def classify_batch(client, model: str, batch: list[dict], retries: int = 3) -> dict:
    items = [{
        "principle_id": r["principle_id"],
        "about": {k: v for k, v in (r.get("about") or {}).items()
                  if k in _SUBJECT_FIELDS},
        "rule": (r.get("rule") or "")[:600],
        "judgment": (r.get("judgment") or "")[:400],
    } for r in batch]
    prompt = CLASSIFY_PROMPT.format(
        roles=" | ".join(RELATIONAL_ROLES),
        items=json.dumps(items, ensure_ascii=False, indent=1),
    )
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            msg = client.messages.create(
                model=model, max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}])
            raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            decisions = parse_json_safe(raw)
            return {d.get("principle_id"): d for d in decisions if isinstance(d, dict)}
        except json.JSONDecodeError as e:
            last_err = f"bad JSON ({e})"
        except anthropic.APIError as e:
            last_err = f"API error ({e})"
        if attempt < retries:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"classify batch failed: {last_err}")


# ---------------------------------------------------------------------------
# Record construction (clean 9 fields + synastry:natal_relational)
# ---------------------------------------------------------------------------
def build_record(rec: dict, decision: dict) -> dict:
    about = rec.get("about") or {}
    syn = {"interaction": "natal_relational", "applies_to": "each",
           "source_domain": rec.get("domain")}
    for k in _SUBJECT_FIELDS:
        if k in about:
            syn[k] = about[k]
    role = decision.get("relational_role")
    if role in RELATIONAL_ROLES:
        syn["relational_role"] = role
    pol = decision.get("polarity")
    if pol in POLARITIES:
        syn["polarity"] = pol
    return {
        "principle_id": rec["principle_id"],
        "domain": DOMAIN,
        "topic_tags": rec.get("topic_tags") or [],
        "rule": rec.get("rule") or "",
        "conditions": rec.get("conditions"),
        "judgment": rec.get("judgment") or "",
        "attribution_in_text": rec.get("attribution_in_text"),
        "notes": rec.get("notes"),
        "tradition": rec.get("tradition"),
        "synastry": syn,
    }


def main() -> int:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--records", type=Path,
                    default=here / "all_principles.grounded.json")
    ap.add_argument("--out", type=Path,
                    default=here / "relationship_natal_principles.clean.json")
    ap.add_argument("--report", type=Path,
                    default=here / "relationship_natal_extract_report.json")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--domains", default="natal,basics",
                    help="source domains to draw from (comma-sep). Default natal+"
                         "basics: static single-chart indicators applicable to a "
                         "couple. predictive/horary/mundane are other reading types.")
    ap.add_argument("--limit", type=int, default=0,
                    help="classify only the first N candidates (smoke test)")
    ap.add_argument("--no-llm", action="store_true",
                    help="pre-filter only; keep all candidates without LLM classify")
    ap.add_argument("--api-key-file", default=None)
    args = ap.parse_args()

    if not args.records.exists():
        sys.exit(f"ERROR: {args.records} not found (run the grounding backfill first).")
    records = json.loads(args.records.read_text(encoding="utf-8"))
    domains = {d.strip() for d in args.domains.split(",") if d.strip()}
    candidates = [r for r in records
                  if r.get("domain") in domains and is_candidate(r)]
    if args.limit:
        candidates = candidates[:args.limit]
    print(f"pre-filter: {len(candidates)} relationship candidates of {len(records)} "
          f"(domains={sorted(domains)})")

    kept: list[dict] = []
    if args.no_llm:
        for r in candidates:
            kept.append(build_record(r, {}))
        print("[--no-llm] kept all candidates without classification")
    else:
        if not load_api_key(args.api_key_file):
            sys.exit("ERROR: no ANTHROPIC_API_KEY (env var or ~/.anthropic_key). "
                     "Set it, or use --no-llm for the pre-filter-only pass.")
        client = anthropic.Anthropic()
        dropped = 0
        for i in range(0, len(candidates), BATCH):
            batch = candidates[i:i + BATCH]
            print(f"  classifying {i + 1}-{i + len(batch)} / {len(candidates)} ...",
                  flush=True)
            decisions = classify_batch(client, args.model, batch)
            for r in batch:
                d = decisions.get(r["principle_id"], {"keep": True})
                if d.get("keep", True):
                    kept.append(build_record(r, d))
                else:
                    dropped += 1
        print(f"classified: kept {len(kept)}, dropped {dropped}")

    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(kept, fh, ensure_ascii=False, indent=1)
    from collections import Counter
    report = {
        "total_records": len(records),
        "candidates": len(candidates),
        "kept": len(kept),
        "by_relational_role": dict(Counter(
            r["synastry"].get("relational_role", "unassigned") for r in kept)),
        "by_source_domain": dict(Counter(
            r["synastry"].get("source_domain") for r in kept)),
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"\n{len(kept)} natal relationship principles -> {args.out}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
