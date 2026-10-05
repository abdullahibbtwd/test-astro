import test from "node:test";
import assert from "node:assert/strict";
import { buildLocalApp } from "../local-api/app";
import { fixture } from "../mock-api/fixtures";
import { validate } from "../src/api/zod";

test("ONB local API creates only core, exposes sections safely, completes and exports feedback", async () => {
  const tr = fixture("natal.1.tr"),
    en = fixture("natal.1.en");
  const plan = {
    order: tr.sections.map((s: any) => s.key),
    movement: {},
    house: {},
    titles: {},
    routed_ids: {},
  } as any;
  for (const s of tr.sections) {
    plan.movement[s.key] = s.movement;
    plan.house[s.key] = s.house;
    plan.titles[s.key] = {
      tr: s.title,
      en: en.sections.find((x: any) => x.key === s.key).title,
    };
    plan.routed_ids[s.key] = ["private:" + s.key];
  }
  const generated: string[] = [];
  const runner = async (data: any) => {
    if (["retain", "release", "export"].includes(data.op)) return {};
    if (data.op === "prepare")
      return {
        plan,
        titles: { tr: tr.title, en: en.title },
        parts: { tr: tr.parts, en: en.parts },
      };
    if (data.op === "translate")
      return {
        text_en: en.sections.find((s: any) => s.key === data.section_key).text,
      };
    generated.push(data.section_key);
    return {
      key: data.section_key,
      text_tr: tr.sections.find((s: any) => s.key === data.section_key).text,
      principle_ids: plan.routed_ids[data.section_key],
      draft_tr: "private draft",
      usage: { calls: 2 },
    };
  };
  const app = buildLocalApp({
    dbPath: ":memory:",
    allowPaid: true,
    progressiveReadings: true,
    sectionRunner: runner,
  });
  try {
    const login = await app.inject({
      method: "POST",
      url: "/v1/auth/email/verify",
      payload: { email: "demo@example.com", code: "000000" },
    });
    const headers = { authorization: "Bearer " + login.json().access_token };
    const source = fixture("profile.1.en");
    const places = (
      await app.inject({
        url: "/v1/places/search?q=Plovdiv&kind=birth&lang=en",
        headers,
      })
    ).json();
    const created = await app.inject({
      method: "POST",
      url: "/v1/profiles",
      headers,
      payload: {
        label: "Offline ONB test",
        relation: "self",
        birth_date: source.birth.date,
        birth_time: source.birth.time,
        birth_place_id: places[0].place_id,
      },
    });
    assert.equal(created.statusCode, 201, created.body);
    const profile = created.json(),
      base = `/v1/profiles/${profile.profile_id}/natal-reading`;
    await new Promise((resolve) => setImmediate(resolve));
    assert.deepEqual(generated, ["core_identity"]);
    let response = await app.inject({
      url: base + "/outline?lang=tr",
      headers,
    });
    assert.equal(response.statusCode, 200, response.body);
    validate("ReadingOutline", response.json());
    response = await app.inject({
      url: base + "/sections/core_identity?lang=tr",
      headers,
    });
    assert.equal(response.statusCode, 200, response.body);
    validate("NatalSection", response.json());
    assert.doesNotMatch(
      response.body,
      /principle_ids|draft_tr|usage|private draft/,
    );
    response = await app.inject({
      method: "POST",
      url: base + "/progress",
      headers,
      payload: { key: "core_identity", event: "opened" },
    });
    assert.equal(response.statusCode, 204);
    await new Promise((resolve) => setImmediate(resolve));
    assert.deepEqual(generated, ["core_identity", "sun_house"]);
    response = await app.inject({
      method: "POST",
      url: "/v1/feedback/reading",
      headers,
      payload: {
        profile_id: profile.profile_id,
        target: { type: "section", key: "core_identity" },
        rating: "spot_on",
        comment: "private feedback",
      },
    });
    assert.equal(response.statusCode, 200, response.body);
    response = await app.inject({ url: base + "?lang=tr", headers });
    assert.equal(response.statusCode, 202, response.body);
    await new Promise((resolve) => setImmediate(resolve));
    response = await app.inject({ url: base + "?lang=tr", headers });
    assert.equal(response.statusCode, 200, response.body);
    validate("NatalReading", response.json());
    assert.equal(new Set(generated).size, plan.order.length);
    const reports = (
      await app.inject({ url: "/v1/reports?lang=tr", headers })
    ).json();
    assert.ok(
      reports.items.some(
        (r: any) => r.profile_id === profile.profile_id && r.type === "natal",
      ),
    );
    response = await app.inject({
      method: "POST",
      url: "/v1/me/export",
      headers,
    });
    assert.equal(response.statusCode, 202, response.body);
    assert.equal(
      response.json().reading_feedback[0].comment,
      "private feedback",
    );
    response = await app.inject({ method: "DELETE", url: "/v1/me", headers });
    assert.equal(response.statusCode, 202, response.body);
  } finally {
    await app.close();
  }
});
