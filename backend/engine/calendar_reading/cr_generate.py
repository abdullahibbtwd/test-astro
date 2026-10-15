"""cr_generate.py - the model half of the calendar texts (CAL_03).

``CalendarGenerator`` reuses the natal L4 call plumbing (``l4_generate.LLMGenerator``:
retry, truncation growth, JSON repair, the cheap translation model with fallback).

Per batch of units:
    TR draft -> one length re-ask per out-of-range unit -> EN translation (sentence-aligned)
    -> detox rewrite of any unit that trips a text rule -> validate (CV1-CV5)
    -> one repair round (redraft with the errors as feedback) -> refuse what still fails
A refused unit stays label-only and its errors go to the manifest.

Texts are cached (``TextStore``) under the CAL_03 §1 keys. They are generated lazily
and prewarmed for the next 14 days.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Iterable, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT, os.path.join(_ROOT, "Interpretation_layer"), os.path.join(_ROOT, "acg_reading")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import llm_client  # noqa: E402
from l4_generate import LLMGenerator  # noqa: E402

import cr_prompts as PR  # noqa: E402
from cr_sections import PROMPT_VERSION, overlaps, window  # noqa: E402
from cr_validate import text_problems, unit_text, validate_unit, word_count  # noqa: E402

BATCH = 6
MAX_TOKENS = 8192


def _units(data: dict) -> dict[str, dict]:
    out = {}
    for u in (data or {}).get("units", []):
        sents = [{"text": (s.get("text") or "").strip(), "ids": list(s.get("ids") or [])}
                 for s in u.get("sentences", []) if (s.get("text") or "").strip()]
        out[u.get("unit_id", "")] = {"unit_id": u.get("unit_id", ""), "sentences": sents}
    return out


class CalendarGenerator(LLMGenerator):
    def draft(self, units: list[dict], feedback: Optional[list[str]] = None) -> dict[str, dict]:
        prompt = PR.build_draft_prompt(units)
        if feedback:
            prompt = PR.with_feedback(prompt, feedback)
        data = self._call_json(self.model, *prompt, temperature=self.section_temperature,
                               max_tokens=MAX_TOKENS, label=f"cal-draft[{units[0]['unit_id']}+{len(units) - 1}]",
                               schema=PR.UNITS_SCHEMA)
        return _units(data)

    def reask_length(self, u: dict, current: dict) -> dict:
        data = self._call_json(self.model, *PR.build_length_reask(u, current, word_count(unit_text(current))),
                               temperature=self.section_temperature, max_tokens=MAX_TOKENS,
                               label=f"cal-length[{u['unit_id']}]", schema=PR.UNITS_SCHEMA)
        got = _units(data)
        return got.get(u["unit_id"]) or next(iter(got.values()), current)

    def translate(self, units: list[dict]) -> dict[str, dict]:
        if not units:
            return {}
        data = self._call_cheap(*PR.build_translation_prompt(units), max_tokens=self.translation_max_tokens,
                                label=f"cal-translate[{units[0]['unit_id']}+{len(units) - 1}]",
                                schema=PR.TRANSLATION_SCHEMA)
        got = {u.get("unit_id"): u.get("sentences", []) for u in data.get("units", [])}
        out = {}
        for tr in units:
            en = got.get(tr["unit_id"]) or []
            if len(en) != len(tr["sentences"]):
                continue                         # CV1 will flag the missing/misaligned EN
            out[tr["unit_id"]] = {"unit_id": tr["unit_id"], "sentences": [
                {"text": (t or "").strip(), "ids": s["ids"]} for t, s in zip(en, tr["sentences"])]}
        return out

    def detox(self, unit: dict, lang: str, problems: list[str]) -> dict:
        data = self._call_cheap(*PR.build_detox_prompt(unit, lang, problems), max_tokens=MAX_TOKENS,
                                label=f"cal-detox[{unit['unit_id']}/{lang}]", schema=PR.TRANSLATION_SCHEMA)
        new = next((u.get("sentences", []) for u in data.get("units", [])), [])
        if len(new) != len(unit["sentences"]):
            return unit
        return {"unit_id": unit["unit_id"], "sentences": [
            {"text": (t or "").strip(), "ids": s["ids"]} for t, s in zip(new, unit["sentences"])]}


def make_generator(**kwargs) -> CalendarGenerator:
    model = kwargs.get("model") or llm_client.DEFAULT_MODEL
    llm_client.require_api_key(model, "calendar texts")
    llm_client.require_api_key(kwargs.get("translation_model") or llm_client.DEFAULT_CHEAP_MODEL,
                               "calendar translation")
    return CalendarGenerator(**kwargs)


def _one_round(gen, plans: list[dict], feedback: dict[str, list[str]]) -> tuple[dict, dict]:
    fb = [e for u in plans for e in feedback.get(u["unit_id"], [])]
    tr = gen.draft(plans, fb or None)
    by = {u["unit_id"]: u for u in plans}
    for uid, u in list(tr.items()):
        if uid in by:
            lo, hi = by[uid]["words"]
            n = word_count(unit_text(u))
            if not (int(lo * 0.8) <= n <= round(hi * 1.2)):
                tr[uid] = gen.reask_length(by[uid], u)
    en = gen.translate([tr[u["unit_id"]] for u in plans if u["unit_id"] in tr])
    for lang, units in (("tr", tr), ("en", en)):
        for uid, u in list(units.items()):
            probs = text_problems(unit_text(u), lang)
            if probs:
                units[uid] = gen.detox(u, lang, probs)
    return tr, en


def generate_batch(gen, plans: list[dict]) -> dict[str, dict]:
    """-> {unit_id: {"tr", "en", "errors"}} after at most one repair round."""
    tr, en = _one_round(gen, plans, {})
    errs = {u["unit_id"]: validate_unit(u, tr.get(u["unit_id"]), en.get(u["unit_id"])) for u in plans}
    retry = [u for u in plans if errs[u["unit_id"]]]
    if retry:
        tr2, en2 = _one_round(gen, retry, errs)
        for u in retry:
            e2 = validate_unit(u, tr2.get(u["unit_id"]), en2.get(u["unit_id"]))
            if len(e2) <= len(errs[u["unit_id"]]):
                tr[u["unit_id"]], en[u["unit_id"]], errs[u["unit_id"]] = \
                    tr2.get(u["unit_id"]), en2.get(u["unit_id"]), e2
    return {u["unit_id"]: {"tr": tr.get(u["unit_id"]), "en": en.get(u["unit_id"]),
                           "errors": errs[u["unit_id"]]} for u in plans}


# --- cache ---------------------------------------------------------------------------------
def cache_key(u: dict, corpus_sha: str, chart_key: Optional[str]) -> str:
    pool_ids = ",".join(sorted(r["id"] for r in u["pool"]))
    blob = "|".join([u["unit_id"], corpus_sha[:16], PROMPT_VERSION, chart_key or "*",
                     hashlib.sha256(pool_ids.encode()).hexdigest()[:12]])
    return blob


class TextStore:
    """Collective texts live in ``<collective_dir>/texts.json`` (shared by all users), personal
    ones in ``<chart_dir>/texts.json``. Entry: {tr, en, trace, unit_type, ref, errors?}."""

    def __init__(self, collective_path: str, personal_path: str):
        self.paths = {"collective": collective_path, "personal": personal_path}
        self.data = {k: self._load(p) for k, p in self.paths.items()}

    @staticmethod
    def _load(p: str) -> dict:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                return json.load(fh)
        return {}

    def get(self, scope: str, key: str) -> Optional[dict]:
        return self.data[scope].get(key)

    def put(self, scope: str, key: str, entry: dict) -> None:
        self.data[scope][key] = entry

    def save(self) -> None:
        for scope, p in self.paths.items():
            os.makedirs(os.path.dirname(p), exist_ok=True)
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(self.data[scope], ensure_ascii=False, indent=1, sort_keys=True) + "\n")
            os.replace(tmp, p)


def ensure_texts(units: Iterable[dict], store: TextStore, gen, corpus_sha: str, chart_key: str,
                 workers: int = 4) -> dict:
    """Generate the uncached text-eligible units (lazy path). -> run stats."""
    todo, cached = [], 0
    for u in units:
        if not u["text"]:
            continue
        key = cache_key(u, corpus_sha, None if u["scope"] == "collective" else chart_key)
        hit = store.get(u["scope"], key)
        # a cached text is re-checked against the CURRENT text rules, so tightening the
        # validator refreshes exactly the entries that now fail (no prompt-version bump)
        if hit and not (text_problems(hit["tr"], "tr") or text_problems(hit["en"], "en")):
            cached += 1
        else:
            todo.append((key, u))
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    refused: dict[str, list[str]] = {}

    def run(batch):
        return batch, generate_batch(gen, [u for _, u in batch])

    if batches:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            for batch, res in pool.map(run, batches):
                for key, u in batch:
                    r = res[u["unit_id"]]
                    if r["errors"]:
                        refused[u["unit_id"]] = r["errors"]
                        continue
                    trace = sorted({i for s in r["tr"]["sentences"] for i in s["ids"]})
                    store.put(u["scope"], key, {"tr": unit_text(r["tr"]), "en": unit_text(r["en"]),
                                                "trace": trace, "unit_type": u["unit_type"], "ref": u["ref"],
                                                "sentences_tr": r["tr"]["sentences"],
                                                "sentences_en": r["en"]["sentences"]})
        store.save()
    return {"cached": cached, "generated": len(todo) - len(refused), "refused": refused,
            "batches": len(batches)}


def prewarm_units(units: dict, today: date, days: int = 14) -> list[dict]:
    """Text-eligible units whose dates fall in [today, today + days) (CAL_03 T5)."""
    first, last = window(today, days)
    return [u for u in units.values() if u["text"] and overlaps(u["span"], first, last)]


def texts_for(units: dict, store: TextStore, corpus_sha: str, chart_key: str, lang: str) -> dict:
    """texts_<lang>.json: {unit_id: {text, trace, unit_type, ref, label}} for every unit; units
    without cached prose carry only the label (text = null)."""
    out = {}
    for uid, u in sorted(units.items()):
        entry = None
        if u["text"]:
            entry = store.get(u["scope"], cache_key(u, corpus_sha, None if u["scope"] == "collective" else chart_key))
        out[uid] = {"text": entry[lang] if entry else None, "trace": entry["trace"] if entry else [],
                    "unit_type": u["unit_type"], "ref": u["ref"], "label": u[f"label_{lang}"]}
    return out


def gaps(units: dict) -> list[dict]:
    return [{"unit_id": u["unit_id"], "reason": u["gap"]} for u in sorted(units.values(), key=lambda x: x["unit_id"])
            if u.get("gap")]
