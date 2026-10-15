import { test } from "node:test";
import assert from "node:assert/strict";
import { formatDay, formatMonth, formatRange, formatShort } from "../src/lib/dates";
import { countryName, countryFlag } from "../src/lib/countries";
test("calendar labels preserve dates and compact ranges in English and Turkish", () => {
 assert.equal(formatMonth("2026-10", "en"), "October 2026");
 assert.equal(formatMonth("2026-10", "tr"), "Ekim 2026");
 assert.equal(formatRange("2026-10-09", "2026-10-14", "en"), "9–14 Oct");
 assert.equal(formatRange("2026-09-28", "2026-10-03", "en"), "28 Sept – 3 Oct");
 for (const lang of ["en", "tr"]) {
  for (const value of [formatDay("2026-10-03", lang, {weekday:true}), formatShort("2026-10-03", lang), formatRange("2026-10-01", "2027-09-30", lang)]) assert.doesNotMatch(value, /\b\d{4}-\d{2}(-\d{2})?\b/);
 }
});
test("country names use the fixture worldview without Intl.DisplayNames", () => {
 assert.equal(countryName("FO", "en"), "Faroe Islands");
 assert.notEqual(countryName("TR", "tr"), "TR");
 assert.equal(countryName("FO", "en", "API country name"), "API country name");
 assert.equal(countryFlag("FO"), "🇫🇴");
 assert.equal(countryFlag("invalid"), "");
 assert.equal(countryName("ZZ", "en"), "Unknown country");
});
