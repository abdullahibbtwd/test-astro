import { create } from "zustand";
export type DismissReason = "timeout" | "action" | "swipe" | "replaced";
export type SnackbarMessage = {
  id: number;
  message: string;
  action?: { label: string; onPress: () => void };
  onDismiss?: (reason: DismissReason) => void;
};
let nextId = 0;
export const useSnackbar = create<{ current: SnackbarMessage | null }>(() => ({
  current: null,
}));
export function dismissSnackbar(
  reason: DismissReason,
  id = useSnackbar.getState().current?.id,
) {
  const current = useSnackbar.getState().current;
  if (!current || current.id !== id) return;
  useSnackbar.setState({ current: null });
  if (reason === "action") current.action?.onPress();
  current.onDismiss?.(reason);
}
export function showSnackbar(
  message: string,
  options: Omit<SnackbarMessage, "message" | "id"> = {},
) {
  dismissSnackbar("replaced");
  const id = ++nextId;
  useSnackbar.setState({ current: { id, message, ...options } });
  return id;
}

export const useSnackbarLayout = create<{ footerHeight: number }>(() => ({
  footerHeight: 0,
}));
