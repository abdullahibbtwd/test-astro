import { URL } from "node:url";
import { readFileSync, writeFileSync } from "node:fs";
const geo = JSON.parse(
  readFileSync(
    new URL("../mock-api/fixtures/geo-countries.json", import.meta.url),
    "utf8",
  ),
);
const countries = Object.fromEntries(
  geo.features
    .map(
      ({
        properties: p,
      }: {
        properties: { iso2: string; name_en: string; name_tr: string };
      }) => [p.iso2, { en: p.name_en, tr: p.name_tr }],
    )
    .sort(([a]: [string], [b]: [string]) => a.localeCompare(b)),
);
writeFileSync(
  new URL("../src/i18n/countries.json", import.meta.url),
  JSON.stringify(countries, null, 2) + "\n",
);
