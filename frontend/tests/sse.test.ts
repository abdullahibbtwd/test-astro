import { test } from "node:test";
import assert from "node:assert/strict";
import { SSEParser, askContext } from "../src/api/sse";
test("SSE parser preserves unicode text across arbitrary framing and CRLF chunks", () => {
  const source =
    'event: delta\r\ndata: {"text":"İstanbul 🌙"}\r\n\r\nevent: done\ndata: {"message_id":"x"}\n\n';
  const parser = new SSEParser();
  const events = [...source].flatMap((char) => parser.push(char));
  assert.deepEqual(
    events.map((e) => e.event),
    ["delta", "done"],
  );
  assert.equal(JSON.parse(events[0]!.data).text, "İstanbul 🌙");
});
test("Ask context excludes all chart numbers and unknown request fields", () => {
  assert.deepEqual(
    askContext({
      date: "2026-10-01",
      place_id: "city",
      profile_id: "private",
      longitude: 123,
      chart: { points: [] },
      degree_in_sign: 14,
      other_profile_id: "person",
    }),
    { date: "2026-10-01", place_id: "city", other_profile_id: "person" },
  );
});
