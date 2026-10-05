import { resolveRoute } from "./routes";
import { todayLocal } from "./dates";
import { mockToday } from "../api/client";
import { showSnackbar } from "../design/components/Snackbar";
import { shouldNotifyJob } from "./job-notification";
import { useEffect, useRef } from "react";
import { AppState } from "react-native";
import { router, usePathname, useGlobalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { queryClient } from "../api/query";
import {
  jobWatcher,
  onJobComplete,
  registerParentJobs,
} from "../api/job-watcher";
import { routeFor } from "./job-route";
import { useApp } from "./state";
import type { BirthProfile } from "../../contracts/spec-types";
export function JobLifecycle() {
  const app = useApp(),
    { t } = useTranslation(),
    pathname = usePathname(),
    params = useGlobalSearchParams();
  const latest = useRef({ app, t, pathname, params });
  useEffect(() => {
    latest.current = { app, t, pathname, params };
  }, [app, t, pathname, params]);
  useEffect(() => {
    if (!app.signedIn) {
      jobWatcher.clear();
      return;
    }
    const stop = onJobComplete((event, lang) => {
      const { app, t, pathname, params } = latest.current;
      if (lang !== app.language || event.missing) return;
      const key = event.parents[0];
      if (!key) return;
      const route = routeFor(key);
      if (
        !shouldNotifyJob(
          event.job.kind,
          route,
          pathname,
          {
            month: todayLocal(app.me?.current_place?.tz, mockToday).slice(0, 7),
            ...params,
          },
          app.activeProfileId ?? app.me?.self_profile_id,
        )
      )
        return;
      const profileId = new URL(route, "http://local").searchParams.get(
        "profile",
      );
      const profiles = queryClient.getQueryData<BirthProfile[]>([
        "profiles",
        lang,
        "/profiles",
      ]);
      const parent = queryClient.getQueryData(key) as
        { place?: { name?: string }; area?: { name?: string } } | undefined;
      const label =
        parent?.place?.name ??
        parent?.area?.name ??
        profiles?.find((p) => p.profile_id === profileId)?.label ??
        t("yourReport");
      showSnackbar(
        event.job.status === "succeeded"
          ? t(`ready_${event.job.kind}`, { label })
          : t("reportCouldNotPrepare", {
              kind: t(`kind_${event.job.kind}`),
              label,
            }),
        {
          action: {
            label: t("open"),
            onPress: () => router.push(resolveRoute(route)),
          },
        },
      );
    });
    // One hydration scan. Later cache updates register only their own parent.
    for (const q of queryClient.getQueryCache().getAll())
      registerParentJobs(q.queryKey, q.state.data);
    const unsubscribe = queryClient.getQueryCache().subscribe((event) => {
      if (
        event.type === "added" ||
        (event.type === "updated" && event.action.type === "success")
      )
        registerParentJobs(event.query.queryKey, event.query.state.data);
    });
    jobWatcher.setActive(AppState.currentState === "active");
    const sub = AppState.addEventListener("change", (state) =>
      jobWatcher.setActive(state === "active"),
    );
    return () => {
      stop();
      unsubscribe();
      sub.remove();
      jobWatcher.setActive(false);
    };
  }, [app.signedIn]);
  return null;
}
