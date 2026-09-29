"""cal_constants.py - fixed numbers for the personal calendar and Best Days (CAL_00..CAL_04).

Every tunable lives here so calibration gates (CAL_02 §7, CAL_04 §6) touch one file.
"""

from __future__ import annotations

# --- horizons (CAL_00 D2) --------------------------------------------------
CALENDAR_MONTHS = 12
BEST_DAYS_DAYS = 90

# --- bodies / points / aspects (CAL_01 §1) ---------------------------------
# Transiting bodies for personal transits. The Moon is NOT a calendar transit.
TRANSIT_BODIES = ["sun", "mercury", "venus", "mars", "jupiter",
                  "saturn", "uranus", "neptune", "pluto"]
# Bodies that station (Mercury..Pluto).
STATION_BODIES = ["mercury", "venus", "mars", "jupiter", "saturn",
                  "uranus", "neptune", "pluto"]
# Sign-ingress bodies (Sun..Pluto; the Moon has its own moon_ingress).
INGRESS_BODIES = ["sun"] + STATION_BODIES
# Bodies the Moon aspects for VOC (Sun..Pluto).
VOC_BODIES = ["sun"] + STATION_BODIES
SLOW_BODIES = {"jupiter", "saturn", "uranus", "neptune", "pluto"}

NATAL_PLANETS = ["sun", "moon", "mercury", "venus", "mars", "jupiter",
                 "saturn", "uranus", "neptune", "pluto"]
NATAL_ANGLES = ["asc", "mc"]            # nodes excluded in v1

ASPECTS = {"conjunction": 0, "sextile": 60, "square": 90,
           "trine": 120, "opposition": 180}
ASPECT_ORDER = ["conjunction", "sextile", "square", "trine", "opposition"]

# Orbs (CAL_01 §1 fallback values; Radul approved 2026-09-29, report Q1).
# Same for all aspects.
TRANSIT_ORB = {"sun": 1.5, "mercury": 1.5, "venus": 1.5, "mars": 1.5,
               "jupiter": 2.0, "saturn": 2.0,
               "uranus": 1.5, "neptune": 1.5, "pluto": 1.5}

# --- episodes (CAL_01 §3.1) ------------------------------------------------
EPISODE_MERGE_GAP_DAYS = 60.0
EXACT_WINDOW_DAYS = {"fast": 1.0, "slow": 3.0}   # ±days around an exact
# Scan margin around the horizon so episodes that started earlier / end later
# are captured whole (outer-planet triple passes can span ~2 years).
SCAN_MARGIN_DAYS = 1100

# --- importance (CAL_01 §3.1) ----------------------------------------------
W_T = {"pluto": 5, "neptune": 5, "uranus": 5, "saturn": 4, "jupiter": 3,
       "mars": 2, "venus": 1, "mercury": 1, "sun": 1}
W_N = {"sun": 1.5, "moon": 1.5, "asc": 1.5, "mc": 1.5, "mercury": 1.0,
       "venus": 1.0, "mars": 1.0, "jupiter": 0.7, "saturn": 0.7,
       "uranus": 0.5, "neptune": 0.5, "pluto": 0.5}
W_A = {"conjunction": 1.2, "opposition": 1.0, "square": 1.0,
       "trine": 0.8, "sextile": 0.6}
IMPORTANCE_MAJOR = 4.0
IMPORTANCE_MODERATE = 2.0

# --- lunations / eclipses / stations in the chart (CAL_01 §3.2-3.3) -------
LUNATION_HIT_ORB = 3.0
ECLIPSE_HIT_ORB = 5.0
LUMINARIES_ANGLES = {"sun", "moon", "asc", "mc"}
STATION_POINT_ORB = 2.0
STATION_POINT_MAJOR_ORB_SLOW = 1.0
STATION_POINT_ASPECTS = ["conjunction", "square", "opposition"]
FAST_STATION_BODIES = {"mercury", "venus", "mars"}

# --- collective build (CAL_01 §2) ------------------------------------------
COLLECTIVE_FIRST_YEAR = 2026
COLLECTIVE_BUILD_YEARS = range(2026, 2032)   # 2026..2031 on first run
# Eclipse maximum vs exact syzygy may differ by a few hours.
ECLIPSE_LUNATION_LINK_DAYS = 0.25

# --- day bands (CAL_02 §4; calibrated at §7, thresholds only) ---------------------------
# Initial spec values. Affinities are |A| <= 0.067 by construction (one source book,
# cal_transit_affinity_review.md), so these get calibrated at the §7 gate.
BAND_SPEC = {"quiet": 0.15, "mixed_min": 0.30, "mixed_ratio": 0.5, "strong": 0.80, "normal": 0.30}
# PROVISIONAL (pending Radul, CAL_02 §7): lambda = 0.04 x spec, from Calendar/CAL_CALIBRATION.md.
# The spec values give 100% quiet days for every goal.
BAND_LAMBDA = 0.04
BAND = {"quiet": round(BAND_SPEC["quiet"] * BAND_LAMBDA, 6),
        "mixed_min": round(BAND_SPEC["mixed_min"] * BAND_LAMBDA, 6),
        "mixed_ratio": BAND_SPEC["mixed_ratio"],
        "strong": round(BAND_SPEC["strong"] * BAND_LAMBDA, 6),
        "normal": round(BAND_SPEC["normal"] * BAND_LAMBDA, 6)}

SCHEMA_COLLECTIVE = "cal-collective-1"
SCHEMA_EVENTS = "cal-events-1"
