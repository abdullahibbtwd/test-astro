import assert from "node:assert/strict";
import test from "node:test";
import { NetworkError } from "../src/api/errors";
import { offlineError } from "../src/api/online";

test("offline state synthesizes NetworkError only without cached data", () => {
  assert.ok(offlineError(false, false) instanceof NetworkError);
  assert.equal(offlineError(false, true), undefined);
  assert.equal(offlineError(true, false), undefined);
});
