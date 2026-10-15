import React from "react";
import { render, screen, fireEvent } from "@testing-library/react-native";
import { ProfilePicker } from "../../src/design/components/ProfileSwitcher";
import { useApp } from "../../src/lib/state";
import i18n from "../../src/i18n";
const mockStorage = new Map<string, string>();
jest.mock("../../src/lib/state", () =>
  jest.requireActual("../../src/lib/state"),
);
jest.mock("expo-localization", () => ({
  getLocales: () => [{ languageCode: "en" }],
}));
jest.mock("../../src/lib/storage", () => ({
  privateStorage: {
    setItem: (k: string, v: string) => mockStorage.set(k, v),
    getItem: (k: string) => mockStorage.get(k),
    removeItem: (k: string) => mockStorage.delete(k),
  },
}));
jest.mock("lucide-react-native", () => ({
  Check: "Check",
  ChevronDown: "ChevronDown",
  ChevronRight: "ChevronRight",
  X: "X",
  Maximize2: "Maximize2",
}));
jest.mock("../../src/api/hooks", () => ({
  useProfiles: () => ({
    data: Array.from({ length: 6 }, (_, i) => ({
      profile_id: String(i),
      label: `Person ${i}`,
      is_self: i === 3,
      relation: "friend",
    })),
  }),
}));
beforeEach(async () => {
  mockStorage.clear();
  useApp.setState({ activeProfileId: null, recentProfileIds: ["4", "2"] });
  await i18n.changeLanguage("en");
});
test("six profiles are self-first then recent, checked selection excludes the other person", async () => {
  const select = jest.fn();
  await render(
    <ProfilePicker
      open
      selectedId="4"
      disabledId="2"
      onSelect={select}
      onClose={() => {}}
    />,
  );
  const rows = screen.getAllByRole("radio");
  expect(rows.map((r) => r.props.accessibilityLabel).slice(0, 3)).toEqual([
    "Person 3",
    "Person 4",
    "Person 2",
  ]);
  expect(screen.getByRole("radio", { name: "Person 4" })).toBeChecked();
  expect(screen.getByRole("radio", { name: "Person 2" })).toBeDisabled();
  await fireEvent.press(screen.getByRole("radio", { name: "Person 1" }));
  expect(select).toHaveBeenCalledWith("1");
  expect(useApp.getState().recentProfileIds[0]).toBe("1");
});
test("active profile and recent choices survive preference hydration", () => {
  useApp
    .getState()
    .update({ activeProfileId: "4", recentProfileIds: ["4", "2"] });
  useApp.setState({ activeProfileId: null, recentProfileIds: [] });
  useApp.getState().hydrate();
  expect(useApp.getState().activeProfileId).toBe("4");
  expect(useApp.getState().recentProfileIds).toEqual(["4", "2"]);
});
