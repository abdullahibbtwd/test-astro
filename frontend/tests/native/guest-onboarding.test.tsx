import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { router } from "expo-router";
import {
  GuestWelcomeScreen,
  GuestCoreScreen,
  OnboardingUnlockedScreen,
} from "../../src/features/onboarding/GuestOnboarding";
import { startGuestReading } from "../../src/lib/guest-onboarding";
import i18n from "../../src/i18n";
const mockUpdate = jest.fn();
const mockState: any = {
  theme: "light",
  language: "en",
  update: mockUpdate,
  editDraft: jest.fn(),
  draft: {},
};
let mockGuest = false;
let mockReading: any = {};
jest.mock("../../src/lib/state", () => ({
  useApp: Object.assign((select: any = (x: any) => x) => select(mockState), {
    getState: () => mockState,
  }),
}));
jest.mock("../../src/api/hooks", () => ({
  useConfig: () => ({ data: { links: {}, flags: {} } }),
}));
jest.mock("../../src/api/query", () => ({
  queryClient: { removeQueries: jest.fn() },
}));
jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useQuery: () => mockReading,
}));
jest.mock("../../src/lib/guest-onboarding", () => ({
  hasGuestReading: () => mockGuest,
  startGuestReading: jest.fn(async () => ({})),
  getGuestReading: jest.fn(),
  retryGuestClaim: jest.fn(),
  clearGuestReading: jest.fn(async () => {
    mockGuest = false;
  }),
}));
jest.mock("../../src/design/components/PlaceSearch", () => ({
  PlaceSearch: () => null,
}));
beforeEach(async () => {
  jest.clearAllMocks();
  mockGuest = false;
  mockState.guestClaimPending = false;
  mockState.draft = {
    date: "1988-12-28",
    time: "13:00",
    place: { place_id: "fixture", name: "Plovdiv" },
    consent: false,
  };
  mockReading = { data: undefined, error: null, refetch: jest.fn() };
  await i18n.changeLanguage("en");
});
test("welcome needs birth details and consent; opening it does not generate a reading", async () => {
  await render(<GuestWelcomeScreen />);
  const button = screen.getByRole("button", { name: "Find out who I am" });
  expect(button).toBeDisabled();
  expect(startGuestReading).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "English" })).toBeOnTheScreen();
  expect(screen.getByRole("link", { name: "Terms" })).toBeOnTheScreen();
  mockState.draft.consent = true;
  await screen.rerender(<GuestWelcomeScreen />);
  await fireEvent.press(
    screen.getByRole("button", { name: "Find out who I am" }),
  );
  expect(startGuestReading).toHaveBeenCalledWith(
    expect.objectContaining({
      birth_date: "1988-12-28",
      birth_time: "13:00",
      birth_place_id: "fixture",
      consent: true,
    }),
  );
  expect(router.push).toHaveBeenCalledWith("/(auth)/core");
});
test("the core result offers sign in with forty percent unlocked", async () => {
  mockGuest = true;
  mockReading.data = {
    status: "ready",
    section: { title: "Core identity", text: "A genuine generated reading." },
  };
  await render(<GuestCoreScreen />);
  expect(screen.getByText("A genuine generated reading.")).toBeOnTheScreen();
  expect(screen.getByRole("progressbar")).toHaveAccessibilityValue({
    min: 0,
    max: 100,
    now: 40,
  });
  await fireEvent.press(
    screen.getByRole("button", { name: "Sign in for more" }),
  );
  expect(router.push).toHaveBeenCalledWith("/(auth)/welcome?mode=signin");
});
test("missing guest sessions have a start-again route instead of an endless spinner", async () => {
  await render(<GuestCoreScreen />);
  await fireEvent.press(screen.getByRole("button", { name: "Start again" }));
  expect(router.replace).toHaveBeenCalledWith("/(auth)/welcome");
});
test("signing in unlocks the actual ahead, match and map routes", async () => {
  await render(<OnboardingUnlockedScreen />);
  expect(screen.getByRole("progressbar")).toHaveAccessibilityValue({
    min: 0,
    max: 100,
    now: 100,
  });
  for (const [label, path] of [
    ["What’s ahead", "/(tabs)/ahead"],
    ["Who’s for me", "/(tabs)/match"],
    ["Where to be", "/(tabs)/map"],
  ]) {
    await fireEvent.press(screen.getByRole("button", { name: label }));
    expect(router.replace).toHaveBeenCalledWith(path);
  }
  expect(mockUpdate).toHaveBeenCalledWith({ onboardingUnlockProfileId: null });
});
