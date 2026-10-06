"""pa_context.py - one turn's subject, people and lazily-loaded layer data (PA_01 §4, PA_04 §2).

Every loader calls an existing layer (deterministic stages only, D4) and memoises per turn.
Birth data lives only in memory here; nothing is logged.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Optional

import _paths  # noqa: F401
import pa_constants as K  # noqa: E402
import pa_dossier as D  # noqa: E402
from compute_chart import BirthData, compute_chart  # noqa: E402


def chart_of(birth: dict) -> dict:
    """``{date, time?, place: {lat, lon}}`` -> chart.json (L1)."""
    y, m, d = (int(x) for x in birth["date"].split("-"))
    kw = {"year": y, "month": m, "day": d, "latitude": birth["place"]["lat"], "longitude": birth["place"]["lon"]}
    if birth.get("time"):
        hh, mm = (int(x) for x in birth["time"].split(":"))
        kw.update(hour=hh, minute=mm, time_precision="exact")
    else:
        kw.update(time_precision="unknown")
    return compute_chart(BirthData(**kw))


class TurnContext:
    def __init__(self, subject: dict, *, profiles: Optional[list] = None, compatibilities: Optional[list] = None,
                 lang: str = "tr", today: Optional[date] = None, cache_root: str = K.CACHE_ROOT):
        self.subject = subject
        self.lang = lang
        self.today = today or date.today()
        self.tz = subject.get("effective_tz") or subject["birth"]["place"]["tz"]
        self.cache_root = cache_root
        self.compatibilities = compatibilities or []
        # people handles p1..pN in the given order (PA_02 §1)
        self.people = {f"p{i + 1}": p for i, p in enumerate(profiles or [])}
        self._memo: dict = {}

    # -- generic memo -------------------------------------------------------------------------------------
    def _m(self, key, fn):
        if key not in self._memo:
            self._memo[key] = fn()
        return self._memo[key]

    # -- natal --------------------------------------------------------------------------------------------
    def natal(self) -> dict:
        return self._m("natal", lambda: chart_of(self.subject["birth"]))

    def chart_key(self) -> str:
        import personal_events as P
        return self._m("chart_key", lambda: P.chart_key(self.natal()))

    def l4_output(self) -> Optional[dict]:
        return self._m("l4", lambda: find_l4_output(self.subject["birth"]))

    def dossier(self) -> dict:
        return self._m("dossier", lambda: D.load_or_build(self.chart_key(), self.natal(), self.l4_output(),
                                                          cache_root=self.cache_root)[0])

    # -- calendar ----------------------------------------------------------------------------------------
    def cal_start(self) -> date:
        return self.today - timedelta(days=K.DAY_PAST_DAYS)          # Phase 0 X11

    def calendar(self) -> dict:
        import run_calendar as RC
        return self._m("cal", lambda: RC.ensure_calendar(self.natal(), self.tz, self.cal_start(), best_days=False))

    def cal_range(self) -> tuple[date, date]:
        h = self.calendar()["events"]["horizon"]
        return date.fromisoformat(h["from_local"]), date.fromisoformat(h["to_local"])

    def best(self) -> dict:
        import run_calendar as RC
        return self._m("best", lambda: RC.ensure_best_days(self.natal(), self.tz, self.today)[0])

    def collective(self) -> dict:
        def load():
            import cal_astro as A
            import collective_events as CE
            a, b = self.cal_range()
            jd0 = A.local_midnight_jd(a, self.tz) - 2
            jd1 = A.local_midnight_jd(b, self.tz) + 2
            return {e["id"]: e for e in CE.load_range(jd0, jd1)}
        return self._m("coll", load)

    def corpus(self) -> tuple[dict, dict]:
        import cal_corpus
        return self._m("corpus", cal_corpus.load)

    def tags(self) -> dict:
        def load():
            import build_transit_affinity as BA
            with open(BA.TAGS, encoding="utf-8") as fh:
                return json.load(fh)
        return self._m("tags", load)

    def units(self) -> dict:
        def load():
            import cr_sections as CS
            cal = self.calendar()
            index, modern = self.corpus()
            u = CS.plan_units(cal["events"], cal["periods"], cal["events"]["collective_refs"], self.collective(),
                              index, modern, self.tags())
            u.update(CS.best_day_units(self.best(), index, modern))
            return u
        return self._m("units", load)

    def text_store(self):
        def load():
            import collective_events as CE
            import cr_generate as G
            import run_calendar as RC
            return G.TextStore(os.path.join(CE.COLLECTIVE_DIR, "texts.json"),
                               os.path.join(RC.CACHE_ROOT, self.chart_key(), "texts.json"))
        return self._m("store", load)

    def cached_text(self, unit_id: str) -> Optional[str]:
        """An already-validated calendar text in ``lang`` (never generated here, D4)."""
        import cal_corpus
        import cr_generate as G
        u = self.units().get(unit_id)
        if not u or not u["text"]:
            return None
        sha = self._m("corpus_sha", cal_corpus.corpus_sha)
        e = self.text_store().get(u["scope"], G.cache_key(u, sha, None if u["scope"] == "collective" else self.chart_key()))
        return e.get(self.lang) if e else None

    # -- predictive (read-only locator, Phase 0 G4) ------------------------------------------------------------
    def predictive_reading(self, horizon: str, target: str, lens: str) -> Optional[dict]:
        def load():
            from compute_forecast import _natal_ref
            return find_prediction(_natal_ref(self.natal()), horizon, target, lens)
        return self._m(("pred", horizon, target, lens), load)

    # -- ACG ----------------------------------------------------------------------------------------------------
    def acg(self) -> dict:
        def load():
            import acg_goals as ag
            import run_acg
            prod = run_acg.build_chart_products(self.natal(), stages=run_acg.Stages())
            prod["aff"] = ag.load_affinity()
            return prod
        return self._m("acg", load)

    # -- people --------------------------------------------------------------------------------------------------
    def person_chart(self, handle: str) -> dict:
        return self._m(("chart", handle), lambda: chart_of(self.people[handle]["birth"]))


# --- read-only locators over run folders (no cache by chart exists, Phase 0 G4 / §3) -----------------------
def _same_birth(inp: dict, birth: dict) -> bool:
    """run_meta ``input`` = {birth_date, birth_time_local, place_query} (run.py)."""
    if inp.get("birth_date") != birth["date"]:
        return False
    t = birth.get("time")
    return t is None or (inp.get("birth_time_local") or "")[:5] == t


def find_l4_output(birth: dict) -> Optional[dict]:
    """Newest ``runs/*/l4_output_<date>.json`` whose run_meta matches this birth (date + time)."""
    import glob
    runs = os.path.join(_paths.ROOT, "runs")
    for meta in sorted(glob.glob(os.path.join(runs, "*", f"run_meta_{birth['date']}.json")), reverse=True):
        try:
            with open(meta, encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        if not _same_birth(m.get("input") or {}, birth):
            continue
        out = os.path.join(os.path.dirname(meta), f"l4_output_{birth['date']}.json")
        if os.path.exists(out):
            with open(out, encoding="utf-8") as fh:
                return json.load(fh)
    return None


def find_prediction(natal_ref: str, horizon: str, target: str, lens: str) -> Optional[dict]:
    """-> {"tr": reading, "en": reading | None} from the newest matching predictive run, or None."""
    import glob
    root = os.path.join(_paths.ROOT, "prediction_run")
    for man in sorted(glob.glob(os.path.join(root, "*", "run_manifest_*.json")), reverse=True):
        try:
            with open(man, encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        if m.get("natal_ref") != natal_ref:
            continue
        d = os.path.dirname(man)
        found = {}
        for p in glob.glob(os.path.join(d, f"reading_{horizon}_{lens}_{target}_*.json")):
            if p.endswith(".rejected.json"):
                continue
            lang = "en" if p.endswith(".en.json") else "tr"
            with open(p, encoding="utf-8") as fh:
                found[lang] = json.load(fh)
        if "tr" in found:
            return {"tr": found["tr"], "en": found.get("en")}
    return None
