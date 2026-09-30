import { useState } from "react";
import { ScrollView, View } from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { useNetInfo } from "@react-native-community/netinfo";
import {
  Txt,
  Button,
  Choices,
  Chip,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { AspectGlyph } from "../../design/components/AspectGlyph";
import { useTheme } from "../../design/theme";
import { useApp } from "../../lib/state";
import { useProfiles, useCatalogue, useChart } from "../../api/hooks";
import { WheelPreview } from "../profiles/WheelPreview";
import { ChartTables, type ChartTab } from "./ChartTables";
import { ChartDetailSheet } from "./ChartDetailSheet";
import type { BirthProfile } from "../../../contracts/spec-types";
import type { Selection } from "./facts";
export default function ChartScreen() {
  const { t } = useTranslation(),
    colors = useTheme(),
    app = useApp(),
    profiles = useProfiles(),
    network = useNetInfo();
  const active =
    profiles.data?.find(
      (p) => p.profile_id === (app.activeProfileId ?? app.me?.self_profile_id),
    ) ?? profiles.data?.find((p) => p.is_self);
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{
        padding: 20,
        gap: 24,
        maxWidth: 680,
        width: "100%",
        alignSelf: "center",
        paddingBottom: 40,
      }}
    >
      {network.isConnected === false && (
        <Txt kind="caption">{t("offline")}</Txt>
      )}
      <Choices>
        {profiles.data?.map((p) => (
          <Chip
            key={p.profile_id}
            label={p.label}
            selected={p.profile_id === active?.profile_id}
            onPress={() => app.update({ activeProfileId: p.profile_id })}
          />
        ))}
      </Choices>
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
    </ScrollView>
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
      <Txt kind="display">{profile.label}</Txt>
      <Choices>
        {(["sun", "moon", "ascendant"] as const).map((key) => (
          <Chip
            key={key}
            label={`${t(key === "ascendant" ? "rising" : key)} · ${c.signs[profile.big_three[key]]}`}
            selected={false}
            onPress={() =>
              select(
                key === "ascendant"
                  ? { kind: "axis", axis: "ASC" }
                  : { kind: "body", body: key },
              )
            }
          />
        ))}
      </Choices>
      <WheelPreview id={profile.profile_id} chartKey={profile.chart_key} />
      <View style={{ gap: 8 }}>
        {(
          [
            ["square", "tenseAspects"],
            ["trine", "flowingAspects"],
            ["conjunction", "conjunctionAspects"],
          ] as const
        ).map(([type, label]) => (
          <View
            key={type}
            style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
          >
            <AspectGlyph type={type} size={20} />
            <Txt kind="caption" muted>
              {t(label)}
            </Txt>
          </View>
        ))}
      </View>
      <Choices>
        {(["reading", "planets", "houses", "aspects"] as const).map((value) => (
          <Chip
            key={value}
            label={t(value)}
            selected={tab === value}
            onPress={() => setTab(value)}
          />
        ))}
      </Choices>
      {tab === "reading" ? (
        <>
          <Txt muted>{t("readingIntro")}</Txt>
          <Button
            label={t("openReading")}
            onPress={() =>
              router.push(`/chart/reading?profile=${profile.profile_id}`)
            }
          />
        </>
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
              <Chip
                key={axis}
                label={c.angles[axis].name}
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
