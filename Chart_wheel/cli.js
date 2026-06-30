#!/usr/bin/env node
// CHART_WHEEL_SPEC.md — CLI: render a chart.json to a self-contained SVG and/or
// run the §8 invariant gate.
//
//   node cli.js [chart.json] [options]
//     --out <file>        write SVG to file (default: stdout)
//     --theme light|dark  theme preset (default: light)
//     --check             run §8 invariant gate; exit 1 on any violation
//     --degree-labels     §9 static per-glyph degree labels (default off)
//     --applying          §9 applying/separating chord styling (default off)
//
import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { renderChart } from './src/render.js';
import { checkInvariants } from './src/invariants.js';

const __dirname = dirname(fileURLToPath(import.meta.url));

function parseArgs(argv) {
  const a = { chart: null, out: null, theme: 'light', check: false, opts: {} };
  for (let i = 0; i < argv.length; i++) {
    const t = argv[i];
    if (t === '--out') a.out = argv[++i];
    else if (t === '--theme') a.theme = argv[++i];
    else if (t === '--check') a.check = true;
    else if (t === '--degree-labels') a.opts.degreeLabels = true;
    else if (t === '--applying') a.opts.applyingStyle = true;
    else if (!t.startsWith('--')) a.chart = t;
  }
  return a;
}

const args = parseArgs(process.argv.slice(2));
const chartPath = resolve(args.chart || resolve(__dirname, '../d_layer/chart.json'));
const chart = JSON.parse(readFileSync(chartPath, 'utf8'));
const opts = { theme: args.theme, ...args.opts };

if (args.check) {
  const { ok, violations, svg } = checkInvariants(chart, opts);
  if (ok) {
    console.error(`✓ §8 invariant gate passed (${chartPath})`);
    if (args.out) writeFileSync(args.out, svg);
    else process.stdout.write(svg);
    process.exit(0);
  } else {
    console.error(`✗ §8 invariant gate FAILED (${chartPath}):`);
    for (const v of violations) console.error('  - ' + v);
    process.exit(1);
  }
} else {
  const svg = renderChart(chart, opts);
  if (args.out) {
    writeFileSync(args.out, svg);
    console.error(`wrote ${args.out} (${svg.length} bytes)`);
  } else {
    process.stdout.write(svg);
  }
}
