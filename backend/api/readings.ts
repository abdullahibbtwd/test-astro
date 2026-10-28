import { spawn } from "node:child_process";
import { fileURLToPath, URL } from "node:url";
export function generateReading(
  chart: unknown,
  profile_id: string,
  chart_key: string,
): Promise<any> {
  return runReadingBridge("reading_bridge.py", {
    chart,
    profile_id,
    chart_key,
  });
}
export function runReadingBridge(
  script:
    | "reading_bridge.py"
    | "reading_section_bridge.py"
    | "forecast_bridge.py"
    | "compatibility_bridge.py"
    | "map_bridge.py"
    | "map_reading_bridge.py",
  payload: unknown,
  onStage?: (stage: string) => void,
): Promise<any> {
  return new Promise((resolve, reject) => {
    const child = spawn(
      process.env.PYTHON ?? "python",
      ["-X", "utf8", fileURLToPath(new URL(`./${script}`, import.meta.url))],
      { windowsHide: true, stdio: ["pipe", "pipe", "pipe"] },
    );
    let output = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error("ReadingTimeout"));
    }, 20 * 60000);
    child.stdout.on("data", (chunk) => {
      output += chunk;
      if (output.length > 4000000) child.kill();
    });
    let stageBuffer = "";
    child.stderr.on("data", (chunk) => {
      if (!onStage) return;
      stageBuffer = (stageBuffer + String(chunk)).slice(-4096);
      let end: number;
      while ((end = stageBuffer.indexOf("\n")) >= 0) {
        const line = stageBuffer.slice(0, end).trim();
        stageBuffer = stageBuffer.slice(end + 1);
        if (/^ONB_STAGE:(reading|synthesis|validate|translation)$/.test(line))
          onStage(line.slice(10));
      }
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      try {
        const data = JSON.parse(output);
        if (code || data.error) {
          const detail =
            typeof data.detail === "string" && data.detail.trim()
              ? data.detail.trim()
              : typeof data.error === "string"
                ? data.error
                : "ReadingFailed";
          throw new Error(detail);
        }
        resolve(data);
      } catch (error) {
        reject(error);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(payload));
  });
}
