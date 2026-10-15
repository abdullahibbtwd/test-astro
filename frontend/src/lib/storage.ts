import * as SecureStore from "expo-secure-store";
import * as Crypto from "expo-crypto";
import { Platform } from "react-native";
import { createMMKV, type MMKV } from "react-native-mmkv";

const memory = new Map<string, string>();
let storage: MMKV | undefined;

/** In-memory KV on iOS until MMKV/NitroModules is correctly linked in the iOS binary. Android keeps encrypted MMKV. */
export async function initStorage() {
  if (Platform.OS === "ios") return;
  let key = await SecureStore.getItemAsync("cache-key");
  if (!key) {
    key = Crypto.randomUUID().replace(/-/g, "");
    await SecureStore.setItemAsync("cache-key", key);
  }
  storage = createMMKV({ id: "astrology-private", encryptionKey: key });
}

export const privateStorage = {
  getItem: (key: string) =>
    Platform.OS === "ios"
      ? (memory.get(key) ?? null)
      : (storage?.getString(key) ?? null),
  setItem: (key: string, value: string) => {
    if (Platform.OS === "ios") {
      memory.set(key, value);
      return;
    }
    storage!.set(key, value);
  },
  removeItem: (key: string) => {
    if (Platform.OS === "ios") {
      memory.delete(key);
      return;
    }
    storage!.remove(key);
  },
  clear: () => {
    if (Platform.OS === "ios") {
      memory.clear();
      return;
    }
    storage!.clearAll();
  },
};

export const tokenStorage = {
  get: () => SecureStore.getItemAsync("session"),
  set: (session: unknown) =>
    SecureStore.setItemAsync("session", JSON.stringify(session)),
  clear: () => SecureStore.deleteItemAsync("session"),
};
