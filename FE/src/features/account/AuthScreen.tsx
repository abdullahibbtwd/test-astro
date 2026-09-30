import { useEffect, useRef, useState } from "react";
import { Alert, Platform, TextInput, View, Pressable } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Button,
  Field,
  ErrorNotice,
  Row,
  Choices,
  Chip,
} from "../../design/components";
import { useTheme } from "../../design/theme";
import { useApp } from "../../lib/state";
import { useActions } from "../../api/hooks";
export default function AuthScreen() {
  const { mode, fresh } = useLocalSearchParams<{
      mode?: string;
      fresh?: string;
    }>(),
    { t } = useTranslation(),
    c = useTheme(),
    app = useApp(),
    actions = useActions();
  const [email, setEmail] = useState(
      __DEV__ ? (fresh ? "new@example.com" : "demo@example.com") : "",
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
  const verify = async (value: string) => {
    if (submitting.current) return;
    submitting.current = true;
    try {
      const session = await actions.verify(email, value);
      router.replace(
        session.me.self_profile_id ? "/(tabs)" : "/(onboarding)/consent",
      );
    } catch {
    } finally {
      submitting.current = false;
    }
  };
  if (!app.languageChosen)
    return (
      <Screen>
        <Txt kind="caption">{"{{APP_NAME}}"}</Txt>
        <View style={{ height: 64 }} />
        <Txt kind="display">{t("chooseLanguage")}</Txt>
        <Txt muted>{t("languageHint")}</Txt>
        <Choices>
          {(["tr", "en"] as const).map((lang) => (
            <Chip
              key={lang}
              label={lang === "tr" ? "Türkçe" : "English"}
              selected={app.language === lang}
              onPress={() => app.update({ language: lang })}
            />
          ))}
        </Choices>
        <Button
          label={t("continue")}
          onPress={() => app.update({ languageChosen: true })}
        />
      </Screen>
    );
  if (mode === "email" || mode === "verify")
    return (
      <Screen back>
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
                void actions
                  .startEmail(email)
                  .then(() => {
                    setCooldown(30);
                    router.setParams({ mode: "verify" });
                  })
                  .catch(() => {});
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
              <View style={{ flexDirection: "row", gap: 8 }}>
                {Array.from({ length: 6 }, (_, i) => (
                  <View
                    key={i}
                    style={{
                      flex: 1,
                      height: 58,
                      borderWidth: 1,
                      borderColor: c.hair,
                      borderRadius: 12,
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
                void actions
                  .startEmail(email)
                  .then(() => {
                    setCooldown(30);
                    setCode("");
                  })
                  .catch(() => {});
              }}
            />
          </>
        )}
        <ErrorNotice error={actions.error} />
        {__DEV__ && (
          <Txt kind="caption" muted>
            {t("previewLogin", { email })}
          </Txt>
        )}
      </Screen>
    );
  return (
    <Screen>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Txt kind="caption">{"{{APP_NAME}}"}</Txt>
        <Chip
          label={app.language === "tr" ? "TR" : "EN"}
          selected={false}
          onPress={() =>
            app.update({ language: app.language === "tr" ? "en" : "tr" })
          }
        />
      </View>
      <View style={{ height: 40 }} />
      <Txt kind="display">{t("welcome")}</Txt>
      <Txt muted>{t("welcomeBody")}</Txt>
      <View>
        {["whoAmI", "whatsAhead", "whoFits", "whereToBe"].map((key, i) => (
          <Row
            key={key}
            label={`${String(i + 1).padStart(2, "0")}    ${t(key)}`}
          />
        ))}
      </View>
      <View style={{ gap: 12 }}>
        {Platform.OS === "ios" && (
          <Button
            secondary
            label={t("appleContinue")}
            onPress={() =>
              Alert.alert(t("appleContinue"), t("providerUnavailable"))
            }
          />
        )}
        <Button
          secondary
          label={t("googleContinue")}
          onPress={() =>
            Alert.alert(t("googleContinue"), t("providerUnavailable"))
          }
        />
        <Button
          label={t("emailContinue")}
          onPress={() => router.push("/(auth)/welcome?mode=email")}
        />
      </View>
      {__DEV__ && (
        <Button
          secondary
          label={t("tryOnboarding")}
          onPress={() => router.push("/(auth)/welcome?mode=email&fresh=1")}
        />
      )}
      <Choices>
        {["terms", "privacy"].map((key) => (
          <Chip
            key={key}
            label={t(key)}
            selected={false}
            onPress={() => Alert.alert(t(key), t("legalUnavailable"))}
          />
        ))}
      </Choices>
      <Txt kind="caption" muted>
        {t("disclaimer")}
      </Txt>
    </Screen>
  );
}
