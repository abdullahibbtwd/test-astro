import React from "react";
import { Text as MockText } from "react-native";
import { render, screen, userEvent } from "@testing-library/react-native";
import { router } from "expo-router";
import "../../src/i18n";
import AheadScreen from "../../src/features/forecast/AheadScreen";
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({
    view: "month",
    profile: "p",
    month: "2026-10",
    lens: "professional",
  }),
  router: { setParams: jest.fn(), push: jest.fn() },
}));
jest.mock("../../src/lib/state", () => ({
  useApp: (selector: any) => {
    const state = { activeProfileId: "p", theme: "light", update: jest.fn() };
    return selector ? selector(state) : state;
  },
}));
jest.mock("../../src/lib/storage", () => ({
  privateStorage: { getItem: () => '{"month":"personal"}', setItem: jest.fn() },
}));
jest.mock("../../src/api/client", () => ({ mockToday: "2026-10-03" }));
jest.mock("../../src/api/hooks", () => ({
  useProfiles: () => ({
    data: [
      { profile_id: "p", label: "Fictional", birth: { tz: "Europe/Sofia" } },
    ],
  }),
  useCatalogue: () => ({
    data: {
      lenses: { general: "General", personal: "Love", professional: "Work" },
    },
  }),
}));
jest.mock("../../src/features/calendar/CalendarScreen", () => () => null);
jest.mock("../../src/design/components/DateTimeField", () => ({
  DateTimeField: () => null,
}));
jest.mock("../../src/features/forecast/ForecastViews", () => ({
  MonthView: ({ profile, month, lens }: any) => (
    <MockText>{profile + "/" + month + "/" + lens}</MockText>
  ),
  DayView: () => null,
  YearView: () => null,
}));
test("saved forecast focus overrides remembered focus and remains changeable", async () => {
  const user = userEvent.setup();
  await render(<AheadScreen />);
  expect(screen.getByText("p/2026-10/professional")).toBeOnTheScreen();
  await user.press(screen.getByRole("radio", { name: "General" }));
  expect(router.setParams).toHaveBeenCalledWith({ lens: "general" });
});
