"""Fixture people for tests and the golden set (PA_04 §9). Reference chart: 1979-03-30 06:30 Sofia."""

SOFIA = {"name": "Sofia", "lat": 42.6977, "lon": 23.3219, "tz": "Europe/Sofia"}
PLOVDIV = {"name": "Plovdiv", "lat": 42.1354, "lon": 24.7453, "tz": "Europe/Sofia"}

SUBJECT = {"profile_id": "prof-self", "label": "Ben", "relation": "self", "is_self": True,
           "birth": {"date": "1979-03-30", "time": "06:30", "place": SOFIA}, "effective_tz": "Europe/Sofia"}
PARTNER = {"profile_id": "prof-ayse", "label": "Ayşe", "relation": "partner",
           "birth": {"date": "1988-12-28", "time": "13:00", "place": PLOVDIV}}
COLLEAGUE = {"profile_id": "prof-mert", "label": "Mert", "relation": "colleague",
             "birth": {"date": "1984-06-12", "time": "09:15", "place": SOFIA}}
PROFILES = [PARTNER, COLLEAGUE]
COMPATIBILITIES = [{"compatibility_id": "cmp-1", "profile_a_id": "prof-self", "profile_b_id": "prof-ayse",
                    "type": "love", "family_relation": None}]
FIXTURE_TODAY = "2026-10-05"
