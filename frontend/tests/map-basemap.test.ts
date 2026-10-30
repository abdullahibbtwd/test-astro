import { test } from "node:test";
import assert from "node:assert/strict";
import { resolveBasemap } from "../src/features/map/basemap";
import { loadMapStyle } from "../src/features/map/style-load";

test("resolveBasemap: empty URL → preview", () => {
  assert.equal(
    resolveBasemap({
      styleUrl: "",
      online: true,
      stylePending: false,
      hasStyle: false,
    }),
    "preview",
  );
  assert.equal(
    resolveBasemap({
      styleUrl: undefined,
      online: true,
      stylePending: true,
      hasStyle: false,
    }),
    "preview",
  );
});

test("resolveBasemap: offline → preview even with URL", () => {
  assert.equal(
    resolveBasemap({
      styleUrl: "https://demotiles.maplibre.org/style.json",
      online: false,
      stylePending: false,
      hasStyle: false,
    }),
    "preview",
  );
});

test("resolveBasemap: style load failure → preview", () => {
  assert.equal(
    resolveBasemap({
      styleUrl: "https://demotiles.maplibre.org/style.json",
      online: true,
      stylePending: false,
      hasStyle: false,
    }),
    "preview",
  );
});

test("resolveBasemap: pending provider fetch → loading", () => {
  assert.equal(
    resolveBasemap({
      styleUrl: "https://demotiles.maplibre.org/style.json",
      online: true,
      stylePending: true,
      hasStyle: false,
    }),
    "loading",
  );
});

test("resolveBasemap: loaded style → provider", () => {
  assert.equal(
    resolveBasemap({
      styleUrl: "https://demotiles.maplibre.org/style.json",
      online: true,
      stylePending: false,
      hasStyle: true,
    }),
    "provider",
  );
});

test("loadMapStyle requests the configured style URL (demotiles placeholder)", async () => {
  const url = "https://demotiles.maplibre.org/style.json";
  const seen: string[] = [];
  const previous = globalThis.fetch;
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    seen.push(String(input));
    return new Response(
      JSON.stringify({
        version: 8,
        sprite: "sprite",
        glyphs: "glyphs/{fontstack}/{range}.pbf",
        sources: {
          openmaptiles: {
            type: "vector",
            url: "tiles.json",
          },
        },
        layers: [
          {
            id: "label",
            type: "symbol",
            source: "openmaptiles",
            layout: { "text-field": "{name}" },
          },
        ],
      }),
      { status: 200 },
    );
  }) as typeof fetch;
  try {
    const style = await loadMapStyle(url, "en");
    assert.deepEqual(seen, [url]);
    assert.equal(style.version, 8);
    assert.equal(style.sprite, new URL("sprite", url).toString());
    assert.equal(
      (style.sources.openmaptiles as { url: string }).url,
      new URL("tiles.json", url).toString(),
    );
  } finally {
    globalThis.fetch = previous;
  }
});
