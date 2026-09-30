import { SvgXml } from "react-native-svg";
import type { AspectType } from "../../../contracts/spec-types";
import { useTheme } from "../theme";
// Original vector forms in the canonical glyphs' stroke style. Outside canonical wheel output.
const paths: Record<AspectType, string> = {
  conjunction: '<circle cx="38" cy="62" r="20"/><path d="M52 48 L80 20"/>',
  opposition:
    '<circle cx="25" cy="75" r="16"/><circle cx="75" cy="25" r="16"/><path d="M37 63 L63 37"/>',
  square: '<path d="M22 22 H78 V78 H22 Z"/>',
  trine: '<path d="M50 18 L84 78 H16 Z"/>',
  sextile: '<path d="M50 15 V85 M20 32 L80 68 M20 68 L80 32"/>',
};
export function AspectGlyph({
  type,
  size = 28,
}: {
  type: AspectType;
  size?: number;
}) {
  const color = useTheme().ink;
  return (
    <SvgXml
      accessible={false}
      width={size}
      height={size}
      xml={`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><g fill="none" stroke="${color}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">${paths[type]}</g></svg>`}
    />
  );
}
