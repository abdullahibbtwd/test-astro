#!/usr/bin/env python3
"""acg_constants.py — the fixed knobs of the astrocartography layer (ACG specs 01–03).

Every tunable number the ACG layer uses lives here, so a change is one edit and is
visible in review. Nothing in this file is interpretive.
"""

from __future__ import annotations

import swisseph as swe  # type: ignore[import-not-found]

SCHEMA_VERSION = "acg-1"
LOCATE_SCHEMA_VERSION = "acg-locate-1"

# --- bodies (spec 01 §2, index D3) ------------------------------------------
# (acg id, swe id, display name as L1 emits it, read in v1?)
# The node mirrors L1: compute_chart.BODIES uses swe.MEAN_NODE. The South Node's
# lines are the North Node's with ASC<->DSC and MC<->IC swapped; the UI derives them.
BODIES: tuple[tuple[str, int, str, bool], ...] = (
    ("sun", swe.SUN, "Sun", True),
    ("moon", swe.MOON, "Moon", True),
    ("mercury", swe.MERCURY, "Mercury", True),
    ("venus", swe.VENUS, "Venus", True),
    ("mars", swe.MARS, "Mars", True),
    ("jupiter", swe.JUPITER, "Jupiter", True),
    ("saturn", swe.SATURN, "Saturn", True),
    ("uranus", swe.URANUS, "Uranus", True),
    ("neptune", swe.NEPTUNE, "Neptune", True),
    ("pluto", swe.PLUTO, "Pluto", True),
    ("north_node", swe.MEAN_NODE, "North Node", False),
)
BODY_ORDER: tuple[str, ...] = tuple(b[0] for b in BODIES)
BODY_DISPLAY: dict[str, str] = {b[0]: b[2] for b in BODIES}
DISPLAY_TO_BODY: dict[str, str] = {b[2]: b[0] for b in BODIES}
READ_IN_V1: dict[str, bool] = {b[0]: b[3] for b in BODIES}
NODE_OUT_OF_SCOPE = "acg_nodes_v1"
PERSONAL_BODIES: tuple[str, ...] = ("sun", "moon", "mercury", "venus", "mars")

ANGLES: tuple[str, ...] = ("MC", "IC", "ASC", "DSC")
# The angular house each angle stands for (spec 03 A4 fallback).
ANGLE_HOUSE: dict[str, int] = {"ASC": 1, "IC": 4, "DSC": 7, "MC": 10}

# --- ephemeris (spec 01 §2; mirrors L1 — see exploration report C1) ---------
ACG_EXTRA_FLAG = swe.FLG_EQUATORIAL
FLAG_NAMES: tuple[str, ...] = ("MOSEPH", "SPEED", "EQUATORIAL")
METHOD = "in_mundo_geometric_horizon"

# --- sampling (spec 01 §5) ----------------------------------------------------
LAT_MIN = -80.0
LAT_MAX = 80.0
LAT_STEP = 0.25
# Earth's sidereal rotation: one minute of birth-time error moves every line by this
# many degrees of longitude (spec 01 §7.1; read by the UI later, not in v1).
LINE_UNCERTAINTY_DEG_PER_MIN = 0.2507

# --- geometry / orbs (spec 02 §3, index D6) -----------------------------------
EARTH_RADIUS_KM = 6371.0
# (tier, max perpendicular distance km), tightest first.
ORB_TIERS_KM: tuple[tuple[str, float], ...] = (
    ("tight", 150.0),
    ("strong", 400.0),
    ("wide", 1000.0),
)
MAX_ORB_KM = ORB_TIERS_KM[-1][1]
# Only ASC/DSC segments whose vertices lie within this many degrees of the place's
# latitude are searched (performance prefilter; exact for orbs <= 1,000 km).
SEGMENT_LAT_WINDOW_DEG = 15.0

# --- relocation (index D8) ---------------------------------------------------
RELOCATION_MAX_ABS_LAT = 66.0

# --- grounding budgets (spec 03) ---------------------------------------------
ACG_MAX_LINES_READ = 4
ACG_MAX_HOUSE_SHIFTS = 5
A4_FILL_TO = 3

ABSENCE_REASONS_COMPUTE = ("birth_time_not_exact", "missing_utc_instant", "ephemeris_error")

# ===========================================================================
# v3 — goals and scoring (ACG spec 08). Thresholds are the INITIAL constants;
# the calibration gate (08 §4) may change the band thresholds only, with a date.
# ===========================================================================

# goal -> (TR label, EN label, normative definition used verbatim by the tagger)
GOALS: dict[str, tuple[str, str, str]] = {
    "love": ("Aşk", "Love",
             "romance, attraction, dating, intimate partnership, marriage"),
    "career": ("Kariyer", "Career",
               "vocation, profession, public role, reputation, recognition, promotion, "
               "authority at work"),
    "business": ("İş ve Ticaret", "Business",
                 "enterprise, commerce, deals, negotiation, clients, business partners, "
                 "entrepreneurship"),
    "money": ("Para", "Money",
              "income, wealth, financial gain or loss, material comfort, spending"),
    "family": ("Aile", "Family",
               "home life, household, parents, children, roots, domestic security"),
    "education": ("Eğitim", "Education",
                  "study, learning, teaching, writing, publishing, intellectual development"),
    "creativity": ("Yaratıcılık", "Creativity",
                   "arts, performance, self-expression, creative work, play"),
    "spirituality": ("Ruhsal Gelişim", "Spiritual Growth",
                     "meaning, faith, inner work, retreat, transcendence, ideals"),
    "rest": ("Dinlenme", "Rest",
             "ease, relaxation, calm, recuperation, low pressure"),
    "travel": ("Seyahat", "Travel",
               "visiting, short stays, exploration, movement, experiences as a visitor"),
    "relocation": ("Kalıcı Taşınma", "Permanent Relocation",
                   "long-term residence, settling, belonging, putting down roots, "
                   "making a place home"),
}
GOAL_ORDER: tuple[str, ...] = tuple(GOALS)
GOAL_POLARITIES: tuple[str, ...] = ("supportive", "challenging", "mixed")
MAX_GOALS_PER_RECORD = 3

# Affinity table (08 §2)
AFFINITY_W_LINE = 1.0          # A1 line records for (p, a)
AFFINITY_W_GENERAL = 0.5       # A2 planet_general records for p
AFFINITY_K = 2.0               # smoothing toward 0 for thin evidence
AFFINITY_V0 = 5.0              # volume at which evidence is fully trusted
AFFINITY_LOW_EVIDENCE = 2.0    # cells with volume < this are flagged

# Place score (08 §3)
CONTRIBUTOR_MIN = 0.05         # |contribution| for a line's records to count as contributors

# Bands (08 §4), evaluated in this order. INITIAL constants (2026-09-25).
BAND_NO_EMPHASIS_PN = 0.20     # P + N below this -> no_emphasis
BAND_MIXED_MIN = 0.35          # max(P, N) at least this ...
BAND_MIXED_RATIO = 0.5         # ... and min(P, N) >= ratio * max(P, N) -> mixed
BAND_STRONG = 1.00             # S >= -> strongly_supportive
BAND_SUPPORTIVE = 0.35         # S >= -> supportive ; S <= -this -> challenging
BANDS: dict[str, tuple[str, str]] = {
    "strongly_supportive": ("Güçlü şekilde destekleyici", "Strongly supportive"),
    "supportive": ("Destekleyici", "Supportive"),
    "mixed": ("Karışık: hem fırsat hem zorluk", "Mixed: opportunity and challenge"),
    "challenging": ("Zorlayıcı", "Challenging"),
    "no_emphasis": ("Belirgin bir vurgu yok", "No clear emphasis"),
}
BAND_RANK: dict[str, int] = {"challenging": 0, "no_emphasis": 1, "mixed": 2,
                             "supportive": 3, "strongly_supportive": 4}

# Aggregates (08 §5)
AGG_COUNTRY_FRAC, AGG_COUNTRY_MIN = 0.05, 3
AGG_REGION_FRAC, AGG_REGION_MIN = 0.10, 1

# UI display labels (07 §4) — UI data only; model prose still bans angle jargon (AV1)
PLANET_TR: dict[str, str] = {
    "sun": "Güneş", "moon": "Ay", "mercury": "Merkür", "venus": "Venüs", "mars": "Mars",
    "jupiter": "Jüpiter", "saturn": "Satürn", "uranus": "Uranüs", "neptune": "Neptün",
    "pluto": "Plüton",
}
ANGLE_LABELS: dict[str, tuple[str, str]] = {
    "ASC": ("Yükselen çizgi", "Rising line"),
    "DSC": ("Alçalan çizgi", "Setting line"),
    "MC": ("Zirve çizgisi", "Culminating line"),
    "IC": ("Kök çizgisi", "Root line"),
}
TIER_LABELS: dict[str, tuple[str, str]] = {
    "tight": ("Çok yakın", "Very close"),
    "strong": ("Yakın", "Near"),
    "wide": ("Uzak etki alanı", "Distant range"),
}

# ===========================================================================
# v4 — parans (ACG spec 10)
# ===========================================================================
PARANS_SCHEMA_VERSION = "acg-parans-1"
PARAN_SAMPLE_STEP = 0.05       # deg of latitude between root-search samples
PARAN_WRAP_JUMP = 90.0         # |Δf| above this between samples is a wrap, not a root
PARAN_BISECT_TOL = 1e-9        # deg
PARAN_ORB_DEG = 1.0            # a place within ±1° of latitude is "near" a paran
PARANS_PER_PLACE = 2           # keep the closest two
W_PARAN = 0.4                  # paran weight at Δφ = 0 (08 §3 addition, spec 10 §6)
KM_PER_DEG_LAT = 111.2
