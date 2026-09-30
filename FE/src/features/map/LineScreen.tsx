import { ReportSurface as Screen } from "./ReportSurface";
import { useLocalSearchParams, router } from "expo-router";
import { useTranslation } from "react-i18next";
import { Txt, Row, ErrorNotice, Skeleton } from "../../design/components";
import { Glyph } from "../../design/components/Glyph";
import { useCatalogue } from "../../api/hooks";
import { useApi } from "../../api/resource";
import { useProfile } from "../shared/useProfile";
import { distanceLabel } from "./geometry";
import type { Body, Angle, LinePlaces } from "../../../contracts/spec-types";
export default function LineScreen() {
  const { body, angle, goal } = useLocalSearchParams<{
      body: Body;
      angle: Angle;
      goal?: string;
    }>(),
    { id } = useProfile(),
    { t } = useTranslation(),
    catalogue = useCatalogue().data,
    node = body?.endsWith("_node"),
    q = useApi<LinePlaces>(
      `/profiles/${id}/acg/lines/${body}/${angle}/places`,
      "LinePlaces",
      !!id && !node,
    );
  return (
    <Screen
      back
      title={`${catalogue.bodies[body]} · ${catalogue.angles[angle]?.line}`}
    >
      <Glyph name={body} />
      {node ? (
        <Txt>{t("nodeReference")}</Txt>
      ) : (
        <>
          <Txt kind="title">{t("placesOnLine")}</Txt>
          {q.isPending && <Skeleton />}
          <ErrorNotice error={q.error} />
          {q.data?.places.map((p) => (
            <Row
              key={p.place_id}
              label={p.name}
              detail={`${p.country_code} · ${distanceLabel(p.distance_km_rounded)} · ${p.tier_label}`}
              onPress={() =>
                router.push(
                  `/map/place/${p.place_id}?profile=${id}${goal ? `&goal=${goal}` : ""}`,
                )
              }
            />
          ))}
          {q.data?.places.length === 0 && <Txt>{t("noResults")}</Txt>}
        </>
      )}
    </Screen>
  );
}
