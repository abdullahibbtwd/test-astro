import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mapChart } from "./chart";
import { geoFixtures } from "./geo";
import { recommendations, linePlaces } from "./recommend";
import { catalogue } from "./catalogue";
import { calendarFixtures, scores } from "./calendar";
import { validate } from "../../src/api/zod";
import type { Lang } from "../../contracts/spec-types";

const root = path.resolve("..");
const read = (file: string) =>
  JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
const labels = JSON.parse(
  execFileSync(
    process.env.PYTHON ?? "python",
    ["-X", "utf8", "mock-api/scripts/backend-labels.py"],
    { encoding: "utf8", maxBuffer: 8_000_000 },
  ),
);
export const ids = [
  "00000000-0000-4000-8000-000000000001",
  "00000000-0000-4000-8000-000000000002",
  "00000000-0000-4000-8000-000000000003",
];
const chartSources = [
  [
    "prediction_run/20260929-130811_qpm",
    "1979-03-30",
    "natal_chart",
    "06:30",
    "Sofia",
  ],
  [
    "runs/20260924-102926_26p_1988-12-28",
    "1988-12-28",
    "chart",
    "13:00",
    "Plovdiv",
  ],
  [
    "runs/20260922-181953_w1d_1984-06-12",
    "1984-06-12",
    "chart",
    "14:57",
    "Sofia",
  ],
];
const generated = "2026-09-29T13:08:11Z";
const manifest: any[] = [];
fs.mkdirSync("mock-api/fixtures", { recursive: true });
const save = (filename: string, schema: string, data: any) => {
  try {
    validate(schema, data);
  } catch (error: any) {
    throw new Error(
      filename +
        " " +
        JSON.stringify(
          error.issues?.map((i: any) => ({ path: i.path, message: i.message })),
        ),
      { cause: undefined },
    );
  }
  fs.writeFileSync(
    `mock-api/fixtures/${filename}.json`,
    JSON.stringify(data, null, 2) + "\n",
  );
  manifest.push({
    file: `${filename}.json`,
    schema,
    sha256: createHash("sha256").update(JSON.stringify(data)).digest("hex"),
  });
  return data;
};
for (const lang of ["tr", "en"] as Lang[]) {
  const cat = save(`catalogue.${lang}`, "Catalogue", catalogue(lang, labels));
  const places = [
    {
      place_id: "geo-sofia",
      name: lang === "tr" ? "Sofya" : "Sofia",
      admin1: null,
      country_code: "BG",
      country_name: lang === "tr" ? "Bulgaristan" : "Bulgaria",
      lat: 42.6977,
      lon: 23.3217,
      tz: "Europe/Sofia",
    },
    {
      place_id: "geo-plovdiv",
      name: lang === "tr" ? "Filibe" : "Plovdiv",
      admin1: null,
      country_code: "BG",
      country_name: lang === "tr" ? "Bulgaristan" : "Bulgaria",
      lat: 42.1419,
      lon: 24.7499,
      tz: "Europe/Sofia",
    },
    {
      place_id: "gn-istanbul",
      name: lang === "tr" ? "İstanbul" : "Istanbul",
      admin1: null,
      country_code: "TR",
      country_name: lang === "tr" ? "Türkiye" : "Turkey",
      lat: 41.0138,
      lon: 28.9497,
      tz: "Europe/Istanbul",
    },
  ];
  for (const p of places) save(`place.${p.place_id}.${lang}`, "Place", p);
  const profiles = chartSources.map(([dir, date, prefix, time, city], i) => {
    const raw = read(`${dir}/${prefix}_${date}.json`);
    const key = createHash("sha256")
      .update(JSON.stringify(raw))
      .digest("hex")
      .slice(0, 16);
    const chart = save(`chart.${i}`, "ChartData", mapChart(raw, ids[i]!, key));
    const place = places[city === "Plovdiv" ? 1 : 0];
    const profile = {
      profile_id: ids[i],
      chart_key: key,
      label: `Person ${String.fromCharCode(65 + i)}`,
      relation: ["self", "partner", "colleague"][i],
      is_self: i === 0,
      birth: { date, time, place, tz: raw.meta.timezone, utc: raw.meta.utc },
      gender: null,
      current_place: null,
      big_three: {
        sun: chart.points.find((p: any) => p.body === "sun").sign,
        moon: chart.points.find((p: any) => p.body === "moon").sign,
        ascendant: chart.axes.asc.sign,
      },
      created_at: generated,
      updated_at: generated,
    };
    save(`profile.${i}.${lang}`, "BirthProfile", profile);
    if (i > 0) {
      const reading = read(`${dir}/l4_output_${date}.json`);
      save(`natal.${i}.${lang}`, "NatalReading", {
        profile_id: ids[i],
        chart_key: key,
        lang,
        generated_at: generated,
        title: labels.natal[lang].title,
        parts: [1, 2].map((movement) => ({
          movement,
          title: labels.natal[lang].parts[movement],
        })),
        sections: reading.sections
          .filter((s: any) => s[`text_${lang}`]?.trim())
          .map((s: any) => ({
            key: s.key,
            movement: s.movement,
            house: s.house ?? null,
            title: labels.natal[lang].sections[s.key][String(s.house ?? 0)],
            text: s[`text_${lang}`],
          })),
      });
    }
    return profile;
  });
  const geo = geoFixtures(root, profiles[0]!.chart_key);
  if (lang === "tr") {
    save("acg-lines", "AcgLines", geo.lines);
    save("geo-countries", "CountryGeometry", geo.countries);
    for (const [iso, data] of Object.entries(geo.regions))
      save(`geo-regions.${iso}`, "RegionGeometry", data);
  }
  save(
    `recommend-love.${lang}`,
    "Recommendation",
    recommendations(root, lang, cat),
  );
  for (const [key, data] of Object.entries(linePlaces(root, lang, cat)))
    save(`line-places.${key.replace("|", ".")}.${lang}`, "LinePlaces", data);
  const prefs = {
    enabled: false,
    types: Object.fromEntries(
      Object.keys(cat.notification_types).map((k) => [k, true]),
    ),
    time: "09:00",
    max_per_day: 1,
    max_per_week: 3,
    quiet_hours: { start: "22:00", end: "08:00" },
  };
  save(`me.${lang}`, "Me", {
    user_id: "00000000-0000-4000-8000-000000000010",
    email: "demo@example.com",
    display_name: "Person A",
    language: lang,
    theme: "system",
    current_place: places[0],
    self_profile_id: ids[0],
    notification_prefs: prefs,
    entitlements: { all: true },
    ask_quota: {
      limit_per_day: 30,
      used_today: 0,
      resets_at: "2026-09-30T00:00:00+03:00",
    },
    consents: {
      birth_data: { version: "mock-only", accepted_at: generated },
      marketing: false,
    },
    created_at: generated,
  });
  const cal = calendarFixtures(root, lang, cat, labels, ids[0]!);
  for (const [month, data] of Object.entries(cal.months))
    save(`month.${month}.${lang}`, "CalendarMonth", data);
  for (const [date, data] of Object.entries(cal.days))
    save(`day.${date}.${lang}`, "CalendarDayDetail", data);
  for (const [id, data] of Object.entries(cal.items))
    save(`item.${encodeURIComponent(id)}.${lang}`, "CalendarItem", data);
  for (const p of cal.periods)
    save(`period.${encodeURIComponent(p.id)}.${lang}`, "PeriodRef", p);
  save(`calendar-year.${lang}`, "CalendarYear", cal.year);
  save(`best-days.${lang}`, "BestDaysOverview", cal.best);
  for (const [key, data] of Object.entries(cal.bestDetails))
    save(`best.${key.replace("/", ".")}.${lang}`, "BestDayDetail", data);
  for (const n of cal.notifications)
    save(
      `notification.${encodeURIComponent(n.id)}.${lang}`,
      "NotificationCandidate",
      n,
    );
  const date = "2026-09-29";
  const day = cal.days[date];
  const ds = cal.rawScores.find((d: any) => d.local_date === date);
  const predict = read(
    `prediction_run/20260929-130811_qpm/reading_day_general_${date}_1979-03-30${lang === "en" ? ".en" : ""}.json`,
  );
  const areas = Object.fromEntries(
    Object.entries(ds.goals).map(([key, g]: any) => [
      key,
      {
        band: g.band,
        label: cat.day_bands[g.band],
        score_10: scores[g.band],
        drivers: ds.drivers[key].map((id: string) => cal.label(id)),
      },
    ]),
  );
  const forecast = save(`forecast-day.${lang}`, "DayForecast", {
    profile_id: ids[0],
    date,
    tz: "Europe/Sofia",
    lens: "general",
    tone: day.tone,
    tone_label: day.tone_label,
    score_10: scores[day.tone],
    areas,
    moon: day.moon,
    retrograde: day.retrograde,
    events: day.events,
    transits: day.transits,
    reading: { status: "ready", text: predict.reading },
    day_note: day.day_note,
    best_activities: day.best_activities,
  });
  const upcomingKinds: Record<string, string> = {
    favorable_window: "best_window",
    period_start: "period_start",
    lunation_in_house: "lunation",
    retrograde_start: "retrograde_start",
    station_on_point: "transit_peak",
    eclipse_hit: "eclipse",
  };
  save(`home.${lang}`, "HomeSummary", {
    date,
    tz: forecast.tz,
    greeting_name: "Person A",
    tone: forecast.tone,
    tone_label: forecast.tone_label,
    score_10: forecast.score_10,
    tiles: ["love", "career", "money", "family"].map((key) => ({
      key,
      label: cat.goals[key],
      band: areas[key]?.band,
      score_10: areas[key]?.score_10,
    })),
    moon: forecast.moon,
    today: forecast.reading,
    next_up: cal.notifications
      .filter(
        (n: any) => n.trigger_date > date && n.trigger_date <= "2026-10-13",
      )
      .sort((a: any, b: any) => a.trigger_date.localeCompare(b.trigger_date))
      .slice(0, 3)
      .map((n: any) => ({
        kind: upcomingKinds[n.type],
        date: n.trigger_date,
        label: n.text,
        deep_link: n.deep_link,
      })),
  });
  const acg = "acg_run/20260929-105635_kgc";
  const raw = read(`${acg}/reading_${lang}_1979-03-30.json`);
  const loc = read(`${acg}/locate_1979-03-30.json`);
  save(`place-report.istanbul.${lang}`, "PlaceReport", {
    place: {
      place_id: "gn-istanbul",
      name: places[2]?.name,
      country_code: "TR",
      lat: loc.place.lat,
      lon: loc.place.lon,
    },
    status: loc.status,
    relocation: { status: loc.relocation.status },
    focus_goal: raw.focus_goal ?? null,
    lines_display: raw.lines_display.map((l: any) => ({
      body: l.body,
      angle: l.angle,
      planet_label: l[`planet_${lang}`],
      angle_label: l[`angle_label_${lang}`],
      distance_km_rounded: l.distance_km_rounded,
      tier: l.tier,
      tier_label: l[`tier_label_${lang}`],
      read_in_prose: l.read_in_prose,
    })),
    parans_display: raw.parans_display.map((p: any) => ({
      id: p.id,
      bodies:
        p.bodies ??
        p.planets ??
        p.planets_en.map((name: string) => name.toLowerCase()),
      planet_labels: p[`planets_${lang}`],
      north_south: p.north_south,
      distance_km_rounded: p.distance_km_rounded,
      label: p[`label_${lang}`],
    })),
    goal_scores: Object.fromEntries(
      Object.entries(raw.goal_scores).map(([g, v]: any) => [
        g,
        { band: v.band, label: v[`band_label_${lang}`] },
      ]),
    ),
    cards: (
      raw.sections.find((s: any) => s.key === "suitability")?.cards ?? []
    ).map((c: any) => ({
      card: c.card,
      goal: c.goal,
      title: c.title,
      band: c.band,
      band_label: c[`band_label_${lang}`],
      text: c.text ?? null,
    })),
    reading: {
      status: "ready",
      sections: raw.sections
        .filter((s: any) => s.key !== "suitability" && s.paragraphs?.length)
        .map((s: any) => ({
          key: s.key,
          title: s.title,
          paragraphs: s.paragraphs.map((p: any) => ({
            slot_id: p.slot_id,
            text: p.text,
          })),
        })),
    },
    footer: raw.footer,
  });
}
save("config", "Config", {
  min_app_version: { ios: "0.1.0", android: "0.1.0" },
  flags: {
    askAstrology: true,
    solarReturn: false,
    familyCompatibility: false,
    compatibilityScore: false,
    homeEnergyTile: false,
    dayScoreNumbers: true,
    elementNotes: false,
    showTraces: false,
  },
  polling: {
    initial_ms: [1000, 2000, 3000],
    interval_ms: 4000,
    slow_after_s: 180,
    give_up_after_s: 600,
  },
  map_style_url: { light: "", dark: "" },
  links: { privacy: "", terms: "", support: "" },
});
const unique = [
  ...new Map(manifest.map((entry) => [entry.file, entry])).values(),
].sort((a, b) => a.file.localeCompare(b.file));
fs.writeFileSync(
  "mock-api/fixtures/manifest.json",
  JSON.stringify(unique, null, 2) + "\n",
);
console.log(
  `${unique.length} validated fixtures from real outputs; no model calls`,
);
