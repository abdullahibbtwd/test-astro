// CHART_WHEEL_SPEC.md §3/§4/§5/§7 — the single constants block.
// No magic numbers anywhere downstream; everything geometric lives here.

// Canvas (§6)
export const VIEWBOX = 1000;
export const CX = 500;
export const CY = 500;
export const R = 460;

// Radial bands as absolute radii on the 1000 viewBox (§7 validated defaults).
// Order + non-overlap are load-bearing (§4); tune values, keep the order.
export const BANDS = {
  zodiacOuter: 460, // zodiac ring 0.88–1.00
  zodiacInner: 410,
  signGlyph: 435, // sign glyph centre band
  tickOuter: 410, // degree ticks 0.85–0.88
  tickInner: 398,
  pointerTop: 408, // pointer anchor on zodiac inner edge (true longitude)
  planetGlyph: 358, // planet/point glyph centre band (~0.78)
  houseCuspOuter: 396, // cusp lines drawn from here…
  houseCuspInner: 236, // …inward to the hub
  houseNum: 252, // house numbers, middle of each arc
  hub: 236, // aspect hub circle (chord endpoints), ≤ 0.50·R
};

// Tick marks (§4)
export const DEGREE_TICK = {
  minor: { inner: 405, outer: 410 }, // every 1°
  major: { inner: 400, outer: 410 }, // every 5°
  bold: { inner: 398, outer: 410 }, // every 10°
};

// Glyph display sizes on the viewBox (§7: glyphs ~30px, generous)
export const GLYPH_SIZE = {
  planet: 34,
  sign: 36,
  node: 34,
  retroOffset: 13, // ℞ mark offset from glyph centre
  retroSize: 15,
};

// Pointer line: glyph-side anchor sits just outside the glyph band.
export const POINTER_GLYPH_R = BANDS.planetGlyph + 16; // 374

// §4 spreading pass
export const MIN_SEP = 6; // degrees — collision threshold + post-spread floor

// §5 aspect strength mapping (one block; no inline magic numbers)
export const ASPECT = {
  maxOrb: 8,
  hard: { opacityBase: 0.3, opacitySpan: 0.55, widthBase: 0.7, widthSpan: 1.5 },
  soft: { opacityBase: 0.45, opacitySpan: 0.45, widthBase: 0.6, widthSpan: 1.0 },
  softFloor: 0.4, // required minimum opacity for soft chords (§5)
};

// Aspect family → CSS var (§5/§7). Hard = square/opposition, soft = trine/sextile.
export const ASPECT_FAMILY = {
  square: 'hard',
  opposition: 'hard',
  trine: 'soft',
  sextile: 'soft',
  conjunction: 'conj',
};
export const ASPECT_VAR = {
  hard: '--aspect-hard',
  soft: '--aspect-soft',
  conj: '--aspect-conj',
};

// §2 — bodies plotted, in canonical render order (matched by points[].name).
export const PLOTTED_BODIES = [
  'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
  'Uranus', 'Neptune', 'Pluto', 'North Node', 'South Node',
];
export const PLANETS = new Set([
  'Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
  'Uranus', 'Neptune', 'Pluto',
]);
export const NODES = new Set(['North Node', 'South Node']);

// Glyph key per body name (maps to symbol ids in glyphs.js)
export const BODY_GLYPH = {
  Sun: 'sun', Moon: 'moon', Mercury: 'mercury', Venus: 'venus', Mars: 'mars',
  Jupiter: 'jupiter', Saturn: 'saturn', Uranus: 'uranus', Neptune: 'neptune',
  Pluto: 'pluto', 'North Node': 'node-n', 'South Node': 'node-s',
};

// 12 sign glyph keys, indexed by sign_index (0 = Aries spanning longitude 0–30°)
export const SIGN_GLYPHS = [
  'aries', 'taurus', 'gemini', 'cancer', 'leo', 'virgo',
  'libra', 'scorpio', 'sagittarius', 'capricorn', 'aquarius', 'pisces',
];
