import React from "react";
import { render } from "@testing-library/react-native";
import { DayView } from "../../src/features/forecast/ForecastViews";
import DayScreen from "../../src/features/calendar/DayScreen";
import PlaceScreen from "../../src/features/map/PlaceScreen";
import "../../src/i18n";
let mockData: any;
jest.mock("../../src/api/resource", () => ({
  useApi: () => ({ data: mockData, retry: jest.fn(), refetch: jest.fn() }),
}));
jest.mock("../../src/api/hooks", () => ({
  useCatalogue: () => ({
    data: require("../../mock-api/fixtures/catalogue.en.json"),
  }),
}));
jest.mock("../../src/lib/flags", () => ({ useFlags: () => ({}) }));
jest.mock("../../src/features/shared/useProfile", () => ({
  useProfile: () => ({ id: "p" }),
}));
jest.mock("../../src/features/map/ReportSurface", () => ({
  ReportSurface: ({ children }: any) => children,
}));
jest.mock("../../src/features/map/selection", () => ({
  useMapSelection: { getState: () => ({ select: jest.fn() }) },
}));
jest.mock("expo-router", () => ({
  useFocusEffect: (callback: () => void) =>
    require("react").useEffect(callback, [callback]),
  Stack: { Screen: () => null },
  useLocalSearchParams: () => ({ date: "2026-09-29", placeId: "gn-1819729" }),
  router: { push: jest.fn(), setParams: jest.fn() },
}));
test("Today tolerates unknown goal, body and band enums", async () => {
  mockData = JSON.parse(
    JSON.stringify(require("../../mock-api/fixtures/forecast-day.en.json")),
  );
  mockData.tone = "future";
  mockData.areas.love.band = "future";
  mockData.areas.future = {
    band: "future",
    label: "Future area",
    score_10: 5,
    drivers: [],
  };
  mockData.retrograde.push("future");
  await render(<DayView profile="p" date="2026-09-29" lens="general" />);
});
test("calendar day tolerates unknown body and tone", async () => {
  mockData = JSON.parse(
    JSON.stringify(require("../../mock-api/fixtures/day.2026-09-29.en.json")),
  );
  mockData.tone = "future";
  mockData.retrograde.push("future");
  await render(<DayScreen />);
});
test("place report tolerates unknown goal and band", async () => {
  mockData = JSON.parse(
    JSON.stringify(
      require("../../mock-api/fixtures/place-report.gn-1819729.en.json"),
    ),
  );
  mockData.cards[0].band = "future";
  mockData.goal_scores.future = { band: "future", label: "Future band" };
  await render(<PlaceScreen />);
});
