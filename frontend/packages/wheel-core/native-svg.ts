import { renderChart } from "./render";
import { THEMES } from "./theme";
import { toWheelInput } from "./adapter";
import type { ChartData } from "../../contracts/spec-types";
/** Native presentation adapter only; canonical geometry and exported SVG remain untouched. */
export function nativeWheelSvg(chart: ChartData, theme: "light" | "dark") {
  const tokens: Record<string, string> = {
    ...THEMES[theme],
    "--glyph-font": "Inter",
    "--axis-font": "Inter",
  };
  let svg = renderChart(toWheelInput(chart), { theme });
  for (let i = 0; i < 3; i++)
    svg = svg.replace(
      /var\((--[\w-]+)(?:,([^)]*))?\)/g,
      (_match: string, key: string, fallback: string) =>
        tokens[key] ?? fallback ?? "",
    );
  return svg.replace(/--[\w-]+\s*:[^;]+;/g, "");
}
