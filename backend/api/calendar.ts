import { spawn } from "node:child_process";
import { fileURLToPath, URL } from "node:url";
import { calendarFixtures } from "../mock/scripts/calendar";
import { defaults } from "./defaults";
import type { BirthProfile, Lang, Place } from "../../frontend/contracts/spec-types";
export async function computeCalendar(
  profile: BirthProfile,
  current: Place | null,
  start: string,
) {
  const source: any = await new Promise((resolve, reject) => {
    const child = spawn(
      process.env.PYTHON ?? "python",
      [
        "-X",
        "utf8",
        fileURLToPath(new URL("./calendar_bridge.py", import.meta.url)),
      ],
      { windowsHide: true, stdio: ["pipe", "pipe", "pipe"] },
    );
    let output = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("Calendar timeout"));
    }, 180000);
    child.stdout.on("data", (chunk) => {
      output += chunk;
      if (output.length > 8000000) child.kill();
    });
    child.stderr.resume();
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      try {
        const result = JSON.parse(output);
        if (code || result.error)
          throw new Error(result.error ?? "Calendar failed");
        resolve(result);
      } catch (error) {
        reject(error);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify({ profile, current, start }));
  });
  return Object.fromEntries(
    (["tr", "en"] as Lang[]).map((lang) => {
      // Drop in-memory helpers (label/active/good) — they are functions and
      // cannot be stored in Postgres JSON, which broke /home after compute.
      const { label: _label, active: _active, good: _good, ...fixtures } =
        calendarFixtures(
          fileURLToPath(new URL("../../", import.meta.url)),
          lang,
          defaults(`catalogue.${lang}`),
          source.labels,
          profile.profile_id,
          source,
        );
      return [
        lang,
        {
          ...fixtures,
          eventLabels: Object.fromEntries(
            Object.entries(source.labels.events).map(([id, labels]: any) => [
              id,
              labels[lang],
            ]),
          ),
        },
      ];
    }),
  );
}
