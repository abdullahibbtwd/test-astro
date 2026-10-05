import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { InlineReading } from "../../src/features/chart/InlineReading";
import { useGenerated } from "../../src/api/jobs";
import i18n from "../../src/i18n";
import type { BirthProfile } from "../../contracts/spec-types";
let mockSaved = false;
jest.mock("../../src/api/hooks", () => ({
  useReports: () => ({
    data: { pages: [{ items: mockSaved ? [{ profile_id: "p" }] : [] }] },
    isPending: false,
    hasNextPage: false,
    fetchNextPage: jest.fn(),
  }),
  useConfig: () => ({ data: { flags: {} } }),
}));
jest.mock("../../src/api/jobs", () => ({
  useGenerated: jest.fn(() => ({ state: "loading", retry: jest.fn() })),
}));
const profile = { profile_id: "p", chart_key: "c" } as BirthProfile;
beforeEach(async () => {
  mockSaved = false;
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
