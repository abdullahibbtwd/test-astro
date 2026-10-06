import { themes, space, type as textStyles } from "../design-system/theme/tokens";
/** Compatibility names for existing screens; values come only from the immutable kit. */
function legacy(c: typeof themes.night | typeof themes.parchment, dark: boolean) {
  return { ...c, dark, bg: c.surface, surface: c.surfaceRaised, surfaceAlt: c.surfaceDeep,
    ink2: c.inkSoft, ink3: c.inkFaint, hair: c.hairline, accentSoft: c.surfaceRaised, onAccent: c.onPrimary };
}
export const colors = { dark: legacy(themes.night, true), light: legacy(themes.parchment, false) };
export const spacing = { xs: space[1], sm: space[2], md: space[3], lg: space[4], gutter: space[8], xl: space[6], xxl: space[8], hero: space[8] + space[2], section: space[12] + space[2] };
export const typography = { display: textStyles.displayTitle, title1: textStyles.displaySection, body: textStyles.body, reading: textStyles.bodyLg };
