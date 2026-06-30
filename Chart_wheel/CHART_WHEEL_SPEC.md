# CHART_WHEEL_SPEC.md

Renderer spec for the user-facing natal chart wheel. Implementation target: a coding agent.

---

## 0. Nature & ethos

The wheel is a **deterministic SVG render of `chart.json`**. No LLM in the loop. Same input → same output. It is to L1 what the L4 reading is to its inputs: re-runnable, auditable, byte-stable.

It is a **user-facing** surface, shipped beside the reading. Two hard product constraints follow:

1. **Tradition mask.** The wheel presents one coherent surface. Nothing on it is labelled "modern", "classical", "whole sign", "Placidus", "triplicity", "dignity", or any tradition marker. All dual-tradition machinery in `chart.json` (whole-sign sectors/cusps/relations, Lot of Spirit, dignity classifications, planetary day/hour) is **excluded** from the default render. See §8 mask check.
2. **Aesthetic, on-brand, themeable.** Vector output, CSS-variable theming, crisp on web + mobile.

---

## 1. Input contract

Single input: `chart.json` (L1 output). The renderer is **pure**: it reads only the fields below and nothing else. Fields not listed here are deliberately ignored.

### Consumed

| Path | Use |
|---|---|
| `points[]` | bodies to plot — see §2 for which |
| `points[].name` | glyph + label key |
| `points[].longitude` | angular position (the only positional source) |
| `points[].degree_in_sign` | optional numeric label |
| `points[].retrograde` | ℞ mark (suppressed on nodes — see §4) |
| `points[].sign` / `sign_index` | sanity only; position comes from `longitude` |
| `axes.ascendant.longitude` | wheel rotation anchor |
| `axes.mc.longitude` | MC line |
| `sectors.placidus_cusps[12]` | house cusp lines + house numbering |
| `relations[]` where `scheme == "modern"` | aspect lines (carries `type`, `orb`, `applying`) |
| `points[].sector.placidus` | **tap/hover panel only** (§9 house number) — never affects geometry |

### Ignored (mask / out of scope for v1)

`meta.*`, `confidence`, `points[].traditional`, `points[].speed`, `points[].sector.whole_sign`, `points[].classifications.*`, `sectors.whole_sign_cusps`, `sector_rulers.*`, `derived_points.spirit`, `planetary_day`, `planetary_hour`, `is_diurnal`, and **all `relations[]` where `scheme == "whole_sign"`**.

> The renderer **must not** read `whole_sign_cusps`, any `whole_sign` relation, or any `classifications` field. Reading them risks them leaking into output and breaking the mask.

---

## 2. What is plotted

**Bodies (from `points[]`, matched by `name`):**

Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn — traditional seven.
Uranus, Neptune, Pluto — modern outers.
North Node — always.
South Node — **product decision pending (§9)**; default render = faint.

There is no Chiron in the data; do not invent one.

**Axes:** Ascendant (Asc) and Midheaven (MC), drawn as labelled lines from rim to centre. Descendant and IC are the opposite ends of the same two lines — draw the full diameters, label the four ends (Asc left, Desc right, MC and IC at their true positions).

**Houses:** 12 cusp lines from `placidus_cusps`. Cusp `[0]` = 1st house = Ascendant.

**Aspects:** modern-scheme relations only (§5).

**Optional, off by default (§9):** Lot of Fortune (`derived_points.fortune`); per-glyph `degree_in_sign` numeric labels.

---

## 3. Geometry — coordinate transform (LOCKED)

Convention: **equal 30° zodiac ring, rotated so the Ascendant sits at screen-left.** This matches the default astro.com round wheel and is fully deterministic. Houses (Placidus) are unequal and drawn at true longitude; the MC therefore floats near — not forced to — the top. Do **not** force MC to 12 o'clock (that requires distorting the sign ring).

Let centre be `(cx, cy)`, outer radius `R`. Screen angle is measured counterclockwise from east (right = 0°, up = 90°, left = 180°, down = 270°):

```
theta_screen(lambda) = (180 + (lambda - asc_longitude)) mod 360
x(lambda, r) = cx + r * cos(theta_screen * pi/180)
y(lambda, r) = cy - r * sin(theta_screen * pi/180)     # note the minus: SVG y grows downward
```

Checks the implementation must satisfy:
- `lambda == asc_longitude` → `theta == 180` (Ascendant at left). 
- `lambda == asc_longitude + 180` → Descendant at right.
- Ecliptic longitude increases counterclockwise on screen (Aries→Taurus→… runs CCW).

All bodies, cusps, axes, and aspect endpoints use this one transform. No second coordinate system anywhere.

---

## 4. Radial band layout (outer → inner)

Bands as fractions of `R`. Tune visually, but keep order and non-overlap.

| Band | Radius | Contents |
|---|---|---|
| Zodiac ring | 0.88 – 1.00 | 12 equal sign sectors, sign glyphs centred, thin boundary spokes every 30° |
| Degree ticks | 0.85 – 0.88 | 1° ticks, heavier at 5°/10° |
| House ring | 0.62 – 0.85 | cusp lines drawn here inward to hub; house numbers 1–12 placed just inside each cusp, in the *middle* of each house arc |
| Planet ring | ~0.74 (glyph centre band) | planet/point glyphs, each with a thin **pointer line** to its exact degree on the zodiac inner edge (0.85) |
| Aspect hub | 0.00 – 0.50 | aspect chords (§5) between planet true-longitude points on the hub circle |

**Glyphs are bundled SVG `<path>`/`<symbol>` defs — never Unicode characters and never system astro fonts** (they render inconsistently across platforms). Required glyph set: 10 planets, N Node (and S Node), Asc/MC labels, 12 sign glyphs. Source an open-licensed vector set; reference it in the PR.

**Retrograde:** append the ℞ mark to a glyph **iff** `retrograde == true` AND the point is a planet. **Suppress ℞ on North Node and South Node** — mean nodes are always retrograde and the mark is conventionally omitted (otherwise every chart looks broken).

### Glyph collision / spreading pass (the one fiddly part)

Planets within a small angular gap (default **6°**) collide on the rim. Algorithm:
1. Sort plotted points by `longitude`.
2. Walk the sorted ring; group any run where consecutive gaps `< min_sep` (6°) into a cluster (wrap-aware at 360/0).
3. Within a cluster, redistribute glyph *display* angles to `min_sep` spacing, centred on the cluster's mean longitude.
4. Keep each glyph's **pointer line** anchored to its **true** longitude on the zodiac inner edge, so the real degree is never lost.

This chart has a Sun/Jupiter pair ~1.1° apart (Cancer) — exercise the spreader against it.

---

## 5. Aspects (modern scheme only)

Source: `relations[]` filtered to `scheme == "modern"`. Each carries `type`, `orb`, `applying`. Render as a chord between the two bodies' points on the hub circle (radius ≤ 0.50).

**Colour by family** (via CSS vars, §7):
- Hard — `square`, `opposition` → `--aspect-hard`
- Soft — `trine`, `sextile` → `--aspect-soft`
- `conjunction` → `--aspect-conj` (neutral/accent)

**Weight / opacity by tightness:** map `orb` → visual strength so tight aspects read bolder. `strength = 1 - min(orb, max_orb)/max_orb`, `max_orb = 8` (one constants block; no inline magic numbers). Reference mapping the mock validated:
- Hard / conjunction: `opacity = 0.30 + 0.55*strength`, `stroke-width = 0.7 + 1.5*strength`
- Soft: `opacity = 0.45 + 0.45*strength`, `stroke-width = 0.6 + 1.0*strength`

**Soft-aspect floor (required).** Wide soft aspects fall below visual threshold and the hub reads one-sided. Clamp soft-aspect opacity to a minimum (`>= 0.40`) so the hub stays balanced even when the soft set is loose. The mock omitted this and the grey chords nearly vanished — do not repeat.

**Near-zero chord:** a tight conjunction (e.g. this chart's Sun–Jupiter ~1.1°) projects to an almost zero-length chord at the hub. Don't special-case it into a dot; let it render as the short line it is. Just confirm it doesn't divide-by-zero in any normalised-direction math.

`applying` is available — optional subtle styling (e.g. applying solid / separating slightly dashed). Off by default; expose as a flag.

Do **not** render any `whole_sign` relation.

---

## 6. Output

- One **self-contained SVG** (defs + styles inline; no external fetches).
- `viewBox="0 0 1000 1000"`, `preserveAspectRatio="xMidYMid meet"`; responsive to container.
- Accessibility: `<title>` and `<desc>`; `role="img"`; `aria-label` summarising the chart in **neutral, unlabelled** language (no tradition terms — mask applies to a11y text too).
- Numeric coordinates rounded to **3 decimals** for byte-stable diffs.

---

## 7. Visual direction (LOCKED) — "quiet modern-minimal"

Decided aesthetic, validated against the reference mock. The engine implements this; it does not invent a look. The discipline: **everything radial is whisper-hairline; the aspect hub is the single expressive element.** Spend boldness only there.

**Palette** (deliberately not the cream/terracotta or night-sky defaults):

```
--bg            #FAFAF8   /* cool porcelain ground */
--ink           #232A38   /* deep blue-grey: glyphs, axes */
--hair          #DEDED7   /* zodiac ring, ticks, spokes, pointers */
--house-line    #E8E8E1   /* cusp lines — lighter than --hair */
--house-num     #9CA0A8
--glyph-retro   #9A9A92
--accent        #2E4A7D   /* Iznik indigo — the ONE accent */
--aspect-hard   var(--accent)
--aspect-conj   var(--accent)
--aspect-soft   #C7CABF   /* pale grey-green */
--highlight     /* §9 grounded layer; derive from --accent at full strength */
```

The accent is an Ottoman-tilework indigo used **only** in the aspect hub (and the §9 highlight). It must never appear on rings, glyphs, or labels — that's what keeps it the signature instead of decoration. One accent, one job.

**Type roles** (three, all via tokens; production replaces the mock's system stack with the chosen faces):
- *Glyphs* — light-to-regular humanist sans, generous size (~30px on the 1000 viewBox), matched in weight to the hairline language.
- *Data / house numbers / degrees* — same family, smaller, lighter (~13px), slight letter-spacing on numerals.
- *Axis labels (AC/DC/MC/IC)* — uppercase, wide letter-spacing (~2px), `--ink`.

Pick real faces deliberately — not the system default. The wheel sits beside Turkish reading text, so the glyph face should harmonise with that body face rather than fight it. Name the choice in the PR.

**Signature rule:** the indigo aspect web is the focal moment. It earns that by contrast with the silence around it — so hold the line on hairline weights everywhere else. If the rest of the wheel starts competing for attention, the signature is lost.

**Theming mechanics:** all colour, stroke, and font via CSS custom properties on the SVG root, with fallbacks. No colour literals in geometry code — tokens only. Ship light (above) + a dark preset (invert ground to a deep blue-grey, lift hairlines, keep the same indigo accent which reads well on dark).

**Band radii (validated defaults, 1000×1000 viewBox, R=460):** zodiac 410–460 · sign glyphs r=435 · ticks 398–410 · planet glyphs r=358 · pointer top r=408 · house cusps 396→236 · house numbers r=252 · hub circle r=236. These are the mock's proven proportions — start here, tune visually, keep the order and non-overlap from §4.

---

## 8. Determinism & invariants (validation gate)

The renderer ships with a check that fails the build on violation:

1. **Determinism** — same `chart.json` → byte-identical SVG (after 3-decimal rounding).
2. **Completeness** — every body listed in §2 that exists in `points[]` is rendered exactly once.
3. **Aspect fidelity** — every `scheme=="modern"` relation rendered exactly once; **zero** `whole_sign` relations rendered.
4. **Anchor** — Ascendant within `0.01°` of screen-left (180°).
5. **No overlap** — after the spreading pass, no two glyph centres closer than `min_sep`.
6. **Node ℞** — no ℞ mark on North or South Node.
7. **Mask check** — the serialized SVG string contains none of: `modern`, `classical`, `whole`, `placidus`, `triplicity`, `dignity`, `domicile`, `detriment`, `exalt`, `fall`, `bound`, `face`, `spirit`, `planetary day`, `planetary hour` (case-insensitive). This is the leak tripwire.

---

## 9. Product decisions (LOCKED for v1)

Settled. Build to these.

- **South Node** — **show, faint.** Render the glyph at low contrast (a notch below the planet glyphs). It's the standard modern North/South axis; suppress its ℞ mark per §4.
- **Lot of Fortune** — **off.** Do not render `derived_points.fortune` in v1. Revisit only when the reading interprets it.
- **Per-glyph degree labels** — **off on the static face; available on tap/hover.** The wheel stays clean; detail is revealed interactively. See data-hook requirement below.
- **Applying/separating aspect styling** — **off.** The hub encodes exactly one variable (orb tightness → boldness). Do not add a second encoding to the chords. `applying` stays unused in v1.
- **Grounded-placement highlight layer** — **deferred.** Keep the decoupled input contract (below) in the design so it slots in later, but do not build it for v1. (Blocked on L4 reliably emitting grounded placements *and* on the open pathology-framing grounding fix — highlighting mis-grounded material would be worse than not highlighting.)

### Tap/hover detail (required for v1, supports the degree-label decision)

The static SVG carries no degree text, but the engine must make per-point detail available to the host component without re-parsing the chart. For each plotted point and axis, emit structured hooks on the SVG node — e.g. `data-point="Sun" data-degree="21.04" data-sign="Cancer" data-house="7"` (Placidus house from `points[].sector.placidus`). The host renders the reveal panel (e.g. "Sun · 21° Cancer · 7th house") on tap (mobile) / hover (desktop).

Keep the panel text **neutral and unlabelled** — the §8.7 mask applies here too (no "Placidus", no tradition terms; "7th house" is fine, "Placidus 7th" is not). The SVG itself stays free of the degree text so the static render and its byte-stable diff are unaffected.

> Note: `points[].sector.placidus` is read **only** to populate this hook. It does not affect geometry (positions come from `longitude`). This is the one sanctioned use of a `sector` field.

### Grounded-highlight layer (decoupled contract — deferred, keep the seam)

If/when shipped: the wheel optionally accepts a second input — a flat list of IDs to emphasise, e.g.

```json
{ "highlight_points": ["Sun", "Saturn"], "highlight_relations": [["Sun","Saturn","opposition"]] }
```

Highlighted glyphs/chords render with `--highlight`; everything else dims slightly. The renderer treats this as opaque data and never computes it — it comes from L3/L4 (which placements the reading actually grounded on). Keeping it a separate input means the wheel never depends on the reading pipeline and can ship before it.

---

## 10. Build order (suggested)

1. Transform + zodiac ring + axes (verify Asc-left against this chart).
2. House cusps + numbering.
3. Planet ring + glyphs + pointers (no spreading yet).
4. Spreading pass (verify on Sun/Jupiter ~1.1°).
5. Aspect hub (modern filter).
6. Theming tokens + light/dark.
7. Invariant gate (§8).
8. Optional layers behind flags (§9).

---

## 11. Reference renderer (geometry oracle, NOT the engine)

A throwaway Python script (`render_wheel.py`) renders one chart to prove the §3 transform and the §7 band proportions. It is the **geometry oracle**: for any given `chart.json`, the engine's glyph/cusp/axis/hub positions must match the reference within `0.1°` / `1px`. Use it to regression-check the engine.

It is **not** the production engine and must not be ported as-is. Differences the engine must close:

- **Glyphs** — reference uses Unicode characters as stand-ins; engine uses bundled vector `<path>`/`<symbol>` defs (§4). No Unicode astro characters in production output.
- **Theming** — reference hardcodes hex; engine drives everything from §7 CSS tokens with light/dark presets.
- **Soft-aspect floor** — reference omits it (grey chords vanish); engine must clamp per §5.
- **Flags & optional layers** — reference has none; engine implements §9 behind flags.
- **Invariant gate** — reference has none; engine ships §8.
- **Generality** — reference is single-chart; engine is a pure function of arbitrary `chart.json` with the §1 contract.

Treat the reference as "this is the geometry you must reproduce," not "this is the code you ship."
