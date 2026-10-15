import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { buildLocalApp } from "../local-api/app";
import { Store } from "../local-api/store";
import { deleteAccount } from "../local-api/account";
import { fixture } from "../mock-api/fixtures";
test("local export excludes credentials; deletion clears account and caches but preserves spending ledger", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "account-tools-")),
    dbPath = path.join(dir, "state.sqlite");
  const demoTenant = createHash("sha256")
    .update("demo@example.com")
    .digest("hex");
  const seed = await Store.open(dbPath);
  const p = fixture("profile.1.en");
  await seed.runAsAsync(demoTenant, async () => {
    await seed.put("profile:" + p.profile_id, p);
    await seed.put("raw:" + p.profile_id, { private_chart: "test" });
  });
  await seed.put("access:secret", { secret: "never-export" });
  await seed.put("idem:test", { secret: "never-export" });
  await seed.close();
  fs.mkdirSync(path.join(dir, "map-products"));
  fs.writeFileSync(path.join(dir, "map-products", "chart.json"), "test");
  fs.writeFileSync(path.join(dir, "ai-budget.sqlite"), "preserve");
  const app = await buildLocalApp({
    dbPath,
    sectionRunner: async () => ({}),
  });
  try {
    assert.equal(
      (await app.inject({ method: "POST", url: "/v1/me/export" })).statusCode,
      401,
    );
    const login = async () =>
      (
        await app.inject({
          method: "POST",
          url: "/v1/auth/email/verify",
          payload: { email: "demo@example.com", code: "000000" },
        })
      ).json();
    const session = await login(),
      headers = { authorization: `Bearer ${session.access_token}` };
    const exported = await app.inject({
      method: "POST",
      url: "/v1/me/export",
      headers,
    });
    assert.equal(exported.statusCode, 202, exported.body);
    assert.equal(exported.json().format, "astrology-local-export-v1");
    assert.equal(exported.json().profiles.length, 1);
    assert.ok(!exported.body.includes("never-export"));
    assert.ok(!exported.body.includes(session.access_token));
    assert.equal(
      (await app.inject({ method: "DELETE", url: "/v1/me", headers }))
        .statusCode,
      202,
    );
    assert.deepEqual(
      (await app.inject({ url: "/v1/profiles", headers })).json(),
      [],
    );
    assert.equal(fs.existsSync(path.join(dir, "map-products")), false);
    assert.equal(
      fs.readFileSync(path.join(dir, "ai-budget.sqlite"), "utf8"),
      "preserve",
    );
    const fresh = await login();
    assert.equal(fresh.me.user_id, session.me.user_id);
    assert.deepEqual(
      (
        await app.inject({
          url: "/v1/profiles",
          headers: { authorization: `Bearer ${fresh.access_token}` },
        })
      ).json(),
      [],
    );
  } finally {
    await app.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("account deletion waits for running work and leaves records intact", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "account-busy-"));
  const store = await Store.open(path.join(dir, "state.sqlite"));
  try {
    await store.put("me", { user_id: "test" });
    await store.put("job:pending", { status: "running" });
    await assert.rejects(deleteAccount(store, path.join(dir, "state.sqlite")), {
      statusCode: 409,
    });
    assert.deepEqual(await store.get("me"), { user_id: "test" });
  } finally {
    await store.close();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
