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
  const color = overrideColor ?? theme.ink;
  const key =
    name === "north_node" ? "node-n" : name === "south_node" ? "node-s" : name;
  return (
    <SvgXml
      accessible={false}
      xml={`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" color="${color}"><defs>${definitions}</defs><use href="#g-${key}" x="0" y="0" width="100" height="100"/></svg>`}
      width={size}
      height={size}
    />
  );
}
