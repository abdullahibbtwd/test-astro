import { ReportSurface as Screen } from "./ReportSurface";
import type { FeatureCollection, Polygon, MultiPolygon } from "geojson";
import { useMapSelection } from "./selection";
import { useEffect, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Txt,
  Row,
  Choices,
  Chip,
  ErrorNotice,
  Skeleton,
} from "../../design/components";
import { useCatalogue } from "../../api/hooks";
import { useApi } from "../../api/resource";
import { useProfile } from "../shared/useProfile";
import { Generated } from "../shared/Blocks";
import type { AreaReport, Goal } from "../../../contracts/spec-types";
export default function AreaScreen() {
  const { areaId, kind } = useLocalSearchParams<{
      areaId: string;
      kind: string;
    }>(),
    { id } = useProfile(),
    { t } = useTranslation(),
    catalogue = useCatalogue().data,
    [goal, setGoal] = useState<Goal>("love"),
    q = useApi<AreaReport>(
      `/profiles/${id}/acg/${kind === "region" ? "regions" : "countries"}/${encodeURIComponent(areaId)}`,
      "AreaReport",
      !!id,
    ),
    d = q.data;
  const geometry = useApi<FeatureCollection<Polygon | MultiPolygon>>(
    kind === "region"
      ? `/geo/regions/${d?.area.iso2 ?? ""}.geojson`
      : "/geo/countries.geojson",
    kind === "region" ? "RegionGeometry" : "CountryGeometry",
    kind !== "region" || !!d,
  );
  useEffect(() => {
    const feature = geometry.data?.features.find((f) =>
      kind === "region"
        ? f.properties?.admin1_id === areaId
        : f.properties?.iso2 === areaId,
    );
    if (feature) useMapSelection.getState().selectArea(feature);
  }, [geometry.data, areaId, kind]);
  return (
    <Screen back title={d?.area.name ?? t("areaReport")}>
      {q.isPending && <Skeleton />}
      <ErrorNotice error={q.error} />
      {d && (
        <>
          {(Object.keys(d.bands) as Goal[]).map((g) => (
            <Txt key={g}>
              {catalogue.goals[g]} · {d.bands[g].label}
            </Txt>
          ))}
          {d.varies_by_region && <Txt>{t("variesByRegion")}</Txt>}
          <Generated part={d.overview} retry={q.retry}>
            {(data) => <Txt kind="reading">{data.text}</Txt>}
          </Generated>
          <Txt kind="title">{t("lines")}</Txt>
          {d.lines_crossing.map((l, i) => (
            <Row
              key={i}
              label={`${l.planet_label} · ${l.angle_label}`}
              onPress={() =>
                router.push(`/map/line/${l.body}/${l.angle}?profile=${id}`)
              }
            />
          ))}
          <Txt kind="title">{t("bestCities")}</Txt>
          <Choices>
            {(Object.keys(d.best_cities) as Goal[]).map((g) => (
              <Chip
                key={g}
                label={catalogue.goals[g]}
                selected={goal === g}
                onPress={() => setGoal(g)}
              />
            ))}
          </Choices>
          {d.best_cities[goal]?.map((p) => (
            <Row
              key={p.place_id}
              label={p.name}
              detail={p.band_label}
              onPress={() =>
                router.push(
                  `/map/place/${p.place_id}?profile=${id}&goal=${goal}`,
                )
              }
            />
          ))}
          {d.regions?.map((r) => (
            <Row
              key={r.admin1_id}
              label={r.name}
              onPress={() =>
                router.push(
                  `/map/area/${r.admin1_id}?kind=region&profile=${id}`,
                )
              }
            />
          ))}
          <Txt kind="caption">{d.footer}</Txt>
        </>
      )}
    </Screen>
  );
}
