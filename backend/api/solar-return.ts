/**
 * Solar Return API adapter — math only via solar_return_math_bridge.py.
 * Interpretation remains the pending-astrologer placeholder (no invented rules).
 */
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath, URL } from "node:url";
import { mapChart } from "../mock/scripts/chart";
import { validate } from "../../frontend/src/api/zod";
import type {
  BirthProfile,
  Lang,
  Place,
  SolarReturn,
} from "../../frontend/contracts/spec-types";

export const SOLAR_RETURN_PLACEHOLDER =
  "[Solar return reading — pending astrologer]";

export type SolarReturnMathInput = {
  natal_sun_longitude: number;
  year: number;
  latitude: number;
  longitude: number;
};

export type SolarReturnMathOutput = {
  return_utc: string;
  year: number;
  chart: unknown;
  interpretation?: string;
};

/** Spawn the Phase 1–2 Python math bridge (stdio JSON). */
export function runSolarReturnBridge(
  payload: SolarReturnMathInput,
): Promise<SolarReturnMathOutput> {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.env.PYTHON ?? "python",
      [
        "-X",
        "utf8",
        fileURLToPath(new URL("./solar_return_math_bridge.py", import.meta.url)),
      ],
      { windowsHide: true, stdio: ["pipe", "pipe", "pipe"] },
    );
    let output = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("Solar return calculation timed out"));
    }, 60000);
    child.stdout.on("data", (chunk) => {
      output += chunk;
      if (output.length > 4_000_000) child.kill();
    });
    child.stderr.resume();
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
            new Error(data.detail ?? data.message ?? "Solar return unavailable"),
            { statusCode: 503 },
          );
        resolve(data as SolarReturnMathOutput);
      } catch (error) {
        reject(error);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(payload));
  });
}

function natalSunLongitude(raw: any): number {
  const points = raw?.points;
  if (!Array.isArray(points))
    throw Object.assign(new Error("Natal chart unavailable"), {
      statusCode: 503,
    });
  const sun = points.find(
    (p: any) => p?.name === "Sun" || p?.body === "sun" || p?.body === "Sun",
  );
  if (typeof sun?.longitude !== "number" || !Number.isFinite(sun.longitude))
    throw Object.assign(new Error("Natal Sun unavailable"), {
      statusCode: 503,
    });
  return sun.longitude;
}

export type BuildSolarReturnArgs = {
  profile: BirthProfile;
  raw: unknown;
  year: number;
  place: Place;
  lang: Lang;
  generate?: (input: SolarReturnMathInput) => Promise<SolarReturnMathOutput>;
};

/** Compute SolarReturn (math + placeholder reading). No paid LLM. */
export async function buildSolarReturn(
  args: BuildSolarReturnArgs,
): Promise<SolarReturn> {
  const { profile, raw, year, place, lang } = args;
  const generate = args.generate ?? runSolarReturnBridge;
  const math = await generate({
    natal_sun_longitude: natalSunLongitude(raw),
    year,
    latitude: place.lat,
    longitude: place.lon,
  });
  const chartKey = createHash("sha256")
    .update(
      JSON.stringify([
        profile.profile_id,
        profile.chart_key,
        year,
        place.place_id,
        math.return_utc,
      ]),
    )
    .digest("hex")
    .slice(0, 32);
  const chart = mapChart(math.chart, profile.profile_id, chartKey);
  validate("ChartData", chart);
  const text = (math.interpretation ?? SOLAR_RETURN_PLACEHOLDER).trim()
    ? (math.interpretation ?? SOLAR_RETURN_PLACEHOLDER)
    : SOLAR_RETURN_PLACEHOLDER;
  const result: SolarReturn = {
    profile_id: profile.profile_id,
    year,
    return_utc: math.return_utc,
    place,
    chart,
    reading: {
      status: "ready",
      sections: [
        {
          key: "overview",
          title: lang === "tr" ? "Güneş dönüşü" : "Solar return",
          text,
        },
      ],
    },
  };
  validate("SolarReturn", result);
  return result;
}
