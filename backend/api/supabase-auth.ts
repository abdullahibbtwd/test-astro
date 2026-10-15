import { createHash } from "node:crypto";
import { z } from "zod";
export interface AuthConfig {
  url: string;
  publishableKey: string;
  /** When set, only this email may sign in (legacy single-operator mode). Omit for multi-user. */
  ownerEmail?: string;
}
const failure = (statusCode = 503) =>
  Object.assign(new Error("Authentication unavailable"), { statusCode });
const userSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  email_confirmed_at: z.string().datetime().nullable(),
});
const tokensSchema = z.object({
  access_token: z.string().min(1),
  refresh_token: z.string().min(1),
  expires_in: z.number().int().positive().max(86400),
});
export type VerifiedSession = z.infer<typeof tokensSchema> & {
  user: z.infer<typeof userSchema>;
};
/** Public-key Auth client. No admin credentials; identity is verified by Supabase, never decoded locally. */
export class SupabaseAuth {
  readonly scope: string;
  readonly ownerEmail: string | undefined;
  readonly multiUser: boolean;
  private readonly base: string;
  constructor(
    private config: AuthConfig,
    private transport: typeof fetch = fetch,
  ) {
    const url = new URL(config.url);
    if (
      url.protocol !== "https:" ||
      !/^[a-z]{20}\.supabase\.co$/.test(url.hostname) ||
      url.pathname !== "/" ||
      url.search ||
      url.hash ||
      url.username ||
      url.password ||
      url.port
    )
      throw new Error("Invalid Supabase project URL");
    if (!/^sb_publishable_[A-Za-z0-9_-]+$/.test(config.publishableKey))
      throw new Error("A Supabase publishable key is required");
    this.ownerEmail = config.ownerEmail
      ? z.string().email().parse(config.ownerEmail.trim().toLowerCase())
      : undefined;
    this.multiUser = !this.ownerEmail;
    this.base = url.origin + "/auth/v1";
    this.scope = createHash("sha256")
      .update(
        this.ownerEmail
          ? url.origin + ":" + this.ownerEmail
          : url.origin + ":multi",
      )
      .digest("hex");
  }
  private email(value: string) {
    const email = value.trim().toLowerCase();
    if (this.ownerEmail && email !== this.ownerEmail) throw failure(403);
    return email;
  }
  private async call(path: string, body?: unknown, access?: string) {
    let response: Response;
    try {
      response = await this.transport(this.base + path, {
        method: body === undefined ? "GET" : "POST",
        headers: {
          apikey: this.config.publishableKey,
          "Content-Type": "application/json",
          ...(access ? { Authorization: "Bearer " + access } : {}),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        signal: AbortSignal.timeout(8000),
        redirect: "error",
      } as RequestInit);
    } catch {
      throw failure();
    }
    if (!response.ok)
      throw failure(
        response.status === 429 ? 429 : response.status >= 500 ? 503 : 401,
      );
    if (response.status === 204) return null;
    try {
      return await response.json();
    } catch {
      throw failure();
    }
  }
  async user(access: string) {
    const parsed = userSchema.safeParse(
      await this.call("/user", undefined, access),
    );
    if (!parsed.success) throw failure(403);
    this.email(parsed.data.email);
    if (!parsed.data.email_confirmed_at) throw failure(403);
    return parsed.data;
  }
  private async verified(data: unknown): Promise<VerifiedSession> {
    const tokens = tokensSchema.safeParse(data);
    if (!tokens.success) throw failure();
    const user = await this.user(tokens.data.access_token);
    return { ...tokens.data, user };
  }
  async startEmailLink(email: string, redirect: string, challenge: string) {
    await this.call("/otp?redirect_to=" + encodeURIComponent(redirect), {
      email: this.email(email),
      create_user: true,
      code_challenge: challenge,
      code_challenge_method: "s256",
    });
  }
  googleUrl(redirect: string, challenge: string) {
    const url = new URL(this.base + "/authorize");
    const params: Record<string, string> = {
      provider: "google",
      redirect_to: redirect,
      code_challenge: challenge,
      code_challenge_method: "s256",
      scopes: "openid email profile",
      prompt: "select_account",
    };
    if (this.ownerEmail) params.login_hint = this.ownerEmail;
    url.search = new URLSearchParams(params).toString();
    return url.toString();
  }
  async exchangeCode(code: string, verifier: string) {
    return this.verified(
      await this.call("/token?grant_type=pkce", {
        auth_code: code,
        code_verifier: verifier,
      }),
    );
  }
  async startEmail(email: string) {
    await this.call("/otp", { email: this.email(email), create_user: true });
  }
  async verify(email: string, code: string) {
    this.email(email);
    if (!/^\d{6}$/.test(code)) throw failure(400);
    return this.verified(
      await this.call("/verify", {
        email: this.email(email),
        token: code,
        type: "email",
      }),
    );
  }
  async provider(provider: "google" | "apple", token: string) {
    return this.verified(
      await this.call("/token?grant_type=id_token", {
        provider,
        id_token: token,
      }),
    );
  }
  async refresh(token: string) {
    return this.verified(
      await this.call("/token?grant_type=refresh_token", {
        refresh_token: token,
      }),
    );
  }
  async logout(access: string) {
    await this.call("/logout?scope=local", {}, access);
  }
}
