import * as SecureStore from "expo-secure-store";
import * as Crypto from "expo-crypto";
import { createMMKV, type MMKV } from "react-native-mmkv";
let storage: MMKV;
export async function initStorage() {
  let key = await SecureStore.getItemAsync("cache-key");
  if (!key) {
    key = Crypto.randomUUID().replace(/-/g, "");
    await SecureStore.setItemAsync("cache-key", key);
  }
  storage = createMMKV({ id: "astrology-private", encryptionKey: key });
}
export const privateStorage = {
  getItem: (key: string) => storage?.getString(key) ?? null,
  setItem: (key: string, value: string) => storage.set(key, value),
  removeItem: (key: string) => {
    storage.remove(key);
  },
  clear: () => storage.clearAll(),
};
export const tokenStorage = {
  get: () => SecureStore.getItemAsync("session"),
  set: (session: unknown) =>
    SecureStore.setItemAsync("session", JSON.stringify(session)),
  clear: () => SecureStore.deleteItemAsync("session"),
};
