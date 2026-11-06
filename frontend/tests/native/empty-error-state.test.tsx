import React from "react";
import { render, screen, userEvent } from "@testing-library/react-native";
import "../../src/i18n";
import i18n from "../../src/i18n";
import { onlineManager } from "@tanstack/react-query";
import {
  EmptyState,
  StandardErrorState,
} from "../../src/design/components";
import { NetworkError, ApiError } from "../../src/api/errors";

beforeEach(async () => {
  await i18n.changeLanguage("en");
  onlineManager.setOnline(true);
});

test("EmptyState renders translated title and optional action", async () => {
  const onAction = jest.fn();
  const user = userEvent.setup();
  await render(
    <EmptyState
      titleKey="emptyReports"
      actionKey="retry"
      onAction={onAction}
    />,
  );
  expect(
    screen.getByText("Readings you open are saved here."),
  ).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Try again" }));
  expect(onAction).toHaveBeenCalled();
});

test("StandardErrorState shows offline banner when cachedOffline", async () => {
  onlineManager.setOnline(false);
  await render(<StandardErrorState cachedOffline />);
  expect(
    screen.getByText("Offline · showing saved information"),
  ).toBeOnTheScreen();
});

test("StandardErrorState maps NetworkError to offline retry copy", async () => {
  await render(
    <StandardErrorState error={new NetworkError()} retry={() => {}} />,
  );
  expect(
    screen.getByText("You're offline. Saved readings are still available."),
  ).toBeOnTheScreen();
  expect(screen.getByRole("button", { name: "Try again" })).toBeOnTheScreen();
});

test("StandardErrorState maps rate limit with countdown action", async () => {
  await render(
    <StandardErrorState
      error={new ApiError(429, "rate_limited", 3)}
      retry={() => {}}
    />,
  );
  expect(
    screen.getByText("Daily reading limit reached. Try again tomorrow."),
  ).toBeOnTheScreen();
});
