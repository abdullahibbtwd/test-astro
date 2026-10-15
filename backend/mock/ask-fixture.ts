import { fixture, collection } from "./fixtures";
import type { AskCard, AskContext, Lang } from "../../frontend/contracts/spec-types";
import fs from "node:fs";
import { URL } from "node:url";
const chrome = Object.fromEntries(
  ["tr", "en"].map((lang) => [
    lang,
    JSON.parse(
      fs.readFileSync(
        new URL(`../../frontend/src/i18n/${lang}.json`, import.meta.url),
        "utf8",
      ),
    ),
  ]),
);
export function askFixture(
  text: string,
  context: AskContext,
  lang: Lang,
  profile: string,
) {
  const t = chrome[lang],
    starter = [1, 2, 3, 4, 5, 6].find((n) => text === t[`starter${n}`]);
  const prefix =
    lang === "tr"
      ? "Önizleme: kayıtlı verilerden bir örnek.\n\n"
      : "Preview: a sample from saved data.\n\n";
  let answer = "",
    card: AskCard | undefined,
    route = "";
  if (starter === 3 || context.place_id) {
    const place = fixture(
      `place-report.${context.place_id ?? "gn-2643743"}.${lang}`,
    );
    if (place) {
      answer = place.reading.sections
        .flatMap((s: any) => s.paragraphs.map((p: any) => p.text))
        .slice(0, 2)
        .join("\n\n");
      card = {
        type: "place",
        place_id: place.place.place_id,
        name: place.place.name,
        country_code: place.place.country_code,
        cards: place.cards.map((c: any) => ({
          goal: c.goal,
          band: c.band,
          band_label: c.band_label,
        })),
      };
      route = `/map/place/${place.place.place_id}?profile=${profile}`;
    }
  } else if (starter === 6 || context.section_key) {
    const point = fixture("chart.0").points.find(
        (p: any) => p.body === "saturn",
      ),
      cat = fixture(`catalogue.${lang}`);
    card = {
      type: "chart_fact",
      body: point.body,
      sign: point.sign,
      degree_in_sign: point.degree_in_sign,
      house: point.house,
      retrograde: point.retrograde,
    };
    answer = `${cat.bodies.saturn} · ${cat.signs[point.sign]} · ${cat.houses[String(point.house)].ordinal}`;
    route = `/chart/focus?profile=${profile}`;
  } else if (starter === 5 || context.activity) {
    const activity = context.activity ?? "business",
      best = fixture(`best-days.${lang}`).activities.find(
        (a: any) => a.activity === activity,
      );
    card = {
      type: "best_days",
      activity,
      days: best.days
        .filter((d: any) => best.top_days.includes(d.date))
        .slice(0, 3)
        .map((d: any) => ({ date: d.date, grade: d.grade })),
    };
    answer =
      best.label +
      "\n" +
      card.days
        .map(
          (d) =>
            `${d.date} · ${t[d.grade] ?? fixture(`catalogue.${lang}`).grades[d.grade]}`,
        )
        .join("\n");
    route = `/best-days/${activity}?profile=${profile}`;
  } else if (starter === 1 || context.item_id) {
    const period = context.item_id
      ? collection("period.", lang).find((p) => p.id === context.item_id)
      : collection("period.", lang).find(
          (p) => p.goal === "love" && p.end >= "2026-09-29",
        );
    if (period) {
      const item = fixture(`item.${encodeURIComponent(period.id)}.${lang}`);
      answer = item?.text?.text ?? period.label;
      card = { type: "period", period };
      route = `/calendar/item/${encodeURIComponent(period.id)}?profile=${profile}`;
    }
  } else if (starter === 2 || context.month) {
    answer =
      lang === "tr"
        ? "Bu takvim ayı için kayıtlı bir iş yorumu yok. Takvim verilerini aylık görünümde inceleyebilirsin."
        : "There is no saved business reading for this calendar month. You can review the calendar facts in the monthly view.";
    card = {
      type: "forecast",
      horizon: "month",
      month: context.month ?? "2026-09",
      title: t.month,
    };
    route = `/forecast/month/${card.month}?profile=${profile}`;
  } else if (!starter && (!context.date || context.date === "2026-09-29")) {
    answer = fixture(`forecast-day.${lang}`).reading.text;
    card = {
      type: "forecast",
      horizon: "day",
      date: "2026-09-29",
      title: t.today,
    };
    route = `/ahead/today?profile=${profile}`;
  }
  return {
    text:
      prefix +
      (answer ||
        (lang === "tr"
          ? "Bu istek için eşleşen kayıtlı bir örnek yok."
          : "No matching saved sample is available for this request.")),
    card,
    route,
  };
}
