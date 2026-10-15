import { useQuery } from "@tanstack/react-query";
import type { FeatureCollection, Polygon, MultiPolygon } from "geojson";
import { queryClient } from "../../api/query";
import { request } from "../../api/client";
export type Countries = FeatureCollection<
  Polygon | MultiPolygon,
  { iso2: string; name_en: string; name_tr: string }
>;
const options = {
  queryKey: ["resource", "shared", "/geo/countries.geojson"],
  staleTime: Infinity,
  gcTime: Infinity,
  queryFn: () =>
    request<Countries>("GET", "/geo/countries.geojson", "CountryGeometry"),
};
export const loadCountries = () => queryClient.fetchQuery(options);
export const useCountries = (enabled = true) =>
  useQuery({ ...options, enabled });
