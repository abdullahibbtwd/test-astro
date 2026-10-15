# DS Phase 0 exploration — Gate A

Date: 2026-10-05. Read-only exploration completed. No application, dependency, state, API, navigation or kit files were changed. This report is the only project addition for this phase.

Source specification: [DS_IMPLEMENTATION_SPEC.md](G:/My Drive/Tech/Astrology app/FE/DS_IMPLEMENTATION_SPEC.md). Kit archive: [astro-design-kit.zip](G:/My Drive/Tech/Astrology app/FE/astro-design-kit.zip). The archive's embedded spec is byte-identical to the standalone spec. Reference Screen_dark and TraitCard_dark were visually inspected; their copies were extracted only into the OS temporary directory.

## 1. Runtime and routing

- Expo 57.0.26; React Native 0.86.3; React 19.2.3. Versions from package.json.
- New Architecture on, Hermes on, edge-to-edge on: android/gradle.properties.
- TypeScript strict:true and noUncheckedIndexedAccess:true, extending expo/tsconfig.base.
- Targets: native Android/iOS. React DOM is installed, but react-native-web is not declared and no web script/target is configured; do not add web as part of this reskin.
- expo-router file routing, typed routes enabled in app.json. Root Stack/header/modal configuration: app/_layout.tsx. Tabs/header actions/profile switcher: app/(tabs)/_layout.tsx. Auth/onboarding layouts are separate. Redirects and route names must be retained.
- iOS screenshots cannot be produced by a local iOS simulator on this Windows host. Gate B needs an available Mac/iOS device or an explicit deferral of iOS evidence; Android evidence can be produced locally.

## 2. Styling, fonts, language and dependencies

- Inline React Native styles plus StyleSheet; no NativeWind/Tamagui/styled-components.
- src/design/tokens.ts owns current light/dark colors and partial spacing/typography. src/design/theme.tsx exports useTheme() returning the color object directly and follows useApp(s=>s.theme) plus useColorScheme().
- app/_layout.tsx calls useFonts({Inter, 'Inter-SemiBold', SourceSerif4}) and holds expo-splash-screen until fonts and storage load. Replace font loading only after Gate A; preserve storage/auth startup.
- i18next + react-i18next + ICU in src/i18n/index.ts. Current language is useApp(s=>s.language), type Lang='tr'|'en'; root syncs it with i18n.changeLanguage. Components use useTranslation(); AppText should read useApp(s=>s.language) and the supplied upper() helper. Do not rename translation keys.

| Dependency | Existing version / action |
|---|---|
| expo-font | 57.0.4 |
| expo-splash-screen | 57.0.9 |
| react-native-svg | 15.15.4 |
| expo-linear-gradient | Missing; install using npx expo install after Gate A (SDK manifest ~57.0.2) |
| react-native-safe-area-context | 5.7.0 |
| @react-native-community/datetimepicker | 9.1.0 |
| lucide-react-native | 1.49.0 |
| @expo/vector-icons | Not declared; no installation proposed |

## 3. Source scan counts

Counts below use rg against all src files, including generated schema/assets, and separately app. Each cell is matching lines / individual occurrences. No source exclusions were silently applied. Generated schemas, bundled chart SVG data, map styles and export HTML require documented exceptions rather than blind replacements.

| Pattern | src lines / occurrences | app lines / occurrences |
|---|---|---|
| Color literals | 57 / 82 | 1 / 1 |
| fontFamily | 14 / 14 | 3 / 3 |
| fontWeight | 0 / 0 | 0 / 0 |
| textTransform | 0 / 0 | 0 / 0 |
| Icon-library imports | 18 / 18 | 8 / 8 |
| Astrology Unicode | 1 / 2 | 0 / 0 |

## 4. Complete route/screen mapping

Paths are relative to the FE working copy unless linked. Group names are retained here to disambiguate root and tabs index routes. Layout files are listed in section 1, not counted as screens. Multiple routes can share one implementation.

| Route | Route file → implementation | Purpose | Proposed DS recipe |
|---|---|---|---|
| /(auth)/link | [app/(auth)/link.tsx](D:/Dev/astrology-app/FE/app/(auth)/link.tsx) → [src/features/account/BrowserSignInScreen.tsx](D:/Dev/astrology-app/FE/src/features/account/BrowserSignInScreen.tsx) | Browser sign-in completion | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /(auth)/welcome | [app/(auth)/welcome.tsx](D:/Dev/astrology-app/FE/app/(auth)/welcome.tsx) → [src/features/account/AuthScreen.tsx](D:/Dev/astrology-app/FE/src/features/account/AuthScreen.tsx) | Welcome, language and existing email/Google/Apple sign-in actions | Welcome: Screen arch + grain, Emblem, displayHero, existing sign-in actions |
| /(onboarding)/[step] | [app/(onboarding)/[step].tsx](D:/Dev/astrology-app/FE/app/(onboarding)/[step].tsx) → [src/features/onboarding/OnboardingScreen.tsx](D:/Dev/astrology-app/FE/src/features/onboarding/OnboardingScreen.tsx) | Consent, name, birth date/time/place, current place, details, notifications and building steps | Birth-data form on birth steps; standard form on other steps; arch/grain only for reveal |
| /(tabs)/ahead | [app/(tabs)/ahead.tsx](D:/Dev/astrology-app/FE/app/(tabs)/ahead.tsx) → [src/features/forecast/AheadScreen.tsx](D:/Dev/astrology-app/FE/src/features/forecast/AheadScreen.tsx) | Day, month, year and calendar forecast views | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /(tabs)/chart | [app/(tabs)/chart.tsx](D:/Dev/astrology-app/FE/app/(tabs)/chart.tsx) → [src/features/chart/ChartScreen.tsx](D:/Dev/astrology-app/FE/src/features/chart/ChartScreen.tsx) | Interactive natal chart and fact tables | Chart chrome only; wheel/tables internals excluded |
| /(tabs) | [app/(tabs)/index.tsx](D:/Dev/astrology-app/FE/app/(tabs)/index.tsx) → [src/features/home/HomeScreen.tsx](D:/Dev/astrology-app/FE/src/features/home/HomeScreen.tsx) | Daily dashboard and shortcuts | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /(tabs)/map | [app/(tabs)/map.tsx](D:/Dev/astrology-app/FE/app/(tabs)/map.tsx) → [src/features/map/MapScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/MapScreen.tsx) | Interactive astrocartography map and controls | Map chrome only; standard title/forms/list/reading around unchanged data visualization |
| /(tabs)/match | [app/(tabs)/match.tsx](D:/Dev/astrology-app/FE/app/(tabs)/match.tsx) → [src/features/compatibility/MatchScreen.tsx](D:/Dev/astrology-app/FE/src/features/compatibility/MatchScreen.tsx) | Saved compatibility reports | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /ahead/calendar | [app/ahead/calendar.tsx](D:/Dev/astrology-app/FE/app/ahead/calendar.tsx) | Navigation redirect; no screen visuals | No visual migration; preserve redirect |
| /ahead/today | [app/ahead/today.tsx](D:/Dev/astrology-app/FE/app/ahead/today.tsx) | Navigation redirect; no screen visuals | No visual migration; preserve redirect |
| /ask/[threadId] | [app/ask/[threadId].tsx](D:/Dev/astrology-app/FE/app/ask/[threadId].tsx) → [src/features/ask/ChatScreen.tsx](D:/Dev/astrology-app/FE/src/features/ask/ChatScreen.tsx) | Streaming Ask conversation and feedback | Provisional chat bubbles + composer |
| /ask | [app/ask/index.tsx](D:/Dev/astrology-app/FE/app/ask/index.tsx) → [src/features/ask/ThreadsScreen.tsx](D:/Dev/astrology-app/FE/src/features/ask/ThreadsScreen.tsx) | Saved Ask conversations | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /best-days/[activity]/[date] | [app/best-days/[activity]/[date].tsx](D:/Dev/astrology-app/FE/app/best-days/[activity]/[date].tsx) → [src/features/calendar/BestDayScreen.tsx](D:/Dev/astrology-app/FE/src/features/calendar/BestDayScreen.tsx) | Selected best-day details | Reading: displaySection + bodyLg + Divider |
| /best-days/[activity] | [app/best-days/[activity]/index.tsx](D:/Dev/astrology-app/FE/app/best-days/[activity]/index.tsx) → [src/features/calendar/BestDaysScreen.tsx](D:/Dev/astrology-app/FE/src/features/calendar/BestDaysScreen.tsx) | Activity selection and ranked dates | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /best-days | [app/best-days/index.tsx](D:/Dev/astrology-app/FE/app/best-days/index.tsx) → [src/features/calendar/BestDaysScreen.tsx](D:/Dev/astrology-app/FE/src/features/calendar/BestDaysScreen.tsx) | Activity selection and ranked dates | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /calendar/day/[date] | [app/calendar/day/[date].tsx](D:/Dev/astrology-app/FE/app/calendar/day/[date].tsx) → [src/features/calendar/DayScreen.tsx](D:/Dev/astrology-app/FE/src/features/calendar/DayScreen.tsx) | Selected calendar day | Reading: displaySection + bodyLg + Divider |
| /calendar | [app/calendar/index.tsx](D:/Dev/astrology-app/FE/app/calendar/index.tsx) → [src/features/calendar/CalendarScreen.tsx](D:/Dev/astrology-app/FE/src/features/calendar/CalendarScreen.tsx) | Monthly calendar | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /calendar/item/[id] | [app/calendar/item/[id].tsx](D:/Dev/astrology-app/FE/app/calendar/item/[id].tsx) → [src/features/calendar/ItemScreen.tsx](D:/Dev/astrology-app/FE/src/features/calendar/ItemScreen.tsx) | Calendar event details | Reading: displaySection + bodyLg + Divider |
| /calendar/periods | [app/calendar/periods.tsx](D:/Dev/astrology-app/FE/app/calendar/periods.tsx) → [src/features/calendar/OverviewScreen.tsx](D:/Dev/astrology-app/FE/src/features/calendar/OverviewScreen.tsx) | Year or period overview | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /calendar/year | [app/calendar/year.tsx](D:/Dev/astrology-app/FE/app/calendar/year.tsx) → [src/features/calendar/OverviewScreen.tsx](D:/Dev/astrology-app/FE/src/features/calendar/OverviewScreen.tsx) | Year or period overview | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /chart/export | [app/chart/export.tsx](D:/Dev/astrology-app/FE/app/chart/export.tsx) → [src/features/exports/ExportScreen.tsx](D:/Dev/astrology-app/FE/src/features/exports/ExportScreen.tsx) | Chart export and share controls | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /chart/focus | [app/chart/focus.tsx](D:/Dev/astrology-app/FE/app/chart/focus.tsx) → [src/features/chart/FocusScreen.tsx](D:/Dev/astrology-app/FE/src/features/chart/FocusScreen.tsx) | Chart focus view | Chart chrome only; wheel/tables internals excluded |
| /chart/reading | [app/chart/reading.tsx](D:/Dev/astrology-app/FE/app/chart/reading.tsx) → [src/features/profiles/ReadingScreen.tsx](D:/Dev/astrology-app/FE/src/features/profiles/ReadingScreen.tsx) | Full natal reading or selected section | Reading: displaySection + bodyLg + Divider |
| /chart/section/[key] | [app/chart/section/[key].tsx](D:/Dev/astrology-app/FE/app/chart/section/[key].tsx) → [src/features/profiles/ReadingScreen.tsx](D:/Dev/astrology-app/FE/src/features/profiles/ReadingScreen.tsx) | Full natal reading or selected section | Reading: displaySection + bodyLg + Divider |
| /forecast/month/[month] | [app/forecast/month/[month].tsx](D:/Dev/astrology-app/FE/app/forecast/month/[month].tsx) → [src/features/forecast/ForecastViews.tsx](D:/Dev/astrology-app/FE/src/features/forecast/ForecastViews.tsx), [src/features/shared/useProfile.tsx](D:/Dev/astrology-app/FE/src/features/shared/useProfile.tsx) | Monthly forecast reading | Reading recipe around existing MonthView |
| /forecast/year | [app/forecast/year.tsx](D:/Dev/astrology-app/FE/app/forecast/year.tsx) | Navigation redirect; no screen visuals | No visual migration; preserve redirect |
| /gallery | [app/gallery.tsx](D:/Dev/astrology-app/FE/app/gallery.tsx) → [src/features/account/Gallery.tsx](D:/Dev/astrology-app/FE/src/features/account/Gallery.tsx) | Existing internal component and audit gallery | Not covered: retain existing audit gallery; separate dev-only DesignSystemGallery |
| / | [app/index.tsx](D:/Dev/astrology-app/FE/app/index.tsx) | Navigation redirect; no screen visuals | No visual migration; preserve redirect |
| /map/area/[areaId] | [app/map/area/[areaId].tsx](D:/Dev/astrology-app/FE/app/map/area/[areaId].tsx) → [src/features/map/AreaScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/AreaScreen.tsx) | Area map report | Map chrome only; standard title/forms/list/reading around unchanged data visualization |
| /map/full | [app/map/full.tsx](D:/Dev/astrology-app/FE/app/map/full.tsx) → [src/features/map/AreaScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/AreaScreen.tsx), [src/features/map/LineScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/LineScreen.tsx), [src/features/map/PlaceScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/PlaceScreen.tsx) | Full-screen report selected by reportPath | Map chrome only; standard title/forms/list/reading around unchanged data visualization |
| /map/line/[body]/[angle] | [app/map/line/[body]/[angle].tsx](D:/Dev/astrology-app/FE/app/map/line/[body]/[angle].tsx) → [src/features/map/LineScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/LineScreen.tsx) | Planet/angle line report | Map chrome only; standard title/forms/list/reading around unchanged data visualization |
| /map/place/[placeId] | [app/map/place/[placeId].tsx](D:/Dev/astrology-app/FE/app/map/place/[placeId].tsx) → [src/features/map/PlaceScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/PlaceScreen.tsx) | Place or selected-coordinate report | Map chrome only; standard title/forms/list/reading around unchanged data visualization |
| /map/point | [app/map/point.tsx](D:/Dev/astrology-app/FE/app/map/point.tsx) → [src/features/map/PlaceScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/PlaceScreen.tsx) | Place or selected-coordinate report | Map chrome only; standard title/forms/list/reading around unchanged data visualization |
| /map/recommend | [app/map/recommend/index.tsx](D:/Dev/astrology-app/FE/app/map/recommend/index.tsx) → [src/features/map/RecommendScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/RecommendScreen.tsx) | Location recommendation filters | Map chrome only; standard title/forms/list/reading around unchanged data visualization |
| /map/recommend/result | [app/map/recommend/result.tsx](D:/Dev/astrology-app/FE/app/map/recommend/result.tsx) → [src/features/map/RecommendResultScreen.tsx](D:/Dev/astrology-app/FE/src/features/map/RecommendResultScreen.tsx) | Ranked location recommendations | Map chrome only; standard title/forms/list/reading around unchanged data visualization |
| /match/[id] | [app/match/[id].tsx](D:/Dev/astrology-app/FE/app/match/[id].tsx) → [src/features/compatibility/MatchReportScreen.tsx](D:/Dev/astrology-app/FE/src/features/compatibility/MatchReportScreen.tsx) | Compatibility reading | Reading: displaySection + bodyLg + Divider |
| /match/new | [app/match/new.tsx](D:/Dev/astrology-app/FE/app/match/new.tsx) → [src/features/compatibility/NewMatchScreen.tsx](D:/Dev/astrology-app/FE/src/features/compatibility/NewMatchScreen.tsx) | Select two people and relationship type | Standard form + picker triggers; qualities recipe not covered (no such step) |
| /profile/about | [app/profile/about.tsx](D:/Dev/astrology-app/FE/app/profile/about.tsx) → [src/features/account/AccountScreen.tsx](D:/Dev/astrology-app/FE/src/features/account/AccountScreen.tsx) | Profile, settings, privacy, location or about page selected by page prop: about | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /profile/charts/[id] | [app/profile/charts/[id].tsx](D:/Dev/astrology-app/FE/app/profile/charts/[id].tsx) → [src/features/profiles/ProfileDetail.tsx](D:/Dev/astrology-app/FE/src/features/profiles/ProfileDetail.tsx) | Saved profile details | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /profile/charts | [app/profile/charts/index.tsx](D:/Dev/astrology-app/FE/app/profile/charts/index.tsx) → [src/features/profiles/ChartsScreen.tsx](D:/Dev/astrology-app/FE/src/features/profiles/ChartsScreen.tsx) | Saved birth profiles | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /profile/charts/new | [app/profile/charts/new.tsx](D:/Dev/astrology-app/FE/app/profile/charts/new.tsx) → [src/features/profiles/ProfileEditor.tsx](D:/Dev/astrology-app/FE/src/features/profiles/ProfileEditor.tsx) | Create/edit birth profile | Birth-data form on birth steps; standard form on other steps; arch/grain only for reveal |
| /profile | [app/profile/index.tsx](D:/Dev/astrology-app/FE/app/profile/index.tsx) → [src/features/account/AccountScreen.tsx](D:/Dev/astrology-app/FE/src/features/account/AccountScreen.tsx) | Profile, settings, privacy, location or about page selected by page prop: profile | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /profile/location | [app/profile/location.tsx](D:/Dev/astrology-app/FE/app/profile/location.tsx) → [src/features/account/AccountScreen.tsx](D:/Dev/astrology-app/FE/src/features/account/AccountScreen.tsx) | Profile, settings, privacy, location or about page selected by page prop: location | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /profile/notifications | [app/profile/notifications.tsx](D:/Dev/astrology-app/FE/app/profile/notifications.tsx) → [src/features/account/NotificationsScreen.tsx](D:/Dev/astrology-app/FE/src/features/account/NotificationsScreen.tsx) | Notification preferences | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /profile/privacy | [app/profile/privacy.tsx](D:/Dev/astrology-app/FE/app/profile/privacy.tsx) → [src/features/account/AccountScreen.tsx](D:/Dev/astrology-app/FE/src/features/account/AccountScreen.tsx) | Profile, settings, privacy, location or about page selected by page prop: privacy | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /profile/reports | [app/profile/reports.tsx](D:/Dev/astrology-app/FE/app/profile/reports.tsx) → [src/features/account/ReportsScreen.tsx](D:/Dev/astrology-app/FE/src/features/account/ReportsScreen.tsx) | Saved reports | Reading: displaySection + bodyLg + Divider |
| /profile/settings | [app/profile/settings.tsx](D:/Dev/astrology-app/FE/app/profile/settings.tsx) → [src/features/account/AccountScreen.tsx](D:/Dev/astrology-app/FE/src/features/account/AccountScreen.tsx) | Profile, settings, privacy, location or about page selected by page prop: settings | Standard Screen + Title + provisional list/form/cards; no dedicated reference |
| /solar-return/[year] | [app/solar-return/[year].tsx](D:/Dev/astrology-app/FE/app/solar-return/[year].tsx) → [src/features/forecast/SolarReturnScreen.tsx](D:/Dev/astrology-app/FE/src/features/forecast/SolarReturnScreen.tsx) | Solar return reading | Reading: displaySection + bodyLg + Divider |

## 5. Reusable component signatures and mapping

Signatures below are extracted from the actual TypeScript AST, not guessed. Includes exported presentation components across design/components and features (screen containers appear in section 4). Generic parameters and local Props aliases are preserved where present. Function bodies, state and callbacks are not to be replaced.

### [src/design/components/ActionSheet.tsx](D:/Dev/astrology-app/FE/src/design/components/ActionSheet.tsx)

```ts
export type SheetAction = {
  label: string;
  onPress: () => void;
  icon?: ReactNode;
  destructive?: boolean;
};
```

```ts
ActionSheet({
  open,
  title,
  actions,
  onClose,
}: {
  open: boolean;
  title: string;
  actions: SheetAction[];
  onClose: () => void;
})
```

Provisional sheet and action rows

### [src/design/components/AspectGlyph.tsx](D:/Dev/astrology-app/FE/src/design/components/AspectGlyph.tsx)

```ts
AspectGlyph({
  type,
  size = 28,
}: {
  type: AspectType;
  size?: number;
})
```

Not covered: aspect symbols absent from kit; chart visualization exception

### [src/design/components/BandChip.tsx](D:/Dev/astrology-app/FE/src/design/components/BandChip.tsx)

```ts
BandChip({ band, label }: { band: string; label: string })
```

Not covered: semantic data band colors are visualization exceptions

### [src/design/components/CitySizeChip.tsx](D:/Dev/astrology-app/FE/src/design/components/CitySizeChip.tsx)

```ts
CitySizeChip({size}:{size:string})
```

Not covered: token-style label

### [src/design/components/ContentList.tsx](D:/Dev/astrology-app/FE/src/design/components/ContentList.tsx)

```ts
export type ContentListProps = Pick<
  FlatListProps<ReactElement>,
  "onEndReached" | "refreshing" | "onRefresh" | "ListEmptyComponent"
>;
```

```ts
ContentList({
  children,
  sheet = false,
  ...props
}: { children: ReactNode; sheet?: boolean } & ContentListProps)
```

Not covered: retain FlatList virtualization; update spacing only

```ts
ContentSections({
  sections,
  header,
  footer,
}: {
  sections: { key: string; header: ReactNode; children: ReactNode }[];
  header?: ReactElement;
  footer?: ReactElement;
})
```

Not covered: retain SectionList virtualization; style header text

### [src/design/components/CountryLabel.tsx](D:/Dev/astrology-app/FE/src/design/components/CountryLabel.tsx)

```ts
CountryLabel({
  code,
  name,
}: {
  code?: string | null;
  name?: string;
})
```

Not covered: text country label; no flag emoji

### [src/design/components/DatePager.tsx](D:/Dev/astrology-app/FE/src/design/components/DatePager.tsx)

```ts
DatePager({
  previousDisabled = false,
  nextDisabled = false,
  label,
  onPrevious,
  onNext,
  onPick,
  onToday,
}: {
  previousDisabled?: boolean;
  nextDisabled?: boolean;
  label: string;
  onPrevious: () => void;
  onNext: () => void;
  onPick: () => void;
  onToday?: () => void;
})
```

Glyph controls + SelectField-style trigger; preserve date navigation

### [src/design/components/DateTimeField.tsx](D:/Dev/astrology-app/FE/src/design/components/DateTimeField.tsx)

```ts
DateTimeField({
  mode,
  value,
  onChange,
  label,
  minimumDate = new Date(1900, 0, 1),
  maximumDate = new Date(),
}: {
  label?: string;
  minimumDate?: Date;
  maximumDate?: Date;
  mode: "date" | "time";
  value: string;
  onChange: (value: string) => void;
})
```

Field + SelectField trigger; keep native picker implementation

### [src/design/components/Glyph.tsx](D:/Dev/astrology-app/FE/src/design/components/Glyph.tsx)

```ts
Glyph({
  name,
  size = 32,
  color: overrideColor,
}: {
  name: Sign | Body;
  size?: number;
  color?: string;
})
```

DS Glyph for supported zodiac/planets; extra bodies not covered

### [src/design/components/IconButton.tsx](D:/Dev/astrology-app/FE/src/design/components/IconButton.tsx)

```ts
IconButton({
  icon,
  accessibilityLabel,
  onPress,
  badge,
  disabled = false,
}: {
  icon: ReactNode;
  accessibilityLabel: string;
  onPress: () => void;
  badge?: boolean;
  disabled?: boolean;
})
```

Not covered: retain accessible 44pt trigger with kit Glyph

### [src/design/components/JobProgress.tsx](D:/Dev/astrology-app/FE/src/design/components/JobProgress.tsx)

```ts
JobProgress({
  job,
  slow,
  failed,
  error,
  retry,
  place,
}: {
  job?: Job;
  slow?: boolean;
  failed?: boolean;
  error?: unknown;
  retry: () => void;
  place?: string;
})
```

Not covered: AppText/Glyph/status composition; preserve polling

### [src/design/components/PlaceSearch.tsx](D:/Dev/astrology-app/FE/src/design/components/PlaceSearch.tsx)

```ts
PlaceSearch({
  onConfirm,
}: {
  onConfirm: (place: Place) => void;
})
```

Field + TextInputField and provisional results list; preserve search logic

### [src/design/components/ProfileSwitcher.tsx](D:/Dev/astrology-app/FE/src/design/components/ProfileSwitcher.tsx)

```ts
ProfilePicker({
  open,
  selectedId,
  disabledId,
  onSelect,
  onClose,
}: {
  open: boolean;
  selectedId?: string | null;
  disabledId?: string;
  onSelect: (id: string) => void;
  onClose: () => void;
})
```

Provisional sheet + list rows

```ts
ProfileSwitcher({
  selectedId,
  onSelect,
}: {
  selectedId?: string;
  onSelect?: (id: string) => void;
})
```

SelectField-style trigger; preserve header placement

### [src/design/components/RouteError.tsx](D:/Dev/astrology-app/FE/src/design/components/RouteError.tsx)

```ts
RouteError({ error, retry }: ErrorBoundaryProps)
```

Not covered: AppText + retry Button; preserve boundary behavior

### [src/design/components/Segmented.tsx](D:/Dev/astrology-app/FE/src/design/components/Segmented.tsx)

```ts
Segmented<T extends string>({
  items,
  value,
  onChange,
  accessibilityLabel,
}: {
  items: readonly { value: T; label: string; accessibilityLabel?: string }[];
  value: T;
  onChange: (value: T) => void;
  accessibilityLabel?: string;
})
```

Not covered: preserve radio semantics, token-style segments

### [src/design/components/Sheet.tsx](D:/Dev/astrology-app/FE/src/design/components/Sheet.tsx)

```ts
Sheet({
  open,
  title,
  onClose,
  onExpand,
  children,
  list = false,
  snapPoints = ["55%", "92%"],
  index = 0,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  onExpand?: () => void;
  children: ReactNode;
  list?: boolean;
  snapPoints?: (string | number)[];
  index?: number;
})
```

Provisional sheet; retain snap points, dismiss, expansion and virtualization

### [src/design/components/Snackbar.tsx](D:/Dev/astrology-app/FE/src/design/components/Snackbar.tsx)

```ts
Snackbar()
```

Not covered: raised surface + existing Undo/action behavior

### [src/design/components/index.tsx](D:/Dev/astrology-app/FE/src/design/components/index.tsx)

```ts
Txt({
  children,
  kind = "body",
  muted = false,
  style,
  numberOfLines,
}: {
  children: React.ReactNode;
  kind?: "body" | "title" | "display" | "caption" | "reading";
  muted?: boolean;
  style?: any;
  numberOfLines?: number;
})
```

AppText; kind → token variant; retain selectable reading behavior

```ts
Screen({
  children,
  title,
  back = false,
  footer,
  scrollRef,
  scrollProps,
  embedded = false,
  pinned,
  scroll = true,
  list = false,
  listProps,
  largeTitle = false,
  headerless = false,
}: {
  children: React.ReactNode;
  title?: string;
  back?: boolean;
  footer?: React.ReactNode;
  scrollRef?: React.RefObject<ScrollView | null>;
  scrollProps?: ScrollViewProps;
  embedded?: boolean;
  pinned?: React.ReactNode;
  scroll?: boolean;
  list?: boolean;
  listProps?: ContentListProps;
  largeTitle?: boolean;
  headerless?: boolean;
})
```

DS Screen background composed with existing virtualized content, pinned controls and footer

```ts
Button({
  label,
  onPress,
  secondary = false,
  danger = false,
  disabled = false,
  loading = false,
}: {
  label: string;
  onPress: () => void;
  secondary?: boolean;
  danger?: boolean;
  disabled?: boolean;
  loading?: boolean;
})
```

DS Button via compatibility adapter; retain busy/loading/destructive semantics (not covered by exact new props)

```ts
Card({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: ViewStyle;
})
```

Not covered: ordinary content cards are not TraitCard; token-styled container

```ts
Row({
  leading,
  label,
  detail,
  onPress,
  onLongPress,
}: {
  leading?: React.ReactNode;
  label: string;
  detail?: string;
  onPress?: () => void;
  onLongPress?: () => void;
})
```

Provisional tappable list row; preserve long press

```ts
Field({ label, ...props }: TextInputProps & { label: string })
```

DS Field + TextInputField; retain all TextInputProps

```ts
Chip({
  role = "radio",
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  role?: "radio" | "checkbox" | "button";
  onPress: () => void;
})
```

Not covered: preserve radio/checkbox semantics; TraitCard only for existing multi-choice qualities (none found)

```ts
Choices({
  children,
  multi = false,
}: PropsWithChildren<{ multi?: boolean }>)
```

Not covered: layout container; preserve multi-select semantics

```ts
ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
})
```

Not covered: AppText + alert Glyph + retry Button, preserve error actions

```ts
Skeleton({
  variant = "block",
  lines = 3,
}: {
  variant?: "lines" | "block";
  lines?: number;
})
```

Not covered: semantic surfaces; preserve reduce-motion

```ts
Progress({ step, total }: { step: number; total: number })
```

Not covered: token-style progress indicator

### [src/features/account/ExportAudit.tsx](D:/Dev/astrology-app/FE/src/features/account/ExportAudit.tsx)

```ts
ExportAudit()
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/account/ListAudit.tsx](D:/Dev/astrology-app/FE/src/features/account/ListAudit.tsx)

```ts
ListAudit()
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/ask/AskCards.tsx](D:/Dev/astrology-app/FE/src/features/ask/AskCards.tsx)

```ts
AskCardView({
  card,
  profile,
}: {
  card: AskCard;
  profile: string;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/calendar/MonthGrid.tsx](D:/Dev/astrology-app/FE/src/features/calendar/MonthGrid.tsx)

```ts
MonthGrid({
  month,
  days,
  today,
  selected,
  bestDays = false,
  onSelect,
}: {
  month: string;
  days: {
    date: string;
    band: string;
    label: string;
    icons?: string;
    tinted?: boolean;
  }[];
  today?: string;
  selected?: string;
  bestDays?: boolean;
  onSelect: (date: string) => void;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/chart/ChartDetailSheet.tsx](D:/Dev/astrology-app/FE/src/features/chart/ChartDetailSheet.tsx)

```ts
ChartDetailSheet({
  chart,
  catalogue: c,
  selection,
  select,
  close,
}: {
  chart: ChartData;
  catalogue: Catalogue;
  selection: Selection;
  select: (value: Selection) => void;
  close: () => void;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/chart/ChartTables.tsx](D:/Dev/astrology-app/FE/src/features/chart/ChartTables.tsx)

```ts
ChartTables({
  chart,
  catalogue: c,
  tab,
  select,
}: {
  chart: ChartData;
  catalogue: Catalogue;
  tab: ChartTab;
  select: (selection: Selection) => void;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/chart/InlineReading.tsx](D:/Dev/astrology-app/FE/src/features/chart/InlineReading.tsx)

```ts
InlineReading({ profile }: { profile: BirthProfile })
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/chart/InteractiveWheel.tsx](D:/Dev/astrology-app/FE/src/features/chart/InteractiveWheel.tsx)

```ts
InteractiveWheel({
  chart,
  catalogue,
  selection,
  select,
  onExpand,
}: {
  onExpand?: () => void;
  chart: ChartData;
  catalogue: Catalogue;
  selection: Selection | null;
  select: (s: Selection | null) => void;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/forecast/ForecastViews.tsx](D:/Dev/astrology-app/FE/src/features/forecast/ForecastViews.tsx)

```ts
DayView({
  profile,
  date,
  lens,
  focusArea,
}: {
  profile: string;
  date: string;
  lens: Lens;
  focusArea?: string;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

```ts
MonthView({
  profile,
  month,
  lens,
}: {
  profile: string;
  month: string;
  lens: Lens;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

```ts
YearView({
  profile,
  month,
  lens,
}: {
  profile: string;
  month: string;
  lens: Lens;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/map/MapCanvas.tsx](D:/Dev/astrology-app/FE/src/features/map/MapCanvas.tsx)

```ts
MapCanvas({
  lines,
  fill = false,
  heat,
  bodies,
  parans = false,
  center = [29, 41],
  onLine,
  onPoint,
  destinations = [],
  onDestination,
  emphasized,
}: {
  fill?: boolean;
  lines?: AcgLines;
  heat?: AcgHeat;
  bodies: Body[];
  parans?: boolean;
  center?: [number, number];
  onLine?: (body: Body, angle: Angle) => void;
  onPoint?: (point: [number, number], zoom: number, long: boolean) => void;
  destinations?: Destination[];
  onDestination?: (place: Destination) => void;
  emphasized?: string[];
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/map/MapSearch.tsx](D:/Dev/astrology-app/FE/src/features/map/MapSearch.tsx)

```ts
MapSearch({
  onSelect,
  areasOnly = false,
}: {
  onSelect: (place: PlaceCandidate) => void;
  areasOnly?: boolean;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/map/ReportSurface.tsx](D:/Dev/astrology-app/FE/src/features/map/ReportSurface.tsx)

```ts
ReportSurface({
  title,
  children,
  list = false,
}: {
  title?: string;
  children: ReactNode;
  list?: boolean;
  back?: boolean;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/profiles/ReadingScreen.tsx](D:/Dev/astrology-app/FE/src/features/profiles/ReadingScreen.tsx)

```ts
ReadingSection({
  section,
  initialExpanded,
  askRoute,
}: {
  section: Pick<NatalSection, "title" | "text">;
  initialExpanded: boolean;
  askRoute?: string;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/profiles/WheelPreview.tsx](D:/Dev/astrology-app/FE/src/features/profiles/WheelPreview.tsx)

```ts
WheelPreview({
  id,
  chartKey,
}: {
  id: string;
  chartKey?: string;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/shared/Blocks.tsx](D:/Dev/astrology-app/FE/src/features/shared/Blocks.tsx)

```ts
Generated<T>({
  part,
  retry,
  children,
}: {
  part: GeneratedPart<T> | null | undefined;
  retry: () => void;
  children: (data: T) => ReactNode;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

```ts
Score({
  label,
  score,
  band,
  bandKey,
}: {
  label: string;
  score: number;
  band: string;
  bandKey?: string;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

```ts
ItemRows({
  items,
  profile,
}: {
  items: CalendarRowItem[];
  profile: string;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

```ts
MoonBlock({ moon }: { moon: MoonInfo })
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

```ts
DateLinks({
  dates,
  profile,
}: {
  dates: string[];
  profile: string;
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

```ts
Domains({
  items,
}: {
  items?: { key: string; title: string; text: string }[];
})
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

### [src/features/shared/TimezoneNotice.tsx](D:/Dev/astrology-app/FE/src/features/shared/TimezoneNotice.tsx)

```ts
TimezoneNotice()
```

Not covered by a dedicated reference. Compose DS text, titles, fields and provisional rows; preserve existing data/interaction and any visualization internals.

## 6. Gaps and proposed decisions for Gate A

1. **Night versus existing theme settings:** the spec's Night-only v1 conflicts with AccountScreen's system/light/dark preference controls and the no-behavior-change rule. Recommend approving the explicitly requested fixed Night appearance as the sole theme behavior exception; keep the API preference schema intact and decide how the visible settings choices should be presented before Phase 3. Do not silently show controls that have no effect. Parchment remains available in the dev gallery.
2. **Birth date/time:** current DateTimeField opens the existing native picker. Keep that interaction, style only its trigger. The three-column date/two-column time reference is not an instruction to replace the native picker or merge the existing onboarding steps.
3. **Compatibility qualities:** no existing qualities questionnaire was found. NewMatchScreen selects profiles/type; adding the sample four qualities would require new state/API behavior. Build TraitCard for the gallery, but do not invent a new onboarding/compatibility step.
4. **Unknown birth time:** sample gallery text says use 12:00. Existing unknown-time validation/calculation must remain unchanged; never introduce that assumption into the app. Gallery samples are display-only.
5. **Fixed sizes versus accessibility:** preserve disabled/loading states, selectable readings, keyboard handling, current list virtualization, sheet gestures, focus and screen-reader roles. Reference sizes are minimum/nominal where text scaling otherwise clips. Any unavoidable acceptance conflict must be documented at Gate B.
6. **Tokens:** several spec-local constants have no named kit token (arch second-line inset 7, card inset 5/corner 18/offset 2, select trailing inset 36, input leading inset 44, pressed opacity .88, transparent gradient endpoint). Do not edit tokens.ts or invent colors. Use only explicitly specified geometry locally inside design-system; request a regenerated token only if additional geometry/color is actually necessary. Native headers and navigation chrome may need an adapter.
7. **Missing patterns/icons:** ordinary content cards, segmented controls, score/band chips, progress/skeleton, Undo snackbar and icon-only buttons need provisional token-based styling while preserving their signatures. Kit icons omit share, copy, external-link, home, users, download, swap and more; retain unmatched Lucide icons with semantic colors and list them in DS_02. Extra chart bodies/aspects and internal astrology visualization glyphs are not covered; preserve as visualization exceptions.
8. **Theme migration:** use a new src/design-system directory, leaving src/design unchanged until Gate B. Build independent provider and gallery for Phase 1/2; at Phase 3 bridge legacy useTheme/Txt/Screen interfaces or migrate their call sites without touching business logic. Do not globally restyle existing primitives before Gate B.
9. **Maps/charts/exports:** MapCanvas, style.ts, glyph-images.ts, InteractiveWheel, chart SVG assets, band palettes and export document SVG/data colors are not globally recolored. Surrounding screen/toolbar/reading chrome changes only. Document residual literal scans with exact files.
10. **Dev gallery routing:** adding a dev-only DesignSystemGallery and font/provider bootstrap is explicitly required by Phase 1/2 despite the broad wording 'no screen files before Gate B'. Treat existing product screens as untouched; dev-only route/bootstrap are the narrow implementation exception. Its development access must work without altering production auth/onboarding redirects.
11. **Validation platforms:** Android available; local iOS simulator unavailable on Windows. Do not label Android evidence as iOS. Gate B must disclose missing iOS screenshots unless device/Mac access is supplied.

## 7. Implementation and review plan

After Gate A: copy immutable theme/glyph data and licensed fonts; verify checksums; install only missing expo-linear-gradient; implement ThemeProvider, upper/AppText and independent gallery; then Glyph/ornaments/Screen/Title/Button/fields/TraitCard. Capture Android Night/Parchment states and Turkish typography against all reference pairs; typecheck; record iOS evidence limitation. Submit DS_01_report.md for Gate B before migrating existing screens.

After Gate B: apply the route mapping above, retain navigation/state/API/i18n keys, capture before/after per screen, scan tokens/icons, and submit DS_02_report.md with visualization/unmatched-pattern exceptions. No paid model calls are needed for this design work.

## Gate A approval request

Approve the mapping and Phase 1/2 implementation with the above no-behavior-change boundaries. Theme-setting presentation remains a Phase 3 decision; no production settings are changed during Phase 1/2.

The supplied spec section 2.4 says: “Stop after Phase 0 (Gate A) and after Phase 2 (Gate B) and wait for Radul's go-ahead. No screen files are touched before Gate B.” This is why work stops at this report rather than editing the app immediately. The earlier authorization to continue FX fixes did not explicitly waive the new design spec's gates.
