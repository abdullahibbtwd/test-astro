import test from "node:test";
import assert from "node:assert/strict";
import { openSync } from "fontkit";
import { upper } from "../src/design-system/text/upper";
import { fontFiles } from "../src/design-system/theme/tokens";
import fs from "node:fs";
test("display casing respects Turkish dotted and dotless i without changing English", () => {
  assert.equal(upper("Haritamı oluştur", "tr"), "HARİTAMI OLUŞTUR");
  assert.equal(upper("Generate my chart", "en"), "GENERATE MY CHART");
  assert.equal(upper("i ı İstanbul İzmir", "tr"), "İ I İSTANBUL İZMİR");
});
for (const name of Object.keys(fontFiles))
  test(`${name} has every Turkish glyph`, () => {
    const font = openSync(`assets/fonts/design-system/${name}.ttf`);
    assert.ok("hasGlyphForCodePoint" in font);
    for (const char of "çğıİöşüÇĞIÖŞÜâîûÂÎÛ")
      assert.ok(
        font.hasGlyphForCodePoint(char.codePointAt(0)!),
        `${name}: ${char}`,
      );
  });
test("design font licenses are bundled", () => {
  for (const name of ["Aboreto", "Poppins"])
    assert.match(
      fs.readFileSync(`assets/fonts/design-system/OFL-${name}.txt`, "utf8"),
      /SIL OPEN FONT LICENSE/,
    );
});
