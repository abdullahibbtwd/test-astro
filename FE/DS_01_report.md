# Design system Phase 1–2 report — Gate B

Date: 2026-10-05. Gate A was approved by Radul ("Go ahead"). Foundation and components are implemented in an isolated dev gallery. Android review is ready; iOS visual acceptance is still pending. Existing product screens have not been migrated.

## Review the result

- [Side-by-side Android/reference review](D:/Dev/astrology-app/FE/artifacts/design-system/index.html) — Night/Parchment toggle, original kit references, full-resolution native screenshots.
- [Night cards](D:/Dev/astrology-app/FE/artifacts/design-system/night-traits.png)
- [Parchment cards](D:/Dev/astrology-app/FE/artifacts/design-system/parchment-traits.png)
- [Night button states](D:/Dev/astrology-app/FE/artifacts/design-system/night-buttons-lower.png)
- [Parchment button states](D:/Dev/astrology-app/FE/artifacts/design-system/parchment-buttons-lower.png)
- [Turkish typography](D:/Dev/astrology-app/FE/artifacts/design-system/night-type-lower.png)
- [English buttons](D:/Dev/astrology-app/FE/artifacts/design-system/night-buttons-english.png)

The gallery is open in the Android emulator. Its top controls switch themes, languages and panels; longer panels scroll. Selection cards toggle, input fields accept text, and the Patterns panel opens a preview modal. No gallery action calls the API or changes saved account data. The gear overlay in screenshots belongs to the development client.

Route: `astrology-dev://design-system-gallery?theme=night&panel=traits`. Other panels: controls, buttons, type, glyphs, hero, wheel, patterns. Optional `lang=en`. The route is development-only and redirects away in production.

## Implemented

- Immutable kit data in `src/design-system/theme` and `src/design-system/glyphs`.
- Four fonts and both OFL licenses in `assets/fonts/design-system`; all nine copied kit files verified byte-for-byte against the supplied ZIP. [SHA-256 manifest](D:/Dev/astrology-app/FE/artifacts/design-system/kit-checksums.json).
- `ThemeProvider` / `useTheme`: Night by default, explicit Parchment toggle, independent of OS appearance.
- `upper` and `AppText`: Turkish-aware casing, exact font keys and weights, no synthetic fontWeight, font scaling caps, Android font padding disabled.
- Glyph sets, ornaments, Emblem, ChartWheel, Divider, Screen with sky/arch/lower gradient, Title, primary/outline/ghost Button, Field, SelectField, TextInputField and TraitCard.
- Provisional ListRow, ChatBubble and modal Sheet, used only by the gallery. Product navigation/header/tab restyling remains Phase 3.
- Every text style and glyph set is available in the gallery, with both button sizes and disabled variants, input hint/error states, selected/unselected cards, and English/Turkish copy.
- Only missing dependency installed: SDK-compatible `expo-linear-gradient ~57.0.2`. Android debug APK rebuilt and installed without clearing app data.

## Verification

| Check | Result |
|---|---|
| TypeScript `tsc --noEmit` | Passed |
| ESLint on new design system, gallery and tests | Passed |
| Native regression suite | 50 tests passed across 16 suites |
| New font/casing/license checks | 6 passed; every supplied font has Turkish extended glyphs |
| New native behavior checks | Included in the 50: disabled button, Turkish display casing, checkbox toggle, field error replacing hint, disabled select |
| Android native build | Passed; 962 Gradle tasks, 50 executed |
| Android visual review | Captured Night/Parchment controls, cards, typography, icons, hero, ornaments, button variants and provisional patterns; extra scrolled sections and English sample |
| Kit integrity | All 9 source/font/license files unchanged |
| iOS screenshots / native execution | Not performed; Windows host has no local iOS simulator |

Screenshots show the supplied gold/charcoal and parchment/charcoal palettes, Aboreto headings, Poppins body/medium/semibold weights, line artwork and selected-card inversion. Source sizing uses supplied tokens: buttons 56/44, fields 48, standard side padding 32 and card ratio 5:8. These are component-sized values in dp, not screenshot pixels. Screenshots are whole emulator views, with preview controls and different viewport dimensions from the kit, so no pixel-identical whole-screen claim is made.

## Scope boundaries and deliberate choices

- No changes to existing feature screens, backend/API code, account state, translations, native picker logic, product routes or chart/map internals.
- Root bootstrap adds font registrations and a narrowly scoped `__DEV__` gallery-routing exemption; the existing production authentication and onboarding redirects remain intact. Existing fonts remain loaded until Gate B migration.
- New theme/system-bar styling is confined to the gallery. Switching the whole app to Night and resolving existing system/light/dark settings waits for Phase 3.
- Parchment is functional in the gallery. Both themes use their own supplied surface/foreground tokens; no kit colors were invented or edited.
- Button and field heights are minimums so accessibility text can grow rather than clip, as proposed in DS_00. Normal text scale matches nominal sizes.
- Hero title shrinks to fit the app name. Other large typography specimens may wrap and scroll, deliberately retaining their token size.
- Wheel art is static. Rotation/fades are optional in the spec; static decoration avoids motion entirely and respects reduced-motion needs.
- Spec-local geometry without named tokens (card corner/inset, select chevron inset, icon sizes, arch inner line) remains inside design-system and uses the exact specified values. The transparent gradient endpoint is the explicitly requested transparency, not an invented brand color.
- Existing app theme settings, real native date/time picker flow and absence of a compatibility-qualities questionnaire remain exactly as documented at Gate A.
- Gallery copy about unknown time is only the mandated design sample. It does not alter real birth-time calculations.

## Gate B

The Android design is ready for review. Approve the component direction before any existing product screen is restyled. The spec also asks for iOS evidence: provide an iOS/Mac test target, or explicitly defer that evidence if proceeding Android-first.

After Gate B, apply the approved route mapping from DS_00, capture before/after screens, preserve all existing interactions, and document remaining visualization/icon exceptions in DS_02. No paid model calls were made or are needed for this design work.
