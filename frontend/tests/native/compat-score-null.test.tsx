import React from "react";
import { render, screen } from "@testing-library/react-native";
import { isPresentCompatibilityScore } from "../../src/features/compatibility/CompatibilityScoreLine";
import type { Compatibility } from "../../contracts/spec-types";

jest.mock("../../src/features/profiles/ReadingScreen", () => {
  const ReactLocal = require("react");
  const { Text } = require("react-native");
  return {
    ReadingSection: ({
      section,
    }: {
      section: { title: string; text: string };
    }) =>
      ReactLocal.createElement(
        ReactLocal.Fragment,
        null,
        ReactLocal.createElement(Text, null, section.title),
        ReactLocal.createElement(Text, null, section.text),
      ),
  };
});

import { CompatibilityReadingBody } from "../../src/features/compatibility/CompatibilityReadingBody";

function readyReading(type: string): Extract<
  Compatibility["reading"],
  { status: "ready" }
> {
  return {
    status: "ready",
    title: `${type} reading`,
    sections: [
      { key: "overview", title: "Overview", text: `${type} prose body` },
      { key: "dynamics", title: "Dynamics", text: `${type} dynamics` },
    ],
  };
}

test("isPresentCompatibilityScore rejects null and empty labels", () => {
  expect(isPresentCompatibilityScore(null)).toBe(false);
  expect(isPresentCompatibilityScore({ value: 0, label: "" })).toBe(false);
  expect(isPresentCompatibilityScore({ value: Number.NaN, label: "x" })).toBe(
    false,
  );
  expect(isPresentCompatibilityScore({ value: 72, label: "Strong" })).toBe(
    true,
  );
});

test("CompatibilityScoreLine shows a real score and hides empty ones", async () => {
  await render(
    <CompatibilityReadingBody
      reading={readyReading("love")}
      score={{ value: 80, label: "A" }}
      scoreEnabled={true}
    />,
  );
  expect(screen.getByTestId("compatibility-score")).toHaveTextContent(
    "80 / 100 · A",
  );
  await render(
    <CompatibilityReadingBody
      reading={readyReading("love")}
      score={{ value: 0, label: "   " }}
      scoreEnabled={true}
    />,
  );
  expect(screen.queryByTestId("compatibility-score")).toBeNull();
});

for (const type of ["love", "work", "family"] as const) {
  test(`${type} reading body shows prose without score chrome`, async () => {
    await render(
      <CompatibilityReadingBody
        reading={readyReading(type)}
        score={null}
        scoreEnabled={false}
      />,
    );
    expect(screen.getByText(`${type} prose body`)).toBeOnTheScreen();
    expect(screen.getByText(`${type} dynamics`)).toBeOnTheScreen();
    expect(screen.queryByTestId("compatibility-score")).toBeNull();
    expect(screen.queryByText(/null/i)).toBeNull();
    expect(screen.queryByText(/0\s*%/)).toBeNull();
    expect(screen.queryByText(/\/ 100/)).toBeNull();
  });

  test(`${type} reading body still hides score when flag on and API score null`, async () => {
    await render(
      <CompatibilityReadingBody
        reading={readyReading(type)}
        score={null}
        scoreEnabled={true}
      />,
    );
    expect(screen.getByText(`${type} prose body`)).toBeOnTheScreen();
    expect(screen.queryByTestId("compatibility-score")).toBeNull();
  });
}
