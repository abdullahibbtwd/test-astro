import { todayLocal } from "./dates";
import { mockToday } from "../api/client";
import { showSnackbar } from "../design/components/Snackbar";
import { shouldNotifyJob } from "./job-notification";
import { useEffect, useRef, useState } from "react";
import { AppState } from "react-native";
import { useQueries } from "@tanstack/react-query";
import { router, usePathname, useGlobalSearchParams } from "expo-router";
import { useTranslation } from "react-i18next";
import { queryClient } from "../api/query";
import { ApiError } from "../api/errors";
import { request } from "../api/client";
import { jobAgeMs } from "../api/job-timing";
import { pollingDelay } from "../api/job-policy";
import { pendingJobs } from "../api/resource";
import { useApp } from "./state";
import type { BirthProfile, Job } from "../../contracts/spec-types";
function routeFor(key: readonly unknown[]): string {
  if (key[0] === "generated" && key[2] === "natal")
    return `/chart/reading?profile=${key[3]}`;
  const path = typeof key[2] === "string" ? key[2] : "",
    url = new URL(path, "http://local"),
    parts = url.pathname.split("/"),
    profile = parts[2] ?? "",
    q = url.searchParams;
  if (url.pathname === "/home") return "/(tabs)/ahead?view=day";
  if (path.startsWith("/compatibility/")) return `/match/${parts[2]}`;
  if (parts[3] === "acg") {
    if (parts[4] === "places")
      return `/map/place/${parts[5]}?profile=${profile}&goal=${q.get("focus_goal") ?? ""}`;
    if (parts[4] === "countries" || parts[4] === "regions")
      return `/map/area/${parts[5]}?profile=${profile}&kind=${parts[4] === "countries" ? "country" : "region"}`;
    if (parts[4] === "recommendations")
      return `/map/recommend/result?profile=${profile}&request=${encodeURIComponent(String(key[3] ?? "{}"))}`;
    return `/(tabs)/map?profile=${profile}`;
  }
  if (parts[3] === "calendar" && parts[4] === "items")
    return `/calendar/item/${parts[5]}?profile=${profile}`;
  if (parts[3] === "best-days" && parts[4] && parts[5])
    return `/best-days/${parts[4]}/${parts[5]}?profile=${profile}`;
  if (parts[3] === "solar-return")
    return `/solar-return/${q.get("year")}?profile=${profile}`;
  return `/(tabs)/ahead?profile=${profile}&view=${parts[4] ?? "day"}&date=${q.get("date") ?? ""}&month=${q.get("month") ?? q.get("from") ?? ""}`;
}
export function JobLifecycle() {
  const app = useApp(),
    { t } = useTranslation(),
    pathname = usePathname(),
    params = useGlobalSearchParams(),
    [active, setActive] = useState(AppState.currentState === "active"),
    [pending, setPending] = useState<
      { job: Job; key: readonly unknown[]; route: string }[]
    >([]),
    seen = useRef(new Set<string>());
  useEffect(() => {
    const sub = AppState.addEventListener("change", (s) =>
      setActive(s === "active"),
    );
    return () => sub.remove();
  }, []);
  useEffect(() => {
    if (!app.signedIn) {
      setPending([]);
      seen.current.clear();
      return;
    }
    const scan = () => {
      const values = queryClient
        .getQueryCache()
        .getAll()
        .filter(
          (q) =>
            (q.queryKey[0] === "resource" || q.queryKey[0] === "generated") &&
            q.queryKey[1] === app.language,
        )
        .flatMap((q) => {
          const data = q.state.data;
          const jobs =
            data &&
            typeof data === "object" &&
            "kind" in data &&
            data.kind === "pending" &&
            "job" in data
              ? [data.job as Job]
              : pendingJobs(data);
          return jobs
            .filter((j) => !seen.current.has(j.job_id))
            .map((job) => ({
              job,
              key: q.queryKey,
              route: routeFor(q.queryKey),
            }));
        });
      const unique = [
        ...new Map(values.map((v) => [v.job.job_id, v])).values(),
      ];
      setPending((old) =>
        old.map((x) => x.job.job_id).join() ==
        unique.map((x) => x.job.job_id).join()
          ? old
          : unique,
      );
    };
    scan();
    let mounted = true,
      queued = false;
    const unsubscribe = queryClient.getQueryCache().subscribe((event) => {
      // Observer changes can fire inside useQueries render. Only react to parent data changes,
      // and defer React updates until that render has finished.
      if (
        !["resource", "generated"].includes(String(event.query.queryKey[0])) ||
        (event.type !== "removed" &&
          !(event.type === "updated" && event.action.type === "success"))
      )
        return;
      if (queued) return;
      queued = true;
      void Promise.resolve().then(() => {
        queued = false;
        if (mounted) scan();
      });
    });
    return () => {
      mounted = false;
      unsubscribe();
    };
  }, [app.signedIn, app.language]);
  const polls = useQueries({
    queries: pending.map((p) => ({
      queryKey: ["job", app.language, p.job.job_id],
      queryFn: () => request<Job>("GET", `/jobs/${p.job.job_id}`, "Job"),
      enabled: active && app.signedIn,
      refetchInterval: (q: {
        state: { data?: Job; dataUpdateCount: number; error: unknown };
      }) =>
        (q.state.error instanceof ApiError && q.state.error.status === 404) ||
        q.state.data?.status === "succeeded" ||
        q.state.data?.status === "failed"
          ? false
          : pollingDelay(
              Math.max(0, q.state.dataUpdateCount - 1),
              jobAgeMs(p.job),
            ),
      refetchOnMount: "always" as const,
      refetchIntervalInBackground: false,
    })),
  });
  const statuses = polls
    .map((p) =>
      p.error instanceof ApiError && p.error.status === 404
        ? "missing"
        : p.data?.status,
    )
    .join();
  useEffect(() => {
    pending.forEach((p, i) => {
      const status = statuses.split(",")[i];
      if (
        (status !== "succeeded" &&
          status !== "failed" &&
          status !== "missing") ||
        seen.current.has(p.job.job_id)
      )
        return;
      seen.current.add(p.job.job_id);
      void queryClient.invalidateQueries({
        queryKey: p.key,
        exact: true,
        refetchType: "none",
      });
      if (
        status !== "missing" &&
        shouldNotifyJob(
          p.job.kind,
          p.route,
          pathname,
          {
            month: todayLocal(app.me?.current_place?.tz, mockToday).slice(0, 7),
            ...params,
          },
          app.activeProfileId ?? app.me?.self_profile_id,
        )
      ) {
        const target = new URL(p.route, "http://local"),
          profileId = target.searchParams.get("profile");
        const profiles = queryClient.getQueryData<BirthProfile[]>([
          "profiles",
          app.language,
          "/profiles",
        ]);
        const parent = queryClient.getQueryData(p.key) as
          | {
              place?: { name?: string };
              area?: { name?: string };
              title?: string;
            }
          | undefined;
        const label =
          parent?.place?.name ??
          parent?.area?.name ??
          profiles?.find((person) => person.profile_id === profileId)?.label ??
          t("yourReport");
        showSnackbar(
          status === "succeeded"
            ? t(`ready_${p.job.kind}`, { label })
            : t("reportCouldNotPrepare", {
                kind: t(`kind_${p.job.kind}`),
                label,
              }),
          {
            action: {
              label: t("open"),
              onPress: () => router.push(p.route as never),
            },
          },
        );
      }
    });
  }, [
    statuses,
    pending,
    t,
    pathname,
    params,
    app.activeProfileId,
    app.me?.self_profile_id,
    app.me?.current_place?.tz,
    app.language,
  ]);
  return null;
}
