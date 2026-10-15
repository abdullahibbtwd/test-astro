import { create } from "zustand";
import { showSnackbar } from "./snackbar-store";
export const useDeletedItems = create<{ hidden: Record<string, boolean> }>(
  () => ({ hidden: {} }),
);
function reveal(key: string) {
  const hidden = { ...useDeletedItems.getState().hidden };
  delete hidden[key];
  useDeletedItems.setState({ hidden });
}
/** Keep the server record until the snackbar is settled without Undo, even across navigation. */
export function deferDelete(
  key: string,
  commit: () => Promise<unknown>,
  labels: { removed: string; undo: string; failed: string },
) {
  if (useDeletedItems.getState().hidden[key]) return;
  useDeletedItems.setState((s) => ({ hidden: { ...s.hidden, [key]: true } }));
  showSnackbar(labels.removed, {
    action: { label: labels.undo, onPress: () => reveal(key) },
    onDismiss: (reason) => {
      if (reason === "action") return;
      void commit()
        .then(() => reveal(key))
        .catch(() => {
          reveal(key);
          showSnackbar(labels.failed);
        });
    },
  });
}
