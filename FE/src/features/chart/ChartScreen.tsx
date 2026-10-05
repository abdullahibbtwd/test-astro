import { space as dsSpace } from "../../design-system/theme/tokens";
import { Glyph } from "../../design/components/Glyph";
import { Segmented } from "../../design/components/Segmented";
import { InlineReading } from "./InlineReading";
import { useState } from "react";
import { Pressable, View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { useNetInfo } from "@react-native-community/netinfo";
import {
  Screen,
  Txt,
  Button,
  Choices,
  Chip,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { AspectGlyph } from "../../design/components/AspectGlyph";
import { useApp } from "../../lib/state";
import { useProfiles, useCatalogue, useChart } from "../../api/hooks";
import { InteractiveWheel } from "./InteractiveWheel";
import { ChartTables, type ChartTab } from "./ChartTables";
import { ChartDetailSheet } from "./ChartDetailSheet";
import type { BirthProfile } from "../../../contracts/spec-types";
import type { Selection } from "./facts";
export default function ChartScreen() {
  const { t } = useTranslation(),
    app = useApp(),
    profiles = useProfiles(),
    network = useNetInfo();
  const active =
    profiles.data?.find(
      (p) => p.profile_id === (app.activeProfileId ?? app.me?.self_profile_id),
    ) ?? profiles.data?.find((p) => p.is_self);
  return (
    <Screen embedded>
      {network.isConnected === false && (
        <Txt kind="caption">{t("offline")}</Txt>
      )}
      {profiles.isPending ? (
        <Skeleton />
      ) : active ? (
        <ChartWorkspace
          key={`${active.profile_id}:${active.chart_key}:${app.language}`}
          profile={active}
        />
      ) : (
        !profiles.error && <Txt>{t("missingProfile")}</Txt>
      )}
      <ErrorNotice
        error={profiles.error}
        retry={() => {
          void profiles.refetch();
        }}
      />
    </Screen>
  );
}
function ChartWorkspace({ profile }: { profile: BirthProfile }) {
  const { t } = useTranslation(),
    chart = useChart(profile.profile_id, profile.chart_key),
    catalogue = useCatalogue();
  const [tab, setTab] = useState<ChartTab>("reading"),
    [selection, select] = useState<Selection | null>(null);
  const c = catalogue.data;
  return (
    <>
      <View style={{ flexDirection: "row", gap: dsSpace[2] }}>
        {(["sun", "moon", "ascendant"] as const).map((key) => (
          <Pressable
            key={key}
            accessibilityRole="button"
            onPress={() =>
              select(
                key === "ascendant"
                  ? { kind: "axis", axis: "ASC" }
                  : { kind: "body", body: key },
              )
            }
            style={{ flex: 1, minHeight: 44, gap: dsSpace[1] }}
          >
            <View style={{ flexDirection: "row", alignItems: "center", gap: dsSpace[1] }}>{key !== "ascendant" && <Glyph name={key} size={20} />}<Txt kind="caption">{t(key === "ascendant" ? "rising" : key)}</Txt></View>
            <Txt kind="caption">{c.signs[profile.big_three[key]]}</Txt>
          </Pressable>
        ))}
      </View>
      {chart.data ? (
        <InteractiveWheel
          chart={chart.data}
          catalogue={c}
          selection={selection}
          select={select}
          onExpand={() =>
            router.push(`/chart/focus?profile=${profile.profile_id}`)
          }
        />
      ) : (
        <Skeleton />
      )}
      <View
        style={{
          flexDirection: "row",
          justifyContent: "space-between",
          gap: dsSpace[1],
        }}
      >
        {(
          [
            ["square", "tenseAspects"],
            ["trine", "flowingAspects"],
            ["conjunction", "conjunctionAspects"],
          ] as const
        ).map(([type, label]) => (
          <View
            key={type}
            style={{
              flex: 1,
              flexDirection: "row",
              alignItems: "center",
              gap: dsSpace[1],
            }}
          >
            <AspectGlyph type={type} size={20} />
            <Txt kind="caption" muted style={{ flexShrink: 1 }}>
              {t(
                label === "tenseAspects"
                  ? "tenseShort"
                  : label === "flowingAspects"
                    ? "flowingShort"
                    : "conjunctionShort",
              )}
            </Txt>
          </View>
        ))}
      </View>
      <Segmented
        value={tab}
        onChange={setTab}
        items={(["reading", "planets", "houses", "aspects"] as const).map(
          (value) => ({ value, label: t(value) }),
        )}
      />
      {tab === "reading" ? (
        <InlineReading profile={profile} />
      ) : chart.data ? (
        <ChartTables
          chart={chart.data}
          catalogue={c}
          tab={tab}
          select={select}
        />
      ) : chart.isPending ? (
        <Skeleton />
      ) : null}
      {chart.data && (
        <>
          <Txt kind="caption">{t("axes")}</Txt>
          <Choices>
            {(["ASC", "DSC", "MC", "IC"] as const).map((axis) => (
              <Chip role="button"
                key={axis}
                label={c.angles[axis]?.name ?? ""}
                selected={false}
                onPress={() => select({ kind: "axis", axis })}
              />
            ))}
          </Choices>
        </>
      )}
      <Button
        secondary
        label={t("edit")}
        onPress={() => router.push(`/profile/charts/${profile.profile_id}`)}
      />
      {selection && chart.data && (
        <ChartDetailSheet
          chart={chart.data}
          catalogue={c}
          selection={selection}
          select={select}
          close={() => select(null)}
        />
      )}
    </>
  );
}
