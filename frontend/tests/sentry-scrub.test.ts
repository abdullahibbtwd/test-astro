import test from "node:test";
import assert from "node:assert/strict";
import {
  beforeSendEvent,
  beforeBreadcrumbEvent,
  scrubError,
} from "../src/lib/telemetry";

const PII = {
  birth_date: "1979-03-30",
  birth_place: "Sofia, Bulgaria",
  email: "person@example.com",
  authorization: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret",
  reading:
    "Your Sun in Aries rising from Sofia on 1979-03-30 shapes a bold path.",
};

const leakPattern =
  /1979-03-30|Sofia|person@example\.com|Bearer eyJ|Sun in Aries|Authorization/i;

test("@sentry/react-native is a declared dependency", async () => {
  const pkg = JSON.parse(
    await import("node:fs").then((fs) =>
      fs.promises.readFile(
        new URL("../package.json", import.meta.url),
        "utf8",
      ),
    ),
  );
  assert.ok(pkg.dependencies["@sentry/react-native"]);
});

test("beforeSend strips birth dates, places, emails, Authorization, and reading text", () => {
  const scrubbed = beforeSendEvent({
    type: undefined,
    message: PII.reading,
    user: { email: PII.email, id: "user-1" },
    request: {
      headers: {
        Authorization: PII.authorization,
        authorization: PII.authorization,
      },
      data: { birth_date: PII.birth_date, place: PII.birth_place },
    },
    extra: {
      birth_date: PII.birth_date,
      birth_place: PII.birth_place,
      email: PII.email,
      reading: PII.reading,
      diagnostic: { kind: "error" },
    },
    breadcrumbs: [
      {
        category: "console",
        message: PII.reading,
        data: { email: PII.email },
      },
    ],
    exception: {
      values: [{ value: `Failed for ${PII.email} born ${PII.birth_date}` }],
    },
  });
  assert.deepEqual(scrubbed.message, scrubError().message);
  assert.deepEqual(scrubbed.tags, scrubError().tags);
  assert.deepEqual(scrubbed.extra, { diagnostic: { kind: "error" } });
  assert.equal("user" in scrubbed, false);
  assert.equal("request" in scrubbed, false);
  assert.equal("breadcrumbs" in scrubbed, false);
  assert.equal("exception" in scrubbed, false);
  assert.doesNotMatch(JSON.stringify(scrubbed), leakPattern);
});

test("beforeBreadcrumb keeps navigation/http shells and drops PII crumbs", () => {
  const nav = beforeBreadcrumbEvent({
    category: "navigation",
    data: {
      to: `/profiles/00000000-0000-4000-8000-000000000001?birth=${PII.birth_date}`,
      email: PII.email,
    },
    message: PII.reading,
  });
  assert.equal(nav?.category, "navigation");
  assert.deepEqual(nav?.data, { route: "/profiles/:id" });
  assert.doesNotMatch(JSON.stringify(nav), leakPattern);

  const http = beforeBreadcrumbEvent({
    category: "http",
    data: {
      url: "https://api.example/v1/me",
      status_code: 401,
      headers: { Authorization: PII.authorization },
      body: PII.reading,
    },
  });
  assert.deepEqual(http, {
    category: "http",
    data: { status_code: 401 },
  });
  assert.doesNotMatch(JSON.stringify(http), leakPattern);

  assert.equal(
    beforeBreadcrumbEvent({
      category: "console",
      message: PII.reading,
      data: { birth_place: PII.birth_place, email: PII.email },
    }),
    null,
  );
  assert.equal(
    beforeBreadcrumbEvent({
      category: "xhr",
      data: { Authorization: PII.authorization },
    }),
    null,
  );
});
