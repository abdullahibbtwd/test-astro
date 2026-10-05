import { removeDeletedReference } from "../../src/api/deleted-cache";
import { queryClient } from "../../src/api/query";
jest.mock("../../src/api/client", () => ({ ApiError: class extends Error {} }));
import { BottomSheetModal } from "@gorhom/bottom-sheet";
import { Sheet } from "../../src/design/components/Sheet";
import {
  deferDelete,
  useDeletedItems,
} from "../../src/design/components/deferred-delete";
import { shouldNotifyJob } from "../../src/lib/job-notification";
import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react-native";
import { AccessibilityInfo, AppState, StyleSheet } from "react-native";
import { Segmented } from "../../src/design/components/Segmented";
import { Snackbar } from "../../src/design/components/Snackbar";
import {
  showSnackbar,
  dismissSnackbar,
  useSnackbar,
} from "../../src/design/components/snackbar-store";
import "../../src/i18n";
afterEach(() => {
  dismissSnackbar("timeout");
  jest.useRealTimers();
});
test("four Turkish segments stay equal width, nowrap, accessible and selectable at large fonts", async () => {
  const change = jest.fn();
  await render(
    <Segmented
      value="0"
      onChange={change}
      items={["Bugün", "Ay", "Yıl", "Takvim"].map((label, i) => ({
        value: String(i),
        label,
      }))}
    />,
  );
  expect(
    StyleSheet.flatten(screen.getByTestId("segmented").props.style).flexWrap,
  ).toBe("nowrap");
  const tabs = screen.getAllByRole("tab");
  expect(tabs).toHaveLength(4);
  for (const tab of tabs)
    expect(StyleSheet.flatten(tab.props.style).flex).toBe(1);
  expect(tabs[0]).toBeSelected();
  expect(screen.getByText("Takvim").props.maxFontSizeMultiplier).toBe(2);
  expect(screen.getByText("Takvim").props.numberOfLines).toBe(1);
  await fireEvent.press(tabs[3]);
  expect(change).toHaveBeenCalledWith("3");
});
test("replacement settles the previous message once; undo never commits deletion", () => {
  const commit = jest.fn(),
    undo = jest.fn();
  showSnackbar("First", { onDismiss: commit });
  const id = showSnackbar("Deleted", {
    action: { label: "Undo", onPress: undo },
    onDismiss: (reason) => {
      if (reason !== "action") commit();
    },
  });
  expect(commit).toHaveBeenCalledWith("replaced");
  commit.mockClear();
  dismissSnackbar("action", id);
  dismissSnackbar("timeout", id);
  expect(undo).toHaveBeenCalledTimes(1);
  expect(commit).not.toHaveBeenCalled();
  expect(useSnackbar.getState().current).toBeNull();
});
test("snackbar timeout commits exactly once after five seconds", async () => {
  jest.useFakeTimers();
  AppState.currentState = "active";
  jest
    .spyOn(AccessibilityInfo, "isScreenReaderEnabled")
    .mockResolvedValue(false);
  const commit = jest.fn();
  await render(<Snackbar />);
  await act(async () => {
    showSnackbar("Deleted", { onDismiss: commit });
  });
  await act(async () => {
    jest.advanceTimersByTime(4999);
  });
  expect(commit).not.toHaveBeenCalled();
  await act(async () => {
    jest.advanceTimersByTime(1);
  });
  expect(commit).toHaveBeenCalledTimes(1);
  expect(commit).toHaveBeenCalledWith("timeout");
});

test("short jobs and the current report never notify; another person does", () => {
  expect(shouldNotifyJob("calendar_text", "/calendar/item/1", "/map", {})).toBe(
    false,
  );
  expect(
    shouldNotifyJob(
      "natal_reading",
      "/chart/reading?profile=p",
      "/chart/reading",
      { profile: "p" },
    ),
  ).toBe(false);
  expect(
    shouldNotifyJob(
      "natal_reading",
      "/chart/reading?profile=p",
      "/chart",
      {},
      "p",
    ),
  ).toBe(false);
  expect(
    shouldNotifyJob("natal_reading", "/chart/reading?profile=p", "/map", {}),
  ).toBe(true);
  expect(
    shouldNotifyJob(
      "natal_reading",
      "/chart/reading?profile=p",
      "/chart/reading",
      { profile: "other" },
    ),
  ).toBe(true);
});
test("Undo sends zero deletes and timeout sends one, including after navigation", async () => {
  const remove = jest.fn(async () => {}),
    labels = { removed: "Removed", undo: "Undo", failed: "Failed" };
  deferDelete("report:one", remove, labels);
  expect(useDeletedItems.getState().hidden["report:one"]).toBe(true);
  dismissSnackbar("action");
  expect(remove).not.toHaveBeenCalled();
  expect(useDeletedItems.getState().hidden["report:one"]).toBeUndefined();
  deferDelete("report:one", remove, labels);
  const id = useSnackbar.getState().current?.id;
  dismissSnackbar("timeout", id);
  dismissSnackbar("timeout", id);
  await Promise.resolve();
  expect(remove).toHaveBeenCalledTimes(1);
});
test("failed deletion restores the visible record", async () => {
  deferDelete(
    "report:failed",
    async () => {
      throw new Error("offline");
    },
    { removed: "Removed", undo: "Undo", failed: "Try again" },
  );
  dismissSnackbar("timeout");
  await Promise.resolve();
  await Promise.resolve();
  expect(useDeletedItems.getState().hidden["report:failed"]).toBeUndefined();
  expect(useSnackbar.getState().current?.message).toBe("Try again");
});

test("closed sheets are never dismissed before their first presentation", async () => {
  const present = jest.spyOn(BottomSheetModal.prototype, "present"),
    dismiss = jest.spyOn(BottomSheetModal.prototype, "dismiss");
  const props = { title: "Legend", onClose: jest.fn(), children: null };
  const view = await render(<Sheet {...props} open={false} />);
  expect(dismiss).not.toHaveBeenCalled();
  await view.rerender(<Sheet {...props} open />);
  expect(present).toHaveBeenCalledTimes(1);
  await view.rerender(<Sheet {...props} open={false} />);
  expect(dismiss).toHaveBeenCalledTimes(1);
  present.mockRestore();
  dismiss.mockRestore();
});
test("screen reader keeps Undo available beyond five seconds", async () => {
  jest.useFakeTimers();
  AppState.currentState = "active";
  jest
    .spyOn(AccessibilityInfo, "isScreenReaderEnabled")
    .mockResolvedValue(true);
  const commit = jest.fn();
  await render(<Snackbar />);
  await act(async () => {
    showSnackbar("Removed", { onDismiss: commit });
  });
  await act(async () => {
    jest.advanceTimersByTime(30000);
  });
  expect(commit).not.toHaveBeenCalled();
});

test("confirmed deletion removes all cached filtered references without touching other rows", () => {
  const key = ["reports", "en", "natal"];
  queryClient.setQueryData(key, {
    pages: [{ items: [{ report_id: "removed" }, { report_id: "keep" }] }],
    pageParams: [""],
  });
  removeDeletedReference("report_id", "removed");
  expect(queryClient.getQueryData(key)).toEqual({
    pages: [{ items: [{ report_id: "keep" }] }],
    pageParams: [""],
  });
  queryClient.clear();
});
