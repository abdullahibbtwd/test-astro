import { useApi } from "../../api/resource";
import type { FeatureCollection, Polygon, MultiPolygon } from "geojson";
import type { StyleSpecification } from "@maplibre/maplibre-react-native";
import { useMapStyle } from "./style";
import { useMapSelection } from "./selection";
import { mapGlyphImages } from "./glyph-images";
import { useEffect, useMemo, useRef, useState } from "react";
import { View } from "react-native";
import {
  Map,
  Images,
  Camera,
  GeoJSONSource,
  Layer,
  type FilterSpecification,
  type CameraRef,
  type LineLayerSpecification,
} from "@maplibre/maplibre-react-native";
import { useConfig } from "../../api/hooks";
import { useTheme } from "../../design/theme";
import { colors } from "../../design/tokens";
import { Txt, ErrorNotice, Skeleton } from "../../design/components";
import { useTranslation } from "react-i18next";
import { heatCells } from "./geometry";
import { bandColor } from "../../design/bands";
import type {
  AcgLines,
  AcgHeat,
  Body,
  Angle,
  Destination,
} from "../../../contracts/spec-types";
export const planetColors = {
  sun: ["#A67C00", "#E7B93A"],
  moon: ["#7D8BA3", "#A9B5C9"],
  mercury: ["#2E9A93", "#4FC2BA"],
  venus: ["#C9658F", "#E48DB2"],
  mars: ["#C8452F", "#E86A52"],
  jupiter: ["#6A4FB3", "#9C86E0"],
  saturn: ["#7A6848", "#B8A27A"],
  uranus: ["#2F8FD8", "#5DB0F0"],
  neptune: ["#1F5FA0", "#5A8FD6"],
  pluto: ["#3B3B40", "#D6D6DC"],
};
export function MapCanvas({
  lines,
  fill = false,
  heat,
  bodies,
  parans = false,
  center = [29, 41],
  onLine,
  onPoint,
  destinations = [],
  onDestination,
  emphasized,
}: {
  fill?: boolean;
  lines?: AcgLines;
  heat?: AcgHeat;
  bodies: Body[];
  parans?: boolean;
  center?: [number, number];
  onLine?: (body: Body, angle: Angle) => void;
  onPoint?: (point: [number, number], zoom: number, long: boolean) => void;
  destinations?: Destination[];
  onDestination?: (place: Destination) => void;
  emphasized?: string[];
}) {
  const camera = useRef<CameraRef>(null);
  const config = useConfig(),
    theme = useTheme(),
    dark = theme === colors.dark,
    { t } = useTranslation(),
    [zoom, setZoom] = useState(2),
    cells = useMemo(() => (heat ? heatCells(heat) : undefined), [heat]);
  const style = config.data?.map_style_url[dark ? "dark" : "light"];
  const preview = __DEV__ && !style;
  const countries = useApi<FeatureCollection<Polygon | MultiPolygon>>(
    "/geo/countries.geojson",
    "CountryGeometry",
    preview,
  );
  const previewStyle = useMemo<StyleSpecification>(
    () => ({
      version: 8,
      sources: {
        "preview-countries": {
          type: "geojson",
          data: countries.data ?? { type: "FeatureCollection", features: [] },
        },
      },
      layers: [
        {
          id: "ocean",
          type: "background",
          paint: { "background-color": dark ? "#151F2C" : "#D9E5EC" },
        },
        ...(countries.data
          ? ([
              {
                id: "preview-land",
                source: "preview-countries",
                type: "fill",
                paint: { "fill-color": dark ? "#303C48" : "#F1EEE7" },
              },
              {
                id: "preview-borders",
                source: "preview-countries",
                type: "line",
                paint: {
                  "line-color": dark ? "#71808B" : "#9AADA9",
                  "line-width": 0.6,
                },
              },
            ] as StyleSpecification["layers"])
          : []),
      ],
    }),
    [dark, countries.data],
  );
  const mapStyle = useMapStyle(style),
    selectedPoint = useMapSelection((s) => s.point),
    selectedArea = useMapSelection((s) => s.area);
  useEffect(() => {
    if (selectedPoint)
      camera.current?.flyTo({ center: selectedPoint, zoom: 6, duration: 650 });
  }, [selectedPoint]);
  const filtered = useMemo(
    () =>
      lines
        ? {
            ...lines.lines,
            features: lines.lines.features
              .filter((f) => bodies.includes(f.properties.body))
              .map((f) => ({
                ...f,
                properties: {
                  ...f.properties,
                  emphasis:
                    !emphasized ||
                    emphasized.includes(
                      `${f.properties.body}:${f.properties.angle}`,
                    )
                      ? 1
                      : 0.2,
                },
              })),
          }
        : undefined,
    [lines, bodies, emphasized],
  );
  const lineColor: NonNullable<LineLayerSpecification["paint"]>["line-color"] =
    [
      "match",
      ["get", "body"],
      "sun",
      planetColors.sun[dark ? 1 : 0]!,
      ...Object.entries(planetColors)
        .filter(([key]) => key !== "sun")
        .flatMap(([key, value]) => [key, value[dark ? 1 : 0]!]),
      theme.ink3,
    ];
  if (!style && !preview)
    return (
      <View style={{ padding: 24, backgroundColor: theme.surfaceAlt, gap: 12 }}>
        <Txt>{t("mapStyleMissing")}</Txt>
        <Txt kind="caption">{t("mapSearchAvailable")}</Txt>
      </View>
    );
  if (preview && countries.isPending) return <Skeleton />;
  if (!preview && mapStyle.isPending) return <Skeleton />;
  if (!preview && !mapStyle.data)
    return (
      <ErrorNotice
        error={mapStyle.error}
        retry={() => void mapStyle.refetch()}
      />
    );
  return (
    <View
      style={
        fill
          ? { flex: 1, overflow: "hidden" }
          : { height: 420, borderRadius: 12, overflow: "hidden" }
      }
    >
      <Map
        mapStyle={preview ? previewStyle : mapStyle.data!}
        attribution
        onRegionDidChange={(e) => setZoom(e.nativeEvent.zoom)}
        onPress={(e) => onPoint?.(e.nativeEvent.lngLat, zoom, false)}
        onLongPress={(e) => onPoint?.(e.nativeEvent.lngLat, zoom, true)}
      >
        {selectedArea && (
          <GeoJSONSource id="selected-area" data={selectedArea}>
            <Layer
              id="selected-area-fill"
              type="fill"
              paint={{ "fill-color": theme.accent, "fill-opacity": 0.1 }}
            />
            <Layer
              id="selected-area-border"
              type="line"
              paint={{ "line-color": theme.accent, "line-width": 2 }}
            />
          </GeoJSONSource>
        )}
        <Images images={mapGlyphImages} />
        <Camera ref={camera} initialViewState={{ center, zoom: 2 }} />
        {cells && (
          <GeoJSONSource id="heat" data={cells}>
            <Layer
              id="heat-fill"
              type="fill"
              paint={{
                "fill-color": [
                  "match",
                  ["get", "level"],
                  2,
                  bandColor("strongly_supportive", dark),
                  1,
                  bandColor("supportive", dark),
                  0,
                  bandColor("mixed", dark),
                  bandColor("challenging", dark),
                ],
                "fill-opacity": dark ? 0.45 : 0.35,
              }}
            />
          </GeoJSONSource>
        )}
        {parans && lines && (
          <GeoJSONSource id="parans" data={lines.parans}>
            <Layer
              id="parans-lines"
              type="line"
              paint={{
                "line-color": theme.ink3,
                "line-width": 1,
                "line-dasharray": [1.5, 3],
              }}
            />
            {[0, 1].map((index) => (
              <Layer
                key={index}
                id={`paran-glyph-${index}`}
                type="symbol"
                layout={{
                  "symbol-placement": "line",
                  "symbol-spacing": 280,
                  "icon-image": [
                    "concat",
                    dark ? "dark-" : "light-",
                    ["at", index, ["get", "bodies"]],
                  ],
                  "icon-size": 0.4,
                  "icon-offset": [index === 0 ? -30 : 30, 0],
                  "icon-rotation-alignment": "viewport",
                  "icon-allow-overlap": true,
                }}
              />
            ))}
            <Layer
              id="paran-cross"
              type="symbol"
              layout={{
                "symbol-placement": "line",
                "symbol-spacing": 280,
                "text-field": "×",
                "text-size": 12,
                "text-rotation-alignment": "viewport",
              }}
              paint={{ "text-color": theme.ink3 }}
            />
          </GeoJSONSource>
        )}
        {filtered && (
          <GeoJSONSource
            id="planet-lines"
            data={filtered}
            hitbox={{ top: 12, bottom: 12, left: 12, right: 12 }}
            onPress={(e) => {
              e.stopPropagation();
              const properties = e.nativeEvent.features[0]?.properties;
              if (properties) onLine?.(properties.body, properties.angle);
            }}
          >
            {(["ASC", "DSC", "MC", "IC"] as Angle[]).map((angle) => (
              <Layer
                key={angle}
                id={`lines-${angle}`}
                type="line"
                filter={
                  [
                    "all",
                    ["==", ["get", "angle"], angle],
                    ["==", ["get", "read"], true],
                  ] as FilterSpecification
                }
                paint={{
                  "line-color": lineColor,
                  "line-opacity": ["get", "emphasis"],
                  "line-width": angle === "ASC" || angle === "DSC" ? 2.5 : 2,
                  ...(angle === "DSC"
                    ? { "line-dasharray": [6, 4] }
                    : angle === "IC"
                      ? { "line-dasharray": [1.5, 3] }
                      : {}),
                }}
              />
            ))}
            <Layer
              id="line-labels"
              type="symbol"
              layout={{
                "symbol-placement": "line",
                "symbol-spacing": 280,
                "icon-image": [
                  "concat",
                  dark ? "dark-" : "light-",
                  ["get", "body"],
                  "-",
                  ["get", "angle"],
                ],
                "icon-size": 0.5,
                "icon-rotation-alignment": "viewport",
              }}
            />
            <Layer
              id="nodes"
              type="line"
              filter={["==", ["get", "read"], false]}
              paint={{
                "line-color": theme.ink3,
                "line-width": 1,
                "line-dasharray": [3, 4],
              }}
            />
          </GeoJSONSource>
        )}
        {selectedPoint && (
          <GeoJSONSource
            id="selected-place"
            data={{
              type: "Feature",
              properties: {},
              geometry: { type: "Point", coordinates: selectedPoint },
            }}
          >
            <Layer
              id="selected-place-pin"
              type="circle"
              paint={{
                "circle-radius": 9,
                "circle-color": theme.accent,
                "circle-stroke-color": theme.surface,
                "circle-stroke-width": 3,
              }}
            />
          </GeoJSONSource>
        )}
        {destinations.length > 0 && (
          <GeoJSONSource
            id="destinations"
            data={{
              type: "FeatureCollection",
              features: destinations.map((p) => ({
                type: "Feature",
                properties: { id: p.place_id, color: bandColor(p.band, dark) },
                geometry: { type: "Point", coordinates: [p.lon, p.lat] },
              })),
            }}
            onPress={(e) => {
              e.stopPropagation();
              const id = e.nativeEvent.features[0]?.properties?.id,
                p = destinations.find((d) => d.place_id === id);
              if (p) onDestination?.(p);
            }}
          >
            <Layer
              id="destination-pins"
              type="circle"
              paint={{
                "circle-radius": 8,
                "circle-color": ["get", "color"],
                "circle-stroke-color": theme.surface,
                "circle-stroke-width": 2,
              }}
            />
          </GeoJSONSource>
        )}
      </Map>
      {preview && (
        <View
          pointerEvents="none"
          style={{
            position: "absolute",
            bottom: fill ? 76 : 8,
            left: 8,
            backgroundColor: theme.surface,
            padding: 4,
          }}
        >
          <Txt kind="caption">{t("previewMap")}</Txt>
        </View>
      )}
    </View>
  );
}
