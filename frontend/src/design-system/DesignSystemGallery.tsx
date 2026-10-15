import { ListRow, ChatBubble, Sheet } from "./components/Patterns";
import { useState } from "react";
import { View, StatusBar, ActivityIndicator } from "react-native";
import { Stack, useLocalSearchParams, Redirect } from "expo-router";
import { useFonts } from "expo-font";
import { ThemeProvider, useTheme } from "./ThemeProvider";
import { AppText } from "./text/AppText";
import {
  type as styles,
  space,
  size,
  type TypeStyleName,
  type ThemeName,
} from "./theme/tokens";
import {
  glyphs,
  type GlyphSet,
  type IconName,
  type MotifName,
} from "./glyphs/glyphs";
import { Screen } from "./components/Screen";
import { Title } from "./components/Title";
import { Button } from "./components/Button";
import { Field, SelectField, TextInputField } from "./components/Fields";
import { Glyph } from "./components/Glyph";
import { Emblem, ChartWheel, Divider } from "./components/Ornament";
import { TraitCard } from "./components/TraitCard";
const copy = {
  tr: {
    subtitle: "Doğduğun anın gökyüzünü keşfet — senin için yazılmış yıldızlar.",
    title: "Doğum haritan için bilgilerin",
    button: "Haritamı oluştur",
    labels: ["Doğum tarihi", "Doğum saati", "Doğum yeri"],
    error: "Doğum yerini listeden seç.",
    hint: "Saati bilmiyorsan 12:00 kullanılır.",
    traits: [
      "Tutku ve karizma",
      "Duygusal denge",
      "Mizah anlayışı",
      "Maddi güven",
    ],
  },
  en: {
    subtitle: "Discover the sky of the moment you were born.",
    title: "Enter your birth details",
    button: "Generate my chart",
    labels: ["Date of birth", "Time of birth", "Place of birth"],
    error: "Choose your birthplace from the list.",
    hint: "If you don't know the time, 12:00 is used.",
    traits: [
      "Passion and charisma",
      "Emotional stability",
      "Sense of humour",
      "Financial security",
    ],
  },
};
function GalleryContent() {
  const params = useLocalSearchParams<{ panel?: string; lang?: string }>();
  const { name, colors, setTheme } = useTheme(),
    [lang, setLang] = useState<"tr" | "en">(params.lang === "en" ? "en" : "tr");
  const [panel, setPanel] = useState(params.panel ?? "controls"),
    [value, setValue] = useState("İstanbul, Türkiye"),
    [selected, setSelected] = useState([false, true, false, false]),
    [pressed, setPressed] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [search, setSearch] = useState("");
  const text = copy[lang],
    hero = panel === "hero";
  return (
    <>
      <Stack.Screen
        options={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.surface },
        }}
      />
      <StatusBar
        barStyle={name === "night" ? "light-content" : "dark-content"}
        backgroundColor={colors.surface}
      />
      <Screen
        arch={hero}
        grain={hero}
        backdrop={panel === "type" ? "plain" : "orbits"}
      >
        <View style={{ flexDirection: "row", gap: space[2] }}>
          <View style={{ flex: 1 }}>
            <Button
              variant="outline"
              size="md"
              onPress={() => setTheme(name === "night" ? "parchment" : "night")}
            >
              {name === "night" ? "Parchment" : "Night"}
            </Button>
          </View>
          <View style={{ flex: 1 }}>
            <Button
              variant="ghost"
              size="md"
              onPress={() => setLang(lang === "tr" ? "en" : "tr")}
            >
              {lang === "tr" ? "English" : "Türkçe"}
            </Button>
          </View>
        </View>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: space[2] }}>
          {[
            "controls",
            "traits",
            "type",
            "glyphs",
            "hero",
            "wheel",
            "patterns",
            "buttons",
          ].map((tab) => (
            <View key={tab} style={{ minWidth: "30%", flexGrow: 1 }}>
              <Button variant="ghost" size="md" onPress={() => setPanel(tab)}>
                {tab}
              </Button>
            </View>
          ))}
        </View>
        {panel === "controls" && (
          <>
            <Title lang={lang}>{text.title}</Title>
            <Field label={text.labels[0]!}>
              <SelectField
                valueLabel="1"
                accessibilityLabel={text.labels[0]!}
                onPress={() => setPressed(!pressed)}
              />
              <SelectField
                valueLabel={lang === "tr" ? "Haziran" : "June"}
                flex={1.5}
                accessibilityLabel="Month"
                onPress={() => setPressed(!pressed)}
              />
              <SelectField
                valueLabel="1994"
                accessibilityLabel="Year"
                onPress={() => setPressed(!pressed)}
              />
            </Field>
            <Field label={text.labels[1]!} hint={text.hint}>
              <SelectField
                valueLabel="12"
                accessibilityLabel="Hour"
                onPress={() => setPressed(!pressed)}
              />
              <SelectField
                valueLabel="00"
                accessibilityLabel="Minute"
                onPress={() => setPressed(!pressed)}
              />
            </Field>
            <Field label={text.labels[2]!} error={text.error}>
              <TextInputField
                icon="map-pin"
                value={value}
                onChangeText={setValue}
                invalid
                accessibilityLabel={text.labels[2]}
              />
            </Field>
            <Field label={lang === "tr" ? "Ara" : "Search"}>
              <TextInputField
                icon="search"
                value={search}
                onChangeText={setSearch}
                placeholder={text.labels[2]}
                accessibilityLabel="Search sample"
              />
            </Field>
            <SelectField
              placeholder={lang === "tr" ? "Seç" : "Choose"}
              accessibilityLabel="Placeholder select"
              disabled
              onPress={() => {}}
            />
            <Button lang={lang} onPress={() => setPressed(!pressed)}>
              {text.button}
            </Button>
            <Button
              lang={lang}
              variant="outline"
              onPress={() => setPressed(!pressed)}
            >
              {text.button}
            </Button>
            <Button
              lang={lang}
              variant="ghost"
              size="md"
              onPress={() => setPressed(!pressed)}
            >
              {text.button}
            </Button>
            <Button lang={lang} disabled onPress={() => {}}>
              {text.button}
            </Button>
            <AppText variant="caption" accessibilityLiveRegion="polite">
              {pressed
                ? "Gallery action selected"
                : "Preview only — no API calls"}
            </AppText>
          </>
        )}
        {panel === "buttons" && (
          <>
            <Title variant="displaySection">{"Button variants"}</Title>
            {(["primary", "outline", "ghost"] as const).map((variant) => (
              <View key={variant} style={{ gap: space[3] }}>
                <AppText variant="caption">{variant}</AppText>
                {(["lg", "md"] as const).map((buttonSize) => (
                  <Button
                    key={buttonSize}
                    size={buttonSize}
                    variant={variant}
                    lang={lang}
                    onPress={() => setPressed(!pressed)}
                  >
                    {text.button}
                  </Button>
                ))}
                <Button
                  variant={variant}
                  disabled
                  lang={lang}
                  onPress={() => {}}
                >
                  {text.button}
                </Button>
              </View>
            ))}
            <Field label={lang === "tr" ? "Ad" : "Name"}>
              <TextInputField
                value={search}
                onChangeText={setSearch}
                placeholder={lang === "tr" ? "Adın" : "Your name"}
                accessibilityLabel="Plain input"
              />
            </Field>
          </>
        )}
        {panel === "patterns" && (
          <>
            <Title variant="displaySection">{"Provisional patterns"}</Title>
            <ListRow onPress={() => setSheet(true)}>
              {lang === "tr" ? "Kayıtlı haritalar" : "Saved charts"}
            </ListRow>
            <ChatBubble role="user">
              {lang === "tr"
                ? "Bugün için ne önerirsin?"
                : "What can I focus on today?"}
            </ChatBubble>
            <ChatBubble role="assistant">{text.subtitle}</ChatBubble>
            <Field label={lang === "tr" ? "Mesaj" : "Message"}>
              <TextInputField
                value={search}
                onChangeText={setSearch}
                placeholder={lang === "tr" ? "Bir soru yaz" : "Ask a question"}
                accessibilityLabel="Preview message"
              />
            </Field>
            <Button size="md" onPress={() => setSheet(true)}>
              {lang === "tr" ? "Önizleme" : "Preview"}
            </Button>
            <Sheet
              open={sheet}
              title={lang === "tr" ? "Seçenekler" : "Options"}
              onClose={() => setSheet(false)}
            >
              <ListRow onPress={() => setSheet(false)}>
                {lang === "tr" ? "Kapat" : "Close"}
              </ListRow>
            </Sheet>
          </>
        )}
        {panel === "traits" && (
          <>
            <Title variant="displaySection" lang={lang}>
              {lang === "tr" ? "Nitelikler" : "Qualities"}
            </Title>
            {[0, 2].map((row) => (
              <View
                key={row}
                style={{
                  flexDirection: "row",
                  gap: space[4],
                  paddingTop: space[4],
                }}
              >
                {[row, row + 1].map((i) => (
                  <TraitCard
                    key={i}
                    label={text.traits[i]!}
                    motif={
                      (
                        ["sun", "crescent", "triquetra", "lotus"] as MotifName[]
                      )[i]!
                    }
                    lang={lang}
                    selected={selected[i]!}
                    onToggle={(next) =>
                      setSelected((old) =>
                        old.map((v, j) => (i === j ? next : v)),
                      )
                    }
                  />
                ))}
              </View>
            ))}
          </>
        )}
        {panel === "type" && (
          <>
            {(Object.keys(styles) as TypeStyleName[]).map((variant) => (
              <View key={variant} style={{ gap: space[2] }}>
                <AppText variant="caption" color="inkFaint">
                  {variant}
                </AppText>
                <AppText variant={variant} lang={lang}>
                  {text.button}
                </AppText>
              </View>
            ))}
          </>
        )}
        {panel === "glyphs" && (
          <>
            {(Object.keys(glyphs) as GlyphSet[]).map((set) => (
              <View key={set} style={{ gap: space[4] }}>
                <Title variant="displaySection">{set}</Title>
                <View
                  style={{
                    flexDirection: "row",
                    flexWrap: "wrap",
                    gap: space[6],
                  }}
                >
                  {Object.keys(glyphs[set]).map((key) => (
                    <View
                      key={key}
                      style={{
                        width: size.buttonLg,
                        alignItems: "center",
                        gap: space[2],
                      }}
                    >
                      <Glyph
                        set={set}
                        name={key as IconName}
                        accessibilityLabel={key}
                      />
                      <AppText variant="caption" align="center">
                        {key}
                      </AppText>
                    </View>
                  ))}
                </View>
              </View>
            ))}
          </>
        )}
        {hero && (
          <>
            <View style={{ alignItems: "center" }}>
              <Emblem width={240} />
            </View>
            <Title variant="displayHero">{"Astrology"}</Title>
            <AppText variant="bodyLg" color="inkSoft" align="center">
              {text.subtitle}
            </AppText>
            <View style={{ marginTop: space[12] }}>
              <Button lang={lang} onPress={() => setPanel("controls")}>
                {text.button}
              </Button>
            </View>
          </>
        )}
        {panel === "wheel" && (
          <>
            <View style={{ alignItems: "center", gap: space[6] }}>
              <ChartWheel width={180} />
              <Divider width={240} />
              <Emblem width={180} />
            </View>
            <Title
              variant="displaySection"
              subtitle={text.subtitle}
              lang={lang}
            >
              {text.title}
            </Title>
            <Title variant="displayCard" lang={lang}>
              {text.traits[0]!}
            </Title>
          </>
        )}
      </Screen>
    </>
  );
}
export default function DesignSystemGallery() {
  const { theme, panel, lang } = useLocalSearchParams<{
    theme?: string;
    panel?: string;
    lang?: string;
  }>();
  const [loaded, error] = useFonts({
    "Aboreto-Regular": require("../../assets/fonts/design-system/Aboreto-Regular.ttf"),
    "Poppins-Regular": require("../../assets/fonts/design-system/Poppins-Regular.ttf"),
    "Poppins-Medium": require("../../assets/fonts/design-system/Poppins-Medium.ttf"),
    "Poppins-SemiBold": require("../../assets/fonts/design-system/Poppins-SemiBold.ttf"),
  });
  if (!__DEV__) return <Redirect href="/" />;
  if (error)
    return (
      <ThemeProvider>
        <AppText>Design fonts could not load.</AppText>
      </ThemeProvider>
    );
  if (!loaded)
    return <ActivityIndicator accessibilityLabel="Loading design fonts" />;
  return (
    <ThemeProvider
      key={`${theme}:${panel}:${lang}`}
      initialTheme={
        (theme === "parchment" ? "parchment" : "night") as ThemeName
      }
    >
      <GalleryContent />
    </ThemeProvider>
  );
}
