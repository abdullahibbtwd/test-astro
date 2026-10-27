import { buildLocalApp } from "../api/app";
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import Fastify from "fastify";
import { DEFAULT_TENANT } from "../api/store";
import { ProgressiveReadings } from "../api/progressive-readings";
import { registerGuestOnboarding } from "../api/guest-onboarding";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";
import {
  clearAuthMode,
  dataDbPath,
  openGuestScopedStore,
  openStore,
  tempDataDir,
} from "./helpers";

const OWNER = DEFAULT_TENANT;

async function waitReadingIdle(
  readings: ProgressiveReadings,
  chart?: string,
) {
  for (let i = 0; i < 200; i++) {
    try {
      readings.assertIdle(chart);
      return;
    } catch {
      await readings.close();
      await new Promise((resolve) => setImmediate(resolve));
    }
  }
  readings.assertIdle(chart);
}

async function setup() {
  const app = Fastify();
  const { store: account, guest } = await openGuestScopedStore();
  await account.runAsAsync(OWNER, async () => {
    await account.put("me", { ...fixture("me.en"), self_profile_id: null });
  });
  let time = Date.now(),
    generated = 0,
    calculated = 0;
  const tr = fixture("natal.1.tr"),
    en = fixture("natal.1.en"),
    base = fixture("profile.1.en");
  const plan: any = {
    order: ["core_identity"],
    movement: { core_identity: 1 },
    house: { core_identity: null },
    titles: { core_identity: { tr: "Kimlik", en: "Core identity" } },
    routed_ids: { core_identity: ["private"] },
  };
  const runner = async (data: any) => {
    if (data.op === "prepare")
      return {
        plan,
        titles: { tr: tr.title, en: en.title },
        parts: { tr: tr.parts, en: en.parts },
      };
    if (data.op === "section") {
      generated++;
      return {
        key: "core_identity",
        text_tr: "Private generated Turkish text",
        principle_ids: ["private"],
        usage: { secret: true },
      };
    }
    if (data.op === "translate")
      return { text_en: "Your core identity reading." };
    return {};
  };
  const readings = await ProgressiveReadings.create(guest, true, runner),
    accountReadings = await ProgressiveReadings.create(account, false, runner);
  registerGuestOnboarding(app, {
    enabled: true,
    guest,
    account,
    readings,
    accountReadings,
    now: () => time,
    authorize: async (r) => {
      if (r.headers.authorization !== "Bearer owner")
        throw Object.assign(new Error(), { statusCode: 401 });
      return DEFAULT_TENANT;
    },
    place: async () => base.birth.place,
    calculate: async (_birth, id) => {
      calculated++;
      return { raw: {}, chart: { ...fixture("chart.1"), profile_id: id } };
    },
  });
  const headers = { "x-guest-token": "a".repeat(64) };
  const payload = {
    birth_date: "1988-12-28",
    birth_time: "14:20",
    birth_place_id: base.birth.place.place_id,
    consent: true,
    lang: "en",
  };
  return {
    app,
    guest,
    account,
    readings,
    accountReadings,
    headers,
    payload,
    counts: () => ({ generated, calculated }),
    expire: () => {
      time += 86400_001;
    },
  };
}
test("guest capability exposes only core identity and sign-in claims it without regeneration", async () => {
  const s = await setup();
  try {
    assert.equal(
      (
        await s.app.inject({
          method: "POST",
          url: "/v1/onboarding/reading",
          headers: s.headers,
          payload: s.payload,
        })
      ).statusCode,
      202,
    );
    await s.readings.close();
    const ready = await s.app.inject({
      url: "/v1/onboarding/reading?lang=en",
      headers: s.headers,
    });
    assert.equal(ready.json().status, "ready");
    assert.equal(ready.json().section.text, "Your core identity reading.");
    assert.ok(
      !ready.body.includes("principle_ids") && !ready.body.includes("usage"),
    );
    assert.equal(
      (
        await s.app.inject({
          url: "/v1/onboarding/reading",
          headers: { "x-guest-token": "b".repeat(64) },
        })
      ).statusCode,
      401,
    );
    assert.equal(
      (
        await s.app.inject({
          method: "POST",
          url: "/v1/me/onboarding/claim",
          payload: { guest_token: s.headers["x-guest-token"] },
        })
      ).statusCode,
      401,
    );
    await waitReadingIdle(s.readings);
    const claimed = await s.app.inject({
      method: "POST",
      url: "/v1/me/onboarding/claim",
      headers: { authorization: "Bearer owner" },
      payload: { guest_token: s.headers["x-guest-token"] },
    });
    assert.equal(claimed.statusCode, 200, claimed.body);
    validate("BirthProfile", claimed.json().profile);
    assert.equal(
      claimed.json().me.self_profile_id,
      claimed.json().profile.profile_id,
    );
    assert.equal(
      (
        await s.app.inject({
          url: "/v1/onboarding/reading",
          headers: s.headers,
        })
      ).statusCode,
      401,
    );
    assert.equal(
      (
        await s.app.inject({
          method: "POST",
          url: "/v1/me/onboarding/claim",
          headers: { authorization: "Bearer owner" },
          payload: { guest_token: s.headers["x-guest-token"] },
        })
      ).statusCode,
      200,
    );
    assert.deepEqual(s.counts(), { generated: 1, calculated: 1 });
  } finally {
    await s.app.close();
    await s.account.close();
    await s.guest.close();
  }
});
test("guest creation is idempotent, validates dates, expires and limits new attempts", async () => {
  const s = await setup();
  try {
    const send = (headers = s.headers, payload = s.payload) =>
      s.app.inject({
        method: "POST",
        url: "/v1/onboarding/reading",
        headers,
        payload,
      });
    assert.equal(
      (await send(s.headers, { ...s.payload, birth_date: "2026-02-31" }))
        .statusCode,
      400,
    );
    assert.equal((await send()).statusCode, 202);
    await s.readings.close();
    assert.equal((await send()).statusCode, 202);
    assert.equal(
      (await send(s.headers, { ...s.payload, birth_time: "13:20" })).statusCode,
      409,
    );
    for (const ch of ["b", "c", "d", "e"]) {
      assert.equal(
        (await send({ "x-guest-token": ch.repeat(64) })).statusCode,
        202,
      );
      await s.readings.close();
    }
    assert.equal(
      (await send({ "x-guest-token": "f".repeat(64) })).statusCode,
      429,
    );
    s.expire();
    assert.equal(
      (
        await s.app.inject({
          url: "/v1/onboarding/reading",
          headers: s.headers,
        })
      ).statusCode,
      401,
    );
  } finally {
    await s.app.close();
    await s.account.close();
    await s.guest.close();
  }
});

test("claiming another birth chart preserves the existing account and saved reading", async () => {
  const s = await setup();
  try {
    const existing = fixture("profile.1.en");
    const self = { ...existing, chart_key: "existing-chart" };
    await s.account.runAsAsync(OWNER, async () => {
      await s.account.put("profile:" + self.profile_id, self);
      await s.account.put("me", {
        ...fixture("me.en"),
        self_profile_id: self.profile_id,
      });
    });
    await s.app.inject({
      method: "POST",
      url: "/v1/onboarding/reading",
      headers: s.headers,
      payload: s.payload,
    });
    await waitReadingIdle(s.readings);
    const response = await s.app.inject({
      method: "POST",
      url: "/v1/me/onboarding/claim",
      headers: { authorization: "Bearer owner" },
      payload: { guest_token: s.headers["x-guest-token"] },
    });
    assert.equal(response.statusCode, 200, response.body);
    assert.equal(response.json().me.self_profile_id, self.profile_id);
    assert.equal(response.json().profile.is_self, false);
    assert.equal(response.json().profile.relation, "other");
    assert.deepEqual(
      await s.account.runAsAsync(OWNER, () =>
        s.account.get("profile:" + self.profile_id),
      ),
      self,
    );
    assert.equal(
      (await s.account.runAsAsync(OWNER, () => s.account.list("profile:")))
        .length,
      2,
    );
    assert.equal((await s.guest.list("profile:")).length, 0);
  } finally {
    await s.app.close();
    await s.account.close();
    await s.guest.close();
  }
});

test("the connected API keeps guest access narrow and reuses core after account sign-in", async () => {
  let generated = 0;
  const tr = fixture("natal.1.tr"),
    en = fixture("natal.1.en");
  const core = tr.sections.find((s: any) => s.key === "core_identity");
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "guest-api-"));
  const dbPath = path.join(folder, "app.sqlite");
  const birthPlace = fixture("profile.1.en").birth.place;
  await clearAuthMode();
  const app = await buildLocalApp({
    dbPath,
    allowPaid: true,
    guestOnboarding: true,
    computeBirthChart: async (_birth, id) => ({
      raw: {},
      chart: { ...fixture("chart.1"), profile_id: id },
    }),
    sectionRunner: async (data) => {
      if (data.op === "prepare")
        return {
          plan: {
            order: ["core_identity"],
            movement: { core_identity: 1 },
            house: { core_identity: null },
            titles: { core_identity: { en: "Core identity", tr: core.title } },
            routed_ids: { core_identity: [] },
          },
          titles: { en: en.title, tr: tr.title },
          parts: { en: en.parts, tr: tr.parts },
        };
      if (data.op === "section") {
        generated++;
        return {
          key: "core_identity",
          text_tr: "Test core",
          principle_ids: [],
        };
      }
      if (data.op === "translate") return { text_en: "Test core English" };
      return {};
    },
  });
  try {
    const store = await openStore();
    await store.put(`place:en:${birthPlace.place_id}`, {
      ...birthPlace,
      kind: "city",
      population: 1000,
      source: "test",
    });
    await store.close();
    assert.equal((await app.inject({ url: "/v1/profiles" })).statusCode, 401);
    const guest = { "x-guest-token": "1".repeat(64) };
    const created = await app.inject({
      method: "POST",
      url: "/v1/onboarding/reading",
      headers: guest,
      payload: {
        birth_date: "1988-12-28",
        birth_time: "13:00",
        birth_place_id: birthPlace.place_id,
        consent: true,
        lang: "en",
      },
    });
    assert.equal(created.statusCode, 202, created.body);
    await new Promise((resolve) => setImmediate(resolve));
    const ready = await app.inject({
      url: "/v1/onboarding/reading?lang=en",
      headers: guest,
    });
    assert.equal(ready.json().status, "ready", ready.body);
    const login = await app.inject({
      method: "POST",
      url: "/v1/auth/email/verify",
      payload: { email: "demo@example.com", code: "000000" },
    });
    assert.equal(login.statusCode, 200, login.body);
    const headers = { authorization: "Bearer " + login.json().access_token };
    const claim = await app.inject({
      method: "POST",
      url: "/v1/me/onboarding/claim",
      headers,
      payload: { guest_token: guest["x-guest-token"] },
    });
    assert.equal(claim.statusCode, 200, JSON.stringify(claim.json()));
    const base =
      "/v1/profiles/" + claim.json().profile.profile_id + "/natal-reading";
    const section = await app.inject({
      url: base + "/sections/core_identity?lang=en",
      headers,
    });
    assert.equal(section.json().text, "Test core English");
    const reading = await app.inject({ url: base + "?lang=en", headers });
    assert.equal(reading.statusCode, 200, reading.body);
    assert.equal(reading.json().sections[0].text, section.json().text);
    assert.equal(generated, 1);
  } finally {
    await app.close();
    await clearAuthMode();
    fs.rmSync(folder, { recursive: true, force: true });
  }
});
test("claiming a matching chart preserves its existing prose and progress", async () => {
  const s = await setup();
  try {
    await s.app.inject({
      method: "POST",
      url: "/v1/onboarding/reading",
      headers: s.headers,
      payload: s.payload,
    });
    await s.readings.close();
    const guest = (await s.guest.list<any>("profile:"))[0];
    const profile = { ...guest, profile_id: "existing-profile" };
    await s.account.runAsAsync(OWNER, async () => {
      await s.account.put("profile:" + profile.profile_id, profile);
      await s.account.put("me", {
        ...fixture("me.en"),
        self_profile_id: profile.profile_id,
      });
      const progress = {
        chart_key: profile.chart_key,
        opened: ["core_identity", "sun_house"],
        furthest_index: 4,
      };
      await s.account.put("reading-progress:" + profile.profile_id, progress);
    });
    const key = `reading-section:${profile.chart_key}:core_identity`;
    await s.account.runAsAsync(OWNER, () =>
      s.account.put(key, {
      key: "core_identity",
      text_tr: "Previously saved text",
      status: "ready",
      }),
    );
    await waitReadingIdle(s.readings);
    await waitReadingIdle(s.accountReadings, profile.chart_key);
    const claim = await s.app.inject({
      method: "POST",
      url: "/v1/me/onboarding/claim",
      headers: { authorization: "Bearer owner" },
      payload: { guest_token: s.headers["x-guest-token"] },
    });
    assert.equal(claim.statusCode, 200, JSON.stringify(claim.json()));
    assert.equal(claim.json().profile.profile_id, profile.profile_id);
    assert.equal(
      (await s.account.runAsAsync(OWNER, () => s.account.get<any>(key))).text_tr,
      "Previously saved text",
    );
    assert.deepEqual(
      await s.account.runAsAsync(OWNER, () =>
        s.account.get("reading-progress:" + profile.profile_id),
      ),
      {
        chart_key: profile.chart_key,
        opened: ["core_identity", "sun_house"],
        furthest_index: 4,
      },
    );
  } finally {
    await s.app.close();
    await s.account.close();
    await s.guest.close();
  }
});
