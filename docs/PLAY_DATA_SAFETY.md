# Play Console Data Safety — draft answers

Draft only. Align with final privacy policy URLs in `frontend/config/identity.json` before submission. Based on **what the app actually collects today**.

## Data collected

| Data type (Play category) | Collected? | How | Ephemeral / stored | Purpose | Optional? |
| --- | --- | --- | --- | --- | --- |
| **Email address** | Yes | Account auth (Supabase email OTP / Google) | Account on backend + Supabase Auth | Account management, sign-in | Required to use signed-in features |
| **Name** | Yes (display name) | Onboarding / profile | Backend account / profiles | Personalization | User-provided |
| **Date of birth / birth time / birth place** | Yes | Onboarding & profiles | Backend profiles (astrology calculation) | App functionality (charts, forecasts, map, compatibility) | Required for core astrology features |
| **Approximate or precise location** | Yes, when user opts in | `expo-location` “use current place” | Stored as current place on `Me` / used for requests | App functionality (local sky context / place) | Optional — search works without GPS |
| **User IDs** | Yes | Supabase user id / app `user_id` | Backend | Account management | Required when signed in |
| **Crash logs / diagnostics** | Yes, if Sentry DSN configured | `@sentry/react-native` | Sentry project | Analytics / stability | Not required for core use; scrub PII in telemetry config |
| **Product interaction** | Possibly | PostHog if enabled in build | PostHog | Analytics | Check whether production builds enable it before answering Yes |
| **Photos / videos** | No library scrape | User may **save** exported chart images to gallery | On-device gallery only | App functionality (export) | Optional |
| **Financial info / payment** | No (not in current app scope) | — | — | — | — |
| **Contacts / SMS / mic / camera** | No | — | — | — | — |

Birth data is **sensitive personal data** for astrology; disclose under personal info and any applicable “sensitive” declarations required by your counsel. The in-app consent string (`consent.birthData`) must leave draft state before store release.

## Data sharing

| Shared with | What | Why |
| --- | --- | --- |
| **Supabase** (auth processor) | Email, auth tokens, user id | Authentication |
| **App API host** (your backend) | Profiles, birth data, place, prefs, readings | Core product |
| **Google** (if Google Sign-In used) | OAuth account email/profile per Google policy | Sign-in |
| **LLM providers** (Gemini / OpenAI via backend) | Prompt context derived from chart/profile (not raw password) | Generate readings when paid generation is enabled |
| **Sentry** (if DSN set) | Crash/diagnostic events | Stability |
| **Map tile / style provider** (if style URL points at a vendor) | Device IP + tile requests (standard CDN) | Show map |

No sale of personal data. No third-party advertising SDK identified in the mobile dependencies list for ads.

## Security practices

- Data encrypted in transit (**HTTPS** required for production API).
- Users can request deletion via in-app **account deletion** (API + Supabase admin when secret configured).
- Users can export data (JSON / PDF export flows).

## Play form quick picks (draft)

1. **Does your app collect or share any of the required user data types?** → **Yes**
2. **Is all user data encrypted in transit?** → **Yes** (production)
3. **Do you provide a way for users to request deletion?** → **Yes** (in-app account deletion)
4. **Location** → Collected, **approximate and/or precise**, app functionality, **optional**
5. **Personal info → Email, Name, User IDs** → Collected, account management / app functionality
6. **Personal info → Other** (birth date/time/place) → Collected, app functionality; cite privacy policy
7. **Photos** → Not collected from library for upload; optional save-to-gallery is on-device — usually answer **No** for “Photos and videos” collection unless Play guidance treats gallery writes as collection (confirm with counsel)

Replace every example domain and confirm analytics (PostHog/Sentry) enablement for the **production** EAS profile before pasting into Play Console.
