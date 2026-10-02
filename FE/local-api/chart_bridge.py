"""Private, no-network bridge to the existing chart engine. JSON in/out via stdio."""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "d_layer"))
from compute_chart import BirthData, compute_chart, resolve_timezone


def calculate(data):
    date, time, place = data["date"], data["time"], data["place"]
    local = datetime.strptime(date + "T" + time, "%Y-%m-%dT%H:%M")
    if local.strftime("%Y-%m-%dT%H:%M") != date + "T" + time:
        raise ValueError("Invalid birth date or time")
    lat, lon = float(place["lat"]), float(place["lon"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid coordinates")
    zone_name = resolve_timezone(lat, lon)
    zone = ZoneInfo(zone_name)
    instants = set()
    for fold in (0, 1):
        candidate = local.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if candidate.astimezone(zone).replace(tzinfo=None) == local:
            instants.add(candidate)
    if len(instants) != 1:
        raise ValueError("Birth time is ambiguous or nonexistent during a clock change")
    instant = next(iter(instants))
    result = compute_chart(BirthData(year=local.year, month=local.month, day=local.day,
        hour=local.hour, minute=local.minute, latitude=lat, longitude=lon,
        time_precision="exact", reading_date_utc=instant), utc_override=instant)
    if not result.get("sectors", {}).get("placidus_cusps"):
        raise ValueError("Placidus houses are unavailable at this latitude")
    return result


def places(data):
    cities = json.loads((ROOT / "Astrocartography/gazetteer.json").read_text(encoding="utf-8"))["cities"]
    countries = {x["iso_a2"]: x for x in json.loads((ROOT / "Astrocartography/countries.json").read_text(encoding="utf-8"))}
    lang = data.get("lang", "en")
    query = data.get("query", "").casefold().strip()
    if data.get("id"):
        found = [c for c in cities if c["id"] == data["id"]]
    elif len(query) >= 2:
        found = [c for c in cities if any(query in str(n).casefold() for n in [c["name"], c.get("name_tr", ""), *c.get("aliases", [])])]
        found.sort(key=lambda c: (c["name"].casefold() != query, -c.get("population", 0)))
        found = found[:8]
    else:
        found = []
    result = []
    for c in found:
        country = countries.get(c["country_code"], {})
        result.append({"place_id": c["id"], "name": c.get("name_tr", c["name"]) if lang == "tr" else c["name"],
            "admin1": c.get("admin1_code"), "country_code": c["country_code"],
            "country_name": country.get("name_tr" if lang == "tr" else "name", c["country_code"]),
            "lat": c["lat"], "lon": c["lon"], "tz": resolve_timezone(c["lat"], c["lon"]),
            "kind": "city", "population": c.get("population"), "source": "gazetteer"})
    return result

if __name__ == "__main__":
    try:
        data = json.load(sys.stdin)
        print(json.dumps(places(data) if data.get("action") == "places" else calculate(data), ensure_ascii=True))
    except ValueError as error:
        print(json.dumps({"error": "validation_error", "message": str(error)}))
    except Exception:
        print(json.dumps({"error": "engine_unavailable"}))
        sys.exit(1)
