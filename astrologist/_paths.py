"""Put every layer's folder on sys.path (the layers import their siblings by bare name)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
for _d in ("", "astrologist", "d_layer", "principles_grounding", "Interpretation_layer", "Calendar",
           "calendar_reading", "Astrocartography", "acg_reading", "synastry_reading",
           "prediction_reading", "Forecast_compute"):
    _p = os.path.join(ROOT, _d) if _d else ROOT
    if _p not in sys.path:
        sys.path.insert(0, _p)
