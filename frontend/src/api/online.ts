import { useSyncExternalStore } from "react";
import { onlineManager } from "@tanstack/react-query";
import { NetworkError } from "./errors";
const offline = new NetworkError();
const subscribe = (listener: () => void) => onlineManager.subscribe(listener);
const snapshot = () => onlineManager.isOnline();
export function useOnline() {
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}
export function useOfflineError(hasData: boolean) {
  const online = useOnline();
  return !online && !hasData ? offline : undefined;
}
