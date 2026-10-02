import path from "node:path";
import { fileURLToPath, URL } from "node:url";
import { buildLocalApp } from "./app";
const folder = fileURLToPath(new URL("../.local-data/", import.meta.url));
const app = buildLocalApp({
  dbPath: path.join(folder, "app.sqlite"),
  allowPaid: process.env.ASTRO_ALLOW_PAID === "1",
});
await app.listen({ host: "127.0.0.1", port: 4020 });
console.log(
  "Local real-chart API: http://127.0.0.1:4020/v1. Private preview login: demo@example.com / 000000. Paid generation " +
    (process.env.ASTRO_ALLOW_PAID === "1"
      ? "enabled under the shared US$20 cap"
      : "disabled") +
    ".",
);
for (const signal of ["SIGINT", "SIGTERM"] as const)
  process.on(signal, () => void app.close().then(() => process.exit(0)));
