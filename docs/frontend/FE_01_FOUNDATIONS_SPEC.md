# FE 01: foundations (stack, architecture, design system, rules)

*Applies to every feature spec. Where a feature spec is silent, this file decides.*

## 1. Stack

Use the **current stable Expo SDK with the New Architecture enabled**. Pin exact versions in `package.json` and
report them in the Phase 0 report. A substitution is allowed only with a reason in that report.

| Concern | Library | Notes |
|---|---|---|
| Runtime | Expo (managed workflow + dev builds via EAS), React Native, TypeScript `strict: true`, `noUncheckedIndexedAccess: true` | minimum OS = the chosen Expo SDK's minimums, never lower than iOS 16 / Android 8 (API 26) |
| Navigation | `expo-router` (typed routes) | file-based routes, deep links, universal links |
| Server state | `@tanstack/react-query` + persister | all API data; job polling (§3.4) |
| Local state | `zustand` | session, active profile, UI prefs |
| Storage | `react-native-mmkv` (encrypted instance) + `expo-secure-store` | query cache persistence; tokens and the MMKV key in SecureStore |
| API client | `openapi-typescript` + `openapi-fetch` | types generated from `openapi.yaml` (FE_02); no hand-written fetch in screens |
| Validation | `zod` (schemas generated from `openapi.yaml`) | validate every response at the client boundary in dev and staging builds; log contract violations to Sentry |
| Graphics | `react-native-svg` | wheel, glyphs, charts |
| Rasterisation | `@shopify/react-native-skia` | SVG → PNG/JPG at arbitrary resolution for exports (FE_05 §6) |
| Map | `@maplibre/maplibre-react-native` | vector base map + GeoJSON layers (FE_07) |
| Gestures / motion | `react-native-gesture-handler`, `react-native-reanimated` | |
| Sheets | `@gorhom/bottom-sheet` | place reports, detail sheets |
| i18n | `i18next`, `react-i18next`, `i18next-icu`, `expo-localization` | §4 |
| Dates | `date-fns` + `@date-fns/tz` (or `date-fns-tz`), `tr` locale | §8 |
| Notifications | `expo-notifications`, `expo-background-task` | local scheduling (FE_08 §6) |
| Export / share | `expo-print`, `expo-sharing`, `expo-media-library`, `react-native-view-shot` | FE_05 §6 |
| Auth | `expo-apple-authentication`, `@react-native-google-signin/google-signin` | FE_03 §2 |
| Location (optional) | `expo-location` | "use my current location" only |
| Streaming | `expo/fetch` (streaming body) | Ask Astrology SSE (FE_09); fallback: `react-native-sse` |
| Icons | `lucide-react-native` for UI icons; astro glyphs come from `packages/wheel-core` | never Unicode astro characters, never astro fonts |
| Crash reporting | `@sentry/react-native` | scrubbing rules §10 |
| Analytics | PostHog (EU) | §10.3 |
| Tests | `jest-expo`, `@testing-library/react-native`, Maestro (E2E) | §11 |
| Lint / format | ESLint (typescript-eslint, react-hooks), Prettier, `i18next-parser` | CI gates §11 |

## 2. Repository layout

```
app/                                expo-router routes (§3.2)
src/
  api/
    schema.d.ts                     generated from openapi.yaml (never edited by hand)
    client.ts                       openapi-fetch instance: base URL, auth, lang, retries, 401 refresh
    zod/                            generated schemas + validate() helper
    jobs.ts                         job polling (§3.4)
    hooks/                          one hook per resource: useMe, useProfiles, useChart, useNatalReading,
                                    useDayForecast, useMonthForecast, …  (screens only use these)
    keys.ts                         query-key factory
  features/
    onboarding/ account/ profiles/ home/ chart/ forecast/ calendar/ bestdays/
    compatibility/ map/ ask/ reports/
  design/
    tokens.ts                       §5 tokens (light + dark)
    theme.tsx                       ThemeProvider, useTheme()
    typography.ts
    components/                     §5.6 inventory
  i18n/
    index.ts  tr.json  en.json  catalogue-fallback.{tr,en}.json
  lib/
    dates.ts                        tz-aware "today", formatting (§8)
    deeplinks.ts                    route builders + notification deep-link mapping
    notifications.ts                local scheduling (FE_08 §6)
    export/                         PDF HTML templates, share-card views, rasteriser
    analytics.ts  sentry.ts  flags.ts
packages/
  wheel-core/                       TS port of Chart_wheel/src (FE_05 §2) + tests + fixtures
mock-api/                           FE_02 §10
e2e/                                Maestro flows
```

Rules:
- Screens import from `src/api/hooks`, `src/design`, `src/features/*`, never from `src/api/client` directly.
- Feature folders own their components; shared components move to `src/design/components` only when used by 2+ features.
- No business logic in route files: a route file renders one feature screen component.

## 3. Architecture

### 3.1 Providers (root `_layout.tsx`)

`SafeAreaProvider` → `ThemeProvider` → `I18nProvider` → `QueryClientProvider` (+ persister) → `AuthGate` →
`BottomSheetModalProvider` → `Stack`. The `AuthGate` routes to `(auth)` when signed out, to `(onboarding)` when the
self profile does not exist yet, else to `(tabs)`.

### 3.2 Navigation map

```
app/
  _layout.tsx
  (auth)/          welcome · sign-in · verify-code
  (onboarding)/    language · consent · name · birth-date · birth-time · birth-place · current-place
                   · details (gender) · notifications · building
  (tabs)/
    _layout.tsx    5 tabs, global Ask button in each tab header (right), avatar (left)
    index.tsx                  Home                         FE_04 §2
    chart/index.tsx            My Chart                     FE_05
    ahead/_layout.tsx          top segmented control: Today | Month | Year | Calendar
    ahead/today.tsx  ahead/month.tsx  ahead/year.tsx  ahead/calendar.tsx
    match/index.tsx            Compatibility home           FE_06
    map/index.tsx              Astro map                    FE_07
  chart/section/[key].tsx      one reading section (deep-linkable)
  forecast/month/[month].tsx   a specific month (from Year "month by month")
  solar-return/[year].tsx      FE_04 §6
  calendar/day/[date].tsx  calendar/item/[id].tsx  calendar/periods.tsx  calendar/year.tsx
  best-days/index.tsx  best-days/[activity].tsx  best-days/[activity]/[date].tsx
  match/new.tsx  match/[id].tsx
  map/country/[iso].tsx  map/region/[id].tsx  map/recommend.tsx  map/recommend/result.tsx
  ask/index.tsx  ask/[threadId].tsx                         (modal stack)
  profile/index.tsx  profile/charts/index.tsx  profile/charts/new.tsx  profile/charts/[id].tsx
  profile/settings.tsx  profile/notifications.tsx  profile/reports.tsx  profile/privacy.tsx  profile/about.tsx
```

Proposed tab labels (native review required, §4.5): TR **Ana Sayfa · Haritam · Öngörü · Uyum · Yerler**,
EN **Home · Chart · Ahead · Match · Map**. ("Harita" means both chart and map in Turkish, so the map tab is
"Yerler" / Places.)

**Active profile.** A global `activeProfileId` (default: the self profile). Chart, Ahead and Map show a
`ProfileSwitcher` chip in the header; switching changes the data of that tab only for the session. Home always
shows the self profile. Match picks its two people explicitly.

**Deep links.** Scheme `{{APP_SCHEME}}://` and universal links `https://{{APP_DOMAIN}}/…` resolve to the same
paths. Notification deep links map as in FE_08 §6.4.

### 3.3 Data layer

- One hook per resource in `src/api/hooks`. Query keys come from `keys.ts` and always include `profile_id`, `lang`
  and every request parameter.
- **Language is part of every key.** Switching language refetches; cached entries of the other language are kept.
- Stale / cache policy:

| Resource | staleTime | Persist offline |
|---|---|---|
| `me`, profiles, catalogue, config | 5 min | yes |
| chart data | ∞ (key includes `chart_key`) | yes |
| any generated reading (natal, month, year, compatibility, place, recommendation, solar return) | ∞ | yes |
| day forecast, home | until local midnight in `me.current_place.tz` | yes |
| calendar month, periods, best days, notification candidates | 12 h | yes |
| map lines, heat layers | ∞ (key includes `chart_key`) | yes (lines); heat: last 3 goals |
| Ask threads | 0 (always refetch) | messages of the last 20 threads |

- `chart_key` changes when birth data changes. Editing a profile invalidates every key containing its `profile_id`.
- Mutations (`POST`/`PATCH`/`DELETE`) invalidate the affected keys explicitly; no optimistic updates for birth data.

### 3.4 Jobs (async generation)

FE_02 §4 defines the pattern: a generated resource answers `200` (ready) or `202` with a `Job`, and composite
resources embed `GeneratedPart` blocks that can be `pending`. Implement it once:

- `useGenerated(key, fetcher)` returns `{ data, job, state }` with `state ∈ loading | pending | ready | failed | absent`.
- Polling: `GET /v1/jobs/{job_id}` after 1 s, 2 s, 3 s, then every 4 s. On `succeeded` refetch the parent resource.
  On `failed` show the failed state with **Retry** (re-requests the resource with `?retry=true`).
- Polling pauses when the app is backgrounded or the screen unmounts and resumes on focus. A job id is persisted
  with the query so a returning user sees progress, not a restart.
- After 3 min show "This is taking longer than usual" and keep polling to 10 min; then show the failed state.
- Pending UI: the `JobProgress` component (§5.6) lists `job.stages` with friendly labels (FE_02 §4.3) and elapsed
  time. It never shows a percentage it cannot know.
- **Never block navigation** on a job. When a job finishes while the user is elsewhere in the app, show a toast
  ("Your reading for İzmir is ready" / "İzmir yorumunuz hazır") that deep-links to it.

### 3.5 Errors

`Problem` responses (FE_02 §5) map to UI states (§7). 401 → one silent refresh, then sign-out to `(auth)`. 429 →
honour `Retry-After`. Network errors → offline state with cached data if present. Each screen has an error
boundary that reports to Sentry and offers "Try again".

### 3.6 Feature flags

`src/lib/flags.ts` reads `GET /v1/meta/config` (FE_02 §8.2) with bundled defaults:

| Flag | Default | Controls |
|---|---|---|
| `askAstrology` | on | FE_09 entry points |
| `solarReturn` | on | FE_04 §6 |
| `familyCompatibility` | on | family type in FE_06 (O4) |
| `compatibilityScore` | off | score block (O1) |
| `homeEnergyTile` | off | Energy tile instead of Family (O2) |
| `dayScoreNumbers` | on | x/10 numbers next to bands (O3) |
| `elementNotes` | on | tap explanations from `/chart/elements`; off → section fallback (FE_05 §3.4) |
| `showTraces` | off | dev menu only (C4) |

A `NEW` backend feature ships behind its flag; the flag turns on when the endpoint is live.

## 4. Internationalisation

### 4.1 Languages
`tr` (default) and `en`. First launch: `tr` if the device language is Turkish, otherwise `en`. The user confirms
it on the first onboarding screen. The choice is saved to `me.language` and sent as `lang` on every request.

### 4.2 What the app owns vs the API
- The **API** supplies every astrological label and text in the requested language: section titles, planet / sign /
  aspect / house names, goal and band labels, activity names, event labels, notification texts, footers.
  The app caches `GET /v1/meta/catalogue` (FE_02 §8.1) and ships `catalogue-fallback.{tr,en}.json` (a build-time
  snapshot) for offline first launch.
- The **app** owns UI chrome: buttons, headings, empty states, settings, onboarding copy, errors, stage labels.

### 4.3 Rules
- No string concatenation to build sentences. Turkish suffixes change with the word (vowel harmony, apostrophes:
  "Güneş'in", "Ay'ın"), so full-sentence keys only; variables only for names, numbers and dates, and never followed
  by a suffix in Turkish (rephrase instead: "Yorum hazır: {place}", not "{place} yorumu hazır").
- Plurals via ICU (`{count, plural, one {…} other {…}}`).
- Casing: `toLocaleUpperCase('tr-TR')` / `toLocaleLowerCase('tr-TR')` in Turkish (i → İ, ı → I). Axis labels
  (AC/DC/MC/IC) stay Latin abbreviations as the wheel spec requires.
- Sorting: `Intl.Collator('tr')` / `('en')`.
- Numbers: `Intl.NumberFormat(lang)`; degrees as `6°56′` (degrees + minutes, tabular numerals).
- User-entered names are never translated or re-cased.

### 4.4 Catalogue of fixed UI glossary (chrome only)
| Concept | TR | EN |
|---|---|---|
| natal chart | Doğum haritası | Birth chart |
| reading | Yorum | Reading |
| life area | Yaşam alanı | Life area |
| lens (general / love / work) | Genel · Aşk ve ilişkiler · İş ve kariyer | General · Love & relationships · Work & career |
| best days | En İyi Günler | Best Days |
| where should I go? | Nereye gitmeliyim? | Where should I go? |
| my charts | Haritalarım | My Charts |
| ask astrology | Astrolojiye sor | Ask Astrology |

### 4.5 Review
All `tr.json` strings are reviewed by a native Turkish speaker (Radul's team) at the Phase 1 gate. Register:
**"sen"** (informal second person), matching the calendar text register (`PROJECT_OVERVIEW` §2 calendar validator).

## 5. Design system

### 5.1 Direction
Extend the wheel's locked aesthetic (`CHART_WHEEL_SPEC.md` §7, "quiet modern-minimal") to the whole app:
**calm, hairline, one accent, editorial reading.** Premium through restraint and typography, not decoration.
International and modern (brief §15). **Not esoteric:** no starfields, nebulae, purple-to-pink gradients, glitter,
tarot or crystal imagery, zodiac clip-art or mascots. The only astrological imagery is the wheel and the vector
glyph set from `wheel-core`.

The accent is the Iznik indigo. The semantic scale for "supportive ↔ challenging" borrows the Iznik tile palette
(tile green, saffron, bole red): culturally resonant for the Turkish market without being folkloric.

### 5.2 Colour tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | `#FAFAF8` | `#1A2030` | app background (= wheel ground) |
| `surface` | `#FFFFFF` | `#222A3C` | cards, sheets |
| `surfaceAlt` | `#F3F3EF` | `#283146` | grouped rows, inputs |
| `ink` | `#232A38` | `#E7E9EE` | primary text, glyphs |
| `ink2` | `#4A5163` | `#B4BAC6` | secondary text |
| `ink3` | `#6B7180` | `#8A91A0` | tertiary text (≥ 14 pt only) |
| `hair` | `#DEDED7` | `#3A4256` | hairlines, dividers, borders |
| `accent` | `#2E4A7D` | `#7FA0D8` | primary actions, selection, links, the aspect hub |
| `accentSoft` | `#E8EDF5` | `#26324A` | selected chip background |
| `onAccent` | `#FFFFFF` | `#1A2030` | text on accent |
| `danger` | `#962F22` | `#E07A60` | destructive actions only |

**Semantic band scale** (one scale for every "supportive ↔ challenging" value in the app):

| Level | API values mapped to it | Light | Dark | Icon |
|---|---|---|---|---|
| `strongPlus` | `strongly_supportive`, grade `excellent` | `#2F6B5A` | `#7CC4AD` | double chevron up |
| `plus` | `supportive`, tone `favorable`, grade `good` | `#4F9A84` | `#5FAF97` | chevron up |
| `mixed` | `mixed` | `#A8761E` | `#E0A94E` | up-down |
| `neutral` | `quiet`, `no_emphasis`, grade `neutral` | `#8A8D84` | `#9CA0A8` | dash |
| `minus` | `challenging`, tone `challenging`, grade `avoid` | `#C0583F` | `#E07A60` | chevron down |
| `strongMinus` | `strongly_challenging` | `#962F22` | `#D9644F` | double chevron down |

Colour is never the only channel: band chips always carry the icon and the API label. Unknown API band values map
to `neutral` (and are logged).

**Map planet line colours** (FE_07; validate ≥ 3:1 against the final base map, adjust hue not role):

| Body | Light | Dark |
|---|---|---|
| sun | `#A67C00` | `#E7B93A` |
| moon | `#7D8BA3` | `#A9B5C9` |
| mercury | `#2E9A93` | `#4FC2BA` |
| venus | `#C9658F` | `#E48DB2` |
| mars | `#C8452F` | `#E86A52` |
| jupiter | `#6A4FB3` | `#9C86E0` |
| saturn | `#7A6848` | `#B8A27A` |
| uranus | `#2F8FD8` | `#5DB0F0` |
| neptune | `#1F5FA0` | `#5A8FD6` |
| pluto | `#3B3B40` | `#D6D6DC` |

The wheel keeps its own tokens from `wheel-core/theme` (light and dark presets); the app theme passes its `bg` so
they match.

### 5.3 Typography
- **UI:** Inter (the wheel's face). **Long-form reading:** Source Serif 4. Both open-licensed (OFL); Phase 0
  confirms Turkish coverage (ç ğ ı İ ö ş ü, â î û) and bundles the fonts with `expo-font`.
- Scale (size/line-height, pt): `display` 32/38 Inter SemiBold · `title1` 24/30 SemiBold · `title2` 20/26 SemiBold ·
  `headline` 17/22 SemiBold · `body` 16/24 Regular · `callout` 15/21 · `caption` 13/18 · `overline` 12/16 Medium,
  letter-spacing 1.2, locale uppercase · `reading` 18/29 Source Serif 4 Regular, paragraph gap 14.
- Tabular numerals for degrees, dates and scores.
- Dynamic Type / font scale supported up to 200% on reading text and 160% on chrome (layouts must wrap, not clip).

### 5.4 Layout
4-pt grid; spacing tokens 4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 56. Screen gutter 20. Radii: chips full, controls 12,
cards 16, sheets 24. Hairline borders instead of shadows; only sheets and the floating Ask button have a soft shadow.
Reading column max width 640 pt (tablets centre it).

### 5.5 Motion
200–300 ms, standard easing; no parallax, no looping ambient animation. The first reveal of a chart animates
rings → houses → planets → aspects in ≤ 2.5 s, skippable by tap. Respect Reduce Motion (cross-fade only).

### 5.6 Component inventory (`src/design/components`)
Buttons (primary, secondary, tertiary, destructive; loading state) · IconButton · Chip (filter, choice) · `BandChip`
(level icon + API label) · `GradeChip` · `ScoreMeter` (x/10 + band, §FE_04) · SegmentedControl · Card · ListRow ·
SectionHeader · `ReadingSection` (title, paragraphs, collapse, "copy" and "share section") · `ReadingText`
(serif, selectable, splits paragraphs on blank lines) · `JobProgress` · Skeleton (per layout) · EmptyState ·
`AbsenceNotice` · ErrorState · `StaleBadge` (offline / cached) · BottomSheet · `ProfileSwitcher` · `PlaceSearchField` ·
DateField / TimeField (native pickers, 24-hour) · `Glyph` (planet, sign, aspect, angle from wheel-core) · Legend ·
Toast · Coachmark · `DisclaimerFooter` · `MonthGrid` / `DayCell` · `TimelineBar` · `AskButton` (floating / header).
Every component has light + dark, TR + EN, and large-font stories in a Storybook-style gallery screen (dev builds only).

## 6. Content rules (UI)

| # | Rule |
|---|---|
| C1 | Never render an empty section, title without text, or placeholder. Absent sections are omitted (the backend's own rule). |
| C2 | `text: null` means **label only by design** (calendar and Best Days units without grounding). Show the label and dates; no "text coming soon". |
| C3 | Texts are plain text. Split paragraphs on blank lines (`\n\n`). No Markdown rendering. Keep the API's typography (curly quotes). |
| C4 | Never show trace / principle ids, record ids, model names, run ids, schema versions, raw scores (`S`, `P`, `N`, `R`, `I`, `A`, `peak_S`, contributions) in production UI. The dev menu flag `showTraces` shows traces under paragraphs for QA. |
| C5 | Tradition mask (F7). CI fails if `tr.json` / `en.json` contain a forbidden term (case-insensitive, Turkish-aware): modern, klasik, classical, traditional, geleneksel, Osmanlı, Ottoman, Arap, Arabic, Hellenistic, whole sign, tam burç, Placidus, ev sistemi, house system, triplicity, üçlük, dignity, asalet, domicile, detriment, exaltation, yücelim, fall, düşüş, bound, term, face, decan, dekan, sect, Lot, Spirit, Fortune, planetary day, planetary hour, time lord, profection. (Allow-list the ordinary words "fall" and "face" only where they are not astrological, reviewed case by case.) |
| C6 | Disclaimers: API footers are shown verbatim (ACG). A general line appears in onboarding and About: TR "Bu uygulama öz-farkındalık içindir; tıbbi, hukuki veya finansal tavsiye değildir." EN "This app is for self-reflection, not medical, legal or financial advice." |
| C7 | Numbers the UI may show: dates, times, degrees and minutes on chart facts, rounded distances with "≈" (FE_07), day counts, grades, `score_10` where FE_02 provides it. Nothing else. |
| C8 | The client never interprets (F8). Chrome may say "Sun · 6°56′ Capricorn · 9th house"; it may not add meaning. |
| C9 | Sensitive themes: the app adds no warnings or softening of its own around API text; the backend validators own that. |
| C10 | Every generated text block offers **Copy** and **Share** (as plain text with the app name and a link) via a long-press or "…" menu. |

## 7. Screen states

Every data view implements these states with the shared components:

| State | When | UI |
|---|---|---|
| loading | first fetch, nothing cached | layout skeleton (not a spinner) |
| partial | deterministic data ready, a `GeneratedPart` pending | render data; text area shows `JobProgress` inline |
| pending | the whole resource is a job (`202`) | full `JobProgress` card; the rest of the app stays usable |
| ready | | |
| absent | `status: "absent"` or `Problem.code = "absent"` | `AbsenceNotice` with reason copy (table below) |
| empty | a valid empty list (e.g. no events this day) | quiet one-line EmptyState, no illustration |
| failed | job failed / `generation_failed` | ErrorState + Retry |
| error | network / 5xx | ErrorState + Retry; cached data if any with `StaleBadge` |
| offline | no network | cached data + `StaleBadge` ("Last updated 14:05") |

Absence copy (chrome strings; reason codes from FE_02 §5.2):

| Reason | TR | EN |
|---|---|---|
| `time_not_exact` | Bu bölüm için kesin doğum saati gerekiyor. Profilde doğum saatini düzenleyebilirsin. | This needs an exact birth time. You can edit it in the profile. |
| `placidus_undefined_high_latitude` | Kutuplara çok yakın yerlerde evler hesaplanamaz; bu yer için yalnızca çizgiler gösteriliyor. | Houses can't be calculated this close to the poles, so this place shows lines only. |
| `no_grounding`, `acg_corpus_missing` | Bu metin şu anda hazırlanamadı. | This text couldn't be prepared right now. |
| `place_not_found` | Bu yeri bulamadık. Listeden seçmeyi dene. | We couldn't find that place. Try choosing from the list. |
| unknown | Bu içerik şu anda kullanılamıyor. | This isn't available right now. |

## 8. Dates and time zones

- `lib/dates.ts` exposes `todayLocal(): ISODate` computed in `me.current_place.tz` (F10), `nowInTz()`, and formatters.
  In non-production builds `todayLocal()` honours the mock clock (`X-Mock-Today`, FE_02 §10) so dated fixtures work.
- API local dates (`YYYY-MM-DD`) and local times (`HH:mm`, including `"24:00"` as end of day) are **plain values**:
  never parse them through the device timezone. Format them with the `tr`/`en` locale ("30 Eylül 2026, Çarşamba").
- UTC timestamps (a few fields end in `_utc`) are converted to `me.current_place.tz` for display.
- When the device timezone differs from `me.current_place.tz` for more than 24 h, show a one-time banner: "You seem to
  be in a different time zone. Update your current location?" → FE_03 §6.
- Viewing another profile (active profile ≠ self): dates use the **viewer's** `current_place.tz` unless that profile
  has its own `current_place` (FE_02 §7.1).

## 9. Accessibility

WCAG 2.2 AA: text contrast ≥ 4.5:1 (tokens in §5.2 comply), non-text ≥ 3:1, touch targets ≥ 44 × 44 pt, full
VoiceOver / TalkBack labels, logical focus order, no information by colour alone. The wheel and the map each have a
complete non-visual alternative (Planets / Houses / Aspects lists; lines list). Respect Reduce Motion, Bold Text and
font scaling (§5.3).

## 10. Security, privacy, telemetry

### 10.1 Data
Birth data is personal data under KVKK (Turkey) and GDPR. Tokens and the MMKV encryption key live in SecureStore.
No birth data (dates, times, places, names of saved people) in logs, analytics, Sentry breadcrumbs or crash
payloads: scrub request/response bodies and URLs containing `/profiles/` parameters.

### 10.2 Consent
Explicit consent for processing birth data (onboarding, FE_03 §3.2) with links to the privacy notice and terms
(legal text supplied by Radul). Account deletion and data export are in-app (FE_03 §7).

### 10.3 Analytics events (no personal data)
`app_open`, `onboarding_step {step}`, `onboarding_complete`, `screen_view {route}`, `reading_open {kind, section?}`,
`lens_change {kind, lens}`, `export {kind: png|jpg|pdf_chart|pdf_report|share_card}`, `share {target?}`,
`compat_create {type}`, `map_layer {goal}`, `place_report_open {kind: city|country|region}`,
`recommend_run {goal, scope}`, `best_days_open {activity}`, `notification_open {type}`, `ask_send`, `ask_feedback {rating}`,
`job_wait {kind, seconds}` (reports real generation latency).

## 11. Testing and CI

| Layer | What |
|---|---|
| Unit | dates/tz helpers, deep-link mapping, notification scheduler (caps, quiet hours), band mapping, job hook state machine |
| Contract | every mock fixture validates against the zod schemas; CI fails on drift between `openapi.yaml` and `schema.d.ts` |
| Wheel | `packages/wheel-core` parity tests (FE_05 §2.5) |
| Component | RNTL tests for each shared component in each state; TR + EN |
| E2E (Maestro, against the mock) | onboarding → home; open natal reading + tap Sun; month forecast lens switch; compatibility create → report; map city report; recommender; calendar day; Best Days activity; Ask message stream; PNG + PDF export; notification deep link |
| Static | `tsc --noEmit`, ESLint, Prettier, `i18next-parser` (no missing / unused keys in either language), C5 forbidden-term scan |

EAS profiles: `development` (mock API default), `preview` (staging API), `production`. The API base URL and
`MAP_STYLE_URL` come from EAS environment variables; a dev menu (shake) switches mock / staging in non-production builds.

## 12. Acceptance (foundations)

| # | Check |
|---|---|
| FA1 | App builds and runs on iOS and Android (dev + preview profiles); cold start < 2.5 s on a mid-range Android (e.g. Galaxy A54) in the preview build. |
| FA2 | Theme: every shared component renders correctly in light and dark; contrast checks pass (§5.2). |
| FA3 | i18n: switching TR ↔ EN updates chrome and refetches API text; no missing keys; Turkish casing test (`"istanbul".toLocaleUpperCase('tr-TR') === "İSTANBUL"`) passes in the formatter layer. |
| FA4 | C5 scan passes; a seeded forbidden term makes CI fail. |
| FA5 | Job hook: a mocked `202` resource shows `JobProgress`, survives app backgrounding and navigation, and resolves to ready; a failed job shows Retry; a 10-min timeout shows failed. |
| FA6 | Offline: with the network off, previously opened readings and today's forecast render from cache with `StaleBadge`. |
| FA7 | Accessibility: VoiceOver and TalkBack can reach every control on Home, My Chart (via lists), Map (via lines list); font scale 200% causes no clipped text on reading screens. |
| FA8 | No personal data in analytics or Sentry payloads (inspect a captured event and a forced crash). |
