import { View, Text } from "react-native";
import { Share2 } from "lucide-react-native";
import { ProfileSwitcher } from "../../src/design/components/ProfileSwitcher";
import { IconButton } from "../../src/design/components/IconButton";
import { useApp } from "../../src/lib/state";
import { useFlags } from "../../src/lib/flags";
import { Tabs, router } from "expo-router";
import { Pressable } from "react-native";
import {
  House,
  CircleDot,
  CalendarDays,
  Users,
  MapPin,
  CircleUserRound,
  MessageCircle,
} from "lucide-react-native";
import { useTranslation } from "react-i18next";
import { useTheme } from "../../src/design/theme";
export default function TabLayout() {
  const { t } = useTranslation(),
    c = useTheme(),
    flags = useFlags(),
    app = useApp();
  const icons = [House, CircleDot, CalendarDays, Users, MapPin];
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: c.bg },
        headerShadowVisible: false,
        headerTitleStyle: { fontFamily: "Inter-SemiBold", color: c.ink },
        tabBarStyle: {
          backgroundColor: c.surface,
          borderTopColor: c.hair,
          height: 70,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: c.accent,
        tabBarInactiveTintColor: c.ink2,
        tabBarLabel: ({ children, color }) => <Text maxFontSizeMultiplier={1.3} style={{ fontFamily: "Inter", fontSize: 12, color }}>{children}</Text>,
        headerLeft: () => (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("profile")}
            onPress={() => router.push("/profile")}
            style={{ padding: 12 }}
          >
            <CircleUserRound color={c.ink} size={24} />
          </Pressable>
        ),
        headerRight: () =>
          flags.askAstrology ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("ask")}
              onPress={() => router.push("/ask")}
              style={{ padding: 12 }}
            >
              <MessageCircle color={c.accent} size={24} />
            </Pressable>
          ) : null,
      }}
    >
      {["index", "chart", "ahead", "match", "map"].map((name, i) => {
        const Icon = icons[i]!;
        return (
          <Tabs.Screen
            key={name}
            name={name}
            options={{
              title: t(i === 0 ? "home" : name),
              ...(["chart", "ahead", "map"].includes(name)
                ? {
                    headerTitle: () => (
                      <ProfileSwitcher
                        onSelect={(id) => {
                          if (name !== "chart")
                            router.setParams({ profile: id });
                        }}
                      />
                    ),
                  }
                : {}),
              ...(name === "chart"
                ? {
                    headerRight: () => (
                      <View style={{ flexDirection: "row" }}>
                        <IconButton
                          accessibilityLabel={t("exportShare")}
                          icon={<Share2 color={c.ink} size={22} />}
                          onPress={() =>
                            router.push(
                              `/chart/export?profile=${app.activeProfileId ?? app.me?.self_profile_id ?? ""}`,
                            )
                          }
                        />
                        {flags.askAstrology && (
                          <IconButton
                            accessibilityLabel={t("ask")}
                            icon={<MessageCircle color={c.accent} size={22} />}
                            onPress={() => router.push("/ask")}
                          />
                        )}
                      </View>
                    ),
                  }
                : {}),
              tabBarIcon: ({ color, size }) => (
                <Icon color={color} size={size} />
              ),
            }}
          />
        );
      })}
    </Tabs>
  );
}
