import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { BrowserSignIn } from "./browser-signin";
import type { SupabaseAuth, VerifiedSession } from "./supabase-auth";
import type { Session } from "../contracts/spec-types";
const startSchema = z.discriminatedUnion("provider", [
  z
    .object({
      provider: z.literal("email"),
      email: z.string().trim().email().max(254),
    })
    .strict(),
  z.object({ provider: z.literal("google") }).strict(),
]);
const pollSchema = z
  .object({ poll_token: z.string().regex(/^[a-f0-9]{64}$/) })
  .strict();
const invalid = () =>
  Object.assign(new Error("Invalid sign-in request"), { statusCode: 400 });
function parse<T>(schema: z.ZodType<T>, input: unknown): T {
  const result = schema.safeParse(input);
  if (!result.success) throw invalid();
  return result.data;
}
export function registerBrowserSignIn(
  app: FastifyInstance,
  auth: SupabaseAuth,
  issue: (value: VerifiedSession) => Session | Promise<Session>,
) {
  const flows = new BrowserSignIn(auth, issue);
  const sweep = setInterval(() => flows.expire(), 30000);
  sweep.unref();
  app.addHook("onClose", async () => {
    clearInterval(sweep);
    flows.clear();
  });
  app.addHook("onRequest", async (request, reply) => {
    if (!request.url.startsWith("/v1/auth/browser/")) return;
    reply
      .header("Cache-Control", "no-store")
      .header("Referrer-Policy", "no-referrer")
      .header("X-Content-Type-Options", "nosniff");
    if (request.method === "POST" && request.headers.origin)
      throw Object.assign(
        new Error("Browser origins cannot claim app sessions"),
        { statusCode: 403 },
      );
  });
  app.post("/v1/auth/browser/start", async (request) =>
    flows.start(parse(startSchema, request.body)),
  );
  app.post("/v1/auth/browser/poll", async (request) =>
    flows.poll(parse(pollSchema, request.body).poll_token),
  );
  app.post("/v1/auth/browser/cancel", async (request, reply) => {
    flows.cancel(parse(pollSchema, request.body).poll_token);
    return reply.code(204).send();
  });
  app.get("/v1/auth/browser/callback/:id", async (request, reply) => {
    const { id } = parse(
      z.object({ id: z.string().regex(/^[a-f0-9]{64}$/) }),
      request.params,
    );
    const q = parse(
      z
        .object({
          code: z.string().uuid().optional(),
          error: z.string().max(200).optional(),
        })
        .passthrough(),
      request.query,
    );
    let ok = false;
    try {
      if (q.error || !q.code) {
        flows.fail(id);
      } else {
        await flows.complete(id, q.code);
        ok = true;
      }
    } catch {
      /* No provider messages or URL values reach the page. */
    }
    reply.header(
      "Content-Security-Policy",
      "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
    );
    return reply
      .type("text/html")
      .code(ok ? 200 : 400)
      .send(
        `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Astrology sign-in</title><body style="font-family:system-ui;max-width:38rem;margin:12vh auto;padding:24px;background:#f8f5ef;color:#262523"><h1>${ok ? "You are signed in" : "Sign-in could not be completed"}</h1><p>${ok ? "Return to the Astrology app in the Android emulator to continue. You can close this tab." : "Return to the app and request a new sign-in link. Use the email address configured for this private preview."}</p></body></html>`,
      );
  });
}
