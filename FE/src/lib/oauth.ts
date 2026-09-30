import {
  GoogleSignin,
  isSuccessResponse,
  statusCodes,
} from "@react-native-google-signin/google-signin";
import * as Apple from "expo-apple-authentication";
import { request, setSession } from "../api/client";
import type { Session } from "../../contracts/spec-types";
export class ProviderUnavailable extends Error {}
export async function providerSignIn(
  provider: "google" | "apple",
): Promise<Session | null> {
  try {
    let body: Record<string, string>;
    if (provider === "google") {
      const webClientId = process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID,
        iosClientId = process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID;
      if (!webClientId) throw new ProviderUnavailable();
      GoogleSignin.configure({
        webClientId,
        ...(iosClientId ? { iosClientId } : {}),
      });
      await GoogleSignin.hasPlayServices({
        showPlayServicesUpdateDialog: true,
      });
      const response = await GoogleSignin.signIn();
      if (!isSuccessResponse(response)) return null;
      if (!response.data.idToken) throw new Error("Missing identity token");
      body = { id_token: response.data.idToken };
    } else {
      if (!(await Apple.isAvailableAsync())) throw new ProviderUnavailable();
      const response = await Apple.signInAsync({
        requestedScopes: [
          Apple.AppleAuthenticationScope.FULL_NAME,
          Apple.AppleAuthenticationScope.EMAIL,
        ],
      });
      if (!response.identityToken || !response.authorizationCode)
        throw new Error("Missing identity token");
      const name = response.fullName
        ? Apple.formatFullName(response.fullName)
        : "";
      body = {
        identity_token: response.identityToken,
        authorization_code: response.authorizationCode,
        ...(name ? { full_name: name } : {}),
      };
    }
    const session = await request<Session>(
      "POST",
      `/auth/${provider}`,
      "Session",
      body,
    );
    await setSession(session);
    return session;
  } catch (e) {
    if (
      e &&
      typeof e === "object" &&
      "code" in e &&
      (e.code === statusCodes.SIGN_IN_CANCELLED ||
        e.code === "ERR_REQUEST_CANCELED")
    )
      return null;
    throw e;
  }
}
