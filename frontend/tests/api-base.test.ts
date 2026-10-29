import test from "node:test";
import assert from "node:assert/strict";
import { resolveApiBase } from "../src/api/api-base";

test("dev may fall back to the local mock API", () => {
  assert.equal(
    resolveApiBase({}, { isDev: true }),
    "http://127.0.0.1:4010/v1",
  );
});

test("non-dev builds refuse a missing EXPO_PUBLIC_API_URL (no silent 4010)", () => {
  assert.throws(
    () => resolveApiBase({}, { isDev: false }),
    /EXPO_PUBLIC_API_URL is missing/,
  );
  assert.throws(
    () => resolveApiBase({ EXPO_PUBLIC_API_URL: "  " }, { isDev: false }),
    /EXPO_PUBLIC_API_URL is missing/,
  );
});

test("configured EXPO_PUBLIC_API_URL wins in every mode", () => {
  const url = "https://api.example.test/v1";
  assert.equal(resolveApiBase({ EXPO_PUBLIC_API_URL: url }, { isDev: false }), url);
  assert.equal(resolveApiBase({ EXPO_PUBLIC_API_URL: url }, { isDev: true }), url);
});

test("release profile must not resolve to loopback mock", () => {
  assert.throws(() => {
    const base = resolveApiBase({}, { isDev: false });
    assert.doesNotMatch(base, /127\.0\.0\.1:4010/);
  }, /EXPO_PUBLIC_API_URL is missing/);
});
