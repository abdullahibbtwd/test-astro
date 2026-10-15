#!/usr/bin/env python3
"""acg_english.py: write an English-only, human-readable summary of an ACG run folder.

Usage (repo root):
    python acg_english.py                 # latest run in acg_run/
    python acg_english.py <run_folder>    # a specific run
Writes <run_folder>/english.md and prints its path. Read-only on the pipeline outputs.
"""
import glob
import json
import os
import sys

GOAL_EN = {"love": "Love", "career": "Career", "business": "Business", "money": "Money",
           "family": "Family", "education": "Education", "creativity": "Creativity",
           "spirituality": "Spiritual growth", "rest": "Rest", "travel": "Travel",
           "relocation": "Permanent relocation"}
ANGLE_EN = {"ASC": "rising", "DSC": "setting", "MC": "culminating", "IC": "root"}


def band_en(b):
    return (b or "").replace("_", " ")


def line_en(d):
    if not d:
        return ""
    s = f"{d['body'].title()} {ANGLE_EN.get(d['angle'], d['angle'])} line"
    if "distance_km_rounded" in d:
        s += f" (~{d['distance_km_rounded']} km)"
    return s


def one(folder, pattern):
    hits = sorted(glob.glob(os.path.join(folder, pattern)))
    return hits[0] if hits else None


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scores_table(scores, key_band="band", key_s="score"):
    out = ["| Goal | Grade | Score |", "|---|---|---|"]
    for g, v in scores.items():
        out.append(f"| {GOAL_EN.get(g, g)} | {band_en(v.get(key_band))} | {v.get(key_s, v.get('S_agg', 0)):+.2f} |")
    return out + [""]


def city_md(folder):
    r = load(one(folder, "reading_en_*.json"))
    L = [f"# City screen: {r['place']['name']}", ""]
    if r.get("focus_goal"):
        L += [f"Focus goal: **{GOAL_EN[r['focus_goal']]}**", ""]
    L += ["## Nearby lines", "", "| Planet | Line | Approx. distance | Proximity | In text |", "|---|---|---|---|---|"]
    for d in r.get("lines_display", []):
        L.append(f"| {d.get('planet_en', d['body'].title())} | {d['angle_label_en']} | ~{d['distance_km_rounded']} km | {d['tier_label_en']} | {'yes' if d['read_in_prose'] else 'no'} |")
    L += [""]
    for s in r["sections"]:
        L += [f"## {s['title']}", ""]
        if "cards" in s:
            for c in s["cards"]:
                L += [f"**{c['title']}** — {c['text']}", ""]
        else:
            L += [s["text"], ""]
    L += ["## All 11 goal scores", ""] + scores_table(r.get("goal_scores", {}))
    L += [f"*{r['footer']}*"]
    return L


def area_md(folder, path):
    a = load(path)
    L = [f"# {a['kind'].title()} screen: {a['name']}", ""]
    ov = a.get("place_overview") or {}
    if ov.get("en"):
        L += ["## Overview", "", ov["en"], ""]
    L += ["## Goal grades (best part of the area)", ""] + scores_table(a.get("bands", {}), key_s="S_agg")
    L += ["## Lines crossing", ""] + [f"- {line_en(x)}" for x in a.get("lines_crossing", [])] + [""]
    L += ["## Best cities per goal", ""]
    for g, cities in a.get("best_cities", {}).items():
        L.append(f"- **{GOAL_EN.get(g, g)}**: " + ", ".join(f"{c['name']} ({band_en(c['band'])})" for c in cities))
    L += [""]
    if a.get("varies_by_region"):
        L += ["Varies by region: " + "; ".join(f"{GOAL_EN.get(v['goal'])} best in {v['name']} ({band_en(v['band'])})"
                                               for v in a.get("varies_highlight", [])), ""]
    foot = a.get("footer", {})
    if isinstance(foot, dict) and foot.get("en"):
        L += [f"*{foot['en']}*"]
    return L


def items_md(title, items):
    if not items:
        return [f"## {title}", "", "(none)", ""]
    L = [f"## {title}", ""]
    for i, x in enumerate(items, 1):
        extra = " · tradeoff" if x.get("has_tradeoff") else ""
        L += [f"**{i}. {x['name']}** ({x.get('country', '')}) — {x.get('band_label_en', band_en(x.get('band')))}"
              f" · {line_en(x.get('dominant_line'))}{extra}", "", x.get("text_en", ""), ""]
    return L


def recommend_md(path):
    r = load(path)
    if r.get("status") == "needs_goal":
        return ["# Where Should I Go?", "", "Status: needs_goal (the free text could not be mapped to a goal).", ""]
    L = [f"# Where Should I Go? Goal: {r.get('goal_label_en', r.get('goal'))}, scope: {r.get('scope')}", "",
         f"Status: {r.get('status')}", ""]
    if r.get("intro", {}).get("en"):
        L += [r["intro"]["en"], ""]
    L += items_md("Cities", r.get("cities"))
    L += items_md("Regions", r.get("regions"))
    L += items_md("Countries", r.get("countries"))
    t = r.get("turkey")
    if t:
        L += ["# Turkey", ""]
        if t.get("intro", {}).get("en"):
            L += [t["intro"]["en"], ""]
        L += items_md("Turkey: cities", t.get("cities"))
        L += items_md("Turkey: regions", t.get("regions"))
    foot = r.get("footer", {})
    if isinstance(foot, dict) and foot.get("en"):
        L += [f"*{foot['en']}*"]
    return L


def map_md(folder):
    L = ["# Map run (no place)", "", "Files for the map UI:", ""]
    for f in sorted(os.listdir(folder)):
        if f.endswith(".geojson") or f.startswith(("acg_", "city_scan", "goal_scan")):
            L.append(f"- {f}")
    return L + [""]


def main():
    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        runs = sorted(d for d in glob.glob(os.path.join("acg_run", "2*")) if os.path.isdir(d))
        if not runs:
            sys.exit("no runs in acg_run/")
        folder = runs[-1]
    if one(folder, "reading_en_*.json"):
        lines = city_md(folder)
    elif one(folder, "country_*.json") or one(folder, "region_*.json"):
        lines = area_md(folder, one(folder, "country_*.json") or one(folder, "region_*.json"))
    elif one(folder, "recommend_*.json"):
        lines = recommend_md(one(folder, "recommend_*.json"))
    elif one(folder, "dry_run_prompts*.json"):
        lines = ["# Dry run: no text generated (prompts only)", ""]
    else:
        lines = map_md(folder)
    out = os.path.join(folder, "english.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(out)


if __name__ == "__main__":
    main()
