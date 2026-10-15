import React from "react";
import { render, screen, userEvent } from "@testing-library/react-native";
import * as Clipboard from "expo-clipboard";
import i18n from "../../src/i18n";
import { ReadingSection } from "../../src/features/profiles/ReadingScreen";
import { RouteError } from "../../src/design/components/RouteError";
jest.mock("@gorhom/bottom-sheet", () => ({
  BottomSheetModal: "BottomSheetModal",
  BottomSheetScrollView: "BottomSheetScrollView",
  BottomSheetBackdrop: "BottomSheetBackdrop",
}));
jest.mock("../../src/api/hooks", () => ({
  useConfig: () => ({ data: { flags: { askAstrology: true } } }),
}));
jest.mock("../../src/api/jobs", () => ({}));
jest.mock("expo-clipboard", () => ({
  setStringAsync: jest.fn().mockResolvedValue(undefined),
}));
const section = {
  key: "core_identity" as const,
  movement: 1 as const,
  house: null,
  title: "Fixture heading",
  text: "First fixture paragraph.\n\nSecond fixture paragraph.",
};
test("reading expands accessibly and copies the complete API section unchanged", async () => {
  await i18n.changeLanguage("en");
  const user = userEvent.setup();
  await render(<ReadingSection section={section} initialExpanded={false} />);
  expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
  await user.press(screen.getByRole("button", { name: section.title }));
  expect(
    screen.getByRole("button", { name: section.title, expanded: true }),
  ).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Copy" }));
  expect(Clipboard.setStringAsync).toHaveBeenCalledWith(
    `${section.title}\n\n${section.text}`,
  );
  expect(screen.getByRole("button", { name: "Copied" })).toBeOnTheScreen();
});
test("route recovery retries without exposing private exception text", async () => {
  await i18n.changeLanguage("en");
  const retry = jest.fn().mockResolvedValue(undefined),
    user = userEvent.setup();
  await render(
    <RouteError error={new Error("private birth data")} retry={retry} />,
  );
  expect(screen.queryByText("private birth data")).toBeNull();
  await user.press(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalledTimes(1);
});
