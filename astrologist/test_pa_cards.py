"""PA_01 §8 T10: every card candidate validates against AskCard; every link route is in the §6 table."""

from __future__ import annotations

import json
import os
import re

from jsonschema import Draft202012Validator

import pa_cards as CARDS
import pa_tools as T
from test_pa_tools import ALL_CALLS

SCHEMA = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "askcard.schema.json"), encoding="utf-8"))
ROUTE_PATTERNS = [re.compile("^" + re.escape(t).replace(r"\{", "{").replace(r"\}", "}")
                             .replace("{key}", "[a-z_]+").replace("{date}", r"\d{4}-\d{2}-\d{2}")
                             .replace("{month}", r"\d{4}-\d{2}").replace("{id}", "[^/?&]+")
                             .replace("{activity}", "[a-z_]+").replace("{place_id}", "[a-z0-9-]+")
                             .replace("{goal}", "[a-z_]+").replace("{scope}", "[A-Za-z]+")
                             .replace("{profile_id}", "[A-Za-z0-9-]*").replace("{type}", "[a-z]+") + "$")
                  for _, t in CARDS.LINKS.values()]


def test_t10_cards_and_links(ctx, ctx_en):
    v = Draft202012Validator(SCHEMA)
    n_cards = 0
    for c in (ctx, ctx_en):
        for i, (tool, args) in enumerate(ALL_CALLS):
            p = T.run_tool(c, f"c{i}", tool, args)
            for cand in p["card_candidates"]:
                errs = list(v.iter_errors(cand["card"]))
                assert not errs, (tool, cand["card"].get("type"), [e.message for e in errs[:2]])
                n_cards += 1
            for lk in p["link_candidates"]:
                assert any(rx.match(lk["route"]) for rx in ROUTE_PATTERNS), lk["route"]
                assert lk["label"]
    assert n_cards >= 15


def test_card_shapes_reject_extras():
    v = Draft202012Validator(SCHEMA)
    bad = {"type": "chart_fact", "body": "venus", "sign": "taurus", "degree_in_sign": 3.2, "house": 7,
           "retrograde": False, "longitude": 33.2}
    assert list(v.iter_errors(bad))
