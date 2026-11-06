import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  clearAuthMode,
  clearUsageCounters,
  demoTenantId,
  openStore,
  wipeDemoTenant,
} from "./helpers";
import { buildLocalApp } from "../api/app";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";
import { SOLAR_RETURN_PLACEHOLDER } from "../api/solar-return";
import { mapChart } from "../mock/scripts/chart";

const emailA = "solar-a@example.com";
const emailB = "solar-b@example.com";

async function login(app: Awaited<ReturnType<typeof buildLocalApp>>, email: string) {
  const res = await app.inject({
    method: "POST",
    url: "/v1/auth/email/verify",
    payload: { email, code: "000000" },
  });
  assert.equal(res.statusCode, 200, res.body);
  return res.json();
}

function bodyName(body: string) {
  return body
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

test("solar-return requires auth, isolates tenants, rejects missing profile, returns math + placeholder", async () => {
  await wipeDemoTenant(emailA);
  await wipeDemoTenant(emailB);
  await clearUsageCounters(demoTenantId(emailA));
  await clearUsageCounters(demoTenantId(emailB));
  await clearAuthMode();

  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "solar-api-"));
  const dbPath = path.join(folder, "state.sqlite");
  const profile = fixture("profile.1.en");
  const engineChart = (() => {
    const base = fixture("chart.1");
    return {
      meta: { utc: base.utc, timezone: base.tz },
      points: base.points.map((p: any) => ({
        name: bodyName(p.body),
        longitude: p.longitude,
        sign: p.sign.charAt(0).toUpperCase() + p.sign.slice(1),
        degree_in_sign: p.degree_in_sign,
        retrograde: p.retrograde,
        sector: { placidus: p.house },
        speed: 1,
      })),
      axes: {
        ascendant: {
          longitude: base.axes.asc.longitude,
          sign:
            base.axes.asc.sign.charAt(0).toUpperCase() +
            base.axes.asc.sign.slice(1),
          degree_in_sign: base.axes.asc.degree_in_sign,
        },
        mc: {
          longitude: base.axes.mc.longitude,
          sign:
            base.axes.mc.sign.charAt(0).toUpperCase() +
            base.axes.mc.sign.slice(1),
          degree_in_sign: base.axes.mc.degree_in_sign,
        },
      },
      sectors: {
        placidus_cusps: base.houses.map((h: any) => h.cusp_longitude),
      },
      sector_rulers: {
        placidus: Object.fromEntries(
          base.houses.map((h: any) => [
            String(h.house),
            {
              sign_on_cusp: h.sign.charAt(0).toUpperCase() + h.sign.slice(1),
              ruler: "Sun",
              modern_ruler: "Sun",
            },
          ]),
        ),
      },
      relations: (base.aspects as any[]).map((a) => ({
        source: bodyName(a.a),
        target: bodyName(a.b),
        type: a.type,
        scheme: "modern",
        orb: a.orb,
      })),
    };
  })();
  // Sanity: mapChart accepts this shape.
  validate("ChartData", mapChart(engineChart, profile.profile_id, "test-key"));

  let app = await buildLocalApp({
    dbPath,
    generateSolarReturn: async (input) => ({
      return_utc: "2024-12-28T04:49:21Z",
      year: input.year,
      chart: engineChart,
      interpretation: SOLAR_RETURN_PLACEHOLDER,
    }),
  });

  try {
    assert.equal(
      (
        await app.inject({
          url: `/v1/profiles/${profile.profile_id}/solar-return?year=2024`,
        })
      ).statusCode,
      401,
    );

    const sessionA = await login(app, emailA);
    const headersA = { authorization: `Bearer ${sessionA.access_token}` };
    const store = await openStore();
    await store.runAsAsync(sessionA.me.user_id, async () => {
      await store.put("profile:" + profile.profile_id, profile);
      await store.put("chart:" + profile.profile_id, fixture("chart.1"));
      await store.put("raw:" + profile.profile_id, {
        points: [{ name: "Sun", longitude: 276.9402 }],
      });
    });
    await store.close();

    const missing = await app.inject({
      url: "/v1/profiles/00000000-0000-4000-8000-000000000099/solar-return?year=2024",
      headers: headersA,
    });
    assert.equal(missing.statusCode, 404, missing.body);

    const badYear = await app.inject({
      url: `/v1/profiles/${profile.profile_id}/solar-return?year=not-a-year`,
      headers: headersA,
    });
    assert.equal(badYear.statusCode, 400, badYear.body);

    const ok = await app.inject({
      url: `/v1/profiles/${profile.profile_id}/solar-return?year=2024`,
      headers: headersA,
    });
    assert.equal(ok.statusCode, 200, ok.body);
    const body = ok.json();
    validate("SolarReturn", body);
    assert.equal(body.profile_id, profile.profile_id);
    assert.equal(body.year, 2024);
    assert.equal(body.return_utc, "2024-12-28T04:49:21Z");
    assert.equal(body.reading.status, "ready");
    assert.equal(body.reading.sections[0].text, SOLAR_RETURN_PLACEHOLDER);
    assert.equal(body.place.place_id, profile.birth.place.place_id);

    // Flag remains off in defaults (surface gated client-side).
    const config = (await app.inject({ url: "/v1/meta/config" })).json();
    assert.equal(config.flags.solarReturn, false);

    const sessionB = await login(app, emailB);
    const headersB = { authorization: `Bearer ${sessionB.access_token}` };
    const cross = await app.inject({
      url: `/v1/profiles/${profile.profile_id}/solar-return?year=2024`,
      headers: headersB,
    });
    assert.equal(cross.statusCode, 404, cross.body);
  } finally {
    await app.close();
    await wipeDemoTenant(emailA);
    await wipeDemoTenant(emailB);
  }
});
