#!/usr/bin/env python3
"""CHART_WHEEL_SPEC.md §11 — reference renderer (geometry oracle, NOT the engine).

Throwaway script that proves the §3 transform and §7 band proportions for a single
chart. It is the geometry oracle: for any chart.json, the engine's glyph / cusp /
axis / hub positions must match this reference within 0.1deg / 1px.

This is NOT the production engine and must not be ported as-is. Known differences
the engine closes (see §11): bundled vector glyphs (here: Unicode stand-ins),
CSS-token theming (here: hardcoded hex), soft-aspect floor, flags/optional layers,
the invariant gate, and generality. Treat this as "the geometry you must
reproduce," not "the code you ship."

Usage:
    python render_wheel.py [chart.json] --positions out.json   # geometry oracle
    python render_wheel.py [chart.json] --svg out.svg          # visual proof
"""
import json
import math
import sys

# --- §7 band radii (mirror of src/constants.js; oracle is allowed to hardcode) ---
VIEWBOX = 1000
CX = CY = 500
B = {
    "zodiacOuter": 460, "zodiacInner": 410, "signGlyph": 435,
    "tickOuter": 410, "tickInner": 398, "pointerTop": 408,
    "planetGlyph": 358, "houseCuspOuter": 396, "houseCuspInner": 236,
    "houseNum": 252, "hub": 236,
}
PLOTTED = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
           "Uranus", "Neptune", "Pluto", "North Node", "South Node"]

# Unicode stand-ins ONLY for the visual proof (engine forbids these — §4/§11).
UNI = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀",
    "Mars": "♂", "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅",
    "Neptune": "♆", "Pluto": "♇", "North Node": "☊", "South Node": "☋",
}
SIGN_UNI = ["♈", "♉", "♊", "♋", "♌", "♍",
            "♎", "♏", "♐", "♑", "♒", "♓"]


def mod360(a):
    return ((a % 360) + 360) % 360


def theta_screen(lam, asc):
    return mod360(180 + (lam - asc))


def project(lam, r, asc):
    th = math.radians(theta_screen(lam, asc))
    return (CX + r * math.cos(th), CY - r * math.sin(th))


def arc_mid(a, b):
    return mod360(a + mod360(b - a) / 2)


def rnd(p):
    return [round(p[0], 3), round(p[1], 3)]


def positions(chart):
    asc = chart["axes"]["ascendant"]["longitude"]
    mc = chart["axes"]["mc"]["longitude"]
    out = {"asc": asc, "mc": mc, "planets": [], "cusps": [], "signs": [],
           "axes": {}, "hub": []}

    by_name = {p["name"]: p for p in chart["points"]}
    for name in PLOTTED:
        p = by_name.get(name)
        if not p:
            continue
        out["planets"].append({
            "name": name, "lon": p["longitude"],
            "glyph": rnd(project(p["longitude"], B["planetGlyph"], asc)),
            "pointerTop": rnd(project(p["longitude"], B["pointerTop"], asc)),
        })

    cusps = chart.get("sectors", {}).get("placidus_cusps")
    if cusps and len(cusps) == 12:
        for i, c in enumerate(cusps):
            out["cusps"].append({
                "house": i + 1, "lon": c,
                "inner": rnd(project(c, B["houseCuspInner"], asc)),
                "outer": rnd(project(c, B["houseCuspOuter"], asc)),
                "num": rnd(project(arc_mid(c, cusps[(i + 1) % 12]), B["houseNum"], asc)),
            })

    for i in range(12):
        out["signs"].append(rnd(project(i * 30 + 15, B["signGlyph"], asc)))

    out["axes"] = {
        "asc": rnd(project(asc, B["zodiacInner"], asc)),
        "desc": rnd(project(asc + 180, B["zodiacInner"], asc)),
        "mc": rnd(project(mc, B["zodiacInner"], asc)),
        "ic": rnd(project(mc + 180, B["zodiacInner"], asc)),
    }

    for rel in chart.get("relations", []):
        if rel.get("scheme") != "modern":
            continue
        s, t = by_name.get(rel["source"]), by_name.get(rel["target"])
        if not s or not t:
            continue
        out["hub"].append({
            "from": rel["source"], "to": rel["target"], "type": rel["type"],
            "a": rnd(project(s["longitude"], B["hub"], asc)),
            "b": rnd(project(t["longitude"], B["hub"], asc)),
        })
    return out


def svg(chart):
    """Visual proof with Unicode stand-ins + hardcoded hex (NOT the engine)."""
    asc = chart["axes"]["ascendant"]["longitude"]
    mc = chart["axes"]["mc"]["longitude"]
    pos = positions(chart)
    el = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VIEWBOX} {VIEWBOX}">',
          f'<rect width="{VIEWBOX}" height="{VIEWBOX}" fill="#FAFAF8"/>']
    el.append(f'<circle cx="{CX}" cy="{CY}" r="{B["zodiacOuter"]}" fill="none" stroke="#DEDED7"/>')
    el.append(f'<circle cx="{CX}" cy="{CY}" r="{B["zodiacInner"]}" fill="none" stroke="#DEDED7"/>')
    for i in range(12):
        a = project(i * 30, B["zodiacInner"], asc)
        b = project(i * 30, B["zodiacOuter"], asc)
        el.append(f'<line x1="{a[0]:.3f}" y1="{a[1]:.3f}" x2="{b[0]:.3f}" y2="{b[1]:.3f}" stroke="#DEDED7"/>')
        c = pos["signs"][i]
        el.append(f'<text x="{c[0]:.3f}" y="{c[1]:.3f}" font-size="30" text-anchor="middle" '
                  f'dominant-baseline="central" fill="#232A38">{SIGN_UNI[i]}</text>')
    for cu in pos["cusps"]:
        el.append(f'<line x1="{cu["inner"][0]:.3f}" y1="{cu["inner"][1]:.3f}" '
                  f'x2="{cu["outer"][0]:.3f}" y2="{cu["outer"][1]:.3f}" stroke="#E8E8E1"/>')
        el.append(f'<text x="{cu["num"][0]:.3f}" y="{cu["num"][1]:.3f}" font-size="13" '
                  f'text-anchor="middle" dominant-baseline="central" fill="#9CA0A8">{cu["house"]}</text>')
    el.append(f'<circle cx="{CX}" cy="{CY}" r="{B["hub"]}" fill="none" stroke="#DEDED7"/>')
    for h in pos["hub"]:
        col = "#2E4A7D" if h["type"] in ("square", "opposition", "conjunction") else "#C7CABF"
        el.append(f'<line x1="{h["a"][0]:.3f}" y1="{h["a"][1]:.3f}" x2="{h["b"][0]:.3f}" '
                  f'y2="{h["b"][1]:.3f}" stroke="{col}" stroke-opacity="0.6"/>')
    for pl in pos["planets"]:
        g = pl["glyph"]
        el.append(f'<text x="{g[0]:.3f}" y="{g[1]:.3f}" font-size="30" text-anchor="middle" '
                  f'dominant-baseline="central" fill="#232A38">{UNI[pl["name"]]}</text>')
    el.append("</svg>")
    return "\n".join(el)


def main():
    argv = sys.argv[1:]
    chart_path = "../d_layer/chart.json"
    mode = positions_out = svg_out = None
    i = 0
    while i < len(argv):
        t = argv[i]
        if t == "--positions":
            mode, positions_out = "positions", argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else None
            if positions_out:
                i += 1
        elif t == "--svg":
            mode, svg_out = "svg", argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else None
            if svg_out:
                i += 1
        elif not t.startswith("--"):
            chart_path = t
        i += 1

    with open(chart_path, encoding="utf-8") as f:
        chart = json.load(f)

    if mode == "svg":
        out = svg(chart)
        if svg_out:
            open(svg_out, "w", encoding="utf-8").write(out)
        else:
            sys.stdout.write(out)
    else:
        out = json.dumps(positions(chart), indent=2)
        if positions_out:
            open(positions_out, "w", encoding="utf-8").write(out)
        else:
            sys.stdout.write(out)


if __name__ == "__main__":
    main()
