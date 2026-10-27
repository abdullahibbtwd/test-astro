import { AppText } from "../src/design-system/text/AppText";
import { ThemeProvider } from "../src/design-system/ThemeProvider";
import { type as dsType } from "../src/design-system/theme/tokens";
import { Snackbar } from "../src/design/components/Snackbar";
import {
  CACHE_MAX_AGE,
  CACHE_BUSTER,
  shouldPersistQuery,
  serializeCache,
} from "../src/api/cache-policy";
import { initTelemetry, reportError } from "../src/lib/telemetry";
import { JobLifecycle } from "../src/lib/JobLifecycle";
import "../src/i18n";
import "../src/lib/notification-background";
import { NotificationLifecycle } from "../src/lib/NotificationLifecycle";
import { Stack, router, useSegments } from "expo-router";
import { useFonts } from "expo-font";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { useEffect, useState } from "react";
import { AppState, View, StatusBar } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { BottomSheetModalProvider } from "@gorhom/bottom-sheet";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { focusManager, onlineManager } from "@tanstack/react-query";
import NetInfo from "@react-native-community/netinfo";
import * as SplashScreen from "expo-splash-screen";
import { initStorage, privateStorage } from "../src/lib/storage";
import { bindSupabaseAuthLifecycle } from "../src/lib/supabase";
import { useApp } from "../src/lib/state";
import { restoreSession } from "../src/api/client";
import { queryClient } from "../src/api/query";
import i18n from "../src/i18n";
import { useTheme } from "../src/design/theme";
void SplashScreen.preventAutoHideAsync();
void initTelemetry();
const persister = createSyncStoragePersister({
  storage: privateStorage,
  key: "query-cache",
  serialize: serializeCache,
});
export default function RootLayout() {
  const [loaded, fontError] = useFonts({
    "Aboreto-Regular": require("../assets/fonts/design-system/Aboreto-Regular.ttf"),
    "Poppins-Regular": require("../assets/fonts/design-system/Poppins-Regular.ttf"),
    "Poppins-Medium": require("../assets/fonts/design-system/Poppins-Medium.ttf"),
    "Poppins-SemiBold": require("../assets/fonts/design-system/Poppins-SemiBold.ttf"),
    Inter: require("../assets/fonts/Inter-Regular.ttf"),
    "Inter-SemiBold": require("../assets/fonts/Inter-SemiBold.ttf"),
    SourceSerif4: require("../assets/fonts/SourceSerif4-Regular.ttf"),
  });
  const [ready, setReady] = useState(false),
    [error, setError] = useState(false),
    app = useApp(),
    segments: readonly string[] = useSegments(),
    c = useTheme();
  useEffect(() => {
    void initStorage()
      .then(async () => {
        useApp.getState().hydrate();
        await restoreSession();
        setReady(true);
      })
      .catch((error) => {
        reportError(error, { area: "storage" });
        setError(true);
      });
    const unbindAuth = bindSupabaseAuthLifecycle();
    const listener = AppState.addEventListener("change", (state) =>
      focusManager.setFocused(state === "active"),
    );
    const unsubscribe = NetInfo.addEventListener((state) =>
      onlineManager.setOnline(!!state.isConnected),
    );
    return () => {
      unbindAuth();
      listener.remove();
      unsubscribe();
    };
  }, []);
  useEffect(() => {
    void i18n.changeLanguage(app.language);
  }, [app.language]);
  useEffect(() => {
    if ((loaded || fontError) && (ready || error))
      void SplashScreen.hideAsync();
  }, [loaded, fontError, ready, error]);
  useEffect(() => {
    if (!ready) return;
    if (__DEV__ && segments[0] === "design-system-gallery") return;
    const section = segments[0];
    if (!app.signedIn && section !== "(auth)" && section !== undefined)
      router.replace("/(auth)/welcome");
    if (app.signedIn) {
      if (app.guestClaimPending) {
        if (segments[1] !== "core") router.replace("/(auth)/core");
        return;
      }
      if (app.onboardingUnlockProfileId) {
        if (segments[1] !== "unlocked") router.replace("/(auth)/unlocked");
        return;
      }
      const onboarding =
        !app.me?.self_profile_id ||
        (app.draft.profileId === app.me.self_profile_id &&
          app.draft.step !== "complete");
      if (onboarding && section !== "(onboarding)")
        router.replace(
          `/(onboarding)/${app.draft.step === "complete" ? "consent" : app.draft.step}`,
        );
      else if (!onboarding && section === "(auth)") router.replace("/(tabs)");
    }
  }, [
    ready,
    app.signedIn,
    app.guestClaimPending,
    app.onboardingUnlockProfileId,
    app.me?.self_profile_id,
    app.draft.profileId,
    app.draft.step,
    segments,
  ]);
  if (error)
    return (
      <View style={{ flex: 1, justifyContent: "center", padding: 24 }}>
        <AppText>Secure storage could not be opened. Restart the app.</AppText>
      </View>
    );
  if (!ready || (!loaded && !fontError)) return null;
  return (
    <ThemeProvider theme={c.dark ? "night" : "parchment"}>
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: c.bg }}>
      <SafeAreaProvider>
        <PersistQueryClientProvider
          client={queryClient}
          persistOptions={{
            persister,
            maxAge: CACHE_MAX_AGE,
            buster: CACHE_BUSTER,
            dehydrateOptions: {
              shouldDehydrateQuery: (q) =>
                shouldPersistQuery(q, queryClient.getQueryCache().getAll()),
            },
          }}
        >
          <BottomSheetModalProvider>
            <NotificationLifecycle />
            <StatusBar
              barStyle={c.dark ? "light-content" : "dark-content"}
            />
            <Stack
              screenOptions={{
                headerShown: true,
                headerStyle: { backgroundColor: c.bg },
                headerTintColor: c.accent,
                headerTitleStyle: { ...dsType.displaySection, color: c.accent },
                headerTitle: ({ children }) => <AppText variant="displaySection" color="accent" numberOfLines={1}>{children}</AppText>,
                headerShadowVisible: false,
                headerBackButtonDisplayMode: "minimal",
                contentStyle: { backgroundColor: c.bg },
              }}
            >
              <Stack.Screen
                name="(auth)"
                options={{ headerShown: false, animation: "fade" }}
              />
              <Stack.Screen
                name="(onboarding)"
                options={{ headerShown: false, animation: "fade" }}
              />
              <Stack.Screen
                name="(tabs)"
                options={{ headerShown: false, animation: "fade" }}
              />
              <Stack.Screen
                name="ask/index"
                options={{ presentation: "modal" }}
              />
              <Stack.Screen
                name="ask/[threadId]"
                options={{ presentation: "modal" }}
              />
              <Stack.Screen
                name="chart/export"
                options={{ presentation: "modal" }}
              />
              {[
                "map/place/[placeId]",
                "map/point",
                "map/area/[areaId]",
                "map/line/[body]/[angle]",
              ].map((name) => (
                <Stack.Screen
                  key={name}
                  name={name}
                  options={{
                    headerShown: false,
                    presentation: "transparentModal",
                    animation: "fade",
                    contentStyle: { backgroundColor: "transparent" },
                  }}
                />
              ))}
            </Stack>
            <JobLifecycle />
            <Snackbar />
          </BottomSheetModalProvider>
        </PersistQueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
    </ThemeProvider>
  );
}

export { RouteError as ErrorBoundary } from "../src/design/components/RouteError";
