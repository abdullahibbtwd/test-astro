import type { FastifyInstance } from "fastify";
import { prisma } from "../db";
import { computeEntitlements } from "../entitlements";

/**
 * GET /v1/billing/status — subscription snapshot for Account management UI.
 * Auth: Bearer (same Session / JWT as the rest of /v1).
 */
export function registerBillingStatus(
  app: FastifyInstance,
  resolveTenant: (token: string) => Promise<string>,
): void {
  app.get("/v1/billing/status", async (request, reply) => {
    const token = String(request.headers.authorization ?? "").replace(
      /^Bearer /,
      "",
    );
    if (!token) {
      return reply.code(401).send({
        type: "about:blank",
        title: "Unauthorized",
        status: 401,
        code: "unauthorized",
      });
    }
    let userId: string;
    try {
      userId = await resolveTenant(token);
    } catch {
      return reply.code(401).send({
        type: "about:blank",
        title: "Unauthorized",
        status: 401,
        code: "unauthorized",
      });
    }
    const computed = await computeEntitlements(prisma(), userId);
    return reply.send({
      plan_id: computed.plan_id,
      free_launch: computed.free_launch,
      entitlements: computed.entitlements,
      subscription: computed.subscription,
    });
  });
}
