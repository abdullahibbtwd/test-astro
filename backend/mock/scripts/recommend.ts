import fs from "node:fs";
import path from "node:path";
import type { Catalogue, Lang } from "../../../frontend/contracts/spec-types";
export function recommendations(
  root: string,
  lang: Lang,
  cat: Catalogue,
  sourceFile = "acg_run/20260928-113431_8l9/recommend_love_world_1979-03-30.json",
) {
  const read = (file: string) =>
    JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
  return mapRecommendation(root, lang, cat, read(sourceFile));
}
export function mapRecommendation(
  root: string,
  lang: Lang,
  cat: Catalogue,
  source: any,
) {
  const read = (file: string) =>
    JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
  const raw = structuredClone(source);
  raw.turkey ??= { cities: [], regions: [], places: [] };
  if (raw.goal === "overall") {
    // Overall is breadth/strain, not a goal-band score. Preserve its explicit summary label.
    raw.cities = raw.places.map((p: any) => ({
      ...p,
      band: "no_emphasis",
      band_label_tr: p.label_tr,
      band_label_en: p.label_en,
    }));
    raw.turkey.cities = (raw.turkey.places ?? []).map((p: any) => ({
      ...p,
      band: "no_emphasis",
      band_label_tr: p.label_tr,
      band_label_en: p.label_en,
    }));
    raw.by_line = [];
    raw.by_purpose = { living: [], travel: [] };
    raw.lines_without_destinations = [];
    raw.countries = [];
    raw.regions = [];
  }
  const dest = new Map(
    read("Astrocartography/destinations.json").destinations.map((p: any) => [
      p.id,
      p,
    ]),
  );
  const city = (p: any) => {
    const meta: any = dest.get(p.id);
    if (!meta) throw new Error("Missing destination metadata " + p.id);
    return {
      place_id: p.id,
      name: lang === "tr" ? (p.name_tr ?? p.name) : p.name,
      country_code: p.country,
      size: meta.size,
      ...(raw.goal === "overall" ? { summary_label: p[`label_${lang}`] } : {}),
      band: p.band,
      band_label: p[`band_label_${lang}`],
      dominant_line:
        p.dominant_line?.kind === "line"
          ? {
              body: p.dominant_line.body,
              angle: p.dominant_line.angle,
              distance_km_rounded: p.dominant_line.distance_km_rounded,
            }
          : null,
      has_tradeoff: p.has_tradeoff,
      purposes: ["living", "travel"].filter((purpose) =>
        (raw.by_purpose[purpose] ?? []).some(
          (item: any) => (typeof item === "string" ? item : item.id) === p.id,
        ),
      ),
      lat: meta.lat,
      lon: meta.lon,
    };
  };
  const area = (p: any, kind: string) => ({
    id: p.id,
    kind,
    name: lang === "tr" ? (p.name_tr ?? p.name) : p.name,
    band: p.band,
    band_label: p[`band_label_${lang}`],
  });
  const groups = raw.by_line.map((g: any) => {
    const group_id =
      g.kind === "line" ? `${g.line.body}|${g.line.angle}` : g.line.id;
    const title =
      g.kind === "line"
        ? `${cat.bodies[g.line.body as keyof typeof cat.bodies]} · ${cat.angles[g.line.angle as keyof typeof cat.angles].line}`
        : g.line.bodies
            .map((b: keyof typeof cat.bodies) => cat.bodies[b])
            .join(" × ");
    return {
      group_id,
      kind: g.kind,
      line:
        g.kind === "line"
          ? { body: g.line.body, angle: g.line.angle }
          : { bodies: g.line.bodies, angles: g.line.angles },
      title,
      destinations: g.destinations.map(city),
    };
  });
  const all = [
    ...raw.cities,
    ...raw.by_line.flatMap((g: any) => g.destinations),
    ...(raw.turkey.cities ?? []),
  ];
  return {
    recommendation_id: "00000000-0000-4000-8000-000000000020",
    status: raw.status,
    goal: raw.goal,
    goal_label: raw[`goal_label_${lang}`],
    scope: raw.scope,
    filters_applied: {
      city_size: raw.filters_applied.city_size,
      max_distance_km: raw.filters_applied.max_distance_km,
      climate: raw.filters_applied.climate,
      purpose: "both",
      policy: raw.filters_applied.policy,
    },
    by_line: groups,
    lines_without_destinations: raw.lines_without_destinations.map(
      (l: any) => ({
        line: l.line,
        title: `${cat.bodies[l.line.body as keyof typeof cat.bodies]} · ${cat.angles[l.line.angle as keyof typeof cat.angles].line}`,
        text: l[`text_${lang}`] ?? l.text,
      }),
    ),
    places: raw.cities.map(city),
    turkey: {
      places: (raw.turkey.cities ?? []).map(city),
      regions: (raw.turkey.regions ?? []).map((p: any) => area(p, "region")),
    },
    countries: raw.countries.map((p: any) => area(p, "country")),
    regions: raw.regions.map((p: any) => area(p, "region")),
    explanations: {
      status: "ready",
      intro: raw.intro[lang],
      turkey_intro: raw.turkey.intro?.[lang] ?? null,
      groups: Object.fromEntries(
        raw.by_line.map((g: any, i: number) => [
          groups[i].group_id,
          g[`text_${lang}`],
        ]),
      ),
      items: Object.fromEntries(
        all
          .filter((p: any) => p[`text_${lang}`])
          .map((p: any) => [p.id, p[`text_${lang}`]]),
      ),
    },
    footer: typeof raw.footer === "string" ? raw.footer : raw.footer[lang],
  };
}
export function linePlaces(root: string, lang: Lang, cat: Catalogue) {
  const read = (file: string) =>
    JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
  const raw = read("acg_run/20260929-105635_kgc/city_scan_1979-03-30.json");
  const gaz = new Map(
    read("Astrocartography/gazetteer.json").cities.map((c: any) => [c.id, c]),
  );
  return Object.fromEntries(
    Object.entries(raw.by_line).map(([key, rows]: any) => {
      const [body, angle] = key.split("|");
      return [
        key,
        {
          line: {
            body,
            angle,
            planet_label: cat.bodies[body as keyof typeof cat.bodies],
            angle_label: cat.angles[angle as keyof typeof cat.angles].line,
          },
          places: rows
            .filter((r: any) => r.distance_km <= 1000)
            .sort((a: any, b: any) => a.distance_km - b.distance_km)
            .map((r: any) => {
              const city: any = gaz.get(r.city_id);
              const near = raw.cities
                .find((c: any) => c.city_id === r.city_id)
                .lines_near.find(
                  (l: any) => l.body === body && l.angle === angle,
                );
              return {
                place_id: r.city_id,
                name: lang === "tr" ? city.name_tr : city.name,
                country_code: city.country_code,
                distance_km_rounded:
                  r.distance_km < 10
                    ? "<10"
                    : Math.round(r.distance_km / 10) * 10,
                tier: near.tier,
                tier_label: cat.tiers[near.tier as keyof typeof cat.tiers],
              };
            }),
        },
      ];
    }),
  );
}
