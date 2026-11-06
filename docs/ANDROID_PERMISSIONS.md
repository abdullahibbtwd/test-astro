# Android permissions audit (merged manifest)

Source: last local release merge under `frontend/android/app/build/intermediates/merged_manifests/release/` (CNG output; regenerate with prebuild). Re-audit after dependency bumps.

Legend: **KEEP** required for a shipped feature · **FLAG** review / likely unnecessary · **DROP** removed by `withAndroidReleaseHardening` when possible.

## Core / feature permissions

| Permission | Source (typical) | Verdict | Why |
| --- | --- | --- | --- |
| `INTERNET` | Expo / RN | **KEEP** | API, auth, map styles, tiles |
| `ACCESS_NETWORK_STATE` | NetInfo / RN | **KEEP** | Offline UI / reconnect |
| `ACCESS_WIFI_STATE` | MapLibre / transitive | **FLAG** | Prefer network-state only; confirm after next MapLibre upgrade whether still declared |
| `ACCESS_COARSE_LOCATION` | `expo-location`, MapLibre | **KEEP** | Optional “use current place” for birth/current location |
| `ACCESS_FINE_LOCATION` | `expo-location`, MapLibre | **KEEP** | Same; requested at runtime only when user taps locate |
| `POST_NOTIFICATIONS` | `expo-notifications` | **KEEP** | Android 13+ runtime notification permission |
| `RECEIVE_BOOT_COMPLETED` | `expo-notifications` | **KEEP** | Reschedule local reminders after reboot |
| `VIBRATE` | notifications / channel | **KEEP** | Channel defaults |
| `WAKE_LOCK` | Play services / notifications | **KEEP** | Alarm delivery for scheduled locals |
| `USE_BIOMETRIC` / `USE_FINGERPRINT` | `expo-secure-store` | **KEEP** | Secure storage backing |
| `READ_EXTERNAL_STORAGE` (maxSdk 32) | `expo-media-library` / file-system | **FLAG** | Legacy ≤API 32; needed only if saving charts on old devices |
| `WRITE_EXTERNAL_STORAGE` (maxSdk 32) | `expo-media-library` | **FLAG** | Same — save-to-gallery on ≤32 |
| `READ_MEDIA_IMAGES` | media-library granular | **DROP intent** | App only **saves** exports; `granularPermissions: []` in `app.json` to avoid this |
| `READ_MEDIA_VISUAL_USER_SELECTED` | `expo-media-library` plugin (always) | **FLAG** | Pulled by library even for save; cannot remove without forking plugin — disclose if retained |
| `SYSTEM_ALERT_WINDOW` | RN debug overlay / stale main merge | **DROP** | Removed by `withAndroidReleaseHardening` — not needed in store builds |
| `FOREGROUND_SERVICE` | `expo-notifications` / FCM stub | **FLAG** | No custom FGS in app code; review if Play declares unused FGS types |
| `com.google.android.c2dm.permission.RECEIVE` | FCM stub in expo-notifications | **FLAG** | Remote push **not** implemented; local-only reminders — consider future trim |
| Launcher **badge** vendor permissions (Samsung/HTC/Sony/… ) | shortcuts-badger via notifications | **FLAG** | Optional badge UX; not required for scheduling |

Package-scoped `*.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` is normal AndroidX and **KEEP**.

## Exact alarms (Android 12+)

`expo-notifications` schedules with `AlarmManagerCompat.setExactAndAllowWhileIdle` **only when** `AlarmManager.canScheduleExactAlarms()` is true (`ExpoSchedulingDelegate`).

- The app **does not** declare `SCHEDULE_EXACT_ALARM` / `USE_EXACT_ALARM`.
- On Android 12+ without exact-alarm grant, scheduling **falls back** to inexact `setAndAllowWhileIdle` — reminders may drift.
- **Android 13+ notifications:** `POST_NOTIFICATIONS` is declared; the UI calls `Notifications.requestPermissionsAsync()` in onboarding / Account / Best Days. Without grant, `synchronizeNotifications` no-ops (no schedule).

Device QA: deny notification permission → no crashes, no schedules; grant → schedules; reboot → `RECEIVE_BOOT_COMPLETED` receiver present (OS may still limit exactness).

## Location

Location is **runtime-optional** (onboarding / account “current place”). Birth place can be search-only. Play listing should mark location as optional, not required for install.

## Storage / photos

PDF/chart export uses share sheet + optional `MediaLibrary.saveToLibraryAsync`. Do not request broad photo **library read** for launch. Re-check merged manifest after every Expo SDK bump.

## How to refresh this list

```bash
cd frontend
npm run prebuild:android
# Build a release variant locally or inspect:
# android/app/build/intermediates/merged_manifests/release/processReleaseManifest/AndroidManifest.xml
rg 'uses-permission' android/app/build/intermediates/merged_manifests/release -n
```
