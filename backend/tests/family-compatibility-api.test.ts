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
import { CompatibilityJobs } from "../api/compatibility-jobs";
import { FAMILY_COMPATIBILITY_PLACEHOLDER } from "../api/family-aspects";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";

const email = "family-compat@example.com";

test("family compatibility no longer 503s; returns aspect math + placeholder", async () => {
  await wipeDemoTenant(email);
  await clearUsageCounters(demoTenantId(email));
  await clearAuthMode();

  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "family-api-"));
  const dbPath = path.join(folder, "state.sqlite");
  const a = fixture("profile.1.en");
  const b = {
    ...a,
    profile_id: "second-family",
    chart_key: "second-family-chart",
    label: "Second",
  };

  const app = await buildLocalApp({
    dbPath,
    // Paid off — family math must still succeed.
    allowPaid: false,
    generateFamilyAspects: async (data: any) => ({
      relationship_type: data.relationship_type,
      profile_a_label: data.profile_a_label,
      profile_b_label: data.profile_b_label,
      aspects: [
        {
          a_point: "Sun",
          b_point: "Moon",
          type: "trine",
          scheme: "modern",
          orb: 1.2,
          separation: 118.8,
          applying: true,
        },
      ],
      interpretation: FAMILY_COMPATIBILITY_PLACEHOLDER,
      math: { aspects: "compute_synastry_aspects" },
    }),
  });

  try {
    assert.equal(
      (await app.inject({ method: "POST", url: "/v1/compatibility" }))
        .statusCode,
      401,
    );

    const session = (
      await app.inject({
        method: "POST",
        url: "/v1/auth/email/verify",
        payload: { email, code: "000000" },
      })
    ).json();
    const headers = { authorization: `Bearer ${session.access_token}` };

    const store = await openStore();
    await store.runAsAsync(session.me.user_id, async () => {
      for (const p of [a, b]) {
        await store.put("profile:" + p.profile_id, p);
        await store.put("raw:" + p.profile_id, { points: [] });
      }
    });
    await store.close();

    const missingRelation = await app.inject({
      method: "POST",
      url: "/v1/compatibility",
      headers,
      payload: {
        profile_a_id: a.profile_id,
        profile_b_id: b.profile_id,
        type: "family",
      },
    });
    assert.equal(missingRelation.statusCode, 400, missingRelation.body);

    const missingProfile = await app.inject({
      method: "POST",
      url: "/v1/compatibility",
      headers,
      payload: {
        profile_a_id: a.profile_id,
        profile_b_id: "missing-profile",
        type: "family",
        family_relation: "siblings",
      },
    });
    assert.equal(missingProfile.statusCode, 404, missingProfile.body);

    const ok = await app.inject({
      method: "POST",
      url: "/v1/compatibility",
      headers,
      payload: {
        profile_a_id: a.profile_id,
        profile_b_id: b.profile_id,
        type: "family",
        family_relation: "parent_child",
      },
    });
    assert.equal(ok.statusCode, 201, ok.body);
    const body = ok.json();
    validate("Compatibility", body);
    assert.equal(body.type, "family");
    assert.equal(body.family_relation, "parent_child");
    assert.equal(body.score, null);
    assert.equal(body.reading.status, "ready");
    assert.equal(body.reading.sections[0].text, FAMILY_COMPATIBILITY_PLACEHOLDER);
    assert.equal(body.aspects?.length, 1);
    assert.equal(body.aspects[0].a_point, "Sun");

    const config = (await app.inject({ url: "/v1/meta/config" })).json();
    assert.equal(config.flags.familyCompatibility, false);
  } finally {
    await app.close();
    await wipeDemoTenant(email);
  }
});

test("CompatibilityJobs family path uses family aspects generator", async () => {
  const store = await openStore();
  const a = fixture("profile.1.en");
  const b = {
    ...a,
    profile_id: "jobs-family-b",
    chart_key: "jobs-family-b",
    label: "B",
  };
  for (const p of [a, b]) {
    await store.put("profile:" + p.profile_id, p);
    await store.put("raw:" + p.profile_id, { points: [{ name: "Sun" }] });
  }
  let calls = 0;
  const jobs = await CompatibilityJobs.create(
    store,
    false,
    undefined,
    async () => {
      calls++;
      return {
        relationship_type: "sibling",
        profile_a_label: a.label,
        profile_b_label: b.label,
        aspects: [],
        interpretation: FAMILY_COMPATIBILITY_PLACEHOLDER,
        math: { aspects: "compute_synastry_aspects" },
      };
    },
  );
  const result = await jobs.create(
    {
      profile_a_id: a.profile_id,
      profile_b_id: b.profile_id,
      type: "family",
      family_relation: "siblings",
    },
    "en",
  );
  assert.equal(calls, 1);
  assert.equal(result.reading.status, "ready");
  assert.equal(result.family_relation, "siblings");
  await jobs.close();
  await store.close();
});
