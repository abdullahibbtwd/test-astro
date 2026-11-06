# Android device test checklist (release candidate)

Use a physical device or emulator with a **preview** or **production** build (not only Metro). Record build ID / versionCode. Do not publish from this checklist.

Identity under test must match `frontend/config/identity.json` (package + scheme).

## 1. Fresh install

- [ ] Uninstall any prior build of the same package
- [ ] Install APK (preview) or internal AAB track build
- [ ] Cold start → splash → first-run language / welcome without crash
- [ ] No prompt for unrelated permissions before user action

## 2. Upgrade install

- [ ] Install older build (prior versionCode), sign in, create/open a profile
- [ ] Install newer build over it (`adb install -r` or Play internal)
- [ ] Session still valid **or** clean re-auth without data corruption
- [ ] Profiles / prefs still listed after upgrade

## 3. Login — email

- [ ] Request email OTP / magic link with a real inbox
- [ ] Complete sign-in; Account shows the correct email
- [ ] Wrong code fails clearly; resend works

## 4. Login — Google

- [ ] Continue with Google (native) succeeds on a test account
- [ ] Account email matches Google account
- [ ] After logout, Google sign-in works again
- [ ] Fail path: cancel Google sheet → app remains usable

## 5. Offline start

- [ ] Enable airplane mode (or disable Wi‑Fi+cellular)
- [ ] Kill app → relaunch
- [ ] App opens without hard crash; offline/empty states shown where expected
- [ ] Map falls back to outline preview caption when styles/tiles unavailable
- [ ] Disable airplane mode → pull-to-refresh / navigation recovers

## 6. Kill and restart persistence

- [ ] Sign in, set language, enable notification prefs, set current place
- [ ] Force-stop from system settings → relaunch
- [ ] Still signed in; language / prefs / place persist
- [ ] Open a cached reading/report if one existed

## 7. Map tiles

- [ ] With API `ASTRO_MAP_STYLE_*` set: Map tab loads vector tiles; attribution visible
- [ ] Toggle light/dark: matching style
- [ ] Toggle EN/TR: labels prefer `name:en` / `name:tr` when present
- [ ] ACG lines / heat still render on preview fallback if style cleared

## 8. Notification scheduling

- [ ] Android 13+: notification permission prompt appears when enabling reminders
- [ ] Deny permission → no crash; no scheduled items
- [ ] Grant permission → enable prefs → schedule candidates / Best Day reminder
- [ ] Trigger or inspect pending (`adb shell dumpsys alarm` / in-app test notification)
- [ ] Reboot device → reminders still plausible (may be inexact without exact-alarm grant)
- [ ] Disable prefs / logout → schedules cleared

## 9. PDF export

- [ ] Export chart PDF → share sheet opens; file opens in a PDF viewer
- [ ] Export fuller report if available → pages render; TR characters OK if TR locale
- [ ] Optional save-to-photos path: grant only what’s prompted; image appears in gallery

## 10. Account deletion

- [ ] Use a disposable test account only
- [ ] Account → delete account → confirm
- [ ] App returns to signed-out state
- [ ] Re-login with same email creates a **fresh** account (or blocked per product rules)
- [ ] Confirm API/Supabase user removed or anonymized per backend behavior

## Sign-off

| Field | Value |
| --- | --- |
| Build profile | preview / production |
| versionName / versionCode | |
| Device / OS | |
| Tester | |
| Date | |
| Result | PASS / FAIL (list defects) |
