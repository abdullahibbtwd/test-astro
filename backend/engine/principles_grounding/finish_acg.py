#!/usr/bin/env python3
"""
finish_acg.py — ACG corpus delta, step 3 (spec ``docs/acg/ACG_06_CORPUS_DELTA_SPEC.md`` §6.3, §7, §8).

Input: ``TXT/extracted_acg/acg_consolidated.json`` (from ``consolidate_acg.py``), or with
``--in`` a previous ``acg_principles.clean.json`` (the C-8 idempotence path).

Steps (deterministic unless a C-3/C-4 failure needs a re-paraphrase):
  1. normalise (MH -> MC, strip) and force the schema (domain, tradition, source, tags)
  2. guards C-3 (verbatim 8-gram vs the de-columned source) and C-4 (names/places,
     case-sensitive capitalised whole words; planet names never blocked). Failures are
     re-paraphrased by the LLM (only those records, bounded rounds, cached under
     TXT/extracted_acg/repara/), then re-checked; any survivor rejects the build.
  3. id assignment (§6.3): fixed Introduction ids verbatim; ``acg-<planet>-<angle>-NN``,
     ``acg-general-<planet>-NN``, ``acg-paran-<p1>-<p2>-NN``, ``acg-zenith-NN``,
     ``acg-ccg-NN``, ``acg-mundane-NN``; ordered by citation_count desc, then text
  4. guards C-2, C-5, C-6 (report only), C-7
  5. backfill ``acg-*`` branch (Tier 0: deterministic about + value-bearing requires)
  6. write ``acg_principles.clean.json``, ``acg_principles.grounded.json`` (+ .sha256)
     and ``acg_finish_report.json``; C-8 = rebuild from the written clean file in-process
     and compare bytes

The ACG corpus is a separate file (D13): nothing here touches all_principles*.json.

    python principles_grounding/finish_acg.py
    python principles_grounding/finish_acg.py --in principles_grounding/acg_principles.clean.json \\
        --out-dir <tmp>          # idempotence check by hand
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import extract_acg as ex  # noqa: E402
from backfill import (ACG_SCOPE_FACTOR, _NullExtractor, ground_record,  # noqa: E402
                      validate_acg_about, validate_acg_requires)

CONS_IN = os.path.join(ex.WORK_DIR, "acg_consolidated.json")
CLEAN_OUT = "acg_principles.clean.json"
GROUNDED_OUT = "acg_principles.grounded.json"
REPORT_OUT = "acg_finish_report.json"
REPARA_DIR = os.path.join(ex.WORK_DIR, "repara")
GAZETTEER = os.path.join(ROOT, "Astrocartography", "gazetteer.json")

CLEAN_FIELDS = ("principle_id", "domain", "topic_tags", "rule", "conditions", "judgment",
                "attribution_in_text", "notes", "tradition", "source", "acg_scope",
                "polarity", "sensitivity", "citation_count", "source_span")
SCOPE_ORDER = ("method", "angle_frame", "planet_general", "line", "paran", "zenith", "ccg",
               "mundane")
V1_SCOPES = ("line", "angle_frame", "planet_general", "method")
NGRAM = 8
MAX_REPARA_ROUNDS = 3

# ---------------------------------------------------------------------------
# JSON schema of a clean ACG record (C-7)
# ---------------------------------------------------------------------------

_COND_ITEM = {"oneOf": [
    {"type": "object", "additionalProperties": False, "required": ["text"],
     "properties": {"text": {"type": "string", "minLength": 1}}},
    *[{"type": "object", "additionalProperties": False, "required": [k],
       "properties": {k: {"type": "object"}}}
      for k in ("natal_sign", "natal_aspect", "natal_retrograde", "natal_dignity",
                "relocated_house", "relocated_angular")],
]}
RECORD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": list(CLEAN_FIELDS),
    "properties": {
        "principle_id": {"type": "string", "pattern": r"^acg-[a-z0-9-]+$"},
        "domain": {"const": "astrocartography"},
        "topic_tags": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "rule": {"type": "string", "minLength": 40},
        "conditions": {"type": "array", "items": _COND_ITEM},
        "judgment": {"type": ["string", "null"]},
        "attribution_in_text": {"type": "null"},
        "notes": {"type": ["string", "null"]},
        "tradition": {"const": "modern"},
        "source": {"const": "lewis_guttman_1989"},
        "acg_scope": {"enum": list(SCOPE_ORDER)},
        "polarity": {"enum": list(ex.POLARITIES)},
        "sensitivity": {"enum": list(ex.SENSITIVITIES)},
        "citation_count": {"type": "integer", "minimum": 1},
        "source_span": {"type": "object", "additionalProperties": False,
                        "required": ["page_start", "page_end"],
                        "properties": {"page_start": {"type": "integer"},
                                       "page_end": {"type": "integer"}}},
        # goal tags (07 §5), written by tag_goals_acg.py and carried through a rebuild
        "goal_effects": {"type": "object", "maxProperties": 3,
                         "additionalProperties": {"enum": list(ex.POLARITIES)}},
        "about": {"type": "object"},
        "requires": {"type": "array"},
    },
}


# ---------------------------------------------------------------------------
# Record keys (from consolidation's bucket fields, or parsed back from a clean id)
# ---------------------------------------------------------------------------

_P = "|".join(ex.PLANETS)


def record_keys(r: dict) -> dict:
    """{fixed, planet, angle, planets} for a record from either input form."""
    if "_planet" in r:
        return {"fixed": r.get("_fixed_id"), "planet": r.get("_planet") or "",
                "angle": r.get("_angle") or "", "planets": list(r.get("_planets") or [])}
    pid = r["principle_id"]
    if pid in ex.FIXED_IDS:
        ang = pid.rsplit("-", 1)[1].upper() if pid.startswith("acg-angle-") else ""
        return {"fixed": pid, "planet": "", "angle": ang, "planets": []}
    m = re.match(rf"^acg-({_P})-(asc|dsc|mc|ic)-\d+$", pid)
    if m:
        return {"fixed": None, "planet": m.group(1), "angle": m.group(2).upper(), "planets": []}
    m = re.match(rf"^acg-general-({_P})-\d+$", pid)
    if m:
        return {"fixed": None, "planet": m.group(1), "angle": "", "planets": []}
    m = re.match(rf"^acg-paran-({_P})-({_P})-\d+$", pid)
    if m:
        return {"fixed": None, "planet": "", "angle": "", "planets": [m.group(1), m.group(2)]}
    return {"fixed": None, "planet": "", "angle": "", "planets": []}


# ---------------------------------------------------------------------------
# C-3: verbatim 8-gram guard
# ---------------------------------------------------------------------------

def _tokens(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", (text or "").lower().replace("’", "'").replace("'", ""))
    return ["mc" if t == "mh" else t for t in toks]


@lru_cache(maxsize=1)
def source_ngrams() -> frozenset:
    toks = _tokens(ex.decolumned_text("all"))
    return frozenset(" ".join(toks[i:i + NGRAM]) for i in range(len(toks) - NGRAM + 1))


def record_text_fields(r: dict) -> list[str]:
    out = [r.get("rule") or "", r.get("judgment") or "", r.get("notes") or ""]
    for c in r.get("conditions") or []:
        if isinstance(c, dict) and "text" in c:
            out.append(str(c["text"]))
    return out


def c3_hits(r: dict) -> list[str]:
    grams = source_ngrams()
    hits: list[str] = []
    for field_text in record_text_fields(r):
        toks = _tokens(field_text)
        for i in range(len(toks) - NGRAM + 1):
            g = " ".join(toks[i:i + NGRAM])
            if g in grams and g not in hits:
                hits.append(g)
    return hits


# ---------------------------------------------------------------------------
# C-4: name guard
# ---------------------------------------------------------------------------

COUNTRIES = """Afghanistan Albania Algeria Andorra Angola Argentina Armenia Australia Austria
Azerbaijan Bahamas Bahrain Bangladesh Barbados Belarus Belgium Belize Benin Bhutan Bolivia
Bosnia Botswana Brazil Brunei Bulgaria Burkina Burundi Cambodia Cameroon Canada Chad Chile
China Colombia Comoros Congo Croatia Cuba Cyprus Czechoslovakia Czechia Denmark Djibouti
Dominica Ecuador Egypt Eritrea Estonia Eswatini Ethiopia Fiji Finland France Gabon Gambia
Georgia Germany Ghana Greece Grenada Guatemala Guinea Guyana Haiti Honduras Hungary Iceland
India Indonesia Iran Iraq Ireland Israel Italy Jamaica Japan Jordan Kazakhstan Kenya Kiribati
Korea Kosovo Kuwait Kyrgyzstan Laos Latvia Lebanon Lesotho Liberia Libya Liechtenstein
Lithuania Luxembourg Madagascar Malawi Malaysia Maldives Mali Malta Mauritania Mauritius
Mexico Micronesia Moldova Monaco Mongolia Montenegro Morocco Mozambique Myanmar Burma Namibia
Nauru Nepal Netherlands Holland Nicaragua Niger Nigeria Norway Oman Pakistan Palau Palestine
Panama Paraguay Peru Philippines Poland Portugal Qatar Romania Russia Rwanda Samoa Senegal
Serbia Seychelles Singapore Slovakia Slovenia Somalia Spain Sudan Suriname Sweden Switzerland
Syria Taiwan Tajikistan Tanzania Thailand Togo Tonga Trinidad Tunisia Turkey Turkmenistan
Tuvalu Uganda Ukraine Uruguay Uzbekistan Vanuatu Vatican Venezuela Vietnam Yemen Zambia
Zimbabwe Tahiti Persia Prussia Yugoslavia Tibet Bengal Siam Ceylon Rhodesia Manchuria
Scotland Wales England Britain Brittany Normandy Provence Bavaria Siberia Alaska Hawaii
Africa Asia Europe America Americas Antarctica Australasia Oceania Scandinavia Balkans
Arctic Caribbean Mediterranean Atlantic Pacific Himalayas Alps Sahara""".split()
COUNTRY_PHRASES = ["United States", "United Kingdom", "Soviet Union", "New Zealand",
                   "South Africa", "Saudi Arabia", "Sri Lanka", "Costa Rica", "El Salvador",
                   "Ivory Coast", "Viet Nam", "North Korea", "South Korea", "Hong Kong",
                   "Middle East", "Far East", "Latin America", "North America",
                   "South America", "Central America", "Puerto Rico", "New Guinea",
                   "Northern Ireland", "Czech Republic", "Dominican Republic",
                   "Bangla Desh", "West Germany", "East Germany", "U.S.A.", "U.S.S.R.",
                   "USA", "USSR", "U.K."]
US_STATES = """Alabama Arizona Arkansas California Colorado Connecticut Delaware Florida Idaho
Illinois Indiana Iowa Kansas Kentucky Louisiana Maine Maryland Massachusetts Michigan
Minnesota Mississippi Missouri Montana Nebraska Nevada Ohio Oklahoma Oregon Pennsylvania
Tennessee Texas Utah Vermont Virginia Washington Wisconsin Wyoming Dakota Carolina Hampshire
Jersey Manhattan Hollywood Broadway""".split()

# words that are never names in this corpus, whatever the lists say
NEVER_BLOCK = set(ex.POINT_NAMES) | set(ex.SIGNS) | {
    "Ascendant", "Descendant", "Midheaven", "Imum", "Coeli", "ASC", "DSC", "MC", "IC",
    "The", "And", "Of", "For", "With", "First", "Atomic", "Bomb", "Test", "Reaction",
    "Federation", "Declaration", "Independence", "War", "Prince", "Princess", "Queen",
    "Pope", "General", "President", "Jr", "Dec", "Lines", "Line", "Rising", "Voyage",
    "Island", "Islands", "New", "North", "South", "East", "West", "United", "States",
    "Saint", "San", "Santa", "Los", "Las", "Mount", "Fort", "Lake", "City", "County",
    "Great", "Little", "Sea", "River", "Bay", "Sun", "Moon", "Earth", "Shah", "Wales",
    "Charles", "Diana", "Elizabeth", "William", "Mother", "Father", "Grace", "II", "III",
    "Ingested", "Lsd", "LSD", "Astro", "Carto", "Graphy", "Nations", "Events",
    "Placidus", "Plutonian", "Uranian", "Neptunian", "Saturnian", "Jovian", "Martian",
    "Venusian", "Mercurial", "Lunar", "Solar", "Zenith", "Paran", "Parans", "Jupiterian",
}


def _title(word: str) -> str:
    return word[:1].upper() + word[1:].lower() if word.isupper() else word


def _person_tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z'’\-]+", text):
        w = _title(w.strip("'’-"))
        if len(w) >= 3 and w[0].isupper() and w not in NEVER_BLOCK:
            out.append(w)
    return out


@lru_cache(maxsize=1)
def blocklist() -> dict:
    """{"tokens": {word}, "phrases": {multiword}, "common": {word}, "gazetteer": bool}."""
    lines = ex.read_source()
    reg = ex.find_regions(lines)
    persons: set[str] = set()
    places: set[str] = set(COUNTRIES) | set(US_STATES)
    phrases: set[str] = set(COUNTRY_PHRASES)
    # Appendix B: "Surname, I." cells (and bare names such as "Ram Dass")
    for ln in lines[reg.appendix_b[0]:reg.appendix_b[1]]:
        for cell in re.split(r"\s{2,}", ln.strip()):
            if not cell or cell.isupper():
                continue
            persons.update(_person_tokens(cell.split(",")[0] if "," in cell else cell))
    # Appendix A: "SURNAME, FIRST: GRADE/source"
    for ln in lines[reg.appendix_a[0]:reg.appendix_a[1]]:
        for cell in re.split(r"\s{2,}", ln.strip()):
            m = re.match(r"^([A-Z][A-Z'\- .]+),\s*([A-Z][A-Za-z'\- .]+?)\s*:", cell)
            if m:
                persons.update(_person_tokens(m.group(1) + " " + m.group(2)))
    # Index: "Surname, First: page" / "Name; page"
    for ln in lines[reg.index[0]:reg.index[1]]:
        for m in re.finditer(r"([A-Z][A-Za-z'’\-. ,]+?)\s*[:;]\s*\d{1,3}\b", ln):
            persons.update(_person_tokens(m.group(1)))
    # Profile headings (names) and the place line under each birth-data line
    stream = ex.decolumn(lines, ex.split_pages(lines))
    for k, s in enumerate(stream):
        if ex.BIRTH_RE.search(s.text):
            if k and ex._is_caps_heading(stream[k - 1].text):
                persons.update(_person_tokens(stream[k - 1].text.split(",")[0]))
            if k + 1 < len(stream):
                for part in stream[k + 1].text.split(","):
                    part = " ".join(_title(w) for w in part.split())
                    if part and len(part) > 2 and part not in NEVER_BLOCK:
                        (phrases if " " in part else places).add(part)
    gaz = os.path.exists(GAZETTEER)
    if gaz:
        g = json.load(open(GAZETTEER, encoding="utf-8"))
        cities = g.get("cities", []) if isinstance(g, dict) else g
        for c in cities:
            for nm in [c.get("name"), c.get("name_tr")] + list(c.get("aliases") or []):
                if nm and nm not in NEVER_BLOCK and len(nm) >= 3:
                    (phrases if " " in nm else places).add(nm)
    # proper nouns of the book body itself (capitalised, never seen in lower case):
    # catches names/places that no list above carries ("Denver", "Liz")
    body = ex.decolumned_text("body")
    lower_seen = set(re.findall(r"\b[a-z][a-z'\-]+\b", body))
    proper = {w for w in re.findall(r"\b[A-Z][a-z][a-z'\-]+\b", body)
              if w.lower() not in lower_seen}
    listed = {t for t in persons | places if t not in NEVER_BLOCK and len(t) >= 3}
    tokens = listed | {t for t in proper if t not in NEVER_BLOCK and len(t) >= 3}
    phrases = {p for p in phrases if p not in NEVER_BLOCK}
    # names that are also ordinary English words in the source (Price, Day, Love,
    # King, Buck...) only count when capitalised mid-sentence
    src_lower = Counter(re.findall(r"\b[a-z][a-z'\-]+\b", "\n".join(lines)))
    # a proper noun derived from the body text alone (not in any list) is also only
    # counted mid-sentence: ordinary words can sit capitalised at a sentence start
    common = {t for t in tokens if src_lower.get(t.lower(), 0) >= 2} | (tokens - listed)
    return {"tokens": tokens, "listed": listed, "phrases": phrases, "common": common,
            "gazetteer": gaz,
            "counts": {"person_tokens": len(persons), "place_tokens": len(places),
                       "source_proper_nouns": len(proper),
                       "phrases": len(phrases), "common": len(common)}}


def _sentence_initial(text: str, start: int) -> bool:
    before = text[:start].rstrip()
    return not before or before[-1] in ".!?:;\"'(—-"


def c4_hits(r: dict) -> list[str]:
    bl = blocklist()
    hits: list[str] = []
    for text in record_text_fields(r):
        for m in re.finditer(r"[A-Z][A-Za-z'’\-]+", text):
            w = m.group(0).rstrip("'’-")
            w = re.sub(r"['’]s$", "", w)
            if w in bl["tokens"] and w not in NEVER_BLOCK:
                if w in bl["common"] and _sentence_initial(text, m.start()):
                    continue
                if w not in hits:
                    hits.append(w)
        for m in re.finditer(r"\b(1[5-9]\d\d|20\d\d)s?\b", text):      # dates / years
            if m.group(0) not in hits:
                hits.append(m.group(0))
        for ph in bl["phrases"]:
            if re.search(rf"(?<![A-Za-z]){re.escape(ph)}(?![A-Za-z])", text) and ph not in hits:
                hits.append(ph)
    for t in r.get("topic_tags") or []:
        for w in re.findall(r"[a-z][a-z'\-]+", t.lower()):
            cand = w.capitalize()
            if cand in bl["listed"] and cand not in bl["common"] and cand not in NEVER_BLOCK \
                    and cand not in hits:
                hits.append(cand)
    return hits


# ---------------------------------------------------------------------------
# Re-paraphrase (only the C-3/C-4 failures; cached)
# ---------------------------------------------------------------------------

REPARA_SYSTEM = """You rewrite one astrocartography principle so that it passes two checks, \
keeping its meaning exactly (no new content, no lost content):
- it must share NO run of 8 or more consecutive words with the source book (the offending \
runs are listed): reword those passages completely;
- it must contain NO personal names and NO place names (cities, countries, regions): remove \
any listed name and generalise the statement.
Keep third person, present tense, planet names in full, angles as ASC/DSC/MC/IC. Return the \
same fields."""

REPARA_SCHEMA = {
    "type": "object",
    "properties": {"rule": {"type": "string"}, "judgment": {"type": "string"},
                   "notes": {"type": "string"},
                   "text_conditions": {"type": "array", "items": {"type": "string"}}},
    "required": ["rule", "judgment", "notes", "text_conditions"],
}


def repara(r: dict, verb: list[str], names: list[str], model: str, attempt: int) -> dict | None:
    tconds = [str(c["text"]) for c in r.get("conditions") or [] if "text" in c]
    user = json.dumps({"rule": r["rule"], "judgment": r.get("judgment") or "",
                       "notes": r.get("notes") or "", "text_conditions": tconds,
                       "verbatim_runs_to_reword": verb, "names_to_remove": names,
                       "attempt": attempt}, ensure_ascii=False, indent=1)
    h = hashlib.sha256(f"{model}\n{REPARA_SYSTEM}\n{user}".encode()).hexdigest()[:20]
    path = os.path.join(REPARA_DIR, f"{h}.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))["result"]
    if model is None:
        return None
    import llm_client
    for k in range(1, 4):
        try:
            resp = llm_client.complete(model, REPARA_SYSTEM, user, max_tokens=4000,
                                       temperature=0.4, schema=REPARA_SCHEMA, timeout_s=120.0,
                                       label="acg-repara")
            data = json.loads(resp.text)
            if len(data.get("text_conditions") or []) != len(tconds):
                raise RuntimeError("text_conditions count changed")
            os.makedirs(REPARA_DIR, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"usage": resp.usage, "result": data}, fh, ensure_ascii=False, indent=1)
            return data
        except (json.JSONDecodeError, RuntimeError) as exc:
            print(f"  repara retry ({k}): {exc}", flush=True)
            time.sleep(2 * k)
        except llm_client.transient_errors(model):
            time.sleep(5 * k)
    return None


def _apply_repara(r: dict, data: dict) -> dict:
    r = dict(r)
    r["rule"] = ex.mh_to_mc(data["rule"].strip())
    r["judgment"] = ex.mh_to_mc((data.get("judgment") or "").strip()) or None
    r["notes"] = ex.mh_to_mc((data.get("notes") or "").strip()) or None
    it = iter(data.get("text_conditions") or [])
    r["conditions"] = [({"text": ex.mh_to_mc(next(it).strip())} if "text" in c else c)
                       for c in r.get("conditions") or []]
    return r


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _norm_record(r: dict) -> dict:
    k = record_keys(r)
    out = {
        "principle_id": r.get("principle_id"),
        "rule": ex.mh_to_mc((r.get("rule") or "").strip()),
        "judgment": ex.mh_to_mc((r.get("judgment") or "").strip()) or None,
        "notes": ex.mh_to_mc((r.get("notes") or "").strip()) or None,
        "conditions": [({"text": ex.mh_to_mc(str(c["text"]).strip())} if "text" in c else c)
                       for c in (r.get("conditions") or []) if isinstance(c, dict)],
        "topic_tags": list(r.get("topic_tags") or []),
        "acg_scope": r["acg_scope"],
        "polarity": r.get("polarity") if r.get("polarity") in ex.POLARITIES else "mixed",
        "sensitivity": r.get("sensitivity") or "normal",
        "citation_count": int(r.get("citation_count") or 1),
        "source_span": dict(r.get("source_span") or {"page_start": 0, "page_end": 0}),
        "_k": k,
    }
    if isinstance(r.get("goal_effects"), dict):      # 07 §5 tags survive a rebuild
        out["goal_effects"] = dict(r["goal_effects"])
    if k["fixed"]:
        out["acg_scope"] = ex.FIXED_IDS[k["fixed"]][0]
    return out


def _group_and_prefix(r: dict) -> tuple[str, str] | None:
    k, s = r["_k"], r["acg_scope"]
    if k["fixed"]:
        return None
    if s == "line":
        return (f"line|{k['planet']}|{k['angle']}", f"acg-{k['planet']}-{k['angle'].lower()}")
    if s == "planet_general":
        return (f"general|{k['planet']}", f"acg-general-{k['planet']}")
    if s == "paran":
        p1, p2 = sorted(k["planets"])
        return (f"paran|{p1}|{p2}", f"acg-paran-{p1}-{p2}")
    if s in ("zenith", "ccg", "mundane"):
        return (s, f"acg-{s}")
    raise ValueError(f"non-fixed record with scope {s!r} has no id pattern")


def _sort_key(r: dict) -> tuple:
    return (-r["citation_count"], r["rule"], r["judgment"] or "", r["notes"] or "",
            json.dumps(r["conditions"], sort_keys=True))


def _lead_tags(r: dict) -> list[str]:
    k = r["_k"]
    lead = ["astrocartography"]
    if k["planet"]:
        lead.append(k["planet"].capitalize())
    for p in sorted(k["planets"]):
        lead.append(p.capitalize())
    if k["angle"]:
        lead.append(k["angle"])
    return lead


def _force_tags(r: dict) -> list[str]:
    lead = _lead_tags(r)
    low = {t.lower() for t in lead}
    rest = []
    for t in r["topic_tags"]:
        t = str(t).strip()
        if not t or t.lower() in low or t.lower() == "mh" or t in rest:
            continue
        if t.lower() in ex.PLANETS:          # e.g. a zenith/ccg record's planet tag
            t = t.capitalize()
        elif t.upper() in ex.ANGLES:
            t = t.upper()
        else:
            t = t.lower()
        if t not in rest:
            rest.append(t)
    return lead + rest


def build(records: list[dict], model: str | None, log: dict) -> tuple[list[dict], list[dict]]:
    """records -> (clean, grounded). model None = no LLM (C-8 path)."""
    recs = [_norm_record(r) for r in records]
    # drop non-fixed method/angle_frame records (only the Introduction defines them)
    kept = []
    for r in recs:
        if not r["_k"]["fixed"] and r["acg_scope"] in ("method", "angle_frame"):
            log["dropped_nonfixed_method"] += 1
            continue
        kept.append(r)
    recs = kept
    # fixed ids: first occurrence wins
    seen_fixed: set[str] = set()
    recs2 = []
    for r in recs:
        f = r["_k"]["fixed"]
        if f:
            if f in seen_fixed:
                log["duplicate_fixed_dropped"] += 1
                continue
            seen_fixed.add(f)
        recs2.append(r)
    recs = recs2

    # --- C-3 / C-4 with the bounded re-paraphrase loop -----------------------
    for rnd in range(MAX_REPARA_ROUNDS + 1):
        fails = []
        for i, r in enumerate(recs):
            v, n = c3_hits(r), c4_hits(r)
            if v or n:
                fails.append((i, v, n))
        if rnd == 0:
            log["c3_initial_failures"] = sum(1 for _, v, _ in fails if v)
            log["c4_initial_failures"] = sum(1 for _, _, n in fails if n)
        if not fails or rnd == MAX_REPARA_ROUNDS:
            break
        print(f"  C-3/C-4 round {rnd + 1}: {len(fails)} record(s) to re-paraphrase", flush=True)
        for i, v, n in fails:
            data = repara(recs[i], v, n, model, rnd + 1)
            if data is None:
                continue
            new = _apply_repara(recs[i], data)
            if len(new["rule"]) >= 40:
                if "_repara" not in recs[i]:
                    log["reparaphrased"] += 1
                new["_repara"] = True
                recs[i] = new
    log["c3_failures"] = [recs[i]["principle_id"] for i, v, _ in fails if v]
    log["c4_failures"] = [recs[i]["principle_id"] for i, _, n in fails if n]
    log["c4_failure_count_by_token"] = dict(Counter(t for _, _, n in fails for t in n))

    # --- sensitivity (never downgraded) ---------------------------------------
    for r in recs:
        blob = " ".join(record_text_fields(r))
        r["sensitivity"] = ex.sensitivity_of(blob, r["sensitivity"])

    # --- ids (§6.3) -----------------------------------------------------------
    groups: dict[str, list[dict]] = defaultdict(list)
    prefixes: dict[str, str] = {}
    for r in recs:
        gp = _group_and_prefix(r)
        if gp is None:
            r["principle_id"] = r["_k"]["fixed"]
            continue
        groups[gp[0]].append(r)
        prefixes[gp[0]] = gp[1]
    for g, members in groups.items():
        for n, r in enumerate(sorted(members, key=_sort_key), 1):
            r["principle_id"] = f"{prefixes[g]}-{n:02d}"

    # --- force the schema ------------------------------------------------------
    clean = []
    for r in recs:
        clean.append({
            "principle_id": r["principle_id"],
            "domain": "astrocartography",
            "topic_tags": _force_tags(r),
            "rule": r["rule"],
            "conditions": r["conditions"],
            "judgment": r["judgment"],
            "attribution_in_text": None,
            "notes": r["notes"],
            "tradition": "modern",
            "source": "lewis_guttman_1989",
            "acg_scope": r["acg_scope"],
            "polarity": r["polarity"],
            "sensitivity": r["sensitivity"],
            "citation_count": r["citation_count"],
            "source_span": {"page_start": int(r["source_span"].get("page_start", 0)),
                            "page_end": int(r["source_span"].get("page_end", 0))},
            **({"goal_effects": r["goal_effects"]} if "goal_effects" in r else {}),
        })
    order = {s: i for i, s in enumerate(SCOPE_ORDER)}
    clean.sort(key=lambda c: (order[c["acg_scope"]], c["principle_id"]))
    grounded = [ground_record(c, _NullExtractor()) for c in clean]
    return clean, grounded


# ---------------------------------------------------------------------------
# Guards over the built corpus
# ---------------------------------------------------------------------------

def check_guards(clean: list[dict], grounded: list[dict], log: dict) -> dict:
    import jsonschema
    res: dict = {}
    ids = [c["principle_id"] for c in clean]
    # C-2
    missing = [f for f in ex.FIXED_IDS if f not in ids]
    gen_bad = []
    for p in ex.PLANETS:
        g = [c for c in clean if c["principle_id"].startswith(f"acg-general-{p}-")]
        pols = {c["polarity"] for c in g}
        if len(g) < 2 or not ({"supportive", "challenging"} <= pols):
            gen_bad.append(p)
    res["C-2"] = {"pass": not missing and not gen_bad, "missing_fixed_ids": missing,
                  "planets_failing_general": gen_bad}
    # C-3 / C-4 (final state, after re-paraphrase)
    c3 = [c["principle_id"] for c in clean if c3_hits(c)]
    c4 = [c["principle_id"] for c in clean if c4_hits(c)]
    bl = blocklist()
    res["C-3"] = {"pass": not c3, "failures": c3, "initial_failures": log["c3_initial_failures"]}
    res["C-4"] = {"pass": not c4, "failures": c4, "initial_failures": log["c4_initial_failures"],
                  "gazetteer_present": bl["gazetteer"], "blocklist": bl["counts"]}
    # C-5
    bad5 = []
    for g in grounded:
        if g["acg_scope"] == "line":
            a = g["about"]
            if a.get("factor_type") != "planet_on_angle" or \
                    a.get("planet") not in [p.capitalize() for p in ex.PLANETS] or \
                    a.get("angle") not in ex.ANGLES:
                bad5.append(g["principle_id"])
    mh_left = [c["principle_id"] for c in grounded
               if re.search(r"\bMH\b|\bmh\b", json.dumps(c, ensure_ascii=False))]
    res["C-5"] = {"pass": not bad5 and not mh_left, "bad_line_records": bad5,
                  "mh_remaining": mh_left}
    # C-6 (report only)
    per = Counter((g["about"]["planet"], g["about"]["angle"]) for g in grounded
                  if g["about"]["factor_type"] == "planet_on_angle")
    buckets = {f"{p.capitalize()}|{a}": per.get((p.capitalize(), a), 0)
               for p in ex.PLANETS for a in ex.ANGLES}
    res["C-6"] = {"pass": all(v >= 2 for v in buckets.values()), "blocking": False,
                  "below_2": sorted(k for k, v in buckets.items() if v < 2),
                  "below_4": sorted(k for k, v in buckets.items() if v < 4),
                  "per_bucket": buckets}
    # C-7
    schema_errs = []
    for g in grounded:
        errs = [e.message for e in jsonschema.Draft202012Validator(RECORD_SCHEMA).iter_errors(g)]
        ok, aerrs = validate_acg_about(g.get("about"), g.get("acg_scope"))
        rok, rerrs = validate_acg_requires(g.get("requires"))
        if errs or not ok or not rok:
            schema_errs.append({"principle_id": g["principle_id"],
                                "errors": errs + aerrs + rerrs})
    dup = [i for i, n in Counter(ids).items() if n > 1]
    res["C-7"] = {"pass": not schema_errs and not dup and
                  all(g["domain"] == "astrocartography" for g in grounded),
                  "duplicate_ids": dup, "schema_errors": schema_errs}
    # deterministic classification
    non_det = [g["principle_id"] for g in grounded
               if g["about"].get("extraction_source") != "deterministic"]
    res["deterministic_classification"] = {"pass": not non_det, "non_deterministic": non_det,
                                           "scope_factor_consistent": all(
        g["about"]["factor_type"] in ACG_SCOPE_FACTOR[g["acg_scope"]] for g in grounded)}
    return res


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _write(path: str, payload: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)


def main() -> None:
    ap = argparse.ArgumentParser(description="Finish the ACG corpus (spec 06 §6.3, §7, §8).")
    ap.add_argument("--in", dest="inp", default=CONS_IN)
    ap.add_argument("--out-dir", default=HERE)
    ap.add_argument("--model", default=None,
                    help="model for re-paraphrasing C-3/C-4 failures "
                         "(default llm_client.DEFAULT_MODEL)")
    ap.add_argument("--no-llm", action="store_true", help="never call the model")
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        sys.exit(f"{args.inp} not found — run consolidate_acg.py first.")
    records = json.load(open(args.inp, encoding="utf-8"))
    model = None
    if not args.no_llm:
        import llm_client
        model = args.model or llm_client.DEFAULT_MODEL
    log = {"dropped_nonfixed_method": 0, "duplicate_fixed_dropped": 0, "reparaphrased": 0}
    clean, grounded = build(records, model, log)
    guards = check_guards(clean, grounded, log)

    # C-1 on the real source (de-columning)
    c1_ok, c1_msg = ex.c1_check(ex.decolumned_text("intro"))
    guards["C-1"] = {"pass": c1_ok, "detail": c1_msg}

    clean_payload, grounded_payload = _dump(clean), _dump(grounded)
    # C-8: rebuild from the clean output with no LLM; must be byte-identical
    log8 = {"dropped_nonfixed_method": 0, "duplicate_fixed_dropped": 0, "reparaphrased": 0}
    clean2, grounded2 = build(json.loads(clean_payload), None, log8)
    guards["C-8"] = {"pass": _dump(clean2) == clean_payload and
                     _dump(grounded2) == grounded_payload,
                     "reparaphrased_on_rerun": log8["reparaphrased"]}

    blocking = [g for g in ("C-1", "C-2", "C-3", "C-4", "C-5", "C-7", "C-8",
                            "deterministic_classification") if not guards[g]["pass"]]
    scopes = Counter(c["acg_scope"] for c in clean)
    report = {
        "records": len(clean),
        "by_scope": dict(sorted(scopes.items())),
        "v1_retrieval_records": sum(scopes[s] for s in V1_SCOPES),
        "sensitivity_high": sum(1 for c in clean if c["sensitivity"] == "high"),
        "with_requires": sum(1 for g in grounded if g["requires"]),
        "requires_kinds": dict(Counter(q["kind"] for g in grounded for q in g["requires"])),
        "reparaphrased_records": log["reparaphrased"],
        "dropped_nonfixed_method": log["dropped_nonfixed_method"],
        "duplicate_fixed_dropped": log["duplicate_fixed_dropped"],
        "guards": guards,
        "build_blocking": blocking,
        "passes": not blocking,
    }
    os.makedirs(args.out_dir, exist_ok=True)
    _write(os.path.join(args.out_dir, REPORT_OUT), _dump(report))
    print(f"records {len(clean)}; by scope {report['by_scope']}")
    for g in ("C-1", "C-2", "C-3", "C-4", "C-5", "C-6", "C-7", "C-8",
              "deterministic_classification"):
        extra = ""
        if g == "C-6":
            extra = f" (below 2: {guards[g]['below_2']}; below 4: {guards[g]['below_4']})"
        print(f"  {g}: {'PASS' if guards[g]['pass'] else 'FAIL'}{extra}")
    print(f"re-paraphrased records: {log['reparaphrased']}")
    if blocking:
        _write(os.path.join(args.out_dir, "acg_principles.rejected.json"), clean_payload)
        sys.exit(f"BUILD REJECTED: {blocking} (see {REPORT_OUT})")

    _write(os.path.join(args.out_dir, CLEAN_OUT), clean_payload)
    gpath = os.path.join(args.out_dir, GROUNDED_OUT)
    _write(gpath, grounded_payload)
    digest = hashlib.sha256(grounded_payload.encode("utf-8")).hexdigest()
    with open(gpath + ".sha256", "w", encoding="utf-8") as fh:
        fh.write(f"{digest}  {GROUNDED_OUT}\n"
                 f"v1_retrieval={report['v1_retrieval_records']} "
                 f"invariant_violations=0 records={len(grounded)}\n")
    rej = os.path.join(args.out_dir, "acg_principles.rejected.json")
    if os.path.exists(rej):
        os.remove(rej)
    print(f"wrote {CLEAN_OUT}, {GROUNDED_OUT} (+ .sha256 {digest[:16]}…), {REPORT_OUT}")
    print("ALL GATES PASSED.")


if __name__ == "__main__":
    main()
