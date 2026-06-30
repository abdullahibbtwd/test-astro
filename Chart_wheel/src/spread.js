// CHART_WHEEL_SPEC.md §4 — glyph collision / spreading pass.
// Redistributes glyph *display* angles so no two centres sit closer than
// MIN_SEP, while each glyph's pointer stays anchored to its TRUE longitude.
//
// §4 describes a per-cluster redistribution. We implement the globally optimal
// form of the same idea: minimise total angular displacement subject to a hard
// `display[i+1] - display[i] >= min_sep` constraint. This is exactly §4's
// "cluster, then spread about the cluster mean" — merged blocks ARE clusters
// centred on their mean — but it also guarantees the §8.5 floor even when two
// stelliums sit adjacent (which the naive per-cluster spread violates, because
// spreading one cluster can push it into the next). The optimal fit is isotonic
// regression (pool-adjacent-violators) on the gap-adjusted positions.
import { MIN_SEP } from './constants.js';
import { mod360 } from './transform.js';

// items: [{ name, longitude, ... }]  (true longitudes)
// returns the same objects augmented with { trueLon, displayLon }, input order.
export function spread(items, minSep = MIN_SEP) {
  const pts = items.map((it) => ({ ...it, trueLon: it.longitude, displayLon: it.longitude }));
  if (pts.length < 2) return pts;

  // Sort a working view by longitude (stable on ties via original index).
  const view = pts.map((p, i) => ({ p, i }));
  view.sort((a, b) => a.p.longitude - b.p.longitude || a.i - b.i);
  const ring = view.map((o) => o.p);
  const n = ring.length;

  // Cut the ring at its largest gap so the points form a linear, non-wrapping
  // sequence. The largest gap (>= 360/n) absorbs the wrap-around constraint.
  let cut = 0;
  let maxGap = -1;
  for (let k = 0; k < n; k++) {
    const g = mod360(ring[(k + 1) % n].longitude - ring[k].longitude);
    if (g > maxGap) {
      maxGap = g;
      cut = (k + 1) % n; // sequence starts just after the largest gap
    }
  }

  // Unwrap desired positions, increasing, starting at the cut.
  const base = ring[cut].longitude;
  const seq = [];
  for (let k = 0; k < n; k++) {
    const node = ring[(cut + k) % n];
    seq.push({ node, desired: base + mod360(node.longitude - base) });
  }

  // Gap-adjust: enforcing display[k+1]-display[k] >= minSep is equivalent to
  // requiring (display[k] - k*minSep) be non-decreasing. Fit the optimal
  // non-decreasing sequence to (desired[k] - k*minSep) via PAVA.
  const adj = seq.map((s, k) => s.desired - k * minSep);
  const fitted = pava(adj);
  seq.forEach((s, k) => {
    s.node.displayLon = mod360(fitted[k] + k * minSep);
  });

  return pts;
}

// Pool-adjacent-violators: L2-optimal non-decreasing fit to `arr`.
function pava(arr) {
  const stack = []; // blocks: { sum, count, mean }
  for (const v of arr) {
    let cur = { sum: v, count: 1, mean: v };
    while (stack.length && stack[stack.length - 1].mean > cur.mean) {
      const p = stack.pop();
      cur = { sum: p.sum + cur.sum, count: p.count + cur.count, mean: 0 };
      cur.mean = cur.sum / cur.count;
    }
    stack.push(cur);
  }
  const out = [];
  for (const b of stack) for (let i = 0; i < b.count; i++) out.push(b.mean);
  return out;
}
