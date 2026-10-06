import fs from "node:fs";
import { SupabaseAuth, type AuthConfig } from "./supabase-auth";
import path from "node:path";
import { fileURLToPath, URL } from "node:url";
import { buildLocalApp } from "./app";
const folder = fileURLToPath(new URL("../.local-data/", import.meta.url));
const authFile = path.join(folder, "auth-config.json");
const authConfig: (AuthConfig & { enabled: boolean }) | undefined =
  fs.existsSync(authFile)
    ? JSON.parse(fs.readFileSync(authFile, "utf8"))
    : undefined;
if (authConfig && typeof authConfig.enabled !== "boolean")
  throw new Error("Auth configuration must declare enabled");
const auth = authConfig?.enabled ? new SupabaseAuth(authConfig) : undefined;
const app = buildLocalApp({
  auth,
  dbPath: path.join(folder, "app.sqlite"),
  allowPaid: process.env.ASTRO_ALLOW_PAID === "1",
  progressiveReadings: process.env.ASTRO_PROGRESSIVE_READING === "1",
  guestOnboarding: process.env.ASTRO_GUEST_ONBOARDING === "1",
});
await app.listen({ host: "127.0.0.1", port: 4020 });
console.log(
  "Local real-chart API: http://127.0.0.1:4020/v1. " +
    (auth
      ? "Supabase owner authentication enabled. "
      : "Private preview login: demo@example.com / 000000. ") +
    "Paid generation " +
    (process.env.ASTRO_ALLOW_PAID === "1"
      ? "enabled under the shared US$20 cap"
      : "disabled") +
    ".",
);
for (const signal of ["SIGINT", "SIGTERM"] as const)
  process.on(signal, () => void app.close().then(() => process.exit(0)));
