import React from "react";
import { render, screen, userEvent } from "@testing-library/react-native";
import i18n from "../../src/i18n";
import BrowserSignInScreen from "../../src/features/account/BrowserSignInScreen";
import {
  startBrowserSignIn,
  cancelBrowserSignIn,
} from "../../src/lib/browser-signin";
jest.mock("expo-router", () => ({
  router: { replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: () => ({ provider: "email" }),
}));
jest.mock("../../src/lib/browser-signin", () => ({
  startBrowserSignIn: jest.fn(),
  pollBrowserSignIn: jest.fn().mockResolvedValue(null),
  cancelBrowserSignIn: jest.fn().mockResolvedValue(undefined),
}));
jest.mock("../../src/api/client", () => ({
  ApiError: class extends Error {},
  setSession: jest.fn(),
}));
jest.mock("../../src/lib/state", () => ({
  useApp: (selector: (s: { theme: string }) => unknown) =>
    selector({ theme: "light" }),
}));
test("email sign-in sends a link, shows return instructions and cancels the private ticket", async () => {
  await i18n.changeLanguage("en");
  const ticket = {
    flow_id: "f".repeat(64),
    poll_token: "a".repeat(64),
    expires_at: new Date(Date.now() + 600000).toISOString(),
  };
  (startBrowserSignIn as jest.Mock).mockResolvedValue(ticket);
  const user = userEvent.setup();
  await render(<BrowserSignInScreen />);
  await user.type(screen.getByLabelText("Email address"), "owner@example.com");
  await user.press(screen.getByRole("button", { name: "Send sign-in link" }));
  expect(startBrowserSignIn).toHaveBeenCalledWith("email", "owner@example.com");
  expect(
    await screen.findByText(/Open the sign-in link in your email/),
  ).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Cancel" }));
  expect(cancelBrowserSignIn).toHaveBeenCalledWith(ticket);
  expect(
    screen.getByRole("button", { name: "Send sign-in link" }),
  ).toBeOnTheScreen();
});
