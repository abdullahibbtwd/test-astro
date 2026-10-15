"""PA_01 §8 D1-D6 on the three fixture charts.  Run: python -m pytest astrologist/test_pa_dossier.py -q"""

from __future__ import annotations

import json

import pytest

import pa_dossier as D

MASKED_KEYS = ["whole_sign", "whole_sign_cusps", "classifications", "derived_points", "planetary_day",
               "planetary_hour", "is_diurnal", "sect", "tradition"]          # FE_02 AC3 / §6.4 (+ X5)


@pytest.fixture(scope="module")
def built(charts):
    out = {}
    for name, ch in charts.items():
        pp = D.ground_chart(ch)
        out[name] = (ch, pp, D.build_dossier(f"k-{name}", ch, pp))
    return out


def test_d1_byte_identical(built, charts):
    for name, (ch, pp, d) in built.items():
        assert D.dumps(D.build_dossier(f"k-{name}", ch, pp)) == D.dumps(d)


def test_d2_every_kept_record_once(built):
    for ch, pp, d in built.values():
        kept = {f"r:natal:{r['principle_id']}" for r in pp["principles"] if not r.get("out_of_scope")}
        assert set(d["records"]) == kept
        ids = [rid for v in d["bundles"].values() for rid in v]
        assert len(ids) == len(set(ids)) == len(kept)


def test_d3_facts_match_chart_and_no_masked_field(built):
    for ch, pp, d in built.values():
        for p in ch["points"]:
            f = d["facts"][f"f:natal:{D._key(p['name'])}"]
            assert f["sign"] == p["sign"].lower() and f["house"] == p["sector"]["placidus"]
        modern = {(D._key(r["source"]), D._key(r["target"]), r["type"]) for r in ch["relations"] if r["scheme"] == "modern"}
        got = {(f["a"], f["b"], f["type"]) for f in d["facts"].values() if f["kind"] == "aspect"}
        assert got == modern
        blob = json.dumps({k: v for k, v in d.items() if k != "records"})
        for key in MASKED_KEYS:
            assert f'"{key}"' not in blob, key
        assert "orb" not in json.dumps(d["facts"])


def test_d4_every_record_reachable(built):
    for ch, pp, d in built.values():
        topic = {rid for fs in d["index"]["by_topic"].values() for f in fs for rid in d["bundles"][f]}
        body = {rid for fs in d["index"]["by_body"].values() for f in fs for rid in d["bundles"][f]}
        assert set(d["records"]) <= topic | body
        print("records reachable only via by_body:", sorted(body - topic))


def test_d5_invalidation(charts, tmp_path, monkeypatch):
    ch = charts["self"]
    d, st = D.load_or_build("kA", ch, cache_root=str(tmp_path))
    assert st == "built"
    assert D.load_or_build("kA", ch, cache_root=str(tmp_path))[1] == "cache_hit"
    l4 = {"sections": [{"key": "partnerships", "text_tr": "x", "text_en": "y",
                        "principle_ids": [next(iter(d["records"]))[len("r:natal:"):]]}]}
    d2, st = D.load_or_build("kA", ch, l4_output=l4, cache_root=str(tmp_path))
    assert st == "prose_updated" and d2["records"] == d["records"] and d2["index"] == d["index"]
    assert d2["availability"]["l4_output"] and "p:natal_section:partnerships" in d2["prose"]
    monkeypatch.setattr(D, "_sha_file", lambda p: "changed-corpus")
    assert D.load_or_build("kA", ch, cache_root=str(tmp_path))[1] == "built"
    assert D.load_or_build("kB", ch, cache_root=str(tmp_path))[1] == "built"


def test_d6_selection_cap_quota_roundrobin(built):
    for ch, pp, d in built.values():
        sel = D.select_natal(d, ["partnerships"], [])
        assert 0 < len(sel) <= 24
        n_cl = sum(d["records"][r]["_tradition"] == "classical" for r in sel)
        assert n_cl * 3 <= len(sel)
        # round-robin: the first records come from distinct bundles, in by_topic order
        factors = d["index"]["by_topic"]["partnerships"]
        firsts = [d["records"][r]["factor"] for r in sel[:min(len(factors), 6)]]
        assert len(set(firsts)) == len(firsts)
    fake = {"index": {"by_topic": {"t": ["A", "B"]}, "by_body": {}},
            "bundles": {"A": ["a1", "a2", "a3"], "B": ["b1", "b2"]},
            "records": {"a1": {"_tradition": "modern"}, "a2": {"_tradition": "modern"}, "a3": {"_tradition": "modern"},
                        "b1": {"_tradition": "classical"}, "b2": {"_tradition": "modern"}}}
    # b1 (classical) would be 1 of 2 > one third: skipped for good; modern runs out at 4 -> stop, never pad
    assert D.select_natal(fake, ["t"], [], cap=5) == ["a1", "b2", "a2", "a3"]
