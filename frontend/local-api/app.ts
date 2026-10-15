import { registerGuestOnboarding } from "./guest-onboarding";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { runReadingBridge } from "./readings";
import {
  ProgressiveReadings,
  type SectionRunner,
} from "./progressive-readings";
import { AskService } from "./ask";
import type { AskRunner } from "./ask-bridge";
import { homeSummary } from "./home";
import { registerBrowserSignIn } from "./browser-auth-routes";
import type { SupabaseAuth, VerifiedSession } from "./supabase-auth";
import { MapJobs, mapContext } from "./map-jobs";
import { exportAccount, deleteAccount } from "./account";
import { LiveMap } from "./map";
import { CompatibilityJobs } from "./compatibility-jobs";
import { ForecastJobs, forecastContext } from "./forecast-jobs";
import { dayForecast, monthForecast, yearForecast } from "./forecast";
import { computeCalendar } from "./calendar";
import Fastify from "fastify";
import { randomBytes, randomUUID, createHash } from "node:crypto";
import { ReadingJobs } from "./reading-jobs";
import { Store, SYSTEM_TENANT } from "./store";
import { bridge, computeBirthChart as defaultBirthChart } from "./engine";
import { fixture } from "../mock-api/fixtures";
import { endpoints } from "../scripts/endpoints";
import { validate, schemas } from "../src/api/zod";
import type { BirthProfile, Me } from "../contracts/spec-types";
const digest = (s: string) => createHash("sha256").update(s).digest("hex");
const issue = (status: number, message = "Request unavailable") =>
  Object.assign(new Error(message), { statusCode: status });
export async function buildLocalApp({
  dbPath,
  allowPaid = false,
  progressiveReadings = false,
  guestOnboarding = false,
  sectionRunner,
  generateForecast,
  calculateCalendar = computeCalendar,
  generateCompatibility,
  computeBirthChart = defaultBirthChart,
  auth,
  askRunner,
  askReady,
}: {
  auth?: SupabaseAuth;
  askRunner?: AskRunner;
  askReady?: () => boolean;
  dbPath: string;
  allowPaid?: boolean;
  progressiveReadings?: boolean;
  guestOnboarding?: boolean;
  sectionRunner?: SectionRunner;
  calculateCalendar?: typeof computeCalendar;
  generateForecast?: (data: any) => Promise<any>;
  generateCompatibility?: (data: unknown) => Promise<any>;
  computeBirthChart?: typeof defaultBirthChart;
}) {
  const app = Fastify({ logger: false, bodyLimit: 65536 });
  const dataRoot =
    dbPath === ":memory:"
      ? path.join(path.dirname(fileURLToPath(import.meta.url)), "../.local-data")
      : path.dirname(dbPath);
  const store = await Store.open(
    process.env.DATABASE_URL
      ? { databaseUrl: process.env.DATABASE_URL }
      : dbPath,
  );
  const ask = new AskService(store, allowPaid, askRunner, askReady);
  const previousAuth = await store.runAsAsync(SYSTEM_TENANT, () =>
    store.get<string>("auth-mode"),
  );
  if (previousAuth && previousAuth !== auth?.scope) {
    await store.close();
    throw new Error(
      "Real authentication is required for this database; keep its original project and owner configuration",
    );
  }
  if (auth)
    await store.runAsAsync(SYSTEM_TENANT, () =>
      store.put("auth-mode", auth.scope),
    );
  const credential = (kind: string, token: string) =>
    (auth ? `supabase:${auth.scope}:` : "") + kind + ":" + digest(token);
  /** Legacy single-operator pin when ownerEmail is configured; multi-user skips this. */
  const bindOwner = async (id: string) => {
    if (!auth || auth.multiUser) return;
    await store.runAsAsync(SYSTEM_TENANT, async () => {
      const bound = await store.get<string>("auth-owner");
      if (bound && bound !== id) throw issue(403);
      await store.put("auth-owner", id);
    });
  };
  const maps = new LiveMap(store);
  const mapJobs = await MapJobs.create(store, allowPaid);
  const readings = await ReadingJobs.create(store, undefined, allowPaid);
  const progressive = await ProgressiveReadings.create(
    store,
    allowPaid && (progressiveReadings || guestOnboarding),
    sectionRunner ??
      ((data, onStage) =>
        runReadingBridge(
          "reading_section_bridge.py",
          {
            ...data,
            dossier_root: path.join(dataRoot, "dossier"),
            reference_id: digest(
              (process.env.DATABASE_URL ?? path.resolve(dbPath)) +
                ":" +
                data.profile_id,
            ),
          },
          onStage,
        )),
  );
  const forecasts = await ForecastJobs.create(store, allowPaid, generateForecast);
  const compatibility = await CompatibilityJobs.create(
    store,
    allowPaid,
    generateCompatibility,
  );
  const now = () => new Date().toISOString();
  const initializeAccount = async (tenantId: string, email = "") => {
    const me: Me = {
      ...fixture("me.en"),
      user_id: tenantId,
      email: email || fixture("me.en").email,
      display_name: "",
      self_profile_id: null,
      current_place: null,
      consents: { birth_data: null, marketing: false },
      created_at: now(),
      ask_quota: { limit_per_day: 0, used_today: 0, resets_at: now() },
    };
    await store.put("me", me);
    return me;
  };
  const ensureAccount = async (tenantId: string, email?: string) => {
    let me = await store.get<Me>("me");
    if (!me) me = await initializeAccount(tenantId, email);
    else if (email && me.email !== email) {
      me = { ...me, email };
      await store.put("me", me);
    }
    return me;
  };
  // Serialize handlers so profile edits/idempotency checks cannot interleave across an await.
  let tail = Promise.resolve();
  app.addHook("onClose", async () => {
    await ask.close();
    await tail;
    await readings.close();
    await progressive.close();
    await forecasts.close();
    await compatibility.close();
    await mapJobs.close();
    await store.close();
  });
  app.setErrorHandler((error: any, _request, reply) => {
    if (error.absence) {
      void reply.code(200).send(error.absence);
      return;
    }
    if (error.problem) {
      void reply
        .code(error.problem.status)
        .type("application/problem+json")
        .send(error.problem);
      return;
    }
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
              403: "forbidden",
              429: "rate_limited",
              404: "not_found",
              409: "conflict",
              410: "unauthorized",
              503: "upstream_unavailable",
            } as any
          )[status] ?? "internal",
      });
  });
  const session = async (
    verified?: VerifiedSession,
    demoTenant?: string,
    demoEmail?: string,
  ) => {
    if (auth && !verified) throw issue(401);
    const tenantId =
      verified?.user.id ??
      demoTenant ??
      randomUUID();
    if (verified) await bindOwner(verified.user.id);
    const access = verified?.access_token ?? randomBytes(32).toString("hex"),
      refresh = verified?.refresh_token ?? randomBytes(32).toString("hex");
    const expires = Date.now() + (verified?.expires_in ?? 3600) * 1000;
    await store.runAsAsync(SYSTEM_TENANT, async () => {
      await store.put(credential("access", access), {
        expires,
        owner: tenantId,
      });
      await store.put(credential("refresh", refresh), {
        expires: Date.now() + 30 * 86400000,
        accessKey: credential("access", access),
        owner: tenantId,
      });
    });
    return store.runAsAsync(tenantId, async () => {
      const me = await ensureAccount(
        tenantId,
        verified?.user.email ?? demoEmail,
      );
      await ask.quota();
      return {
        access_token: access,
        refresh_token: refresh,
        access_expires_at: new Date(expires).toISOString(),
        is_new_user: !me.self_profile_id,
        me: (await store.get<Me>("me"))!,
      };
    });
  };
  const resolveTenant = async (token: string) => {
    const record = await store.runAsAsync(SYSTEM_TENANT, () =>
      store.get<{ expires: number; owner?: string }>(
        credential("access", token),
      ),
    );
    if (!record || record.expires <= Date.now() || !record.owner)
      throw issue(401);
    if (auth) {
      const user = await auth.user(token);
      await bindOwner(user.id);
      if (user.id !== record.owner) throw issue(401);
    }
    return record.owner;
  };
  if (auth) registerBrowserSignIn(app, auth, session);
  const calendarContext = async (profile: BirthProfile) => {
    const me = (await store.get<Me>("me"))!;
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
    const context = await calendarContext(profile);
    const start = requestedStart ? validDate(requestedStart) : context.start;
    const current = context.current;
    const key = context.prefix + start;
    let saved = await store.get(key);
    if (!saved) {
      saved = await calculateCalendar(profile, current, start);
      await store.put(key, saved);
    }
    return saved[lang];
  };
  const place = async (id: string, lang: string) => {
    const key = `place:${lang}:${id}`;
    let value = await store.get(key);
    if (!value) {
      value = (await bridge({ action: "places", id, lang }))[0];
      if (!value) throw issue(400);
      await store.put(key, value);
    }
    const {
      kind: _kind,
      population: _population,
      source: _source,
      ...result
    } = value;
    return result;
  };
  if (guestOnboarding) {
    const guestStore = await Store.open(
      process.env.DATABASE_URL
        ? { databaseUrl: process.env.DATABASE_URL }
        : dbPath === ":memory:"
          ? ":memory:"
          : path.join(dataRoot, "onboarding-guests.sqlite"),
    );
    // Isolate guest records under a dedicated tenant when sharing Postgres.
    const guestTenant = "guest-pool";
    const guestScoped = {
      get: <T = any>(key: string) =>
        guestStore.runAsAsync(guestTenant, () => guestStore.get<T>(key)),
      put: (key: string, value: unknown) =>
        guestStore.runAsAsync(guestTenant, () => guestStore.put(key, value)),
      remove: (key: string) =>
        guestStore.runAsAsync(guestTenant, () => guestStore.remove(key)),
      list: <T = any>(prefix: string) =>
        guestStore.runAsAsync(guestTenant, () => guestStore.list<T>(prefix)),
      transaction: <T>(fn: () => Promise<T>) =>
        guestStore.runAsAsync(guestTenant, () => guestStore.transaction(fn)),
      clear: () => guestStore.runAsAsync(guestTenant, () => guestStore.clear()),
      close: () => guestStore.close(),
      runAs: guestStore.runAs.bind(guestStore),
      runAsAsync: guestStore.runAsAsync.bind(guestStore),
      tenant: () => guestTenant,
    } as unknown as Store;
    const guestReadings = await ProgressiveReadings.create(
      guestScoped,
      allowPaid,
      sectionRunner ??
        ((data, onStage) =>
          runReadingBridge(
            "reading_section_bridge.py",
            {
              ...data,
              dossier_root: path.join(dataRoot, "dossier"),
              reference_id: digest("guest:" + data.profile_id),
            },
            onStage,
          )),
    );
    registerGuestOnboarding(app, {
      enabled: allowPaid,
      guest: guestScoped,
      account: store,
      readings: guestReadings,
      accountReadings: progressive,
      place,
      withAccount: async (work) => {
        const previous = tail;
        let unlock!: () => void;
        tail = new Promise<void>((resolve) => {
          unlock = resolve;
        });
        await previous;
        try {
          return await work();
        } finally {
          unlock();
        }
      },
      authorize: async (request) => {
        const token = String(request.headers.authorization ?? "").replace(
          /^Bearer /,
          "",
        );
        const owner = await resolveTenant(token);
        return store.runAsAsync(owner, async () => (await store.get<Me>("me"))!.user_id);
      },
      calculate: computeBirthChart,
    });
    app.addHook("onClose", async () => {
      await guestReadings.close();
      await guestStore.close();
    });
  }
  for (const endpoint of endpoints) {
    app.route({
      method: endpoint.method.toUpperCase() as any,
      url: "/v1" + endpoint.path.replace(/\{([^}]+)\}/g, ":$1"),
      handler: async (request, reply) => {
        let unlock!: () => void;
        const prior = tail;
        tail = new Promise<void>((resolve) => {
          let released = false;
          unlock = () => {
            if (!released) {
              released = true;
              resolve();
            }
          };
        });
        await prior;
        try {
          const q = request.query as Record<string, string>,
            p = request.params as Record<string, string>;
          const publicRoute =
            /^\/(auth|meta|geo)\//.test(endpoint.path) ||
            (guestOnboarding &&
              endpoint.method === "get" &&
              ["/places/search", "/places/{place_id}"].includes(endpoint.path));
          let tenantId: string | undefined;
          if (!publicRoute) {
            const token = String(request.headers.authorization ?? "").replace(
              /^Bearer /,
              "",
            );
            tenantId = await resolveTenant(token);
          }
          const run = async <T>(fn: () => Promise<T>): Promise<T> =>
            tenantId ? store.runAsAsync(tenantId, fn) : fn();
          return await run(async () => {
          const lang =
            q.lang ??
            (await store.get<Me>("me"))?.language ??
            "en";
          if (!["en", "tr"].includes(lang)) throw issue(400);
          let body: any = request.body ?? {};
          if (endpoint.body) {
            try {
              body = schemas[endpoint.body]!.parse(body);
            } catch {
              throw issue(400);
            }
          }
          const idempotency = request.headers["idempotency-key"];
          const cacheKey =
            idempotency &&
            !endpoint.path.startsWith("/auth/") &&
            endpoint.method !== "get"
              ? `idem:${endpoint.method}:${request.url}:${String(idempotency)}`
              : null;
          if (cacheKey) {
            const saved = await store.get(cacheKey);
            if (saved && saved.expires > Date.now()) {
              if (saved.body !== JSON.stringify(body)) throw issue(409);
              if (
                endpoint.path === "/compatibility" &&
                endpoint.method === "post"
              )
                return reply
                  .code(saved.status)
                  .send(
                    await compatibility.get(
                      saved.result.compatibility_id,
                      lang as "en" | "tr",
                    ),
                  );
              return reply.code(saved.status).send(saved.result);
            }
          }
          const me = (await store.get<Me>("me"))!;
          const profile = p.id
            ? await store.get<BirthProfile>("profile:" + p.id)
            : undefined;
          if (endpoint.path.startsWith("/profiles/{id}") && !profile)
            throw issue(404);
          let result: any;
          switch (`${endpoint.method} ${endpoint.path}`) {
            case "get /meta/config":
              result = fixture("config");
              result.flags.askAstrology = ask.enabled();
              result.flags.guestOnboarding = guestOnboarding && allowPaid;
              result.flags.familyCompatibility = false;
              result.flags.solarReturn = false;
              break;
            case "get /meta/catalogue":
              result = fixture(`catalogue.${lang}`);
              break;
            // Demo credentials are accepted only when real authentication has never been enabled.
            case "post /auth/email/start":
              if (auth) await auth.startEmail(body.email);
              else if (!body.email?.includes("@")) throw issue(503);
              return reply.code(204).send();
            case "post /auth/email/verify":
              if (auth)
                result = await session(await auth.verify(body.email, body.code));
              else {
                if (body.code !== "000000") throw issue(401);
                result = await session(
                  undefined,
                  digest(String(body.email).trim().toLowerCase()),
                  String(body.email).trim().toLowerCase(),
                );
              }
              break;
            case "post /auth/google":
            case "post /auth/apple":
              if (!auth) throw issue(503);
              result = await session(
                await auth.provider(
                  endpoint.path.endsWith("google") ? "google" : "apple",
                  body.id_token ?? body.identity_token,
                ),
              );
              break;
            case "post /auth/refresh": {
              const key = credential("refresh", body.refresh_token);
              const saved = await store.runAsAsync(SYSTEM_TENANT, () =>
                store.get<{
                  expires: number;
                  accessKey?: string;
                  accessHash?: string;
                  owner?: string;
                }>(key),
              );
              if (!saved || saved.expires <= Date.now()) throw issue(401);
              const verified = auth
                ? await auth.refresh(body.refresh_token)
                : undefined;
              result = await store.runAsAsync(SYSTEM_TENANT, async () => {
                await store.remove(key);
                await store.remove(
                  saved.accessKey ?? "access:" + saved.accessHash,
                );
                return session(verified, saved.owner);
              });
              break;
            }
            case "post /auth/logout": {
              const key = credential("refresh", body.refresh_token);
              const saved = await store.runAsAsync(SYSTEM_TENANT, () =>
                store.get<{ accessKey?: string; accessHash?: string }>(key),
              );
              if (saved) {
                await store.runAsAsync(SYSTEM_TENANT, async () => {
                  await store.remove(
                    saved.accessKey ?? "access:" + saved.accessHash,
                  );
                  await store.remove(key);
                });
                const access = String(
                  request.headers.authorization ?? "",
                ).replace(/^Bearer /, "");
                if (auth && credential("access", access) === saved.accessKey) {
                  await auth.logout(access).catch(() => {});
                }
              }
              return reply.code(204).send();
            }
            case "post /me/export":
              result = {
                ...(await exportAccount(store)),
                dossiers: await progressive.exportDossiers(),
              };
              break;
            case "delete /me":
              await ask.close();
              progressive.assertIdle();
              if (
                (await store.list<any>("job:")).some((j) =>
                  ["queued", "running"].includes(j.status),
                )
              )
                throw issue(409);
              for (const target of await store.list<BirthProfile>("profile:"))
                await progressive.releaseProfile(target);
              await deleteAccount(store, dbPath === ":memory:" ? dataRoot : dbPath);
              if (auth)
                await store.runAsAsync(SYSTEM_TENANT, async () => {
                  await store.put("auth-mode", auth.scope);
                });
              if (tenantId) await initializeAccount(tenantId);
              return reply.code(202).send();
            case "get /me":
              result = { ...me, ask_quota: await ask.quota() };
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
                ...(await store.get<Me>("me"))!,
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
              await store.put("me", result);
              break;
            }
            case "get /places/search":
              if (q.kind && !["birth", "city", "area"].includes(q.kind))
                throw issue(400);
              result = await bridge({
                action: "places",
                kind: q.kind,
                query: (q.q ?? "").slice(0, 100),
                lang,
              });
              for (const candidate of result)
                await store.put(`place:${lang}:${candidate.place_id}`, candidate);
              break;
            case "get /places/{place_id}":
              result = await place(p.place_id!, lang);
              break;
            case "get /places/reverse":
              if (
                q.lat === undefined ||
                q.lon === undefined ||
                !q.lat.trim() ||
                !q.lon.trim() ||
                !Number.isFinite(Number(q.lat)) ||
                !Number.isFinite(Number(q.lon))
              )
                throw issue(400);
              result = await bridge({
                action: "reverse",
                lat: Number(q.lat),
                lon: Number(q.lon),
                lang,
              });
              break;
            case "get /profiles":
              result = await store.list<BirthProfile>("profile:");
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
              if (!profile && (await store.list("profile:")).length >= 50)
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
              if (profile) progressive.assertIdle(profile.chart_key);
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
              if (progressiveReadings) await progressive.prepare(result);
              await store.transaction(async () => {
                await store.put("profile:" + id, result);
                await store.put("chart:" + id, chart);
                await store.put("raw:" + id, computed.raw);
                if (profile && profile.chart_key !== chart.chart_key)
                  for (const language of ["tr", "en"])
                    await store.remove(`report:${id}:${language}`);
                if (result.is_self)
                  await store.put("me", {
                    ...(await store.get<Me>("me"))!,
                    self_profile_id: id,
                  });
                if (cacheKey)
                  await store.put(cacheKey, {
                    body: JSON.stringify(body),
                    status: endpoint.status ?? 200,
                    result,
                    expires: Date.now() + 86400000,
                  });
              });
              if (profile && profile.chart_key !== result.chart_key)
                await progressive.releaseProfile(profile);
              if (progressiveReadings && result.is_self)
                await progressive.start(result);
              break;
            }
            case "delete /profiles/{id}":
              if (profile!.is_self) throw issue(409);
              progressive.assertIdle(profile!.chart_key);
              await progressive.releaseProfile(profile!);
              await store.transaction(async () => {
                for (const prefix of ["profile:", "chart:", "raw:"])
                  await store.remove(prefix + p.id);
                for (const language of ["tr", "en"])
                  await store.remove(`report:${p.id}:${language}`);
              });
              return reply.code(204).send();
            case "post /profiles/{id}/acg/recommendations":
              result = await maps.recommend(
                profile!,
                body,
                lang as "en" | "tr",
              );
              if (result.status !== "needs_goal") {
                const home =
                  (profile!.is_self
                    ? (await store.get<Me>("me"))?.current_place
                    : profile!.current_place) ?? profile!.birth.place;
                result = await mapJobs.get(
                  mapContext(profile!, "recommendation", {
                    request: body,
                    home: [home.lat, home.lon],
                  }),
                  result,
                  lang as "en" | "tr",
                  q.retry === "true",
                );
              }
              break;
            case "get /profiles/{id}/acg/countries/{iso2}":
              result = await maps.area(
                profile!,
                "country",
                p.iso2!,
                lang as "en" | "tr",
              );
              result = await mapJobs.get(
                mapContext(profile!, "area", {
                  kind: "country",
                  code: p.iso2!,
                }),
                result,
                lang as "en" | "tr",
                q.retry === "true",
              );
              break;
            case "get /profiles/{id}/acg/regions/{admin1_id}":
              result = await maps.area(
                profile!,
                "region",
                p.admin1_id!,
                lang as "en" | "tr",
              );
              result = await mapJobs.get(
                mapContext(profile!, "area", {
                  kind: "region",
                  code: p.admin1_id!,
                }),
                result,
                lang as "en" | "tr",
                q.retry === "true",
              );
              break;
            case "get /profiles/{id}/acg/places/{place_id}": {
              const found = await place(p.place_id!, lang);
              result = await maps.placeReport(
                profile!,
                {
                  place_id: found.place_id,
                  name: found.name,
                  country_code: found.country_code,
                  lat: found.lat,
                  lon: found.lon,
                },
                lang as "en" | "tr",
                q.focus_goal,
              );
              const canonical = await place(p.place_id!, "en");
              result = await mapJobs.get(
                mapContext(profile!, "place", {
                  place: { ...result.place, name: canonical.name },
                  focus_goal: q.focus_goal || null,
                }),
                result,
                lang as "en" | "tr",
                q.retry === "true",
              );
              break;
            }
            case "get /profiles/{id}/acg/point": {
              if (
                q.lat === undefined ||
                q.lon === undefined ||
                !q.lat.trim() ||
                !q.lon.trim()
              )
                throw issue(400);
              const lat = Number(q.lat),
                lon = Number(q.lon);
              result = await maps.placeReport(
                profile!,
                {
                  place_id: null,
                  name: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
                  country_code: null,
                  lat,
                  lon,
                },
                lang as "en" | "tr",
                q.focus_goal,
              );
              result = await mapJobs.get(
                mapContext(profile!, "place", {
                  place: result.place,
                  focus_goal: q.focus_goal || null,
                }),
                result,
                lang as "en" | "tr",
                q.retry === "true",
              );
              break;
            }
            case "get /profiles/{id}/acg/heat/{goal}":
              result = await maps.heat(profile!, p.goal!);
              break;
            case "get /profiles/{id}/acg/lines":
              result = await maps.lines(profile!);
              break;
            case "get /profiles/{id}/acg/lines/{body}/{angle}/places":
              result = await maps.places(
                profile!,
                p.body!,
                p.angle!,
                lang as "en" | "tr",
                Number(q.limit ?? 5),
              );
              break;
            case "get /geo/countries.geojson":
              result = fixture("geo-countries-simple");
              break;
            case "get /geo/regions/{iso2}.geojson":
              if (!/^[A-Z]{2}$/.test(p.iso2 ?? "")) throw issue(400);
              try {
                result = fixture(`geo-regions.${p.iso2}`);
              } catch {
                throw issue(404);
              }
              break;
            case "get /profiles/{id}/chart":
              result = await store.get("chart:" + p.id);
              break;
            case "get /home": {
              const me = (await store.get<Me>("me"))!;
              const self = await store.get<BirthProfile>(
                "profile:" + me.self_profile_id,
              );
              if (!self) throw issue(404);
              const context = await calendarContext(self);
              const cal = await calendarFor(
                self,
                lang,
                context.start.slice(0, 7) + "-01",
              );
              const catalogue = fixture(`catalogue.${lang}`);
              const day = dayForecast(
                cal,
                catalogue,
                self.profile_id,
                context.start,
              );
              if (!day) throw issue(400);
              result = homeSummary(
                day as never,
                self.label,
                catalogue,
                await forecasts.peek(
                  forecastContext(
                    self,
                    context.current,
                    context.start,
                    "day",
                    "general",
                  ),
                  lang as "en" | "tr",
                ),
                cal.notifications,
              );
              break;
            }
            case "get /profiles/{id}/forecast/day":
            case "get /profiles/{id}/forecast/month":
            case "get /profiles/{id}/forecast/year": {
              if (
                q.lens &&
                !["general", "personal", "professional"].includes(q.lens)
              )
                throw issue(400);
              const date = endpoint.path.endsWith("/day")
                ? validDate(q.date ?? (await calendarContext(profile!)).start)
                : validDate(
                    `${(endpoint.path.endsWith("/year") ? q.from : q.month) ?? (await calendarContext(profile!)).start.slice(0, 7)}-01`,
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
              result.reading = await forecasts.get(
                forecastContext(
                  profile!,
                  (await calendarContext(profile!)).current,
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
            case "get /profiles/{id}/calendar/items/{item_id}": {
              const prefix = (await calendarContext(profile!)).prefix;
              result = (await store.list<any>(prefix))
                .map((snapshot) => snapshot[lang]?.items[p.item_id!])
                .find(Boolean);
              result ??= (await calendarFor(profile!, lang)).items[p.item_id!];
              if (!result) throw issue(404);
              break;
            }
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
            case "get /profiles/{id}/natal-reading/outline":
              result = await progressive.outline(profile!, lang as "tr" | "en");
              break;
            case "get /profiles/{id}/natal-reading/sections/{key}": {
              const value = await progressive.section(
                profile!,
                p.key as any,
                lang as "tr" | "en",
                false,
                q.retry === "true",
              );
              if (value.absence)
                return reply.send({ status: "absent", absence: value.absence });
              if (value.job) return reply.code(202).send({ job: value.job });
              result = value.section;
              break;
            }
            case "post /profiles/{id}/natal-reading/progress":
              await progressive.opened(profile!, body.key, body.event);
              return reply.code(204).send();
            case "post /profiles/{id}/natal-reading/complete":
              return reply.code(202).send({
                job: await progressive.complete(profile!, lang as "tr" | "en"),
              });
            case "post /feedback/reading": {
              const target = await store.get<BirthProfile>(
                "profile:" + body.profile_id,
              );
              if (!target) throw issue(404);
              result = await progressive.feedback(target, body);
              break;
            }
            case "get /profiles/{id}/natal-reading": {
              const value = (progressiveReadings || (guestOnboarding && await store.get(`reading-section:${profile!.chart_key}:core_identity`)))
                ? await progressive.reading(
                    profile!,
                    lang as "en" | "tr",
                    false,
                    q.retry === "true",
                  )
                : await readings.get(
                    profile!,
                    lang as "en" | "tr",
                    q.retry === "true",
                  );
              if (value.absence)
                return reply
                  .code(200)
                  .send({ status: "absent", absence: value.absence });
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
              result = await store.get("job:" + p.job_id);
              if (!result) throw issue(404);
              break;
            case "get /reports": {
              const natal = [];
              for (const r of await store.list<any>("report:")) {
                if (
                  r.lang === lang &&
                  (await store.get("profile:" + r.profile_id))
                )
                  natal.push(r);
              }
              const all = [
                ...natal,
                ...(await forecasts.reports(lang as "en" | "tr")),
                ...(await compatibility.reports(lang as "en" | "tr")),
                ...(await mapJobs.reports(lang as "en" | "tr")),
              ];
              const visible = [];
              for (const r of all) {
                if (
                  (!q.type || r.type === q.type) &&
                  !(await store.get("hidden-report:" + r.report_id))
                )
                  visible.push(r);
              }
              visible.sort(
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
                items: visible.slice(start, start + count),
                next_cursor:
                  start + count < visible.length
                    ? String(start + count)
                    : null,
              };
              break;
            }
            case "delete /reports/{report_id}": {
              const reports = [
                ...(await store.list<any>("report:")),
                ...(await forecasts.reports("en")),
                ...(await forecasts.reports("tr")),
                ...(await compatibility.reports("en")),
                ...(await compatibility.reports("tr")),
                ...(await mapJobs.reports("en")),
                ...(await mapJobs.reports("tr")),
              ];
              if (
                !reports.some((r) => r.report_id === p.report_id) ||
                (await store.get("hidden-report:" + p.report_id))
              )
                throw issue(404);
              await store.put("hidden-report:" + p.report_id, true);
              return reply.code(204).send();
            }
            case "post /compatibility":
              result = await compatibility.create(body, lang as "en" | "tr");
              if (cacheKey)
                await store.put(cacheKey, {
                  body: JSON.stringify(body),
                  result,
                  status: 201,
                  expires: Date.now() + 86400000,
                });
              break;
            case "get /compatibility/{id}":
              result = await compatibility.get(
                p.id!,
                lang as "en" | "tr",
                q.retry === "true",
              );
              break;
            case "delete /compatibility/{id}":
              await compatibility.remove(p.id!);
              return reply.code(204).send();
            case "get /compatibility": {
              const items = await compatibility.list();
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
              result = await ask.list(q.cursor, q.limit);
              break;
            case "post /ask/threads":
              result = await ask.create(body.profile_id);
              break;
            case "get /ask/threads/{id}":
              result = await ask.get(p.id!);
              break;
            case "delete /ask/threads/{id}":
              await ask.remove(p.id!);
              return reply.code(204).send();
            case "post /ask/threads/{id}/messages": {
              const streaming = ask.start(p.id!, body, lang, reply);
              unlock();
              await streaming;
              return reply;
            }
            case "post /ask/messages/{message_id}/feedback":
              await ask.feedback(p.message_id!, body.rating, body.reason);
              return reply.code(204).send();
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
          });
        } finally {
          unlock();
        }
      },
    });
  }
  return app;
}
