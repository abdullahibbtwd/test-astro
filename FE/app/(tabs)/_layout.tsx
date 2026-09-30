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
    c = useTheme();
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
        tabBarLabelStyle: { fontFamily: "Inter", fontSize: 12 },
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
        headerRight: () => (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("ask")}
            onPress={() => router.push("/ask")}
            style={{ padding: 12 }}
          >
            <MessageCircle color={c.accent} size={24} />
          </Pressable>
        ),
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
