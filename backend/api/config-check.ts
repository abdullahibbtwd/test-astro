/**
 * Startup / `npm run config:check` environment audit.
 * Reports variable NAMES only — never values.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  MAP_STYLE_ENV,
  validateMapStyleUrl,
} from "./map-style-config";

export type ConfigFinding = {
  level: "refuse" | "warn";
  /** Environment variable name(s) involved — never values. */
  names: string[];
  message: string;
};

export type ConfigCheckResult = {
  ok: boolean;
  findings: ConfigFinding[];
};

const DEFAULT_DB_USER = "astrology";
const DEFAULT_DB_PASSWORD = "astrology";

/** AUTH_ENABLED is on unless explicitly "0" (matches server.ts). */
export function authEnabled(env: NodeJS.ProcessEnv = process.env): boolean {
  return env.AUTH_ENABLED !== "0";
}

/**
 * Production-like: NODE_ENV=production (Dockerfile/Coolify) or explicit
 * ASTRO_PRODUCTION_LIKE=1 for staging that must fail closed the same way.
 */
export function isProductionLike(env: NodeJS.ProcessEnv = process.env): boolean {
  return env.NODE_ENV === "production" || env.ASTRO_PRODUCTION_LIKE === "1";
}

/**
 * Payments are enabled when ASTRO_PAYMENT_PROVIDER is set to a concrete
 * provider id (not empty / "unset"). Webhook secret rules apply only then.
 */
export function paymentsEnabled(env: NodeJS.ProcessEnv = process.env): boolean {
  const provider = (env.ASTRO_PAYMENT_PROVIDER ?? "").trim().toLowerCase();
  return provider !== "" && provider !== "unset";
}

/**
 * Minimal production-like env var NAMES required for config:check to pass
 * (payments off). Values are never recorded here — see docs/COOLIFY_SETUP.md.
 */
export const REQUIRED_PRODUCTION_ENV_NAMES = [
  "NODE_ENV",
  "DATABASE_URL",
  "AUTH_ENABLED",
  "SUPABASE_URL",
  "SUPABASE_SECRET_KEY",
  "ASTRO_DEMO_AUTH",
] as const;

/** Whether a Gemini key is available via env or ~/.gemini_key (existence only). */
export function geminiKeyPresent(
  env: NodeJS.ProcessEnv = process.env,
  home = os.homedir(),
): boolean {
  if (env.GEMINI_API_KEY?.trim() || env.GOOGLE_API_KEY?.trim()) return true;
  try {
    const file = path.join(home, ".gemini_key");
    return fs.existsSync(file) && fs.statSync(file).size > 0;
  } catch {
    return false;
  }
}

function parseUrlHost(raw: string | undefined): string | null {
  if (!raw?.trim()) return null;
  try {
    return new URL(raw).host.toLowerCase();
  } catch {
    return null;
  }
}

function databaseUsesDefaultCredentials(url: string): boolean {
  try {
    const parsed = new URL(url);
    return (
      decodeURIComponent(parsed.username) === DEFAULT_DB_USER &&
      decodeURIComponent(parsed.password) === DEFAULT_DB_PASSWORD
    );
  } catch {
    return /:\/\/astrology:astrology@/i.test(url);
  }
}

function databaseUsesLoopback(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    return host === "127.0.0.1" || host === "localhost";
  } catch {
    return /@127\.0\.0\.1(?:[:/]|$)/.test(url) || /@localhost(?:[:/]|$)/i.test(url);
  }
}

/**
 * Inspect `env` and return refuse/warn findings. Pure aside from optional
 * Gemini key-file existence check under `home`.
 */
export function checkConfig(
  env: NodeJS.ProcessEnv = process.env,
  home = os.homedir(),
): ConfigCheckResult {
  const findings: ConfigFinding[] = [];
  const refuse = (names: string[], message: string) =>
    findings.push({ level: "refuse", names, message });
  const warn = (names: string[], message: string) =>
    findings.push({ level: "warn", names, message });

  const productionLike = isProductionLike(env);

  if (productionLike && env.ASTRO_DEMO_AUTH === "1") {
    refuse(
      ["NODE_ENV", "ASTRO_DEMO_AUTH"],
      "ASTRO_DEMO_AUTH must not be enabled in production-like config",
    );
  }

  if (authEnabled(env) && !env.SUPABASE_URL?.trim()) {
    refuse(
      ["AUTH_ENABLED", "SUPABASE_URL"],
      "AUTH_ENABLED is on but SUPABASE_URL is missing",
    );
  }

  // Production must have a real issuer/JWKS source (derived from SUPABASE_URL).
  if (productionLike && !env.SUPABASE_URL?.trim()) {
    refuse(
      ["NODE_ENV", "SUPABASE_URL"],
      "Production-like config requires SUPABASE_URL (JWT issuer/JWKS source)",
    );
  }

  if (productionLike && !authEnabled(env)) {
    refuse(
      ["NODE_ENV", "AUTH_ENABLED"],
      "AUTH_ENABLED must not be 0 in production-like config",
    );
  }

  if (productionLike && env.ASTRO_RATE_LIMIT_DISABLED === "1") {
    refuse(
      ["NODE_ENV", "ASTRO_RATE_LIMIT_DISABLED"],
      "ASTRO_RATE_LIMIT_DISABLED must not be enabled in production-like config",
    );
  }

  // Webhook / provider secrets only when payments are explicitly enabled.
  if (productionLike && paymentsEnabled(env)) {
    const provider = (env.ASTRO_PAYMENT_PROVIDER ?? "").trim().toLowerCase();
    const webhookSecret = env.ASTRO_FAKE_PAYMENT_WEBHOOK_SECRET?.trim();
    if (provider === "fake") {
      if (!webhookSecret) {
        refuse(
          [
            "NODE_ENV",
            "ASTRO_PAYMENT_PROVIDER",
            "ASTRO_FAKE_PAYMENT_WEBHOOK_SECRET",
          ],
          "Payments enabled with fake provider requires ASTRO_FAKE_PAYMENT_WEBHOOK_SECRET",
        );
      } else if (webhookSecret === "fake-webhook-secret") {
        refuse(
          ["NODE_ENV", "ASTRO_FAKE_PAYMENT_WEBHOOK_SECRET"],
          "ASTRO_FAKE_PAYMENT_WEBHOOK_SECRET must not use the built-in default value",
        );
      }
    }
  }

  if (env.ASTRO_ALLOW_PAID === "1" && !geminiKeyPresent(env, home)) {
    refuse(
      ["ASTRO_ALLOW_PAID", "GEMINI_API_KEY", "GOOGLE_API_KEY"],
      "ASTRO_ALLOW_PAID=1 but no Gemini key was found (GEMINI_API_KEY, GOOGLE_API_KEY, or ~/.gemini_key)",
    );
  }

  if (env.OPENAI_BASE_URL !== undefined && env.OPENAI_BASE_URL !== "") {
    refuse(
      ["OPENAI_BASE_URL"],
      "OPENAI_BASE_URL is set; paid calls would refuse a non-default endpoint — leave it unset",
    );
  }

  if (
    env.GOOGLE_GENAI_USE_VERTEXAI !== undefined &&
    env.GOOGLE_GENAI_USE_VERTEXAI !== ""
  ) {
    refuse(
      ["GOOGLE_GENAI_USE_VERTEXAI"],
      "GOOGLE_GENAI_USE_VERTEXAI is set; paid calls would refuse",
    );
  }

  if (productionLike) {
    const db =
      env.DATABASE_URL?.trim() ||
      "postgres://astrology:astrology@127.0.0.1:5432/astrology";
    if (databaseUsesDefaultCredentials(db)) {
      refuse(
        ["DATABASE_URL", "NODE_ENV"],
        "In production, DATABASE_URL must not use the default astrology/astrology credentials",
      );
    }
    if (databaseUsesLoopback(db)) {
      refuse(
        ["DATABASE_URL", "NODE_ENV"],
        "In production, DATABASE_URL must not use host 127.0.0.1 (or localhost)",
      );
    }
  }

  if (env.AUTH_OWNER_EMAIL?.trim()) {
    warn(
      ["AUTH_OWNER_EMAIL"],
      "AUTH_OWNER_EMAIL is set — only that email can sign in",
    );
  }

  if (env.ASTRO_BUDGET_LIMIT !== undefined && env.ASTRO_BUDGET_LIMIT !== "") {
    warn(
      ["ASTRO_BUDGET_LIMIT"],
      "ASTRO_BUDGET_LIMIT is set (custom spending cap)",
    );
  }

  if (env.ASTRO_BUDGET_USER !== undefined && env.ASTRO_BUDGET_USER !== "") {
    warn(
      ["ASTRO_BUDGET_USER"],
      "ASTRO_BUDGET_USER is set (custom budget ledger partition)",
    );
  }

  if (authEnabled(env) && env.SUPABASE_URL?.trim() && !env.SUPABASE_SECRET_KEY?.trim()) {
    warn(
      ["SUPABASE_SECRET_KEY"],
      "SUPABASE_SECRET_KEY is missing — account deletion would not remove the login user",
    );
  }

  const supabaseHost = parseUrlHost(env.SUPABASE_URL);
  const jwksHost = parseUrlHost(env.SUPABASE_JWKS_URL);
  if (supabaseHost && jwksHost && supabaseHost !== jwksHost) {
    warn(
      ["SUPABASE_JWKS_URL", "SUPABASE_URL"],
      "SUPABASE_JWKS_URL host differs from SUPABASE_URL",
    );
  }

  for (const name of Object.values(MAP_STYLE_ENV)) {
    const message = validateMapStyleUrl(name, env[name]);
    if (message) refuse([name], message);
  }

  return {
    ok: !findings.some((f) => f.level === "refuse"),
    findings,
  };
}

/** Format findings for stderr/stdout. Names only — never values. */
export function formatConfigCheck(result: ConfigCheckResult): string {
  if (!result.findings.length) return "config:check ok (no refuse/warn findings)";
  return result.findings
    .map((f) => {
      const tag = f.level === "refuse" ? "REFUSE" : "WARN";
      return `[config:${tag}] ${f.message} (vars: ${f.names.join(", ")})`;
    })
    .join("\n");
}

/**
 * Run the check. On refuse: print clear message and exit 1 (or throw if
 * `throwOnRefuse`). Warnings print loudly but do not fail.
 */
export function runConfigCheck(options?: {
  env?: NodeJS.ProcessEnv;
  home?: string;
  throwOnRefuse?: boolean;
  log?: (line: string) => void;
}): ConfigCheckResult {
  const result = checkConfig(options?.env ?? process.env, options?.home);
  const log = options?.log ?? ((line: string) => console.error(line));
  const text = formatConfigCheck(result);
  if (result.findings.length) log(text);
  else if (!options?.throwOnRefuse) log(text);
  if (!result.ok) {
    const message =
      "Configuration check failed — refusing to start.\n" + text;
    if (options?.throwOnRefuse) throw new Error(message);
    console.error(message);
    process.exit(1);
  }
  return result;
}
