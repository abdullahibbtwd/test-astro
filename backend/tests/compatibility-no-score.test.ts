import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { clearAuthMode, clearUsageCounters, demoTenantId, openStore, wipeDemoTenant } from "./helpers";
import { buildLocalApp } from "../api/app";
import { FAMILY_COMPATIBILITY_PLACEHOLDER } from "../api/family-aspects";
import { fixture } from "../mock/fixtures";
import { validate } from "../../frontend/src/api/zod";

const email = "compat-no-score@example.com";

test("love, work, and family compatibility all return score:null with flag off", async () => {
  await wipeDemoTenant(email);
  await clearUsageCounters(demoTenantId(email));
  await clearAuthMode();

  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "compat-no-score-"));
  const a = fixture("profile.1.en");
  const b = {
    ...a,
    profile_id: "no-score-b",
    chart_key: "no-score-b",
    label: "Bea",
  };

  const app = await buildLocalApp({
    dbPath: path.join(folder, "state.sqlite"),
    allowPaid: true,
    generateCompatibility: async (data: any) => ({
      context: data.context,
      readings: Object.fromEntries(
        ["en", "tr"].map((lang) => [
          lang,
          {
            title: `${data.context.type}-${lang}`,
            sections: [
              {
                key: "overview",
                movement: 0,
                title: "Overview",
                text: `${data.context.type} reading text`,
              },
            ],
          },
        ]),
      ),
    }),
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
          orb: 1,
          separation: 120,
          applying: true,
        },
      ],
      interpretation: FAMILY_COMPATIBILITY_PLACEHOLDER,
      math: { aspects: "compute_synastry_aspects" },
    }),
  });

  try {
    const config = (await app.inject({ url: "/v1/meta/config" })).json();
    assert.equal(config.flags.compatibilityScore, false);

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

    for (const type of ["love", "work"] as const) {
      const res = await app.inject({
        method: "POST",
        url: "/v1/compatibility",
        headers: { ...headers, "idempotency-key": `no-score-${type}` },
        payload: {
          profile_a_id: a.profile_id,
          profile_b_id: b.profile_id,
          type,
        },
      });
      assert.equal(res.statusCode, 201, res.body);
      const body = res.json();
      validate("Compatibility", body);
      assert.equal(body.type, type);
      assert.equal(body.score, null);

      // Wait for async generation to settle, then re-fetch — score stays null.
      for (let i = 0; i < 40; i++) {
        await new Promise((r) => setTimeout(r, 25));
        const got = await app.inject({
          url: `/v1/compatibility/${body.compatibility_id}`,
          headers,
        });
        assert.equal(got.statusCode, 200, got.body);
        const ready = got.json();
        assert.equal(ready.score, null);
        if (ready.reading?.status === "ready") {
          assert.ok(ready.reading.sections?.[0]?.text);
          break;
        }
        if (i === 39) assert.fail(`${type} reading did not become ready`);
      }
    }

    const family = await app.inject({
      method: "POST",
      url: "/v1/compatibility",
      headers: { ...headers, "idempotency-key": "no-score-family" },
      payload: {
        profile_a_id: a.profile_id,
        profile_b_id: b.profile_id,
        type: "family",
        family_relation: "siblings",
      },
    });
    assert.equal(family.statusCode, 201, family.body);
    const familyBody = family.json();
    validate("Compatibility", familyBody);
    assert.equal(familyBody.score, null);
    assert.equal(familyBody.reading?.status, "ready");
    assert.ok(familyBody.reading?.sections?.[0]?.text);
    assert.ok(Array.isArray(familyBody.aspects));
  } finally {
    await app.close();
    await wipeDemoTenant(email);
  }
});
