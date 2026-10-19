import { createHash } from "node:crypto";
import { createRemoteJWKSet, jwtVerify } from "jose";

export type JwtClaims = {
  sub: string;
  email: string;
};

const unauthorized = () =>
  Object.assign(new Error("Unauthorized"), { statusCode: 401 });

/**
 * Verify Supabase access tokens via JWKS (asymmetric).
 * Checks signature, issuer, expiry, and audience "authenticated".
 */
export class JwtAuth {
  readonly scope: string;
  private readonly jwks: ReturnType<typeof createRemoteJWKSet>;
  private readonly issuer: string;

  constructor(supabaseUrl: string, jwksUrl?: string) {
    const url = new URL(supabaseUrl);
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
    this.issuer = url.origin + "/auth/v1";
    const jwks = new URL(
      jwksUrl?.trim() || url.origin + "/auth/v1/.well-known/jwks.json",
    );
    if (jwks.origin !== url.origin)
      throw new Error("SUPABASE_JWKS_URL must be on the same project host");
    this.jwks = createRemoteJWKSet(jwks);
    this.scope = createHash("sha256")
      .update(url.origin + ":jwks")
      .digest("hex");
  }

  async verify(token: string): Promise<JwtClaims> {
    if (!token || token.length > 8192) throw unauthorized();
    try {
      const { payload } = await jwtVerify(token, this.jwks, {
        issuer: this.issuer,
        audience: "authenticated",
        clockTolerance: 5,
      });
      const sub = payload.sub;
      const email =
        typeof payload.email === "string" ? payload.email.trim().toLowerCase() : "";
      if (!sub || !/^[0-9a-f-]{36}$/i.test(sub) || !email.includes("@"))
        throw unauthorized();
      return { sub, email };
    } catch (error) {
      if ((error as { statusCode?: number }).statusCode === 401)
        throw error;
      throw unauthorized();
    }
  }
}
