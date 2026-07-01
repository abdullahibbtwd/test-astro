#!/usr/bin/env python3
"""
combine_relationship_principles.py

Merge the two relationship sources into the single corpus that
``ground_relationship.py`` consumes:

    relationship_principles.clean.json          (synastry, from the book)
    relationship_natal_principles.clean.json     (natal_relational, from the corpus)
        -> combined_relationship_principles.clean.json

Both inputs are already in the same clean+`synastry` format, so this is a
concatenation — with a dedup guard (ids are disjoint: `syn-*` vs the natal ids)
and a light shape check. Written with `\\n` newlines so the artifact is
byte-stable (this tree lives in Google Drive).

Run:
    python combine_relationship_principles.py
    python combine_relationship_principles.py --inputs a.json b.json --out c.json
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter

_REQUIRED = {"principle_id", "domain", "synastry"}


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inputs", nargs="+", default=[
        os.path.join(here, "relationship_principles.clean.json"),
        os.path.join(here, "relationship_natal_principles.clean.json"),
    ])
    ap.add_argument("--out",
                    default=os.path.join(here, "combined_relationship_principles.clean.json"))
    args = ap.parse_args()

    combined: list[dict] = []
    seen: set[str] = set()
    dupes = 0
    for path in args.inputs:
        if not os.path.exists(path):
            print(f"! skipping missing input: {path}")
            continue
        records = json.load(open(path, encoding="utf-8"))
        added = 0
        for r in records:
            missing = _REQUIRED - set(r)
            if missing:
                print(f"! {os.path.basename(path)}: record "
                      f"{r.get('principle_id','?')} missing {sorted(missing)} — skipped")
                continue
            pid = r["principle_id"]
            if pid in seen:
                dupes += 1
                continue
            seen.add(pid)
            combined.append(r)
            added += 1
        print(f"+ {os.path.basename(path)}: {added} records")

    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(combined, fh, ensure_ascii=False, indent=1)

    by_inter = Counter((r.get("synastry") or {}).get("interaction") for r in combined)
    print(f"\ncombined {len(combined)} records"
          + (f" ({dupes} duplicate id(s) skipped)" if dupes else ""))
    print("by interaction:", dict(by_inter))
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
