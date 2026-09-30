# Latest build progress

## Reading and saved reports — 30 September 2026

The Android preview has been updated in place. Reopen it with `D:\Dev\astrology-app\Open Android Preview.cmd`.

### Try it

1. Sign in with **demo@example.com**, code **000000**, if needed.
2. Open **Chart**, choose **Person B** or **Person C**, scroll below the wheel and choose **Read your chart**.
3. Use **Contents** to open an individual section. Expand/collapse sections, copy their exact text, or open the native share sheet.
4. Open the profile/avatar menu → **Saved reports**. Reports show a date and profile name, can be filtered, reopened, and deleted with confirmation.

Person A has no natal reading in the supplied source fixtures. Its missing reading is shown as an error; no replacement interpretation is invented. Birth calculations and reading generation remain mocked.

### What changed

- API-backed natal document viewer with the supplied titles, parts and sections, serif text, two-line collapsed previews, expand/collapse all and deep-linked section screens.
- Copy and native share actions preserve the complete section text.
- Populated saved-report lifecycle in the mock: records are created only after a reading is ready, separated by language, paginated, filtered, and deleted independently of birth profiles.
- Saved-report deletion refreshes only the report cache so it cannot accidentally regenerate its deleted reference. Profile deletion and birth-data edits remove obsolete mock references.
- Localized retry boundaries for routes; raw error details are not displayed. Telemetry vendor reporting is still unconfigured.
- Long-press deletion with confirmation on non-self My Charts rows; the detail screen retains its accessible Delete action.
- Generation retry errors are contained in the UI and retry responses are schema-validated.

### Verified

- `npm run check`: strict TypeScript and lint pass; 4,451 fixtures validate; **31 Node tests and 5 native component tests pass**.
- `npm run bundle`: Android and iOS JavaScript/Hermes bundles pass. The existing Android development APK runs these updates; no new native dependency was added.
- Android emulator: mock sign-in, pending-to-ready natal reading, section deep link, populated dated saved report and confirmed deletion to the empty state.
- Automated regression coverage includes missing fixtures, ready-only saving, no duplicate references, language/filter isolation, cursor pagination, report and profile deletion, exact section copying, accessible expansion, and recovery without exposing private exception text.
- Screenshot: `artifacts/screenshots/reading-en-dark.png` (local, Git-ignored).

### Still open

The remaining production configuration, iOS device validation, accessibility/performance audit, notifications, global job-ready toast and interactive chart work from `PHASE_1_REPORT.md` remain. This increment completes populated saved-report management and route retry boundaries and starts the chart-reading work; it does not close the entire Phase 1 gate. Real Google/Apple sign-in and production legal content still need configuration. Contents currently opens an inline section list with deep links rather than a bottom sheet.
