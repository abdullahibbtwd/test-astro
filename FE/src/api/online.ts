import { useSyncExternalStore } from "react";
import { onlineManager } from "@tanstack/react-query";
import { NetworkError } from "./errors";
const offline = new NetworkError();
const subscribe = (listener: () => void) => onlineManager.subscribe(listener);
const snapshot = () => onlineManager.isOnline();
export function useOfflineError(hasData: boolean) {
  const online = useSyncExternalStore(subscribe, snapshot, snapshot);
  return !online && !hasData ? offline : undefined;
}
