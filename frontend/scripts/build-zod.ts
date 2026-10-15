import fs from "node:fs";
import YAML from "yaml";

const api = YAML.parse(fs.readFileSync("openapi.yaml", "utf8"));
const names: string[] = Object.keys(api.components.schemas);
function expression(s: any): string {
  if (Array.isArray(s.type))
    return `z.union([${s.type.map((type: string) => expression({ ...s, type })).join(",")}])`;
  if (s === false) return "z.never()";
  if (s === true) return "z.unknown()";
  if (s.$ref) {
    const key = decodeURIComponent(s.$ref.split("/").at(-1));
    return `z.lazy(() => schemas[${JSON.stringify(key)}]!)`;
  }
  if ("const" in s) return `z.literal(${JSON.stringify(s.const)})`;
  if (s.enum)
    return s.enum.length === 1
      ? `z.literal(${JSON.stringify(s.enum[0])})`
      : `z.union([${s.enum.map((v: any) => `z.literal(${JSON.stringify(v)})`).join(",")}])`;
  const union = s.anyOf ?? s.oneOf;
  if (union)
    return union.length === 1
      ? expression(union[0])
      : `z.union([${union.map(expression).join(",")}])`;
  if (s.allOf)
    return s.allOf
      .map(expression)
      .reduce((a: string, b: string) => `z.intersection(${a},${b})`);
  if (s.type === "null") return "z.null()";
  if (s.type === "boolean") return "z.boolean()";
  if (s.type === "number" || s.type === "integer")
    return (
      "z.number()" +
      (s.type === "integer" ? ".int()" : "") +
      (s.minimum !== undefined ? `.min(${s.minimum})` : "") +
      (s.maximum !== undefined ? `.max(${s.maximum})` : "")
    );
  if (s.type === "string")
    return (
      "z.string()" +
      (s.minLength !== undefined ? `.min(${s.minLength})` : "") +
      (s.maxLength !== undefined ? `.max(${s.maxLength})` : "") +
      (s.pattern ? `.regex(new RegExp(${JSON.stringify(s.pattern)}))` : "")
    );
  if (s.type === "array") {
    let result = s.prefixItems
      ? `z.tuple([${s.prefixItems.map(expression).join(",")}])`
      : `z.array(${expression(s.items ?? {})})`;
    if (!s.prefixItems) {
      if (s.minItems !== undefined) result += `.min(${s.minItems})`;
      if (s.maxItems !== undefined) result += `.max(${s.maxItems})`;
    }
    return result;
  }
  if (s.type === "object" || s.properties) {
    const fields = Object.entries(s.properties ?? {})
      .map(
        ([k, v]) =>
          `${JSON.stringify(k)}:${expression(v)}${s.required?.includes(k) ? "" : ".optional()"}`,
      )
      .join(",");
    let result = `z.object({${fields}})`;
    if (typeof s.additionalProperties === "object")
      result += `.catchall(${expression(s.additionalProperties)})`;
    else if (s.additionalProperties !== false) result += ".passthrough()";
    else result += ".strict()";
    return result;
  }
  if (Object.keys(s).length === 0 || s.description) return "z.unknown()";
  throw new Error(`Unsupported schema: ${JSON.stringify(s)}`);
}
const source =
  `// Generated from openapi.yaml. Do not edit.\nimport { z } from 'zod';\nimport { validateContract } from '../contract-validation';\nexport const schemas: Record<string,z.ZodTypeAny> = {};\n` +
  names
    .map(
      (name) =>
        `schemas[${JSON.stringify(name)}] = ${expression(api.components.schemas[name])};`,
    )
    .join("\n") +
  `\nexport function validate<T = unknown>(name: string, value: unknown): T {\n const schema = schemas[name];\n if (!schema) throw new Error('Unknown contract schema: '+name);\n return validateContract<T>(name, value, schema);\n}\n`;
fs.mkdirSync("src/api/zod", { recursive: true });
fs.writeFileSync("src/api/zod/index.ts", source);
console.log(`Generated ${names.length} Zod schemas`);
