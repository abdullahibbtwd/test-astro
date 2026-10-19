/**
 * Supabase Auth admin client using the backend secret key only.
 * Never import this into the mobile app.
 */
export class SupabaseAdmin {
  private readonly base: string;
  constructor(
    supabaseUrl: string,
    private secretKey: string,
    private transport: typeof fetch = fetch,
  ) {
    const url = new URL(supabaseUrl);
    if (
      url.protocol !== "https:" ||
      !/^[a-z]{20}\.supabase\.co$/.test(url.hostname)
    )
      throw new Error("Invalid Supabase project URL");
    if (!/^sb_secret_[A-Za-z0-9_-]+$/.test(secretKey))
      throw new Error("A Supabase secret key is required for admin deletes");
    this.base = url.origin + "/auth/v1";
  }

  /**
   * Delete an auth user. Idempotent: missing users (404) count as success.
   */
  async deleteUser(userId: string): Promise<void> {
    let response: Response;
    try {
      response = await this.transport(this.base + "/admin/users/" + userId, {
        method: "DELETE",
        headers: {
          apikey: this.secretKey,
          Authorization: "Bearer " + this.secretKey,
        },
        signal: AbortSignal.timeout(8000),
        redirect: "error",
      } as RequestInit);
    } catch {
      throw Object.assign(new Error("Auth provider unavailable"), {
        statusCode: 503,
      });
    }
    if (response.ok || response.status === 404) return;
    throw Object.assign(new Error("Auth provider delete failed"), {
      statusCode: response.status === 429 ? 429 : 503,
    });
  }
}
