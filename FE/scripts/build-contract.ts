import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { createGenerator } from "ts-json-schema-generator";
import YAML from "yaml";
import { endpoints } from "./endpoints";

const blocks = [
  "FE_02_API_CONTRACT_SPEC.md",
  "FE_09_ASK_ASTROLOGY_SPEC.md",
].flatMap((file) =>
  [...fs.readFileSync(file, "utf8").matchAll(/```ts\r?\n([\s\S]*?)```/g)].map(
    (match) => match[1],
  ),
);
const supplement = `
export interface ReadingOutline {
  profile_id: string; chart_key: string; lang: Lang; title: string;
  parts: { movement: 1 | 2; title: string }[];
  sections: { key: NatalSection['key']; movement: 1 | 2; house: number | null; title: string;
    status: 'not_started' | 'generating' | 'ready' | 'failed'; access: 'open' | 'account_required' }[];
  big_three: { sun: Sign; moon: Sign; rising: Sign };
  accuracy: { score: number; n: number } | null;
}
export interface ReadingProgressInput { key: NatalSection['key']; event: 'opened' | 'finished' }
export interface ReadingFeedbackInput {
  profile_id: string; target: { type: 'reading' | 'section' | 'big_three'; key?: string };
  rating: 'spot_on' | 'partly' | 'not_me'; comment?: string;
}
export interface ReadingAccuracy { accuracy: { score: number; n: number } }

export interface EmailStart { email: string; lang: Lang }
export interface EmailVerify { email: string; code: string }
export interface AppleSignIn { identity_token: string; authorization_code: string; full_name?: string }
export interface GoogleSignIn { id_token: string }
export interface RefreshSession { refresh_token: string }
export type MeInput = Partial<Pick<Me,'display_name'|'language'|'theme'|'notification_prefs'|'consents'>> & { current_place_id?: string | null };
export type BirthProfilePatch = Partial<BirthProfileInput>;
export type PlaceOrNull = Place | null;
export interface CompatibilityInput { profile_a_id: string; profile_b_id: string; type: CompatType; family_relation?: FamilyRelation }
export interface CompatibilityPage { items: CompatibilitySummary[]; next_cursor: string | null }
export interface ThreadInput { profile_id: string }
// FE_02 names ThreadSummary without defining it. Proposal recorded in exploration report.
export type ThreadSummary = Omit<Thread, 'messages'>;
export interface ThreadPage { items: ThreadSummary[]; next_cursor: string | null }
export interface FeedbackInput { rating: 'up' | 'down'; reason?: string }
export interface ReportPage { items: ReportRef[]; next_cursor: string | null }
export interface JobAccepted { job: Job }
export interface GenerationAbsent { status: "absent"; absence: Absence }
export type CountryGeometry = GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, { iso2: string; name_tr: string; name_en: string }>;
export type RegionGeometry = GeoJSON.FeatureCollection<GeoJSON.Polygon | GeoJSON.MultiPolygon, { admin1_id: string; iso2: string; name_tr: string; name_en: string }>;
`;
fs.mkdirSync("contracts", { recursive: true });
fs.writeFileSync(
  "contracts/spec-types.ts",
  `// Generated from FE_02 and FE_09 by scripts/build-contract.ts.\nimport type * as GeoJSON from 'geojson';\n` +
    blocks
      .join("\n")
      .replace(
        "kind: 'natal_reading'",
        "kind: 'natal_section' | 'dossier' | 'natal_reading'",
      )
      .replace(
        "| 'upstream_unavailable' | 'internal';",
        "| 'upstream_unavailable' | 'internal' | 'busy' | 'account_required' | 'read_ahead_limit';",
      )
      .replace(
        "detail?: string;",
        "blocking_job_id?: string;\n  detail?: string;",
      )
      .replace(/^(type|interface) /gm, "export $1 ") +
    supplement,
);
const schema = createGenerator({
  path: path.resolve("contracts/spec-types.ts"),
  type: "*",
  tsconfig: path.resolve("tsconfig.contract.json"),
  expose: "all",
  skipTypeCheck: false,
  additionalProperties: true,
}).createSchema("*");
const names = Object.fromEntries(
  Object.keys(schema.definitions ?? {}).map((name) => [
    name,
    /^[a-zA-Z0-9._-]+$/.test(name)
      ? name
      : name.split("<")[0]!.replace(/[^a-zA-Z0-9._-]/g, "_") +
        "_" +
        createHash("sha256").update(name).digest("hex").slice(0, 12),
  ]),
);
const schemas = Object.fromEntries(
  Object.entries(schema.definitions ?? {}).map(([name, value]) => [
    names[name]!,
    value,
  ]),
);
function rewriteRefs(node: any): void {
  if (!node || typeof node !== "object") return;
  if (node.$ref?.startsWith("#/definitions/"))
    node.$ref =
      "#/components/schemas/" + names[decodeURIComponent(node.$ref.slice(14))];
  for (const value of Object.values(node)) rewriteRefs(value);
}
rewriteRefs(schemas);
// JSON Schema draft-07 tuple items become prefixItems in OpenAPI 3.1 (2020-12).
function migrate(node: any): void {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node.items)) {
    node.prefixItems = node.items;
    delete node.items;
    if (node.additionalItems === false) node.items = false;
    delete node.additionalItems;
  }
  for (const value of Object.values(node)) migrate(value);
}
migrate(schemas);
const ref = (name: string): any =>
  name.endsWith("[]")
    ? { type: "array", items: ref(name.slice(0, -2)) }
    : { $ref: `#/components/schemas/${name}` };
const paths: Record<string, any> = {};
const json = (s: any) => ({ "application/json": { schema: s } });
for (const route of endpoints) {
  const parameters: any[] = [...route.path.matchAll(/\{([^}]+)\}/g)].map(
    (m) => ({
      name: m[1],
      in: "path",
      required: true,
      schema: { type: "string" },
    }),
  );
  parameters.push({ name: "lang", in: "query", schema: ref("Lang") });
  for (const name of route.query ?? [])
    parameters.push({
      name,
      in: "query",
      required: ["q", "lat", "lon"].includes(name),
      schema:
        name === "limit"
          ? { type: "integer", minimum: 1, maximum: 50, default: 20 }
          : ["lat", "lon"].includes(name)
            ? {
                type: "number",
                minimum: name === "lat" ? -90 : -180,
                maximum: name === "lat" ? 90 : 180,
              }
            : name === "lens"
              ? ref("Lens")
              : { type: "string" },
    });
  if (route.method === "get")
    parameters.push(
      { name: "retry", in: "query", schema: { type: "boolean" } },
      { name: "If-None-Match", in: "header", schema: { type: "string" } },
    );
  if (route.method === "post")
    parameters.push({
      name: "Idempotency-Key",
      in: "header",
      schema: { type: "string", format: "uuid" },
    });
  const responses: any = {
    [String(route.status ?? 200)]: {
      description: route.stream ? "Server-sent events (FE_09 §4)" : "Success",
      ...(route.response
        ? { content: json(ref(route.response)) }
        : route.stream
          ? { content: { "text/event-stream": { schema: { type: "string" } } } }
          : {}),
    },
    default: {
      description: "RFC 7807 problem",
      content: { "application/problem+json": { schema: ref("Problem") } },
    },
  };
  if (
    route.path.endsWith("natal-reading") ||
    route.path.includes("/natal-reading/sections/") ||
    (route.path.startsWith("/compatibility") &&
      route.method !== "delete" &&
      (route.path.endsWith("{id}") || route.method === "post"))
  ) {
    responses["200"] = {
      description: "Reading or paused generation",
      content: json({ anyOf: [ref(route.response!), ref("GenerationAbsent")] }),
    };
    responses["409"] = {
      description: "Another reading is being prepared",
      content: { "application/problem+json": { schema: ref("Problem") } },
    };
  }
  if (route.generated)
    responses["202"] = {
      description: "Generation queued or running",
      content: json(ref("JobAccepted")),
    };
  if (route.method === "get")
    responses["304"] = { description: "Not modified" };
  for (const response of Object.values(responses) as any[])
    response.headers = {
      "X-Mock-Today": {
        schema: { type: "string" },
        description: "Development-only fixture date",
      },
      ETag: { schema: { type: "string" } },
      "Retry-After": { schema: { type: "string" } },
    };
  paths[route.path] ??= {};
  paths[route.path][route.method] = {
    operationId: `${route.method}_${route.path.replace(/[^a-zA-Z0-9]+/g, "_")}`,
    tags: [route.path.split("/")[1]],
    "x-backend-status": route.backend,
    parameters,
    responses,
    ...(route.body
      ? { requestBody: { required: true, content: json(ref(route.body)) } }
      : {}),
    ...(/^\/(auth|meta|geo)\//.test(route.path) ? { security: [] } : {}),
  };
}
const api = {
  openapi: "3.1.0",
  info: {
    title: "Astrology mobile API",
    version: "1.1.0",
    description:
      "FE_02 contract. Outstanding ambiguities are recorded in FE_EXPLORATION_REPORT.md.",
  },
  servers: [{ url: "http://localhost:4010/v1" }],
  security: [{ bearerAuth: [] }],
  paths,
  components: {
    securitySchemes: {
      bearerAuth: { type: "http", scheme: "bearer", bearerFormat: "JWT" },
    },
    schemas,
  },
};
fs.writeFileSync("openapi.yaml", YAML.stringify(api));
fs.writeFileSync("contracts/openapi.json", JSON.stringify(api, null, 2) + "\n");
console.log(
  `${endpoints.length} operations; ${Object.keys(schemas).length} schemas`,
);

fs.writeFileSync(
  "src/api/contract-version.ts",
  `// Generated by contract:build.\nexport const CONTRACT_VERSION = ${JSON.stringify(api.info.version)};\n`,
);
