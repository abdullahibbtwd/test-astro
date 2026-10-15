"""distill.py — pipeline stage L5: distil a reading into ratable statements.

Implements EVAL_HARNESS_SPEC.md (Feature 2 + the score-sheet half of Feature 3).

Primary path: ``run.py`` imports and calls :func:`distill` as the final, mandatory
stage of one orchestrated run (ORCHESTRATOR_SPEC.md §4 step 7). It turns the locked
final reading (``l4_output.json``) into:

  * ``statements.json`` — atomic, jargon-free, third-person claims about the person,
    deduplicated across sections, each tagged with a category, source sections,
    a grounding-trace (``principle_ids``) and a cross-section ``frequency``.
  * ``statements.txt`` — the same statements as plain bullets.
  * ``scoresheet.csv`` — one empty-``score`` row per statement, for a human to fill.

Secondary path: runnable standalone to re-distil an existing run (§8):

    python distill.py --l4 runs/<id>/l4_output.json --out runs/<id>/

The score *readback* lives in ``score_report.py`` and runs after a human fills in
the scores — it cannot be a stage of the automated run (the scores don't exist yet).

One English model call (gpt-6-luna default — extraction-shaped work suits the cheap model);
provider follows the model id via llm_client.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

import os as _os
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
import llm_client  # provider-agnostic completion (Anthropic / Gemini)

DEFAULT_MODEL = llm_client.DEFAULT_CHEAP_MODEL  # extraction-shaped English call: gpt-6-luna
_MAX_TOKENS = 8192
_STREAM_STALL_TIMEOUT_S = 120.0

# Sampling parameters are removed on the Claude 5 / Opus 4.7+ family; sending `temperature`
# there returns a 400. Only forward it to older models that still accept it.
_NO_SAMPLING_PREFIXES = llm_client.NO_SAMPLING_PREFIXES


_supports_temperature = llm_client.supports_temperature

# Closed category enum (EVAL_HARNESS_SPEC.md §4). Reuses the 42-statement clustering
# so the readback (score_report.py) reproduces those groupings automatically.
CATEGORIES = {
    "cognitive_style",   # how they think / process / decide
    "values",            # what matters to them, priorities
    "behavioral",        # observable habits, tendencies, actions
    "emotional",         # inner emotional life, regulation, reactivity
    "relational",        # how they relate to others
    "motivational",      # drives, ambitions, what moves them
    "shadow",            # self-sabotage / fear / pathology-framing claims
    "other",             # valid statement that fits none of the above
}

# Constrained-decoding schema (same house pattern as L4 l4_generate). Forcing the
# output to this shape guarantees non-empty, valid JSON — without it the model can
# (and did) return an empty/unparseable response that no retry recovers.
STATEMENTS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "statements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "text": {"type": "string"},
                    "category": {"type": "string", "enum": sorted(CATEGORIES)},
                    "source_sections": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "category", "source_sections"],
            },
        },
    },
    "required": ["statements"],
}

# Astrology-term blocklist (§7 invariant 1). A *light* guard: the prompt is what
# enforces jargon-freeness; this only flags leaks so they're visible during tuning.
# We flag, never silently drop. Word-boundary, case-insensitive matching keeps
# false positives low; an occasional flag is cheaper than a buried miss.
_ASTRO_TERMS = [
    # luminaries / planets / points
    "sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
    "uranus", "neptune", "pluto", "chiron", "lilith",
    "ascendant", "descendant", "midheaven", "imum coeli", "north node",
    "south node", "lunar node",
    # signs
    "aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra",
    "scorpio", "sagittarius", "capricorn", "aquarius", "pisces",
    # structure / method vocabulary
    "zodiac", "zodiacal", "horoscope", "natal", "placement", "house",
    "cusp", "ruler", "rulership", "dignity", "exaltation", "detriment",
    "fall", "sect", "diurnal", "nocturnal", "decan", "lot", "part of fortune",
    "retrograde", "stationary", "rising sign",
    # aspects
    "conjunction", "conjunct", "opposition", "trine", "sextile", "square",
    "quincunx", "inconjunct", "aspect", "orb",
]
_ASTRO_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _ASTRO_TERMS) + r")\b",
    re.IGNORECASE,
)


def _log(msg: str) -> None:
    print(f"[l5] {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# JSON extraction — defensive parse per the house pattern (l4_generate._extract_json).
# Models occasionally wrap JSON in prose or code fences even when told not to.
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start:end + 1], strict=False)
        raise


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM = """You distil an astrological character reading into clean, ratable \
statements about the *person* — the kind a stranger could read and judge true or \
false about themselves. You output JSON only.

You will be given the reading split into labelled sections. Extract atomic claims \
about the person. Every statement you emit MUST satisfy ALL of these:

1. ATOMIC — exactly one claim per statement. Split compound sentences into \
separate statements.
2. ABOUT THE PERSON — a description of who they are, how they think, what they \
value, how they feel, or how they behave. DROP anything about the chart, the \
method, the planets, or the reading itself.
3. JARGON-FREE — NO astrology terms whatsoever. No planet, sign, house, aspect, \
element, dignity, sect, lot, ruler, "natal", "placement", "rising", etc. If a \
claim cannot survive without such a word, rewrite it in plain psychological / \
behavioural language, or drop it entirely.
4. FALSIFIABLE / PLAIN — a flat, declarative third-person statement the person \
could confirm or deny. No hedging ("may sometimes perhaps"), no poetry, no fluff, \
no second-person sermonising. Use forms like "Tends to…", "Values…", "Is drawn \
to…", "Struggles with…".
5. SELF-CONTAINED — understandable on its own, without the surrounding paragraph.

DEDUPLICATION: when the same underlying claim appears in more than one section, \
emit it ONCE and list every section it came from in `source_sections`. Do not \
repeat near-identical claims.

CATEGORY: assign each statement exactly one category from this closed set:
  cognitive_style  — how they think / process / decide
  values           — what matters to them, priorities
  behavioral       — observable habits, tendencies, actions
  emotional        — inner emotional life, regulation, reactivity
  relational       — how they relate to others
  motivational     — drives, ambitions, what moves them
  shadow           — self-sabotage, fear, or pathology-framing claims
  other            — a valid statement that fits none of the above

OUTPUT: return JSON ONLY — no prose, no markdown fences — of exactly this shape:
{
  "statements": [
    {
      "text": "Tends to analyse a problem thoroughly before acting.",
      "category": "cognitive_style",
      "source_sections": ["core_identity", "communication_learning"]
    }
  ]
}
Every `source_sections` value MUST be one of the section labels you were given."""


def _build_user(sections: list[dict]) -> str:
    blocks = []
    for s in sections:
        key = s.get("key", "")
        text = (s.get("text_en") or "").strip()
        if not text:
            continue
        blocks.append(f"### SECTION: {key}\n{text}")
    body = "\n\n".join(blocks)
    return (
        "Here is the reading, split into labelled sections. Distil it into "
        "statements per the rules. Return JSON only.\n\n" + body
    )


# ---------------------------------------------------------------------------
# Model call (one English call, retry once on parse failure, then fail loudly)
# ---------------------------------------------------------------------------

def _call_model(system: str, user: str, model: str) -> dict:
    llm_client.require_api_key(model, "the L5 distiller")

    def _once(extra_system: str) -> dict:
        # Constrained decoding: the API guarantees schema-conforming JSON, so
        # an empty / prose / fenced response can't slip through.
        resp = llm_client.complete(
            model, system + extra_system, user, max_tokens=_MAX_TOKENS,
            temperature=0.2 if _supports_temperature(model) else None,  # extraction, not invention
            schema=STATEMENTS_SCHEMA, timeout_s=_STREAM_STALL_TIMEOUT_S,
            label="distill")
        text = resp.text
        if not text.strip():
            # Should be unreachable with constrained decoding; surface the reason
            # rather than a cryptic "Expecting value" on an empty string.
            raise RuntimeError(
                f"distiller model returned no text (stop_reason={resp.stop_reason!r})")
        return _extract_json(text)

    try:
        return _once("")
    except llm_client.ProviderQuotaError as err:
        # The cheap model has no credits: the scoresheet is still needed, so run
        # the one call on the main reading model instead of failing the run.
        if model == llm_client.DEFAULT_MODEL:
            raise
        _log(f"{err} — falling back to {llm_client.DEFAULT_MODEL}")
        return _call_model(system, user, llm_client.DEFAULT_MODEL)
    except json.JSONDecodeError:
        _log("first response was not parseable JSON — retrying once")
        return _once(
            "\n\nREMINDER: return JSON ONLY. No prose, no explanation, no "
            "markdown code fences — just the JSON object."
        )


# ---------------------------------------------------------------------------
# Post-processing: ids, provenance union, frequency, validation, jargon guard
# ---------------------------------------------------------------------------

def _post_process(raw: dict, sections: list[dict]) -> list[dict]:
    pid_by_section: dict[str, list[str]] = {
        s.get("key", ""): list(s.get("principle_ids") or []) for s in sections
    }
    known_keys = set(pid_by_section)

    out: list[dict] = []
    n = 0
    for item in (raw.get("statements") or []):
        text = (item.get("text") or "").strip()
        if not text:
            continue

        # source_sections: keep only labels that actually exist; dedupe, preserve order.
        seen: set[str] = set()
        srcs: list[str] = []
        for k in (item.get("source_sections") or []):
            if k in known_keys and k not in seen:
                seen.add(k)
                srcs.append(k)
        if not srcs:
            # Invariant 5: source_sections must be non-empty. An untraceable claim
            # is dropped (loudly) rather than written invalid.
            _log(f"DROP (no valid source section): {text!r}")
            continue

        # category: coerce unknown values to 'other' so invariant 4 always holds.
        category = (item.get("category") or "").strip()
        if category not in CATEGORIES:
            _log(f"category {category!r} not in enum — coercing to 'other': {text!r}")
            category = "other"

        # principle_ids: union of the source sections' ids, in stable order.
        pids: list[str] = []
        pseen: set[str] = set()
        for k in srcs:
            for p in pid_by_section.get(k, []):
                if p not in pseen:
                    pseen.add(p)
                    pids.append(p)

        # jargon guard (§7 invariant 1): flag leaks, do not drop.
        leak = _ASTRO_RE.search(text)
        if leak:
            _log(f"ASTROLOGY TERM LEAK ({leak.group(0)!r}) — flagged, kept: {text!r}")

        n += 1
        out.append({
            "id": f"s{n:03d}",
            "text": text,
            "category": category,
            "source_sections": srcs,
            "principle_ids": pids,            # best-effort provenance; may be empty
            "frequency": len(srcs),           # distinct sections expressing the claim
        })
    return out


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def _run_id(l4_output: dict, out_dir: str) -> str:
    rid = l4_output.get("run_id")
    if rid:
        return str(rid)
    base = os.path.basename(os.path.normpath(out_dir))
    return base or "unknown"


def _write_json(path: str, run_id: str, statements: list[dict]) -> None:
    payload = {
        "run_id": run_id,
        "source": "l4_output.json",
        "language": "en",
        "count": len(statements),
        "statements": statements,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _write_txt(path: str, statements: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for s in statements:
            fh.write(f"- {s['text']}\n")


def _write_csv(path: str, statements: list[dict]) -> None:
    # stdlib csv writer with proper quoting (statements contain commas). score and
    # comment are emitted empty for the human to fill (§5). One row per statement.
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "statement", "category", "source_sections",
                    "frequency", "score", "comment"])
        for s in statements:
            w.writerow([
                s["id"],
                s["text"],
                s["category"],
                ";".join(s["source_sections"]),   # ';'-joined per §5
                s["frequency"],
                "",                                 # score — empty
                "",                                 # comment — empty
            ])


# ---------------------------------------------------------------------------
# Public entry point — pipeline stage L5
# ---------------------------------------------------------------------------

def _suffixed(filename: str, suffix: str | None) -> str:
    """Insert ``_<suffix>`` after the base name (before the first dot), so the L5
    outputs match the rest of a run folder's birth-date-suffixed artifacts.
    ``suffix=None`` (standalone default) leaves names unchanged. Idempotent."""
    if not suffix:
        return filename
    base, dot, rest = filename.partition(".")
    tag = f"_{suffix}"
    if base.endswith(tag):
        return filename
    return f"{base}{tag}{dot}{rest}"


def distill(l4_output: dict, out_dir: str, *, model: str = DEFAULT_MODEL,
            suffix: str | None = None) -> list[str]:
    """Distil the locked final reading into clean statements.

    Writes ``statements.json``, ``statements.txt`` and ``scoresheet.csv`` into
    ``out_dir`` and returns the written paths. When ``suffix`` is given (e.g. the
    birth date, as the orchestrator passes), it is inserted into each filename
    (``statements_1990-07-13.json``, …) so artifacts never collide across runs.
    Reads only the English text (``text_en``); never emits Turkish (§7 inv. 6).
    """
    sections = l4_output.get("sections") or []
    if not sections:
        raise ValueError("l4_output has no sections — nothing to distil.")

    os.makedirs(out_dir, exist_ok=True)

    _log(f"distilling {len(sections)} sections with {model}")
    raw = _call_model(_SYSTEM, _build_user(sections), model)
    statements = _post_process(raw, sections)
    if not statements:
        raise RuntimeError(
            "distillation produced zero valid statements — refusing to write empty "
            "outputs. Inspect the model response / source reading."
        )
    _log(f"{len(statements)} statements after dedup + validation")

    run_id = _run_id(l4_output, out_dir)
    json_path = os.path.join(out_dir, _suffixed("statements.json", suffix))
    txt_path = os.path.join(out_dir, _suffixed("statements.txt", suffix))
    csv_path = os.path.join(out_dir, _suffixed("scoresheet.csv", suffix))

    _write_json(json_path, run_id, statements)
    _write_txt(txt_path, statements)
    _write_csv(csv_path, statements)

    _log(f"wrote {json_path}, {txt_path}, {csv_path}")
    return [json_path, txt_path, csv_path]


# ---------------------------------------------------------------------------
# Standalone CLI (§8 secondary path) — re-distil an existing run
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Re-distil a locked reading into statements + scoresheet (L5)."
    )
    ap.add_argument("--l4", required=True,
                    help="path to the run's l4_output.json")
    ap.add_argument("--out", required=True,
                    help="output directory (the run folder) for statements.* / scoresheet.csv")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"distiller model (default {DEFAULT_MODEL})")
    ap.add_argument("--suffix", default=None,
                    help="insert this token (e.g. the birth date) into each output "
                         "filename, matching the orchestrator's run-folder naming")
    args = ap.parse_args(argv)

    with open(args.l4, encoding="utf-8") as fh:
        l4_output = json.load(fh)

    paths = distill(l4_output, args.out, model=args.model, suffix=args.suffix)
    print("Wrote:")
    for p in paths:
        print(f"  {p}")
    csv_path = paths[-1]   # distill returns [statements.json, statements.txt, scoresheet.csv]
    print(
        f"\nNext: fill in the `score` column (0–10) in {os.path.basename(csv_path)}, "
        f"then run:\n  python score_report.py {csv_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
