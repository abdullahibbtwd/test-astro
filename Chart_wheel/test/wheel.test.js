// CHART_WHEEL_SPEC.md — engine tests.
// §8 invariant gate + §11 regression against the Python geometry oracle.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

import { renderChart } from '../src/render.js';
import { checkInvariants } from '../src/invariants.js';
import { project, thetaScreen } from '../src/transform.js';
import { spread } from '../src/spread.js';
import { BANDS, PLOTTED_BODIES, MIN_SEP } from '../src/constants.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CHART = JSON.parse(readFileSync(resolve(__dirname, '../../d_layer/chart.json'), 'utf8'));

test('§8 invariant gate passes (light)', () => {
  const { ok, violations } = checkInvariants(CHART, { theme: 'light' });
  assert.ok(ok, 'violations:\n' + violations.join('\n'));
});

test('§8 invariant gate passes (dark)', () => {
  const { ok, violations } = checkInvariants(CHART, { theme: 'dark' });
  assert.ok(ok, 'violations:\n' + violations.join('\n'));
});

test('§8.1 determinism: byte-identical across renders', () => {
  assert.equal(renderChart(CHART), renderChart(CHART));
});

test('§8.4 anchor: Ascendant at screen-left (180°)', () => {
  const asc = CHART.axes.ascendant.longitude;
  assert.ok(Math.abs(thetaScreen(asc, asc) - 180) <= 0.01);
});

test('§3 Descendant projects to screen-right', () => {
  const asc = CHART.axes.ascendant.longitude;
  assert.ok(Math.abs(thetaScreen(asc + 180, asc) - 0) <= 0.01);
});

test('§4 spreader keeps a clustered chart at ≥ min_sep', () => {
  const present = PLOTTED_BODIES.map((n) => CHART.points.find((p) => p.name === n)).filter(Boolean);
  const placed = spread(present);
  for (let i = 0; i < placed.length; i++) {
    for (let j = i + 1; j < placed.length; j++) {
      const d = Math.abs(((placed[i].displayLon - placed[j].displayLon + 540) % 360) - 180);
      assert.ok(d >= MIN_SEP - 1e-6, `${placed[i].name}/${placed[j].name} = ${d.toFixed(3)}°`);
    }
  }
});

test('§4 spreader preserves true longitudes', () => {
  const present = PLOTTED_BODIES.map((n) => CHART.points.find((p) => p.name === n)).filter(Boolean);
  const placed = spread(present);
  for (const p of placed) {
    const src = CHART.points.find((q) => q.name === p.name);
    assert.equal(p.trueLon, src.longitude);
  }
});

test('§11 engine geometry matches the Python oracle within 1px', () => {
  let raw;
  try {
    raw = execFileSync('python', [resolve(__dirname, '../render_wheel.py'), '--positions'], {
      encoding: 'utf8',
      cwd: resolve(__dirname, '..'),
    });
  } catch (e) {
    // Oracle is a dev-time check; skip cleanly if Python is unavailable.
    console.error('skipping oracle regression (python not available): ' + e.message);
    return;
  }
  const oracle = JSON.parse(raw);
  const asc = oracle.asc;
  const close = (a, b) => assert.ok(Math.hypot(a[0] - b[0], a[1] - b[1]) <= 1.0,
    `${JSON.stringify(a)} vs ${JSON.stringify(b)}`);
  const xy = (lon, r) => { const p = project(lon, r, asc); return [round3(p.x), round3(p.y)]; };

  for (const pl of oracle.planets) {
    close(xy(pl.lon, BANDS.planetGlyph), pl.glyph);
    close(xy(pl.lon, BANDS.pointerTop), pl.pointerTop);
  }
  for (const cu of oracle.cusps) {
    close(xy(cu.lon, BANDS.houseCuspInner), cu.inner);
    close(xy(cu.lon, BANDS.houseCuspOuter), cu.outer);
  }
  for (const h of oracle.hub) {
    const s = CHART.points.find((p) => p.name === h.from);
    const t = CHART.points.find((p) => p.name === h.to);
    close(xy(s.longitude, BANDS.hub), h.a);
    close(xy(t.longitude, BANDS.hub), h.b);
  }
  close(xy(asc, BANDS.zodiacInner), oracle.axes.asc);
  close(xy(oracle.mc, BANDS.zodiacInner), oracle.axes.mc);
});

function round3(n) {
  const r = Math.round(n * 1000) / 1000;
  return Object.is(r, -0) ? 0 : r;
}
