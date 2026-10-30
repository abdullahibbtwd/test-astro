import { useQuery } from "@tanstack/react-query";
import { useApp } from "../../lib/state";
import { loadMapStyle } from "./style-load";

export { loadMapStyle } from "./style-load";

export function useMapStyle(url?: string) {
  const lang = useApp((s) => s.language);
  return useQuery({
    queryKey: ["map-style", url, lang],
    enabled: !!url,
    staleTime: Infinity,
    queryFn: ({ signal }) => loadMapStyle(url!, lang, signal),
  });
}
