import { create } from "zustand";
export const useCapabilities = create<{
  unavailable: Record<string, boolean>;
  mark: (flag: string) => void;
}>((set) => ({
  unavailable: {},
  mark: (flag) =>
    set((s) => ({ unavailable: { ...s.unavailable, [flag]: true } })),
}));
