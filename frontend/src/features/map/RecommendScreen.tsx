import { space as dsSpace } from "../../design-system/theme/tokens";
import { useState } from "react";
import { View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Field,
  Choices,
  Chip,
  Button,
} from "../../design/components";
import { validate } from "../../api/zod";
import { useCatalogue } from "../../api/hooks";
import { useProfile } from "../shared/useProfile";
import { MapSearch } from "./MapSearch";
import type {
  Goal,
  RecommendationRequest,
} from "../../../contracts/spec-types";
type Filters = NonNullable<RecommendationRequest["filters"]>;
export default function RecommendScreen() {
  const params = useLocalSearchParams<{ request?: string }>();
  let initial: RecommendationRequest = {};
  try {
    initial = params.request
      ? validate<RecommendationRequest>(
          "RecommendationRequest",
          JSON.parse(params.request),
        )
      : {};
  } catch {
    /* A malformed link uses defaults. */
  }
  const { id } = useProfile(),
    { t } = useTranslation(),
    cat = useCatalogue().data,
    [goal, setGoal] = useState<Goal | "overall">(initial.goal ?? "overall"),
    [text, setText] = useState(initial.query_text ?? ""),
    [scope, setScope] = useState(initial.scope ?? "world"),
    [scopeName, setScopeName] = useState(""),
    [country, setCountry] = useState(false),
    [refine, setRefine] = useState(false),
    [filters, setFilters] = useState<Filters>(initial.filters ?? {});
  const toggle = <K extends "regions" | "city_size" | "climate">(
    key: K,
    value: NonNullable<Filters[K]>[number],
    defaults: NonNullable<Filters[K]>,
  ) => {
    const selected = (filters[key] ?? defaults) as string[];
    setFilters({
      ...filters,
      [key]: selected.includes(value)
        ? selected.filter((v) => v !== value)
        : [...selected, value],
    });
  };
  const regions = [
    "europe",
    "turkey",
    "mediterranean",
    "middle_east_gulf",
    "caucasus",
    "americas",
    "east_asia",
    "south_southeast_asia",
    "oceania",
    "central_asia",
  ] as const;
  const submit = () => {
    const body: RecommendationRequest = {
      ...(text.trim() ? { query_text: text.trim() } : { goal }),
      scope,
      ...(Object.keys(filters).length ? { filters } : {}),
    };
    router.push(
      `/map/recommend/result?profile=${id}&request=${encodeURIComponent(JSON.stringify(body))}`,
    );
  };
  return (
    <Screen back title={t("whereShouldIGo")}>
      <Choices gap={dsSpace[3]}>
        {(["overall", ...Object.keys(cat.goals)] as (Goal | "overall")[]).map(
          (g) => (
            <Chip
              key={g}
              compact
              label={g === "overall" ? t("overall") : cat.goals[g]}
              selected={!text && goal === g}
              onPress={() => {
                setGoal(g);
                setText("");
              }}
            />
          ),
        )}
      </Choices>
      <Field
        label={t("askOwnWords")}
        value={text}
        onChangeText={setText}
        maxLength={1000}
      />
      <View style={{ gap: dsSpace[3] }}>
        <Txt kind="title">{t("scope")}</Txt>
        <Choices gap={dsSpace[3]}>
          <Chip
            compact
            label={t("world")}
            selected={scope === "world"}
            onPress={() => setScope("world")}
          />
          <Chip
            compact
            label="Türkiye"
            selected={scope === "TR"}
            onPress={() => setScope("TR")}
          />
          <Chip
            compact
            label={scopeName || t("chooseCountry")}
            selected={!["world", "TR"].includes(scope)}
            onPress={() => setCountry(!country)}
          />
        </Choices>
      </View>
      {country && (
        <MapSearch
          areasOnly
          onSelect={(p) => {
            setScope(p.country_code);
            setScopeName(p.country_name);
            setCountry(false);
          }}
        />
      )}
      <Button
        secondary
        label={t("refine")}
        onPress={() => setRefine(!refine)}
      />
      {refine && (
        <View style={{ gap: dsSpace[4] }}>
          <View style={{ gap: dsSpace[2] }}>
            <Txt kind="caption" muted>
              {t("regions")}
            </Txt>
            <Choices multi gap={dsSpace[3]}>
              {regions.map((r) => (
                <Chip
                  role="checkbox"
                  compact
                  key={r}
                  label={t(r)}
                  selected={(filters.regions ?? regions).includes(r)}
                  onPress={() => toggle("regions", r, [...regions])}
                />
              ))}
            </Choices>
          </View>
          <View style={{ gap: dsSpace[2] }}>
            <Txt kind="caption" muted>
              {t("citySize")}
            </Txt>
            <Choices multi gap={dsSpace[3]}>
              {(["big", "mid", "small"] as const).map((s) => (
                <Chip
                  role="checkbox"
                  compact
                  key={s}
                  label={t(s)}
                  selected={(filters.city_size ?? ["big", "mid"]).includes(s)}
                  onPress={() => toggle("city_size", s, ["big", "mid"])}
                />
              ))}
            </Choices>
          </View>
          <View style={{ gap: dsSpace[2] }}>
            <Txt kind="caption" muted>
              {t("maxDistance")}
            </Txt>
            <Choices gap={dsSpace[3]}>
              {[0, 500, 1000, 2000, 3000, 5000].map((km) => (
                <Chip
                  compact
                  key={km}
                  label={km ? `≈ ${km.toLocaleString()} km` : t("off")}
                  selected={(filters.max_distance_km ?? 0) === km}
                  onPress={() =>
                    setFilters({ ...filters, max_distance_km: km || null })
                  }
                />
              ))}
            </Choices>
          </View>
          <View style={{ gap: dsSpace[2] }}>
            <Txt kind="caption" muted>
              {t("climate")}
            </Txt>
            <Choices multi gap={dsSpace[3]}>
              {(["warm", "mild", "cold"] as const).map((c) => (
                <Chip
                  role="checkbox"
                  compact
                  key={c}
                  label={t(c)}
                  selected={(filters.climate ?? []).includes(c)}
                  onPress={() => toggle("climate", c, [])}
                />
              ))}
            </Choices>
          </View>
          <View style={{ gap: dsSpace[2] }}>
            <Txt kind="caption" muted>
              {t("purpose")}
            </Txt>
            <Choices gap={dsSpace[3]}>
              {(["auto", "living", "travel", "both"] as const).map((p) => (
                <Chip
                  compact
                  key={p}
                  label={t(p === "both" ? "livingTravel" : p)}
                  selected={(filters.purpose ?? "auto") === p}
                  onPress={() => {
                    const next = { ...filters };
                    if (p === "auto") delete next.purpose;
                    else next.purpose = p;
                    setFilters(next);
                  }}
                />
              ))}
            </Choices>
          </View>
        </View>
      )}
      <Button label={t("findPlaces")} onPress={submit} />
    </Screen>
  );
}
