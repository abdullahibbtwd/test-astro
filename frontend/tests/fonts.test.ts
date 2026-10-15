import { test } from "node:test";
import assert from "node:assert/strict";
import { openSync } from "fontkit";
import fs from "node:fs";
for (const file of ["Inter-Regular", "Inter-SemiBold", "SourceSerif4-Regular"])
  test(`${file}: Turkish glyph coverage`, () => {
    const font = openSync(`assets/fonts/${file}.ttf`);
    assert.ok("hasGlyphForCodePoint" in font);
    for (const char of "çğıİöşüÇĞIÖŞÜâîûÂÎÛ")
      assert.ok(
        font.hasGlyphForCodePoint(char.codePointAt(0)!),
        `Missing ${char}`,
      );
  });
test("bundled font licenses permit redistribution", () => {
  for (const file of ["Inter-OFL", "SourceSerif4-OFL"])
    assert.match(
      fs.readFileSync(`assets/fonts/${file}.txt`, "utf8"),
      /SIL OPEN FONT LICENSE/,
    );
});
