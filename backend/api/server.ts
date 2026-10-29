import fs from "node:fs";
import { SupabaseAuth, type AuthConfig } from "./supabase-auth";
import { JwtAuth } from "./jwt-auth";
import { SupabaseAdmin } from "./supabase-admin";
import path from "node:path";
import { buildLocalApp } from "./app";
import { dataDir } from "./data-dir";
import { migrateDeploy } from "./db";
import { runConfigCheck } from "./config-check";

if (!process.env.DATABASE_URL) {
  process.env.DATABASE_URL =
    "postgres://astrology:astrology@127.0.0.1:5432/astrology";
}

runConfigCheck({ throwOnRefuse: true });

await migrateDeploy();

const folder = dataDir();
const authFile = path.join(folder, "auth-config.json");
const authConfig: (AuthConfig & { enabled: boolean }) | undefined =
  fs.existsSync(authFile)
    ? JSON.parse(fs.readFileSync(authFile, "utf8"))
    : undefined;
if (authConfig && typeof authConfig.enabled !== "boolean")
  throw new Error("Auth configuration must declare enabled");
const fromEnv =
  process.env.SUPABASE_URL &&
  process.env.SUPABASE_PUBLISHABLE_KEY
    ? {
        enabled: process.env.AUTH_ENABLED !== "0",
        url: process.env.SUPABASE_URL,
        publishableKey: process.env.SUPABASE_PUBLISHABLE_KEY,
        ...(process.env.AUTH_OWNER_EMAIL
          ? { ownerEmail: process.env.AUTH_OWNER_EMAIL }
          : {}),
      }
    : undefined;
const resolved = fromEnv ?? authConfig;
const auth = resolved?.enabled ? new SupabaseAuth(resolved) : undefined;
const jwt =
  process.env.SUPABASE_URL && process.env.AUTH_ENABLED !== "0"
    ? new JwtAuth(process.env.SUPABASE_URL, process.env.SUPABASE_JWKS_URL)
    : undefined;
const admin =
  process.env.SUPABASE_URL &&
  process.env.SUPABASE_SECRET_KEY &&
  process.env.AUTH_ENABLED !== "0"
    ? new SupabaseAdmin(
        process.env.SUPABASE_URL,
        process.env.SUPABASE_SECRET_KEY,
      )
    : undefined;
const demoAuth = process.env.ASTRO_DEMO_AUTH === "1";
const app = await buildLocalApp({
  auth,
  jwt,
  admin,
  dbPath: path.join(folder, "app.sqlite"),
  allowPaid: process.env.ASTRO_ALLOW_PAID === "1",
  progressiveReadings: process.env.ASTRO_PROGRESSIVE_READING === "1",
  guestOnboarding: process.env.ASTRO_GUEST_ONBOARDING === "1",
});
const host = process.env.HOST ?? "127.0.0.1";
const port = Number(process.env.PORT ?? 4020);
await app.listen({ host, port });
console.log(
  `Local real-chart API: http://${host}:${port}/v1. ` +
    (jwt
      ? "Supabase JWT (JWKS) verification enabled. "
      : auth
        ? auth.multiUser
          ? "Supabase multi-user authentication enabled. "
          : "Supabase owner authentication enabled. "
        : demoAuth
          ? "Demo login enabled (any email / 000000). "
          : "Demo login disabled. ") +
    "PostgreSQL + Prisma. " +
    `DATA_DIR=${folder}. ` +
    "Paid generation " +
    (process.env.ASTRO_ALLOW_PAID === "1"
      ? "enabled under the shared US$20 cap"
      : "disabled") +
    ".",
);
for (const signal of ["SIGINT", "SIGTERM"] as const)
  process.on(signal, () => void app.close().then(() => process.exit(0)));
