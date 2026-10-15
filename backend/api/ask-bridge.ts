import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, URL } from "node:url";

export type AskEvent = { event: string; data: any };
export type AskRunner = (
  request: Record<string, unknown>,
  signal: AbortSignal,
  emit: (event: AskEvent) => void,
) => Promise<void>;
export const askRoot = () =>
  path.resolve(
    process.env.ASTRO_PA_ROOT ??
      fileURLToPath(new URL("../../", import.meta.url)),
  );
export function askBackendReady() {
  const root = askRoot();
  return (
    process.env.ASTRO_ASK_ENABLED === "1" &&
    ["ask_bridge.py", "astrologist/pa_engine.py"].every((p) =>
      fs.existsSync(path.join(root, p)),
    )
  );
}
/** PA_04 JSONL protocol. No prompts, birth details or provider stderr enter server logs. */
export const runAskBridge: AskRunner = (request, signal, emit) =>
  new Promise((resolve, reject) => {
    if (signal.aborted) return reject(new Error("AskInterrupted"));
    const child = spawn(
      process.env.PYTHON ?? "python",
      [
        "-X",
        "utf8",
        fileURLToPath(new URL("./ask_bridge.py", import.meta.url)),
      ],
      {
        cwd: askRoot(),
        windowsHide: true,
        stdio: ["pipe", "pipe", "pipe"],
      },
    );
    let buffer = "",
      bytes = 0,
      terminal = false,
      failure: Error | undefined;
    const fail = (message: string) => {
      failure ??= new Error(message);
      child.kill();
    };
    const abort = () => fail("AskInterrupted");
    signal.addEventListener("abort", abort, { once: true });
    const timer = setTimeout(() => fail("AskTimeout"), 90_000);
    child.stderr.resume();
    child.stdout.setEncoding("utf8");
    const line = (value: string) => {
      if (!value.trim()) return;
      if (terminal) throw new Error("Unexpected event after terminal event");
      const event = JSON.parse(value) as AskEvent;
      if (
        !["status", "delta", "card", "link", "final", "error"].includes(
          event.event,
        ) ||
        !event.data
      )
        throw new Error("Invalid event");
      emit(event);
      terminal = event.event === "final" || event.event === "error";
    };
    child.stdout.on("data", (chunk: string) => {
      bytes += Buffer.byteLength(chunk);
      if (bytes > 2_000_000) return fail("AskOutputLimit");
      buffer += chunk;
      try {
        let end: number;
        while ((end = buffer.indexOf("\n")) >= 0) {
          const value = buffer.slice(0, end);
          buffer = buffer.slice(end + 1);
          line(value);
        }
      } catch {
        fail("AskInvalidStream");
      }
    });
    child.stdin.on("error", () => fail("AskInputFailed"));
    child.on("error", () => {
      failure ??= new Error("AskUnavailable");
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      signal.removeEventListener("abort", abort);
      try {
        if (!failure && buffer.trim()) line(buffer);
      } catch {
        failure = new Error("AskInvalidStream");
      }
      if (failure || code !== 0 || !terminal)
        reject(failure ?? new Error("AskIncomplete"));
      else resolve();
    });
    child.stdin.end(JSON.stringify({ op: "turn", request }));
  });
