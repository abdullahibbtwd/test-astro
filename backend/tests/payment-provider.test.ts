import test from "node:test";
import assert from "node:assert/strict";
import {
  FakeProvider,
  ProviderNotConfiguredError,
  RevenueCatStubProvider,
  NativeStubProvider,
  getPaymentProvider,
  fakeSamplePayloads,
} from "../api/payments";

test("FakeProvider signs and verifies webhook payloads", () => {
  const provider = new FakeProvider("test-secret");
  const body = JSON.stringify(fakeSamplePayloads().purchase);
  const sig = provider.sign(body);
  assert.equal(
    provider.verifyWebhookSignature({ "x-fake-signature": sig }, body),
    true,
  );
  assert.equal(
    provider.verifyWebhookSignature({ "x-fake-signature": "00" }, body),
    false,
  );
});

test("FakeProvider parses sample purchase event", () => {
  const provider = new FakeProvider();
  const raw = JSON.stringify(fakeSamplePayloads().renew);
  const event = provider.parseWebhookEvent(raw);
  assert.equal(event.type, "renew");
  assert.equal(event.source_store, "fake");
  assert.equal(event.plan_id, "premium");
  assert.ok(event.event_id);
});

test("RevenueCat and native stubs refuse until configured", async () => {
  const rc = new RevenueCatStubProvider();
  const native = new NativeStubProvider();
  assert.throws(() => rc.verifyWebhookSignature(), ProviderNotConfiguredError);
  assert.throws(() => native.parseWebhookEvent(), ProviderNotConfiguredError);
  await assert.rejects(() => rc.listProducts(), ProviderNotConfiguredError);
});

test("getPaymentProvider(fake) returns FakeProvider", () => {
  assert.equal(getPaymentProvider("fake").id, "fake");
});
