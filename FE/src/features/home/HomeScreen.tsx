import { TimezoneNotice } from "../shared/TimezoneNotice";
import { useCallback, useEffect } from "react";
import { AppState, RefreshControl, View } from "react-native";
import { router, useFocusEffect } from "expo-router";
import { useTranslation } from "react-i18next";
import { useCatalogue } from "../../api/hooks";
import { useApi } from "../../api/resource";
import { useApp } from "../../lib/state";
import { useFlags } from "../../lib/flags";
import { greetingKey, notificationRoute } from "../../lib/calendar";
import { formatDate } from "../../lib/dates";
import {
  Screen,
  Txt,
  Card,
  Button,
  Row,
  Skeleton,
  ErrorNotice,
  Choices,
} from "../../design/components";
import { Generated, Score } from "../shared/Blocks";
import type { HomeSummary } from "../../../contracts/spec-types";
export default function HomeScreen() {
  const { t } = useTranslation(),
    app = useApp(),
    catalogue = useCatalogue(),
    flags = useFlags(),
    query = useApi<HomeSummary>("/home", "HomeSummary"),
    data = query.data;
  const today = () =>
    router.push(
      `/(tabs)/ahead?view=day&profile=${app.me?.self_profile_id ?? ""}`,
    );
  const refetch = query.refetch;
  useFocusEffect(
    useCallback(() => {
      void refetch();
    }, [refetch]),
  );
  useEffect(() => {
    const sub = AppState.addEventListener("change", (s) => {
      if (
        s === "active" &&
        data &&
        new Intl.DateTimeFormat("en-CA", {
          timeZone: data.tz,
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        }).format(new Date()) !== data.date
      )
        void refetch();
    });
    return () => sub.remove();
  }, [refetch, data]);
  return (
    <Screen
      embedded
      scrollProps={{
        refreshControl: (
          <RefreshControl
            refreshing={query.isRefetching}
            onRefresh={() => {
              void query.refetch();
            }}
          />
        ),
      }}
    >
      <TimezoneNotice />
      {query.isPending && <Skeleton />}
      {data && (
        <>
          <Txt kind="display">
            {t(greetingKey(data.tz), { name: data.greeting_name })}
          </Txt>
          <Txt muted>
            {formatDate(data.date, app.language)} · {data.moon.phase_label} ·{" "}
            {data.moon.sign_label}
          </Txt>
          <Card>
            <Txt kind="title">{t("yourDay")}</Txt>
            <Score
              label={t("overall")}
              score={data.score_10}
              band={data.tone_label}
              bandKey={data.tone}
            />
            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 16 }}>
              {data.tiles
                .filter((tile) => tile.key !== "energy" || flags.homeEnergyTile)
                .filter(
                  (tile) =>
                    !(
                      flags.homeEnergyTile &&
                      data.tiles.some((x) => x.key === "energy") &&
                      tile.key === "family"
                    ),
                )
                .map((tile) => (
                  <View key={tile.key} style={{ gap: 8, width: "47%" }}>
                    <Score
                      label={tile.label}
                      score={tile.score_10}
                      band={catalogue.data.day_bands[tile.band] ?? tile.label}
                      bandKey={tile.band}
                    />
                    <Button
                      secondary
                      label={t("exploreArea", { area: tile.label })}
                      onPress={() =>
                        router.push(
                          `/(tabs)/ahead?view=day&area=${tile.key}&profile=${app.me?.self_profile_id ?? ""}`,
                        )
                      }
                    />
                  </View>
                ))}
            </View>
          </Card>
          <Txt kind="title">{t("todayAstrology")}</Txt>
          {data.today.status === "absent" ? (
            <Row label={t("readTodayForecast")} onPress={today} />
          ) : (
            <Generated part={data.today} retry={today}>
              {(reading) => (
                <>
                  <Txt kind="reading" numberOfLines={5}>
                    {reading.text}
                  </Txt>
                  <Button label={t("readMore")} onPress={today} />
                </>
              )}
            </Generated>
          )}
          {!!data.next_up.length && (
            <>
              <Txt kind="title">{t("comingUp")}</Txt>
              {data.next_up.slice(0, 3).map((item, i) => (
                <Row
                  key={i}
                  label={item.label}
                  detail={formatDate(item.date, app.language)}
                  onPress={() =>
                    router.push(
                      notificationRoute(
                        item.deep_link,
                        app.me?.self_profile_id ?? undefined,
                      ) as never,
                    )
                  }
                />
              ))}
            </>
          )}
        </>
      )}
      <Choices>
        {(
          [
            ["chart", "myCharts"],
            ["ahead", "today"],
            ["match", "compatibility"],
            ["map", "map"],
          ] as const
        ).map(([route, label]) => (
          <Button
            key={route}
            secondary
            label={t(label)}
            onPress={() => {
              if (route === "chart")
                app.update({ activeProfileId: app.me?.self_profile_id });
              router.push(`/(tabs)/${route}`);
            }}
          />
        ))}
      </Choices>
      {flags.askAstrology && (
        <Button
          secondary
          label={t("askDay")}
          onPress={() =>
            router.push(
              `/ask?date=${data?.date ?? ""}&profile=${app.me?.self_profile_id ?? ""}`,
            )
          }
        />
      )}
      <ErrorNotice
        error={query.error}
        retry={() => {
          void query.refetch();
        }}
      />
    </Screen>
  );
}
