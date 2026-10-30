import { space as dsSpace } from "../../design-system/theme/tokens";
import { useCallback, useEffect, useRef, useState } from "react";
import { View, AppState } from "react-native";
import * as Linking from "expo-linking";
import { router, useLocalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import {
  Screen,
  Txt,
  Field,
  Button,
  ErrorNotice,
} from "../../design/components";
import {
  startBrowserSignIn,
  pollBrowserSignIn,
  cancelBrowserSignIn,
  type SignInTicket,
} from "../../lib/browser-signin";
import { ApiError, setSession, routeAfterSignIn } from "../../api/client";
import { resolveRoute } from "../../lib/routes";
export default function BrowserSignInScreen() {
  const { provider: raw } = useLocalSearchParams<{ provider?: string }>();
  const provider = raw === "google" ? "google" : "email";
  const { t } = useTranslation();
  const [email, setEmail] = useState(""),
    [ticket, setTicket] = useState<SignInTicket | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const alive = useRef(true),
    current = useRef<SignInTicket | null>(null),
    starting = useRef(false),
    auto = useRef(false);
  const start = useCallback(async () => {
    if (starting.current) return;
    starting.current = true;
    setBusy(true);
    setError(undefined);
    if (current.current) {
      await cancelBrowserSignIn(current.current);
      current.current = null;
      setTicket(null);
    }
    try {
      const next = await startBrowserSignIn(provider, email);
      if (!alive.current) {
        await cancelBrowserSignIn(next);
        return;
      }
      current.current = next;
      setTicket(next);
      if (next.url) await Linking.openURL(next.url);
    } catch (e) {
      if (alive.current) setError(e);
    } finally {
      starting.current = false;
      if (alive.current) setBusy(false);
    }
  }, [provider, email]);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (current.current) void cancelBrowserSignIn(current.current);
    };
  }, []);
  useEffect(() => {
    if (provider === "google" && !auto.current) {
      auto.current = true;
      void start();
    }
  }, [provider, start]); // One browser launch on entry.
  useEffect(() => {
    if (!ticket) return;
    let stopped = false,
      checking = false;
    const check = async () => {
      if (stopped || checking || AppState.currentState !== "active") return;
      if (Date.now() >= Date.parse(ticket.expires_at)) {
        setError(new ApiError(401, "unauthorized"));
        setTicket(null);
        return;
      }
      checking = true;
      try {
        const session = await pollBrowserSignIn(ticket);
        if (!stopped && session) {
          await setSession(session);
          await cancelBrowserSignIn(ticket);
          current.current = null;
          router.replace(resolveRoute(routeAfterSignIn()));
        }
      } catch (e) {
        if (!stopped) {
          setError(e);
          if (e instanceof ApiError && [400, 401, 403].includes(e.status))
            setTicket(null);
        }
      } finally {
        checking = false;
      }
    };
    const timer = setInterval(() => void check(), 2500);
    const listener = AppState.addEventListener("change", (state) => {
      if (state === "active") void check();
    });
    void check();
    return () => {
      stopped = true;
      clearInterval(timer);
      listener.remove();
    };
  }, [ticket]);
  return (
    <Screen back>
      <Txt kind="display">
        {t(
          provider === "google"
            ? "googleContinue"
            : ticket
              ? "checkInbox"
              : "emailTitle",
        )}
      </Txt>
      {provider === "email" && !ticket && (
        <Field
          label={t("email")}
          value={email}
          onChangeText={setEmail}
          keyboardType="email-address"
          autoCapitalize="none"
          autoComplete="email"
        />
      )}
      <Txt muted>
        {t(
          ticket
            ? provider === "google"
              ? "googleLinkWaiting"
              : "emailLinkWaiting"
            : provider === "google"
              ? "googleLinkWaiting"
              : "emailLinkIntro",
        )}
      </Txt>
      <ErrorNotice error={error} />
      {ticket ? (
        <View style={{ gap: dsSpace[3] }}>
          {ticket.url && (
            <Button
              secondary
              label={t("reopenSignIn")}
              onPress={() => void Linking.openURL(ticket.url!).catch(setError)}
            />
          )}
          <Button
            secondary
            label={t("cancel")}
            onPress={() => {
              void cancelBrowserSignIn(ticket);
              current.current = null;
              setTicket(null);
              setError(undefined);
            }}
          />
        </View>
      ) : (
        <Button
          label={t(provider === "google" ? "googleContinue" : "sendSignInLink")}
          loading={busy}
          disabled={
            provider === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
          }
          onPress={() => void start()}
        />
      )}
      <Txt kind="caption" muted>
        {t("privateSignInHint")}
      </Txt>
    </Screen>
  );
}
