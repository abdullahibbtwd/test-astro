import { useState } from "react";
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
      <Choices>
        {(["overall", ...Object.keys(cat.goals)] as (Goal | "overall")[]).map(
          (g) => (
            <Chip
              key={g}
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
      <Txt kind="title">{t("scope")}</Txt>
      <Choices>
        <Chip
          label={t("world")}
          selected={scope === "world"}
          onPress={() => setScope("world")}
        />
        <Chip
          label="Türkiye"
          selected={scope === "TR"}
          onPress={() => setScope("TR")}
        />
        <Chip
          label={scopeName || t("chooseCountry")}
          selected={!["world", "TR"].includes(scope)}
          onPress={() => setCountry(!country)}
        />
      </Choices>
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
        <>
          <Txt>{t("regions")}</Txt>
          <Choices multi>
            {regions.map((r) => (
              <Chip role="checkbox"
                key={r}
                label={t(r)}
                selected={(filters.regions ?? regions).includes(r)}
                onPress={() => toggle("regions", r, [...regions])}
              />
            ))}
          </Choices>
          <Txt>{t("citySize")}</Txt>
          <Choices multi>
            {(["big", "mid", "small"] as const).map((s) => (
              <Chip role="checkbox"
                key={s}
                label={t(s)}
                selected={(filters.city_size ?? ["big", "mid"]).includes(s)}
                onPress={() => toggle("city_size", s, ["big", "mid"])}
              />
            ))}
          </Choices>
          <Txt>{t("maxDistance")}</Txt>
          <Choices>
            {[0, 500, 1000, 2000, 3000, 5000].map((km) => (
              <Chip
                key={km}
                label={km ? `≈ ${km.toLocaleString()} km` : t("off")}
                selected={(filters.max_distance_km ?? 0) === km}
                onPress={() =>
                  setFilters({ ...filters, max_distance_km: km || null })
                }
              />
            ))}
          </Choices>
          <Txt>{t("climate")}</Txt>
          <Choices multi>
            {(["warm", "mild", "cold"] as const).map((c) => (
              <Chip role="checkbox"
                key={c}
                label={t(c)}
                selected={(filters.climate ?? []).includes(c)}
                onPress={() => toggle("climate", c, [])}
              />
            ))}
          </Choices>
          <Txt>{t("purpose")}</Txt>
          <Choices>
            {(["auto", "living", "travel", "both"] as const).map((p) => (
              <Chip
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
        </>
      )}
      <Button label={t("findPlaces")} onPress={submit} />
    </Screen>
  );
}
