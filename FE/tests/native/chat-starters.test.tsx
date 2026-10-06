import React from "react";
import { StyleSheet } from "react-native";
import { render, screen, fireEvent } from "@testing-library/react-native";
import ChatScreen from "../../src/features/ask/ChatScreen";
import { streamAnswer } from "../../src/api/ask-stream";
import i18n from "../../src/i18n";
const mockThread = { thread_id: "t", profile_id: "p", messages: [] as any[] };
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ threadId: "t" }),
  useFocusEffect: (cb: any) => require("react").useEffect(cb, [cb]),
  Stack: { Screen: () => null },
  router: {
    push: jest.fn(),
    back: jest.fn(),
    replace: jest.fn(),
    canGoBack: () => true,
  },
}));
jest.mock("@react-native-community/netinfo", () => ({
  useNetInfo: () => ({ isConnected: true }),
}));
jest.mock("../../src/api/hooks", () => ({
  useProfiles: () => ({ data: [{ profile_id: "p", label: "My chart" }] }),
  useMe: () => ({
    data: { ask_quota: { limit_per_day: 20, used_today: 0 } },
    refetch: jest.fn(),
  }),
}));
jest.mock("../../src/api/resource", () => ({
  useApi: () => ({ data: mockThread, isPending: false, refetch: jest.fn() }),
}));
jest.mock("../../src/api/client", () => ({
  request: jest.fn(),
  updateSessionMe: jest.fn(),
}));
jest.mock("../../src/api/ask-stream", () => ({ streamAnswer: jest.fn() }));
jest.mock("../../src/lib/storage", () => ({
  privateStorage: {
    getItem: () => null,
    setItem: jest.fn(),
    removeItem: jest.fn(),
  },
}));
jest.mock("../../src/lib/flags", () => ({
  useFlags: () => ({ askAstrology: true }),
}));
jest.mock("../../src/design/components/ProfileSwitcher", () => ({
  ProfilePicker: () => null,
  ProfileSwitcher: () => null,
}));
jest.mock("../../src/design/components/ActionSheet", () => ({
  ActionSheet: () => null,
}));
jest.mock("../../src/features/ask/AskCards", () => ({
  AskCardView: () => null,
}));
// A rendered label must have a net upright transform through its native ancestors.
// Counting only host nodes avoids counting React wrapper props twice.
function verticalDirection(node: any) {
  let direction = 1;
  for (let current = node; current; current = current.parent) {
    if (typeof current.type !== "string") continue;
    const style = StyleSheet.flatten(current.props.style);
    for (const transform of style?.transform ?? []) {
      if ("scale" in transform) direction *= transform.scale;
      if ("scaleY" in transform) direction *= transform.scaleY;
    }
  }
  return direction;
}
beforeEach(async () => {
  mockThread.messages = [];
  jest.clearAllMocks();
  await i18n.changeLanguage("en");
});
test("all empty-chat suggestions are upright and selecting one only fills the composer", async () => {
  await render(<ChatScreen />);
  for (let n = 1; n <= 6; n++) {
    const button = screen.getByRole("button", { name: i18n.t(`starter${n}`) });
    expect(verticalDirection(button)).toBe(1);
  }
  await fireEvent.press(
    screen.getByRole("button", { name: i18n.t("starter6") }),
  );
  expect(screen.getByLabelText("Your question")).toHaveDisplayValue(
    i18n.t("starter6"),
  );
  expect(streamAnswer).not.toHaveBeenCalled();
});
test("populated chat keeps messages upright and hides the empty-chat suggestions", async () => {
  mockThread.messages = [
    {
      message_id: "m1",
      role: "user",
      text: "My existing question",
      cards: [],
      links: [],
      status: "complete",
    },
  ];
  await render(<ChatScreen />);
  expect(verticalDirection(screen.getByText("My existing question"))).toBe(1);
  expect(screen.queryByRole("button", { name: i18n.t("starter1") })).toBeNull();
});
