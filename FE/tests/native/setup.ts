import { jest } from "@jest/globals";
jest.mock("../../src/lib/state", () => ({
  useApp: (select: (value: unknown) => unknown = (value) => value) =>
    select({ theme: "light", language: "en", recent: [], update: jest.fn() }),
}));
jest.mock("expo-router", () => ({
  router: {
    push: jest.fn(),
    back: jest.fn(),
    replace: jest.fn(),
    canGoBack: () => true,
  },
}));
jest.mock(
  "react-native-safe-area-context",
  () => require("react-native-safe-area-context/jest/mock").default,
);

jest.mock("lucide-react-native", () => ({
  ArrowLeft: "ArrowLeft",
  ChevronRight: "ChevronRight",
}));
