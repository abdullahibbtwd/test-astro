import { useEffect, useRef, useState } from "react";
import { AppState, View, AccessibilityInfo } from "react-native";
import { useQueries } from "@tanstack/react-query";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { queryClient } from "../api/query";
import { request } from "../api/client";
import { pendingJobs } from "../api/resource";
import { useApp } from "./state";
import { Txt, Button, Choices } from "../design/components";
import { useTheme } from "../design/theme";
import type { Job } from "../../contracts/spec-types";
function routeFor(key: readonly unknown[]): string {
  if (key[0] === "generated" && key[2] === "natal")
    return `/chart/reading?profile=${key[3]}`;
  const path = typeof key[2] === "string" ? key[2] : "",
    url = new URL(path, "http://local"),
    parts = url.pathname.split("/"),
    profile = parts[2] ?? "",
    q = url.searchParams;
  if (url.pathname === "/home") return "/ahead/today";
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
    c = useTheme(),
    [active, setActive] = useState(AppState.currentState === "active"),
    [pending, setPending] = useState<
      { job: Job; key: readonly unknown[]; route: string }[]
    >([]),
    [toast, setToast] = useState<string>(),
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
      setToast(undefined);
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
            .filter(
              (j) =>
                !seen.current.has(j.job_id) &&
                Date.now() - Date.parse(j.created_at) < 600000,
            )
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
      refetchInterval: (q: { state: { data?: Job } }) =>
        Date.now() - Date.parse(p.job.created_at) >= 600000 ||
        q.state.data?.status === "succeeded" ||
        q.state.data?.status === "failed"
          ? false
          : 4000,
      refetchIntervalInBackground: false,
    })),
  });
  const statuses = polls.map((p) => p.data?.status).join();
  useEffect(() => {
    pending.forEach((p, i) => {
      const status = statuses.split(",")[i];
      if (
        (status !== "succeeded" && status !== "failed") ||
        seen.current.has(p.job.job_id)
      )
        return;
      seen.current.add(p.job.job_id);
      void queryClient.invalidateQueries({ queryKey: p.key, exact: true });
      if (status === "succeeded") {
        setToast(p.route);
        AccessibilityInfo.announceForAccessibility(t("reportReady"));
      }
    });
  }, [statuses, pending, t]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(undefined), 10000);
    return () => clearTimeout(timer);
  }, [toast]);
  if (!toast || !app.signedIn) return null;
  return (
    <View
      accessibilityLiveRegion="polite"
      style={{
        position: "absolute",
        left: 16,
        right: 16,
        bottom: 84,
        padding: 16,
        gap: 8,
        backgroundColor: c.surface,
        borderWidth: 1,
        borderColor: c.hair,
        borderRadius: 12,
        elevation: 8,
      }}
    >
      <Txt>{t("reportReady")}</Txt>
      <Choices>
        <Button
          secondary
          label={t("open")}
          onPress={() => {
            router.push(toast as never);
            setToast(undefined);
          }}
        />
        <Button
          secondary
          label={t("close")}
          onPress={() => setToast(undefined)}
        />
      </Choices>
    </View>
  );
}
