import { createHash, randomBytes } from "node:crypto";
import type { SupabaseAuth, VerifiedSession } from "./supabase-auth";
const error = (statusCode: number) =>
  Object.assign(new Error("Sign-in unavailable"), { statusCode });
const digest = (value: string) =>
  createHash("sha256").update(value).digest("hex");
const callback = "http://127.0.0.1:4020/v1/auth/browser/callback/";
type Pending<T> = {
  id: string;
  verifier: string;
  pollHash: string;
  expires: number;
  busy?: boolean;
  failed?: boolean;
  session?: T;
};
/** Private emulator bridge: transient PKCE secrets and sessions never enter URLs or the disk store. */
export class BrowserSignIn<T> {
  private flows = new Map<string, Pending<T>>();
  private lastEmail = 0;
  constructor(
    private auth: SupabaseAuth,
    private issue: (value: VerifiedSession) => T | Promise<T>,
    private now = Date.now,
  ) {}
  expire() {
    this.prune();
  }
  private prune() {
    for (const [id, f] of this.flows)
      if (f.expires <= this.now()) this.flows.delete(id);
  }
  async start(input: { provider: "email" | "google"; email?: string }) {
    this.prune();
    if (this.flows.size >= 5) throw error(429);
    if (
      input.provider === "email" &&
      this.lastEmail &&
      this.now() - this.lastEmail < 60000
    )
      throw error(429);
    const id = randomBytes(32).toString("hex"),
      poll = randomBytes(32).toString("hex"),
      verifier = randomBytes(48).toString("base64url");
    const challenge = createHash("sha256").update(verifier).digest("base64url");
    const flow: Pending<T> = {
      id,
      verifier,
      pollHash: digest(poll),
      expires: this.now() + 600000,
    };
    this.flows.set(id, flow);
    try {
      let url: string | undefined;
      if (input.provider === "email") {
        await this.auth.startEmailLink(
          input.email ?? "",
          callback + id,
          challenge,
        );
        this.lastEmail = this.now();
      } else url = this.auth.googleUrl(callback + id, challenge);
      return {
        flow_id: id,
        poll_token: poll,
        expires_at: new Date(flow.expires).toISOString(),
        ...(url ? { url } : {}),
      };
    } catch (e) {
      this.flows.delete(id);
      throw e;
    }
  }
  async complete(id: string, code: string) {
    this.prune();
    const flow = this.flows.get(id);
    if (!flow) throw error(401);
    if (flow.busy || flow.session || flow.failed) throw error(409);
    flow.busy = true;
    try {
      const verified = await this.auth.exchangeCode(code, flow.verifier);
      if (!this.flows.has(id) || flow.expires <= this.now()) throw error(401);
      flow.session = await this.issue(verified);
      flow.expires = this.now() + 60000;
    } catch (e) {
      flow.failed = true;
      throw e;
    } finally {
      flow.verifier = "";
      flow.busy = false;
    }
  }
  fail(id: string) {
    const flow = this.flows.get(id);
    if (flow && !flow.session) flow.failed = true;
  }
  private find(token: string) {
    this.prune();
    const hash = digest(token);
    const flow = [...this.flows.values()].find((f) => f.pollHash === hash);
    if (!flow) throw error(401);
    return flow;
  }
  poll(token: string) {
    const f = this.find(token);
    return f.failed
      ? { status: "failed" as const }
      : f.session
        ? { status: "complete" as const, session: f.session }
        : { status: "waiting" as const };
  }
  cancel(token: string) {
    const f = this.find(token);
    this.flows.delete(f.id);
  }
  clear() {
    this.flows.clear();
  }
}
