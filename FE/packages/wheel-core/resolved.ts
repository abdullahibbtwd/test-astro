import { nativeWheelSvg } from "./native-svg";
import type { ChartData } from "../../contracts/spec-types";
/** Resolve the canonical, simple class rules into SVG presentation attributes for Skia. */
export function renderChartResolved(
  chart: ChartData,
  theme: "light" | "dark" = "light",
) {
  let svg = nativeWheelSvg(chart, theme);
  const rules = new Map<string, Record<string, string>>();
  for (const style of svg.matchAll(/<style>([\s\S]*?)<\/style>/g))
    for (const rule of style[1]!.matchAll(/\.([\w-]+)\s*\{([^}]+)\}/g)) {
      const attrs: Record<string, string> = {};
      for (const declaration of rule[2]!.split(";")) {
        const colon = declaration.indexOf(":");
        if (colon < 0) continue;
        const key = declaration.slice(0, colon).trim(),
          value = declaration.slice(colon + 1).trim();
        if (
          key &&
          value &&
          !key.startsWith("--") &&
          !["background", "text-transform"].includes(key)
        )
          attrs[key] = value;
      }
      rules.set(rule[1]!, attrs);
    }
  svg = svg.replace(/<style>[\s\S]*?<\/style>/g, "");
  return svg.replace(
    /<([\w:-]+)([^<>]*?)>/g,
    (tag: string, _name: string, attrs: string) => {
      const cls = attrs.match(/class="([^"]*)"/);
      if (!cls) return tag;
      const values = Object.assign(
        {},
        ...cls[1]!.split(/\s+/).map((c) => rules.get(c) ?? {}),
      );
      const inline = Object.entries(values)
        .filter(([key]) => !new RegExp(`(?:^|\\s)${key}=`).test(attrs))
        .map(
          ([key, value]) =>
            ` ${key}="${String(value).replace(/"/g, "&quot;")}"`,
        )
        .join("");
      return tag.replace(/\sclass="[^"]*"/, inline);
    },
  );
}

/** Skia does not render SVG symbol instances; expand them without changing their transforms. */
export function expandGlyphUses(svg: string) {
  const symbols = new Map(
    [...svg.matchAll(/<symbol\s+id="([^"]+)"[^>]*>([\s\S]*?)<\/symbol>/g)].map(
      (m) => [m[1]!, m[2]!],
    ),
  );
  return svg
    .replace(/<use\s+([^>]+)\/>/g, (_tag, attrs: string) => {
      const attributes = Object.fromEntries(
        [...attrs.matchAll(/([\w:-]+)="([^"]*)"/g)].map((m) => [m[1]!, m[2]!]),
      );
      const inner = symbols.get(
        (attributes.href ?? attributes["xlink:href"] ?? "").replace("#", ""),
      );
      if (!inner) throw new Error("Unknown glyph reference");
      const color = attributes.color ?? "#232A38";
      return `<g transform="translate(${attributes.x} ${attributes.y}) scale(${Number(attributes.width) / 100} ${Number(attributes.height) / 100})"${attributes.opacity ? ` opacity="${attributes.opacity}"` : ""}>${inner.replace(/currentColor/g, color)}</g>`;
    })
    .replace(/<defs>[\s\S]*?<\/defs>/g, "");
}
