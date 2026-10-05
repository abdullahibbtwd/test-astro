import { z } from "zod";
import { reportContractViolation } from "../lib/telemetry";
export class ContractError extends Error {
  constructor() {
    super("Contract validation failed");
  }
}
const collection = z
  .object({
    type: z.literal("FeatureCollection"),
    features: z.array(z.unknown()),
  })
  .passthrough();
export function validateContract<T>(
  name: string,
  value: unknown,
  schema: z.ZodTypeAny,
  strict = (typeof __DEV__ !== "undefined"
    ? __DEV__
    : process.env.NODE_ENV !== "production") ||
    process.env.EXPO_PUBLIC_STRICT_CONTRACT === "1",
): T {
  const envelope =
    name.startsWith("FeatureCollection") ||
    ["CountryGeometry", "RegionGeometry"].includes(name)
      ? collection
      : name === "AcgLines"
        ? z
            .object({
              chart_key: z.string(),
              lines: collection,
              parans: collection,
            })
            .passthrough()
        : name === "AcgHeat"
          ? z
              .object({
                chart_key: z.string(),
                goal: z.string(),
                grid_step_deg: z.number(),
                points: z.array(z.unknown()),
              })
              .passthrough()
          : undefined;
  if (envelope) {
    const started = performance.now();
    envelope.parse(value);
    if (typeof __DEV__ !== "undefined" && __DEV__)
      console.info(
        "Contract envelope validation ms",
        name,
        Math.round((performance.now() - started) * 100) / 100,
      );
    return value as T;
  }
  if (strict) return schema.parse(value) as T;
  const result = schema.safeParse(value);
  if (result.success) return result.data as T;
  reportContractViolation(name, result.error.issues);
  // Probe only the top-level type; incomplete objects remain renderable in release.
  const probe = schema.safeParse(Array.isArray(value) ? [] : {});
  const topLevelWrong =
    !probe.success &&
    probe.error.issues.some(
      (issue) => issue.path.length === 0 && issue.code === "invalid_type",
    );
  if (!value || typeof value !== "object" || topLevelWrong)
    throw new ContractError();
  return value as T;
}
