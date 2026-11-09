/**
 * Upgrade path: legacy durable session JSON that embedded tokens must migrate
 * into SecureStore (or clear cleanly if tokens cannot be recovered).
 */
import test from "node:test";
import assert from "node:assert/strict";

const mem = new Map<string, string>();

const mockSecure = {
  async getItemAsync(key: string) {
    return mem.has(`sec:${key}`) ? mem.get(`sec:${key}`)! : null;
  },
  async setItemAsync(key: string, value: string) {
    mem.set(`sec:${key}`, value);
  },
  async deleteItemAsync(key: string) {
    mem.delete(`sec:${key}`);
  },
};

const durable = new Map<string, string>();

/** Mirrors tokenStorage migration logic without RN/Expo natives. */
async function migrateGet(): Promise<string | null> {
  const shellRaw = durable.get("session") ?? null;
  if (!shellRaw) return null;
  const shell = JSON.parse(shellRaw) as {
    access_token?: string;
    refresh_token?: string;
    me?: { user_id: string };
  };
  if (shell.access_token) {
    await mockSecure.setItemAsync("session-access:n", "1");
    await mockSecure.setItemAsync("session-access:0", shell.access_token);
    if (shell.refresh_token) {
      await mockSecure.setItemAsync("session-refresh:n", "1");
      await mockSecure.setItemAsync("session-refresh:0", shell.refresh_token);
    }
    const { access_token: _a, refresh_token: _r, ...rest } = shell;
    durable.set("session", JSON.stringify(rest));
    return JSON.stringify(shell);
  }
  const n = await mockSecure.getItemAsync("session-access:n");
  if (!n) return null;
  const access = await mockSecure.getItemAsync("session-access:0");
  if (!access) return null;
  const refresh =
    (await mockSecure.getItemAsync("session-refresh:0")) ?? "";
  return JSON.stringify({ ...shell, access_token: access, refresh_token: refresh });
}

test("legacy plaintext session migrates tokens out of durable file", async () => {
  mem.clear();
  durable.clear();
  durable.set(
    "session",
    JSON.stringify({
      access_token: "legacy-access",
      refresh_token: "legacy-refresh",
      me: { user_id: "u1" },
    }),
  );
  const raw = await migrateGet();
  assert.ok(raw);
  const parsed = JSON.parse(raw!);
  assert.equal(parsed.access_token, "legacy-access");
  assert.equal(parsed.refresh_token, "legacy-refresh");
  // Durable shell no longer holds tokens
  const shell = JSON.parse(durable.get("session")!);
  assert.equal(shell.access_token, undefined);
  assert.equal(shell.refresh_token, undefined);
  assert.equal(shell.me.user_id, "u1");
  assert.equal(await mockSecure.getItemAsync("session-access:0"), "legacy-access");
});

test("corrupt durable session without SecureStore tokens signs out cleanly", async () => {
  mem.clear();
  durable.clear();
  durable.set("session", JSON.stringify({ me: { user_id: "u1" } }));
  const raw = await migrateGet();
  assert.equal(raw, null);
});
