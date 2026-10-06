# Frontend (mobile app): spec index

*Spec set v1, 2026-09-30. Written against `PROJECT_OVERVIEW.md` (state 2026-09-29), the client's functional
brief ("Функционално задание за мобилно астрологично приложение", sections 1–20) and **real run outputs** of every
backend layer (natal, synastry, predictive, ACG, calendar). Read this file first, then the specs in order.
The brief is in Bulgarian; everything the frontend needs from it is restated in English in these specs, so the
agent does not need to read the original.*

## 1. What gets built

A **React Native (Expo) app for iOS and Android** that implements the client brief end to end: onboarding and
accounts, saved birth profiles ("My Charts"), the natal reading with an **interactive chart wheel**, day / month /
year forecasts (+ Solar Return), compatibility (love / family / work), the astrocartography map with city, country
and region reports and the "Where Should I Go?" recommender, the personal calendar with Best Days and push
notifications, the **Ask Astrology** assistant, and export / share of the chart and reports.

The product is built around the brief's four questions:

| Question | Feature | Tab |
|---|---|---|
| WHO AM I? | Natal chart + reading | **Chart** |
| WHAT'S AHEAD? | Today / Month / Year, Calendar, Best Days | **Ahead** |
| WHO FITS ME? | Compatibility (love / family / work) | **Match** |
| WHERE SHOULD I BE? | Astro map, place reports, recommender | **Map** |

**Backend reality.** The backend today is a set of Python CLI orchestrators (`run.py`, `synastry_run.py`,
`run_predictive.py`, `run_acg.py`, `run_calendar.py`) that write JSON into run folders. **There is no HTTP API.**
This spec set therefore defines the API contract (FE_02). The frontend builds against a **mock server** that serves
that contract from real fixtures. Radul's backend agent implements the same contract later. The contract is the
only thing the two sides share.

## 2. Files in this set

| # | File | Scope |
|---|---|---|
| 0 | `FE_00_INDEX.md` | decisions, brief map, backend readiness, phases, open decisions, Phase 0 report |
| 1 | `FE_01_FOUNDATIONS_SPEC.md` | stack, repo layout, architecture, navigation, design system, i18n, content rules, states, a11y, privacy, testing |
| 2 | `FE_02_API_CONTRACT_SPEC.md` | the REST contract: conventions, jobs, errors, every endpoint and type, source mapping, mock server, fixtures |
| 3 | `FE_03_ONBOARDING_ACCOUNT_SPEC.md` | auth, onboarding, My Charts (birth profiles), place search, settings, saved reports, privacy |
| 4 | `FE_04_HOME_FORECAST_SPEC.md` | Home, Today, Month, Year, Solar Return |
| 5 | `FE_05_NATAL_CHART_SPEC.md` | My Chart, the interactive wheel (port of `Chart_wheel/`), reading, planets/houses/aspects, export and share |
| 6 | `FE_06_COMPATIBILITY_SPEC.md` | compatibility flow and report |
| 7 | `FE_07_ASTRO_MAP_SPEC.md` | map, lines, heat layers, city / country / region reports, "Where Should I Go?" |
| 8 | `FE_08_CALENDAR_BEST_DAYS_SPEC.md` | calendar, periods, day detail, Best Days, local notifications |
| 9 | `FE_09_ASK_ASTROLOGY_SPEC.md` | the AI assistant chat |

## 3. Locked decisions

| # | Decision |
|---|---|
| F1 | **Stack: React Native + Expo, TypeScript strict**, one codebase for iOS and Android. Development builds via EAS (MapLibre and Skia need native code; Expo Go is not a target). Details in FE_01 §1. |
| F2 | **Contract-first.** FE_02 is the only interface. The app never reads backend files, never calls an LLM, and never runs astrology math, with one exception (F6). |
| F3 | **Scope = the full brief, end to end**, including auth, Ask Astrology, Solar Return, PDF/PNG export, sharing and notifications. Where the backend lacks a feature, FE_02 marks the endpoint `NEW`. The app is built and tested against the mock and goes live per feature as the backend lands (feature flags, FE_01 §3.6). |
| F4 | **Free / Premium is ignored.** Every user gets every feature and the full-length content. No paywall, no locks, no teasers. Keep one seam: `me.entitlements` (all `true` in v1) and an `<Entitled feature>` wrapper that currently always renders its children. |
| F5 | **Languages: Turkish (default) and English.** The backend writes Turkish first and English second; no other language exists. All reading text and astrological labels come from the API in the requested language. The app owns only UI chrome strings. |
| F6 | **The chart wheel is a port of `Chart_wheel/`** (the existing deterministic JS renderer) into a TypeScript package, with byte-identical SVG output for the static render and an interactive layer on top (FE_05). It is the only client-side astrology code, and it is geometry, not interpretation. |
| F7 | **Tradition mask on every surface.** The dual-tradition architecture is invisible. No UI string, label, accessibility text or export may contain: modern, classical, traditional, Ottoman, Arabic, Hellenistic, whole sign, Placidus, house system, triplicity, dignity, domicile, detriment, exaltation, fall, bound, term, face, decan, sect, Lot, Spirit, Fortune, planetary day, planetary hour, time lord, profection (and their Turkish equivalents). CI enforces it on the i18n files (FE_01 §6). |
| F8 | **No-hallucination contract extends to the UI.** The client never composes an astrological statement. Interpretive copy about a user's chart comes only from API text fields. UI chrome may *name* structured facts ("Sun · 6° Capricorn · 9th house") but never *interpret* them ("…which makes you ambitious"). |
| F9 | **Exact birth time is required** (Radul's assumption, ACG_07). There is no "I don't know my time" flow in v1. If the API still returns an absence contract (e.g. `time_not_exact`), the UI shows it gracefully (FE_01 §7). |
| F10 | **"Today" is computed in the user's current-location timezone** (`me.current_place.tz`), not the device timezone (CAL_00 D1). All API dates are local calendar dates in that tz. |
| F11 | **Readings are asynchronous.** Any LLM-backed resource may answer `202` + a job. Observed generation times from real runs: natal ≈ 1.5 min, city reading ≈ 70 s, day/month/year ≈ 10–40 s each, compatibility several minutes. The UI never blocks navigation on a job (FE_01 §7). |
| F12 | **Deterministic before narrative.** Every screen renders its computed data at once (wheel, bands, lines, dates, grades) and brings the text in when it is ready. |
| F13 | **Render-if-present for `NEW` fields.** Optional fields that the backend does not produce yet (e.g. per-domain daily paragraphs) are typed as optional; the UI renders their block only when present and never shows a placeholder for them. |
| F14 | **Navigation:** 5 tabs (Home · Chart · Ahead · Match · Map). Ask Astrology is a global action on every tab. Profile / My Charts / Settings open from the avatar. The brief's 8-item menu maps onto this in §4. |
| F15 | **Notifications are local:** the app schedules them on the device from API notification candidates. Defaults: max 1 per day, max 3 per week, quiet hours 22:00–08:00 (CAL_00 D4). |
| F16 | **Exports are generated on the device:** PNG/JPG from the wheel SVG (Skia rasterisation), PDF from HTML templates (`expo-print`), share cards from a rendered view. No export endpoint. |

## 4. Brief → spec map

| Brief § | Requirement (summary) | Where |
|---|---|---|
| 1 | Personal astrology navigator; 4 questions; Free/Premium | this file §1, F4 |
| 2 | Registration: name, birth date, exact time, place, gender (optional), current residence (optional), language; auto coordinates + timezone. My Charts: partner, children, parents, family, friends, colleagues, business partners | FE_03 |
| 3 | Natal reading (short and full lists of topics) | FE_05 §4 (full reading for everyone, F4) |
| 4 | Graphic natal wheel: 12 signs, 12 houses, ASC, MC, planets, exact degrees, aspects with visual distinction; tap planet → sign → house → aspect for personal meaning | FE_05 §2–3 |
| 5 | Download Chart (PNG/JPG), PDF (chart + basic info), Full Report PDF; Share Chart via WhatsApp, Instagram, Messenger, email, other apps; branded share image | FE_05 §6 |
| 6 | Daily forecast from transits to the natal chart: main energy, love, family, work, money, communication, emotional state, important transits, advice | FE_04 §3 |
| 7 | Monthly forecast: theme, love, family, work, career, money, social, travel, important transits, best days, tense days, important periods | FE_04 §4 |
| 8 | Yearly forecast (12 months) with themes + month by month; Solar Return | FE_04 §5–6 |
| 9 | Compatibility between two saved charts or a new person; Love / Family / Work; optional 0–100 score (analysis matters more) | FE_06 |
| 10 | Interactive world map with personal lines; pick city or country; 11 goals; city report (overview, lines near + distance, positives, challenges, suitability for travel / living / work / business / love / family); "Where Should I Go?" | FE_07 |
| 11 | Personal calendar: transits, new/full moons, eclipses, retrogrades, personal aspects, favourable and challenging periods; push notifications | FE_08 §2–4, §6 |
| 12 | Best Days for 10 activities | FE_08 §5 |
| 13 | Ask Astrology: AI chat over the user's computed data; the AI never invents positions | FE_09 |
| 14 | Home: "Good morning, [Name]"; Your Day with overall rating + Love / Career / Money / Energy (x/10); Today's Astrology text; quick access My Chart / Today / Compatibility / Astro Map | FE_04 §2 |
| 15 | Menu: Home, My Chart, Forecast (Today/Month/Year), Compatibility, Astro Map, Calendar, Ask Astrology, Profile/My Charts; modern, premium, clean, international look, not esoteric or old-fashioned | F14, FE_01 §3.2, §5 |
| 16 | Backend functions (auth, profiles, subscriptions, payments, engine, PDF, sharing…) | FE_02 (payments/subscriptions out, F4) |
| 17 | The wheel must be generated dynamically from structured chart data, sharp on screen, in PDF and in high-res images | FE_05 §2, §6 |
| 18 | Free/Premium split | ignored (F4) |
| 19 | Later: progressions, electional, business, child astrology, relationship timeline, life timeline, relocation chart | out of scope (§8) |
| 20 | Product principle: the real natal chart underlies every feature | F8, F12 |

Menu mapping (brief §15 → F14): Home → Home tab · My Chart → Chart tab · Forecast (Today/Month/Year) → Ahead tab,
segments Today / Month / Year · Calendar → Ahead tab, segment Calendar (Best Days inside it) · Compatibility → Match
tab · Astro Map → Map tab · Ask Astrology → global button · Profile / My Charts → avatar menu.

## 5. Backend readiness

Legend (used on every endpoint in FE_02): **WRAP** = the data exists in an orchestrator output; the API runs /
caches the orchestrator and reshapes the output (the source file and field are given). **DERIVED** = computed in the
API layer from existing outputs by a deterministic rule given in FE_02. **NEW** = needs backend work beyond wrapping.

| Feature | Status | Notes |
|---|---|---|
| Chart data + wheel | WRAP | `compute_chart` → `chart.json`; wheel ported client-side (F6) |
| Natal reading (17 sections, TR + EN) | WRAP | `l4_output.json` + titles from `l4_render.py` |
| Tap explanations for planet / sign / house / aspect | **NEW** (fallback defined) | FE_05 §3.4 falls back to the matching reading section |
| Day / month / year readings, 3 lenses | WRAP | `reading_<horizon>_<profile>_<date>.json` |
| Daily per-domain paragraphs + "advice" | **NEW**, optional | render-if-present (F13) |
| Life-area bands per day, tone, moon, retrogrades | WRAP | calendar `day_scores.json`, `calendar_<YYYY-MM>.json` |
| x/10 day ratings | DERIVED | band → number mapping (FE_02 §6.2), open decision O3 |
| Solar Return | **NEW** | contract in FE_02 §7.5 |
| Compatibility love / work | WRAP | `synastry_run.py` reading types `personal` / `professional` |
| Compatibility family | **NEW** | no family profile in S3 yet; fallback `general` (O4) |
| Compatibility score | not planned | S3 spec §6 forbids a numeric score (O1) |
| ACG lines, parans, heat layers | WRAP / DERIVED | `acg.geojson`, `acg_parans.geojson`, `goal_heat_<goal>.geojson` |
| City / country / region reports | WRAP | `reading_<lang>.json`, `country_<ISO>.json`, `region_<ID>.json` |
| "Where Should I Go?" | WRAP | `recommend_<goal>_<scope>.json` (ACG_09 + ACG_11) |
| Calendar month / day / periods / year overview | WRAP | `run_calendar.py` views |
| Best Days (10 activities, 90 days) | WRAP | `best_days.json` |
| Notification candidates | WRAP | `notifications.json` |
| Accounts, auth, profile storage, saved reports index | **NEW** | there is no user store today |
| Place search (birthplace autocomplete) | **NEW** | wraps a geocoder + the gazetteer (O7) |
| Ask Astrology | **NEW** | FE_09 contract |
| Label catalogue, config | DERIVED | from the existing TR/EN catalogues |

## 6. Phases and gates

| Phase | Deliverable | Gate |
|---|---|---|
| **0: Exploration + contract** | `FE_EXPLORATION_REPORT.md` (§9), `openapi.yaml` generated from FE_02, `mock-api/` serving every endpoint from the fixture pack, empty app shell building on iOS + Android | Radul reviews the report, `openapi.yaml` and the mock |
| 1: Foundations | design system, navigation shell, i18n, API client + job hook, auth + onboarding + My Charts (FE_01, FE_03) | FE_01 §12 and FE_03 acceptance pass on both platforms |
| 2: Chart | `packages/wheel-core` port (parity tests), interactive wheel, reading, tables, exports and share (FE_05) | wheel parity W1–W4 pass; Radul reviews TR reading layout + a PDF |
| 3: Ahead | Home, Today / Month / Year / Solar Return, Calendar, Best Days, notifications (FE_04, FE_08) | acceptance of both specs |
| 4: Match | compatibility (FE_06) | acceptance |
| 5: Map | map, reports, recommender (FE_07) | acceptance + performance budget on a mid-range Android |
| 6: Ask | assistant chat (FE_09) | acceptance against the scripted mock |
| 7: Hardening | a11y, performance, offline, analytics, store metadata, E2E suite green | FE_01 §12 full pass; TestFlight + internal Play track builds |

Each phase ends with a short report to Radul: what was built, screenshots (TR and EN, light and dark), deviations
from the spec, and contract questions. **Don't adapt the contract silently.** A contract change is proposed in the
report and applied to FE_02 by Radul before code depends on it.

## 7. Open decisions for Radul (defaults apply until answered)

| # | Question | Default used by the specs |
|---|---|---|
| O1 | Compatibility 0–100 score? The brief allows it; S3 §6 forbids a numeric score. | **No score.** `score` stays `null`; the UI hides the block (FE_06 §4). |
| O2 | Home "Energy" tile: there is no energy life area in the 11-goal taxonomy. | **Family** tile instead of Energy until a grounded energy metric exists. |
| O3 | Home and Today "x/10" numbers are a mapping of calendar bands, and calendar calibration is still open (`PROJECT_OVERVIEW` §8.6). | Show the number **and** the band word (FE_02 §6.2 mapping). Flag `dayScoreNumbers` can switch to bands only. |
| O4 | Family compatibility: S3 has no family profile. | `general` reading + family relation stamped in the request; flag `familyCompatibility` on; backend adds a `family` profile later (NEW). |
| O5 | Auth provider. | API-issued JWT (access + refresh) with Sign in with Apple, Google and email one-time code. |
| O6 | Map tiles provider and border point of view (Cyprus and disputed areas matter for the Turkish market, ACG_07 §3). | MapLibre with a vector style from a provider that supports a **Turkey point-of-view** worldview; provider behind config (`MAP_STYLE_URL`). |
| O7 | Birthplace autocomplete provider (Nominatim's usage policy forbids autocomplete; the "Instanbul" run resolved to Antwerp). | Backend proxies a commercial or self-hosted autocomplete (e.g. Photon); the app always shows the resolved place for confirmation (FE_03 §4). |
| O8 | App name, logo, icon. | Placeholders `{{APP_NAME}}`, neutral monogram icon. |
| O9 | Ask Astrology model, tools and daily quota. | Contract in FE_09; quota from `me.ask_quota` (default 30 messages/day). |
| O10 | Analytics vendor. | PostHog (EU cloud), no birth data in events. |
| O11 | Crash reporting. | Sentry with birth-data scrubbing. |

## 8. Out of scope for v1

Payments and subscriptions (F4); brief §19 items (progressions, electional, business and child astrology,
relationship and life timelines, relocation chart as a separate feature); a web app; widgets and watch apps; a
synastry bi-wheel; any "unknown birth time" flow (F9); languages other than TR and EN.

## 9. Inputs the agent receives, and the Phase 0 report

**Inputs:** this spec set; `PROJECT_OVERVIEW.md`; `Chart_wheel/` (spec, `src/*.js`, tests, `render_wheel.py`);
the **fixture pack** listed in FE_02 §11 (prepared by Radul from test charts; person labels anonymised);
`CAL_00`–`CAL_05` and `ACG_07`–`ACG_11` for background on the data (read-only context, not tasks).

**Phase 0 report (`FE_EXPLORATION_REPORT.md`)**, answered with file references and excerpts, no feature code:

1. The exact library versions chosen for every row of FE_01 §1 and any substitution with its reason (e.g. if the
   MapLibre React Native binding or Skia is not compatible with the current Expo SDK / New Architecture).
2. `openapi.yaml` generated from FE_02, plus a list of every ambiguity found while writing it.
3. The wheel port plan: which `Chart_wheel/src` modules are ported verbatim, the TS types, and a first parity run
   (FE_05 §2.5, W1) on the three fixture charts.
4. The mock server: routes, scenario switches (FE_02 §10), and proof that every fixture validates against the zod
   schemas generated from `openapi.yaml`.
5. Font licences and Turkish glyph coverage for the chosen faces (FE_01 §5.3).
6. Anything in these specs that contradicts the fixtures, `Chart_wheel/` or platform constraints. **Flag it; don't
   adapt silently.**
