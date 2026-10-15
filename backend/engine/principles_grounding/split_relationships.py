#!/usr/bin/env python3
"""
split_relationships.py

Separate ``TXT/Relationships.txt`` (Sakoian & Acker, *Analyzing Human
Relationships* — the horoscopic-comparison text) into clean, digestible
chunks that can be fed to an LLM one at a time for principle extraction.

The book has a very regular structure:

    PART III  COMPARATIVE INFLUENCES OF THE PLANETS
      <Planet chapter>            e.g. "Sun"   (a bare planet name on its own line)
        <chapter intro>
        COMPARATIVE HOUSE PLACEMENTS
            First House ...  ...  Twelfth House ...
        COMPARATIVE CONJUNCTIONS
            A's Sun Conjunct B's Sun ...
            A's Sun Conjunct B's Moon ...
        COMPARATIVE SEXTILES / SQUARES / TRINES / OPPOSITIONS
            ...

Each ``(chapter, section)`` pair is a natural digestible unit, and each
``A's X Aspect B's Y`` line (or ``Nth House`` line) is a single principle.

The OCR text is polluted with running headers / footers that split
sentences mid-paragraph:

    COMPARATIVE CONJUNCTIONS 67        <- running header (page 67)
    68 sun                             <- running footer
    ANALYZING HUMAN RELATIONSHIPS 37   <- book running head
    61                                 <- bare page number
    VII                                <- roman-numeral chapter number

These are detected and removed so the reconstructed prose reads cleanly.

Usage
-----
    python split_relationships.py                       # sensible defaults
    python split_relationships.py --granularity entry   # one file per principle
    python split_relationships.py --input path.txt --outdir out/

Outputs (into --outdir, default ./relationships_chunks/):
    chunks/0001_sun__comparative_conjunctions.txt   ... one file per chunk
    manifest.json                                   ... list of chunk metadata
    chunks.jsonl                                    ... same, with full text inline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #

PLANETS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars",
    "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
]
PLANETS_UPPER = {p.upper() for p in PLANETS}

# The six aspect/placement subsections, normalized to their canonical caps form.
SUBSECTION_TITLES = [
    "COMPARATIVE HOUSE PLACEMENTS",
    "COMPARATIVE CONJUNCTIONS",
    "COMPARATIVE SEXTILES",
    "COMPARATIVE SQUARES",
    "COMPARATIVE TRINES",
    "COMPARATIVE OPPOSITIONS",
]
SUBSECTION_SET = set(SUBSECTION_TITLES)

# Running heads that are page furniture, never a real section we want to keep.
ALWAYS_DROP_TITLES = {
    "ANALYZING HUMAN RELATIONSHIPS",
    "BASIC CONCEPTS IN HOROSCOPIC COMPARISON",
}

HOUSE_ORDINALS = [
    "First", "Second", "Third", "Fourth", "Fifth", "Sixth",
    "Seventh", "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth",
]
HOUSE_ENTRY_RE = re.compile(
    r"^(?:%s)\s+House$" % "|".join(HOUSE_ORDINALS), re.IGNORECASE
)

# Atomic comparison entry, e.g.  A's Sun Conjunct B's Moon (A's O d B's J)
# Apostrophe may be straight ' , curly ’ , or backtick.
APOS = r"[’'`]"
ENTRY_RE = re.compile(rf"^A{APOS}s\s+.+?\bB{APOS}s\s+.+", re.IGNORECASE)

ROMAN_ONLY_RE = re.compile(r"^[IVXLCM]{1,7}$")
DIGITS_ONLY_RE = re.compile(r"^\d{1,4}$")


# --------------------------------------------------------------------------- #
# Line normalization / classification helpers
# --------------------------------------------------------------------------- #

def caps_core(line: str) -> str:
    """
    Reduce a candidate header line to its title 'core':

      * keep only A-Z and spaces (drops digits, punctuation, OCR glyphs)
      * collapse whitespace
      * strip trailing 1-2 letter tokens (OCR-mangled page numbers such as
        the 'I' in 'I45', the 'X' in 'X 55', the 'H' in 'H7')

    'COMPARATIVE CONJUNCTIONS 67'   -> 'COMPARATIVE CONJUNCTIONS'
    'COMPARATIVE SEXTILES I45'      -> 'COMPARATIVE SEXTILES'
    '58 BASIC CONCEPTS IN ...'      -> 'BASIC CONCEPTS IN ...'
    """
    letters = re.sub(r"[^A-Za-z ]+", " ", line.upper())
    tokens = letters.split()
    # strip trailing short OCR page-token debris
    while tokens and len(tokens[-1]) <= 2:
        tokens.pop()
    return " ".join(tokens)


def is_all_caps_title(line: str) -> bool:
    """True if the alphabetic characters of the line are all uppercase."""
    alpha = [c for c in line if c.isalpha()]
    return bool(alpha) and all(c.isupper() for c in alpha)


def title_case(s: str) -> str:
    small = {"of", "the", "in", "to", "and", "or", "a", "an"}
    words = s.lower().split()
    out = []
    for i, w in enumerate(words):
        out.append(w if (w in small and i) else w.capitalize())
    return " ".join(out)


# --------------------------------------------------------------------------- #
# Text reflow (undo OCR line wrapping within a paragraph)
# --------------------------------------------------------------------------- #

def reflow(lines: list[str]) -> str:
    """Join a list of body lines into a single clean paragraph string."""
    out = ""
    for raw in lines:
        piece = raw.strip()
        if not piece:
            continue
        if not out:
            out = piece
            continue
        if out.endswith("-"):
            # de-hyphenate a word broken across the line wrap
            out = out[:-1] + piece
        else:
            out = out + " " + piece
    # tidy a few common OCR spacing artifacts around punctuation
    out = re.sub(r"\s+([,.;:!?])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class Entry:
    label: str                       # e.g. "A's Sun Conjunct B's Moon" or "First House"
    lines: list[str] = field(default_factory=list)

    def text(self) -> str:
        return reflow(self.lines)


@dataclass
class Section:
    chapter: str                     # "Sun", or "Basic Concepts" for front matter
    title: str                       # section / subsection title (Title Case)
    intro_lines: list[str] = field(default_factory=list)
    entries: list[Entry] = field(default_factory=list)

    def intro_text(self) -> str:
        return reflow(self.intro_lines)

    def is_empty(self) -> bool:
        return not self.intro_lines and not self.entries


# --------------------------------------------------------------------------- #
# Core parser
# --------------------------------------------------------------------------- #

def parse(text: str) -> list[Section]:
    lines = text.splitlines()
    sections: list[Section] = []

    chapter = "Basic Concepts"          # front matter until first planet chapter
    part = "Basic Concepts in Horoscopic Comparison"
    cur: Section | None = None
    cur_entry: Entry | None = None

    def open_section(title: str):
        nonlocal cur, cur_entry
        cur = Section(chapter=chapter, title=title)
        sections.append(cur)
        cur_entry = None

    def body_target() -> list[str]:
        """Where a plain body line should go: current entry, else section intro."""
        if cur is None:
            open_section("Preamble")
        if cur_entry is not None:
            return cur_entry.lines
        return cur.intro_lines

    for raw in lines:
        s = raw.strip()

        # -- blank line: paragraph separator, keep as a soft break marker ----
        if not s:
            body_target().append("")
            continue

        # -- pure page number / roman-numeral chapter marker: drop -----------
        if DIGITS_ONLY_RE.match(s) or ROMAN_ONLY_RE.match(s):
            continue

        core = caps_core(s)
        has_digit = any(c.isdigit() for c in s)

        # -- planet running footer/header ("62 SUN", "68 sun"): drop ---------
        if has_digit and core in PLANETS_UPPER:
            continue

        # -- planet chapter title (bare "Sun", "Moon", ...): new chapter -----
        if s in PLANETS:
            chapter = s
            part = "Comparative Influences of the Planets"
            # a fresh planet chapter opens with its introduction section
            open_section("Chapter Introduction")
            continue

        # -- one of the six aspect subsections (bare or with page number) ----
        if core in SUBSECTION_SET:
            # running header repeating the current subsection -> ignore
            if cur is not None and cur.title.upper() == core:
                continue
            open_section(title_case(core))
            continue

        # -- atomic comparison / house-placement entry ----------------------
        if ENTRY_RE.match(s) or HOUSE_ENTRY_RE.match(s):
            if cur is None:
                open_section("Entries")
            cur_entry = Entry(label=s)
            cur.entries.append(cur_entry)
            continue

        # -- generic all-caps section header (front matter, sign roles) ------
        if is_all_caps_title(s) and len(core) >= 4 and core not in ALWAYS_DROP_TITLES:
            if cur is not None and cur.title.upper() == core:
                continue                       # running head repeat
            open_section(title_case(core))
            continue

        # drop remaining always-drop running heads (with or without numbers)
        if core in ALWAYS_DROP_TITLES:
            continue

        # -- ordinary body text ---------------------------------------------
        body_target().append(raw)

    # drop empty sections produced by consecutive headers
    return [sec for sec in sections if not sec.is_empty()]


# --------------------------------------------------------------------------- #
# Chunk assembly + output
# --------------------------------------------------------------------------- #

BOOK = "Analyzing Human Relationships (Sakoian & Acker) — Horoscopic Comparison"


def part_for(chapter: str) -> str:
    return ("Comparative Influences of the Planets"
            if chapter in PLANETS else
            "Basic Concepts in Horoscopic Comparison")


def slug(*parts: str) -> str:
    s = "_".join(parts).lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")[:80]


def render_chunk_header(chapter: str, section: str, entry: str | None = None) -> str:
    lines = [
        f"[Book]    {BOOK}",
        f"[Part]    {part_for(chapter)}",
        f"[Chapter] {chapter}",
        f"[Section] {section}",
    ]
    if entry:
        lines.append(f"[Entry]   {entry}")
    lines.append("-" * 60)
    return "\n".join(lines)


def build_chunks(sections: list[Section], granularity: str) -> list[dict]:
    chunks: list[dict] = []
    seq = 0

    for sec in sections:
        if granularity == "entry":
            # subsection intro becomes its own context chunk (if any)
            if sec.intro_text():
                seq += 1
                chunks.append(_mk(seq, sec.chapter, sec.title, None,
                                  sec.intro_text()))
            for ent in sec.entries:
                body = ent.text()
                if not body and not ent.label:
                    continue
                seq += 1
                text = f"{ent.label}\n{body}".strip()
                chunks.append(_mk(seq, sec.chapter, sec.title, ent.label, text,
                                  n_entries=1))
        else:  # granularity == "subsection"
            parts: list[str] = []
            intro = sec.intro_text()
            if intro:
                parts.append(intro)
            for ent in sec.entries:
                block = ent.label
                body = ent.text()
                if body:
                    block += "\n" + body
                parts.append(block)
            body_text = "\n\n".join(parts).strip()
            if not body_text:
                continue
            seq += 1
            chunks.append(_mk(seq, sec.chapter, sec.title, None, body_text,
                              n_entries=len(sec.entries)))
    return chunks


def _mk(seq, chapter, section, entry, body, n_entries=0) -> dict:
    header = render_chunk_header(chapter, section, entry)
    full = header + "\n" + body + "\n"
    name = slug(f"{seq:04d}", chapter, section, entry or "")
    return {
        "id": f"{seq:04d}",
        "seq": seq,
        "book": BOOK,
        "part": part_for(chapter),
        "chapter": chapter,
        "section": section,
        "entry": entry,
        "n_entries": n_entries,
        "char_count": len(body),
        "word_count": len(body.split()),
        "file": f"chunks/{name}.txt",
        "text": full,
    }


def write_outputs(chunks: list[dict], outdir: Path) -> None:
    chunks_dir = outdir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    # clear stale chunk files from a previous run
    for old in chunks_dir.glob("*.txt"):
        old.unlink()

    for c in chunks:
        (outdir / c["file"]).write_text(c["text"], encoding="utf-8")

    manifest = [{k: v for k, v in c.items() if k != "text"} for c in chunks]
    (outdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    with (outdir / "chunks.jsonl").open("w", encoding="utf-8") as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    default_input = here.parent / "TXT" / "Relationships.txt"

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", type=Path, default=default_input,
                    help=f"path to Relationships.txt (default: {default_input})")
    ap.add_argument("--outdir", type=Path, default=here / "relationships_chunks",
                    help="output directory (default: ./relationships_chunks)")
    ap.add_argument("--granularity", choices=["subsection", "entry"],
                    default="subsection",
                    help="chunk size: one file per subsection (default) or per "
                         "atomic principle entry")
    args = ap.parse_args(argv)

    if not args.input.exists():
        print(f"ERROR: input not found: {args.input}", file=sys.stderr)
        return 1

    text = args.input.read_text(encoding="utf-8", errors="replace")
    sections = parse(text)
    chunks = build_chunks(sections, args.granularity)
    write_outputs(chunks, args.outdir)

    # summary
    total_words = sum(c["word_count"] for c in chunks)
    chapters = {}
    for c in chunks:
        chapters.setdefault(c["chapter"], 0)
        chapters[c["chapter"]] += 1

    print(f"Parsed  : {args.input}")
    print(f"Sections: {len(sections)}")
    print(f"Chunks  : {len(chunks)}  (granularity={args.granularity})")
    print(f"Words   : {total_words:,}")
    print(f"Output  : {args.outdir}")
    print(f"           - chunks/*.txt")
    print(f"           - manifest.json")
    print(f"           - chunks.jsonl")
    print("\nChunks per chapter:")
    order = ["Basic Concepts"] + PLANETS
    for ch in order + [c for c in chapters if c not in order]:
        if ch in chapters:
            print(f"  {ch:16s} {chapters[ch]:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
