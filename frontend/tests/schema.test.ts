import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import SwaggerParser from "@apidevtools/swagger-parser";
import { endpoints } from "../scripts/endpoints";
test("OpenAPI is valid and every operation has a unique operationId", async () => {
  const api = await SwaggerParser.validate("openapi.yaml");
  const ids = new Set<string>();
  let count = 0;
  for (const methods of Object.values(api.paths ?? {}))
    for (const op of Object.values(methods ?? {}) as any[]) {
      assert.ok(op.operationId);
      assert.ok(!ids.has(op.operationId));
      ids.add(op.operationId);
      count++;
    }
  assert.equal(count, endpoints.length);
});
test("chrome keys match in Turkish and English; no masked terms", () => {
  const tr = JSON.parse(fs.readFileSync("src/i18n/tr.json", "utf8"));
  const en = JSON.parse(fs.readFileSync("src/i18n/en.json", "utf8"));
  assert.deepEqual(Object.keys(tr).sort(), Object.keys(en).sort());
  for (const copy of [tr, en])
    assert.ok(
      !/modern|classical|traditional|ottoman|hellenistic|placidus|whole sign|triplicity|domicile|profection|planetary hour|tam burç|yücelim/iu.test(
        JSON.stringify(copy),
      ),
    );
});

test("TR and EN chrome do not contain Windows encoding corruption", () => {
  for (const lang of ["tr", "en"]) {
    const text = fs.readFileSync(`src/i18n/${lang}.json`, "utf8");
    assert.ok(
      !/[\u0400-\u04ff\ufffd]/u.test(text),
      `${lang} contains corrupted encoding`,
    );
  }
});
