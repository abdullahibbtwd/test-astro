// CHART_WHEEL_SPEC.md §7 — "quiet modern-minimal". All colour/stroke/font via
// CSS custom properties on the SVG root, with fallbacks. No colour literals in
// geometry code — tokens only. Light (default) + dark preset.
//
// Type roles (§7): production replaces the mock's system stack with chosen
// faces. We name them here as a token so the host can swap them in one place.
//   --glyph-font : light humanist sans for glyphs/data
//   --axis-font  : same family, used uppercase + wide tracking for AC/DC/MC/IC
// Chosen face (cite in PR): "Inter" as the harmonising humanist sans — it sits
// quietly beside Turkish body text and has the open, low-contrast forms §7 asks
// for. Falls back through a system humanist stack so the SVG renders standalone.

const FONT_STACK =
  "'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif";

// The signature accent — Ottoman-tilework indigo. ONE accent, one job (the hub).
const ACCENT = "#2E4A7D";

export const THEMES: Record<string, Record<string, string>> = {
  light: {
    "--bg": "#FAFAF8",
    "--ink": "#232A38",
    "--hair": "#DEDED7",
    "--house-line": "#E8E8E1",
    "--house-num": "#9CA0A8",
    "--glyph-retro": "#9A9A92",
    "--accent": ACCENT,
    "--aspect-hard": "var(--accent)",
    "--aspect-conj": "var(--accent)",
    "--aspect-soft": "#C7CABF",
    "--highlight": ACCENT, // §9 grounded layer (deferred) — derives from accent
    "--node-faint": "0.5", // South Node contrast notch (§9)
    "--glyph-font": FONT_STACK,
    "--axis-font": FONT_STACK,
  },
  // Dark preset: invert ground to a deep blue-grey, lift hairlines, keep indigo.
  dark: {
    "--bg": "#1A2030",
    "--ink": "#E7E9EE",
    "--hair": "#3A4256",
    "--house-line": "#2E3548",
    "--house-num": "#7C8290",
    "--glyph-retro": "#6E7480",
    "--accent": "#7FA0D8", // indigo lifted for dark ground; same hue family
    "--aspect-hard": "var(--accent)",
    "--aspect-conj": "var(--accent)",
    "--aspect-soft": "#5E6A5C",
    "--highlight": "#7FA0D8",
    "--node-faint": "0.5",
    "--glyph-font": FONT_STACK,
    "--axis-font": FONT_STACK,
  },
};

// Build the `style` block that defines tokens on :root and maps roles.
export function themeStyle(themeName = "light") {
  const vars = THEMES[themeName] || THEMES.light;
  const decls = Object.entries(vars!)
    .map(([k, v]) => `    ${k}: ${v};`)
    .join("\n");
  // Fallbacks are baked into var() usages at the geometry layer; here we only
  // declare the token values on the root.
  return (
    `  .cw-root {\n${decls}\n` +
    `    background: var(--bg);\n` +
    `    font-family: var(--glyph-font);\n` +
    `  }\n` +
    `  .cw-hair { stroke: var(--hair); fill: none; }\n` +
    `  .cw-house-line { stroke: var(--house-line); fill: none; }\n` +
    `  .cw-house-num { fill: var(--house-num); }\n` +
    `  .cw-glyph { color: var(--ink); }\n` +
    `  .cw-glyph-faint { color: var(--ink); opacity: var(--node-faint); }\n` +
    `  .cw-retro { color: var(--glyph-retro); }\n` +
    `  .cw-axis-line { stroke: var(--ink); fill: none; }\n` +
    `  .cw-axis-label { fill: var(--ink); font-family: var(--axis-font); ` +
    `letter-spacing: 2px; text-transform: uppercase; }\n` +
    `  .cw-degree { fill: var(--house-num); letter-spacing: 0.5px; }\n`
  );
}
