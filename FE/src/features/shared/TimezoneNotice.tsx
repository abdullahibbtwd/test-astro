import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import { router } from "expo-router";
import { getCalendars } from "expo-localization";
import { useTranslation } from "react-i18next";
import { useApp } from "../../lib/state";
import { IconButton } from "../../design/components/IconButton";
import { Glyph } from "../../design-system/components/Glyph";
import { AppText } from "../../design-system/text/AppText";
import { size, space } from "../../design-system/theme/tokens";

export function TimezoneNotice() {
  const app = useApp(),
    { t } = useTranslation(),
    [dismissed, setDismissed] = useState(""),
    device = getCalendars()[0]?.timeZone,
    place = app.me?.current_place,
    stored = place?.tz,
    key = `${device}:${stored}`;
  if (!device || !stored || device === stored || dismissed === key) return null;
  const prompt = t("currentCityReminder", { city: place.name });
  return (
    <View style={styles.row}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${prompt} ${t("updateLocation")}`}
        onPress={() => router.push("/profile/location")}
        style={({ pressed }) => [styles.update, { opacity: pressed ? 0.65 : 1 }]}
      >
        <Glyph name="map-pin" size={space[4]} color="inkSoft" />
        <AppText variant="caption" color="inkSoft" style={styles.prompt}>
          {prompt}
        </AppText>
        <AppText variant="caption" color="accent" style={styles.link}>
          {t("change")}
        </AppText>
      </Pressable>
      <IconButton
        icon={<Glyph name="close" size={space[4]} color="inkSoft" />}
        accessibilityLabel={t("dismissCityReminder")}
        onPress={() => setDismissed(key)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: space[1] },
  update: {
    flex: 1,
    minHeight: size.buttonMd,
    flexDirection: "row",
    alignItems: "center",
    gap: space[2],
  },
  prompt: { flexShrink: 1 },
  link: { textDecorationLine: "underline" },
});
