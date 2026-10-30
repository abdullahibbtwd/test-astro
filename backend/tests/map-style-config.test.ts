import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import {
  applyMapStyleEnv,
  validateMapStyleUrl,
} from "../api/map-style-config";
import { buildLocalApp } from "../api/app";
import { dataDbPath, tempDataDir } from "./helpers";

const DEMO = "https://demotiles.maplibre.org/style.json";

test("validateMapStyleUrl accepts https and empty", () => {
  assert.equal(validateMapStyleUrl("ASTRO_MAP_STYLE_LIGHT", undefined), null);
  assert.equal(validateMapStyleUrl("ASTRO_MAP_STYLE_LIGHT", ""), null);
  assert.equal(validateMapStyleUrl("ASTRO_MAP_STYLE_LIGHT", `  ${DEMO}  `), null);
  assert.match(
    validateMapStyleUrl("ASTRO_MAP_STYLE_LIGHT", "http://x/style.json") ?? "",
    /must use https/,
  );
});

test("applyMapStyleEnv overlays only set sides", () => {
  assert.deepEqual(
    applyMapStyleEnv(
      { light: "", dark: "https://example.com/dark.json" },
      { ASTRO_MAP_STYLE_LIGHT: DEMO },
    ),
    { light: DEMO, dark: "https://example.com/dark.json" },
  );
});

test("/meta/config exposes ASTRO_MAP_STYLE_* as map_style_url", async () => {
  const prevLight = process.env.ASTRO_MAP_STYLE_LIGHT;
  const prevDark = process.env.ASTRO_MAP_STYLE_DARK;
  process.env.ASTRO_MAP_STYLE_LIGHT = DEMO;
  process.env.ASTRO_MAP_STYLE_DARK = DEMO;
  const dir = tempDataDir("map-style-");
  const app = await buildLocalApp({ dbPath: dataDbPath(dir), allowPaid: false });
  try {
    const body = (await app.inject({ url: "/v1/meta/config" })).json();
    assert.equal(body.map_style_url.light, DEMO);
    assert.equal(body.map_style_url.dark, DEMO);
  } finally {
    await app.close();
    fs.rmSync(dir, { recursive: true, force: true });
    if (prevLight === undefined) delete process.env.ASTRO_MAP_STYLE_LIGHT;
    else process.env.ASTRO_MAP_STYLE_LIGHT = prevLight;
    if (prevDark === undefined) delete process.env.ASTRO_MAP_STYLE_DARK;
    else process.env.ASTRO_MAP_STYLE_DARK = prevDark;
  }
});
