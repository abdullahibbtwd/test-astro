import type { FastifyInstance, FastifyRequest } from "fastify";
import { Readable } from "node:stream";
import { prisma } from "../db";
import { applyPaymentEvent } from "./apply-event";
import { getPaymentProvider } from "./index";

type RawRequest = FastifyRequest & { rawBody?: string };

/**
 * POST /v1/webhooks/payments — store/provider webhook.
 * Signature verification + idempotent apply. No auth Bearer required.
 */
export function registerPaymentWebhook(app: FastifyInstance): void {
  app.addHook("preParsing", async (request, _reply, payload) => {
    if (!request.url.includes("/webhooks/payments")) return payload;
    const chunks: Buffer[] = [];
    for await (const chunk of payload) {
      chunks.push(typeof chunk === "string" ? Buffer.from(chunk) : chunk);
    }
    const raw = Buffer.concat(chunks);
    (request as RawRequest).rawBody = raw.toString("utf8");
    return Readable.from(raw);
  });

  app.post("/v1/webhooks/payments", async (request, reply) => {
    // Never default to "fake" — that bypassed the production guard in getPaymentProvider.
    const provider = getPaymentProvider();
    const raw =
      (request as RawRequest).rawBody ??
      (typeof request.body === "string"
        ? request.body
        : JSON.stringify(request.body ?? {}));

    const headers = request.headers as Record<
      string,
      string | string[] | undefined
    >;
    let ok = false;
    try {
      ok = await provider.verifyWebhookSignature(headers, raw);
    } catch {
      return reply.code(501).send({
        type: "about:blank",
        title: "Payment provider not configured",
        status: 501,
        code: "upstream_unavailable",
      });
    }
    if (!ok) {
      return reply.code(401).send({
        type: "about:blank",
        title: "Invalid webhook signature",
        status: 401,
        code: "unauthorized",
      });
    }

    let event;
    try {
      event = await provider.parseWebhookEvent(raw, headers);
    } catch {
      return reply.code(400).send({
        type: "about:blank",
        title: "Invalid webhook payload",
        status: 400,
        code: "validation_error",
      });
    }

    if (!event.event_id) {
      return reply.code(400).send({
        type: "about:blank",
        title: "Missing event_id",
        status: 400,
        code: "validation_error",
      });
    }

    const result = await applyPaymentEvent(prisma(), provider.id, event);
    return reply.code(200).send({
      ok: true,
      applied: result.applied,
      reason: "reason" in result ? result.reason : undefined,
      subscription_id:
        result.applied && "subscription_id" in result
          ? result.subscription_id
          : undefined,
    });
  });
}
