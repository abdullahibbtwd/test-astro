import * as SecureStore from "expo-secure-store";
import * as Crypto from "expo-crypto";
import {
  guestStateSchema,
  type GuestBirth,
} from "../../contracts/guest-onboarding";
import {
  apiBase,
  ApiError,
  request,
  updateSessionMe,
  refreshSession,
} from "../api/client";
import { privateStorage } from "./storage";
import { useApp } from "./state";
import { validate } from "../api/zod";
import { queryClient } from "../api/query";
import type { BirthProfile, Me } from "../../contracts/spec-types";
const key = "onboarding-guest";
export const hasGuestReading = () =>
  privateStorage.getItem("guest-preview-active") === "1";
async function guestRequest(
  method: "POST" | "GET" | "DELETE",
  body?: GuestBirth,
) {
  let token = await SecureStore.getItemAsync(key);
  if (!token && method === "POST") {
    token = (Crypto.randomUUID() + Crypto.randomUUID()).replaceAll("-", "");
    await SecureStore.setItemAsync(key, token);
  }
  if (!token) throw new ApiError(401, "unauthorized");
  const response = await fetch(
    `${apiBase}/onboarding/reading?lang=${useApp.getState().language}`,
    {
      method,
      headers: {
        "X-Guest-Token": token,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    },
  );
  if (!response.ok)
    throw new ApiError(
      response.status,
      response.status === 429 ? "rate_limited" : "upstream_unavailable",
    );
  if (response.status === 204) return;
  return guestStateSchema.parse(await response.json());
}
export async function startGuestReading(body: GuestBirth) {
  const input = JSON.stringify([
    body.birth_date,
    body.birth_time,
    body.birth_place_id,
  ]);
  const previous = privateStorage.getItem("guest-preview-input");
  if (hasGuestReading() && previous && previous !== input)
    await clearGuestReading();
  privateStorage.setItem("guest-preview-input", input);
  privateStorage.setItem("guest-preview-active", "1");
  return guestRequest("POST", body);
}
export async function getGuestReading() {
  return guestRequest("GET");
}
export async function clearGuestReading() {
  if (hasGuestReading()) {
    try {
      await guestRequest("DELETE");
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
    }
  }
  await SecureStore.deleteItemAsync(key);
  privateStorage.removeItem("guest-preview-active");
  privateStorage.removeItem("guest-preview-input");
  queryClient.removeQueries({ queryKey: ["guest-core"] });
  useApp.getState().update({ guestClaimPending: false });
}
export async function claimGuestReading() {
  const token = await SecureStore.getItemAsync(key);
  if (!hasGuestReading()) return null;
  if (!token) {
    await clearGuestReading();
    return null;
  }
  const result = await request<{ profile: unknown; me: unknown }>(
    "POST",
    "/me/onboarding/claim",
    undefined,
    { guest_token: token },
    false,
  );
  const profile = validate<BirthProfile>("BirthProfile", result.profile);
  const me = validate<Me>("Me", result.me);
  await SecureStore.deleteItemAsync(key);
  privateStorage.removeItem("guest-preview-active");
  privateStorage.removeItem("guest-preview-input");
  // Birth is already claimed — finish the same account setup as sign-up-first
  // (consent + name + current place…), not a shortcut into the app.
  useApp.getState().editDraft({
    step: "consent",
    profileId: profile.profile_id,
    name: "",
    date: profile.birth.date,
    time: profile.birth.time,
    place: profile.birth.place,
    consent: false,
  });
  useApp.getState().update({
    activeProfileId: profile.profile_id,
    onboardingUnlockProfileId: null,
    guestClaimPending: false,
  });
  queryClient.removeQueries({ queryKey: ["guest-core"] });
  return { profile, me };
}
export async function retryGuestClaim() {
  let result;
  try {
    result = await claimGuestReading();
  } catch (error) {
    if (
      !(error instanceof ApiError) ||
      error.status !== 401 ||
      !(await refreshSession())
    )
      throw error;
    result = await claimGuestReading();
  }
  if (result) await updateSessionMe(result.me);
  return result;
}
