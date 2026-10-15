import type { WheelInput, WheelOptions } from "./types";
// CHART_WHEEL_SPEC.md §8 — determinism & invariants (validation gate).
// Returns { ok, violations[] }. CLI/tests fail the build on any violation.
import { renderChart } from "./render";
import { spread } from "./spread";
import { thetaScreen, mod360 } from "./transform";
import { PLOTTED_BODIES, NODES, MIN_SEP } from "./constants";

// §8.7 leak tripwire — none of these may appear in the serialized SVG.
const FORBIDDEN = [
  "modern",
  "classical",
  "whole",
  "placidus",
  "triplicity",
  "dignity",
  "domicile",
  "detriment",
  "exalt",
  "fall",
  "bound",
  "face",
  "spirit",
  "planetary day",
  "planetary hour",
];

export function checkInvariants(chart: WheelInput, opts: WheelOptions = {}) {
  const violations = [];
  const svg = renderChart(chart, opts);

  // 1. Determinism — same input → byte-identical output.
  if (renderChart(chart, opts) !== svg) {
    violations.push("§8.1 determinism: two renders of the same chart differ.");
  }

  // 2. Completeness — every §2 body present in points rendered exactly once.
  const expected = PLOTTED_BODIES.filter((n) =>
    chart.points.some((p) => p.name === n),
  );
  for (const name of expected) {
    const count = occurrences(svg, `data-point="${name}"`);
    if (count !== 1) {
      violations.push(
        `§8.2 completeness: "${name}" rendered ${count}× (want 1).`,
      );
    }
  }

  // 3. Aspect fidelity — every modern relation once; zero masked relations.
  const modernCount = (chart.relations || []).filter(
    (r) =>
      r.scheme === "modern" &&
      chart.points.some((p) => p.name === r.source) &&
      chart.points.some((p) => p.name === r.target),
  ).length;
  const renderedAspects = occurrences(svg, 'class="cw-aspect"');
  if (renderedAspects !== modernCount) {
    violations.push(
      `§8.3 aspect fidelity: ${renderedAspects} chords rendered, ${modernCount} expected.`,
    );
  }

  // 4. Anchor — Ascendant within 0.01° of screen-left (180°).
  const asc = chart.axes.ascendant.longitude;
  const ascTheta = thetaScreen(asc, asc);
  if (Math.abs(ascTheta - 180) > 0.01) {
    violations.push(`§8.4 anchor: Ascendant at ${ascTheta}° (want 180±0.01).`);
  }

  // 5. No overlap — after spreading, no two glyph centres closer than MIN_SEP.
  const present = PLOTTED_BODIES.map((n) =>
    chart.points.find((p) => p.name === n),
  ).filter((p) => p !== undefined);
  const placed = spread(present);
  for (let i = 0; i < placed.length; i++) {
    for (let j = i + 1; j < placed.length; j++) {
      const sep = angularSep(placed[i]!.displayLon, placed[j]!.displayLon);
      if (sep < MIN_SEP - 1e-6) {
        violations.push(
          `§8.5 overlap: ${placed[i]!.name}/${placed[j]!.name} separated by ${sep.toFixed(3)}° (< ${MIN_SEP}).`,
        );
      }
    }
  }

  // 6. Node ℞ — no retrograde mark on North or South Node.
  for (const name of NODES) {
    const group = pointGroup(svg, name);
    if (group && group.includes("#g-retro")) {
      violations.push(`§8.6 node ℞: "${name}" carries a retrograde mark.`);
    }
  }

  // 7. Mask check — forbidden substrings (case-insensitive).
  const lower = svg.toLowerCase();
  for (const word of FORBIDDEN) {
    if (lower.includes(word)) {
      violations.push(`§8.7 mask leak: serialized SVG contains "${word}".`);
    }
  }

  return { ok: violations.length === 0, violations, svg };
}

function occurrences(hay: any, needle: any) {
  let n = 0;
  let i = hay.indexOf(needle);
  while (i !== -1) {
    n++;
    i = hay.indexOf(needle, i + needle.length);
  }
  return n;
}

// Slice a single cw-point group (no nested <g> inside) for `name`.
function pointGroup(svg: any, name: any) {
  const start = svg.indexOf(`data-point="${name}"`);
  if (start === -1) return null;
  const open = svg.lastIndexOf("<g ", start);
  const end = svg.indexOf("</g>", start);
  return svg.slice(open, end);
}

function angularSep(a: any, b: any) {
  const d = mod360(a - b);
  return Math.min(d, 360 - d);
}
