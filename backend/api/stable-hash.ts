import { createHash } from "node:crypto";

/** Order-stable JSON so Postgres JSONB round-trips do not break identity hashes. */
export function stableStringify(value: unknown): string {
  if (value === null || typeof value !== "object")
    return JSON.stringify(value);
  if (Array.isArray(value))
    return `[${value.map(stableStringify).join(",")}]`;
  const obj = value as Record<string, unknown>;
  return `{${Object.keys(obj)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${stableStringify(obj[key])}`)
    .join(",")}}`;
}

export const stableHash = (value: unknown) =>
  createHash("sha256").update(stableStringify(value)).digest("hex");
