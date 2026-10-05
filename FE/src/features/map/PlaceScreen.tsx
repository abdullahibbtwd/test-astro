import { ReportSurface as Screen } from "./ReportSurface";
import { Share } from "react-native";
import { useMapSelection } from "./selection";
import { useEffect, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Txt,
  Card,
  Choices,
  Chip,
  Button,
  ErrorNotice,
  Skeleton,
} from "../../design/components";
import { useApi } from "../../api/resource";
import { useProfile } from "../shared/useProfile";
import { useCatalogue } from "../../api/hooks";
import { useFlags } from "../../lib/flags";
import { Generated } from "../shared/Blocks";
import { distanceLabel } from "./geometry";
import type { PlaceReport, Goal } from "../../../contracts/spec-types";
export default function PlaceScreen() {
  const params = useLocalSearchParams<{
      placeId?: string;
      lat?: string;
      lon?: string;
      goal?: string;
    }>(),
    { id } = useProfile(),
    { t } = useTranslation(),
    catalogue = useCatalogue().data,
    flags = useFlags(),
    [error, setError] = useState<unknown>();
  const path = params.placeId
    ? `places/${encodeURIComponent(params.placeId)}`
    : `point?lat=${encodeURIComponent(params.lat ?? "")}&lon=${encodeURIComponent(params.lon ?? "")}`;
  const q = useApi<PlaceReport>(
      `/profiles/${id}/acg/${path}${path.includes("?") ? "&" : "?"}focus_goal=${params.goal ?? ""}`,
      "PlaceReport",
      !!id,
    ),
    d = q.data;
  useEffect(() => {
    if (d) useMapSelection.getState().select([d.place.lon, d.place.lat]);
  }, [d]);
  return (
    <Screen
      back
      title={
        d
          ? d.place.place_id
            ? d.place.name
            : t("selectedSpot")
          : t("placeReport")
      }
    >
      {q.isPending && <Skeleton />}
      <ErrorNotice error={error ?? q.error} />
      {d && (
        <>
          <Txt muted>{d.place.country_code}</Txt>
          {d.lines_display[0] && (
            <Txt>
              {d.lines_display[0].planet_label} ·{" "}
              {d.lines_display[0].angle_label} ·{" "}
              {distanceLabel(d.lines_display[0].distance_km_rounded)}
            </Txt>
          )}
          {d.relocation.status === "absent" && (
            <Txt>{t("relocationAbsent")}</Txt>
          )}
          <Txt kind="title">{t("suitedFor")}</Txt>
          {d.cards.map((card) => (
            <Card key={card.card}>
              <Txt kind="title">{card.title}</Txt>
              <Txt>{card.band_label}</Txt>
              {card.text ? (
                <Txt kind="reading">{card.text}</Txt>
              ) : d.reading.status === "pending" ? (
                <Skeleton />
              ) : null}
            </Card>
          ))}
          <Txt kind="title">{t("otherAreas")}</Txt>
          <Choices>
            {(Object.keys(d.goal_scores) as Goal[])
              .filter((g) => !!catalogue.goals[g] && !d.cards.some((c) => c.goal === g))
              .map((g) => (
                <Chip
                  key={g}
                  label={`${catalogue.goals[g]} · ${d.goal_scores[g].label}`}
                  selected={params.goal === g}
                  onPress={() => router.setParams({ goal: g })}
                />
              ))}
          </Choices>
          <Txt kind="title">{t("nearbyLines")}</Txt>
          {d.lines_display.map((line, i) => (
            <Txt key={i} muted={!line.read_in_prose}>
              {line.planet_label} · {line.angle_label} · {line.tier_label} ·{" "}
              {distanceLabel(line.distance_km_rounded)}
            </Txt>
          ))}
          {d.parans_display.length > 0 && (
            <Txt kind="title">{t("latitudeCrossings")}</Txt>
          )}
          {d.parans_display.map((p) => (
            <Txt key={p.id}>
              {p.label} · {t(p.north_south)} ·{" "}
              {distanceLabel(p.distance_km_rounded)}
            </Txt>
          ))}
          <Generated part={d.reading} retry={q.retry}>
            {(reading) =>
              reading.sections.map((s) => (
                <Card key={s.key}>
                  <Txt kind="title">{s.title}</Txt>
                  {s.paragraphs.map((p) => (
                    <Txt key={p.slot_id} kind="reading">
                      {p.text}
                    </Txt>
                  ))}
                </Card>
              ))
            }
          </Generated>
          <Txt kind="caption">{d.footer}</Txt>
          {flags.askAstrology && d.place.place_id && (
            <Button
              label={t("ask")}
              onPress={() =>
                router.push(`/ask?profile=${id}&place_id=${d.place.place_id}`)
              }
            />
          )}
          <Button
            secondary
            label={t("share")}
            onPress={() => {
              const text =
                d.reading.status === "ready"
                  ? d.reading.sections[0]?.paragraphs
                      .map((p) => p.text)
                      .join("\n\n")
                  : "";
              void Share.share({
                message: [d.place.name, text, d.footer]
                  .filter(Boolean)
                  .join("\n\n"),
              }).catch(setError);
            }}
          />
          {d.place.country_code && (
            <Button
              secondary
              label={t("countryReport")}
              onPress={() =>
                router.push(
                  `/map/area/${d.place.country_code}?kind=country&profile=${id}`,
                )
              }
            />
          )}
        </>
      )}
    </Screen>
  );
}
