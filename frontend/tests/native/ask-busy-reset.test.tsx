/**
 * Contract: ChatScreen send() always runs `setBusy(false)` in `finally`
 * (see frontend/src/features/ask/ChatScreen.tsx). Full ChatScreen render
 * pulls too many native shells for Jest; this documents the invariant and
 * asserts the source still contains the finally clear.
 */
import fs from "node:fs";
import path from "node:path";

test("ChatScreen send path clears busy in finally", () => {
  const src = fs.readFileSync(
    path.join(__dirname, "../../src/features/ask/ChatScreen.tsx"),
    "utf8",
  );
  expect(src).toMatch(/finally\s*\{[\s\S]*setBusy\(false\)/);
  expect(src).toMatch(/maxLength=\{1000\}/);
  expect(src).toMatch(/abort\.signal\.aborted \? "interrupted" : "failed"/);
});
