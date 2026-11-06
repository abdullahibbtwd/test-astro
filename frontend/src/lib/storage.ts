import * as SecureStore from "expo-secure-store";
import * as Crypto from "expo-crypto";
import { Platform } from "react-native";
import { File, Paths } from "expo-file-system";
import { createMMKV, type MMKV } from "react-native-mmkv";
import { secureGet, secureRemove, secureSet } from "./secure-kv";

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
 * Non-secret durable prefs (api-base, me shell). Tokens use SecureStore via
 * tokenStorage / secure-kv (chunked past the 2048-byte item limit).
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
const ACCESS_KEY = "session-access";
const REFRESH_KEY = "session-refresh";

type TokenSession = {
  access_token?: string;
  refresh_token?: string;
  [k: string]: unknown;
};

export const tokenStorage = {
  get: async (): Promise<string | null> => {
    const shellRaw = await durableStorage.getItem(SESSION_KEY);
    if (!shellRaw) return null;
    try {
      const shell = JSON.parse(shellRaw) as TokenSession;
      // Migrate legacy plaintext session files that still held tokens.
      if (shell.access_token) {
        await secureSet(ACCESS_KEY, shell.access_token);
        if (shell.refresh_token)
          await secureSet(REFRESH_KEY, shell.refresh_token);
        const { access_token: _a, refresh_token: _r, ...rest } = shell;
        await durableStorage.setItem(SESSION_KEY, JSON.stringify(rest));
        return JSON.stringify(shell);
      }
      const access_token = await secureGet(ACCESS_KEY);
      if (!access_token) return null;
      const refresh_token = (await secureGet(REFRESH_KEY)) ?? "";
      return JSON.stringify({ ...shell, access_token, refresh_token });
    } catch {
      return null;
    }
  },
  set: async (session: unknown): Promise<void> => {
    const value = session as TokenSession;
    const access = String(value.access_token ?? "");
    const refresh = String(value.refresh_token ?? "");
    if (access) await secureSet(ACCESS_KEY, access);
    else await secureRemove(ACCESS_KEY);
    if (refresh) await secureSet(REFRESH_KEY, refresh);
    else await secureRemove(REFRESH_KEY);
    const { access_token: _a, refresh_token: _r, ...rest } = value;
    await durableStorage.setItem(SESSION_KEY, JSON.stringify(rest));
  },
  clear: async (): Promise<void> => {
    await durableStorage.removeItem(SESSION_KEY);
    await secureRemove(ACCESS_KEY);
    await secureRemove(REFRESH_KEY);
  },
};
