"""pa_dossier.py - the personal dossier: every grounded natal principle for one chart (PA_01 §2).

Deterministic, no model. Reuses the layers, never re-implements them:
  * natal grounding  = principles_grounding.ground.ground (as run.py calls it)
  * topic routing    = Interpretation_layer.l4_routing.route (records -> the 17 section keys)
  * record text      = the record's ``rule`` - the only prose the L4 renderer sends
                       (Phase 0 X2; the renderer's other fields are internal)
The 2:1 modern:classical quota of PA_01 §2.3 is implemented here (Phase 0 G1: not in L4 code).

Cached as ``ask_run/_cache/<chart_key>/dossier.json`` (schema ``pa-dossier-1``).
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Optional

import _paths  # noqa: F401
import pa_catalogue as C  # noqa: E402
import pa_constants as K  # noqa: E402
from ground import ground  # noqa: E402
from l4_routing import route  # noqa: E402

CORPUS_PATH = os.path.join(_paths.ROOT, "principles_grounding", "all_principles.grounded.json")
_ROUTING_FILES = [os.path.join(_paths.ROOT, "Interpretation_layer", f)
                  for f in ("l4_routing.py", "l4_sections.py")]

# goal -> natal topics (PA_01 §2.4)
GOAL_TOPICS = {
    "love": ["partnerships", "joy_creativity_children", "transformation_intimacy"],
    "career": ["status_vocation", "health_routine_pets", "identity"],
    "business": ["status_vocation", "values_money", "friendships_future"],
    "money": ["values_money", "transformation_intimacy"],
    "family": ["family_home", "joy_creativity_children"],
    "education": ["communication_learning", "travel_philosophy"],
    "creativity": ["joy_creativity_children", "identity"],
    "spirituality": ["subconscious_solitude", "travel_philosophy"],
    "rest": ["subconscious_solitude", "family_home"],
    "travel": ["travel_philosophy", "communication_learning"],
    "relocation": ["family_home", "travel_philosophy"],
}
PERSONALITY_TOPICS = ["core_identity", "inner_drives", "identity"]


def _sha_file(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def routing_version() -> str:
    h = hashlib.sha256()
    for p in _ROUTING_FILES:
        with open(p, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()[:16]


def _key(name: str) -> str:
    """Chart / corpus names -> catalogue keys ('North Node' -> 'north_node', 'Ascendant' -> 'asc')."""
    n = (name or "").strip().lower().replace(" ", "_")
    return {"ascendant": "asc", "midheaven": "mc", "descendant": "dsc"}.get(n, n)


# --- facts (FE_02 §7.2 mapping; masked fields never copied) -----------------------------------------
def chart_facts(chart: dict) -> dict:
    facts: dict = {}
    for p in chart["points"]:
        b = _key(p["name"])
        facts[f"f:natal:{b}"] = {"kind": "placement", "body": b, "sign": p["sign"].lower(),
                                 "house": (p.get("sector") or {}).get("placidus"),
                                 "retrograde": bool(p.get("retrograde"))}
    axes = chart.get("axes") or {}
    for a, k in (("ascendant", "asc"), ("mc", "mc")):
        if a in axes:
            facts[f"f:natal:{k}"] = {"kind": "angle", "angle": k, "sign": axes[a]["sign"].lower()}
    for h, blk in sorted(((chart.get("sector_rulers") or {}).get("placidus") or {}).items(), key=lambda x: int(x[0])):
        rulers = [_key(blk["ruler"])]
        mr = _key(blk.get("modern_ruler") or blk["ruler"])
        if mr not in rulers:
            rulers.append(mr)
        facts[f"f:natal:house:{int(h)}"] = {"kind": "house", "house": int(h),
                                           "sign": blk["sign_on_cusp"].lower(), "rulers": rulers}
    modern = [r for r in chart.get("relations", []) if r.get("scheme") == "modern"]
    for rank, r in enumerate(sorted(modern, key=lambda r: (r.get("orb", 99), r["source"], r["target"])), 1):
        a, b = _key(r["source"]), _key(r["target"])
        facts[f"f:natal:aspect:{a}|{b}|{r['type']}"] = {"kind": "aspect", "a": a, "b": b, "type": r["type"],
                                                         "rank": rank}
    return dict(sorted(facts.items()))


def fact_label(fact: dict, lang: str) -> str:
    k = fact["kind"]
    if k == "placement":
        return C.placement_label(fact["body"], fact["sign"], fact.get("house"), fact.get("retrograde"), lang)
    if k == "angle":
        return C.angle_label(fact["angle"], fact["sign"], lang)
    if k == "house":
        return C.house_label(fact["house"], fact["sign"], fact["rulers"], lang)
    return C.aspect_label(fact["a"], fact["b"], fact["type"], lang)


# --- bodies a record's factor involves ----------------------------------------------------------------
def _record_bodies(rec: dict) -> list[str]:
    a = rec.get("about") or {}
    out = []
    for v in (a.get("point"), (a.get("aspect") or {}).get("source"), (a.get("aspect") or {}).get("target")):
        if v:
            out.append(_key(v))
    if a.get("factor_type") == "ascendant":
        out.append("asc")
    return [b for b in dict.fromkeys(out) if b in C.BODIES or b in ("asc", "mc")]


def claims_of(about: dict) -> dict:
    """What a record's factor asserts, for the PV4 claim check (internal; never sent to the model):
    {"sign": [[body, sign]], "house": [[body, house]], "aspect": [[a, b, type]]}."""
    a = about or {}
    ft = a.get("factor_type")
    pt = _key(a.get("point") or "")
    out: dict = {"sign": [], "house": [], "aspect": []}
    if ft in ("planet_in_sign", "planet_in_sign_and_house", "node") and pt and a.get("sign"):
        out["sign"].append([pt, a["sign"].lower()])
    if ft in ("planet_in_house", "planet_in_sign_and_house", "node") and pt and a.get("house"):
        out["house"].append([pt, int(a["house"])])
    if ft == "aspect":
        asp = a.get("aspect") or {}
        if asp.get("source") and asp.get("target"):
            out["aspect"].append([_key(asp["source"]), _key(asp["target"]), asp.get("type")])
    if ft == "ascendant" and a.get("ascendant_sign"):
        out["sign"].append(["asc", a["ascendant_sign"].lower()])
    return out


_BODY_ORDER = {"planet_in_sign": 0, "node": 0, "planet_in_house": 1, "planet_in_sign_and_house": 1,
               "aspect": 2, "dignity": 3, "house_ruler": 4, "house_lord_relative": 4, "house_domain": 5}


def _body_sort_key(rec: dict, facts: dict) -> tuple:
    a = rec.get("about") or {}
    ft = a.get("factor_type")
    rank = 99
    if ft == "aspect":
        asp = a.get("aspect") or {}
        s, t = _key(asp.get("source")), _key(asp.get("target"))
        for key in (f"f:natal:aspect:{s}|{t}|{asp.get('type')}", f"f:natal:aspect:{t}|{s}|{asp.get('type')}"):
            if key in facts:
                rank = facts[key]["rank"]
    return (_BODY_ORDER.get(ft, 6), rank)


# --- build ---------------------------------------------------------------------------------------------
def ground_chart(chart: dict, corpus: Optional[list] = None) -> dict:
    """personal_principles payload for a chart (deterministic, no model; Phase 0 §1)."""
    if corpus is None:
        with open(CORPUS_PATH, encoding="utf-8") as fh:
            corpus = json.load(fh)
    return ground(corpus, chart, reading="natal", house_policy="placidus").kept_payload()


def build_dossier(chart_key: str, chart: dict, personal_principles: Optional[dict] = None,
                  l4_output: Optional[dict] = None, availability: Optional[dict] = None,
                  corpus_sha: Optional[str] = None) -> dict:
    pp = personal_principles or ground_chart(chart)
    facts = chart_facts(chart)
    records, bundles = {}, {}
    rid_of: dict[str, str] = {}
    for factor, recs in pp["bundled_by_factor"].items():
        ids = []
        for r in recs:
            if r.get("out_of_scope"):
                continue                                  # Phase 0 X4
            rid = f"r:natal:{r['principle_id']}"
            if rid in records:
                continue
            records[rid] = {"factor": factor, "render": (r.get("rule") or "").strip(),
                            "polarity": r.get("polarity"), "sensitivity": r.get("sensitivity"),
                            "goal_tags": sorted((r.get("goal_effects") or {}).keys()),
                            "_tradition": "modern" if r.get("tradition") == "modern" else "classical",
                            "_bodies": _record_bodies(r), "_sort": list(_body_sort_key(r, facts)),
                            "_claims": claims_of(r.get("about"))}
            rid_of[r["principle_id"]] = rid
            ids.append(rid)
        if ids:
            bundles[factor] = ids
    factor_of = {rid: rec["factor"] for rid, rec in records.items()}

    # by_topic: L4 routing, bundles in routing order
    kept = [r for r in pp["principles"] if f"r:natal:{r['principle_id']}" in records]
    routed = route(kept, chart)
    by_topic = {}
    for key in C.SECTION_KEYS:
        seen = []
        for rp in routed.sections.get(key, []):
            rid = rid_of.get(rp.principle_id)
            f = factor_of.get(rid) if rid else None
            if f and f not in seen:
                seen.append(f)
        if seen:
            by_topic[key] = seen
    # by_body: bundles whose factor involves the body (sign, house, aspects by rank, lordship)
    by_body: dict[str, list] = {}
    for factor, ids in bundles.items():
        first = records[ids[0]]
        for b in first["_bodies"]:
            by_body.setdefault(b, []).append((tuple(first["_sort"]), factor))
    by_body = {b: [f for _, f in sorted(v)] for b, v in sorted(by_body.items())}

    prose = prose_from(l4_output, records)
    avail = {"l4_output": bool(l4_output), "calendar": False, "best_days": False, "acg_map": False}
    avail.update(availability or {})
    return {"schema_version": K.DOSSIER_SCHEMA, "chart_key": chart_key,
            "versions": {"corpus_sha256": corpus_sha or _sha_file(CORPUS_PATH),
                         "routing_version": routing_version(), "catalogue_version": C.catalogue_sha()},
            "facts": facts, "records": records, "bundles": bundles,
            "index": {"by_topic": by_topic, "by_body": by_body}, "prose": prose, "availability": avail}


def dumps(d: dict) -> str:
    return json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def dossier_path(chart_key: str, cache_root: str = K.CACHE_ROOT) -> str:
    return os.path.join(cache_root, chart_key, "dossier.json")


def prose_from(l4_output: Optional[dict], record_ids) -> dict:
    """``l4_output.json`` sections -> prose entries, traces mapped to the dossier's record ids."""
    ok = set(record_ids)
    out = {}
    for sec in (l4_output or {}).get("sections", []):
        out[f"p:natal_section:{sec['key']}"] = {
            "text_tr": sec.get("text_tr", ""), "text_en": sec.get("text_en", ""),
            "trace": [f"r:natal:{p}" for p in sec.get("principle_ids", []) if f"r:natal:{p}" in ok]}
    return out


def load_or_build(chart_key: str, chart: dict, l4_output: Optional[dict] = None,
                  availability: Optional[dict] = None, cache_root: str = K.CACHE_ROOT) -> tuple[dict, str]:
    """Cached dossier -> (dossier, 'cache_hit' | 'built' | 'prose_updated'). PA_01 §2.5: chart_key,
    corpus, routing or catalogue changes rebuild; a new or changed l4_output updates prose only."""
    path = dossier_path(chart_key, cache_root)
    want = {"corpus_sha256": _sha_file(CORPUS_PATH), "routing_version": routing_version(),
            "catalogue_version": C.catalogue_sha()}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        if d.get("schema_version") == K.DOSSIER_SCHEMA and d.get("chart_key") == chart_key and d["versions"] == want:
            prose = prose_from(l4_output, d["records"]) if l4_output else d["prose"]
            avail = {**d["availability"], **(availability or {}),
                     "l4_output": bool(l4_output) or d["availability"].get("l4_output", False)}
            if prose != d["prose"] or avail != d["availability"]:
                d["prose"], d["availability"] = prose, avail
                _write(path, d)
                return d, "prose_updated"
            return d, "cache_hit"
    d = build_dossier(chart_key, chart, None, l4_output, availability, corpus_sha=want["corpus_sha256"])
    _write(path, d)
    return d, "built"


def _write(path: str, d: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(d))
    os.replace(tmp, path)


# --- natal retrieval (PA_01 §2.3) ------------------------------------------------------------------------
def select_natal(dossier: dict, topics: list[str], bodies: list[str], cap: Optional[int] = None) -> list[str]:
    if cap is None:
        cap = K.NATAL_CAP_ONE if len(topics) + len(bodies) <= 1 else K.NATAL_CAP_MANY
    idx = dossier["index"]
    cand: list[str] = []
    for t in topics:
        for f in idx["by_topic"].get(t, []):
            if f not in cand:
                cand.append(f)
    for b in bodies:
        for f in idx["by_body"].get(b, []):
            if f not in cand:
                cand.append(f)
    queues = [list(dossier["bundles"][f]) for f in cand]
    recs = dossier["records"]
    out: list[str] = []
    n_classical = 0
    while len(out) < cap and any(queues):
        progressed = False
        for q in queues:
            while q:
                rid = q.pop(0)
                if rid in out:
                    continue
                if recs[rid]["_tradition"] == "classical":
                    # 2:1 quota on the running selection: classical never exceeds one third
                    if (n_classical + 1) > K.CLASSICAL_MAX_SHARE * (len(out) + 1):
                        continue                         # skip; look for a modern one in this bundle
                    n_classical += 1
                out.append(rid)
                progressed = True
                break
            if len(out) >= cap:
                break
        if not progressed:
            break
    return out
