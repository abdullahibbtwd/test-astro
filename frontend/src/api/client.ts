import { ApiError, NetworkError } from "./errors";
export { ApiError, NetworkError } from "./errors";
import type { Problem } from "../../contracts/spec-types";
import { useCapabilities } from "../lib/capabilities";
import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type { Session, Me } from "../../contracts/spec-types";
import type { Session as SupabaseSession } from "@supabase/supabase-js";
import { validate } from "./zod";
import { tokenStorage, privateStorage, durableStorage } from "../lib/storage";
import { useApp, resetLocalState } from "../lib/state";
import {
  isSupabaseAuth,
  refreshSupabaseSession,
  getSupabaseSession,
  signOutSupabase,
} from "../lib/supabase";
export const apiBase =
  process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:4010/v1";
let session: Session | null = null;
let refreshing: Promise<boolean> | null = null;
/** Temporary Bearer while bootstrapping /me after Supabase OTP (before Session exists). */
let bootstrapToken: string | null = null;
export let mockToday: string | undefined;
export async function setSession(value: Session | null): Promise<Session | null> {
  session = value;
  if (value) {
    const { hasGuestReading, claimGuestReading } = await import("../lib/guest-onboarding");
    if (hasGuestReading()) {
      useApp.getState().update({ guestClaimPending: true });
      try {
        const claimed = await claimGuestReading();
        if (claimed) value = { ...value, me: claimed.me, is_new_user: false };
      } catch {
        // Sign-in succeeds; the result screen offers a safe claim retry.
      }
    }
    session = value;
    await tokenStorage.set(value);
  }
  else {
    useApp.setState({ signedIn: false, me: null });
    await tokenStorage.clear();
    if (isSupabaseAuth()) await signOutSupabase();
    const { queryClient } = await import("./query");
    await queryClient.cancelQueries();
    queryClient.clear();
    const notifications = await import("expo-notifications");
    await notifications.cancelAllScheduledNotificationsAsync();
    privateStorage.clear();
    resetLocalState();
  }
  privateStorage.setItem("api-base", apiBase);
  await durableStorage.setItem("api-base", apiBase);
  useApp.getState().update({ signedIn: !!value, me: value?.me ?? null });
  return session;
}
function sessionFromSupabase(supa: SupabaseSession, me: Me): Session {
  const expiresAt = supa.expires_at
    ? new Date(supa.expires_at * 1000).toISOString()
    : new Date(Date.now() + 3600_000).toISOString();
  return {
    access_token: supa.access_token,
    refresh_token: supa.refresh_token ?? "",
    access_expires_at: expiresAt,
    is_new_user: !me.self_profile_id,
    me,
  };
}
/** After Supabase OTP/verify: Bearer = access token, load /me, persist Session. */
export async function adoptSupabaseSession(
  supa: SupabaseSession,
): Promise<Session> {
  bootstrapToken = supa.access_token;
  try {
    const me = await request<Me>("GET", "/me", "Me", undefined, false);
    const value = sessionFromSupabase(supa, me);
    return (await setSession(value)) ?? value;
  } finally {
    bootstrapToken = null;
  }
}
/** Where to go after sign-in (uses post-claim app state, not a stale Session). */
export function routeAfterSignIn(): string {
  const app = useApp.getState();
  if (app.guestClaimPending) return "/(auth)/core";
  if (app.onboardingUnlockProfileId) return "/(auth)/unlocked";
  const self = app.me?.self_profile_id;
  if (
    self &&
    app.draft.profileId === self &&
    app.draft.step &&
    app.draft.step !== "complete"
  )
    return `/(onboarding)/${app.draft.step}`;
  if (self) return "/(tabs)";
  return "/(onboarding)/consent";
}
export async function restoreSession() {
  // api-base must be durable: on iOS privateStorage is memory-only, so a reload
  // used to always look like an API switch and call setSession(null) → signOut.
  const previousApi = await durableStorage.getItem("api-base");
  if (previousApi != null && previousApi !== apiBase) await setSession(null);
  privateStorage.setItem("api-base", apiBase);
  await durableStorage.setItem("api-base", apiBase);
  if (isSupabaseAuth()) {
    const supa = await getSupabaseSession();
    if (supa) {
      try {
        await adoptSupabaseSession(supa);
        return;
      } catch {
        await setSession(null);
        return;
      }
    }
  }
  const raw = await tokenStorage.get();
  if (raw) {
    try {
      session = JSON.parse(raw);
      await setSession(session);
    } catch {
      await tokenStorage.clear();
    }
  }
}
export async function refreshSession() {
  if (!refreshing)
    refreshing = (async () => {
      if (!session && !bootstrapToken) return false;
      try {
        if (isSupabaseAuth()) {
          const next = await refreshSupabaseSession();
          if (!next) {
            await setSession(null);
            return false;
          }
          if (session) {
            const updated = sessionFromSupabase(next, session.me);
            session = updated;
            await tokenStorage.set(updated);
            return true;
          }
          await adoptSupabaseSession(next);
          return true;
        }
        if (!session) return false;
        const response = await fetch(`${apiBase}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: session.refresh_token }),
        });
        if (!response.ok) {
          await setSession(null);
          return false;
        }
        await setSession(validate<Session>("Session", await response.json()));
        return true;
      } catch {
        return false;
      }
    })().finally(() => {
      refreshing = null;
    });
  return refreshing;
}
export const client = createClient<paths>({ baseUrl: apiBase });
client.use({
  onRequest({ request }) {
    const token = bootstrapToken ?? session?.access_token;
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
  },
  onResponse({ response }) {
    mockToday = response.headers.get("X-Mock-Today") ?? mockToday;
  },
});
// Transport stays centralized; screens only use resource hooks.
export async function request<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  schema?: string,
  body?: unknown,
  retry = true,
  idempotencyKey?: string,
): Promise<T> {
  const url = new URL(`${apiBase}${path}`);
  url.searchParams.set("lang", useApp.getState().language);
  const response = await client
    .request(
      // Runtime contract validation covers this dynamic openapi-fetch boundary.
      method as never,
      // Path is selected at runtime and validated by the response contract.
      path.split("?")[0] as never,
      {
        params: { query: Object.fromEntries(url.searchParams) },
        body,
        headers: {
          ...(body ? { "Content-Type": "application/json" } : {}),
          ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
        },
        // openapi-fetch cannot infer options for the runtime-selected method/path.
      } as never,
    )
    .catch((error: unknown) => {
      if (error instanceof TypeError) throw new NetworkError();
      throw error;
    });
  if (response.response.status === 401 && retry && !path.startsWith("/auth/")) {
    if (await refreshSession())
      return request(method, path, schema, body, false, idempotencyKey);
    await setSession(null);
  }
  if (response.error || !response.response.ok) {
    if (response.response.status === 404) {
      if (path.split("?")[0] === "/ask/threads")
        useCapabilities.getState().mark("askAstrology");
      if (path.includes("/solar-return"))
        useCapabilities.getState().mark("solarReturn");
      if (path.includes("/chart/elements"))
        useCapabilities.getState().mark("elementNotes");
    }
    const error = response.error as Problem | undefined;
    throw new ApiError(
      response.response.status,
      error?.code ?? "upstream_unavailable",
      Number(response.response.headers.get("Retry-After") ?? 0),
      error,
    );
  }
  const data: unknown = response.data;
  if (
    data &&
    typeof data === "object" &&
    "status" in data &&
    data.status === "absent" &&
    "absence" in data
  ) {
    const absence = validate<{ status: "absent"; absence: Problem["absence"] }>(
      "GenerationAbsent",
      data,
    );
    throw new ApiError(200, "absent", 0, {
      type: "about:blank",
      title: "Reading unavailable",
      status: 200,
      code: "absent",
      absence: absence.absence,
    });
  }
  if (schema?.endsWith("[]") && Array.isArray(data))
    return data.map((value) => validate(schema.slice(0, -2), value)) as T;
  return schema && data !== undefined ? validate<T>(schema, data) : (data as T);
}
export function refreshToken() {
  return session?.refresh_token ?? "";
}

export async function updateSessionMe(me: Me) {
  if (session) {
    session = { ...session, me };
    await tokenStorage.set(session);
  }
  useApp.getState().update({ me, theme: me.theme });
}

export function accessToken() {
  return session?.access_token ?? "";
}
