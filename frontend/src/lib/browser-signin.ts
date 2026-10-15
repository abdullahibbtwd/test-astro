import { z } from "zod";
import { ApiError, request } from "../api/client";
import { validate } from "../api/zod";
import type { Session } from "../../contracts/spec-types";
const ticketSchema = z.object({
  flow_id: z.string().regex(/^[a-f0-9]{64}$/),
  poll_token: z.string().regex(/^[a-f0-9]{64}$/),
  expires_at: z.string().datetime(),
  url: z.string().url().optional(),
});
export type SignInTicket = z.infer<typeof ticketSchema>;
export async function startBrowserSignIn(
  provider: "email" | "google",
  email: string,
) {
  const ticket = ticketSchema.parse(
    await request(
      "POST",
      "/auth/browser/start",
      undefined,
      provider === "email" ? { provider, email: email.trim() } : { provider },
    ),
  );
  if (provider === "google") {
    const url = new URL(ticket.url ?? "");
    if (
      url.protocol !== "https:" ||
      url.hostname !== "zaswojdliqgmlrpzicvl.supabase.co" ||
      url.pathname !== "/auth/v1/authorize" ||
      url.username ||
      url.password ||
      url.port
    )
      throw new ApiError(503, "upstream_unavailable");
  }
  return ticket;
}
export async function pollBrowserSignIn(ticket: SignInTicket) {
  const result = z
    .object({
      status: z.enum(["waiting", "complete", "failed"]),
      session: z.unknown().optional(),
    })
    .parse(
      await request("POST", "/auth/browser/poll", undefined, {
        poll_token: ticket.poll_token,
      }),
    );
  if (result.status === "failed") throw new ApiError(401, "unauthorized");
  if (result.status !== "complete") return null;
  const session = validate<Session>("Session", result.session);
  return session;
}
export async function cancelBrowserSignIn(ticket: SignInTicket) {
  await request("POST", "/auth/browser/cancel", undefined, {
    poll_token: ticket.poll_token,
  }).catch(() => {});
}
