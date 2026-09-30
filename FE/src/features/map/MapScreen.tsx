import { useState } from "react";
import { Alert, ScrollView, View } from "react-native";
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
import { useCatalogue, useProfiles } from "../../api/hooks";
import { useApi } from "../../api/resource";
import { request } from "../../api/client";
import { useApp } from "../../lib/state";
import { useProfile } from "../shared/useProfile";
import { MapCanvas, planetColors } from "./MapCanvas";
import { MapSearch } from "./MapSearch";
import { countryAt } from "./geometry";
import type { FeatureCollection, Polygon, MultiPolygon } from "geojson";
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
  const { id, profile } = useProfile(),
    app = useApp(),
    profiles = useProfiles(),
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
          ? `/map/area/${encodeURIComponent(p.place_id.replace(/^(iso2|admin1):/, ""))}?kind=${p.kind}&profile=${id}`
          : `/map/place/${p.place_id}?profile=${id}${goal ? `&goal=${goal}` : ""}`,
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
        const countries = await request<
            FeatureCollection<Polygon | MultiPolygon, { iso2: string }>
          >("GET", "/geo/countries.geojson"),
          country = countryAt([lon, lat], countries);
        if (country)
          router.push(`/map/area/${country}?kind=country&profile=${id}`);
        else
          Alert.alert(t("noCityNearby"), undefined, [
            { text: t("exploreSpot"), onPress: spot },
            { text: t("cancel"), style: "cancel" },
          ]);
      } else {
        const city = await request<Place | null>(
          "GET",
          `/places/reverse?lat=${lat}&lon=${lon}`,
        );
        if (city)
          router.push(
            `/map/place/${city.place_id}?profile=${id}${goal ? `&goal=${goal}` : ""}`,
          );
        else
          Alert.alert(t("noCityNearby"), undefined, [
            { text: t("exploreSpot"), onPress: spot },
            { text: t("cancel"), style: "cancel" },
          ]);
      }
    } catch (e) {
      setError(e);
    }
  };
  const current = profile?.is_self
    ? app.me?.current_place
    : profile?.current_place;
  return (
    <Screen embedded>
      <Choices>
        {profiles.data?.map((p) => (
          <Chip
            key={p.profile_id}
            label={p.label}
            selected={id === p.profile_id}
            onPress={() => {
              app.update({ activeProfileId: p.profile_id });
              router.setParams({ profile: p.profile_id });
            }}
          />
        ))}
      </Choices>
      <MapSearch onSelect={place} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={{ flexDirection: "row", gap: 8 }}>
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
      <Choices>
        <Button
          secondary
          label={t("layers")}
          onPress={() => setLayers(!layers)}
        />
        <Button
          secondary
          label={t("legend")}
          onPress={() => setLegend(!legend)}
        />
        <Button
          secondary
          label={t(list ? "map" : "list")}
          onPress={() => setList(!list)}
        />
      </Choices>
      {layers && (
        <Choices>
          {(Object.keys(planetColors) as Body[]).map((body) => (
            <Chip
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
            label={t("nodes")}
            selected={nodes}
            onPress={() => setNodes(!nodes)}
          />
          <Chip
            label={t("latitudeCrossings")}
            selected={parans}
            onPress={() => setParans(!parans)}
          />
        </Choices>
      )}
      {legend && (
        <>
          <Txt>{t("lineStyles")}</Txt>
          {(Object.keys(planetColors) as Body[]).map((body) => (
            <Txt
              key={body}
              style={{
                color: planetColors[body as keyof typeof planetColors][0],
              }}
            >
              {catalogue.bodies[body]}
            </Txt>
          ))}
          {goal &&
            ["strongly_supportive", "supportive", "mixed", "challenging"].map(
              (b) => (
                <Txt key={b}>
                  {
                    catalogue.place_bands[
                      b as keyof typeof catalogue.place_bands
                    ]
                  }
                </Txt>
              ),
            )}
        </>
      )}
      {lines.isPending && <Skeleton />}
      <ErrorNotice error={error ?? lines.error ?? (goal ? heat.error : null)} />
      {list ? (
        allBodies.map((body) => (
          <Choices key={body}>
            <Txt kind="title">{catalogue.bodies[body]}</Txt>
            {(["ASC", "DSC", "MC", "IC"] as Angle[]).map((angle) => (
              <Row
                key={angle}
                label={catalogue.angles[angle].line}
                onPress={() => line(body, angle)}
              />
            ))}
          </Choices>
        ))
      ) : (
        <MapCanvas
          lines={lines.data}
          heat={goal ? heat.data : undefined}
          bodies={allBodies}
          parans={parans}
          center={current ? [current.lon, current.lat] : undefined}
          onLine={line}
          onPoint={(p, z, l) => void point(p, z, l)}
        />
      )}
      <Button
        label={t("whereShouldIGo")}
        onPress={() => router.push(`/map/recommend?profile=${id}`)}
      />
    </Screen>
  );
}
