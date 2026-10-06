# Remaining work, decisions and definition of done

This is a delivery backlog, not approval of a pricing plan or a new platform purchase. The owner's three requested priorities are P (payments), D (design), and I (iOS). R items are the release dependencies needed to make those work for customers.

## P — Payment policy and implementation

**Current:** no purchase SDK, store product catalogue, receipt verification, subscription webhooks or paid entitlement enforcement. The `Me.entitlements` field is a contract hook, not a billing implementation.

| ID | Owner | Work | Done when |
| --- | --- | --- | --- |
| P1 | Radul + product | Decide what stays free: guest core, signed-in charts, forecasts, compatibility, map, Ask, exports; define charging unit | One approved free/paid feature matrix; onboarding promises match it |
| P2 | Radul + product | Choose subscriptions, credits, one-off reports, or a combination; prices, currencies/markets, trials, renewals, cancellation/refunds | Written policy and store-product mapping; no invented prices in code |
| P3 | Product + backend | Set AI usage allowances, retry charging, regeneration rules, abuse limits and gross-cost monitoring | Repeat opens use cached prose; failed/cancelled/duplicate jobs cannot incorrectly consume an allowance |
| P4 | Mobile + backend | Select store billing integration and implement paywall, product loading, pending/success/failure/cancel states, restore and manage-subscription links | Purchase flow works in both store sandboxes with localized price text |
| P5 | Backend | Verify store purchases and notifications; bind entitlements to authenticated account; make updates idempotent | Backend rejects forged/local-only unlocks; renewal, refund, expiry, revocation and account switching are tested |
| P6 | Mobile + QA | Cross-device restore, reinstall, offline/expired access, upgrades/downgrades if offered, duplicate notifications, interrupted purchases | Written acceptance results for Android and iOS; no double charge/double allowance |

**Preserve the current funnel:** guest core before sign-in; 40% → 100% means feature access after sign-in. It is not a paid conversion meter. If some later content becomes paid, product must decide and rewrite the relevant promise.

For in-app digital content, Apple and Google generally require their billing mechanisms, with storefront/program exceptions. Assess the selected launch markets before deciding on an external checkout. Sources checked 6 October 2026: [Apple 3.1](https://developer.apple.com/app-store/review/guidelines/#in-app-purchase) and [Google Play Payments](https://support.google.com/googleplay/android-developer/answer/9858738). This backlog does not assume universal permission for web checkout or select a payment vendor.

## D — Improve UX/UI within the current direction

| ID | Work | Done when |
| --- | --- | --- |
| D1 | Audit all routes and produce a screen/state design inventory | Welcome, loading, core, sign-in, unlock, tabs, detail sheets, exports, errors and empty states have approved designs |
| D2 | Consolidate typography, spacing, button priority, cards, headers and sheets using existing tokens | No accidental competing headings/CTAs; coherent Night and Parchment screens |
| D3 | Refine onboarding and reading experience | Footer language/legal links stay visible; primary action fits small screens; long readings scroll; 40% copy is clear; generated text has editorial sign-off |
| D4 | Clarify profiles and identity | “You” vs additional charts is obvious; switching profiles preserves context; repeated generic “My chart” labels do not confuse users |
| D5 | Refine Home, Ahead/calendar and Match | Main daily content leads; city is secondary; focus/date controls and pending states are comprehensible |
| D6 | Refine map/chart interactions | Thin parans preserved; selected lines/places and chart details remain discoverable; legends and search do not obscure content |
| D7 | Refine Ask | Readable conversation layout, upright starters, composer/keyboard behavior, clear fallback/retry states and grounded cards/links |
| D8 | Complete accessibility and language review | EN/TR, Turkish uppercase, screen readers, focus order, large text, reduced motion, contrast and touch targets verified on both platforms |
| D9 | Prepare brand/release assets | Final name approved; app icon/splash/store screenshots, support and legal pages agree with the product |

Use the supplied original kit plus current tokens/components. The latest owner requests supersede older welcome designs in FE_03/DS snapshots. Full design-system screen acceptance is unfinished; component migration alone is not visual sign-off.

## I — iOS version

**Current:** a shared Expo/React Native application with iOS config/plugins; no validated native iOS release.

| ID | Owner | Work / acceptance |
| --- | --- | --- |
| I1 | Mobile + Radul | Confirm app name, bundle ID, supported iPhone/iPad range and minimum OS; provision Apple/Expo project access and signing |
| I2 | Mobile | Produce reproducible native dev and release builds on macOS/Xcode or configured EAS; resolve native dependency issues |
| I3 | Mobile + backend | Implement/verify Apple sign-in and Google/email callbacks; account linking, private-relay email, cancellation, revocation, refresh and logout |
| I4 | Mobile | Adapt safe areas, headers/back gesture, keyboard, date/time pickers, sheets and permission prompts to iOS while preserving the visual direction |
| I5 | Mobile + backend | Connect store purchases and restoration from P4–P6 |
| I6 | QA | Physical iPhone plus simulator coverage: map/Skia wheel, exports/PDF/share/photos, notifications, app resume, offline cache and large text |
| I7 | Release owner | TestFlight build, privacy declarations, legal/support links, review account, store metadata and submission checklist |

Apple's login-services requirements need review alongside the existing Google login; Apple sign-in was postponed during Android work, not completed. See [Apple 4.8](https://developer.apple.com/app-store/review/guidelines/#login-services). Follow [Expo build setup](https://docs.expo.dev/build/setup/) for signing/build prerequisites. Checked 6 October 2026.

A JavaScript iOS export is not a native iOS build. An Android emulator screenshot is not iOS acceptance.

## R — Release dependencies and remaining backend qualification

| ID | Owner | Work / acceptance |
| --- | --- | --- |
| R1 | Backend/platform | Hosted HTTPS API, per-account authorization/data isolation, durable jobs, managed persistence, backups, secrets and monitoring |
| R2 | Backend/auth | Public Google/Supabase configuration; finish email-link delivery/callback tests and production mobile redirects; retain account linking/identity checks |
| R3 | Backend + mobile | Complete account export/deletion across identity provider, app database, caches, generated files and retention policy; local deletion alone is insufficient |
| R4 | Radul + legal/release | Approve consent/privacy/terms/support content, final IDs, data-processing disclosures, map/data/font/engine/corpus licensing and final analytics/crash reporting setup |
| R5 | Backend | Complete the ONB_02 shared-product migration and its warm-cache/background performance acceptance; avoid duplicate compute/generation |
| R6 | Reading/agent owner | Resolve progressive-reading length/quality review; run the PA golden/adversarial benchmark, fallback analysis, Turkish editorial review and realistic latency/cost coverage |
| R7 | Product + backend | Explicitly keep Solar Return/family compatibility out of release or fund their backend implementation; retain hidden/disabled controls until supported |
| R8 | QA/release | Repeat complete Android/iOS acceptance on staging and physical devices; remove development UI and mock endpoints; release check passes for real reasons |

Release also needs a production map service configuration/attribution decision. Existing blank configurable style/legal URLs and local base-map preview are not a production service agreement.

## Suggested order

1. Team reproduces the supplied baseline; Radul resolves P1/P2 and final app identity.
2. Designer starts D1–D3 while mobile establishes the iOS build and backend establishes staging/multiuser ownership.
3. Implement entitlement APIs and store sandbox purchases alongside the refined UI.
4. Complete platform/device/editorial acceptance, then stage release.

Design work can begin before prices are selected. Do not block the whole team while waiting for payment policy, but do not hard-code a payment assumption.

## Decision register for Radul

| Decision | Current position | Needed for |
| --- | --- | --- |
| Final name / publisher | ASTROLOGY is temporary | IDs, branding, store/legal content |
| Free versus paid features | Guest core + sign-in unlock flow approved; monetization undecided | Paywall and entitlement rules |
| Pricing model and usage allowance | Not chosen | Store products, margins and limits |
| Trial, cancellation/refunds, failed-generation treatment | Not chosen | Purchase copy and support flows |
| Initial markets and platforms | Android preview; iOS requested | Store/billing/localization decisions |
| Hosting and release budget | Private preview exists; no production hosting decision recorded | Staging and customer launch |
| Apple/Google/Expo project invitations | Team-specific access not provided here | Native builds/auth/purchases |
| Legal/support identity/content | Draft/placeholder | Release check and store submission |

OpenAI account login/token sharing remains deferred. No new service registration, commercial commitment or pricing approval is implied by this document.
