# Route authorization matrix

Source of truth: `backend/api/route-auth-matrix.ts`.  
Verified by: `backend/tests/route-auth-matrix.test.ts`.

## Auth levels

| Level | Meaning |
| --- | --- |
| **public** | No Bearer. Some routes use body credentials (`refresh_token`). |
| **user** | `Authorization: Bearer <access token>` required (JWT via JWKS or demo opaque token). |
| **webhook** | HMAC signature header; no Bearer. |
| **guest** | `X-Guest-Token` capability header (guest onboarding only). |
| **capability** | Browser sign-in `poll_token` / callback flow id. |
| **admin** | **None.** There are no admin routes. |

## Expected results (user routes)

| Token variant | Expected HTTP |
| --- | --- |
| No token | **401** |
| Malformed token | **401** |
| Expired JWT | **401** |
| Wrong audience | **401** |
| Wrong issuer | **401** |
| Valid JWT | **not 401** (200 / 400 / 404 / 409 / 503 depending on resource) |

Public routes must not return 401 solely because Bearer is missing.  
Webhook: bad/missing signature → **401**; valid signature → non-401.

## Routes

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| POST | `/v1/auth/email/start` | public | |
| POST | `/v1/auth/email/verify` | public | |
| POST | `/v1/auth/apple` | public | |
| POST | `/v1/auth/google` | public | |
| POST | `/v1/auth/refresh` | public | Body `refresh_token` |
| POST | `/v1/auth/logout` | public | Body `refresh_token` |
| GET | `/v1/meta/config` | public | |
| GET | `/v1/meta/catalogue` | public | |
| GET | `/v1/geo/countries.geojson` | public | |
| POST | `/v1/auth/browser/start` | public | When SupabaseAuth wired |
| POST | `/v1/auth/browser/poll` | capability | `poll_token` |
| POST | `/v1/auth/browser/cancel` | capability | `poll_token` |
| GET | `/v1/auth/browser/callback/:id` | capability | Flow id + code |
| POST | `/v1/webhooks/payments` | webhook | HMAC |
| POST/GET/DELETE | `/v1/onboarding/reading` | guest | Guest onboarding flag |
| POST | `/v1/me/onboarding/claim` | user | Bearer + `guest_token` |
| GET | `/v1/billing/status` | user | |
| * | All other `/v1/*` inventory routes | user | See `route-auth-matrix.ts` |

Ownership for `{id}` resources is tenant-scoped (see IDOR suite). Missing foreign ids return **404**, not **403**.
