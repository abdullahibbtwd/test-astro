import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath, URL } from "node:url";
import { mapChart } from "../mock-api/scripts/chart";
import { validate } from "../src/api/zod";
export type BirthInput = {
  date: string;
  time: string;
  place: { lat: number; lon: number; tz: string };
};
export async function bridge(input: unknown): Promise<any> {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.env.PYTHON ?? "python",
      [
        "-X",
        "utf8",
        fileURLToPath(new URL("./chart_bridge.py", import.meta.url)),
      ],
      { windowsHide: true, stdio: ["pipe", "pipe", "pipe"] },
    );
    let output = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("Chart calculation timed out"));
    }, 60000);
    child.stdout.on("data", (chunk) => {
      output += chunk;
      if (output.length > 4000000) child.kill();
    });
    child.stderr.resume(); // Never forward engine traces or personal inputs to clients/logs.
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      try {
        const data = JSON.parse(output);
        if (code || data.error)
          throw Object.assign(
            new Error(data.message ?? "Chart engine unavailable"),
            { statusCode: data.error === "validation_error" ? 400 : 503 },
          );
        resolve(data);
      } catch (error) {
        reject(error);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(input));
  });
}
export async function computeBirthChart(birth: BirthInput, profileId: string) {
  const raw = await bridge(birth);
  const chartKey = createHash("sha256")
    .update(
      JSON.stringify([
        raw.meta,
        birth.date,
        birth.time,
        birth.place.lat,
        birth.place.lon,
        raw.points,
        raw.sectors,
      ]),
    )
    .digest("hex")
    .slice(0, 32);
  const chart = mapChart(raw, profileId, chartKey);
  validate("ChartData", chart);
  return { raw, chart };
}
