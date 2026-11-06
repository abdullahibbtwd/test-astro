import { space as dsSpace } from "../../design-system/theme/tokens";
import { useCountries } from "./countries";
import { BandChip } from "../../design/components/BandChip";
import { View } from "react-native";
import { ReportSurface as Screen } from "./ReportSurface";
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
  EmptyState,
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
      `/profiles/${id}/acg/countries/${encodeURIComponent(areaId)}`,
      "AreaReport",
      !!id && kind !== "region",
    ),
    d = q.data;
  const countries = useCountries(kind !== "region");
  useEffect(() => {
    const feature = countries.data?.features.find(
      (f) => f.properties?.iso2 === areaId,
    );
    if (feature) useMapSelection.getState().selectArea(feature);
  }, [countries.data, areaId]);
  if (kind === "region") {
    return (
      <Screen list back title={t("areaReport")}>
        <Txt muted>{t("regionReportsUnavailable")}</Txt>
      </Screen>
    );
  }
  return (
    <Screen list back title={d?.area.name ?? t("areaReport")}>
      {q.isPending && <Skeleton />}
      <ErrorNotice error={q.error} />
      {d && (
        <>
          {(Object.keys(d.bands) as Goal[]).map((g) => (
            <View key={g} style={{ gap: dsSpace[2] }}>
              <Txt>{catalogue.goals[g]}</Txt>
              <BandChip band={d.bands[g].band} label={d.bands[g].label} />
            </View>
          ))}
          {d.varies_by_region && <Txt>{t("variesByRegion")}</Txt>}
          <Generated part={d.overview} retry={q.retry}>
            {(data) => <Txt kind="reading">{data.text}</Txt>}
          </Generated>
          <Txt kind="title">{t("lines")}</Txt>
          {d.lines_crossing.length === 0 && (
            <EmptyState titleKey="emptyAreaLines" />
          )}
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
            <View key={p.place_id}>
              <BandChip band={p.band} label={p.band_label} />
              <Row
                label={p.name}
                onPress={() =>
                  router.push(
                    `/map/place/${p.place_id}?profile=${id}&goal=${goal}`,
                  )
                }
              />
            </View>
          ))}
          <Txt kind="caption">{d.footer}</Txt>
        </>
      )}
    </Screen>
  );
}
