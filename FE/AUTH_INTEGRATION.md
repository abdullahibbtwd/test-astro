# Local Android authentication

## Current implementation

Supabase handles email links and Google. Only the configured owner email, confirmed by Supabase, is accepted. The first verified Supabase UUID is pinned. Public project settings live in ignored `.local-data/auth-config.json`; provider secrets belong in the provider dashboards, never the mobile bundle. Dashboard setup is complete and real authentication is enabled. End-to-end login awaits the user completing Chrome first-run setup and Google sign-in in the emulator. Apple is deferred by user choice.

### Private preview HTTP extension

These routes supplement the spec API only on the local server in real-auth mode. The server binds 127.0.0.1:4020; ADB reverse makes that address available in the emulator. They are intentionally not deployed as a public auth service.

| Route | Request | Response |
| --- | --- | --- |
| POST /v1/auth/browser/start | `{provider:"email",email:string}` or `{provider:"google"}` | `{flow_id,poll_token,expires_at,url?}` |
| POST /v1/auth/browser/poll | `{poll_token}` | `{status:"waiting"}` / `{status:"failed"}` / `{status:"complete",session}` |
| POST /v1/auth/browser/cancel | `{poll_token}` | 204 |
| GET /v1/auth/browser/callback/:flow_id | Provider code or error in query | Static success/failure page, no session credentials |

Identifiers and poll secrets are independent 32-byte random hex values. The PKCE verifier remains in server memory. Attempts expire after 10 minutes and completed results after 1 minute; completion can be polled again within that minute to recover a lost response. Restart cancels attempts. POST requests with a browser Origin are rejected; responses are no-store. Invalid input returns 400, missing/expired attempts 401, browser-origin POST 403, replay 409, and excess attempts 429. Session shape matches the existing Session contract. Only the owner identity verified by Supabase can issue a session.

### Dashboard completion (steps 1–3 completed; live acceptance pending)

1. Obtain acceptance of Google's displayed API Services User Data Policy, then complete Astro app branding in existing Cloud project `gen-lang-client-0801610698` (External, Testing, owner as test user).
2. Create a Web OAuth client using the exact callback displayed in Supabase's Google provider panel. Configure that client in Supabase. Request only openid/email/profile.
3. Save the prepared Supabase loopback redirect allowlist entry. Preserve the free default email template.
4. Enable the local auth config, restart local API and Metro through `scripts/Start-Android-Preview.ps1 -RealCharts`, and exercise email and Google login, refresh and logout on Android. Preserve existing local data. Once real auth has been activated, configuration removal must not downgrade the database to demo auth.

## Deferred ChatGPT connection — outside current scope

User decision on 3 October 2026: defer Continue with ChatGPT and plan usage because commercial availability is limited. Do not implement or activate it in the current scope. The following is retained only as future research. For this personal, locally hosted preview, use OpenAI's documented local-app flow. Do not assume the same registration grants permission to offer the feature in a hosted commercial app; that has a separate access process.

Proposed implementation order:

1. Complete verified owner sign-in above. Link the ChatGPT identity while the owner is authenticated, binding the verified subject plus issued client ID to the existing local account. Do not merge accounts merely because their email text matches. Subsequent ChatGPT sign-in can resume the linked local account.
2. Persist one opaque host ID, use fresh state/nonce/PKCE for each browser attempt, validate the signed ID token against OpenAI's JWKS, and validate granted plan-use scopes separately from identity. Keep credentials in protected local storage outside Drive; never reuse Codex or browser session tokens.
3. Show the connected account, plan-use status, disconnect/reconnect and usage-management controls. Let the user authorize access on OpenAI's page; never ask them to paste OAuth tokens in chat.
4. Fetch models available to that account. Preserve the approved writer model unless a change is explicitly accepted. Adapt eligible writing calls to the documented streaming Responses API with storage disabled, leaving the approved grounding prompts and validation intact.
5. Keep Gemini's research calls separately budgeted. ChatGPT allowance is not the API's dollar ledger; never silently fall back to paid API calls after plan limits or permission failures. The existing $20 API cap remains in force and normal preview generation remains off until the new route is tested.
6. Validate linkage, state/nonce/PKCE, account mismatch, refresh/revocation, scope denial, exhausted allowance, streaming completion/errors and restart behavior with mocked tests; then obtain the user's interactive authorization and run one explicitly bounded reading test.

Acceptance requires both successful real sign-in and a completed eligible model request. A connected identity alone is not evidence that ChatGPT allowance can fund readings. Subscription eligibility and available writer models remain unverified for this user.

Official sources reviewed on 3 October 2026:

- [Local-app overview and eligibility boundary](https://developers.openai.com/siwc/token-sharing-open-source)
- [Registration, token validation and permissions](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference)
- [Preview request restrictions](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)
- [Supabase email links](https://supabase.com/docs/guides/auth/auth-email-passwordless)
- [Supabase Google sign-in](https://supabase.com/docs/guides/auth/social-login/auth-google)
