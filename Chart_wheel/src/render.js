// CHART_WHEEL_SPEC.md — the production engine.
// Pure function: renderChart(chart, opts) -> self-contained SVG string.
// Reads ONLY the §1 "Consumed" fields. Never touches masked fields.
import {
  VIEWBOX, CX, CY, BANDS, DEGREE_TICK, GLYPH_SIZE, POINTER_GLYPH_R,
  ASPECT, ASPECT_FAMILY, ASPECT_VAR, PLOTTED_BODIES, PLANETS, NODES,
  BODY_GLYPH, SIGN_GLYPHS,
} from './constants.js';
import { project, num, arcMidpoint, mod360 } from './transform.js';
import { glyphDefs } from './glyphs.js';
import { themeStyle } from './theme.js';
import { spread } from './spread.js';

const SIGNS = [
  'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces',
];
const signFromLon = (lon) => SIGNS[Math.floor(mod360(lon) / 30)];
const degInSign = (lon) => mod360(lon) % 30;

// ---- small SVG emitters (all coords pre-rounded) ----
const P = (lon, r, asc) => {
  const { x, y } = project(lon, r, asc);
  return { x: num(x), y: num(y) };
};
const line = (a, b, cls, extra = '') =>
  `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="${cls}"${extra ? ' ' + extra : ''}/>`;
const circle = (cx, cy, r, cls, extra = '') =>
  `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(r)}" class="${cls}"${extra ? ' ' + extra : ''}/>`;
const useGlyph = (key, cx, cy, size, cls) => {
  const s = num(size);
  return `<use href="#g-${key}" x="${num(cx - size / 2)}" y="${num(cy - size / 2)}" width="${s}" height="${s}" class="${cls}"/>`;
};
const text = (x, y, cls, body, extra = '') =>
  `<text x="${num(x)}" y="${num(y)}" text-anchor="middle" dominant-baseline="central" class="${cls}"${extra ? ' ' + extra : ''}>${body}</text>`;
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export function renderChart(chart, opts = {}) {
  const o = {
    theme: 'light',
    degreeLabels: false, // §9 off; available on tap/hover via data hooks
    fortune: false, // §9 off
    applyingStyle: false, // §9 off — hub encodes exactly one variable
    highlight: null, // §9 deferred grounded layer — seam kept, off by default
    ...opts,
  };
  const asc = chart.axes.ascendant.longitude;
  const layers = [];

  // ---------- zodiac ring (§4: 0.88–1.00) ----------
  const ring = [];
  ring.push(circle(CX, CY, BANDS.zodiacOuter, 'cw-hair'));
  ring.push(circle(CX, CY, BANDS.zodiacInner, 'cw-hair'));
  for (let i = 0; i < 12; i++) {
    const lon = i * 30; // sign boundary spokes every 30°
    ring.push(line(P(lon, BANDS.zodiacInner, asc), P(lon, BANDS.zodiacOuter, asc), 'cw-hair'));
    const mid = P(i * 30 + 15, BANDS.signGlyph, asc);
    ring.push(useGlyph(SIGN_GLYPHS[i], mid.x, mid.y, GLYPH_SIZE.sign, 'cw-glyph'));
  }
  layers.push(`<g class="cw-zodiac">${ring.join('')}</g>`);

  // ---------- degree ticks (§4: 0.85–0.88) ----------
  const ticks = [];
  for (let d = 0; d < 360; d++) {
    let band = DEGREE_TICK.minor;
    if (d % 10 === 0) band = DEGREE_TICK.bold;
    else if (d % 5 === 0) band = DEGREE_TICK.major;
    ticks.push(line(P(d, band.inner, asc), P(d, band.outer, asc), 'cw-hair'));
  }
  layers.push(`<g class="cw-ticks">${ticks.join('')}</g>`);

  // ---------- house cusps + numbering (§4: 0.62–0.85) ----------
  const cusps = chart.sectors?.placidus_cusps;
  if (Array.isArray(cusps) && cusps.length === 12) {
    const houses = [];
    for (let i = 0; i < 12; i++) {
      houses.push(line(P(cusps[i], BANDS.houseCuspInner, asc), P(cusps[i], BANDS.houseCuspOuter, asc), 'cw-house-line'));
    }
    for (let i = 0; i < 12; i++) {
      const mid = arcMidpoint(cusps[i], cusps[(i + 1) % 12]);
      const pos = P(mid, BANDS.houseNum, asc);
      houses.push(text(pos.x, pos.y, 'cw-house-num', String(i + 1), 'font-size="13"'));
    }
    layers.push(`<g class="cw-houses">${houses.join('')}</g>`);
  }

  // ---------- aspect hub (§5) ----------
  layers.push(renderHub(chart, asc, o));

  // ---------- axes (§2): full diameters Asc–Desc, MC–IC ----------
  const mc = chart.axes.mc.longitude;
  const axisLines = [
    line(P(asc, BANDS.zodiacInner, asc), P(asc + 180, BANDS.zodiacInner, asc), 'cw-axis-line'),
    line(P(mc, BANDS.zodiacInner, asc), P(mc + 180, BANDS.zodiacInner, asc), 'cw-axis-line'),
  ];
  layers.push(`<g class="cw-axes">${axisLines.join('')}</g>`);

  // ---------- planets / points (§4) ----------
  layers.push(renderPoints(chart, asc, o));

  // ---------- axis labels on top (§7: AC/DC/MC/IC uppercase, wide) ----------
  // Sit just outside the rim so a body conjunct an angle never collides with
  // its label (e.g. a planet on the MC).
  const labelR = 478;
  const axisLabels = [
    axisHook('Ascendant', 'AC', asc, chart.axes.ascendant, labelR, asc),
    axisHook('Descendant', 'DC', asc + 180, null, labelR, asc),
    axisHook('Midheaven', 'MC', mc, chart.axes.mc, labelR, asc),
    axisHook('Imum Coeli', 'IC', mc + 180, null, labelR, asc),
  ];
  layers.push(`<g class="cw-axis-labels">${axisLabels.join('')}</g>`);

  // ---------- assemble ----------
  const ariaLabel =
    'Natal chart wheel. Twelve zodiac signs around the rim, the Sun, Moon and ' +
    'planets with the lunar nodes plotted by position, twelve house divisions, ' +
    'and aspect lines connecting the bodies at the centre.';
  const style = themeStyle(o.theme);
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${VIEWBOX} ${VIEWBOX}" ` +
      `preserveAspectRatio="xMidYMid meet" role="img" aria-label="${esc(ariaLabel)}" ` +
      `class="cw-root" data-theme="${o.theme}">`,
    `<title>Natal chart wheel</title>`,
    `<desc>${esc(ariaLabel)}</desc>`,
    `<defs>${glyphDefs()}</defs>`,
    `<style>\n${style}</style>`,
    `<rect x="0" y="0" width="${VIEWBOX}" height="${VIEWBOX}" fill="var(--bg,#FAFAF8)"/>`,
    layers.join('\n'),
    `</svg>`,
    '',
  ].join('\n');
}

// ---------- axis label + data hook ----------
function axisHook(name, abbr, lon, srcPos, r, asc) {
  const p = project(lon, r, asc);
  const deg = srcPos ? srcPos.degree_in_sign : degInSign(lon);
  const sign = srcPos ? srcPos.sign : signFromLon(lon);
  return (
    `<g class="cw-axis" data-axis="${esc(name)}" data-degree="${num2(deg)}" data-sign="${esc(sign)}">` +
    text(p.x, p.y, 'cw-axis-label', esc(abbr), 'font-size="15"') +
    `</g>`
  );
}

// ---------- planets / points ----------
function renderPoints(chart, asc, o) {
  const present = PLOTTED_BODIES
    .map((n) => chart.points.find((p) => p.name === n))
    .filter(Boolean);

  const placed = spread(present); // adds trueLon / displayLon
  const groups = placed.map((pt) => {
    const isNode = NODES.has(pt.name);
    const glyphCls = pt.name === 'South Node' ? 'cw-glyph-faint' : 'cw-glyph';
    const key = BODY_GLYPH[pt.name];

    // pointer: glyph-side anchor (display angle) → true longitude on inner edge
    const anchor = P(pt.displayLon, POINTER_GLYPH_R, asc);
    const top = P(pt.trueLon, BANDS.pointerTop, asc);
    const gc = P(pt.displayLon, BANDS.planetGlyph, asc);

    const parts = [line(anchor, top, 'cw-hair')];
    parts.push(useGlyph(key, gc.x, gc.y, GLYPH_SIZE.node, glyphCls));

    // §4 retrograde: only planets, never nodes
    if (pt.retrograde === true && PLANETS.has(pt.name) && !isNode) {
      const rx = gc.x + GLYPH_SIZE.retroOffset;
      const ry = gc.y - GLYPH_SIZE.retroOffset;
      parts.push(useGlyph('retro', rx, ry, GLYPH_SIZE.retroSize, 'cw-retro'));
    }

    // §9 optional static degree label (off by default)
    if (o.degreeLabels) {
      const dp = P(pt.displayLon, BANDS.planetGlyph - 22, asc);
      parts.push(text(dp.x, dp.y, 'cw-degree', `${Math.floor(degInSign(pt.trueLon))}°`, 'font-size="11"'));
    }

    // data hooks (§9) — Placidus house read ONLY here, never affects geometry
    const deg = pt.degree_in_sign != null ? pt.degree_in_sign : degInSign(pt.trueLon);
    const sign = pt.sign || signFromLon(pt.trueLon);
    const house = pt.sector && pt.sector.placidus != null ? ` data-house="${pt.sector.placidus}"` : '';
    const hl = o.highlight && o.highlight.highlight_points?.includes(pt.name);
    const dim = o.highlight && !hl ? ' opacity="0.35"' : '';
    return (
      `<g class="cw-point${hl ? ' cw-highlight' : ''}" data-point="${esc(pt.name)}" ` +
      `data-degree="${num2(deg)}" data-sign="${esc(sign)}"${house}${dim}>${parts.join('')}</g>`
    );
  });
  return `<g class="cw-points">${groups.join('')}</g>`;
}

// ---------- aspect hub ----------
function renderHub(chart, asc, o) {
  const byName = new Map(chart.points.map((p) => [p.name, p]));
  const rels = (chart.relations || []).filter((r) => r.scheme === 'modern');
  const chords = [];
  for (const rel of rels) {
    const s = byName.get(rel.source);
    const t = byName.get(rel.target);
    if (!s || !t) continue;
    const family = ASPECT_FAMILY[rel.type] || 'conj';
    const grp = family === 'soft' ? ASPECT.soft : ASPECT.hard;
    const strength = 1 - Math.min(rel.orb ?? 0, ASPECT.maxOrb) / ASPECT.maxOrb;
    let opacity = grp.opacityBase + grp.opacitySpan * strength;
    if (family === 'soft') opacity = Math.max(opacity, ASPECT.softFloor); // §5 floor
    const width = grp.widthBase + grp.widthSpan * strength;

    const a = P(s.longitude, BANDS.hub, asc);
    const b = P(t.longitude, BANDS.hub, asc);
    const cssVar = ASPECT_VAR[family];

    // §9 highlight seam (deferred/off): emphasise matched chord, dim under it.
    const hit = o.highlight?.highlight_relations?.some(
      ([x, y]) => (x === rel.source && y === rel.target) || (x === rel.target && y === rel.source)
    );
    const strokeVar = hit ? '--highlight' : cssVar;
    const dimOpacity = o.highlight && !hit ? Math.min(opacity, 0.18) : opacity;
    // §9 applying styling (off by default): separating → subtle dash
    const dash = o.applyingStyle && rel.applying === false ? ' stroke-dasharray="6 5"' : '';

    chords.push(
      `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="cw-aspect" ` +
        `data-aspect="${esc(rel.type)}" data-from="${esc(rel.source)}" data-to="${esc(rel.target)}" ` +
        `stroke="var(${strokeVar})" stroke-opacity="${num(dimOpacity)}" ` +
        `stroke-width="${num(width)}" stroke-linecap="round"${dash}/>`
    );
  }
  const hubCircle = circle(CX, CY, BANDS.hub, 'cw-hair', 'stroke-opacity="0.6"');
  return `<g class="cw-hub">${hubCircle}${chords.join('')}</g>`;
}

const num2 = (n) => {
  const r = Math.round(n * 100) / 100;
  return Object.is(r, -0) ? 0 : r;
};
