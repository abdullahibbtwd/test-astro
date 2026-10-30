import { queryClient } from "../../src/api/query";
import { jobWatcher } from "../../src/api/job-watcher";
import React from "react";
import { AppState, Text } from "react-native";
import { render, screen, waitFor, act } from "@testing-library/react-native";
import { QueryClientProvider } from "@tanstack/react-query";
import { ErrorNotice } from "../../src/design/components";
import { JobProgress } from "../../src/design/components/JobProgress";
import { useGenerated } from "../../src/api/jobs";
import { useParentJobs } from "../../src/api/use-parent-jobs";
import { ApiError, NetworkError } from "../../src/api/errors";
import { request } from "../../src/api/client";
import i18n from "../../src/i18n";
let mockFocusCleanup: (() => void) | undefined;
jest.mock("expo-router", () => ({
  Stack: { Screen: () => null },
  router: { back: jest.fn() },
  useFocusEffect: (callback: () => (() => void) | void) => {
    require("react").useEffect(() => {
      // Keep the cleanup local so an earlier screen unmount cannot blur a later one.
      const cleanup = callback();
      mockFocusCleanup =
        typeof cleanup === "function" ? cleanup : undefined;
      return () => {
        cleanup?.();
        if (mockFocusCleanup === cleanup) mockFocusCleanup = undefined;
      };
    }, [callback]);
  },
}));
jest.mock("../../src/api/client", () => ({ request: jest.fn() }));
const job = {
  job_id: "old-job",
  kind: "natal_reading",
  status: "running",
  created_at: new Date(Date.now() - 30 * 60_000).toISOString(),
  updated_at: new Date().toISOString(),
  eta_seconds: null,
  error: null,
  stages: [],
};
const client = () => {
  queryClient.clear();
  queryClient.setDefaultOptions({
    queries: { retry: false, gcTime: Infinity },
  });
  return queryClient;
};
afterEach(() => {
  jobWatcher.clear();
  queryClient.clear();
  jest.useRealTimers();
});
beforeEach(async () => {
  jest.clearAllMocks();
  jobWatcher.clear();
  jobWatcher.setActive(true);
  Object.defineProperty(AppState, "currentState", {
    value: "active",
    configurable: true,
  });
  await i18n.changeLanguage("en");
});
test.each([
  [new NetworkError(), "errorOffline", true],
  [{ code: "busy" }, "errorBusy", false],
  [{ status: 503 }, "errorServer", true],
] as const)("notice %s has the correct action", async (error, key, retry) => {
  await render(<ErrorNotice error={error} retry={jest.fn()} />);
  expect(screen.getByText(i18n.t(key))).toBeOnTheScreen();
  expect(!!screen.queryByRole("button", { name: i18n.t("retry") })).toBe(retry);
});
test("429 countdown disables retry until the deadline", async () => {
  jest.useFakeTimers();
  await render(
    <ErrorNotice
      error={new ApiError(429, "rate_limited", 3)}
      retry={jest.fn()}
    />,
  );
  expect(screen.getByRole("button")).toBeDisabled();
  await act(async () => {
    jest.advanceTimersByTime(3000);
  });
  expect(screen.getByRole("button", { name: i18n.t("retry") })).toBeEnabled();
  jest.useRealTimers();
});
test("a thirty-minute pending job shows very slow and never Retry", async () => {
  await render(<JobProgress job={job as never} retry={jest.fn()} />);
  expect(screen.getByText(i18n.t("verySlow"))).toBeOnTheScreen();
  expect(screen.queryByRole("button", { name: i18n.t("retry") })).toBeNull();
});
function Reading() {
  const result = useGenerated<{ text: string }>(["test"], "/reading", "Object");
  return <Text>{result.state}</Text>;
}
jest.mock("../../src/api/zod", () => ({
  validate: (_name: string, value: unknown) => value,
}));
test.each(["succeeded", "missing"])(
  "hydrated old job reconciles %s once using a normal parent GET",
  async (outcome) => {
    const q = client();
    q.setQueryData(["generated", "en", "test"], { kind: "pending", job });
    jest.mocked(request).mockImplementation(async (_method, path) => {
      if (path.startsWith("/jobs/old-job")) {
        if (outcome === "missing") throw new ApiError(404, "not_found");
        return { ...job, status: "succeeded" };
      }
      return { text: "Ready" };
    });
    const view = await render(
      <QueryClientProvider client={q}>
        <Reading />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("ready")).toBeOnTheScreen());
    expect(
      jest.mocked(request).mock.calls.filter((c) => c[1] === "/reading"),
    ).toHaveLength(1);
    expect(
      jest.mocked(request).mock.calls.some((c) => c[1].includes("retry=true")),
    ).toBe(false);
    await view.unmount();
    q.clear();
  },
);
function Waiting({ refresh }: { refresh: () => void }) {
  useParentJobs(
    { status: "failed", error: { code: "busy", blocking_job_id: "blocker" } },
    null,
    JSON.stringify(["resource", "en", "B"]),
    true,
    refresh,
  );
  return null;
}
test.each([true, false])(
  "blocker completion resumes B only if it remains focused: %s",
  async (focused) => {
    const q = client(),
      refresh = jest.fn();
    let finish!: (v: any) => void;
    jest.mocked(request).mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    const view = await render(
      <QueryClientProvider client={q}>
        <Waiting refresh={refresh} />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(request).toHaveBeenCalled());
    if (!focused)
      await act(async () => {
        mockFocusCleanup?.();
      });
    await act(async () => {
      finish({ ...job, status: "failed" });
    });
    if (focused) await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
    else expect(refresh).not.toHaveBeenCalled();
    await view.unmount();
    q.clear();
  },
);
