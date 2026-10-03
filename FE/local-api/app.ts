import { CompatibilityJobs } from "./compatibility-jobs";
import { ForecastJobs, forecastContext } from "./forecast-jobs";
import { dayForecast, monthForecast, yearForecast } from "./forecast";
import { computeCalendar } from "./calendar";
import Fastify from "fastify";
import { randomBytes, randomUUID, createHash } from "node:crypto";
import { ReadingJobs } from "./reading-jobs";
import { Store } from "./store";
import { bridge, computeBirthChart } from "./engine";
import { fixture } from "../mock-api/fixtures";
import { endpoints } from "../scripts/endpoints";
import { validate } from "../src/api/zod";
import type { BirthProfile, Me } from "../contracts/spec-types";
const digest = (s: string) => createHash("sha256").update(s).digest("hex");
const issue = (status: number, message = "Request unavailable") =>
  Object.assign(new Error(message), { statusCode: status });
export function buildLocalApp({
  dbPath,
  allowPaid = false,
  generateCompatibility,
}: {
  dbPath: string;
  allowPaid?: boolean;
  generateCompatibility?: (data: unknown) => Promise<any>;
}) {
  const app = Fastify({ logger: false, bodyLimit: 65536 });
  const store = new Store(dbPath);
  const readings = new ReadingJobs(store, undefined, allowPaid);
  const forecasts = new ForecastJobs(store, allowPaid);
  const compatibility = new CompatibilityJobs(
    store,
    allowPaid,
    generateCompatibility,
  );
  const now = () => new Date().toISOString();
  if (!store.get("me")) {
    const me: Me = {
      ...fixture("me.en"),
      user_id: randomUUID(),
      display_name: "",
      self_profile_id: null,
      current_place: null,
      consents: { birth_data: null, marketing: false },
      created_at: now(),
      ask_quota: { limit_per_day: 0, used_today: 0, resets_at: now() },
    };
    store.put("me", me);
  }
  // Serialize handlers so profile edits/idempotency checks cannot interleave across an await.
  let tail = Promise.resolve();
  app.addHook("onClose", async () => {
    await tail;
    await readings.close();
    await forecasts.close();
    await compatibility.close();
    store.close();
  });
  app.setErrorHandler((error: any, _request, reply) => {
    const status = error.statusCode ?? 500;
    reply
      .code(status)
      .type("application/problem+json")
      .send({
        type: "about:blank",
        title: "Unable to complete request",
        status,
        code:
          (
            {
              400: "validation_error",
              401: "unauthorized",
              404: "not_found",
              409: "conflict",
              503: "upstream_unavailable",
            } as any
          )[status] ?? "internal",
      });
  });
  const session = () => {
    const access = randomBytes(32).toString("hex"),
      refresh = randomBytes(32).toString("hex");
    const expires = Date.now() + 3600000;
    store.put("access:" + digest(access), { expires });
    store.put("refresh:" + digest(refresh), {
      expires: Date.now() + 30 * 86400000,
      accessHash: digest(access),
    });
    const me = store.get<Me>("me")!;
    return {
      access_token: access,
      refresh_token: refresh,
      access_expires_at: new Date(expires).toISOString(),
      is_new_user: !me.self_profile_id,
      me,
    };
  };
  const calendarContext = (profile: BirthProfile) => {
    const me = store.get<Me>("me")!;
    const current =
      (profile.is_self ? me.current_place : profile.current_place) ??
      profile.birth.place;
    const start = new Intl.DateTimeFormat("en-CA", {
      timeZone: current.tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(new Date());
    return {
      current,
      start,
      prefix: `calendar:${profile.profile_id}:${profile.chart_key}:${current.lat}:${current.lon}:`,
    };
  };
  const validDate = (date: string) => {
    if (
      !/^20\d{2}-\d{2}-\d{2}$/.test(date) ||
      !Number.isFinite(Date.parse(date)) ||
      new Date(date).toISOString().slice(0, 10) !== date
    )
      throw issue(400);
    return date;
  };
  const calendarFor = async (
    profile: BirthProfile,
    lang: string,
    requestedStart?: string,
  ) => {
    const context = calendarContext(profile);
    const start = requestedStart ? validDate(requestedStart) : context.start;
    const current = context.current;
    const key = context.prefix + start;
    let saved = store.get(key);
    if (!saved) {
      saved = await computeCalendar(profile, current, start);
      store.put(key, saved);
    }
    return saved[lang];
  };
  const place = async (id: string, lang: string) => {
    const key = `place:${lang}:${id}`;
    let value = store.get(key);
    if (!value) {
      value = (await bridge({ action: "places", id, lang }))[0];
      if (!value) throw issue(400);
      store.put(key, value);
    }
    const {
      kind: _kind,
      population: _population,
      source: _source,
      ...result
    } = value;
    return result;
  };
  for (const endpoint of endpoints) {
    app.route({
      method: endpoint.method.toUpperCase() as any,
      url: "/v1" + endpoint.path.replace(/\{([^}]+)\}/g, ":$1"),
      handler: async (request, reply) => {
        let unlock!: () => void;
        const prior = tail;
        tail = new Promise<void>((resolve) => {
          unlock = resolve;
        });
        await prior;
        try {
          const q = request.query as Record<string, string>,
            p = request.params as Record<string, string>;
          const lang = q.lang ?? store.get<Me>("me")!.language;
          if (!["en", "tr"].includes(lang)) throw issue(400);
          if (!/^\/(auth|meta|geo)\//.test(endpoint.path)) {
            const token = String(request.headers.authorization ?? "").replace(
              /^Bearer /,
              "",
            );
            if (
              (store.get("access:" + digest(token))?.expires ?? 0) <= Date.now()
            )
              throw issue(401);
          }
          let body: any = request.body ?? {};
          if (endpoint.body) {
            try {
              body = validate(endpoint.body, body);
            } catch {
              throw issue(400);
            }
          }
          const idempotency = request.headers["idempotency-key"];
          const cacheKey =
            idempotency && endpoint.method !== "get"
              ? `idem:${endpoint.method}:${request.url}:${String(idempotency)}`
              : null;
          if (cacheKey) {
            const saved = store.get(cacheKey);
            if (saved && saved.expires > Date.now()) {
              if (saved.body !== JSON.stringify(body)) throw issue(409);
              if (
                endpoint.path === "/compatibility" &&
                endpoint.method === "post"
              )
                return reply
                  .code(saved.status)
                  .send(
                    compatibility.get(
                      saved.result.compatibility_id,
                      lang as "en" | "tr",
                    ),
                  );
              return reply.code(saved.status).send(saved.result);
            }
          }
          const me = store.get<Me>("me")!;
          const profile = p.id
            ? store.get<BirthProfile>("profile:" + p.id)
            : undefined;
          if (endpoint.path.startsWith("/profiles/{id}") && !profile)
            throw issue(404);
          let result: any;
          switch (`${endpoint.method} ${endpoint.path}`) {
            case "get /meta/config":
              result = fixture("config");
              result.flags.askAstrology = false;
              result.flags.familyCompatibility = false;
              break;
            case "get /meta/catalogue":
              result = fixture(`catalogue.${lang}`);
              break;
            // Private emulator access only. This deliberately does not claim email delivery or OAuth.
            case "post /auth/email/start":
              if (body.email !== "demo@example.com") throw issue(503);
              return reply.code(204).send();
            case "post /auth/email/verify":
              if (body.email !== "demo@example.com" || body.code !== "000000")
                throw issue(401);
              result = session();
              break;
            case "post /auth/refresh": {
              const key = "refresh:" + digest(body.refresh_token),
                saved = store.get(key);
              if (!saved || saved.expires <= Date.now()) throw issue(401);
              result = store.transaction(() => {
                store.remove(key);
                store.remove("access:" + saved.accessHash);
                return session();
              });
              break;
            }
            case "post /auth/logout": {
              const key = "refresh:" + digest(body.refresh_token),
                saved = store.get(key);
              if (saved) {
                store.remove("access:" + saved.accessHash);
                store.remove(key);
              }
              return reply.code(204).send();
            }
            case "get /me":
              result = me;
              break;
            case "patch /me": {
              const { current_place_id } = body;
              const updates = Object.fromEntries(
                [
                  "display_name",
                  "language",
                  "theme",
                  "notification_prefs",
                  "consents",
                ]
                  .filter((k) => Object.hasOwn(body, k))
                  .map((k) => [k, body[k]]),
              );
              result = {
                ...me,
                ...updates,
                ...(current_place_id !== undefined
                  ? {
                      current_place:
                        current_place_id === null
                          ? null
                          : await place(current_place_id, lang),
                    }
                  : {}),
              };
              validate("Me", result);
              store.put("me", result);
              break;
            }
            case "get /places/search":
              if (q.kind === "area") throw issue(503);
              result = await bridge({
                action: "places",
                query: (q.q ?? "").slice(0, 100),
                lang,
              });
              for (const candidate of result)
                store.put(`place:${lang}:${candidate.place_id}`, candidate);
              break;
            case "get /places/{place_id}":
              result = await place(p.place_id!, lang);
              break;
            case "get /places/reverse":
              result = null;
              break;
            case "get /profiles":
              result = store.list<BirthProfile>("profile:");
              break;
            case "get /profiles/{id}":
              result = profile;
              break;
            case "post /profiles":
            case "patch /profiles/{id}": {
              const label = (body.label ?? profile?.label ?? "").trim();
              const date = body.birth_date ?? profile?.birth.date,
                time = body.birth_time ?? profile?.birth.time;
              if (
                !label ||
                label.length > 40 ||
                !/^\d{4}-\d{2}-\d{2}$/.test(date ?? "") ||
                date < "1900-01-01" ||
                date > now().slice(0, 10) ||
                !/^([01]\d|2[0-3]):[0-5]\d$/.test(time ?? "")
              )
                throw issue(400);
              const relation = body.relation ?? profile?.relation;
              if (
                (relation === "self" &&
                  me.self_profile_id &&
                  me.self_profile_id !== p.id) ||
                (profile?.is_self && relation !== "self")
              )
                throw issue(409);
              if (!profile && store.list("profile:").length >= 50)
                throw issue(409);
              const birthPlace = body.birth_place_id
                ? await place(body.birth_place_id, lang)
                : profile!.birth.place;
              const current =
                body.current_place_id !== undefined
                  ? body.current_place_id === null
                    ? null
                    : await place(body.current_place_id, lang)
                  : (profile?.current_place ?? null);
              const id = profile?.profile_id ?? randomUUID();
              const computed = await computeBirthChart(
                { date, time, place: birthPlace },
                id,
              );
              const chart = computed.chart;
              result = {
                profile_id: id,
                chart_key: chart.chart_key,
                label,
                relation,
                is_self: relation === "self",
                gender:
                  body.gender !== undefined
                    ? body.gender
                    : (profile?.gender ?? null),
                birth: {
                  date,
                  time,
                  place: { ...birthPlace, tz: chart.tz },
                  tz: chart.tz,
                  utc: chart.utc,
                },
                current_place: current,
                big_three: {
                  sun: chart.points.find((x) => x.body === "sun")!.sign,
                  moon: chart.points.find((x) => x.body === "moon")!.sign,
                  ascendant: chart.axes.asc.sign,
                },
                created_at: profile?.created_at ?? now(),
                updated_at: now(),
              };
              validate("BirthProfile", result);
              store.transaction(() => {
                store.put("profile:" + id, result);
                store.put("chart:" + id, chart);
                store.put("raw:" + id, computed.raw);
                if (profile && profile.chart_key !== chart.chart_key)
                  for (const language of ["tr", "en"])
                    store.remove(`report:${id}:${language}`);
                if (result.is_self)
                  store.put("me", { ...me, self_profile_id: id });
                if (cacheKey)
                  store.put(cacheKey, {
                    body: JSON.stringify(body),
                    status: endpoint.status ?? 200,
                    result,
                    expires: Date.now() + 86400000,
                  });
              });
              break;
            }
            case "delete /profiles/{id}":
              if (profile!.is_self) throw issue(409);
              store.transaction(() => {
                for (const prefix of ["profile:", "chart:", "raw:"])
                  store.remove(prefix + p.id);
                for (const language of ["tr", "en"])
                  store.remove(`report:${p.id}:${language}`);
              });
              return reply.code(204).send();
            case "get /profiles/{id}/chart":
              result = store.get("chart:" + p.id);
              break;
            case "get /profiles/{id}/forecast/day":
            case "get /profiles/{id}/forecast/month":
            case "get /profiles/{id}/forecast/year": {
              if (
                q.lens &&
                !["general", "personal", "professional"].includes(q.lens)
              )
                throw issue(400);
              const date = endpoint.path.endsWith("/day")
                ? validDate(q.date ?? calendarContext(profile!).start)
                : validDate(
                    `${(endpoint.path.endsWith("/year") ? q.from : q.month) ?? calendarContext(profile!).start.slice(0, 7)}-01`,
                  );
              const month = date.slice(0, 7);
              const cal = await calendarFor(profile!, lang, month + "-01");
              result = endpoint.path.endsWith("/day")
                ? dayForecast(
                    cal,
                    fixture(`catalogue.${lang}`),
                    profile!.profile_id,
                    date,
                    q.lens,
                  )
                : endpoint.path.endsWith("/month")
                  ? monthForecast(cal, profile!.profile_id, month, q.lens)
                  : yearForecast(
                      cal,
                      profile!.profile_id,
                      month,
                      lang as "en" | "tr",
                      q.lens as
                        "general" | "personal" | "professional" | undefined,
                    );
              if (!result) throw issue(400);
              const horizon = endpoint.path.endsWith("/day")
                ? "day"
                : endpoint.path.endsWith("/month")
                  ? "month"
                  : "year";
              result.reading = forecasts.get(
                forecastContext(
                  profile!,
                  calendarContext(profile!).current,
                  date,
                  horizon,
                  (q.lens ?? "general") as
                    "general" | "personal" | "professional",
                ),
                lang as "en" | "tr",
                q.retry === "true",
              );
              break;
            }
            case "get /profiles/{id}/calendar/months/{month}":
              result = (
                await calendarFor(profile!, lang, validDate(`${p.month}-01`))
              ).months[p.month!];
              if (!result) throw issue(400);
              break;
            case "get /profiles/{id}/calendar/days/{date}":
              result = (
                await calendarFor(
                  profile!,
                  lang,
                  validDate(p.date!).slice(0, 7) + "-01",
                )
              ).days[p.date!];
              if (!result) throw issue(400);
              break;
            case "get /profiles/{id}/calendar/items/{item_id}":
              result = store
                .list<any>(calendarContext(profile!).prefix)
                .map((snapshot) => snapshot[lang]?.items[p.item_id!])
                .find(Boolean);
              result ??= (await calendarFor(profile!, lang)).items[p.item_id!];
              if (!result) throw issue(404);
              break;
            case "get /profiles/{id}/calendar/year":
              result = (await calendarFor(profile!, lang)).year;
              break;
            case "get /profiles/{id}/calendar/periods":
              result = (await calendarFor(profile!, lang)).periods.filter(
                (x: any) =>
                  (!q.goal || x.goal === q.goal) &&
                  (!q.from || x.end >= q.from) &&
                  (!q.to || x.start <= q.to),
              );
              break;
            case "get /profiles/{id}/best-days":
              result = (await calendarFor(profile!, lang)).best;
              break;
            case "get /profiles/{id}/best-days/{activity}/{date}":
              result = (await calendarFor(profile!, lang)).bestDetails[
                `${p.activity}/${p.date}`
              ];
              if (!result) throw issue(400);
              break;
            case "get /profiles/{id}/notification-candidates":
              result = (await calendarFor(profile!, lang)).notifications.filter(
                (x: any) =>
                  (!q.from || x.trigger_date >= q.from) &&
                  (!q.to || x.trigger_date <= q.to),
              );
              break;
            case "get /profiles/{id}/natal-reading": {
              const value = readings.get(
                profile!,
                lang as "en" | "tr",
                q.retry === "true",
              );
              if (value.reading) {
                result = value.reading;
                break;
              }
              if (value.job?.status === "failed")
                return reply
                  .code(503)
                  .type("application/problem+json")
                  .send(value.job.error);
              return reply.code(202).send({ job: value.job });
            }
            case "get /jobs/{job_id}":
              result = store.get("job:" + p.job_id);
              if (!result) throw issue(404);
              break;
            case "get /reports": {
              const all = [
                ...store
                  .list<any>("report:")
                  .filter(
                    (r) =>
                      r.lang === lang && store.get("profile:" + r.profile_id),
                  ),
                ...forecasts.reports(lang as "en" | "tr"),
                ...compatibility.reports(lang as "en" | "tr"),
              ]
                .filter(
                  (r) =>
                    (!q.type || r.type === q.type) &&
                    !store.get("hidden-report:" + r.report_id),
                )
                .sort(
                  (a, b) =>
                    b.created_at.localeCompare(a.created_at) ||
                    a.report_id.localeCompare(b.report_id),
                );
              const start = Number(q.cursor ?? 0),
                count = Number(q.limit ?? 20);
              if (
                !Number.isInteger(start) ||
                start < 0 ||
                !Number.isInteger(count) ||
                count < 1 ||
                count > 50
              )
                throw issue(400);
              result = {
                items: all.slice(start, start + count),
                next_cursor:
                  start + count < all.length ? String(start + count) : null,
              };
              break;
            }
            case "delete /reports/{report_id}": {
              const reports = [
                ...store.list<any>("report:"),
                ...forecasts.reports("en"),
                ...forecasts.reports("tr"),
                ...compatibility.reports("en"),
                ...compatibility.reports("tr"),
              ];
              if (
                !reports.some((r) => r.report_id === p.report_id) ||
                store.get("hidden-report:" + p.report_id)
              )
                throw issue(404);
              store.put("hidden-report:" + p.report_id, true);
              return reply.code(204).send();
            }
            case "post /compatibility":
              result = compatibility.create(body, lang as "en" | "tr");
              if (cacheKey)
                store.put(cacheKey, {
                  body: JSON.stringify(body),
                  result,
                  status: 201,
                  expires: Date.now() + 86400000,
                });
              break;
            case "get /compatibility/{id}":
              result = compatibility.get(
                p.id!,
                lang as "en" | "tr",
                q.retry === "true",
              );
              break;
            case "delete /compatibility/{id}":
              compatibility.remove(p.id!);
              return reply.code(204).send();
            case "get /compatibility": {
              const items = compatibility.list();
              const offset = Math.max(0, Number(q.cursor) || 0),
                limit = Math.min(100, Math.max(1, Number(q.limit) || 20));
              result = {
                items: items.slice(offset, offset + limit),
                next_cursor:
                  offset + limit < items.length ? String(offset + limit) : null,
              };
              break;
            }
            case "get /ask/threads":
              result = { items: [], next_cursor: null };
              break;
            default:
              throw issue(503);
          }
          if (endpoint.response) {
            const array = endpoint.response.endsWith("[]"),
              schema = array
                ? endpoint.response.slice(0, -2)
                : endpoint.response;
            if (array) result.forEach((v: unknown) => validate(schema, v));
            else validate(schema, result);
          }
          return reply.code(endpoint.status ?? 200).send(result);
        } finally {
          unlock();
        }
      },
    });
  }
  return app;
}
