import { randomUUID } from "node:crypto";
import type { FastifyReply } from "fastify";
import type {
  BirthProfile,
  Me,
  Message,
  Thread,
  AskRequest,
} from "../../frontend/contracts/spec-types";
import { Store } from "./store";
import { validate } from "../../frontend/src/api/zod";
import { askBackendReady, runAskBridge, type AskRunner } from "./ask-bridge";
const problem = (status: number, code: string) => ({
  type: "about:blank",
  title: "Conversation unavailable",
  status,
  code,
});
const issue = (status: number, code: string) =>
  Object.assign(new Error(code), { problem: problem(status, code) });
const stamp = () => new Date().toISOString();
export class AskService {
  private active = new Map<
    string,
    { abort: AbortController; finished: Promise<void> }
  >();
  constructor(
    private store: Store,
    private allowPaid: boolean,
    private runner: AskRunner = runAskBridge,
    private ready = askBackendReady,
    private dailyLimit = 20,
  ) {}
  enabled() {
    return this.allowPaid && this.ready();
  }
  async quota() {
    const { prisma } = await import("./db");
    const { utcDay } = await import("./limits");
    const me = (await this.store.get<Me>("me"))!;
    const day = utcDay();
    const row = await prisma().usageCounter.findUnique({
      where: {
        userId_kind_date: { userId: me.user_id, kind: "ASK", date: day },
      },
    });
    const reset = new Date(day);
    reset.setUTCDate(reset.getUTCDate() + 1);
    const quota = {
      limit_per_day: this.enabled() ? this.dailyLimit : 0,
      used_today: row?.count ?? 0,
      resets_at: reset.toISOString(),
    };
    await this.store.put("me", { ...me, ask_quota: quota });
    return quota;
  }
  async get(id: string): Promise<Thread> {
    const thread = await this.store.get<Thread>("ask-thread:" + id);
    if (!thread) throw issue(404, "not_found");
    return thread;
  }
  async list(cursor?: string, limit?: string) {
    const offset = Number(cursor ?? 0),
      size = Number(limit ?? 20);
    if (
      !Number.isSafeInteger(offset) ||
      offset < 0 ||
      !Number.isSafeInteger(size) ||
      size < 1 ||
      size > 100
    )
      throw issue(400, "validation_error");
    const threads = (await this.store.list<Thread>("ask-thread:")).sort(
      (a, b) =>
        b.updated_at.localeCompare(a.updated_at) ||
        a.thread_id.localeCompare(b.thread_id),
    );
    return {
      items: threads
        .slice(offset, offset + size)
        .map(({ messages: _messages, ...thread }) => thread),
      next_cursor:
        offset + size < threads.length ? String(offset + size) : null,
    };
  }
  async create(profile_id: string) {
    if (!this.enabled()) throw issue(503, "upstream_unavailable");
    if (!(await this.store.get("profile:" + profile_id)))
      throw issue(404, "not_found");
    const thread: Thread = {
      thread_id: randomUUID(),
      profile_id,
      title: "",
      created_at: stamp(),
      updated_at: stamp(),
      messages: [],
    };
    await this.store.put("ask-thread:" + thread.thread_id, thread);
    return thread;
  }
  async remove(id: string) {
    const thread = await this.get(id),
      running = this.active.get(id);
    if (running) {
      running.abort.abort();
      await running.finished;
    }
    for (const message of thread.messages ?? []) {
      await this.store.remove("ask-audit:" + message.message_id);
      await this.store.remove("ask-feedback:" + message.message_id);
    }
    await this.store.remove("ask-thread:" + id);
  }
  async feedback(id: string, rating: "up" | "down", reason?: string) {
    const threads = await this.store.list<Thread>("ask-thread:");
    const thread = threads.find((t) =>
      t.messages?.some((m) => m.message_id === id && m.role === "assistant"),
    );
    if (!thread) throw issue(404, "not_found");
    thread.messages!.find((m) => m.message_id === id)!.feedback = rating;
    await this.store.put("ask-thread:" + thread.thread_id, thread);
    await this.store.put("ask-feedback:" + id, {
      message_id: id,
      rating,
      reason,
    });
  }
  async close() {
    for (const running of this.active.values()) running.abort.abort();
    await Promise.all([...this.active.values()].map((r) => r.finished));
  }
  /** Called under the API's short mutation lock; stream runs after releasing it. */
  start(
    id: string,
    input: AskRequest,
    lang: string,
    reply: FastifyReply,
  ): Promise<void> {
    return (async () => {
      const thread = await this.get(id);
      if (this.active.has(id)) throw issue(409, "busy");
      if (!this.enabled()) throw issue(503, "upstream_unavailable");
      if (!input.text.trim() || input.text.length > 1000)
        throw issue(400, "validation_error");
      const profile = await this.store.get<BirthProfile>(
        "profile:" + thread.profile_id,
      );
      if (!profile) throw issue(409, "conflict");
      const me = (await this.store.get<Me>("me"))!;
      const { tryConsumeUsage } = await import("./limits");
      if (this.active.size >= this.dailyLimit)
        throw issue(429, "rate_limited");
      if (
        (await tryConsumeUsage(me.user_id, "ASK", this.dailyLimit)) == null
      )
        throw issue(429, "rate_limited");
      const quota = await this.quota();
      const subject = async (p: BirthProfile) => ({
        profile_id: p.profile_id,
        ...((await this.store.get("dossier-ref:" + p.profile_id)) ===
        p.chart_key
          ? { dossier_chart_key: p.chart_key }
          : {}),
        label: p.label,
        relation: p.relation,
        is_self: p.is_self,
        birth: p.birth,
        effective_tz: (
          (p.is_self ? me.current_place : p.current_place) ?? p.birth.place
        ).tz,
      });
      const own = await subject(profile);
      const profiles = await Promise.all(
        (await this.store.list<BirthProfile>("profile:"))
          .filter((p) => p.profile_id !== profile.profile_id)
          .map(subject),
      );
      const compatibilities = (
        await Promise.all(
          (await this.store.list<any>("compat:")).map(async (c) => {
            const ok = await Promise.all(
              c.context.people.map((p: any) =>
                this.store.get("profile:" + p.profile_id),
              ),
            );
            if (!ok.every(Boolean)) return null;
            return {
              compatibility_id: c.id,
              profile_a_id: c.context.people[0].profile_id,
              profile_b_id: c.context.people[1].profile_id,
              type: c.context.type,
              family_relation: c.context.family_relation ?? null,
            };
          }),
        )
      ).filter(Boolean) as {
        compatibility_id: string;
        profile_a_id: string;
        profile_b_id: string;
        type: string;
        family_relation: string | null;
      }[];
      if (
        input.context?.other_profile_id &&
        !profiles.some((p) => p.profile_id === input.context!.other_profile_id)
      )
        throw issue(400, "validation_error");
      if (
        input.context?.compatibility_id &&
        !compatibilities.some(
          (c) => c.compatibility_id === input.context!.compatibility_id,
        )
      )
        throw issue(400, "validation_error");
      const history: {
        role: string;
        text: string;
        calls?: unknown[];
      }[] = [];
      for (const m of (thread.messages ?? []).slice(-8)) {
        history.push({
          role: m.role,
          text: m.text,
          ...(m.role === "assistant"
            ? {
                calls:
                  (await this.store.get("ask-audit:" + m.message_id))?.calls ??
                  [],
              }
            : {}),
        });
      }
      const request = {
        thread_id: id,
        subject: own,
        profiles,
        compatibilities,
        text: input.text,
        context: input.context ?? {},
        lang,
        today: new Intl.DateTimeFormat("en-CA", {
          timeZone: own.effective_tz,
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        }).format(new Date()),
        history,
        llm_route: {},
      };
      const user: Message = {
        message_id: randomUUID(),
        role: "user",
        text: input.text,
        cards: [],
        links: [],
        status: "complete",
        created_at: stamp(),
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
      if (!thread.title) {
        const cut = input.text.trim().slice(0, 60);
        thread.title =
          input.text.trim().length > 60 && cut.includes(" ")
            ? cut.slice(0, cut.lastIndexOf(" "))
            : cut;
      }
      thread.updated_at = stamp();
      await this.store.put("ask-thread:" + id, thread);
      const persist = async () => {
        const saved = await this.store.get<Thread>("ask-thread:" + id);
        if (!saved) return;
        const feedback = new Map(
          saved.messages?.map((m) => [m.message_id, m.feedback]),
        );
        thread.messages = thread.messages?.map((m) => ({
          ...m,
          ...(feedback.get(m.message_id)
            ? { feedback: feedback.get(m.message_id) }
            : {}),
        }));
        await this.store.put("ask-thread:" + id, thread);
      };
      const abort = new AbortController();
      let finish!: () => void;
      const finished = new Promise<void>((resolve) => {
        finish = resolve;
      });
      this.active.set(id, { abort, finished });
      reply.hijack();
      reply.raw.writeHead(200, {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
      });
      const disconnected = () => abort.abort();
      reply.raw.on("close", disconnected);
      const send = (event: string, data: unknown) => {
        if (!abort.signal.aborted && !reply.raw.destroyed)
          reply.raw.write(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
      };
      let final: any,
        terminal = false;
      try {
        await this.runner(request, abort.signal, ({ event, data }) => {
          if (abort.signal.aborted) return;
          if (terminal) throw new Error("Event after terminal");
          if (event === "final") {
            if (
              data.message?.status !== "complete" ||
              data.message.text !== answer.text ||
              JSON.stringify(data.message.cards ?? []) !==
                JSON.stringify(answer.cards) ||
              JSON.stringify(data.message.links ?? []) !==
                JSON.stringify(answer.links)
            )
              throw new Error("Final mismatch");
            validate("Message", {
              ...answer,
              ...data.message,
              message_id: answer.message_id,
              role: "assistant",
              created_at: answer.created_at,
            });
            final = data;
            terminal = true;
            return;
          }
          if (event === "delta") {
            if (typeof data.text !== "string") throw new Error("Invalid delta");
            answer.text += data.text;
          } else if (event === "card") {
            validate("AskCard", data);
            answer.cards.push(data);
          } else if (event === "link") {
            if (
              typeof data.label !== "string" ||
              typeof data.route !== "string" ||
              !data.route.startsWith("/") ||
              data.route.startsWith("//")
            )
              throw new Error("Invalid link");
            answer.links.push(data);
          } else if (event === "error") {
            terminal = true;
            answer.status = "failed";
            send(
              "error",
              problem(
                503,
                data.code === "upstream_unavailable"
                  ? "upstream_unavailable"
                  : "generation_failed",
              ),
            );
            return;
          } else if (event === "status") {
            if (!["understanding", "computing", "writing"].includes(data.phase))
              throw new Error("Invalid status");
          } else throw new Error("Invalid event");
          send(event, data);
        });
        if (final && !abort.signal.aborted) {
          answer.status = "complete";
          await this.store.transaction(async () => {
            // Store only the specified audit fields. Never persist arbitrary bridge response fields.
            const audit = final.audit ?? {};
            await this.store.put("ask-audit:" + answer.message_id, {
              calls: audit.calls ?? [],
              plan: audit.plan,
              plan_drops: audit.plan_drops ?? [],
              validation: audit.validation,
              usage: audit.usage,
              answer_kind: final.message.answer_kind,
              lang,
            });
            await persist();
          });
          send("done", {
            message_id: answer.message_id,
            quota: await this.quota(),
          });
        } else if (!abort.signal.aborted && answer.status !== "failed")
          throw new Error("Missing final");
      } catch {
        if (!abort.signal.aborted) {
          answer.status = "failed";
          send("error", problem(503, "generation_failed"));
        }
      } finally {
        if (answer.status !== "complete") {
          const { refundUsageIfNoSettledSpend } = await import("./limits");
          await refundUsageIfNoSettledSpend(
            me.user_id,
            "ASK",
            new Date(answer.created_at ?? Date.now()),
          );
          await this.quota();
        }
        thread.updated_at = stamp();
        await persist();
        reply.raw.off("close", disconnected);
        reply.raw.end();
        this.active.delete(id);
        finish();
      }
    })();
  }
}
