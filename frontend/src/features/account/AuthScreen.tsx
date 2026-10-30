import { GuestWelcomeScreen, WelcomeFooter } from "../onboarding/GuestOnboarding";
import { Title } from "../../design-system/components/Title";
import { space as dsSpace, radius as dsRadius } from "../../design-system/theme/tokens";
import { Emblem } from "../../design-system/components/Ornament";
import { showSnackbar } from "../../design/components/Snackbar";
import Constants from "expo-constants";
import { providerSignIn, ProviderUnavailable } from "../../lib/oauth";
import { useEffect, useRef, useState } from "react";
import { TextInput, View, Pressable } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Field,
  ErrorNotice,
} from "../../design/components";
import { useTheme } from "../../design/theme";
import { useActions } from "../../api/hooks";
import { routeAfterSignIn } from "../../api/client";
import { ApiError, NetworkError } from "../../api/errors";
import { resolveRoute } from "../../lib/routes";
import { showDemoLoginHint, isSupabaseAuth } from "../../lib/supabase";

const demoBackend =
  !isSupabaseAuth() &&
  __DEV__ &&
  process.env.EXPO_PUBLIC_AUTH_MODE !== "supabase";

export default function AuthScreen() {
  const { mode, fresh } = useLocalSearchParams<{
      mode?: string;
      fresh?: string;
    }>(),
    { t } = useTranslation(),
    c = useTheme(),
    actions = useActions();
  const [providerBusy, setProviderBusy] = useState(false),
    [providerError, setProviderError] = useState<unknown>(),
    [authError, setAuthError] = useState<unknown>();
  const signIn = async (provider: "google" | "apple") => {
    if (!demoBackend && provider === "google") {
      router.push("/(auth)/link?provider=google");
      return;
    }
    setProviderBusy(true);
    setProviderError(undefined);
    try {
      const session = await providerSignIn(provider);
      if (session) router.replace(resolveRoute(routeAfterSignIn()));
    } catch (e) {
      if (e instanceof ProviderUnavailable)
        showSnackbar(t("providerUnavailable"));
      else setProviderError(e);
    } finally {
      setProviderBusy(false);
    }
  };
  const [email, setEmail] = useState(
      demoBackend && showDemoLoginHint()
        ? fresh
          ? "new@example.com"
          : "demo@example.com"
        : "",
    ),
    [code, setCode] = useState(""),
    [cooldown, setCooldown] = useState(0);
  const input = useRef<TextInput>(null),
    submitting = useRef(false);
  useEffect(() => {
    if (!cooldown) return;
    const id = setTimeout(() => setCooldown(cooldown - 1), 1000);
    return () => clearTimeout(id);
  }, [cooldown]);
  const explainAuthError = (error: unknown) => {
    if (error instanceof NetworkError) return error;
    if (error instanceof ApiError) {
      if (error.code === "rate_limited") return error;
      if (error.code === "unauthorized")
        return new ApiError(401, "otp_invalid");
      return error;
    }
    return error;
  };
  const verify = async (value: string) => {
    if (submitting.current) return;
    submitting.current = true;
    setAuthError(undefined);
    try {
      await actions.verify(email, value);
      router.replace(resolveRoute(routeAfterSignIn()));
    } catch (e) {
      setAuthError(explainAuthError(e));
      setCode("");
    } finally {
      submitting.current = false;
    }
  };
  if (!mode && process.env.EXPO_PUBLIC_BACKEND_MODE !== "demo")
    return <GuestWelcomeScreen />;
  if (mode === "email" || mode === "verify")
    return (
      <Screen headerless back>
        <Txt kind="display">
          {t(mode === "email" ? "emailTitle" : "checkInbox")}
        </Txt>
        {mode === "email" ? (
          <>
            <Field
              label={t("email")}
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              autoComplete="email"
            />
            <Button
              label={t("sendCode")}
              disabled={!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)}
              loading={actions.isPending}
              onPress={() => {
                setAuthError(undefined);
                void actions
                  .startEmail(email)
                  .then(() => {
                    setCooldown(60);
                    router.setParams({ mode: "verify" });
                  })
                  .catch((e) => setAuthError(explainAuthError(e)));
              }}
            />
          </>
        ) : (
          <>
            <Txt muted>{t("codeHint")}</Txt>
            <Pressable
              onPress={() => input.current?.focus()}
              accessibilityLabel={t("code")}
            >
              <View style={{ flexDirection: "row", gap: dsSpace[2] }}>
                {Array.from({ length: 6 }, (_, i) => (
                  <View
                    key={i}
                    style={{
                      flex: 1,
                      height: 58,
                      borderWidth: 1,
                      borderColor: c.hair,
                      borderRadius: dsRadius.md,
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Txt kind="title">{code[i] ?? " "}</Txt>
                  </View>
                ))}
              </View>
            </Pressable>
            <TextInput
              ref={input}
              accessibilityLabel={t("code")}
              value={code}
              keyboardType="number-pad"
              textContentType="oneTimeCode"
              autoComplete="sms-otp"
              maxLength={6}
              style={{ position: "absolute", width: 1, height: 1, opacity: 0 }}
              onChangeText={(value) => {
                const digits = value.replace(/\D/g, "").slice(0, 6);
                setCode(digits);
                if (digits.length === 6) void verify(digits);
              }}
              autoFocus
            />
            <Button
              label={cooldown ? `${t("resend")} (${cooldown})` : t("resend")}
              secondary
              disabled={cooldown > 0}
              onPress={() => {
                setAuthError(undefined);
                void actions
                  .startEmail(email)
                  .then(() => {
                    setCooldown(60);
                    setCode("");
                  })
                  .catch((e) => setAuthError(explainAuthError(e)));
              }}
            />
          </>
        )}
        <ErrorNotice error={authError ?? actions.error} />
        {showDemoLoginHint() && (
          <Txt kind="caption" muted>
            {t("previewLogin", { email: email || "demo@example.com" })}
          </Txt>
        )}
      </Screen>
    );
  return (
    <Screen headerless arch grain footer={<WelcomeFooter />}>
      <Title variant="displayHero">{Constants.expoConfig?.name ?? "Astrology"}</Title>
      <View style={{ alignItems: "center" }}><Emblem width={120} /></View>
      <Txt kind="display">{t("guestMore")}</Txt>
      <Txt muted>{t("guestUnlockBody")}</Txt>
      <ErrorNotice error={providerError} />
      <Button secondary label={t("googleContinue")} loading={providerBusy} onPress={() => void signIn("google")} />
      <Button
        label={t("emailContinue")}
        onPress={() => router.push("/(auth)/welcome?mode=email")}
      />
      <Button secondary label={t("back")} onPress={() => router.back()} />
    </Screen>
  );
}
