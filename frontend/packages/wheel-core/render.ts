import { computeWheel, type WheelModel } from "./model";
import type { WheelInput, WheelOptions } from "./types";
// CHART_WHEEL_SPEC.md — the production engine.
// Pure function: renderChart(chart, opts) -> self-contained SVG string.
// Reads ONLY the §1 "Consumed" fields. Never touches masked fields.
import {
  VIEWBOX,
  CX,
  CY,
  BANDS,
  GLYPH_SIZE,
  ASPECT_VAR,
  PLANETS,
  NODES,
  BODY_GLYPH,
  SIGN_GLYPHS,
} from "./constants";
import { num, mod360 } from "./transform";
import { glyphDefs } from "./glyphs";
import { themeStyle } from "./theme";

const SIGNS = [
  "Aries",
  "Taurus",
  "Gemini",
  "Cancer",
  "Leo",
  "Virgo",
  "Libra",
  "Scorpio",
  "Sagittarius",
  "Capricorn",
  "Aquarius",
  "Pisces",
];
const signFromLon = (lon: number) => SIGNS[Math.floor(mod360(lon) / 30)];
const degInSign = (lon: number) => mod360(lon) % 30;

// ---- small SVG emitters (all coords pre-rounded) ----
const line = (
  a: { x: number; y: number },
  b: { x: number; y: number },
  cls: string,
  extra = "",
) =>
  `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="${cls}"${extra ? " " + extra : ""}/>`;
const circle = (cx: number, cy: number, r: number, cls: string, extra = "") =>
  `<circle cx="${num(cx)}" cy="${num(cy)}" r="${num(r)}" class="${cls}"${extra ? " " + extra : ""}/>`;
const useGlyph = (
  key: string,
  cx: number,
  cy: number,
  size: number,
  cls: string,
) => {
  const s = num(size);
  return `<use href="#g-${key}" x="${num(cx - size / 2)}" y="${num(cy - size / 2)}" width="${s}" height="${s}" class="${cls}"/>`;
};
const text = (x: number, y: number, cls: string, body: string, extra = "") =>
  `<text x="${num(x)}" y="${num(y)}" text-anchor="middle" dominant-baseline="central" class="${cls}"${extra ? " " + extra : ""}>${body}</text>`;
const esc = (s: unknown) =>
  String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

export function renderChart(chart: WheelInput, opts: WheelOptions = {}) {
  const o = {
    theme: "light",
    degreeLabels: false, // §9 off; available on tap/hover via data hooks
    fortune: false, // §9 off
    applyingStyle: false, // §9 off — hub encodes exactly one variable
    highlight: null, // §9 deferred grounded layer — seam kept, off by default
    ...opts,
  };
  const model = computeWheel(chart);
  const P = (lon: number, r: number, _asc: number) => model.point(lon, r);
  const asc = model.asc;
  const layers = [];

  // ---------- zodiac ring (§4: 0.88–1.00) ----------
  const ring = [];
  ring.push(circle(CX, CY, BANDS.zodiacOuter, "cw-hair"));
  ring.push(circle(CX, CY, BANDS.zodiacInner, "cw-hair"));
  model.signs.forEach((sign, i) => {
    ring.push(line(sign.start, sign.end, "cw-hair"));
    ring.push(
      useGlyph(
        SIGN_GLYPHS[i]!,
        sign.glyph.x,
        sign.glyph.y,
        GLYPH_SIZE.sign,
        "cw-glyph",
      ),
    );
  });
  layers.push(`<g class="cw-zodiac">${ring.join("")}</g>`);

  // ---------- degree ticks (§4: 0.85–0.88) ----------
  const ticks = [];
  for (const tick of model.ticks) ticks.push(line(tick.a, tick.b, "cw-hair"));
  layers.push(`<g class="cw-ticks">${ticks.join("")}</g>`);

  // ---------- house cusps + numbering (§4: 0.62–0.85) ----------
  const cusps = chart.sectors?.placidus_cusps;
  if (Array.isArray(cusps) && cusps.length === 12) {
    const houses = [];
    for (const house of model.houses)
      houses.push(line(house.a, house.b, "cw-house-line"));
    for (const house of model.houses)
      houses.push(
        text(
          house.label.x,
          house.label.y,
          "cw-house-num",
          String(house.house),
          'font-size="13"',
        ),
      );
    layers.push(`<g class="cw-houses">${houses.join("")}</g>`);
  }

  // ---------- aspect hub (§5) ----------
  layers.push(renderHub(chart, asc, o, model));

  // ---------- axes (§2): full diameters Asc–Desc, MC–IC ----------
  const mc = chart.axes.mc.longitude;
  const axisLines = [
    line(
      P(asc, BANDS.zodiacInner, asc),
      P(asc + 180, BANDS.zodiacInner, asc),
      "cw-axis-line",
    ),
    line(
      P(mc, BANDS.zodiacInner, asc),
      P(mc + 180, BANDS.zodiacInner, asc),
      "cw-axis-line",
    ),
  ];
  layers.push(`<g class="cw-axes">${axisLines.join("")}</g>`);

  // ---------- planets / points (§4) ----------
  layers.push(renderPoints(chart, asc, o, model));

  // ---------- axis labels on top (§7: AC/DC/MC/IC uppercase, wide) ----------
  // Sit just outside the rim so a body conjunct an angle never collides with
  // its label (e.g. a planet on the MC).
  const labelR = 478;
  const axisLabels = [
    axisHook("Ascendant", "AC", asc, chart.axes.ascendant, labelR, asc, model),
    axisHook("Descendant", "DC", asc + 180, null, labelR, asc, model),
    axisHook("Midheaven", "MC", mc, chart.axes.mc, labelR, asc, model),
    axisHook("Imum Coeli", "IC", mc + 180, null, labelR, asc, model),
  ];
  layers.push(`<g class="cw-axis-labels">${axisLabels.join("")}</g>`);

  // ---------- assemble ----------
  const ariaLabel =
    "Natal chart wheel. Twelve zodiac signs around the rim, the Sun, Moon and " +
    "planets with the lunar nodes plotted by position, twelve house divisions, " +
    "and aspect lines connecting the bodies at the centre.";
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
    layers.join("\n"),
    `</svg>`,
    "",
  ].join("\n");
}

// ---------- axis label + data hook ----------
function axisHook(
  name: string,
  abbr: string,
  lon: number,
  srcPos: WheelInput["axes"]["ascendant"] | null,
  r: number,
  asc: number,
  model: WheelModel,
) {
  const p = model.point(lon, r);
  const deg = srcPos ? srcPos.degree_in_sign : degInSign(lon);
  const sign = srcPos ? srcPos.sign : signFromLon(lon);
  return (
    `<g class="cw-axis" data-axis="${esc(name)}" data-degree="${num2(deg)}" data-sign="${esc(sign)}">` +
    text(p.x, p.y, "cw-axis-label", esc(abbr), 'font-size="15"') +
    `</g>`
  );
}

// ---------- planets / points ----------
function renderPoints(
  chart: WheelInput,
  asc: number,
  o: WheelOptions,
  model: WheelModel,
) {
  const placed = model.points; // adds trueLon / displayLon
  const groups = placed.map((pt) => {
    const isNode = NODES.has(pt.name);
    const glyphCls = pt.name === "South Node" ? "cw-glyph-faint" : "cw-glyph";
    const key = BODY_GLYPH[pt.name]!;

    // pointer: glyph-side anchor (display angle) → true longitude on inner edge
    const anchor = pt.anchor;
    const top = pt.top;
    const gc = pt.glyph;

    const parts = [line(anchor, top, "cw-hair")];
    parts.push(useGlyph(key, gc.x, gc.y, GLYPH_SIZE.node, glyphCls));

    // §4 retrograde: only planets, never nodes
    if (pt.retrograde === true && PLANETS.has(pt.name) && !isNode) {
      const rx = gc.x + GLYPH_SIZE.retroOffset;
      const ry = gc.y - GLYPH_SIZE.retroOffset;
      parts.push(useGlyph("retro", rx, ry, GLYPH_SIZE.retroSize, "cw-retro"));
    }

    // §9 optional static degree label (off by default)
    if (o.degreeLabels) {
      const dp = model.point(pt.displayLon, BANDS.planetGlyph - 22);
      parts.push(
        text(
          dp.x,
          dp.y,
          "cw-degree",
          `${Math.floor(degInSign(pt.trueLon))}°`,
          'font-size="11"',
        ),
      );
    }

    // data hooks (§9) — Placidus house read ONLY here, never affects geometry
    const deg =
      pt.degree_in_sign != null ? pt.degree_in_sign : degInSign(pt.trueLon);
    const sign = pt.sign || signFromLon(pt.trueLon);
    const house =
      pt.sector && pt.sector.placidus != null
        ? ` data-house="${pt.sector.placidus}"`
        : "";
    const hl = o.highlight && o.highlight.highlight_points?.includes(pt.name);
    const dim = o.highlight && !hl ? ' opacity="0.35"' : "";
    return (
      `<g class="cw-point${hl ? " cw-highlight" : ""}" data-point="${esc(pt.name)}" ` +
      `data-degree="${num2(deg)}" data-sign="${esc(sign)}"${house}${dim}>${parts.join("")}</g>`
    );
  });
  return `<g class="cw-points">${groups.join("")}</g>`;
}

// ---------- aspect hub ----------
function renderHub(
  chart: WheelInput,
  asc: number,
  o: WheelOptions,
  model: WheelModel,
) {
  const chords = [];
  for (const chord of model.chords) {
    const { rel, family, opacity, width, a, b } = chord;
    const cssVar = ASPECT_VAR[family];

    // §9 highlight seam (deferred/off): emphasise matched chord, dim under it.
    const hit = o.highlight?.highlight_relations?.some(
      ([x, y]) =>
        (x === rel.source && y === rel.target) ||
        (x === rel.target && y === rel.source),
    );
    const strokeVar = hit ? "--highlight" : cssVar;
    const dimOpacity = o.highlight && !hit ? Math.min(opacity, 0.18) : opacity;
    // §9 applying styling (off by default): separating → subtle dash
    const dash =
      o.applyingStyle && "applying" in rel && rel.applying === false
        ? ' stroke-dasharray="6 5"'
        : "";

    chords.push(
      `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" class="cw-aspect" ` +
        `data-aspect="${esc(rel.type)}" data-from="${esc(rel.source)}" data-to="${esc(rel.target)}" ` +
        `stroke="var(${strokeVar})" stroke-opacity="${num(dimOpacity)}" ` +
        `stroke-width="${num(width)}" stroke-linecap="round"${dash}/>`,
    );
  }
  const hubCircle = circle(
    CX,
    CY,
    BANDS.hub,
    "cw-hair",
    'stroke-opacity="0.6"',
  );
  return `<g class="cw-hub">${hubCircle}${chords.join("")}</g>`;
}

const num2 = (n: number) => {
  const r = Math.round(n * 100) / 100;
  return Object.is(r, -0) ? 0 : r;
};
