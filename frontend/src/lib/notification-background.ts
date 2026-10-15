import * as TaskManager from "expo-task-manager";
import * as BackgroundTask from "expo-background-task";
import { initStorage } from "./storage";
import { restoreSession } from "../api/client";
import { useApp } from "./state";
import { synchronizeNotifications } from "./notifications";
export const notificationTask = "astrology-notification-sync";
TaskManager.defineTask(notificationTask, async () => {
  try {
    await initStorage();
    useApp.getState().hydrate();
    await restoreSession();
    const state = useApp.getState();
    if (state.me && state.signedIn)
      await synchronizeNotifications(state.me, state.language);
    return BackgroundTask.BackgroundTaskResult.Success;
  } catch {
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
});
