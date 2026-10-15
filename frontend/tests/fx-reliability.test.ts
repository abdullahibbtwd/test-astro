import test from "node:test";
import assert from "node:assert/strict";
import { QueryClient, dehydrate, hydrate } from "@tanstack/react-query";
import { ApiError, NetworkError, describeError } from "../src/api/errors";
import {
  validateContract,
  ContractError,
} from "../src/api/contract-validation";
import { schemas } from "../src/api/zod";
import {
  diagnosticReports,
  reportError,
  reportContractViolation,
  initTelemetry,
} from "../src/lib/telemetry";
import {
  shouldPersistQuery,
  keepsReading,
  CACHE_MAX_AGE,
} from "../src/api/cache-policy";
import { fixture } from "../../backend/mock/fixtures";
import { jobPhase } from "../src/api/job-timing";

test("every error category has an appropriate message and action", () => {
  const rows: [unknown, string, string][] = [
    [new NetworkError(), "offline", "retry"],
    [{ code: "busy" }, "busy", "wait"],
    [new ApiError(429, "rate_limited", 5), "rate_limited", "retry"],
    [{ code: "generation_failed" }, "generation_failed", "retry"],
    [{ absence: { reason: "generation_paused" } }, "paused", "none"],
    [{ absence: { reason: "not_generated" } }, "not_generated", "request"],
    [{ code: "upstream_unavailable" }, "server", "retry"],
    [{ code: "internal" }, "server", "retry"],
    [{ status: 502 }, "server", "retry"],
    [{ code: "not_found" }, "not_found", "back"],
    [{ code: "out_of_range" }, "out_of_range", "none"],
    [{ code: "validation_error" }, "invalid", "none"],
    [{ code: "conflict" }, "conflict", "refresh"],
    [{ code: "unauthorized" }, "unauthorized", "none"],
    [new ContractError(), "server", "retry"],
  ];
  for (const [error, kind, action] of rows) {
    assert.equal(describeError(error).kind, kind);
    assert.equal(describeError(error).action, action);
  }
  assert.equal(describeError({}, false).kind, "offline");
  assert.equal(
    describeError(new ApiError(429, "rate_limited", 5)).retryAfterSec,
    5,
  );
});
test("old running jobs remain very slow, never failed", () => {
  const now = Date.now();
  assert.equal(
    jobPhase({ created_at: new Date(now - 30 * 60_000).toISOString() }, now),
    "very_slow",
  );
  assert.equal(
    jobPhase({ created_at: new Date(now - 4 * 60_000).toISOString() }, now),
    "slow",
  );
});
test("release accepts new enums once reported; development stays strict; wrong envelopes fail", () => {
  const value = { ...fixture("forecast-day.en"), tone: "future_band" };
  const before = diagnosticReports().length;
  assert.equal(
    validateContract("DayForecast", value, schemas.DayForecast!, false),
    value,
  );
  assert.equal(diagnosticReports().length, before + 1);
  assert.throws(() =>
    validateContract("DayForecast", value, schemas.DayForecast!, true),
  );
  for (const invalid of [null, "<html>error</html>", []])
    assert.throws(
      () =>
        validateContract("DayForecast", invalid, schemas.DayForecast!, false),
      ContractError,
    );
});
test("large geometry validates envelope only while fixture schemas retain full validation", () => {
  const value = {
    type: "FeatureCollection",
    features: [{ arbitrary: "not a geometry" }],
  };
  assert.equal(
    validateContract("CountryGeometry", value, schemas.CountryGeometry!, true),
    value,
  );
  assert.equal(schemas.CountryGeometry!.safeParse(value).success, false);
  assert.throws(() =>
    validateContract(
      "CountryGeometry",
      { type: "FeatureCollection", features: null },
      schemas.CountryGeometry!,
      true,
    ),
  );
});
test("cache excludes polling, errors, geography and older heat goals; three-day readings hydrate", () => {
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity } },
  });
  const key = ["generated", "en", "natal", "test"];
  client.setQueryData(
    key,
    { kind: "ready", data: fixture("natal.1.en") },
    { updatedAt: Date.now() - 3 * 86400000 },
  );
  for (const [name, path] of [
    ["job", "id"],
    ["resource", "/geo/countries.geojson"],
  ])
    client.setQueryData([name, "en", path], {});
  for (let i = 0; i < 5; i++)
    client.setQueryData(
      ["resource", "en", `/profiles/test/acg/heat/${i}`],
      {},
      { updatedAt: i + 1 },
    );
  const all = client.getQueryCache().getAll();
  const state = dehydrate(client, {
    shouldDehydrateQuery: (q) => shouldPersistQuery(q, all),
  });
  assert.equal(state.queries.length, 4);
  assert.ok(state.queries.some((q) => q.queryKey[0] === "generated"));
  assert.ok(CACHE_MAX_AGE > 3 * 86400000);
  assert.ok(
    keepsReading([
      "resource",
      "en",
      "/profiles/test/forecast/month?month=2026-10",
    ]),
  );
  const restored = new QueryClient({
    defaultOptions: { queries: { gcTime: Infinity } },
  });
  hydrate(restored, state);
  assert.deepEqual(restored.getQueryData(key), client.getQueryData(key));
  client.clear();
  restored.clear();
});
test("diagnostics never retain birth details and no DSN causes no vendor initialization", async () => {
  delete process.env.EXPO_PUBLIC_SENTRY_DSN;
  await initTelemetry();
  reportError(new Error("Private Name born 1990-01-01 in Sofia"), {
    birth_date: "1990-01-01",
    lat: 42,
  });
  reportContractViolation("DayForecast", [
    { path: ["Private Name", "1990-01-01", "tone"], code: "invalid_type" },
  ]);
  for (let i = 0; i < 60; i++) reportError(new Error("secret"));
  assert.equal(diagnosticReports().length, 50);
  assert.doesNotMatch(
    JSON.stringify(diagnosticReports()),
    /Private|1990|Sofia|secret/,
  );
});
