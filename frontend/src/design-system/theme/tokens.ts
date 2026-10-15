/**
 * Astrology App — design tokens for React Native / Expo.
 * Generated from the "Astrology App" design system (tokens.json). Data only — do not hand-edit values;
 * change the design system and regenerate.
 *
 * Themes: `night` (default, the brand's dark look) and `parchment` (light).
 * Fonts: register the four TTFs in ./fonts with expo-font under EXACTLY the names used in `fontFamily` below.
 * Display styles and buttons have `uppercase: true` — uppercase the string in JS with the language-aware
 * helper described in the spec (Turkish i → İ). Do not rely on `textTransform`.
 */

/** Brand palette — marketing and fixed brand moments only. UI code uses `themes[...]`. */
export const brand = {
  gold: "#D8A250",
  night: "#1F2628",
  parchment: "#E8D4B6",
  white: "#FFFFFF",
  bronzeLight: "#A68758",
  bronzeDeep: "#5B3D11",
} as const;

/** Semantic colours per theme. Same keys in both themes. */
export const themes = {
  night: {
    surface: "#1F2628",  // Screen background.
    surfaceDeep: "#191E1F",  // The darker, grain-heavy lower part of hero screens and sunken wells.
    surfaceRaised: "#273033",  // The only lifted surface: bottom sheets, menus, toasts.
    surfaceInverse: "#E8D4B6",  // Inverse panels — tooltips, the reading quote block. Text on it is on-inverse.
    onInverse: "#1F2628",  // Text and line art on surface-inverse (10.6:1 both themes).
    ink: "#E6DFD2",  // Long-form reading text and emphasis, on surface, surface-raised and surface-deep (≥11:1 both themes).
    inkSoft: "#BDB7AA",  // The reference's body grey: field labels, subtitles, input values, on surface and surface-raised (≥6.7:1).
    inkFaint: "#9A968C",  // Captions, placeholders, helper text, on surface and surface-raised only (≥4.5:1).
    accent: "#D8A250",  // Display type (Aboreto), card labels, line art, chevrons. Gold on Night (6.7:1), charcoal on Parchment (10.6:1).
    borderControl: "#B8955A",  // 1px borders of selects, inputs, outline buttons and unselected cards (≥3.6:1 on surface).
    hairline: "rgba(216, 162, 80, 0.18)",  // Decorative only: background orbit rings, constellation lines, inner card frames. Never a control boundary.
    star: "rgba(232, 212, 182, 0.4)",  // Starfield speckle and scattered dots on cards. Decorative only.
    primary: "#D8A250",  // Primary button and selected-card fill. Gold on Night; charcoal on Parchment, where gold would not hold a boundary.
    onPrimary: "#1F2628",  // Labels, check marks and line art on a primary fill (6.7:1 dark, 10.6:1 light).
    danger: "#F09A86",  // Field errors only, always with the alert icon and words; on surface and surface-raised (≥6:1).
    focus: "#F2EADC",  // Keyboard focus ring colour (see shadow focus-ring); ≥10:1 on surface.
    scrim: "rgba(12, 15, 16, 0.72)",  // Behind bottom sheets and dialogs.
  },
  parchment: {
    surface: "#E8D4B6",
    surfaceDeep: "#DDC6A2",
    surfaceRaised: "#F2E5D0",
    surfaceInverse: "#1F2628",
    onInverse: "#E8D4B6",
    ink: "#1F2628",
    inkSoft: "#47423A",
    inkFaint: "#625C50",
    accent: "#1F2628",
    borderControl: "#7D6A4A",
    hairline: "rgba(31, 38, 40, 0.16)",
    star: "rgba(31, 38, 40, 0.28)",
    primary: "#1F2628",
    onPrimary: "#E8D4B6",
    danger: "#9A2F1F",
    focus: "#1F2628",
    scrim: "rgba(31, 38, 40, 0.48)",
  },
} as const;

export type ThemeName = keyof typeof themes;
export type ThemeColors = { [K in keyof typeof themes.night]: string };

/** Font family names — must match the keys passed to expo-font `useFonts`. */
export const fontFiles = {
  "Aboreto-Regular": "fonts/Aboreto-Regular.ttf",
  "Poppins-Regular": "fonts/Poppins-Regular.ttf",
  "Poppins-Medium": "fonts/Poppins-Medium.ttf",
  "Poppins-SemiBold": "fonts/Poppins-SemiBold.ttf",
} as const;

/**
 * Text styles. letterSpacing is in points (RN has no `em`). No fontWeight — each weight is its own family
 * (Android ignores fontWeight on custom fonts). `uppercase` is a flag for the Text primitive, not a style prop.
 */
export const type = {
  displayHero: {
    fontFamily: "Aboreto-Regular",
    fontSize: 64,
    lineHeight: 64,
    letterSpacing: 1.28,
    uppercase: true,
  },
  displayPoster: {
    fontFamily: "Aboreto-Regular",
    fontSize: 44,
    lineHeight: 52,
    letterSpacing: 0.88,
    uppercase: true,
  },
  displayTitle: {
    fontFamily: "Aboreto-Regular",
    fontSize: 26,
    lineHeight: 31,
    letterSpacing: 0.78,
    uppercase: true,
  },
  displaySection: {
    fontFamily: "Aboreto-Regular",
    fontSize: 20,
    lineHeight: 26,
    letterSpacing: 0.8,
    uppercase: true,
  },
  displayCard: {
    fontFamily: "Aboreto-Regular",
    fontSize: 15,
    lineHeight: 19,
    letterSpacing: 0.75,
    uppercase: true,
  },
  bodyLg: {
    fontFamily: "Poppins-Regular",
    fontSize: 16,
    lineHeight: 24,
    letterSpacing: 0,
    uppercase: false,
  },
  body: {
    fontFamily: "Poppins-Regular",
    fontSize: 14,
    lineHeight: 20,
    letterSpacing: 0,
    uppercase: false,
  },
  label: {
    fontFamily: "Poppins-Medium",
    fontSize: 14,
    lineHeight: 20,
    letterSpacing: 0,
    uppercase: false,
  },
  input: {
    fontFamily: "Poppins-SemiBold",
    fontSize: 16,
    lineHeight: 24,
    letterSpacing: 0,
    uppercase: false,
  },
  button: {
    fontFamily: "Poppins-SemiBold",
    fontSize: 15,
    lineHeight: 20,
    letterSpacing: 0.6,
    uppercase: true,
  },
  caption: {
    fontFamily: "Poppins-Regular",
    fontSize: 12,
    lineHeight: 16,
    letterSpacing: 0.12,
    uppercase: false,
  },
} as const;

export type TypeStyleName = keyof typeof type;

/** 4pt spacing scale. Keys are the token step: space(4) = 16. */
export const space = {
  "1": 4,
  "2": 8,
  "3": 12,
  "4": 16,
  "6": 24,
  "8": 32,
  "12": 48,
  "16": 64,
} as const;

export const radius = {
  card: 4,
  md: 8,
  lg: 24,
  screen: 40,
  full: 9999,
} as const;

/** Fixed sizes measured from the reference at 375pt. */
export const size = {
  screenPaddingX: 32,      // space 8
  screenPaddingTop: 48,    // space 12
  archInset: 16,           // arch frame inset from the screen edge
  buttonLg: 56,
  buttonMd: 44,
  control: 48,             // Select / TextInput height
  controlBorder: 1,
  traitCardAspect: 5 / 8,  // width / height
  checkBadge: 28,
  glyph: 24,
  motif: 40,
} as const;

export const opacity = {
  disabled: 0.4,
  traitFrame: 0.55,        // inner frame line of a TraitCard
  traitScatter: 0.8,       // scattered dots/sparkles on a TraitCard
} as const;

/** Motion (ms). Fades only — no springs or bounces. Honour reduce-motion by skipping them. */
export const motion = {
  fast: 200,
  base: 250,
  screen: 320,             // fade + 8pt rise
  screenRise: 8,
  wheelTurn: 120000,       // one ChartWheel rotation, hero screens only
} as const;

/** Bottom-sheet shadow (iOS) + elevation (Android). The UI is otherwise flat. */
export const shadow = {
  sheet: {
    night: { shadowColor: "#000000", shadowOpacity: 0.6, shadowRadius: 20, shadowOffset: { width: 0, height: -12 }, elevation: 16 },
    parchment: { shadowColor: "#5B3D11", shadowOpacity: 0.25, shadowRadius: 20, shadowOffset: { width: 0, height: -12 }, elevation: 12 },
  },
} as const;
