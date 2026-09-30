import { useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useColorScheme,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import tr from "../src/i18n/tr.json";
import en from "../src/i18n/en.json";
import { colors, spacing, typography } from "../src/design/tokens";

/** Phase 0 empty native shell. Product screens begin after the FE_00 review gate. */
export default function Index() {
  const [lang, setLang] = useState<"tr" | "en">("tr");
  const copy = lang === "tr" ? tr : en;
  const theme = colors[useColorScheme() === "dark" ? "dark" : "light"];
  return (
    <SafeAreaView style={[styles.page, { backgroundColor: theme.bg }]}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <View
            style={[styles.monogram, { borderColor: theme.hair }]}
            accessibilityElementsHidden
          >
            <Text style={[typography.title1, { color: theme.accent }]}>A</Text>
          </View>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={copy.language}
            accessibilityHint={lang === "tr" ? "English" : "Türkçe"}
            onPress={() => setLang(lang === "tr" ? "en" : "tr")}
            style={({ pressed }) => [
              styles.language,
              {
                borderColor: theme.hair,
                backgroundColor: pressed ? theme.accentSoft : theme.bg,
              },
            ]}
          >
            <Text style={[typography.body, { color: theme.ink }]}>
              {lang === "tr" ? "English" : "Türkçe"}
            </Text>
          </Pressable>
        </View>
        <Text
          accessibilityRole="header"
          style={[styles.title, typography.display, { color: theme.ink }]}
        >
          {copy.appName}
        </Text>
        {[copy.whoAmI, copy.whatsAhead, copy.whoFits, copy.whereToBe].map(
          (question, i) => (
            <View key={i} style={[styles.row, { borderColor: theme.hair }]}>
              <Text style={[styles.number, { color: theme.accent }]}>
                {String(i + 1).padStart(2, "0")}
              </Text>
              <Text
                style={[
                  styles.question,
                  typography.reading,
                  { color: theme.ink },
                ]}
              >
                {question}
              </Text>
            </View>
          ),
        )}
        <Text
          style={[styles.disclaimer, typography.body, { color: theme.ink2 }]}
        >
          {copy.disclaimer}
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  page: { flex: 1 },
  content: {
    padding: spacing.gutter,
    maxWidth: 640,
    width: "100%",
    alignSelf: "center",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.section,
  },
  monogram: {
    width: 48,
    height: 48,
    borderWidth: 1,
    borderRadius: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  language: {
    minHeight: 48,
    paddingHorizontal: spacing.lg,
    justifyContent: "center",
    borderWidth: 1,
    borderRadius: 12,
  },
  title: { marginBottom: spacing.hero },
  row: {
    flexDirection: "row",
    gap: spacing.xl,
    paddingVertical: spacing.xl,
    borderTopWidth: StyleSheet.hairlineWidth,
    alignItems: "baseline",
  },
  number: { fontFamily: "Inter", fontSize: 14, fontVariant: ["tabular-nums"] },
  question: { flex: 1 },
  disclaimer: { marginTop: spacing.section },
});
