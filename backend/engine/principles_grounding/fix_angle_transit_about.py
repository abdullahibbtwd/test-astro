#!/usr/bin/env python3
"""fix_angle_transit_about.py - one-off corpus fix (Calendar/CAL_BUILD_NOTES.md).

11 structured transit records describe a transit to the Ascendant or Midheaven, but
their ``about.aspect.target`` was backfilled as a planet (mostly "Sun"). Predictive
grounding (ground_forecast.py) keys on ``about``, so those records were served for
the wrong natal planet. This sets the target from the principle_id ("Ascendant"
or "MC", the names ground_forecast.ANGLE_TARGETS uses). Nothing else changes.

Idempotent. It refuses to write unless the file round-trips byte-identically, and it
keeps a backup next to each file.

    python principles_grounding/fix_angle_transit_about.py
"""
from __future__ import annotations

import json
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["all_principles_grounded.with_predictive.json"]
_RX = re.compile(r"-(midheaven|ascendant|mc|asc)(?:-|$)")
_ANGLE = {"midheaven": "MC", "mc": "MC", "ascendant": "Ascendant", "asc": "Ascendant"}


def fix(records: list[dict]) -> list[str]:
    changed = []
    for r in records:
        a = r.get("about") or {}
        if r.get("tradition") != "modern" or a.get("factor_type") != "aspect":
            continue
        m = _RX.search(r["principle_id"])
        if not m:
            continue
        want = _ANGLE[m.group(1)]
        asp = a.get("aspect") or {}
        if asp.get("target") != want:
            changed.append(f"{r['principle_id']}: {asp.get('target')} -> {want}")
            asp["target"] = want
    return changed


def main() -> None:
    for name in FILES:
        path = os.path.join(HERE, name)
        raw = open(path, encoding="utf-8").read()
        data = json.loads(raw)
        if json.dumps(data, ensure_ascii=False, indent=2) != raw:
            raise SystemExit(f"{name}: does not round-trip byte-identically; not touching it")
        changed = fix(data)
        print(f"{name}: {len(changed)} record(s)")
        for c in changed:
            print("  " + c)
        if changed:
            shutil.copyfile(path, path + ".bak-pre-angle-fix")
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
