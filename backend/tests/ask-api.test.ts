import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { buildLocalApp } from "../api/app";
import { Store } from "../api/store";
import { fixture } from "../mock/fixtures";
import type { AskRunner } from "../api/ask-bridge";
import { validate } from "../../frontend/src/api/zod";
async function setup(runner?: AskRunner, ready = true) {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), "pa-api-"));
  const dbPath = path.join(folder, "db.sqlite");
  const app = await buildLocalApp({
    dbPath,
    allowPaid: true,
    askRunner: runner,
    askReady: () => ready,
  });
  const profile = fixture("profile.0.en");
  const login = await app.inject({
    method: "POST",
    url: "/v1/auth/email/verify",
    payload: { email: "demo@example.com", code: "000000" },
  });
  const tenantId = login.json().me.user_id;
  const store = await Store.open(dbPath);
  await store.runAsAsync(tenantId, async () => {
    await store.put("profile:" + profile.profile_id, profile);
  });
  const headers = { authorization: `Bearer ${login.json().access_token}` };
  const create = await app.inject({
    method: "POST",
    url: "/v1/ask/threads",
    headers,
    payload: { profile_id: profile.profile_id },
  });
  const inTenant = <T>(fn: () => Promise<T>) => store.runAsAsync(tenantId, fn);
  return {
    app,
    store,
    tenantId,
    inTenant,
    profile,
    headers,
    create,
    close: async () => {
      await app.close();
      await store.close();
      fs.rmSync(folder, { recursive: true, force: true });
    },
  };
}
const complete: AskRunner = async (_request, _signal, emit) => {
  emit({ event: "status", data: { phase: "understanding", sources: [] } });
  emit({ event: "delta", data: { text: "Test answer.\n\nSecond paragraph." } });
  emit({
    event: "final",
    data: {
      message: {
        text: "Test answer.\n\nSecond paragraph.",
        cards: [],
        links: [],
        status: "complete",
        answer_kind: "composed",
      },
      audit: { calls: [{ tool: "natal_topics", args: {} }] },
    },
  });
};
test("PA routes persist real protocol messages, bounded history, quota and feedback; delete erases private records", async () => {
  const requests: any[] = [];
  const t = await setup(async (request, signal, emit) => {
    requests.push(request);
    await complete(request, signal, emit);
  });
  try {
    assert.equal(t.create.statusCode, 200);
    validate("Thread", t.create.json());
    const id = t.create.json().thread_id,
      url = `/v1/ask/threads/${id}/messages?lang=tr`;
    assert.equal(
      (await t.app.inject({ url: `/v1/ask/threads/${id}` })).statusCode,
      401,
    );
    for (let i = 0; i < 6; i++) {
      const response = await t.app.inject({
        method: "POST",
        url,
        headers: t.headers,
        payload: { text: `Question ${i}`, context: { date: "2026-10-05" } },
      });
      assert.equal(response.statusCode, 200);
      assert.match(response.body, /event: done/);
      assert.doesNotMatch(response.body, /event: final|audit|natal_topics/);
    }
    assert.equal(requests[0].subject.profile_id, t.profile.profile_id);
    assert.equal(requests[0].lang, "tr");
    assert.equal(requests[0].history.length, 0);
    assert.equal(requests[5].history.length, 8);
    assert.equal(requests[5].history[1].calls[0].tool, "natal_topics");
    const thread = (
      await t.app.inject({ url: `/v1/ask/threads/${id}`, headers: t.headers })
    ).json();
    validate("Thread", thread);
    assert.equal(thread.messages.length, 12);
    assert.equal(thread.messages[1].status, "complete");
    const me = (
      await t.app.inject({ url: "/v1/me", headers: t.headers })
    ).json();
    assert.equal(me.ask_quota.used_today, 6);
    const message_id = thread.messages[1].message_id;
    assert.equal(
      (
        await t.app.inject({
          method: "POST",
          url: `/v1/ask/messages/${message_id}/feedback`,
          headers: t.headers,
          payload: { rating: "down", reason: "not_helpful" },
        })
      ).statusCode,
      204,
    );
    assert.equal((await t.inTenant(() => t.store.list("ask-audit:"))).length, 6);
    assert.equal(
      (
        await t.app.inject({
          method: "DELETE",
          url: `/v1/ask/threads/${id}`,
          headers: t.headers,
        })
      ).statusCode,
      204,
    );
    assert.equal((await t.inTenant(() => t.store.list("ask-audit:"))).length, 0);
    assert.equal((await t.inTenant(() => t.store.list("ask-feedback:"))).length, 0);
  } finally {
    await t.close();
  }
});
test("PA stays unavailable without engine and does not create placeholder conversations", async () => {
  const t = await setup(complete, false);
  try {
    assert.equal(t.create.statusCode, 503);
    assert.equal((await t.inTenant(() => t.store.list("ask-thread:"))).length, 0);
    assert.equal(
      (await t.app.inject({ url: "/v1/meta/config" })).json().flags
        .askAstrology,
      false,
    );
  } finally {
    await t.close();
  }
});
test("PA rejects malformed finals without consuming quota", async () => {
  const t = await setup(async (_r, _s, emit) => {
    emit({ event: "delta", data: { text: "Partial" } });
    emit({
      event: "final",
      data: { message: { text: "Different", status: "complete" } },
    });
  });
  try {
    const id = t.create.json().thread_id;
    const response = await t.app.inject({
      method: "POST",
      url: `/v1/ask/threads/${id}/messages`,
      headers: t.headers,
      payload: { text: "Question" },
    });
    assert.match(response.body, /event: error/);
    assert.doesNotMatch(response.body, /event: done/);
    assert.equal(
      (await t.inTenant(() => t.store.get("me"))).ask_quota.used_today,
      0,
    );
    assert.equal(
      (await t.inTenant(() => t.store.get("ask-thread:" + id))).messages[1]
        .status,
      "failed",
    );
  } finally {
    await t.close();
  }
});
test("PA concurrent send returns busy; deleting an active thread cancels without resurrection or quota", async () => {
  let started!: () => void;
  const ready = new Promise<void>((resolve) => {
    started = resolve;
  });
  const t = await setup(async (_r, signal, emit) => {
    emit({ event: "status", data: { phase: "understanding" } });
    started();
    await new Promise<void>((resolve) =>
      signal.addEventListener("abort", () => resolve(), { once: true }),
    );
  });
  try {
    const id = t.create.json().thread_id,
      url = `/v1/ask/threads/${id}/messages`;
    const first = t.app
      .inject({
        method: "POST",
        url,
        headers: t.headers,
        payload: { text: "First" },
      })
      .then((r) => r);
    await ready;
    const second = await t.app.inject({
      method: "POST",
      url,
      headers: t.headers,
      payload: { text: "Second" },
    });
    assert.equal(second.statusCode, 409);
    assert.equal(second.json().code, "busy");
    await t.app.inject({
      method: "DELETE",
      url: `/v1/ask/threads/${id}`,
      headers: t.headers,
    });
    await first;
    assert.equal(await t.inTenant(() => t.store.get("ask-thread:" + id)), undefined);
    assert.equal(
      (await t.inTenant(() => t.store.get("me"))).ask_quota.used_today,
      0,
    );
  } finally {
    await t.close();
  }
});

test("PA enforces quota, rejects foreign context, and keeps deleted-profile threads read-only", async () => {
  let calls = 0;
  const t = await setup(async (r, s, emit) => {
    calls++;
    await complete(r, s, emit);
  });
  try {
    const id = t.create.json().thread_id,
      url = `/v1/ask/threads/${id}/messages`;
    const send = (payload: any) =>
      t.app.inject({ method: "POST", url, headers: t.headers, payload });
    assert.equal((await send({ text: "   " })).statusCode, 400);
    assert.equal(
      (
        await send({
          text: "Question",
          context: { other_profile_id: "unknown" },
        })
      ).statusCode,
      400,
    );
    let me = await t.inTenant(() => t.store.get("me"));
    me.ask_quota.used_today = 20;
    await t.inTenant(() => t.store.put("me", me));
    assert.equal((await send({ text: "Question" })).statusCode, 429);
    me.ask_quota.resets_at = "2020-01-01T00:00:00Z";
    await t.inTenant(() => t.store.put("me", me));
    assert.match((await send({ text: "Question" })).body, /event: done/);
    assert.equal(
      (await t.inTenant(() => t.store.get("me"))).ask_quota.used_today,
      1,
    );
    await t.inTenant(() => t.store.remove("profile:" + t.profile.profile_id));
    assert.equal((await send({ text: "Question" })).statusCode, 409);
    assert.equal(
      (await t.app.inject({ url: `/v1/ask/threads/${id}`, headers: t.headers }))
        .statusCode,
      200,
    );
    assert.equal(calls, 1);
  } finally {
    await t.close();
  }
});

test("PA client disconnect saves interrupted answer without charging quota", async () => {
  let cancelled!: () => void;
  const stopped = new Promise<void>((resolve) => {
    cancelled = resolve;
  });
  const t = await setup(async (_r, signal, emit) => {
    emit({ event: "delta", data: { text: "Partial answer" } });
    await new Promise<void>((resolve) =>
      signal.addEventListener("abort", () => resolve(), { once: true }),
    );
    cancelled();
  });
  try {
    const address = await t.app.listen({ port: 0, host: "127.0.0.1" });
    const id = t.create.json().thread_id,
      controller = new AbortController();
    const response = await fetch(`${address}/v1/ask/threads/${id}/messages`, {
      method: "POST",
      signal: controller.signal,
      headers: { ...t.headers, "Content-Type": "application/json" },
      body: JSON.stringify({ text: "Question" }),
    });
    const reader = response.body!.getReader();
    await reader.read();
    controller.abort();
    await stopped;
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(
      (await t.inTenant(() => t.store.get("ask-thread:" + id))).messages[1]
        .status,
      "interrupted",
    );
    assert.equal(
      (await t.inTenant(() => t.store.get("me"))).ask_quota.used_today,
      0,
    );
  } finally {
    await t.close();
  }
});
