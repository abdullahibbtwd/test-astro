import { JobLifecycle } from "../src/lib/JobLifecycle";
import "../src/i18n";
import "../src/lib/notification-background";
import { NotificationLifecycle } from "../src/lib/NotificationLifecycle";
import { Stack, router, useSegments } from "expo-router";
import { useFonts } from "expo-font";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { useEffect, useState } from "react";
import { AppState, View, Text, StatusBar } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { BottomSheetModalProvider } from "@gorhom/bottom-sheet";
import { PersistQueryClientProvider } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";
import { focusManager, onlineManager } from "@tanstack/react-query";
import NetInfo from "@react-native-community/netinfo";
import * as SplashScreen from "expo-splash-screen";
import { initStorage, privateStorage } from "../src/lib/storage";
import { useApp } from "../src/lib/state";
import { restoreSession } from "../src/api/client";
import { queryClient } from "../src/api/query";
import i18n from "../src/i18n";
import { useTheme } from "../src/design/theme";
void SplashScreen.preventAutoHideAsync();
const persister = createSyncStoragePersister({
  storage: privateStorage,
  key: "query-cache",
});
export default function RootLayout() {
  const [loaded, fontError] = useFonts({
    Inter: require("../assets/fonts/Inter-Regular.ttf"),
    "Inter-SemiBold": require("../assets/fonts/Inter-SemiBold.ttf"),
    SourceSerif4: require("../assets/fonts/SourceSerif4-Regular.ttf"),
  });
  const [ready, setReady] = useState(false),
    [error, setError] = useState(false),
    app = useApp(),
    segments = useSegments(),
    c = useTheme();
  useEffect(() => {
    void initStorage()
      .then(async () => {
        useApp.getState().hydrate();
        await restoreSession();
        setReady(true);
      })
      .catch(() => setError(true));
    const listener = AppState.addEventListener("change", (state) =>
      focusManager.setFocused(state === "active"),
    );
    const unsubscribe = NetInfo.addEventListener((state) =>
      onlineManager.setOnline(!!state.isConnected),
    );
    return () => {
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
    const section = segments[0];
    if (!app.signedIn && section !== "(auth)" && section !== undefined)
      router.replace("/(auth)/welcome");
    if (app.signedIn) {
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
    app.me?.self_profile_id,
    app.draft.profileId,
    app.draft.step,
    segments,
  ]);
  if (error)
    return (
      <View style={{ flex: 1, justifyContent: "center", padding: 24 }}>
        <Text>Secure storage could not be opened. Restart the app.</Text>
      </View>
    );
  if (!ready || (!loaded && !fontError)) return null;
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <PersistQueryClientProvider
          client={queryClient}
          persistOptions={{ persister, maxAge: 86400000, buster: "phase1" }}
        >
          <BottomSheetModalProvider>
            <NotificationLifecycle />
            <StatusBar
              barStyle={c.bg === "#1A2030" ? "light-content" : "dark-content"}
            />
            <Stack
              screenOptions={{
                headerShown: false,
                contentStyle: { backgroundColor: c.bg },
                animation: "fade",
              }}
            >
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
                    presentation: "transparentModal",
                    animation: "fade",
                    contentStyle: { backgroundColor: "transparent" },
                  }}
                />
              ))}
            </Stack>
            <JobLifecycle />
          </BottomSheetModalProvider>
        </PersistQueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

export { RouteError as ErrorBoundary } from "../src/design/components/RouteError";
