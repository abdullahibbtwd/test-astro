import { test } from "node:test";
import assert from "node:assert/strict";
import { resolveBasemap } from "../src/features/map/basemap";
import { loadMapStyle } from "../src/features/map/style-load";

test("resolveBasemap: empty URL → preview (empty_style)", () => {
  assert.deepEqual(
    resolveBasemap({
      styleUrl: "",
      online: true,
      stylePending: false,
      hasStyle: false,
    }),
    { mode: "preview", reason: "empty_style" },
  );
  assert.deepEqual(
    resolveBasemap({
      styleUrl: undefined,
      online: true,
      stylePending: true,
      hasStyle: false,
    }),
    { mode: "preview", reason: "empty_style" },
  );
});

test("resolveBasemap: offline → preview even with URL", () => {
  assert.deepEqual(
    resolveBasemap({
      styleUrl: "https://demotiles.maplibre.org/style.json",
      online: false,
      stylePending: false,
      hasStyle: false,
    }),
    { mode: "preview", reason: "offline" },
  );
});

test("resolveBasemap: style load failure → preview", () => {
  assert.deepEqual(
    resolveBasemap({
      styleUrl: "https://demotiles.maplibre.org/style.json",
      online: true,
      stylePending: false,
      hasStyle: false,
    }),
    { mode: "preview", reason: "style_failed" },
  );
});

test("resolveBasemap: pending provider fetch → loading", () => {
  assert.deepEqual(
    resolveBasemap({
      styleUrl: "https://demotiles.maplibre.org/style.json",
      online: true,
      stylePending: true,
      hasStyle: false,
    }),
    { mode: "loading", reason: "loading" },
  );
});

test("resolveBasemap: loaded style → provider", () => {
  assert.deepEqual(
    resolveBasemap({
      styleUrl: "https://demotiles.maplibre.org/style.json",
      online: true,
      stylePending: false,
      hasStyle: true,
    }),
    { mode: "provider", reason: "provider" },
  );
});

test("loadMapStyle rewrites labels for app language (en/tr)", async () => {
  const url = "https://demotiles.maplibre.org/style.json";
  const previous = globalThis.fetch;
  globalThis.fetch = (async () =>
    new Response(
      JSON.stringify({
        version: 8,
        sources: { openmaptiles: { type: "vector", url: "tiles.json" } },
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
    )) as typeof fetch;
  try {
    const style = await loadMapStyle(url, "tr");
    const field = (style.layers[0] as { layout: { "text-field": unknown } })
      .layout["text-field"];
    assert.deepEqual(field, ["coalesce", ["get", "name:tr"], ["get", "name"]]);
  } finally {
    globalThis.fetch = previous;
  }
});
