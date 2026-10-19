import { createClient, type Session as SupabaseSession } from "@supabase/supabase-js";
import * as SecureStore from "expo-secure-store";
import { ApiError, NetworkError } from "../api/errors";

const url = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
const publishableKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";

/** SecureStore adapter so Supabase persists/refreshes the session locally. */
const secureStorage = {
  getItem: (key: string) => SecureStore.getItemAsync(key),
  setItem: (key: string, value: string) => SecureStore.setItemAsync(key, value),
  removeItem: (key: string) => SecureStore.deleteItemAsync(key),
};

export const supabaseConfigured =
  /^https:\/\/[a-z]{20}\.supabase\.co\/?$/.test(url) &&
  /^sb_publishable_[A-Za-z0-9_-]+$/.test(publishableKey);

export const supabase = supabaseConfigured
  ? createClient(url.replace(/\/$/, ""), publishableKey, {
      auth: {
        storage: secureStorage,
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
      },
    })
  : null;

export function isSupabaseAuth() {
  return (
    process.env.EXPO_PUBLIC_AUTH_MODE === "supabase" && supabaseConfigured
  );
}

/** Dev-only hint for email + 000000; off unless explicitly enabled. */
export function showDemoLoginHint() {
  return (
    __DEV__ &&
    process.env.EXPO_PUBLIC_DEMO_LOGIN_HINT === "1" &&
    !isSupabaseAuth()
  );
}

function mapAuthError(error: { message?: string; status?: number } | null): never {
  const message = (error?.message ?? "").toLowerCase();
  const status = error?.status;
  if (status === 429 || message.includes("rate") || message.includes("too many"))
    throw new ApiError(429, "rate_limited");
  if (
    message.includes("expired") ||
    message.includes("invalid") ||
    message.includes("otp") ||
    message.includes("token") ||
    status === 401 ||
    status === 403
  )
    throw new ApiError(401, "unauthorized");
  throw new ApiError(503, "upstream_unavailable");
}

export async function signInWithEmailOtp(email: string) {
  if (!supabase) throw new ApiError(503, "upstream_unavailable");
  const normalized = email.trim().toLowerCase();
  try {
    const { error } = await supabase.auth.signInWithOtp({
      email: normalized,
      options: { shouldCreateUser: true },
    });
    if (error) mapAuthError(error);
  } catch (e) {
    if (e instanceof ApiError) throw e;
    if (e instanceof TypeError) throw new NetworkError();
    throw new NetworkError();
  }
  return normalized;
}

export async function verifyEmailOtp(email: string, token: string) {
  if (!supabase) throw new ApiError(503, "upstream_unavailable");
  try {
    const { data, error } = await supabase.auth.verifyOtp({
      email: email.trim().toLowerCase(),
      token,
      type: "email",
    });
    if (error) mapAuthError(error);
    if (!data.session) throw new ApiError(401, "unauthorized");
    return data.session;
  } catch (e) {
    if (e instanceof ApiError || e instanceof NetworkError) throw e;
    if (e instanceof TypeError) throw new NetworkError();
    throw new NetworkError();
  }
}

export async function refreshSupabaseSession(): Promise<SupabaseSession | null> {
  if (!supabase) return null;
  try {
    const { data, error } = await supabase.auth.refreshSession();
    if (error || !data.session) return null;
    return data.session;
  } catch {
    return null;
  }
}

export async function getSupabaseSession(): Promise<SupabaseSession | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session;
}

export async function signOutSupabase() {
  if (!supabase) return;
  await supabase.auth.signOut({ scope: "local" }).catch(() => {});
}
