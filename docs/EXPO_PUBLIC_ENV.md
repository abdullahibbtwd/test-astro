# EXPO_PUBLIC_* inventory

These values are **inlined into the JS bundle** and must be treated as public.

| Variable | Secret? | Purpose |
| --- | --- | --- |
| `EXPO_PUBLIC_API_URL` | No | API base URL |
| `EXPO_PUBLIC_EAS_BUILD_PROFILE` | No | Build profile label |
| `EXPO_PUBLIC_AUTH_MODE` | No | `supabase` / demo mode flag |
| `EXPO_PUBLIC_BACKEND_MODE` | No | UI backend label |
| `EXPO_PUBLIC_SUPABASE_URL` | No | Project URL (public) |
| `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | No | Publishable key only — never `SUPABASE_SECRET_KEY` |
| `EXPO_PUBLIC_DEMO_LOGIN_HINT` | No | Dev-only hint (`__DEV__`) |
| `EXPO_PUBLIC_SENTRY_DSN` | No | Public DSN (client ingest) |
| `EXPO_PUBLIC_PAYMENTS_UI` | No | Feature flag |
| `EXPO_PUBLIC_PAYMENT_PROVIDER` | No | Provider name for UI |
| `EXPO_PUBLIC_STRICT_CONTRACT` | No | Dev contract checks |
| `EXPO_PUBLIC_FX_AUDIT` | No | Gallery/audit flag |
| `EXPO_PUBLIC_SHARE_URL` | No | Share link base (docs) |
| `EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID` | No | OAuth client id (public) |
| `EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID` | No | OAuth client id (public) |

**Confirmed:** none of the `EXPO_PUBLIC_*` names are backend secrets. Backend secrets (`SUPABASE_SECRET_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, webhook secrets, DB passwords) must stay server-side / Coolify only.
