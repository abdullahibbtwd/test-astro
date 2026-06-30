# Chart wheel renderer

Deterministic SVG renderer for the user-facing natal chart wheel, per
[`CHART_WHEEL_SPEC.md`](CHART_WHEEL_SPEC.md). Pure function of `chart.json`:
same input → byte-identical output. No LLM, no network, no fonts, no Unicode
glyphs.

```
chart.json ──▶ renderChart() ──▶ self-contained <svg>  (+ §8 invariant gate)
```

## Usage

```bash
# render the default chart to stdout
node cli.js

# render a specific chart to a file, dark theme
node cli.js ../d_layer/chart.json --theme dark --out wheel-dark.svg

# render AND run the §8 invariant gate (exit 1 on any violation)
node cli.js path/to/chart.json --check --out wheel.svg

# optional §9 layers (off by default)
node cli.js chart.json --degree-labels   # static per-glyph degree labels
node cli.js chart.json --applying         # applying/separating chord styling

# tests: invariant gate + geometry regression vs the Python oracle
npm test
```

Library entry point:

```js
import { renderChart } from './src/render.js';
const svg = renderChart(chart, { theme: 'light' });
```

`renderChart(chart, opts)` options (all default to the §9 v1 decisions):
`theme` `'light'|'dark'`, `degreeLabels` `false`, `applyingStyle` `false`,
`fortune` `false`, `highlight` `null` (deferred grounded-layer seam, §9).

## Layout

```
src/constants.js   §3/§4/§5/§7 — the single constants block (band radii, etc.)
src/transform.js   §3 — the LOCKED coordinate transform (the only coord system)
src/glyphs.js      §4 — bundled vector glyph defs (signs, planets, nodes, ℞)
src/theme.js       §7 — CSS-variable tokens, light + dark presets
src/spread.js      §4 — glyph collision / spreading pass
src/render.js      the engine: renderChart(chart, opts) -> svg string
src/invariants.js  §8 — determinism & invariant gate
cli.js             render + gate CLI
render_wheel.py    §11 — Python geometry oracle (NOT the engine)
test/wheel.test.js invariant gate + §11 oracle regression (within 1px)
```

## PR notes (required by the spec)

- **Glyph set (§4).** The 12 signs, 10 planets, both nodes, and the ℞ mark are
  **original stroke-path vectors authored for this renderer** in
  [`src/glyphs.js`](src/glyphs.js) — simplified renditions of the standard
  astronomical/astrological symbols, redrawn from scratch (not extracted from
  any font), released under this repo's licence. They are bundled `<symbol>`
  defs and inherit `currentColor`; **no Unicode astro characters and no system
  astro fonts** appear in production output (§4, §11).
- **Type faces (§7).** Glyph/data/axis roles all resolve through the
  `--glyph-font` / `--axis-font` tokens. The chosen face is **Inter** — an open,
  low-contrast humanist sans that harmonises with the Turkish reading body text
  rather than fighting it — with a system humanist fallback stack so the SVG
  still renders standalone. Swap faces in one place ([`src/theme.js`](src/theme.js)).
- **Soft-aspect floor (§5).** Implemented: soft-chord opacity is clamped to
  `>= 0.40` so the grey hub never reads one-sided (the mock's omission is fixed).
- **Spreader generalises §4's per-cluster description.** §4 sketches "cluster,
  then redistribute about the cluster mean." A naive literal implementation can
  push one stellium into an adjacent one and **violate the §8.5 floor** (seen on
  a real chart with two adjacent Capricorn/Sagittarius clusters). We implement
  the globally optimal form of the same idea — minimise total angular
  displacement subject to a hard `>= min_sep` constraint, solved by
  pool-adjacent-violators (isotonic regression). Merged blocks *are* clusters
  centred on their mean, pointers stay anchored to true longitude, and the §8.5
  invariant now holds for arbitrary charts. See [`src/spread.js`](src/spread.js).
- **Theming.** All colour/stroke/font come from §7 CSS custom properties on the
  SVG root; no colour literals in geometry code. Ships light + dark presets.

## §11 — relationship to the reference renderer

[`render_wheel.py`](render_wheel.py) is the **geometry oracle, not the engine**.
It proves the §3 transform and §7 band proportions for a single chart and is used
by the test suite to regression-check the engine's glyph/cusp/axis/hub positions
to within 1px. The engine closes every §11 difference: bundled vector glyphs (the
oracle uses Unicode stand-ins), CSS-token theming (the oracle hardcodes hex), the
soft-aspect floor, the §9 flags/optional layers, the §8 invariant gate, and
generality (pure function of arbitrary `chart.json`).

## §8 invariant gate (the build fails on violation)

1. Determinism — same chart → byte-identical SVG.
2. Completeness — every §2 body present is rendered exactly once.
3. Aspect fidelity — every `modern` relation once; **zero** `whole_sign`.
4. Anchor — Ascendant within `0.01°` of screen-left.
5. No overlap — no two glyph centres closer than `min_sep` after spreading.
6. Node ℞ — no retrograde mark on either node.
7. Mask — the serialized SVG contains none of the tradition-marker substrings.

Run it with `node cli.js <chart.json> --check` or `npm test`.
