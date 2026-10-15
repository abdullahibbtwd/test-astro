import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mapChart } from "./chart";
import { geoFixtures } from "./geo";
import { recommendations, linePlaces } from "./recommend";
import { catalogue } from "./catalogue";
import { calendarFixtures, scores } from "./calendar";
import { validate } from "../../../frontend/src/api/zod";
import type { Lang } from "../../../frontend/contracts/spec-types";

const root = path.resolve("..");
const read = (file: string) =>
  JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
const labels = JSON.parse(
  execFileSync(
    process.env.PYTHON ?? "python",
    ["-X", "utf8", "mock/scripts/backend-labels.py"],
    { encoding: "utf8", maxBuffer: 8_000_000 },
  ),
);
const areaSource = JSON.parse(
  execFileSync(
    process.env.PYTHON ?? "python",
    ["-X", "utf8", "mock/scripts/areas.py"],
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
fs.mkdirSync("mock/fixtures", { recursive: true });
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
    `mock/fixtures/${filename}.json`,
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
  for (const [goal, run] of Object.entries({
    overall: "20260928-114920_2xr",
    career: "20260928-112003_5ta",
    relocation: "20260928-112140_9qt",
    travel: "20260928-112245_gzw",
  }))
    save(
      `recommend-${goal}.${lang}`,
      "Recommendation",
      recommendations(
        root,
        lang,
        cat,
        `acg_run/${run}/recommend_${goal}_world_1979-03-30.json`,
      ),
    );
  if (lang === "tr")
    for (const goal of Object.keys(cat.goals)) {
      const heat = read(
        `acg_run/20260929-105635_kgc/goal_heat_${goal}_1979-03-30.geojson`,
      );
      const levels: Record<string, number> = {
        strongly_supportive: 2,
        supportive: 1,
        mixed: 0,
        challenging: -1,
        strongly_challenging: -1,
      };
      save(`heat.${goal}`, "AcgHeat", {
        chart_key: profiles[0]!.chart_key,
        goal,
        grid_step_deg: 0.5,
        points: heat.features
          .filter((f: any) => f.properties.band in levels)
          .map((f: any) => [
            ...f.geometry.coordinates,
            levels[f.properties.band],
          ]),
      });
    }
  for (const [key, data] of Object.entries(linePlaces(root, lang, cat)))
    save(`line-places.${key.replace("|", ".")}.${lang}`, "LinePlaces", data);
  for (const area of areaSource.areas.filter((a: any) => a.status === "ok")) {
    const meta = (
      area.kind === "country" ? areaSource.countries : areaSource.regions
    ).find(
      (a: any) =>
        (a.iso_a2 === area.code && area.kind === "country") ||
        a.admin1_id === area.code,
    );
    save(`area-search.${area.code}.${lang}`, "PlaceCandidate", {
      place_id: `${area.kind === "country" ? "iso2" : "admin1"}:${area.code}`,
      kind: area.kind,
      name: lang === "tr" ? area.name_tr : area.name,
      admin1: null,
      country_code: area.iso_a2,
      country_name: new Intl.DisplayNames([lang], { type: "region" }).of(
        area.iso_a2,
      ),
      lat: (meta.bbox[1] + meta.bbox[3]) / 2,
      lon: (meta.bbox[0] + meta.bbox[2]) / 2,
      tz: "Etc/UTC",
      population: null,
      source: "gazetteer",
    });
    save(`area-report.${area.code}.${lang}`, "AreaReport", {
      area: {
        kind: area.kind,
        id: area.code,
        iso2: area.iso_a2,
        name: lang === "tr" ? area.name_tr : area.name,
      },
      status: "ok",
      bands: Object.fromEntries(
        Object.entries(area.bands).map(([key, value]: any) => [
          key,
          { band: value.band, label: cat.place_bands[value.band] },
        ]),
      ),
      lines_crossing: area.lines_crossing.map((l: any) => ({
        body: l.body,
        angle: l.angle,
        planet_label: cat.bodies[l.body],
        angle_label: cat.angles[l.angle].line,
      })),
      best_cities: Object.fromEntries(
        Object.entries(area.best_cities).map(([key, items]: any) => [
          key,
          items.map((c: any) => ({
            place_id: c.id,
            name: lang === "tr" ? c.name_tr : c.name,
            band: c.band,
            band_label: cat.place_bands[c.band],
          })),
        ]),
      ),
      varies_by_region: area.varies_by_region,
      ...(area.kind === "country"
        ? {
            regions: areaSource.areas
              .filter(
                (a: any) => a.kind === "region" && a.iso_a2 === area.iso_a2,
              )
              .map((a: any) => ({
                admin1_id: a.code,
                name: lang === "tr" ? a.name_tr : a.name,
              })),
          }
        : {}),
      overview: { status: "absent", absence: { reason: "no_grounding" } },
      footer: read(
        `acg_run/20260929-105635_kgc/reading_${lang}_1979-03-30.json`,
      ).footer,
    });
  }
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
  // Calendar-month facts are exact. Existing rolling-month prose is deliberately not relabelled.
  for (const [month, data] of Object.entries(cal.months) as [string, any][]) {
    const last = new Date(
      Date.UTC(Number(month.slice(0, 4)), Number(month.slice(5)), 0),
    ).getUTCDate();
    save(`forecast-month.${month}.${lang}`, "MonthForecast", {
      profile_id: ids[0],
      month,
      tz: "Europe/Sofia",
      lens: "general",
      segments: {
        early: { from: `${month}-01`, to: `${month}-10` },
        mid: { from: `${month}-11`, to: `${month}-20` },
        late: { from: `${month}-21`, to: `${month}-${last}` },
      },
      reading: { status: "absent", absence: { reason: "no_grounding" } },
      highlights: {
        favorable_days: data.days
          .filter((d: any) => d.tone === "favorable")
          .map((d: any) => d.date),
        challenging_days: data.days
          .filter((d: any) => d.tone === "challenging")
          .map((d: any) => d.date),
        periods: data.periods,
        major_transits: data.major_transits,
        lunations: data.lunations,
        eclipses: data.eclipses,
        retrogrades: data.retrograde_periods,
      },
    });
  }
  const yearSource = read(
    `prediction_run/20260929-130811_qpm/reading_year_general_2026-09-29_1979-03-30${lang === "en" ? ".en" : ""}.json`,
  );
  const yearStart = Date.UTC(2026, 8, 29);
  const dateAt = (offset: number) =>
    new Date(yearStart + offset * 86400000).toISOString().slice(0, 10);
  save(`forecast-year.${lang}`, "YearForecast", {
    profile_id: ids[0],
    from: dateAt(0),
    to: dateAt(364),
    tz: "Europe/Sofia",
    lens: "general",
    quarters: ["q1", "q2", "q3", "q4"].map((key, i) => ({
      key,
      from: dateAt(Math.floor((365 * i) / 4)),
      to: dateAt(Math.floor((365 * (i + 1)) / 4) - 1),
    })),
    reading: {
      status: "ready",
      ...Object.fromEntries(
        ["overview", "q1", "q2", "q3", "q4", "focus"].map((k) => [
          k,
          yearSource[k],
        ]),
      ),
      focus_title: cat.lens_focus_titles.general,
    },
    highlights: {
      strongest_periods: cal.periods
        .filter(
          (p: any) =>
            p.kind === "favorable" &&
            (p.importance === "major" || p.strength === "strong"),
        )
        .slice(0, 6),
      challenging_periods: cal.periods
        .filter(
          (p: any) =>
            p.kind === "challenging" &&
            (p.importance === "major" || p.strength === "strong"),
        )
        .slice(0, 6),
      key_events: [
        ...cal.year.eclipses,
        ...cal.year.major_transits.map((e: any) => ({ ...e, kind: "transit" })),
      ],
      retrogrades: cal.year.retrograde_periods,
    },
    months: Array.from({ length: 12 }, (_, i) => {
      const d = new Date(Date.UTC(2026, 8 + i, 1));
      return {
        month: d.toISOString().slice(0, 7),
        label: new Intl.DateTimeFormat(lang, {
          month: "long",
          year: "numeric",
          timeZone: "UTC",
        }).format(d),
      };
    }),
  });
  const relationship = read(
    "synastry_run/20260701-131712_uxp_1988-12-28_1979-03-30/relationship_reading_1988-12-28_1979-03-30.json",
  );
  const person = (i: number) => ({
    profile_id: ids[i],
    label: profiles[i]!.label,
    big_three: profiles[i]!.big_three,
  });
  save(`compat-love.${lang}`, "Compatibility", {
    compatibility_id: "00000000-0000-4000-8000-000000000030",
    type: "love",
    family_relation: null,
    people: { a: person(1), b: person(0) },
    created_at: generated,
    score: null,
    reading: {
      status: "ready",
      title: labels.compat.title[lang],
      sections: relationship.sections.map((section: any) => ({
        key: section.key,
        movement: section.movement,
        title: labels.compat.titles[section.key][lang],
        text: section[`text_${lang}`]
          .replace(/\bR\b/g, profiles[1]!.label)
          .replace(/\bN\b/g, profiles[0]!.label),
      })),
    },
  });
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
  for (const [dayDate, detail] of Object.entries(cal.days) as [string, any][]) {
    if (dayDate === date) continue;
    const rawDay = cal.rawScores.find((d: any) => d.local_date === dayDate);
    if (!rawDay) continue;
    save(`forecast-day.${dayDate}.${lang}`, "DayForecast", {
      ...forecast,
      date: dayDate,
      tone: detail.tone,
      tone_label: detail.tone_label,
      score_10: scores[detail.tone],
      areas: Object.fromEntries(
        Object.entries(rawDay.goals).map(([key, g]: any) => [
          key,
          {
            band: g.band,
            label: cat.day_bands[g.band],
            score_10: scores[g.band],
            drivers: rawDay.drivers[key].map((id: string) => cal.label(id)),
          },
        ]),
      ),
      moon: detail.moon,
      retrograde: detail.retrograde,
      events: detail.events,
      transits: detail.transits,
      day_note: detail.day_note,
      best_activities: detail.best_activities,
      reading: { status: "absent", absence: { reason: "no_grounding" } },
    });
  }
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
  const gazetteer = read("Astrocartography/gazetteer.json").cities;
  for (const run of [
    "20260929-105635_kgc",
    "20260928-091748_iqi",
    "20260928-091853_dql",
    "20260928-091951_ovn",
    "20260928-092115_26m",
    "20260928-102133_dp1",
    "20260929-103820_3o1",
  ]) {
    const acg = `acg_run/${run}`;
    const raw = read(`${acg}/reading_${lang}_1979-03-30.json`);
    const loc = read(`${acg}/locate_1979-03-30.json`);
    const city = gazetteer.find((p: any) => p.name === loc.place.name);
    const placeId = city?.id ?? `spot-${run}`;
    if (city)
      save(`map-place.${placeId}.${lang}`, "Place", {
        place_id: placeId,
        name: lang === "tr" ? city.name_tr : city.name,
        admin1: null,
        country_code: city.country_code,
        country_name: new Intl.DisplayNames([lang], { type: "region" }).of(
          city.country_code,
        ),
        lat: loc.place.lat,
        lon: loc.place.lon,
        tz: (
          {
            BG: "Europe/Sofia",
            TR: "Europe/Istanbul",
            DE: "Europe/Berlin",
            GB: "Europe/London",
            ES: "Europe/Madrid",
            HK: "Asia/Hong_Kong",
          } as Record<string, string>
        )[city.country_code],
      });
    save(`place-report.${placeId}.${lang}`, "PlaceReport", {
      place: {
        place_id: placeId,
        name: lang === "tr" ? raw.place.name_tr : raw.place.name,
        country_code: loc.place.country_code,
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
      parans_display: (raw.parans_display ?? []).map((p: any) => ({
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
  "mock/fixtures/manifest.json",
  JSON.stringify(unique, null, 2) + "\n",
);
console.log(
  `${unique.length} validated fixtures from real outputs; no model calls`,
);
