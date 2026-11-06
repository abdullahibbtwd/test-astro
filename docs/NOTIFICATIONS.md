# Notifications: what exists vs launch options

**Status:** Local scheduling is implemented. Remote push and transactional email for reminders are **not** implemented. This doc is read-only guidance — no code changes required to “enable” channels that do not exist yet.

## What exists today (local only)

| Capability | Where | Behavior |
| --- | --- | --- |
| Candidate generation | `GET /profiles/{id}/notification-candidates` (calendar-backed) | Server returns upcoming reminder candidates for a date window |
| Preference storage | `Me.notification_prefs` via `PATCH /me` | Enabled flag + per-type toggles persisted on the account |
| Permission prompt | Onboarding + Account notifications UI | `expo-notifications` permission request |
| Scheduling | `frontend/src/lib/notifications.ts` → `synchronizeNotifications` | Pulls candidates, merges manual reminders, `scheduleNotificationAsync` with DATE triggers |
| Android channel | `prepareNotifications` | Channel id `astrology` |
| Cancel on logout / disable | `clearSession`, prefs toggle | `cancelAllScheduledNotificationsAsync` |
| Lifecycle handler | `frontend/src/lib/NotificationLifecycle.tsx` | Foreground presentation handler |

**Not present in repo (searched):** Expo push tokens, FCM/APNs server send, Expo push receipts, Resend/SMTP reminder mailers, device token storage tables.

Auth **email OTP** (Supabase) is unrelated to astrology reminder delivery.

iOS entitlements historically use `aps-environment: development` when a native tree is generated — production push would need a production entitlement + Apple setup even after app code lands.

## What launch needs (decision)

| Channel | Needed for Android tester? | Needed for store launch? | Notes |
| --- | --- | --- | --- |
| **Local** | Yes (already) | Yes | Sufficient for calendar-style reminders while the app can reschedule |
| **Push (FCM / APNs via Expo)** | Optional | Recommended if reminders must fire after force-quit / across devices | Requires Expo project credentials, token registration API, backend sender or Expo push service |
| **Email reminders** | Optional | Optional / compliance-sensitive | Needs ESP (e.g. Resend), templates EN/TR, unsubscribe, and a scheduler |

## Gap: remote push

**Missing pieces**

1. Client: `getExpoPushTokenAsync` (or native FCM/APNs), persist token to backend  
2. Backend: `device_tokens` (or equivalent) per user, register/unregister routes  
3. Worker/cron: turn `notification-candidates` into push sends (Expo Push API or FCM/APNs)  
4. Ops: Expo/Apple/Google credentials, production `aps-environment`, Play FCM  
5. UX: permission rationale, failure when token missing, quiet hours already partly in prefs  

**Rough effort:** **M** (≈ 3–6 eng-days) for Expo push end-to-end excluding store credential chase; **+S** for TestFlight/Play credential wiring.

## Gap: email reminders

**Missing pieces**

1. ESP integration (API key only on server)  
2. Templates EN/TR + legal footer / unsubscribe  
3. Job that emails candidates (digest vs per-event)  
4. Preference: marketing vs product reminders already partially separated (`consents.marketing` vs `notification_prefs`)  

**Rough effort:** **M** (≈ 3–5 eng-days) for per-event or daily digest; **+S** for compliance copy.

## Recommended default for near-term launch

1. Ship **local notifications only** (current path).  
2. Document in store listing / support that reminders require notification permission and periodic app open to refresh the schedule (OS limits on scheduled locals).  
3. Defer push/email until after Android production core features unless product insists on cross-device delivery day one.

## Effort summary

| Work item | Effort | Depends on |
| --- | ---: | --- |
| Keep / harden local sync + Android permission E2E | **S** | Device QA |
| Expo push (client token + API + sender) | **M** | Expo/Apple/Google accounts |
| Email reminder digest | **M** | ESP + legal copy |
| Full push + email + admin tooling | **L** | Both channels |

## Decision log

| Date | Decision | By |
| --- | --- | --- |
| _pending_ | Local-only vs add push/email for launch | |
