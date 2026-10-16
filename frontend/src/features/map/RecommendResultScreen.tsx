import {
  space as dsSpace,
  radius as dsRadius,
} from "../../design-system/theme/tokens";
import { CitySizeChip } from "../../design/components/CitySizeChip";
import { ContentSections } from "../../design/components/ContentList";
import { BandChip } from "../../design/components/BandChip";
import { CountryLabel } from "../../design/components/CountryLabel";
import { countryName } from "../../lib/countries";
import { useApp } from "../../lib/state";
import { useMemo, useState } from "react";
import { View } from "react-native";
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
import { useTheme } from "../../design/theme";
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
  const theme = useTheme();
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
      <View
        style={{
          flexDirection: "row",
          flexWrap: "wrap",
          gap: dsSpace[2],
          alignItems: "center",
        }}
      >
        <CitySizeChip size={p.size} />
        <CountryLabel code={p.country_code} />
        <BandChip band={p.band} label={p.band_label} compact />
      </View>
      {p.summary_label && <Txt muted>{p.summary_label}</Txt>}
      {p.dominant_line && (
        <Txt kind="caption" muted>
          {distanceLabel(p.dominant_line.distance_km_rounded)}
        </Txt>
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
  const filterLabel = (key: string, value: unknown) => {
    if (key === "purpose" && value === "both") return t("livingTravel");
    if (key === "city_size")
      return Array.isArray(value)
        ? value
            .map((v) => t(v === "big" ? "largeCities" : String(v)))
            .join(", ")
        : t(String(value));
    const shown = Array.isArray(value)
      ? value.map((v) => t(String(v))).join(", ")
      : t(String(value));
    return `${t(key)}: ${shown}`;
  };
  return (
    <Screen scroll={false} back title={d?.goal_label ?? t("whereShouldIGo")}>
      <ContentSections
        header={
          <View style={{ gap: dsSpace[4], marginBottom: dsSpace[4] }}>
            {!parsed.error && q.isPending && <Skeleton />}
            <ErrorNotice error={parsed.error ?? q.error} />
            {d && (
              <>
                {d.status === "needs_goal" ? (
                  <View style={{ gap: dsSpace[3] }}>
                    <Txt>{t("whichGoal")}</Txt>
                    <Choices gap={dsSpace[3]}>
                      {d.goal_options?.map((g) => (
                        <Chip
                          role="button"
                          compact
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
                  </View>
                ) : (
                  <>
                    {d.status === "thin_result" && <Txt>{t("thinResult")}</Txt>}
                    <View style={{ gap: dsSpace[3] }}>
                      <Txt kind="caption" muted>
                        {d.scope === "world"
                          ? t("world")
                          : countryName(d.scope, lang)}
                      </Txt>
                      <Choices gap={dsSpace[3]}>
                        {Object.entries(d.filters_applied)
                          .filter(([k, v]) => k !== "policy" && v != null)
                          .map(([key, value]) => (
                            <Chip
                              key={key}
                              compact
                              label={filterLabel(key, value)}
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
                                else
                                  delete filters[key as keyof typeof filters];
                                router.setParams({
                                  request: JSON.stringify({
                                    ...body,
                                    filters,
                                  }),
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
                    </View>
                    <View style={{ gap: dsSpace[3] }}>
                      <Generated part={d.explanations} retry={q.retry}>
                        {(e) => <Txt kind="reading">{e.intro}</Txt>}
                      </Generated>
                    </View>
                    <View
                      style={{
                        marginTop: dsSpace[1],
                        paddingTop: dsSpace[4],
                        borderTopWidth: 1,
                        borderTopColor: theme.hair,
                        gap: dsSpace[3],
                      }}
                    >
                      <View
                        style={{
                          flexDirection: "row",
                          flexWrap: "wrap",
                          gap: dsSpace[2],
                          padding: dsSpace[1],
                          borderRadius: dsRadius.md,
                          borderWidth: 1,
                          borderColor: theme.borderControl,
                          alignSelf: "flex-start",
                        }}
                      >
                        {(
                          [
                            [false, "list"],
                            [true, "map"],
                          ] as const
                        ).map(([showMap, label]) => (
                          <Chip
                            key={label}
                            compact
                            label={t(label)}
                            selected={map === showMap}
                            onPress={() => setMap(showMap)}
                          />
                        ))}
                      </View>
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
                    </View>
                  </>
                )}
              </>
            )}
          </View>
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
