import React from "react";
import { render, screen } from "@testing-library/react-native";
import { onlineManager } from "@tanstack/react-query";
import i18n from "../../src/i18n";
import { offlineError } from "../../src/api/online";
import { ErrorNotice, Txt } from "../../src/design/components";

function CachedScreen({ data }: { data?: string }) {
  const error = offlineError(onlineManager.isOnline(), !!data);
  return (
    <>
      {data && <Txt>{data}</Txt>}
      <ErrorNotice error={error} retry={() => {}} />
    </>
  );
}

afterEach(() => {
  onlineManager.setOnline(true);
});

test("no-cache offline state shows a disabled network action", async () => {
  await i18n.changeLanguage("en");
  onlineManager.setOnline(false);
  await render(<CachedScreen />);

  expect(
    screen.getByText("You're offline. Saved readings are still available."),
  ).toBeOnTheScreen();
  expect(
    screen.getByText("Connect to the internet to use this action."),
  ).toBeOnTheScreen();
  expect(screen.getByRole("button", { name: "Try again" })).toBeDisabled();
});

test("cached ready data remains visible offline without an error", async () => {
  await i18n.changeLanguage("en");
  onlineManager.setOnline(false);
  await render(<CachedScreen data="Cached ready reading" />);

  expect(screen.getByText("Cached ready reading")).toBeOnTheScreen();
  expect(screen.queryByText(i18n.t("errorOffline"))).toBeNull();
});
