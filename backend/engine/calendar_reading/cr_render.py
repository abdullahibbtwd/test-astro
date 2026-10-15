"""cr_render.py - write the calendar text outputs (CAL_03 §5).

texts_tr.json / texts_en.json: {unit_id: {text, trace, unit_type, ref, label}}. Units
without prose carry text = null and only the deterministic label. The manifest gets
``gaps`` (label-only units and why) and ``refused`` (units the validator rejected).
"""

from __future__ import annotations

import json
import os

import cr_generate as G


def write_texts(out_dir: str, units: dict, store: G.TextStore, corpus_sha: str, chart_key: str,
                suffix: str = "") -> dict[str, str]:
    paths = {}
    for lang in ("tr", "en"):
        p = os.path.join(out_dir, f"texts_{lang}{suffix}.json")
        os.makedirs(out_dir, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(G.texts_for(units, store, corpus_sha, chart_key, lang),
                                ensure_ascii=False, indent=1, sort_keys=True) + "\n")
        paths[lang] = p
    return paths
