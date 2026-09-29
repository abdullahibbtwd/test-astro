#!/usr/bin/env python3
"""
extract_acg.py — ACG corpus delta, step 1 (spec ``ACG/ACG_06_CORPUS_DELTA_SPEC.md``).

Source: ``TXT/ACG/The-astro-carto-graphy-book-of-maps-the-astrology-of-relocation.txt``
(an OCR scan; two-column pages interleaved line by line). The source stays in
``TXT/`` (gitignored). Every intermediate that can still carry source wording
(per-chunk LLM outputs, ``acg_raw.jsonl``) is written under ``TXT/extracted_acg/``
(also gitignored); only the guarded corpus built by ``finish_acg.py`` leaves TXT/.

Pipeline (deterministic up to the LLM call):
  1. pre-clean + page split (page-number lines; plausibility-checked sequence)
  2. de-column each page (spec §3): split every line at the whitespace run nearest
     the page's modal right-column start; emit the left buffer, then the right
  3. drop noise lines (< 40% alphabetic, or < 4 chars), running heads; de-hyphenate
  4. regions: Introduction (one chunk, fixed-id prompt §4.1), case studies (one chunk
     per person profile: ALL-CAPS name line + birth-data line), Nations/Events
     (``region: mundane``); front matter, The Maps conventions page, Appendix A/B,
     the index and the trailing book ads are skipped
  5. per chunk: ``llm_client.complete(..., schema=..., temperature=0.2)``; the record
     shape, ids, scope/planet/angle vocab, conditions and domain are forced in code

Run:
    python principles_grounding/extract_acg.py --dry-run     # chunk stats + C-1 test
    python principles_grounding/extract_acg.py --limit 2     # smoke test
    python principles_grounding/extract_acg.py               # full (resumable)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import llm_client  # noqa: E402

SOURCE = os.path.join(ROOT, "TXT", "ACG",
                      "The-astro-carto-graphy-book-of-maps-the-astrology-of-relocation.txt")
WORK_DIR = os.path.join(ROOT, "TXT", "extracted_acg")
CHUNK_DIR = os.path.join(WORK_DIR, "chunks")
RAW_OUT = os.path.join(WORK_DIR, "acg_raw.jsonl")

PLANETS = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn",
           "uranus", "neptune", "pluto")
ANGLES = ("ASC", "DSC", "MC", "IC")
SCOPES = ("line", "angle_frame", "planet_general", "method", "paran", "zenith",
          "ccg", "mundane")
POLARITIES = ("supportive", "challenging", "mixed")
SENSITIVITIES = ("normal", "high")
SIGNS = ("Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio",
         "Sagittarius", "Capricorn", "Aquarius", "Pisces")
ASPECTS = ("conjunction", "sextile", "square", "trine", "opposition")
DIGNITIES = ("domicile", "detriment", "exaltation", "fall")
POINT_NAMES = tuple(p.capitalize() for p in PLANETS)
COND_KINDS = ("natal_sign", "natal_aspect", "natal_retrograde", "natal_dignity",
              "relocated_house", "relocated_angular", "text")

# Spec §4.1: the Introduction's fixed ids and their scopes.
FIXED_IDS: dict[str, tuple[str, str]] = {
    "acg-method-lines-permanent": ("method", "the lines are fixed at birth"),
    "acg-method-time-activation": ("ccg", "lines are activated over time by transits and "
                                   "progressions (cyclo-carto-graphy temporary lines)"),
    "acg-method-remote-activation": ("method", "a place can affect the person through "
                                     "dealings with it from afar, without visiting"),
    "acg-method-no-influence": ("method", "places with no line accent nothing beyond natal "
                                "importance (or let stressful natal potentials be evaded)"),
    "acg-method-crossings": ("paran", "where two lines cross, the combined influence acts "
                             "along the whole latitude of the crossing"),
    "acg-method-orb-distance": ("method", "effects are strongest near the line, perceptible up "
                                "to roughly 1,000 km, especially if it is the only line nearby; "
                                "the nearest line is the most potent regardless of distance"),
    "acg-method-zenith": ("zenith", "zenith points on the MC lines: a centre of intense energy "
                          "with a latitudinal effect"),
    "acg-method-polar-convergence": ("method", "where very many lines converge they tend to "
                                     "cancel out, yet the place feels intense"),
    "acg-method-ambivalence": ("method", "there are no good or bad planets; the use made of "
                               "the planetary energy decides"),
    "acg-method-natal-modifies-response": ("method", "the response to a planet depends on its "
                                           "natal condition (aspects, house) and on the "
                                           "person's circumstances"),
    "acg-method-degree-of-expression": ("method", "ordinary people live the same planetary "
                                        "symbols at a smaller scale than famous people"),
    "acg-method-relocated-chart": ("method", "in a new place one meets the chart one would have "
                                   "had if born there; angularity equals strength"),
    "acg-angle-mc": ("angle_frame", "the meaning of the Midheaven (MC) as a place of expression"),
    "acg-angle-asc": ("angle_frame", "the meaning of the Ascendant as a place of expression"),
    "acg-angle-ic": ("angle_frame", "the meaning of the IC as a place of expression"),
    "acg-angle-dsc": ("angle_frame", "the meaning of the Descendant as a place of expression"),
}

# ---------------------------------------------------------------------------
# 1. Pages
# ---------------------------------------------------------------------------

_PAGE_NUM_RE = re.compile(r"^\s{10,}(\d{1,3})\s*$")
_RUNNING_HEAD_RE = re.compile(
    r"^\s*(introduction|astro\W{0,3}carto\W{0,3}graphy|the maps|activists|spiritual pioneers|"
    r"entertainers|musicians and artists|writers|politicians|explorers.*|"
    r"miscellaneous personalities|nations and events|appendix [ab])\s*$", re.I)


@dataclass
class Page:
    number: int
    start: int                  # raw line index (inclusive)
    end: int                    # raw line index (exclusive)


def split_pages(lines: list[str]) -> list[Page]:
    """Pages end at a page-number line. A candidate number is accepted only if it
    continues the sequence (prev < n <= prev + 6), which rejects the digits that
    map-label OCR garbage leaves on otherwise empty lines."""
    pages: list[Page] = []
    prev_num, start = 0, 0
    for i, ln in enumerate(lines):
        m = _PAGE_NUM_RE.match(ln)
        if not m:
            continue
        n = int(m.group(1))
        if prev_num < n <= prev_num + 6:
            pages.append(Page(n, start, i))
            prev_num, start = n, i + 1
    if start < len(lines):
        pages.append(Page(prev_num + 1, start, len(lines)))
    # A missing/garbled page number merges two text pages, and a merged page
    # de-columns wrongly (left+left, then right+right). A profile heading (ALL-CAPS
    # name line followed by a birth-data line) always opens a new text page, so the
    # pages are also cut there.
    out: list[Page] = []
    for pg in pages:
        cuts = [i for i in range(pg.start + 1, pg.end) if _is_profile_head(lines, i, pg.end)]
        a = pg.start
        for c in cuts:
            out.append(Page(pg.number, a, c))
            a = c
        out.append(Page(pg.number, a, pg.end))
    return out


def _left_part(line: str) -> str:
    m = re.search(r"\S {4,}\S", line)
    return line[:m.start() + 1] if m else line


def _is_profile_head(lines: list[str], i: int, end: int) -> bool:
    head = _left_part(lines[i]).strip()
    if not head or not _is_caps_heading(head) or BIRTH_RE.search(head):
        return False
    for k in range(i + 1, min(i + 3, end)):
        if lines[k].strip():
            return bool(BIRTH_RE.search(_left_part(lines[k])))
    return False


# ---------------------------------------------------------------------------
# 2. De-column
# ---------------------------------------------------------------------------

_GAP_RE = re.compile(r" {4,}")


def _internal_gaps(line: str) -> list[tuple[int, int]]:
    """(start, end) of every run of >= 4 spaces that has text on both sides."""
    first = len(line) - len(line.lstrip(" "))
    body_end = len(line.rstrip())
    return [(m.start(), m.end()) for m in _GAP_RE.finditer(line)
            if m.start() > first and m.end() < body_end]


def estimate_split(lines: list[str]) -> int | None:
    """The modal start column of right-column text on this page (±3 bins), or
    None when fewer than 6 lines show a two-column gap."""
    cands: list[int] = []
    for ln in lines:
        for s, e in _internal_gaps(ln):
            if 30 <= e <= 110 and s >= 12:
                cands.append(e)
    if len(cands) < 6:
        return None
    hist = Counter(cands)
    best, best_n = None, -1
    for c in range(30, 111):
        n = sum(hist.get(k, 0) for k in range(c - 3, c + 4))
        if n > best_n:
            best, best_n = c, n
    return best


def decolumn_page(lines: list[str], split: int | None, base: int = 0
                  ) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Return (left, right) buffers for one page as (text, raw line index)."""
    if split is None:
        return [(ln.rstrip(), base + i) for i, ln in enumerate(lines)], []
    left: list[tuple[str, int]] = []
    right: list[tuple[str, int]] = []
    for i, raw in enumerate(lines):
        r = base + i
        ln = raw.rstrip().replace("	", "    ")
        if not ln.strip():
            left.append(("", r))
            right.append(("", r))
            continue
        gaps = [(s, e) for s, e in _internal_gaps(ln) if abs(e - split) <= 15]
        if gaps:
            s, e = min(gaps, key=lambda g: abs(g[1] - split))
            left.append((ln[:s].rstrip(), r))
            right.append((ln[e:].rstrip(), r))
            continue
        indent = len(ln) - len(ln.lstrip(" "))
        if indent >= split - 10:
            right.append((ln.strip(), r))
        else:
            left.append((ln, r))
    return left, right


def _is_noise(line: str) -> bool:
    s = line.strip()
    if len(s) < 4:
        return True
    if BIRTH_RE.search(s):
        return False                   # birth-data lines are digit-heavy but structural
    alpha = sum(ch.isalpha() for ch in s)
    return alpha / max(1, len(s)) < 0.40


def _dehyphenate(buf: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Join 'word-' + 'continuation' line breaks (lowercase continuation only)."""
    out: list[tuple[str, int]] = []
    for ln, r in buf:
        s = ln.strip()
        if out and out[-1][0].endswith("-") and s[:1].islower() and len(out[-1][0]) > 1                 and out[-1][0][-2].isalpha():
            prev, pr = out[-1]
            word, _, rest = s.partition(" ")
            out[-1] = (prev[:-1] + word, pr)
            if rest:
                out.append((rest, r))
            continue
        out.append((s, r))
    return out


@dataclass
class SLine:
    text: str
    page: int
    raw: int                   # raw line index it came from


def decolumn(lines: list[str], pages: list[Page]) -> list[SLine]:
    """The whole book as a de-columned stream of cleaned lines."""
    stream: list[SLine] = []
    last_split: int | None = None
    for pg in pages:
        body = lines[pg.start:pg.end]
        split = estimate_split(body)
        if split is None and last_split is not None:
            # a page with only a few two-column lines: reuse the neighbour's column
            gappy = sum(1 for ln in body if any(abs(e - last_split) <= 15
                                                for _, e in _internal_gaps(ln)))
            split = last_split if gappy >= 2 else None
        if split is not None:
            last_split = split
        left, right = decolumn_page(body, split, pg.start)
        for buf in (left, right):
            kept = [(ln, r) for ln, r in buf if ln.strip() and not _is_noise(ln)
                    and not _RUNNING_HEAD_RE.match(ln)]
            for t, r in _dehyphenate(kept):
                if t:
                    stream.append(SLine(t, pg.number, r))
    return stream


# ---------------------------------------------------------------------------
# 3. Regions and chunks
# ---------------------------------------------------------------------------

_MONTHS = ("JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|"
           "NOVEMBER|DECEMBER")
BIRTH_RE = re.compile(rf"\b({_MONTHS})\s+\d{{1,2}}\s*,\s*\d{{3,4}}")


def _find(lines: list[str], pat: str, after: int = 0) -> int:
    rx = re.compile(pat)
    for i in range(after, len(lines)):
        if rx.match(lines[i]):
            return i
    raise SystemExit(f"region marker not found: {pat!r} after line {after}")


@dataclass
class Regions:
    intro: tuple[int, int]
    cases: tuple[int, int]
    mundane: tuple[int, int]
    appendix_a: tuple[int, int]
    appendix_b: tuple[int, int]
    index: tuple[int, int]


def find_regions(lines: list[str]) -> Regions:
    intro = _find(lines, r"^\s*INTRODUCTION\s*$", 200)
    maps = _find(lines, r"^\s*THE MAPS\s*$", intro)
    cases = _find(lines, r"^\s*Activists\s*$", maps)
    nations = _find(lines, r"^\s*Nations and Events\s*$", cases)
    app_a = _find(lines, r"^\s*APPENDIX A\s*$", nations)
    app_b = _find(lines, r"^\s*APPENDIX B\s*$", app_a)
    idx = _find(lines, r"^\s*ALPHABETICAL INDEX\s*$", app_b)
    # the index ends at the first page-number line after which the index-entry
    # pattern stops appearing (the trailing book advertisements follow).
    entry = re.compile(r"[A-Z][\w.'\- ,]+[:;]\s*\d{1,3}\b")
    idx_end = len(lines)
    for i in range(idx + 1, len(lines)):
        if _PAGE_NUM_RE.match(lines[i]):
            ahead = [ln for ln in lines[i + 1:i + 40] if ln.strip()][:25]
            if sum(1 for ln in ahead if entry.search(ln)) < 3:
                idx_end = i
                break
    # the intro ends at the page before "THE MAPS" (its page-number line)
    intro_end = maps
    for i in range(maps - 1, intro, -1):
        if _PAGE_NUM_RE.match(lines[i]):
            intro_end = i
            break
    return Regions((intro, intro_end), (cases, nations), (nations, app_a),
                   (app_a, app_b), (app_b, idx), (idx, idx_end))


@dataclass
class Chunk:
    chunk_id: str
    kind: str                   # intro | profile | window
    region: str                 # intro | person | mundane
    text: str
    page_start: int
    page_end: int
    meta: dict = field(default_factory=dict)


def _text_of(sl: list[SLine]) -> str:
    return "\n".join(s.text for s in sl)


def _windows(sl: list[SLine], size: int = 6000, overlap: int = 600) -> list[list[SLine]]:
    out: list[list[SLine]] = []
    i = 0
    while i < len(sl):
        n, j = 0, i
        while j < len(sl) and n < size:
            n += len(sl[j].text) + 1
            j += 1
        out.append(sl[i:j])
        if j >= len(sl):
            break
        back, k = 0, j
        while k > i + 1 and back < overlap:
            k -= 1
            back += len(sl[k].text) + 1
        i = k
    return out


def _is_caps_heading(t: str) -> bool:
    letters = [c for c in t if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) >= 0.8


def build_chunks(lines: list[str] | None = None) -> tuple[list[Chunk], list[SLine], Regions]:
    lines = lines if lines is not None else read_source()
    pages = split_pages(lines)
    stream = decolumn(lines, pages)
    reg = find_regions(lines)

    chunks: list[Chunk] = []
    intro = [s for s in stream if reg.intro[0] <= s.raw < reg.intro[1]]
    # the first intro page starts before the INTRODUCTION marker (it shares the
    # foreword's last page): keep only from the marker's heading onward.
    for k, s in enumerate(intro):
        if s.text.strip().upper() == "INTRODUCTION":
            intro = intro[k + 1:]
            break
    chunks.append(Chunk("intro", "intro", "intro", _text_of(intro),
                        intro[0].page, intro[-1].page))

    seq = 0
    for region, (a, b) in (("person", reg.cases), ("mundane", reg.mundane)):
        sl = [s for s in stream if a <= s.raw < b]
        starts: list[int] = []
        for k, s in enumerate(sl):
            if BIRTH_RE.search(s.text):
                h = k - 1
                while h >= 0 and not sl[h].text.strip():
                    h -= 1
                if h >= 0 and _is_caps_heading(sl[h].text) and not BIRTH_RE.search(sl[h].text):
                    starts.append(h)
                else:
                    starts.append(k)
        starts = sorted(set(starts))
        bounds = list(zip(starts, starts[1:] + [len(sl)]))
        # text before the first profile (category headings, map garbage) as windows
        if starts and sum(len(s.text) for s in sl[:starts[0]]) > 1500:
            bounds.insert(0, (0, starts[0]))
        for (x, y) in bounds:
            part = sl[x:y]
            if not part:
                continue
            seq += 1
            prefix = "mu" if region == "mundane" else "cs"
            is_profile = x in starts
            txt = _text_of(part)
            if len(txt) <= 9000:
                chunks.append(Chunk(f"{prefix}-{seq:03d}", "profile" if is_profile else "window",
                                    region, txt, part[0].page, part[-1].page))
            else:
                for wi, w in enumerate(_windows(part)):
                    chunks.append(Chunk(f"{prefix}-{seq:03d}{chr(97 + wi)}",
                                        "profile" if is_profile else "window", region,
                                        _text_of(w), w[0].page, w[-1].page))
    return chunks, stream, reg


def _page_of(pages: list[Page], raw: int) -> int:
    for p in pages:
        if p.start <= raw < p.end:
            return p.number
    return -1


def read_source() -> list[str]:
    with open(SOURCE, encoding="utf-8", errors="replace") as fh:
        return fh.read().split(chr(10))


def decolumned_text(region: str = "all") -> str:
    """The de-columned, cleaned text used by the C-1 and C-3 guards.
    region: 'intro' | 'body' (intro + case studies + mundane) | 'all'."""
    lines = read_source()
    pages = split_pages(lines)
    stream = decolumn(lines, pages)
    reg = find_regions(lines)
    if region == "intro":
        a, b = reg.intro
    elif region == "body":
        a, b = reg.intro[0], reg.mundane[1]
    else:
        a, b = 0, len(lines)
    return _text_of([s for s in stream if a <= s.raw < b])


def c1_check(intro_text: str) -> tuple[bool, str]:
    """Spec §3 test C-1: principle 6's heading and '700 miles' are within 400 chars
    and no right-column text ('Famous people exhibit') sits between them."""
    flat = re.sub(r"\s+", " ", intro_text)
    h = flat.find("How Close Do You Have to Be?")
    m = flat.find("700 miles", h if h >= 0 else 0)
    if h < 0 or m < 0:
        return False, f"heading at {h}, '700 miles' at {m}"
    between = flat[h:m]
    if m - h > 400:
        return False, f"distance {m - h} > 400"
    if "Famous people exhibit" in between:
        return False, "right-column text interleaved"
    return True, f"distance {m - h} chars, contiguous"


# ---------------------------------------------------------------------------
# 4. Prompts + schemas
# ---------------------------------------------------------------------------

COMMON_RULES = """You are an extraction engine for an astrology knowledge base. The source \
is a book on astrocartography (ACG, "locational astrology"): a person's natal planets drawn \
as lines on a world map where each planet was rising (ASC), setting (DSC), culminating (MC; \
the book writes "MH" — always write MC) or anti-culminating (IC) at birth. You output \
structured, atomic interpretive PRINCIPLES (technique -> meaning), never a summary.

RULES (all mandatory):
1. GENERALISE. No personal names, no place names (cities, countries, regions, landmarks), \
no dates or years, no biographical events, no organisations, no titles of works. Turn an \
anecdote into the general principle it illustrates: "Saturn on the MC coincided with the \
subject's forced resignation" -> "Saturn on the MC: public responsibility can come with \
exposure to judgement and loss of standing when authority is misused."
2. PARAPHRASE. Never reuse the source's wording: no run of more than SEVEN consecutive words \
from the source, no distinctive images or turns of phrase. Restate in neutral, technical \
language of your own.
3. Third person, present tense ("the person", "someone living under this line"). Never "you".
4. Technique + meaning only: what the placement/line tends to bring. No chart-reading advice \
about the book, no praise of the method, no statistics about the book's examples.
5. Planet names in full (Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, \
Pluto); angles as ASC, DSC, MC, IC (or Ascendant, Descendant, Midheaven, IC).
6. polarity: "supportive", "challenging" or "mixed", as the source frames the meaning. Keep \
supportive and challenging content in SEPARATE records whenever the source gives both sides.
7. sensitivity: "high" if the meaning involves death, violence, accident, injury, illness, \
crime, addiction or victimisation; else "normal".
8. conditions: ONLY conditions the source explicitly states as modifying the meaning (e.g. \
"when Mars squares Saturn at birth", "if the planet is retrograde"). Never invent one. Use \
the structured kinds:
   natal_sign {point, sign}; natal_aspect {point, other, aspect (or "" if unspecified)};
   natal_retrograde {point}; natal_dignity {point, dignity: domicile|detriment|exaltation|fall};
   relocated_house {point, house 1-12}; relocated_angular {point};
   text {text} for any other stated condition (generalised, no names/places).
   Unused fields are "" (or 0 for house). Most records have NO conditions ([]).
9. rule = the principle (1-3 sentences). judgment = its practical meaning in one sentence. \
notes = nuance or tension, else "". topic_tags = 3-6 lower-case theme tags (no planet/angle \
names, no names or places)."""

INTRO_SYSTEM = COMMON_RULES + """

TASK: this is the book's INTRODUCTION. It states the method principles, the meaning of each \
planet when dominant in a location, and the meaning of the four angles. Produce:
(a) EXACTLY ONE record for each of these 16 fixed ids (field fixed_id), capturing what the \
source says about the topic described:
{fixed}
(b) records with fixed_id "general": each planet's synopsis when it dominates a location. For \
EACH of the 10 planets give 2-4 records, with AT LEAST one "supportive" record (the gifts) \
and AT LEAST one "challenging" record (the dangers/shadow) — separate records, planet set.
For fixed-id records leave planet "" unless the topic is about one planet. Self-check: 16 \
fixed ids present once each; every planet has >=1 supportive and >=1 challenging general \
record; no names, places, dates; no 8-word run from the source; no "you"."""

CASE_SYSTEM = COMMON_RULES + """

TASK: the text is ONE case study (one person's ACG map, or a nation's/event's map) from the \
book. Lines are cited like "SA MH" (Saturn on the MC), "VE DSC" (Venus on the Descendant); \
"X*Y" or "X/ANG*Y/ANG" is a latitude crossing (paran). Planet codes: SU MO ME VE MA JU SA UR \
NE PL. Extract the GENERALISABLE principles the case illustrates, as records with scope:
- "line": what planet P on angle A tends to bring where the person lives or deals (planet + \
angle set). This is the main target.
- "paran": the meaning of a latitude crossing of two planets (planet + planet2 set).
- "zenith": a planet's zenith point / its latitude effect (planet set).
- "ccg": activation of a line in time by transits or progressions (planet/angle if stated).
- "planet_general": a planet's general locational meaning, or a profession-planet \
tendency (set vocation true for the latter).
- "mundane": only for maps of nations or events (a country's founding, a disaster).
0-12 records; skip anything that only restates a biography. One principle per record; one \
scope per record. Never mention the person, the country, the city or the event."""

USER_TMPL = """SOURCE TEXT ({kind}; region: {region}):
\"\"\"
{text}
\"\"\"

Return JSON {{"principles": [ ... ]}} as specified."""

_COND_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(COND_KINDS)},
        "point": {"type": "string", "enum": [""] + list(POINT_NAMES)},
        "other": {"type": "string", "enum": [""] + list(POINT_NAMES)},
        "aspect": {"type": "string", "enum": [""] + list(ASPECTS)},
        "sign": {"type": "string", "enum": [""] + list(SIGNS)},
        "dignity": {"type": "string", "enum": [""] + list(DIGNITIES)},
        "house": {"type": "integer"},
        "text": {"type": "string"},
    },
    "required": ["kind", "point", "other", "aspect", "sign", "dignity", "house", "text"],
}


def _record_schema(intro: bool) -> dict:
    props = {
        "planet": {"type": "string", "enum": [""] + list(PLANETS)},
        "topic_tags": {"type": "array", "items": {"type": "string"}},
        "rule": {"type": "string"},
        "judgment": {"type": "string"},
        "notes": {"type": "string"},
        "polarity": {"type": "string", "enum": list(POLARITIES)},
        "sensitivity": {"type": "string", "enum": list(SENSITIVITIES)},
        "conditions": {"type": "array", "items": _COND_SCHEMA},
    }
    req = ["planet", "topic_tags", "rule", "judgment", "notes", "polarity",
           "sensitivity", "conditions"]
    if intro:
        props = {"fixed_id": {"type": "string", "enum": list(FIXED_IDS) + ["general"]}, **props}
        req = ["fixed_id"] + req
    else:
        props = {"scope": {"type": "string", "enum": ["line", "paran", "zenith", "ccg",
                                                        "planet_general", "mundane"]},
                 "angle": {"type": "string", "enum": ["", "ASC", "DSC", "MC", "IC"]},
                 "planet2": {"type": "string", "enum": [""] + list(PLANETS)},
                 "vocation": {"type": "boolean"}, **props}
        req = ["scope", "angle", "planet2", "vocation"] + req
    return {"type": "object",
            "properties": {"principles": {"type": "array",
                                          "items": {"type": "object", "properties": props,
                                                    "required": req}}},
            "required": ["principles"]}


INTRO_SCHEMA = _record_schema(True)
CASE_SCHEMA = _record_schema(False)

# ---------------------------------------------------------------------------
# 5. Shaping (forced in code)
# ---------------------------------------------------------------------------

_HIGH_RE = re.compile(
    r"\b(death|dying|die[sd]?|mortal|murder\w*|kill\w*|violen\w*|assassin\w*|accident\w*|"
    r"injur\w*|wound\w*|illness|ill(?!-)|disease\w*|sick\w*|crim\w*|addict\w*|drug\w*|alcohol\w*|"
    r"victim\w*|abus\w*|suicid\w*|attack\w*|war|warfare|persecut\w*)\b", re.I)


def sensitivity_of(text: str, declared: str) -> str:
    return "high" if declared == "high" or _HIGH_RE.search(text or "") else "normal"


def mh_to_mc(s: str) -> str:
    return re.sub(r"\bMH\b", "MC", s or "")


def shape_condition(c: dict) -> dict | None:
    """Model condition object -> the stored wrapper form {kind: {...fields}}."""
    kind = c.get("kind")
    pt, other = c.get("point") or "", c.get("other") or ""
    if kind == "natal_sign" and pt and c.get("sign"):
        return {"natal_sign": {"point": pt, "sign": c["sign"]}}
    if kind == "natal_aspect" and pt and other and pt != other:
        d = {"point": pt, "other": other}
        if c.get("aspect"):
            d["aspect"] = c["aspect"]
        return {"natal_aspect": d}
    if kind == "natal_retrograde" and pt:
        return {"natal_retrograde": {"point": pt}}
    if kind == "natal_dignity" and pt and c.get("dignity"):
        return {"natal_dignity": {"point": pt, "dignity": c["dignity"]}}
    if kind == "relocated_house" and pt and isinstance(c.get("house"), int) \
            and 1 <= c["house"] <= 12:
        return {"relocated_house": {"point": pt, "house": c["house"]}}
    if kind == "relocated_angular" and pt:
        return {"relocated_angular": {"point": pt}}
    txt = (c.get("text") or "").strip()
    if txt:
        return {"text": mh_to_mc(txt)}
    return None


def _tags(item: dict, lead: list[str]) -> list[str]:
    tags = [t.strip().lower() for t in (item.get("topic_tags") or [])
            if isinstance(t, str) and t.strip()]
    skip = {x.lower() for x in lead} | set(PLANETS) | {a.lower() for a in ANGLES} | {"mh"}
    out = list(lead)
    for t in tags:
        if t not in skip and t not in out:
            out.append(t)
    return out[:len(lead) + 6]


def shape(chunk: Chunk, data: dict) -> list[dict]:
    out: list[dict] = []
    n = 0
    for item in data.get("principles") or []:
        rule = mh_to_mc((item.get("rule") or "").strip())
        if len(rule) < 40:
            continue
        planet = item.get("planet") or ""
        planet = planet if planet in PLANETS else ""
        fixed = None
        vocation = False
        planets: list[str] = []
        angle = ""
        if chunk.kind == "intro":
            fid = item.get("fixed_id")
            if fid in FIXED_IDS:
                fixed = fid
                scope = FIXED_IDS[fid][0]
                if scope == "angle_frame":
                    angle = fid.rsplit("-", 1)[1].upper()
            elif fid == "general" and planet:
                scope = "planet_general"
            else:
                continue
        else:
            scope = item.get("scope")
            angle = item.get("angle") or ""
            angle = "MC" if angle == "MH" else angle
            vocation = bool(item.get("vocation"))
            if chunk.region == "mundane":
                scope = "mundane"
            elif scope == "mundane":
                continue                               # person chunks: no mundane records
            if scope == "line" and not (planet and angle in ANGLES):
                continue
            if scope == "planet_general" and not planet:
                continue
            if scope == "paran":
                p2 = item.get("planet2") or ""
                if not (planet and p2 in PLANETS and p2 != planet):
                    continue
                planets = sorted([planet, p2])
            if scope not in ("line", "ccg"):
                angle = "" if scope != "mundane" else angle
        conds = [c2 for c2 in (shape_condition(c) for c in (item.get("conditions") or [])
                               if isinstance(c, dict)) if c2]
        judgment = mh_to_mc((item.get("judgment") or "").strip()) or None
        notes = mh_to_mc((item.get("notes") or "").strip()) or None
        lead: list[str] = ["astrocartography"]
        if planet and scope != "paran":
            lead.append(planet.capitalize())
        for p in planets:
            lead.append(p.capitalize())
        if angle:
            lead.append(angle)
        if vocation and scope == "planet_general":
            lead.append("vocation")
        polarity = item.get("polarity") if item.get("polarity") in POLARITIES else "mixed"
        blob = " ".join(filter(None, [rule, judgment, notes]))
        n += 1
        out.append({
            "principle_id": fixed or f"raw-{chunk.chunk_id}-{n:02d}",
            "domain": "astrocartography",
            "topic_tags": _tags(item, lead),
            "rule": rule,
            "conditions": conds,
            "judgment": judgment,
            "attribution_in_text": None,
            "notes": notes,
            "tradition": "modern",
            "source": "lewis_guttman_1989",
            "acg_scope": scope,
            "polarity": polarity,
            "sensitivity": sensitivity_of(blob, item.get("sensitivity") or "normal"),
            "citation_count": 1,
            "source_span": {"page_start": chunk.page_start, "page_end": chunk.page_end},
            # bucketing keys (consumed by consolidate/finish; not corpus fields)
            "_planet": planet if scope != "paran" else "",
            "_angle": angle if scope in ("line", "angle_frame", "ccg") else "",
            "_planets": planets,
            "_fixed_id": fixed,
            "_chunk": chunk.chunk_id,
        })
    return out


def intro_problems(recs: list[dict]) -> list[str]:
    probs: list[str] = []
    have = Counter(r["_fixed_id"] for r in recs if r["_fixed_id"])
    missing = [f for f in FIXED_IDS if not have.get(f)]
    if missing:
        probs.append(f"missing fixed ids: {missing}")
    for p in PLANETS:
        pol = {r["polarity"] for r in recs
               if r["acg_scope"] == "planet_general" and r["_planet"] == p}
        if not ({"supportive", "challenging"} <= pol):
            probs.append(f"{p}: general polarities {sorted(pol)}")
    return probs


def dedupe_fixed(recs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for r in recs:
        f = r["_fixed_id"]
        if f:
            if f in seen:
                continue
            seen.add(f)
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# 6. Driver
# ---------------------------------------------------------------------------

def _chunk_path(cid: str) -> str:
    return os.path.join(CHUNK_DIR, f"{cid}.json")


def extract_chunk(chunk: Chunk, model: str) -> dict:
    intro = chunk.kind == "intro"
    if intro:
        fixed = "\n".join(f"  - {k}: {v[1]}" for k, v in FIXED_IDS.items())
        system = INTRO_SYSTEM.replace("{fixed}", fixed)
        schema = INTRO_SCHEMA
    else:
        system, schema = CASE_SYSTEM, CASE_SCHEMA
    user = USER_TMPL.format(kind=chunk.kind, region=chunk.region, text=chunk.text)
    usage = {k: 0 for k in llm_client.USAGE_KEYS}
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = llm_client.complete(model, system, user,
                                       max_tokens=24000 if intro else 12000,
                                       temperature=0.2, schema=schema, timeout_s=300.0,
                                       label=f"acg/{chunk.chunk_id}")
            for k in usage:
                usage[k] += (resp.usage or {}).get(k, 0)
            if resp.stop_reason == "max_tokens":
                raise RuntimeError("output truncated")
            recs = shape(chunk, json.loads(resp.text))
            if intro:
                recs = dedupe_fixed(recs)
                probs = intro_problems(recs)
                if probs:
                    raise RuntimeError("; ".join(probs))
            return {"chunk_id": chunk.chunk_id, "kind": chunk.kind, "region": chunk.region,
                    "page_start": chunk.page_start, "page_end": chunk.page_end,
                    "model": model, "attempts": attempt, "usage": usage, "principles": recs}
        except (json.JSONDecodeError, RuntimeError) as exc:
            last = exc
            print(f"  retry {chunk.chunk_id} ({attempt}): {exc}", flush=True)
            time.sleep(2 * attempt)
        except llm_client.transient_errors(model) as exc:
            last = exc
            time.sleep(5 * attempt)
    raise RuntimeError(f"{chunk.chunk_id}: failed after 3 attempts: {last}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract ACG principles (corpus delta, spec 06).")
    ap.add_argument("--model", default=llm_client.DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="only the first N pending chunks")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true",
                    help="chunk stats + the C-1 de-column test; no model calls")
    args = ap.parse_args()

    if not os.path.exists(SOURCE):
        sys.exit(f"source text not found: {SOURCE}")
    chunks, stream, reg = build_chunks()
    kinds = Counter((c.kind, c.region) for c in chunks)
    sizes = [len(c.text) for c in chunks]
    print(f"regions (raw lines): intro {reg.intro}, cases {reg.cases}, mundane {reg.mundane}, "
          f"appendix A {reg.appendix_a}, appendix B {reg.appendix_b}, index {reg.index}")
    print(f"{len(chunks)} chunks: {dict(kinds)}; chars total {sum(sizes):,}, "
          f"min {min(sizes)}, max {max(sizes)}")
    intro_text = next(c.text for c in chunks if c.kind == "intro")
    ok, msg = c1_check(intro_text)
    print(f"C-1 de-column test: {'PASS' if ok else 'FAIL'} ({msg})")
    if args.dry_run:
        for c in chunks:
            first = c.text.strip().splitlines()[0][:50] if c.text.strip() else ""
            print(f"  {c.chunk_id:8s} {c.kind:7s} {c.region:7s} p{c.page_start}-{c.page_end} "
                  f"{len(c.text):6d} chars | {first}")
        if not ok:
            sys.exit(1)
        return
    if not ok:
        sys.exit("C-1 failed: fix the de-columning before extracting.")

    llm_client.require_api_key(args.model, "ACG extraction")
    os.makedirs(CHUNK_DIR, exist_ok=True)
    todo = [c for c in chunks if not os.path.exists(_chunk_path(c.chunk_id))]
    already = len(chunks) - len(todo)
    if args.limit:
        todo = todo[:args.limit]
    print(f"{already} chunk(s) already extracted; {len(todo)} to run now with {args.model} "
          f"({args.workers} workers)")

    t0 = time.time()
    failed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(extract_chunk, c, args.model): c for c in todo}
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                res = fut.result()
            except Exception as exc:          # noqa: BLE001 — report and continue
                failed += 1
                print(f"  FAILED {c.chunk_id}: {exc}", flush=True)
                continue
            with open(_chunk_path(c.chunk_id), "w", encoding="utf-8", newline="\n") as fh:
                json.dump(res, fh, ensure_ascii=False, indent=2)
            print(f"  ok {c.chunk_id:8s} {len(res['principles']):2d} records "
                  f"(in={res['usage']['input_tokens']} out={res['usage']['output_tokens']})",
                  flush=True)

    combined: list[dict] = []
    usage = {k: 0 for k in llm_client.USAGE_KEYS}
    n_on_disk = 0
    for c in chunks:
        p = _chunk_path(c.chunk_id)
        if not os.path.exists(p):
            continue
        res = json.load(open(p, encoding="utf-8"))
        combined.extend(res["principles"])
        for k in usage:
            usage[k] += (res.get("usage") or {}).get(k, 0)
        n_on_disk += 1
    with open(RAW_OUT, "w", encoding="utf-8", newline="\n") as fh:
        for r in combined:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    scopes = Counter(r["acg_scope"] for r in combined)
    print(f"\ndone in {time.time() - t0:.0f}s: {n_on_disk}/{len(chunks)} chunks on disk, "
          f"{len(combined)} records -> {os.path.relpath(RAW_OUT, ROOT)}")
    print(f"scopes: {dict(scopes)}")
    print(f"tokens (all chunks on disk): in={usage['input_tokens']:,} "
          f"out={usage['output_tokens']:,}")
    if failed:
        print(f"{failed} chunk(s) failed — re-run to retry them (resumable).")
        sys.exit(1)


if __name__ == "__main__":
    main()
