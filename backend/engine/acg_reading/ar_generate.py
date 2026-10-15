#!/usr/bin/env python3
"""ar_generate.py — the model half of the ACG place reading.

Reuses the natal L4 machinery (exploration report §8): ``ACGGenerator`` subclasses
``l4_generate.LLMGenerator`` for ``_call_json`` (retry, truncation growth, JSON
repair, usage accounting) and ``_call_cheap`` (cheap translation model with a
fallback to the synthesis model). Only the prompts and the unit shape are ACG's.

Pipeline (spec 04 §1, 07 §6):
    TR drafts, in parallel: lines_here, positives, challenges, life_areas_here, cards
    TR place_overview, last, with the other drafts as context
    EN translation per section (sentence-aligned, so every sentence keeps its ids)
    detox rewrite of any unit that trips AV1/AV2/AV8/AV10 or a forbidden token
    one length re-ask per out-of-range TR unit
    ar_validate -> refuse on any remaining violation

``no_emphasis`` cards make NO model call (07 §6.2): a fixed template traced to
``acg-method-no-influence``. Card band labels are prepended in code (AV9).
"""

from __future__ import annotations

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "Interpretation_layer")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import llm_client  # noqa: E402
from l4_generate import LLMGenerator  # noqa: E402

import ar_prompts as P  # noqa: E402
from ar_routing import traced_ids  # noqa: E402
from ar_sections import BANDS, NO_EMPHASIS_ID, NO_EMPHASIS_TEXT, length_bounds  # noqa: E402
from ar_validate import text_problems, unit_text, validate, word_count  # noqa: E402

DEFAULT_MODEL = llm_client.DEFAULT_MODEL
DEFAULT_TRANSLATION_MODEL = llm_client.DEFAULT_CHEAP_MODEL
DRAFT_MAX_TOKENS = 8192
FALLBACK_CARD_TEXT = {
    "tr": "Bu değerlendirme, bu yerin yakınından geçen gezegen çizgilerinin genel "
          "dağılımından hesaplanmıştır.",
    "en": "This assessment is computed from the overall pattern of planetary lines near "
          "this place.",
}
FALLBACK_CARD_ID = "acg-method-orb-distance"


# ---------------------------------------------------------------------------
# Pools: which ids each unit may trace
# ---------------------------------------------------------------------------

def unit_pools(plan: dict) -> dict[str, set[str]]:
    pools: dict[str, set[str]] = {}
    all_section_ids: set[str] = set()
    for sec in plan["sections"]:
        for slot in sec.get("slots", []):
            ids = {r["id"] for r in slot["records"]}
            pools[slot["slot_id"]] = ids
            if sec["key"] != "place_overview":
                all_section_ids |= ids
    # the overview may trace its framing records or any id already used elsewhere
    pools["place_overview"] = pools.get("place_overview", set()) | all_section_ids
    return pools


def polarity_map(plan: dict) -> dict[str, Optional[str]]:
    out: dict[str, Optional[str]] = {}
    for sec in plan["sections"]:
        for slot in sec.get("slots", []):
            for r in slot["records"]:
                out[r["id"]] = r.get("polarity")
        for c in sec.get("cards", []):
            for r in c["records"]:
                out[r["id"]] = r.get("polarity")
    return out


def _section(plan: dict, key: str) -> Optional[dict]:
    return next((s for s in plan["sections"] if s["key"] == key), None)


# ---------------------------------------------------------------------------
# Prompt construction (also the --dry-run output)
# ---------------------------------------------------------------------------

def draft_prompts(plan: dict) -> dict[str, tuple[str, str]]:
    """section key -> (system, user) for every TR draft call except the overview."""
    place = plan["place"]
    out: dict[str, tuple[str, str]] = {}
    for sec in plan["sections"]:
        k = sec["key"]
        if k == "lines_here":
            out[k] = P.build_lines_prompt(sec, place)
        elif k == "background_influences":
            out[k] = P.build_background_prompt(sec, place)
        elif k in ("positives", "challenges"):
            out[k] = P.build_polarity_prompt(k, sec, place)
        elif k == "life_areas_here":
            out[k] = P.build_life_areas_prompt(sec, place)
        elif k == "suitability":
            model_cards = [c for c in sec["cards"] if not c["template"]]
            if model_cards:
                out[k] = P.build_cards_prompt(model_cards, place)
    return out


def dry_run_prompts(plan: dict) -> dict:
    drafts = draft_prompts(plan)
    ov = _section(plan, "place_overview")
    placeholder = {s["key"]: [{"text": f"<{s['key']} draft>", "ids": []}]
                   for s in plan["sections"] if s["key"] != "place_overview"}
    ov_prompt = P.build_overview_prompt(ov, placeholder, plan["place"],
                                        ov.get("focus_goal"), plan["no_lines"])
    return {"plan": plan,
            "prompts": {k: {"system": s, "user": u} for k, (s, u) in drafts.items()}
            | {"place_overview": {"system": ov_prompt[0], "user": ov_prompt[1]}},
            "template_cards": [c["card"] for c in (_section(plan, "suitability") or {})
                               .get("cards", []) if c["template"]],
            "model_calls": 0}


# ---------------------------------------------------------------------------
# The generator
# ---------------------------------------------------------------------------

def _units(data: dict) -> dict[str, dict]:
    out = {}
    for u in (data or {}).get("units", []):
        sents = [{"text": (s.get("text") or "").strip(), "ids": list(s.get("ids") or [])}
                 for s in u.get("sentences", []) if (s.get("text") or "").strip()]
        out[u.get("unit_id", "")] = {"unit_id": u.get("unit_id", ""), "sentences": sents}
    return out


class ACGGenerator(LLMGenerator):
    """Adds the ACG unit calls on top of L4's call/retry/fallback plumbing."""

    def draft(self, key: str, system: str, user: str) -> dict[str, dict]:
        data = self._call_json(self.model, system, user, temperature=self.section_temperature,
                               max_tokens=DRAFT_MAX_TOKENS, label=f"acg-draft[{key}]",
                               schema=P.UNITS_SCHEMA)
        return _units(data)

    def overview(self, system: str, user: str) -> dict[str, dict]:
        data = self._call_json(self.synthesis_model, system, user,
                               temperature=self.synthesis_temperature,
                               max_tokens=DRAFT_MAX_TOKENS, label="acg-overview",
                               schema=P.UNITS_SCHEMA)
        return _units(data)

    def translate_units(self, key: str, units: dict[str, dict], place: dict) -> dict[str, dict]:
        if not units:
            return {}
        system, user = P.build_translation_prompt(list(units.values()), place)
        data = self._call_cheap(system, user, max_tokens=self.translation_max_tokens,
                                label=f"acg-translate[{key}]", schema=P.TRANSLATION_SCHEMA)
        got = {u.get("unit_id"): u.get("sentences", []) for u in data.get("units", [])}
        out = {}
        for uid, unit in units.items():
            en = got.get(uid) or []
            if len(en) != len(unit["sentences"]):
                raise RuntimeError(f"translation of {key}/{uid} changed the sentence count "
                                   f"({len(unit['sentences'])} -> {len(en)})")
            out[uid] = {"unit_id": uid, "sentences": [
                {"text": (t or "").strip(), "ids": s["ids"]}
                for t, s in zip(en, unit["sentences"])]}
        return out

    def detox_unit(self, unit: dict, lang: str, problems: list[str]) -> dict:
        system, user = P.build_detox_prompt(unit, lang, problems)
        data = self._call_cheap(system, user, max_tokens=DRAFT_MAX_TOKENS,
                                label=f"acg-detox[{unit['unit_id']}/{lang}]",
                                schema=P.TRANSLATION_SCHEMA)
        new = next((u.get("sentences", []) for u in data.get("units", [])), [])
        if len(new) != len(unit["sentences"]):
            return unit                                  # keep; the validator will refuse
        return {"unit_id": unit["unit_id"], "sentences": [
            {"text": (t or "").strip(), "ids": s["ids"]} for t, s in zip(new, unit["sentences"])]}

    def reask_length(self, key: str, unit: dict, pool: list[dict]) -> dict:
        lo, hi = P.SECTIONS[key][2]                       # the nominal range, not ±20%
        system, user = P.build_length_reask(key, unit, lo, hi, word_count(unit_text(unit)),
                                            pool)
        data = self._call_json(self.model, system, user, temperature=self.section_temperature,
                               max_tokens=DRAFT_MAX_TOKENS, label=f"acg-length[{key}]",
                               schema=P.UNITS_SCHEMA)
        got = _units(data)
        return next(iter(got.values()), unit) if got else unit


# ---------------------------------------------------------------------------
# Orchestration of one reading
# ---------------------------------------------------------------------------

def _card_output(card: dict, tr_units: dict, en_units: dict) -> dict:
    label_tr, label_en = BANDS[card["band"]]
    base = {k: card[k] for k in ("card", "goal", "title_tr", "title_en", "band",
                                 "band_label_tr", "band_label_en", "contributors")}
    if card["band"] == "no_emphasis":
        return {**base, "template": True, "trace": [NO_EMPHASIS_ID],
                "text_tr": f"{label_tr}. {NO_EMPHASIS_TEXT['tr']}",
                "text_en": f"{label_en}. {NO_EMPHASIS_TEXT['en']}"}
    if card["template"]:                              # band set, but no usable records
        return {**base, "template": True, "trace": [FALLBACK_CARD_ID],
                "text_tr": f"{label_tr}. {FALLBACK_CARD_TEXT['tr']}",
                "text_en": f"{label_en}. {FALLBACK_CARD_TEXT['en']}"}
    tr, en = tr_units.get(card["card"]), en_units.get(card["card"])
    trace = sorted({i for s in (tr or {}).get("sentences", []) for i in s["ids"]})
    return {**base, "template": False, "trace": trace,
            "text_tr": f"{label_tr}. {unit_text(tr or {})}".strip(),
            "text_en": f"{label_en}. {unit_text(en or {})}".strip()}


_SECTION_IN_ERROR = re.compile(r"\b(place_overview|lines_here|background_influences|positives|challenges|life_areas_here)\b")
_CARD_IN_ERROR = re.compile(r"\bcard (\w+)")


def sections_in_errors(errors: list[str]) -> set[str]:
    """Which sections (or 'suitability') a list of validator errors points at."""
    out: set[str] = set()
    for e in errors:
        m = _SECTION_IN_ERROR.search(e)
        if m:
            out.add(m.group(1))
        if _CARD_IN_ERROR.search(e):
            out.add("suitability")
    return out


def _with_feedback(prompt: tuple[str, str], errors: list[str]) -> tuple[str, str]:
    system, user = prompt
    fb = "\n".join(f"- {e}" for e in errors[:12])
    return system, (user + "\n\nA PREVIOUS ATTEMPT FAILED THESE CHECKS; fix every one of "
                    "them (keep all other rules):\n" + fb)


def _draft_round(plan: dict, gen: "ACGGenerator", keys: set[str], tr: dict, card_tr: dict,
                 feedback: list[str]) -> dict:
    """(Re)draft the given sections into ``tr`` / ``card_tr``; overview last."""
    place = plan["place"]
    prompts = {k: v for k, v in draft_prompts(plan).items() if k in keys}
    if feedback:
        prompts = {k: _with_feedback(v, [e for e in feedback if k in e or
                                         (k == "suitability" and "card" in e)])
                   for k, v in prompts.items()}
    with ThreadPoolExecutor(max_workers=gen.max_workers) as pool:
        futs = {k: pool.submit(gen.draft, k, s, u) for k, (s, u) in prompts.items()}
        for k, f in futs.items():
            if k == "suitability":
                card_tr.clear()
                card_tr.update(f.result())
            else:
                tr[k] = f.result()
    if "place_overview" in keys:
        ov_sec = _section(plan, "place_overview")
        ctx = {k: [s for u in v.values() for s in u["sentences"]] for k, v in tr.items()
               if k != "place_overview"}
        prompt = P.build_overview_prompt(ov_sec, ctx, place, ov_sec.get("focus_goal"),
                                         plan["no_lines"])
        if feedback:
            prompt = _with_feedback(prompt, [e for e in feedback if "place_overview" in e])
        tr["place_overview"] = gen.overview(*prompt)
    # one length re-ask per out-of-range TR unit
    pool_records = {slot["slot_id"]: slot["records"] for sec in plan["sections"]
                    for slot in sec.get("slots", [])}
    for key in keys - {"suitability"}:
        lo, hi = length_bounds(key)
        for uid, unit in list(tr.get(key, {}).items()):
            if not (lo <= word_count(unit_text(unit)) <= hi):
                tr[key][uid] = gen.reask_length(key, unit, pool_records.get(uid, []))
    # EN translation (sentence-aligned) for the redrafted sections
    en_new: dict = {}
    with ThreadPoolExecutor(max_workers=gen.max_workers) as pool:
        futs = {k: pool.submit(gen.translate_units, k, tr[k], place)
                for k in keys - {"suitability"} if k in tr}
        if "suitability" in keys and card_tr:
            futs["suitability"] = pool.submit(gen.translate_units, "suitability", card_tr, place)
        for k, f in futs.items():
            en_new[k] = f.result()
    # detox any unit that trips a text rule (both languages)
    for lang, secs in (("tr", {k: tr[k] for k in keys if k in tr}), ("en", en_new),
                       ("tr", {"suitability": card_tr} if "suitability" in keys else {})):
        for key, units in secs.items():
            for uid, unit in list(units.items()):
                probs = text_problems(unit_text(unit), lang)
                if probs:
                    units[uid] = gen.detox_unit(unit, lang, probs)
    return en_new


def generate(plan: dict, gen: ACGGenerator, allowed_ids: set[str]) -> tuple[dict, list[str]]:
    """-> (internal reading {tr, en, cards}, validation errors). One targeted repair
    round: sections named by validator errors are redrafted with those errors as
    feedback, then the whole reading is validated again; anything left is refused."""
    pools = unit_pools(plan)
    all_keys = set(draft_prompts(plan)) | {"place_overview"}
    tr: dict[str, dict] = {}
    card_tr: dict = {}
    en: dict = {}
    card_en: dict = {}
    feedback: list[str] = []
    errors: list[str] = []
    keys = all_keys
    for _round in range(2):
        en_new = _draft_round(plan, gen, keys, tr, card_tr, feedback)
        card_en = en_new.pop("suitability", card_en)
        en.update(en_new)
        cards_sec = _section(plan, "suitability")
        cards = [_card_output(c, card_tr, card_en) for c in (cards_sec or {}).get("cards", [])]
        reading = {"tr": tr, "en": en, "cards": cards}
        errors = validate(reading, plan, pools, polarity_map(plan),
                          allowed_ids | traced_ids(plan))
        if not errors:
            break
        keys = sections_in_errors(errors) & all_keys
        if not keys:
            break
        # an overview gist depends on the other sections: redo it whenever they change
        keys |= {"place_overview"}
        feedback = errors
    return reading, errors
