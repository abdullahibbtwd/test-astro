import { jest } from "@jest/globals";
jest.mock("../../src/lib/state", () => ({
  useApp: (select: (value: unknown) => unknown = (value) => value) =>
    select({ theme: "light", language: "en", recent: [], update: jest.fn() }),
}));
jest.mock("expo-router", () => ({
  usePathname: () => "/map",
  useGlobalSearchParams: () => ({}),
  useFocusEffect: (callback: () => void) =>
    require("react").useEffect(callback, [callback]),
  useSegments: () => ["(tabs)"],
  Stack: { Screen: () => null },
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
  ChevronLeft: "ChevronLeft",
  X: "X",
  Maximize2: "Maximize2",
  ChevronRight: "ChevronRight",
}));

jest.mock("@gorhom/bottom-sheet", () => require("@gorhom/bottom-sheet/mock"));
jest.mock("react-native-reanimated", () => ({
  ReduceMotion: { System: "system" },
}));
