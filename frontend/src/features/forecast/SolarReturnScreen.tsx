import { useMemo, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { useApi } from "../../api/resource";
import { useProfile } from "../shared/useProfile";
import { useApp } from "../../lib/state";
import { SolarReturnSkeleton } from "../step3/SolarReturnSkeleton";
import { buildSolarReturnSkeleton } from "../step3/math";
import type { SolarReturn } from "../../../contracts/spec-types";

/**
 * Solar Return route screen — skeleton UI over Phase 1–2 math.
 * Interpretation is always the pending-astrologer placeholder until copy ships.
 */
export default function SolarReturnScreen() {
  const params = useLocalSearchParams<{ year: string }>(),
    { id, profile } = useProfile(),
    app = useApp(),
    { t } = useTranslation(),
    initialYear = Number.parseInt(params.year || "", 10),
    [year, setYear] = useState(
      Number.isFinite(initialYear) ? initialYear : new Date().getFullYear(),
    );
  const placeId =
    (profile?.is_self
      ? app.me?.current_place?.place_id
      : profile?.current_place?.place_id) ?? profile?.birth.place.place_id;
  const query = useApi<SolarReturn>(
    `/profiles/${id}/solar-return?year=${year}${placeId ? `&place_id=${encodeURIComponent(placeId)}` : ""}`,
    "SolarReturn",
    !!id,
  );
  const model = useMemo(() => {
    if (!query.data) return null;
    return buildSolarReturnSkeleton({
      return_utc: query.data.return_utc,
      year,
      chart: query.data.chart,
      place_label: query.data.place?.name,
    });
  }, [query.data, year]);
  const status = query.isPending
    ? "loading"
    : query.error
      ? "error"
      : model
        ? "ready"
        : "idle";
  return (
    <SolarReturnSkeleton
      title={t("solar_return")}
      year={year}
      onYearChange={(next) => {
        setYear(next);
        router.setParams({ year: String(next) });
      }}
      status={status}
      model={model}
      error={query.error}
      onRetry={() => {
        void query.refetch();
      }}
    />
  );
}
