import { test } from "node:test";
import assert from "node:assert/strict";
import { identity } from "../src/config/identity";
import {
  acceptBirthDataConsent,
  withdrawBirthDataConsent,
} from "../src/features/consent";

test("accepting records the configured version and timestamp; withdrawal clears it", () => {
  const acceptedAt = new Date("2026-11-06T11:45:00.000Z");
  assert.deepEqual(acceptBirthDataConsent(true, acceptedAt), {
    consents: {
      birth_data: {
        version: identity.consentVersion,
        accepted_at: acceptedAt.toISOString(),
      },
      marketing: true,
    },
  });
  assert.deepEqual(withdrawBirthDataConsent(true), {
    consents: {
      birth_data: null,
      marketing: true,
    },
  });
});
