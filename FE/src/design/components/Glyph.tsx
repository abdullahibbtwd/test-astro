import { SvgXml } from "react-native-svg";
import { glyphDefs } from "../../../../Chart_wheel/src/glyphs.js";
import { useTheme } from "../theme";
import type { Sign } from "../../../contracts/spec-types";
const definitions = glyphDefs();
export function Glyph({ name, size = 32 }: { name: Sign; size?: number }) {
  const color = useTheme().ink;
  return (
    <SvgXml
      accessible={false}
      xml={`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" color="${color}"><defs>${definitions}</defs><use href="#g-${name}" x="0" y="0" width="100" height="100"/></svg>`}
      width={size}
      height={size}
    />
  );
}
