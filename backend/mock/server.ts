import { buildApp } from "./app";
const app = buildApp();
await app.listen({
  port: Number(process.env.PORT ?? 4010),
  host: process.env.MOCK_HOST ?? "127.0.0.1",
});
console.log(
  "Mock API at http://127.0.0.1:4010/v1 — demo@example.com / 000000. Fixture date: 2026-09-29.",
);
