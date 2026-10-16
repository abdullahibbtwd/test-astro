import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "../src/generated/prisma/client.js";

let client: PrismaClient | undefined;

export function databaseUrl(): string {
  const url = process.env.DATABASE_URL;
  if (!url)
    throw new Error(
      "DATABASE_URL is required (SQLite store removed; use docker-compose.dev.yml Postgres)",
    );
  return url;
}

export function prisma(): PrismaClient {
  if (!client) {
    client = new PrismaClient({
      adapter: new PrismaPg({ connectionString: databaseUrl() }),
    });
  }
  return client;
}

export async function disconnectPrisma(): Promise<void> {
  if (!client) return;
  await client.$disconnect();
  client = undefined;
}

/** Apply pending migrations (API startup / tests). */
export async function migrateDeploy(): Promise<void> {
  const { execFile } = await import("node:child_process");
  const { promisify } = await import("node:util");
  const { fileURLToPath } = await import("node:url");
  const path = await import("node:path");
  const exec = promisify(execFile);
  const backendRoot = path.join(fileURLToPath(new URL(".", import.meta.url)), "..");
  await exec(
    process.execPath,
    [
      path.join(backendRoot, "node_modules/prisma/build/index.js"),
      "migrate",
      "deploy",
    ],
    {
      cwd: backendRoot,
      env: { ...process.env, DATABASE_URL: databaseUrl() },
    },
  );
}
