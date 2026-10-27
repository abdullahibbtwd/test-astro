import * as SecureStore from "expo-secure-store";
import * as Crypto from "expo-crypto";
import { Platform } from "react-native";
import { File, Paths } from "expo-file-system";
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

function durableFile(key: string) {
  const safe = encodeURIComponent(key).replace(/%/g, "_");
  return new File(Paths.document, `kv-${safe}.json`);
}

/**
 * Survives app restarts without Keychain entitlements (needed on unsigned iOS
 * Simulator builds) and without SecureStore's 2048-byte value limit (Supabase
 * session JWTs often exceed that).
 */
export const durableStorage = {
  getItem: async (key: string): Promise<string | null> => {
    try {
      const file = durableFile(key);
      if (file.exists) return await file.text();
    } catch {
      /* fall through */
    }
    return memory.get(key) ?? null;
  },
  setItem: async (key: string, value: string): Promise<void> => {
    memory.set(key, value);
    try {
      durableFile(key).write(value);
    } catch {
      /* memory already holds the value for this process */
    }
  },
  removeItem: async (key: string): Promise<void> => {
    memory.delete(key);
    try {
      const file = durableFile(key);
      if (file.exists) file.delete();
    } catch {
      /* ignore */
    }
  },
};

const SESSION_KEY = "session";

export const tokenStorage = {
  get: () => durableStorage.getItem(SESSION_KEY),
  set: (session: unknown) =>
    durableStorage.setItem(SESSION_KEY, JSON.stringify(session)),
  clear: () => durableStorage.removeItem(SESSION_KEY),
};
