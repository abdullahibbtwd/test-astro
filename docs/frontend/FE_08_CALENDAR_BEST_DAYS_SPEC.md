# FE 08: Calendar, Best Days, notifications

*Brief §11 (personal calendar + push notifications) and §12 (Best Days). API: FE_02 §7.8–7.9. Backend: CAL_00–CAL_05
(12-month calendar, 90-day Best Days, modern-only, deterministic scores, texts generated lazily, notification
candidates as data; scheduling and sending are the app's job, CAL_00 D4).*

## 1. Where it lives
Ahead tab → segment **Calendar** (FE_01 §3.2). Best Days is reached from the Calendar header, from Today ("Good for
today"), from notifications and from Home "Coming up". The active profile applies (FE_04 §1.4).

## 2. Calendar month (`ahead/calendar`)

`GET /profiles/{id}/calendar/months/{YYYY-MM}`. Month navigator ‹ › limited to the 12-month horizon.

### 2.1 Grid (`MonthGrid`)
- Weeks start on **Monday** (TR and EN locale for this market). Today outlined; days outside the horizon disabled.
- Cell: day number; a thin ring in the day's **tone** level colour (`favorable` → plus, `mixed` → mixed,
  `quiet` → neutral (no ring), `challenging` → minus); up to three micro-icons in priority order: eclipse,
  new / full moon, a station (a planet turning retrograde or direct), a major transit exact date.
- Filter chips above the grid: **All** + the 11 goals. With a goal selected, the ring shows that goal's `DayBand`
  (`goals[g]`) instead of the tone, and days inside an active period of that goal get a soft band tint.
- Tap a day → Day detail (§3).

### 2.2 Below the grid ("This month")
In date order: lunations and eclipses (`EventRow`), retrograde periods overlapping the month (`RetrogradeRef` rows
with date range), major transits (`TransitRow`), periods (`PeriodRow`). Every row → `calendar/item/[id]`.

### 2.3 Header actions
**Best Days** (§5) · **Periods** (§4.2) · **Year overview** (§4.3).

## 3. Day detail (`calendar/day/[date]`)

`GET /profiles/{id}/calendar/days/{date}`.

| Order | Block | Binding |
|---|---|---|
| 1 | Date, tone chip | `date`, `tone_label` |
| 2 | Day note (serif, if present) | `day_note` (GeneratedPart; `null` = none) |
| 3 | The Moon: phase glyph + label, sign, void-of-course windows, retrograde planets | `moon`, `retrograde` |
| 4 | Events: `EventRow`s; rows with `has_text` expand to their text (§4.1) | `events` |
| 5 | Transits active today: `TransitRow`s with phase | `transits` |
| 6 | Periods active today: `PeriodRow`s | `active_periods` |
| 7 | Life areas: 11 band chips | `goals` |
| 8 | Good for: activity chips (excellent / good) → Best Days detail | `best_activities` |
| 9 | Ask about this day → Ask with `context.date` | — |

## 4. Items, periods, year

### 4.1 Item detail (`calendar/item/[id]`)
`GET /profiles/{id}/calendar/items/{id}`. Title = `label`, kind icon, dates (start – end; exact dates for transits;
the peak for periods), period goal + kind chip, lunation sign + life-area name (`house_label`), then the text:
- `text` ready → serif text;
- `text.status = pending` → a short `JobProgress` (lazy generation, usually seconds);
- `text: null` → nothing more. **Label only by design** (minor transits, units without grounding, CAL_03): no
  placeholder, no "coming soon" (C2).
Actions: **Show on calendar** (opens the month with the item's dates highlighted), **Ask about this**.

### 4.2 Periods timeline (`calendar/periods`)
`GET /profiles/{id}/calendar/periods`. Eleven rows (goals, catalogue order) × a horizontally scrollable 12-month
axis with month ticks and a "today" line. Bars: favourable = `plus`, challenging = `minus`; `strength: strong` bars
thicker and more saturated. Tap a bar → item detail. A **List** toggle shows the same periods grouped by goal
(the accessible alternative).

### 4.3 Year overview (`calendar/year`)
`GET /profiles/{id}/calendar/year`: sections Eclipses · New and full moons (grouped by month) · Retrograde periods
(bars on a 12-month axis) · Major transits (date ranges) · Strong periods. Every row → item detail.

## 5. Best Days (brief §12)

`GET /profiles/{id}/best-days` (90 days, all 10 activities).

### 5.1 Activities (`best-days/index`)
A grid of 10 tiles in catalogue order — Love · Meetings · Business · Signing a contract · Important conversation ·
Travel · Shopping · Starting a project · Job interview · Moving (labels from `catalogue.activities`). Each tile:
icon, label, "Next good day: 3 Eki" (first `top_days` entry ≥ today) and the count of good + excellent days in the
horizon. Header note: "Next 90 days".

### 5.2 Activity (`best-days/[activity]`)
- A 3-month strip of mini month grids coloured by grade: excellent `strongPlus`, good `plus`, neutral none,
  avoid `minus` outline (hatched pattern for colour-blind safety). Tap a day → §5.3.
- **Top days** (date chips) · **Good windows** ("9–14 Eki · 6 gün") · **Days to avoid** (date chips).
- Empty lists are hidden (C1).

### 5.3 Day for an activity (`best-days/[activity]/[date]`)
`GET /profiles/{id}/best-days/{activity}/{date}`: grade chip + label; **What helps** (positive reason labels) and
**What makes it harder** (negative reason labels) as plain rows; the text when present (`null` → nothing);
**Remind me** (a one-off local notification at 09:00 that day, counted against the caps in §6.2); **Ask about this day**.

The app never shows the underlying numbers (`R`, factors, contributions, thresholds) (C4).

## 6. Notifications (local, F15)

### 6.1 Source
For the **self profile only** (v1): `GET /profiles/{self}/notification-candidates?from=<today>&to=<today+14>`.
Candidates carry `type`, `priority` (**1 = highest**, CAL_02 §6), `trigger_date`, `suggested_time`, localised `text`
and `deep_link`. The backend never schedules or sends (CAL_00 D4).

### 6.2 Scheduler (`lib/notifications.ts`, deterministic, unit-tested)
1. Drop candidates whose `type` is disabled in `me.notification_prefs.types`, and those whose trigger moment is past.
2. Trigger moment = `trigger_date` at `prefs.time` (default `09:00`, which equals the backend's
   `suggested_time`) **in `me.current_place.tz`**, converted to an absolute instant for the OS scheduler. Inside
   quiet hours → move to `quiet_hours.end` the same day.
3. Per local day keep at most `max_per_day` (default 1): the lowest `priority` number, ties by the backend's order.
4. Across any rolling 7 days keep at most `max_per_week` (default 3), again preferring lower `priority` numbers,
   then earlier dates. "Remind me" items (§5.3) count too and win ties.
5. Schedule with the candidate `id` as the identifier (idempotent): cancel scheduled items that are no longer
   selected, add new ones. Content: title `{{APP_NAME}}`, body = `text`, data = `deep_link`.
6. Run on: app foreground (at most once per local day), a daily background task (`expo-background-task`),
   language change, current-place change, prefs change, self birth-data change. Sign-out and account deletion
   cancel everything.

### 6.3 Settings (`profile/notifications`)
Master switch · per-type switches with the catalogue labels and one-line chrome descriptions · delivery time ·
max per day (1–2) · max per week (1–7) · quiet hours · **Send a test notification**. Changes `PATCH /me
{ notification_prefs }` and reschedule. If the OS permission is denied, show "Turn on notifications in Settings"
with a deep link to the system settings.

### 6.4 Deep links

| `deep_link.view` | `ref` example | Route |
|---|---|---|
| `best_days` | `win:contract:2026-09-29` | `best-days/contract?date=2026-09-29` (activity screen scrolled to the window) |
| `period` | `per:career:challenging:2026-11-20` | `calendar/item/per:career:challenging:2026-11-20` |
| `event` | `lun:2026-10-10:new`, `stn:mercury:R:2026-10-24`, `stp:…`, `ecl:2027-02-20:lunar` | `calendar/item/{ref}` |
| unknown | | Calendar tab |

Opening a notification logs `notification_open {type}`.

## 7. Acceptance

| # | Check |
|---|---|
| CB1 | Month grid for the fixture month 2026-10 shows tone rings, the new-moon icon on 10 Oct and the full-moon icon on 26 Oct; selecting "Family" switches rings to family bands (9 Oct challenging). |
| CB2 | Day detail renders every block present in the fixture; an event with `has_text: false` does not expand; an item with `text: null` shows only its label and dates. |
| CB3 | Periods timeline shows every period of `periods.json` in the right row and date span; the list toggle shows the same set. |
| CB4 | Best Days: 10 activities; the contract activity shows 29–30 Sep as top days and the fixture windows; the day detail shows positive and negative reason labels with no numbers. |
| CB5 | Scheduler unit tests: caps (1/day, 3/week), priority order, quiet-hours shift, tz change (Istanbul → Tokyo) moves trigger instants, idempotent rescheduling, disabled types excluded, "Remind me" counted. |
| CB6 | Each deep-link view opens the right screen from a cold start. |
| CB7 | Notification prefs round-trip through `PATCH /me` and survive reinstall (restored from `me`). |
