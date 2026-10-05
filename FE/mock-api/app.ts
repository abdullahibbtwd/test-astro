import { TZDate } from "@date-fns/tz";
import Fastify, { type FastifyReply } from "fastify";
import cors from "@fastify/cors";
import { createHash, randomUUID } from "node:crypto";
import fs from "node:fs";
import { fileURLToPath, URL } from "node:url";
import { validate } from "../src/api/zod";
import { fixture, collection } from "./fixtures";
import { askFixture } from "./ask-fixture";
import { Jobs } from "./jobs";
import type { Job, Thread, Message, ReportRef } from "../contracts/spec-types";

const api = JSON.parse(
  fs.readFileSync(
    fileURLToPath(new URL("../contracts/openapi.json", import.meta.url)),
    "utf8",
  ),
);
const problem = (
  code: string,
  status: number,
  lang: string,
  detail?: string,
) => ({
  type: "about:blank",
  title: lang === "tr" ? "İstek tamamlanamadı" : "Unable to complete request",
  status,
  code,
  ...(detail ? { detail } : {}),
});
export function buildApp(options: { now?: () => number; jobMs?: number } = {}) {
  const app = Fastify({ logger: false });
  app.register(cors, {
    origin: /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/,
    exposedHeaders: ["ETag", "Retry-After", "X-Mock-Today"],
  });
  const jobs = new Jobs(
    options.now,
    options.jobMs ?? Number(process.env.MOCK_JOB_SECONDS ?? 6) * 1000,
  );
  let me = fixture("me.tr");
  let profiles = collection("profile.", "tr");
  const source = new Map(profiles.map((p, i) => [p.profile_id, i]));
  const seedProfiles = structuredClone(profiles);
  const birthKey = (birth: any) =>
    JSON.stringify([birth.date, birth.time, birth.place.place_id]);
  const localizedProfile = (value: any, lang: string) => ({
    ...value,
    birth: {
      ...value.birth,
      place: fixture(`place.${value.birth.place.place_id}.${lang}`),
    },
    current_place: value.current_place
      ? fixture(`place.${value.current_place.place_id}.${lang}`)
      : null,
  });
  const reports = new Map<string, ReportRef & { lang: string }>();
  const threads = new Map<string, Thread>();
  const compat = new Map<string, any>();
  const tokens = new Set(["mock-access"]);
  const refreshTokens = new Set(["mock-refresh"]);
  const idempotency = new Map<
    string,
    { body: string; value: any; status: number; expires: number }
  >();
  const clock = options.now ?? (() => Date.now());
  const session = () => {
    const access = `mock-${randomUUID()}`,
      refresh = `mock-${randomUUID()}`;
    tokens.add(access);
    refreshTokens.add(refresh);
    return {
      access_token: access,
      access_expires_at: new Date(clock() + 3600000).toISOString(),
      refresh_token: refresh,
      is_new_user: false,
      me,
    };
  };
  const page = (values: any[], query: any) => {
    const cursor = query.cursor ? Number(query.cursor) : 0;
    const limit = Math.min(Number(query.limit ?? 20), 50);
    if (
      !Number.isInteger(cursor) ||
      cursor < 0 ||
      !Number.isInteger(limit) ||
      limit < 1
    )
      throw Object.assign(new Error("Invalid pagination"), { statusCode: 400 });
    return {
      items: values.slice(cursor, cursor + limit),
      next_cursor:
        cursor + limit < values.length ? String(cursor + limit) : null,
    };
  };
  function fail(
    reply: FastifyReply,
    code: string,
    status: number,
    lang: string,
    detail?: string,
  ) {
    return reply
      .code(status)
      .type("application/problem+json")
      .send(validate("Problem", problem(code, status, lang, detail)));
  }
  app.setErrorHandler((error, request, reply) =>
    fail(
      reply,
      (error as any).statusCode === 400 ? "validation_error" : "internal",
      (error as any).statusCode === 400 ? 400 : 500,
      (request.query as any)?.lang ?? "tr",
    ),
  );
  for (const [route, methods] of Object.entries(api.paths) as [string, any][]) {
    for (const [method, operation] of Object.entries(methods) as [
      string,
      any,
    ][]) {
      app.route({
        method: method.toUpperCase() as any,
        url: "/v1" + route.replace(/\{([^}]+)\}/g, ":$1"),
        handler: async (request, reply) => {
          const q = request.query as Record<string, string>,
            p = request.params as Record<string, string>;
          const body = (request.body ?? {}) as any;
          const lang = q.lang ?? me?.language ?? "tr";
          const scenario = String(
            request.headers["x-mock-scenario"] ?? "ready",
          );
          reply.header("X-Mock-Today", "2026-09-29");
          if (scenario === "offline") {
            request.raw.destroy();
            return reply;
          }
          if (!["tr", "en"].includes(lang))
            return fail(reply, "validation_error", 400, "tr");
          if (scenario === "rate_limited") {
            reply.header("Retry-After", "30");
            return fail(reply, "rate_limited", 429, lang);
          }
          if (scenario === "new_off" && operation["x-backend-status"] === "NEW")
            return fail(reply, "not_found", 404, lang);
          if (
            operation.security === undefined &&
            !tokens.has(
              String(request.headers.authorization ?? "").replace(
                /^Bearer /,
                "",
              ),
            )
          )
            return fail(reply, "unauthorized", 401, lang);
          if (operation.requestBody) {
            const schema = operation.requestBody.content[
              "application/json"
            ].schema.$ref
              .split("/")
              .at(-1);
            try {
              validate(schema, body);
            } catch {
              return fail(reply, "validation_error", 400, lang);
            }
          }
          for (const param of operation.parameters ?? [])
            if (param.in === "query" && param.required && !q[param.name])
              return fail(reply, "validation_error", 400, lang);
          const keyHeader = request.headers["idempotency-key"];
          const idem = keyHeader
            ? `${method}:${request.url.split("?")[0]}:${lang}:${String(keyHeader)}`
            : undefined;
          if (idem) {
            const prior = idempotency.get(idem);
            if (prior && prior.expires > clock()) {
              if (prior.body !== JSON.stringify(body))
                return fail(reply, "conflict", 409, lang);
              return reply.code(prior.status).send(prior.value);
            }
          }
          const profile =
            p.id && route.startsWith("/profiles/")
              ? profiles.find((x) => x.profile_id === p.id)
              : undefined;
          if (p.id && route.startsWith("/profiles/") && !profile)
            return fail(reply, "not_found", 404, lang);
          const idx = profile ? source.get(profile.profile_id) : 0;
          const selfId = me?.self_profile_id;
          const originalSelf =
            idx === 0 && profile?.chart_key === seedProfiles[0].chart_key;
          const fixtureOnly = () =>
            fail(
              reply,
              "upstream_unavailable",
              503,
              lang,
              "The requested fixture is missing or does not match this profile/period. See FE_EXPLORATION_REPORT.md.",
            );
          const accepted = () => reply.code(202).send();
          const noContent = () => reply.code(204).send();
          let result: any;
          const status = operation.responses["201"] ? 201 : 200;
          switch (`${method} ${route}`) {
            case "post /auth/email/start":
              if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.email))
                return fail(reply, "validation_error", 400, lang);
              return noContent();
            case "post /auth/email/verify":
              if (
                body.code !== "000000" ||
                !["demo@example.com", "new@example.com"].includes(body.email)
              )
                return fail(reply, "unauthorized", 401, lang);
              if (!me || body.email === "new@example.com") {
                me = fixture("me.tr");
                me.email = body.email;
                me.self_profile_id = null;
                me.consents = { birth_data: null, marketing: false };
                profiles = [];
                threads.clear();
                reports.clear();
              }
              result = session();
              result.is_new_user = !me.self_profile_id;
              break;
            case "post /auth/apple":
            case "post /auth/google":
              return fixtureOnly();
            case "post /auth/refresh":
              if (!refreshTokens.delete(body.refresh_token))
                return fail(reply, "unauthorized", 401, lang);
              result = session();
              break;
            case "post /auth/logout":
              refreshTokens.delete(body.refresh_token);
              tokens.clear();
              return noContent();
            case "get /me":
              result = {
                ...me,
                language: lang,
                current_place: me.current_place
                  ? fixture(`place.${me.current_place.place_id}.${lang}`)
                  : null,
              };
              break;
            case "patch /me": {
              const { current_place_id, ...updates } = body;
              if (current_place_id !== undefined) {
                const place =
                  current_place_id === null
                    ? null
                    : fixture(`place.${current_place_id}.${lang}`);
                if (current_place_id && !place)
                  return fail(reply, "validation_error", 400, lang);
                me.current_place = place;
              }
              me = { ...me, ...updates };
              result = me;
              break;
            }
            case "delete /me":
              tokens.clear();
              refreshTokens.clear();
              profiles = [];
              threads.clear();
              compat.clear();
              reports.clear();
              me = null;
              return accepted();
            case "post /me/export":
              return fixtureOnly(); // No email transport: never claim an export was sent.
            case "get /meta/config":
              result = fixture("config");
              break;
            case "get /meta/catalogue":
              result = fixture(`catalogue.${lang}`);
              break;
            case "get /places/search":
              if (q.kind && !["birth", "city", "area"].includes(q.kind))
                return fail(reply, "validation_error", 400, lang);
              if (q.kind === "area") {
                result = collection("area-search.", lang)
                  .filter(
                    (x) =>
                      (q.q?.length ?? 0) >= 2 &&
                      x.name
                        .toLocaleLowerCase(lang)
                        .includes((q.q ?? "").toLocaleLowerCase(lang)),
                  )
                  .slice(0, Math.min(Number(q.limit ?? 8), 50));
                break;
              }
              result =
                (q.q?.length ?? 0) < 2
                  ? []
                  : [
                      ...collection("place.", lang),
                      ...(q.kind === "city"
                        ? collection("map-place.", lang)
                        : []),
                    ]
                      .filter((x) =>
                        x.name
                          .toLocaleLowerCase(lang)
                          .includes(q.q!.toLocaleLowerCase(lang)),
                      )
                      .slice(0, Math.min(Number(q.limit ?? 8), 50))
                      .map((x) => ({
                        ...x,
                        kind: "city",
                        population: null,
                        source: "geocoder",
                      }));
              break;
            case "get /places/{place_id}":
              result =
                fixture(`place.${p.place_id}.${lang}`) ??
                fixture(`map-place.${p.place_id}.${lang}`);
              if (!result) return fail(reply, "not_found", 404, lang);
              break;
            case "get /places/reverse": {
              const lat = Number(q.lat),
                lon = Number(q.lon);
              if (
                !Number.isFinite(lat) ||
                !Number.isFinite(lon) ||
                Math.abs(lat) > 90 ||
                Math.abs(lon) > 180
              )
                return fail(reply, "validation_error", 400, lang);
              result =
                collection("place.", lang)
                  .map((x) => ({
                    x,
                    d: Math.hypot(
                      (x.lat - lat) * 111,
                      (x.lon - lon) * 111 * Math.cos((lat * Math.PI) / 180),
                    ),
                  }))
                  .sort((a, b) => a.d - b.d)
                  .find((x) => x.d <= 75)?.x ?? null;
              break;
            }
            case "get /profiles":
              result = profiles.map((x) => localizedProfile(x, lang));
              break;
            case "get /profiles/{id}":
              result = localizedProfile(profile, lang);
              break;
            case "post /profiles":
            case "patch /profiles/{id}": {
              if (method === "post" && profiles.length >= 50)
                return fail(reply, "conflict", 409, lang);
              if (
                body.label !== undefined &&
                (body.label.trim().length < 1 || body.label.trim().length > 40)
              )
                return fail(reply, "validation_error", 400, lang);
              if (
                body.birth_date !== undefined &&
                (!/^\d{4}-\d{2}-\d{2}$/.test(body.birth_date) ||
                  Number.isNaN(Date.parse(body.birth_date)) ||
                  new Date(body.birth_date).toISOString().slice(0, 10) !==
                    body.birth_date ||
                  body.birth_date < "1900-01-01" ||
                  body.birth_date > "2026-09-29")
              )
                return fail(reply, "validation_error", 400, lang);
              if (
                body.birth_time !== undefined &&
                !/^([01]\d|2[0-3]):[0-5]\d$/.test(body.birth_time)
              )
                return fail(reply, "validation_error", 400, lang);
              if (
                body.relation === "self" &&
                profiles.some((x) => x.is_self && x.profile_id !== p.id)
              )
                return fail(reply, "conflict", 409, lang);
              if (profile?.is_self && body.relation && body.relation !== "self")
                return fail(reply, "conflict", 409, lang);
              if (
                body.birth_place_id &&
                !fixture(`place.${body.birth_place_id}.${lang}`)
              )
                return fail(reply, "validation_error", 400, lang);
              const original = profile ?? seedProfiles[0];
              const birth = {
                ...original.birth,
                date: body.birth_date ?? original.birth.date,
                time: body.birth_time ?? original.birth.time,
                place: body.birth_place_id
                  ? fixture(`place.${body.birth_place_id}.${lang}`)
                  : original.birth.place,
              };
              const changed =
                method === "post" ||
                birthKey(birth) !== birthKey(original.birth);
              const hash = createHash("sha256")
                .update(birthKey(birth))
                .digest("hex");
              const exact = seedProfiles.findIndex(
                (x: any) => birthKey(x.birth) === birthKey(birth),
              );
              const selected = changed
                ? exact >= 0
                  ? exact
                  : parseInt(hash.slice(0, 2), 16) % 3
                : Number(idx);
              const seed = seedProfiles[selected];
              if (changed) {
                for (const [key, report] of reports)
                  if (report.profile_id === p.id) reports.delete(key);
                const [year, month, day] = birth.date.split("-").map(Number);
                const [hour, minute] = birth.time.split(":").map(Number);
                birth.tz = birth.place.tz;
                birth.utc = new TZDate(
                  year,
                  month - 1,
                  day,
                  hour,
                  minute,
                  birth.tz,
                ).toISOString();
                birth.utc = new Date(birth.utc).toISOString();
              }
              let currentPlace = original.current_place;
              if (Object.hasOwn(body, "current_place_id")) {
                currentPlace =
                  body.current_place_id === null
                    ? null
                    : fixture(`place.${body.current_place_id}.${lang}`);
                if (body.current_place_id && !currentPlace)
                  return fail(reply, "validation_error", 400, lang);
              }
              result = localizedProfile(
                {
                  ...original,
                  profile_id:
                    method === "post" ? randomUUID() : profile.profile_id,
                  label: body.label ?? original.label,
                  relation: body.relation ?? original.relation,
                  is_self: (body.relation ?? original.relation) === "self",
                  gender: Object.hasOwn(body, "gender")
                    ? body.gender
                    : original.gender,
                  current_place: currentPlace,
                  birth,
                  big_three: seed.big_three,
                  chart_key: changed
                    ? exact >= 0
                      ? seed.chart_key
                      : hash.slice(0, 16)
                    : original.chart_key,
                  created_at:
                    method === "post"
                      ? new Date(clock()).toISOString()
                      : original.created_at,
                  updated_at: new Date(clock()).toISOString(),
                },
                lang,
              );
              if (method === "post") profiles.push(result);
              else
                profiles = profiles.map((x) =>
                  x.profile_id === result.profile_id ? result : x,
                );
              source.set(result.profile_id, selected);
              if (result.is_self) {
                me.self_profile_id = result.profile_id;
                result.natal_reading_job = jobs.resource(
                  `natal:${result.profile_id}:${result.chart_key}:${lang}`,
                  "natal_reading",
                  fixture(`natal.${selected}.${lang}`) ? scenario : "fail",
                  false,
                );
              }
              break;
            }
            case "delete /profiles/{id}":
              if (profile.is_self) return fail(reply, "conflict", 409, lang);
              profiles = profiles.filter((x) => x.profile_id !== p.id);
              for (const [key, report] of reports)
                if (report.profile_id === p.id) reports.delete(key);
              return noContent();
            case "get /profiles/{id}/chart":
              result = {
                ...fixture(`chart.${idx}`),
                profile_id: profile.profile_id,
                chart_key: profile.chart_key,
                utc: profile.birth.utc,
                tz: profile.birth.tz,
              };
              break;
            case "get /profiles/{id}/natal-reading":
              result = fixture(`natal.${idx}.${lang}`);
              if (!result) return fixtureOnly();
              result = {
                ...result,
                profile_id: profile.profile_id,
                chart_key: profile.chart_key,
              };
              break;
            case "get /home":
              if (
                profiles.find((x) => x.is_self)?.chart_key !==
                seedProfiles[0].chart_key
              )
                return fixtureOnly();
              result = fixture(`home.${lang}`);
              if (q.variant === "not_generated")
                result.today = {
                  status: "absent",
                  absence: { reason: "not_generated" },
                };
              result.greeting_name = me.display_name;
              break;
            case "get /profiles/{id}/forecast/day":
              if (!originalSelf) return fixtureOnly();
              result = fixture(
                q.date && q.date !== "2026-09-29"
                  ? `forecast-day.${q.date}.${lang}`
                  : `forecast-day.${lang}`,
              );
              if (!result) return fail(reply, "out_of_range", 400, lang);
              result.lens = q.lens ?? "general";
              if (result.lens !== "general")
                result.reading = {
                  status: "absent",
                  absence: { reason: "no_grounding" },
                };
              break;
            case "get /profiles/{id}/forecast/month":
              if (!originalSelf) return fixtureOnly();
              result = fixture(`forecast-month.${q.month}.${lang}`);
              if (!result) return fail(reply, "out_of_range", 400, lang);
              result.lens = q.lens ?? "general";
              break;
            case "get /profiles/{id}/forecast/year":
              if (
                !originalSelf ||
                q.from !== "2026-09" ||
                (q.lens && q.lens !== "general")
              )
                return fixtureOnly();
              result = fixture(`forecast-year.${lang}`);
              break;
            case "get /profiles/{id}/calendar/months/{month}":
              if (!originalSelf) return fixtureOnly();
              result = fixture(`month.${p.month}.${lang}`);
              if (!result) return fail(reply, "out_of_range", 400, lang);
              break;
            case "get /profiles/{id}/calendar/days/{date}":
              if (!originalSelf) return fixtureOnly();
              result = fixture(`day.${p.date}.${lang}`);
              if (!result) return fail(reply, "out_of_range", 400, lang);
              if (scenario === "empty_day")
                result = {
                  ...result,
                  events: [],
                  active_periods: [],
                  transits: [],
                  best_activities: [],
                  day_note: null,
                };
              break;
            case "get /profiles/{id}/calendar/items/{item_id}":
              if (!originalSelf) return fixtureOnly();
              result = fixture(
                `item.${encodeURIComponent(p.item_id!)}.${lang}`,
              );
              if (!result) return fail(reply, "not_found", 404, lang);
              break;
            case "get /profiles/{id}/calendar/periods":
              if (!originalSelf) return fixtureOnly();
              result = collection("period.", lang).filter(
                (x) =>
                  (!q.goal || x.goal === q.goal) &&
                  (!q.from || x.end >= q.from) &&
                  (!q.to || x.start <= q.to),
              );
              break;
            case "get /profiles/{id}/calendar/year":
              if (!originalSelf) return fixtureOnly();
              result = fixture(`calendar-year.${lang}`);
              break;
            case "get /profiles/{id}/best-days":
              if (!originalSelf) return fixtureOnly();
              result = fixture(`best-days.${lang}`);
              break;
            case "get /profiles/{id}/best-days/{activity}/{date}":
              if (!originalSelf) return fixtureOnly();
              result = fixture(`best.${p.activity}.${p.date}.${lang}`);
              if (!result) return fail(reply, "out_of_range", 400, lang);
              break;
            case "get /profiles/{id}/notification-candidates":
              if (!originalSelf) return fixtureOnly();
              result = collection("notification.", lang).filter(
                (x) =>
                  (!q.from || x.trigger_date >= q.from) &&
                  (!q.to || x.trigger_date <= q.to),
              );
              break;
            case "get /profiles/{id}/acg/places/{place_id}":
              if (!originalSelf) return fixtureOnly();
              result = fixture(
                `place-report.${p.place_id === "gn-istanbul" ? "gn-745044" : p.place_id}.${lang}`,
              );
              if (!result) return fixtureOnly();
              if (scenario === "absent_polar")
                result.relocation = {
                  status: "absent",
                  absence: { reason: "placidus_undefined_high_latitude" },
                };
              break;
            case "get /profiles/{id}/acg/countries/{iso2}":
            case "get /profiles/{id}/acg/regions/{admin1_id}":
              if (!originalSelf) return fixtureOnly();
              result = fixture(`area-report.${p.iso2 ?? p.admin1_id}.${lang}`);
              if (!result) return fixtureOnly();
              break;
            case "get /profiles/{id}/acg/heat/{goal}":
              if (!originalSelf) return fixtureOnly();
              result = fixture(`heat.${p.goal}`);
              if (!result) return fail(reply, "not_found", 404, lang);
              break;
            case "get /profiles/{id}/acg/lines":
              if (!originalSelf) return fixtureOnly();
              result = fixture("acg-lines");
              break;
            case "get /geo/countries.geojson":
              result = fixture("geo-countries-simple");
              break;
            case "get /geo/regions/{iso2}.geojson":
              result = fixture(`geo-regions.${p.iso2}`);
              if (!result) return fail(reply, "not_found", 404, lang);
              break;
            case "get /profiles/{id}/acg/lines/{body}/{angle}/places":
              if (!originalSelf) return fixtureOnly();
              result = fixture(`line-places.${p.body}.${p.angle}.${lang}`);
              if (!result) return fail(reply, "not_found", 404, lang);
              result.places = result.places.slice(
                0,
                Math.min(Number(q.limit ?? 20), 50),
              );
              break;
            case "post /profiles/{id}/acg/recommendations": {
              if (!originalSelf) return fixtureOnly();
              result = fixture(`recommend-${body.goal ?? "love"}.${lang}`);
              if (!result) return fixtureOnly();
              if (
                scenario === "needs_goal" ||
                (!body.goal && body.query_text)
              ) {
                const cat = fixture(`catalogue.${lang}`);
                result = {
                  ...result,
                  status: "needs_goal",
                  goal: null,
                  goal_label: null,
                  goal_options: Object.entries(cat.goals).map(
                    ([goal, label]) => ({ goal, label }),
                  ),
                  by_line: [],
                  places: [],
                  turkey: { places: [], regions: [] },
                  countries: [],
                  regions: [],
                  explanations: {
                    status: "absent",
                    absence: { reason: "no_grounding" },
                  },
                };
              } else {
                if ((body.scope && body.scope !== "world") || body.filters)
                  return fixtureOnly();
                if (scenario === "thin_result") {
                  result.status = "thin_result";
                  result.places = result.places.slice(0, 1);
                  result.by_line = result.by_line.slice(0, 1);
                  result.countries = [];
                  result.regions = [];
                }
              }
              break;
            }
            case "get /reports":
              result = page(
                [...reports.values()]
                  .filter(
                    (report) =>
                      report.lang === lang &&
                      (!q.type || report.type === q.type),
                  )
                  .sort((a, b) => b.created_at.localeCompare(a.created_at))
                  .map(({ lang: _lang, ...report }) => report),
                q,
              );
              break;
            case "delete /reports/{report_id}": {
              const entry = [...reports].find(
                ([, report]) => report.report_id === p.report_id,
              );
              if (!entry) return fail(reply, "not_found", 404, lang);
              reports.delete(entry[0]);
              return noContent();
            }
            case "post /compatibility": {
              const a = profiles.find(
                (x) => x.profile_id === body.profile_a_id,
              );
              const b = profiles.find(
                (x) => x.profile_id === body.profile_b_id,
              );
              if (!a || !b) return fail(reply, "not_found", 404, lang);
              if (a.profile_id === b.profile_id)
                return fail(reply, "validation_error", 400, lang);
              const pair = [a.chart_key, b.chart_key].sort().join(":");
              if (
                body.type !== "love" ||
                pair !==
                  [seedProfiles[0].chart_key, seedProfiles[1].chart_key]
                    .sort()
                    .join(":")
              )
                return fixtureOnly();
              const prior = [...compat.values()].find(
                (x) =>
                  x.people.a.profile_id === a.profile_id &&
                  x.people.b.profile_id === b.profile_id &&
                  x.type === body.type,
              );
              result = {
                ...fixture(`compat-love.${lang}`),
                compatibility_id: prior?.compatibility_id ?? randomUUID(),
                created_at:
                  prior?.created_at ?? new Date(clock()).toISOString(),
                people: {
                  a: {
                    profile_id: a.profile_id,
                    label: a.label,
                    big_three: a.big_three,
                  },
                  b: {
                    profile_id: b.profile_id,
                    label: b.label,
                    big_three: b.big_three,
                  },
                },
              };
              compat.set(result.compatibility_id, structuredClone(result));
              break;
            }
            case "get /compatibility/{id}": {
              const saved = compat.get(p.id!);
              if (!saved) return fail(reply, "not_found", 404, lang);
              result = {
                ...saved,
                reading: fixture(`compat-love.${lang}`).reading,
              };
              break;
            }
            case "get /compatibility":
              result = page(
                [...compat.values()].map(
                  ({
                    reading,
                    score: _score,
                    family_relation: _family,
                    ...r
                  }) => ({ ...r, status: reading.status }),
                ),
                q,
              );
              break;
            case "delete /compatibility/{id}":
              if (!compat.delete(p.id!))
                return fail(reply, "not_found", 404, lang);
              return noContent();
            case "get /jobs/{job_id}":
              result = jobs.get(p.job_id!);
              if (!result) return fail(reply, "not_found", 404, lang);
              break;
            case "post /ask/threads":
              if (!profiles.some((x) => x.profile_id === body.profile_id))
                return fail(reply, "not_found", 404, lang);
              result = {
                thread_id: randomUUID(),
                profile_id: body.profile_id,
                title: "",
                created_at: new Date(clock()).toISOString(),
                updated_at: new Date(clock()).toISOString(),
                messages: [],
              };
              threads.set(result.thread_id, result);
              break;
            case "get /ask/threads":
              result = page(
                [...threads.values()].map(({ messages, ...t }) => t).reverse(),
                q,
              );
              break;
            case "get /ask/threads/{id}":
              result = threads.get(p.id!);
              if (!result) return fail(reply, "not_found", 404, lang);
              break;
            case "delete /ask/threads/{id}":
              if (!threads.delete(p.id!))
                return fail(reply, "not_found", 404, lang);
              return noContent();
            case "post /ask/threads/{id}/messages": {
              const thread = threads.get(p.id!);
              if (!thread) return fail(reply, "not_found", 404, lang);
              if (!profiles.some((x) => x.profile_id === thread.profile_id))
                return fail(reply, "conflict", 409, lang);
              if (
                !body.text.trim() ||
                body.text.length > 1000 ||
                Object.keys(body).some(
                  (k) => !["text", "context"].includes(k),
                ) ||
                Object.keys(body.context ?? {}).some(
                  (k) =>
                    ![
                      "date",
                      "month",
                      "place_id",
                      "other_profile_id",
                      "compatibility_id",
                      "item_id",
                      "activity",
                      "section_key",
                    ].includes(k),
                )
              )
                return fail(reply, "validation_error", 400, lang);
              if (me.ask_quota.used_today >= me.ask_quota.limit_per_day) {
                reply.header("Retry-After", "3600");
                return fail(reply, "rate_limited", 429, lang);
              }
              if (
                thread.profile_id !== selfId ||
                profiles.find((x) => x.is_self)?.chart_key !==
                  seedProfiles[0].chart_key
              )
                return fixtureOnly();
              const sample = askFixture(
                body.text,
                body.context ?? {},
                lang as "tr" | "en",
                thread.profile_id,
              );
              if (
                body.context?.other_profile_id === seedProfiles[1].profile_id ||
                body.context?.compatibility_id
              ) {
                const existing = body.context?.compatibility_id
                  ? compat.get(body.context.compatibility_id)
                  : [...compat.values()].find((c) => c.type === "love");
                const report = existing ?? {
                  ...fixture(`compat-love.${lang}`),
                  compatibility_id: randomUUID(),
                };
                compat.set(report.compatibility_id, report);
                sample.text =
                  (lang === "tr"
                    ? "Önizleme: kayıtlı uyum yorumundan bir bölüm.\n\n"
                    : "Preview: an excerpt from the saved compatibility reading.\n\n") +
                  fixture(`compat-love.${lang}`).reading.sections[0].text;
                sample.card = {
                  type: "compatibility",
                  compatibility_id: report.compatibility_id,
                  labels: [report.people.a.label, report.people.b.label],
                  compat_type: "love",
                };
                sample.route = `/match/${report.compatibility_id}`;
              }
              const text = sample.text;
              reply.hijack();
              reply.raw.writeHead(200, {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "X-Mock-Today": "2026-09-29",
              });
              const send = (event: string, data: any) =>
                reply.raw.write(
                  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`,
                );
              const user: Message = {
                message_id: randomUUID(),
                role: "user",
                text: body.text,
                cards: [],
                links: [],
                status: "complete",
                created_at: new Date(clock()).toISOString(),
              };
              const answer: Message = {
                ...user,
                message_id: randomUUID(),
                role: "assistant",
                text: "",
                status: "interrupted",
              };
              thread.messages ??= [];
              thread.messages.push(user, answer);
              thread.title ||= body.text;
              thread.updated_at = new Date(clock()).toISOString();
              send("status", {
                phase: "computing",
                sources: [
                  {
                    kind: "forecast",
                    label: lang === "tr" ? "Günlük öngörü" : "Daily forecast",
                  },
                ],
              });
              if (scenario === "slow")
                await new Promise((resolve) => setTimeout(resolve, 8000));
              if (scenario === "fail") {
                answer.status = "failed";
                send("error", problem("generation_failed", 503, lang));
                reply.raw.end();
                return;
              }
              for (const chunk of text.match(/.{1,28}/gs) ?? []) {
                if (reply.raw.destroyed) return;
                answer.text += chunk;
                send("delta", { text: chunk });
                await new Promise((resolve) => setTimeout(resolve, 25));
              }
              if (sample.card) {
                answer.cards.push(sample.card);
                send("card", sample.card);
                const link = {
                  label: lang === "tr" ? "Aç" : "Open",
                  route: sample.route,
                };
                answer.links.push(link);
                send("link", link);
              }
              answer.status = "complete";
              me.ask_quota.used_today++;
              send("done", {
                message_id: answer.message_id,
                quota: {
                  used_today: me.ask_quota.used_today,
                  limit_per_day: me.ask_quota.limit_per_day,
                },
              });
              reply.raw.end();
              return;
            }
            case "post /ask/messages/{message_id}/feedback": {
              const msg = [...threads.values()]
                .flatMap((t) => t.messages ?? [])
                .find((m) => m.message_id === p.message_id);
              if (!msg) return fail(reply, "not_found", 404, lang);
              msg.feedback = body.rating;
              return noContent();
            }
            default:
              return fixtureOnly();
          }
          if (operation.responses["202"]?.content) {
            const job = jobs.resource(
              route.endsWith("natal-reading")
                ? `natal:${p.id}:${profile?.chart_key}:${lang}`
                : `${route}:${p.id}:${lang}:${profile?.chart_key}`,
              route.endsWith("elements") ? "element_notes" : "natal_reading",
              scenario,
              q.retry === "true",
            );
            if (job.status === "failed")
              return fail(reply, "generation_failed", 503, lang);
            if (job.status !== "succeeded") {
              reply.header("Retry-After", "1");
              return reply.code(202).send(validate("JobAccepted", { job }));
            }
            if (route.endsWith("natal-reading")) {
              const key = `${profile.profile_id}:${profile.chart_key}:${lang}`;
              if (!reports.has(key))
                reports.set(key, {
                  report_id: randomUUID(),
                  type: "natal",
                  lang,
                  title: result.title,
                  subtitle: profile.label,
                  profile_id: profile.profile_id,
                  created_at: new Date(clock()).toISOString(),
                  route: `/chart/reading?profile=${encodeURIComponent(profile.profile_id)}`,
                });
            }
          } else if (
            result &&
            typeof result === "object" &&
            !Array.isArray(result)
          ) {
            for (const key of [
              "reading",
              "today",
              "text",
              "day_note",
              "overview",
              "explanations",
            ])
              if (result[key]?.status === "ready") {
                const kind: Job["kind"] =
                  route === "/home" || route.endsWith("forecast/day")
                    ? "day_reading"
                    : route.includes("/compatibility")
                      ? "compatibility"
                      : route.endsWith("forecast/month")
                        ? "month_reading"
                        : route.endsWith("forecast/year")
                          ? "year_reading"
                          : route.endsWith("recommendations")
                            ? "recommendation"
                            : route.includes("/acg/")
                              ? "place_reading"
                              : "calendar_text";
                const job = jobs.resource(
                  `${route}:${JSON.stringify(p)}:${JSON.stringify(
                    Object.fromEntries(
                      Object.entries(q)
                        .filter(([k]) => k !== "retry")
                        .sort(),
                    ),
                  )}:${profile?.chart_key}:${lang}:${key}:${method === "post" ? JSON.stringify(body) : ""}`,
                  kind,
                  scenario,
                  q.retry === "true",
                );
                if (job.status !== "succeeded")
                  result[key] =
                    job.status === "failed"
                      ? { status: "failed", error: job.error }
                      : { status: "pending", job };
              }
          }
          if (result?.cards && result?.reading?.status !== "ready")
            result.cards = result.cards.map((card: any) => ({
              ...card,
              text: card.band === "no_emphasis" ? card.text : null,
            }));
          // History records only completed interpretations, never pending or absent parts.
          const ready =
            result?.reading?.status === "ready" ||
            result?.explanations?.status === "ready" ||
            result?.overview?.status === "ready";
          if (ready) {
            let type: ReportRef["type"] | undefined,
              target = "",
              title = "";
            if (route.includes("/compatibility") && result.compatibility_id) {
              type = "compatibility";
              target = `/match/${result.compatibility_id}`;
              title = result.reading.title;
            } else if (route.endsWith("forecast/year")) {
              type = "forecast_year";
              target = `/forecast/year?profile=${p.id}&month=${q.from}`;
              title = `${result.from} – ${result.to}`;
            } else if (route.endsWith("forecast/month")) {
              type = "forecast_month";
              target = `/forecast/month/${q.month}?profile=${p.id}`;
              title = result.month;
            } else if (
              route.endsWith("recommendations") &&
              result.status !== "needs_goal"
            ) {
              type = "recommendation";
              target = `/map/recommend/result?profile=${p.id}&request=${encodeURIComponent(JSON.stringify(body))}`;
              title = result.goal_label;
            } else if (route.includes("/acg/places/")) {
              type = "place";
              target = `/map/place/${p.place_id}?profile=${p.id}`;
              title = result.place.name;
            }
            if (type) {
              const key = `${type}:${target}:${lang}`;
              if (!reports.has(key))
                reports.set(key, {
                  report_id: randomUUID(),
                  type,
                  lang,
                  title,
                  subtitle:
                    profile?.label ??
                    Object.values(result.people ?? {})
                      .map((p: any) => p.label)
                      .join(" · "),
                  profile_id:
                    profile?.profile_id ?? result.people?.a.profile_id,
                  created_at: new Date(clock()).toISOString(),
                  route: target,
                });
            }
          }
          const responseSchema =
            operation.responses[String(status)]?.content?.["application/json"]
              ?.schema;
          if (responseSchema?.$ref)
            validate(
              decodeURIComponent(responseSchema.$ref.split("/").at(-1)),
              result,
            );
          if (responseSchema?.items?.$ref)
            for (const value of result)
              validate(
                decodeURIComponent(responseSchema.items.$ref.split("/").at(-1)),
                value,
              );
          const etag =
            '"' +
            createHash("sha256").update(JSON.stringify(result)).digest("hex") +
            '"';
          reply.header("ETag", etag);
          if (method === "get" && request.headers["if-none-match"] === etag)
            return reply.code(304).send();
          if (idem)
            idempotency.set(idem, {
              body: JSON.stringify(body),
              value: structuredClone(result),
              status,
              expires: clock() + 86400000,
            });
          return reply.code(status).send(result);
        },
      });
    }
  }
  return app;
}
