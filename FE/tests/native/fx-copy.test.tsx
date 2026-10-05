import PlaceScreen from "../../src/features/map/PlaceScreen";
import React from "react";
import { render, screen, cleanup } from "@testing-library/react-native";
import { StyleSheet } from "react-native";
import i18n from "../../src/i18n";
import CalendarScreen from "../../src/features/calendar/CalendarScreen";
import BestDaysScreen from "../../src/features/calendar/BestDaysScreen";
import BestDayScreen from "../../src/features/calendar/BestDayScreen";
import DayScreen from "../../src/features/calendar/DayScreen";
import {
  MonthView,
  YearView,
  DayView,
} from "../../src/features/forecast/ForecastViews";
import { MonthGrid } from "../../src/features/calendar/MonthGrid";

let mockLang = "en";
const mockParams: Record<string, string> = {
  date: "2026-10-21",
  activity: "business",
  month: "2026-10",
};

let mockEmptyReasons = false;
const mockRefetch = jest.fn();
jest.mock("../../src/lib/state", () => ({
  useApp: (select: any = (s: any) => s) =>
    select({ language: mockLang, theme: "light", update: jest.fn() }),
}));
jest.mock("expo-router", () => ({
  Stack: { Screen: () => null },
  useFocusEffect: (cb: any) => require("react").useEffect(cb, [cb]),
  useLocalSearchParams: () => mockParams,
  router: { push: jest.fn(), setParams: jest.fn() },
}));
jest.mock("../../src/api/hooks", () => ({
  useCatalogue: () => ({
    data: require(`../../mock-api/fixtures/catalogue.${mockLang}.json`),
  }),
  useActions: () => ({}),
}));
jest.mock("../../src/api/client", () => ({ mockToday: "2026-10-03" }));
jest.mock("../../src/features/shared/useProfile", () => ({
  useProfile: () => ({ id: "p", tz: "Europe/Sofia" }),
}));
jest.mock("../../src/lib/flags", () => ({
  useFlags: () => ({ dayScoreNumbers: true }),
}));
jest.mock("expo-notifications", () => ({ requestPermissionsAsync: jest.fn() }));
jest.mock("../../src/lib/notifications", () => ({
  prepareNotifications: jest.fn(),
  addReminder: jest.fn(),
}));
jest.mock("../../src/features/map/ReportSurface", () => ({
  ReportSurface: ({ children }: any) => children,
}));
jest.mock("../../src/features/map/selection", () => ({
  useMapSelection: { getState: () => ({ select: jest.fn() }) },
}));
jest.mock("../../src/api/resource", () => ({
  useApi: (_: string, schema: string) => {
    const names: Record<string, string> = {
      CalendarMonth: "month.2026-10",
      BestDaysOverview: "best-days",
      BestDayDetail: "best.business.2026-10-21",
      CalendarDayDetail: "day.2026-10-21",
      MonthForecast: "forecast-month.2026-10",
      YearForecast: "forecast-year",
      DayForecast: "forecast-day",
      PlaceReport: "place-report.gn-1819729",
    };

    const data = JSON.parse(
      JSON.stringify(
        require(`../../mock-api/fixtures/${names[schema]}.${mockLang}.json`),
      ),
    );
    if (schema === "BestDayDetail" && mockEmptyReasons)
      data.reasons = { positive: [], negative: [] };
    return { data, retry: mockRefetch, refetch: mockRefetch };
  },
}));
function nodes(node: any): any[] {
  return !node || typeof node !== "object"
    ? []
    : Array.isArray(node)
      ? node.flatMap(nodes)
      : [node, ...nodes(node.children)];
}
function renderedText(node: any): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(renderedText).join(" ");
  return node?.children ? renderedText(node.children) : "";
}
for (const lang of ["en", "tr"])
  test(`date screens have no raw ISO labels in ${lang}`, async () => {
    mockLang = lang;
    await i18n.changeLanguage(lang);
    for (const element of [
      <CalendarScreen />,
      <BestDaysScreen />,
      <BestDayScreen />,
      <DayScreen />,
      <DayView profile="p" date="2026-10-21" lens="general" />,
      <MonthView profile="p" month="2026-10" lens="general" />,
      <YearView profile="p" month="2026-10" lens="general" />,
    ]) {
      const view = await render(element);
      expect(renderedText(view.toJSON())).not.toMatch(
        /\b\d{4}-\d{2}(-\d{2})?\b/,
      );
      for (const pressable of nodes(view.toJSON()).filter((n) =>
        ["button", "radio", "checkbox", "tab"].includes(
          n.props?.accessibilityRole,
        ),
      )) {
        if (pressable.props.disabled) continue;
        expect(
          pressable.props.accessibilityLabel || renderedText(pressable),
        ).toBeTruthy();
      }
      await cleanup();
    }
  });
test("Best Day omits empty reason headings and retains its calendar action", async () => {
  mockLang = "en";
  await i18n.changeLanguage("en");
  mockEmptyReasons = true;
  await render(<BestDayScreen />);
  expect(screen.queryByText("What helps")).toBeNull();
  expect(
    screen.getByRole("button", { name: "See in calendar" }),
  ).toBeOnTheScreen();
  mockEmptyReasons = false;
});
test("mixed and quiet calendar days have no ring and a selected day has a fill", async () => {
  mockLang = "en";
  await i18n.changeLanguage("en");
  await render(
    <MonthGrid
      month="2026-10"
      selected="2026-10-03"
      today="2026-10-04"
      days={[
        { date: "2026-10-03", band: "mixed", label: "Mixed" },
        { date: "2026-10-04", band: "plus", label: "Favourable", icons: "●" },
      ]}
      onSelect={() => {}}
    />,
  );
  const mixed = screen.getByRole("button", { name: "3 October, Mixed" });
  expect(mixed).toBeSelected();
  expect(
    screen.getByRole("button", { name: "4 October, Favourable, Full moon" }),
  ).toBeOnTheScreen();
  const ring = nodes(screen.toJSON()).find(
    (n) =>
      n.props?.style && StyleSheet.flatten(n.props.style)?.borderRadius === 20,
  );
  expect(StyleSheet.flatten(ring.props.style).borderWidth).toBe(0);
});

test("place report spells out the country and gives every actionable row a name", async () => {
  mockLang = "en";
  await i18n.changeLanguage("en");
  const view = await render(<PlaceScreen />);
  const text = renderedText(view.toJSON());
  expect(text).not.toMatch(/\bCN\b/);
  for (const node of nodes(view.toJSON()).filter((n) =>
    ["button", "radio", "checkbox"].includes(n.props?.accessibilityRole),
  ))
    expect(node.props.accessibilityLabel || renderedText(node)).toBeTruthy();
});

test("Best Days activity renders its calendar dates, not an empty grid",async()=>{
 mockLang="en";mockParams.activity="business";await i18n.changeLanguage("en");await render(<BestDaysScreen/>);
 expect(screen.getAllByRole("button").filter(node=>/October|November|December/.test(node.props.accessibilityLabel ?? "")).length).toBeGreaterThan(20);
});
