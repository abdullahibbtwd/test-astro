import test from "node:test";
import assert from "node:assert/strict";
import {
  initSentry,
  scrubSentryEvent,
  Sentry,
} from "../api/sentry";
import type { ErrorEvent } from "@sentry/node";

const PII = {
  email: "person@example.com",
  birth_date: "1979-03-30",
  authorization: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature",
};

test("initSentry warns and continues when SENTRY_DSN is missing", () => {
  const warnings: string[] = [];
  const original = console.warn;
  console.warn = (...args: unknown[]) => {
    warnings.push(args.map(String).join(" "));
  };
  try {
    assert.equal(initSentry({}), false);
    assert.equal(initSentry({ SENTRY_DSN: "   " }), false);
    assert.ok(warnings.some((w) => /SENTRY_DSN/.test(w)));
  } finally {
    console.warn = original;
  }
});

test("scrubSentryEvent drops emails, birth dates, tokens, and request bodies", () => {
  const scrubbed = scrubSentryEvent({
    message: `Failed for ${PII.email} born ${PII.birth_date}`,
    user: { email: PII.email, id: "user-1" },
    request: {
      headers: { authorization: PII.authorization },
      data: {
        birth_date: PII.birth_date,
        email: PII.email,
        id_token: "secret-token",
      },
      cookies: { session: "abc" },
    },
    extra: {
      email: PII.email,
      birth_date: PII.birth_date,
      access_token: "tok",
    },
  } as ErrorEvent);

  assert.ok(scrubbed);
  assert.equal(scrubbed.request?.data, undefined);
  assert.equal(scrubbed.request?.cookies, undefined);
  assert.equal(scrubbed.user?.email, undefined);
  assert.equal(scrubbed.request?.headers?.authorization, "[Filtered]");
  assert.equal(scrubbed.extra?.email, "[Filtered]");
  assert.equal(scrubbed.extra?.birth_date, "[Filtered]");
  assert.equal(scrubbed.extra?.access_token, "[Filtered]");
  const json = JSON.stringify(scrubbed);
  assert.doesNotMatch(json, /person@example\.com/);
  assert.doesNotMatch(json, /1979-03-30/);
  assert.doesNotMatch(json, /Bearer eyJ/);
  assert.doesNotMatch(json, /secret-token/);
});

test("captureException delivers a scrubbed event when DSN is configured", async () => {
  const captured: ErrorEvent[] = [];
  assert.equal(
    initSentry(
      { SENTRY_DSN: "https://publickey@o0.ingest.sentry.io/1" },
      {
        afterScrub: (event) => {
          captured.push(event);
          return null; // do not send over the network
        },
      },
    ),
    true,
  );

  Sentry.captureException(
    new Error(`boom for ${PII.email} on ${PII.birth_date}`),
  );
  await Sentry.flush(2000);

  assert.equal(captured.length, 1);
  const json = JSON.stringify(captured[0]);
  assert.doesNotMatch(json, /person@example\.com/);
  assert.doesNotMatch(json, /1979-03-30/);
  assert.match(json, /\[Filtered\]|boom/);
});
