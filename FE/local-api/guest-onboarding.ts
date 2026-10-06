import { createHash, randomUUID } from "node:crypto";
import type { FastifyInstance, FastifyRequest } from "fastify";
import type { BirthProfile, Me, Place, Lang } from "../contracts/spec-types";
import {
  guestBirthSchema,
  guestTokenSchema,
  type GuestBirth,
} from "../contracts/guest-onboarding";
import { validBirth } from "../src/lib/dates";
import { computeBirthChart } from "./engine";
import { Store } from "./store";
import { ProgressiveReadings } from "./progressive-readings";
const hash = (value: string) =>
  createHash("sha256").update(value).digest("hex");
const fail = (statusCode: number) =>
  Object.assign(new Error("Onboarding unavailable"), { statusCode });
type Guest = {
  hash: string;
  fingerprint: string;
  expires: number;
  profile: BirthProfile;
  claimed?: { owner: string; profile_id: string };
};
export function registerGuestOnboarding(
  app: FastifyInstance,
  options: {
    enabled: boolean;
    guest: Store;
    account: Store;
    readings: ProgressiveReadings;
    accountReadings: ProgressiveReadings;
    place: (id: string, lang: string) => Promise<Place>;
    authorize: (request: FastifyRequest) => Promise<string>;
    withAccount?: <T>(work: () => Promise<T>) => Promise<T>;
    calculate?: typeof computeBirthChart;
    now?: () => number;
  },
) {
  const { guest, account, readings, accountReadings } = options;
  const clock = options.now ?? Date.now;
  const withAccount =
    options.withAccount ?? (async <T>(work: () => Promise<T>) => work());
  let tail = Promise.resolve();
  const serial = async <T>(fn: () => Promise<T>): Promise<T> => {
    const previous = tail;
    let unlock!: () => void;
    tail = new Promise<void>((resolve) => {
      unlock = resolve;
    });
    await previous;
    try {
      return await fn();
    } finally {
      unlock();
    }
  };
  const tokenHash = (request: FastifyRequest) => {
    const value = guestTokenSchema.safeParse(request.headers["x-guest-token"]);
    if (!value.success) throw fail(401);
    return hash(value.data);
  };
  const lookup = (id: string) => {
    const record = guest.get<Guest>("guest:" + id);
    if (!record || record.expires <= clock() || record.claimed) throw fail(401);
    return record;
  };
  const state = async (record: Guest, lang: Lang, retry = false) => {
    const result = await readings.section(
      record.profile,
      "core_identity",
      lang,
      true,
      retry,
    );
    if (result.absence) throw fail(503);
    return {
      status: result.section
        ? "ready"
        : result.job?.status === "failed"
          ? "failed"
          : "generating",
      expires_at: new Date(record.expires).toISOString(),
      ...(result.section
        ? {
            section: {
              key: "core_identity",
              title: result.section.title,
              text: result.section.text,
            },
          }
        : {}),
      stage: result.job?.stages?.find((s) => s.status === "running")?.name,
    };
  };
  const remove = async (record: Guest) => {
    await readings.releaseProfile(record.profile);
    guest.transaction(() => {
      for (const prefix of ["profile:", "chart:", "raw:"])
        guest.remove(prefix + record.profile.profile_id);
      guest.remove("guest:" + record.hash);
    });
  };
  const sweep = async () => {
    for (const record of guest.list<Guest>("guest:")) {
      if (record.expires > clock()) continue;
      try {
        await remove(record);
      } catch {
        /* Active generation is collected on the next sweep. */
      }
    }
    for (const entry of guest.list<{ key: string; expires: number }>(
      "guest-rate:",
    ))
      if (entry.expires <= clock()) guest.remove(entry.key);
  };
  const timer = setInterval(() => void serial(sweep).catch(() => {}), 60_000);
  timer.unref();
  app.addHook("onClose", async () => {
    clearInterval(timer);
    await tail;
    await readings.close();
    guest.close();
  });
  app.post("/v1/onboarding/reading", async (request, reply) =>
    serial(async () => {
      if (!options.enabled) throw fail(503);
      const id = tokenHash(request);
      const parsed = guestBirthSchema.safeParse(request.body);
      if (
        !parsed.success ||
        !validBirth(
          parsed.data.birth_date,
          parsed.data.birth_time,
          new Date(clock()).toISOString().slice(0, 10),
        )
      )
        throw fail(400);
      const input: GuestBirth = parsed.data;
      const fingerprint = hash(
        JSON.stringify([
          input.birth_date,
          input.birth_time,
          input.birth_place_id,
        ]),
      );
      const saved = guest.get<Guest>("guest:" + id);
      if (saved) {
        const record = lookup(id);
        if (record.fingerprint !== fingerprint) throw fail(409);
        return reply.code(202).send(await state(record, input.lang, true));
      }
      await sweep();
      const rateKey = "guest-rate:" + hash(request.ip);
      let rate = guest.get<{ key: string; count: number; expires: number }>(
        rateKey,
      );
      if (!rate || rate.expires <= clock())
        rate = { key: rateKey, count: 0, expires: clock() + 3600_000 };
      if (rate.count >= 5 || guest.list<Guest>("guest:").length >= 20)
        throw fail(429);
      // Persist the attempt before expensive work; tokens cannot bypass this budget bound.
      guest.put(rateKey, { ...rate, count: rate.count + 1 });
      const place = await options.place(input.birth_place_id, input.lang);
      const profile_id = randomUUID();
      const { chart, raw } = await (options.calculate ?? computeBirthChart)(
        { date: input.birth_date, time: input.birth_time, place },
        profile_id,
      );
      const profile: BirthProfile = {
        profile_id,
        chart_key: chart.chart_key,
        label: input.lang === "tr" ? "Benim haritam" : "My chart",
        relation: "self",
        is_self: true,
        gender: null,
        birth: {
          date: input.birth_date,
          time: input.birth_time,
          place: { ...place, tz: chart.tz },
          tz: chart.tz,
          utc: chart.utc,
        },
        current_place: null,
        big_three: {
          sun: chart.points.find((p) => p.body === "sun")!.sign,
          moon: chart.points.find((p) => p.body === "moon")!.sign,
          ascendant: chart.axes.asc.sign,
        },
        created_at: new Date(clock()).toISOString(),
        updated_at: new Date(clock()).toISOString(),
      };
      const record: Guest = {
        hash: id,
        fingerprint,
        profile,
        expires: clock() + 86400_000,
      };
      guest.transaction(() => {
        guest.put("profile:" + profile_id, profile);
        guest.put("chart:" + profile_id, chart);
        guest.put("raw:" + profile_id, raw);
        guest.put("guest:" + id, record);
      });
      return reply.code(202).send(await state(record, input.lang));
    }),
  );
  app.get("/v1/onboarding/reading", async (request) =>
    serial(async () => {
      if (!options.enabled) throw fail(503);
      const lang = (request.query as { lang?: string }).lang ?? "en";
      if (lang !== "en" && lang !== "tr") throw fail(400);
      return state(lookup(tokenHash(request)), lang);
    }),
  );
  app.delete("/v1/onboarding/reading", async (request, reply) =>
    serial(async () => {
      await remove(lookup(tokenHash(request)));
      return reply.code(204).send();
    }),
  );
  app.post("/v1/me/onboarding/claim", async (request) =>
    serial(() =>
      withAccount(async () => {
        const owner = await options.authorize(request);
        const token = guestTokenSchema.safeParse(
          (request.body as { guest_token?: unknown })?.guest_token,
        );
        if (!token.success) throw fail(400);
        const id = hash(token.data),
          record = guest.get<Guest>("guest:" + id);
        if (!record || record.expires <= clock()) throw fail(410);
        if (record.claimed) {
          if (record.claimed.owner !== owner) throw fail(403);
          return {
            profile: account.get("profile:" + record.claimed.profile_id),
            me: account.get("me"),
          };
        }
        readings.assertIdle(record.profile.chart_key);
        accountReadings.assertIdle(record.profile.chart_key);
        const sectionKey = `reading-section:${record.profile.chart_key}:core_identity`;
        const section = guest.get<any>(sectionKey);
        if (!section?.text_tr) throw fail(409);
        const me = account.get<Me>("me")!;
        const matching = account
          .list<BirthProfile>("profile:")
          .find((p) => p.chart_key === record.profile.chart_key);
        if (!matching && account.list("profile:").length >= 50) throw fail(409);
        const profile = matching ?? {
          ...record.profile,
          is_self: !me.self_profile_id,
          relation: me.self_profile_id ? ("other" as const) : ("self" as const),
        };
        account.transaction(() => {
          account.put("profile:" + profile.profile_id, profile);
          if (!matching) {
            account.put(
              "raw:" + profile.profile_id,
              guest.get("raw:" + record.profile.profile_id),
            );
            account.put("chart:" + profile.profile_id, {
              ...guest.get<any>("chart:" + record.profile.profile_id),
              profile_id: profile.profile_id,
            });
          }
          // An existing account reading remains authoritative after a guest claim.
          const existing = account.get<any>(sectionKey);
          account.put(
            sectionKey,
            existing?.text_tr ? existing : { ...section, job_id: undefined },
          );
          if (
            account.get<any>("reading-progress:" + profile.profile_id)
              ?.chart_key !== profile.chart_key
          )
            account.put("reading-progress:" + profile.profile_id, {
              opened: ["core_identity"],
              furthest_index: 0,
              chart_key: profile.chart_key,
            });
          if (!me.self_profile_id)
            account.put("me", {
              ...me,
              self_profile_id: profile.profile_id,
              display_name: me.display_name || profile.label,
              consents: {
                ...me.consents,
                birth_data: {
                  version: "onboarding-preview-v1",
                  accepted_at: profile.created_at,
                },
              },
            });
        });
        await accountReadings.prepare(profile);
        record.claimed = { owner, profile_id: profile.profile_id };
        guest.put("guest:" + id, record);
        await readings.releaseProfile(record.profile);
        for (const prefix of ["profile:", "raw:", "chart:"])
          guest.remove(prefix + record.profile.profile_id);
        return { profile, me: account.get("me") };
      }),
    ),
  );
}
