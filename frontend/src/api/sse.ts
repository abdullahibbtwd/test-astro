export interface ServerEvent {
  event: string;
  data: string;
}
export class SSEParser {
  private buffer = "";
  push(chunk: string): ServerEvent[] {
    this.buffer = (this.buffer + chunk).replace(/\r\n/g, "\n");
    const output: ServerEvent[] = [];
    let end: number;
    while ((end = this.buffer.indexOf("\n\n")) >= 0) {
      const block = this.buffer.slice(0, end);
      this.buffer = this.buffer.slice(end + 2);
      let event = "message";
      const lines: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        if (line.startsWith("data:"))
          lines.push(line.slice(5).replace(/^ /, ""));
      }
      if (lines.length) output.push({ event, data: lines.join("\n") });
    }
    return output;
  }
}
export const contextKeys = [
  "date",
  "month",
  "place_id",
  "other_profile_id",
  "compatibility_id",
  "item_id",
  "activity",
  "section_key",
] as const;
export function askContext(input: Record<string, unknown>) {
  return Object.fromEntries(
    contextKeys.flatMap((key) =>
      typeof input[key] === "string" && input[key] ? [[key, input[key]]] : [],
    ),
  );
}
