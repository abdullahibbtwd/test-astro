"""Phase 3 Family / Match aspect-math bridge — aspects only, no interpretation.

Calls compute_synastry_aspects. Reading text is the pending-astrologer placeholder.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE / "principles_grounding"))
sys.path.insert(0, str(ENGINE / "d_layer"))
sys.path.insert(0, str(ENGINE / "rules"))

PLACEHOLDER = "[Family compatibility reading — pending astrologer]"


def generate(data: dict) -> dict:
    from synastry_aspects import compute_synastry_aspects
    from load_rules import load_family_rules

    relationship_type = data.get("relationship_type", "romantic")
    rules = load_family_rules()
    aspects = compute_synastry_aspects(
        data["chart_a"], data["chart_b"], relationship_type,
    )
    return {
        "relationship_type": relationship_type,
        "profile_a_label": data.get("profile_a_label", "A"),
        "profile_b_label": data.get("profile_b_label", "B"),
        "aspects": aspects,
        "interpretation": PLACEHOLDER,
        "rules_status": (rules.get("_meta") or {}).get("status", "UNKNOWN"),
        "math": {"aspects": "compute_synastry_aspects"},
    }


if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
        print(json.dumps(generate(payload), ensure_ascii=True))
    except Exception as error:
        print(json.dumps({"error": type(error).__name__, "detail": str(error)}))
        sys.exit(1)
