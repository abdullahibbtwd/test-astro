import { createHash, randomUUID } from "node:crypto";
import type { FastifyInstance, FastifyRequest } from "fastify";
import type { BirthProfile, Me, Place, Lang } from "../../frontend/contracts/spec-types";
import {
  guestBirthSchema,
  guestTokenSchema,
  type GuestBirth,
} from "../../frontend/contracts/guest-onboarding";
import type { GuestSession, Prisma } from "../src/generated/prisma/client.js";
import { validBirth } from "../../frontend/src/lib/dates";
import { computeBirthChart } from "./engine";
import { prisma as getPrisma } from "./db";
import {
  countActiveGuestSessions,
  tryConsumeGuestRate,
  withGuestPoolLock,
} from "./limits";
import { Store } from "./store";
import { ProgressiveReadings } from "./progressive-readings";

const GUEST_POOL_MAX = 20;

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

function fromRow(row: GuestSession): Guest {
  return {
    hash: row.tokenHash,
    fingerprint: row.fingerprint,
    expires: row.expiresAt.getTime(),
    profile: row.profile as unknown as BirthProfile,
    claimed:
      row.claimedById && row.claimedProfileId
        ? { owner: row.claimedById, profile_id: row.claimedProfileId }
        : undefined,
  };
}

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
  const db = getPrisma();
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
  const load = async (id: string) => {
    const row = await db.guestSession.findUnique({ where: { tokenHash: id } });
    return row ? fromRow(row) : undefined;
  };
  const lookup = async (id: string) => {
    const record = await load(id);
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
    await guest.transaction(async () => {
      for (const prefix of ["profile:", "chart:", "raw:"])
        await guest.remove(prefix + record.profile.profile_id);
    });
    await db.guestSession
      .delete({ where: { tokenHash: record.hash } })
      .catch(() => undefined);
  };
  const sweep = async () => {
    const expired = await db.guestSession.findMany({
      where: { expiresAt: { lte: new Date(clock()) } },
    });
    for (const row of expired) {
      try {
        await remove(fromRow(row));
      } catch {
        /* Active generation is collected on the next sweep. */
      }
    }
  };
  const timer = setInterval(() => void serial(sweep).catch(() => {}), 60_000);
  (timer as unknown as NodeJS.Timeout).unref();
  app.addHook("onClose", async () => {
    clearInterval(timer);
    await tail;
    await readings.close();
    await guest.close();
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
      const saved = await load(id);
      if (saved) {
        const record = await lookup(id);
        if (record.fingerprint !== fingerprint) throw fail(409);
        return reply.code(202).send(await state(record, input.lang, true));
      }
      await sweep();
      // Persist the attempt before expensive work; tokens cannot bypass this budget bound.
      if ((await tryConsumeGuestRate(hash(request.ip), db)) == null)
        throw fail(429);
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
      const expiresAt = new Date(clock() + 86400_000);
      const record: Guest = {
        hash: id,
        fingerprint,
        profile,
        expires: expiresAt.getTime(),
      };
      await withGuestPoolLock(async (tx) => {
        if ((await countActiveGuestSessions(tx)) >= GUEST_POOL_MAX)
          throw fail(429);
        await tx.guestSession.create({
          data: {
            tokenHash: id,
            fingerprint,
            expiresAt,
            profile: profile as unknown as Prisma.InputJsonValue,
            chartKey: chart.chart_key,
          },
        });
      }, db);
      await guest.transaction(async () => {
        await guest.put("profile:" + profile_id, profile);
        await guest.put("chart:" + profile_id, chart);
        await guest.put("raw:" + profile_id, raw);
      });
      // Retry clears a prior failed section for the same chart_key.
      return reply.code(202).send(await state(record, input.lang, true));
    }),
  );
  app.get("/v1/onboarding/reading", async (request) =>
    serial(async () => {
      if (!options.enabled) throw fail(503);
      const lang = (request.query as { lang?: string }).lang ?? "en";
      if (lang !== "en" && lang !== "tr") throw fail(400);
      return state(await lookup(tokenHash(request)), lang);
    }),
  );
  app.delete("/v1/onboarding/reading", async (request, reply) =>
    serial(async () => {
      await remove(await lookup(tokenHash(request)));
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
        const id = hash(token.data);
        const record = await load(id);
        if (!record || record.expires <= clock()) throw fail(410);
        return account.runAsAsync(owner, async () => {
          if (record.claimed) {
            if (record.claimed.owner !== owner) throw fail(403);
            return {
              profile: await account.get(
                "profile:" + record.claimed.profile_id,
              ),
              me: await account.get("me"),
            };
          }
          readings.assertIdle(record.profile.chart_key);
          accountReadings.assertIdle(record.profile.chart_key);
          const sectionKey = `reading-section:${record.profile.chart_key}:core_identity`;
          const section = await guest.get<any>(sectionKey);
          if (!section?.text_tr && !section?.text_en) throw fail(409);
          const me = (await account.get<Me>("me"))!;
          const profiles = await account.list<BirthProfile>("profile:");
          const matching = profiles.find(
            (p) => p.chart_key === record.profile.chart_key,
          );
          if (!matching && profiles.length >= 50) throw fail(409);
          const profile = matching ?? {
            ...record.profile,
            is_self: !me.self_profile_id,
            relation: me.self_profile_id
              ? ("other" as const)
              : ("self" as const),
          };
          await account.transaction(async () => {
            await account.put("profile:" + profile.profile_id, profile);
            if (!matching) {
              await account.put(
                "raw:" + profile.profile_id,
                await guest.get("raw:" + record.profile.profile_id),
              );
              await account.put("chart:" + profile.profile_id, {
                ...(await guest.get<any>(
                  "chart:" + record.profile.profile_id,
                )),
                profile_id: profile.profile_id,
              });
            }
            // An existing account reading remains authoritative after a guest claim.
            const existing = await account.get<any>(sectionKey);
            await account.put(
              sectionKey,
              existing?.text_tr ? existing : { ...section, job_id: undefined },
            );
            if (
              (await account.get<any>("reading-progress:" + profile.profile_id))
                ?.chart_key !== profile.chart_key
            )
              await account.put("reading-progress:" + profile.profile_id, {
                opened: ["core_identity"],
                furthest_index: 0,
                chart_key: profile.chart_key,
              });
            if (!me.self_profile_id)
              await account.put("me", {
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
          await db.guestSession.update({
            where: { tokenHash: id },
            data: {
              claimedById: owner,
              claimedProfileId: profile.profile_id,
            },
          });
          await readings.releaseProfile(record.profile);
          for (const prefix of ["profile:", "raw:", "chart:"])
            await guest.remove(prefix + record.profile.profile_id);
          return { profile, me: await account.get("me") };
        });
      }),
    ),
  );
}
