# FE 03: onboarding, accounts, My Charts, settings

*Brief §2 (registration, profile, My Charts) and the account surfaces every app needs. API: FE_02 §7.1, §7.11.*

## 1. Flow overview

```
first launch ─► Language ─► Welcome ─► Sign in (Apple · Google · Email code)
                                             │
             signed in, no self profile ─────┴─► Consent ─► Name ─► Birth date ─► Birth time
                                                  ─► Birth place (confirm) ══ POST /profiles (self) starts the natal job
                                                  ─► Current place ─► Details (optional) ─► Notifications ─► Building ─► Home
             signed in, self profile exists ─────► Home
```

One question per screen, a thin progress bar, Back always available, state kept if the app is killed mid-flow
(persist the draft in MMKV). All copy is chrome (FE_01 §4) and goes through native review.

## 2. Sign in

### 2.1 Welcome
- `{{APP_NAME}}` wordmark, one line of value proposition, and the four questions as a quiet list
  (Who am I? · What's ahead? · Who fits me? · Where should I be?).
- Buttons: iOS **Continue with Apple**, **Continue with Google**, **Continue with email**; Android: Google, email.
- Footer: Terms · Privacy (links from `meta/config.links`) and the general disclaimer (FE_01 C6).

### 2.2 Email code
- Email field (keyboard `email-address`, autofill `email`), **Send code** → `POST /auth/email/start`.
- Code screen: 6 separate digit cells with one hidden input (`textContentType="oneTimeCode"`), paste support,
  auto-submit on 6 digits → `POST /auth/email/verify`. Resend enabled after 30 s. Wrong code → inline error, cells
  shake (skip shake with Reduce Motion).

### 2.3 Apple / Google
Native SDK sheets. Apple's `full_name` (first time only) prefills the Name step.

### 2.4 Session
Store `access_token`, `refresh_token` in SecureStore. Refresh on 401 once, then sign out. On sign-in, `PATCH /me`
with the language chosen on first launch if it differs from `me.language`.

## 3. Onboarding steps

| Step | Field | Control | Validation | API |
|---|---|---|---|---|
| Language (first launch, before sign-in) | app language | two large choices: Türkçe · English | required | stored locally; `PATCH /me` after sign-in |
| Consent | birth-data processing (required), marketing (optional, off) | checkboxes + links | required box ticked | `PATCH /me { consents }` |
| Name | display name | text, prefilled from Apple/Google | 1–40 chars, trimmed | `PATCH /me { display_name }`; also the self profile `label` |
| Birth date | date | native picker (iOS wheels, Android calendar), locale format | 1900-01-01 … today | draft |
| Birth time | exact local time | native 24-hour time picker | required (F9) | draft |
| Birth place | place | `PlaceSearchField` `kind=birth` + confirm card (§4) | a confirmed `place_id` | `POST /profiles` (self) on confirm |
| Current place | where the user lives now | chips: **Same as birthplace** · **Use my location** · search | optional (default: birthplace) | `PATCH /me { current_place_id }` |
| Details | gender | chips: Female · Male · Other · Prefer not to say; **Skip** | optional | `PATCH /profiles/{self}` |
| Notifications | permission | explainer + **Allow** / **Not now** | — | OS prompt; `PATCH /me { notification_prefs.enabled }` |
| Building | — | §5 | — | `GET /profiles/{self}/chart` |

### 3.1 Birth time copy
Helper under the picker (chrome, native review):
- TR: "Kesin saat önemli: yükselen burcun ve evlerin birkaç dakikada değişebilir. Doğum belgene, hastane
  kayıtlarına bakabilir ya da ailene sorabilirsin."
- EN: "The exact time matters: your rising sign and houses can change within minutes. Check your birth certificate
  or hospital records, or ask your family."

No "I don't know" option (F9).

### 3.2 Consent
Consent is **explicit and separate** from the terms (KVKK "açık rıza"). The birth-data box text is supplied by
Radul's legal counsel; until then use a clearly marked placeholder string (`consent.birthData.placeholder`) that
fails the release checklist. Store version + timestamp via `PATCH /me`.

### 3.3 Creating the self profile early
Create the self profile as soon as the birth place is confirmed, so the natal reading job (≈ 1.5 min) runs while
the user finishes the remaining steps. If the user goes back and changes date, time or place, `PATCH` the profile
(new `chart_key`, new job).

## 4. Place search and confirmation (`PlaceSearchField`)

A real failure in the backend fixtures: the query "Instanbul" was geocoded to **Antwerp** (lat 51.23, lon 4.47)
and a whole reading was produced for the wrong city. The UI must make that impossible:

- Free text is **never** submitted. The user must pick a candidate from `GET /places/search`.
- Debounce 250 ms, min 2 characters, show up to 8 candidates: **name** (bold), `admin1, country_name` (secondary),
  country flag emoji from `country_code`. Candidates with the same name are disambiguated by the secondary line.
- Turkish-aware matching is the server's job; the field only lowercases with the active locale.
- After selection, a **confirm card** shows "Plovdiv · Plovdiv · Bulgaria" and the question "Is this the right
  place?" with **Yes** / **Change**. Only **Yes** stores the `place_id`.
- `kind=birth` for birthplaces (any settlement), `kind=city` for map search, `kind=area` for countries / regions.
- Empty result: "No places found. Check the spelling or try a nearby larger town."
- Recent selections (last 5, local) appear when the field is focused and empty.

## 5. Building screen

1. `GET /profiles/{self}/chart` (instant). Animate the wheel reveal (FE_01 §5.5) with the big three below it:
   "Güneş Oğlak · Ay Başak · Yükselen Koç" (labels from the catalogue; sign glyphs from `wheel-core`).
2. Show the natal job's progress in a single quiet line ("Your full reading is being written. We'll let you know
   when it's ready.") — the user does not wait for it.
3. **Continue** → Home. When the natal job finishes, show the toast from FE_01 §3.4.

## 6. Current location

- Settings row "Current location" shows `me.current_place` and opens the same picker as onboarding.
- **Use my location:** request foreground location permission once, then `GET /places/reverse`; if it returns
  `null` (no gazetteer city within 75 km), fall back to search with a hint.
- Changing it changes "today" (F10) and invalidates day-level caches, calendar months, Best Days and notification
  candidates; reschedule local notifications (FE_08 §6).
- Time-zone mismatch banner: FE_01 §8.

## 7. My Charts (birth profiles)

Brief §2: the user saves additional profiles (partner, children, parents, family, friends, colleagues, business
partners) and reuses them for compatibility.

### 7.1 List (`profile/charts`)
- The self profile first with a "You / Sen" badge, then the others by creation date.
- Row: a round avatar with the **sun sign glyph**, `label`, relation label, formatted birth date.
- Swipe (or long-press menu) → Delete (not for self) with a confirm dialog naming the person.
- **Add person** button (limit 50, FE_02 §7.1).

### 7.2 Add / edit
- Step 1: relation chips (Partner · Child · Parent · Family · Friend · Colleague · Business partner · Other).
- Then name, birth date, birth time, birth place (same controls and rules as onboarding), optional current place
  ("Where does this person live now?", used for their day boundaries).
- Save → `POST /profiles` → the detail screen with two suggested actions: **View chart** and **Compare with you**
  (opens FE_06 with both people preselected).
- Editing date / time / place shows: "Changing birth data recalculates this chart and every reading for it." →
  confirm → `PATCH`.

### 7.3 Detail (`profile/charts/[id]`)
Big three, birth date, time, place, time zone, relation. Actions: **Chart** (sets the active profile, opens the Chart
tab) · **Forecast** (Ahead tab) · **Map** · **Compare** · **Edit** · **Delete**.

## 8. Profile and settings (avatar menu)

| Row | Behaviour |
|---|---|
| Header | name, email, sign-in method |
| My Charts | §7 |
| Saved reports | §9 |
| Language | Türkçe / English → `PATCH /me`, refetch (FE_01 §3.3) |
| Appearance | System / Light / Dark → `PATCH /me { theme }` |
| Current location | §6 |
| Notifications | FE_08 §6.3 |
| Privacy | consent status and date; **Download my data** (`POST /me/export`, "We'll email you a link"); **Delete account** (§8.1) |
| About | version, the general disclaimer, credits (§8.2), terms, privacy, support |
| Sign out | `POST /auth/logout`, clear SecureStore, the query cache and scheduled notifications |

### 8.1 Delete account
Two steps: an explanation of what is deleted (profiles, readings, conversations) and when (sessions end now,
data within 30 days), then type the confirmation word (TR "SİL", EN "DELETE") → `DELETE /me` → sign out.

### 8.2 Credits (required attributions)
"Contains data from GeoNames (geonames.org), CC BY 4.0" (ACG_07 D16) · "Made with Natural Earth" · WorldClim
(CC BY 4.0, ACG_11 climate) · the map tile provider's and OpenStreetMap's attribution as the chosen style requires
(also shown on the map, FE_07 §2) · "Planetary positions: Swiss Ephemeris (Astrodienst)" · font licences (OFL).

## 9. Saved reports (`profile/reports`)

`GET /reports`: filter chips by type (Chart readings · Compatibility · Places · Recommendations · Forecasts ·
Solar Return), rows with `title`, `subtitle`, date, tap → `route`, swipe → delete (`DELETE /reports/{id}`).
Empty state: "Readings you open are saved here."

## 10. Acceptance

| # | Check |
|---|---|
| ON1 | Fresh install → onboarding completes on iOS and Android with each sign-in method (mock); the self profile exists and the natal job was started at the birth-place step (the mock logs the `POST` before the Current place step). |
| ON2 | Killing the app mid-onboarding and relaunching resumes at the same step with the entered values. |
| ON3 | Place search: typing "Instanbul" never produces a place without an explicit candidate tap + **Yes**; two same-name candidates (e.g. "Alexandria" EG vs US) show different secondary lines. |
| ON4 | Birth date outside 1900…today and an empty time cannot be submitted. |
| ON5 | Changing current location changes `todayLocal()` for a tz across the date line (mock Tokyo vs Istanbul) and reschedules notifications. |
| ON6 | My Charts: add, edit (with the recalculation warning), delete; the self profile cannot be deleted; "Compare with you" opens FE_06 preselected. |
| ON7 | Delete account requires the typed confirmation, calls `DELETE /me`, and leaves no tokens, cache or scheduled notifications. |
| ON8 | All onboarding and settings strings exist in TR and EN; the consent placeholder string is detected by the release checklist. |
