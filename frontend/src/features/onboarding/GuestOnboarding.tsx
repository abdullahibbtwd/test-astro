import { useEffect, useRef, useState } from "react";
import {
  AccessibilityInfo,
  ActivityIndicator,
  Animated,
  Easing,
  Modal,
  Pressable,
  ScrollView,
  View,
  useWindowDimensions,
} from "react-native";
import * as Linking from "expo-linking";
import Constants from "expo-constants";
import { router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  ErrorNotice,
  Progress,
  Row,
} from "../../design/components";
import { DateTimeField } from "../../design/components/DateTimeField";
import { PlaceSearch } from "../../design/components/PlaceSearch";
import { SelectField, Field } from "../../design-system/components/Fields";
import { AppText } from "../../design-system/text/AppText";
import { Emblem } from "../../design-system/components/Ornament";
import { space } from "../../design-system/theme/tokens";
import { useTheme } from "../../design/theme";
import { useApp } from "../../lib/state";
import { useConfig } from "../../api/hooks";
import { validBirth, todayLocal } from "../../lib/dates";
import {
  clearGuestReading,
  getGuestReading,
  hasGuestReading,
  retryGuestClaim,
  startGuestReading,
} from "../../lib/guest-onboarding";
import { showSnackbar } from "../../design/components/Snackbar";
import { queryClient } from "../../api/query";
const padding = space[6];
export function WelcomeFooter() {
  const { t } = useTranslation(),
    app = useApp(),
    config = useConfig();
  return (
    <View
      testID="welcome-footer"
      style={{
        paddingHorizontal: padding,
        paddingVertical: space[2],
        flexDirection: "row",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <View style={{ flexDirection: "row" }}>
        {(["en", "tr"] as const).map((language) => (
          <Pressable
            key={language}
            accessibilityRole="button"
            accessibilityLabel={language === "en" ? "English" : "Türkçe"}
            accessibilityState={{ selected: app.language === language }}
            onPress={() => app.update({ language, languageChosen: true })}
            style={{
              minWidth: 48,
              minHeight: 44,
              justifyContent: "center",
              paddingHorizontal: space[2],
            }}
          >
            <AppText
              variant="caption"
              color={app.language === language ? "accent" : "inkSoft"}
            >
              {language === "en" ? "EN" : "TR"}
            </AppText>
          </Pressable>
        ))}
      </View>
      <View style={{ flexDirection: "row" }}>
        {(["terms", "privacy"] as const).map((key) => (
          <Pressable
            key={key}
            accessibilityRole="link"
            accessibilityLabel={t(key)}
            style={{
              minHeight: 44,
              paddingHorizontal: space[2],
              justifyContent: "center",
            }}
            onPress={() => {
              const url = config.data?.links[key];
              if (url && /^https:\/\//.test(url))
                void Linking.openURL(url).catch(() =>
                  showSnackbar(t("legalUnavailable")),
                );
              else showSnackbar(t("legalUnavailable"));
            }}
          >
            <AppText variant="caption" color="inkSoft" style={{ fontSize: 11 }}>
              {t(key)}
            </AppText>
          </Pressable>
        ))}
      </View>
    </View>
  );
}
function Brand() {
  return (
    <AppText
      variant="displayHero"
      color="accent"
      align="center"
      accessibilityRole="header"
      numberOfLines={1}
      adjustsFontSizeToFit
      style={{ fontSize: 44, lineHeight: 54 }}
    >
      {Constants.expoConfig?.name ?? "ASTROLOGY"}
    </AppText>
  );
}
function BirthAnimation() {
  const rotation = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    let active = true,
      loop: Animated.CompositeAnimation | undefined;
    const start = (reduced: boolean) => {
      loop?.stop();
      rotation.setValue(0);
      if (active && !reduced) {
        loop = Animated.loop(
          Animated.timing(rotation, {
            toValue: 1,
            duration: 14000,
            easing: Easing.linear,
            useNativeDriver: true,
          }),
        );
        loop.start();
      }
    };
    void AccessibilityInfo.isReduceMotionEnabled().then(start);
    const subscription = AccessibilityInfo.addEventListener(
      "reduceMotionChanged",
      start,
    );
    return () => {
      active = false;
      loop?.stop();
      subscription.remove();
    };
  }, [rotation]);
  return (
    <View style={{ alignItems: "center", paddingVertical: space[6] }}>
      <Animated.View
        style={{
          transform: [
            {
              rotate: rotation.interpolate({
                inputRange: [0, 1],
                outputRange: ["0deg", "360deg"],
              }),
            },
          ],
        }}
      >
        <Emblem width={150} />
      </Animated.View>
    </View>
  );
}
export function GuestWelcomeScreen() {
  const app = useApp(),
    { t } = useTranslation(),
    theme = useTheme(),
    { height } = useWindowDimensions();
  const [placeOpen, setPlaceOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const draft = app.draft;
  const submit = async () => {
    if (busy || !draft.place) return;
    setBusy(true);
    setError(undefined);
    try {
      app.update({ languageChosen: true });
      await startGuestReading({
        birth_date: draft.date,
        birth_time: draft.time,
        birth_place_id: draft.place.place_id,
        consent: true,
        lang: app.language,
      });
      queryClient.removeQueries({ queryKey: ["guest-core"] });
      router.push("/(auth)/core");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen headerless arch grain scroll={false}>
      <View style={{ flex: 1 }}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{
            flexGrow: 1,
            justifyContent: "center",
            paddingHorizontal: padding + space[2],
            paddingTop: space[6],
            paddingBottom: space[2],
            gap: height < 720 ? space[3] : space[4],
          }}
        >
          <Brand />
          <View style={{ alignItems: "center" }}>
            <Emblem width={height < 720 ? 76 : 108} />
          </View>
          <AppText variant="displaySection" color="accent" align="center">
            {t("guestWelcome")}
          </AppText>
          <View style={{ flexDirection: "row", gap: space[3] }}>
            <View style={{ flex: 1.4 }}>
              <DateTimeField
                mode="date"
                compact
                value={draft.date}
                onChange={(date) => app.editDraft({ date })}
              />
            </View>
            <View style={{ flex: 1 }}>
              <DateTimeField
                mode="time"
                placeholder={t("guestTime")}
                value={draft.time}
                onChange={(time) => app.editDraft({ time })}
              />
            </View>
          </View>
          <Field label={t("birthPlace")}>
            <SelectField
              accessibilityLabel={t("birthPlace")}
              valueLabel={
                draft.place
                  ? [draft.place.name, draft.place.country_name]
                      .filter(Boolean)
                      .join(", ")
                  : undefined
              }
              placeholder={t("guestChoosePlace")}
              onPress={() => setPlaceOpen(true)}
            />
          </Field>
          <Pressable
            accessibilityRole="checkbox"
            accessibilityLabel={t("guestConsent")}
            accessibilityState={{ checked: draft.consent }}
            onPress={() => app.editDraft({ consent: !draft.consent })}
            style={{
              minHeight: 44,
              flexDirection: "row",
              gap: space[3],
              alignItems: "center",
            }}
          >
            <View
              style={{
                width: 20,
                height: 20,
                borderWidth: 1,
                borderColor: theme.accent,
                backgroundColor: draft.consent ? theme.accent : "transparent",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              {draft.consent && (
                <Txt style={{ color: theme.onAccent, fontSize: 13 }}>✓</Txt>
              )}
            </View>
            <Txt kind="caption" muted style={{ flex: 1, fontSize: 12 }}>
              {t("guestConsent")}
            </Txt>
          </Pressable>
          <ErrorNotice error={error} />
          <Button
            label={t("guestFindMe")}
            loading={busy}
            disabled={
              !draft.consent ||
              !draft.place ||
              !validBirth(draft.date, draft.time, todayLocal())
            }
            onPress={() => void submit()}
          />
          {hasGuestReading() && (
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push("/(auth)/core")}
              style={{ minHeight: 44, justifyContent: "center" }}
            >
              <AppText variant="caption" color="accent" align="center">
                {t("guestResume")}
              </AppText>
            </Pressable>
          )}
          <Pressable
            accessibilityRole="button"
            onPress={() => router.push("/(auth)/welcome?mode=signin")}
            style={{ minHeight: 44, justifyContent: "center" }}
          >
            <AppText variant="caption" align="center" color="inkSoft">
              {t("guestAlreadyAccount")}
            </AppText>
          </Pressable>
        </ScrollView>
        <WelcomeFooter />
      </View>
      <Modal
        visible={placeOpen}
        animationType="slide"
        onRequestClose={() => setPlaceOpen(false)}
      >
        <Screen
          headerless
          footer={
            <Button
              secondary
              label={t("cancel")}
              onPress={() => setPlaceOpen(false)}
            />
          }
        >
          <Txt kind="display">{t("birthPlace")}</Txt>
          <PlaceSearch
            onConfirm={(place) => {
              app.editDraft({ place });
              setPlaceOpen(false);
            }}
          />
        </Screen>
      </Modal>
    </Screen>
  );
}
export function GuestCoreScreen() {
  const { t } = useTranslation(),
    app = useApp();
  const [claimError, setClaimError] = useState<unknown>(),
    [claimBusy, setClaimBusy] = useState(false);
  const reading = useQuery({
    queryKey: ["guest-core", app.language],
    queryFn: getGuestReading,
    enabled: !app.guestClaimPending && hasGuestReading(),
    retry: false,
    refetchInterval: (query) =>
      query.state.error ||
      query.state.data?.status === "ready" ||
      query.state.data?.status === "failed"
        ? false
        : 1600,
  });
  const ready = !reading.error && reading.data?.status === "ready",
    failed = reading.data?.status === "failed",
    missing = !hasGuestReading();
  const restart = async () => {
    setClaimBusy(true);
    setClaimError(undefined);
    try {
      await clearGuestReading();
      router.replace(app.signedIn ? "/(tabs)" : "/(auth)/welcome");
    } catch (error) {
      setClaimError(error);
    } finally {
      setClaimBusy(false);
    }
  };
  const retry = async () => {
    if (claimBusy) return;
    setClaimBusy(true);
    setClaimError(undefined);
    try {
      if (app.guestClaimPending) {
        await retryGuestClaim();
      } else {
        const { draft, language } = useApp.getState();
        if (!draft.place) {
          router.replace("/(auth)/welcome");
          return;
        }
        await startGuestReading({
          birth_date: draft.date,
          birth_time: draft.time,
          birth_place_id: draft.place.place_id,
          consent: true,
          lang: language,
        });
        await reading.refetch();
      }
    } catch (e) {
      setClaimError(e);
    } finally {
      setClaimBusy(false);
    }
  };
  return (
    <Screen headerless arch grain scroll={false}>
      <View style={{ flex: 1 }}>
        <ScrollView
          contentContainerStyle={{
            padding,
            paddingTop: space[6],
            gap: space[6],
          }}
        >
          <Brand />
          {app.guestClaimPending ? (
            <>
              <Txt kind="display">{t("guestSaving")}</Txt>
              <Txt muted>{t("guestClaimRetry")}</Txt>
              <ErrorNotice error={claimError} />
              <Button
                label={t("retry")}
                loading={claimBusy}
                onPress={() => void retry()}
              />
              <Button
                secondary
                label={t("guestContinueAccount")}
                disabled={claimBusy}
                onPress={() => void restart()}
              />
            </>
          ) : missing ? (
            <>
              <Txt kind="display">{t("guestExpired")}</Txt>
              <Button
                label={t("guestStartAgain")}
                onPress={() => router.replace("/(auth)/welcome")}
              />
            </>
          ) : ready ? (
            <>
              <View style={{ gap: space[3] }}>
                <Txt kind="caption">{t("guestProgress")}</Txt>
                <Progress step={40} total={100} />
              </View>
              <Txt kind="display">{reading.data!.section!.title}</Txt>
              <Txt kind="reading">{reading.data!.section!.text}</Txt>
              <Txt kind="display">{t("guestMore")}</Txt>
              <Txt muted>{t("guestUnlockBody")}</Txt>
              {["guestAhead", "guestMatch", "guestWhere"].map((key) => (
                <Row key={key} label={t(key)} detail={t("guestAfterSignIn")} />
              ))}
            </>
          ) : (
            <>
              <BirthAnimation />
              <Txt kind="display">{t("guestPreparing")}</Txt>
              <Txt muted>{t("guestPreparingBody")}</Txt>
              {!reading.error && !failed && (
                <ActivityIndicator accessibilityLabel={t("guestPreparing")} />
              )}
              <ErrorNotice
                error={
                  reading.error ??
                  claimError ??
                  (failed ? { code: "generation_failed" } : undefined)
                }
                retry={() => void retry()}
              />
              {(reading.error || failed) && (
                <Button
                  secondary
                  label={t("guestStartAgain")}
                  loading={claimBusy}
                  onPress={() => void restart()}
                />
              )}
            </>
          )}
        </ScrollView>
        {ready && !app.guestClaimPending && (
          <View
            style={{ paddingHorizontal: padding, paddingVertical: space[3] }}
          >
            <Button
              label={t("guestMore")}
              onPress={() => router.push("/(auth)/welcome?mode=signin")}
            />
          </View>
        )}
        <WelcomeFooter />
      </View>
    </Screen>
  );
}
export function OnboardingUnlockedScreen() {
  const { t } = useTranslation(),
    app = useApp();
  const open = (
    path: "/(tabs)" | "/(tabs)/ahead" | "/(tabs)/match" | "/(tabs)/map",
  ) => {
    app.update({ onboardingUnlockProfileId: null });
    router.replace(path);
  };
  return (
    <Screen headerless arch grain scroll={false}>
      <View style={{ flex: 1 }}>
        <ScrollView
          contentContainerStyle={{
            padding,
            paddingTop: space[6],
            gap: space[6],
          }}
        >
          <Brand />
          <View style={{ alignItems: "center" }}>
            <Emblem width={120} />
          </View>
          <Txt kind="display">{t("guestUnlocked")}</Txt>
          <Progress step={100} total={100} />
          <Txt muted>{t("guestUnlockedBody")}</Txt>
          <Row label={t("guestAhead")} onPress={() => open("/(tabs)/ahead")} />
          <Row label={t("guestMatch")} onPress={() => open("/(tabs)/match")} />
          <Row label={t("guestWhere")} onPress={() => open("/(tabs)/map")} />
          <Button label={t("guestExplore")} onPress={() => open("/(tabs)")} />
        </ScrollView>
        <WelcomeFooter />
      </View>
    </Screen>
  );
}
