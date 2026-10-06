import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { InlineReading } from "../../src/features/chart/InlineReading";
import { useGenerated } from "../../src/api/jobs";
import i18n from "../../src/i18n";
import type { BirthProfile } from "../../contracts/spec-types";
let mockSaved = false;
let mockGuest = false;
jest.mock("../../src/api/resource", () => ({
  useApi: () => ({
    data: { sections: [{ key: "core_identity", status: "ready" }] },
  }),
}));
jest.mock("../../src/api/hooks", () => ({
  useReports: () => ({
    data: { pages: [{ items: mockSaved ? [{ profile_id: "p" }] : [] }] },
    isPending: false,
    hasNextPage: false,
    fetchNextPage: jest.fn(),
  }),
  useConfig: () => ({ data: { flags: { guestOnboarding: mockGuest } } }),
}));
jest.mock("../../src/api/jobs", () => ({
  useGenerated: jest.fn(() => ({ state: "loading", retry: jest.fn() })),
}));
const profile = { profile_id: "p", chart_key: "c" } as BirthProfile;
beforeEach(async () => {
  mockSaved = false;
  mockGuest = false;
  jest.clearAllMocks();
  await i18n.changeLanguage("en");
});
test("viewing Chart cannot generate a new natal reading until the user requests it", async () => {
  await render(<InlineReading profile={profile} />);
  expect(jest.mocked(useGenerated).mock.calls.at(-1)?.[3]).toBe(false);
  await fireEvent.press(
    screen.getByRole("button", { name: "Prepare my reading" }),
  );
  expect(jest.mocked(useGenerated).mock.calls.at(-1)?.[3]).toBe(true);
});
test("an existing saved reading is loaded without a prepare button", async () => {
  mockSaved = true;
  await render(<InlineReading profile={profile} />);
  expect(jest.mocked(useGenerated).mock.calls.at(-1)?.[3]).toBe(true);
  expect(
    screen.queryByRole("button", { name: "Prepare my reading" }),
  ).toBeNull();
});

test("a saved guest core reading is shown without requesting the rest of the natal chart", async () => {
  mockGuest = true;
  jest
    .mocked(useGenerated)
    .mockImplementation((key: any) =>
      key[0] === "natal-core"
        ? ({
            data: {
              key: "core_identity",
              title: "Core identity",
              text: "Saved guest reading.",
            },
          } as any)
        : ({ state: "loading", retry: jest.fn() } as any),
    );
  await render(<InlineReading profile={profile} />);
  expect(screen.getByText("Saved guest reading.")).toBeOnTheScreen();
  expect(
    jest
      .mocked(useGenerated)
      .mock.calls.find((call) => call[0][0] === "natal")?.[3],
  ).toBe(false);
  expect(
    screen.getByRole("button", { name: "Prepare my reading" }),
  ).toBeOnTheScreen();
});
