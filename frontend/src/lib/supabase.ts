import { createClient, type Session as SupabaseSession } from "@supabase/supabase-js";
import { AppState, type NativeEventSubscription } from "react-native";
import { ApiError, NetworkError } from "../api/errors";
import { durableStorage } from "./storage";

const url = process.env.EXPO_PUBLIC_SUPABASE_URL ?? "";
const publishableKey = process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "";

export const supabaseConfigured =
  /^https:\/\/[a-z]{20}\.supabase\.co\/?$/.test(url) &&
  /^sb_publishable_[A-Za-z0-9_-]+$/.test(publishableKey);

export const supabase = supabaseConfigured
  ? createClient(url.replace(/\/$/, ""), publishableKey, {
      auth: {
        // File-backed storage (not SecureStore): persists across restarts on
        // unsigned iOS builds and avoids SecureStore's 2048-byte limit.
        storage: durableStorage,
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: false,
      },
    })
  : null;

/** Keep token refresh alive when the app returns from background (RN requirement). */
export function bindSupabaseAuthLifecycle(): () => void {
  if (!supabase) return () => {};
  const onChange = (state: string) => {
    if (state === "active") void supabase.auth.startAutoRefresh();
    else void supabase.auth.stopAutoRefresh();
  };
  if (AppState.currentState === "active") onChange("active");
  const sub: NativeEventSubscription = AppState.addEventListener(
    "change",
    onChange,
  );
  return () => sub.remove();
}

export function isSupabaseAuth() {
  // Prefer explicit mode; if unset, use Supabase whenever keys are configured
  // so release builds never fall back to the email magic-link UI.
  const mode = process.env.EXPO_PUBLIC_AUTH_MODE;
  if (mode === "demo") return false;
  if (mode === "supabase") return supabaseConfigured;
  return supabaseConfigured;
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
