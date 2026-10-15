import { space as dsSpace, radius as dsRadius } from "../../design-system/theme/tokens";
import { Info } from "../../design-system/LegacyIcons";
import { routes } from "../../lib/routes";
import Layers from "lucide-react-native/icons/layers";
import List from "lucide-react-native/icons/list";

import { Sheet } from "../../design/components/Sheet";
import { ActionSheet } from "../../design/components/ActionSheet";
import { IconButton } from "../../design/components/IconButton";
import { BandChip } from "../../design/components/BandChip";
import { useTheme } from "../../design/theme";
import { bandColor } from "../../design/bands";
import { useState } from "react";
import { ScrollView, View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Choices,
  Chip,
  Button,
  Row,
  ErrorNotice,
  Skeleton,
} from "../../design/components";
import { useCatalogue } from "../../api/hooks";
import { useApi } from "../../api/resource";
import { request } from "../../api/client";
import { useApp } from "../../lib/state";
import { useProfile } from "../shared/useProfile";
import { MapCanvas } from "./MapCanvas";
import { planetColors } from "./mapColors";
import { MapSearch } from "./MapSearch";
import { countryAt } from "./geometry";
import { loadCountries } from "./countries";
import type {
  AcgLines,
  AcgHeat,
  Body,
  Angle,
  Goal,
  Place,
  PlaceCandidate,
} from "../../../contracts/spec-types";
export default function MapScreen() {
  const [spotAction, setSpotAction] = useState<(() => void) | null>(null),
    colors = useTheme();
  const { id, profile } = useProfile(true),
    app = useApp(),
    catalogue = useCatalogue().data,
    { t } = useTranslation(),
    [goal, setGoal] = useState<Goal>(),
    [layers, setLayers] = useState(false),
    [legend, setLegend] = useState(false),
    [list, setList] = useState(false),
    [parans, setParans] = useState(false),
    [nodes, setNodes] = useState(false),
    [bodies, setBodies] = useState<Body[]>(Object.keys(planetColors) as Body[]),
    [error, setError] = useState<unknown>();
  const lines = useApi<AcgLines>(`/profiles/${id}/acg/lines`, "AcgLines", !!id),
    heat = useApi<AcgHeat>(
      `/profiles/${id}/acg/heat/${goal}`,
      "AcgHeat",
      !!id && !!goal,
    ),
    allBodies: Body[] = nodes
      ? [...bodies, "north_node", "south_node"]
      : bodies;
  const line = (body: Body, angle: Angle) =>
      router.push(
        `/map/line/${body}/${angle}?profile=${id}${goal ? `&goal=${goal}` : ""}`,
      ),
    place = (p: PlaceCandidate) =>
      router.push(
        p.kind === "country" || p.kind === "region"
          ? routes.area(p.place_id.replace(/^(iso2|admin1):/, ""), p.kind, id)
          : routes.place(p.place_id, { profile: id, goal: goal || undefined }),
      );
  const point = async (
    [lon, lat]: [number, number],
    zoom: number,
    long: boolean,
  ) => {
    const spot = () =>
      router.push(
        `/map/point?profile=${id}&lat=${lat}&lon=${lon}${goal ? `&goal=${goal}` : ""}`,
      );
    if (long) {
      spot();
      return;
    }
    try {
      if (zoom < 3.5) {
        const started = performance.now();
        const countries = await loadCountries(),
          country = countryAt([lon, lat], countries);
        if (__DEV__)
          console.info("Country tap lookup ms", performance.now() - started);
        if (country) router.push(routes.area(country, "country", id));
        else setSpotAction(() => spot);
      } else {
        const city = await request<Place | null>(
          "GET",
          `/places/reverse?lat=${lat}&lon=${lon}`,
        );
        if (city)
          router.push(
            routes.place(city.place_id, {
              profile: id,
              goal: goal || undefined,
            }),
          );
        else setSpotAction(() => spot);
      }
    } catch (e) {
      setError(e);
    }
  };
  const current = profile?.is_self
    ? app.me?.current_place
    : profile?.current_place;
  return (
    <Screen embedded scroll={false}>
      <MapCanvas
        fill
        lines={lines.data}
        heat={goal ? heat.data : undefined}
        bodies={allBodies}
        parans={parans}
        center={current ? [current.lon, current.lat] : undefined}
        onLine={line}
        onPoint={(p, z, l) => void point(p, z, l)}
      />
      <View
        pointerEvents="box-none"
        style={{ position: "absolute", top: 12, left: 12, right: 12, gap: dsSpace[2] }}
      >
        <MapSearch onSelect={place} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={{ flexDirection: "row", gap: dsSpace[2] }}>
            <Chip
              label={t("lines")}
              selected={!goal}
              onPress={() => setGoal(undefined)}
            />
            {(Object.keys(catalogue.goals) as Goal[]).map((g) => (
              <Chip
                key={g}
                label={catalogue.goals[g]}
                selected={goal === g}
                onPress={() => setGoal(g)}
              />
            ))}
          </View>
        </ScrollView>
      </View>
      <View
        style={{
          position: "absolute",
          right: 12,
          top: 132,
          borderRadius: dsRadius.lg,
          backgroundColor: colors.surface,
        }}
      >
        <IconButton
          accessibilityLabel={t("layers")}
          icon={<Layers size={22} color={colors.ink} />}
          onPress={() => setLayers(true)}
        />
        <IconButton
          accessibilityLabel={t("legend")}
          icon={<Info size={22} color={colors.ink} />}
          onPress={() => setLegend(true)}
        />
        <IconButton
          accessibilityLabel={t("list")}
          icon={<List size={22} color={colors.ink} />}
          onPress={() => setList(true)}
        />
      </View>
      <Sheet open={layers} title={t("layers")} onClose={() => setLayers(false)}>
        <Choices multi>
          {(Object.keys(planetColors) as Body[]).map((body) => (
            <Chip
              role="checkbox"
              key={body}
              label={catalogue.bodies[body]}
              selected={bodies.includes(body)}
              onPress={() =>
                setBodies(
                  bodies.includes(body)
                    ? bodies.filter((b) => b !== body)
                    : [...bodies, body],
                )
              }
            />
          ))}
          <Chip
            role="checkbox"
            label={t("nodes")}
            selected={nodes}
            onPress={() => setNodes(!nodes)}
          />
          <Chip
            role="checkbox"
            label={t("latitudeCrossings")}
            selected={parans}
            onPress={() => setParans(!parans)}
          />
        </Choices>
      </Sheet>
      <Sheet open={legend} title={t("legend")} onClose={() => setLegend(false)}>
        <Txt>{t("lineStyles")}</Txt>
        {(Object.keys(planetColors) as (keyof typeof planetColors)[]).map(
          (body) => (
            <View
              key={body}
              style={{ flexDirection: "row", alignItems: "center", gap: dsSpace[3] }}
            >
              <View
                style={{
                  width: 40,
                  height: 3,
                  backgroundColor:
                    planetColors[body][colors.dark ? 1 : 0],
                }}
              />
              <Txt>{catalogue.bodies[body]}</Txt>
            </View>
          ),
        )}
        {(["ASC", "DSC", "MC", "IC"] as const).map((angle, i) => (
          <View
            key={angle}
            style={{ flexDirection: "row", alignItems: "center", gap: dsSpace[3] }}
          >
            <View
              style={{
                width: 40,
                borderTopWidth: i === 2 ? 1 : 2,
                borderColor: colors.ink,
                borderStyle: i === 1 ? "dashed" : i === 3 ? "dotted" : "solid",
              }}
            />
            <Txt>{catalogue.angles[angle].name}</Txt>
          </View>
        ))}
        {goal &&
          ["strongly_supportive", "supportive", "mixed", "challenging"].map(
            (b) => (
              <View
                key={b}
                style={{ flexDirection: "row", alignItems: "center", gap: dsSpace[3] }}
              >
                <View
                  style={{
                    width: 24,
                    height: 24,
                    backgroundColor: bandColor(b, colors.dark),
                  }}
                />
                <BandChip
                  band={b}
                  label={
                    catalogue.place_bands[
                      b as keyof typeof catalogue.place_bands
                    ]
                  }
                />
              </View>
            ),
          )}
      </Sheet>
      <View
        pointerEvents="box-none"
        style={{ position: "absolute", left: 12, right: 12, bottom: 76 }}
      >
        {lines.isPending && <Skeleton variant="lines" lines={1} />}
        <ErrorNotice
          error={error ?? lines.error ?? (goal ? heat.error : null)}
        />
      </View>
      <Sheet open={list} title={t("list")} onClose={() => setList(false)}>
        {allBodies.map((body) => (
          <Choices key={body}>
            <Txt kind="title">{catalogue.bodies[body]}</Txt>
            {(["ASC", "DSC", "MC", "IC"] as Angle[]).map((angle) => (
              <Row
                key={angle}
                label={catalogue.angles[angle]?.line ?? ""}
                onPress={() => {
                  setList(false);
                  line(body, angle);
                }}
              />
            ))}
          </Choices>
        ))}
      </Sheet>
      <ActionSheet
        open={!!spotAction}
        title={t("noCityNearby")}
        onClose={() => setSpotAction(null)}
        actions={[{ label: t("exploreSpot"), onPress: () => spotAction?.() }]}
      />
      <View style={{ position: "absolute", bottom: 12, left: 16, right: 16 }}>
        <Button
          label={t("whereShouldIGo")}
          onPress={() => router.push(`/map/recommend?profile=${id}`)}
        />
      </View>
    </Screen>
  );
}
