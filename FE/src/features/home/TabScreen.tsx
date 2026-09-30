import { WheelPreview } from "../profiles/WheelPreview";
import { useLocalSearchParams, router } from "expo-router";
import { useTranslation } from "react-i18next";
import { ScrollView, View } from "react-native";
import { ArrowUpRight } from "lucide-react-native";
import { useNetInfo } from "@react-native-community/netinfo";
import {
  Txt,
  Card,
  Button,
  Row,
  Chip,
  Choices,
  Skeleton,
  ErrorNotice,
} from "../../design/components";
import { useTheme } from "../../design/theme";
import { useProfiles, useCatalogue, useMe } from "../../api/hooks";
import { useApp } from "../../lib/state";
export default function TabScreen({ tab = "home" }: { tab?: string }) {
  const { t } = useTranslation(),
    c = useTheme(),
    app = useApp(),
    profiles = useProfiles(),
    catalogue = useCatalogue(),
    me = useMe(),
    network = useNetInfo(),
    params = useLocalSearchParams();
  const active = profiles.data?.find(
    (p) => p.profile_id === (app.activeProfileId ?? me.data?.self_profile_id),
  );
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: c.bg }}
      contentContainerStyle={{
        padding: 20,
        gap: 24,
        maxWidth: 680,
        width: "100%",
        alignSelf: "center",
        paddingBottom: 40,
      }}
    >
      {!network.isConnected && <Txt kind="caption">{t("offline")}</Txt>}
      {tab === "home" ? (
        <>
          <Txt kind="caption" muted>
            {me.data?.display_name}
          </Txt>
          <Txt kind="display">{t("homeTitle")}</Txt>
          <Txt muted>{t("homeBody")}</Txt>
          <Card style={{ backgroundColor: c.accentSoft }}>
            <View
              style={{ flexDirection: "row", justifyContent: "space-between" }}
            >
              <Txt kind="title">{t("myCharts")}</Txt>
              <ArrowUpRight color={c.accent} />
            </View>
            <Txt muted>{t("whoAmI")}</Txt>
            <Button
              label={t("openCharts")}
              onPress={() => router.push("/profile/charts")}
            />
          </Card>
          <View>
            {["whatsAhead", "whoFits", "whereToBe"].map((key, i) => (
              <Row
                key={key}
                label={t(key)}
                onPress={() =>
                  router.push(
                    `/(tabs)/${["ahead", "match", "map"][i]}` as never,
                  )
                }
              />
            ))}
          </View>
        </>
      ) : (
        <>
          {["chart", "ahead", "map"].includes(tab) && (
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
          )}
          <Txt kind="display">
            {t(
              tab === "chart"
                ? "whoAmI"
                : tab === "ahead"
                  ? "whatsAhead"
                  : tab === "match"
                    ? "whoFits"
                    : "whereToBe",
            )}
          </Txt>
          {tab === "chart" && active && (
            <WheelPreview id={active.profile_id} chartKey={active.chart_key} />
          )}
          {tab === "chart" && active ? (
            <Card>
              <Txt kind="title">{active.label}</Txt>
              {(["sun", "moon", "ascendant"] as const).map((key) => (
                <Row
                  key={key}
                  label={t(key === "ascendant" ? "rising" : key)}
                  detail={catalogue.data?.signs[active.big_three[key]]}
                />
              ))}
              <Button
                label={t("openReading")}
                onPress={() =>
                  router.push(`/chart/reading?profile=${active.profile_id}`)
                }
              />
              <Button
                secondary
                label={t("edit")}
                onPress={() =>
                  router.push(`/profile/charts/${active.profile_id}`)
                }
              />
            </Card>
          ) : (
            <>
              <Txt muted>{t("phaseMessage")}</Txt>
              {tab === "match" && params.other && (
                <Txt>
                  {
                    profiles.data?.find((p) => p.profile_id === params.other)
                      ?.label
                  }
                </Txt>
              )}
              <Button
                secondary
                label={t("myCharts")}
                onPress={() => router.push("/profile/charts")}
              />
            </>
          )}
        </>
      )}
      {profiles.isPending && <Skeleton />}
      <ErrorNotice
        error={profiles.error}
        retry={() => void profiles.refetch()}
      />
    </ScrollView>
  );
}
