import { spawn } from "node:child_process";
import { fileURLToPath, URL } from "node:url";
import { calendarFixtures } from "../mock-api/scripts/calendar";
import { fixture } from "../mock-api/fixtures";
import type { BirthProfile, Lang, Place } from "../contracts/spec-types";
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
    (["tr", "en"] as Lang[]).map((lang) => [
      lang,
      {
        ...calendarFixtures(
          fileURLToPath(new URL("../../", import.meta.url)),
          lang,
          fixture(`catalogue.${lang}`),
          source.labels,
          profile.profile_id,
          source,
        ),
        eventLabels: Object.fromEntries(
          Object.entries(source.labels.events).map(([id, labels]: any) => [
            id,
            labels[lang],
          ]),
        ),
      },
    ]),
  );
}
