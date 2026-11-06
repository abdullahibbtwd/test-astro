# Security checklist

Review-and-test hardening (not a pentest). Branches: `security/1-route-auth-matrix` … `security/10-security-checklist`. Do not deploy from this checklist alone.

## 1. Route authorization

| Control | How verified | Owner manual |
| --- | --- | --- |
| Every route has an auth level | `docs/ROUTE_AUTH_MATRIX.md` + `backend/api/route-auth-matrix.ts` | Keep matrix updated when adding routes |
| User routes reject bad tokens | `backend/tests/route-auth-matrix.test.ts` (no / malformed / expired / wrong iss·aud → 401) | — |
| Public / webhook levels | Same suite | — |
| No admin routes | Matrix asserts zero admin | If admin UI is added later, define role claims first |

**Branch:** `security/1-route-auth-matrix`

## 2. Production fail-closed

| Control | How verified | Owner manual |
| --- | --- | --- |
| Demo auth refused | `config-check` + tests | Coolify: `NODE_ENV=production`, `ASTRO_DEMO_AUTH=0` |
| Issuer / JWKS present | Refuse if `SUPABASE_URL` missing or `AUTH_ENABLED=0` | Set `SUPABASE_URL`, never disable auth in prod |
| Webhook secret / provider | Refuse unset provider; refuse default fake secret | Set `ASTRO_PAYMENT_PROVIDER` (not fake) or a non-default `ASTRO_FAKE_PAYMENT_WEBHOOK_SECRET` |
| Rate limits on | Refuse `ASTRO_RATE_LIMIT_DISABLED=1` | Leave unset in Coolify |
| Staging parity | `ASTRO_PRODUCTION_LIKE=1` | Optional for staging |

**Branch:** `security/2-production-fail-closed`

## 3. IDOR

| Control | How verified | Owner manual |
| --- | --- | --- |
| Cross-tenant resource access → 404 | `backend/tests/idor-sweep.test.ts` | — |
| Compatibility DELETE foreign id → 404 | Fixed in suite | — |

**Branch:** `security/3-idor-sweep`

## 4. Deletion completeness

| Control | How verified | Owner manual |
| --- | --- | --- |
| Data inventory | `docs/ACCOUNT_DATA_INVENTORY.md` | Confirm Coolify snapshot + Supabase backup TTLs (**BLOCKED** until documented in ops) |
| Local wipe + guest claimed rows | Tests + inventory | — |
| IdP delete + retry after tombstone | `backend/tests/deletion-idp.test.ts` (mocked admin) | Coolify must set `SUPABASE_SECRET_KEY` |
| Store billing not canceled | Product copy / `ACCOUNT_DELETION_SUBSCRIPTIONS.md` | App Store / Play cancel is user-owned |

**Branch:** `security/4-deletion-completeness`

## 5. Secrets

| Control | How verified | Owner manual |
| --- | --- | --- |
| `.env.*` ignored except examples | `.gitignore` / `git check-ignore` | Never force-add env files |
| Gitleaks CI + pre-commit | `.github/workflows/secret-scan.yml`, `.githooks/pre-commit` | `git config core.hooksPath .githooks`; `brew install gitleaks` |
| Full history scan | `docs/SECRET_SCAN_REPORT.md` — **0 findings** | Re-run on release |
| `EXPO_PUBLIC_*` non-secret | `docs/EXPO_PUBLIC_ENV.md` | Never put secret keys in Expo env |

**Branch:** `security/5-secrets`

## 6. Input / output safety

| Control | How verified | Owner manual |
| --- | --- | --- |
| Body limit 64 KiB | Fastify `bodyLimit` + io-safety test | Traefik/Coolify body limits optional |
| Security headers | `io-safety.test.ts` | CDN/proxy may add HSTS |
| No stack/SQL/token in errors | Error handler + scrub test | — |
| Schema validation | Zod on endpoint bodies | Extend OpenAPI `maxLength` over time (**PARTIAL**) |
| Prompt injection (Ask / labels) | `ask-guards`, `sanitizeLabel` | Review new LLM prompt builders for raw user text |
| CORS | Intentional: no CORS on mobile API; browser auth rejects Origin POSTs | Do not open `*` CORS on Coolify |

**Branch:** `security/6-input-output-safety`

## 7. Dependencies

| Control | How verified | Owner manual |
| --- | --- | --- |
| npm / pip audit | `docs/DEPENDENCY_AUDIT.md` | Schedule zod@4 + Expo SDK upgrades |
| Safe upgrades applied | fastify 5.12.8, pillow 13.0.0, lockfile audit fix | Rebuild Docker image after pillow bump |

**Branch:** `security/7-dependencies`

## 8. Mobile hardening

| Control | How verified | Owner manual |
| --- | --- | --- |
| Tokens in SecureStore | `docs/MOBILE_HARDENING.md` + code | Device check: no tokens in `kv-session.json` |
| allowBackup / cleartext | CNG plugin | Inspect EAS-merged manifest |
| debuggable false | Gradle release default | `release:check` / apksigner |
| No release debug menus | Gallery `__DEV__` only | — |
| Logs / Sentry scrub | telemetry + inventory | Confirm `EXPO_PUBLIC_SENTRY_DSN` only (public) |

**Branch:** `security/8-mobile-hardening`  
**BLOCKED:** unsigned iOS Simulator SecureStore entitlements — use TestFlight/device.

## 9. Webhooks

| Control | How verified | Owner manual |
| --- | --- | --- |
| Signature | `payment-webhook.test.ts` | Real RevenueCat/Apple secrets in Coolify when leaving fake |
| Timestamp ±15m | Stale event → `stale_or_future` | Align provider clocks |
| Idempotency | Duplicate `event_id` → not re-applied | — |
| Unknown types ignored | No subscription grant | When wiring RevenueCat, map event types explicitly |

**Branch:** `security/9-webhooks`

## 10. This checklist

| Control | How verified | Owner manual |
| --- | --- | --- |
| Controls listed | This file | Walk Coolify / Supabase / EAS / stores below each release |

**Branch:** `security/10-security-checklist`

---

## Owner runbook (Coolify / Supabase / EAS / stores)

### Coolify

1. `NODE_ENV=production`, `ASTRO_DEMO_AUTH=0`, `AUTH_ENABLED` not `0`.
2. Set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`.
3. Set `ASTRO_PAYMENT_PROVIDER` to the real provider (not unset/fake) before paid launch.
4. Do not set `ASTRO_RATE_LIMIT_DISABLED`.
5. Set `ASTRO_TRUST_PROXY_HOPS` to match Traefik/Cloudflare hop count.
6. Confirm TLS terminates at Traefik; API listens on internal port only as designed.
7. Document volume snapshot retention for deletion requests.

### Supabase

1. Confirm JWKS at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`.
2. Secret key only on backend; publishable key in the app.
3. Note Auth user backup retention for GDPR deletion follow-up.
4. After account delete, spot-check Auth users admin UI.

### EAS / stores

1. Production profile: HTTPS `EXPO_PUBLIC_API_URL`, no sslip/http.
2. Run `npm run release:check` in `frontend/`.
3. Confirm merged Android manifest: `allowBackup=false`, no cleartext on release.
4. Play / App Store: subscription cancel is user-owned; deletion copy already says so.
5. Data safety form: see `docs/PLAY_DATA_SAFETY.md`.
