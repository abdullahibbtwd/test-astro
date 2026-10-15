import test from "node:test";
import assert from "node:assert/strict";
import { routes, resolveRoute } from "../src/lib/routes";
test("API routes reject external, malformed and traversing links", () => {
  for (const path of [
    "https://evil.test",
    "//evil.test",
    "/map/../profile",
    "/map/%2e%2e/profile",
    "/map/place/%2Fprofile",
    "/map/place/%ZZ",
    "/unknown",
  ]) {
    assert.equal(resolveRoute(path), "/(tabs)");
  }
  assert.deepEqual(
    resolveRoute("/map/place/gn-1?profile=a&goal=love"),
    routes.place("gn-1", { profile: "a", goal: "love" }),
  );
  assert.deepEqual(
    resolveRoute("/calendar/item/transit%3A1?profile=a"),
    routes.calendarItem("transit:1", "a"),
  );
  assert.deepEqual(resolveRoute("/profile/charts/new"), {
    pathname: "/profile/charts/new",
    params: {},
  });
});
