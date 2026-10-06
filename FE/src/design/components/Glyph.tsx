import { Glyph as KitGlyph } from "../../design-system/components/Glyph";
import { glyphs } from "../../design-system/glyphs/glyphs";
import { SvgXml } from "react-native-svg";
import { glyphDefs } from "../../../packages/wheel-core/glyphs";
import { useTheme } from "../theme";
import type { Sign, Body } from "../../../contracts/spec-types";
const definitions = glyphDefs();
export function Glyph({
  name,
  size = 32,
  color: overrideColor,
}: {
  name: Sign | Body;
  size?: number;
  color?: string;
}) {
  const theme = useTheme();
  const color = overrideColor ?? theme.accent;
  if ((!overrideColor || [theme.ink, theme.accent, theme.ink2].includes(overrideColor as any)) && (name in glyphs.zodiac || name in glyphs.planets))
    return <KitGlyph name={name as any} set={name in glyphs.zodiac ? "zodiac" : "planets"} size={size} />;
  const key =
    name === "north_node" ? "node-n" : name === "south_node" ? "node-s" : name;
  if (!definitions.includes(`id="g-${key}"`)) return null;
  return (
    <SvgXml
      accessible={false}
      xml={`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" color="${color}"><defs>${definitions}</defs><use href="#g-${key}" x="0" y="0" width="100" height="100"/></svg>`}
      width={size}
      height={size}
    />
  );
}
