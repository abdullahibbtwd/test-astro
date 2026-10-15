import fs from "node:fs";
const tr = JSON.parse(fs.readFileSync("src/i18n/tr.json", "utf8"));
const app = JSON.parse(fs.readFileSync("app.json", "utf8"));
const failures = [];
if (tr["consent.birthData.placeholder"])
  failures.push("Legal consent is still a draft.");
if (app.expo.android.package.includes("example"))
  failures.push("Application identifier is a placeholder.");
if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
