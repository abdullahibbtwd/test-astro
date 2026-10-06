# FE 02: API contract (v1)

*The single interface between the app and the backend. Derived from real run outputs (listed per endpoint).
Phase 0 turns this file into `openapi.yaml`; from then on `openapi.yaml` is the source of truth for code, and this
file for intent. A change goes through Radul (FE_00 §6).*

## 1. Scope and legend

Every endpoint carries a backend status:

| Status | Meaning |
|---|---|
| **WRAP** | The data exists in an orchestrator output. The API runs (or reuses the cache of) the orchestrator and reshapes the output. The source file and fields are named. |
| **DERIVED** | Computed in the API layer from existing outputs by the deterministic rule given here. |
| **NEW** | Needs backend work beyond wrapping. The contract is fixed here so the app can be built against the mock. |

The API layer normalises ids (§6.1), picks the requested language, strips masked and internal fields, and never
adds interpretation of its own.

## 2. Conventions

| Topic | Rule |
|---|---|
| Base URL | `https://api.{{APP_DOMAIN}}/v1` (mock: `http://localhost:4010/v1`) |
| Auth | `Authorization: Bearer <access_token>` on everything except `/auth/*`, `/meta/*`, `/geo/*` |
| Language | query `lang=tr\|en` on every endpoint that returns human-readable text; **every** human-readable string in the response is in that language (single string, not `{tr, en}` pairs). Missing `lang` → `me.language`. |
| Content type | `application/json; charset=utf-8`; SSE for Ask (`text/event-stream`) |
| Dates | `ISODate` = `YYYY-MM-DD`, a **local calendar date** in the profile's effective timezone (§7.1). `LocalTime` = `HH:mm` (`"24:00"` allowed as an end time). `ISODateTime` = RFC 3339 with offset. Fields ending in `_utc` are UTC. |
| Ids | `profile_id`, `compatibility_id`, `thread_id`, `job_id`: UUID v4. `chart_key`: opaque string, changes when birth data changes. Place ids: opaque strings (`gn-…` gazetteer, `dst-…` destination, `geo-…` geocoder). |
| Caching | Generated and deterministic resources send `ETag`; the app sends `If-None-Match` → `304`. |
| Idempotency | `POST` endpoints that create generated work accept `Idempotency-Key` (UUID); the same key within 24 h returns the same result. |
| Pagination | Lists that can grow (`/compatibility`, `/reports`, `/ask/threads`) use `?cursor=&limit=` (default 20, max 50) and return `{ items: T[], next_cursor: string \| null }`. |
| Versioning | Breaking changes → `/v2`. Additive fields may appear at any time; the app ignores unknown fields and maps unknown enum values to a safe default (FE_01 §5.2). |
| Rate limits | `429` + `Retry-After` (seconds). |

## 3. Shared types

```ts
type Lang = 'tr' | 'en';
type ISODate = string;          // 'YYYY-MM-DD' local
type LocalTime = string;        // 'HH:mm'
type ISODateTime = string;

type Body = 'sun' | 'moon' | 'mercury' | 'venus' | 'mars' | 'jupiter' | 'saturn'
          | 'uranus' | 'neptune' | 'pluto' | 'north_node' | 'south_node';
type Angle = 'ASC' | 'DSC' | 'MC' | 'IC';
type Sign = 'aries' | 'taurus' | 'gemini' | 'cancer' | 'leo' | 'virgo'
          | 'libra' | 'scorpio' | 'sagittarius' | 'capricorn' | 'aquarius' | 'pisces';
type AspectType = 'conjunction' | 'sextile' | 'square' | 'trine' | 'opposition';

type Goal = 'love' | 'career' | 'business' | 'money' | 'family' | 'education'
          | 'creativity' | 'spirituality' | 'rest' | 'travel' | 'relocation';      // ACG_08 §1, CAL_00 D8
type PlaceBand = 'strongly_supportive' | 'supportive' | 'mixed' | 'no_emphasis' | 'challenging';  // ACG_08 §4
type DayBand = 'strongly_supportive' | 'supportive' | 'quiet' | 'mixed'
             | 'challenging' | 'strongly_challenging';                                  // calendar day_scores
type DayTone = 'favorable' | 'mixed' | 'quiet' | 'challenging';
type Activity = 'love' | 'meetings' | 'business' | 'contract' | 'conversation'
              | 'travel' | 'shopping' | 'project_start' | 'interview' | 'moving';       // CAL_04
type Grade = 'excellent' | 'good' | 'neutral' | 'avoid';
type Importance = 'major' | 'moderate' | 'minor' | 'collective';
type MoonPhase = 'new' | 'waxing_crescent' | 'first_quarter' | 'waxing_gibbous'
               | 'full' | 'waning_gibbous' | 'last_quarter' | 'waning_crescent';
type Lens = 'general' | 'personal' | 'professional';     // forecast "profile"; UI: General · Love & relationships · Work & career
type CompatType = 'love' | 'family' | 'work';
type FamilyRelation = 'parent_child' | 'siblings' | 'other';
type Relation = 'self' | 'partner' | 'child' | 'parent' | 'family' | 'friend'
              | 'colleague' | 'business_partner' | 'other';
type Tier = 'tight' | 'strong' | 'wide';
type TransitPhase = 'building' | 'peak' | 'easing';

interface Place {
  place_id: string;
  name: string;                 // in `lang` (name_tr for tr when available)
  admin1: string | null;        // province / state
  country_code: string;         // ISO-3166-1 alpha-2
  country_name: string;
  lat: number; lon: number;
  tz: string;                   // IANA
}
```

## 4. Jobs and generated parts

### 4.1 Pattern
LLM-backed work takes seconds to minutes (FE_00 F11). Two shapes:

1. **Whole resource is generated** (natal reading, chart element notes): `GET` answers `200` with the resource when it
   exists, else **`202`** with `{ "job": Job }` and a `Retry-After` hint. The first `GET` starts the work; repeated
   `GET`s while running return the same job. After success the same `GET` answers `200`.
2. **Composite resource** (day / month / year forecasts, Solar Return, compatibility, place and area reports,
   recommendations, calendar items): answers `200` at once with
   its deterministic data, and each generated block is a `GeneratedPart<T>`.

`?retry=true` on the same `GET` restarts a failed job.

### 4.2 Types

```ts
interface Job {
  job_id: string;
  kind: 'natal_reading' | 'element_notes' | 'day_reading' | 'month_reading' | 'year_reading'
      | 'solar_return' | 'compatibility' | 'place_reading' | 'area_reading' | 'recommendation'
      | 'calendar_text' | 'best_day_text';
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  stages: { name: JobStage; status: 'pending' | 'running' | 'ok' | 'skipped' | 'failed' }[];
  created_at: ISODateTime; updated_at: ISODateTime;
  eta_seconds: number | null;     // best guess from recent jobs of the same kind; may be null
  error: Problem | null;
}

type JobStage = string;          // manifest stage names; known values in §4.3, unknown → "Preparing"

type GeneratedPart<T> =
  | ({ status: 'ready' } & T)
  | { status: 'pending'; job: Job }
  | { status: 'failed'; error: Problem }
  | { status: 'absent'; absence: Absence };
```

`GET /v1/jobs/{job_id}` → `Job` (**NEW**, infrastructure). Jobs are visible only to their owner and expire 24 h after
finishing.

### 4.3 Stage names
`JobStage` values come from the orchestrator manifests (`stages[].name`). The app shows friendly labels (chrome):

| Stage(s) | TR | EN |
|---|---|---|
| `input-resolve`, `compute_chart`, `natal`, `compute_forecast`, `compute_acg`, `compute_parans`, `city_scan`, `goal_scan`, `locate`, `relocate`, `collective`, `events`, `scores`, `best_days`, `notifications`, `views` | Hesaplanıyor | Calculating |
| `ground`, `ground_forecast`, `ground_acg`, `grounding` | Haritana uyan ilkeler seçiliyor | Matching principles to your chart |
| `reading`, `sections`, `synthesis`, `texts`, `explanations` | Yazılıyor | Writing |
| `translation` | Çevriliyor | Translating |
| `validate`, `detox` | Kontrol ediliyor | Checking |
| unknown | Hazırlanıyor | Preparing |

## 5. Errors

### 5.1 Problem (RFC 7807)

```ts
interface Problem {
  type: string; title: string; status: number;
  code: 'validation_error' | 'unauthorized' | 'forbidden' | 'not_found' | 'conflict'
      | 'out_of_range' | 'rate_limited' | 'generation_failed' | 'absent'
      | 'upstream_unavailable' | 'internal';
  detail?: string;                               // developer text, never shown to users
  fields?: { field: string; issue: string }[];   // validation_error
  absence?: Absence;                             // code = 'absent'
}
interface Absence { reason: AbsenceReason; stage?: string }
type AbsenceReason = 'time_not_exact' | 'placidus_undefined_high_latitude' | 'acg_corpus_missing'
                   | 'no_grounding' | 'place_not_found' | (string & {});   // open set, §5.2
```

### 5.2 Absence reasons
Backend absence contracts (never exceptions) surface as `Absence`:

| `reason` | Source |
|---|---|
| `time_not_exact` | L1 precision tier ≠ exact (ACG D5); not expected in v1 (F9) |
| `placidus_undefined_high_latitude` | relocation above \|lat\| 66° (ACG D8) |
| `acg_corpus_missing` | ACG preflight (ACG_05 §1) |
| `no_grounding` | a text unit with no eligible records (CAL_03 §1) |
| `place_not_found` | locate / geocoder failure |
| other strings | shown with the generic copy (FE_01 §7) |

## 6. Derivation rules (API layer)

### 6.1 Id normalisation
- Bodies: `chart.json` names (`"Sun"`, `"North Node"`) and calendar / ACG ids (`"venus"`, `"north_node"`) →
  `Body` (lowercase snake).
- Angles: `"ASC"/"MC"` (ACG), `"asc"/"mc"` (calendar ids), `"Ascendant"`, `"IC"` (forecast) → `Angle`.
- Signs: `"Capricorn"`, `"gemini"` → lowercase `Sign`.
- Calendar item ids keep the calendar scheme without text-unit prefixes: `tr:saturn:conjunction:sun:2026a`,
  `lun:2026-10-10:new`, `ecl:2027-02-20:lunar`, `stn:venus:R:2026-10-03`, `stp:mercury:D:opposition:moon:2026-11-13`,
  `ing:jupiter:virgo:…`, `rx:mercury:2026-10-24`, `per:career:challenging:2026-11-20`, `win:contract:2026-09-29`.
  The prefixes `t:`, `p:`, `l:`, `b:`, `c:` of `texts_<lang>.json` keys are stripped.

### 6.2 Band → `score_10` (Home, Today; open decision O3)

| Day band | `score_10` | | Day tone | `score_10` |
|---|---|---|---|---|
| `strongly_supportive` | 9 | | `favorable` | 8 |
| `supportive` | 8 | | `quiet` | 6 |
| `quiet` | 6 | | `mixed` | 5 |
| `mixed` | 5 | | `challenging` | 4 |
| `challenging` | 4 | | | |
| `strongly_challenging` | 2 | | | |

Band-only on purpose: the number is a readable restatement of the band, never a finer measurement.

### 6.3 Transit labels and phases
- Labels for transit episodes, lunations, eclipses, stations, ingresses and periods come from the calendar's
  deterministic label catalogue (CAL_03 §2; the same strings as `label` in `texts_<lang>.json` and `label_tr/en` in
  `calendar_<YYYY-MM>.json`). Example: `tr:mars:opposition:venus:2026a` → EN "Mars opposite your Venus".
- `TransitPhase` of an episode on a date `d`: `building` if `d < min(exacts_local)`, `easing` if
  `d > max(exacts_local)`, else `peak`.

### 6.4 Masking
The API never returns: whole-sign sectors, cusps or relations; `classifications` (dignities, triplicity, bound,
face); `derived_points`; `planetary_day` / `planetary_hour`; `sect` / `is_diurnal`; `tradition` fields; principle ids
or traces (except behind the dev flag `?debug=traces`, allowed only for staff accounts); model names; corpus hashes.

## 7. Endpoints

### 7.1 Account, profiles, places

#### Auth (**NEW**)
| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/auth/email/start` | `{ email, lang }` | `204` (sends a 6-digit code) |
| POST | `/auth/email/verify` | `{ email, code }` | `Session` |
| POST | `/auth/apple` | `{ identity_token, authorization_code, full_name?: string }` | `Session` |
| POST | `/auth/google` | `{ id_token }` | `Session` |
| POST | `/auth/refresh` | `{ refresh_token }` | `Session` |
| POST | `/auth/logout` | `{ refresh_token }` | `204` |

```ts
interface Session {
  access_token: string; access_expires_at: ISODateTime;
  refresh_token: string;
  is_new_user: boolean;
  me: Me;
}
```

#### Me (**NEW**)
`GET /me` → `Me` · `PATCH /me` (partial of the writable fields) → `Me` · `DELETE /me` → `202` (erasure scheduled,
KVKK/GDPR; all profiles, readings, threads deleted within 30 days; sessions revoked at once) ·
`POST /me/export` → `202` then an email with a download link (JSON of profiles, readings, threads).

```ts
interface Me {
  user_id: string;
  email: string | null;
  display_name: string;                     // writable
  language: Lang;                           // writable
  theme: 'system' | 'light' | 'dark';       // writable
  current_place: Place | null;              // writable via current_place_id; drives "today" (F10)
  self_profile_id: string | null;
  notification_prefs: NotificationPrefs;    // writable
  entitlements: Record<string, true>;       // all true in v1 (F4)
  ask_quota: { limit_per_day: number; used_today: number; resets_at: ISODateTime };
  consents: { birth_data: { version: string; accepted_at: ISODateTime } | null;
              marketing: boolean };         // writable (accept via PATCH { consents: {...} })
  created_at: ISODateTime;
}
interface NotificationPrefs {
  enabled: boolean;
  types: Record<NotificationType, boolean>;  // default all true
  time: LocalTime;                           // default '09:00'
  max_per_day: number;                       // default 1
  max_per_week: number;                      // default 3
  quiet_hours: { start: LocalTime; end: LocalTime };   // default 22:00–08:00
}
type NotificationType = 'favorable_window' | 'period_start' | 'lunation_in_house'
                      | 'retrograde_start' | 'station_on_point' | 'eclipse_hit';
```

#### Places (**NEW**: wraps a geocoder + `gazetteer.json` + `destinations.json` + `timezonefinder`)
| Method | Path | Notes |
|---|---|---|
| GET | `/places/search?q=&kind=birth\|city\|area&lang=&limit=8` | `birth`: any settlement worldwide (geocoder, for birthplaces). `city`: gazetteer + destinations (map search). `area`: countries + admin-1 regions. Min 2 chars. |
| GET | `/places/{place_id}?lang=` | one place |
| GET | `/places/reverse?lat=&lon=&lang=` | nearest gazetteer city within 75 km, else `null` (map tap) |

```ts
interface PlaceCandidate extends Place {
  kind: 'city' | 'town' | 'village' | 'district' | 'region' | 'country' | 'destination';
  population: number | null;
  source: 'gazetteer' | 'destination' | 'geocoder';
}
// kind=area results: { place_id: 'iso2:TR' | 'admin1:TUR-…', kind: 'country'|'region', name, country_code, … }
```

Timezone is resolved **server-side** for the birth date and place (brief §2: coordinates and timezone are automatic).

#### Birth profiles, "My Charts" (**NEW** storage; compute WRAPs `compute_chart`)
| Method | Path | Body / notes |
|---|---|---|
| GET | `/profiles` | `BirthProfile[]` (self first, then by `created_at`) |
| POST | `/profiles` | `BirthProfileInput` → `201 BirthProfile`. Computes the chart synchronously (< 1 s). For the self profile it also **starts the natal reading job** and returns it in `natal_reading_job`. |
| GET | `/profiles/{id}` | `BirthProfile` |
| PATCH | `/profiles/{id}` | partial `BirthProfileInput`. Changing birth fields produces a new `chart_key`; all generated artifacts for the old key become unreachable. |
| DELETE | `/profiles/{id}` | `204`. The self profile cannot be deleted (`409 conflict`); delete the account instead. |

```ts
interface BirthProfileInput {
  label: string;                       // 1–40 chars, as the user typed it
  relation: Relation;                  // exactly one profile per user has 'self'
  birth_date: ISODate;                 // 1900-01-01 … today
  birth_time: LocalTime;               // exact time required (F9)
  birth_place_id: string;              // from /places/search?kind=birth
  gender?: 'female' | 'male' | 'other' | null;       // optional (brief §2); not used by readings
  current_place_id?: string | null;    // optional, for other people; self uses me.current_place
}
interface BirthProfile {
  profile_id: string; chart_key: string;
  label: string; relation: Relation; is_self: boolean;
  birth: { date: ISODate; time: LocalTime; place: Place; tz: string; utc: ISODateTime };
  gender: 'female' | 'male' | 'other' | null;
  current_place: Place | null;
  big_three: { sun: Sign; moon: Sign; ascendant: Sign };    // DERIVED from chart.json
  natal_reading_job?: Job;                                  // only on POST of the self profile
  created_at: ISODateTime; updated_at: ISODateTime;
}
```

**Effective timezone** of a profile for local dates: `profile.current_place.tz` if set, else `me.current_place.tz`,
else the birth `tz`.

Limits: max 50 profiles per user (`409` beyond).

### 7.2 Chart and natal reading

#### `GET /profiles/{id}/chart` → `ChartData` (**WRAP** `compute_chart` → `chart.json`)

```ts
interface ChartData {
  profile_id: string; chart_key: string;
  utc: ISODateTime; tz: string;
  points: ChartPoint[];          // 12: ten planets + both nodes, in chart.json order
  axes: { asc: AxisPoint; mc: AxisPoint };
  houses: House[];               // 12
  aspects: Aspect[];
}
interface ChartPoint { body: Body; longitude: number; sign: Sign; degree_in_sign: number;
                       house: number; retrograde: boolean }
interface AxisPoint { longitude: number; sign: Sign; degree_in_sign: number }
interface House { house: number; cusp_longitude: number; sign: Sign;
                  rulers: Body[]; planets: Body[] }
interface Aspect { a: Body; b: Body; type: AspectType; orb: number }
```

Mapping from `chart.json`:

| Field | Source |
|---|---|
| `points[]` | `points[]`: `name`→`body` (§6.1), `longitude`, `sign`, `degree_in_sign`, `retrograde`, `sector.placidus`→`house` |
| `axes` | `axes.ascendant`, `axes.mc` |
| `houses[n-1]` | `sectors.placidus_cusps[n-1]` → `cusp_longitude`; `sector_rulers.placidus[n]`: `sign_on_cusp`→`sign`; `rulers` = `[ruler, modern_ruler]` de-duplicated, in that order (never labelled as traditional/modern); `planets` = bodies whose `house == n` |
| `aspects[]` | `relations[]` **where `scheme == "modern"` only**: `source`→`a`, `target`→`b`, `type`, `orb` |
| `tz`, `utc` | `meta.timezone`, `meta.utc` |

Everything else is masked (§6.4). The wheel adapter (FE_05 §2.3) rebuilds the renderer's input from these fields,
so: keep `points` in `chart.json` order and `aspects` in `relations` order, and **never round** longitudes, degrees
or orbs (the byte-parity test W1 depends on full precision).

#### `GET /profiles/{id}/natal-reading?lang=` → `200 NatalReading | 202 { job }` (**WRAP** `run.py` → `l4_output.json`)

```ts
interface NatalReading {
  profile_id: string; chart_key: string; lang: Lang; generated_at: ISODateTime;
  title: string;                                        // l4_render _DOC_TITLE
  parts: { movement: 1 | 2; title: string }[];          // l4_render MOVEMENT_TITLES
  sections: NatalSection[];                             // l4_output order; empty ones already omitted
}
interface NatalSection {
  key: 'core_identity' | 'sun_house' | 'moon_house' | 'inner_drives' | 'chart_shape'
     | 'identity' | 'values_money' | 'communication_learning' | 'family_home'
     | 'joy_creativity_children' | 'health_routine_pets' | 'partnerships'
     | 'transformation_intimacy' | 'travel_philosophy' | 'status_vocation'
     | 'friendships_future' | 'subconscious_solitude';
  movement: 1 | 2;
  house: number | null;
  title: string;          // l4_render.section_title(key, lang, house)
  text: string;           // text_tr | text_en; paragraphs separated by blank lines
}
```

Drop `principle_ids`, `schema_version`, `precision_tier`. The API does not run the distiller / scoresheet stage for
app requests (eval only).

#### `GET /profiles/{id}/chart/elements?lang=` → `200 ChartElements | 202 { job } | 404` (**NEW**)
Short grounded notes for the wheel's tap panels (brief §4). One note per plotted body, per house, per occupied
sign and per aspect, 30–60 words each, grounded in the chart's kept principles (`personal_principles.json`, bundled
by factor), same validator discipline as L4. Until live, the flag `elementNotes` is off and the app uses the section
fallback (FE_05 §3.4).

```ts
interface ChartElements {
  chart_key: string; lang: Lang;
  bodies: Partial<Record<Body, ElementNote>>;
  houses: Partial<Record<'1'|'2'|'3'|'4'|'5'|'6'|'7'|'8'|'9'|'10'|'11'|'12', ElementNote>>;
  signs: Partial<Record<Sign, ElementNote>>;
  aspects: { a: Body; b: Body; type: AspectType; note: ElementNote }[];
}
interface ElementNote { text: string; section_key: NatalSection['key'] | null }
```

### 7.3 Home and the day forecast

#### `GET /profiles/{id}/forecast/day?date=&lens=&lang=` → `DayForecast`
`date` default = today in the profile's effective tz; allowed range: today − 7 … today + 365 (`out_of_range` otherwise).
`lens` default `general`.

```ts
interface DayForecast {
  profile_id: string; date: ISODate; tz: string; lens: Lens;
  tone: DayTone; tone_label: string; score_10: number;             // §6.2
  areas: Record<Goal, DayArea>;                                     // all 11
  moon: MoonInfo;
  retrograde: Body[];
  events: CalendarEventRef[];                                       // the day's calendar events
  transits: TransitEpisode[];                                       // episodes active on `date`, importance major|moderate
  reading: GeneratedPart<{ text: string }>;                         // 120–180 words
  day_note: GeneratedPart<{ text: string }> | null;                 // CAL_03 day_note (40–60 words)
  best_activities: { activity: Activity; label: string; grade: 'excellent' | 'good' }[];  // Best Days on `date`
  domains?: { key: 'love' | 'family' | 'work' | 'money' | 'communication' | 'emotions';
              title: string; text: string }[];                      // NEW, optional (F13)
  advice?: string;                                                  // NEW, optional (F13)
}
interface DayArea { band: DayBand; label: string; score_10: number; drivers: string[] /* transit labels */ }
interface MoonInfo { phase: MoonPhase; phase_label: string; sign: Sign; sign_label: string;
                     void_of_course: { start: LocalTime; end: LocalTime }[] }
interface CalendarEventRef { id: string; kind: CalendarItemKind; label: string;
                             importance: Importance; has_text: boolean }
interface TransitEpisode {
  id: string; label: string; importance: Importance;
  transiting: Body; aspect: AspectType; natal: Body | Angle;
  start: ISODate; end: ISODate; exact_dates: ISODate[];
  phase: TransitPhase; phase_label: string;                         // relative to the request date, §6.3
  has_text: boolean;
}
```

| Field | Status | Source |
|---|---|---|
| `reading` | WRAP | `run_predictive.py --horizons day --target <date> --current-location <tz place>` with profile = lens → `reading_day_<lens>_<date>.json` (`reading`), `.en.json` for EN |
| `tone`, `areas` | WRAP + DERIVED | calendar `day_scores.json` `days[local_date==date]`: `tone`, `goals[g].band`, `drivers[g]` (ids → labels §6.3); `score_10` §6.2 |
| `moon`, `retrograde`, `events` | WRAP | `calendar_<YYYY-MM>.json` `days[local_date==date]` |
| `transits` | WRAP + DERIVED | `personal_events.json` episodes with `start_local ≤ date ≤ end_local` and importance major/moderate; phase §6.3 |
| `day_note` | WRAP | `run_calendar.py --mode day <date>` → `day_<date>.json` `day_note` (lazy, CAL_03) |
| `best_activities` | WRAP | `best_days.json`: activities whose `days[date].grade` is `excellent` or `good` (empty beyond the 90-day horizon) |
| `domains`, `advice` | NEW | not produced today |

#### `GET /home?lang=` → `HomeSummary` (**DERIVED**, self profile, today)

```ts
interface HomeSummary {
  date: ISODate; tz: string; greeting_name: string;       // display_name or self label
  tone: DayTone; tone_label: string; score_10: number;
  tiles: { key: Goal | 'energy'; label: string; band: DayBand; score_10: number }[];
        // love, career, money, family (O2; 'energy' only if flag homeEnergyTile and backend provides it)
  moon: MoonInfo;
  today: GeneratedPart<{ text: string }>;                  // = day reading, general lens
  next_up: UpcomingItem[];                                 // ≤ 3, next 14 days
}
interface UpcomingItem {
  kind: 'period_start' | 'lunation' | 'eclipse' | 'retrograde_start' | 'best_window' | 'transit_peak';
  date: ISODate; label: string;
  deep_link: { view: 'best_days' | 'period' | 'event'; ref: string };
}
```
`next_up` = the first three `notification_candidates` (§7.9) by `trigger_date` from tomorrow on, using their text
as `label`.

### 7.4 Month and year forecasts

#### `GET /profiles/{id}/forecast/month?month=YYYY-MM&lens=&lang=` → `MonthForecast` (**WRAP** + DERIVED)
The API calls `run_predictive.py --horizons month --target <YYYY-MM-01>` with the profile's effective tz.
**Backend to confirm** that the month window is the calendar month of the target (if it is a rolling window, the
API must still present calendar-month semantics).

```ts
interface MonthForecast {
  profile_id: string; month: string; tz: string; lens: Lens;
  segments: { early: DateRange; mid: DateRange; late: DateRange };   // the backend's beat split (expected 1–10, 11–20, 21–end; backend confirms)
  reading: GeneratedPart<{ overview: string; early: string; mid: string; late: string;
                           focus: string; focus_title: string }>;
  highlights: {
    favorable_days: ISODate[];          // calendar days with tone 'favorable'
    challenging_days: ISODate[];        // tone 'challenging'
    periods: PeriodRef[];               // periods overlapping the month
    major_transits: TransitEpisode[];   // calendar month `major_transits` (+ phase at mid-month)
    lunations: CalendarEventRef[];
    eclipses: CalendarEventRef[];
    retrogrades: RetrogradeRef[];
  };
  domains?: { key: 'love' | 'family' | 'work' | 'career' | 'money' | 'social' | 'travel';
              title: string; text: string }[];                       // NEW, optional (brief §7)
}
interface DateRange { from: ISODate; to: ISODate }
interface PeriodRef { id: string; goal: Goal; goal_label: string; kind: 'favorable' | 'challenging';
                      label: string; start: ISODate; end: ISODate; peak: ISODate;
                      strength: 'normal' | 'strong'; importance: Importance; has_text: boolean }
interface RetrogradeRef { id: string; body: Body; label: string; start: ISODate; end: ISODate }
```

| Field | Source |
|---|---|
| `reading.overview/early/mid/late/focus` | `reading_month_<lens>_<date>.json` (TR) / `.en.json` (EN) |
| `reading.focus_title` | chrome-like label per lens from the catalogue (`lens_focus_titles`): general → "Focus of the month", personal → "Love & relationships", professional → "Work & career" |
| `highlights.*` | `calendar_<YYYY-MM>.json` (`days[].tone`, `periods`, `major_transits`, `lunations`, `eclipses`, `retrograde_periods`) resolved through `periods.json` / `personal_events.json` / collective events |

#### `GET /profiles/{id}/forecast/year?from=YYYY-MM&lens=&lang=` → `YearForecast` (**WRAP** + DERIVED)
`from` default = the current month. `run_predictive.py --horizons year --target <from-01>`.

```ts
interface YearForecast {
  profile_id: string; from: string; to: string; tz: string; lens: Lens;
  quarters: { key: 'q1' | 'q2' | 'q3' | 'q4'; from: ISODate; to: ISODate }[];
  reading: GeneratedPart<{ overview: string; q1: string; q2: string; q3: string; q4: string;
                           focus: string; focus_title: string }>;
  highlights: {
    strongest_periods: PeriodRef[];      // favorable, importance major or strength strong, ≤ 6
    challenging_periods: PeriodRef[];    // challenging, importance major or strength strong, ≤ 6
    key_events: CalendarEventRef[];      // eclipses, Jupiter–Pluto ingresses, major transits (12 months)
    retrogrades: RetrogradeRef[];
  };
  months: { month: string; label: string }[];   // 12 entries → each opens MonthForecast (generated lazily)
  domains?: { key: 'growth' | 'love' | 'family' | 'career' | 'business' | 'money'
                  | 'home_property' | 'travel' | 'social'; title: string; text: string }[];  // NEW, optional (brief §8)
}
```

### 7.5 Solar Return (**NEW**)
`GET /profiles/{id}/solar-return?year=&place_id=&lang=` → `SolarReturn`. `year` default: the return year whose
birthday is the most recent; `place_id` = where the person is on that birthday (default: the profile's effective
current place). Backend work: compute the solar-return instant (Sun returns to its natal longitude), cast the chart
at that instant for the place (same L1), and a grounded reading. The contract mirrors the natal types.

```ts
interface SolarReturn {
  profile_id: string; year: number; return_utc: ISODateTime; place: Place;
  chart: ChartData;                                     // same shape as §7.2
  reading: GeneratedPart<{ sections: { key: string; title: string; text: string }[] }>;
}
```

### 7.6 Compatibility
**WRAP** `synastry_run.py` (S1–S3), except `family` (**NEW**, O4).

| Method | Path | Notes |
|---|---|---|
| POST | `/compatibility` | `{ profile_a_id, profile_b_id, type: CompatType, family_relation?: FamilyRelation }` → `201 Compatibility` (reading pending). Idempotent on (a, b, type, family_relation, both chart_keys): returns the existing one. |
| GET | `/compatibility?cursor=&limit=` | `{ items: CompatibilitySummary[], next_cursor }` |
| GET | `/compatibility/{id}?lang=` | `Compatibility` |
| DELETE | `/compatibility/{id}` | `204` |

```ts
interface Compatibility {
  compatibility_id: string; type: CompatType; family_relation: FamilyRelation | null;
  people: { a: PersonRef; b: PersonRef };
  created_at: ISODateTime;
  reading: GeneratedPart<{ title: string; sections: CompatSection[] }>;
  score: null | { value: number; label: string };   // always null in v1 (O1; S3 §6 no-score)
}
interface PersonRef { profile_id: string; label: string; big_three: BirthProfile['big_three'] }
interface CompatSection { key: string; movement: number; title: string; text: string }
interface CompatibilitySummary { compatibility_id: string; type: CompatType;
  people: { a: PersonRef; b: PersonRef }; status: 'ready' | 'pending' | 'failed'; created_at: ISODateTime }
```

| `type` | S3 `reading_type` | Section keys (render order from the file) |
|---|---|---|
| `love` | `personal` | `what_each_brings`, `attraction`, `emotional`, `communication`, `friction`, `values`, `commitment`, `purpose` |
| `work` | `professional` | `what_each_brings`, `working_rapport`, `roles_leadership`, `decision_making`, `reliability`, `money_resources`, `conflict_style`, `shared_goals` |
| `family` | NEW `family` profile; **until live: `general`** (stamped with `family_relation`) | general keys: `what_each_brings`, `rapport`, `emotional_dynamics`, `communication`, `friction`, `values`, `support_trust`, `direction` |

`title` per section and `reading.title` come from `s3_profiles.py` (`titles`, `doc_title`) in the requested
language. `text` = `text_tr`/`text_en` of `relationship_reading_*.json`. Drop `source_ids`. Person labels are
substituted by the backend exactly as the user typed them.

The app treats section keys as opaque: it renders whatever sections arrive, in order, with the API titles.

### 7.7 Astrocartography
Map data depends only on birth data and is cached per `chart_key` (ACG_07 §8).

| Method | Path | Status | Response |
|---|---|---|---|
| GET | `/profiles/{id}/acg/lines` | WRAP | `AcgLines` |
| GET | `/profiles/{id}/acg/heat/{goal}` | DERIVED | `AcgHeat` |
| GET | `/profiles/{id}/acg/lines/{body}/{angle}/places?limit=20&lang=` | DERIVED | `LinePlaces`: gazetteer cities along one line (`city_scan.json` `by_line["<body>\|<angle>"]`, distance-sorted) |
| GET | `/profiles/{id}/acg/places/{place_id}?focus_goal=&lang=` | WRAP + DERIVED | `PlaceReport` (gazetteer `gn-…`, destination `dst-…`, or a `/places` id) |
| GET | `/profiles/{id}/acg/point?lat=&lon=&focus_goal=&lang=` | WRAP | `PlaceReport` for an arbitrary spot (`run_acg.py --lat --lon`) |
| GET | `/profiles/{id}/acg/countries/{iso2}?lang=` | WRAP | `AreaReport` (`country_<ISO>.json`) |
| GET | `/profiles/{id}/acg/regions/{admin1_id}?lang=` | WRAP | `AreaReport` (`region_<ID>.json`) |
| POST | `/profiles/{id}/acg/recommendations?lang=` | WRAP | `Recommendation` (ACG_09 + ACG_11) |
| GET | `/geo/countries.geojson` | WRAP (static) | simplified admin-0 polygons, properties `{ iso2, name_tr, name_en }` (`countries.geojson`, ACG_07 §3) |
| GET | `/geo/regions/{iso2}.geojson` | WRAP (static) | simplified admin-1 polygons of one country, properties `{ admin1_id, iso2, name_tr, name_en }` |

```ts
interface AcgLines {
  chart_key: string;
  lines: GeoJSON.FeatureCollection<GeoJSON.MultiLineString,
          { body: Body; angle: Angle; read: boolean }>;            // acg.geojson; read_in_v1 → read
  parans: GeoJSON.FeatureCollection<GeoJSON.LineString,
          { id: string; bodies: [Body, Body]; angles: [Angle, Angle] }>;   // acg_parans.geojson
}
```
The API simplifies geometry (Douglas–Peucker, tolerance 0.05°) so `lines` + `parans` stay ≤ 150 KB gzipped.
Nodes' lines are included with `read: false`.

```ts
interface AcgHeat {
  chart_key: string; goal: Goal; grid_step_deg: number;          // 0.5
  points: [lon: number, lat: number, level: 2 | 1 | 0 | -1][];   // 2 strongly_supportive, 1 supportive, 0 mixed, -1 challenging
}
```
Source: `goal_heat_<goal>.geojson` (points whose band ≠ `no_emphasis`, ACG_08 §6); `S` is dropped (C4).

```ts
interface LinePlaces {
  line: { body: Body; angle: Angle; planet_label: string; angle_label: string };
  places: { place_id: string; name: string; country_code: string;
            distance_km_rounded: number | '<10'; tier: Tier; tier_label: string }[];
}
```
Distances rounded to 10 km, `'<10'` below 10 km (ACG_07 §4). Only cities within 1,000 km.

```ts
interface PlaceReport {
  place: { place_id: string | null; name: string; country_code: string | null; lat: number; lon: number };
  status: 'ok' | 'absent'; absence?: Absence;
  relocation: { status: 'ok' | 'absent'; absence?: Absence };
  focus_goal: Goal | null;
  lines_display: LineDisplay[];            // immediate
  parans_display: ParanDisplay[];          // immediate
  goal_scores: Record<Goal, { band: PlaceBand; label: string }>;   // immediate
  cards: SuitabilityCard[];                // immediate bands; text pending until the reading is ready
  reading: GeneratedPart<{ sections: PlaceSection[] }>;
  footer: string;                          // fixed ACG footer (ACG_04 §6)
}
interface LineDisplay { body: Body; angle: Angle; planet_label: string; angle_label: string;
  distance_km_rounded: number | '<10'; tier: Tier; tier_label: string; read_in_prose: boolean }
interface ParanDisplay { id: string; bodies: [Body, Body]; planet_labels: [string, string];
  north_south: 'north' | 'south'; distance_km_rounded: number | '<10'; label: string }
interface SuitabilityCard { card: 'travel' | 'living' | 'work' | 'business' | 'love' | 'family' | 'focus';
  goal: Goal; title: string; band: PlaceBand; band_label: string;
  text: string | null }        // no_emphasis: fixed template text at once; others: null until reading ready
interface PlaceSection { key: string; title: string; paragraphs: { slot_id: string; text: string }[] }
```

| Field | Source (`reading_<lang>.json`, schema `acg-reading-3`) |
|---|---|
| `lines_display` | `lines_display[]` (`planet_tr/en`→`planet_label`, `angle_label_tr/en`, `tier_label_tr/en`) |
| `parans_display` | `parans_display[]` (`planets_tr/en`, `label_tr/en`) |
| `goal_scores` | `goal_scores[g].band`, `band_label_tr/en` (drop `score`, `P`, `N`) |
| `cards` | `sections[key=suitability].cards[]` (`card`, `goal`, `title`, `band`, `band_label_*`, `text`) |
| `reading.sections` | every other `sections[]` entry in file order (`place_overview`, `lines_here`, `background_influences`, `positives`, `challenges`, `life_areas_here`, …), `paragraphs[].{slot_id,text}`; drop `trace`, `sentences` |
| `footer` | `footer` |

**Immediate vs pending.** For gazetteer cities the deterministic block comes from the per-chart cache
(`city_scan.json`, `goal_scan.npz`) at once; the reading runs as a job (≈ 70 s observed). The API must return the
deterministic block without waiting for the reading. **Backend note:** today `lines_display` and `goal_scores`
are only written inside `reading_<lang>.json`; the API needs them from the locate + goal-scan stages directly.

```ts
interface AreaReport {
  area: { kind: 'country' | 'region'; id: string; iso2: string; name: string };
  status: 'ok' | 'absent'; absence?: Absence;
  bands: Record<Goal, { band: PlaceBand; label: string }>;          // bands[g].band (drop S_agg, P_agg, N_agg, k)
  lines_crossing: { body: Body; angle: Angle; planet_label: string; angle_label: string }[];
  best_cities: Record<Goal, { place_id: string; name: string; band: PlaceBand; band_label: string }[]>;  // top 3
  varies_by_region: boolean;
  regions?: { admin1_id: string; name: string }[];                  // countries only
  overview: GeneratedPart<{ text: string }>;                        // place_overview, 90–140 words
  footer: string;
}
```

**Recommendations** (`POST /profiles/{id}/acg/recommendations`):

```ts
interface RecommendationRequest {
  goal?: Goal | 'overall';
  query_text?: string;                       // free text (ACG_09 §2) when goal is absent
  scope?: 'world' | string;                  // 'world' (default) or ISO-2 ('TR', 'DE', …)
  filters?: {
    regions?: ('europe' | 'turkey' | 'mediterranean' | 'middle_east_gulf' | 'caucasus' | 'americas'
             | 'east_asia' | 'south_southeast_asia' | 'oceania' | 'central_asia')[];
    city_size?: ('big' | 'mid' | 'small')[];
    max_distance_km?: number | null;
    climate?: ('warm' | 'mild' | 'cold')[] | null;
    purpose?: 'living' | 'travel' | 'both';
  };
}
interface Recommendation {
  recommendation_id: string;
  status: 'ok' | 'thin_result' | 'needs_goal';
  goal: Goal | 'overall' | null; goal_label: string | null; scope: string;
  goal_options?: { goal: Goal; label: string }[];      // needs_goal only
  filters_applied: RecommendationRequest['filters'] & { policy: string };
  by_line: {
    group_id: string; kind: 'line' | 'paran';
    line: { body: Body; angle: Angle } | { bodies: [Body, Body]; angles: [Angle, Angle] };
    title: string;                                     // e.g. "Jupiter · Culminating line" (labels from catalogue)
    destinations: Destination[];
  }[];
  lines_without_destinations: { line: { body: Body; angle: Angle }; title: string; text: string }[];
  places: Destination[];                               // flat top list (ACG_11 §5.6); for 'overall' the ranked list
  turkey: { places: Destination[]; regions: AreaRef[] };
  countries: AreaRef[]; regions: AreaRef[];
  explanations: GeneratedPart<{ intro: string; turkey_intro: string | null;
                                 groups: Record<string, string>; items: Record<string, string> }>;
  footer: string;
}
interface Destination {
  place_id: string; name: string; country_code: string; size: 'big' | 'mid' | 'small';
  band: PlaceBand; band_label: string;
  summary_label?: string;                              // 'overall': e.g. "Supportive for 7 goals"
  dominant_line: { body: Body; angle: Angle; distance_km_rounded: number | '<10' } | null;
  has_tradeoff: boolean;
  purposes: ('living' | 'travel')[];
  lat: number; lon: number;
}
interface AreaRef { id: string; kind: 'country' | 'region'; name: string; band: PlaceBand; band_label: string }
```

Source: `recommend_<goal>_<scope>.json` (`acg-recommend-2` for goals, `acg-recommend-overall-1` for overall;
ACG_09 §5, ACG_11 §7):

| Field | Source |
|---|---|
| `places` | `cities[]` (goal) or `places[]` (overall); `id`→`place_id`, `name_tr`/`name`, `country`→`country_code` |
| `by_line[]` | `by_line[]`: `line`, `kind`, destinations; `group_id` = `"<body>\|<angle>"` (or the paran id) |
| `purposes` | membership of the item's id in `by_purpose.living` / `by_purpose.travel` |
| `turkey` | `turkey.cities` / `turkey.places`, `turkey.regions` |
| `countries`, `regions` | `countries[]`, `regions[]` → `AreaRef` |
| `explanations` | `intro`, `turkey.intro`, `by_line[].text_*`, each item's `text_*` |

`explanations.items` is keyed by `place_id`, `explanations.groups` by `group_id`. Drop `S`, `P`, `N`, `overall`,
`breadth`, `strain`, `affinity`, `supporting_lines`, `challenging_lines`, `contributors`, `trace`, `validation`,
`include_unreviewed`. **The ranking is returned at once** (the recommender's `--dry-run` path produces the full
ranking with zero model calls, ACG_09 W8); the explanations are a job. Recommendations are cached per
(chart_key, request) and listed in saved reports.

### 7.8 Calendar (**WRAP** `run_calendar.py`)
Horizon: 12 rolling months from today in the effective tz (CAL_00 D2); outside → `out_of_range`.

| Method | Path | Response | Source |
|---|---|---|---|
| GET | `/profiles/{id}/calendar/months/{YYYY-MM}?lang=` | `CalendarMonth` | `calendar_<YYYY-MM>.json` |
| GET | `/profiles/{id}/calendar/days/{date}?lang=` | `CalendarDayDetail` | `day_<date>.json` |
| GET | `/profiles/{id}/calendar/items/{item_id}?lang=` | `CalendarItem` | `personal_events.json`, `periods.json`, collective `<year>.json`, `texts_<lang>.json` |
| GET | `/profiles/{id}/calendar/periods?from=&to=&goal=&lang=` | `PeriodRef[]` | `periods.json` |
| GET | `/profiles/{id}/calendar/year?lang=` | `CalendarYear` | `personal_events.json`, `periods.json`, collective `<year>.json` (the data behind `year_overview.<lang>.md`) |

```ts
type CalendarItemKind = 'transit' | 'lunation' | 'eclipse' | 'station' | 'station_on_point'
                      | 'ingress' | 'retrograde_period' | 'period';
interface CalendarMonth {
  profile_id: string; month: string; tz: string;
  days: CalendarDay[];
  lunations: CalendarEventRef[]; eclipses: CalendarEventRef[];
  retrograde_periods: RetrogradeRef[]; major_transits: TransitEpisode[]; periods: PeriodRef[];
}
interface CalendarDay {
  date: ISODate; tone: DayTone; tone_label: string;
  moon: MoonInfo; retrograde: Body[];
  events: CalendarEventRef[];
  active_periods: { id: string; goal: Goal; kind: 'favorable' | 'challenging' }[];
  goals: Record<Goal, DayBand>;
}
interface CalendarDayDetail extends CalendarDay {
  day_note: GeneratedPart<{ text: string }> | null;
  transits: TransitEpisode[];                                    // active episodes (as in DayForecast)
  best_activities: { activity: Activity; label: string; grade: 'excellent' | 'good' }[];   // from best_days
}
interface CalendarItem {
  id: string; kind: CalendarItemKind; label: string; importance: Importance;
  start?: ISODate; end?: ISODate; peak?: ISODate; exact_dates?: ISODate[];
  transiting?: Body; aspect?: AspectType; natal?: Body | Angle;           // transit, station_on_point
  goal?: Goal; goal_label?: string; period_kind?: 'favorable' | 'challenging';
  strength?: 'normal' | 'strong';                                         // period
  sign?: Sign; natal_house?: number; house_label?: string;                // lunation / eclipse
  lunation_kind?: 'new' | 'full'; eclipse_kind?: 'solar' | 'lunar';
  body?: Body;                                                            // station / retrograde / ingress
  text: GeneratedPart<{ text: string }> | null;    // null = label only by design (CAL_03: minor transits, no grounding)
}
interface CalendarYear {
  horizon: DateRange; lunations: CalendarEventRef[]; eclipses: CalendarEventRef[];
  retrograde_periods: RetrogradeRef[]; major_transits: TransitEpisode[]; periods: PeriodRef[];
}
```

Texts are generated lazily on first view and pre-warmed nightly for 14 days (CAL_03). An item whose unit has a
text rule but no cached text returns `text.status = 'pending'` with a `calendar_text` job; an item whose unit has no
text by design (minor transit, `no_grounding` gap) returns `text: null`. `has_text` on refs tells the app which is
which before opening.

### 7.9 Best Days and notification candidates (**WRAP** `run_calendar.py`)

| Method | Path | Response | Source |
|---|---|---|---|
| GET | `/profiles/{id}/best-days?lang=` | `BestDaysOverview` | `best_days.json` (90 days) |
| GET | `/profiles/{id}/best-days/{activity}/{date}?lang=` | `BestDayDetail` | `best_days.json` `activities[a].reasons[date]`, `texts` |
| GET | `/profiles/{id}/notification-candidates?from=&to=&lang=` | `NotificationCandidate[]` | `notifications.json` `candidates[]` |

```ts
interface BestDaysOverview {
  horizon: DateRange; tz: string;
  activities: {
    activity: Activity; label: string;
    days: { date: ISODate; grade: Grade }[];          // every day of the horizon
    top_days: ISODate[];
    windows: { start: ISODate; end: ISODate; days: number }[];
    avoid_days: ISODate[];
  }[];                                                 // 10, in the catalogue order
}
interface BestDayDetail {
  activity: Activity; activity_label: string; date: ISODate; grade: Grade; grade_label: string;
  reasons: { positive: string[]; negative: string[] };    // label_tr/en of reasons[date], ordered by contribution
  text: GeneratedPart<{ text: string }> | null;
}
interface NotificationCandidate {
  id: string; type: NotificationType; priority: 1 | 2 | 3;
  trigger_date: ISODate; suggested_time: LocalTime;
  text: string;                                            // text_tr | text_en
  deep_link: { view: 'best_days' | 'period' | 'event'; ref: string };
}
```
Drop `R`, `factors`, `contribution`, `trigger`, `calibration_version`, `factors_disabled`, `grade_thresholds`.

### 7.10 Ask Astrology (**NEW**)
Full behaviour in FE_09. Endpoints:

| Method | Path | Notes |
|---|---|---|
| POST | `/ask/threads` | `{ profile_id }` → `Thread` |
| GET | `/ask/threads?cursor=&limit=` | `{ items: ThreadSummary[], next_cursor }` |
| GET | `/ask/threads/{id}?lang=` | `Thread` with messages |
| DELETE | `/ask/threads/{id}` | `204` |
| POST | `/ask/threads/{id}/messages?lang=` | `{ text, context? }` → `text/event-stream` (FE_09 §4) |
| POST | `/ask/messages/{message_id}/feedback` | `{ rating: 'up' \| 'down', reason?: string }` → `204` |

### 7.11 Saved reports (**NEW**, an index over generated artifacts)
`GET /reports?type=&cursor=&limit=&lang=` → `{ items: ReportRef[], next_cursor }`; `DELETE /reports/{report_id}`.

```ts
interface ReportRef {
  report_id: string;
  type: 'natal' | 'compatibility' | 'place' | 'area' | 'recommendation'
      | 'forecast_month' | 'forecast_year' | 'solar_return';
  title: string; subtitle: string;          // e.g. "İzmir" / "Ayşe · 30 Eyl 2026"
  profile_id: string; created_at: ISODateTime;
  route: string;                            // app path to open it, e.g. "/map?place=gn-311046"
}
```

## 8. Meta

### 8.1 `GET /meta/catalogue?lang=` → `Catalogue` (**DERIVED** from the backend's TR/EN catalogues)

```ts
interface Catalogue {
  version: string; lang: Lang;
  bodies: Record<Body, string>;                          // "Güneş", "Kuzey Ay Düğümü" …
  angles: Record<Angle, { short: string; name: string; line: string }>;   // AC/Yükselen/Yükselen çizgi …
  signs: Record<Sign, string>;
  aspects: Record<AspectType, string>;
  houses: Record<string, { ordinal: string; name: string }>;   // "9": { "9. Ev", "Uzak Seyahatler ve Felsefe" }
  goals: Record<Goal, string>;
  place_bands: Record<PlaceBand, string>; day_bands: Record<DayBand, string>;
  tones: Record<DayTone, string>; grades: Record<Grade, string>;
  activities: Record<Activity, string>;
  lenses: Record<Lens, string>; lens_focus_titles: Record<Lens, string>;
  compat_types: Record<CompatType, string>; family_relations: Record<FamilyRelation, string>;
  relations: Record<Relation, string>;
  moon_phases: Record<MoonPhase, string>;
  transit_phases: Record<TransitPhase, string>;
  tiers: Record<Tier, string>;
  notification_types: Record<NotificationType, string>;
  recommend_regions: Record<string, string>;             // filter chips
  city_sizes: Record<'big' | 'mid' | 'small', string>; climates: Record<'warm' | 'mild' | 'cold', string>;
  purposes: Record<'living' | 'travel' | 'both', string>;
  terms: {                                               // short astro terms used as UI labels
    retrograde: string;                                  // "Retro" / "Retrograde"
    void_of_course: string;                              // "Boşlukta Ay" / "Void-of-course Moon"
    new_moon: string; full_moon: string; solar_eclipse: string; lunar_eclipse: string;
    solar_return: string; rising: string; big_three: string;
  };
}
```

Sources: `l4_render.py` (section titles, house names), ACG_08 §1 (goals), ACG_08 §4 (place bands), ACG_07 §4
(angle and tier labels), CAL_03 §2 label catalogue, `calendar_reading/notification_templates.json`, `s3_profiles.py`.
Aspect, sign, body and moon-phase names: from the calendar label catalogue (e.g. TR `kavuşum`, `altmışlık`, `kare`,
`üçgen`, `karşıt`). The app bundles a snapshot (`catalogue-fallback.{tr,en}.json`) generated from this endpoint.

### 8.2 `GET /meta/config` → `Config` (**NEW**, trivial)

```ts
interface Config {
  min_app_version: { ios: string; android: string };    // force-update below
  flags: Record<string, boolean>;                       // FE_01 §3.6
  polling: { initial_ms: number[]; interval_ms: number; slow_after_s: number; give_up_after_s: number };
  map_style_url: { light: string; dark: string };
  links: { privacy: string; terms: string; support: string };
}
```

## 9. Endpoint index

| Method | Path | Status |
|---|---|---|
| POST | `/auth/email/start`, `/auth/email/verify`, `/auth/apple`, `/auth/google`, `/auth/refresh`, `/auth/logout` | NEW |
| GET/PATCH/DELETE | `/me`; POST `/me/export` | NEW |
| GET | `/places/search`, `/places/{id}`, `/places/reverse` | NEW |
| GET/POST/PATCH/DELETE | `/profiles`, `/profiles/{id}` | NEW (storage) + WRAP (chart) |
| GET | `/profiles/{id}/chart` | WRAP |
| GET | `/profiles/{id}/natal-reading` | WRAP |
| GET | `/profiles/{id}/chart/elements` | NEW |
| GET | `/home` | DERIVED |
| GET | `/profiles/{id}/forecast/day` | WRAP + DERIVED (+ NEW optional fields) |
| GET | `/profiles/{id}/forecast/month`, `/forecast/year` | WRAP + DERIVED |
| GET | `/profiles/{id}/solar-return` | NEW |
| POST/GET/DELETE | `/compatibility`, `/compatibility/{id}` | WRAP (family NEW) |
| GET | `/profiles/{id}/acg/lines` | WRAP |
| GET | `/profiles/{id}/acg/heat/{goal}`, `/acg/lines/{body}/{angle}/places` | DERIVED |
| GET | `/profiles/{id}/acg/places/{place_id}`, `/acg/point` | WRAP + DERIVED |
| GET | `/profiles/{id}/acg/countries/{iso2}`, `/acg/regions/{id}` | WRAP |
| POST | `/profiles/{id}/acg/recommendations` | WRAP |
| GET | `/geo/countries.geojson`, `/geo/regions/{iso2}.geojson` | WRAP (static) |
| GET | `/profiles/{id}/calendar/months/{m}`, `/days/{d}`, `/items/{id}`, `/periods`, `/year` | WRAP |
| GET | `/profiles/{id}/best-days`, `/best-days/{activity}/{date}` | WRAP |
| GET | `/profiles/{id}/notification-candidates` | WRAP |
| POST/GET/DELETE | `/ask/threads…`, `/ask/messages/{id}/feedback` | NEW |
| GET/DELETE | `/reports`, `/reports/{id}` | NEW |
| GET | `/jobs/{job_id}` | NEW (infra) |
| GET | `/meta/catalogue`, `/meta/config` | DERIVED / NEW |

## 10. Mock server (`mock-api/`)

- Node + Fastify + TypeScript. Routes generated from `openapi.yaml`; responses validated against the same zod
  schemas the app uses.
- **Fixtures are built, not hand-written:** `mock-api/scripts/build-fixtures.ts` reads the raw fixture pack (§11)
  and applies the mapping rules of this file (§6, the per-endpoint mapping tables) to produce API-shaped JSON in
  `mock-api/fixtures/`. The script is the executable version of this contract and a reference for the backend agent.
- Seed state: one user (`demo@example.com`, any code `000000`), self profile = the 1979-03-30 06:30 Sofia chart,
  three more profiles (partner, colleague, child) mapped to the other fixture charts. New profiles created in the
  mock reuse the nearest fixture chart (by `chart_key` hash) for their data.
- Jobs: the first `GET` of a generated resource returns `202` and completes after `MOCK_JOB_SECONDS` (default 6 s)
  with realistic stage progression from the real manifests.
- Scenarios (header `X-Mock-Scenario` or the dev menu): `ready` (default) · `slow` (jobs 90 s) · `fail` (jobs fail) ·
  `absent_polar` (relocation absent) · `empty_day` · `needs_goal` · `thin_result` · `new_off` (every NEW endpoint
  returns `404`, to test the flag fallbacks) · `rate_limited` · `offline` (connection refused).
- **Mock clock:** the fixtures are dated (calendar horizon from 2026-09-28, readings for 2026-09-29). The mock
  answers with header `X-Mock-Today: 2026-09-29`; in non-production builds the app's `todayLocal()` honours it
  (dev menu "Use fixture date", on by default with the mock) so "today" lands inside the fixture horizons.
- Ask: scripted SSE streams (FE_09 §7) that reuse text fragments from the fixture readings. **Synthetic fixtures
  (Ask, Solar Return, element notes, domains) must reuse sentences from real readings; never invent astrology.**

## 11. Fixture pack (Radul prepares; person labels anonymised to "Person A/B")

| Layer | Files | Note |
|---|---|---|
| Natal | `runs/20260924-102926_26p_1988-12-28/` (`chart`, `l4_output`, wheel `.light/.dark.svg`); `runs/20260922-181953_w1d_1984-06-12/` (same files) | 17-section model |
| Natal (to generate) | a fresh `run.py` run for **1979-03-30 06:30 Sofia**, the reference chart used by the calendar, predictive and ACG fixtures | the July run predates the 17-section model |
| Wheel parity | the three charts above with their `.light.svg` / `.dark.svg`; `Chart_wheel/wheel*.svg` + its default input | FE_05 §2.5 |
| Synastry | `synastry_run/20260702-111541_ra2_…/` (personal) | to generate: `general` and `professional` for 1979-03-30 × 1988-12-28 |
| Predictive | `prediction_run/20260929-130811_qpm/` (day, month, year, general, with calendar context); `20260929-135552_9r2/` (month) | to generate: `personal` and `professional` for day, month, year on 1979-03-30 |
| ACG map | `acg_run/_cache/<chart_key of 1979-03-30>/` (`acg.geojson`, `acg_parans.geojson`, `city_scan.json`, all 11 `goal_heat_*.geojson`) | |
| ACG city | `acg_run/20260929-105635_kgc/`, `acg_run/20260929-105241_zs2/` | the second was queried as "Instanbul" and resolved to Antwerp (lat 51.23, lon 4.47). Relabel it Antwerp; it is the reason for FE_03 §4 confirmation |
| ACG recommend | `acg_run/20260928-114920_2xr/recommend_overall_world_…json`, `20260928-113431_8l9/recommend_love_world_…json` | to generate: `career` world with the ACG_11 `by_line` output |
| ACG areas (to generate) | `--country TR`, `--country DE`, `--region <Antalya admin1_id>`; `--lat 70 --lon 25` (relocation absent) | |
| Calendar | `cal_run/20260929-130418_c7m_1979-03-30/` (all modes), `cal_run/_collective/2026.json`, `2027.json` | |

## 12. Acceptance (contract)

| # | Check |
|---|---|
| AC1 | `openapi.yaml` covers every endpoint and type in this file; `schema.d.ts` and the zod schemas are generated from it in CI. |
| AC2 | Every mock fixture validates against its schema; `build-fixtures.ts` is deterministic (same pack → same bytes). |
| AC3 | Masking: a key scan of all fixtures finds none of the keys `whole_sign`, `whole_sign_cusps`, `classifications`, `derived_points`, `planetary_day`, `planetary_hour`, `principle_ids`, `trace`, `sentences`, `source_ids`, `contributors`, `S`, `P`, `N`, `S_agg`, `R`, `factors`, `models`, `schema_version`; and no string value contains an unambiguous mask term: placidus, whole sign, whole-sign, triplicity, domicile, detriment, exaltation, planetary day, planetary hour, time lord, profection, lot of fortune, lot of spirit, tam burç, üçlük, yücelim (case-insensitive, Turkish-aware). Ordinary words that are also technical terms ("face", "fall", "modern") are checked only in labels, not in reading prose. |
| AC4 | Language: for every endpoint, `lang=tr` and `lang=en` fixtures differ only in human-readable strings (a structural diff is empty). |
| AC5 | Jobs: each generated resource in the mock goes `202 → job running → succeeded → 200`; `?retry=true` restarts a failed job. |
| AC6 | Every `NEW` endpoint returns `404` under the `new_off` scenario and the app degrades per its flag. |
