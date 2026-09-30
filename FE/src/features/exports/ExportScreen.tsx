import { Glyph } from "../../design/components/Glyph";
import Constants from "expo-constants";
import { useRef, useState } from "react";
import { View, Switch, Alert } from "react-native";
import { SvgCss } from "react-native-svg/css";
import { captureRef } from "react-native-view-shot";
import * as Sharing from "expo-sharing";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Choices,
  Chip,
  Button,
  ErrorNotice,
  Skeleton,
} from "../../design/components";
import { useCatalogue, useChart } from "../../api/hooks";
import { useGenerated } from "../../api/jobs";
import { useProfile } from "../shared/useProfile";
import { useApp } from "../../lib/state";
import { nativeWheelSvg } from "../../../packages/wheel-core/native-svg";
import { chartDocument } from "./document";
import { exportPdf, exportChartImage } from "./native";
import type { NatalReading } from "../../../contracts/spec-types";
export default function ExportScreen() {
  const { id, profile } = useProfile(),
    chart = useChart(id, profile?.chart_key ?? ""),
    cat = useCatalogue().data,
    { t } = useTranslation(),
    app = useApp(),
    [format, setFormat] = useState<"png" | "jpg">("png"),
    [dark, setDark] = useState(false),
    [details, setDetails] = useState(false),
    [story, setStory] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    card = useRef<View>(null);
  const reading = useGenerated<NatalReading>(
      ["natal", id, profile?.chart_key ?? ""],
      `/profiles/${id}/natal-reading`,
      "NatalReading",
      !!id,
    ),
    brand = Constants.expoConfig?.name ?? "Astrology",
    bg = dark ? "#1A2030" : "#FAFAF8",
    ink = dark ? "#E7E9EE" : "#232A38";
  const run = async (task: () => Promise<unknown>) => {
    setBusy(true);
    setError(undefined);
    try {
      await task();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const pdf = (full: boolean) => {
    if (!profile || !chart.data) return;
    const labels = Object.fromEntries(
      [
        "chart",
        "sun",
        "moon",
        "ascendant",
        "contents",
        "planets",
        "houses",
        "aspects",
        "sign",
        "house",
        "orb",
      ].map((k) => [k, t(k === "ascendant" ? "rising" : k)]),
    );
    void run(() =>
      exportPdf(
        profile.label,
        chartDocument(
          profile,
          chart.data!,
          cat,
          labels,
          full ? reading.data : undefined,
        ),
        t("disclaimer"),
        brand,
        `${profile.label}-${app.language === "tr" ? "dogum-haritasi" : "birth-chart"}${full ? "-report" : ""}`,
      ),
    );
  };
  const image = (save: boolean) => {
    if (!profile || !chart.data) return;
    void run(async () => {
      await exportChartImage(
        chart.data!,
        [
          profile.label,
          `${profile.birth.date} · ${profile.birth.time}`,
          profile.birth.place.name,
          brand,
        ],
        dark,
        format,
        profile.label,
        save,
      );
      if (save) Alert.alert(t("savedToPhotos"));
    });
  };
  return (
    <Screen back title={t("exportShare")}>
      <ErrorNotice error={error} />
      {!profile || !chart.data ? (
        <Skeleton />
      ) : (
        <>
          <Choices>
            {(["png", "jpg"] as const).map((f) => (
              <Chip
                key={f}
                label={f.toUpperCase()}
                selected={format === f}
                onPress={() => setFormat(f)}
              />
            ))}
          </Choices>
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Txt>{t("darkExport")}</Txt>
            <Switch
              accessibilityLabel={t("darkExport")}
              value={dark}
              onValueChange={setDark}
            />
          </View>
          <Button
            label={t("saveChartImage")}
            disabled={busy}
            onPress={() => image(true)}
          />
          <Button
            secondary
            label={t("shareChartImage")}
            disabled={busy}
            onPress={() => image(false)}
          />
          <Button
            secondary
            label={t("downloadPdf")}
            disabled={busy}
            onPress={() => pdf(false)}
          />
          <Button
            secondary
            label={t("downloadFullReport")}
            disabled={busy || !reading.data}
            onPress={() => pdf(true)}
          />
          {!reading.data && <Txt muted>{t("readingNotReady")}</Txt>}
          <Txt kind="title">{t("shareCard")}</Txt>
          <Choices>
            <Chip
              label={t("feed")}
              selected={!story}
              onPress={() => setStory(false)}
            />
            <Chip
              label={t("story")}
              selected={story}
              onPress={() => setStory(true)}
            />
          </Choices>
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Txt>{t("includeBirthDetails")}</Txt>
            <Switch
              accessibilityLabel={t("includeBirthDetails")}
              value={details}
              onValueChange={setDetails}
            />
          </View>
          <View
            ref={card}
            collapsable={false}
            style={{
              width: 300,
              height: story ? 533.333333 : 375,
              backgroundColor: bg,
              alignSelf: "center",
              justifyContent: "center",
              alignItems: "center",
              padding: 12,
              gap: 6,
            }}
          >
            <Txt
              numberOfLines={1}
              style={{ color: ink, fontSize: 20, lineHeight: 24 }}
            >
              {profile.label}
            </Txt>
            <SvgCss
              xml={nativeWheelSvg(chart.data, dark ? "dark" : "light")}
              width={details ? 224 : 240}
              height={details ? 224 : 240}
            />
            <View style={{ flexDirection: "row", gap: 8 }}>
              {(["sun", "moon", "ascendant"] as const).map((key) => (
                <View key={key} style={{ alignItems: "center", gap: 2 }}>
                  <Glyph
                    name={key === "ascendant" ? profile.big_three.ascendant : key}
                    size={14}
                    color={ink}
                  />
                  <Txt style={{ color: ink, fontSize: 9, lineHeight: 12 }}>
                    {cat.signs[profile.big_three[key]]}
                  </Txt>
                </View>
              ))}
            </View>
            {details && (
              <Txt
                style={{ color: ink, fontSize: 9, lineHeight: 12 }}
              >{`${profile.birth.date} · ${profile.birth.time} · ${profile.birth.place.name}`}</Txt>
            )}
            <Txt style={{ color: ink, fontSize: 10, lineHeight: 14 }}>
              {brand}
            </Txt>
            {process.env.EXPO_PUBLIC_SHARE_URL && (
              <Txt
                numberOfLines={1}
                style={{ color: ink, fontSize: 9, lineHeight: 12 }}
              >
                {process.env.EXPO_PUBLIC_SHARE_URL}
              </Txt>
            )}
          </View>
          <Button
            label={t("shareCard")}
            disabled={busy}
            onPress={() =>
              void run(async () => {
                const uri = await captureRef(card, {
                  format: "png",
                  quality: 1,
                  width: 1080,
                  height: story ? 1920 : 1350,
                  result: "tmpfile",
                });
                await Sharing.shareAsync(uri, { mimeType: "image/png" });
              })
            }
          />
        </>
      )}
    </Screen>
  );
}
