"""Phase 1–2 Solar Return math bridge — moment + chart, no interpretation.

Calls find_solar_return_utc + compute_solar_return_chart. Reading text is the
pending-astrologer placeholder only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE / "d_layer"))

PLACEHOLDER = "[Solar return reading — pending astrologer]"


def generate(data: dict) -> dict:
    from solar_return import compute_solar_return_chart, find_solar_return_utc

    lon = float(data["natal_sun_longitude"])
    year = int(data["year"])
    latitude = float(data["latitude"])
    longitude = float(data["longitude"])
    moment = find_solar_return_utc(lon, year)
    chart = compute_solar_return_chart(moment, latitude, longitude)
    return {
        "return_utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "year": year,
        "chart": chart,
        "interpretation": PLACEHOLDER,
        "math": {
            "moment": "find_solar_return_utc",
            "chart": "compute_solar_return_chart",
        },
    }


if __name__ == "__main__":
    try:
        payload = json.load(sys.stdin)
        print(json.dumps(generate(payload), ensure_ascii=True))
    except Exception as error:
        print(json.dumps({"error": type(error).__name__, "detail": str(error)}))
        sys.exit(1)
