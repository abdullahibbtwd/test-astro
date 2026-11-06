# Payments setup (owner checklist)

Phase 1 ships **without** live Apple/Google/RevenueCat calls. This doc is what the owner must create before turning paid launch on.

Related: [`PLANS_SCHEMA.md`](./PLANS_SCHEMA.md), [`ACCOUNT_DELETION_SUBSCRIPTIONS.md`](./ACCOUNT_DELETION_SUBSCRIPTIONS.md).

## BLOCKED until owner decides

| Decision | Where to set | Status |
|----------|--------------|--------|
| Plan **names** / display strings | `config/plans.json` → `plans[].name`, `display_name_en`, `display_name_tr` | empty placeholders |
| Which features are **premium** | `config/plans.json` → `feature_catalog.*.premium` (`true`/`false`) | all `null` (ungated) |
| **Free-tier daily AI limits** | `config/plans.json` → `plans[id=free].daily_limits` | all `null` (env fallbacks) |
| Provider: **RevenueCat** or **native IAP** | `config/plans.json` → `provider`, plus `ASTRO_PAYMENT_PROVIDER` / `EXPO_PUBLIC_PAYMENT_PROVIDER` | `"unset"` |
| Store **product IDs** | `config/plans.json` → `store_product_ids.apple` / `.google` | empty |
| Turn off free launch | `free_launch.entitle_all: false` and/or `ASTRO_FREE_LAUNCH_ENTITLE_ALL=0` | currently entitled-all |
| Enable payments UI | `EXPO_PUBLIC_PAYMENTS_UI=1` or meta flag `paymentsUi` | **OFF** by default |

Do **not** commit secrets (shared secrets, API keys, service-account JSON) to the repo. Use host env / secret manager only.

---

## 1. Fill `config/plans.json`

1. Set `provider` to `"revenuecat"` or `"native"`.
2. Name each plan and set EN/TR display names.
3. Mark each feature `premium: true|false`.
4. Set numeric `daily_limits` for free and paid plans.
5. Paste App Store / Play product ids into `store_product_ids`.
6. Set `free_launch.entitle_all` to `false` when ready to enforce.

Prices must **never** be stored in this file — the app reads localized prices from the store at runtime.

---

## 2. App Store Connect (Apple)

Create (exact product ids must match `config/plans.json`):

1. **App** record (if missing) with the production bundle id.
2. **Subscriptions** group (e.g. one group for the app).
3. **Auto-renewable subscription** products — one per paid plan duration you sell (e.g. monthly / yearly). Record each **Product ID**.
4. Localizations (EN + TR at minimum): display name + description (no hard-coded price in marketing that contradicts the store).
5. **Sandbox testers** (Users and Access → Sandbox → Testers): at least one Apple ID per engineer.
6. **In-App Purchase key** / App Store Server API key (Issuer ID, Key ID, `.p8`) if using **native** server notifications — store only in secrets.
7. **App Store Server Notifications V2** URL (native path):

   `https://<API_HOST>/v1/webhooks/payments`

   (Wire the real Apple verifier only after `provider: "native"` is implemented beyond the stub.)

8. If using **RevenueCat**: connect the app in RevenueCat; paste the same product ids; set RevenueCat’s Apple shared secret / StoreKit config per their docs — still no secrets in git.

---

## 3. Google Play Console

1. App listing with the release application id.
2. **Monetize → Products → Subscriptions**: create base plans / offers. Record each **Product ID**.
3. License / **license testers** (or internal testing track with test accounts).
4. **Google Play Developer API** service account (for native RTDN / purchase verify) — JSON key in secrets only.
5. **Real-time developer notifications** (Pub/Sub) topic → push endpoint (native path) pointing at:

   `https://<API_HOST>/v1/webhooks/payments`

6. If using **RevenueCat**: link the Play app + service account in RevenueCat; use RevenueCat webhook URL **or** our `/v1/webhooks/payments` once the RevenueCat stub is replaced with a real verifier.

---

## 4. Keys and env (host only)

| Secret / env | Purpose |
|--------------|---------|
| `ASTRO_FAKE_PAYMENT_WEBHOOK_SECRET` | HMAC for FakeProvider webhooks (dev/test) |
| `ASTRO_PAYMENT_PROVIDER` | `fake` \| `revenuecat` \| `native` |
| `ASTRO_FREE_LAUNCH_ENTITLE_ALL` | `1` / `0` override for entitle-all |
| `EXPO_PUBLIC_PAYMENTS_UI` | `1` to show paywall / Account subscription UI |
| `EXPO_PUBLIC_PAYMENT_PROVIDER` | mobile provider choice |
| RevenueCat public SDK key + webhook Authorization | only after provider = revenuecat |
| Apple `.p8` / shared secret | only after native Apple path |
| Play service-account JSON | only after native Play path |

Webhook path (all providers, once configured):

`POST https://<API_HOST>/v1/webhooks/payments`

FakeProvider (local): header `x-fake-signature: <hmac-sha256-hex of raw body>`.

---

## 5. Sandbox test checklist

Use sandbox / license testers only. Do not charge production users until free launch is off and product matrix is filled.

| # | Scenario | Expected |
|---|----------|----------|
| 1 | **Successful purchase** | Store shows localized price (not a hard-coded string). Webhook/restore marks subscription `active` with future `expires_at`. `GET /v1/billing/status` shows paid `plan_id`. Premium-gated features succeed when free launch is off. |
| 2 | **Failed purchase** | User cancels or payment fails; no new `active` subscription; UI shows failure state (`paywallFailed` / ErrorNotice). |
| 3 | **Cancel** | User cancels in store; webhook `cancel` → status `canceled` (access until expiry if store sends that). After expiry / `expire` event → free plan entitlements. |
| 4 | **Refund** | Refund webhook → status `refunded`; entitlements fall back to free when free launch is off. |
| 5 | **Restore** | Account → Subscription → Restore purchases; prior sandbox purchase reappears; duplicate webhook event does not double-apply (`applied: false`, `reason: "duplicate"`). |
| 6 | **Expiry** | Let sandbox subscription expire (or send FakeProvider `expire` sample); plan returns to `default_plan_id` (`free`); premium features return `premium_required`. |

### Local FakeProvider samples

Backend tests use payloads from `fakeSamplePayloads()` (`purchase`, `renew`, `cancel`, `refund`, `grace`, `billing_retry`, `restore`, `expire`). Run:

```bash
cd backend && npm test
# or focused:
node --import tsx --test tests/payment-webhook.test.ts tests/payment-provider.test.ts tests/feature-gates.test.ts tests/entitlements.test.ts
```

### After owner chooses RevenueCat or native

1. Replace the corresponding stub provider with a real verifier (still no secrets in repo).
2. Drop sample payloads from that provider’s official docs into `backend/tests/fixtures/payments/` and extend webhook tests.
3. Enable `paymentsUi`, set product ids, turn `free_launch.entitle_all` off in a controlled rollout.

---

## 6. Account deletion reminder

Deleting an account clears our `subscriptions` / `payment_events`. **Users must cancel in App Store / Play themselves.** See [`ACCOUNT_DELETION_SUBSCRIPTIONS.md`](./ACCOUNT_DELETION_SUBSCRIPTIONS.md).
