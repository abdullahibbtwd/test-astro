import { useQuery } from "@tanstack/react-query";
import type { StyleSpecification } from "@maplibre/maplibre-react-native";
import { useApp } from "../../lib/state";
export function useMapStyle(url?: string) {
  const lang = useApp((s) => s.language);
  return useQuery({
    queryKey: ["map-style", url, lang],
    enabled: !!url,
    staleTime: Infinity,
    queryFn: async ({ signal }) => {
      const response = await fetch(url!, { signal });
      if (!response.ok) throw new Error("Map style unavailable");
      const style = (await response.json()) as StyleSpecification;
      if (style.version !== 8 || !Array.isArray(style.layers) || !style.sources)
        throw new Error("Invalid map style");
      const absolute = (value: string) =>
        /^[a-z]+:/i.test(value) ? value : new URL(value, url).toString();
      return {
        ...style,
        ...(typeof style.sprite === "string"
          ? { sprite: absolute(style.sprite) }
          : {}),
        ...(style.glyphs ? { glyphs: absolute(style.glyphs) } : {}),
        sources: Object.fromEntries(
          Object.entries(style.sources).map(([id, source]) => [
            id,
            {
              ...source,
              ...("url" in source && source.url
                ? { url: absolute(source.url) }
                : {}),
              ...("tiles" in source && source.tiles
                ? { tiles: source.tiles.map(absolute) }
                : {}),
            },
          ]),
        ),
        layers: style.layers.map((layer) =>
          layer.type === "symbol" && layer.layout?.["text-field"]
            ? {
                ...layer,
                layout: {
                  ...layer.layout,
                  "text-field": [
                    "coalesce",
                    ["get", `name:${lang}`],
                    ["get", "name"],
                  ],
                },
              }
            : layer,
        ),
      } as StyleSpecification;
    },
  });
}
