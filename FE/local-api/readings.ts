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
    | "forecast_bridge.py"
    | "compatibility_bridge.py"
    | "map_bridge.py",
  payload: unknown,
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
    child.stderr.resume();
    child.on("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      try {
        const data = JSON.parse(output);
        if (code || data.error) throw new Error(data.error ?? "ReadingFailed");
        resolve(data);
      } catch (error) {
        reject(error);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(payload));
  });
}
