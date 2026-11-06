import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { test } from "node:test";

const ts = createRequire(import.meta.url)("typescript") as typeof import("typescript");

type Messages = Record<string, string>;

const readMessages = (locale: "en" | "tr"): Messages =>
  JSON.parse(fs.readFileSync(`src/i18n/${locale}.json`, "utf8")) as Messages;

const interpolationTokens = (value: string): string[] =>
  [...value.matchAll(/\{\{?([A-Za-z0-9_]+)\}?\}/g)]
    .map((match) => match[1]!)
    .sort();

test("English and Turkish message keys and interpolation tokens match", () => {
  const en = readMessages("en");
  const tr = readMessages("tr");

  assert.deepEqual(Object.keys(tr).sort(), Object.keys(en).sort());
  for (const key of Object.keys(en)) {
    assert.deepEqual(
      interpolationTokens(tr[key]!),
      interpolationTokens(en[key]!),
      `Interpolation tokens differ for "${key}"`,
    );
  }
});

const UI_STRING_PROPS = new Set([
  "accessibilityHint",
  "accessibilityLabel",
  "description",
  "helperText",
  "label",
  "message",
  "placeholder",
  "subtitle",
  "title",
]);

const SCAN_ROOTS = ["app", "src/features"];
const EXCLUDED_FILES = new Set([
  "app/design-system-gallery.tsx",
  "app/gallery.tsx",
  "src/features/account/ExportAudit.tsx",
  "src/features/account/Gallery.tsx",
  "src/features/account/ListAudit.tsx",
]);

const isVisibleText = (value: string): boolean => {
  const normalized = value.replace(/\s+/g, " ").trim();
  if (["English", "Türkçe"].includes(normalized)) return false;
  if (
    /GeoNames|Natural Earth|WorldClim|Swiss Ephemeris|SIL Open Font License/u.test(
      normalized,
    )
  ) {
    return false;
  }
  return /\p{L}/u.test(normalized) && !/^[A-Z0-9_]+$/.test(normalized);
};

const lineAndColumn = (
  sourceFile: import("typescript").SourceFile,
  node: import("typescript").Node,
): string => {
  const location = sourceFile.getLineAndCharacterOfPosition(node.getStart());
  return `${location.line + 1}:${location.character + 1}`;
};

const collectTsxFiles = (root: string): string[] => {
  const files: string[] = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const entryPath = path.join(root, entry.name);
    if (entry.isDirectory()) files.push(...collectTsxFiles(entryPath));
    else if (entry.isFile() && entry.name.endsWith(".tsx")) files.push(entryPath);
  }
  return files;
};

test("app and feature TSX contain no hardcoded user-visible strings", () => {
  const failures: string[] = [];
  const files = SCAN_ROOTS.flatMap(collectTsxFiles).filter(
    (file) => !EXCLUDED_FILES.has(file),
  );

  for (const file of files) {
    const source = fs.readFileSync(file, "utf8");
    const sourceFile = ts.createSourceFile(
      file,
      source,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );

    const report = (node: import("typescript").Node, value: string) => {
      if (isVisibleText(value)) {
        failures.push(
          `${file}:${lineAndColumn(sourceFile, node)} ${JSON.stringify(value.trim())}`,
        );
      }
    };

    const inspectLiteralBranches = (
      expression: import("typescript").Expression,
    ): void => {
      if (
        ts.isStringLiteral(expression) ||
        ts.isNoSubstitutionTemplateLiteral(expression)
      ) {
        report(expression, expression.text);
      } else if (ts.isConditionalExpression(expression)) {
        inspectLiteralBranches(expression.whenTrue);
        inspectLiteralBranches(expression.whenFalse);
      } else if (ts.isParenthesizedExpression(expression)) {
        inspectLiteralBranches(expression.expression);
      } else if (
        ts.isBinaryExpression(expression) &&
        expression.operatorToken.kind === ts.SyntaxKind.PlusToken
      ) {
        inspectLiteralBranches(expression.left);
        inspectLiteralBranches(expression.right);
      }
    };

    const visit = (node: import("typescript").Node): void => {
      if (ts.isJsxText(node)) report(node, node.text);

      if (
        ts.isJsxAttribute(node) &&
        ts.isIdentifier(node.name) &&
        UI_STRING_PROPS.has(node.name.text)
      ) {
        if (node.initializer && ts.isStringLiteral(node.initializer)) {
          report(node.initializer, node.initializer.text);
        } else if (
          node.initializer &&
          ts.isJsxExpression(node.initializer) &&
          node.initializer.expression
        ) {
          inspectLiteralBranches(node.initializer.expression);
        }
      }

      if (
        ts.isJsxExpression(node) &&
        node.parent &&
        (ts.isJsxElement(node.parent) || ts.isJsxFragment(node.parent)) &&
        node.expression
      ) {
        inspectLiteralBranches(node.expression);
      }

      ts.forEachChild(node, visit);
    };
    visit(sourceFile);
  }

  assert.deepEqual(
    failures,
    [],
    `Hardcoded user-visible strings found:\n${failures.join("\n")}`,
  );
});

test("reviewed Turkish button and tab labels stay within length budgets", () => {
  const tr = readMessages("tr");
  const tabKeys = [
    "home",
    "chart",
    "ahead",
    "match",
    "map",
    "today",
    "month",
    "year",
    "list",
    "timeline",
  ];
  const buttonKeys = [
    "continue",
    "getStarted",
    "emailContinue",
    "googleContinue",
    "appleContinue",
    "sendCode",
    "allow",
    "openCharts",
    "createReport",
    "findPlaces",
    "downloadFullReport",
    "prepareMyReading",
  ];

  for (const key of tabKeys) {
    assert.ok(tr[key]!.length <= 12, `TR tab "${key}" exceeds 12 characters`);
  }
  for (const key of buttonKeys) {
    assert.ok(
      tr[key]!.length <= 30,
      `TR button "${key}" exceeds 30 characters`,
    );
  }
});
