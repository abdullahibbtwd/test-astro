import "dotenv/config";
import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "../src/generated/prisma/client.js";

const url =
  process.env.DATABASE_URL ??
  "postgres://astrology:astrology@127.0.0.1:5432/astrology";

const prisma = new PrismaClient({
  adapter: new PrismaPg({ connectionString: url }),
});

await prisma.systemConfig.upsert({
  where: { key: "prisma-smoke" },
  create: { key: "prisma-smoke", value: { ok: true, at: new Date().toISOString() } },
  update: { value: { ok: true, at: new Date().toISOString() } },
});
const row = await prisma.systemConfig.findUnique({ where: { key: "prisma-smoke" } });
if (!row) throw new Error("smoke query failed");
await prisma.systemConfig.delete({ where: { key: "prisma-smoke" } });
console.log("prisma smoke ok", { version: "7.10.1" });
await prisma.$disconnect();
