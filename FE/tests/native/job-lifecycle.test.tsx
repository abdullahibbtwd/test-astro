import { jobWatcher } from "../../src/api/job-watcher";
import { Snackbar } from "../../src/design/components/Snackbar";
import { dismissSnackbar } from "../../src/design/components/snackbar-store";
import React from "react";
import { AppState } from "react-native";
import { render, screen, waitFor, act } from "@testing-library/react-native";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "../../src/api/query";
import { JobLifecycle } from "../../src/lib/JobLifecycle";
import i18n from "../../src/i18n";
jest.mock("../../src/lib/state", () => ({
  useApp: (select = (v: unknown) => v) =>
    select({ signedIn: true, language: "en", theme: "light" }),
}));
jest.mock("../../src/api/client", () => ({
  ApiError: class extends Error {},
  request: jest.fn(async () => ({ status: "succeeded" })),
}));
test("completion notifier ignores render-time observer events and opens the completed parent", async () => {
  Object.defineProperty(AppState, "currentState", {
    value: "active",
    configurable: true,
  });
  await i18n.changeLanguage("en");
  jobWatcher.clear();
  queryClient.clear();
  queryClient.setDefaultOptions({
    queries: { gcTime: Infinity, retry: false },
  });
  queryClient.setQueryData(
    ["profiles", "en", "/profiles"],
    [{ profile_id: "self", label: "Test person" }],
  );
  const key = ["resource", "en", "/profiles/self/forecast/year?from=2026-09"];
  queryClient.setQueryData(key, {
    reading: {
      status: "pending",
      job: {
        kind: "year_reading",
        job_id: "regression",
        created_at: new Date().toISOString(),
      },
    },
  });
  jest.spyOn(queryClient, "invalidateQueries").mockResolvedValue(undefined);
  const view = await render(
    <QueryClientProvider client={queryClient}>
      <JobLifecycle />
      <Snackbar />
    </QueryClientProvider>,
  );
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Open" })).toBeOnTheScreen(),
  );
  expect(
    screen.getByText("Your yearly forecast for Test person is ready"),
  ).toBeOnTheScreen();
  await act(async () => {
    for (let i = 0; i < 30; i++)
      queryClient.getQueryCache().notify({
        type: "observerOptionsUpdated",
        query: queryClient.getQueryCache().find({ queryKey: key })!,
        observer: {} as never,
      });
  });
  expect(screen.getByRole("button", { name: "Open" })).toBeOnTheScreen();
  expect(queryClient.invalidateQueries).toHaveBeenCalledWith({
    queryKey: key,
    exact: true,
    refetchType: "none",
  });
  await view.unmount();
  jobWatcher.clear();
  queryClient.clear();
});

afterEach(() => {
  dismissSnackbar("timeout");
  jobWatcher.clear();
  queryClient.clear();
  jest.restoreAllMocks();
});
