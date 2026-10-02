import { useCapabilities } from "../lib/capabilities";
import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type { Session, Me } from "../../contracts/spec-types";
import { validate } from "./zod";
import { tokenStorage, privateStorage } from "../lib/storage";
import { useApp, resetLocalState } from "../lib/state";
export const apiBase =
  process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:4010/v1";
let session: Session | null = null;
let refreshing: Promise<boolean> | null = null;
export let mockToday: string | undefined;
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public retryAfter = 0,
  ) {
    super(code);
  }
}
export async function setSession(value: Session | null) {
  session = value;
  if (value) await tokenStorage.set(value);
  else {
    useApp.setState({ signedIn: false, me: null });
    await tokenStorage.clear();
    const { queryClient } = await import("./query");
    await queryClient.cancelQueries();
    queryClient.clear();
    const notifications = await import("expo-notifications");
    await notifications.cancelAllScheduledNotificationsAsync();
    privateStorage.clear();
    resetLocalState();
  }
  privateStorage.setItem("api-base", apiBase);
  useApp.getState().update({ signedIn: !!value, me: value?.me ?? null });
}
export async function restoreSession() {
  const previousApi = privateStorage.getItem("api-base");
  if (previousApi !== apiBase) await setSession(null);
  privateStorage.setItem("api-base", apiBase);
  const raw = await tokenStorage.get();
  if (raw) {
    try {
      session = JSON.parse(raw);
      useApp.getState().update({ signedIn: true, me: session!.me });
    } catch {
      await tokenStorage.clear();
    }
  }
}
export async function refreshSession() {
  if (!refreshing)
    refreshing = (async () => {
      if (!session) return false;
      try {
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
    if (session)
      request.headers.set("Authorization", `Bearer ${session.access_token}`);
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
  const response = await client.request(
    method as never,
    path.split("?")[0] as never,
    {
      params: { query: Object.fromEntries(url.searchParams) },
      body,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
      },
    } as never,
  );
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
    const error = response.error as { code?: string } | undefined;
    throw new ApiError(
      response.response.status,
      error?.code ?? "upstream_unavailable",
      Number(response.response.headers.get("Retry-After") ?? 0),
    );
  }
  const data: unknown = response.data;
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
