import { CitySizeChip } from "../../design/components/CitySizeChip";
import { ContentSections } from "../../design/components/ContentList";
import { BandChip } from "../../design/components/BandChip";
import { CountryLabel } from "../../design/components/CountryLabel";
import { countryName } from "../../lib/countries";
import { useApp } from "../../lib/state";
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
import { ApiError } from "../../api/client";
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
  const lang = useApp((s) => s.language);
  const params = useLocalSearchParams<{ request: string }>(),
    { id } = useProfile(),
    { t } = useTranslation(),
    [map, setMap] = useState(false),
    parsed = useMemo(() => {
      try {
        return {
          body: validate<RecommendationRequest>(
            "RecommendationRequest",
            JSON.parse(params.request),
          ),
        };
      } catch {
        return { error: new ApiError(400, "validation_error") };
      }
    }, [params.request]),
    body = parsed.body;
  const q = useApi<Recommendation>(
      `/profiles/${id}/acg/recommendations`,
      "Recommendation",
      !!id && !!body,
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
      <Card key={`${a.kind}-${a.id}`}>
        <BandChip band={a.band} label={a.band_label} />
        <Row
          label={a.name}
          onPress={() =>
            router.push(`/map/area/${a.id}?kind=${a.kind}&profile=${id}`)
          }
        />
      </Card>
    );
  const item = (p: Destination) => (
    <Card key={p.place_id}>
      <Row label={p.name} onPress={() => place(p)} />
      <CitySizeChip size={p.size}/>
      <CountryLabel code={p.country_code} />
      <BandChip band={p.band} label={p.band_label} />
      {p.summary_label && <Txt>{p.summary_label}</Txt>}
      {p.dominant_line && (
        <Txt>{distanceLabel(p.dominant_line.distance_km_rounded)}</Txt>
      )}
      {p.has_tradeoff && <Txt kind="caption">{t("hasTradeoff")}</Txt>}
      {d?.explanations.status === "ready" &&
        d.explanations.items[p.place_id] && (
          <Txt kind="reading">{d.explanations.items[p.place_id]}</Txt>
        )}
      {d?.explanations.status === "pending" && (
        <Skeleton variant="lines" lines={2} />
      )}
    </Card>
  );
  return (
    <Screen scroll={false} back title={d?.goal_label ?? t("whereShouldIGo")}>
      <ContentSections
        header={
          <>
            {!parsed.error && q.isPending && <Skeleton />}
            <ErrorNotice error={parsed.error ?? q.error} />
            {d && (
              <>
                {d.status === "needs_goal" ? (
                  <>
                    <Txt>{t("whichGoal")}</Txt>
                    <Choices>
                      {d.goal_options?.map((g) => (
                        <Chip
                          role="button"
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
                    <Txt>
                      {d.scope === "world"
                        ? t("world")
                        : countryName(d.scope, lang)}
                    </Txt>
                    <Choices>
                      {Object.entries(d.filters_applied)
                        .filter(([k, v]) => k !== "policy" && v != null)
                        .map(([key, value]) => (
                          <Chip
                            key={key}
                            label={
                              key === "purpose" && value === "both"
                                ? t("livingTravel")
                                : key === "city_size"
                                  ? Array.isArray(value)
                                    ? value
                                        .map((v) =>
                                          t(
                                            v === "big"
                                              ? "largeCities"
                                              : String(v),
                                          ),
                                        )
                                        .join(", ")
                                    : t(String(value))
                                  : `${t(key)}: ${Array.isArray(value) ? value.map((v) => t(String(v))).join(", ") : t(String(value))}`
                            }
                            selected
                            onPress={() => {
                              const filters = { ...body?.filters };
                              if (key === "city_size")
                                filters.city_size = ["big", "mid", "small"];
                              else if (key === "climate")
                                filters.climate = null;
                              else if (key === "max_distance_km")
                                filters.max_distance_km = null;
                              else if (key === "purpose")
                                filters.purpose = "both";
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
                  </>
                )}
              </>
            )}
          </>
        }
        sections={
          !d || d.status === "needs_goal"
            ? []
            : [
                ...(d.goal === "overall"
                  ? [
                      {
                        key: "places",
                        header: null,
                        children: d.places.map(item),
                      },
                    ]
                  : d.by_line.map((g) => ({
                      key: g.group_id,
                      header: (
                        <>
                          <Txt kind="title">{g.title}</Txt>
                          {d.explanations.status === "ready" && (
                            <Txt kind="reading">
                              {d.explanations.groups[g.group_id]}
                            </Txt>
                          )}
                        </>
                      ),
                      children: g.destinations.map(item),
                    }))),
                {
                  key: "without-destinations",
                  header: null,
                  children: d.lines_without_destinations.map((line, index) => (
                    <Card key={index}>
                      <Txt>{line.title}</Txt>
                      <Txt kind="reading">{line.text}</Txt>
                    </Card>
                  )),
                },
                ...(d.scope === "world"
                  ? [
                      {
                        key: "turkey",
                        header: (
                          <>
                            <Txt kind="title">{t("inTurkey")}</Txt>
                            {d.explanations.status === "ready" && (
                              <Txt kind="reading">
                                {d.explanations.turkey_intro}
                              </Txt>
                            )}
                          </>
                        ),
                        children: [
                          ...d.turkey.places.map(item),
                          ...d.turkey.regions.map(area),
                        ],
                      },
                    ]
                  : []),
                {
                  key: "areas",
                  header: <Txt kind="title">{t("areas")}</Txt>,
                  children: [...d.countries.map(area), ...d.regions.map(area)],
                },
              ]
        }
        footer={d ? <Txt kind="caption">{d.footer}</Txt> : undefined}
      />
    </Screen>
  );
}
