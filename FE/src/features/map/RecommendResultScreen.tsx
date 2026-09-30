import { useMemo, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Card,
  Row,
  Choices,
  Chip,
  Button,
  ErrorNotice,
  Skeleton,
} from "../../design/components";
import { useApi } from "../../api/resource";
import { useProfile } from "../shared/useProfile";
import { Generated } from "../shared/Blocks";
import { MapCanvas, planetColors } from "./MapCanvas";
import { distanceLabel } from "./geometry";
import { validate } from "../../api/zod";
import type {
  Recommendation,
  RecommendationRequest,
  Destination,
  AreaRef,
  Body,
  AcgLines,
} from "../../../contracts/spec-types";
export default function RecommendResultScreen() {
  const params = useLocalSearchParams<{ request: string }>(),
    { id } = useProfile(),
    { t } = useTranslation(),
    [map, setMap] = useState(false),
    body = useMemo(
      () =>
        validate<RecommendationRequest>(
          "RecommendationRequest",
          JSON.parse(params.request),
        ),
      [params.request],
    );
  const q = useApi<Recommendation>(
      `/profiles/${id}/acg/recommendations`,
      "Recommendation",
      !!id,
      body,
    ),
    d = q.data,
    lines = useApi<AcgLines>(
      `/profiles/${id}/acg/lines`,
      "AcgLines",
      !!id && map,
    );
  const place = (p: Destination) =>
      router.push(
        `/map/place/${p.place_id}?profile=${id}${d?.goal && d.goal !== "overall" ? `&goal=${d.goal}` : ""}`,
      ),
    area = (a: AreaRef) => (
      <Row
        key={`${a.kind}-${a.id}`}
        label={a.name}
        detail={a.band_label}
        onPress={() =>
          router.push(`/map/area/${a.id}?kind=${a.kind}&profile=${id}`)
        }
      />
    );
  const item = (p: Destination) => (
    <Card key={p.place_id}>
      <Row
        label={p.name}
        detail={`${p.country_code} · ${t(p.size)} · ${p.summary_label ?? p.band_label}`}
        onPress={() => place(p)}
      />
      {p.dominant_line && (
        <Txt>{distanceLabel(p.dominant_line.distance_km_rounded)}</Txt>
      )}
      {p.has_tradeoff && <Txt kind="caption">{t("hasTradeoff")}</Txt>}
      {d?.explanations.status === "ready" &&
        d.explanations.items[p.place_id] && (
          <Txt kind="reading">{d.explanations.items[p.place_id]}</Txt>
        )}
      {d?.explanations.status === "pending" && <Skeleton />}
    </Card>
  );
  return (
    <Screen back title={d?.goal_label ?? t("whereShouldIGo")}>
      {q.isPending && <Skeleton />}
      <ErrorNotice error={q.error} />
      {d && (
        <>
          {d.status === "needs_goal" ? (
            <>
              <Txt>{t("whichGoal")}</Txt>
              <Choices>
                {d.goal_options?.map((g) => (
                  <Chip
                    key={g.goal}
                    label={g.label}
                    selected={false}
                    onPress={() =>
                      router.setParams({
                        request: JSON.stringify({
                          ...body,
                          goal: g.goal,
                          query_text: undefined,
                        }),
                      })
                    }
                  />
                ))}
              </Choices>
            </>
          ) : (
            <>
              {d.status === "thin_result" && <Txt>{t("thinResult")}</Txt>}
              <Txt>{d.scope === "world" ? t("world") : d.scope}</Txt>
              <Choices>
                {Object.entries(d.filters_applied)
                  .filter(([k, v]) => k !== "policy" && v != null)
                  .map(([key, value]) => (
                    <Chip
                      key={key}
                      label={`${t(key)}: ${Array.isArray(value) ? value.map((v) => t(String(v))).join(", ") : t(String(value))} ×`}
                      selected
                      onPress={() => {
                        const filters = { ...body.filters };
                        if (key === "city_size")
                          filters.city_size = ["big", "mid", "small"];
                        else if (key === "climate") filters.climate = null;
                        else if (key === "max_distance_km")
                          filters.max_distance_km = null;
                        else if (key === "purpose") filters.purpose = "both";
                        else delete filters[key as keyof typeof filters];
                        router.setParams({
                          request: JSON.stringify({ ...body, filters }),
                        });
                      }}
                    />
                  ))}
              </Choices>
              <Button
                secondary
                label={t("changeFilters")}
                onPress={() =>
                  router.replace(
                    `/map/recommend?profile=${id}&request=${encodeURIComponent(JSON.stringify(body))}`,
                  )
                }
              />
              <Generated part={d.explanations} retry={q.retry}>
                {(e) => <Txt kind="reading">{e.intro}</Txt>}
              </Generated>
              <Choices>
                <Chip
                  label={t("list")}
                  selected={!map}
                  onPress={() => setMap(false)}
                />
                <Chip
                  label={t("map")}
                  selected={map}
                  onPress={() => setMap(true)}
                />
              </Choices>
              {map && (
                <MapCanvas
                  emphasized={d.by_line.flatMap((g) => {
                    const line = g.line;
                    return "body" in line
                      ? [`${line.body}:${line.angle}`]
                      : line.bodies.map(
                          (body, i) => `${body}:${line.angles[i]}`,
                        );
                  })}
                  lines={lines.data}
                  bodies={Object.keys(planetColors) as Body[]}
                  destinations={d.places}
                  onDestination={place}
                />
              )}
              {d.goal === "overall"
                ? d.places.map(item)
                : d.by_line.map((g) => (
                    <Card key={g.group_id}>
                      <Txt kind="title">{g.title}</Txt>
                      {d.explanations.status === "ready" && (
                        <Txt kind="reading">
                          {d.explanations.groups[g.group_id]}
                        </Txt>
                      )}
                      {g.destinations.map(item)}
                    </Card>
                  ))}
              {d.lines_without_destinations.map((l, i) => (
                <Card key={i}>
                  <Txt>{l.title}</Txt>
                  <Txt kind="reading">{l.text}</Txt>
                </Card>
              ))}
              {d.scope === "world" && (
                <>
                  <Txt kind="title">{t("inTurkey")}</Txt>
                  {d.explanations.status === "ready" && (
                    <Txt kind="reading">{d.explanations.turkey_intro}</Txt>
                  )}
                  {d.turkey.places.map(item)}
                  {d.turkey.regions.map(area)}
                </>
              )}
              <Txt kind="title">{t("areas")}</Txt>
              {d.countries.map(area)}
              {d.regions.map(area)}
              <Txt kind="caption">{d.footer}</Txt>
            </>
          )}
        </>
      )}
    </Screen>
  );
}
