// CHART_WHEEL_SPEC.md §3 — coordinate transform (LOCKED).
// The ONLY coordinate system. All bodies/cusps/axes/aspect endpoints use it.
import { CX, CY } from "./constants";

const DEG = Math.PI / 180;

// Screen angle: CCW from east. asc → 180° (screen-left).
export function thetaScreen(lambda: number, ascLongitude: number) {
  return mod360(180 + (lambda - ascLongitude));
}

// Polar → Cartesian. Note the minus on y: SVG y grows downward.
export function project(lambda: number, r: number, ascLongitude: number) {
  const theta = thetaScreen(lambda, ascLongitude) * DEG;
  return {
    x: CX + r * Math.cos(theta),
    y: CY - r * Math.sin(theta),
  };
}

export function mod360(a: number) {
  return ((a % 360) + 360) % 360;
}

// Round to 3 decimals (§6 byte-stable diffs) and kill negative-zero.
export function num(n: number) {
  const r = Math.round(n * 1000) / 1000;
  return Object.is(r, -0) ? 0 : r;
}

// Smallest signed angular separation a→b in degrees, range (-180, 180].
export function angDiff(a: number, b: number) {
  let d = mod360(b - a);
  if (d > 180) d -= 360;
  return d;
}

// CCW arc midpoint from a to b (b reached by increasing longitude).
export function arcMidpoint(a: number, b: number) {
  const span = mod360(b - a);
  return mod360(a + span / 2);
}
