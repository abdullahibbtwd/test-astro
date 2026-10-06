import { create } from "zustand";
import type { Feature, Polygon, MultiPolygon } from "geojson";
export const useMapSelection = create<{
  point: [number, number] | null;
  area: Feature<Polygon | MultiPolygon> | null;
  select: (point: [number, number] | null) => void;
  selectArea: (area: Feature<Polygon | MultiPolygon> | null) => void;
}>((set) => ({
  point: null,
  area: null,
  select: (point) => set({ point, area: null }),
  selectArea: (area) => set({ area, point: null }),
}));
