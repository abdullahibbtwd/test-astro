/**
 * Chunked SecureStore for values that may exceed the 2048-byte item limit
 * (Supabase JWTs / session JSON). Never logs values.
 */
import * as SecureStore from "expo-secure-store";

const CHUNK = 1800;

export async function secureGet(key: string): Promise<string | null> {
  const nRaw = await SecureStore.getItemAsync(`${key}:n`);
  if (nRaw == null) {
    // Legacy single-slot value
    return SecureStore.getItemAsync(key);
  }
  const n = Number(nRaw);
  if (!Number.isFinite(n) || n < 1 || n > 32) return null;
  let out = "";
  for (let i = 0; i < n; i++) {
    const part = await SecureStore.getItemAsync(`${key}:${i}`);
    if (part == null) return null;
    out += part;
  }
  return out;
}

export async function secureSet(key: string, value: string): Promise<void> {
  const prev = await SecureStore.getItemAsync(`${key}:n`);
  const prevN = prev ? Number(prev) : 0;
  const chunks = Math.max(1, Math.ceil(value.length / CHUNK));
  await SecureStore.setItemAsync(`${key}:n`, String(chunks));
  for (let i = 0; i < chunks; i++) {
    await SecureStore.setItemAsync(
      `${key}:${i}`,
      value.slice(i * CHUNK, (i + 1) * CHUNK),
    );
  }
  // Drop legacy single-slot and any leftover higher chunks.
  await SecureStore.deleteItemAsync(key).catch(() => undefined);
  for (let i = chunks; i < prevN; i++) {
    await SecureStore.deleteItemAsync(`${key}:${i}`).catch(() => undefined);
  }
}

export async function secureRemove(key: string): Promise<void> {
  const prev = await SecureStore.getItemAsync(`${key}:n`);
  const prevN = prev ? Number(prev) : 0;
  await SecureStore.deleteItemAsync(`${key}:n`).catch(() => undefined);
  await SecureStore.deleteItemAsync(key).catch(() => undefined);
  for (let i = 0; i < Math.max(prevN, 1); i++) {
    await SecureStore.deleteItemAsync(`${key}:${i}`).catch(() => undefined);
  }
}

/** AsyncStorage-shaped adapter for Supabase auth (chunked SecureStore). */
export const secureKvAdapter = {
  getItem: (key: string) => secureGet(key),
  setItem: (key: string, value: string) => secureSet(key, value),
  removeItem: (key: string) => secureRemove(key),
};
