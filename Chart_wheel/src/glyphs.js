// CHART_WHEEL_SPEC.md §4 — bundled SVG glyph defs.
// Original hand-authored vector forms (no Unicode astro chars, no system fonts).
// Each glyph is drawn in a 0..100 box centred on (50,50) and exposed as a
// <symbol viewBox="0 0 100 100">. Geometry inherits `currentColor` so colour
// is driven entirely by the §7 theme tokens via the consuming class.
//
// Provenance (cite in PR): forms are simplified renditions of the standard
// astronomical/astrological symbols, redrawn from scratch as stroke paths for
// this renderer — not extracted from any font. Released under the repo licence.

// Inner markup per glyph key. Wrapped at build time in a stroke group.
const GLYPH_PATHS = {
  // ---- luminaries & planets ----
  sun: '<circle cx="50" cy="50" r="30"/><circle cx="50" cy="50" r="4.5" fill="currentColor" stroke="none"/>',
  moon: '<path d="M60,18 A36,36 0 1 0 60,82 A30,30 0 1 1 60,18 Z" fill="currentColor" stroke="none"/>',
  mercury:
    '<path d="M37,21 A14,14 0 0 0 63,21"/>' +
    '<circle cx="50" cy="46" r="14"/>' +
    '<path d="M50,60 L50,86 M37,73 L63,73"/>',
  venus:
    '<circle cx="50" cy="37" r="16"/>' +
    '<path d="M50,53 L50,87 M36,71 L64,71"/>',
  mars:
    '<circle cx="44" cy="58" r="16"/>' +
    '<path d="M55,47 L78,24 M78,24 L62,24 M78,24 L78,40"/>',
  jupiter:
    '<path d="M31,33 C31,19 53,19 53,35 C53,46 42,49 36,49"/>' +
    '<path d="M53,35 L53,85 M39,79 L69,79"/>',
  saturn:
    '<path d="M29,28 L53,28 M42,20 L42,58 C42,82 70,80 63,57"/>',
  uranus:
    '<path d="M34,26 L34,58 M66,26 L66,58 M34,42 L66,42 M50,42 L50,69"/>' +
    '<circle cx="50" cy="77" r="8"/>',
  neptune:
    '<path d="M32,24 L32,47 M68,24 L68,47 M50,24 L50,86"/>' +
    '<path d="M30,45 Q50,62 70,45"/>' +
    '<path d="M38,74 L62,74"/>',
  pluto:
    '<circle cx="50" cy="33" r="10"/>' +
    '<path d="M33,40 A17,17 0 0 0 67,40"/>' +
    '<path d="M50,57 L50,87 M38,73 L62,73"/>',
  // ---- lunar nodes ----
  'node-n':
    '<path d="M31,74 C31,30 69,30 69,74"/>' +
    '<circle cx="31" cy="78" r="6"/><circle cx="69" cy="78" r="6"/>',
  'node-s':
    '<path d="M31,26 C31,70 69,70 69,26"/>' +
    '<circle cx="31" cy="22" r="6"/><circle cx="69" cy="22" r="6"/>',
  // ---- zodiac signs (index 0 = Aries) ----
  aries: '<path d="M50,78 L50,40 C50,23 33,23 33,43 C33,54 42,56 47,49 M50,40 C50,23 67,23 67,43 C67,54 58,56 53,49"/>',
  taurus: '<circle cx="50" cy="64" r="18"/><path d="M27,46 A26,22 0 0 1 73,46"/>',
  gemini: '<path d="M36,26 L36,74 M64,26 L64,74 M30,28 Q50,19 70,28 M30,72 Q50,81 70,72"/>',
  cancer:
    '<path d="M45,42 C61,42 65,29 50,27"/>' +
    '<path d="M55,58 C39,58 35,71 50,73"/>' +
    '<circle cx="38" cy="42" r="7" fill="currentColor" stroke="none"/>' +
    '<circle cx="62" cy="58" r="7" fill="currentColor" stroke="none"/>',
  leo: '<path d="M41,55 A11,11 0 1 1 53,44 C53,30 35,30 35,52 C35,72 57,74 66,58"/>',
  virgo: '<path d="M30,30 L30,74 M30,35 C30,28 44,28 44,40 L44,74 M44,35 C44,28 58,28 58,40 L58,72 M58,58 C58,46 76,46 73,64 C71,77 57,73 53,64"/>',
  libra: '<path d="M26,74 L74,74 M26,57 L39,57 A13,13 0 0 1 61,57 L74,57"/>',
  scorpio: '<path d="M30,30 L30,74 M30,35 C30,28 44,28 44,40 L44,74 M44,35 C44,28 58,28 58,40 L58,74 L72,74 M72,74 L62,69 M72,74 L75,62"/>',
  sagittarius: '<path d="M28,74 L72,32 M72,32 L54,34 M72,32 L70,50 M43,45 L61,63"/>',
  capricorn: '<path d="M27,34 L41,62 C45,70 53,67 51,57 L45,40 C43,32 53,30 57,40 C64,58 50,74 35,69"/>',
  aquarius: '<path d="M27,46 L37,40 L47,46 L57,40 L67,46 M27,60 L37,54 L47,60 L57,54 L67,60"/>',
  pisces: '<path d="M34,26 C24,40 24,60 34,74 M66,26 C76,40 76,60 66,74 M34,50 L66,50"/>',
  // ---- retrograde mark (vector ℞), tiny ----
  retro: '<path d="M30,24 L30,76 M30,24 L52,24 C66,24 66,48 52,48 L30,48 M44,48 L66,76"/>',
};

// Default stroke language: hairline-matched, round caps/joins (§7).
const STROKE_W = 7;

export function glyphDefs() {
  return Object.entries(GLYPH_PATHS)
    .map(
      ([key, body]) =>
        `<symbol id="g-${key}" viewBox="0 0 100 100" overflow="visible">` +
        `<g fill="none" stroke="currentColor" stroke-width="${STROKE_W}" ` +
        `stroke-linecap="round" stroke-linejoin="round">${body}</g></symbol>`
    )
    .join('');
}

export const GLYPH_KEYS = Object.keys(GLYPH_PATHS);
