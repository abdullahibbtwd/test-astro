import test from "node:test";
import { clearAuthMode, openStore, tempDataDir, wipeDemoTenant } from "./helpers";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createHash } from "node:crypto";
import { buildLocalApp } from "../api/app";
import { Store } from "../api/store";
import { deleteAccount } from "../api/account";
import { prisma } from "../api/db";
import { fixture } from "../mock/fixtures";
test("local export excludes credentials; deletion clears account and caches but preserves spending ledger", async () => {
  await wipeDemoTenant();
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "account-tools-")),
    dbPath = path.join(dir, "state.sqlite");
  const demoTenant = createHash("sha256")
    .update("demo@example.com")
    .digest("hex");
  const seed = await openStore();
  const { prisma } = await import("../api/db");
  await prisma().user.upsert({
    where: { id: demoTenant },
    create: { id: demoTenant, displayName: "demo" },
    update: {},
  });
  const p = fixture("profile.1.en");
  await seed.runAsAsync(demoTenant, async () => {
    await seed.put("profile:" + p.profile_id, p);
    await seed.put("raw:" + p.profile_id, { private_chart: "test" });
  });
  await seed.put("access:secret", { secret: "never-export" });
  await seed.put("idem:test", { secret: "never-export" });
  await seed.close();
  fs.mkdirSync(path.join(dir, "map-products", demoTenant), { recursive: true });
  fs.writeFileSync(
    path.join(dir, "map-products", demoTenant, "chart.json"),
    "test",
  );
  fs.mkdirSync(path.join(dir, "map-products", "other-user"), { recursive: true });
  fs.writeFileSync(
    path.join(dir, "map-products", "other-user", "chart.json"),
    "keep",
  );
  fs.writeFileSync(path.join(dir, "ai-budget.sqlite"), "preserve");
  await clearAuthMode();
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
    assert.equal(
      (await app.inject({ url: "/v1/profiles", headers })).statusCode,
      401,
    );
    assert.equal(
      fs.existsSync(path.join(dir, "map-products", demoTenant)),
      false,
    );
    assert.equal(
      fs.readFileSync(
        path.join(dir, "map-products", "other-user", "chart.json"),
        "utf8",
      ),
      "keep",
    );
    assert.equal(
      fs.readFileSync(path.join(dir, "ai-budget.sqlite"), "utf8"),
      "preserve",
    );
    const again = await app.inject({
      method: "POST",
      url: "/v1/auth/email/verify",
      payload: { email: "demo@example.com", code: "000000" },
    });
    assert.equal(again.statusCode, 403);
  } finally {
    await app.close();
    await clearAuthMode();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("account deletion waits for running work and leaves records intact", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "account-busy-"));
  const store = await openStore();
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

test("deleting one account removes only that user's map cache", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "account-map-cache-"));
  const keep = "map-cache-keep-user";
  const drop = "map-cache-drop-user";
  const db = prisma();
  await db.user.upsert({
    where: { id: keep },
    create: { id: keep, displayName: "keep" },
    update: {},
  });
  await db.user.upsert({
    where: { id: drop },
    create: { id: drop, displayName: "drop" },
    update: {},
  });
  for (const id of [keep, drop]) {
    fs.mkdirSync(path.join(dir, "map-products", id), { recursive: true });
    fs.writeFileSync(path.join(dir, "map-products", id, "chart.json"), id);
  }
  fs.writeFileSync(path.join(dir, "map-products", "shared.json"), "shared");
  try {
    await deleteAccount(db, drop, dir);
    assert.equal(
      fs.existsSync(path.join(dir, "map-products", drop)),
      false,
    );
    assert.equal(
      fs.readFileSync(path.join(dir, "map-products", keep, "chart.json"), "utf8"),
      keep,
    );
    assert.equal(
      fs.readFileSync(path.join(dir, "map-products", "shared.json"), "utf8"),
      "shared",
    );
    assert.equal(fs.existsSync(path.join(dir, "map-products")), true);
  } finally {
    await db.deletedUser.deleteMany({ where: { id: { in: [keep, drop] } } });
    await db.user.deleteMany({ where: { id: { in: [keep, drop] } } });
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test("account export rebuilds a missing dossier through the real bridge", async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "account-export-"));
  const dbPath = path.join(dir, "state.sqlite");
  await clearAuthMode();
  const app = await buildLocalApp({ dbPath, allowPaid: false });
  try {
    const login = await app.inject({
      method: "POST",
      url: "/v1/auth/email/verify",
      payload: {
        email: `export-${Date.now()}@example.test`,
        code: "000000",
      },
    });
    assert.equal(login.statusCode, 200, login.body);
    const headers = {
      authorization: `Bearer ${login.json().access_token}`,
    };
    const places = await app.inject({
      url: "/v1/places/search?q=Istanbul&kind=birth&lang=en",
      headers,
    });
    assert.equal(places.statusCode, 200, places.body);
    const place = places.json()[0];
    const created = await app.inject({
      method: "POST",
      url: "/v1/profiles",
      headers: { ...headers, "idempotency-key": "export-real-bridge" },
      payload: {
        label: "Export",
        relation: "self",
        birth_date: "1991-04-04",
        birth_time: "04:04",
        birth_place_id: place.place_id,
      },
    });
    assert.equal(created.statusCode, 201, created.body);
    const profile = created.json();
    const outline = await app.inject({
      url: `/v1/profiles/${profile.profile_id}/natal-reading/outline`,
      headers,
    });
    assert.equal(outline.statusCode, 200, outline.body);
    const dossier = path.join(dir, "dossier", profile.chart_key);
    assert.equal(fs.existsSync(path.join(dossier, "manifest.json")), true);
    fs.rmSync(dossier, { recursive: true, force: true });
    const exported = await app.inject({
      method: "POST",
      url: "/v1/me/export",
      headers,
    });
    assert.equal(exported.statusCode, 202, exported.body);
    const body = exported.json();
    assert.equal(body.format, "astrology-local-export-v1");
    assert.equal(body.dossiers.length, 1);
    assert.equal(body.dossiers[0].manifest.chart_key, profile.chart_key);
    assert.ok(body.dossiers[0].grounded_principle_ids.length > 0);
    assert.equal(fs.existsSync(path.join(dossier, "manifest.json")), true);
    assert.ok(!exported.body.includes(login.json().access_token));
  } finally {
    await app.close();
    await clearAuthMode();
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
