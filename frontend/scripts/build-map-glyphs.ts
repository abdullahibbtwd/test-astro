import fs from "node:fs";
import { Resvg } from "@resvg/resvg-js";
import { glyphDefs } from "../packages/wheel-core/glyphs";
import { BODY_GLYPH } from "../packages/wheel-core/constants";
const definitions = glyphDefs();
const out = "assets/map";
fs.mkdirSync(out, { recursive: true });
const imports: string[] = [];
for (const theme of ["light", "dark"])
  for (const [name, key] of Object.entries(BODY_GLYPH))
    for (const angle of ["", "ASC", "DSC", "MC", "IC"]) {
      const body = name.toLowerCase().replace(/ /g, "_"),
        id = `${theme}-${body}${angle ? `-${angle}` : ""}`,
        color = theme === "dark" ? "#E7E9EE" : "#232A38",
        label = angle === "ASC" ? "AC" : angle === "DSC" ? "DC" : angle;
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${angle ? 128 : 64}" height="64" color="${color}"><defs>${definitions}</defs><use href="#g-${key}" x="0" y="0" width="64" height="64"/>${angle ? `<text x="66" y="42" fill="${color}" font-size="24" font-family="Inter">${label}</text>` : ""}</svg>`;
      fs.writeFileSync(
        `${out}/${id}.png`,
        new Resvg(svg, {
          font: {
            fontFiles: ["assets/fonts/Inter-Regular.ttf"],
            loadSystemFonts: false,
          },
        })
          .render()
          .asPng(),
      );
      imports.push(`  "${id}": require("../../../assets/map/${id}.png"),`);
    }
// A bundled multiplication marker avoids a font/glyph-server dependency on
// the local preview style (and works offline alongside the planet icons).
for (const theme of ["light", "dark"]) {
  const id = `${theme}-paran-cross`;
  const color = theme === "dark" ? "#E7E9EE" : "#232A38";
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32"><path d="M8 8L24 24M24 8L8 24" stroke="${color}" stroke-width="3" stroke-linecap="round"/></svg>`;
  fs.writeFileSync(`${out}/${id}.png`, new Resvg(svg).render().asPng());
  imports.push(`  "${id}": require("../../../assets/map/${id}.png"),`);
}
fs.writeFileSync(
  "src/features/map/glyph-images.ts",
  `// Generated from the canonical vector glyphs by scripts/build-map-glyphs.ts.\nexport const mapGlyphImages = {\n${imports.join("\n")}\n};\n`,
);
console.log(`${imports.length} canonical map sprites generated`);
