# UX screen inventory

Date: 2026-11-06. Source: `frontend/app/**` routes and the feature screens they render under `frontend/src/features/**`. No device run. Feature flags left unchanged.

## Legend

| Column | Meaning |
| --- | --- |
| Back | `back` = `router.back()` (fallback `/`); `none` = tab/root; `replace` = route replace; `close` = sheet dismiss via back |
| Loading | Shared `Skeleton` / `JobProgress` / raw `ActivityIndicator` / ad-hoc / GAP |
| Empty | Shared `EmptyState` (none yet) / ad-hoc i18n key / GAP |
| Error | Shared `ErrorNotice` / ad-hoc / GAP |
| Offline | Explicit banner, via `ErrorNotice` when fetch fails, or GAP |
| Shared | Which shared building blocks the screen already uses |
| Gap | Missing state or inconsistent pattern |

Shared components today: `Screen`, `Skeleton`, `ErrorNotice`, `JobProgress`, `Generated`, `RouteError` (boundary). **No** dedicated `EmptyState` or unified offline banner. `LockedFeature` exists but is unused by screens.

## Inventory

| Route | Title | Back | Loading | Empty | Error | Offline | Success | Shared | Gaps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `/(tabs)` | greeting / `home` | none | Skeleton | none | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | No dedicated empty home |
| `/(tabs)/chart` | profile label | none | Skeleton | ad-hoc missing profile | ErrorNotice | banner `offline` | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | Offline is ad-hoc Txt, not shared |
| `/(tabs)/ahead` | date range | none | Skeleton | ad-hoc `noTransits` | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | Empty ad-hoc |
| `/(tabs)/match` | `whoFits` / `match` | none | Skeleton | ad-hoc `emptyCompatibility` | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty ad-hoc |
| `/(tabs)/map` | ProfileSwitcher | none | Skeleton | ad-hoc `noResults` | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty ad-hoc |
| `/(auth)/welcome` | app name / guest | none | ad-hoc | none | ErrorNotice | ErrorNotice | navigate | Screen, ErrorNotice | Loading not Skeleton |
| `/(auth)/link` | email/google title | back | ad-hoc | none | ErrorNotice | ErrorNotice | navigate | Screen, ErrorNotice | Loading not Skeleton |
| `/(auth)/core` | guest preparing | none | ActivityIndicator | ad-hoc guest expired | ErrorNotice | ErrorNotice | content | Screen, ErrorNotice | Loading not shared Skeleton/JobProgress |
| `/(auth)/unlocked` | guest unlocked | replace | none | none | **GAP** | none | navigate | Screen | No error surface |
| `/(onboarding)/[step]` | step titles | back | JobProgress (building) | none | ErrorNotice | ErrorNotice | navigate | Screen, ErrorNotice, JobProgress | Consent draft copy (expected) |
| `/ask` | `ask` | back (modal) | Skeleton | **GAP** | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty thread list |
| `/ask/[threadId]` | subject / `ask` | back (modal) | Skeleton | ad-hoc starters | ErrorNotice | banner `offline` | content / stream | Screen, Skeleton, ErrorNotice | Offline ad-hoc; failed msg uses `error` (= connection copy) even for busy |
| `/chart/focus` | profile label | back | Skeleton | none | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | — |
| `/chart/export` | `exportShare` | back (modal) | Skeleton | none | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | — |
| `/chart/reading` | profile / reading | back | JobProgress | ad-hoc missing profile | ad-hoc / JobProgress | **GAP** | content | Screen, Skeleton, JobProgress | Failures via JobProgress; weak offline |
| `/chart/section/[key]` | profile label | back | JobProgress | ad-hoc missing section | ad-hoc | **GAP** | content | Screen, Skeleton, JobProgress | Same as reading |
| `/profile` | `profile` | back | **GAP** | none | ErrorNotice | ErrorNotice | content | Screen, ErrorNotice | Blank while me loads |
| `/profile/settings` | `settings` | back | **GAP** | none | ErrorNotice | ErrorNotice | content | Screen, ErrorNotice | Blank while me loads |
| `/profile/location` | `currentLocation` | back | **GAP** | none | ErrorNotice | ErrorNotice | navigate | Screen, ErrorNotice | — |
| `/profile/privacy` | `privacy` | back | **GAP** | none | ErrorNotice | ErrorNotice | content | Screen, ErrorNotice | Consent shown; **no withdraw** |
| `/profile/about` | `about` | back | none | none | ErrorNotice | none | content | Screen, ErrorNotice | Hardcoded attribution EN |
| `/profile/notifications` | `notifications` | back | **GAP** | none | ErrorNotice | ErrorNotice | content | Screen, ErrorNotice | Blank until details |
| `/profile/reports` | `savedReports` | back | Skeleton | ad-hoc `emptyReports` | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty ad-hoc |
| `/profile/subscription` | `subscriptionTitle` | back | ActivityIndicator | none | ErrorNotice | ErrorNotice | content | Screen, ErrorNotice | Loading not Skeleton |
| `/profile/charts` | `myCharts` | back | Skeleton | **GAP** | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty profiles |
| `/profile/charts/new` | `addPerson` | back | Skeleton | none | ErrorNotice | ErrorNotice | navigate | Screen, Skeleton, ErrorNotice | — |
| `/profile/charts/[id]` | profile label | back | Skeleton | ad-hoc missing | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | — |
| `/forecast/month/[month]` | month string | back | Skeleton | none | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | — |
| `/solar-return/[year]` | `solar_return`+year | back | Skeleton | none | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Flag-gated |
| `/calendar` | `calendar` | back | Skeleton | **GAP** | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty month |
| `/calendar/year` | `yearOverview` | back | Skeleton | **GAP** | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty year |
| `/calendar/periods` | `periods` | back | Skeleton | **GAP** | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty periods |
| `/calendar/day/[date]` | formatted date | back | Skeleton | none | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | — |
| `/calendar/item/[id]` | item / `calendar` | back | Skeleton | none | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | — |
| `/best-days` | `bestDays` | back | Skeleton | **GAP** | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty activities |
| `/best-days/[activity]` | activity / `bestDays` | back | Skeleton | **GAP** | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Empty days |
| `/best-days/[activity]/[date]` | activity | back | Skeleton | none | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | — |
| `/match/new` | `newCompatibility` | back | ad-hoc | none | ErrorNotice | ErrorNotice | navigate | Screen, ErrorNotice | Profile load placeholder |
| `/match/[id]` | people labels | back | Skeleton | none | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | — |
| `/match/family` | **hardcoded** “Family Compatibility” | back | Skeleton | none | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | Title not i18n |
| `/map/recommend` | `whereShouldIGo` | back | none | none | ad-hoc (search) | **GAP** | navigate | Screen | No screen-level offline/error |
| `/map/recommend/result` | goal / recommend | back | Skeleton | ad-hoc thin result | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | — |
| `/map/place/[placeId]` | place / reading | close | Skeleton | ad-hoc relocation | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | — |
| `/map/point` | place / reading | close | Skeleton | ad-hoc relocation | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | — |
| `/map/area/[areaId]` | area / report | close | Skeleton | **GAP** | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | Empty lines |
| `/map/line/[body]/[angle]` | body·angle | close | Skeleton | ad-hoc `noResults` | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice | — |
| `/map/full` | report-dependent | back | Skeleton | inherits | ErrorNotice | ErrorNotice | content + JobProgress | Screen, Skeleton, ErrorNotice, JobProgress | Same empty gaps |
| `/paywall` | `paywallTitle` | back | ActivityIndicator | ad-hoc `paywallNoProducts` | ErrorNotice | ErrorNotice | navigate | Screen, ErrorNotice | Flag-gated; empty products until owner config |
| `/gallery` | `gallery` | back | JobProgress | none | ErrorNotice | ErrorNotice | content | Screen, Skeleton, ErrorNotice, JobProgress | Dev-only |
| `/design-system-gallery` | Design System Gallery | none | ActivityIndicator | none | **GAP** | none | content | Screen | Dev-only; font-load failure |

Redirect-only (no UI inventory): `/`, `/ahead/today`, `/ahead/calendar`, `/forecast/year`.

## Cross-cutting gaps (flagged)

1. **No `EmptyState` component** — lists and zero-data screens use ad-hoc `Txt` or omit empty entirely.
2. **No standard offline component** — only Chart + Ask show an offline banner; others rely on `ErrorNotice` after a failed fetch (or show cached data silently).
3. **`LockedFeature` unused** — `premium_required` renders as `ErrorNotice` without upgrade CTA.
4. **Ask busy → connection copy** — stream failures set message status `failed`, which renders `t("error")` (“Check your connection…”) even when `ErrorNotice` correctly shows `errorBusy`.
5. **503 / timeout** — both collapse to generic `errorServer` in `describeError`; not distinct friendly states.
6. **Consent withdraw** — privacy shows accepted timestamp + version is stored on accept; no withdraw control.
7. **Hardcoded user-visible strings** — `/match/family` title; About attribution block; some gallery/dev labels.
8. **Account screens loading** — profile/settings/privacy/notifications can render blank until `me` resolves (no Skeleton).
9. **Job leave/return** — `leavePreparing` copy + `JobLifecycle` snackbar exist; confirm per job-starting screen in item 4.
10. **Tablet layout** — no adaptive layouts decided (item 8).

## Shared-component adoption target

After items 2–3:

| Component | Role |
| --- | --- |
| `EmptyState` | title + optional body + optional CTA; i18n keys only |
| `ErrorNotice` (standard error/retry/offline) | single surface for offline, 429+Retry-After, 503, timeout, premium_required, busy, generation errors |
| `LockedFeature` | premium lock with clear lock UI (when payments UI flag on) |
| `Skeleton` / `JobProgress` | loading / queued / running / failure / paused |

## Offline expectation (draft for item 5)

| Works offline (cached) | Disabled offline |
| --- | --- |
| Previously loaded chart, forecasts, calendar, reports, match readings | New generation, Ask send, purchase/restore, place search, map tiles (outline preview only), sign-in, onboarding submit |

Per-screen offline matrix and tests belong on the offline branch.
