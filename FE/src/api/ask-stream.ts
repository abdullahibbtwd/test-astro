import { fetch } from "expo/fetch";
import { apiBase, accessToken, refreshSession, ApiError } from "./client";
import { SSEParser, askContext } from "./sse";
import { useApp } from "../lib/state";
import type { AskContext } from "../../contracts/spec-types";
export async function streamAnswer(
  thread: string,
  text: string,
  context: AskContext,
  signal: AbortSignal,
  onEvent: (event: string, data: unknown) => void,
) {
  const send = () =>
    fetch(
      `${apiBase}/ask/threads/${encodeURIComponent(thread)}/messages?lang=${useApp.getState().language}`,
      {
        method: "POST",
        signal,
        headers: {
          Accept: "text/event-stream",
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken()}`,
        },
        body: JSON.stringify({
          text,
          context: askContext(context as Record<string, unknown>),
        }),
      },
    );
  let response = await send();
  if (response.status === 401 && (await refreshSession()))
    response = await send();
  if (!response.ok) {
    const problem = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      problem?.code ?? "upstream_unavailable",
      Number(response.headers.get("Retry-After")) || 0,
      problem ?? undefined,
    );
  }
  if (!response.body) throw new Error("Missing stream");
  const reader = response.body.getReader(),
    decoder = new TextDecoder(),
    parser = new SSEParser();
  let done = false;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      for (const event of parser.push(
        decoder.decode(chunk.value, { stream: true }),
      )) {
        const data: unknown = JSON.parse(event.data);
        onEvent(event.event, data);
        if (event.event === "done") done = true;
      }
    }
    if (!done && !signal.aborted) throw new Error("Interrupted stream");
  } finally {
    if (!done) await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
