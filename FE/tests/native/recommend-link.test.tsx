import React from "react";
import { render, screen } from "@testing-library/react-native";
import i18n from "../../src/i18n";
import { useApi } from "../../src/api/resource";
import RecommendResultScreen from "../../src/features/map/RecommendResultScreen";
let mockRequest = "broken-json";
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ request: mockRequest }),
  router: { canGoBack: () => true, back: jest.fn() },
}));
jest.mock("../../src/api/resource", () => ({
  useApi: jest.fn(() => ({ isPending: true, data: undefined })),
}));
jest.mock("../../src/api/client", () => ({ ApiError: class extends Error {} }));
jest.mock("../../src/features/shared/useProfile", () => ({
  useProfile: () => ({ id: "p" }),
}));
jest.mock("../../src/features/map/MapCanvas", () => ({
  MapCanvas: () => null,
  planetColors: {},
}));
test.each(["broken-json", JSON.stringify({ goal: "invented" })])(
  "invalid recommendation link shows an error without a request: %s",
  async (value) => {
    mockRequest = value;
    await i18n.changeLanguage("en");
    await render(<RecommendResultScreen />);
    expect(screen.getByText(i18n.t("errorServer"))).toBeOnTheScreen();
    expect(screen.queryByLabelText("Loading")).toBeNull();
    expect(useApi).toHaveBeenCalledWith(
      "/profiles/p/acg/recommendations",
      "Recommendation",
      false,
      undefined,
    );
  },
);

jest.mock("../../src/lib/flags", () => ({ useFlags: () => ({}) }));
